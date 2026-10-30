---
name: conectar-con-conectta
description: "Conecta cualquier herramienta (tienda, POS, CRM, ERP) con Conectta: código cnx_, WhatsApp y pedidos con su clave, y avisos (webhooks) firmados. Incluye el caso Luja."
license: MIT
---

# Conectar una herramienta con Conectta

Conectta es una plataforma de ventas y atención por WhatsApp (chat con IA, Kanban, ventas, citas y pedidos). Un cliente de Conectta conecta una herramienta externa desde **Ajustes → Herramientas conectadas** y recibe un **código de conexión `cnx_…`** que pega en la herramienta. Con ese código la herramienta puede:

1. **Escribir a los clientes** por el WhatsApp de la cuenta (los mensajes salen en el chat con el nombre de la herramienta).
2. **Mandar pedidos**: Conectta guarda el contacto y la conversación, y anota la venta solo si el pedido viene pagado.
3. **Recibir avisos** firmados de lo que pasa en la cuenta: mensajes, conversaciones, ventas, citas, pedidos, etapas del Kanban y bajas.

No puede cambiar ajustes, equipo ni facturación, ni borrar nada.

Usar esta skill para guiar al desarrollador y escribir con él el código de cada una de esas piezas, en su lenguaje y su framework. El primer caso real es Luja (punto de venta, tienda online y pedidos por WhatsApp); sirve igual para cualquier herramienta.

## Reglas que no se rompen

1. **No inventar.** La clave abre exactamente 19 rutas (lista en `references/api.md` §3) y los avisos tienen los campos de `references/avisos.md`. Si piden algo que no está, decir que hoy no se puede y ofrecer el rodeo de `references/huecos.md`. Nunca suponer rutas de otras plataformas.
2. **Secretos fuera del código.** El código `cnx_`, la `clave` y el `secreto` van en variables de entorno o en un almacén cifrado por cuenta, nunca en el repositorio, en el navegador ni en logs. Si el usuario pega un código real en el chat, usarlo solo para lo que pida y recordarle que lo trate como una contraseña. En ejemplos, usar valores inventados.
3. **Dos firmas distintas con el mismo `secreto`.** Avisos: `sha256=` + hex de HMAC-SHA256 de `{timestamp}.{cuerpo}`. Pedidos: Base64 de HMAC-SHA256 del cuerpo. Ambas en `X-Conectta-Signature`. Detalle en `references/verificacion-de-avisos.md`.
4. **Dos números de conversación.** En la API, `{id}` es el número de la cuenta: `id` de `POST /conversations`, `conversation.id` en avisos del chat, `conversation_display_id` en avisos de negocio. Nunca `conversation_id` de un aviso de negocio.
5. **Teléfonos con `+` e indicativo** (`+573001234567`) y **montos como número sin separador de miles** (`59900`).
6. **Ventana de 24 h de WhatsApp.** Texto libre solo si `can_reply` es `true`; si no, plantilla aprobada.
7. Hablar siempre de Conectta y de sus cabeceras `X-Conectta-*`; ignorar cualquier otra cabecera que llegue.

## Flujo de trabajo

### 1. Entender qué se quiere conectar

Si no está claro, preguntar en pocas palabras:

- Lenguaje y framework del sistema (para elegir el fragmento de `assets/`).
- Qué necesita: recibir avisos, escribir por WhatsApp, mandar pedidos, o varias.
- Si la herramienta está en el catálogo de Conectta (como Luja) o el cliente la conecta como «Otra herramienta».
- Si es para un solo cliente o para muchos (entonces hay un código y una dirección de avisos por cliente).

Traducir la necesidad a piezas:

| El desarrollador dice… | Piezas |
|---|---|
| «recibir las ventas / citas en mi sistema» | receptor de avisos + `sale_created`/`sale_updated` (o `appointment_*`) |
| «avisar al cliente por WhatsApp cuando…» | cliente de la API: contacto → conversación → plantilla o texto |
| «mandar mis pedidos / ventas a Conectta» | `sendOrder` a la dirección `pedidos` |
| «responder los mensajes desde mi sistema» | receptor (`message_created` entrantes) + `sendText` |
| «conectar Luja» | todo lo anterior: seguir `references/ejemplo-luja.md` |

