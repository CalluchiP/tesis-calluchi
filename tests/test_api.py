import io

import pytest

from app import create_app

BAJO = {"regimen": "mype_tributario", "rubro": "comercio", "antiguedad_anios": 8, "ventas_comprobantes": 600000,
        "ventas_declaradas": 600000, "compras_declaradas": 468000, "compras_proveedores_riesgo": 0,
        "gastos_no_deducibles": 1000, "meses_fuera_plazo": 0, "multas_previas": 0, "meses_saldo_favor": 0}
ALTO = {**BAJO, "ventas_declaradas": 420000, "compras_proveedores_riesgo": 180000, "gastos_no_deducibles": 30000,
        "meses_fuera_plazo": 7, "multas_previas": 3, "meses_saldo_favor": 8}


@pytest.fixture()
def c(tmp_path):
    app = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": f"sqlite:///{tmp_path/'t.db'}"})
    cl = app.test_client()
    cl.post("/api/auth/registro", json={"nombre": "Ana", "email": "ana@x.pe", "password": "clave12345"})
    t = cl.post("/api/auth/login", json={"email": "ana@x.pe", "password": "clave12345"}).json["token"]
    cl.h = {"Authorization": f"Bearer {t}"}
    return cl


def test_sin_sesion(c):
    assert c.post("/api/evaluaciones", json={"datos": BAJO}).status_code == 401


def test_validacion(c):
    r = c.post("/api/evaluaciones", json={"datos": {**BAJO, "rubro": "minería", "meses_fuera_plazo": 15}}, headers=c.h)
    assert r.status_code == 422 and {"rubro", "meses_fuera_plazo"} <= set(r.json["detalle"])


def test_riesgo_coherente(c):
    bajo = c.post("/api/evaluaciones", json={"datos": BAJO}, headers=c.h).json
    alto = c.post("/api/evaluaciones", json={"datos": ALTO}, headers=c.h).json
    assert bajo["nivel_riesgo"] == "Bajo" and alto["nivel_riesgo"] == "Alto"
    assert len(alto["alertas"]) >= 4 and alto["alertas"][0]["severidad"] == "alta"
    assert abs(sum(alto["probabilidades"].values()) - 1) < 0.01


def test_tiempo_sesion_y_costo(c):
    s = c.post("/api/evaluaciones/iniciar", headers=c.h).json["sesion"]
    j = c.post("/api/evaluaciones", json={"datos": BAJO, "sesion": s}, headers=c.h).json
    assert j["tiempo"]["metodo"] == "sesion" and j["costo"]["calculado"] >= 0
    r = c.patch(f"/api/evaluaciones/{j['id']}/costo", json={"costo": 12.5}, headers=c.h).json
    assert r["costo"]["final"] == 12.5 and r["costo"]["corregido"] == 12.5
    assert c.patch(f"/api/evaluaciones/{j['id']}/costo", json={"costo": -1}, headers=c.h).status_code == 422
    assert c.patch(f"/api/evaluaciones/{j['id']}/costo", json={"costo": None}, headers=c.h).json["costo"]["corregido"] is None


def test_archivo(c):
    ventas = "periodo,base_imponible,estado\n" + "".join(f"2025-{m:02d},50000,emitido\n" for m in range(1, 13))
    pdt = "periodo,ventas_declaradas,compras_declaradas\n" + "".join(f"2025-{m:02d},35000,39000\n" for m in range(1, 13))
    compras = "periodo,base_imponible,estado_proveedor,deducible\n" + "".join(f"2025-{m:02d},20000,no habido,no\n" for m in range(1, 7)) + "".join(f"2025-{m:02d},19000,habido,si\n" for m in range(7, 13))
    data = {"referencia": "CASO-A", "regimen": "mype_tributario", "rubro": "comercio", "antiguedad_anios": "3",
            "meses_fuera_plazo": "4", "multas_previas": "1", "meses_saldo_favor": "2",
            "ventas": (io.BytesIO(ventas.encode()), "v.csv"), "pdt621": (io.BytesIO(pdt.encode()), "p.csv"),
            "compras": (io.BytesIO(compras.encode()), "c.csv")}
    r = c.post("/api/evaluaciones/archivo", data=data, headers=c.h, content_type="multipart/form-data")
    assert r.status_code == 201, r.json
    j = r.json
    assert j["origen"] == "archivo" and j["entrada"]["ventas_comprobantes"] == 600000
    assert j["entrada"]["compras_proveedores_riesgo"] == 120000 and j["nivel_riesgo"] in ("Medio", "Alto")


