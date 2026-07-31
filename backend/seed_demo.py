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


def crear_catalogo_personal(api, admin_token, cid, proveedor_id: int) -> dict:
    """Empleado + haberes + conceptos de liquidación del encargado.

    Sin esto el módulo Personal queda vacío en el demo, que es justo uno de
    los diferenciales frente a llevar el consorcio en una planilla.

    Los payloads siguen EmpleadoCrear (backend/schemas.py:666), HaberCrear
    (:701) y ConceptoLiquidacionCrear (:727). Ojo con los enums: `categoria`
    es CategoriaEmpleado, `tipo` de haber es TipoHaber y `tipo` de concepto es
    TipoConcepto (backend/models.py:125-140).
    """
    r = api.req("POST", "/empleados", token=admin_token, cid=cid, json={
        "nombre_completo": "Ramón Gutiérrez",
        "cuil": "20-14555666-3",
        "categoria": "encargado_permanente_con_vivienda",
        "fecha_ingreso": "2019-03-01",
        "sueldo_basico": 950_000.0,
        "proveedor_id": proveedor_id,
    }, expect=201)
    empleado_id = r.json()["id"]

    # Proveedores institucionales para descuentos y contribuciones. Se crean
    # acá — no se reusan los proveedores comerciales del consorcio (limpieza,
    # ascensores, etc.) porque no representan a quién se le paga de verdad
    # una retención o contribución — siguiendo el mismo patrón que
    # backend/seed.py (Fase 3: AFIP/ARCA/FATERYH/SUTERH como Proveedor).
    # "AFIP", "FATERYH" y "SUTERH" son nombres genérico-institucionales del
    # rubro (como "AFIP" en cualquier software de administración argentino);
    # para el proveedor de ART usamos una etiqueta obviamente ficticia
    # ("ART Demo SA") en vez del nombre de una aseguradora real — este
    # dataset se publica en un demo público y una razón social real con un
    # CUIT inventado se leería como un dato genuino.
    r = api.req("POST", "/proveedores", token=admin_token, cid=cid, json={
        "razon_social": "AFIP", "cuit": "30-00000101-1",
    }, expect=201)
    proveedor_afip = r.json()["id"]
    r = api.req("POST", "/proveedores", token=admin_token, cid=cid, json={
        "razon_social": "FATERYH", "cuit": "30-00000102-2",
    }, expect=201)
    proveedor_fateryh = r.json()["id"]
    r = api.req("POST", "/proveedores", token=admin_token, cid=cid, json={
        "razon_social": "SUTERH", "cuit": "30-00000103-3",
    }, expect=201)
    proveedor_suterh = r.json()["id"]
    r = api.req("POST", "/proveedores", token=admin_token, cid=cid, json={
        "razon_social": "ART Demo SA", "cuit": "30-00000104-4",
    }, expect=201)
    proveedor_art = r.json()["id"]

    # El sueldo básico NO entra solo por estar en el empleado: _calcular_y_guardar
    # (backend/routers/liquidaciones.py:289) arma el bruto sumando únicamente
    # los haberes de la liquidación. Por eso el catálogo necesita un haber
    # "Básico" porcentaje_sobre_basico al 100%, igual que backend/seed.py:338 —
    # sin él, el bruto se arma sólo con los adicionales y el sueldo real del
    # encargado casi desaparece del rubro.
    # "Horas extra" queda última a propósito: poblar_demo necesita saber cuál
    # de los ids requiere `cantidad` al armar la liquidación
    # (LiquidacionHaberItem, schemas.py:756).
    haberes = []
    for orden, (nombre, tipo, valor) in enumerate([
        ("Básico", "porcentaje_sobre_basico", 100.0),
        ("Antigüedad", "porcentaje_sobre_basico", 20.0),
        ("Presentismo", "monto_fijo", 95_000.0),
        ("Plus por limpieza", "monto_fijo", 60_000.0),
        ("Horas extra", "cantidad_x_valor", 6_500.0),
    ]):
        r = api.req("POST", "/haberes", token=admin_token, cid=cid, json={
            "nombre": nombre, "tipo": tipo,
            "valor_default": valor, "orden": orden,
        }, expect=201)
        haberes.append(r.json()["id"])

    # Todos los conceptos llevan `proveedor_id`, descuentos incluidos.
    # _generar_gastos (backend/routers/liquidaciones.py:252-276) sólo
    # materializa un Gasto por cada proveedor con detalle asociado — sin
    # proveedor_id el monto se calcula y queda en liquidacion.detalle, pero
    # nunca entra al prorrateo. Los descuentos NO son un pago que el empleado
    # hace por su cuenta: el empleador los retiene del bruto y los deposita
    # él mismo en AFIP, la obra social y el sindicato — por eso también
    # necesitan generar su propio Gasto, igual que backend/seed.py:349-355
    # (que le asigna proveedor_id a los 4 conceptos `descuento`, no sólo a
    # las contribuciones). Esto no duplica el descuento del neto:
    # `descuentos_total` en _generar_gastos se calcula por `concepto_tipo`,
    # sin importar si el concepto tiene proveedor — el Gasto por-proveedor es
    # un agrupado aparte sobre `liquidacion.detalle`.
    conceptos = []
    for orden, (nombre, tipo, porcentaje, prov) in enumerate([
        ("Jubilación", "descuento", 11.0, proveedor_afip),
        ("Ley 19.032", "descuento", 3.0, proveedor_afip),
        ("Obra social FATERYH", "descuento", 3.0, proveedor_fateryh),
        ("Sindicato SUTERH", "descuento", 2.0, proveedor_suterh),
        ("Contribuciones patronales", "contribucion", 17.0, proveedor_afip),
        ("ART", "contribucion", 5.0, proveedor_art),
    ]):
        payload = {"nombre": nombre, "tipo": tipo, "porcentaje": porcentaje, "orden": orden}
        if prov is not None:
            payload["proveedor_id"] = prov
        r = api.req("POST", "/conceptos-liquidacion", token=admin_token, cid=cid, json=payload,
                    expect=201)
        conceptos.append(r.json()["id"])

    return {"empleado_id": empleado_id, "haberes": haberes, "conceptos": conceptos}


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

    # El encargado necesita un proveedor (le paga la administración); usamos
    # el primero de la lista ya creada arriba.
    personal = crear_catalogo_personal(api, admin_token, cid, proveedores[0])

    puntuales, irregulares, morosos = perfiles_deterministas(deptos)

    email_de = {d["id"]: f"uf{d['codigo'][3:].lower()}@{DOMINIO_DEMO}" for d in deptos}
    tokens_depto = {}
    for depto in puntuales + irregulares:
        email = email_de[depto["id"]]
        token = api.login(email, passwords_iniciales[email])
        api.cambiar_password(token, passwords_iniciales[email], seed_password)
        tokens_depto[depto["id"]] = token

    comprobantes = 0
    liquidaciones = 0
    for periodo in meses:
        for rubro, concepto, lo, hi in RUBROS_COMUNES:
            if rubro == "sueldos_y_cargas_sociales":
                continue  # ahora los genera la liquidación, ver más abajo
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

        # Liquidación del encargado: genera gastos del rubro
        # sueldos_y_cargas_sociales que tienen que entrar al prorrateo de
        # este período, por eso se carga antes del cierre.
        haberes_payload = [{"haber_id": h} for h in personal["haberes"]]
        # El último haber del catálogo (Horas extra) es cantidad_x_valor: sin
        # `cantidad` el endpoint devuelve 400 "requiere `cantidad`"
        # (backend/routers/liquidaciones.py:148).
        haberes_payload[-1]["cantidad"] = 8.0
        api.req("POST", "/liquidaciones", token=admin_token, cid=cid, json={
            "empleado_id": personal["empleado_id"],
            "periodo": periodo,
            "caja_id": _caja_default(api, admin_token, cid),
            "haberes": haberes_payload,
        }, expect=201)
        liquidaciones += 1

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
        "liquidaciones": liquidaciones,
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
    `PRAGMA foreign_keys=ON` en cada conexión, y el modelo tiene un ciclo de FK
    (cajas → consorcios → presupuestos → trabajos), así que al soltar la primera
    tabla referenciada por otra con filas cargadas SQLite tira
    `IntegrityError: FOREIGN KEY constraint failed`. El pragma es *por
    conexión*, por eso lo apagamos en la conexión donde corre el DROP en vez de
    tocar la configuración global del engine.
    """
    from sqlalchemy import text

    from .models import Base

    if engine.url.get_backend_name() != "sqlite":
        Base.metadata.drop_all(bind=engine)
        return

    try:
        with engine.connect() as conn:
            conn.execute(text("PRAGMA foreign_keys=OFF"))
            Base.metadata.drop_all(bind=conn)
            conn.commit()
    finally:
        # Salir del `with` NO cierra la conexión física: la devuelve al
        # QueuePool con foreign_keys todavía en OFF. El listener de
        # backend/database.py:19 sólo corre al abrir conexiones *nuevas*, no en
        # los checkouts reciclados, y el pool es LIFO — así que el próximo
        # SessionLocal() del proceso se lleva justo esa conexión y opera sin
        # integridad referencial, en silencio y para siempre. Acá pasa de
        # verdad: generar_dataset_demo() sigue con TestClient(app), cuyo
        # lifespan hace create_all sobre este mismo engine, y la Task 7 va a
        # llamar a todo esto desde el proceso del servidor vivo en cada corrida
        # del cron.
        #
        # dispose() descarta el pool entero, así que la siguiente conexión es
        # física y nueva y el listener vuelve a poner foreign_keys=ON. Se
        # prefiere a un `PRAGMA foreign_keys=ON` de cierre porque va en
        # `finally`: si el drop falla a mitad de camino, la conexión vuelve al
        # pool igual de envenenada, y un pragma de reparación tendría que correr
        # sobre una conexión que quizás ya está en estado inválido.
        engine.dispose()


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
