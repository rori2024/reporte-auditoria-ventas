<?php

declare(strict_types=1);

/**
 * La auditoría de formas de pago desde la línea de comandos.
 *
 *     php cli/auditoria.php                              # el mes en curso
 *     php cli/auditoria.php --mes=2026-11
 *     php cli/auditoria.php --desde=2026-11-01 --hasta=2026-11-17
 *     php cli/auditoria.php --mes=2026-11 --excel
 *     php cli/auditoria.php --mes=2026-11 --excel --salida=C:\ruta\Auditoria.xlsx
 *     php cli/auditoria.php --mes=2026-11 --json
 *
 * ===========================================================================
 *  LA PANTALLA ES LA FORMA NORMAL DE USAR ESTO; ESTO ES PARA LO DEMÁS
 * ---------------------------------------------------------------------------
 *  Mismo servicio, misma consulta, mismos números: `Auditoria::correr()`. Lo
 *  que cambia es que aquí no hay navegador, y eso lo hace útil para tres cosas
 *  que la pantalla no puede:
 *
 *   · Comprobar que todo funciona antes de que alguien lo use.
 *   · Sacar el Excel de un mes cerrado sin tener la pantalla delante, o desde
 *     una tarea programada.
 *   · Ver el error completo. En la pantalla el fallo llega resumido a
 *     propósito —un mensaje del AS400 en una respuesta JSON no se lee— y aquí
 *     sale entero.
 * ===========================================================================
 */

if (PHP_SAPI !== 'cli') {
    http_response_code(404);
    exit;
}

require_once __DIR__ . '/../config/as400.php';
require_once __DIR__ . '/../config/librerias.php';
require_once __DIR__ . '/../servicios/Auditoria.php';
require_once __DIR__ . '/../servicios/InformeExcel.php';
require_once __DIR__ . '/../servicios/Periodo.php';

/*
 * Un mes puede tardar más de los 30 segundos de rigor: son tres consultas al
 * AS400 por ODBC. En CLI el límite suele venir ya en 0, pero no en todas las
 * instalaciones de XAMPP.
 */
set_time_limit(0);

function arg(string $clave, ?string $porDefecto = null): ?string
{
    foreach ($GLOBALS['argv'] as $a) {
        if (str_starts_with($a, '--' . $clave . '=')) {
            return substr($a, strlen($clave) + 3);
        }
    }

    return $porDefecto;
}

function bandera(string $clave): bool
{
    return in_array('--' . $clave, $GLOBALS['argv'], true);
}

function bs(float $n): string
{
    return number_format($n, 2, ',', '.');
}

function cant(int $n): string
{
    return number_format($n, 0, ',', '.');
}

/** `rótulo ......................` para que las cifras alineen a la derecha. */
function rotulo(string $texto, int $ancho = 36): string
{
    $faltan = $ancho - mb_strlen($texto);

    return $texto . ($faltan > 0 ? ' ' . str_repeat('.', $faltan - 1) : '');
}

/* --- El período ----------------------------------------------------------- */

try {
    $mes = arg('mes');

    $periodo = $mes !== null
        ? Periodo::delMes($mes)
        : Periodo::de(
            (string) arg('desde', date('Y-m-01')),
            (string) arg('hasta', date('Y-m-t'))
        );
} catch (Throwable $e) {
    fwrite(STDERR, $e->getMessage() . "\n");
    exit(1);
}

/* --- La corrida ----------------------------------------------------------- */

try {
    CONECTARAS400();
} catch (Throwable $e) {
    fwrite(STDERR, 'No se pudo conectar con el AS400: ' . $e->getMessage() . "\n\n"
        . "  Qué hacer: `php cli/probar-as400.php` lo comprueba paso a paso y dice\n"
        . "  cuál falla. Y recuerde que con la VPN activa no se llega al AS400.\n");
    exit(1);
}

try {
    $informe = Auditoria::correr($periodo);
} catch (Throwable $e) {
    fwrite(STDERR, "La consulta al AS400 falló:\n  " . $e->getMessage() . "\n");
    DESCONECTARAS400();
    exit(1);
} finally {
    DESCONECTARAS400();
}

$r = $informe['resumen'];

/* --- El JSON en crudo, si se pide ----------------------------------------- */

if (bandera('json')) {
    echo json_encode($informe, JSON_UNESCAPED_UNICODE | JSON_PRETTY_PRINT), "\n";
    exit(0);
}

/* --- Lo que se encontró, por pantalla ------------------------------------- */

printf("=== Auditoría de formas de pago ===============================\n");
printf("  %s %s\n", rotulo('período'), $periodo->rotulo());
printf("  %s %s\n", rotulo('origen'), 'AS400 en vivo');
printf("  %s %s s\n", rotulo('tardó'), number_format((float) $informe['segundos'], 2, ',', '.'));

/*
 * El desglose por archivo. Está aquí y no escondido en un `--verbose` porque
 * es el dato que hace falta para saber si hay que abrir un ticket: `RTP325` se
 * lleva el 98 % de la espera por no tener ningún índice por fecha, y mientras
 * eso no cambie conviene tenerlo delante cada vez.
 */
foreach (($informe['tiempos'] ?? []) as $que => $cuanto) {
    printf("      %s %s s\n", rotulo($que, 32), number_format((float) $cuanto, 2, ',', '.'));
}

if ($r['documentos'] === 0) {
    printf("\n");
    printf("  No hay ni un documento en IDP210 entre el %s y el %s.\n",
        Periodo::corta($periodo->desde), Periodo::corta($periodo->hasta));
    printf("\n");
    printf("  Esto se lee del AS400 en vivo, así que no es que «falte cargar»: es\n");
    printf("  que el servidor no tiene facturas de esos días. O son días de cierre,\n");
    printf("  o el rango está mal.\n");
    exit(2);
}

