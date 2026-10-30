# Ejemplo completo: Luja conectada a Conectta

Luja (punto de venta, tienda online y pedidos por WhatsApp) es la primera herramienta del catálogo de Conectta. Este es el recorrido entero, de punta a punta, que sirve de plantilla para cualquier herramienta del catálogo. Para «Otra herramienta» todo es igual salvo que `herramienta` llega `null` y Conectta no exige la firma de los pedidos.

## 0. Lo que tiene que existir en Luja antes

1. Un campo «Código de Conectta» en los ajustes de cada comercio, donde el comercio pega el `cnx_…`.
2. Una dirección de avisos **por comercio**, pública y con HTTPS, p. ej. `https://api.luja.example/conectta/avisos/{comercio_id}`. Se la enseña al comercio para que la pegue en Conectta antes de pulsar «Conectar» (o luego en «Editar avisos»).
3. Almacenamiento cifrado para los datos del código, por comercio.

## 1. El comercio conecta Luja (en Conectta)

Ajustes → Herramientas conectadas → elige **Luja** → pega la dirección de avisos de Luja → deja la bandeja de WhatsApp → revisa los avisos (por defecto: Mensaje nuevo, Conversación nueva, Venta confirmada, Cambió el estado de una venta, Cita agendada, Cambió el estado de una cita, Cambio de etapa en el Kanban, Cambió la fase de un pedido) → **Conectar** → copia el código → lo pega en Luja.

## 2. Luja guarda y comprueba el código

```js
import { readConnectionCode, createClient } from './conectta.mjs';

export async function guardarCodigoDeConectta(comercioId, codigoPegado) {
  const conexion = readConnectionCode(codigoPegado);            // lanza si no es cnx_ v1
  if (conexion.herramienta !== 'luja') throw new Error('Este código no es de Luja');
  if (!conexion.bandeja) throw new Error('La cuenta de Conectta no tiene WhatsApp conectado');

  const conectta = createClient(conexion);
  const bandeja = await conectta.getInbox();                     // 200 = la clave sirve
  const plantillas = (bandeja.message_templates || []).filter(t => t.status === 'APPROVED');

  await db.conexionesConectta.upsert({                          // cifrado en reposo
    comercioId, cuenta: conexion.cuenta, api: conexion.api, bandeja: conexion.bandeja,
    clave: conexion.clave, pedidos: conexion.pedidos, secreto: conexion.secreto,
    numeroWhatsApp: bandeja.phone_number, estado: 'activa',
  });
  return { numero: bandeja.phone_number, plantillas: plantillas.map(t => t.name) };
}
```

Si la llamada da `401`, el código es viejo (alguien pulsó «Clave nueva»); `403 conexiones_no_incluidas`, el plan no trae la casilla; `402 cuenta_sin_plan`, la cuenta no está al día.

## 3. Un pedido por WhatsApp, todavía sin cobrar

El comprador pide por WhatsApp. Luja mantiene un mapa `teléfono → conversación` (de la respuesta de `POST /conversations` y de los avisos `conversation_created` y `message_created`), así que normalmente ya conoce la conversación de Ana.

**Primero la conversación, después el pedido.** Conectta pone el pedido, y luego la venta, en la conversación abierta o pendiente más reciente de Ana en la bandeja. Si Luja la asegura antes, todo queda en un mismo hilo y Luja ya sabe su número. Al revés, si Conectta reutiliza una conversación que Luja no tenía guardada, no llega ningún aviso, Luja abre otra y el hilo queda partido en dos.

```js
import { createClient, sendOrder } from './conectta.mjs';

const conectta = createClient(conexion);
const conversacionId = await conectta.conversationFor({
  phone: '+573001234567', name: 'Ana Gómez',
  known: await db.conversaciones.get(conexion.cuenta, '+573001234567'),   // id guardado o null
});
await db.conversaciones.set(conexion.cuenta, '+573001234567', conversacionId);

await sendOrder(conexion, {
  id: 'PED-1042',
  status: 'pending',
  total: 89900,
  currency: 'COP',
  customer: { name: 'Ana Gómez', phone: '+573001234567', email: 'ana@ejemplo.com' },
});
// → {"status": "queued"}
```

