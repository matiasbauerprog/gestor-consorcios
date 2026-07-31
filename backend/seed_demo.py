"""Generador del dataset demo — 18 UF, 6 meses de operación real.

A diferencia de `backend/seed.py` (fixture de smoke-test que escribe directo a
la DB), este módulo puebla la app **a través de su propia API** con TestClient
in-process, reusando la maquinaria de `backend/seed_e2e.py`. Dos consecuencias:

1. El dataset es consistente por construcción: los saldos, los intereses y el
   FIFO de pagos los calcula el mismo código que corre en producción.
2. El generador funciona como test end-to-end de 6 meses de operación. Si
   termina sin error, el sistema aguanta un semestre.

Uso:
    DEMO_SEED_PASSWORD=... SUPER_ADMIN_EMAIL=... SUPER_ADMIN_PASSWORD=... \\
    DATABASE_URL=sqlite:///./demo.db SEED_ENABLED=false \\
        python -m backend.seed_demo [--reset]

`SEED_ENABLED=false` no es opcional: el lifespan de backend/main.py corre
`seed_if_empty`, que sobre una base vacía crea la "Administración Demo" y el
"Consorcio Demo" del smoke-test. Ese consorcio fantasma quedaría a la vista del
visitante junto al demo real.
"""
import os
import sys
import time
from datetime import date, timedelta

from .seed_e2e import (
    RNG,
    Api,
    _caja_default,
    _consorcio_payload,
    _dia_del_periodo,
    _fechas_del_periodo,
    _padron_csv,
)
from .seed_e2e import _PNG_1PX as _PNG_1PX_DEMO
from .seed_e2e import RUBROS_COMUNES

PISOS_DEMO = 3                      # 3 pisos × 6 unidades (A–F) = 18 UF
DOMINIO_DEMO = "demo.local"
EMAIL_ADMIN_DEMO = "admin@demo.local"
NOMBRE_CONSORCIO = "Edificio Libertador"

# Deptos pinneados: son los destinos del selector de rol de /auth/demo-login.
CODIGO_PUNTUAL_FIJO = "UF-01A"
CODIGO_MOROSO_FIJO = "UF-03C"


def meses_demo(hoy: date, cantidad: int = 6) -> list[str]:
    """Los `cantidad` meses calendario completos anteriores al mes en curso.

    Corriendo el 2026-07-31 → ['2026-01' … '2026-06'].
    El mes en curso queda abierto a propósito: el visitante tiene un período
    vivo donde cargar gastos y probar el cierre él mismo, que es la acción más
    demostrativa del sistema.
    """
    meses: list[str] = []
    anio, mes = hoy.year, hoy.month
    for _ in range(cantidad):
        mes -= 1
        if mes == 0:
            anio, mes = anio - 1, 12
        meses.append(f"{anio:04d}-{mes:02d}")
    return list(reversed(meses))


def perfiles_deterministas(
    deptos: list[dict],
) -> tuple[list[dict], list[dict], list[dict]]:
    """Reparte los deptos en (puntuales, irregulares, morosos) sin azar.

    `seed_e2e.py` mezcla con RNG.shuffle antes de asignar perfiles. Para el demo
    eso no sirve: el selector de rol apunta a emails fijos, así que qué depto es
    moroso tiene que estar pinneado y ser estable entre corridas.

    Mantiene la distribución 70/15/15 del original, que sobre 18 UF da 12/3/3.
    """
    por_codigo = {d["codigo"]: d for d in deptos}
    n = len(deptos)
    cupo_puntuales = int(n * 0.70)
    cupo_irregulares = int(n * 0.85) - cupo_puntuales

    fijo_puntual = por_codigo.get(CODIGO_PUNTUAL_FIJO)
    fijo_moroso = por_codigo.get(CODIGO_MOROSO_FIJO)
    pinneados = {d["codigo"] for d in (fijo_puntual, fijo_moroso) if d is not None}

    # Orden estable por código, con los pinneados fuera del reparto para no
    # asignarlos dos veces. Se reinsertan a mano en su grupo al final.
    resto = [
        d for d in sorted(deptos, key=lambda x: x["codigo"])
        if d["codigo"] not in pinneados
    ]

    # Un solo cursor sobre `resto` garantiza el invariante que piden los tests:
    # cada depto cae en exactamente un grupo, sin huecos ni repetidos.
    cursor = 0
    puntuales = [fijo_puntual] if fijo_puntual is not None else []
    faltan = max(cupo_puntuales - len(puntuales), 0)
    puntuales += resto[cursor:cursor + faltan]
    cursor += faltan

    irregulares = resto[cursor:cursor + cupo_irregulares]
    cursor += len(irregulares)

    # Los morosos se llevan el remanente: así nunca se pierde un depto por
    # redondeo de los cupos.
    morosos = ([fijo_moroso] if fijo_moroso is not None else []) + resto[cursor:]

    return puntuales, irregulares, morosos


