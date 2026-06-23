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
| 3 | Encargado y cargas sociales | Empleado, sueldo básico, aportes/contribuciones automáticas (AFIP F931, FATERYH, SUTERH, etc.). Alimenta Rubro 1. |
| **3.5** ✅ | **Cuenta corriente por departamento** (completada 2026-06-17) | Rewrite del módulo de pagos. Cada depto tiene cuenta con movimientos (débitos/créditos). Comprobantes aprobados generan movimientos en lugar de cambiar el estado binario de la expensa. Soporta sobre-pagos, devoluciones, notas de crédito/débito, asignación de pagos a múltiples expensas. Prerrequisito de Fase 4. |
| **4** ✅ | **Cierre de período y liquidación** (completada 2026-06-22) | Botón "Cerrar período" → genera expensas con desglose por rubro y clase. Saldo anterior (= saldo de cuenta), créditos/débitos, 1°/2° vencimiento, intereses punitorios. |
| **5** ✅ | **Tesorería: caja, fondo de reparación, estado financiero** (completada 2026-06-23) | Cajas configurables (banco/efectivo/fondo/otro), transferencias entre cajas, ajustes manuales como red de seguridad, dashboard "Estado financiero" con saldos por caja + total + últimos movimientos. |
| 6 | Reportes Ley 941 + PDF de liquidación | Estado financiero, patrimonial, lista de proveedores, evolución de cobranzas, lista de morosos, PDF con formato real. |

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

## Próximo paso

Brainstorming de Fase 6 (Reportes Ley 941 + PDF de liquidación).
