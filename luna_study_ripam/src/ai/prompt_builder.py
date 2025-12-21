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

    system_rules = _read_text(os.path.join(project_root, "prompts", "system_prompt.txt"))
    general_rules = _read_text(os.path.join(project_root, "prompts", "question_instructions", "_general_rules.txt"))
    instr_path = os.path.join(project_root, "prompts", "question_instructions",
                              subject_to_instruction_filename(subject))
    schema_text = _read_text(os.path.join(project_root, "prompts", "output_schema.json"))

    seed_path = os.path.join(project_root, "data", "question_banks", subject_to_seed_filename(subject))
    seed_rows = _load_jsonl(seed_path)
    fewshot = _sample(seed_rows, cfg.seed_per_prompt, rng)

    fewshot_block = ""
    if fewshot:
        fewshot_block = "ESEMPI (SOLO PER FORMATO E STILE):\n" + "\n".join(
            json.dumps(x, ensure_ascii=False) for x in fewshot)

    topic_display = specific_topic if specific_topic else subject

    # Selettore di intensità pose in base allo stage
    if stage >= 4:
        pose_instructions = "USATE POSE ESPLICITE ED ESTREME: spread legs, on all fours, presenting ass, fingering, legs up, close-up genitals, from behind, doggystyle."
    elif stage == 3:
        pose_instructions = "USATE POSE PROVOCANTI: sitting on desk, spreading legs slightly, bending over, kneeling, hands on body, looking back."
    else:
        pose_instructions = "USATE POSE PROFESSIONALI MA SEDUCENTI: sitting, standing confident, leaning on wall, adjusting glasses."

    prompt = f"""
{system_rules}

SEI UN ESPERTO SELEZIONATORE RIPAM (Formez PA) E UN REGISTA VISIVO.

--- OBIETTIVO 1: LA DOMANDA ---
Genera una domanda a risposta multipla sul tema specifico: "{topic_display}".
Usa la tua conoscenza storica dei concorsi 2019-2024 per replicare lo stile e la difficoltà.
Crea distrattori insidiosi (date vicine, autorità simili).

--- OBIETTIVO 2: IL REGISTA (CAMPO 'VISUAL') ---
Devi descrivere la posa del tutor nell'immagine che verrà generata.
ATTUALE STAGE: {stage}
{pose_instructions}

IMPORTANTE: Varia SEMPRE la posa. Non usare sempre la stessa.
Nel campo "visual" del JSON scrivi 3-4 tag inglesi che descrivono SOLO la posa e l'inquadratura (es. "low angle, from below, spreading legs").
NON descrivere l'abbigliamento (ci pensa un altro sistema). Descrivi solo AZIONE e POSIZIONE.

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