def test_archivo_columnas_faltantes(c):
    data = {"ventas": (io.BytesIO(b"a,b\n1,2\n"), "v.csv"), "pdt621": (io.BytesIO(b"a,b\n1,2\n"), "p.csv"),
            "regimen": "mype_tributario", "rubro": "comercio"}
    r = c.post("/api/evaluaciones/archivo", data=data, headers=c.h, content_type="multipart/form-data")
    assert r.status_code == 422 and "base_imponible" in r.json["error"]


def test_archivos_de_ejemplo_producen_evaluacion(c):
    from pathlib import Path

    base = Path(__file__).resolve().parent.parent / "app" / "static" / "ejemplos"
    data = {
        "referencia": "Caso-Ejemplo-001", "regimen": "mype_tributario", "rubro": "comercio",
        "antiguedad_anios": "8", "meses_fuera_plazo": "7", "multas_previas": "3",
        "meses_saldo_favor": "8",
        "ventas": (io.BytesIO((base / "ventas.csv").read_bytes()), "ventas.csv"),
        "pdt621": (io.BytesIO((base / "pdt621.csv").read_bytes()), "pdt621.csv"),
        "compras": (io.BytesIO((base / "compras.csv").read_bytes()), "compras.csv"),
    }
    r = c.post("/api/evaluaciones/archivo", data=data, headers=c.h, content_type="multipart/form-data")
    assert r.status_code == 201, r.json
    e = r.json
    assert e["origen"] == "archivo"
    assert e["entrada"]["ventas_comprobantes"] == 600000
    assert e["entrada"]["ventas_declaradas"] == 420000
    assert e["entrada"]["compras_proveedores_riesgo"] == 120000
    assert e["nivel_riesgo"] in ("Medio", "Alto")


def test_indicadores_y_exportacion(c):
    c.post("/api/evaluaciones", json={"datos": BAJO}, headers=c.h)
    ind = c.get("/api/indicadores", headers=c.h).json
    assert ind["casos"] == 1
    assert {"T_tiempo_promedio_seg", "C_costo_promedio_soles", "P_casos_por_semana",
            "P_casos_por_dia_activo"} <= set(ind)
    csv_ = c.get("/api/indicadores/exportar.csv", headers=c.h).data.decode()
    assert csv_.startswith("fuente,fecha") and csv_.count("\n") == 2
    assert "grupo" not in csv_


def test_registro_sin_grupo(c):
    r = c.post("/api/auth/registro", json={"nombre": "Sin grupo", "email": "sin.grupo@x.pe",
                                           "password": "clave12345", "grupo": "GC"})
    assert r.status_code == 201 and "grupo" not in r.json
    login = c.post("/api/auth/login", json={"email": "sin.grupo@x.pe", "password": "clave12345"})
    assert login.status_code == 200 and "grupo" not in login.json["usuario"]


def test_plantillas_y_aislamiento(c):
    assert c.get("/api/plantillas/ventas.csv").status_code == 200
    j = c.post("/api/evaluaciones", json={"datos": BAJO}, headers=c.h).json
    c.post("/api/auth/registro", json={"nombre": "B", "email": "b@x.pe", "password": "clave12345"})
    t = c.post("/api/auth/login", json={"email": "b@x.pe", "password": "clave12345"}).json["token"]
    assert c.get(f"/api/evaluaciones/{j['id']}", headers={"Authorization": f"Bearer {t}"}).status_code == 404
    assert b"Evaluaci" in c.get(f"/api/evaluaciones/{j['id']}/reporte", headers=c.h).data
