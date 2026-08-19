"""Contrato de fechas que salen al navegador.

No es de un router: es una regla del contrato entera. Todo instante que la
base escribe con su reloj está en UTC, pero SQLite no guarda la zona y vuelve
sin marca; serializado así, el navegador lo lee como hora local y se corre por
el offset del huso. Estos tests fijan de qué lado cae cada campo.
"""


def test_created_at_sale_marcado_como_utc(client, headers_depto_a, db):
    """Sin la marca de zona, el navegador lee el instante como hora local.

    La campanita calcula "hace cuánto" restando; con el corrimiento la resta
    da negativa y todo aviso dice "recién" durante sus primeras horas de vida.
    """
    from backend.models import Notificacion

    db.add(Notificacion(consorcio_id=1, usuario_id=2, tipo="x", mensaje="X"))
    db.commit()

    r = client.get("/notificaciones", headers=headers_depto_a)
    assert r.status_code == 200
    crudo = r.json()[0]["created_at"]
    assert crudo.endswith("Z") or crudo.endswith("+00:00"), crudo


def test_fecha_creacion_de_peticion_sale_marcada_como_utc(client, headers_depto_a):
    """Mismo instante en UTC que `created_at`: la pone la base con su reloj."""
    r = client.get("/peticiones", headers=headers_depto_a)
    assert r.status_code == 200
    crudo = r.json()[0]["fecha_creacion"]
    assert crudo.endswith("Z") or crudo.endswith("+00:00"), crudo


def test_el_horario_de_una_reserva_no_se_marca_como_utc(client, headers_depto_a):
    """La reserva NO es un instante del reloj de la base: es hora de pared.

    El vecino eligió "de 14 a 17" en el calendario del consorcio. Marcarla como
    UTC la correría por el huso y el SUM aparecería reservado a otra hora.
    """
    r = client.get("/reservas", headers=headers_depto_a)
    assert r.status_code == 200
    assert r.json(), "el seed tiene una reserva confirmada"
    crudo = r.json()[0]["inicio"]
    assert not crudo.endswith("Z") and not crudo.endswith("+00:00"), crudo