def poblar_demo(api, admin_token, seed_password: str) -> dict:
    """Crea el consorcio demo y lo puebla con 6 meses de operación."""
    t0 = time.monotonic()
    meses = meses_demo(date.today())

    r = api.req("POST", "/consorcios", token=admin_token,
                json=_consorcio_payload(NOMBRE_CONSORCIO, 33333), expect=201)
    cid = r.json()["id"]

    r = api.req("POST", "/clases-prorrateo", token=admin_token, cid=cid,
                json={"codigo": "A", "nombre": "Expensas ordinarias"}, expect=201)
    clase_a = r.json()["id"]
    r = api.req("POST", "/clases-prorrateo", token=admin_token, cid=cid,
                json={"codigo": "B", "nombre": "Expensas extraordinarias"}, expect=201)
    clase_b = r.json()["id"]

    proveedores = []
    for razon in ["Limpieza Total SRL", "Ascensores Vertirod SA", "ElectroSur SRL",
                  "Plomería Paz", "Seguros La Continental"]:
        r = api.req("POST", "/proveedores", token=admin_token, cid=cid,
                    json={"razon_social": razon,
                          "cuit": f"30-{RNG.randint(10_000_000, 99_999_999)}-{RNG.randint(0, 9)}"},
                    expect=201)
        proveedores.append(r.json()["id"])

    amenities = {}
    for nombre_a, precio in [("SUM", 25_000.0), ("Laundry", 3_000.0)]:
        r = api.req("POST", "/amenities", token=admin_token, cid=cid,
                    json={"nombre": nombre_a, "precio_reserva": precio}, expect=201)
        amenities[nombre_a] = r.json()["id"]

    # Padrón: 3 pisos × 6 unidades = 18 UF, con sus usuarios.
    csv_bytes = _padron_csv(PISOS_DEMO, DOMINIO_DEMO)
    r = api.req("POST", "/padron/importar", token=admin_token, cid=cid,
                files={"file": ("padron.csv", csv_bytes, "text/csv")}, expect=200)
    resultados = r.json()["resultados"]
    passwords_iniciales = {x["email"]: x["password_generada"] for x in resultados}

    r = api.req("GET", "/departamentos", token=admin_token, cid=cid, expect=200)
    deptos = r.json()
    n = len(deptos)

    base = round(100.0 / n, 4)
    coefs = [{"departamento_id": d["id"], "clase_prorrateo_id": clase_a,
              "porcentaje": base} for d in deptos]
    coefs[-1]["porcentaje"] = round(100.0 - base * (n - 1), 4)
    api.req("PUT", "/coeficientes", token=admin_token, cid=cid,
            json={"coeficientes": coefs}, expect=200)

    puntuales, irregulares, morosos = perfiles_deterministas(deptos)

    email_de = {d["id"]: f"uf{d['codigo'][3:].lower()}@{DOMINIO_DEMO}" for d in deptos}
    tokens_depto = {}
    for depto in puntuales + irregulares:
        email = email_de[depto["id"]]
        token = api.login(email, passwords_iniciales[email])
        api.cambiar_password(token, passwords_iniciales[email], seed_password)
        tokens_depto[depto["id"]] = token

    comprobantes = 0
    for periodo in meses:
        for rubro, concepto, lo, hi in RUBROS_COMUNES:
            api.req("POST", "/gastos", token=admin_token, cid=cid, json={
                "periodo": periodo, "rubro": rubro,
                "clase_prorrateo_id": clase_a,
                "proveedor_id": RNG.choice(proveedores),
                "concepto": concepto,
                "monto": round(RNG.uniform(lo, hi), 2),
                "forma_pago": "transferencia",
                "caja_id": _caja_default(api, admin_token, cid),
                "fecha_pago": _dia_del_periodo(periodo, RNG.randint(3, 26)).isoformat(),
            }, expect=201)

        for _ in range(RNG.randint(1, 3)):
            depto = RNG.choice(deptos)
            api.req("POST", "/gastos", token=admin_token, cid=cid, json={
                "periodo": periodo, "rubro": "trabajos_reparaciones_unidades",
                "departamento_id": depto["id"],
                "proveedor_id": RNG.choice(proveedores),
                "concepto": f"Reparación privada {depto['codigo']}",
                "monto": round(RNG.uniform(15_000, 90_000), 2),
                "forma_pago": "transferencia",
                "caja_id": _caja_default(api, admin_token, cid),
                "fecha_pago": _dia_del_periodo(periodo, RNG.randint(5, 25)).isoformat(),
            }, expect=201)

        f1, f2 = _fechas_del_periodo(periodo)
        api.req("POST", f"/periodos/{periodo}/cerrar", token=admin_token, cid=cid, json={
            "fecha_primer_vencimiento": f1.isoformat(),
            "fecha_segundo_vencimiento": f2.isoformat(),
        }, expect=201)

        r = api.req("GET", f"/expensas?periodo={periodo}", token=admin_token, cid=cid,
                    expect=200)
        expensas_por_depto = {e["departamento_id"]: e for e in r.json()}

        pagan = [d["id"] for d in puntuales]
        pagan += [d["id"] for d in irregulares if RNG.random() < 0.5]

        for depto_id in pagan:
            exp = expensas_por_depto.get(depto_id)
            if exp is None or depto_id not in tokens_depto:
                continue
            fecha_pago = min(f1 - timedelta(days=RNG.randint(0, 5)), date.today())
            monto = exp["monto_primer_vencimiento"]
            if RNG.random() < 0.05:
                monto = float(int(monto / 1000 + 1) * 1000)
            r = api.req("POST", "/comprobantes", token=tokens_depto[depto_id], cid=cid,
                        data={"fecha_pago": fecha_pago.isoformat(), "monto": monto},
                        files={"archivo": ("pago.png", _PNG_1PX_DEMO, "image/png")},
                        expect=201)
            api.req("PATCH", f"/comprobantes/{r.json()['id']}", token=admin_token, cid=cid,
                    json={"estado": "aprobado"}, expect=200)
            comprobantes += 1
        print(f"[demo] {periodo}: cerrado · {len(pagan)} pagos")

    dt = time.monotonic() - t0
    return {
        "consorcio_id": cid,
        "clase_a": clase_a,
        "clase_b": clase_b,
        "deptos": n,
        "meses": meses,
        "comprobantes": comprobantes,
        "amenities": amenities,
        "proveedores": proveedores,
        "tokens_depto": tokens_depto,
        "morosos": [d["codigo"] for d in morosos],
        "segundos": round(dt, 1),
    }


