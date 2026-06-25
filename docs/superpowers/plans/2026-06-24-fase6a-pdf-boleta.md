# Fase 6a — PDF boleta + envío masivo Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Generar PDF de boleta de expensas (HTML+CSS → PDF con WeasyPrint, on-demand) y permitir envío masivo por email a todos los deptos del período (síncrono con resumen).

**Architecture:**
- 2 endpoints nuevos: `GET /expensas/{id}/pdf` (autorizado por rol+ownership) y `POST /periodos/{periodo}/enviar-pdfs` (admin con soft-warning si período no cerrado).
- 2 módulos puros: `backend/pdf.py` (Jinja2 + WeasyPrint), `backend/email.py` (smtplib + modo console).
- 1 template HTML + 1 CSS en `backend/templates/`.
- Frontend: cliente `pdf.js` con blob URL, filtro+banner en `/expensas`, botón en `/periodos`, modal de envío con warning si no cerrado.

**Tech Stack:** Python (WeasyPrint, Jinja2, smtplib), FastAPI, React 18, blob URLs vía `URL.createObjectURL`.

**Reference:** El diseño detallado vive en `docs/superpowers/specs/2026-06-24-fase6a-pdf-boleta-design.md`.

---

## Task 0: Setup branch + dependencias

**Files:** ninguno (operaciones de git/instalación).

- [ ] **Step 1: Crear branch desde master**

```bash
git checkout master
git checkout -b feature/expensas-fase6a-pdf
```

- [ ] **Step 2: Verificar baseline de la suite**

```bash
.venv/Scripts/python.exe -m pytest tests/ --tb=no -q
```

Expected: `525 passed` (baseline post-Fase 5).

- [ ] **Step 3: Instalar ReportLab en el venv**

```bash
.venv/Scripts/python.exe -m pip install reportlab
```

ReportLab es Python puro — sin deps de SO en Windows/Linux/Mac.

- [ ] **Step 4: Smoke import**

```bash
.venv/Scripts/python.exe -c "from reportlab.pdfgen import canvas; from reportlab.lib.pagesizes import A4; print('OK')"
```

Expected: `OK`.

- [ ] **Step 5: Sumar dependencia a requirements.txt**

Agregar al final de `requirements.txt`:
```
reportlab>=4.0
```

- [ ] **Step 6: Commit**

```bash
git add requirements.txt
git commit -m "chore(deps): reportlab para Fase 6a (PDF generator)"
```

---

## Task 1: Módulo `backend/email.py` + tests

**Files:**
- Create: `backend/email.py`
- Create: `tests/test_email.py`

- [ ] **Step 1: Crear `tests/test_email.py` (TDD primero)**

```python
"""Tests del módulo de envío de email."""
from unittest.mock import patch, MagicMock

import pytest

from backend.email import enviar_email


def test_modo_console_devuelve_true_y_loggea(capsys):
    """Si SMTP_HOST está vacío, modo console: loggea y devuelve True."""
    with patch("backend.email.get_settings") as mock_settings:
        mock_settings.return_value.SMTP_HOST = ""
        mock_settings.return_value.SMTP_FROM_EMAIL = "from@local"
        mock_settings.return_value.SMTP_FROM_NAME = "Test"
        ok = enviar_email(
            to="depto@example.com",
            subject="Test asunto",
            body="Cuerpo del email",
            attachments=[],
        )
    captured = capsys.readouterr()
    assert ok is True
    assert "depto@example.com" in captured.out
    assert "Test asunto" in captured.out


def test_modo_smtp_llama_send_message():
    """Con SMTP_HOST seteado, llama a smtplib.SMTP.send_message."""
    with patch("backend.email.get_settings") as mock_settings, \
         patch("backend.email.smtplib.SMTP") as mock_smtp_cls:
        mock_settings.return_value.SMTP_HOST = "smtp.test.local"
        mock_settings.return_value.SMTP_PORT = 587
        mock_settings.return_value.SMTP_USER = "user"
        mock_settings.return_value.SMTP_PASSWORD = "pass"
        mock_settings.return_value.SMTP_FROM_EMAIL = "from@local"
        mock_settings.return_value.SMTP_FROM_NAME = "Test"

        mock_smtp_instance = MagicMock()
        mock_smtp_cls.return_value.__enter__.return_value = mock_smtp_instance

        ok = enviar_email(
            to="depto@example.com",
            subject="Test",
            body="Body",
            attachments=[],
        )

    assert ok is True
    mock_smtp_instance.send_message.assert_called_once()


def test_attachment_construye_multipart():
    """Con attachments, el mensaje incluye el PDF como parte."""
    with patch("backend.email.get_settings") as mock_settings:
        mock_settings.return_value.SMTP_HOST = ""  # console mode
        mock_settings.return_value.SMTP_FROM_EMAIL = "from@local"
        mock_settings.return_value.SMTP_FROM_NAME = "Test"

        ok = enviar_email(
            to="depto@example.com",
            subject="Boleta",
            body="Adjunto",
            attachments=[("boleta.pdf", b"%PDF-fake-bytes", "application/pdf")],
        )
    # En modo console, el assert es que no rompió con attachment
    assert ok is True
```

- [ ] **Step 2: Run tests para verificar que fallan (módulo no existe)**

```bash
.venv/Scripts/python.exe -m pytest tests/test_email.py -v
```

Expected: FAIL con `ImportError: cannot import name 'enviar_email' from 'backend.email'`.

- [ ] **Step 3: Crear `backend/email.py`**

