# Los avisos que Conectta manda a la herramienta

Conectta hace un `POST` con JSON a la «Dirección de avisos» de la conexión cada vez que pasa en la cuenta algo de lo que el cliente marcó. Firma, cabeceras, reintentos y cómo responder: `verificacion-de-avisos.md`.

## Índice

1. Qué avisos se pueden recibir
2. Avisos de negocio (forma común y uno por uno)
3. Avisos del chat
4. Trampas conocidas

---

## 1. Qué avisos se pueden recibir

El cliente los elige al conectar («Avisos que recibe» → «Cambiar avisos») y los cambia después con «Editar avisos». Sin dirección de avisos no sale ninguno.

| Evento | Nombre en la pantalla | Grupo | Luja por defecto |
|---|---|---|---|
| `sale_created` | Venta confirmada | negocio | sí |
| `sale_updated` | Cambió el estado de una venta | negocio | sí |
| `appointment_booked` | Cita agendada | negocio | sí |
| `appointment_updated` | Cambió el estado de una cita | negocio | sí |
| `order_status_changed` | Cambió la fase de un pedido | negocio | sí |
| `kanban_stage_changed` | Cambio de etapa en el Kanban | negocio | sí |
| `contact_opted_out` | Pidió que no le escriban | negocio | no |
| `message_created` | Mensaje nuevo | chat | sí |
| `message_updated` | Se actualizó un mensaje | chat | no |
| `conversation_created` | Conversación nueva | chat | sí |
| `conversation_status_changed` | Cambió el estado de la conversación | chat | no |
| `conversation_updated` | Se actualizó la conversación | chat | no |
| `contact_created` | Contacto nuevo | chat | no |
| `contact_updated` | Se actualizó un contacto | chat | no |

Para una herramienta conectada, los avisos de negocio llegan con la casilla «Herramientas conectadas» del plan (no hace falta «Eventos de negocio salientes»). Solo salen mientras la cuenta tiene plan o prueba vigente.

Lo que necesita cada caso:

- Recibir ventas: `sale_created` + `sale_updated` (ver trampa 4.1).
- Contestar a los clientes: `message_created` (solo `incoming`) y, para saber si lo propio llegó, `message_updated`.
- Saber la conversación de un pedido o de un contacto nuevo: `conversation_created`.
- Respetar bajas: `contact_opted_out`.

---

## 2. Avisos de negocio

Todos tienen la misma forma:

```json
{ "event": "sale_created", "account": { "id": 42, "name": "Tienda de Ana" }, "data": { ... } }
```

El contacto (`data.contact`) es siempre:

```json
{ "id": 129, "name": "Ana Gómez", "phone_number": "+573001234567", "email": "ana@ejemplo.com",
  "custom_attributes": {}, "tags": [] }
```

**Dos números de conversación.** `data.conversation_display_id` es el número que usa la API (`/conversations/{id}`). `data.conversation_id` es un identificador interno: no usarlo en la API. Cualquiera de los dos puede llegar `null` si la venta, cita o pedido no tiene conversación.

### `sale_created` — se registra una venta

La cierra la IA, el nodo «Cobrar», un agente, la tienda o un pedido que entró por la dirección de pedidos.

```json
{
  "event": "sale_created",
  "account": { "id": 42, "name": "Tienda de Ana" },
  "data": {
    "id": 80, "amount": 89900.0, "currency": "COP",
    "product": { "id": 7, "name": "Kit de aromaterapia" },
    "contact": { "id": 129, "name": "Ana Gómez", "phone_number": "+573001234567", "email": "ana@ejemplo.com", "custom_attributes": {}, "tags": [] },
    "conversation_id": 68, "conversation_display_id": 27,
    "closed_by": "Laura Méndez",
    "created_at": "2026-10-27T11:38:25Z"
  }
}
```

`product` puede venir con `id` y `name` en `null` (las ventas que entran por pedidos no llevan producto). `closed_by` es el nombre de quien cerró o `null`. **No trae `status`** (trampa 4.1).

### `sale_updated` — una venta cambia de estado

Estados: `pending`, `confirmed`, `refunded`, `voided`. En contra entrega, `pending → confirmed` es cuando se cobra y `pending → voided` cuando se cae.

```json
{
  "event": "sale_updated",
  "account": { "id": 42, "name": "Tienda de Ana" },
  "data": {
    "id": 80, "from": "pending", "to": "confirmed", "amount": 89900.0, "currency": "COP",
    "product": { "id": 7, "name": "Kit de aromaterapia" },
    "contact": { "id": 129, "name": "Ana Gómez", "phone_number": "+573001234567", "email": "ana@ejemplo.com", "custom_attributes": {}, "tags": [] },
    "conversation_id": 68, "conversation_display_id": 27,
    "at": "2026-10-29T15:02:11Z"
  }
}
```

### `appointment_booked` — se agenda una cita

