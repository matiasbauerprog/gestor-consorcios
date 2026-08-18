"""Diagnóstico del correo saliente.

Manda un mensaje de prueba con la configuración que tenga cargada el entorno y
reporta qué usó y qué pasó. Sirve para separar "el correo está mal configurado"
de "el circuito de recuperación tiene un problema", que desde la pantalla se
ven igual.

Uso:
    python -m backend.probar_email destinatario@ejemplo.com
"""
import sys

from .config import get_settings
from .mail_service import enviar_email


def _enmascarar(secreto: str) -> str:
    """Muestra lo justo para reconocer la clave sin revelarla."""
    if not secreto:
        return "(vacía)"
    if len(secreto) <= 6:
        return "***"
    return f"{secreto[:4]}***{secreto[-2:]}"


def _direccion_valida(direccion: str) -> bool:
    """Chequeo mínimo de forma: parte local, arroba y dominio con punto.

    No pretende validar un email de verdad —eso sólo lo hace mandarlo— sino
    atajar el error de tipeo que se ve a simple vista y que el servidor rechaza
    con un mensaje incomprensible: escribir `noreply.dominio.com` con un punto
    donde va la arroba.
    """
    if direccion.count("@") != 1:
        return False
    local, _, dominio = direccion.partition("@")
    return bool(local) and "." in dominio and not dominio.startswith(".")


def _pedir_dominios(clave: str) -> list[dict]:
    """Le pregunta a Resend qué dominios ve **esa clave**.

    Es lo que zanja el caso confuso: el panel muestra el dominio verificado
    pero el envío lo rechaza. Casi siempre la clave pertenece a otra cuenta o
    equipo, o lo verificado es un subdominio y se manda desde el dominio pelado.
    """
    import json
    import urllib.request

    pedido = urllib.request.Request(
        "https://api.resend.com/domains",
        headers={"Authorization": f"Bearer {clave}"},
    )
    with urllib.request.urlopen(pedido, timeout=15) as respuesta:
        return json.loads(respuesta.read()).get("data", [])


def _dominio_de(direccion: str) -> str:
    return direccion.rpartition("@")[2].lower()


def _listar_dominios(s) -> int:
    """Imprime los dominios que ve la clave y compara con el remitente."""
    if "resend" not in s.SMTP_HOST:
        print(
            f"--dominios sólo sabe consultarle a Resend, y SMTP_HOST es "
            f"{s.SMTP_HOST!r}."
        )
        return 2

    import urllib.error

    try:
        dominios = _pedir_dominios(s.SMTP_PASSWORD)
    except urllib.error.HTTPError as e:
        if e.code == 403:
            # Las claves de Resend son "sending only" por defecto: pueden
            # mandar pero no leer la lista de dominios. Es lo esperable y no
            # hay nada que arreglar.
            print(
                "La clave es sólo de envío: puede mandar correo pero no leer la "
                "lista de dominios (403).\n"
                "Es el tipo de clave por defecto en Resend y es la correcta para "
                "esto. Si querés usar este diagnóstico, generá una clave con "
                "permiso de lectura; si no, probá el envío directo:\n"
                "  python -m backend.probar_email tu-email@ejemplo.com"
            )
            return 0
        if e.code == 401:
            print(
                "La clave no es válida (401). Revisá SMTP_PASSWORD en el .env: "
                "tiene que ser la API key de Resend, la que empieza con re_."
            )
            return 1
        print(f"Resend respondió {e.code}: {e.reason}")
        return 1
    except Exception as e:  # noqa: BLE001 — se reporta tal cual, es diagnóstico
        print(f"No se pudo consultar la API de Resend: {e}")
        return 1

    if not dominios:
        print(
            "Esa clave no ve ningún dominio.\n"
            "Lo más probable: la clave pertenece a otra cuenta o a otro equipo "
            "de Resend, distinto de aquel donde verificaste el dominio.\n"
            "Generá una clave nueva desde el mismo equipo que aparece arriba de "
            "la lista de dominios en el panel."
        )
        return 1

    print("Dominios que ve esta clave:")
    for d in dominios:
        print(f"  {d.get('name')}  [{d.get('status')}]")
    print()

    esperado = _dominio_de(s.SMTP_FROM_EMAIL)
    verificados = {
        d.get("name", "").lower()
        for d in dominios
        if d.get("status") == "verified"
    }

    if esperado in verificados:
        print(f"El remitente corresponde: {esperado} está verificado.")
        return 0

    print(
        f"El remitente NO coincide con ningún dominio verificado.\n"
        f"  mandás desde : {esperado}\n"
        f"  verificados  : {', '.join(sorted(verificados)) or '(ninguno)'}\n\n"
        "Resend trata el dominio pelado y cada subdominio como cosas distintas: "
        "verificar notificaciones.midominio.com no habilita midominio.com.\n"
        "O cambiás SMTP_FROM_EMAIL para que use un dominio de la lista, o "
        "verificás en Resend el que querés usar."
    )
    return 1


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if not argv:
        print("Uso: python -m backend.probar_email destinatario@ejemplo.com")
        print("     python -m backend.probar_email --dominios")
        return 2

    s = get_settings()

    if argv[0] == "--dominios":
        return _listar_dominios(s)

    destino = argv[0]

    print("Configuración de correo:")
    print(f"  servidor   : {s.SMTP_HOST or '(vacío)'}:{s.SMTP_PORT}")
    print(f"  usuario    : {s.SMTP_USER or '(vacío)'}")
    print(f"  clave      : {_enmascarar(s.SMTP_PASSWORD)}")
    print(f"  remitente  : {s.SMTP_FROM_NAME} <{s.SMTP_FROM_EMAIL}>")
    print(f"  destinatario: {destino}")
    print()

    if s.DEMO_MODE:
        print(
            "DEMO_MODE está prendido: mail_service fuerza modo consola y no "
            "manda nada real. Apagalo para probar el envío."
        )
        return 1

    if not s.SMTP_HOST:
        print(
            "SMTP_HOST está vacío: el sistema está en MODO CONSOLA. Los mensajes "
            "se imprimen acá y no salen a ningún lado.\n"
            "Cargá SMTP_HOST, SMTP_PORT, SMTP_USER y SMTP_PASSWORD en el .env."
        )
        return 1

    if not _direccion_valida(s.SMTP_FROM_EMAIL):
        print(
            f"El remitente no es una dirección válida: {s.SMTP_FROM_EMAIL!r}\n"
            "Le falta la arroba, o el dominio está mal. Tiene que ser de la "
            "forma nombre@dominio.com — un error típico es escribir un punto "
            "donde va la arroba.\n"
            "Corregí SMTP_FROM_EMAIL en el .env."
        )
        return 1

    if not _direccion_valida(destino):
        print(
            f"El destinatario no es una dirección válida: {destino!r}\n"
            "Tiene que ser de la forma nombre@dominio.com"
        )
        return 1

    ok = enviar_email(
        to=destino,
        subject="Prueba de configuración",
        body=(
            "Si estás leyendo esto, el correo saliente del sistema de "
            "consorcios está bien configurado.\n\n"
            f"Salió de {s.SMTP_FROM_EMAIL} vía {s.SMTP_HOST}."
        ),
    )

    if ok:
        print("Enviado. Revisá la bandeja del destinatario (y el correo no deseado).")
        return 0

    print(
        "No se pudo enviar. El error concreto está en la línea [EMAIL ERROR] de "
        "arriba.\n"
        "Lo más común: la clave no corresponde al usuario, o el remitente usa un "
        "dominio que el proveedor todavía no verificó."
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
