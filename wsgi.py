"""Punto de entrada WSGI para producción (gunicorn)."""
from app import create_app

app = create_app()
