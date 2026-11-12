from datetime import datetime, timezone

from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import check_password_hash, generate_password_hash

db = SQLAlchemy()


def ahora():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Usuario(db.Model):
    __tablename__ = "usuarios"
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(160), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    rol = db.Column(db.String(20), default="contador", nullable=False)  # contador | admin
    tarifa_hora = db.Column(db.Float)                                    # S/ por hora (indicador C)
    creado = db.Column(db.DateTime, default=ahora)

    def set_password(self, p):
        self.password_hash = generate_password_hash(p)

    def check_password(self, p):
        return check_password_hash(self.password_hash, p)


class Evaluacion(db.Model):
    __tablename__ = "evaluaciones"
    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey("usuarios.id"), nullable=False, index=True)
    referencia = db.Column(db.String(120))            # alias anonimizado (NUNCA RUC/razón social)
    origen = db.Column(db.String(12), nullable=False)  # formulario | archivo
    entrada = db.Column(db.JSON, nullable=False)
    nivel_riesgo = db.Column(db.String(10), nullable=False)
    probabilidad = db.Column(db.Float, nullable=False)   # prob. de la clase predicha
    probabilidades = db.Column(db.JSON)                  # {Bajo, Medio, Alto}
    alertas = db.Column(db.JSON)
    variables_influyentes = db.Column(db.JSON)
    avisos = db.Column(db.JSON)                          # advertencias de calidad de datos
    modelo = db.Column(db.String(40))
    tarifa_hora = db.Column(db.Float)
    costo_calculado = db.Column(db.Float)                # duración(h) x tarifa
    costo_corregido = db.Column(db.Float)                # el contador puede corregirlo
    creado = db.Column(db.DateTime, default=ahora)
    usuario = db.relationship("Usuario", backref="evaluaciones")
    tiempo = db.relationship("RegistroTiempo", uselist=False, backref="evaluacion")

    @property
    def costo_final(self):
        return self.costo_corregido if self.costo_corregido is not None else self.costo_calculado


class RegistroTiempo(db.Model):
    """Indicador T. metodo='sesion' = desde que el contador abre el caso; 'servidor' = solo procesamiento."""
    __tablename__ = "registro_tiempos"
    id = db.Column(db.Integer, primary_key=True)
    evaluacion_id = db.Column(db.Integer, db.ForeignKey("evaluaciones.id"), unique=True, nullable=False)
    inicio = db.Column(db.DateTime, nullable=False)
    fin = db.Column(db.DateTime, nullable=False)
    duracion_seg = db.Column(db.Float, nullable=False)
    metodo = db.Column(db.String(10), nullable=False)

