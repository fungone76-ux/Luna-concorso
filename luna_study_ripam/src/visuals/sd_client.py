# src/visuals/sd_client.py
import base64
import requests
import os
from dataclasses import dataclass


@dataclass
class SDConfig:
    url: str = "http://127.0.0.1:7860"

    @staticmethod
    def from_env():
        return SDConfig()


class SDClient:
    def __init__(self, config: SDConfig):
        self.config = config

    def generate_image(self, prompt: str, negative_prompt: str, output_path: str):
        """
        Invia la richiesta a Stable Diffusion WebUI (Automatic1111) e salva l'immagine.
        """
        payload = {
            "prompt": prompt,
            "negative_prompt": negative_prompt,
            "steps": 24,
            "cfg_scale": 7,
            "width": 512,  # Verticale per ritratti, puoi mettere 512x768 se vuoi
            "height": 768,
            "sampler_name": "DPM++ 2M Karras",
            "batch_size": 1,
        }

        try:
            response = requests.post(f"{self.config.url}/sdapi/v1/txt2img", json=payload, timeout=760)

            if response.status_code == 200:
                r = response.json()
                if "images" in r and r["images"]:
                    # Decodifica l'immagine base64
                    image_data = base64.b64decode(r["images"][0])

                    # Salva su disco
                    with open(output_path, "wb") as f:
                        f.write(image_data)
                    print(f"[SD] Immagine salvata: {output_path}")
                    return True
            else:
                print(f"[SD] Errore API: {response.status_code} - {response.text}")

        except requests.exceptions.ConnectionError:
            print("[SD] Errore: Impossibile connettersi a Stable Diffusion. Assicurati che WebUI sia aperto con --api")
        except Exception as e:
            print(f"[SD] Errore generico: {e}")

        return False