"""
Download required offline models:
1. Silero VAD v5 ONNX model (~1.8 MB)
2. Vosk Small English US Model v0.15 (~40 MB)
"""

import os
import urllib.request
import zipfile

MODELS_DIR = "/home/rayyan-error/Projects/Uranus/models"

SILERO_VAD_URL = "https://raw.githubusercontent.com/snakers4/silero-vad/master/src/silero_vad/data/silero_vad.onnx"
SILERO_VAD_PATH = os.path.join(MODELS_DIR, "silero_vad.onnx")

VOSK_MODEL_URL = "https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip"
VOSK_ZIP_PATH = os.path.join(MODELS_DIR, "vosk-model-small-en-us-0.15.zip")
VOSK_EXTRACT_PATH = os.path.join(MODELS_DIR, "vosk-model-small-en-us-0.15")


def download_file(url: str, dest: str):
    print(f"Downloading {url} -> {dest} ...")
    urllib.request.urlretrieve(url, dest)
    print(f"Done: {os.path.getsize(dest)} bytes.")


def main():
    os.makedirs(MODELS_DIR, exist_ok=True)

    # 1. Silero VAD
    if not os.path.exists(SILERO_VAD_PATH):
        download_file(SILERO_VAD_URL, SILERO_VAD_PATH)
    else:
        print(f"Silero VAD already exists at {SILERO_VAD_PATH}")

    # 2. Vosk Model
    if not os.path.exists(VOSK_EXTRACT_PATH):
        if not os.path.exists(VOSK_ZIP_PATH):
            download_file(VOSK_MODEL_URL, VOSK_ZIP_PATH)
        print(f"Extracting {VOSK_ZIP_PATH} ...")
        with zipfile.ZipFile(VOSK_ZIP_PATH, 'r') as zip_ref:
            zip_ref.extractall(MODELS_DIR)
        print("Extraction complete.")
        if os.path.exists(VOSK_ZIP_PATH):
            os.remove(VOSK_ZIP_PATH)
    else:
        print(f"Vosk model already exists at {VOSK_EXTRACT_PATH}")

    print("All models ready.")


if __name__ == "__main__":
    main()