```json
{
  "event": "appointment_booked",
  "account": { "id": 42, "name": "Tienda de Ana" },
  "data": {
    "id": 31, "starts_at": "2026-10-30T15:00:00Z", "ends_at": "2026-10-30T15:30:00Z",
    "calendar": { "id": 2, "name": "Agenda principal" },
    "contact": { "id": 129, "name": "Ana Gómez", "phone_number": "+573001234567", "email": "ana@ejemplo.com", "custom_attributes": {}, "tags": [] },
    "conversation_id": 68, "conversation_display_id": 27,
    "created_at": "2026-10-27T11:41:01Z"
  }
}
```

### `appointment_updated` — una cita cambia de estado

Estados: `pending`, `confirmed`, `rescheduled`, `cancelled`, `attended`, `no_show`.

```json
{
  "event": "appointment_updated",
  "account": { "id": 42, "name": "Tienda de Ana" },
  "data": {
    "id": 31, "from": "confirmed", "to": "cancelled", "starts_at": "2026-10-30T15:00:00Z",
    "calendar": { "id": 2, "name": "Agenda principal" },
    "contact": { "id": 129, "name": "Ana Gómez", "phone_number": "+573001234567", "email": "ana@ejemplo.com", "custom_attributes": {}, "tags": [] },
    "conversation_id": 68, "conversation_display_id": 27,
    "at": "2026-10-28T09:12:40Z"
  }
}
```

No trae `ends_at`.

### `order_status_changed` — un pedido de Conectta cambia de fase

Solo los pedidos del módulo de pedidos y la tienda **de Conectta**. Los pedidos que la herramienta manda a su dirección de pedidos no crean un pedido de ese módulo y no disparan este aviso. Fases por defecto: `received`, `preparing`, `shipped`, `delivered`, `cancelled`.

```json
{
  "event": "order_status_changed",
  "account": { "id": 42, "name": "Tienda de Ana" },
  "data": {
    "id": 12, "code": "PED-1042", "from": "preparing", "to": "shipped",
    "total": 89900.0, "currency": "COP",
    "contact": { "id": 129, "name": "Ana Gómez", "phone_number": "+573001234567", "email": "ana@ejemplo.com", "custom_attributes": {}, "tags": [] },
    "conversation_id": 68, "conversation_display_id": 27,
    "at": "2026-10-28T10:05:00Z"
  }
}
```

### `kanban_stage_changed` — la tarjeta cambia de etapa

La mueva quien la mueva (persona, flujo, agenda, pedido, la IA). `board_id` es el tablero si es uno propio y `null` en el embudo de ventas. `from` llega `null` si la tarjeta no tenía etapa guardada. Cuando entra un pedido pagado, la tarjeta pasa a `convertido`.

```json
{
  "event": "kanban_stage_changed",
  "account": { "id": 42, "name": "Tienda de Ana" },
  "data": {
    "conversation_id": 68, "conversation_display_id": 27,
    "contact": { "id": 129, "name": "Ana Gómez", "phone_number": "+573001234567", "email": "ana@ejemplo.com", "custom_attributes": {}, "tags": [] },
    "from": "en_atendimiento", "to": "convertido", "board_id": null
  }
}
```

Las etapas son textos internos del tablero de cada cuenta: no dar por hecha una lista fija.

### `contact_opted_out` — alguien pide que no le escriban

`motivo` puede ser `peticion`, `palabra_de_baja` o `stop_keyword`. La herramienta debe dejar de escribirle también por su lado.

```json
{
  "event": "contact_opted_out",
  "account": { "id": 42, "name": "Tienda de Ana" },
  "data": {
    "contact": { "id": 129, "name": "Ana Gómez", "phone_number": "+573001234567", "email": "ana@ejemplo.com", "custom_attributes": {}, "tags": ["no_contactar"] },
    "motivo": "stop_keyword"
  }
}
```

---

## 3. Avisos del chat

Llega el objeto entero (mensaje, conversación o contacto) con `event` arriba y la cuenta en `account`. Aquí `conversation.id` **sí** es el número de la API. Los ejemplos están recortados: llegan más campos y no hay que fallar si aparece uno nuevo.

### `message_created` — entra o sale un mensaje

```json
{
  "event": "message_created",
  "id": 339,
  "message_type": "incoming",
  "content": "¿Me lo pueden mandar hoy?",
  "content_type": "text",
  "content_attributes": {},
  "private": false,
  "source_id": "wamid.HBgMNTczMDAxMjM0NTY3FQIAEhgg",
  "created_at": "2026-10-27T11:48:09.278Z",
  "sender": { "id": 129, "name": "Ana Gómez", "phone_number": "+573001234567", "email": "ana@ejemplo.com" },
  "inbox": { "id": 7, "name": "WhatsApp" },
  "account": { "id": 42, "name": "Tienda de Ana" },
  "conversation": {
    "id": 27, "inbox_id": 7, "status": "open", "can_reply": true,
    "contact_inbox": { "source_id": "573001234567" },
    "custom_attributes": {}, "labels": [],
    "messages": [{ "id": 339, "status": "sent" }]
  },
  "attachments": [{ "file_type": "image", "data_url": "https://…" }]
}
```

