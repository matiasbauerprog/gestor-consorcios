"""Seed E2E a gran escala — puebla la app EXCLUSIVAMENTE a través de la API.

A diferencia de un seed que escribe directo a la DB, este script pasa por
todas las validaciones de negocio (períodos cerrados, tenancy, permisos,
passwords). Si algo falla acá, es un bug real de la aplicación.

Escala: 2 consorcios (60 y 120 deptos) × 6 meses de gastos, cierres,
expensas, pagos por comprobante, reservas de amenities y peticiones/trabajos.

Uso:
    SUPER_ADMIN_EMAIL=... SUPER_ADMIN_PASSWORD=... SEED_E2E_PASSWORD=... \
        python -m backend.seed_e2e

Variables requeridas (sin defaults — nunca hardcodear credenciales):
    SUPER_ADMIN_EMAIL / SUPER_ADMIN_PASSWORD  credenciales del super admin
    SEED_E2E_PASSWORD  password que quedará para TODOS los usuarios de prueba
"""
import csv as csv_mod
import io
import os
import random
import sys
import time
from datetime import date, datetime, timedelta

# Reproducible: mismos datos en cada corrida.
RNG = random.Random(20260710)

# PNG 1×1 válido para comprobantes (asset binario, no una credencial).
_PNG_1PX = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
    "0000000d4944415478da63fcffff3f0300050201f2a2668e0000000049454e44ae426082"
)

MESES = ["2026-01", "2026-02", "2026-03", "2026-04", "2026-05", "2026-06"]

RUBROS_COMUNES = [
    ("sueldos_y_cargas_sociales", "Sueldo encargado", 900_000, 1_300_000),
    ("sueldos_y_cargas_sociales", "Cargas sociales", 350_000, 500_000),
    ("servicios_publicos", "AySA agua común", 40_000, 90_000),
    ("servicios_publicos", "Edesur espacios comunes", 60_000, 130_000),
    ("abonos_y_servicios", "Abono limpieza", 180_000, 260_000),
    ("abonos_y_servicios", "Abono ascensores", 120_000, 200_000),
    ("abonos_y_servicios", "Fumigación mensual", 25_000, 45_000),
    ("mantenimiento_partes_comunes", "Mantenimiento bombas", 30_000, 80_000),
    ("gastos_administracion", "Honorarios administración", 250_000, 350_000),
    ("gastos_bancarios", "Comisiones bancarias", 8_000, 20_000),
    ("seguros", "Seguro integral consorcio", 90_000, 140_000),
]


class ApiError(RuntimeError):
    pass


class Api:
    """Wrapper mínimo sobre TestClient con manejo de token + X-Consorcio-Id."""

    def __init__(self, client):
        self.client = client

    def req(self, method, path, *, token=None, cid=None, expect=None, **kw):
        headers = kw.pop("headers", {})
        if token:
            headers["Authorization"] = f"Bearer {token}"
        if cid is not None:
            headers["X-Consorcio-Id"] = str(cid)
        r = self.client.request(method, path, headers=headers, **kw)
        if expect is not None and r.status_code != expect:
            raise ApiError(
                f"{method} {path} → {r.status_code} (esperaba {expect}): {r.text[:300]}"
            )
        return r

    def login(self, email, password):
        r = self.req(
            "POST", "/auth/login",
            json={"email": email, "password": password}, expect=200,
        )
        return r.json()["access_token"]

    def cambiar_password(self, token, actual, nueva):
        self.req(
            "POST", "/auth/cambiar-password", token=token,
            json={"current_password": actual, "new_password": nueva}, expect=204,
        )


def _consorcio_payload(nombre, cuit_suffix):
    return {
        "nombre": nombre,
        "consorcio_domicilio": f"Av. Siempreviva {RNG.randint(100, 9999)}, CABA",
        "consorcio_cuit": f"30-711{cuit_suffix:05d}-{RNG.randint(0,9)}",
        "usa_personal_propio": True,
        "admin_nombre": "Administración Semilla SRL",
        "admin_domicilio": "Lavalle 1234 4°B, CABA",
        "admin_email": "contacto@semilla-admin.local",
        "admin_telefono": "11-5555-0000",
        "admin_cuit": "30-70000000-3",
        "admin_rpa": "12345",
        "admin_situacion_fiscal": "Responsable Inscripto",
        "banco_titular": f"Consorcio {nombre}",
        "banco_nombre": "Banco Nación",
        "banco_sucursal": "0042",
        "banco_numero_cuenta": f"000-{RNG.randint(100000,999999)}/9",
        "banco_cbu": "".join(str(RNG.randint(0, 9)) for _ in range(22)),
        "banco_alias": f"{nombre.split()[0].upper()}.EXPENSAS",
        "dia_primer_vencimiento": 10,
        "dias_entre_vencimientos": 10,
        "recargo_segundo_vencimiento_pct": 7.0,
        "tasa_interes_mensual_pct": 3.0,
        "reportes_visibles_a_depto": True,
    }


