"""Mint a JWT for a known Usuario.id — dev/testing only.

Usage:
    python tools/mint_token.py <user_id>

Requires:
    - SECRET_KEY env var (or .env entry) configured.
    - DB previously seeded so that the user exists.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.auth import create_access_token  # noqa: E402
from backend.database import SessionLocal  # noqa: E402
from backend.models import Usuario  # noqa: E402


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: python tools/mint_token.py <user_id>", file=sys.stderr)
        return 2

    try:
        user_id = int(sys.argv[1])
    except ValueError:
        print("user_id debe ser un entero.", file=sys.stderr)
        return 2

    with SessionLocal() as db:
        user = db.get(Usuario, user_id)
        if user is None:
            print(f"Usuario id={user_id} no existe.", file=sys.stderr)
            return 1
        token = create_access_token(
            user_id=user.id,
            rol=user.rol,
            departamento_id=user.departamento_id,
        )

    print(token)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
