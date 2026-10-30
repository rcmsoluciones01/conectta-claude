"""Receptor de avisos de Conectta con la biblioteca estándar de Python.

    CONECTTA_CODIGO=cnx_... PORT=3000 python servidor_avisos.py

Para un solo cliente lee el secreto del código. Con muchos clientes, dar a cada
uno su dirección (/conectta/avisos/{cliente}) y buscar su secreto ahí.
Conectta no avisa a localhost: para probar, un túnel público y esa dirección en
Ajustes → Herramientas conectadas → Editar avisos.

Con Flask el cuerpo crudo es request.get_data(); con FastAPI, await request.body();
con Django, request.body.
"""

import json
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from conectta import read_connection_code, verify_event

CONEXION = read_connection_code(os.environ["CONECTTA_CODIGO"])
PORT = int(os.environ.get("PORT", "3000"))

# X-Conectta-Delivery se repite en los reintentos. En producción, guardarlo en
# la base de datos o en Redis con caducidad; aquí basta con memoria.
_entregados: dict = {}
_lock = threading.Lock()
UN_DIA = 24 * 60 * 60


def ya_procesado(delivery: str) -> bool:
    ahora = time.time()
    with _lock:
        for clave in [k for k, v in _entregados.items() if ahora - v > UN_DIA]:
            del _entregados[clave]
        if not delivery:
            return False
        if delivery in _entregados:
            return True
        _entregados[delivery] = ahora
        return False


def procesar(aviso: dict) -> None:
    evento = aviso.get("event")
    if evento == "message_created":
        # También llegan los mensajes propios y los del equipo (outgoing).
        if aviso.get("message_type") != "incoming" or aviso.get("private"):
            return
        print(f"Mensaje de {aviso['sender'].get('phone_number')} en la conversación {aviso['conversation']['id']}: {aviso.get('content')}")
    elif evento == "sale_created":
        # No trae el estado: casi siempre nace confirmed y no recibe sale_updated.
        # Contra entrega y formularios de WhatsApp nacen pending (luego sale_updated).
        print(f"Venta {aviso['data']['id']} registrada: {aviso['data']['amount']} {aviso['data']['currency']}")
    elif evento == "sale_updated":
        print(f"Venta {aviso['data']['id']}: {aviso['data']['from']} -> {aviso['data']['to']}")
    elif evento == "conversation_created":
        print(f"Conversación {aviso['id']} con {(aviso.get('meta') or {}).get('sender', {}).get('phone_number')}")
    else:
        print("Aviso", evento, json.dumps(aviso.get("data", {}), ensure_ascii=False))


class Avisos(BaseHTTPRequestHandler):
    def do_POST(self):
        if not self.path.startswith("/conectta/avisos"):
            self.send_response(404)
            self.end_headers()
            return
        largo = int(self.headers.get("Content-Length") or 0)
        cuerpo = self.rfile.read(largo)  # crudo: la firma va sobre estos bytes
        if not verify_event(cuerpo, self.headers, CONEXION["secreto"]):
            self.send_response(401)
            self.end_headers()
            return
        # Responder antes de 5 segundos y procesar después.
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"ok":true}')
        if ya_procesado(self.headers.get("X-Conectta-Delivery", "")):
            return
        try:
            aviso = json.loads(cuerpo)
        except ValueError:
            return
        threading.Thread(target=procesar, args=(aviso,), daemon=True).start()

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    print(f"Escuchando avisos de Conectta en http://localhost:{PORT}/conectta/avisos")
    ThreadingHTTPServer(("", PORT), Avisos).serve_forever()
