# src/ai/response_parser.py
from __future__ import annotations

from typing import Any, Dict, Optional

from src.domain.models import Question


class ResponseParseError(Exception):
    """Errore di parsing/validazione del JSON dell'LLM."""


def parse_question_from_llm_json(data: Dict[str, Any]) -> Question:
    """
    Parser compatibile con prompts/output_schema.json dell'utente.

    Campi attesi (minimi):
    - tutor: "Luna"/"Stella"/"Maria"
    - materia: string
    - difficulty: int 1..5
    - question_id: string
    - domanda: string
    - opzioni: dict A,B,C,D
    - corretta: A/B/C/D
    - spiegazione_breve: string
    - tags: [..]
    - visual: string
    """
    tutor = _require_enum(data, "tutor", {"Luna", "Stella", "Maria"})
    materia = _require_str(data, "materia")
    difficulty = _require_int_range(data, "difficulty", 1, 5)
    question_id = _require_str(data, "question_id")

    domanda = _require_str(data, "domanda")
    opzioni = _require_options(data)

    corretta = _require_choice_letter(data, "corretta")
    spiegazione = _require_str(data, "spiegazione_breve")

    tags = _require_str_list(data, "tags", min_items=1)
    visual = _require_str(data, "visual")

    # NB: nel tuo schema NON esiste "tipo" (standard/situazionale)
    # Per ora assumiamo standard. Se dopo vuoi situazionali, estendiamo schema+codice.
    return Question(
        tutor=tutor,
        materia=materia,
        tipo="standard",
        domanda=domanda,
        opzioni=opzioni,
        corretta=corretta,
        efficacia=None,
        difficulty=difficulty,
        question_id=question_id,
        spiegazione_breve=spiegazione,
        tags=tags,
        visual=visual,
    )


# -------------------------
# Helpers
# -------------------------

def _require_str(data: Dict[str, Any], key: str) -> str:
    v = data.get(key)
    if not isinstance(v, str) or not v.strip():
        raise ResponseParseError(f"Campo '{key}' mancante o non valido (string).")
    return v.strip()


def _require_enum(data: Dict[str, Any], key: str, allowed: set[str]) -> str:
    v = data.get(key)
    if not isinstance(v, str):
        raise ResponseParseError(f"Campo '{key}' mancante o non valido (enum).")
    v = v.strip()
    if v not in allowed:
        raise ResponseParseError(f"Campo '{key}'='{v}' non in {sorted(allowed)}.")
    return v


def _require_int_range(data: Dict[str, Any], key: str, lo: int, hi: int) -> int:
    v = data.get(key)
    if not isinstance(v, int):
        raise ResponseParseError(f"Campo '{key}' mancante o non valido (int).")
    if not (lo <= v <= hi):
        raise ResponseParseError(f"Campo '{key}'={v} fuori range {lo}..{hi}.")
    return v


def _normalize_letter(s: str) -> str:
    s = s.strip().upper()
    if s and s[0] in ("A", "B", "C", "D"):
        return s[0]
    return s


def _require_choice_letter(data: Dict[str, Any], key: str) -> str:
    v = data.get(key)
    if not isinstance(v, str) or not v.strip():
        raise ResponseParseError(f"Campo '{key}' mancante o non valido (A/B/C/D).")
    letter = _normalize_letter(v)
    if letter not in ("A", "B", "C", "D"):
        raise ResponseParseError(f"Campo '{key}'='{v}' non è una lettera A/B/C/D.")
    return letter


def _require_options(data: Dict[str, Any]) -> Dict[str, str]:
    v = data.get("opzioni")
    if not isinstance(v, dict):
        raise ResponseParseError("Campo 'opzioni' mancante o non valido (dict).")

    out: Dict[str, str] = {}
    for k in ("A", "B", "C", "D"):
        raw = v.get(k)
        if not isinstance(raw, str) or not raw.strip():
            raise ResponseParseError(f"Opzione '{k}' mancante o non valida.")
        out[k] = raw.strip()

    return out


def _require_str_list(data: Dict[str, Any], key: str, min_items: int = 0) -> list[str]:
    v = data.get(key)
    if not isinstance(v, list):
        raise ResponseParseError(f"Campo '{key}' mancante o non valido (array).")
    out: list[str] = []
    for item in v:
        if isinstance(item, str) and item.strip():
            out.append(item.strip())
    if len(out) < min_items:
        raise ResponseParseError(f"Campo '{key}' deve avere almeno {min_items} elementi validi.")
    return out
