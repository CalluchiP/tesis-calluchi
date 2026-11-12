"""Datos de demostración: usuario contador y una evaluación de ejemplo.

Uso (desde backend/):  python -m scripts.seed_demo
Es idempotente y no usa RUC, DNI ni razón social real.
"""
from datetime import timedelta

from app.models import Evaluacion, RegistroTiempo, Usuario, ahora, db
from app.services.alertas import generar as generar_alertas

DEMO_EMAIL = "demo@example.test"
PRUEBA_EMAIL = "prueba@example.test"
PASSWORD = "Demo12345"
PASSWORD_PRUEBA = "Prueba12345"

DEMO_DATA = {
    "regimen": "mype_tributario", "rubro": "comercio", "antiguedad_anios": 8,
    "ventas_comprobantes": 600000, "ventas_declaradas": 420000,
    "compras_declaradas": 468000, "compras_proveedores_riesgo": 180000,
    "gastos_no_deducibles": 30000, "meses_fuera_plazo": 7,
    "multas_previas": 3, "meses_saldo_favor": 8,
}


def sembrar(app):
    resumen = {"usuarios_creados": 0, "evaluaciones_creadas": 0}
    usuarios = [
        (DEMO_EMAIL, "Contador Demo", PASSWORD),
        (PRUEBA_EMAIL, "Usuario de Prueba", PASSWORD_PRUEBA),
    ]
    creados = {}
    for email, nombre, password in usuarios:
        usuario = Usuario.query.filter_by(email=email).first()
        if not usuario:
            usuario = Usuario(nombre=nombre, email=email, tarifa_hora=35)
            usuario.set_password(password)
            db.session.add(usuario)
            db.session.flush()
            resumen["usuarios_creados"] += 1
        creados[email] = usuario

    usuario = creados[DEMO_EMAIL]
    if not Evaluacion.query.filter_by(usuario_id=usuario.id, referencia="DEMO-001").first():
        pred = app.predictor.predecir(DEMO_DATA)
        fin = ahora() - timedelta(days=2)
        duracion = 780.0
        ev = Evaluacion(
            usuario_id=usuario.id, referencia="DEMO-001", origen="formulario", entrada=DEMO_DATA,
            nivel_riesgo=pred["nivel_riesgo"], probabilidad=pred["probabilidad"],
            probabilidades=pred["probabilidades"], alertas=generar_alertas(DEMO_DATA),
            variables_influyentes=pred["variables_influyentes"], avisos=[], modelo=pred["modelo"],
            tarifa_hora=35, costo_calculado=duracion / 3600 * 35, costo_corregido=12.5, creado=fin,
        )
        db.session.add(ev)
        db.session.flush()
        db.session.add(RegistroTiempo(evaluacion_id=ev.id, inicio=fin - timedelta(seconds=duracion),
                                      fin=fin, duracion_seg=duracion, metodo="sesion"))
        resumen["evaluaciones_creadas"] += 1

    db.session.commit()
    return resumen


if __name__ == "__main__":
    from app import create_app

    app = create_app()
    with app.app_context():
        print(sembrar(app))
    print(f"Demo: {DEMO_EMAIL} / {PASSWORD}")
    print(f"Pruebas: {PRUEBA_EMAIL} / {PASSWORD_PRUEBA}")
