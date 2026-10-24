import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Base directories
BASE_DIR = Path(__file__).resolve().parent
TEMP_DIR = BASE_DIR / "temp"
OUTPUT_DIR = BASE_DIR / "output"
MODELS_DIR = BASE_DIR / "models"
STATIC_DIR = BASE_DIR / "static"

# Create required directories if they don't exist
for d in [TEMP_DIR, OUTPUT_DIR, MODELS_DIR, STATIC_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# Whisper Speech-to-Text configuration
DEFAULT_WHISPER_MODEL = os.getenv("WHISPER_MODEL", "base")  # tiny, base, small, medium, large-v3
DEFAULT_DEVICE = os.getenv("WHISPER_DEVICE", "cpu")         # "cuda" or "cpu"
DEFAULT_COMPUTE_TYPE = os.getenv("WHISPER_COMPUTE_TYPE", "int8" if DEFAULT_DEVICE == "cpu" else "float16")

# Google Gemini API configuration
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
DEFAULT_GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")



# Server settings
HOST = os.getenv("SERVER_HOST", "127.0.0.1")
PORT = int(os.getenv("SERVER_PORT", "8000"))
MAX_UPLOAD_SIZE_MB = int(os.getenv("MAX_UPLOAD_SIZE_MB", "500"))