```python
"""Envío de email con modo console fallback para dev/test.

Si SMTP_HOST está vacío en config, los emails se loggean al stdout
en lugar de mandarse — útil para desarrollo y CI sin SMTP real.
"""
import smtplib
from email.message import EmailMessage

from .config import get_settings


def enviar_email(
    to: str,
    subject: str,
    body: str,
    attachments: list[tuple[str, bytes, str]] | None = None,
) -> bool:
    """Envía un email. Modo console si SMTP_HOST vacío.

    Args:
        to: destinatario (string single email).
        subject: asunto.
        body: cuerpo (texto plano).
        attachments: lista de tuplas (filename, content_bytes, mime_type).

    Returns:
        True si OK (incluido modo console), False si falló el envío.
    """
    attachments = attachments or []
    settings = get_settings()

    if not settings.SMTP_HOST:
        # Modo console: loggear y devolver True
        print(f"[EMAIL CONSOLE MODE] To: {to} | Subject: {subject}")
        print(f"[EMAIL CONSOLE MODE] Body:\n{body}")
        for fname, content, mime in attachments:
            print(f"[EMAIL CONSOLE MODE] Attachment: {fname} ({len(content)} bytes, {mime})")
        return True

    msg = EmailMessage()
    msg["From"] = f"{settings.SMTP_FROM_NAME} <{settings.SMTP_FROM_EMAIL}>"
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)

    for fname, content, mime in attachments:
        maintype, subtype = mime.split("/", 1)
        msg.add_attachment(content, maintype=maintype, subtype=subtype, filename=fname)

    try:
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as smtp:
            smtp.starttls()
            if settings.SMTP_USER:
                smtp.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            smtp.send_message(msg)
        return True
    except Exception as e:
        print(f"[EMAIL ERROR] To: {to} | Error: {e}")
        return False
```

- [ ] **Step 4: Sumar variables SMTP en `backend/config.py`**

Leer `backend/config.py` y agregar a la clase `Settings`:

```python
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM_EMAIL: str = "consorcio@local"
    SMTP_FROM_NAME: str = "Consorcio"
```

(Defaults vacíos para que arranque sin SMTP real — modo console.)

- [ ] **Step 5: Run tests**

```bash
.venv/Scripts/python.exe -m pytest tests/test_email.py -v
```

Expected: 3 passed.

- [ ] **Step 6: Commit**

```bash
git add backend/email.py backend/config.py tests/test_email.py
git commit -m "feat(email): módulo enviar_email con modo console + SMTP + tests"
```

---

## Task 2: Módulo `backend/pdf.py` con ReportLab + tests

**Files:**
- Create: `backend/pdf.py`
- Create: `tests/test_pdf_boleta.py`

**Nota**: el plan original usaba WeasyPrint con templates HTML/CSS. Cambiamos a ReportLab (Python puro, sin GTK runtime en Windows) — decidido tras BLOCKED en Task 0. El PDF se arma programáticamente con primitivas `Paragraph`, `Table`, `Spacer`. Sin archivos HTML/CSS.

- [ ] **Step 1: Crear `backend/pdf.py` con ReportLab**

```python
"""Generación del PDF de boleta de liquidación (Fase 6a).

Función pura: lee de la DB lo necesario, arma el PDF con ReportLab.
No persiste nada. ReportLab es Python puro — sin deps del SO.
"""
from collections import defaultdict
from datetime import date
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import (
    ConfiguracionConsorcio,
    Departamento,
    Expensa,
    ExpensaDetalle,
    MovimientoCuenta,
    TipoMovimiento,
)

_RUBRO_LABELS = {
    "sueldos_y_cargas_sociales": "Sueldos y cargas sociales",
    "servicios_publicos": "Servicios públicos",
    "abonos_y_servicios": "Abonos y servicios",
    "mantenimiento_partes_comunes": "Mantenimiento partes comunes",
    "trabajos_reparaciones_unidades": "Trabajos / reparaciones en unidades",
    "gastos_bancarios": "Gastos bancarios",
    "gastos_administracion": "Gastos administración",
    "seguros": "Seguros",
    "gastos_generales": "Gastos generales",
}


def _money(n: float) -> str:
    return f"${n:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _rubro_label(rubro_value: str) -> str:
    return _RUBRO_LABELS.get(rubro_value, rubro_value)


def generar_pdf_boleta(expensa: Expensa, db: Session) -> bytes:
    """Genera el PDF de la boleta. Devuelve bytes."""
    config = db.get(ConfiguracionConsorcio, 1)
    departamento = db.get(Departamento, expensa.departamento_id)

    pagos = list(db.scalars(
        select(MovimientoCuenta).where(
            MovimientoCuenta.departamento_id == expensa.departamento_id,
            MovimientoCuenta.tipo == TipoMovimiento.pago_recibido,
        ).order_by(MovimientoCuenta.fecha)
    ).all())

    intereses = list(db.scalars(
        select(MovimientoCuenta).where(
            MovimientoCuenta.departamento_id == expensa.departamento_id,
            MovimientoCuenta.tipo == TipoMovimiento.interes_punitorio,
        )
    ).all())

    detalles = list(db.scalars(
        select(ExpensaDetalle).where(ExpensaDetalle.expensa_id == expensa.id)
    ).all())

    gastos_por_rubro: dict[str, list[ExpensaDetalle]] = defaultdict(list)
    for d in detalles:
        gastos_por_rubro[d.rubro.value].append(d)

    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=1.5 * cm, rightMargin=1.5 * cm,
        topMargin=1.5 * cm, bottomMargin=1.5 * cm,
        title=f"Boleta {expensa.periodo} - Depto {departamento.codigo}",
    )

    styles = getSampleStyleSheet()
    h1 = styles["Heading1"]
    h2 = styles["Heading2"]
    h3 = styles["Heading3"]
    normal = styles["Normal"]
    small = ParagraphStyle("small", parent=normal, fontSize=8, textColor=colors.grey)

    story = []

    # Header
    story.append(Paragraph(config.consorcio_nombre, h1))
    story.append(Paragraph(
        f"{config.consorcio_domicilio} · CUIT {config.consorcio_cuit}", normal
    ))
    story.append(Paragraph(
        f"Admin: {config.admin_nombre} (RPA {config.admin_rpa}) · "
        f"{config.admin_email} · {config.admin_telefono}", small
    ))
    story.append(Spacer(1, 0.3 * cm))
    story.append(Paragraph(
        f"<b>Boleta Nº</b> {expensa.id} · "
        f"<b>Período</b> {expensa.periodo} · "
        f"<b>Emitida</b> {date.today().isoformat()}", normal
    ))
    story.append(Spacer(1, 0.5 * cm))

    # Depto
    story.append(Paragraph(f"Departamento {departamento.codigo}", h2))
    story.append(Spacer(1, 0.3 * cm))

    # Liquidación
    story.append(Paragraph("Su liquidación", h3))
    liq_data = [["Concepto", "Importe"]]
    liq_data.append(["Saldo anterior", _money(expensa.saldo_anterior)])
    for mov in pagos:
        liq_data.append([f"{mov.fecha} · {mov.descripcion}", f"({_money(mov.monto)})"])
    for mov in intereses:
        liq_data.append([f"Intereses · {mov.descripcion}", _money(mov.monto)])
    liq_tbl = Table(liq_data, colWidths=[12 * cm, 4 * cm])
    liq_tbl.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(liq_tbl)
    story.append(Spacer(1, 0.4 * cm))

    # Gastos por rubro
    story.append(Paragraph("Gastos del período (su prorrateo)", h3))
    for rubro, items in gastos_por_rubro.items():
        sub_total = sum(it.monto for it in items)
        story.append(Paragraph(
            f"<b>{_rubro_label(rubro)}</b> — {_money(sub_total)}", normal
        ))
        gas_data = [[it.concepto, _money(it.monto)] for it in items]
        gas_tbl = Table(gas_data, colWidths=[12 * cm, 4 * cm])
        gas_tbl.setStyle(TableStyle([
            ("ALIGN", (1, 0), (1, -1), "RIGHT"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("LEFTPADDING", (0, 0), (0, -1), 16),
            ("TEXTCOLOR", (0, 0), (-1, -1), colors.grey),
        ]))
        story.append(gas_tbl)
    story.append(Spacer(1, 0.4 * cm))

    # Totales
    story.append(Paragraph("Total a pagar", h3))
    tot_data = [
        [f"1° vencimiento {expensa.fecha_primer_vencimiento}",
         _money(expensa.monto_primer_vencimiento)],
        [f"2° vencimiento {expensa.fecha_segundo_vencimiento} (+recargo)",
         _money(expensa.monto_segundo_vencimiento)],
    ]
    tot_tbl = Table(tot_data, colWidths=[12 * cm, 4 * cm])
    tot_tbl.setStyle(TableStyle([
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("FONTNAME", (1, 0), (1, 0), "Helvetica-Bold"),
        ("LINEABOVE", (0, 0), (-1, 0), 0.5, colors.grey),
        ("LINEABOVE", (0, 1), (-1, 1), 0.5, colors.grey),
    ]))
    story.append(tot_tbl)
    story.append(Spacer(1, 0.6 * cm))

    # Datos para pagar
    story.append(Paragraph("Para pagar", h3))
    story.append(Paragraph(
        f"{config.banco_nombre} · CBU {config.banco_cbu}", normal
    ))
    if config.banco_alias:
        story.append(Paragraph(f"Alias: {config.banco_alias}", normal))
    story.append(Paragraph(f"Titular: {config.banco_titular}", normal))

    doc.build(story)
    return buf.getvalue()
```

