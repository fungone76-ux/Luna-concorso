# src/voice_narrator.py
"""
Gestisce la sintesi vocale tramite Google Cloud TTS e riproduzione con Pygame.
Supporta voci diverse per ogni Tutor.
"""

import threading
import time
import os
import re
import tempfile
import uuid
from typing import Optional

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

# --- CONFIGURAZIONE ---
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "google_credentials.json"

# Mappa Voci per Tutor (TUTTE FEMMINILI)
# it-IT-Neural2-A = Femminile (Neural)
# it-IT-Neural2-C = Maschile (DA EVITARE per donne)
# it-IT-Wavenet-A = Femminile (Wavenet)
# it-IT-Wavenet-B = Femminile (Wavenet)
VOICE_MAP = {
    "Luna": "it-IT-Neural2-A",  # Voce Neural (Alta qualità)
    "Maria": "it-IT-Wavenet-A",  # Voce Wavenet (Femminile 1)
    "Stella": "it-IT-Wavenet-B",  # Voce Wavenet (Femminile 2)
    "default": "it-IT-Neural2-A"
}

# Stato interno
_audio_thread: Optional[threading.Thread] = None
_stop_event = threading.Event()
_is_initialized = False
_init_lock = threading.Lock()


def _sanitize_text_for_tts(text: str) -> str:
    if not text: return ""
    s = str(text).strip()
    s = s.replace("*", "")
    s = re.sub(r"<[^>]+>", " ", s)
    s = re.sub(r"[\[\(][^\]\)]+[\]\)]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _generate_file_google(text: str, out_path: str, voice_name: str):
    """Genera audio con la voce specifica."""
    if not texttospeech:
        raise ImportError("Libreria google.cloud.texttospeech mancante")

    try:
        client = texttospeech.TextToSpeechClient()
        synthesis_input = texttospeech.SynthesisInput(text=text)

        voice = texttospeech.VoiceSelectionParams(
            language_code="it-IT",
            name=voice_name
        )

        audio_config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.MP3,
            speaking_rate=1.1,
            pitch=0.0
        )

        response = client.synthesize_speech(
            input=synthesis_input, voice=voice, audio_config=audio_config
        )

        with open(out_path, "wb") as out:
            out.write(response.audio_content)

    except Exception as e:
        print(f"[GOOGLE TTS] ❌ Errore API ({voice_name}): {e}")
        raise e


def _playback_worker(text: str, tutor: str):
    """Genera un file UNIVOCO per il tutor specifico, lo suona e poi lo cancella."""
    temp_path = None
    try:
        clean_text = _sanitize_text_for_tts(text)
        if not clean_text:
            return

        # Recupera la voce corretta
        voice_name = VOICE_MAP.get(tutor, VOICE_MAP["default"])

        unique_name = f"voice_{tutor}_{uuid.uuid4().hex}.mp3"
        temp_path = os.path.join(tempfile.gettempdir(), unique_name)

        # Generazione
        try:
            _generate_file_google(clean_text, temp_path, voice_name)
        except Exception:
            return

        # Riproduzione
        if os.path.exists(temp_path) and os.path.getsize(temp_path) > 0:
            if not pygame or not pygame.mixer.get_init():
                return

            try:
                pygame.mixer.music.load(temp_path)
                pygame.mixer.music.play()

                while pygame.mixer.music.get_busy() and not _stop_event.is_set():
                    pygame.time.Clock().tick(10)

                if _stop_event.is_set():
                    pygame.mixer.music.stop()

                try:
                    pygame.mixer.music.unload()
                except AttributeError:
                    pass

            except Exception as e:
                print(f"[AUDIO] Errore riproduzione: {e}")

    except Exception as e:
        print(f"[AUDIO] Errore worker: {e}")

    finally:
        if temp_path and os.path.exists(temp_path):
            try:
                time.sleep(0.1)
                os.remove(temp_path)
            except Exception:
                pass


def init_narrator():
    global _is_initialized
    if not pygame: return
    with _init_lock:
        if _is_initialized: return
        try:
            pygame.mixer.init()
            _is_initialized = True
            print("[AUDIO] Narrator Google inizializzato (Multi-Voce).")
        except Exception as e:
            print(f"[AUDIO] Errore init pygame: {e}")


def speak(text: str, tutor: str = "Luna"):
    """Avvia la lettura del testo con la voce del tutor specificato."""
    global _audio_thread
    if not text: return

    if not _is_initialized:
        init_narrator()

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
            except AttributeError:
                pass
        except Exception:
            pass


def shutdown_narrator():
    stop()
    if pygame:
        try:
            pygame.mixer.quit()
        except Exception:
            pass