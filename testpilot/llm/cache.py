"""On-disk cache of LLM answers, keyed by everything that can change the answer."""

import hashlib
import json
from pathlib import Path


def cache_key(provider: str, model: str, system: str, prompt: str, temperature: float, seed: int):
    blob = json.dumps([provider, model, system, prompt, temperature, seed], ensure_ascii=False)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


class Cache:
    def __init__(self, folder: Path):
        self.folder = Path(folder)

    def _path(self, key: str) -> Path:
        return self.folder / key[:2] / f"{key}.json"

    def get(self, key: str) -> dict | None:
        path = self._path(key)
        if not path.is_file():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return None

    def put(self, key: str, value: dict) -> None:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
        tmp.replace(path)
