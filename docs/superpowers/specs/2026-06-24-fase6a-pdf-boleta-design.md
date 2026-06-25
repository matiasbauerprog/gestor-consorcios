# Fase 6a — PDF de boleta de liquidación + envío masivo por email

Fecha: 2026-06-24
Estado: spec aprobado (brainstorming cerrado con el usuario)

## Contexto y motivación

Al cerrar un período (Fase 4), el sistema genera N `Expensa` con su `ExpensaDetalle` por rubro. Hoy esa info vive solo dentro de la app — el admin no tiene cómo entregar al depto un documento imprimible/mailable con la liquidación del mes.

Fase 6a soluciona dos necesidades concretas:
1. **Boleta PDF descargable / visualizable**: cualquier expensa puede verse como PDF (admin: cualquiera; depto: solo las suyas) sin descargar — el browser lo abre con su visor nativo. Opcional: descargar.
2. **Envío masivo por email**: el admin, después del cierre, dispara con un botón el envío de las N boletas a los emails de los usuarios de cada depto. Modo síncrono con resumen al final ("28 enviados, 2 fallaron").

Esto es la pieza visible que falta para que el sistema cubra el ciclo completo del consorcio: cargar gastos → cerrar período → emitir y entregar boletas.

## Alcance — explícitamente Fase 6a, NO Fase 6b

Esta fase cubre **PDF de boleta + envío de boletas**. Los reportes Ley 941 (estado patrimonial, lista de morosos, lista de proveedores, evolución de cobranzas) viven en Fase 6b — spec aparte cuando se necesite.

## Decisiones (cerradas en brainstorming)

1. **Split**: 6a (PDF boleta) y 6b (reportes Ley 941) separados.
2. **Engine de PDF**: ReportLab server-side (Python puro, sin deps del SO). ~~WeasyPrint~~ se descartó tras detectar en Task 0 que requiere GTK3 runtime en Windows (friccion de setup recurrente).
3. **Contenido**: estándar (header consorcio, datos del depto, desglose por rubro, vencimientos, datos bancarios).
4. **Generación**: on-demand. Cada GET regenera el PDF con datos actuales. Sin storage en disco.
5. **Envío masivo**: síncrono. El endpoint procesa los N emails y devuelve un resumen `{enviados, fallaron, errores}`. Sin tracking persistido.
6. **UX de visualización**: "Ver PDF" abre el endpoint en nueva pestaña (`target="_blank"`) con `Content-Disposition: inline`. El visor del browser ya cubre zoom/descarga/impresión.
7. **UX de envío**: combinación de 2 entry points — `/expensas` con filtro+banner contextual cuando hay un período filtrado cerrado; `/periodos` con botón en cada fila del historial. Ambos llaman al mismo endpoint.
8. **Destinatario**: email del `Usuario` (rol=departamento) asociado al `Departamento`. Si un depto tiene 2 usuarios, se manda a ambos.

## Arquitectura — Backend

### Librerías nuevas
- **`reportlab`** (Python puro, sin deps del SO — funciona en Windows/Linux/Mac out of the box).

### Sin templates HTML
ReportLab no usa HTML/CSS — el layout se dibuja programáticamente con primitivas (`Paragraph`, `Table`, `Spacer`) sobre un `SimpleDocTemplate`. Toda la estructura de la boleta vive en `backend/pdf.py`.

### Módulo nuevo `backend/pdf.py`
```python
from io import BytesIO
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

def generar_pdf_boleta(expensa: Expensa, db: Session) -> bytes:
    """Genera el PDF de una expensa. Función pura: no persiste nada.

    Carga:
    - ConfiguracionConsorcio
    - Departamento
    - MovimientoCuenta del depto (pagos, intereses, notas)
    - ExpensaDetalle agrupado por rubro

    Devuelve los bytes del PDF generado con ReportLab (SimpleDocTemplate sobre BytesIO).
    """
```

### Módulo nuevo `backend/email.py`
```python
import smtplib
from email.message import EmailMessage

def enviar_email(
    to: str,
    subject: str,
    body: str,
    attachments: list[tuple[str, bytes, str]] = [],  # [(filename, content, mime_type)]
) -> bool:
    """Envía un email. Devuelve True/False según éxito.

    Si settings.SMTP_HOST está vacío → modo console: loggea al stdout y devuelve True.
    Si hay SMTP_HOST → envía vía smtplib con TLS.
    """
```

