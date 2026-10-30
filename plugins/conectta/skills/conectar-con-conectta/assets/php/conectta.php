<?php
// Conectta para PHP 7.4 o superior, con la extensión curl.
//
//   conectta_leer_codigo($codigo)                       lee el código cnx_ que pega el cliente
//   conectta_api($conexion, $metodo, $ruta, $cuerpo)    la API con la clave de la herramienta
//   conectta_contacto($conexion, $telefono, ...)        crea o encuentra un contacto
//   conectta_conversacion($conexion, $telefono, ...)    reutiliza o abre una conversación
//   conectta_texto / conectta_plantilla                 manda un mensaje
//   conectta_enviar_pedido($conexion, $pedido)          manda un pedido firmado
//   conectta_verificar_aviso($cuerpoCrudo, $cabeceras, $secreto)  comprueba la firma de un aviso
//
// Copiar este archivo al proyecto. Nunca dejar el código cnx_, la clave ni el
// secreto en el repositorio: van en variables de entorno o en un almacén cifrado.

class ConecttaError extends RuntimeException
{
    public $status;
    public $body;
    public $codigo;

    public function __construct(int $status, $body)
    {
        $this->status = $status;
        $this->body = $body;
        $this->codigo = is_array($body) ? ($body['code'] ?? null) : null;
        $detalle = is_array($body) ? ($body['code'] ?? $body['error'] ?? $body['message'] ?? '') : (string) $body;
        parent::__construct("Conectta respondió {$status}" . ($detalle !== '' ? ": {$detalle}" : ''));
    }
}

// El código es "cnx_" + JSON en Base64 para URL, sin relleno.
function conectta_leer_codigo(string $codigo): array
{
    $texto = trim($codigo);
    if (strpos($texto, 'cnx_') !== 0) {
        throw new InvalidArgumentException('No es un código de conexión de Conectta (tiene que empezar por cnx_)');
    }
    $base64 = strtr(substr($texto, 4), '-_', '+/');
    $base64 .= str_repeat('=', (4 - strlen($base64) % 4) % 4);
    $datos = json_decode((string) base64_decode($base64, true), true);
    if (!is_array($datos) || ($datos['v'] ?? null) !== 1) {
        throw new InvalidArgumentException('Código de conexión ilegible o de una versión no soportada');
    }
    foreach (['api', 'cuenta', 'clave', 'pedidos', 'secreto'] as $campo) {
        if (empty($datos[$campo])) {
            throw new InvalidArgumentException("Al código de conexión le falta \"{$campo}\"");
        }
    }
    return $datos;
}

function conectta_http(string $metodo, string $url, array $cabeceras, ?string $cuerpo)
{
    $ch = curl_init($url);
    curl_setopt_array($ch, [
        CURLOPT_CUSTOMREQUEST => $metodo,
        CURLOPT_RETURNTRANSFER => true,
        CURLOPT_HTTPHEADER => $cabeceras,
        CURLOPT_TIMEOUT => 30,
    ]);
    if ($cuerpo !== null) {
        curl_setopt($ch, CURLOPT_POSTFIELDS, $cuerpo);
    }
    $respuesta = curl_exec($ch);
    if ($respuesta === false) {
        $error = curl_error($ch);
        curl_close($ch);
        throw new RuntimeException("No se pudo conectar con Conectta: {$error}");
    }
    $status = (int) curl_getinfo($ch, CURLINFO_RESPONSE_CODE);
    curl_close($ch);
    $datos = $respuesta === '' ? null : json_decode($respuesta, true);
    if ($datos === null && $respuesta !== '' && json_last_error() !== JSON_ERROR_NONE) {
        $datos = $respuesta;
    }
    if ($status >= 400) {
        throw new ConecttaError($status, $datos);
    }
    return $datos;
}

// La API de la cuenta con la clave. Solo abre 19 rutas (contactos,
// conversaciones, mensajes y ver una bandeja); el resto da 401.
function conectta_api(array $conexion, string $metodo, string $ruta, ?array $cuerpo = null)
{
    $url = "{$conexion['api']}/api/v1/accounts/{$conexion['cuenta']}{$ruta}";
    $cabeceras = [
        'api_access_token: ' . $conexion['clave'],
        'Content-Type: application/json',
        'Accept: application/json',
    ];
    $json = $cuerpo === null ? null : json_encode($cuerpo, JSON_UNESCAPED_UNICODE);
    return conectta_http($metodo, $url, $cabeceras, $json);
}

