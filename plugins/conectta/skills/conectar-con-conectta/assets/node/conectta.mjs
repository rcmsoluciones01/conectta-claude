// Conectta para Node 18 o superior (fetch y crypto nativos, sin dependencias).
//
//   readConnectionCode(codigo)        lee el código cnx_ que pega el cliente
//   createClient(conexion)            la API con la clave de la herramienta
//   sendOrder(conexion, pedido)       manda un pedido firmado a la dirección de pedidos
//   verifyEvent(cuerpoCrudo, cabeceras, secreto)   comprueba la firma de un aviso
//
// Copiar este archivo al proyecto. Nunca dejar el código cnx_, la clave ni el
// secreto en el repositorio: van en variables de entorno o en un almacén cifrado.

import crypto from 'node:crypto';

const PREFIJO = 'cnx_';

// El código es "cnx_" + JSON en Base64 para URL, sin relleno.
export function readConnectionCode(code) {
  const text = String(code ?? '').trim();
  if (!text.startsWith(PREFIJO)) {
    throw new Error('No es un código de conexión de Conectta (tiene que empezar por cnx_)');
  }
  const data = JSON.parse(Buffer.from(text.slice(PREFIJO.length), 'base64url').toString('utf8'));
  if (data.v !== 1) throw new Error(`Versión de código de conexión no soportada: ${data.v}`);
  for (const campo of ['api', 'cuenta', 'clave', 'pedidos', 'secreto']) {
    if (!data[campo]) throw new Error(`Al código de conexión le falta "${campo}"`);
  }
  return data;
}

export class ConecttaError extends Error {
  constructor(status, body) {
    const detalle = body && typeof body === 'object' ? body.code || body.error || body.message : body;
    super(`Conectta respondió ${status}${detalle ? `: ${detalle}` : ''}`);
    this.name = 'ConecttaError';
    this.status = status;
    this.code = body && typeof body === 'object' ? body.code : undefined;
    this.body = body;
  }
}

