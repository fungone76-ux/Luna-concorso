# src/ai/response_parser.py
from __future__ import annotations
from typing import Any, Dict
from src.domain.models import Question


class ResponseParseError(Exception):
    pass


def parse_question_from_llm_json(data: Dict[str, Any]) -> Question:
    # Campi base
    tutor = _require_enum(data, "tutor", {"Luna", "Stella", "Maria"})
    materia = _require_str(data, "materia")

    # NUOVO: Estrazione della lezione
    lezione = _require_str(data, "lezione")

    # Estrazione Quiz
    domanda = _require_str(data, "domanda")
    opzioni = _require_options(data)
    corretta = _require_choice_letter(data, "corretta")
    spiegazione = _require_str(data, "spiegazione_breve")

    # Visual
    tags = _require_str_list(data, "tags", min_items=0)
    visual = data.get("visual", "")

    return Question(
        lezione=lezione,
        domanda=domanda,
        opzioni=opzioni,
        corretta=corretta,
        spiegazione=spiegazione,
        tutor=tutor,
        materia=materia,
        tags=tags,
        visual=visual,
        spiegazione_breve=spiegazione
    )


# --- Helpers (lascia pure quelli che c'erano o usa questi semplificati) ---
def _require_str(data, key):
    v = data.get(key)
    if not isinstance(v, str): raise ResponseParseError(f"Manca {key}")
    return v.strip()


def _require_enum(data, key, allowed):
    v = _require_str(data, key)
    if v not in allowed: raise ResponseParseError(f"{v} non valido per {key}")
    return v


def _require_options(data):
    opts = data.get("opzioni", {})
    if not all(k in opts for k in ["A", "B", "C", "D"]): raise ResponseParseError("Opzioni mancanti")
    return {k: str(v).strip() for k, v in opts.items()}


def _require_choice_letter(data, key):
    v = _require_str(data, key).upper()
    if v not in ["A", "B", "C", "D"]: raise ResponseParseError("Lettera non valida")
    return v


def _require_str_list(data, key, min_items=0):
    v = data.get(key, [])
    if not isinstance(v, list): return []
    return [str(x) for x in v]