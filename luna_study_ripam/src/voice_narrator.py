"""
src/voice_narrator.py
Gestisce la sintesi vocale tramite Google Cloud TTS e riproduzione con Pygame.
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
# Assicurati che questo file esista nella root del progetto
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "google_credentials.json"

# Voce Femminile Italiana (Neural2-A è femminile, C è maschile)
GOOGLE_VOICE_NAME = "it-IT-Neural2-A"

# Stato interno
_audio_thread: Optional[threading.Thread] = None
_stop_event = threading.Event()
_is_initialized = False
_init_lock = threading.Lock()

def _sanitize_text_for_tts(text: str) -> str:
    if not text: return ""
    s = str(text).strip()
    s = s.replace("*", "")
    # Rimuove tag HTML/XML e parentesi quadre/tonde che contengono metadati
    s = re.sub(r"<[^>]+>", " ", s)
    s = re.sub(r"[\[\(][^\]\)]+[\]\)]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s

def _generate_file_google(text: str, out_path: str):
    """Genera audio e lo salva in un percorso specifico."""
    if not texttospeech:
        raise ImportError("Libreria google.cloud.texttospeech mancante")

    try:
        client = texttospeech.TextToSpeechClient()
        synthesis_input = texttospeech.SynthesisInput(text=text)

        voice = texttospeech.VoiceSelectionParams(
            language_code="it-IT",
            name=GOOGLE_VOICE_NAME
        )

        audio_config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.MP3,
            speaking_rate=1.1, # Leggermente più veloce per dinamismo
            pitch=0.0
        )

        response = client.synthesize_speech(
            input=synthesis_input, voice=voice, audio_config=audio_config
        )

        with open(out_path, "wb") as out:
            out.write(response.audio_content)

    except Exception as e:
        print(f"[GOOGLE TTS] ❌ Errore API: {e}")
        raise e

def _playback_worker(text: str):
    """Genera un file UNIVOCO, lo suona e poi lo cancella."""
    temp_path = None
    try:
        clean_text = _sanitize_text_for_tts(text)
        if not clean_text:
            return

        # 1. Crea un percorso file UNIVOCO
        unique_name = f"voice_{uuid.uuid4().hex}.mp3"
        temp_path = os.path.join(tempfile.gettempdir(), unique_name)

        # 2. Generazione
        try:
            _generate_file_google(clean_text, temp_path)
        except Exception:
            return

        # 3. Riproduzione
        if os.path.exists(temp_path) and os.path.getsize(temp_path) > 0:
            if not pygame or not pygame.mixer.get_init():
                return

            try:
                pygame.mixer.music.load(temp_path)
                pygame.mixer.music.play()

                # Attesa attiva con check dello stop_event
                while pygame.mixer.music.get_busy() and not _stop_event.is_set():
                    pygame.time.Clock().tick(10)

                if _stop_event.is_set():
                    pygame.mixer.music.stop()

                # Libera il file
                try:
                    pygame.mixer.music.unload()
                except AttributeError:
                    pass

            except Exception as e:
                print(f"[AUDIO] Errore riproduzione: {e}")

    except Exception as e:
        print(f"[AUDIO] Errore worker: {e}")

    finally:
        # 4. Pulizia file temporaneo
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
            print("[AUDIO] Narrator Google inizializzato (Voce Femminile).")
        except Exception as e:
            print(f"[AUDIO] Errore init pygame: {e}")

def speak(text: str):
    """Avvia la lettura del testo in un thread separato."""
    global _audio_thread
    if not text: return

    if not _is_initialized:
        init_narrator()

    # Ferma eventuale audio precedente
    stop()
    _stop_event.clear()

    _audio_thread = threading.Thread(target=_playback_worker, args=(text,), daemon=True)
    _audio_thread.start()

def stop():
    """Interrompe immediatamente la riproduzione."""
    _stop_event.set()
    if pygame and pygame.mixer.get_init():
        try:
            pygame.mixer.music.stop()
            # unload per rilasciare il file lock su Windows
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