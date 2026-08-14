import json
from functools import lru_cache
from pathlib import Path


@lru_cache
def translations(language: str) -> dict[str, str]:
    path = Path(__file__).resolve().parents[1] / "i18n" / f"{language}.json"
    if not path.exists():
        path = path.with_name("en.json")
    return json.loads(path.read_text(encoding="utf-8"))


def t(key: str, language: str = "en") -> str:
    current = translations(language)
    return current.get(key, translations("en").get(key, key))