printf("  %s %s\n", rotulo('documentos auditados'), cant((int) $r['documentos']));
printf("  %s %s\n", rotulo('días con documentos'), cant((int) $r['dias']));

$tipos = [];

foreach ($r['tipos'] as $tipo => $n) {
    $tipos[] = $tipo . ' ' . cant((int) $n);
}

printf("  %s %s\n", rotulo('por tipo'), implode(', ', $tipos));
printf("  %s %s Bs\n", rotulo('total facturado'), bs((float) $r['total_facturado']));
printf("  %s %s Bs\n", rotulo('total en formas de pago'), bs((float) $r['total_pagado']));

printf("\n--- El veredicto ----------------------------------------------\n");
printf("  %s %s (%.1f %%)\n", rotulo('cuadran al céntimo'), cant((int) $r['cuadran']),
    $r['cuadran'] / $r['documentos'] * 100);
printf("  %s %s  (%s Bs en total)\n", rotulo('redondeo del IGTF'),
    cant((int) $r['redondeo']), bs((float) $r['redondeo_bs']));
printf("  %s %s (ajustes NC-2)\n", rotulo('no aplica'), cant((int) $r['no_aplica']));
printf("  %s %s\n", rotulo('A REVISAR'), cant((int) $r['revisar']));

if ($r['revisar'] > 0) {
    printf("      %s %s Bs\n", rotulo('falta por asentar', 32), bs((float) $r['falta_bs']));

    if ($r['sobra_bs'] > 0) {
        printf("      %s %s Bs\n", rotulo('registrado de más', 32), bs((float) $r['sobra_bs']));
    }
}

printf("\n--- El detalle contra el encabezado ---------------------------\n");
printf("  %s %s\n", rotulo('cuadra'), cant((int) $r['detalle_cuadra']));
printf("  %s %s\n", rotulo('NO cuadra'), cant((int) $r['detalle_descuadrado']));
printf("  %s %s (abonos y ajustes)\n", rotulo('no aplica'), cant((int) $r['detalle_no_aplica']));

printf("\n--- Lo que no se marca, y por qué -----------------------------\n");
printf("  %s %s\n", rotulo('sin una línea de pago'), cant((int) $r['sin_pagos']));
printf("  %s %s\n", rotulo('sin líneas de detalle'), cant((int) $r['sin_lineas']));
printf("  %s %s (cuadran todas)\n", rotulo('anuladas'), cant((int) $r['anuladas']));
printf("  %s %s (cuadran todas)\n", rotulo('abonos NC-3'), cant((int) $r['abonos']));
printf("  %s %s (nada que contrastar)\n", rotulo('ajustes NC-2'), cant((int) $r['ajustes']));
printf("  %s %s\n", rotulo('facturas manuales'), cant((int) $r['manuales']));

if ($r['revisar'] > 0) {
    printf("\n--- Las que hay que revisar -----------------------------------\n");

    $aRevisar = array_values(array_filter(
        $informe['documentos'],
        static fn($d) => (string) $d['clase'] === Auditoria::REVISAR
    ));

    usort($aRevisar, static fn($a, $b) => abs((float) $b['dif_pago']) <=> abs((float) $a['dif_pago']));

    foreach ($aRevisar as $d) {
        printf("  %s  %-24s %s %-8s  %16s Bs  (%s %% registrado)\n",
            date('d/m', (int) strtotime((string) $d['fecha'])),
            mb_substr((string) $d['tienda'], 0, 24),
            $d['tipo_doc'], $d['numero_doc'],
            bs((float) $d['dif_pago']),
            $d['pct_pagado'] === null ? '  --' : number_format((float) $d['pct_pagado'], 1, ',', '.'));
    }
}

printf("\n--- En qué se cobró -------------------------------------------\n");

foreach ($informe['formas'] as $forma) {
    printf("  %-4s %-32s %18s Bs  %6s líneas%s\n",
        $forma['forma_pago'],
        mb_substr((string) $forma['descripcion'], 0, 32),
        bs((float) $forma['bs']),
        cant((int) $forma['lineas']),
        $forma['es_financiamiento'] ? '  [financiamiento]' : '');
}

if ($informe['avisos'] !== []) {
    printf("\n--- Avisos ----------------------------------------------------\n");

    foreach ($informe['avisos'] as $aviso) {
        printf("  · %s\n\n", wordwrap((string) $aviso['texto'], 70, "\n    ", false));
    }
}

/* --- El Excel, si se pide ------------------------------------------------- */

if (!bandera('excel')) {
    printf("\nPara el Excel:\n  php cli/auditoria.php --mes=%s --excel\n",
        substr($periodo->desde, 0, 7));
    exit(0);
}

$carpeta = __DIR__ . '/../almacen/auditoria';

if (!is_dir($carpeta) && !@mkdir($carpeta, 0777, true) && !is_dir($carpeta)) {
    fwrite(STDERR, "No se pudo crear la carpeta {$carpeta}.\n");
    exit(1);
}

$salida = (string) arg('salida', $carpeta . '/' . InformeExcel::nombreArchivo($informe));

try {
    InformeExcel::escribir($informe, $salida);
} catch (Throwable $e) {
    fwrite(STDERR, "\nNo se pudo escribir el Excel:\n  " . $e->getMessage() . "\n");
    exit(1);
}

printf("\n--- Escrito ---------------------------------------------------\n");
printf("  %s\n", realpath($salida) ?: $salida);
printf("  %s KB, cinco pestañas: Resumen, A revisar, Auditoría, Formas de pago, Método.\n",
    number_format(filesize($salida) / 1024, 0, ',', '.'));

exit(0);
