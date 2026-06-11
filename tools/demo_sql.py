"""Demo: ver el SQL real que SQLAlchemy genera detrás de cada operación.

Uso (desde la raíz del proyecto):
    ./.venv/Scripts/python.exe tools/demo_sql.py

No toca consorcio.db: usa una DB SQLite en memoria que se descarta al terminar.
"""
import sys
from pathlib import Path

# Permitir importar el paquete `backend` cuando se corre desde la raíz.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

# echo=True hace que el motor imprima cada SQL antes de ejecutarlo.
engine = create_engine("sqlite:///:memory:", echo=True, future=True)

from backend.models import Base, Departamento, EstadoPeticion, Peticion

print("\n" + "=" * 70)
print("PASO 1 — CREATE TABLE (lo mismo que hace main.py al arrancar el server)")
print("=" * 70)
Base.metadata.create_all(bind=engine)

Session = sessionmaker(bind=engine, future=True)
db = Session()

print("\n" + "=" * 70)
print("PASO 2 — INSERT (crear un departamento y una petición)")
print("=" * 70)
depto = Departamento(codigo="UF-1A", descripcion="Piso 1, Unidad A")
db.add(depto)
db.commit()

peticion = Peticion(
    departamento_id=depto.id,
    titulo="Luz quemada",
    descripcion="Pasillo 2do piso",
    estado=EstadoPeticion.abierta,
)
db.add(peticion)
db.commit()

print("\n" + "=" * 70)
print("PASO 3 — SELECT (listar peticiones del depto)")
print("=" * 70)
stmt = select(Peticion).where(Peticion.departamento_id == depto.id)
resultados = db.scalars(stmt).all()

print("\n" + "=" * 70)
print("PASO 4 — UPDATE (rechazar la petición)")
print("=" * 70)
peticion.estado = EstadoPeticion.rechazada
db.commit()

print("\n" + "=" * 70)
print("PASO 5 — DELETE (borrar la petición)")
print("=" * 70)
db.delete(peticion)
db.commit()

db.close()
print("\nFin del demo.")
