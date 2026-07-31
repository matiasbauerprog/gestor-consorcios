def test_health_devuelve_200_sin_token(client):
    # Publico a proposito: un monitor externo lo pingea cada 10 min y no
    # deberia necesitar credenciales para eso.
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_health_responde_head(client):
    """Los planes gratuitos de varios monitores de uptime solo mandan HEAD.

    FastAPI, a diferencia de Starlette pelado, no agrega HEAD automaticamente a
    las rutas GET: declarado con @app.get esto daria 405 y el monitor lo
    reportaria como caida.
    """
    r = client.head("/health")
    assert r.status_code == 200


def test_health_no_toca_la_base(client, monkeypatch):
    """No debe abrir sesion de DB.

    Es lo que lo hace barato de pingear con frecuencia, y lo que hace que siga
    respondiendo 200 aunque la base este caida — un monitor que mide "el
    proceso esta vivo" no debe fallar por un problema de la base.
    """
    from backend import database

    def _explotar():
        raise AssertionError("/health no debe abrir una sesion de base")

    monkeypatch.setattr(database, "SessionLocal", _explotar)
    r = client.get("/health")
    assert r.status_code == 200
