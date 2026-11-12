import csv
import io
import json
from datetime import datetime, timezone

from flask import Blueprint, Response, current_app, g, jsonify, request
from sqlalchemy import func

from app.models import Evaluacion, RegistroTiempo, Usuario, ahora, db
from app.services import archivos
from app.services.alertas import generar as generar_alertas
from app.services.auth import emitir_sesion, emitir_token, leer_sesion, requiere_sesion
from app.services.reportes import evaluacion_a_dict, reporte_html
from app.services.validacion import validar_caso
from ml.features import MARGEN_REF, REGIMENES, RUBROS

bp = Blueprint("api", __name__, url_prefix="/api")


@bp.get("/health")
def health():
    return jsonify(estado="ok", modelo=current_app.predictor.nombre)


@bp.get("/opciones")
def opciones():
    return jsonify(regimenes=REGIMENES, rubros=RUBROS, margen_referencia=MARGEN_REF)


@bp.get("/plantillas/<nombre>.csv")
def plantilla(nombre):
    if nombre not in archivos.PLANTILLAS:
        return jsonify(error="Plantilla no existe"), 404
    return Response(archivos.PLANTILLAS[nombre], mimetype="text/csv",
                    headers={"Content-Disposition": f"attachment; filename=plantilla_{nombre}.csv"})


# ---- Autenticación ----------------------------------------------------------------------------
@bp.post("/auth/registro")
def registro():
    d = request.get_json(silent=True) or {}
    nombre, email, pwd = (d.get("nombre") or "").strip(), (d.get("email") or "").strip().lower(), d.get("password") or ""
    if not nombre or "@" not in email or len(pwd) < 8:
        return jsonify(error="nombre, email válido y password (mín. 8) son obligatorios"), 422
    if Usuario.query.filter_by(email=email).first():
        return jsonify(error="El email ya está registrado"), 409
    u = Usuario(nombre=nombre, email=email)
    if isinstance(d.get("tarifa_hora"), (int, float)) and d["tarifa_hora"] > 0:
        u.tarifa_hora = float(d["tarifa_hora"])
    u.set_password(pwd)
    db.session.add(u)
    db.session.commit()
    return jsonify(id=u.id, email=u.email), 201


@bp.post("/auth/login")
def login():
    d = request.get_json(silent=True) or {}
    u = Usuario.query.filter_by(email=(d.get("email") or "").strip().lower()).first()
    if not u or not u.check_password(d.get("password") or ""):
        return jsonify(error="Credenciales inválidas"), 401
    return jsonify(token=emitir_token(u), usuario=_perfil(u))


def _tarifa(u):
    return u.tarifa_hora or current_app.config["TARIFA_HORA_SOLES"]


def _perfil(u):
    return {"id": u.id, "nombre": u.nombre, "rol": u.rol, "tarifa_hora": _tarifa(u)}


@bp.get("/usuarios/yo")
@requiere_sesion()
def yo():
    return jsonify(_perfil(g.usuario))


@bp.patch("/usuarios/yo")
@requiere_sesion()
def actualizar_yo():
    t = (request.get_json(silent=True) or {}).get("tarifa_hora")
    if not isinstance(t, (int, float)) or t <= 0 or t > 10000:
        return jsonify(error="tarifa_hora debe ser un número positivo (S/ por hora)"), 422
    g.usuario.tarifa_hora = float(t)
    db.session.commit()
    return jsonify(_perfil(g.usuario))


# ---- Evaluación ---------------------------------------------------------------------------------
@bp.post("/evaluaciones/iniciar")
@requiere_sesion()
def iniciar():
    """El frontend llama aquí cuando el contador abre un caso nuevo: arranca el cronómetro del indicador T."""
    inicio = ahora().isoformat()
    return jsonify(sesion=emitir_sesion(g.usuario, inicio), inicio=inicio), 201


def _guardar(entrada, avisos, origen, referencia, sesion, t0):
    fin = ahora()
    inicio_s = leer_sesion(sesion, g.usuario.id) if sesion else None
    inicio, metodo = (datetime.fromisoformat(inicio_s), "sesion") if inicio_s else (t0, "servidor")
    dur = max((fin - inicio).total_seconds(), 0.0)
    r = current_app.predictor.predecir(entrada)
    tarifa = _tarifa(g.usuario)
    ev = Evaluacion(usuario_id=g.usuario.id, referencia=(referencia or "")[:120] or None, origen=origen, entrada=entrada,
                    nivel_riesgo=r["nivel_riesgo"], probabilidad=r["probabilidad"], probabilidades=r["probabilidades"],
                    alertas=generar_alertas(entrada), variables_influyentes=r["variables_influyentes"], avisos=avisos,
                    modelo=r["modelo"], tarifa_hora=tarifa, costo_calculado=dur / 3600 * tarifa)
    db.session.add(ev)
    db.session.flush()
    db.session.add(RegistroTiempo(evaluacion_id=ev.id, inicio=inicio, fin=fin, duracion_seg=dur, metodo=metodo))
    db.session.commit()
    return ev


@bp.post("/evaluaciones")
@requiere_sesion()
def crear_formulario():
    t0 = ahora()
    d = request.get_json(silent=True) or {}
    entrada, errores, avisos = validar_caso(d.get("datos"))
    if errores:
        return jsonify(error="Datos inválidos", detalle=errores), 422
    return jsonify(evaluacion_a_dict(_guardar(entrada, avisos, "formulario", d.get("referencia"), d.get("sesion"), t0))), 201


