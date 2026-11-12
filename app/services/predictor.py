"""Módulo de ML (predicción en línea): carga el Pipeline guardado (preprocesamiento idéntico al entrenamiento)."""
import joblib
import pandas as pd

from ml.features import CAMPOS, ETIQUETAS, NIVELES, NUM, construir_features


class Predictor:
    def __init__(self, models_dir, activo="auto"):
        archivo = "modelo_riesgo.joblib" if activo == "auto" else f"{activo}.joblib"
        art = joblib.load(models_dir / archivo)
        self.pipe, self.medianas, self.nombre = art["pipeline"], art["medianas"], art["modelo"]

    @staticmethod
    def _indice(proba):  # índice de riesgo 0-1 para medir influencia
        return proba[:, 1] * 0.5 + proba[:, 2]

    def predecir(self, entrada: dict) -> dict:
        X = construir_features([{c: entrada[c] for c in CAMPOS}])
        pr = self.pipe.predict_proba(X)
        k = int(pr[0].argmax())
        base = float(self._indice(pr)[0])
        impactos = []
        for col in NUM:  # influencia agnóstica al modelo: reemplazar la variable por la mediana de entrenamiento
            alt = X.copy()
            alt[col] = self.medianas[col]
            impactos.append((col, base - float(self._indice(self.pipe.predict_proba(alt))[0])))
        impactos.sort(key=lambda t: abs(t[1]), reverse=True)
        top = [{"variable": c, "etiqueta": ETIQUETAS[c], "impacto": round(i, 3),
                "efecto": "aumenta el riesgo" if i > 0 else "reduce el riesgo"} for c, i in impactos[:3] if abs(i) > 0.02]
        return {"nivel_riesgo": NIVELES[k], "probabilidad": round(float(pr[0][k]), 4),
                "probabilidades": {n: round(float(pr[0][i]), 4) for i, n in enumerate(NIVELES)},
                "variables_influyentes": top, "modelo": self.nombre}
