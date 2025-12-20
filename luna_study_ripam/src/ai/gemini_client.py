# src/ai/gemini_client.py
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class GeminiConfig:
    api_key: str
    model: str = "gemini-2.0-flash"  # cambia in .env/config se vuoi
    temperature: float = 0.7
    max_output_tokens: int = 1200


class GeminiClient:
    """
    Client basato sul nuovo SDK google.genai (pacchetto: google-genai).
    Restituisce sempre il testo generato, e offre helper per JSON.
    """

    def __init__(self, cfg: GeminiConfig):
        if not cfg.api_key:
            raise ValueError("GeminiConfig.api_key è vuoto.")
        self.cfg = cfg

        # Import SOLO nuovo SDK
        from google import genai  # type: ignore
        from google.genai import types  # type: ignore

        self._types = types
        self._client = genai.Client(
            api_key=cfg.api_key,
            http_options=types.HttpOptions(api_version="v1"),
        )

    def generate_text(self, prompt: str) -> str:
        """
        Genera testo dal modello.
        """
        types = self._types
        resp = self._client.models.generate_content(
            model=self.cfg.model,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=self.cfg.temperature,
                max_output_tokens=self.cfg.max_output_tokens,
            ),
        )
        text = (resp.text or "").strip()
        if not text:
            raise RuntimeError("Risposta vuota da Gemini.")
        return text

    def generate_json(self, prompt: str) -> Dict[str, Any]:
        """
        Chiede al modello di produrre JSON e lo parse-a.
        Tenta anche estrazione robusta se il modello “incarta” il JSON.
        """
        raw = self.generate_text(prompt)
        json_text = _extract_json_text(raw)
        try:
            return json.loads(json_text)
        except Exception as e:
            raise RuntimeError(
                "JSON non valido da Gemini.\n"
                f"RAW (inizio): {raw[:800]}\n"
                f"JSON_EXTRACT (inizio): {json_text[:800]}"
            ) from e


def _extract_json_text(raw: str) -> str:
    """
    Estrae JSON da:
    - raw JSON puro
    - raw con ```json ... ```
    - raw con testo extra (cerchiamo la prima { e l'ultima })
    """
    s = raw.strip()

    # Caso 1: blocco markdown ```json
    if s.startswith("```"):
        # rimuove le triple backtick iniziali/finali
        s = s.strip("`").strip()
        # se inizia con "json\n"
        if s.lower().startswith("json"):
            s = s.split("\n", 1)[-1].strip()

    # Caso 2: già JSON
    if s.startswith("{") and s.endswith("}"):
        return s

    # Caso 3: estrai tra prima { e ultima }
    first = s.find("{")
    last = s.rfind("}")
    if first != -1 and last != -1 and last > first:
        return s[first : last + 1]

    # fallback: ritorna tutto e lasciamo fallire json.loads con errore chiaro
    return s
