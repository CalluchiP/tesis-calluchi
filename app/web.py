"""Interfaz web (capa de presentación). Consume la misma API /api que un frontend externo."""
from flask import Blueprint, render_template

bp = Blueprint("web", __name__)


@bp.get("/")
def index():
    return render_template("index.html")
