from ml.features import CAMPOS, REGIMENES, RUBROS

ENTEROS = {"meses_fuera_plazo", "multas_previas", "meses_saldo_favor"}


def validar_caso(datos):
    """(entrada_limpia, errores, avisos). Rechaza faltantes, tipos y rangos; avisa incoherencias."""
    if not isinstance(datos, dict):
        return {}, {"_": "El cuerpo debe ser un objeto JSON"}, []
    limpia, errores, avisos = {}, {}, []
    for campo, regla in CAMPOS.items():
        v = datos.get(campo)
        if v is None or str(v).strip() == "":
            errores[campo] = "campo obligatorio"
            continue
        if regla == "categoria":
            v = str(v).strip().lower()
            if v not in (REGIMENES if campo == "regimen" else RUBROS):
                errores[campo] = f"valor no válido; use: {', '.join(REGIMENES if campo == 'regimen' else RUBROS)}"
            else:
                limpia[campo] = v
            continue
        try:
            f = float(str(v).replace(",", "")) if not isinstance(v, (int, float)) else float(v)
        except ValueError:
            errores[campo] = "debe ser numérico"
            continue
        lo, hi = regla
        if f < lo or f > hi:
            errores[campo] = f"debe estar entre {lo:g} y {hi:g}"
        elif campo in ENTEROS and f != int(f):
            errores[campo] = "debe ser un entero"
        else:
            limpia[campo] = int(f) if campo in ENTEROS else f
    if not errores:
        if limpia["ventas_comprobantes"] + limpia["ventas_declaradas"] <= 0:
            errores["ventas_declaradas"] = "ventas declaradas y comprobantes no pueden ser ambas 0"
        if limpia["compras_proveedores_riesgo"] > limpia["compras_declaradas"] > 0:
            avisos.append("Las compras a proveedores de riesgo superan las compras declaradas; revise los montos.")
        if limpia["ventas_declaradas"] > limpia["ventas_comprobantes"] * 1.05 > 0:
            avisos.append("Las ventas declaradas superan a los comprobantes emitidos; verifique el período.")
    return limpia, errores, avisos