- [ ] **Step 2: Crear `tests/test_pdf_boleta.py`**

```python
"""Tests de generación de PDF de boleta."""
from backend.pdf import generar_pdf_boleta


def test_genera_pdf_devuelve_bytes_con_magic_header(db, client, headers_admin):
    """Smoke: para una expensa sembrada, generar PDF devuelve bytes válidos."""
    from backend.models import Expensa
    expensa = db.query(Expensa).first()
    assert expensa is not None, "El seed debe tener al menos una expensa"
    pdf = generar_pdf_boleta(expensa, db)
    assert isinstance(pdf, bytes)
    assert len(pdf) > 1000, "PDF debería pesar al menos 1KB"
    assert pdf.startswith(b"%PDF-"), "Debería empezar con magic header de PDF"


def test_genera_pdf_con_saldo_anterior(db):
    """Si la expensa tiene saldo_anterior > 0, igual genera sin error."""
    from backend.models import Expensa
    expensa = db.query(Expensa).first()
    expensa.saldo_anterior = 2500.0
    db.flush()
    pdf = generar_pdf_boleta(expensa, db)
    assert pdf.startswith(b"%PDF-")


def test_genera_pdf_con_detalle_multi_rubro(db):
    """Expensa con ExpensaDetalle en varios rubros se renderiza correctamente."""
    from backend.models import Expensa, ExpensaDetalle, Rubro
    expensa = db.query(Expensa).first()
    db.add_all([
        ExpensaDetalle(
            expensa_id=expensa.id, rubro=Rubro.servicios_publicos,
            clase_prorrateo_id=None, departamento_origen_id=None,
            concepto="Luz", monto=5000,
        ),
        ExpensaDetalle(
            expensa_id=expensa.id, rubro=Rubro.seguros,
            clase_prorrateo_id=None, departamento_origen_id=None,
            concepto="Seguro hogar", monto=3000,
        ),
    ])
    db.flush()
    pdf = generar_pdf_boleta(expensa, db)
    assert pdf.startswith(b"%PDF-")
    assert len(pdf) > 1000
```

- [ ] **Step 3: Run tests**

```bash
.venv/Scripts/python.exe -m pytest tests/test_pdf_boleta.py -v
```

Expected: 3 passed.

- [ ] **Step 4: Commit**

```bash
git add backend/pdf.py tests/test_pdf_boleta.py
git commit -m "feat(pdf): generador de boleta con ReportLab + tests"
```

---

## Task 3: Endpoint `GET /expensas/{expensa_id}/pdf` + tests

**Files:**
- Modify: `backend/routers/expensas.py`
- Create: `tests/test_expensa_pdf_endpoint.py`

- [ ] **Step 1: Sumar import al inicio de `backend/routers/expensas.py`**

```python
from fastapi.responses import Response

from ..pdf import generar_pdf_boleta
```

- [ ] **Step 2: Sumar el endpoint al final del router (antes del último `}`)**

