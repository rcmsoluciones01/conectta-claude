# Errores y cómo diagnosticarlos

Guiarse por el código HTTP y el campo `code`: el texto de `error` puede venir en el idioma de la cuenta.

## 1. Llamadas a la API con la clave

Conectta comprueba en este orden; la primera que falla decide la respuesta:

| # | Comprobación | Respuesta | Qué hacer |
|---|---|---|---|
| 1 | La clave existe | `401` `{"error": "Invalid Access Token"}` | Clave mal copiada, o el cliente pulsó «Clave nueva» / «Desconectar». Pedir el código nuevo. |
| 2 | La ruta está entre las 19 permitidas | `401` `{"error": "Access to this endpoint is not authorized for bots"}` | La clave no puede hacer eso. Ver la lista en `api.md` §3; no hay alternativa con esta clave. |
| 3 | La cuenta de la URL es la de la clave | `401` `{"error": "Bot is not authorized to access this account"}` · `404` si la cuenta no existe | Usar `cuenta` del código en la ruta. |
| 4 | La cuenta tiene plan o prueba vigente | `402` `{"code": "cuenta_sin_plan"}` | El cliente tiene que pagar o renovar en Conectta. |
| 5 | El plan trae «Herramientas conectadas» | `403` `{"code": "conexiones_no_incluidas"}` | El cliente tiene que pasarse a un plan que la traiga. |
| 6 | El recurso existe en esa cuenta | `404` `{"error": "Resource could not be found"}` | Id equivocado. ¿Se usó `conversation_id` (interno) en vez del número de conversación? |
| 7 | Los datos son válidos | `422` `{"message": "...", "attributes": [...]}` | Leer el mensaje. Típicos: teléfono ya usado o sin formato `+indicativo`, correo ya usado, `q` vacío en la búsqueda. |

Una cuenta suspendida responde `401` («Account is suspended»).

Conviene que la herramienta trate `401` y `403` como «conexión rota»: dejar de reintentar, marcar la conexión del cliente como caída y pedirle que revise Ajustes → Herramientas conectadas. `402` y `429` sí pueden reintentarse más tarde.

## 2. Mensajes que no llegan

`POST /messages` responde `200` aunque WhatsApp lo rechace después. El resultado llega en `message_updated` (`conversation.messages[0].status` y `content_attributes.external_error`) o en `GET /conversations/{id}/messages?after={id-1}` (el primero es ese mensaje).

| Síntoma | Causa más común |
|---|---|
| `status: "failed"` con texto libre | Fuera de la ventana de 24 h (`can_reply: false`). Mandar plantilla. |
| `failed` con plantilla | Plantilla no aprobada, nombre o idioma distintos, número de variables distinto. Revisar con `GET /inboxes/{bandeja}`. |
| El mensaje sale en otra bandeja | Se abrió la conversación con otro `inbox_id`. Usar `bandeja` del código. |
| Dos conversaciones para el mismo cliente | Se llamó a `POST /conversations` dos veces. Guardar y reutilizar el `id`. |

## 3. Pedidos

| Respuesta | Causa | Qué hacer |
|---|---|---|
| `400` | Cuerpo vacío o que no es un objeto JSON | Mandar un objeto JSON con `Content-Type: application/json`. |
| `401` | Falta `X-Conectta-Signature` o no coincide | Firmar en Base64 el cuerpo exacto que se manda, con el `secreto` del último código. No usar la firma de los avisos. |
| `404` | La dirección cambió (clave nueva o reconexión) | Pedir el código nuevo y usar su `pedidos`. |
| `429` | Más de 300 pedidos por minuto | Esperar y reintentar con espera creciente. |
| `200 {"status": "inactive"}` | La conexión está desconectada | El cliente tiene que «Volver a conectar». |
| `200 {"status": "queued"}` | Recibido | El resultado lo ve el cliente en la tarjeta; ver abajo. |

Estados del pedido en la tarjeta («Último pedido recibido»):

| Estado en pantalla | Interno | Significa |
|---|---|---|
| En cola | `pending` | Aún no se procesó. |
| Guardado | `recorded` | Contacto y conversación guardados; venta anotada si venía pagado. |
| WhatsApp enviado | `sent` | Solo si Conectta tiene una plantilla de confirmación para la herramienta. |
| Omitido | `skipped` | Pedido repetido, plan sin la casilla o sin plan vigente, o conexión desconectada. |
| Falló | `failed` | Sin teléfono, o sin WhatsApp conectado cuando hacía falta mandar plantilla. |

Venta que no aparece aunque el pedido salió «Guardado»: `status` no era `"paid"`, faltaba `id`, o ya existía una venta con esa referencia.

## 4. Avisos que no llegan

| Síntoma | Causa |
|---|---|
| No llega nada | Sin «Dirección de avisos» en la conexión, el evento no está marcado, la cuenta no tiene plan vigente o el plan perdió «Herramientas conectadas». |
| La tarjeta dice «Con fallos» | El último aviso no se entregó tras los reintentos; el motivo sale en «Último aviso enviado». |
| La firma nunca coincide | Se firma el JSON re-serializado en vez del cuerpo crudo, se usa la fórmula de los pedidos, o el `secreto` es de un código viejo. |
| Llegan repetidos | Reintentos: deduplicar por `X-Conectta-Delivery`. |
| No llega a `localhost` | Conectta no avisa a redes privadas: usar un túnel público. |
| Llegan mis propios mensajes | Es normal: filtrar `message_type: "outgoing"`. |