- Arriba, `message_type` es texto: `incoming`, `outgoing` o `template` (en las respuestas de la API es número).
- `sender` cambia según quién escribe: el contacto (sin `type`), una persona del equipo (`"type": "user"`), una herramienta conectada (`"type": "agent_bot"`) o `null` (sistema).
- `attachments` solo aparece si hay adjuntos.
- **La herramienta recibe también sus propios mensajes** (`outgoing`, `sender.type: "agent_bot"`). Para no contestarse a sí misma: procesar solo `incoming` o ignorar los `outgoing`.
- Las notas internas llegan con `private: true`: no reenviarlas al cliente.

### `message_updated` — cambia un mensaje (p. ej. su estado de entrega)

Misma forma que `message_created`. El objeto de arriba no trae `status`: el estado va en `conversation.messages[0].status` (`sent`, `delivered`, `read`, `failed`) y el motivo de un fallo en `content_attributes.external_error`. `conversation.messages[0]` es el último mensaje del chat: comprobar que su `id` es el `id` del aviso.

### `conversation_created` — se abre una conversación

```json
{
  "event": "conversation_created",
  "id": 27, "inbox_id": 7, "status": "open", "can_reply": true,
  "channel": "Channel::Whatsapp",
  "contact_inbox": { "source_id": "573001234567" },
  "meta": { "sender": { "id": 129, "name": "Ana Gómez", "phone_number": "+573001234567" }, "assignee": null },
  "custom_attributes": {}, "labels": [], "messages": [],
  "account": { "id": 42, "name": "Tienda de Ana" }
}
```

El contacto va en `meta.sender`. Sirve para guardar `id` (número de conversación) por contacto, porque la clave no puede listar conversaciones.

### `conversation_status_changed` y `conversation_updated`

La conversación entera (como `conversation_created`) más `changed_attributes`:

```json
{
  "event": "conversation_updated",
  "id": 27, "inbox_id": 7, "status": "open",
  "account": { "id": 42, "name": "Tienda de Ana" },
  "changed_attributes": [
    { "custom_attributes": { "previous_value": { "kanban_stage": "en_atendimiento" }, "current_value": { "kanban_stage": "convertido" } } }
  ]
}
```

`conversation_status_changed`: se resuelve, se reabre o queda pendiente (`status`: `open`, `resolved`, `pending`, `snoozed`). `conversation_updated`: asignación, etiquetas, atributos, etapa del Kanban.

### `contact_created` y `contact_updated`

```json
{
  "event": "contact_created",
  "id": 129, "name": "Ana Gómez", "phone_number": "+573001234567", "email": "ana@ejemplo.com",
  "identifier": null, "custom_attributes": {}, "additional_attributes": {},
  "blocked": false, "avatar": "", "thumbnail": "",
  "account": { "id": 42, "name": "Tienda de Ana" }
}
```

`contact_updated` lleva además `changed_attributes` y solo sale si algo cambió de verdad.

---

## 4. Trampas conocidas

### 4.1 «Venta confirmada» no dice si la venta está cobrada

`sale_created` sale al **crear** una venta y no trae su estado. Según el código de Conectta:

- Nacen `confirmed`, el valor por defecto: las de la IA con pago verificado, las de la caja de Reservas, las de la tienda (al marcar «Pago recibido» o al entregarse) y los pedidos que la herramienta manda con `status: "paid"`. **Estas no reciben nunca `sale_updated`**, salvo que después se reembolsen o se anulen.
- Nacen `pending` solo dos tipos: las de contra entrega que cierra la IA y las de los formularios de WhatsApp (siempre). Cuando se cobran pasan a `confirmed`, y si se caen pasan a `voided`. En los dos casos llega `sale_updated` con `from: "pending"`.

Por eso **no hay que esperar a `sale_updated` para dar una venta por buena**: las confirmadas no lo reciben y se quedarían a medias para siempre. Lo que funciona hoy:

- Tratar `sale_created` como una venta (es lo normal) y corregirla cuando llegue `sale_updated`. `from: "pending"` dice que hasta ese momento no estaba cobrada; `to: "voided"` o `"refunded"`, que ya no cuenta.
- Si la herramienta necesita una contabilidad exacta, preguntar al comercio si usa contra entrega o formularios de WhatsApp. Si los usa, hoy no se puede saber al recibir el aviso si la venta está `pending` (hueco 1 de `huecos.md`).

### 4.2 El orden no está garantizado

Un reintento puede llegar después de un aviso más nuevo. Usar `at` / `created_at` y el estado `to` para no retroceder (no pasar de `confirmed` a `pending` por un aviso viejo).

### 4.3 Los avisos de vuelta

Lo que hace la herramienta también genera avisos: su mensaje dispara `message_created`, su pedido pagado dispara `conversation_created` (si abre conversación), `sale_created` y `kanban_stage_changed`. No crear otra vez un pedido al recibir el `sale_created` de un pedido propio: comparar con la referencia guardada.

### 4.4 No hay aviso de prueba para una herramienta conectada

La pantalla no tiene «Enviar una prueba» para una conexión. Para probar: cuenta de prueba de Conectta y provocar el evento de verdad (escribir al WhatsApp, mandar un pedido pagado a la dirección de pedidos, agendar una cita…).