Conectta guarda el contacto y usa esa conversación. **No anota venta. No le escribe a Ana.**

## 4. Luja le escribe a Ana

En la misma conversación (`conversacionId` del paso anterior):

```js
const conversacion = await conectta.getConversation(conversacionId);
if (conversacion.can_reply) {
  await conectta.sendText(conversacionId, '¡Hola Ana! Recibimos tu pedido PED-1042. Te mando el link de pago.');
} else {
  await conectta.sendTemplate(conversacionId, {
    name: 'pedido_recibido', language: 'es', category: 'UTILITY',
    body: { 1: 'Ana', 2: 'PED-1042' },
    content: 'Hola Ana, recibimos tu pedido PED-1042. Te mandamos el link de pago.',
  });
}
```

El mensaje sale por el WhatsApp del comercio y en el chat de Conectta aparece con el nombre «Luja».

## 5. Ana paga: el mismo pedido, ahora pagado

```js
await sendOrder(conexion, { id: 'PED-1042', status: 'paid', total: 89900, currency: 'COP',
  customer: { name: 'Ana Gómez', phone: '+573001234567' } });
```

Como `PED-1042` ya llegó sin pagar, Conectta anota **una** venta confirmada en la conversación que ya existía, mueve la tarjeta a «convertido» y no repite nada más. A Luja le llegan `sale_created` y `kanban_stage_changed` (si los tiene marcados). Mandarlo pagado otra vez no crea otra venta.

`sale_created` no trae la referencia `PED-1042`: si Luja necesita saber que esa venta es la suya, cruzarla por teléfono de `data.contact`, importe y hora con el pedido que acaba de mandar.

## 6. Ana contesta

Llega `message_created` con `message_type: "incoming"`, `conversation.id` y `conversation.can_reply: true`. Luja lo pasa a su bandeja o a su bot, y contesta con `sendText(conversation.id, …)`. Los avisos `message_created` con `message_type: "outgoing"` son los propios mensajes de Luja (o del equipo del comercio): no contestarlos.

## 7. El receptor de avisos de Luja

```js
// POST /conectta/avisos/:comercioId — con el cuerpo CRUDO
const conexion = await db.conexionesConectta.get(req.params.comercioId);
if (!conexion || !verifyEvent(rawBody, req.headers, conexion.secreto)) return res.status(401).end();

const delivery = req.headers['x-conectta-delivery'];
res.status(200).end();                                   // responder antes de 5 s
if (await yaProcesado(delivery)) return;

const aviso = JSON.parse(rawBody);
switch (aviso.event) {
  case 'message_created':
    if (aviso.message_type === 'incoming' && !aviso.private) await bandejaLuja.recibir(aviso);
    await db.conversaciones.set(aviso.account.id, aviso.sender?.phone_number, aviso.conversation.id);
    break;
  case 'conversation_created':
    await db.conversaciones.set(aviso.account.id, aviso.meta?.sender?.phone_number, aviso.id);
    break;
  case 'sale_created':   await ventas.registradaEnConectta(aviso.data); break;  // sin estado: casi siempre confirmed
  case 'sale_updated':   await ventas.cambioDeEstado(aviso.data); break;        // from → to
  case 'appointment_booked':
  case 'appointment_updated': await agenda.sincronizar(aviso.event, aviso.data); break;
  case 'kanban_stage_changed': await crm.etapa(aviso.data); break;
  case 'order_status_changed': await pedidosConectta.fase(aviso.data); break;   // pedidos del módulo de Conectta, no los de Luja
}
```

Versión completa y ejecutable: `assets/node/servidor-avisos.mjs`.

## 8. Cuando algo se rompe

- `401` en la API o `401`/`404` en pedidos → el comercio desconectó Luja o generó clave nueva: marcar la conexión como caída y pedirle el código nuevo.
- `403 conexiones_no_incluidas` → su plan de Conectta ya no trae la casilla.
- La tarjeta de Luja en Conectta dice «Con fallos» → los avisos no llegan a la dirección de Luja: revisar que responda `2xx` en menos de 5 s y que la firma se compruebe con el `secreto` del último código.