// Crea el contacto listo para escribirle por la bandeja; si el teléfono ya
// existe (422), lo busca. $telefono con + e indicativo: "+573001234567".
function conectta_contacto(array $conexion, string $telefono, string $nombre = '', string $correo = '', ?int $bandeja = null): array
{
    $cuerpo = ['inbox_id' => $bandeja ?? $conexion['bandeja'], 'name' => $nombre !== '' ? $nombre : $telefono, 'phone_number' => $telefono];
    if ($correo !== '') {
        $cuerpo['email'] = $correo;
    }
    try {
        return conectta_api($conexion, 'POST', '/contacts', $cuerpo)['payload']['contact'];
    } catch (ConecttaError $error) {
        if ($error->status !== 422) {
            throw $error;
        }
        $encontrados = conectta_api($conexion, 'GET', '/contacts/search?q=' . rawurlencode($telefono));
        foreach ($encontrados['payload'] ?? [] as $contacto) {
            if (($contacto['phone_number'] ?? '') === $telefono) {
                return $contacto;
            }
        }
        throw $error;
    }
}

// Reutiliza $conocida (un id guardado) si sigue abierta en esa bandeja; si no,
// abre una. La clave no puede listar conversaciones: guardar lo que devuelve.
function conectta_conversacion(array $conexion, string $telefono, string $nombre = '', ?int $conocida = null, ?int $bandeja = null): int
{
    $bandeja = $bandeja ?? $conexion['bandeja'];
    if ($conocida) {
        try {
            $conversacion = conectta_api($conexion, 'GET', "/conversations/{$conocida}");
            if (($conversacion['status'] ?? '') !== 'resolved' && ($conversacion['inbox_id'] ?? null) === $bandeja) {
                return (int) $conversacion['id'];
            }
        } catch (ConecttaError $error) {
            if ($error->status !== 404) {
                throw $error;
            }
        }
    }
    $contacto = conectta_contacto($conexion, $telefono, $nombre, '', $bandeja);
    $conversacion = conectta_api($conexion, 'POST', '/conversations', ['inbox_id' => $bandeja, 'contact_id' => $contacto['id']]);
    return (int) $conversacion['id'];
}

// Texto libre: solo sale si el cliente escribió en las últimas 24 h (can_reply).
function conectta_texto(array $conexion, int $conversacion, string $texto): array
{
    return conectta_api($conexion, 'POST', "/conversations/{$conversacion}/messages", ['content' => $texto]);
}

// Plantilla aprobada. $variables: ['1' => 'Ana', '2' => 'PED-1042'].
// $texto: lo que leerá el cliente, con las variables puestas (queda en el chat).
function conectta_plantilla(array $conexion, int $conversacion, string $nombre, string $idioma, string $categoria, array $variables, string $texto): array
{
    return conectta_api($conexion, 'POST', "/conversations/{$conversacion}/messages", [
        'content' => $texto,
        'template_params' => [
            'name' => $nombre,
            'language' => $idioma,
            'category' => $categoria,
            'processed_params' => ['body' => (object) $variables],
        ],
    ]);
}

// Firma de los PEDIDOS: HMAC-SHA256 del cuerpo crudo con el secreto, en Base64.
function conectta_firmar_pedido(string $cuerpo, string $secreto): string
{
    return base64_encode(hash_hmac('sha256', $cuerpo, $secreto, true));
}

// Manda un pedido a la dirección `pedidos` del código, siempre firmado.
// Formato estándar: ['id' => 'PED-1042', 'status' => 'paid', 'total' => 59900,
// 'currency' => 'COP', 'customer' => ['name' => ..., 'phone' => '+573001234567', 'email' => ...]].
// Errores: 400 cuerpo inválido, 401 firma, 404 dirección vieja, 429 más de 300/min.
function conectta_enviar_pedido(array $conexion, array $pedido)
{
    $cuerpo = json_encode($pedido, JSON_UNESCAPED_UNICODE);
    $cabeceras = [
        'Content-Type: application/json',
        'X-Conectta-Signature: ' . conectta_firmar_pedido($cuerpo, $conexion['secreto']),
    ];
    return conectta_http('POST', $conexion['pedidos'], $cabeceras, $cuerpo); // ['status' => 'queued']
}

// Firma de los AVISOS: "sha256=" + HMAC-SHA256 en hex de "{timestamp}.{cuerpo}".
// $cuerpoCrudo: file_get_contents('php://input') (en Laravel, $request->getContent()).
// $cabeceras: array con las cabeceras; se buscan sin distinguir mayúsculas.
function conectta_verificar_aviso(string $cuerpoCrudo, array $cabeceras, string $secreto, int $tolerancia = 300): bool
{
    $cabeceras = array_change_key_case($cabeceras, CASE_LOWER);
    $timestamp = (string) ($cabeceras['x-conectta-timestamp'] ?? '');
    $firma = (string) ($cabeceras['x-conectta-signature'] ?? '');
    if (!ctype_digit($timestamp) || abs(time() - (int) $timestamp) > $tolerancia) {
        return false;
    }
    $esperada = 'sha256=' . hash_hmac('sha256', $timestamp . '.' . $cuerpoCrudo, $secreto);
    return hash_equals($esperada, $firma);
}
