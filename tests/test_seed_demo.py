from app import create_app
from app.models import Evaluacion, Usuario
from scripts.seed_demo import sembrar


def test_seed_demo_crea_usuario_y_evaluacion(tmp_path):
    app = create_app({"TESTING": True,
                      "SQLALCHEMY_DATABASE_URI": f"sqlite:///{tmp_path/'seed.db'}"})
    with app.app_context():
        r = sembrar(app)
        assert r == {"usuarios_creados": 2, "evaluaciones_creadas": 1}
        assert Usuario.query.count() == 2
        assert Evaluacion.query.count() == 1
        assert Usuario.query.filter_by(email="demo@example.test").one().check_password("Demo12345")
        assert Usuario.query.filter_by(email="prueba@example.test").one().check_password("Prueba12345")

        r2 = sembrar(app)
        assert r2 == {"usuarios_creados": 0, "evaluaciones_creadas": 0}
        assert Evaluacion.query.count() == 1
