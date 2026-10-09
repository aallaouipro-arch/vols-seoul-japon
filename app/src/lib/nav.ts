/** Navigation par hash (#/, #/recherche, #/alertes/<id>) + préremplissage de la recherche. */

import { useEffect, useState } from "react";
import type { SearchQuery } from "./api";

export const useRoute = () => {
  const [hash, setHash] = useState(location.hash || "#/");
  useEffect(() => {
    const on = () => setHash(location.hash || "#/");
    window.addEventListener("hashchange", on);
    return () => window.removeEventListener("hashchange", on);
  }, []);
  return hash.replace(/^#/, "") || "/";
};

export const go = (path: string) => {
  location.hash = path;
};

const SEARCH_KEY = "gt-search";

export const defaultQuery: SearchQuery = {
  origin: "CDG+ORY",
  destination: "SEL",
  originLabel: "Paris",
  destinationLabel: "Séoul",
  depart: "2027-07-21",
  ret: "2027-08-19",
  stops: "1",
  bagsOut: 1,
  bagsRet: 2,
};

export function savedQuery(): SearchQuery {
  try {
    return { ...defaultQuery, ...JSON.parse(localStorage.getItem(SEARCH_KEY) || "{}") };
  } catch {
    return defaultQuery;
  }
}

export const saveQuery = (q: SearchQuery) => localStorage.setItem(SEARCH_KEY, JSON.stringify(q));

/** Ouvre l'onglet Recherche avec ce trajet et lance la recherche. */
export function openSearch(q: Partial<SearchQuery>) {
  // Nouveau départ / nouvelle destination : on oublie le texte secondaire de l'ancien lieu
  const reset: Partial<SearchQuery> = {
    ...(q.origin !== undefined && q.originDetail === undefined ? { originDetail: undefined } : {}),
    ...(q.destination !== undefined && q.destinationDetail === undefined ? { destinationDetail: undefined } : {}),
  };
  saveQuery({ ...savedQuery(), ...reset, ...q });
  sessionStorage.setItem("gt-autorun", "1");
  window.dispatchEvent(new Event("gt-search-prefill"));
  go("/recherche");
}
