"""Alertas explicables basadas en reglas: qué revisar y por qué. Complementan al modelo de ML."""
from ml.features import MARGEN_REF, construir_features


def _s(x):
    return f"S/ {x:,.0f}"


def generar(entrada: dict):
    f = construir_features([entrada]).iloc[0]
    e, out = entrada, []

    def add(var, sev, msg, accion):
        out.append({"variable": var, "severidad": sev, "mensaje": msg, "accion": accion})

    b = f.brecha_ventas
    if b > 0.05:
        add("brecha_ventas", "alta" if b > 0.15 else "media",
            f"Ventas declaradas ({_s(e['ventas_declaradas'])}) menores a los comprobantes emitidos ({_s(e['ventas_comprobantes'])}): brecha de {b:.0%}.",
            "Cuadrar el Registro de Ventas con el PDT 621 mes a mes y rectificar si corresponde.")
    p = f.pct_compras_riesgo
    if p > 0.05:
        add("pct_compras_riesgo", "alta" if p > 0.15 else "media",
            f"{p:.0%} de las compras ({_s(e['compras_proveedores_riesgo'])}) son a proveedores no habidos, de baja o sospechosos.",
            "Validar el RUC y la existencia real de la operación: riesgo de perder el crédito fiscal del IGV.")
    d = f.desv_margen
    if d < -0.10:
        add("desv_margen", "alta" if d < -0.20 else "media",
            f"Margen bruto de {1 - f.ratio_compras_ventas:.0%} frente a ~{MARGEN_REF[e['rubro']]:.0%} referencial del rubro {e['rubro']}.",
            "Revisar compras sobrevaloradas o ventas no registradas.")
    g = f.pct_gastos_no_ded
    if g > 0.03:
        add("pct_gastos_no_ded", "alta" if g > 0.06 else "media",
            f"Gastos no deducibles de {_s(e['gastos_no_deducibles'])} ({g:.1%} de las ventas).",
            "Depurar gastos sin comprobante válido o ajenos al giro antes de la declaración anual (reparos de renta).")
    t = e["meses_fuera_plazo"]
    if t >= 3:
        add("pct_meses_tardios", "alta" if t >= 6 else "media", f"{t} de 12 meses declarados fuera de plazo.",
            "Regularizar calendario de vencimientos; evaluar multas por presentación tardía (Art. 176 C.T.).")
    m = e["multas_previas"]
    if m >= 1:
        add("multas_previas", "alta" if m >= 3 else "media", f"{m} multa(s) previa(s) registrada(s).",
            "Revisar si hay deudas o fraccionamientos vigentes y la causa de las multas.")
    if e["meses_saldo_favor"] >= 6:
        add("pct_meses_saldo_favor", "media", f"{e['meses_saldo_favor']} meses con saldo a favor del IGV.",
            "Sustentar el crédito fiscal acumulado: es un foco habitual de fiscalización.")
    if e["antiguedad_anios"] < 1:
        add("antiguedad", "baja", "Empresa con menos de 1 año de operaciones.", "Mayor probabilidad de errores por falta de historial.")
    orden = {"alta": 0, "media": 1, "baja": 2}
    return sorted(out, key=lambda a: orden[a["severidad"]])
