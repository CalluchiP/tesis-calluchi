import os
from pathlib import Path

from dotenv import load_dotenv

BASE = Path(__file__).resolve().parent.parent
load_dotenv(BASE / ".env")


def _database_url():
    url = os.getenv("DATABASE_URL", f"sqlite:///{BASE / 'riesgo_tributario.db'}")
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    return url


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-inseguro")
    SQLALCHEMY_DATABASE_URI = _database_url()
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    TOKEN_MAX_AGE_SEG = int(os.getenv("TOKEN_MAX_AGE_SEG", 28800))
    MODELO_ACTIVO = os.getenv("MODELO_ACTIVO", "auto")
    TARIFA_HORA_SOLES = float(os.getenv("TARIFA_HORA_SOLES", 35))
    MAX_CONTENT_LENGTH = 10 * 1024 * 1024
    MODELS_DIR = BASE / "models"