```python
@router.get(
    "/{expensa_id}/pdf",
    summary="Generar PDF de la boleta de expensa",
    responses={
        200: {"content": {"application/pdf": {}}, "description": "PDF de la boleta"},
        403: {"description": "Depto no autorizado a ver expensa ajena"},
        404: {"description": "Expensa no encontrada"},
    },
)
def descargar_pdf_expensa(
    expensa_id: int,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> Response:
    expensa = db.get(Expensa, expensa_id)
    if expensa is None:
        raise HTTPException(404, "Expensa no encontrada.")

    # Autorización: depto solo ve las propias; admin/representante cualquiera
    if user.rol == Rol.departamento:
        if user.departamento_id != expensa.departamento_id:
            raise HTTPException(403, "No autorizado para ver esta expensa.")

    pdf_bytes = generar_pdf_boleta(expensa, db)
    filename = f"expensa-{expensa.periodo}-depto-{expensa.departamento_id}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'inline; filename="{filename}"',
        },
    )
```

**Importante:** verificar que el router ya importa `get_current_user` y `Rol`. Si no, agregarlos.

- [ ] **Step 3: Crear `tests/test_expensa_pdf_endpoint.py`**

```python
"""Tests del endpoint GET /expensas/{id}/pdf."""


def test_admin_descarga_pdf_de_cualquier_expensa(client, headers_admin, db):
    from backend.models import Expensa
    expensa = db.query(Expensa).first()
    r = client.get(f"/expensas/{expensa.id}/pdf", headers=headers_admin)
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert r.content.startswith(b"%PDF-")


def test_depto_descarga_su_propia_expensa(client, headers_depto_a, db):
    from backend.models import Expensa
    # Asumiendo que depto-a tiene id=2 (revisar conftest si difiere)
    expensa = db.query(Expensa).filter_by(departamento_id=1).first()
    if expensa is None:
        # Si depto-a tiene otro id en seed, ajustar
        expensa = db.query(Expensa).first()
    r = client.get(f"/expensas/{expensa.id}/pdf", headers=headers_depto_a)
    # Debe ser 200 si la expensa es del depto del usuario, 403 si no
    assert r.status_code in (200, 403)


def test_depto_no_puede_descargar_expensa_ajena(client, headers_depto_a, db):
    """Depto-a no debe ver expensa de depto-b."""
    from backend.models import Expensa
    # Tomar una expensa que NO sea del departamento_id de depto-a (asumimos id=1)
    expensa = db.query(Expensa).filter(Expensa.departamento_id != 1).first()
    if expensa is None:
        # Si no hay, saltar
        return
    r = client.get(f"/expensas/{expensa.id}/pdf", headers=headers_depto_a)
    assert r.status_code == 403


def test_sin_token_devuelve_401(client, db):
    from backend.models import Expensa
    expensa = db.query(Expensa).first()
    r = client.get(f"/expensas/{expensa.id}/pdf")
    assert r.status_code == 401


def test_expensa_inexistente_devuelve_404(client, headers_admin):
    r = client.get("/expensas/99999/pdf", headers=headers_admin)
    assert r.status_code == 404


def test_content_disposition_inline(client, headers_admin, db):
    from backend.models import Expensa
    expensa = db.query(Expensa).first()
    r = client.get(f"/expensas/{expensa.id}/pdf", headers=headers_admin)
    assert "inline" in r.headers.get("content-disposition", "")
    assert ".pdf" in r.headers.get("content-disposition", "")
```

- [ ] **Step 4: Run tests**

```bash
.venv/Scripts/python.exe -m pytest tests/test_expensa_pdf_endpoint.py -v
```

Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/routers/expensas.py tests/test_expensa_pdf_endpoint.py
git commit -m "feat(expensas): endpoint GET /expensas/{id}/pdf con auth por ownership + tests"
```

---

## Task 4: Endpoint `POST /periodos/{periodo}/enviar-pdfs` + tests

**Files:**
- Modify: `backend/routers/periodos.py`
- Modify: `backend/schemas.py`
- Create: `tests/test_envio_pdfs.py`

- [ ] **Step 1: Sumar schema `EnviarPdfsIn` y `EnviarPdfsOut` en `backend/schemas.py`**

```python
# === Fase 6a — envío masivo PDFs ===

class EnviarPdfsIn(BaseModel):
    confirmar_sin_cerrar: bool = False


class ErrorEnvioOut(BaseModel):
    depto_id: int
    email: str | None
    motivo: str


class EnviarPdfsOut(BaseModel):
    enviados: int
    fallaron: int
    errores: list[ErrorEnvioOut]
```

- [ ] **Step 2: Sumar imports al inicio de `backend/routers/periodos.py`**

```python
from sqlalchemy.orm import selectinload

from ..email import enviar_email
from ..models import Departamento, Expensa, PeriodoCerrado, Usuario
from ..pdf import generar_pdf_boleta
from ..schemas import EnviarPdfsIn, EnviarPdfsOut, ErrorEnvioOut
```

- [ ] **Step 3: Sumar el endpoint al final del router**

```python
@router.post(
    "/{periodo}/enviar-pdfs",
    response_model=EnviarPdfsOut,
    status_code=200,
    summary="Enviar boletas PDF por email a los deptos del período",
)
def enviar_pdfs_periodo(
    periodo: str,
    payload: EnviarPdfsIn,
    db: Session = Depends(get_db),
    _u: CurrentUser = Depends(require_roles(Rol.administracion)),
) -> EnviarPdfsOut:
    # 1. Buscar expensas del período
    expensas = list(db.scalars(
        select(Expensa).where(Expensa.periodo == periodo)
    ).all())
    if not expensas:
        raise HTTPException(404, f"No hay expensas para el período {periodo}.")

    # 2. Si NO está cerrado y NO confirmó, 409
    cerrado = db.get(PeriodoCerrado, periodo) is not None
    if not cerrado and not payload.confirmar_sin_cerrar:
        raise HTTPException(
            status_code=409,
            detail=f"El período {periodo} no está cerrado. Para enviar igual, reenviá con confirmar_sin_cerrar=true.",
        )

    # 3. Iterar expensas y enviar
    enviados = 0
    errores: list[ErrorEnvioOut] = []
    for exp in expensas:
        # Resolver emails del depto: usuarios con rol=departamento de ese depto
        usuarios = list(db.scalars(
            select(Usuario).where(
                Usuario.departamento_id == exp.departamento_id,
                Usuario.rol == Rol.departamento,
            )
        ).all())
        emails = [u.email for u in usuarios if u.email]
        if not emails:
            errores.append(ErrorEnvioOut(
                depto_id=exp.departamento_id,
                email=None,
                motivo="Sin destinatarios (depto sin usuarios)",
            ))
            continue

        try:
            pdf = generar_pdf_boleta(exp, db)
        except Exception as e:
            errores.append(ErrorEnvioOut(
                depto_id=exp.departamento_id,
                email=", ".join(emails),
                motivo=f"Error generando PDF: {e}",
            ))
            continue

        subject = f"Boleta de expensa — {periodo}"
        body = (
            f"Estimado/a vecino/a,\n\n"
            f"Adjuntamos la boleta de expensas correspondiente al período {periodo}.\n\n"
            f"Saludos cordiales,\nLa administración."
        )
        attachment = (f"expensa-{periodo}-depto-{exp.departamento_id}.pdf", pdf, "application/pdf")

        # Enviar a cada email del depto (un mail por destinatario)
        for em in emails:
            ok = enviar_email(to=em, subject=subject, body=body, attachments=[attachment])
            if ok:
                enviados += 1
            else:
                errores.append(ErrorEnvioOut(
                    depto_id=exp.departamento_id,
                    email=em,
                    motivo="Error de envío SMTP (ver logs)",
                ))

    return EnviarPdfsOut(
        enviados=enviados,
        fallaron=len(errores),
        errores=errores,
    )
