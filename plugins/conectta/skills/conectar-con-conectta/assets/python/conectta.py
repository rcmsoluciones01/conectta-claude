"""Conectta para Python 3.9 o superior (solo biblioteca estándar).

    read_connection_code(codigo)          lee el código cnx_ que pega el cliente
    ConecttaClient(conexion)              la API con la clave de la herramienta
    send_order(conexion, pedido)          manda un pedido firmado a la dirección de pedidos
    verify_event(cuerpo_crudo, cabeceras, secreto)   comprueba la firma de un aviso

Copiar este archivo al proyecto. Nunca dejar el código cnx_, la clave ni el
secreto en el repositorio: van en variables de entorno o en un almacén cifrado.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Mapping, Optional

PREFIJO = "cnx_"


def read_connection_code(code: str) -> dict:
    """El código es "cnx_" + JSON en Base64 para URL, sin relleno."""
    text = (code or "").strip()
    if not text.startswith(PREFIJO):
        raise ValueError("No es un código de conexión de Conectta (tiene que empezar por cnx_)")
    data = text[len(PREFIJO):]
    connection = json.loads(base64.urlsafe_b64decode(data + "=" * (-len(data) % 4)))
    if connection.get("v") != 1:
        raise ValueError(f"Versión de código de conexión no soportada: {connection.get('v')}")
    for campo in ("api", "cuenta", "clave", "pedidos", "secreto"):
        if not connection.get(campo):
            raise ValueError(f'Al código de conexión le falta "{campo}"')
    return connection


class ConecttaError(Exception):
    def __init__(self, status: int, body: Any):
        self.status = status
        self.body = body
        self.code = body.get("code") if isinstance(body, dict) else None
        detalle = (body.get("code") or body.get("error") or body.get("message")) if isinstance(body, dict) else body
        super().__init__(f"Conectta respondió {status}" + (f": {detalle}" if detalle else ""))


def _http(method: str, url: str, headers: dict, body: Optional[bytes]) -> Any:
    request = urllib.request.Request(url, data=body, method=method, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            raw = response.read()
            status = response.status
    except urllib.error.HTTPError as error:
        raw = error.read()
        status = error.code
    try:
        data = json.loads(raw) if raw else None
    except ValueError:
        data = raw.decode("utf-8", "replace")
    if status >= 400:
        raise ConecttaError(status, data)
    return data


class ConecttaClient:
    """La API de la cuenta con la clave de la herramienta. Solo abre 19 rutas
    (contactos, conversaciones, mensajes y ver una bandeja); el resto da 401."""

    def __init__(self, connection: dict):
        self.connection = connection
        self.base = f"{connection['api']}/api/v1/accounts/{connection['cuenta']}"

    def request(self, method: str, path: str, body: Any = None) -> Any:
        headers = {
            "api_access_token": self.connection["clave"],
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        data = None if body is None else json.dumps(body).encode("utf-8")
        return _http(method, self.base + path, headers, data)

    def _inbox(self, inbox_id: Optional[int]) -> Optional[int]:
        return inbox_id if inbox_id is not None else self.connection.get("bandeja")

    def get_inbox(self, inbox_id: Optional[int] = None) -> dict:
        """Número, plantillas (message_templates) y lock_to_single_conversation."""
        return self.request("GET", f"/inboxes/{self._inbox(inbox_id)}")

    def search_contacts(self, q: str) -> dict:
        return self.request("GET", "/contacts/search?q=" + urllib.parse.quote(q, safe=""))

    def find_or_create_contact(self, phone: str, name: str = "", email: str = "", inbox_id: Optional[int] = None) -> dict:
        """Crea el contacto listo para escribirle; si el teléfono ya existe (422), lo busca.
        `phone` con + e indicativo: "+573001234567"."""
        body = {"inbox_id": self._inbox(inbox_id), "name": name or phone, "phone_number": phone}
        if email:
            body["email"] = email
        try:
            return self.request("POST", "/contacts", body)["payload"]["contact"]
        except ConecttaError as error:
            if error.status != 422:
                raise
            found = self.search_contacts(phone).get("payload") or []
            for contact in found:
                if contact.get("phone_number") == phone:
                    return contact
            raise

    def get_conversation(self, conversation_id: int) -> dict:
        return self.request("GET", f"/conversations/{conversation_id}")

    def open_conversation(self, contact_id: int, inbox_id: Optional[int] = None, message: Optional[dict] = None) -> int:
        """Abre una conversación y devuelve su número. OJO: abre una nueva cada vez."""
        body = {"inbox_id": self._inbox(inbox_id), "contact_id": contact_id}
        if message:
            body["message"] = message
        return self.request("POST", "/conversations", body)["id"]

    def conversation_for(self, phone: str, name: str = "", email: str = "",
                         inbox_id: Optional[int] = None, known: Optional[int] = None) -> int:
        """Reutiliza `known` (un id guardado) si sigue abierta en esa bandeja; si no, abre una.
        La clave no puede listar conversaciones: guardar lo que devuelve esto."""
        if known:
            try:
                conversation = self.get_conversation(known)
                if conversation.get("status") != "resolved" and conversation.get("inbox_id") == self._inbox(inbox_id):
                    return conversation["id"]
            except ConecttaError as error:
                if error.status != 404:
                    raise
        contact = self.find_or_create_contact(phone, name, email, inbox_id)
        return self.open_conversation(contact["id"], inbox_id)

    def send_text(self, conversation_id: int, content: str, private: bool = False) -> dict:
        """Solo sale si el cliente escribió en las últimas 24 h (`can_reply`)."""
        return self.request("POST", f"/conversations/{conversation_id}/messages",
                            {"content": content, "private": private})

    def send_template(self, conversation_id: int, name: str, language: str, category: str,
                      body: Optional[dict] = None, content: str = "",
                      header: Optional[dict] = None, buttons: Optional[list] = None) -> dict:
        """Plantilla aprobada. `body`: {"1": "Ana", "2": "PED-1042"}.
        `content`: el texto tal como lo leerá el cliente (queda en el chat)."""
        processed = {"body": body or {}}
        if header:
            processed["header"] = header
        if buttons:
            processed["buttons"] = buttons
        return self.request("POST", f"/conversations/{conversation_id}/messages", {
            "content": content,
            "template_params": {"name": name, "language": language, "category": category,
                                "processed_params": processed},
        })

    def get_messages(self, conversation_id: int) -> dict:
        return self.request("GET", f"/conversations/{conversation_id}/messages")

    def set_conversation_status(self, conversation_id: int, status: str) -> dict:
        return self.request("POST", f"/conversations/{conversation_id}/toggle_status", {"status": status})

    def set_conversation_attributes(self, conversation_id: int, attributes: dict) -> dict:
        """Se suman a los atributos que ya tiene la conversación."""
        return self.request("POST", f"/conversations/{conversation_id}/custom_attributes",
                            {"custom_attributes": attributes})


def sign_order(body: bytes, secret: str) -> str:
    """Firma de los PEDIDOS: HMAC-SHA256 del cuerpo crudo con el secreto, en Base64."""
    return base64.b64encode(hmac.new(secret.encode("utf-8"), body, hashlib.sha256).digest()).decode("ascii")


def send_order(connection: dict, order: dict) -> Any:
    """Manda un pedido a la dirección `pedidos` del código, siempre firmado.
    Formato estándar: {id, status: "paid" | otro, total: 59900, currency: "COP",
    customer: {name, phone: "+573001234567", email}}.
    Errores: 400 cuerpo inválido, 401 firma, 404 dirección vieja, 429 más de 300/min."""
    body = json.dumps(order).encode("utf-8")
    headers = {"Content-Type": "application/json", "X-Conectta-Signature": sign_order(body, connection["secreto"])}
    return _http("POST", connection["pedidos"], headers, body)  # {"status": "queued"} o {"status": "inactive"}


def verify_event(raw_body: bytes, headers: Mapping[str, str], secret: str, tolerance_seconds: int = 300) -> bool:
    """Firma de los AVISOS: "sha256=" + HMAC-SHA256 en hex de "{timestamp}.{cuerpo}".
    `raw_body`: los bytes tal como llegaron, antes de json.loads.
    `headers`: cualquier mapeo de cabeceras (se buscan sin distinguir mayúsculas)."""
    lower = {str(k).lower(): v for k, v in headers.items()}
    timestamp = str(lower.get("x-conectta-timestamp", ""))
    signature = str(lower.get("x-conectta-signature", ""))
    if not timestamp.isdigit() or abs(time.time() - int(timestamp)) > tolerance_seconds:
        return False
    message = timestamp.encode("utf-8") + b"." + raw_body
    expected = "sha256=" + hmac.new(secret.encode("utf-8"), message, hashlib.sha256).hexdigest()
    return hmac.compare_digest(signature, expected)
