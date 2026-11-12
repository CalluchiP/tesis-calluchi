from functools import wraps

from flask import current_app, g, jsonify, request
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from app.models import Usuario, db


def _ser(salt):
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"], salt=salt)


def emitir_token(u):
    return _ser("auth").dumps({"uid": u.id})


def emitir_sesion(u, inicio_iso):
    return _ser("sesion").dumps({"uid": u.id, "inicio": inicio_iso})


def leer_sesion(token, usuario_id, max_seg=8 * 3600):
    try:
        d = _ser("sesion").loads(token, max_age=max_seg)
    except (BadSignature, SignatureExpired):
        return None
    return d["inicio"] if d.get("uid") == usuario_id else None


def requiere_sesion(rol=None):
    def deco(fn):
        @wraps(fn)
        def wrap(*a, **k):
            h = request.headers.get("Authorization", "")
            if not h.startswith("Bearer "):
                return jsonify(error="Sesión requerida"), 401
            try:
                uid = _ser("auth").loads(h[7:], max_age=current_app.config["TOKEN_MAX_AGE_SEG"])["uid"]
            except SignatureExpired:
                return jsonify(error="Sesión expirada"), 401
            except BadSignature:
                return jsonify(error="Token inválido"), 401
            u = db.session.get(Usuario, uid)
            if not u:
                return jsonify(error="Usuario no existe"), 401
            if rol and u.rol != rol:
                return jsonify(error="Sin permisos"), 403
            g.usuario = u
            return fn(*a, **k)
        return wrap
    return deco