```

- [ ] **Step 4: Crear `tests/test_envio_pdfs.py`**

```python
"""Tests del endpoint POST /periodos/{periodo}/enviar-pdfs."""


def test_admin_envia_pdfs_periodo_cerrado(client, headers_admin, db, capsys):
    """Período cerrado: envía sin necesidad de confirmar."""
    from backend.models import Expensa, PeriodoCerrado
    # Tomar un período que tenga expensas y cerrarlo
    expensa = db.query(Expensa).first()
    periodo = expensa.periodo
    if db.get(PeriodoCerrado, periodo) is None:
        db.add(PeriodoCerrado(periodo=periodo, cerrado_por_usuario_id=1,
                               total_expensado=0, total_intereses=0, cantidad_expensas=1))
        db.commit()
    r = client.post(
        f"/periodos/{periodo}/enviar-pdfs",
        json={"confirmar_sin_cerrar": False},
        headers=headers_admin,
    )
    assert r.status_code == 200
    body = r.json()
    assert "enviados" in body
    assert "fallaron" in body
    assert "errores" in body


def test_envio_periodo_no_cerrado_devuelve_409(client, headers_admin, db):
    """Sin confirmar y período no cerrado → 409."""
    from backend.models import Expensa, PeriodoCerrado
    # Crear una expensa en período NO cerrado
    expensa = Expensa(
        departamento_id=1, periodo="2030-12",
        monto_primer_vencimiento=1000, fecha_primer_vencimiento="2030-12-10",
        monto_segundo_vencimiento=1070, fecha_segundo_vencimiento="2030-12-20",
        saldo_anterior=0,
    )
    db.add(expensa); db.commit()
    r = client.post(
        "/periodos/2030-12/enviar-pdfs",
        json={"confirmar_sin_cerrar": False},
        headers=headers_admin,
    )
    assert r.status_code == 409


def test_envio_periodo_no_cerrado_con_confirmar_ok(client, headers_admin, db):
    """Con confirmar_sin_cerrar=true, envía aunque no esté cerrado."""
    from backend.models import Expensa
    expensa = Expensa(
        departamento_id=1, periodo="2031-01",
        monto_primer_vencimiento=1000, fecha_primer_vencimiento="2031-01-10",
        monto_segundo_vencimiento=1070, fecha_segundo_vencimiento="2031-01-20",
        saldo_anterior=0,
    )
    db.add(expensa); db.commit()
    r = client.post(
        "/periodos/2031-01/enviar-pdfs",
        json={"confirmar_sin_cerrar": True},
        headers=headers_admin,
    )
    assert r.status_code == 200


def test_periodo_inexistente_devuelve_404(client, headers_admin):
    r = client.post(
        "/periodos/9999-12/enviar-pdfs",
        json={"confirmar_sin_cerrar": True},
        headers=headers_admin,
    )
    assert r.status_code == 404


def test_envio_como_depto_devuelve_403(client, headers_depto_a):
    r = client.post(
        "/periodos/2026-05/enviar-pdfs",
        json={"confirmar_sin_cerrar": True},
        headers=headers_depto_a,
    )
    assert r.status_code == 403
```

- [ ] **Step 5: Run tests**

```bash
.venv/Scripts/python.exe -m pytest tests/test_envio_pdfs.py -v --tb=short
```

Expected: 5 passed.

- [ ] **Step 6: Suite completa**

```bash
.venv/Scripts/python.exe -m pytest tests/ --tb=no -q
```

Expected: ~540 pass (525 baseline + 14 nuevos), 0 fail.

- [ ] **Step 7: Commit**

```bash
git add backend/routers/periodos.py backend/schemas.py tests/test_envio_pdfs.py
git commit -m "feat(periodos): POST /periodos/{periodo}/enviar-pdfs + soft-warning si no cerrado + tests"
```

---

## Task 5: Documentar SMTP en .env.example + README

**Files:**
- Modify: `.env.example`
- Modify: `README.md`

- [ ] **Step 1: Sumar variables SMTP al final de `.env.example`**

```
# --- Fase 6a: SMTP para envío de PDFs ---
# Si SMTP_HOST está vacío, los emails se loggean al stdout (modo console, dev).
SMTP_HOST=
SMTP_PORT=587
SMTP_USER=
SMTP_PASSWORD=
SMTP_FROM_EMAIL=consorcio@local
SMTP_FROM_NAME=Consorcio
```

- [ ] **Step 2: Sumar sección "Email saliente (SMTP)" al README**

Buscar la sección de setup del backend y sumar al final:

```markdown
### Email saliente (SMTP)

Para enviar PDFs por email, configurar en `.env`:

```
SMTP_HOST=smtp.gmail.com   # o tu servidor
SMTP_PORT=587
SMTP_USER=tu_email@gmail.com
SMTP_PASSWORD=tu_app_password
SMTP_FROM_EMAIL=consorcio@tu-dominio.com
SMTP_FROM_NAME=Administración Consorcio
```

