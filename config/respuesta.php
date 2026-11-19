<?php

declare(strict_types=1);

/**
 * La única forma en que esta aplicación contesta en JSON.
 *
 * Existe por un fallo concreto: `json_encode()` devuelve `false` cuando algo
 * del array no es UTF-8 válido, y `echo false` no imprime nada. El resultado
 * era una respuesta de cero bytes con cabeceras correctas, que en el navegador
 * aparece como "Unexpected end of JSON input" y no dice absolutamente nada de
 * la causa.
 *
 * Aquí eso no puede pasar: los bytes inválidos que se hayan escapado de la
 * conversión se sustituyen, y si aun así fallara la codificación se manda un
 * JSON de emergencia. Una respuesta vacía nunca es aceptable, porque es la
 * única que no se puede diagnosticar.
 */

require_once __DIR__ . '/texto.php';

/**
 * @param array<string,mixed> $datos
 */
function responder_json(array $datos, int $estado = 200): void
{
    if (!headers_sent()) {
        header('Content-Type: application/json; charset=utf-8');
        header('Cache-Control: no-store');
        http_response_code($estado);
    }

    // SUBSTITUTE cambia el byte imposible por «�» en lugar de tirar todo el
    // encode; es la red de seguridad por si algún texto se coló sin convertir.
    $json = json_encode($datos, JSON_UNESCAPED_UNICODE | JSON_INVALID_UTF8_SUBSTITUTE);

    if ($json === false) {
        error_log('[respuesta] json_encode falló: ' . json_last_error_msg());

        $json = json_encode([
            'ok'      => false,
            'mensaje' => 'El servidor no pudo preparar la respuesta.',
        ], JSON_UNESCAPED_UNICODE);
    }

    echo $json;
}
