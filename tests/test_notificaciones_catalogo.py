"""El catálogo es declarativo: estos tests lo tratan como datos, no como código."""
import pytest

from backend.models import Rol
from backend.notificaciones.catalogo import (
    CATALOGO,
    Audiencia,
    evento,
    eventos_para_rol,
)


def test_catalogo_tiene_los_doce_eventos():
    assert len(CATALOGO) == 12


def test_evento_desconocido_explota():
    with pytest.raises(KeyError):
        evento("no_existe")


def test_la_clave_del_dict_coincide_con_la_del_evento():
    for clave, ev in CATALOGO.items():
        assert ev.clave == clave


def test_un_evento_que_no_manda_mail_no_declara_asunto():
    for ev in CATALOGO.values():
        if not ev.email_por_defecto and ev.asunto is None:
            assert ev.cuerpo is None, f"{ev.clave} declara cuerpo sin asunto"
        if ev.asunto is not None:
            assert ev.cuerpo is not None, f"{ev.clave} declara asunto sin cuerpo"


def test_un_evento_que_manda_mail_por_defecto_declara_asunto():
    for ev in CATALOGO.values():
        if ev.email_por_defecto:
            assert ev.asunto is not None, f"{ev.clave} manda mail sin asunto"


def test_solo_reserva_confirmada_es_solo_mail():
    solo_mail = [ev.clave for ev in CATALOGO.values() if not ev.crea_campanita]
    assert solo_mail == ["reserva_confirmada"]


def test_los_pendientes_son_exactamente_dos():
    pendientes = sorted(ev.clave for ev in CATALOGO.values() if ev.entidad_tipo)
    assert pendientes == ["comprobante_presentado", "peticion_nueva"]


def test_eventos_para_rol_departamento():
    claves = {ev.clave for ev in eventos_para_rol(Rol.departamento)}
    assert claves == {
        "peticion_estado_cambiado",
        "trabajo_completado",
        "reserva_confirmada",
        "reserva_cancelada_por_admin",
        "comunicado_publicado",
        "expensa_emitida",
        "comprobante_aprobado",
        "comprobante_rechazado",
    }


def test_eventos_para_rol_administracion():
    claves = {ev.clave for ev in eventos_para_rol(Rol.administracion)}
    assert claves == {
        "peticion_nueva",
        "comprobante_presentado",
        "peticion_borrada_por_depto",
        "reserva_nueva_de_depto",
    }


def test_eventos_para_representante_es_vacio():
    assert eventos_para_rol(Rol.representante) == []


def test_mensaje_de_peticion_incluye_el_estado_crudo():
    # tests/test_trabajos.py filtra por este texto. No es cosmético.
    ev = evento("peticion_estado_cambiado")
    texto = ev.mensaje({"titulo": "Filtración", "estado": "convertida_en_trabajo"})
    assert "convertida_en_trabajo" in texto


def test_todas_las_audiencias_son_conocidas():
    for ev in CATALOGO.values():
        assert ev.audiencia in (Audiencia.DEPARTAMENTO, Audiencia.ADMINISTRACION)
