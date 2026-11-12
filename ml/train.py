"""Pipeline de entrenamiento OFFLINE (se ejecuta una sola vez):  python -m ml.train
Los MISMOS datos preprocesados alimentan los 3 modelos (Random Forest, XGBoost, SVM). Se comparan con
validación cruzada estratificada y se guardan los tres + el mejor (por F1 macro) como modelo_riesgo.joblib.
"""
import json
import shutil
import warnings
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score, precision_score, recall_score
from sklearn.model_selection import StratifiedKFold, cross_validate, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.svm import SVC
from xgboost import XGBClassifier

from ml.features import CAMPOS, CAT, NIVELES, NUM, construir_features

warnings.filterwarnings("ignore")
BASE = Path(__file__).resolve().parent.parent
SEED = 42


def preprocesador():
    return ColumnTransformer([
        ("num", Pipeline([("imp", SimpleImputer(strategy="median")), ("esc", StandardScaler())]), NUM),
        ("cat", OneHotEncoder(handle_unknown="ignore"), CAT)])


def candidatos():
    modelos = {
        "random_forest": RandomForestClassifier(n_estimators=300, class_weight="balanced", random_state=SEED, n_jobs=-1),
        "xgboost": XGBClassifier(n_estimators=300, max_depth=4, learning_rate=0.08, subsample=0.9,
                                 eval_metric="mlogloss", random_state=SEED, n_jobs=1),
        "svm": SVC(kernel="rbf", C=3, probability=True, class_weight="balanced", random_state=SEED),
    }
    return {n: Pipeline([("prep", preprocesador()), ("clf", m)]) for n, m in modelos.items()}


def main():
    df = pd.read_csv(BASE / "data" / "dataset_sintetico.csv").drop_duplicates()
    X, y = construir_features(df[list(CAMPOS)]), df["riesgo"].astype(int)
    X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=0.2, stratify=y, random_state=SEED)
    cv = StratifiedKFold(5, shuffle=True, random_state=SEED)
    scoring = {"precision": "precision_macro", "recall": "recall_macro", "f1": "f1_macro"}
    cvres, holdout, modelos = {}, {}, candidatos()
    (BASE / "models").mkdir(exist_ok=True)
    for nombre, pipe in modelos.items():
        s = cross_validate(pipe, X_tr, y_tr, cv=cv, scoring=scoring)
        cvres[nombre] = {m: round(float(np.mean(s[f"test_{m}"])), 4) for m in scoring}
        pipe.fit(X_tr, y_tr)
        p = pipe.predict(X_te)
        holdout[nombre] = {"accuracy": accuracy_score(y_te, p), "precision": precision_score(y_te, p, average="macro"),
                           "recall": recall_score(y_te, p, average="macro"), "f1": f1_score(y_te, p, average="macro"),
                           "matriz_confusion": confusion_matrix(y_te, p).tolist()}
        holdout[nombre] = {k: (round(float(v), 4) if k != "matriz_confusion" else v) for k, v in holdout[nombre].items()}
        print(nombre, cvres[nombre])
    mejor = max(cvres, key=lambda n: cvres[n]["f1"])
    med = X[NUM].median().to_dict()
    for nombre, pipe in modelos.items():
        pipe.fit(X, y)  # reentrena con todo para producción
        joblib.dump({"pipeline": pipe, "medianas": med, "modelo": nombre}, BASE / "models" / f"{nombre}.joblib")
    shutil.copy(BASE / "models" / f"{mejor}.joblib", BASE / "models" / "modelo_riesgo.joblib")
    (BASE / "models" / "metricas.json").write_text(json.dumps({
        "dataset": "Sintético generado con reglas expertas (docs/REGLAS_RIESGO.md)", "n_registros": int(len(X)),
        "clases": NIVELES, "validacion_cruzada_5fold": cvres, "holdout_20pct": holdout,
        "modelo_seleccionado": mejor, "criterio_seleccion": "mayor F1 macro en validación cruzada",
    }, indent=2, ensure_ascii=False), encoding="utf-8")
    print("MEJOR:", mejor, holdout[mejor])


if __name__ == "__main__":
    main()
