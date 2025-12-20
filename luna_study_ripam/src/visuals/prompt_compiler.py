# src/visuals/prompt_compiler.py
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple, Optional
import sys

from src.domain.models import TutorName, Question


@dataclass(frozen=True)
class SDPrompt:
    prompt: str
    negative_prompt: str


def compile_sd_prompt(
        project_root: str,
        tutor: TutorName,
        stage: int,
        is_punish: bool,
        question: Optional[Question] = None,
) -> SDPrompt:
    """
    Versione DEBUG con stampe in console.
    """
    print(f"\n--- [DEBUG] Compilazione Prompt ---")
    print(f"ROOT: {project_root}")
    print(f"Tutor: {tutor} | Stage: {stage} | Punish: {is_punish}")

    root = Path(project_root)
    sd_dir = root / "prompts" / "sd"

    # 1. Carica Global e Tutor Base
    global_path = sd_dir / "base" / "global.txt"
    tutor_path = sd_dir / "base" / f"{tutor.lower()}.txt"

    global_txt = _read_text(global_path)
    tutor_txt = _read_text(tutor_path)

    print(f"Global loaded ({len(global_txt)} chars). Tutor loaded ({len(tutor_txt)} chars).")

    # 2. Carica Stage
    n = _clamp_int(stage, 1, 5)
    stage_path = sd_dir / "stages" / f"stage{n}.txt"
    stage_txt = _read_text(stage_path)

    if not stage_txt:
        print(f"!!! ATTENZIONE: Stage file vuoto o non trovato: {stage_path}")
    else:
        print(f"Stage loaded from {stage_path.name} ({len(stage_txt)} chars).")

    # 3. Punish
    punish_txt = ""
    if is_punish:
        punish_path = sd_dir / "punish" / f"{tutor.lower()}.txt"
        punish_txt = _read_text(punish_path)
        print(f"Punish mode ON. Loaded {punish_path.name}")

    pos_global, neg_global = _split_negative(global_txt)

    chunks: List[str] = []
    chunks.extend(_to_chunks(pos_global))
    chunks.extend(_to_chunks(tutor_txt))
    chunks.extend(_to_chunks(stage_txt))

    if is_punish:
        chunks.extend(_to_chunks(punish_txt))

    # 4. Tags + Visual
    if question is not None:
        print("Question object: PRESENTE")
        tags_raw = getattr(question, "tags", []) or []
        visual_raw = getattr(question, "visual", "") or ""

        print(f"Tags raw: {tags_raw}")
        print(f"Visual raw: {visual_raw}")

        tags = [t.strip() for t in tags_raw if isinstance(t, str) and t.strip()]
        visual = visual_raw.strip()

        if tags:
            joined_tags = ", ".join(tags)
            chunks.append(joined_tags)
            print(f"Tags aggiunti: {joined_tags[:50]}...")
        else:
            print("!!! ATTENZIONE: Nessun tag valido trovato.")

        if visual:
            if not is_punish:
                chunks.append(visual)
                print("Visual aggiunto.")
            else:
                print("Visual ignorato per punizione.")
    else:
        print("!!! ATTENZIONE: Question object è NONE")

    prompt = _join(chunks)
    negative_prompt = _join(_to_chunks(neg_global))

    print(f"Prompt finale lungh: {len(prompt)}")
    print("-----------------------------------\n")

    return SDPrompt(prompt=prompt, negative_prompt=negative_prompt)


# -------------------------
# Helpers
# -------------------------

def _read_text(path: Path) -> str:
    if not path.exists():
        print(f"[DEBUG] File NON trovato: {path}")
        return ""
        # Usa utf-8-sig per gestire il BOM
    try:
        return path.read_text(encoding="utf-8-sig").strip()
    except Exception as e:
        print(f"[DEBUG] Errore lettura {path}: {e}")
        return ""


def _split_negative(text: str) -> Tuple[str, str]:
    if not text:
        return "", ""
    upper = text.upper()
    marker = "NEGATIVE:"
    idx = upper.find(marker)
    if idx < 0:
        return text, ""
    positive = text[:idx].strip()
    negative = text[idx + len(marker):].strip()
    return positive, negative


def _to_chunks(text: str) -> List[str]:
    if not text:
        return []
    out: List[str] = []
    for line in text.splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        out.append(s)
    return out


def _join(chunks: List[str]) -> str:
    parts = [c.strip().strip(",") for c in chunks if c and c.strip()]
    joined = ", ".join(parts).strip().strip(",")
    while ", ," in joined:
        joined = joined.replace(", ,", ",")
    return joined


def _clamp_int(v: int, lo: int, hi: int) -> int:
    try:
        x = int(v)
    except Exception:
        x = lo
    return max(lo, min(hi, x))