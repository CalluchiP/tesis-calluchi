"""Lectura de archivos subidos (CSV o Excel) y agregación a las variables del caso."""
import io
import re
import unicodedata

import pandas as pd

MAX_FILAS = 100_000
RIESGO_PROV = ("no habido", "no hallado", "baja", "suspension", "suspendido", "sospechoso", "no_habido")


class ArchivoError(ValueError):
    pass


def _norm(c):
    c = unicodedata.normalize("NFKD", str(c)).encode("ascii", "ignore").decode().lower().strip()
    return re.sub(r"[^a-z0-9]+", "_", c).strip("_")


def _num(s):
    return pd.to_numeric(s.astype(str).str.replace(r"[S/\s,]", "", regex=True), errors="coerce")


def leer(fs, nombre):
    """fs: FileStorage de Flask. Devuelve DataFrame con columnas normalizadas."""
    raw = fs.read()
    n = (fs.filename or "").lower()
    try:
        if n.endswith((".xlsx", ".xls")):
            df = pd.read_excel(io.BytesIO(raw))
        else:
            df = pd.read_csv(io.BytesIO(raw), sep=None, engine="python", encoding_errors="replace")
    except Exception as e:  # noqa: BLE001
        raise ArchivoError(f"{nombre}: no se pudo leer el archivo ({type(e).__name__}). Use CSV o Excel.")
    if len(df) > MAX_FILAS:
        raise ArchivoError(f"{nombre}: demasiadas filas (máx. {MAX_FILAS}).")
    df.columns = [_norm(c) for c in df.columns]
    return df


def _req(df, cols, nombre):
    faltan = [c for c in cols if c not in df.columns]
    if faltan:
        raise ArchivoError(f"{nombre}: faltan columnas {faltan}. Descargue la plantilla en /api/plantillas/{nombre}.csv")


def agregar(ventas, pdt621, compras=None):
    """Devuelve (campos_agregados, avisos)."""
    avisos = []
    _req(ventas, ["base_imponible"], "ventas")
    _req(pdt621, ["ventas_declaradas", "compras_declaradas"], "pdt621")
    if "estado" in ventas.columns:
        ventas = ventas[~ventas["estado"].astype(str).str.lower().str.contains("anul", na=False)]
    vc = _num(ventas["base_imponible"]).sum()
    vd = _num(pdt621["ventas_declaradas"]).sum()
    cd = _num(pdt621["compras_declaradas"]).sum()
    out = {"ventas_comprobantes": float(vc), "ventas_declaradas": float(vd), "compras_declaradas": float(cd),
           "compras_proveedores_riesgo": 0.0, "gastos_no_deducibles": 0.0}
    for nombre, df in (("ventas", ventas), ("pdt621", pdt621)):
        if "periodo" in df.columns:
            k = df["periodo"].astype(str).nunique()
            if k != 12:
                avisos.append(f"El archivo de {nombre} tiene {k} períodos distintos (se esperan 12).")
    if compras is not None:
        _req(compras, ["base_imponible"], "compras")
        base = _num(compras["base_imponible"]).fillna(0)
        if "estado_proveedor" in compras.columns:
            est = compras["estado_proveedor"].astype(str).str.lower()
            out["compras_proveedores_riesgo"] = float(base[est.str.contains("|".join(RIESGO_PROV), na=False)].sum())
        else:
            avisos.append("El archivo de compras no trae 'estado_proveedor': no se pudo medir compras a proveedores de riesgo.")
        if "deducible" in compras.columns:
            ded = compras["deducible"].astype(str).str.lower().str.strip()
            out["gastos_no_deducibles"] = float(base[ded.isin(["no", "n", "0", "false", "falso"])].sum())
    else:
        avisos.append("No se subió archivo de compras: proveedores de riesgo y gastos no deducibles se tomaron como 0 (puede indicarlos en el formulario).")
    if out["ventas_comprobantes"] <= 0:
        raise ArchivoError("ventas: la suma de base_imponible es 0 o no numérica.")
    return out, avisos


PLANTILLAS = {
    "ventas": "periodo,tipo_comprobante,base_imponible,igv,estado\n2025-01,factura,12500.00,2250.00,emitido\n2025-01,boleta,830.50,149.49,emitido\n",
    "compras": "periodo,proveedor_ref,base_imponible,estado_proveedor,deducible\n2025-01,PROV-001,8000.00,habido,si\n2025-01,PROV-002,1500.00,no habido,no\n",
    "pdt621": "periodo,ventas_declaradas,compras_declaradas\n2025-01,13330.50,9500.00\n2025-02,11200.00,8100.00\n",
}
