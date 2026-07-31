"""Responde si el reset del demo (DROP SCHEMA public CASCADE) va a funcionar.

El reset por cron necesita que el rol de conexión sea dueño del esquema `public`.
En Postgres 15+ el dueño de la base lo es; en 14 o anterior el dueño es el
superusuario `postgres` y el DROP falla con "must be owner of schema public"
—en silencio, cada 6 horas, salvo que alguien mire los logs del cron.

Uso:
    python tools/check_demo_db.py "postgresql://usuario:pass@host/base"

La URL es la "External Database URL" del panel de Render.
"""
import sys


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 2

    try:
        import psycopg2
    except ImportError:
        print("Falta psycopg2. Instalalo con: pip install psycopg2-binary")
        return 2

    try:
        conn = psycopg2.connect(sys.argv[1])
    except Exception as e:
        print(f"No se pudo conectar: {e}")
        return 2

    with conn, conn.cursor() as cur:
        cur.execute("SHOW server_version")
        version = cur.fetchone()[0]
        cur.execute(
            "SELECT pg_get_userbyid(nspowner), current_user "
            "FROM pg_namespace WHERE nspname = 'public'"
        )
        dueno, usuario = cur.fetchone()
        # has_schema_privilege no cubre ownership; la pregunta real es si
        # current_user es el dueño o miembro del rol dueño.
        cur.execute("SELECT pg_has_role(current_user, %s, 'USAGE')", (dueno,))
        puede = cur.fetchone()[0]

    print(f"Postgres:        {version}")
    print(f"Usuario:         {usuario}")
    print(f"Dueño de public: {dueno}")
    print()

    if puede:
        print("OK — el reset por cron va a funcionar tal como está.")
        return 0

    print("PROBLEMA — este usuario NO puede hacer DROP SCHEMA public CASCADE.")
    print("El cron del demo va a fallar cada 6 h en silencio.")
    print()
    print("Solución: cambiar la rama Postgres de _resetear_esquema()")
    print("en backend/seed_demo.py por la variante portable (dropear tabla")
    print("por tabla vía el metadata), documentada en el comentario de esa")
    print("misma función.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
