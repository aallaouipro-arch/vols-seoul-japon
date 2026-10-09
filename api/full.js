/**
 * Liste complète Google Flights (« Afficher plus de vols »), via un vrai navigateur.
 *
 * La 1re page de Google (lue directement par l'API Python) ne contient que 9 à 25 vols. Le reste
 * est chargé par la page elle-même (RPC GetShoppingResults), avec un jeton anti-robot que seul le
 * JavaScript de Google sait produire : on ouvre donc la recherche dans Chromium, on clique sur
 * « Afficher plus de vols » et on renvoie la réponse de Google telle quelle. L'API Python la
 * lit avec le même code que la 1re page (tracker/gflights.py).
 *
 * Appelée uniquement par l'API (Authorization: Bearer CRON_SECRET).
 * En local : CHROME_PATH=chemin/vers/chrome.exe (ou msedge.exe).
 */
import chromium from "@sparticuz/chromium";
import puppeteer from "puppeteer-core";

const CONSENT = { SOCS: "CAESHAgBEhJnd3NfMjAyMzA4MTAtMF9SQzIaAmVuIAEaBgiAo_CmBg", CONSENT: "YES+cb" };
const MORE_RE = /plus de vols/i;

let launching = null;

// Le navigateur reste ouvert entre deux appels tant que l'instance vit (démarrage ~1 s au lieu de ~4 s)
async function browser() {
  const cur = launching && (await launching.catch(() => null));
  if (cur?.connected) return cur;
  const local = process.env.CHROME_PATH;
  launching = puppeteer.launch(
    local
      ? { executablePath: local, headless: true }
      : {
          args: await puppeteer.defaultArgs({ args: chromium.args, headless: "shell" }),
          executablePath: await chromium.executablePath(),
          headless: "shell",
        },
  );
  return launching;
}

// Réponse en flux : ")]}'" puis des blocs « taille + retour à la ligne + [["wrb.fr",null,"<json>"]] ». Google renvoie
// plusieurs versions de la liste au fil de l'arrivée des prix : on garde la dernière complète
// (une ligne coupée en fin de flux est ignorée).
function lastPayload(text) {
  let best = null;
  for (const line of text.split("\n")) {
    if (!line.startsWith('[["wrb.fr"')) continue;
    try {
      for (const row of JSON.parse(line)) {
        if (row[0] !== "wrb.fr" || !row[2]) continue;
        const p = JSON.parse(row[2]);
        if (Array.isArray(p[3]) && p[3][0]?.length) best = row[2];
      }
    } catch {
      // bloc incomplet
    }
  }
  return best;
}

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

