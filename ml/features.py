"""Contrato único de variables (API <-> entrenamiento). La MISMA función construye las variables
en el entrenamiento y en la predicción en línea => preprocesamiento idéntico.
"""
import numpy as np
import pandas as pd

REGIMENES = ["mype_tributario", "regimen_general", "regimen_especial"]
RUBROS = ["comercio", "servicios", "manufactura", "construccion"]
# Margen bruto de referencia por rubro (SUPUESTO a validar con un contador / estadísticas sectoriales)
MARGEN_REF = {"comercio": 0.22, "servicios": 0.45, "manufactura": 0.30, "construccion": 0.25}
NIVELES = ["Bajo", "Medio", "Alto"]

# Campos de entrada de un caso (12 meses). Montos en soles.
CAMPOS = {
    "regimen": "categoria", "rubro": "categoria",
    "antiguedad_anios": (0, 80),
    "ventas_comprobantes": (0, 1e10),        # según comprobantes electrónicos emitidos (Registro de Ventas)
    "ventas_declaradas": (0, 1e10),          # PDT 621
    "compras_declaradas": (0, 1e10),         # PDT 621
    "compras_proveedores_riesgo": (0, 1e10), # a proveedores no habidos / de baja / sospechosos
    "gastos_no_deducibles": (0, 1e10),
    "meses_fuera_plazo": (0, 12),
    "multas_previas": (0, 50),
    "meses_saldo_favor": (0, 12),
}
NUM = ["brecha_ventas", "ratio_compras_ventas", "desv_margen", "pct_compras_riesgo", "pct_gastos_no_ded",
       "pct_meses_tardios", "multas_previas", "pct_meses_saldo_favor", "antiguedad", "log_ventas"]
CAT = ["regimen", "rubro"]
ETIQUETAS = {
    "brecha_ventas": "Brecha ventas declaradas vs. comprobantes", "ratio_compras_ventas": "Compras / ventas",
    "desv_margen": "Desviación del margen vs. rubro", "pct_compras_riesgo": "Compras a proveedores de riesgo",
    "pct_gastos_no_ded": "Gastos no deducibles", "pct_meses_tardios": "Meses declarados fuera de plazo",
    "multas_previas": "Multas previas", "pct_meses_saldo_favor": "Meses con saldo a favor",
    "antiguedad": "Antigüedad", "log_ventas": "Tamaño (ventas)",
}


def construir_features(filas) -> pd.DataFrame:
    df = pd.DataFrame(filas).copy()
    vc, vd, cd = df["ventas_comprobantes"].astype(float), df["ventas_declaradas"].astype(float), df["compras_declaradas"].astype(float)
    base_v = np.maximum(np.maximum(vc, vd), 1.0)
    out = pd.DataFrame(index=df.index)
    out["brecha_ventas"] = ((vc - vd) / base_v).clip(-0.5, 1.0)
    out["ratio_compras_ventas"] = (cd / np.maximum(vd, 1.0)).clip(0, 3)
    margen = (1 - out["ratio_compras_ventas"]).clip(-1, 1)
    ref = df["rubro"].map(MARGEN_REF).astype(float)
    out["desv_margen"] = margen - ref
    out["pct_compras_riesgo"] = (df["compras_proveedores_riesgo"].astype(float) / np.maximum(cd, 1.0)).clip(0, 1)
    out["pct_gastos_no_ded"] = (df["gastos_no_deducibles"].astype(float) / np.maximum(vd, 1.0)).clip(0, 1)
    out["pct_meses_tardios"] = df["meses_fuera_plazo"].astype(float) / 12
    out["multas_previas"] = df["multas_previas"].astype(float).clip(0, 10)
    out["pct_meses_saldo_favor"] = df["meses_saldo_favor"].astype(float) / 12
    out["antiguedad"] = df["antiguedad_anios"].astype(float).clip(0, 40)
    out["log_ventas"] = np.log10(np.maximum(np.maximum(vc, vd), 1.0))
    out["regimen"], out["rubro"] = df["regimen"].values, df["rubro"].values
    return out[NUM + CAT]
