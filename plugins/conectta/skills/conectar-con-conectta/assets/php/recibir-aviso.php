<?php
// Receptor de avisos de Conectta en PHP puro. Ponerlo detrás de la
// «Dirección de avisos» (p. ej. https://mi-herramienta.com/conectta/avisos.php).
// Variable de entorno CONECTTA_CODIGO con el código cnx_ del cliente; con
// muchos clientes, buscar el secreto de cada uno por su dirección.

require __DIR__ . '/conectta.php';

$conexion = conectta_leer_codigo((string) getenv('CONECTTA_CODIGO'));

$cuerpo = file_get_contents('php://input'); // crudo: la firma va sobre estos bytes
$cabeceras = function_exists('getallheaders') ? getallheaders() : [];
if (!$cabeceras) {
    foreach ($_SERVER as $clave => $valor) {
        if (strpos($clave, 'HTTP_') === 0) {
            $cabeceras[str_replace('_', '-', substr($clave, 5))] = $valor;
        }
    }
}

if ($_SERVER['REQUEST_METHOD'] !== 'POST' || !conectta_verificar_aviso($cuerpo, $cabeceras, $conexion['secreto'])) {
    http_response_code(401);
    exit;
}

$cabeceras = array_change_key_case($cabeceras, CASE_LOWER);
$entrega = $cabeceras['x-conectta-delivery'] ?? '';

// Responder antes de 5 segundos. Lo pesado, a una cola (base de datos, Redis…).
http_response_code(200);
header('Content-Type: application/json');
echo '{"ok":true}';
if (function_exists('fastcgi_finish_request')) {
    fastcgi_finish_request(); // con PHP-FPM, la respuesta sale ya y seguimos
}

// X-Conectta-Delivery se repite en los reintentos: no procesar dos veces.
// Aquí con un archivo para el ejemplo; en producción, una tabla con índice único.
$visto = sys_get_temp_dir() . '/conectta-' . hash('sha256', $entrega);
if ($entrega !== '' && file_exists($visto)) {
    exit;
}
if ($entrega !== '') {
    touch($visto);
}

$aviso = json_decode($cuerpo, true);
switch ($aviso['event'] ?? '') {
    case 'message_created':
        // También llegan los mensajes propios y los del equipo (outgoing).
        if (($aviso['message_type'] ?? '') === 'incoming' && empty($aviso['private'])) {
            error_log("Mensaje de {$aviso['sender']['phone_number']} en la conversación {$aviso['conversation']['id']}: {$aviso['content']}");
        }
        break;
    case 'sale_created':
        // No trae el estado: casi siempre nace confirmed y no recibe sale_updated.
        // Contra entrega y formularios de WhatsApp nacen pending (luego sale_updated).
        error_log("Venta {$aviso['data']['id']} registrada: {$aviso['data']['amount']} {$aviso['data']['currency']}");
        break;
    case 'sale_updated':
        error_log("Venta {$aviso['data']['id']}: {$aviso['data']['from']} -> {$aviso['data']['to']}");
        break;
    default:
        error_log('Aviso ' . ($aviso['event'] ?? '?'));
}
