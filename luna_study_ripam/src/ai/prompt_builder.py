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
    # se True, inserisce nel prompt una “sezione severa” anti-output extra
    strict_json_only: bool = True


def _read_text(path: str) -> str:
    if not os.path.exists(path):
        return ""
    with open(path, "r", encoding="utf-8") as f:
        return f.read().strip()


def _load_jsonl(path: str) -> List[Dict]:
    rows: List[Dict] = []
    if not os.path.exists(path):
        return rows
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except Exception:
                # se una riga è rotta la ignoriamo (meglio robusto)
                continue
    return rows


def _sample(rows: List[Dict], k: int, rng: random.Random) -> List[Dict]:
    if not rows:
        return []
    if len(rows) <= k:
        return rows
    return rng.sample(rows, k)


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
    # fallback
    return mapping.get(subject, "logica.txt")


def subject_to_seed_filename(subject: str) -> str:
    mapping = {
        "Diritto amministrativo": "seed_amministrativo.jsonl",
        "Logica": "seed_logica.jsonl",
        "Quesiti situazionali": "seed_situazionali.jsonl",
        "Informatica (TIC)": "seed_informatica.jsonl",
        "Inglese A2": "seed_inglese_a2.jsonl",
        "Codice dell'Amministrazione Digitale (CAD)": "seed_cad.jsonl",
        "Diritto dell'Unione Europea": "seed_diritto_ue.jsonl",
        "Contabilità di Stato": "seed_contabilita_stato.jsonl",
        "Diritto penale (PA)": "seed_penale_pa.jsonl",
        "Lavoro pubblico": "seed_lavoro_pubblico.jsonl",
        "Responsabilità del dipendente pubblico": "seed_responsabilita_dp.jsonl",
        "Beni culturali": "seed_beni_culturali.jsonl",
        "Struttura MIC": "seed_mic_struttura.jsonl",
        "Marketing e comunicazione PA": "seed_marketing_comunicazione.jsonl",
        "Sicurezza (D.Lgs. 81/2008)": "seed_sicurezza81.jsonl",
        "Contratti pubblici": "seed_contratti_pubblici.jsonl",
    }
    return mapping.get(subject, "seed_logica.jsonl")


def build_question_prompt(
    project_root: str,
    subject: str,
    tutor: str,
    stage: int,
    outcome_hint: str,
    cfg: PromptBuildConfig,
    rng: Optional[random.Random] = None,
) -> str:
    """
    Crea il prompt per generare UNA domanda (stile RIPAM) + campi visuali.

    Parametri:
    - project_root: root del progetto (cartella che contiene prompts/, data/, src/)
    - subject: materia estratta
    - tutor: tutor associata (tono/persona, ma la domanda resta da concorso)
    - stage: stage corrente della tutor (1..5)
    - outcome_hint: "corretta"/"errata"/"omessa" (solo come contesto per i tag/visual del prossimo frame)
    - cfg: configurazione prompt
    - rng: per scegliere i seed

    Output atteso dall'LLM:
    - JSON valido (nessun testo extra)
    - conforme a prompts/output_schema.json
    """
    rng = rng or random.Random()

    # --- file path ---
    general_rules_path = os.path.join(project_root, "prompts", "question_instructions", "_general_rules.txt")
    instr_path = os.path.join(
        project_root,
        "prompts",
        "question_instructions",
        subject_to_instruction_filename(subject),
    )
    schema_path = os.path.join(project_root, "prompts", "output_schema.json")

    seed_path = os.path.join(
        project_root,
        "data",
        "question_banks",
        subject_to_seed_filename(subject),
    )

    # --- read content ---
    general_rules = _read_text(general_rules_path)
    subject_instructions = _read_text(instr_path)
    schema_text = _read_text(schema_path)

    seed_rows = _load_jsonl(seed_path)
    fewshot = _sample(seed_rows, cfg.seed_per_prompt, rng)

    fewshot_block = ""
    if fewshot:
        # IMPORTANT: sono esempi “di stile”, NON da copiare
        fewshot_block = "ESEMPI (solo stile, NON copiare e NON ripetere):\n" + "\n".join(
            json.dumps(x, ensure_ascii=False) for x in fewshot
        )

    strict = ""
    if cfg.strict_json_only:
        strict = (
            "VINCOLO FORTISSIMO:\n"
            "- Rispondi SOLO con JSON valido.\n"
            "- Vietato testo extra, vietati backticks, vietati commenti.\n"
            "- Nessuna spiegazione fuori dal JSON.\n"
        )

    # --- build prompt ---
    prompt = f"""
Sei un generatore di domande per concorso pubblico RIPAM.
Genera 1 domanda nuova (non vista prima) per la prova del MIC (Assistente vigilanza/accoglienza).

CONTESTO GIOCO (solo per tono e visual):
- Tutor attiva: {tutor}
- Materia: {subject}
- Stage tutor: {stage} (1=vestita ... 5=hot non-explicit)
- Ultimo esito utente: {outcome_hint} (usa solo per mood dei tag/visual)

{strict}

REGOLE GENERALI:
{general_rules}

ISTRUZIONI SPECIFICHE MATERIA:
{subject_instructions}

{fewshot_block}

OUTPUT OBBLIGATORIO:
- Produci un JSON conforme allo schema.
- Compila SEMPRE almeno:
  tutor, materia, tipo, domanda, opzioni(A-D), corretta (se standard), spiegazione
- Se tipo="situazionale": includi efficacia per A-D (efficace/neutra/inefficace)
- Aggiungi anche:
  tags_en: lista breve di keyword utili per SD (pose/outfit/mood coerenti con stage+esito)
  visual_en: descrizione concreta e “SD-friendly” (no emozioni vaghe, no narrativa)

SCHEMA JSON:
{schema_text}
""".strip()

    return prompt
