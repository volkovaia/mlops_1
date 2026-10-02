# src/toxic_service/features.py
import re
from typing import Any

import pandas as pd

BAD_WORDS = {
    "toxic",
    "idiot",
    "moron",
    "stupid",
    "dumb",
    "shut",
    "up",
    "die",
    "kill",
    "trash",
    "hell",
    "hate",
    "ugly",
    "shit",
    "fuck",
    "bitch",
    "bastard",
}


def extract_meta_features(text: str) -> dict[str, Any]:
    clean_text = text if isinstance(text, str) else ""
    total_chars = max(len(clean_text), 1)

    caps_count = sum(1 for c in clean_text if c.isupper())
    caps_ratio = round(caps_count / total_chars, 4)
    exclaim_count = clean_text.count("!")

    words = re.findall(r"\b\w+\b", clean_text.lower())
    bad_word_count = sum(1 for w in words if w in BAD_WORDS)

    return {
        "comment_text": clean_text,
        "caps_ratio": caps_ratio,
        "exclaim_count": exclaim_count,
        "bad_word_count": bad_word_count,
    }


def transform_texts_to_df(texts: list[str]) -> pd.DataFrame:
    rows = [extract_meta_features(t) for t in texts]
    return pd.DataFrame(rows)