### Endpoints nuevos

#### `GET /expensas/{expensa_id}/pdf`
- **Roles**: admin y representante (cualquier expensa), depto (solo las suyas → 403 si pide ajena).
- **Response**: `application/pdf` con `Content-Disposition: inline; filename="expensa-{periodo}-depto-{codigo}.pdf"`.
- **404** si expensa no existe.
- **403** si depto pide ajena.

#### `POST /periodos/{periodo}/enviar-pdfs`
- **Rol**: admin only.
- **Body**: vacío (todo se infiere del periodo).
- **Comportamiento**:
  1. Validar que el período existe (al menos una `Expensa` con ese período). Si no hay → 404.
  2. Iterar las expensas del período.
  3. Para cada una: obtener emails de los usuarios del depto (`rol=departamento`), generar PDF, enviar email con asunto `"Boleta de expensa — {periodo}"` y cuerpo HTML mínimo, adjuntando el PDF.
  4. Si un envío falla (SMTP error, email inválido, etc.), capturarlo y seguir.
  5. Devolver `{enviados: N, fallaron: M, errores: [{depto, email, motivo}]}`.
- **Response 200** con el resumen.

### Cambios a endpoints existentes
- Ninguno. Los endpoints existentes (`/expensas`, `/periodos`) no se modifican.

### Cambios a modelos
- Ninguno. No hay tablas nuevas.

### Configuración nueva en `backend/config.py` + `.env`
```
SMTP_HOST=                       # vacío → modo console (dev)
SMTP_PORT=587
SMTP_USER=
SMTP_PASSWORD=
SMTP_FROM_EMAIL=consorcio@local
SMTP_FROM_NAME=Consorcio
```
Defaults vacíos para que el sistema arranque sin SMTP real (modo console).

## Arquitectura — Frontend

### Cliente API nuevo `frontend/src/api/pdf.js`
```javascript
import { apiFetch, API_BASE } from "./client";

export function urlPdfExpensa(expensaId) {
  // Devuelve URL absoluta con el token en query string (browser open inline)
  // El backend acepta token via query param para casos donde no se puede mandar header
  return `${API_BASE}/expensas/${expensaId}/pdf`;
}

export function enviarPdfsDePeriodo(periodo) {
  return apiFetch(`/periodos/${periodo}/enviar-pdfs`, { method: "POST", body: {} });
}
```

**Nota técnica**: si abrimos el PDF con `window.open(url, "_blank")`, el browser hace GET sin el header `Authorization`. Dos soluciones:
- (a) Aceptar el token también vía query param `?token=...` en el endpoint PDF (más simple).
- (b) Hacer fetch del PDF en JS, convertirlo a blob, abrir blob URL en nueva pestaña (más limpio pero suma código).

Decisión: **(b)** para no exponer el token en URLs. El cliente fetcha con `apiFetch`, recibe blob, abre `URL.createObjectURL(blob)` en nueva pestaña.

### Ajuste `/expensas`
- **Filtro nuevo por período**: dropdown con períodos disponibles + opción "Todos". Reusa el patrón existente del filtro de período de `/gastos`.
- **Banner contextual**: cuando hay un período filtrado **y está cerrado** (verificar con `listarPeriodos()` cacheado), aparece arriba de la lista:
  ```jsx
  <Banner>
    📅 Período {periodo} (cerrado) · {expensas.length} expensas
    <button onClick={handleEnviar}>✉ Enviar PDFs por email</button>
  </Banner>
  ```
- **Botón "📄 Ver PDF"** en cada tarjeta de expensa (admin y depto, según permisos).

### Ajuste `/mi-cuenta`
- Botón "📄 Ver PDF" en cada expensa listada (incluyendo el bloque "Próximo vencimiento").

### Ajuste `/periodos`
- Nueva columna o botón en cada fila: **"✉ Enviar PDFs"**. Click → modal de confirmación → llamada al endpoint → muestra resumen.

