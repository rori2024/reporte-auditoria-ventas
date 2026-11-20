<?php

declare(strict_types=1);

/**
 * Descarga el Excel de la auditoría.
 *
 *     GET php/auditoria/excel.php?token=<el de la consulta>
 *     GET php/auditoria/excel.php?desde=2026-11-01&hasta=2026-11-19
 *
 * ===========================================================================
 *  CON TOKEN SE DESCARGA LO QUE SE MIRÓ; SIN ÉL, SE VUELVE A CONSULTAR
 * ---------------------------------------------------------------------------
 *  La pantalla manda el token de la corrida que está pintada, y entonces este
 *  archivo no toca el AS400: coge esa corrida de la caché y la formatea. Es lo
 *  que hace que el Excel y la pantalla no puedan discrepar (ver
 *  `CacheAuditoria`).
 *
 *  Sin token —o con uno caducado— se consulta de nuevo, y el archivo lleva
 *  dentro la hora en que se leyó el AS400, así que se ve. La alternativa
 *  —negarse— dejaría a quien vuelve media hora después sin forma de bajar el
 *  informe, y el dato está a una consulta de distancia.
 * ===========================================================================
 *
 * ESTE ARCHIVO NO ESCRIBE NADA EN LA RESPUESTA HASTA EL FINAL
 * -----------------------------------------------------------
 * Un `.xlsx` es binario. Un aviso de PHP, un salto de línea de más o un
 * mensaje de error impreso antes de las cabeceras se cuelan DENTRO del archivo
 * y Excel dice «formato no válido» sin más pistas. Por eso el libro se escribe
 * primero a un temporal, y sólo cuando está completo se mandan las cabeceras y
 * el contenido. Si algo falla antes de ese punto, lo que sale es una página de
 * error en HTML, que al menos se puede leer.
 */

require_once __DIR__ . '/../../servicios/SesionIntranet.php';
require_once __DIR__ . '/../../config/as400.php';
require_once __DIR__ . '/../../config/librerias.php';
require_once __DIR__ . '/../../servicios/Auditoria.php';
require_once __DIR__ . '/../../servicios/CacheAuditoria.php';
require_once __DIR__ . '/../../servicios/InformeExcel.php';
require_once __DIR__ . '/../../servicios/Periodo.php';

/**
 * Corta con una página legible. No devuelve.
 *
 * En HTML y no en JSON porque esto se abre en una pestaña del navegador —es
 * una descarga—, y un JSON en pantalla no lo lee nadie.
 */
function cortar(string $mensaje, int $estado = 400): never
{
    http_response_code($estado);
    header('Content-Type: text/html; charset=utf-8');

    echo '<!doctype html><html lang="es"><head><meta charset="utf-8">'
        , '<title>No se pudo generar el Excel</title>'
        , '<style>body{font:16px/1.6 "Segoe UI",system-ui,sans-serif;color:#0f172a;'
        , 'background:#f8fafc;margin:0;padding:48px 24px}'
        , 'main{max-width:38rem;margin:0 auto;background:#fff;border:1px solid #e2e8f0;'
        , 'border-radius:12px;padding:32px}'
        , 'h1{font-size:20px;margin:0 0 12px}p{margin:0 0 12px}'
        , 'a{color:#0369a1}</style></head><body><main>'
        , '<h1>No se pudo generar el Excel</h1><p>'
        , htmlspecialchars($mensaje, ENT_QUOTES, 'UTF-8')
        , '</p><p>Vuelva a la pantalla, consulte el período otra vez y pulse descargar '
        , 'desde ahí.</p></main></body></html>';

    exit;
}

/* --- Quién entra ---------------------------------------------------------- */

try {
    $sesion = SesionIntranet::continuar();
} catch (AccesoDenegado $e) {
    cortar($e->getMessage(), 403);
}

if (!$sesion->puede('visualizar')) {
    cortar('No tiene permiso para descargar esta auditoría.', 403);
}

/* --- La corrida: de la caché o del AS400 ---------------------------------- */

$token   = trim((string) ($_GET['token'] ?? ''));
$informe = null;

if ($token !== '') {
    $informe = CacheAuditoria::recuperar($token);
}

if ($informe === null) {
    try {
        $periodo = Periodo::de(
            trim((string) ($_GET['desde'] ?? '')),
            trim((string) ($_GET['hasta'] ?? ''))
        );
    } catch (InvalidArgumentException $e) {
        cortar($e->getMessage(), 422);
    }

    set_time_limit(180);

    try {
        CONECTARAS400();
    } catch (Throwable $e) {
        error_log('[auditoria/excel] AS400: ' . $e->getMessage());
        cortar($e->getMessage(), 503);
    }

    try {
        $informe = Auditoria::correr($periodo);
    } catch (Throwable $e) {
        error_log('[auditoria/excel] ' . $e->getMessage());
        cortar('El AS400 rechazó la consulta. El motivo quedó en el registro del servidor.', 500);
    } finally {
        DESCONECTARAS400();
    }
}

/* --- El libro, a un temporal ---------------------------------------------- */

$temporal = tempnam(sys_get_temp_dir(), 'auditoria');

if ($temporal === false) {
    cortar('El servidor no pudo crear el archivo temporal del Excel.', 500);
}

try {
    InformeExcel::escribir($informe, $temporal);
} catch (Throwable $e) {
    @unlink($temporal);
    error_log('[auditoria/excel] ' . $e->getMessage());
    cortar($e->getMessage(), 500);
}

/* --- Y ahora sí, a la respuesta ------------------------------------------- */

$nombre = InformeExcel::nombreArchivo($informe);
$bytes  = (int) filesize($temporal);

/*
 * Un búfer de salida abierto con algo dentro —un aviso, un espacio— se
 * vaciaría delante del binario y lo rompería. Se tiran todos antes de mandar
 * la primera cabecera.
 */
while (ob_get_level() > 0) {
    ob_end_clean();
}

header('Content-Type: application/vnd.openxmlformats-officedocument.spreadsheetml.sheet');
header('Content-Disposition: attachment; filename="' . $nombre . '"');
header('Content-Length: ' . $bytes);
header('Cache-Control: no-store, no-cache, must-revalidate');
header('X-Content-Type-Options: nosniff');

readfile($temporal);

@unlink($temporal);

exit;
