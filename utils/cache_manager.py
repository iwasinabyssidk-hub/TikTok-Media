from __future__ import annotations

import hashlib
import json
import pickle
from pathlib import Path
from typing import Any


class CacheManager:


    def __init__(self, cache_dir: str | Path) -> None:
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def build_key(self, namespace: str, payload: dict[str, Any]) -> str:
        raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
        digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        return f"{namespace}_{digest}"

    def _path(self, key: str) -> Path:
        return self.cache_dir / f"{key}.pkl"

    def exists(self, key: str) -> bool:
        return self._path(key).exists()

    def load(self, key: str) -> Any:
        with self._path(key).open("rb") as handle:
            return pickle.load(handle)

    def save(self, key: str, data: Any) -> Path:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("wb") as handle:
            pickle.dump(data, handle)
        return path

    def resolve_path(self, namespace: str, suffix: str) -> Path:
        path = self.cache_dir / namespace / suffix
        path.parent.mkdir(parents=True, exist_ok=True)
        return path