@bp.post("/evaluaciones/archivo")
@requiere_sesion()
def crear_archivo():
    """multipart/form-data: archivos 'ventas' y 'pdt621' (obligatorios), 'compras' (opcional) + campos del caso."""
    t0 = ahora()
    f = request.form
    for req in ("ventas", "pdt621"):
        if req not in request.files:
            return jsonify(error=f"Falta el archivo '{req}'", plantillas=[f"/api/plantillas/{n}.csv" for n in archivos.PLANTILLAS]), 422
    try:
        ventas, pdt = archivos.leer(request.files["ventas"], "ventas"), archivos.leer(request.files["pdt621"], "pdt621")
        compras = archivos.leer(request.files["compras"], "compras") if "compras" in request.files else None
        agg, avisos_a = archivos.agregar(ventas, pdt, compras)
    except archivos.ArchivoError as e:
        return jsonify(error=str(e)), 422
    datos = {k: f.get(k) for k in ("regimen", "rubro", "antiguedad_anios", "meses_fuera_plazo", "multas_previas", "meses_saldo_favor")}
    for k in ("gastos_no_deducibles", "compras_proveedores_riesgo"):  # el formulario complementa lo que no vino en archivos
        datos[k] = agg[k] if agg[k] > 0 or not f.get(k) else f.get(k)
    datos.update({k: agg[k] for k in ("ventas_comprobantes", "ventas_declaradas", "compras_declaradas")})
    entrada, errores, avisos = validar_caso(datos)
    if errores:
        return jsonify(error="Datos inválidos", detalle=errores), 422
    return jsonify(evaluacion_a_dict(_guardar(entrada, avisos_a + avisos, "archivo", f.get("referencia"), f.get("sesion"), t0))), 201


def _propia(id_):
    ev = db.session.get(Evaluacion, id_)
    return ev if ev and (ev.usuario_id == g.usuario.id or g.usuario.rol == "admin") else None


@bp.get("/evaluaciones")
@requiere_sesion()
def listar():
    q = Evaluacion.query.order_by(Evaluacion.creado.desc())
    if g.usuario.rol != "admin":
        q = q.filter_by(usuario_id=g.usuario.id)
    p = q.paginate(page=request.args.get("page", 1, type=int), per_page=min(request.args.get("per_page", 20, type=int), 100), error_out=False)
    return jsonify(total=p.total, pagina=p.page, items=[evaluacion_a_dict(e) for e in p.items])


@bp.get("/evaluaciones/<int:id_>")
@requiere_sesion()
def detalle(id_):
    ev = _propia(id_)
    return (jsonify(evaluacion_a_dict(ev)), 200) if ev else (jsonify(error="No encontrada"), 404)


@bp.get("/evaluaciones/<int:id_>/reporte")
@requiere_sesion()
def reporte(id_):
    ev = _propia(id_)
    return Response(reporte_html(ev), mimetype="text/html") if ev else (jsonify(error="No encontrada"), 404)


@bp.patch("/evaluaciones/<int:id_>/costo")
@requiere_sesion()
def corregir_costo(id_):
    ev = _propia(id_)
    if not ev:
        return jsonify(error="No encontrada"), 404
    c = (request.get_json(silent=True) or {}).get("costo")
    if c is None:  # quitar la corrección y volver al costo calculado
        ev.costo_corregido = None
    elif not isinstance(c, (int, float)) or c < 0:
        return jsonify(error="costo debe ser un número ≥ 0 (S/)"), 422
    else:
        ev.costo_corregido = float(c)
    db.session.commit()
    return jsonify(evaluacion_a_dict(ev))


# ---- Indicadores de la tesis: P, T, C --------------------------------------------------------------
def _filas():
    """[(fecha, duracion_seg, costo, fuente)] de evaluaciones con el asistente."""
    out = []
    q = (db.session.query(Evaluacion.id, Evaluacion.creado, RegistroTiempo.duracion_seg, Evaluacion)
         .join(RegistroTiempo, RegistroTiempo.evaluacion_id == Evaluacion.id))
    for id_, creado, dur, ev in q:
        out.append((creado, dur, ev.costo_final, f"evaluacion:{id_}"))
    return out


@bp.get("/indicadores")
@requiere_sesion()
def indicadores():
    filas = _filas()
    if not filas:
        return jsonify({"casos": 0, "T_tiempo_promedio_seg": 0, "C_costo_promedio_soles": 0,
                        "P_casos_por_semana": 0, "P_casos_por_dia_activo": 0})
    fechas = [f for f, _, _, _ in filas]
    dias_activos = len({f.date() for f in fechas})
    semanas = max(((max(fechas) - min(fechas)).days + 1) / 7, 1)
    n = len(filas)
    return jsonify({"casos": n,
                    "T_tiempo_promedio_seg": round(sum(d for _, d, _, _ in filas) / n, 3),
                    "C_costo_promedio_soles": round(sum(c for _, _, c, _ in filas) / n, 2),
                    "P_casos_por_semana": round(n / semanas, 2),
                    "P_casos_por_dia_activo": round(n / dias_activos, 2)})


@bp.get("/indicadores/exportar.csv")
@requiere_sesion()
def exportar():
    """Una fila por caso, lista para el análisis estadístico (cap. 5.8)."""
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["fuente", "fecha", "tiempo_seg", "costo_soles"])
    for fecha, dur, costo, fuente in sorted(_filas(), key=lambda x: x[0]):
        w.writerow([fuente, fecha.isoformat(), round(dur, 3), round(costo, 2)])
    return Response(buf.getvalue(), mimetype="text/csv", headers={"Content-Disposition": "attachment; filename=indicadores.csv"})


@bp.get("/modelo")
def modelo():
    return jsonify(json.loads((current_app.config["MODELS_DIR"] / "metricas.json").read_text(encoding="utf-8")))
