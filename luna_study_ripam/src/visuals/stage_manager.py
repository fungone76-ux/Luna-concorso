# src/visuals/stage_manager.py
from dataclasses import dataclass
from src.domain.models import SessionState


@dataclass
class StageUpdate:
    new_stage: int
    new_progress: int
    is_punish: bool
    # CAMPO MANCANTE AGGIUNTO:
    outcome: str  # "corretta" o "errata"


class StageManager:
    def __init__(self, step: int = 10, min_stage: int = 1, max_stage: int = 5):
        self.step = step
        self.min_stage = min_stage
        self.max_stage = max_stage

    def apply_outcome(self, state: SessionState, tutor: str, outcome: str) -> StageUpdate:
        """
        Calcola i nuovi punti e lo stage in base alla risposta.
        """
        current_points = state.progress.get(tutor, 0)
        current_stage = state.stage.get(tutor, 1)

        is_punish = False

        if outcome == "corretta":
            # Aumenta punti
            current_points += 10
            # Logica avanzamento stage (ogni self.step punti, sali di 1)
            # Esempio: a 10 punti -> stage 2
            potential_stage = 1 + (current_points // self.step)
            current_stage = min(potential_stage, self.max_stage)

        elif outcome == "errata":
            # Logica punizione
            current_points = max(0, current_points - 5)  # Perde 5 punti ma non va sotto zero
            is_punish = True
            # Retrocessione stage? Per ora manteniamo lo stage o lo ricalcoliamo
            potential_stage = 1 + (current_points // self.step)
            current_stage = max(self.min_stage, min(potential_stage, self.max_stage))

        # Aggiorna lo stato globale
        state.progress[tutor] = current_points
        state.stage[tutor] = current_stage

        return StageUpdate(
            new_stage=current_stage,
            new_progress=current_points,
            is_punish=is_punish,
            outcome=outcome  # Ora passiamo l'esito alla GUI!
        )