Si `SMTP_HOST` queda vacío, los emails NO se envían — se loggean al stdout
(útil para dev y CI). En modo console, el endpoint `POST /periodos/{X}/enviar-pdfs`
igual devuelve éxito.
```

- [ ] **Step 3: Commit**

```bash
git add .env.example README.md
git commit -m "docs: setup de WeasyPrint + variables SMTP para Fase 6a"
```

---

## Task 6: OpenAPI

**Files:**
- Modify: `openapi.yaml`

- [ ] **Step 1: Sumar 2 paths en la sección `paths:`**

```yaml
  /expensas/{expensa_id}/pdf:
    get:
      tags: [Expensas]
      summary: Descargar PDF de la boleta
      operationId: descargarPdfExpensa
      security: [{bearerAuth: []}]
      parameters:
        - name: expensa_id
          in: path
          required: true
          schema: { type: integer }
      responses:
        '200':
          description: PDF
          content:
            application/pdf:
              schema: { type: string, format: binary }
        '403': { description: Depto no autorizado a ver expensa ajena }
        '404': { description: Expensa no encontrada }

  /periodos/{periodo}/enviar-pdfs:
    post:
      tags: [Periodos]
      summary: Enviar boletas por email a deptos del período (admin)
      operationId: enviarPdfsPeriodo
      security: [{bearerAuth: []}]
      parameters:
        - $ref: '#/components/parameters/periodoParam'
      requestBody:
        required: true
        content:
          application/json:
            schema: { $ref: '#/components/schemas/EnviarPdfsIn' }
      responses:
        '200':
          description: Resumen del envío
          content:
            application/json:
              schema: { $ref: '#/components/schemas/EnviarPdfsOut' }
        '404': { description: Período sin expensas }
        '409': { description: Período no cerrado y no se confirmó }
```

- [ ] **Step 2: Sumar 3 schemas en `components.schemas`**

```yaml
    EnviarPdfsIn:
      type: object
      properties:
        confirmar_sin_cerrar: { type: boolean, default: false }

    ErrorEnvioOut:
      type: object
      properties:
        depto_id: { type: integer }
        email: { type: string, nullable: true }
        motivo: { type: string }

    EnviarPdfsOut:
      type: object
      properties:
        enviados: { type: integer }
        fallaron: { type: integer }
        errores:
          type: array
          items: { $ref: '#/components/schemas/ErrorEnvioOut' }
```

- [ ] **Step 3: Validar yaml**

```bash
.venv/Scripts/python.exe -c "import yaml; yaml.safe_load(open('openapi.yaml').read()); print('OK')"
```

Expected: `OK`.

- [ ] **Step 4: Commit**

```bash
git add openapi.yaml
git commit -m "docs(openapi): paths + schemas de Fase 6a (PDF + envío masivo)"
```

---

## Task 7: Frontend API client + botón "Ver PDF"

**Files:**
- Create: `frontend/src/api/pdf.js`
- Modify: `frontend/src/screens/Expensas.jsx`
- Modify: `frontend/src/screens/MiCuenta.jsx`

- [ ] **Step 1: Crear `frontend/src/api/pdf.js`**

```javascript
import { apiFetch, API_BASE } from "./client";

/**
 * Abre el PDF de una expensa en una nueva pestaña.
 * Fetcha como blob para evitar pasar el token por query string.
 */
export async function abrirPdfExpensa(expensaId, token) {
  const res = await fetch(`${API_BASE}/expensas/${expensaId}/pdf`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) {
    throw new Error(`Error al cargar PDF: HTTP ${res.status}`);
  }
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  window.open(url, "_blank");
  // Liberar memoria después de un rato
  setTimeout(() => URL.revokeObjectURL(url), 60_000);
}

export function enviarPdfsDePeriodo(periodo, confirmarSinCerrar = false) {
  return apiFetch(`/periodos/${periodo}/enviar-pdfs`, {
    method: "POST",
    body: { confirmar_sin_cerrar: confirmarSinCerrar },
  });
}
```

**Nota:** `API_BASE` debe estar exportado desde `client.js`. Verificar — si no lo está, agregarlo: `export const API_BASE = ...`.

- [ ] **Step 2: En `frontend/src/screens/Expensas.jsx`, sumar botón "Ver PDF"**

Importar:
```javascript
import { abrirPdfExpensa } from "../api/pdf";
import { useAuth } from "../auth/useAuth";  // o como acceda al token
```

En cada tarjeta de expensa, junto a los otros botones (Ver desglose, Ver comprobantes), sumar:

```jsx
<button
  type="button"
  onClick={async () => {
    try { await abrirPdfExpensa(expensa.id, token); }
    catch (e) { alert(`No se pudo abrir el PDF: ${e.message}`); }
  }}
>
  📄 Ver PDF
</button>
```

(Adaptar el acceso al `token` al patrón existente — puede ser useAuth, useContext(AuthContext), etc.)

- [ ] **Step 3: Idem en `frontend/src/screens/MiCuenta.jsx`** (bloque "Próximo vencimiento" + lista de expensas)

- [ ] **Step 4: Build smoke**

```bash
cd frontend && npm run build
```

Expected: OK.

- [ ] **Step 5: Commit**

```bash
cd .. && git add frontend/src/api/pdf.js frontend/src/screens/Expensas.jsx frontend/src/screens/MiCuenta.jsx
git commit -m "feat(frontend): cliente api/pdf + botón Ver PDF en Expensas y MiCuenta"
```

---

## Task 8: Filtro por período + banner contextual en `/expensas`

**Files:**
- Modify: `frontend/src/screens/Expensas.jsx`

- [ ] **Step 1: Sumar imports**

```javascript
import { listarPeriodos } from "../api/periodos";
```

- [ ] **Step 2: Sumar state y carga al montar**

Dentro del componente principal `Expensas`:

```javascript
const [periodos, setPeriodos] = useState([]);  // lista de PeriodoCerrado del backend
const [periodosCerradosSet, setPeriodosCerradosSet] = useState(new Set());