// La API de la cuenta con la clave de la herramienta. Solo abre 19 rutas
// (contactos, conversaciones, mensajes y ver una bandeja); el resto da 401.
export function createClient(connection) {
  const base = `${connection.api}/api/v1/accounts/${connection.cuenta}`;

  async function request(method, path, body) {
    const response = await fetch(base + path, {
      method,
      headers: {
        api_access_token: connection.clave,
        'Content-Type': 'application/json',
        Accept: 'application/json',
      },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
    const text = await response.text();
    let data = null;
    try {
      data = text ? JSON.parse(text) : null;
    } catch {
      data = text;
    }
    if (!response.ok) throw new ConecttaError(response.status, data);
    return data;
  }

  const inbox = inboxId => inboxId ?? connection.bandeja;

  const client = {
    request,

    // La bandeja de WhatsApp: número, plantillas (message_templates) y si
    // abre una sola conversación por contacto (lock_to_single_conversation).
    getInbox: inboxId => request('GET', `/inboxes/${inbox(inboxId)}`),

    searchContacts: q => request('GET', `/contacts/search?q=${encodeURIComponent(q)}`),

    // Crea el contacto listo para escribirle por la bandeja. Si el teléfono ya
    // existe (422), lo busca. `phone` con + e indicativo: "+573001234567".
    async findOrCreateContact({ phone, name, email, inboxId }) {
      try {
        const created = await request('POST', '/contacts', {
          inbox_id: inbox(inboxId),
          name: name || phone,
          phone_number: phone,
          ...(email ? { email } : {}),
        });
        return created.payload.contact;
      } catch (error) {
        if (!(error instanceof ConecttaError) || error.status !== 422) throw error;
        const found = await client.searchContacts(phone);
        const contact = (found.payload || []).find(c => c.phone_number === phone);
        if (!contact) throw error;
        return contact;
      }
    },

    getConversation: id => request('GET', `/conversations/${id}`),

    // Abre una conversación y devuelve su número (el `id` que usa la API).
    // OJO: abre una nueva cada vez. Para reutilizar, usar conversationFor.
    async openConversation({ contactId, inboxId, message }) {
      const conversation = await request('POST', '/conversations', {
        inbox_id: inbox(inboxId),
        contact_id: contactId,
        ...(message ? { message } : {}),
      });
      return conversation.id;
    },

    // La conversación con ese teléfono: reutiliza `known` (un id guardado por
    // la herramienta) si sigue abierta en esa bandeja; si no, abre una.
    // La clave no puede listar conversaciones: guardar lo que devuelve esto.
    async conversationFor({ phone, name, email, inboxId, known }) {
      if (known) {
        try {
          const conversation = await client.getConversation(known);
          if (conversation.status !== 'resolved' && conversation.inbox_id === inbox(inboxId)) return conversation.id;
        } catch (error) {
          if (!(error instanceof ConecttaError) || error.status !== 404) throw error;
        }
      }
      const contact = await client.findOrCreateContact({ phone, name, email, inboxId });
      return client.openConversation({ contactId: contact.id, inboxId });
    },

    // Texto libre: solo sale si el cliente escribió en las últimas 24 h
    // (`can_reply` de la conversación). Si no, sendTemplate.
    sendText: (conversationId, content, { private: isPrivate = false } = {}) =>
      request('POST', `/conversations/${conversationId}/messages`, { content, private: isPrivate }),

    // Plantilla aprobada. `body`: {"1": "Ana", "2": "PED-1042"} (o por nombre).
    // `content`: el texto tal como lo leerá el cliente; es lo que queda en el chat.
    sendTemplate: (conversationId, { name, language, category, body = {}, header, buttons, content }) =>
      request('POST', `/conversations/${conversationId}/messages`, {
        content,
        template_params: {
          name,
          language,
          category,
          processed_params: { body, ...(header ? { header } : {}), ...(buttons ? { buttons } : {}) },
        },
      }),

    getMessages: conversationId => request('GET', `/conversations/${conversationId}/messages`),

    setConversationStatus: (conversationId, status) =>
      request('POST', `/conversations/${conversationId}/toggle_status`, { status }),

    // Se suman a los atributos que ya tiene la conversación.
    setConversationAttributes: (conversationId, attributes) =>
      request('POST', `/conversations/${conversationId}/custom_attributes`, { custom_attributes: attributes }),

    // Reemplaza la lista entera de etiquetas.
    setConversationLabels: (conversationId, labels) =>
      request('POST', `/conversations/${conversationId}/labels`, { labels }),
  };

  return client;
}

// Firma de los PEDIDOS: HMAC-SHA256 del cuerpo crudo con el secreto, en Base64.
export function signOrder(body, secret) {
  return crypto.createHmac('sha256', secret).update(body).digest('base64');
}

// Manda un pedido a la dirección `pedidos` del código. Se firma siempre: a las
// herramientas del catálogo Conectta se lo exige y a «Otra herramienta» no le
// molesta. Formato estándar:
//   { id, status: "paid" | otro, total: 59900, currency: "COP",
//     customer: { name, phone: "+573001234567", email } }
export async function sendOrder(connection, order) {
  const body = JSON.stringify(order);
  const response = await fetch(connection.pedidos, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'X-Conectta-Signature': signOrder(body, connection.secreto) },
    body,
  });
  const text = await response.text();
  let data = null;
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    data = text;
  }
  // 400 cuerpo inválido · 401 firma · 404 dirección vieja · 429 más de 300/min
  if (!response.ok) throw new ConecttaError(response.status, data);
  return data; // {"status": "queued"} o {"status": "inactive"}
}

// Firma de los AVISOS: "sha256=" + HMAC-SHA256 en hex de "{timestamp}.{cuerpo}".
// `rawBody`: el cuerpo tal como llegó (Buffer o string), antes de JSON.parse.
// `headers`: cabeceras en minúsculas, como las da Node.
export function verifyEvent(rawBody, headers, secret, toleranceSeconds = 300) {
  const timestamp = String(headers['x-conectta-timestamp'] ?? '');
  const signature = String(headers['x-conectta-signature'] ?? '');
  if (!/^\d+$/.test(timestamp)) return false;
  if (Math.abs(Date.now() / 1000 - Number(timestamp)) > toleranceSeconds) return false;

  const body = Buffer.isBuffer(rawBody) ? rawBody : Buffer.from(String(rawBody), 'utf8');
  const expected =
    'sha256=' +
    crypto
      .createHmac('sha256', secret)
      .update(Buffer.concat([Buffer.from(`${timestamp}.`, 'utf8'), body]))
      .digest('hex');
  const a = Buffer.from(signature);
  const b = Buffer.from(expected);
  return a.length === b.length && crypto.timingSafeEqual(a, b);
}
