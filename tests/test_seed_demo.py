from datetime import date

from backend.seed_demo import meses_demo, perfiles_deterministas


def test_meses_demo_devuelve_los_6_meses_completos_anteriores():
    # El mes en curso (julio) queda deliberadamente abierto: el visitante
    # tiene un periodo vivo para cargar gastos y probar el cierre el mismo.
    assert meses_demo(date(2026, 7, 31)) == [
        "2026-01", "2026-02", "2026-03", "2026-04", "2026-05", "2026-06",
    ]


def test_meses_demo_cruza_el_anio_correctamente():
    assert meses_demo(date(2026, 3, 15)) == [
        "2025-09", "2025-10", "2025-11", "2025-12", "2026-01", "2026-02",
    ]


def test_meses_demo_desde_enero():
    assert meses_demo(date(2026, 1, 1)) == [
        "2025-07", "2025-08", "2025-09", "2025-10", "2025-11", "2025-12",
    ]


def test_meses_demo_respeta_la_cantidad():
    assert meses_demo(date(2026, 7, 31), cantidad=2) == ["2026-05", "2026-06"]


def _deptos(n):
    letras = "ABCDEF"
    return [
        {"id": i + 1, "codigo": f"UF-{i // 6 + 1:02d}{letras[i % 6]}"}
        for i in range(n)
    ]


def test_perfiles_pinnean_uf01a_puntual_y_uf03c_moroso():
    # El selector de rol apunta a uf01a@ y uf03c@, asi que su comportamiento
    # no puede salir de un shuffle: tiene que ser estable entre corridas.
    puntuales, irregulares, morosos = perfiles_deterministas(_deptos(18))
    assert "UF-01A" in {d["codigo"] for d in puntuales}
    assert "UF-03C" in {d["codigo"] for d in morosos}


def test_perfiles_reparten_18_deptos_como_12_3_3():
    puntuales, irregulares, morosos = perfiles_deterministas(_deptos(18))
    assert (len(puntuales), len(irregulares), len(morosos)) == (12, 3, 3)


def test_perfiles_no_pierden_ni_duplican_deptos():
    deptos = _deptos(18)
    puntuales, irregulares, morosos = perfiles_deterministas(deptos)
    ids = [d["id"] for d in puntuales + irregulares + morosos]
    assert sorted(ids) == sorted(d["id"] for d in deptos)


def test_perfiles_es_estable_entre_corridas():
    a = perfiles_deterministas(_deptos(18))
    b = perfiles_deterministas(_deptos(18))
    assert [[d["codigo"] for d in grupo] for grupo in a] == \
           [[d["codigo"] for d in grupo] for grupo in b]