useEffect(() => {
  (async () => {
    const r = await listarPeriodos();
    if (r.status === 200) {
      setPeriodos(r.data);
      setPeriodosCerradosSet(new Set(r.data.map(p => p.periodo)));
    }
  })();
}, []);
```

Si ya hay un state `filtroPeriodo` (o similar) usado en el GET de expensas, reusarlo. Si no, sumar:

```javascript
const [filtroPeriodo, setFiltroPeriodo] = useState("");
```

Y en el GET de expensas pasarlo como query param si aplica.

- [ ] **Step 3: Sumar dropdown de filtro en el JSX**

En la cabecera de la pantalla (donde están los otros filtros):

```jsx
<label>
  Período:
  <input
    type="month"
    value={filtroPeriodo}
    onChange={(e) => setFiltroPeriodo(e.target.value)}
  />
  {filtroPeriodo && (
    <button type="button" onClick={() => setFiltroPeriodo("")}>Limpiar</button>
  )}
</label>
```

- [ ] **Step 4: Sumar banner contextual cuando hay período filtrado**

Justo encima de la lista de expensas:

```jsx
{filtroPeriodo && (
  <div className={`banner-periodo ${periodosCerradosSet.has(filtroPeriodo) ? 'cerrado' : 'abierto'}`}>
    📅 Período {filtroPeriodo}
    {periodosCerradosSet.has(filtroPeriodo) ? ' (cerrado)' : ' (sin cerrar)'}
    · {expensasFiltradas.length} expensas
    <button type="button" onClick={() => setModalEnvio(filtroPeriodo)}>
      ✉ Enviar PDFs por email
    </button>
  </div>
)}
```

Donde `setModalEnvio(filtroPeriodo)` setea un state para abrir el `ModalEnvioPdfs` (que creamos en Task 9).

- [ ] **Step 5: Filtrar las expensas localmente si el GET no soporta query period**

```javascript
const expensasFiltradas = filtroPeriodo
  ? expensas.filter(e => e.periodo === filtroPeriodo)
  : expensas;
```

(Si el GET `/expensas` ya soporta `?periodo=`, mejor pasarlo al backend.)

- [ ] **Step 6: Build smoke**

```bash
cd frontend && npm run build
```

- [ ] **Step 7: Commit**

```bash
cd .. && git add frontend/src/screens/Expensas.jsx
git commit -m "feat(expensas): filtro por período + banner contextual con botón envío PDFs"
```

---

## Task 9: ModalEnvioPdfs + botón en `/periodos`

**Files:**
- Create: `frontend/src/components/ModalEnvioPdfs.jsx`
- Modify: `frontend/src/screens/Periodos.jsx`
- Modify: `frontend/src/screens/Expensas.jsx`

- [ ] **Step 1: Crear `frontend/src/components/ModalEnvioPdfs.jsx`**

```jsx
import { useState } from "react";
import Modal from "./Modal";
import { enviarPdfsDePeriodo } from "../api/pdf";

