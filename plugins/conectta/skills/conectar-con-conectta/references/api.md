# API de Conectta para una herramienta conectada

Todo lo de este archivo está leído del código de Conectta (octubre de 2026). Si algo no aparece aquí, la clave de una herramienta no lo puede hacer: no hay que suponerlo.

## Índice

1. El código de conexión `cnx_`
2. Autenticación y dirección base
3. Las 19 rutas que abre la clave
4. Escribir a un cliente por WhatsApp
5. Saber si un mensaje llegó
6. Mandar pedidos
7. Límites

---

## 1. El código de conexión `cnx_`

Cuando el cliente pulsa «Conectar» en Ajustes → Herramientas conectadas, Conectta le enseña **una sola vez** un código que pega en la herramienta. Formato:

```
cnx_ + JSON en Base64 para URL (alfabeto con - y _), SIN relleno "="
```

No va cifrado: quien lo tenga puede usar la clave. Guardarlo como una contraseña (gestor de secretos, variable de entorno, columna cifrada). Nunca en el repositorio ni en el navegador.

Campos (versión `v: 1`):

| Campo | Tipo | Qué es |
|---|---|---|
| `v` | número | Versión del formato. Hoy `1`. Rechazar otras. |
| `herramienta` | texto o `null` | Identificador en el catálogo (`"luja"`). `null` si el cliente eligió «Otra herramienta». |
| `api` | texto | Dirección de Conectta sin `/` final (puede ser un dominio de marca blanca). |
| `cuenta` | número | Id de la cuenta del cliente. |
| `bandeja` | número o `null` | Id de la bandeja con la que escribe la herramienta (la que eligió el cliente o la WhatsApp principal). `null` si la cuenta no tiene WhatsApp. |
| `clave` | texto | La clave de la herramienta. Va en la cabecera `api_access_token`. |
| `pedidos` | texto | Dirección completa donde la herramienta manda sus pedidos (`{api}/webhooks/entrada/{token}`). |
| `secreto` | texto | Con él se comprueba la firma de los avisos y se firman los pedidos. |

Ejemplo (datos inventados):

```json
{
  "v": 1,
  "herramienta": "luja",
  "api": "https://conectta.me",
  "cuenta": 42,
  "bandeja": 7,
  "clave": "Xk7pQ2mN9vR4tW8yB3cF6hJ1",
  "pedidos": "https://conectta.me/webhooks/entrada/3f6b1c2e-8a4d-4e7b-9c1a-5d2e7f8a9b0c",
  "secreto": "c3f9a1e7b2d84f6a9e0c5b7d1f3a8e2c4b6d9f0a1e3c5b7d"
}
```

Leerlo: ver `assets/node/conectta.mjs` (`readConnectionCode`), `assets/python/conectta.py` (`read_connection_code`) o `assets/php/conectta.php` (`conectta_leer_codigo`).

**Cuándo cambia.** «Clave nueva» y «Volver a conectar» generan a la vez clave, secreto **y** dirección de pedidos nuevos; los viejos dejan de servir en el acto (la clave vieja responde `401`, la dirección vieja `404`). La herramienta debe dejar pegar un código nuevo en cualquier momento y sustituir los datos juntos. Guardar los datos por cuenta de Conectta (`cuenta`): una herramienta con muchos clientes tiene un código por cliente.

**Una dirección de avisos por cuenta.** Dentro de una cuenta, cada dirección de avisos solo puede estar una vez. Lo más simple es que la herramienta dé a cada cliente una dirección propia (por ejemplo `https://mi-herramienta.com/conectta/avisos/{id-del-cliente}`) y con ella sepa qué `secreto` usar para comprobar la firma.

---

## 2. Autenticación y dirección base

- Dirección base: `{api}/api/v1/accounts/{cuenta}`.
- Cabecera: `api_access_token: {clave}`. También vale `Authorization: Bearer {clave}`.
- Cuerpo y respuesta en JSON (`Content-Type: application/json`).

```bash
curl https://conectta.me/api/v1/accounts/42/inboxes/7 \
  -H "api_access_token: $CONECTTA_CLAVE"
```

La clave es la identidad de la herramienta dentro de la cuenta: lo que manda sale en el chat con el nombre (y el logo) de la herramienta, y el cliente la revoca sin tocar la clave de nadie. Solo funciona mientras la conexión está activa y el plan trae la casilla «Herramientas conectadas». No necesita la casilla «Acceso a la API».

