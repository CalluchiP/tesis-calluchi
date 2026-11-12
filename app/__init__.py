from flask import Flask, jsonify

from app.config import Config
from app.models import db
from app.services.predictor import Predictor


def create_app(config=None):
    app = Flask(__name__)
    app.config.from_object(Config)
    if config:
        app.config.update(config)
    db.init_app(app)
    app.predictor = Predictor(app.config["MODELS_DIR"], app.config["MODELO_ACTIVO"])
    from app.routes import bp
    from app.web import bp as web_bp
    app.register_blueprint(bp)
    app.register_blueprint(web_bp)
    with app.app_context():
        db.create_all()

    @app.errorhandler(404)
    def _404(_):
        return jsonify(error="Ruta no encontrada"), 404

    @app.errorhandler(413)
    def _413(_):
        return jsonify(error="Archivo demasiado grande (máx. 10 MB)"), 413

    @app.errorhandler(500)
    def _500(_):
        return jsonify(error="Error interno"), 500

    return app