// État de la page : "error" (« Une erreur s'est produite »), "more" (bouton présent), "list" (vols sans bouton)
const pageState = (re) => {
  if (/Une erreur s'est produite/.test(document.body?.innerText || "")) return "error";
  const more = [...document.querySelectorAll("button, [role=button]")].some((e) => new RegExp(re, "i").test(`${e.textContent} ${e.getAttribute("aria-label") || ""}`));
  if (more) return "more";
  return document.querySelector("li.pIav2d") ? "list" : "";
};

async function attempt(ctx, url) {
  const page = await ctx.newPage();
  try {
    // Repartir de cookies vierges (consentement seulement) à chaque essai
    const cdp = await page.createCDPSession();
    await cdp.send("Network.clearBrowserCookies");
    await cdp.detach();
    await ctx.setCookie(...Object.entries(CONSENT).map(([name, value]) => ({ name, value, domain: ".google.com", path: "/" })));
    return await readFullList(page, url);
  } finally {
    await page.close().catch(() => {});
  }
}

async function readFullList(page, url) {
  const t = { start: Date.now() };
  await page.setViewport({ width: 1366, height: 900 });
  await page.setExtraHTTPHeaders({ "Accept-Language": "fr-FR,fr;q=0.9" });
  const cdp = await page.createCDPSession();
  await cdp.send("Network.enable");
  // Images et polices inutiles (sans intercepter chaque requête, ce qui ralentirait la page)
  await cdp.send("Network.setBlockedURLs", { urls: ["*.png*", "*.jpg*", "*.jpeg*", "*.gif*", "*.webp*", "*.woff2*", "*encrypted-tbn*"] });

  // Lecture en flux de la réponse GetShoppingResults qui suit le clic
  let armed = false;
  let stream = null;
  cdp.on("Network.responseReceived", (e) => {
    if (!armed || stream || !e.response.url.includes("GetShoppingResults")) return;
    stream = { id: e.requestId, head: null, tail: [], done: false, failed: false };
    cdp
      .send("Network.streamResourceContent", { requestId: e.requestId })
      .then((r) => (stream.head = Buffer.from(r.bufferedData, "base64")))
      .catch(() => (stream.head = Buffer.alloc(0)));
  });
  cdp.on("Network.dataReceived", (e) => e.data && stream?.id === e.requestId && stream.tail.push(Buffer.from(e.data, "base64")));
  cdp.on("Network.loadingFinished", (e) => stream?.id === e.requestId && (stream.done = true));
  cdp.on("Network.loadingFailed", (e) => stream?.id === e.requestId && (stream.done = stream.failed = true));
  const received = () => (stream?.head ? Buffer.concat([stream.head, ...stream.tail]).toString("utf8") : "");

  await page.goto(url, { waitUntil: "domcontentloaded", timeout: 20000 });
  t.loaded = Date.now();
  // La liste du serveur s'affiche, puis le JavaScript de Google prend le relais (~1-2 s) : on attend
  // le bouton « Afficher plus de vols », une erreur, ou 4 s de liste sans bouton (= tout est déjà là)
  let state = "";
  let listSince = 0;
  for (const t0 = Date.now(); Date.now() - t0 < 15000; await sleep(200)) {
    state = await page.evaluate(pageState, MORE_RE.source);
    if (state === "error" || state === "more") break;
    if (state === "list") {
      listSince ||= Date.now();
      if (Date.now() - listSince > 4000) break;
    }
  }
  t.ready = Date.now();
  if (state === "list") return { more: false, payload: null, timing: timing(t) };
  if (state !== "more") throw new Error(state === "error" ? "Google a affiché une erreur" : "résultats non affichés");
  // Laisser la page finir de se charger (scripts de Google) avant de cliquer, comme un utilisateur
  await page.waitForNetworkIdle({ idleTime: 500, timeout: Number(process.env.SETTLE_MS || 4000) }).catch(() => {});
  if (await page.evaluate(pageState, MORE_RE.source) === "error") throw new Error("Google a affiché une erreur");
  t.idle = Date.now();

  armed = true;
  await page.evaluate((re) => {
    const btns = [...document.querySelectorAll("button, [role=button]")];
    btns.find((e) => new RegExp(re, "i").test(`${e.textContent} ${e.getAttribute("aria-label") || ""}`))?.click();
  }, MORE_RE.source);
  t.click = Date.now();

  // Google envoie d'abord la liste avec la plupart des prix, puis des mises à jour pendant parfois
  // 20 s et plus : on s'arrête à la fin du flux, ou 4 s après la 1re liste complète
  let payload = null;
  for (;;) {
    await sleep(150);
    const text = received();
    const p = text ? lastPayload(text) : null;
    if (p) {
      payload = p;
      t.first ||= Date.now();
    }
    if (stream?.done) {
      if (!payload && stream.head && !stream.failed) {
        // flux non disponible : corps complet
        const body = await cdp.send("Network.getResponseBody", { requestId: stream.id }).catch(() => null);
        payload = body ? lastPayload(body.base64Encoded ? Buffer.from(body.body, "base64").toString("utf8") : body.body) : null;
      }
      break;
    }
    if (t.first && Date.now() - t.first > 4000) break;
    if (Date.now() - t.click > 20000) break;
  }
  t.end = Date.now();
  if (!payload) throw new Error(stream ? "Google a refusé la liste complète" : "pas de réponse de Google après le clic");
  return { more: true, payload, complete: !!stream?.done, timing: timing(t) };
}

// Durées (ms) de chaque étape, pour le suivi
function timing(t) {
  const out = {};
  for (const k of ["loaded", "ready", "idle", "click", "first", "end"]) if (t[k]) out[k] = t[k] - t.start;
  return out;
}

async function fullList(tfs, curr) {
  const url = `https://www.google.com/travel/flights/search?tfs=${encodeURIComponent(tfs)}&hl=fr&curr=${curr}&gl=FR`;
  const errors = [];
  const t0 = Date.now();
  // Google refuse parfois la liste (erreur 13) : jusqu'à 3 essais tant qu'il reste du temps
  for (let i = 0; i < 3 && Date.now() - t0 < 18000; i++) {
    // Contexte par défaut : le Chromium allégé de Vercel (--single-process) plante sur createBrowserContext
    const ctx = (await browser()).defaultBrowserContext();
    try {
      return { ...(await attempt(ctx, url)), attempts: i + 1 };
    } catch (e) {
      errors.push(String(e?.message || e));
    }
  }
  throw new Error(errors.join(" | "));
}

export default async function handler(req, res) {
  const secret = process.env.CRON_SECRET;
  if (!secret || req.headers.authorization !== `Bearer ${secret}`) return res.status(401).json({ error: "Non autorisé" });
  const tfs = String(req.query.tfs || "");
  const curr = String(req.query.curr || "EUR");
  if (!/^[A-Za-z0-9_=+/-]{10,3000}$/.test(tfs) || !/^[A-Z]{3}$/.test(curr)) return res.status(400).json({ error: "Paramètres invalides" });
  const t0 = Date.now();
  try {
    const reused = !!(launching && (await launching.catch(() => null))?.connected);
    await browser();
    const launch = Date.now() - t0;
    const out = await fullList(tfs, curr);
    res.setHeader("Cache-Control", "no-store");
    return res.status(200).json({ ...out, reused, launch, ms: Date.now() - t0 });
  } catch (e) {
    return res.status(502).json({ error: String(e?.message || e), ms: Date.now() - t0 });
  }
}