# Guard de reentrada. generar_dataset_demo levanta la app con TestClient, lo
# que vuelve a correr el lifespan de backend/main.py — y ese lifespan, en modo
# demo, llama a generar_dataset_demo si la base está vacía. Sin este flag la
# generación se invocaría a sí misma sin fin al bootear.
GENERANDO = False


def _resetear_esquema(engine) -> None:
    """Borra todas las tablas para regenerar el dataset desde cero.

    En SQLite no alcanza con `drop_all`: backend/database.py activa
    `PRAGMA foreign_keys=ON` en cada conexión, así que al soltar la primera
    tabla referenciada por otra con filas cargadas SQLite tira
    `IntegrityError: FOREIGN KEY constraint failed`. El pragma es *por
    conexión*, por eso lo apagamos en la misma conexión donde corre el DROP en
    vez de tocar la configuración global del engine.
    """
    from sqlalchemy import text

    from .models import Base

    if engine.url.get_backend_name() == "sqlite":
        with engine.connect() as conn:
            conn.execute(text("PRAGMA foreign_keys=OFF"))
            Base.metadata.drop_all(bind=conn)
            conn.commit()
    else:
        Base.metadata.drop_all(bind=engine)


def generar_dataset_demo(*, seed_password: str, sa_email: str, sa_password: str,
                         reset: bool = False) -> dict:
    """Genera el dataset demo completo. Núcleo reusable.

    No lee sys.argv ni llama a sys.exit: la Task 7 lo invoca desde el lifespan
    del servidor, donde un exit abrupto dejaría la app muerta. Ante un problema
    levanta la excepción para que el llamador decida.
    """
    global GENERANDO
    from fastapi.testclient import TestClient

    from .database import SessionLocal, engine
    from .main import app
    from .seed_super_admin import seed as seed_super_admin

    if reset:
        print("[demo] reset: borrando todas las tablas")
        _resetear_esquema(engine)

    t0 = time.monotonic()
    GENERANDO = True
    try:
        return _generar(seed_password, sa_email, sa_password, t0, TestClient,
                        app, SessionLocal, seed_super_admin)
    finally:
        GENERANDO = False


