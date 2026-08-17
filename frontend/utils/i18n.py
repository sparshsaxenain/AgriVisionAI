import json
import re
from functools import lru_cache
from pathlib import Path


@lru_cache
def translations(language: str) -> dict[str, str]:
    path = Path(__file__).resolve().parents[1] / "i18n" / f"{language}.json"
    if not path.exists():
        path = path.with_name("en.json")
    return json.loads(path.read_text(encoding="utf-8"))


def current_language() -> str:
    """Return the language selected for the current Streamlit session."""
    try:
        import streamlit as st

        return st.session_state.get("language", "en")
    except Exception:
        return "en"


def _hindi_dynamic(text: str) -> str:
    """Translate common API-generated status sentences without changing record names."""
    patterns = (
        (r"^Due in (\d+) days?$", lambda match: f"{match.group(1)} दिन में नियत"),
        (r"^Overdue by (\d+) days?$", lambda match: f"{match.group(1)} दिन से लंबित"),
        (r"^(.+) detected$", lambda match: f"{match.group(1)} का पता चला"),
        (r"^High-severity (.+)$", lambda match: f"{match.group(1)} की गंभीर स्थिति"),
        (r"^(.+) needs attention$", lambda match: f"{match.group(1)} पर ध्यान आवश्यक है"),
        (r"^(.+) vaccination due soon$", lambda match: f"{match.group(1)} टीकाकरण जल्द नियत है"),
        (r"^(.+) is due for vaccination in (\d+) days?\.$", lambda match: f"{match.group(1)} का टीकाकरण {match.group(2)} दिन में नियत है।"),
        (r"^Detected with (\d+)% confidence\. Review recommended actions\.$", lambda match: f"{match.group(1)}% विश्वसनीयता के साथ पहचान हुई। सुझाए गए कदम देखें।"),
    )
    for pattern, replace in patterns:
        match = re.match(pattern, text)
        if match:
            return replace(match)
    return text


def t(key: str, language: str | None = None, **values: object) -> str:
    """Translate a UI key or an English source phrase and interpolate values."""
    language = language or current_language()
    current = translations(language)
    text = current.get(key, translations("en").get(key, key))
    if language == "hi" and text == key:
        text = _hindi_dynamic(text)
    return text.format(**values) if values else text
