"""Stockage clé-valeur de l'appli (alertes, abonnements aux notifications).

En ligne : Upstash Redis via son API REST (variables d'environnement posées par
l'intégration Vercel). En local, sans ces variables : un fichier JSON.
"""

import json
import os
import threading
import time
import urllib.request
from pathlib import Path


class Store:
    def get(self, key: str):
        raise NotImplementedError

    def set(self, key: str, value, ex: int | None = None) -> None:
        """ex : durée de vie en secondes (cache)."""
        raise NotImplementedError

    def delete(self, key: str) -> None:
        raise NotImplementedError

    def sadd(self, key: str, member: str) -> None:
        raise NotImplementedError

    def srem(self, key: str, member: str) -> None:
        raise NotImplementedError

    def smembers(self, key: str) -> list[str]:
        raise NotImplementedError

    def push_capped(self, key: str, value, maxlen: int) -> None:
        """Ajoute en fin de liste et ne garde que les `maxlen` derniers éléments."""
        raise NotImplementedError

    def lrange(self, key: str) -> list:
        raise NotImplementedError


class RedisStore(Store):
    def __init__(self, url: str, token: str):
        self.url = url.rstrip("/")
        self.token = token

    def _call(self, *commands):
        """Une ou plusieurs commandes Redis (pipeline) → liste des résultats."""
        req = urllib.request.Request(
            f"{self.url}/pipeline",
            data=json.dumps([list(c) for c in commands]).encode(),
            headers={"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=15) as r:
            out = json.loads(r.read())
        for item in out:
            if "error" in item:
                raise RuntimeError(f"Redis : {item['error']}")
        return [item.get("result") for item in out]

    def get(self, key):
        raw = self._call(["GET", key])[0]
        return json.loads(raw) if raw is not None else None

    def set(self, key, value, ex=None):
        cmd = ["SET", key, json.dumps(value, ensure_ascii=False)]
        self._call(cmd + (["EX", int(ex)] if ex else []))

    def delete(self, key):
        self._call(["DEL", key])

    def sadd(self, key, member):
        self._call(["SADD", key, member])

    def srem(self, key, member):
        self._call(["SREM", key, member])

    def smembers(self, key):
        return sorted(self._call(["SMEMBERS", key])[0] or [])

    def push_capped(self, key, value, maxlen):
        self._call(["RPUSH", key, json.dumps(value)], ["LTRIM", key, -maxlen, -1])

    def lrange(self, key):
        return [json.loads(x) for x in self._call(["LRANGE", key, 0, -1])[0] or []]


class FileStore(Store):
    """Pour le développement local uniquement."""

    _lock = threading.Lock()

    def __init__(self, path: Path):
        self.path = path

    def _load(self) -> dict:
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def _save(self, data):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    def _edit(self, fn):
        with self._lock:
            data = self._load()
            out = fn(data)
            self._save(data)
            return out

    def get(self, key):
        v = self._load().get(key)
        if isinstance(v, dict) and "__exp" in v:  # entrée de cache avec expiration
            return v["v"] if v["__exp"] > time.time() else None
        return v

    def set(self, key, value, ex=None):
        self._edit(lambda d: d.__setitem__(key, {"__exp": time.time() + ex, "v": value} if ex else value))

    def delete(self, key):
        self._edit(lambda d: d.pop(key, None))

    def sadd(self, key, member):
        self._edit(lambda d: d.__setitem__(key, sorted(set(d.get(key, [])) | {member})))

    def srem(self, key, member):
        self._edit(lambda d: d.__setitem__(key, [m for m in d.get(key, []) if m != member]))

    def smembers(self, key):
        return list(self._load().get(key, []))

    def push_capped(self, key, value, maxlen):
        self._edit(lambda d: d.__setitem__(key, (d.get(key, []) + [value])[-maxlen:]))

    def lrange(self, key):
        return list(self._load().get(key, []))


def get_store() -> Store:
    url = os.environ.get("KV_REST_API_URL") or os.environ.get("UPSTASH_REDIS_REST_URL")
    token = os.environ.get("KV_REST_API_TOKEN") or os.environ.get("UPSTASH_REDIS_REST_TOKEN")
    if url and token:
        return RedisStore(url, token)
    return FileStore(Path(__file__).resolve().parent.parent / "data" / "app_store.json")