Errores de autenticación y plan: ver `errores.md`.

---

## 3. Las 19 rutas que abre la clave

Rutas relativas a `{api}/api/v1/accounts/{cuenta}`. Cualquier otra ruta o método responde `401` («Access to this endpoint is not authorized for bots»). En particular **no** puede: listar conversaciones, ver las conversaciones de un contacto, borrar nada, tocar ajustes, equipo, facturación, webhooks ni plantillas por su ruta propia.

### Contactos

| Método y ruta | Para qué | Cuerpo / parámetros |
|---|---|---|
| `GET /contacts` | Contactos de la cuenta, por páginas | `?page=2` |
| `GET /contacts/search?q={texto}` | Buscar por nombre, teléfono o correo (contiene, sin distinguir mayúsculas) | `q` obligatorio; el `+` va como `%2B` |
| `GET /contacts/{id}` | Ver un contacto | — |
| `POST /contacts` | Crear un contacto | `{"inbox_id": 7, "name": "Ana Gómez", "phone_number": "+573001234567", "email": "ana@ejemplo.com"}` |
| `PATCH /contacts/{id}` | Cambiar nombre, correo, atributos (los `custom_attributes` se suman a los que ya tiene) | `{"name": "...", "email": "...", "custom_attributes": {...}}` |
| `POST /contacts/{id}/contact_inboxes` | Dejar listo un contacto para otra bandeja | `{"inbox_id": 7}` |
| `GET /contacts/{id}/labels` | Sus etiquetas | — |
| `POST /contacts/{id}/labels` | Poner etiquetas (lista completa, reemplaza) | `{"labels": ["cliente", "vip"]}` |

Respuestas:

- `POST /contacts` → `200` con `{"payload": {"contact": {"id": 129, "name": "Ana Gómez", "phone_number": "+573001234567", ...}, "contact_inbox": {"source_id": "573001234567", ...}}}`.
- `GET /contacts` y `GET /contacts/search` → `{"meta": {"count": 1, "current_page": 1}, "payload": [ {contacto}, ... ]}`.
- `phone_number` en formato internacional: `+`, indicativo y solo dígitos. Si no, `422`.
- Teléfono (o correo) ya usado en la cuenta → `422` («Phone number has already been taken»). Buscar con `GET /contacts/search?q=%2B573001234567` y quedarse con el que tenga `phone_number` exactamente igual.

### Conversaciones

| Método y ruta | Para qué | Cuerpo |
|---|---|---|
| `POST /conversations` | Abrir una conversación (y opcionalmente mandar el primer mensaje) | `{"inbox_id": 7, "contact_id": 129, "message": {...}}` |
| `GET /conversations/{id}` | Ver una conversación (incluye `can_reply`, `status`, `custom_attributes`, `labels`) | — |
| `PATCH /conversations/{id}` | Cambiar **solo** la prioridad | `{"priority": "urgent"}` (`urgent`, `high`, `medium`, `low` o `null`) |
| `POST /conversations/{id}/toggle_status` | Resolver, reabrir o dejar pendiente | `{"status": "resolved"}` (`open`, `resolved`, `pending`) |
| `POST /conversations/{id}/custom_attributes` | Guardar atributos propios. **Se suman** a los que ya hay (no borra claves) | `{"custom_attributes": {"pedido_luja": "PED-1042"}}` |
| `GET /conversations/{id}/labels` | Sus etiquetas | — |
| `POST /conversations/{id}/labels` | Poner etiquetas (lista completa) | `{"labels": ["pedido"]}` |
| `POST /conversations/{id}/assignments` | Asignar a un agente o a un equipo | `{"assignee_id": 3}` o `{"team_id": 2}` |

- `{id}` es el **número de conversación de la cuenta** (`display_id`): el `id` que devuelve `POST /conversations`, `conversation.id` en los avisos del chat y `conversation_display_id` en los avisos de negocio. Nunca `conversation_id` de los avisos de negocio (ese es interno).
- `POST /conversations` → `200` con la conversación: `{"id": 27, "inbox_id": 7, "status": "open", "can_reply": false, ...}`. Guardar `id`.
- **Abre una conversación nueva cada vez**, salvo que la bandeja esté configurada como «una sola conversación por contacto» (`lock_to_single_conversation: true` en `GET /inboxes/{id}`). La clave no puede buscar la conversación abierta de un contacto, así que hay que guardar el `id` por contacto (o tomarlo de los avisos `conversation_created` / `message_created`) y reutilizarlo.
- Si el contacto existe pero no tenía relación con esa bandeja, `POST /conversations` la crea sola con `contact_id` + `inbox_id`.