export default function ModalEnvioPdfs({ periodo, periodoCerrado, cantidadExpensas, onClose, onCompletado }) {
  const [confirmado, setConfirmado] = useState(periodoCerrado);
  const [enviando, setEnviando] = useState(false);
  const [resumen, setResumen] = useState(null);
  const [error, setError] = useState(null);

  async function handleEnviar() {
    setEnviando(true);
    setError(null);
    const r = await enviarPdfsDePeriodo(periodo, !periodoCerrado);
    setEnviando(false);
    if (r.status === 200) {
      setResumen(r.data);
      onCompletado?.(r.data);
    } else if (r.status === 409) {
      setError("El período no está cerrado y no se confirmó el envío. Tildá la confirmación.");
    } else {
      setError(r.data?.detail || "Error al enviar.");
    }
  }

  return (
    <Modal titulo={`Enviar boletas PDF — ${periodo}`} onClose={onClose}>
      {!resumen && (
        <>
          {!periodoCerrado && (
            <div className="warning-banner" style={{
              background: "#fff3cd", border: "1px solid #ffc107",
              padding: "1em", marginBottom: "1em", borderRadius: "4px"
            }}>
              <strong>⚠ Este período NO está cerrado.</strong>
              <p>Las boletas pueden cambiar si después aprobás comprobantes,
              agregás gastos o cerrás el período. Una vez enviadas no podés "desenviarlas".</p>
              <label>
                <input
                  type="checkbox"
                  checked={confirmado}
                  onChange={(e) => setConfirmado(e.target.checked)}
                />
                Sí, entiendo y quiero enviar igual.
              </label>
            </div>
          )}

          <p>Vas a enviar <strong>{cantidadExpensas}</strong> boletas por email a los departamentos del período <strong>{periodo}</strong>.</p>

          {error && <p role="alert" className="error-banner">{error}</p>}

          <button type="button" onClick={onClose} disabled={enviando}>Cancelar</button>
          <button
            type="button"
            onClick={handleEnviar}
            disabled={!confirmado || enviando}
            style={{ marginLeft: "0.5em" }}
          >
            {enviando ? "Enviando…" : "Confirmar envío"}
          </button>
        </>
      )}

      {resumen && (
        <>
          <h3>Resumen del envío</h3>
          <p>✅ <strong>{resumen.enviados}</strong> enviados.</p>
          <p>❌ <strong>{resumen.fallaron}</strong> fallaron.</p>
          {resumen.errores.length > 0 && (
            <table>
              <thead>
                <tr><th>Depto</th><th>Email</th><th>Motivo</th></tr>
              </thead>
              <tbody>
                {resumen.errores.map((e, i) => (
                  <tr key={i}>
                    <td>{e.depto_id}</td>
                    <td>{e.email || "—"}</td>
                    <td>{e.motivo}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          <button type="button" onClick={onClose}>Cerrar</button>
        </>
      )}
    </Modal>
  );
}
```

- [ ] **Step 2: En `frontend/src/screens/Periodos.jsx`, sumar botón "Enviar PDFs" por fila**

Sumar import:
```javascript
import { useState } from "react";
import ModalEnvioPdfs from "../components/ModalEnvioPdfs";
```

State:
```javascript
const [modalEnvio, setModalEnvio] = useState(null);  // { periodo, cantidadExpensas }
```

En la tabla, columna nueva (al final) en cada fila:
```jsx
<td>
  <button type="button" onClick={() => setModalEnvio({
    periodo: p.periodo,
    cantidadExpensas: p.cantidad_expensas,
    periodoCerrado: true,  // todas las filas de /periodos son cerradas
  })}>
    ✉ Enviar PDFs
  </button>
</td>
```

Render del modal al final del JSX:
```jsx
{modalEnvio && (
  <ModalEnvioPdfs
    periodo={modalEnvio.periodo}
    periodoCerrado={modalEnvio.periodoCerrado}
    cantidadExpensas={modalEnvio.cantidadExpensas}
    onClose={() => setModalEnvio(null)}
  />
)}
```

- [ ] **Step 3: En `frontend/src/screens/Expensas.jsx`, integrar el modal con el botón del banner**

State:
```javascript
const [modalEnvio, setModalEnvio] = useState(null);
```

El botón del banner (de Task 8) ahora hace:
```jsx
<button type="button" onClick={() => setModalEnvio({
  periodo: filtroPeriodo,
  cantidadExpensas: expensasFiltradas.length,
  periodoCerrado: periodosCerradosSet.has(filtroPeriodo),
})}>
  ✉ Enviar PDFs por email
</button>
```

Render del modal:
```jsx
{modalEnvio && (
  <ModalEnvioPdfs
    periodo={modalEnvio.periodo}
    periodoCerrado={modalEnvio.periodoCerrado}
    cantidadExpensas={modalEnvio.cantidadExpensas}
    onClose={() => setModalEnvio(null)}
  />
)}
```

- [ ] **Step 4: Build smoke**

```bash
cd frontend && npm run build
```

- [ ] **Step 5: Commit**

```bash
cd .. && git add frontend/src/components/ModalEnvioPdfs.jsx frontend/src/screens/Periodos.jsx frontend/src/screens/Expensas.jsx
git commit -m "feat(frontend): ModalEnvioPdfs con soft-warning + botones en Periodos y Expensas"
```

---

## Task 10: Smoke + merge + roadmap

**Files:**
- Modify: `docs/superpowers/specs/2026-06-16-expensas-completas-roadmap.md`

- [ ] **Step 1: Smoke E2E manual**

Arrancar uvicorn + frontend:
```powershell
.venv\Scripts\python -m uvicorn backend.main:app --reload
# terminal 2:
cd frontend; npm run dev
```

Pruebas:
1. Login admin → `/expensas` → click "📄 Ver PDF" en cualquier tarjeta → se abre el PDF en nueva pestaña con datos correctos.
2. Logout, login depto → `/mi-cuenta` → "Ver PDF" en una expensa propia → OK.
3. Depto intenta abrir manualmente `/expensas/{id_de_otro_depto}/pdf` → 403.
4. Admin → `/expensas` → filtrar por período cerrado → ver banner "📅 Período 2026-05 (cerrado) · N expensas · Enviar PDFs".
5. Click "Enviar PDFs" → modal directo (sin warning) → confirmar → resumen con N enviados (en modo console, los emails se loggean al stdout de uvicorn).
6. Admin → `/expensas` → filtrar por período NO cerrado → banner amarillo en el modal con checkbox de confirmación.
7. Admin → `/periodos` → botón "Enviar PDFs" en una fila → modal + envío.
8. Verificar que el stdout de uvicorn muestra `[EMAIL CONSOLE MODE] To: depto-a@consorcio.local | Subject: Boleta de expensa — 2026-05`.

- [ ] **Step 2: Suite final**

```bash
.venv/Scripts/python.exe -m pytest tests/ --tb=no -q
```

Expected: ~540+ passed, 0 fail.

- [ ] **Step 3: Actualizar roadmap**

En `docs/superpowers/specs/2026-06-16-expensas-completas-roadmap.md`:

Reemplazar la línea de Fase 6:
```markdown
| 6 | Reportes Ley 941 + PDF de liquidación | Estado financiero, patrimonial, lista de proveedores, evolución de cobranzas, lista de morosos, PDF con formato real. |
```

Por:
```markdown
| **6a** ✅ | **PDF boleta + envío masivo** (completada 2026-06-24) | WeasyPrint, GET /expensas/{id}/pdf, POST /periodos/{periodo}/enviar-pdfs con soft-warning, frontend con filtro+banner+modal. |
| 6b | Reportes Ley 941 | Estado patrimonial, lista de proveedores, evolución de cobranzas, lista de morosos. |
```

Sumar al historial:
```markdown
- 2026-06-24: **Fase 6a completada** (~540 tests, mergeada a master). PDF on-demand con WeasyPrint, envío masivo síncrono con soft-warning de período no cerrado. Modo console SMTP para dev. Reportes Ley 941 quedan para Fase 6b.
```

Actualizar próximo paso:
```markdown
Brainstorming de Fase 6b (Reportes Ley 941).
```

- [ ] **Step 4: Commit + merge**

```bash
git add docs/superpowers/specs/2026-06-16-expensas-completas-roadmap.md
git commit -m "docs(roadmap): Fase 6a completada (PDF boleta + envío masivo)"

git checkout master
git merge --no-ff feature/expensas-fase6a-pdf -m "Merge feature/expensas-fase6a-pdf: PDF boleta + envío masivo

Fase 6a — Genera PDFs de boletas con WeasyPrint (on-demand, sin storage).
Endpoint admin para envío masivo por email a todos los deptos del período,
síncrono con resumen y soft-warning si el período no está cerrado."
```

- [ ] **Step 5: Done. Fase 6b queda para brainstorming.**

---

## Notas finales

- **Orden de tasks**: dependencias mínimas (módulo email → módulo pdf → endpoints → frontend → smoke/merge). Permite testing incremental.
- **TDD**: Tasks 1, 2, 3, 4 escriben tests primero (RED) → implementación (GREEN) → commit.
- **Commits frecuentes**: ~10 commits totales.
- **WeasyPrint en Windows**: el único punto de potencial fricción del plan. Si falla en setup, BLOQUEAR y resolver antes de seguir.
- **Modo console SMTP**: alcanza para CI + dev sin necesidad de servidor de mail real.
