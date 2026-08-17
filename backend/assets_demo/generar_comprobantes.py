"""Genera los tres PNG de "comprobante de transferencia" que rota
`imagen_comprobante` (backend/seed_demo.py) al adjuntar comprobantes en el
dataset demo.

Script de UNA sola corrida, fuera del runtime de producción: no lo importa
ningún módulo del backend ni ningún test. `backend/seed_demo.py` sólo LEE
los tres PNG ya generados (`backend/assets_demo/comprobante_*.png`); nunca
importa Pillow. Por eso Pillow no está en requirements.txt — hace falta
únicamente para correr este script a mano, cuando alguien necesite
regenerar o ajustar las imágenes.

Uso:
    python -m backend.assets_demo.generar_comprobantes

Genera capturas sintéticas (dibujadas por código, sin descargar nada de
Internet ni usar capturas de un banco real —son marca registrada—) con
datos inventados: fondo claro, un título "Comprobante de transferencia", un
ícono de tilde genérico, y cuatro filas de datos (Importe, CBU destino
parcialmente enmascarado, Fecha, Nro. de operación). No lleva nombre de
titular, CUIT/CUIL, ni número de cuenta completo en ningún lado.
"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ANCHO, ALTO = 600, 800

# Importes del orden de magnitud real del dataset demo (~$545.810-$635.416
# medido sobre demo.db): no calzan al centavo con ningún pago puntual, pero
# pasan el chequeo de "¿el monto es del orden correcto?" que hace un
# administrador al abrir la captura — mucho más creíble que un importe sin
# relación con lo que se factura en el resto del dataset.
VARIANTES = [
    {"importe": "$ 567.930,00", "cbu": "0000003100 0012******1234",
     "fecha": "15/03/2026", "estado": "Acreditada", "operacion": "OP-889214"},
    {"importe": "$ 598.245,50", "cbu": "0000007200 0034******5678",
     "fecha": "02/04/2026", "estado": "Acreditada", "operacion": "OP-114087"},
    {"importe": "$ 612.180,00", "cbu": "0000001800 0056******9012",
     "fecha": "28/04/2026", "estado": "Acreditada", "operacion": "OP-552903"},
]

COLOR_FONDO = (247, 248, 250)
COLOR_TARJETA = (255, 255, 255)
COLOR_BORDE = (210, 214, 220)
COLOR_TEXTO = (60, 66, 74)
COLOR_LABEL = (140, 146, 156)
COLOR_ACENTO = (40, 130, 90)

# TrueType con acentos, no la bitmap ImageFont.load_default() (no tiene
# glifos para vocales acentuadas: "ó" sale como un cuadrado vacío). Prueba
# varias candidatas y falla ruidosamente si ninguna existe, en vez de volver
# a caer en texto sin tildes en silencio.
_CANDIDATOS_FUENTE = [
    r"C:\Windows\Fonts\arial.ttf",
    r"C:\Windows\Fonts\segoeui.ttf",
    r"C:\Windows\Fonts\calibri.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
]


def _ruta_fuente() -> str:
    for candidato in _CANDIDATOS_FUENTE:
        if Path(candidato).exists():
            return candidato
    raise RuntimeError(
        f"Ninguna fuente TrueType con acentos disponible ({_CANDIDATOS_FUENTE})"
    )


def _fuente(tamano: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(_ruta_fuente(), tamano)


def generar(variante: dict) -> Image.Image:
    img = Image.new("RGB", (ANCHO, ALTO), COLOR_FONDO)
    draw = ImageDraw.Draw(img)
    margen = 40
    draw.rounded_rectangle([margen, margen, ANCHO - margen, ALTO - margen],
                            radius=18, fill=COLOR_TARJETA, outline=COLOR_BORDE, width=2)
    draw.rounded_rectangle([margen, margen, ANCHO - margen, margen + 90],
                            radius=18, fill=COLOR_ACENTO)
    draw.rectangle([margen, margen + 60, ANCHO - margen, margen + 90], fill=COLOR_ACENTO)

    f_titulo, f_label, f_valor = _fuente(26), _fuente(16), _fuente(22)
    draw.text((margen + 24, margen + 30), "Comprobante de transferencia",
              font=f_titulo, fill=(255, 255, 255))

    cx, cy, r = ANCHO // 2, margen + 150, 46
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(232, 245, 238),
                 outline=COLOR_ACENTO, width=3)
    draw.line([(cx - 20, cy + 2), (cx - 6, cy + 18), (cx + 22, cy - 18)],
              fill=COLOR_ACENTO, width=6, joint="curve")
    draw.text((ANCHO // 2, cy + r + 20), variante["estado"], font=f_valor,
               fill=COLOR_ACENTO, anchor="mm")

    y = cy + r + 70
    filas = [("Importe", variante["importe"]), ("CBU destino", variante["cbu"]),
             ("Fecha", variante["fecha"]), ("Nro. de operación", variante["operacion"])]
    for label, valor in filas:
        draw.line([(margen + 24, y), (ANCHO - margen - 24, y)], fill=COLOR_BORDE, width=1)
        y += 18
        draw.text((margen + 24, y), label, font=f_label, fill=COLOR_LABEL)
        y += 22
        draw.text((margen + 24, y), valor, font=f_valor, fill=COLOR_TEXTO)
        y += 46

    draw.line([(margen + 24, y), (ANCHO - margen - 24, y)], fill=COLOR_BORDE, width=1)
    y += 30
    draw.text((margen + 24, y), "Comprobante generado para fines de demostración.",
              font=f_label, fill=COLOR_LABEL)
    return img


def main() -> None:
    destino = Path(__file__).parent
    for i, variante in enumerate(VARIANTES, start=1):
        archivo = destino / f"comprobante_{i}.png"
        generar(variante).save(archivo, format="PNG")
        print(f"[assets_demo] {archivo} ({archivo.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
