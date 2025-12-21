from dataclasses import dataclass
from src.domain.models import SessionState


@dataclass
class StageUpdate:
    new_stage: int
    new_progress: int
    is_punish: bool
    outcome: str


class StageManager:
    def __init__(self, step: int = 10, min_stage: int = 1, max_stage: int = 5):
        self.step = step  # Soglia punti per cambiare livello (es. 10)
        self.min_stage = min_stage
        self.max_stage = max_stage

    def apply_outcome(self, state: SessionState, tutor: str, outcome: str) -> StageUpdate:
        """
        Calcola i nuovi punti e lo stage.
        Regola: +1 punto se corretta, -1 se errata.
        Stage: 0-10 -> Stg 1 | 11-20 -> Stg 2 | 21-30 -> Stg 3 | ecc.
        """
        # Recupera i punti attuali (default 0)
        current_points = state.progress.get(tutor, 0)

        is_punish = False

        # --- 1. AGGIORNAMENTO PUNTEGGIO ---
        if outcome == "corretta":
            current_points += 1
        elif outcome == "errata":
            # Sottrae 1 punto, ma non scende sotto 0 (evita bug di logica)
            current_points = max(0, current_points - 1)
            is_punish = True

        # --- 2. CALCOLO STAGE MATEMATICO ---
        # La formula gestisce le soglie: 1-10=1, 11-20=2, 21-30=3
        if current_points <= self.step:
            calculated_stage = 1
        else:
            # Esempio: con step 10
            # Punti 11 -> (10 // 10) + 1 = 2
            # Punti 20 -> (19 // 10) + 1 = 2
            # Punti 21 -> (20 // 10) + 1 = 3
            calculated_stage = ((current_points - 1) // self.step) + 1

        # Assicuriamo che lo stage resti tra 1 e 5
        current_stage = max(self.min_stage, min(calculated_stage, self.max_stage))

        # --- 3. SALVATAGGIO STATO ---
        state.progress[tutor] = current_points
        state.stage[tutor] = current_stage

        return StageUpdate(
            new_stage=current_stage,
            new_progress=current_points,
            is_punish=is_punish,
            outcome=outcome
        )