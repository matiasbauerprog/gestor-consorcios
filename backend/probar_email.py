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


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if not argv:
        print("Uso: python -m backend.probar_email destinatario@ejemplo.com")
        return 2

    destino = argv[0]
    s = get_settings()

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