### 2. Conseguir y guardar el código de conexión

- El cliente lo genera en Conectta (Ajustes → Herramientas conectadas → elegir la herramienta → «Conectar») y lo ve **una sola vez**. Si se pierde: «Clave nueva» (cambian clave, secreto y dirección de pedidos a la vez).
- En la herramienta: un campo para pegarlo, leerlo (`readConnectionCode` / `read_connection_code` / `conectta_leer_codigo`), comprobar que la clave sirve con `GET /inboxes/{bandeja}` y guardarlo cifrado por cuenta. Permitir reemplazarlo en cualquier momento.
- Si `bandeja` es `null`, la cuenta no tiene WhatsApp. No se puede escribir a nadie y los pedidos se guardan sin conversación. En ese caso, comprobar la clave con `GET /contacts` y avisar al cliente.
- Campos del código y qué hacer con cada uno: `references/api.md` §1.
- Para avisos, la herramienta tiene que dar al cliente una **dirección de avisos pública con HTTPS** (mejor una por cliente) para pegarla en Conectta al conectar o luego en «Editar avisos».

### 3. Recibir avisos

1. Copiar el receptor del lenguaje (`assets/node/servidor-avisos.mjs`, `assets/python/servidor_avisos.py` o `assets/php/recibir-aviso.php`) o adaptar la función de verificación al framework (tabla del cuerpo crudo en `references/verificacion-de-avisos.md` §2).
2. Verificar la firma sobre el **cuerpo crudo**, rechazar avisos de más de 5 minutos, responder `2xx` en menos de 5 segundos y procesar después.
3. Deduplicar por `X-Conectta-Delivery` (los reintentos lo repiten: 30 s, 2 min, 10 min).
4. Manejar cada evento con su forma real (`references/avisos.md`). Tener presentes las trampas: `sale_created` no trae el estado (casi todas nacen `confirmed` y nunca reciben `sale_updated`, así que no hay que esperarlo para confirmar); llegan también los mensajes propios (`outgoing`); el orden no está garantizado.
5. Decir al desarrollador qué avisos tiene que marcar el cliente en Conectta para su caso.

### 4. Escribir a los clientes por WhatsApp

1. Plantillas aprobadas: `GET /inboxes/{bandeja}` → `message_templates` con `status: "APPROVED"`.
2. Conversación: reutilizar la que la herramienta tenga guardada para ese teléfono (comprobar con `GET /conversations/{id}`); si no hay, crear o encontrar el contacto (`POST /contacts`, y si da `422`, `GET /contacts/search`) y abrir una con `POST /conversations`. Guardar el `id`: la clave no puede listar conversaciones y `POST /conversations` abre una nueva cada vez. Las funciones `conversationFor` / `conversation_for` / `conectta_conversacion` ya lo hacen.
3. Mensaje: `sendText` si `can_reply`; si no, `sendTemplate` con `content` (texto final) y `template_params` (`name`, `language`, `category`, `processed_params.body`).
4. Confirmar la entrega con `message_updated` o `GET /conversations/{id}/messages?after={id-1}` (sin `after` solo vienen los 20 últimos).

Rutas, cuerpos y respuestas: `references/api.md` §3–§5.

### 5. Mandar pedidos

