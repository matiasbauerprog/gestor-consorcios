# Publicar la demo

Fecha: 2026-08-17

La demo corre entera en el navegador de quien la mira. No necesita backend, ni
base de datos, ni cron. Se publica como archivos estáticos.

## Los dos proyectos de Vercel

Ambos apuntan **al mismo repositorio y a la misma rama**. Lo único que los
diferencia es una variable de entorno.

| | Demo | Producción |
|---|---|---|
| Variable `VITE_DEMO_MODE` | `true` | **sin definir** |
| Variable `VITE_API_BASE_URL` | no hace falta | la URL del backend del cliente |
| Comando de build | `npm test && npm run build` | `npm run build` |
| Qué se despliega | La demo sin backend | La aplicación real |

Compartir rama significa que **la demo se actualiza sola** con cada cambio. La
alternativa —una rama por proyecto— da control sobre cuándo se actualiza, a
cambio de mantener dos ramas y acordarse de pasar los cambios; en la práctica
termina en una demo que muestra un producto de hace meses.

## Por qué el build de la demo corre las pruebas primero

Compartir rama tiene un riesgo: agregar una pantalla que consulte algo nuevo
hace que producción ande y la demo se rompa, y se publica sola.

Por eso el comando de build de la demo es `npm test && npm run build`: una
prueba en rojo aborta el despliegue. **Una demo vieja online es mejor que una
demo rota online.**

La red de contención concreta es `frontend/src/demo/recorrido.test.js`, que
recorre las 23 rutas que las pantallas consultan al cargar. Si alguna deja de
responder, el despliegue falla antes de publicarse.

## Las dos advertencias que importan

**No definir `VITE_DEMO_MODE` en el proyecto de producción.** Es el único error
que convierte el producto en la demo de cara a un cliente. Las variables son por
proyecto, así que alcanza con no tocarla ahí — pero conviene revisarlo el día
que se cree el segundo proyecto.

**El plan gratuito de Vercel es para uso no comercial.** La demo cae cómoda ahí.
El día que haya un cliente pagando sobre el proyecto de producción, ese proyecto
debería pasar a un plan pago según sus propios términos.

## Antes de publicar, dos comprobaciones

**Que la demo funcione sin backend.** Con el backend apagado:

```bash
cd frontend
VITE_DEMO_MODE=true npm run build
npx vite preview --port 4200
```

Recorrer los dos circuitos y confirmar en la pestaña de red del navegador que
**no sale ningún pedido** a ningún servidor.

**Que el dataset no llegue al cliente.** Esto ya se rompió una vez —un import
estático desde el aviso superior metió los 426 KB del dataset dentro del paquete
de producción— así que conviene verificarlo cada vez que se toque algo del
módulo de demo:

```bash
cd frontend
rm -rf dist && VITE_DEMO_MODE=false npm run build
grep -l "_generado" dist/assets/*.js && echo "PROBLEMA: el dataset entró" || echo "ok"
```

Con la bandera apagada tienen que emitirse **sólo** el paquete de la aplicación y
su hoja de estilos. Si aparece un archivo `dataset-*.js` o `demo-*.js`, hay un
import que el empaquetador no pudo descartar: buscar quién importa
`src/demo/index.js` o `src/demo/dataset.json` sin la guarda
`import.meta.env.VITE_DEMO_MODE === "true"`.

## Lo que hoy está publicado y conviene bajar

El backend viejo del demo en Render está **suspendido** y el frontend de Vercel
apunta a él: quien entre desde la landing recibe un error de conexión. Hasta
publicar esta demo, conviene bajar el enlace de la landing o apuntarlo acá.

## Regenerar el dataset

Cuando cambie el sistema o se quiera refrescar el edificio de la demo:

```bash
DEMO_SEED_PASSWORD=... SUPER_ADMIN_EMAIL=... SUPER_ADMIN_PASSWORD=... \
DATABASE_URL=sqlite:///./demo.db SEED_ENABLED=false \
  python -m backend.seed_demo --reset --exportar
```

Tarda unos dos minutos. Deja actualizados `frontend/src/demo/dataset.json`, los
PDF de `frontend/public/demo-pdfs/` y las imágenes de
`frontend/public/demo-comprobantes/`. Los tres se versionan.

**No hace falta regenerarlo periódicamente:** la demo corre las fechas del
dataset al día de la visita, así que no envejece sola.

**Si el comando corta con un error del exportador**, es a propósito: alguna
ruta declarada en `backend/export_demo.py` contestó 404 o 405. El mensaje dice
cuál. Sin esa verificación el cuerpo del error se guardaba en el dataset como
si fueran datos y la pantalla que lo consume aparecía vacía sin que nadie se
enterara.

Después de regenerar conviene correr `pytest tests/test_dataset_demo_curado.py`:
audita la base recién generada (caja en positivo, morosidad plausible, cada
gasto con un proveedor de su rubro, el circuito de trabajos completo).
