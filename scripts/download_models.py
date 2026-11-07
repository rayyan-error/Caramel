"""
Download required offline models:
1. Silero VAD v5 ONNX model (~1.8 MB)
2. Vosk Small English US Model v0.15 (~40 MB)
"""

from pathlib import Path
import urllib.request
import zipfile

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MODELS_DIR = PROJECT_ROOT / "models"

SILERO_VAD_URL = "https://raw.githubusercontent.com/snakers4/silero-vad/master/src/silero_vad/data/silero_vad.onnx"
SILERO_VAD_PATH = MODELS_DIR / "silero_vad.onnx"

VOSK_MODEL_URL = "https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip"
VOSK_ZIP_PATH = MODELS_DIR / "vosk-model-small-en-us-0.15.zip"
VOSK_EXTRACT_PATH = MODELS_DIR / "vosk-model-small-en-us-0.15"


def download_file(url: str, dest: Path):
    print(f"Downloading {url} -> {dest} ...")
    urllib.request.urlretrieve(url, str(dest))
    print(f"Done: {dest.stat().st_size} bytes.")


def main():
    MODELS_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Silero VAD
    if not SILERO_VAD_PATH.exists():
        download_file(SILERO_VAD_URL, SILERO_VAD_PATH)
    else:
        print(f"Silero VAD already exists at {SILERO_VAD_PATH}")

    # 2. Vosk Model
    if not VOSK_EXTRACT_PATH.exists():
        if not VOSK_ZIP_PATH.exists():
            download_file(VOSK_MODEL_URL, VOSK_ZIP_PATH)
        print(f"Extracting {VOSK_ZIP_PATH} ...")
        with zipfile.ZipFile(str(VOSK_ZIP_PATH), 'r') as zip_ref:
            zip_ref.extractall(str(MODELS_DIR))
        print("Extraction complete.")
        if VOSK_ZIP_PATH.exists():
            VOSK_ZIP_PATH.unlink()
    else:
        print(f"Vosk model already exists at {VOSK_EXTRACT_PATH}")

    print("All models ready.")


if __name__ == "__main__":
    main()