def _padron_csv(pisos, dominio):
    """CSV codigo,ubicacion,email para POST /padron/importar."""
    buf = io.StringIO()
    w = csv_mod.writer(buf)
    w.writerow(["codigo", "ubicacion", "email"])
    letras = "ABCDEF"
    for piso in range(1, pisos + 1):
        for letra in letras:
            codigo = f"UF-{piso:02d}{letra}"
            w.writerow([
                codigo,
                f"Piso {piso}, Unidad {letra}",
                f"uf{piso:02d}{letra.lower()}@{dominio}",
            ])
    return buf.getvalue().encode("utf-8")


def _fechas_del_periodo(periodo):
    """Vencimientos históricos: día 10 del mes siguiente, +10 días."""
    anio, mes = map(int, periodo.split("-"))
    if mes == 12:
        anio, mes = anio + 1, 1
    else:
        mes += 1
    f1 = date(anio, mes, 10)
    return f1, f1 + timedelta(days=10)


def _dia_del_periodo(periodo, dia):
    anio, mes = map(int, periodo.split("-"))
    return date(anio, mes, min(dia, 28))


def seed_consorcio(api, admin_token, nombre, pisos, dominio, cuit_suffix, seed_password):
    """Crea y puebla un consorcio completo. Devuelve dict con métricas."""
    t0 = time.monotonic()

    # --- Consorcio + catálogos ---
    r = api.req("POST", "/consorcios", token=admin_token,
                json=_consorcio_payload(nombre, cuit_suffix), expect=201)
    cid = r.json()["id"]
    print(f"[{nombre}] consorcio id={cid}")

    r = api.req("POST", "/clases-prorrateo", token=admin_token, cid=cid,
                json={"codigo": "A", "nombre": "Expensas ordinarias"}, expect=201)
    clase_a = r.json()["id"]

    proveedores = []
    for razon in ["Limpieza Total SRL", "Ascensores Vertirod SA", "ElectroSur SRL",
                  "Plomería Paz", "Seguros La Continental"]:
        r = api.req("POST", "/proveedores", token=admin_token, cid=cid,
                    json={"razon_social": f"{razon}", "cuit": f"30-{RNG.randint(10_000_000, 99_999_999)}-{RNG.randint(0,9)}"},
                    expect=201)
        proveedores.append(r.json()["id"])

    amenities = {}
    for nombre_a, precio in [("SUM", 25_000.0), ("Parrilla", 10_000.0), ("Laundry", 3_000.0)]:
        r = api.req("POST", "/amenities", token=admin_token, cid=cid,
                    json={"nombre": nombre_a, "precio_reserva": precio}, expect=201)
        amenities[nombre_a] = r.json()["id"]

    # --- Padrón masivo (deptos + usuarios) por CSV ---
    csv_bytes = _padron_csv(pisos, dominio)
    r = api.req("POST", "/padron/importar", token=admin_token, cid=cid,
                files={"file": ("padron.csv", csv_bytes, "text/csv")}, expect=200)
    resultados = r.json()["resultados"]
    errores = [x for x in resultados if x["depto_status"] == "error" or x["usuario_status"] == "error"]
    if errores:
        raise ApiError(f"[{nombre}] errores en import padrón: {errores[:3]}")
    passwords_iniciales = {x["email"]: x["password_generada"] for x in resultados}
    print(f"[{nombre}] padrón importado: {len(resultados)} deptos+usuarios")

    r = api.req("GET", "/departamentos", token=admin_token, cid=cid, expect=200)
    deptos = r.json()  # [{id, codigo, descripcion}]
    n = len(deptos)

    # --- Coeficientes: partes iguales, con ajuste para sumar exactamente 100 ---
    base = round(100.0 / n, 4)
    coefs = [
        {"departamento_id": d["id"], "clase_prorrateo_id": clase_a, "porcentaje": base}
        for d in deptos
    ]
    coefs[-1]["porcentaje"] = round(100.0 - base * (n - 1), 4)
    api.req("PUT", "/coeficientes", token=admin_token, cid=cid,
            json={"coeficientes": coefs}, expect=200)

    # --- Perfiles de comportamiento ---
    # 70% pagadores puntuales · 15% pagan salteado · 15% morosos que nunca pagan
    deptos_orden = deptos[:]
    RNG.shuffle(deptos_orden)
    corte_punt = int(n * 0.70)
    corte_irr = int(n * 0.85)
    puntuales = deptos_orden[:corte_punt]
    irregulares = deptos_orden[corte_punt:corte_irr]

    # Activar (login + cambio de password) solo los usuarios que van a operar.
    email_de = {
        d["id"]: f"uf{d['codigo'][3:].lower()}@{dominio}" for d in deptos
    }
    operadores = {d["id"] for d in puntuales} | {d["id"] for d in irregulares}
    tokens_depto = {}
    for depto_id in operadores:
        email = email_de[depto_id]
        token = api.login(email, passwords_iniciales[email])
        api.cambiar_password(token, passwords_iniciales[email], seed_password)
        tokens_depto[depto_id] = token
    print(f"[{nombre}] usuarios activados: {len(tokens_depto)} de {n}")

    # --- 6 meses de operación ---
    comprobantes = 0
    for i, periodo in enumerate(MESES):
        # Gastos comunes del mes
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
        # 1-3 gastos particulares a deptos random
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

        # Cierre con vencimientos históricos del mes siguiente
        f1, f2 = _fechas_del_periodo(periodo)
        api.req("POST", f"/periodos/{periodo}/cerrar", token=admin_token, cid=cid, json={
            "fecha_primer_vencimiento": f1.isoformat(),
            "fecha_segundo_vencimiento": f2.isoformat(),
        }, expect=201)

        # Pagos: expensas del período → comprobante del depto → aprobación admin
        r = api.req("GET", f"/expensas?periodo={periodo}", token=admin_token, cid=cid, expect=200)
        expensas_por_depto = {e["departamento_id"]: e for e in r.json()}

        pagan_este_mes = [d["id"] for d in puntuales]
        pagan_este_mes += [d["id"] for d in irregulares if RNG.random() < 0.5]

        for depto_id in pagan_este_mes:
            exp = expensas_por_depto.get(depto_id)
            if exp is None or depto_id not in tokens_depto:
                continue
            fecha_pago = min(f1 - timedelta(days=RNG.randint(0, 5)), date.today())
            monto = exp["monto_primer_vencimiento"]
            # ~5% paga de más (redondea para arriba) → queda saldo a favor.
            if RNG.random() < 0.05:
                monto = float(int(monto / 1000 + 1) * 1000)
            r = api.req("POST", "/comprobantes", token=tokens_depto[depto_id], cid=cid,
                        data={"fecha_pago": fecha_pago.isoformat(),
                              "monto": monto},
                        files={"archivo": ("pago.png", _PNG_1PX, "image/png")},
                        expect=201)
            api.req("PATCH", f"/comprobantes/{r.json()['id']}", token=admin_token, cid=cid,
                    json={"estado": "aprobado"}, expect=200)
            comprobantes += 1
        print(f"[{nombre}] {periodo}: cerrado · {len(pagan_este_mes)} pagos")

    # --- Reservas de amenities (fechas futuras) ---
    reservantes = RNG.sample(sorted(tokens_depto), k=min(25, len(tokens_depto)))
    reservas_hechas = 0
    for j, depto_id in enumerate(reservantes):
        amenity = RNG.choice(list(amenities.values()))
        inicio = datetime.now().replace(minute=0, second=0, microsecond=0) + timedelta(
            days=RNG.randint(2, 40), hours=RNG.randint(1, 5)
        )
        r = api.req("POST", f"/amenities/{amenity}/reservas", token=tokens_depto[depto_id],
                    cid=cid, json={
                        "inicio": inicio.isoformat(),
                        "fin": (inicio + timedelta(hours=RNG.randint(1, 3))).isoformat(),
                    })
        if r.status_code == 201:
            reservas_hechas += 1
            # 20% cancela (prueba la reversa del cargo)
            if RNG.random() < 0.2:
                api.req("DELETE", f"/reservas/{r.json()['id']}",
                        token=tokens_depto[depto_id], cid=cid)
    print(f"[{nombre}] reservas: {reservas_hechas}")

    # --- Peticiones → trabajos → presupuestos ---
    peticionantes = RNG.sample(sorted(tokens_depto), k=min(12, len(tokens_depto)))
    trabajos_creados = 0
    for depto_id in peticionantes:
        r = api.req("POST", "/peticiones", token=tokens_depto[depto_id], cid=cid, json={
            "titulo": RNG.choice([
                "Pérdida de agua en baño", "Humedad en pared del dormitorio",
                "Portero eléctrico sin audio", "Luz de pasillo quemada",
                "Filtración en balcón", "Ascensor hace ruido",
            ]),
            "descripcion": "Solicito revisión y reparación a la brevedad. Gracias.",
        }, expect=201)
        peticion_id = r.json()["id"]

        if RNG.random() < 0.6:  # el resto queda abierta (realista)
            r = api.req("POST", "/trabajos", token=admin_token, cid=cid, json={
                "peticion_id": peticion_id,
                "descripcion": "Trabajo generado a partir del reclamo del depto.",
            }, expect=201)
            trabajo_id = r.json()["id"]
            trabajos_creados += 1

            elegido = None
            for prov in RNG.sample(proveedores, k=RNG.randint(1, 3)):
                # El endpoint de presupuestos recibe multipart/form-data.
                r = api.req("POST", f"/trabajos/{trabajo_id}/presupuestos",
                            token=admin_token, cid=cid,
                            data={"proveedor_id": str(prov),
                                  "monto": str(round(RNG.uniform(20_000, 150_000), 2))},
                            expect=201)
                elegido = r.json()
            if elegido is not None:
                api.req("POST",
                        f"/trabajos/{trabajo_id}/presupuestos/{elegido['id']}/aprobar",
                        token=admin_token, cid=cid, expect=200)
    print(f"[{nombre}] peticiones: {len(peticionantes)} · trabajos: {trabajos_creados}")

    dt = time.monotonic() - t0
    print(f"[{nombre}] listo en {dt:.1f}s")
    return {"cid": cid, "deptos": n, "comprobantes": comprobantes}