def _generar(seed_password, sa_email, sa_password, t0, TestClient, app,
             SessionLocal, seed_super_admin) -> dict:
    with TestClient(app) as client:  # lifespan: create_all + migraciones
        with SessionLocal() as db:
            seed_super_admin(db)

        api = Api(client)
        sa_token = api.login(sa_email, sa_password)

        r = api.req("POST", "/super-admin/administraciones", token=sa_token, json={
            "razon_social": "Administración Demo SRL",
            "cuit": "30-70000000-3",
            "email_contacto": "contacto@demo.local",
            "admin_email": EMAIL_ADMIN_DEMO,
            "admin_password_inicial": seed_password + "-inicial",
        }, expect=201)
        print(f"[demo] administración creada id={r.json()['id']}")

        admin_token = api.login(EMAIL_ADMIN_DEMO, seed_password + "-inicial")
        api.cambiar_password(admin_token, seed_password + "-inicial", seed_password)

        m = poblar_demo(api, admin_token, seed_password)

    m["segundos_total"] = round(time.monotonic() - t0, 1)
    print(f"\n[demo] listo en {m['segundos_total']} s · {m['deptos']} UF · "
          f"{len(m['meses'])} períodos · {m['comprobantes']} comprobantes")
    print(f"[demo] meses generados: {m['meses'][0]} … {m['meses'][-1]}")
    return m


def main() -> None:
    """Entrypoint de CLI: valida el entorno y delega."""
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    sa_email = os.environ.get("SUPER_ADMIN_EMAIL", "")
    sa_password = os.environ.get("SUPER_ADMIN_PASSWORD", "")
    seed_password = os.environ.get("DEMO_SEED_PASSWORD", "")
    if not sa_email or not sa_password or not seed_password:
        print("Faltan SUPER_ADMIN_EMAIL / SUPER_ADMIN_PASSWORD / DEMO_SEED_PASSWORD",
              file=sys.stderr)
        sys.exit(1)
    if len(seed_password) < 8:
        print("DEMO_SEED_PASSWORD debe tener al menos 8 caracteres", file=sys.stderr)
        sys.exit(1)

    generar_dataset_demo(
        seed_password=seed_password,
        sa_email=sa_email,
        sa_password=sa_password,
        reset="--reset" in sys.argv,
    )


if __name__ == "__main__":
    main()
