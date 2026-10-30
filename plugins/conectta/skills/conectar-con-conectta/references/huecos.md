# Lo que la integración no puede hacer hoy

Huecos y límites encontrados al leer el código de Conectta (octubre de 2026). Al diseñar una integración, decirlos claramente y proponer el rodeo indicado; no inventar rutas ni campos para taparlos. Si algo de esto es imprescindible, la herramienta tiene que pedírselo al equipo de Conectta.

| # | Hueco | Rodeo |
|---|---|---|
| 1 | `sale_created` («Venta confirmada») no trae `status`. Casi todas las ventas nacen `confirmed` y no reciben `sale_updated`. Solo nacen `pending` las de contra entrega que cierra la IA y las de los formularios de WhatsApp. | Tratarla como venta y corregirla con `sale_updated`: `from: "pending"` significa que no estaba cobrada; `to: "voided"` o `"refunded"`, que ya no cuenta. **No** esperar a `sale_updated` para confirmar, porque las confirmadas no lo reciben. Para una contabilidad exacta con contra entrega, pedir a Conectta que añada `status` al aviso. |
| 2 | `sale_created` no trae la referencia del pedido ni su origen. | Cruzar por teléfono del contacto, importe y hora con el pedido recién mandado. |
| 3 | La clave no ve el resultado de un pedido: la dirección de pedidos responde siempre `{"status": "queued"}` y el registro de pedidos no está entre sus rutas. | Escuchar `conversation_created` / `sale_created`; el comercio ve el estado en la tarjeta («Último pedido recibido»). |
| 4 | La clave no puede listar conversaciones ni buscar la conversación abierta de un contacto, y `POST /conversations` abre una nueva cada vez (salvo bandejas con una sola conversación por contacto). | Guardar `teléfono → conversación` desde la respuesta de `POST /conversations` y los avisos `conversation_created` / `message_created`; comprobar con `GET /conversations/{id}` antes de reutilizar. |
| 5 | No hay «Enviar una prueba» para una herramienta conectada. | Cuenta de prueba y eventos reales. |
| 6 | El código `cnx_` no trae el id del bot de la herramienta, y sus propios mensajes vuelven en `message_created`. | Filtrar `message_type: "outgoing"` (o `sender.type: "agent_bot"`). |
| 7 | `message_updated` no trae `status` en el objeto de arriba; va en `conversation.messages[0]`, que es el último mensaje del chat. | Comparar `conversation.messages[0].id` con `id`; si no coincide, `GET /conversations/{id}/messages?after={id-1}` (el primero de la lista es ese mensaje). |
| 8 | El formato estándar de pedidos no añade indicativo de país a teléfonos locales. | Mandar siempre `+` e indicativo (o pedir a Conectta que ponga el indicativo en la ficha de la herramienta del catálogo). |
| 9 | `total` se interpreta quitando todo lo que no sea dígito, punto o coma y tomando la coma como decimal: `"59.900"` vale 59,9. | Número JSON sin separador de miles. |
| 10 | La clave no tiene `GET /inboxes` (listado) ni `/inboxes/{id}/message_templates`. | Usar `bandeja` del código y `GET /inboxes/{bandeja}` (trae `message_templates`). |
| 11 | Con el formato estándar Conectta no le escribe al comprador al recibir un pedido. | La herramienta escribe con su clave (o Conectta configura una plantilla de confirmación en la ficha del catálogo). |
| 12 | Los pedidos de la herramienta no crean pedidos del módulo de Conectta: no disparan `order_status_changed`. | Las fases del pedido las lleva la herramienta. |
| 13 | Los avisos no salen a redes privadas. | Túnel público para probar en local. |
| 14 | No hay alta tipo OAuth («Conectar con Conectta»): el comercio copia y pega el código. | Pedir el código con un campo de pegar y validarlo al momento. |
| 15 | En la pantalla, «Bandeja con la que escribe» deja elegir cualquier bandeja; si no es de WhatsApp, los pedidos no abren conversación. | Pedir al comercio que elija la de WhatsApp. |
| 16 | La pantalla dice «Tiene que empezar por https://» pero acepta `http://`. | Usar siempre `https://`. |
