# Expensas completas — roadmap de fases

Fecha: 2026-06-16
Estado: roadmap acordado. Cada fase tiene su propio brainstorming → spec → plan → implementación.

## Contexto

Hoy el módulo de expensas solo guarda un monto total por (depto, período). El usuario quiere replicar el modelo de una **liquidación real de consorcio** (Ley 941 CABA), tomando como referencia dos liquidaciones reales (`file.pdf` y `LIQUIDACION AVALOS 2019 E MAYO 2026 - copia (1).pdf` en la raíz del repo).

El proyecto es educativo, pero con un fin comercial a largo plazo. Por eso se elige réplica fiel del modelo real (opción 2), descompuesta en fases para que cada una sea ejecutable en un ciclo spec→plan→implementación independiente.

## Fases

| # | Fase | Alcance principal |
|---|---|---|
| 1 | Modelo de datos central | Rubros, clases de prorrateo, coeficientes múltiples por depto, proveedores, configuración del consorcio. |
| 2 | Gastos del consorcio | Carga/edición de gastos con metadata completa (rubro, clase, proveedor, factura, pago, cuota). Gastos particulares a depto. |
| **3** ✅ | **Encargado y cargas sociales** (completada 2026-06-17) | Empleado, sueldo básico, aportes/contribuciones automáticas (AFIP F931, FATERYH, SUTERH, etc.). Alimenta Rubro 1. |
| **3.5** ✅ | **Cuenta corriente por departamento** (completada 2026-06-17) | Rewrite del módulo de pagos. Cada depto tiene cuenta con movimientos (débitos/créditos). Comprobantes aprobados generan movimientos en lugar de cambiar el estado binario de la expensa. Soporta sobre-pagos, devoluciones, notas de crédito/débito, asignación de pagos a múltiples expensas. Prerrequisito de Fase 4. |
| **4** ✅ | **Cierre de período y liquidación** (completada 2026-06-22) | Botón "Cerrar período" → genera expensas con desglose por rubro y clase. Saldo anterior (= saldo de cuenta), créditos/débitos, 1°/2° vencimiento, intereses punitorios. |
| **5** ✅ | **Tesorería: caja, fondo de reparación, estado financiero** (completada 2026-06-23) | Cajas configurables (banco/efectivo/fondo/otro), transferencias entre cajas, ajustes manuales como red de seguridad, dashboard "Estado financiero" con saldos por caja + total + últimos movimientos. |
| **6a** ✅ | **PDF boleta + envío masivo** (completada 2026-06-25) | ReportLab para generación de PDFs on-demand; GET /expensas/{id}/pdf (admin/depto con auth por ownership); POST /periodos/{periodo}/enviar-pdfs (admin, sync + soft-warning 409 si período no cerrado); frontend con filtro+banner en /expensas, modal con warning + checkbox, integración tras cierre exitoso; modo console SMTP para dev; cleanup de "Ver desglose" redundante. |
| **6b** ✅ | **Reportes (PBA-friendly)** (completada 2026-06-26) | 4 reportes consultables y exportables a PDF: morosos, estado financiero, detalle de gastos del período, lista de proveedores. Toggle opt-in en config para visibilidad por depto (default off — admin habilita). Sin formato Ley 941 oficial CABA (queda para Fase 6c si entra cliente CABA). |
| **11** ✅ | **Tareas y Presupuestos** (completada 2026-06-27) | Workflow end-to-end petición → trabajo → presupuestos → completar → genera Gasto. Presupuestos con archivo adjunto (PDF/JPG/PNG/WebP ≤5MB) y FK a Proveedor. Notificaciones doble canal (in-app campanita con polling 60s + email best-effort). Trabajos recurrentes con materialización manual. Cierra el módulo "Tareas y Presupuestos" descrito en CLAUDE.md. |
| **12** ✅ | **Reserva de espacios (amenities)** (completada 2026-06-28) | CRUD admin de amenities (soft-delete). Reservas con políticas configurables (duración, anticipación, límite por depto), cobro automático al confirmar (nota de débito en cuenta corriente), reversa al cancelar (con/sin plazo, admin override), notificaciones doble canal. Cierra el módulo "Reserva de espacios" descrito en CLAUDE.md. |

