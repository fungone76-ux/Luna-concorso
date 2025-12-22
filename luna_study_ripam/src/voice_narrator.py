# src/voice_narrator.py
"""
Gestisce la sintesi vocale tramite Google Cloud TTS.
FIX: Supporto per testi lunghi (>5000 bytes) tramite chunking automatico.
"""

import threading
import time
import os
import re
import tempfile
import uuid
from typing import Optional, List
from pathlib import Path

# Import Google Cloud TTS
try:
    from google.cloud import texttospeech
except ImportError:
    print("[AUDIO] Warning: google-cloud-texttospeech non installato.")
    texttospeech = None

# Import Pygame
try:
    import pygame
except Exception:
    print("[AUDIO] Warning: pygame non installato.")
    pygame = None

# --- CONFIGURAZIONE CREDENZIALI ---
BASE_DIR = Path(__file__).resolve().parent.parent
CREDENTIALS_FILE = "google_credentials.json"
CREDENTIALS_PATH = BASE_DIR / CREDENTIALS_FILE

if CREDENTIALS_PATH.exists():
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(CREDENTIALS_PATH)
    print(f"[AUDIO] Credenziali trovate in: {CREDENTIALS_PATH}")
else:
    print(f"[AUDIO] ATTENZIONE: {CREDENTIALS_FILE} mancante!")

# Mappa Voci
VOICE_MAP = {
    "Luna": "it-IT-Neural2-A",
    "Maria": "it-IT-Wavenet-A",
    "Stella": "it-IT-Wavenet-B",
    "default": "it-IT-Neural2-A"
}

_audio_thread: Optional[threading.Thread] = None
_stop_event = threading.Event()
_is_initialized = False
_init_lock = threading.Lock()


def _sanitize_text_for_tts(text: str) -> str:
    """Pulisce il testo e espande le abbreviazioni legali."""
    if not text: return ""
    s = str(text).strip()
    s = s.replace("*", "").replace("_", "").replace("#", "")
    s = re.sub(r"<[^>]+>", " ", s)
    s = re.sub(r"\[.*?\]", "", s)

    # Espansione Leggi (Smart Reading)
    s = re.sub(r'\b[Ll]\.?\s*(\d+)/(\d+)', r'Legge \1 del \2', s)
    s = re.sub(r'\bD\.?Lgs\.?\s*(\d+)/(\d+)', r'Decreto Legislativo \1 del \2', s, flags=re.IGNORECASE)
    s = re.sub(r'\bDPR\s*(\d+)/(\d+)', r'Decreto del Presidente della Repubblica \1 del \2', s, flags=re.IGNORECASE)
    s = re.sub(r'\bArt\.\s*(\d+)', r'Articolo \1', s, flags=re.IGNORECASE)

    return re.sub(r"\s+", " ", s).strip()


def _split_text(text: str, max_chars: int = 4000) -> List[str]:
    """Divide il testo in pezzi più piccoli di max_chars senza tagliare le parole."""
    if len(text) <= max_chars:
        return [text]

    chunks = []
    while len(text) > max_chars:
        # Cerca l'ultimo punto fermo entro il limite
        split_idx = text.rfind('.', 0, max_chars)
        if split_idx == -1:
            # Se non ci sono punti, cerca uno spazio
            split_idx = text.rfind(' ', 0, max_chars)
        if split_idx == -1:
            # Se è una parola gigante, taglia brutalmente
            split_idx = max_chars

        chunks.append(text[:split_idx + 1])
        text = text[split_idx + 1:].strip()

    if text:
        chunks.append(text)
    return chunks


def _generate_file_google(text: str, out_path: str, voice_name: str):
    if not texttospeech: return
    try:
        client = texttospeech.TextToSpeechClient()
        synthesis_input = texttospeech.SynthesisInput(text=text)
        voice = texttospeech.VoiceSelectionParams(language_code="it-IT", name=voice_name)
        audio_config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.MP3,
            speaking_rate=1.1,
            pitch=0.0
        )
        response = client.synthesize_speech(input=synthesis_input, voice=voice, audio_config=audio_config)
        with open(out_path, "wb") as out:
            out.write(response.audio_content)
    except Exception as e:
        print(f"[GOOGLE TTS] Errore: {e}")


def _playback_worker(text: str, tutor: str):
    try:
        clean_text = _sanitize_text_for_tts(text)
        if not clean_text: return

        # DIVIDI IL TESTO IN CHUNK PER EVITARE L'ERRORE 5000 BYTES
        chunks = _split_text(clean_text)

        voice_name = VOICE_MAP.get(tutor, VOICE_MAP["default"])

        # Per ogni pezzo di testo...
        for i, chunk in enumerate(chunks):
            if _stop_event.is_set(): break

            unique_name = f"voice_{tutor}_{uuid.uuid4().hex}_{i}.mp3"
            temp_path = os.path.join(tempfile.gettempdir(), unique_name)

            _generate_file_google(chunk, temp_path, voice_name)

            if os.path.exists(temp_path) and os.path.getsize(temp_path) > 0:
                if not pygame or not pygame.mixer.get_init(): break

                try:
                    pygame.mixer.music.load(temp_path)
                    pygame.mixer.music.play()

                    while pygame.mixer.music.get_busy() and not _stop_event.is_set():
                        pygame.time.Clock().tick(10)
                except:
                    pass

            # Pulizia file temporaneo
            if temp_path and os.path.exists(temp_path):
                try:
                    pygame.mixer.music.unload()
                    time.sleep(0.1)
                    os.remove(temp_path)
                except:
                    pass

    except Exception as e:
        print(f"[AUDIO] Errore worker: {e}")


def init_narrator():
    global _is_initialized
    if not pygame: return
    with _init_lock:
        if _is_initialized: return
        try:
            pygame.mixer.init()
            _is_initialized = True
            print("[AUDIO] Narrator Google Inizializzato.")
        except Exception as e:
            print(f"[AUDIO] Errore init pygame: {e}")


def speak(text: str, tutor: str = "Luna"):
    global _audio_thread
    if not text: return
    if not _is_initialized: init_narrator()
    stop()
    _stop_event.clear()
    _audio_thread = threading.Thread(target=_playback_worker, args=(text, tutor), daemon=True)
    _audio_thread.start()


def stop():
    _stop_event.set()
    if pygame and pygame.mixer.get_init():
        try:
            pygame.mixer.music.stop()
            try:
                pygame.mixer.music.unload()
            except:
                pass
        except:
            pass


def shutdown_narrator():
    stop()
    if pygame:
        try:
            pygame.mixer.quit()
        except:
            pass