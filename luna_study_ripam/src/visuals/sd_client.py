# src/visuals/sd_client.py
from __future__ import annotations

import base64
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import requests


@dataclass(frozen=True)
class SDConfig:
    """
    Config per Automatic1111.
    Puoi settare tutto via env senza toccare codice:

    - SD_TXT2IMG_URL       (default: http://127.0.0.1:7860/sdapi/v1/txt2img)
    - SD_TIMEOUT_SEC       (default: 720)
    - SD_OUTPUT_DIR        (default: outputs/images)
    - SD_WIDTH             (default: 768)
    - SD_HEIGHT            (default: 1024)
    - SD_STEPS             (default: 28)
    - SD_CFG_SCALE         (default: 6.5)
    - SD_SAMPLER           (default: DPM++ 2M Karras)
    - SD_SEED              (default: -1 -> random)
    """
    txt2img_url: str = "http://127.0.0.1:7860/sdapi/v1/txt2img"
    timeout_sec: int = 720
    output_dir: str = "outputs/images"

    width: int = 768
    height: int = 1024
    steps: int = 24
    cfg_scale: float = 7
    sampler_name: str = "DPM++ 2M Karras"
    seed: int = -1

    @staticmethod
    def from_env() -> "SDConfig":
        import os

        def _int(name: str, default: int) -> int:
            v = os.getenv(name)
            if v is None or not v.strip():
                return default
            try:
                return int(v)
            except Exception:
                return default

        def _float(name: str, default: float) -> float:
            v = os.getenv(name)
            if v is None or not v.strip():
                return default
            try:
                return float(v)
            except Exception:
                return default

        return SDConfig(
            txt2img_url=os.getenv("SD_TXT2IMG_URL", SDConfig.txt2img_url),
            timeout_sec=_int("SD_TIMEOUT_SEC", SDConfig.timeout_sec),
            output_dir=os.getenv("SD_OUTPUT_DIR", SDConfig.output_dir),
            width=_int("SD_WIDTH", SDConfig.width),
            height=_int("SD_HEIGHT", SDConfig.height),
            steps=_int("SD_STEPS", SDConfig.steps),
            cfg_scale=_float("SD_CFG_SCALE", SDConfig.cfg_scale),
            sampler_name=os.getenv("SD_SAMPLER", SDConfig.sampler_name),
            seed=_int("SD_SEED", SDConfig.seed),
        )


@dataclass(frozen=True)
class SDResult:
    image_path: str
    seed: Optional[int] = None
    info: Optional[Dict[str, Any]] = None


class SDClient:
    """
    Client minimale per Automatic1111 txt2img.

    - Prende prompt e negative_prompt
    - Fa POST su /sdapi/v1/txt2img
    - Salva PNG su disco (outputs/images)
    """

    def __init__(self, config: Optional[SDConfig] = None):
        self.config = config or SDConfig.from_env()

    def txt2img(
        self,
        prompt: str,
        negative_prompt: str = "",
        *,
        width: Optional[int] = None,
        height: Optional[int] = None,
        steps: Optional[int] = None,
        cfg_scale: Optional[float] = None,
        sampler_name: Optional[str] = None,
        seed: Optional[int] = None,
        extra_payload: Optional[Dict[str, Any]] = None,
        file_stem: Optional[str] = None,
    ) -> SDResult:
        """
        Genera un'immagine con A1111.

        extra_payload:
          - se vuoi passare override_settings, enable_hr, lora via prompt, etc.
        file_stem:
          - nome base del file (senza estensione). Se None, usa timestamp.
        """
        payload = {
            "prompt": prompt,
            "negative_prompt": negative_prompt,
            "width": int(width if width is not None else self.config.width),
            "height": int(height if height is not None else self.config.height),
            "steps": int(steps if steps is not None else self.config.steps),
            "cfg_scale": float(cfg_scale if cfg_scale is not None else self.config.cfg_scale),
            "sampler_name": str(sampler_name if sampler_name is not None else self.config.sampler_name),
            "seed": int(seed if seed is not None else self.config.seed),
        }

        if extra_payload:
            # NON sovrascrivere i campi base se non vuoi: qui li merge-iamo
            payload.update(extra_payload)

        resp = requests.post(
            self.config.txt2img_url,
            json=payload,
            timeout=self.config.timeout_sec,
        )
        try:
            resp.raise_for_status()
        except Exception as e:
            # prova a mostrare un msg utile
            detail = ""
            try:
                detail = resp.text[:1500]
            except Exception:
                detail = "<no response text>"
            raise RuntimeError(f"SD txt2img error: {e}\nResponse: {detail}") from e

        data = resp.json()
        img_b64 = _extract_first_image_b64(data)
        info = _extract_info_dict(data)

        # seed: spesso A1111 la mette dentro info come JSON string
        used_seed = _try_extract_seed(info)

        out_dir = Path(self.config.output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)

        if not file_stem:
            file_stem = time.strftime("%Y%m%d_%H%M%S")

        # evitiamo collisioni
        out_path = _unique_path(out_dir / f"{file_stem}.png")
        out_path.write_bytes(base64.b64decode(img_b64))

        return SDResult(image_path=str(out_path), seed=used_seed, info=info)


# -------------------------
# Helpers
# -------------------------

def _extract_first_image_b64(data: Dict[str, Any]) -> str:
    images = data.get("images")
    if not isinstance(images, list) or not images:
        raise RuntimeError("SD response non contiene 'images' (lista base64).")
    first = images[0]
    if not isinstance(first, str) or not first.strip():
        raise RuntimeError("SD response 'images[0]' non è una stringa base64 valida.")
    return first


def _extract_info_dict(data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    info = data.get("info")
    # A1111 spesso mette "info" come stringa JSON
    if info is None:
        return None
    if isinstance(info, dict):
        return info
    if isinstance(info, str) and info.strip():
        try:
            return json.loads(info)
        except Exception:
            return {"raw_info": info}
    return None


def _try_extract_seed(info: Optional[Dict[str, Any]]) -> Optional[int]:
    if not info:
        return None
    # Alcune build mettono "seed" o "all_seeds"
    if "seed" in info:
        try:
            return int(info["seed"])
        except Exception:
            pass
    if "all_seeds" in info and isinstance(info["all_seeds"], list) and info["all_seeds"]:
        try:
            return int(info["all_seeds"][0])
        except Exception:
            pass
    return None


def _unique_path(path: Path) -> Path:
    if not path.exists():
        return path
    stem = path.stem
    suffix = path.suffix
    parent = path.parent
    i = 2
    while True:
        p = parent / f"{stem}_{i}{suffix}"
        if not p.exists():
            return p
        i += 1