### Mensajes

| Método y ruta | Para qué | Cuerpo |
|---|---|---|
| `GET /conversations/{id}/messages` | Mensajes de la conversación, cada uno con su `status` | `?before={id}` / `?after={id}` (ver abajo) |
| `POST /conversations/{id}/messages` | Mandar texto o plantilla | ver sección 4 |

Respuesta de `POST /messages` (`200`, recortada):

```json
{
  "id": 341, "content": "¡Listo, Ana! Tu pedido PED-1042 ya salió.", "inbox_id": 7,
  "conversation_id": 27, "message_type": 1, "content_type": "text",
  "status": "sent", "content_attributes": {}, "created_at": 1761568089,
  "private": false, "source_id": null,
  "sender": { "id": 5, "name": "Luja", "type": "agent_bot" }
}
```

Aquí `message_type` va como número: `0` entrante, `1` saliente, `2` actividad, `3` plantilla. `GET /messages` devuelve `{"meta": {...}, "payload": [mensajes]}` con la misma forma.

Paginación de `GET /messages`, siempre del más viejo al más nuevo:
- Sin parámetros: los **20 últimos**.
- `?before={id}`: los 20 anteriores a ese mensaje.
- `?after={id}`: hasta 100 posteriores.

Para mirar un mensaje concreto: `?after={id-1}` y tomar el primero.

Para una nota interna (no sale al cliente): `{"content": "...", "private": true}`.

### Bandeja

| Método y ruta | Para qué |
|---|---|
| `GET /inboxes/{id}` | Ver una bandeja. Si es de WhatsApp (`channel_type: "Channel::Whatsapp"`), trae sus plantillas en `message_templates` y el número en `phone_number`. |

La clave no tiene `GET /inboxes` (listado) ni `/inboxes/{id}/message_templates`: usar la `bandeja` del código.

---

## 4. Escribir a un cliente por WhatsApp

Regla de WhatsApp: texto libre solo dentro de las 24 h siguientes al último mensaje del cliente. Fuera de esa ventana, o a alguien que nunca escribió, **plantilla aprobada por Meta**. `can_reply` de la conversación dice si la ventana está abierta. Fuera de ventana, el texto libre se acepta (`200`) pero luego queda `failed`.

### 4.1 Plantillas disponibles

`GET /inboxes/{bandeja}` → `message_templates`. Usar solo las de `"status": "APPROVED"`.

Las plantillas no se crean en Conectta ni con la clave. Se crean y se aprueban en WhatsApp (en el administrador de WhatsApp de Meta o en el del proveedor). En Conectta se ven en **Ajustes → Plantillas**, con el botón «Sincronizar plantillas». Si la herramienta necesita una, el comercio la crea allí y la sincroniza.

```json
{ "name": "pedido_confirmado", "language": "es", "status": "APPROVED", "category": "UTILITY",
  "parameter_format": "POSITIONAL",
  "components": [{ "type": "BODY", "text": "Hola {{1}}, recibimos tu pedido {{2}} por {{3}}. Te avisamos cuando salga." }] }
```

### 4.2 A un número nuevo: contacto → conversación → plantilla

```bash
# 1. Contacto (si da 422, buscarlo con /contacts/search)
curl -X POST "$BASE/contacts" -H "api_access_token: $CLAVE" -H "Content-Type: application/json" \
  -d '{"inbox_id": 7, "name": "Ana Gómez", "phone_number": "+573001234567"}'

# 2. Conversación (guardar el id)
curl -X POST "$BASE/conversations" -H "api_access_token: $CLAVE" -H "Content-Type: application/json" \
  -d '{"inbox_id": 7, "contact_id": 129}'

# 3. Plantilla
curl -X POST "$BASE/conversations/27/messages" -H "api_access_token: $CLAVE" -H "Content-Type: application/json" \
  -d '{
    "content": "Hola Ana, recibimos tu pedido PED-1042 por $89.900. Te avisamos cuando salga.",
    "template_params": {
      "name": "pedido_confirmado",
      "category": "UTILITY",
      "language": "es",
      "processed_params": { "body": { "1": "Ana", "2": "PED-1042", "3": "$89.900" } }
    }
  }'
```