## Orden y dependencias

- Fase 1 es prerrequisito de todas las demás.
- Fase 2 depende de Fase 1.
- Fase 3 depende de Fase 1 y Fase 2 (los sueldos producen gastos).
- **Fase 3.5 depende de Fase 1, 2 y 3 (necesita el modelo `Expensa` y `Comprobante` para reescribirlos).**
- Fase 4 depende de **Fase 3.5** (necesita cuenta corriente para modelar saldos, intereses y pagos correctamente).
- Fases 5 y 6 dependen de Fase 4.

## Out-of-scope explícito (fuera de las 6 fases)

- Asambleas y resoluciones formales.
- Inversiones de fondos (más allá de notas de texto en reportes).
- Notificaciones / mailing automático de expensas.
- Integraciones con bancos para conciliación automática.
- App mobile nativa (sigue siendo SPA responsive).

## Estimación

Cada fase: 1–3 semanas. Total: 10–17 semanas (incluyendo Fase 3.5). Estimación informal, sujeta a refinamiento al cerrar cada fase.

## Historial de cambios

- 2026-06-16: roadmap inicial con 6 fases.
- 2026-06-17: se introduce **Fase 3.5 (Cuenta corriente)** después de descubrir durante el brainstorming de Fase 4 que el modelo binario `Expensa.estado=pagada|pendiente` no permite modelar pagos parciales, sobre-pagos, notas de crédito ni intereses correctamente. Decisión: rediseñar el módulo de pagos antes de afrontar el cierre.
- 2026-06-17: **Fase 3.5 completada** (453 tests, mergeada a master). Incluye además soft-delete de comprobantes y archivo obligatorio en el POST.
- 2026-06-22: **Fase 4 completada** (481 tests, mergeada a master). Cierre formal con tabla `PeriodoCerrado`; genera N expensas con desglose por rubro/clase (`ExpensaDetalle`), 1°/2° vencimiento con recargo configurable, saldo anterior heredado e intereses automáticos sobre morosos. Bloqueo 409 cross-recurso en `/gastos`, `/expensas` y `/liquidaciones` cuando el período está cerrado.
- 2026-06-22: **Fase 4.5 completada** (mergeada a master). Refactor UX sin backend: botón "Cerrar período" inline en `/gastos`, modal de comprobantes accesible desde cada expensa, botón "Presentar pago" pre-seleccionado en `/mi-cuenta`. Sidebar -1 item.
- 2026-06-23: **Fase 5 completada** (525 tests, mergeada a master). Multi-caja sin conciliación: modelos `Caja`/`MovimientoCaja`/`TransferenciaCaja`, integración con gastos/comprobantes/liquidaciones (caja_id required + cascade automático de MovimientoCaja), ajustes manuales como red de seguridad, dashboard /estado-financiero. Frontend con 3 pantallas nuevas + sección Tesorería en sidebar. Bloqueo cross-recurso ampliado a transferencias y ajustes.
- 2026-06-25: **Fase 6a completada** (542 tests, mergeada a master). PDF de boleta con ReportLab (Python puro, sin GTK runtime) generado on-demand. Endpoint admin para envío masivo síncrono por email a deptos del período con soft-warning si no cerrado (409 + flag `confirmar_sin_cerrar`). Frontend: filtro por período + banner contextual en `/expensas`, modal de envío con warning + checkbox, integración tras cierre exitoso (ofrece envío inmediato), nota informativa sobre aplicación FIFO en presentación de pago. Cleanup: removido `ModalDesgloseExpensa` (redundante con PDF). Modo console SMTP para dev. Reportes Ley 941 quedan para Fase 6b.
- 2026-06-26: **Fase 6b completada** (570 tests, mergeada a master). 4 reportes (morosos, estado financiero, gastos del período, lista de proveedores) consultables y exportables a PDF reusando ReportLab. Acceso para admin/representante siempre; para depto opt-in vía toggle `reportes_visibles_a_depto` en configuración (default false — admin habilita explícitamente). Refactor `_dibujar_header_consorcio` para reuso entre boleta + 4 reportes. Cierra el roadmap original de 6 fases.
- 2026-06-27: **Fase 11 completada** (603 tests, branch `feature/expensas-fase11-tareas-presupuestos`). Cierra el módulo "Tareas y Presupuestos" del CLAUDE.md: workflow petición → trabajo → presupuestos → completar → Gasto integrado a la caja. Presupuesto con upload de archivo (PDF/JPG/PNG/WebP ≤5MB) y FK a Proveedor (en lugar de string suelto). Sistema de Notificaciones doble canal reusable (campanita in-app + email best-effort) que se dispara en cambios de estado de petición/trabajo. Trabajos recurrentes con materialización manual (plantilla → Trabajo on-demand). Seed con 2 plantillas demo (limpieza tanque trimestral + ascensores mensual).
- 2026-06-28: **Fase 12 completada** (mergeada a master). Cierra el módulo "Reserva de espacios" del CLAUDE.md: amenities (CRUD admin, soft-delete) + reservas con políticas configurables por amenity (duración, anticipación mínima, límite de reservas activas por depto), cobro automático al confirmar como nota de débito en cuenta corriente (Fase 3.5), reversa automática al cancelar (con o sin plazo, con override de admin) y notificaciones doble canal (email al reservar + doble canal cuando admin cancela reserva ajena).
- 2026-07-03 a 2026-07-30: trabajo posterior al roadmap original, fuera de las 6+3 fases pero mergeado a master — no tenía tracking en este documento hasta ahora: rediseño visual "Aire" + paleta Command (2026-07-03), aside de navegación en acordeón + hub "Mi cuenta" para depto (2026-07-04), **multi-tenancy** completa — Plan A backend core + Plan B super_admin con panel de módulos habilitables por administración (2026-07-06/07/11, ver `2026-07-06-multitenant-saas-design.md`), rebranding mobile-first (2026-07-28), reestructura de navegación + limpieza de theming por módulo (2026-07-30).
- 2026-07-30: se corrige este documento — Fase 3 y Fase 12 estaban implementadas pero no marcadas ✅ en la tabla; multi-tenancy figuraba como pendiente opcional en "Próximo paso" pese a estar mergeada desde julio.
- 2026-07-31: **Modo demo completado** (927 tests, branch `feature/modo-demo`, ver `2026-07-30-modo-demo-design.md`). Demo público sin credenciales: flag `DEMO_MODE`, endpoint `/auth/demo-login` con lista blanca de 3 roles y 3 candados anti-producción, generador de dataset realista (18 UF, 6 meses de operación, ~67 s runtime), reset por cron sobre Postgres (sin seed-on-boot), selector de rol + banner en frontend, mirror por snapshot al repo público (commit huérfano, nunca historial — protege `consorcio.db.corrupta`). Guard del workflow ampliado a `.sqlite3`/`.db.bak`/`.sql`/`.dump`/`.backup`.

## Próximo paso

**Módulos "Tareas y Presupuestos" y "Reserva de espacios" cerrados. Multi-tenancy (ex-Fase 7) también completada** — ver `2026-07-06-multitenant-saas-design.md` y los planes de super_admin / módulos por administración. Queda pendiente (opcionales, para comercialización):
- Fase 6c: modo Ley 941 oficial CABA (formato específico) — cuando aparezca primer cliente CABA.
- Fase 8: audit log + backups automáticos — confianza profesional.
- Fase 9: integraciones AFIP/SUTERH — diferenciador comercial.
- Feature flag de personal (SaaS): toggle en Configuración del consorcio para ocultar el módulo de Personal/Liquidaciones si la administración no tiene empleados propios.
