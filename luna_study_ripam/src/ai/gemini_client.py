# src/ai/gemini_client.py
import google.generativeai as genai
from dataclasses import dataclass
import os


@dataclass
class GeminiConfig:
    api_key: str
    # USIAMO LA VERSIONE 3 (Preview) - La più recente assoluta
    model_name: str = "gemini-3-flash-preview"


class GeminiClient:
    def __init__(self, config: GeminiConfig):
        self.config = config
        if not config.api_key or config.api_key == "dummy":
            print("[GEMINI] Warning: API Key mancante o dummy.")
            self.model = None
        else:
            try:
                genai.configure(api_key=config.api_key)
                self.model = genai.GenerativeModel(config.model_name)
            except Exception as e:
                print(f"[GEMINI] Errore configurazione: {e}")
                self.model = None

    def generate_content(self, prompt: str) -> str:
        """
        Invia il prompt a Gemini e restituisce il testo della risposta.
        """
        if not self.model:
            print("[GEMINI] Errore: Modello non inizializzato (manca API Key?).")
            return "{}"

        try:
            # Configurazione per rendere la risposta creativa ma coerente
            generation_config = genai.types.GenerationConfig(
                temperature=0.7
            )

            response = self.model.generate_content(
                prompt,
                generation_config=generation_config
            )

            if not response.parts:
                try:
                    print(f"[GEMINI] Blocco Safety: {response.prompt_feedback}")
                except:
                    pass
                return "{}"

            return response.text
        except Exception as e:
            print(f"[GEMINI] Errore generazione (Modello: {self.config.model_name}): {e}")
            return "{}"