1. Formato estándar: `{ id, status, total, currency, customer: { name, phone, email } }`. Solo `status: "paid"` mete la venta en el libro.
2. Firmar siempre (`sendOrder` / `send_order` / `conectta_enviar_pedido` ya firman).
3. Patrón recomendado si la herramienta cobra después: mandar el pedido al crearlo (`"pending"`) y **otra vez con el mismo `id`** al cobrarlo (`"paid"`). Conectta anota una sola venta.
4. Si la herramienta también le escribe al comprador: **primero la conversación** (paso 4.2) y **después el pedido**. Conectta pone el pedido y la venta en la conversación abierta o pendiente más reciente de ese contacto en la bandeja. Así todo queda en el mismo hilo y la herramienta ya conoce su número. Al revés, si Conectta reutiliza una conversación que la herramienta no tenía guardada, no llega ningún aviso y la herramienta acaba abriendo otra.
5. Conectta **no le escribe al comprador** con el formato estándar: si hay que confirmarle algo, hacerlo con la API (paso 4).
6. Reintentar ante `429`, `5xx` o error de red; ante `401`/`404`, pedir el código nuevo.

Tabla de qué hace Conectta con cada pedido y cada respuesta: `references/api.md` §6.

### 6. Probar

- Cuenta de prueba de Conectta con WhatsApp conectado; conectar la herramienta desde Ajustes → Herramientas conectadas.
- Para avisos en local: túnel público (`cloudflared tunnel --url http://localhost:3000` o `ngrok http 3000`); Conectta no avisa a `localhost`. No hay botón de «aviso de prueba» para una herramienta conectada: provocar eventos reales (escribir al WhatsApp, mandar un pedido pagado…).
- Comprobar en la tarjeta de la herramienta en Conectta: estado, «Último aviso enviado» y «Último pedido recibido».
- Si algo falla: `references/errores.md`.

### 7. Revisión final

Antes de dar la integración por terminada, comprobar con el desarrollador:

- [ ] El código `cnx_` se guarda cifrado y se puede reemplazar; `401`/`403` marcan la conexión como caída.
- [ ] La firma de los avisos se calcula sobre el cuerpo crudo, en tiempo constante, con tolerancia de 5 minutos.
- [ ] El receptor responde en menos de 5 s y deduplica por `X-Conectta-Delivery`.
- [ ] Se ignoran los mensajes `outgoing` propios y las notas `private`.
- [ ] Se usa el número de conversación correcto y se reutilizan conversaciones.
- [ ] Teléfonos en `+` e indicativo; `total` numérico; el mismo `id` para el pedido pendiente y el pagado.
- [ ] Los pedidos van firmados en Base64 y los errores `429`/`5xx` se reintentan.
- [ ] Los huecos que afectan a su caso (`references/huecos.md`) están explicados.

## Recursos

**references/** (leer cuando haga falta):

- `api.md` — código `cnx_`, autenticación, las 19 rutas con cuerpos y respuestas, WhatsApp y plantillas, pedidos y límites.
- `avisos.md` — los 14 avisos que se pueden elegir, con su payload real y sus trampas.
- `verificacion-de-avisos.md` — cabeceras, firma, cuerpo crudo por framework, reintentos, deduplicación, túnel.
- `errores.md` — cada código de error de la API, de los pedidos y de los avisos, y qué hacer.
- `ejemplo-luja.md` — la integración completa de Luja, de punta a punta.
- `huecos.md` — lo que hoy no se puede hacer y su rodeo.

**assets/** (copiar al proyecto del desarrollador y adaptar; sin dependencias externas):

- `node/conectta.mjs` — `readConnectionCode`, `createClient` (contactos, `conversationFor`, `sendText`, `sendTemplate`…), `sendOrder`, `verifyEvent`. Node 18+.
- `node/servidor-avisos.mjs` — receptor de avisos completo con `node:http`.
- `python/conectta.py` — lo mismo para Python 3.9+ (solo biblioteca estándar).
- `python/servidor_avisos.py` — receptor con `http.server`.
- `php/conectta.php` — lo mismo para PHP 7.4+ con curl.
- `php/recibir-aviso.php` — receptor en PHP puro.

Para otro lenguaje (Go, Ruby, Java, C#…), portar desde `assets/node/conectta.mjs`: las fórmulas exactas de las dos firmas y del código están en `references/verificacion-de-avisos.md` y `references/api.md` §1.
