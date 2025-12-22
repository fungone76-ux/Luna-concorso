# src/ai/prompt_builder.py
from __future__ import annotations

import json
import os
import random
from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass(frozen=True)
class PromptBuildConfig:
    seed_per_prompt: int = 4
    strict_json_only: bool = True


def _read_text(path: str) -> str:
    if not os.path.exists(path): return ""
    with open(path, "r", encoding="utf-8") as f: return f.read().strip()


def _load_jsonl(path: str) -> List[Dict]:
    rows = []
    if not os.path.exists(path): return rows
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                try:
                    rows.append(json.loads(line.strip()))
                except:
                    continue
    return rows


def _sample(rows: List[Dict], k: int, rng: random.Random) -> List[Dict]:
    if not rows: return []
    return rng.sample(rows, min(len(rows), k))


def subject_to_instruction_filename(subject: str) -> str:
    mapping = {
        "Diritto amministrativo": "amministrativo.txt",
        "Logica": "logica.txt",
        "Quesiti situazionali": "situazionali.txt",
        "Informatica (TIC)": "informatica.txt",
        "Inglese A2": "inglese_a2.txt",
        "Codice dell'Amministrazione Digitale (CAD)": "cad.txt",
        "Diritto dell'Unione Europea": "diritto_ue.txt",
        "Contabilità di Stato": "contabilita_stato.txt",
        "Diritto penale (PA)": "penale_pa.txt",
        "Lavoro pubblico": "lavoro_pubblico.txt",
        "Responsabilità del dipendente pubblico": "responsabilita_dp.txt",
        "Beni culturali": "beni_culturali.txt",
        "Struttura MIC": "mic_struttura.txt",
        "Marketing e comunicazione PA": "marketing_comunicazione.txt",
        "Sicurezza (D.Lgs. 81/2008)": "sicurezza81.txt",
        "Contratti pubblici": "contratti_pubblici.txt",
    }
    return mapping.get(subject, "logica.txt")


def subject_to_seed_filename(subject: str) -> str:
    base = "seed_" + subject_to_instruction_filename(subject).replace(".txt", ".jsonl")
    return base


def build_question_prompt(
        project_root: str,
        subject: str,
        tutor: str,
        stage: int,
        outcome_hint: str,
        cfg: PromptBuildConfig,
        specific_topic: str = "",
        rng: Optional[random.Random] = None,
) -> str:
    rng = rng or random.Random()

    # Usa il prompt "Solo Quiz" perché la lezione è già stata fatta a parte
    system_rules = _read_text(os.path.join(project_root, "prompts", "ripam_quiz_only.txt"))
    general_rules = _read_text(os.path.join(project_root, "prompts", "question_instructions", "_general_rules.txt"))
    instr_path = os.path.join(project_root, "prompts", "question_instructions",
                              subject_to_instruction_filename(subject))
    schema_text = _read_text(os.path.join(project_root, "prompts", "output_schema.json"))

    seed_path = os.path.join(project_root, "data", "question_banks", subject_to_seed_filename(subject))
    seed_rows = _load_jsonl(seed_path)
    fewshot = _sample(seed_rows, cfg.seed_per_prompt, rng)

    fewshot_block = ""
    if fewshot:
        fewshot_block = "EXAMPLES (STYLE REFERENCE ONLY):\n" + "\n".join(
            json.dumps(x, ensure_ascii=False) for x in fewshot)

    topic_display = specific_topic if specific_topic else subject

    # Selettore di intensità pose in base allo stage (TRADOTTO E PULITO)
    if stage >= 4:
        pose_instructions = "USE EXPLICIT & DYNAMIC BODY POSES: spread legs, on all fours, presenting ass, legs up, from behind, doggystyle, arched back."
    elif stage == 3:
        pose_instructions = "USE TEASING BODY POSES: sitting on desk, spreading legs slightly, bending over, kneeling, hands on hips, looking back."
    else:
        pose_instructions = "USE CONFIDENT BODY POSES: sitting, standing, leaning on wall, crossing legs."

    prompt = f"""
{system_rules}

YOU ARE AN EXPERT EXAM CREATOR (RIPAM/Formez PA) AND AN AI VISUAL DIRECTOR.

--- GOAL 1: THE QUESTION ---
Generate a multiple-choice question on the specific topic: "{topic_display}".
Use your historical knowledge of Italian public contests (2019-2024) to replicate the style and difficulty.
Create tricky distractors.

--- GOAL 2: THE VISUAL DIRECTOR (FIELD 'VISUAL') ---
You must describe the Tutor's pose for the AI image generator.
CURRENT STAGE: {stage}
{pose_instructions}

--- STRICT FACE SAFETY PROTOCOL (NO DEFORMATIONS) ---
The AI image generator often distorts faces when facial tags are present.
THEREFORE, YOU ARE STRICTLY FORBIDDEN FROM DESCRIBING THE FACE.

1. **NO FACE TAGS:** Do NOT use words like: 'face', 'eyes', 'mouth', 'lips', 'expression', 'smile', 'stare', 'gaze', 'look'.
2. **NO EMOTIONS:** Do NOT use words like: 'neutral', 'happy', 'seductive face', 'angry'.
3. **NO HEAD DETAILS:** Do NOT use words like: 'glasses', 'hair', 'teeth'.

**INSTRUCTION:** Focus 100% of the 'visual' tags on the BODY, POSE, and CAMERA ANGLE only.
Example of VALID tags: "sitting on desk, low angle, legs crossed, hands on lap".
Example of INVALID tags: "sitting on desk, seductive smile, looking at viewer".

CONTESTO GIOCO:
- Tutor: {tutor} | Stage: {stage}

{general_rules}

ISTRUZIONI MATERIA ({subject}):
{_read_text(instr_path)}

{fewshot_block}

OUTPUT RICHIESTO (SOLO JSON):
{schema_text}
""".strip()

    return prompt