### Componente nuevo `ModalEnvioPdfs.jsx`
- Recibe `{ periodo, periodoCerrado, cantidadExpensas, onClose, onCompletado }`.
- **Si el período NO está cerrado**: muestra banner amarillo "⚠ Este período no fue cerrado..." + checkbox "Sí, entiendo y quiero enviar igual" que habilita el botón. Al confirmar manda `confirmar_sin_cerrar=true` al endpoint.
- **Si está cerrado**: confirmación normal "¿Enviar boletas a los {N} departamentos del período {periodo}?".
- Confirmar → loading spinner → llamada al endpoint.
- Al recibir respuesta, mostrar resumen con tabla de errores si hay.
- Botón "Cerrar" cuando termina (o "Cancelar" antes de empezar).

### Ajuste `/configuracion`
- Ningún cambio en esta fase. La config SMTP vive en `.env` (no en DB) por simplicidad y para no exponer credenciales del servidor en el storage de la app. Si más adelante hace falta config SMTP por la UI, se hace en Fase 6.x con un modelo aparte y encripción.

## Reglas operativas

- **Período no cerrado — envío**: el endpoint POST `/periodos/{periodo}/enviar-pdfs` acepta un body `{ "confirmar_sin_cerrar": bool }` opcional. Si el período NO está cerrado y `confirmar_sin_cerrar` es `false` (o falta), el endpoint devuelve **409** con detail `"El período {periodo} no está cerrado. Para enviar igual, reenviá con confirmar_sin_cerrar=true."`. Esto es la red de seguridad para evitar envíos por error de boletas no finalizadas.
- **Período no cerrado — frontend**: el `ModalEnvioPdfs` detecta si el período está cerrado (consulta cacheada de `listarPeriodos()`). Si no lo está, muestra **un banner amarillo bien visible**: `"⚠ Este período no fue cerrado. Las boletas pueden cambiar si después aprobás comprobantes, agregás gastos o cerrás el período. ¿Querés enviar igual?"`, con un checkbox `"Sí, entiendo y quiero enviar igual"` que habilita el botón "Enviar". Esto traduce el 409 a una decisión consciente del admin.
- **Período inexistente**: si no hay ninguna expensa con ese período → 404.
- **Email sin destinatarios**: si un depto no tiene usuarios con rol=departamento (caso raro), se cuenta como error con motivo "sin destinatarios".
- **PDF de período no cerrado — visualización**: el GET `/expensas/{id}/pdf` siempre funciona, esté el período cerrado o no. Útil para preview antes del cierre y para reimpresión después.
- **Acceso**: depto solo ve PDFs de SUS expensas. Admin y representante ven cualquiera.

## Tests

### Backend
- `tests/test_pdf_boleta.py` (~6 tests): smoke de generación, validar bytes con magic `%PDF-`, GET 200 admin, GET 403 depto ajeno, GET 200 depto propio, generación con saldo anterior > 0.
- `tests/test_envio_pdfs.py` (~5 tests): POST 200 admin con modo console, POST 403 depto, POST 404 período inexistente, response shape correcto, conteo enviados/fallaron correcto.
- `tests/test_email.py` (~3 tests): modo console devuelve True + loggea, modo SMTP con mock llama a send_message, attachment construye MIMEMultipart correcto.

### Sin tests E2E del frontend
- Smoke manual al cierre.

## Out-of-scope explícito

- ❌ Reportes Ley 941 → Fase 6b.
- ❌ Tracking persistido de envíos (modelo `EnvioEmail`, pantalla `/envios`, reintentos auto).
- ❌ Async background tasks para envío masivo (sync alcanza).
- ❌ QR / código de barras en boleta.
- ❌ Gráficos en PDF (matplotlib).
- ❌ Plantillas alternativas / multi-formato.
- ❌ Firmas digitales en PDF.
- ❌ Adjuntar comprobantes escaneados al PDF.
- ❌ Internacionalización (todo es-AR).
- ❌ Config SMTP por UI (vive solo en `.env`).

## Setup en README
- Documentar instalación de WeasyPrint en Windows (GTK runtime).
- Documentar variables SMTP en `.env.example`.
- Aclarar modo console como default para dev.

## Estimación
- ~8-10 tasks (módulo pdf + templates + tests · módulo email + tests · 2 endpoints + tests · ajustes config model/schemas · frontend api client + 4 pantallas modificadas · smoke + merge).
- Tiempo total: 1-1.5 semanas estimadas.

## Historial
- 2026-06-24: brainstorming + spec inicial post-merge Fase 5. Decisión clave: separar de Fase 6b (reportes Ley 941) para foco. UX combinada con filtro+banner en /expensas + botón en /periodos.
