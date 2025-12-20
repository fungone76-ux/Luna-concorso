# src/visuals/prompt_compiler.py
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple, Optional

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
    Compone il prompt per Stable Diffusion usando file .txt del progetto e (opzionalmente) tags/visual dell'LLM.

    File usati (relativi a project_root):
      prompts/sd/base/global.txt
      prompts/sd/base/<tutor>.txt          (luna/stella/maria)
      prompts/sd/stages/stageN.txt         (se is_punish=False)
      prompts/sd/punish/<tutor>.txt        (se is_punish=True)

    Logica:
      - global + tutor base SEMPRE inclusi
      - stage o punish in base a is_punish
      - se question presente: aggiunge ", ".join(question.tags) + question.visual in coda
      - estrae NEGATIVE: dal global.txt (se presente) come negative_prompt
    """
    root = Path(project_root)
    sd_dir = root / "prompts" / "sd"

    global_txt = _read_text(sd_dir / "base" / "global.txt")
    tutor_txt = _read_text(sd_dir / "base" / f"{tutor.lower()}.txt")

    if is_punish:
        stage_txt = _read_text(sd_dir / "punish" / f"{tutor.lower()}.txt")
    else:
        n = _clamp_int(stage, 1, 5)
        stage_txt = _read_text(sd_dir / "stages" / f"stage{n}.txt")

    pos_global, neg_global = _split_negative(global_txt)

    chunks: List[str] = []
    chunks.extend(_to_chunks(pos_global))
    chunks.extend(_to_chunks(tutor_txt))
    chunks.extend(_to_chunks(stage_txt))

    # aggiunta LLM (opzionale): tags + visual
    if question is not None:
        tags_raw = getattr(question, "tags", []) or []
        visual_raw = getattr(question, "visual", "") or ""

        tags = [t.strip() for t in tags_raw if isinstance(t, str) and t.strip()]
        visual = visual_raw.strip()

        if tags:
            chunks.append(", ".join(tags))
        if visual:
            chunks.append(visual)

    prompt = _join(chunks)
    negative_prompt = _join(_to_chunks(neg_global))

    return SDPrompt(prompt=prompt, negative_prompt=negative_prompt)


# -------------------------
# Helpers
# -------------------------

def _read_text(path: Path) -> str:
    if not path.exists():
        raise FileNotFoundError(f"File prompt SD mancante: {path}")
    return path.read_text(encoding="utf-8").strip()


def _split_negative(text: str) -> Tuple[str, str]:
    """
    Se trova 'NEGATIVE:' (case-insensitive) separa positivo/negativo.
    Esempio:
      high quality, ...
      NEGATIVE: low quality, blurry, ...
    """
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
    """
    Trasforma un testo multi-linea in chunks:
    - rimuove righe vuote
    - ignora commenti che iniziano con '#'
    - NON spezza ulteriormente: se vuoi virgole, scrivile tu nel file.
    """
    if not text:
        return []
    out: List[str] = []
    for line in text.splitlines():
        s = line.strip()
        if not s:
            continue
        if s.startswith("#"):
            continue
        out.append(s)
    return out


def _join(chunks: List[str]) -> str:
    # unione in stile SD: virgole tra chunk
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

