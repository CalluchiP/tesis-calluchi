from html import escape

from ml.features import ETIQUETAS

COLOR = {"Bajo": "#1a7f37", "Medio": "#b7791f", "Alto": "#c53030"}
SEV = {"alta": "#c53030", "media": "#b7791f", "baja": "#4a5568"}


def evaluacion_a_dict(e):
    t = e.tiempo
    return {"id": e.id, "referencia": e.referencia, "origen": e.origen, "entrada": e.entrada,
            "nivel_riesgo": e.nivel_riesgo, "probabilidad": e.probabilidad, "probabilidades": e.probabilidades,
            "alertas": e.alertas, "variables_influyentes": e.variables_influyentes, "avisos": e.avisos,
            "modelo": e.modelo, "creado": e.creado.isoformat(),
            "tiempo": {"inicio": t.inicio.isoformat(), "fin": t.fin.isoformat(),
                       "duracion_seg": round(t.duracion_seg, 3), "metodo": t.metodo} if t else None,
            "costo": {"tarifa_hora": e.tarifa_hora, "calculado": round(e.costo_calculado or 0, 2),
                      "corregido": e.costo_corregido, "final": round(e.costo_final or 0, 2)}}


def reporte_html(e):
    al = "".join(f"<li><b style='color:{SEV[a['severidad']]}'>[{a['severidad'].upper()}]</b> {escape(a['mensaje'])}<br>"
                 f"<i>Qué revisar:</i> {escape(a['accion'])}</li>" for a in (e.alertas or [])) or "<li>Sin alertas.</li>"
    d = e.entrada
    filas = "".join(f"<tr><td>{escape(k)}</td><td>{escape(str(v))}</td></tr>" for k, v in d.items())
    return f"""<!doctype html><html lang="es"><meta charset="utf-8"><title>Reporte #{e.id}</title>
<body style="font-family:Arial;max-width:760px;margin:2rem auto;line-height:1.45">
<h1>Evaluación de riesgo tributario #{e.id}</h1>
<p>Caso: <b>{escape(e.referencia or '-')}</b> · {e.creado:%d/%m/%Y %H:%M} UTC · Origen: {e.origen} · Modelo: {e.modelo}</p>
<h2 style="color:{COLOR[e.nivel_riesgo]}">Riesgo {e.nivel_riesgo} ({e.probabilidad:.0%})</h2>
<h3>Alertas y qué revisar</h3><ul>{al}</ul>
<h3>Datos del caso</h3><table border="1" cellpadding="5" style="border-collapse:collapse">{filas}</table>
<p>Tiempo: {e.tiempo.duracion_seg:.1f} s · Costo: S/ {e.costo_final:.2f}</p>
<p style="color:#666;font-size:.85rem">Apoyo a la decisión del contador; no sustituye su criterio profesional.</p>
</body></html>"""