_caja_cache: dict[int, int] = {}


def _caja_default(api, admin_token, cid):
    if cid not in _caja_cache:
        r = api.req("GET", "/cajas", token=admin_token, cid=cid, expect=200)
        _caja_cache[cid] = r.json()[0]["id"]
    return _caja_cache[cid]


def main() -> None:
    # Cargar .env local si existe (pydantic-settings carga solo cuando se
    # instancia Settings, pero acá leemos os.environ antes de importar backend).
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    sa_email = os.environ.get("SUPER_ADMIN_EMAIL", "")
    sa_password = os.environ.get("SUPER_ADMIN_PASSWORD", "")
    seed_password = os.environ.get("SEED_E2E_PASSWORD", "")
    if not sa_email or not sa_password or not seed_password:
        print("Faltan SUPER_ADMIN_EMAIL / SUPER_ADMIN_PASSWORD / SEED_E2E_PASSWORD", file=sys.stderr)
        sys.exit(1)
    if len(seed_password) < 8:
        print("SEED_E2E_PASSWORD debe tener al menos 8 caracteres", file=sys.stderr)
        sys.exit(1)

    from fastapi.testclient import TestClient

    from backend.database import SessionLocal
    from backend.main import app
    from backend.seed_super_admin import seed as seed_super_admin

    t0 = time.monotonic()
    with TestClient(app) as client:  # lifespan: crea tablas + migraciones
        with SessionLocal() as db:
            seed_super_admin(db)

        api = Api(client)
        sa_token = api.login(sa_email, sa_password)

        # Administración + su primer usuario admin
        admin_email = "admin@semilla-admin.local"
        r = api.req("POST", "/super-admin/administraciones", token=sa_token, json={
            "razon_social": "Administración Semilla SRL",
            "cuit": "30-70000000-3",
            "email_contacto": "contacto@semilla-admin.local",
            "admin_email": admin_email,
            "admin_password_inicial": seed_password + "-inicial",
        }, expect=201)
        print(f"administración creada id={r.json()['id']}")

        # Primer login del admin + cambio de password obligatorio (flujo real)
        admin_token = api.login(admin_email, seed_password + "-inicial")
        api.cambiar_password(admin_token, seed_password + "-inicial", seed_password)

        seed_consorcio(api, admin_token, "Edificio San Martín 1550",
                       pisos=10, dominio="sanmartin.local", cuit_suffix=11111,
                       seed_password=seed_password)
        seed_consorcio(api, admin_token, "Torre Libertador",
                       pisos=20, dominio="libertador.local", cuit_suffix=22222,
                       seed_password=seed_password)

    dt = time.monotonic() - t0
    print(f"\nSeed E2E completo en {dt/60:.1f} min")
    print(f"Login admin: {admin_email} / $SEED_E2E_PASSWORD")
    print("Logins depto: uf<NN><letra>@sanmartin.local | @libertador.local / $SEED_E2E_PASSWORD")
    print("(solo los usuarios 'operadores' tienen esa password; el resto quedó con la")
    print(" password generada en el import, sin activar — realista)")


if __name__ == "__main__":
    main()
