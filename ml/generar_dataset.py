"""Genera el dataset SINTÉTICO de entrenamiento a partir de reglas de riesgo (docs/REGLAS_RIESGO.md).
Uso: python -m ml.generar_dataset [n]   -> data/dataset_sintetico.csv
Sustituir por casos reales anonimizados cuando existan (mismas columnas de ml/features.CAMPOS + 'riesgo').
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from ml.features import MARGEN_REF, RUBROS, construir_features

BASE = Path(__file__).resolve().parent.parent


def puntaje(f: pd.DataFrame, rng) -> np.ndarray:
    """Reglas expertas (0-100). Se documentan en docs/REGLAS_RIESGO.md para validarlas con un contador."""
    s = np.clip(f.brecha_ventas.clip(lower=0) / 0.25, 0, 1) * 30
    s += np.clip(f.pct_compras_riesgo / 0.30, 0, 1) * 20
    s += np.clip((-f.desv_margen).clip(lower=0) / 0.25, 0, 1) * 10
    s += np.clip(f.pct_gastos_no_ded / 0.08, 0, 1) * 10
    s += f.pct_meses_tardios * 10
    s += np.clip(f.multas_previas / 3, 0, 1) * 10
    s += np.clip(f.pct_meses_saldo_favor / 0.5, 0, 1) * 5
    s += (f.antiguedad < 1) * 3
    s += ((f.brecha_ventas > 0.10) & (f.pct_compras_riesgo > 0.10)) * 5
    return s + rng.normal(0, 4, len(f))  # criterio subjetivo del evaluador


def generar(n=4000, seed=42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    u = np.where(rng.random(n) < 0.30, rng.beta(4, 2.5, n), rng.beta(1.2, 6, n))  # propensión a incumplir (latente)
    ventas = np.clip(np.exp(rng.normal(np.log(700_000), 1.4, n)), 40_000, 60_000_000)
    rubro = rng.choice(RUBROS, n, p=[.40, .30, .15, .15])
    regimen = np.where(ventas <= 9_000_000, rng.choice(["mype_tributario", "regimen_general", "regimen_especial"], n, p=[.6, .3, .1]), "regimen_general")
    sub = np.clip(rng.normal(0.38 * u ** 1.2, 0.03), -0.03, 0.6)
    vd = ventas * (1 - sub)
    margen = np.array([MARGEN_REF[r] for r in rubro]) + rng.normal(0, 0.05, n) - 0.22 * u * rng.random(n)
    compras = np.clip(vd * (1 - margen), 0, None)
    riesgo_c = np.where(rng.random(n) < 0.10 + 0.65 * u, compras * rng.uniform(0.02, 0.55, n) * (0.5 + u), 0)
    df = pd.DataFrame({
        "regimen": regimen, "rubro": rubro,
        "antiguedad_anios": np.round(np.clip(rng.exponential(6, n) - 3 * u, 0.1, 40), 1),
        "ventas_comprobantes": ventas.round(2), "ventas_declaradas": vd.round(2), "compras_declaradas": compras.round(2),
        "compras_proveedores_riesgo": np.minimum(riesgo_c, compras).round(2),
        "gastos_no_deducibles": (vd * (0.004 + 0.09 * u * rng.random(n))).round(2),
        "meses_fuera_plazo": rng.binomial(12, np.clip(0.04 + 0.5 * u, 0, 1)),
        "multas_previas": rng.poisson(0.15 + 3.2 * u ** 1.3),
        "meses_saldo_favor": rng.binomial(12, np.where(u > 0.5, 0.35, 0.06)),
    })
    p = puntaje(construir_features(df), rng)
    df["riesgo"] = np.select([p < 25, p < 50], [0, 1], 2)  # 0 Bajo, 1 Medio, 2 Alto
    return df


if __name__ == "__main__":
    d = generar(int(sys.argv[1]) if len(sys.argv) > 1 else 4000)
    (BASE / "data").mkdir(exist_ok=True)
    d.to_csv(BASE / "data" / "dataset_sintetico.csv", index=False)
    print(d.riesgo.value_counts(normalize=True).sort_index().round(3).to_dict(), len(d))