Los pasos 2 y 3 pueden ir juntos: `POST /conversations` acepta `"message": {"content": ..., "template_params": {...}}`.

Campos de la plantilla:

| Campo | Qué es |
|---|---|
| `content` | El texto tal como lo leerá el cliente (variables ya puestas). Es lo que queda en el chat. |
| `template_params.name` | Nombre de la plantilla aprobada. |
| `template_params.language` | Idioma tal como está en la plantilla (`es`, `pt_BR`…). |
| `template_params.category` | Categoría (`UTILITY`, `MARKETING`…). |
| `template_params.processed_params.body` | Variables del cuerpo: `{"1": "Ana", "2": "PED-1042"}`. Si la plantilla usa variables con nombre, la clave es el nombre. |
| `template_params.processed_params.header` | Cabecera con medio: `{"media_url": "https://…", "media_type": "image"}` (`image`, `video`, `document`). |
| `template_params.processed_params.buttons` | Botón con URL variable: `[{"type": "url", "parameter": "PED-1042"}]`. |

### 4.3 Dentro de la ventana de 24 h

```bash
curl -X POST "$BASE/conversations/27/messages" -H "api_access_token: $CLAVE" -H "Content-Type: application/json" \
  -d '{"content": "¡Listo, Ana! Tu pedido PED-1042 ya salió. Llega mañana."}'
```

---

## 5. Saber si un mensaje llegó

`200` en `POST /messages` solo dice que Conectta lo aceptó; el envío a WhatsApp va justo después.

- Aviso `message_updated` (si la conexión lo recibe): el estado va en `conversation.messages[0].status` (`sent`, `delivered`, `read`, `failed`) y el motivo de un fallo en `content_attributes.external_error`. `conversation.messages[0]` es el **último** mensaje del chat: comprobar que su `id` coincide con el `id` del aviso; si no, preguntar con `GET`.
- O preguntar: `GET /conversations/{id}/messages?after={id-1}` → el primero de la lista es ese mensaje, con su `status`; `source_id` es el id del mensaje en WhatsApp. Sin `after` solo vienen los 20 últimos.

Ojo: «Se actualizó un mensaje» (`message_updated`) no viene marcado por defecto en Luja; el cliente lo añade con «Editar avisos».

---

## 6. Mandar pedidos

Un `POST` con JSON a la dirección `pedidos` del código. **No lleva la clave**: la dirección ya identifica la conexión.

### 6.1 Formato estándar

Salvo que la ficha de la herramienta en el catálogo de Conectta diga otra cosa (lo decide Conectta en su Super Admin), el pedido es:

```json
{
  "id": "PED-1042",
  "status": "paid",
  "total": 59900,
  "currency": "COP",
  "customer": { "name": "Ana Gómez", "phone": "+573001234567", "email": "ana@ejemplo.com" }
}
```

| Campo | Regla |
|---|---|
| `id` | Referencia única del pedido. Hace falta para no duplicar y para anotar la venta. |
| `status` | Solo `"paid"` (mayúsculas o minúsculas da igual) mete la venta en el libro. Cualquier otro valor guarda contacto y conversación, nada más. |
| `total` | Número sin separador de miles (`59900` o `59900.5`). Conectta borra lo que no sea dígito, punto o coma y convierte la coma en punto: `"59.900"` se leería como 59,9. |
| `currency` | Código de moneda. `COP` si no viene. |
| `customer.phone` | **Obligatorio.** Con `+` e indicativo. Sin él el pedido queda «fallido». El formato estándar no añade indicativo: un número local de 10 dígitos se guardaría tal cual. |
| `customer.name` | Nombre del comprador (si el contacto ya tiene uno de verdad, no se cambia). |
| `customer.email` | Correo (solo se rellena si el contacto no tenía). |

Se pueden mandar más campos (líneas, dirección…): Conectta los guarda en el registro del pedido y no hacen daño.

### 6.2 Firma

Firmar **siempre** con el `secreto`:

```
X-Conectta-Signature: base64( HMAC-SHA256( secreto, cuerpo_crudo ) )
```

Sin prefijo y sin timestamp. Firmar exactamente los bytes que se mandan (serializar una vez y mandar esa misma cadena). Las herramientas del catálogo (`herramienta` distinto de `null`) **tienen** que firmar: sin firma o con una que no coincide, `401`. Para «Otra herramienta» Conectta no comprueba la firma, así que firmar no molesta y deja el código igual para todos.

No es la misma firma que la de los avisos (ver `verificacion-de-avisos.md`).

### 6.3 Respuestas

| Código | Cuerpo | Qué significa |
|---|---|---|
| `200` | `{"status": "queued"}` | Recibido; se procesa en segundo plano. |
| `200` | `{"status": "inactive"}` | La conexión está desconectada; queda anotado y no se hace nada. |
| `200` | `{"status": "sample_stored"}` | La dirección estaba en «modo escucha» (no pasa en una conexión normal). |
| `400` | — | Cuerpo vacío o que no es un objeto JSON. |
| `401` | — | Falta la firma o no coincide. |
| `404` | — | La dirección ya no existe (clave nueva o reconexión): pedir el código nuevo. |
| `429` | — | Más de 300 pedidos en un minuto a esa dirección. Esperar y reintentar. |

`200` no garantiza que el pedido se guardara bien: el resultado solo lo ve el cliente en la tarjeta de la herramienta («Último pedido recibido»: Guardado, WhatsApp enviado, Omitido, Falló, En cola) y, si la herramienta los recibe, llegan los avisos `conversation_created` / `sale_created`. La clave no puede leer el registro de pedidos.

Reintentar con el mismo `id` es seguro (ver 6.4). Reintentar ante `429`, `5xx` o error de red; no ante `400`, `401` o `404`.

### 6.4 Qué hace Conectta con cada pedido

1. Si la cuenta no tiene plan o prueba vigente, o el plan no trae «Herramientas conectadas»: lo anota como omitido.
2. Lee `customer.phone` y lo deja en dígitos. Sin teléfono (menos de 8 dígitos): fallido.
3. Mira si ya llegó otro pedido con el mismo `id`:

| Llega | Resultado |
|---|---|
| primera vez, sin pagar | contacto + conversación, sin venta («Guardado») |
| primera vez, pagado | contacto + conversación + **venta** («Guardado») |
| antes sin pagar, ahora pagado | **venta** en la conversación que ya se abrió («Guardado») |
| antes pagado, ahora pagado otra vez | nada nuevo («Omitido»): nunca dos ventas |
| antes sin pagar, ahora sin pagar | nada nuevo («Omitido») |

4. Contacto: lo busca por teléfono; si no existe lo crea con nombre y correo; si existe solo rellena huecos.
5. Conversación: usa la abierta o pendiente **más reciente** de ese contacto en la bandeja de WhatsApp de la conexión. Si no hay ninguna, abre una (y sale `conversation_created`); si reutiliza una, no sale ningún aviso. Por eso, si la herramienta va a escribir al comprador, le conviene abrir o reutilizar la conversación **antes** de mandar el pedido: la venta cae en esa misma conversación y la herramienta ya conoce su número. Si la bandeja de la conexión no es de WhatsApp, o la cuenta no tiene WhatsApp, no hay conversación (la venta queda sin conversación).
6. Venta (solo si viene pagado): entra al libro como confirmada, verificada por la pasarela, con `payment_reference` = `id`. La tarjeta del Kanban pasa a «convertido». Salen los avisos `sale_created` y `kanban_stage_changed`.
7. **No manda ningún WhatsApp** con el formato estándar: escribir al comprador lo hace la herramienta con su clave (sección 4). Solo si Conectta configuró una plantilla de confirmación en la ficha de la herramienta manda él la plantilla con el primer aviso del pedido.

Un pedido mandado así **no** crea un «pedido» en el módulo de pedidos de Conectta: por eso no dispara `order_status_changed`.

---

## 7. Límites

- Dirección de pedidos: 300 peticiones por minuto por dirección (`429` al pasarse).
- API en general: límite por IP de la instancia (3000 peticiones por minuto por defecto).
- Avisos: Conectta espera la respuesta unos 5 segundos; ver `verificacion-de-avisos.md`.
- No hay más límites por clave en el código.
