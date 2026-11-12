from app import create_app


def _client(tmp_path):
    app = create_app({"TESTING": True,
                      "SQLALCHEMY_DATABASE_URI": f"sqlite:///{tmp_path/'web.db'}"})
    return app.test_client()


def test_interfaz_web_disponible(tmp_path):
    cl = _client(tmp_path)
    r = cl.get("/")
    assert r.status_code == 200
    assert "text/html" in r.headers["Content-Type"]
    html = r.get_data(as_text=True)
    assert "Mesa de evaluación" in html
    assert "Subir archivos" in html and "Formulario guiado" in html
    assert "app.js" in html and "app.css" in html
    assert "RUC, DNI" in html
    assert "regGroup" not in html
    assert "Fichas GC" not in html and "Grupo experimental" not in html
    assert "Indicadores" not in html and "Tarifa por hora" not in html
    assert "btnCasoEjemplo" in html


def test_archivos_de_ejemplo_disponibles(tmp_path):
    cl = _client(tmp_path)
    esperados = {
        "ventas.csv": "periodo,tipo_comprobante,base_imponible",
        "pdt621.csv": "periodo,ventas_declaradas,compras_declaradas",
        "compras.csv": "periodo,proveedor_ref,base_imponible",
    }
    for nombre, cabecera in esperados.items():
        r = cl.get(f"/static/ejemplos/{nombre}")
        assert r.status_code == 200
        assert r.get_data(as_text=True).startswith(cabecera)


def test_recursos_estaticos(tmp_path):
    cl = _client(tmp_path)
    css = cl.get("/static/app.css")
    js = cl.get("/static/app.js")
    assert css.status_code == 200 and "text/css" in css.headers["Content-Type"]
    assert js.status_code == 200 and "javascript" in js.headers["Content-Type"]
    assert b"/evaluaciones/iniciar" in js.data


def test_api_no_se_ve_afectada(tmp_path):
    cl = _client(tmp_path)
    assert cl.get("/api/health").status_code == 200
    r = cl.get("/api/no-existe")
    assert r.status_code == 404 and r.is_json
