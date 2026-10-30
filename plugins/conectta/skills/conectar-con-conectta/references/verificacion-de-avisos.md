# Recibir y verificar los avisos

Cómo montar el receptor de la «Dirección de avisos»: comprobar que el aviso es de Conectta, responder a tiempo, aguantar los reintentos y no procesar dos veces.

## 1. Las cabeceras

Cada aviso es un `POST` con `Content-Type: application/json` y estas cabeceras:

| Cabecera | Qué lleva |
|---|---|
| `X-Conectta-Signature` | `sha256=` + HMAC-SHA256 en **hexadecimal** de `{timestamp}.{cuerpo}` con el `secreto` de la conexión. |
| `X-Conectta-Timestamp` | Segundos Unix del envío. Cambia en cada intento. |
| `X-Conectta-Delivery` | Id de la entrega (UUID). **Igual en todos los intentos** del mismo aviso. |

Pueden llegar otras cabeceras con el mismo valor y otro prefijo: ignorarlas y usar solo las `X-Conectta-*`.

## 2. El algoritmo

```
mensaje   = X-Conectta-Timestamp + "." + cuerpo_crudo
esperada  = "sha256=" + hex( HMAC_SHA256( clave = secreto, datos = mensaje ) )
válido    = comparación_en_tiempo_constante(X-Conectta-Signature, esperada)
            y |ahora - X-Conectta-Timestamp| <= 300 segundos
```

Reglas:

1. **Cuerpo crudo**: los bytes tal como llegaron, antes de convertirlos en JSON. Volver a serializar el JSON cambia espacios u orden y la firma ya no coincide.
2. **Comparación en tiempo constante** (`crypto.timingSafeEqual`, `hmac.compare_digest`, `hash_equals`).
3. **Rechazar avisos de más de 5 minutos** (o del futuro) para que no se pueda repetir uno capturado.
4. Firma mala → responder `401` y no hacer nada. Conectta no reintenta un `4xx` distinto de `408` y `429`.
5. El `secreto` cambia cuando el cliente pulsa «Clave nueva» o «Volver a conectar»: hay que guardar el del último código. Cada aviso se firma con el secreto que había **cuando se generó**, y sus reintentos también. De ahí salen dos consejos para no perder avisos en el cambio:
   - Mientras el cliente no pegue el código nuevo, los avisos nuevos fallan la firma. Si a esos se les responde `503` en vez de `401`, Conectta los reintenta durante unos 12 minutos (30 s, 2 min y 10 min), y si el código se pega a tiempo, entran. Un aviso falso no se reintenta, así que esto no abre ningún agujero. Lo mismo sirve para una dirección de avisos cuyo cliente todavía no pegó su código.
   - Después de pegarlo, aceptar también durante unos 15 minutos la firma con el secreto anterior: los reintentos de avisos generados antes del cambio siguen llegando firmados con él.

Funciones listas: `assets/node/conectta.mjs` (`verifyEvent`), `assets/python/conectta.py` (`verify_event`), `assets/php/conectta.php` (`conectta_verificar_aviso`). Receptores completos: `assets/node/servidor-avisos.mjs`, `assets/python/servidor_avisos.py`, `assets/php/recibir-aviso.php`.

### Cómo leer el cuerpo crudo según el framework

| Framework | Cuerpo crudo |
|---|---|
| Node `http` | juntar los `chunk` del `req` en un `Buffer` |
| Express | `express.raw({ type: 'application/json' })` en esa ruta (no `express.json()`); `req.body` es un `Buffer` |
| Fastify | `addContentTypeParser('application/json', { parseAs: 'buffer' }, …)` o el plugin `fastify-raw-body` |
| Next.js (App Router) | `await request.text()` antes de `JSON.parse` |
| Flask | `request.get_data()` |
| FastAPI / Starlette | `await request.body()` |
| Django | `request.body` |
| PHP puro | `file_get_contents('php://input')` |
| Laravel | `$request->getContent()` |

## 3. Responder a tiempo

- Conectta espera la respuesta unos **5 segundos**. Responder `2xx` enseguida y procesar después (cola, trabajo en segundo plano, `setImmediate`…).
- Reintenta a los **30 s, 2 min y 10 min** (cuatro intentos en total) si se agota el tiempo, no conecta o la respuesta es `408`, `429`, `500`, `502`, `503` o `504`.
- Cualquier otro `4xx` (o `501`) es un «no» y no se repite.
- Tras el último intento fallido el aviso se pierde. La tarjeta de la herramienta en Conectta pasa a «Con fallos» y enseña el evento, la hora y el motivo.

## 4. No procesar dos veces

`X-Conectta-Delivery` es el mismo en todos los intentos. Guardarlo (base de datos o Redis, con caducidad de un día) y descartar lo ya procesado, respondiendo `200` igualmente.

Además, para lo que importa de verdad usar claves de negocio: el `id` de la venta, el `id` del mensaje o la referencia del pedido. Un mismo hecho puede llegar en varios avisos distintos (`sale_created` y luego `sale_updated`).

## 5. No depender del orden

Un reintento puede llegar después de un aviso más nuevo. Comparar `at` / `created_at` y no retroceder estados.

## 6. Dirección pública

Conectta no manda avisos a redes privadas (`localhost`, `127.0.0.1`, `192.168.x.x`, `10.x.x.x`…). Para probar en local, abrir un túnel con dirección pública (por ejemplo `cloudflared tunnel --url http://localhost:3000` o `ngrok http 3000`) y poner esa dirección en «Editar avisos». La pantalla exige una dirección completa que empiece por `http://` o `https://` y tenga dominio con punto; en producción, `https://`.

## 7. Las dos firmas, para no confundirlas

| | Avisos (Conectta → herramienta) | Pedidos (herramienta → Conectta) |
|---|---|---|
| Cabecera | `X-Conectta-Signature` | `X-Conectta-Signature` |
| Secreto | `secreto` del código | `secreto` del código |
| Qué se firma | `{timestamp}.{cuerpo}` | solo el cuerpo |
| Formato | `sha256=` + hexadecimal | Base64, sin prefijo |
| Timestamp | `X-Conectta-Timestamp` | no lleva |
