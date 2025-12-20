# src/main.py
from __future__ import annotations

import os
from pathlib import Path

from src.ai.gemini_client import GeminiClient, GeminiConfig
from src.domain.models import SessionState
from src.engine.session_engine import SessionEngine

from src.visuals.sd_client import SDClient, SDConfig
from src.visuals.prompt_compiler import compile_sd_prompt


def _project_root() -> str:
    # root progetto = cartella sopra src/
    return str(Path(__file__).resolve().parent.parent)


def _get_env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def _print_question(q):
    print("\n" + "=" * 80)
    diff = getattr(q, "difficulty", 1)
    print(f"Tutor: {q.tutor} | Materia: {q.materia} | Tipo: {q.tipo} | Diff: {diff}")
    print("-" * 80)
    print(q.domanda)
    print("-" * 80)

    # opzioni: standard A/B/C/D
    for k in ("A", "B", "C", "D"):
        if k in q.opzioni:
            print(f"{k}) {q.opzioni[k]}")
    print("=" * 80)


def _read_answer() -> str:
    s = input("Risposta (A/B/C/D, invio=omessa, Q=quit): ").strip()
    if not s:
        return ""
    if s.lower() in ("q", "quit", "exit"):
        raise KeyboardInterrupt()
    return s


def _ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def main() -> int:
    api_key = _get_env("GEMINI_API_KEY")
    if not api_key:
        print("ERRORE: GEMINI_API_KEY non è impostata.")
        return 2

    model = _get_env("GEMINI_MODEL", "gemini-2.0-flash")
    temp = float(_get_env("GEMINI_TEMPERATURE", "0.7"))
    max_tokens = int(_get_env("GEMINI_MAX_TOKENS", "1200"))

    project_root = _project_root()

    # --- Gemini ---
    gemini = GeminiClient(
        GeminiConfig(
            api_key=api_key,
            model=model,
            temperature=temp,
            max_output_tokens=max_tokens,
        )
    )

    # --- Engine ---
    engine = SessionEngine(
        project_root=project_root,
        gemini=gemini,
    )

    # --- SD ---
    sd = SDClient(SDConfig.from_env())
    # assicura output dir
    _ensure_dir(Path(sd.config.output_dir))

    state = SessionState()

    print("LUNA STUDY - RIPAM (CLI)")
    print(f"- Root: {project_root}")
    print(f"- Model: {model}")
    print(f"- SD: {sd.config.txt2img_url} (timeout={sd.config.timeout_sec}s)")
    print("Premi Q per uscire.\n")

    while state.question_index < state.total_questions:
        # 1) domanda
        q = engine.start_next_question(state)
        _print_question(q)

        # 2) risposta
        try:
            ans = _read_answer()
        except KeyboardInterrupt:
            print("\nUscita.")
            return 0

        user_choice = ans if ans else None

        # 3) applica punteggio + stage
        res = engine.apply_answer(state, q, user_choice)

        print("\n--- ESITO ---")
        print(f"Esito: {res.outcome} | Delta: {res.delta_score:+.3f} | Score: {res.new_score:.3f}")
        print(f"{res.tutor} -> progress: {res.new_progress} | stage: {res.new_stage}")
        print("Stage attuali:", state.stage)
        print("Progress attuali:", state.progress)

        # 4) genera immagine SEMPRE dopo la risposta
        is_punish = (res.outcome != "corretta")
        stage_now = state.stage[res.tutor]  # stage aggiornato

        # prompt SD con tags+visual dell'LLM (se presenti in q)
        sd_prompt = compile_sd_prompt(
            project_root=project_root,
            tutor=res.tutor,
            stage=stage_now,
            is_punish=is_punish,
            question=q,  # <-- fondamentale: qui passiamo q
        )

        # debug utile: conferma che stai allegando tags+visual
        tags_len = len(getattr(q, "tags", []) or [])
        visual_len = len((getattr(q, "visual", "") or ""))
        print("\n[SD DEBUG] tutor:", res.tutor, "stage:", stage_now, "punish:", is_punish)
        print("[SD DEBUG] tags_len:", tags_len, "| visual_len:", visual_len)
        print("[SD DEBUG] prompt_len:", len(sd_prompt.prompt), "| neg_len:", len(sd_prompt.negative_prompt))
        print("[SD DEBUG] prompt_tail:", sd_prompt.prompt[-250:])

        # file name: tutor + progress/idx
        file_stem = f"{res.tutor.lower()}_{state.question_index:03d}"

        try:
            out = sd.txt2img(
                prompt=sd_prompt.prompt,
                negative_prompt=sd_prompt.negative_prompt,
                file_stem=file_stem,
            )
            print(f"[SD] Immagine salvata: {out.image_path}")
        except Exception as e:
            print(f"[SD] ERRORE generazione immagine: {e}")

    print("\nTest completato.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
