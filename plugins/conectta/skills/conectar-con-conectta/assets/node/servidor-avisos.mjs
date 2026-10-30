// Receptor de avisos de Conectta, con Node 18+ y sin dependencias.
//
//   CONECTTA_CODIGO=cnx_... PORT=3000 node servidor-avisos.mjs
//
// Para un solo cliente lee el secreto del código. Con muchos clientes, dar a
// cada uno su dirección (/conectta/avisos/{cliente}) y buscar su secreto ahí.
// Conectta no avisa a localhost: para probar, un túnel público
// (cloudflared tunnel --url http://localhost:3000) y esa dirección en
// Ajustes → Herramientas conectadas → Editar avisos.

import http from 'node:http';
import { readConnectionCode, verifyEvent } from './conectta.mjs';

const conexion = readConnectionCode(process.env.CONECTTA_CODIGO);
const PORT = Number(process.env.PORT || 3000);

// X-Conectta-Delivery se repite en los reintentos. En producción, guardarlo en
// la base de datos o en Redis con caducidad; aquí basta con memoria.
const entregados = new Map();
const UN_DIA = 24 * 60 * 60 * 1000;
function yaProcesado(delivery) {
  const ahora = Date.now();
  for (const [id, momento] of entregados) if (ahora - momento > UN_DIA) entregados.delete(id);
  if (!delivery) return false;
  if (entregados.has(delivery)) return true;
  entregados.set(delivery, ahora);
  return false;
}

async function procesar(aviso) {
  switch (aviso.event) {
    case 'message_created':
      // También llegan los mensajes propios y los del equipo (outgoing).
      if (aviso.message_type !== 'incoming' || aviso.private) return;
      console.log(`Mensaje de ${aviso.sender?.phone_number} en la conversación ${aviso.conversation.id}: ${aviso.content}`);
      break;
    case 'message_updated': {
      const ultimo = aviso.conversation?.messages?.[0];
      if (ultimo?.id === aviso.id) console.log(`Mensaje ${aviso.id}: ${ultimo.status}`, aviso.content_attributes?.external_error ?? '');
      break;
    }
    case 'conversation_created':
      console.log(`Conversación ${aviso.id} con ${aviso.meta?.sender?.phone_number}`);
      break;
    case 'sale_created':
      // No trae el estado: casi siempre nace confirmed y no recibe sale_updated.
      // Contra entrega y formularios de WhatsApp nacen pending (luego sale_updated).
      console.log(`Venta ${aviso.data.id} registrada: ${aviso.data.amount} ${aviso.data.currency}`);
      break;
    case 'sale_updated':
      console.log(`Venta ${aviso.data.id}: ${aviso.data.from} → ${aviso.data.to}`);
      break;
    case 'appointment_booked':
    case 'appointment_updated':
    case 'order_status_changed':
    case 'kanban_stage_changed':
    case 'contact_opted_out':
      console.log(aviso.event, JSON.stringify(aviso.data));
      break;
    default:
      console.log('Aviso', aviso.event);
  }
}

const server = http.createServer((req, res) => {
  if (req.method !== 'POST' || !req.url.startsWith('/conectta/avisos')) {
    res.writeHead(404).end();
    return;
  }
  const trozos = [];
  req.on('data', trozo => trozos.push(trozo));
  req.on('end', () => {
    const cuerpo = Buffer.concat(trozos); // crudo: la firma va sobre estos bytes
    if (!verifyEvent(cuerpo, req.headers, conexion.secreto)) {
      res.writeHead(401).end();
      return;
    }
    // Responder antes de 5 segundos y procesar después.
    res.writeHead(200, { 'Content-Type': 'application/json' }).end('{"ok":true}');
    if (yaProcesado(req.headers['x-conectta-delivery'])) return;

    setImmediate(() => {
      let aviso;
      try {
        aviso = JSON.parse(cuerpo.toString('utf8'));
      } catch {
        return;
      }
      procesar(aviso).catch(error => console.error('Error procesando el aviso', error));
    });
  });
});

server.listen(PORT, () => console.log(`Escuchando avisos de Conectta en http://localhost:${PORT}/conectta/avisos`));
