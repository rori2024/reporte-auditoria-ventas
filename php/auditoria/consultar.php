<?php

declare(strict_types=1);

/**
 * Corre la auditoría contra el AS400 y devuelve el informe en JSON.
 *
 *     POST php/auditoria/consultar.php
 *          desde=2026-11-01&hasta=2026-11-19
 *
 * ===========================================================================
 *  POST Y NO GET, AUNQUE NO CAMBIE NADA
 * ---------------------------------------------------------------------------
 *  Esto sólo lee: no escribe en el AS400 ni en ningún sitio, así que por la
 *  letra de HTTP sería un GET. Va por POST por dos razones prácticas:
 *
 *   · Una consulta de un mes son tres lecturas al AS400 y varios segundos. Un
 *     GET lo guardan en caché el navegador y cualquier intermediario, y lo
 *     reintentan solos al volver atrás o al recargar. Una auditoría en vivo
 *     que devuelve la respuesta de hace media hora deja de ser en vivo, y
 *     nadie se entera.
 *   · Un GET se pone en un enlace, y un enlace se pulsa por accidente. Esto
 *     no es gratis: cada pulsación son varios segundos de sesión ODBC.
 * ===========================================================================
 */

require_once __DIR__ . '/../../servicios/SesionIntranet.php';
require_once __DIR__ . '/../../config/respuesta.php';
require_once __DIR__ . '/../../config/as400.php';
require_once __DIR__ . '/../../config/librerias.php';
require_once __DIR__ . '/../../servicios/Auditoria.php';
require_once __DIR__ . '/../../servicios/CacheAuditoria.php';
require_once __DIR__ . '/../../servicios/Periodo.php';

/* --- Quién entra ---------------------------------------------------------- */

try {
    $sesion = SesionIntranet::continuar();
} catch (AccesoDenegado $e) {
    responder_json(['ok' => false, 'mensaje' => $e->getMessage()], 403);
    exit;
}

if (!$sesion->puede('visualizar')) {
    responder_json([
        'ok' => false,
        'mensaje' => 'No tiene permiso para consultar esta auditoría.',
    ], 403);
    exit;
}

if (($_SERVER['REQUEST_METHOD'] ?? '') !== 'POST') {
    responder_json(['ok' => false, 'mensaje' => 'Este punto de entrada sólo admite POST.'], 405);
    exit;
}

/* --- El período ----------------------------------------------------------- */

try {
    $periodo = Periodo::de(
        trim((string) ($_POST['desde'] ?? '')),
        trim((string) ($_POST['hasta'] ?? ''))
    );
} catch (InvalidArgumentException $e) {
    /*
     * 422 y no 500: la petición llegó bien, lo que no vale es lo que pide. Y el
     * mensaje de `Periodo` se devuelve TAL CUAL porque está escrito para que lo
     * lea una persona —«el rango son 365 días y el tope es 93»— y no para un
     * registro.
     */
    responder_json(['ok' => false, 'mensaje' => $e->getMessage()], 422);
    exit;
}

/* --- La corrida ----------------------------------------------------------- */

/*
 * Tres lecturas al AS400 por ODBC no caben en los 30 segundos de rigor cuando
 * el rango es de un mes con movimiento. El límite se sube aquí y no en el
 * php.ini porque es esta página la que lo necesita, no todas.
 */
set_time_limit(180);

/*
 * Y el navegador no debe reintentar solo mientras el AS400 responde: si el
 * usuario recarga a los diez segundos, se abre una SEGUNDA sesión ODBC sobre el
 * mismo rango y las dos compiten. No se puede impedir desde aquí, pero sí
 * evitar que la respuesta se quede guardada en ningún sitio.
 */
header('Cache-Control: no-store, no-cache, must-revalidate');

try {
    CONECTARAS400();
} catch (Throwable $e) {
    /*
     * El motivo de verdad al registro; al navegador, el mensaje de la
     * excepción, que `config/as400.php` ya redacta para una persona («No se
     * pudo conectar con el servidor AS400. Compruebe la red…»). Lo que NO se
     * manda es el mensaje del driver: lleva el nombre del servidor y del
     * usuario, y eso no tiene por qué salir a la pantalla.
     */
    error_log('[auditoria/consultar] AS400: ' . $e->getMessage());

    responder_json([
        'ok'      => false,
        'mensaje' => $e->getMessage(),
        'pista'   => 'Si está usando la VPN, desconéctela: mientras está activa no se '
            . 'llega al AS400. Si el problema sigue, `php cli/probar-as400.php` dice '
            . 'exactamente qué paso falla.',
    ], 503);
    exit;
}

try {
    $informe = Auditoria::correr($periodo);
} catch (Throwable $e) {
    error_log('[auditoria/consultar] ' . $e->getMessage());

    responder_json([
        'ok'      => false,
        'mensaje' => 'El AS400 rechazó la consulta. El motivo quedó en el registro del '
            . 'servidor; `php cli/probar-as400.php` lo reproduce con el detalle completo.',
    ], 500);
    exit;
} finally {
    DESCONECTARAS400();
}

/* --- Se guarda, para que el Excel sea esto mismo -------------------------- */

$token = null;

try {
    $token = CacheAuditoria::guardar($informe);
} catch (Throwable $e) {
    /*
     * Que la caché falle NO tumba la consulta: el informe ya está calculado y
     * la pantalla puede pintarlo. Lo único que se pierde es la garantía de que
     * el Excel sea exactamente esta corrida, y eso se dice —el aviso sale en la
     * pantalla— en lugar de dejar que la persona lo descubra comparando dos
     * archivos que no coinciden.
     */
    error_log('[auditoria/consultar] caché: ' . $e->getMessage());
}

responder_json([
    'ok'      => true,
    'token'   => $token,
    'informe' => $informe,
    'aviso_cache' => $token === null
        ? 'No se pudo guardar esta corrida en el servidor. El Excel volverá a consultar '
          . 'el AS400 al descargarlo, así que puede traer algún documento más que el '
          . 'que ve aquí.'
        : null,
]);
