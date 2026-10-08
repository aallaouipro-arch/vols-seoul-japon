import json
import sqlite3
from datetime import datetime
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    errors INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS searches (
    run_id INTEGER NOT NULL,
    ts TEXT NOT NULL,
    key TEXT NOT NULL,
    best_price INTEGER,
    best_offer TEXT,
    level TEXT,
    typical_low INTEGER,
    typical_high INTEGER,
    url TEXT
);
CREATE INDEX IF NOT EXISTS idx_searches_key ON searches(key, ts);
-- Historique de prix fourni par Google (≈ 60 derniers jours) : 1 point par jour
CREATE TABLE IF NOT EXISTS google_history (
    key TEXT NOT NULL,
    day TEXT NOT NULL,
    price INTEGER NOT NULL,
    PRIMARY KEY (key, day)
);
CREATE TABLE IF NOT EXISTS combos (
    run_id INTEGER NOT NULL,
    ts TEXT NOT NULL,
    strategy TEXT NOT NULL,
    total INTEGER NOT NULL,
    details TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS state (
    k TEXT PRIMARY KEY,
    v TEXT
);
"""


class DB:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)

    def start_run(self) -> tuple[int, str]:
        ts = datetime.now().isoformat(timespec="seconds")
        cur = self.conn.execute("INSERT INTO runs (ts) VALUES (?)", (ts,))
        self.conn.commit()
        return cur.lastrowid, ts

    def end_run(self, run_id: int, errors: int):
        self.conn.execute("UPDATE runs SET errors=? WHERE id=?", (errors, run_id))
        self.conn.commit()

    def save_search(self, run_id, ts, key, result):
        best = result.best
        ins = result.insights
        self.conn.execute(
            "INSERT INTO searches VALUES (?,?,?,?,?,?,?,?,?)",
            (
                run_id, ts, key,
                best.price if best else None,
                json.dumps(best.__dict__, ensure_ascii=False) if best else None,
                ins.level if ins else None,
                ins.typical_low if ins else None,
                ins.typical_high if ins else None,
                result.url,
            ),
        )
        if ins:
            self.conn.executemany(
                "INSERT OR REPLACE INTO google_history VALUES (?,?,?)",
                [(key, day, price) for day, price in ins.history],
            )
        self.conn.commit()

    def save_combo(self, run_id, ts, strategy, total, details):
        self.conn.execute(
            "INSERT INTO combos VALUES (?,?,?,?,?)",
            (run_id, ts, strategy, total, json.dumps(details, ensure_ascii=False)),
        )
        self.conn.commit()

    def best_combo_series(self, strategies) -> list[tuple[str, int]]:
        """Meilleur total par run, parmi les stratégies données (celles du plan actuel :
        l'historique d'un ancien itinéraire n'est pas comparable)."""
        marks = ",".join("?" * len(strategies))
        rows = self.conn.execute(
            f"SELECT ts, MIN(total) AS total FROM combos WHERE strategy IN ({marks}) GROUP BY run_id ORDER BY ts",
            list(strategies),
        ).fetchall()
        return [(r["ts"], r["total"]) for r in rows]

    def combo_series(self, strategy) -> list[tuple[str, int]]:
        rows = self.conn.execute(
            "SELECT ts, MIN(total) AS total FROM combos WHERE strategy=? GROUP BY run_id ORDER BY ts",
            (strategy,),
        ).fetchall()
        return [(r["ts"], r["total"]) for r in rows]

    def google_history(self, key) -> list[tuple[str, int]]:
        rows = self.conn.execute(
            "SELECT day, price FROM google_history WHERE key=? ORDER BY day", (key,)
        ).fetchall()
        return [(r["day"], r["price"]) for r in rows]

    def get_state(self, k, default=None):
        row = self.conn.execute("SELECT v FROM state WHERE k=?", (k,)).fetchone()
        return json.loads(row["v"]) if row else default

    def set_state(self, k, v):
        self.conn.execute(
            "INSERT OR REPLACE INTO state VALUES (?,?)", (k, json.dumps(v, ensure_ascii=False))
        )
        self.conn.commit()
