<?php

declare(strict_types=1);

/**
 * Comprueba el cálculo y el Excel con datos inventados, SIN tocar el AS400.
 *
 *     php cli/probar-excel.php
 *     php cli/probar-excel.php --documentos=4000
 *     php cli/probar-excel.php --salida=C:\ruta\Prueba.xlsx
 *
 * ===========================================================================
 *  POR QUÉ ESTE ARCHIVO EXISTE
 * ---------------------------------------------------------------------------
 *  Al AS400 de esta casa no se llega con la VPN activa. Eso significa que
 *  durante buena parte del desarrollo no hay servidor al que preguntar, y un
 *  informe que sólo se puede comprobar «cuando se pueda» es un informe que no
 *  se comprueba.
 *
 *  Así que las reglas se prueban con datos fabricados que cubren a propósito
 *  los casos difíciles —el que cuadra al céntimo, el de redondeo del IGTF, el
 *  que falta dinero, el ajuste que no se contrasta, el abono, el anulado, la
 *  forma de pago que no está en el catálogo— y se COMPRUEBA QUE EL VEREDICTO
 *  ES EL ESPERADO en cada uno. No es un «parece que va»: cada caso dice de
 *  antemano qué tiene que salir y el script falla si sale otra cosa.
 *
 *  Lo que esto NO puede probar, y hay que probar contra el servidor con
 *  `php cli/probar-as400.php`:
 *
 *    · Que los campos del AS400 se llamen como creemos.
 *    · Que la clave del documento CRUCE entre los tres archivos.
 *    · Cuánto tarda de verdad.
 * ===========================================================================
 */

if (PHP_SAPI !== 'cli') {
    http_response_code(404);
    exit;
}

require_once __DIR__ . '/../servicios/Auditoria.php';
require_once __DIR__ . '/../servicios/InformeExcel.php';
require_once __DIR__ . '/../servicios/Periodo.php';

function arg(string $clave, ?string $porDefecto = null): ?string
{
    foreach ($GLOBALS['argv'] as $a) {
        if (str_starts_with($a, '--' . $clave . '=')) {
            return substr($a, strlen($clave) + 3);
        }
    }

    return $porDefecto;
}

$fallos = 0;

function comprobar(string $que, mixed $obtenido, mixed $esperado): void
{
    global $fallos;

    $ok = $obtenido === $esperado;

    if (!$ok) {
        $fallos++;
    }

    printf("  %s  %-58s %s\n", $ok ? '[ok]   ' : '[FALLO]', $que,
        $ok ? (string) var_export($obtenido, true)
            : sprintf('obtuvo %s, esperaba %s',
                var_export($obtenido, true), var_export($esperado, true)));
}

/* =========================================================================
 *  Los maestros inventados
 * ========================================================================= */

$tiendas = [
    47 => ['nombre' => 'DISTRIBUIDORA TAUCAN',     'razon_social' => 'DISTRIBUIDORA TAUCAN, C.A.',  'activa' => true],
    73 => ['nombre' => 'COMERCIALIZADORA ELISPERLA','razon_social' => 'ELISPERLA, C.A.',            'activa' => true],
    12 => ['nombre' => 'RORI PORLAMAR',            'razon_social' => 'COMERCIAL NEW MAR, C.A.',     'activa' => true],
    54 => ['nombre' => 'DISTRIBUIDORA ROYAL DR LOS CORTIJOS', 'razon_social' => 'ROYAL DR, C.A.',   'activa' => true],
];

$catalogo = [
    'EF' => ['codigo' => 'EF', 'tipo' => 'EF', 'descripcion' => 'EFECTIVO BS',      'tipo_nombre' => 'EFECTIVO',       'tipos' => 1, 'filas' => 1],
    'PM' => ['codigo' => 'PM', 'tipo' => 'TR', 'descripcion' => 'PAGO MOVIL',       'tipo_nombre' => 'TRANSFERENCIA',  'tipos' => 1, 'filas' => 3],
    'PV' => ['codigo' => 'PV', 'tipo' => 'TJ', 'descripcion' => 'PUNTO DE VENTA',   'tipo_nombre' => 'TARJETA',        'tipos' => 1, 'filas' => 9],
    'DV' => ['codigo' => 'DV', 'tipo' => 'DI', 'descripcion' => 'DIVISAS EFECTIVO', 'tipo_nombre' => 'DIVISA',         'tipos' => 1, 'filas' => 2],
    'CR' => ['codigo' => 'CR', 'tipo' => 'FI', 'descripcion' => 'CREDITO CASHEA',   'tipo_nombre' => 'FINANCIAMIENTO', 'tipos' => 1, 'filas' => 1],
    'VB' => ['codigo' => 'VB', 'tipo' => 'FI', 'descripcion' => 'CREDITO VIBES',    'tipo_nombre' => 'FINANCIAMIENTO', 'tipos' => 1, 'filas' => 1],
    // `OT` se queda FUERA a propósito: es el caso real de una forma que se usa
    // y que `IDTA116` no tiene dada de alta, y el informe tiene que avisarlo.
];

/* =========================================================================
 *  Los casos difíciles, cada uno con el veredicto que TIENE que salir
 * ========================================================================= */

$encabezados = [];
$detalle     = [];
$pagos       = [];
$esperados   = [];

/**
 * Fabrica un documento y lo deja en los tres archivos.
 *
 * @param list<array{forma:string,monto:float}> $lineasPago
 */
function documento(
    string $fecha, int $tienda, string $tipo, int $numero,
    float $bruto, float $descuento, float $iva, float $igtf,
    array $lineasPago,
    string $estatus = '1', string $tipoNc = '', ?float $detalleBruto = null,
    int $lineasDetalle = 3, float $abono = 0.0, float $seniat = 0.0, bool $manual = false
): string {
    global $encabezados, $detalle, $pagos;

    $clave = ModeloAuditoriaFalso::clave($fecha, $tienda, $tipo, $numero);

    $encabezados[] = [
        'clave'            => $clave,
        'fecha'            => $fecha,
        'codigo_as400'     => $tienda,
        'tipo_doc'         => $tipo,
        'numero_doc'       => $numero,
        'estatus'          => $estatus,
        'tipo_nc'          => $tipoNc,
        'factura_aplicada' => $tipoNc === '2' ? 122658 : 0,
        'tienda_aplicada'  => $tipoNc === '2' ? $tienda : 0,
        'monto_bruto'      => $bruto,
        'descuento'        => $descuento,
        'iva'              => $iva,
        'dscto_seniat'     => $seniat,
        'igtf'             => $igtf,
        'abono'            => $abono,
        'unidades'         => $estatus === '9' ? 0 : 7,
        'tasa_bcv_doc'     => 231.45,
        'manual'           => $manual,
        'vendedor'         => '0412',
        'hora'             => '14:32:08',
        'cliente_cedula'   => 'V12345678',
        'cliente_nombre'   => 'CLIENTE DE PRUEBA',
    ];

    if ($lineasDetalle > 0) {
        $detalle[$clave] = [
            'lineas'    => $lineasDetalle,
            'bruto'     => $detalleBruto ?? $bruto,
            'descuento' => $detalleBruto === null ? $descuento : 0.0,
            'piezas'    => 7,
        ];
    }

    if ($lineasPago !== []) {
        $suma = 0.0;

        foreach ($lineasPago as $l) {
            $suma += $l['monto'];
        }

        $pagos[$clave] = [
            'formas' => count($lineasPago),
            'pagado' => $suma,
            'caja'   => '01',
            'lineas' => $lineasPago,
        ];
    }

    return $clave;
}

/** Sólo para componer la clave igual que el modelo de verdad. */
final class ModeloAuditoriaFalso
{
    public static function clave(string $fecha, int $tienda, string $tipo, int $numero): string
    {
        return ModeloAuditoria::clave($fecha, $tienda, $tipo, $numero);
    }
}

printf("=== Prueba del cálculo y del Excel, sin AS400 =================\n");
printf("\n--- Los casos difíciles ---------------------------------------\n");

/* 1. Factura que cuadra al céntimo. El caso normal: 97 de cada 100. */
$esperados[documento('2026-11-03', 47, 'FC', 122001, 1000.00, 100.00, 144.00, 0.00,
    [['forma' => 'PV', 'monto' => 1044.00]])] = Auditoria::CUADRA;

/* 2. Redondeo del IGTF: 3,20 Bs de diferencia, con IGTF presente. Por debajo
 *    del corte de 5 Bs, así que NO es dinero que falte. */
$esperados[documento('2026-11-03', 47, 'FE', 122002, 5000.00, 0.00, 800.00, 174.00,
    [['forma' => 'DV', 'monto' => 5970.80]])] = Auditoria::REDONDEO;

/* 3. Falta dinero de verdad: se registró sólo la parte financiada de CASHEA y
 *    no la inicial del cliente. 20 % por asentar. */
$esperados[documento('2026-11-05', 73, 'FC', 122003, 100000.00, 0.00, 16000.00, 0.00,
    [['forma' => 'CR', 'monto' => 92800.00]])] = Auditoria::REVISAR;

/* 4. Se registró MÁS que el total. La diferencia sale negativa. */
$esperados[documento('2026-11-05', 73, 'FC', 122004, 2000.00, 0.00, 320.00, 0.00,
    [['forma' => 'EF', 'monto' => 5000.00]])] = Auditoria::REVISAR;

/* 5. Sin una sola línea de pago, y con total distinto de cero. */
$esperados[documento('2026-11-06', 12, 'FC', 122005, 800.00, 0.00, 128.00, 0.00,
    [])] = Auditoria::REVISAR;

/* 6. ANULADA: cero piezas y cero venta en el encabezado, pero conserva sus
 *    líneas de detalle. No es un descuadre, es lo correcto — y cuadra. */
$esperados[documento('2026-11-06', 12, 'FC', 122006, 0.00, 0.00, 0.00, 0.00,
    [], '9', '', 450.00, 3)] = Auditoria::CUADRA;

/* 7. Nota de crédito CLASE 3 («ABON»): el abono repite el bruto, el detalle no
 *    cuadra a propósito, y cuadra con su forma de pago. */
$esperados[documento('2026-11-10', 54, 'NC', 26800, 3500.00, 0.00, 0.00, 0.00,
    [['forma' => 'PM', 'monto' => 3500.00]], '1', '3', 9900.00, 5, 3500.00)] = Auditoria::CUADRA;

/* 8. Nota de crédito CLASE 2 («AJUS»): ni detalle ni pagos. NO APLICA, que es
 *    el caso que el verificador encontró el 19/11/2026 y que antes salía como
 *    «falta por asentar 42,40 Bs». */
$esperados[documento('2026-11-18', 47, 'NC', 26829, 42.40, 0.00, 0.00, 0.00,
    [], '1', '2', null, 0)] = Auditoria::NO_APLICA;

/* 9. Nota de crédito CLASE 1 (devolución de mercancía): se contrasta como una
 *    factura normal. */
$esperados[documento('2026-11-12', 54, 'NE', 26810, 1200.00, 0.00, 192.00, 0.00,
    [['forma' => 'PM', 'monto' => 1392.00]], '1', '1')] = Auditoria::CUADRA;

/* 10. Factura manual (FLA011 = 'M'), con una forma de pago que NO está en
 *     IDTA116. Dos cosas que el informe tiene que decir. */
$esperados[documento('2026-11-14', 73, 'FC', 122010, 150000.00, 0.00, 24000.00, 5220.00,
    [['forma' => 'OT', 'monto' => 179220.00]], '1', '', null, 4, 0.0, 0.0, true)]
    = Auditoria::CUADRA;

/* 11. Descuento SENIAT distinto de cero: la fórmula del total se midió sobre un
 *     período donde ese importe era siempre cero, así que tiene que avisar. */
$esperados[documento('2026-11-14', 12, 'FC', 122011, 900.00, 0.00, 144.00, 0.00,
    [['forma' => 'EF', 'monto' => 1044.00]], '1', '', null, 2, 0.0, 15.00)] = Auditoria::CUADRA;

/* 12. El detalle de líneas no cuadra con el encabezado, pero los pagos sí.
 *     Son dos comprobaciones independientes y el informe las separa. */
$esperados[documento('2026-11-17', 47, 'FC', 122012, 4000.00, 0.00, 640.00, 0.00,
    [['forma' => 'PV', 'monto' => 4640.00]], '1', '', 3750.00, 6)] = Auditoria::CUADRA;

$casosDificiles = count($encabezados);

/* --- Un pago y un detalle HUÉRFANOS, sin encabezado ---------------------- */

$claveHuerfana = ModeloAuditoria::clave('2026-11-19', 47, 'FC', 999001);
$pagos[$claveHuerfana] = ['formas' => 1, 'pagado' => 7500.00, 'caja' => '02',
    'lineas' => [['forma' => 'EF', 'monto' => 7500.00]]];

$detalle[ModeloAuditoria::clave('2026-11-19', 47, 'FC', 999002)] =
    ['lineas' => 2, 'bruto' => 300.00, 'descuento' => 0.0, 'piezas' => 2];

/* --- Y relleno, para medir el tamaño de verdad --------------------------- */

$relleno = max(0, (int) arg('documentos', '1200') - $casosDificiles);

for ($i = 0; $i < $relleno; $i++) {
    $dia    = 1 + ($i % 28);
    $tienda = array_keys($tiendas)[$i % 4];
    $bruto  = round(500 + ($i % 997) * 37.5, 2);
    $iva    = round($bruto * 0.16, 2);

    documento(
        sprintf('2026-11-%02d', $dia), $tienda,
        ($i % 7 === 0) ? 'FE' : 'FC', 200000 + $i,
        $bruto, 0.0, $iva, 0.0,
        [['forma' => ['EF', 'PM', 'PV', 'DV'][$i % 4], 'monto' => round($bruto + $iva, 2)]]
    );
}

/* =========================================================================
 *  El cálculo de verdad, con el código de verdad
 * ========================================================================= */

$periodo = Periodo::de('2026-11-01', '2026-11-30');

$t = microtime(true);

$informe = Auditoria::informar(
    $periodo, $tiendas, $catalogo,
    ['documentos' => $encabezados, 'sin_fecha' => 2],
    $detalle, $pagos
);

$informe['segundos'] = round(microtime(true) - $t, 2);

/* --- El JSON, si se pide ------------------------------------------------- */

/*
 * `--json=ruta` escribe el informe con la MISMA forma con la que lo devuelve
 * `php/auditoria/consultar.php`. Sirve para probar la pantalla sin AS400:
 * basta servir ese archivo donde el navegador espera la respuesta. Sin esto,
 * el frontend sólo se puede ver con la red buena, que es la mitad del tiempo.
 */
$rutaJson = arg('json');

if ($rutaJson !== null) {
    $sobre = ['ok' => true, 'token' => null, 'informe' => $informe, 'aviso_cache' => null];

    file_put_contents($rutaJson,
        (string) json_encode($sobre, JSON_UNESCAPED_UNICODE | JSON_PRETTY_PRINT));

    printf("  [ok]     JSON de la respuesta escrito en %s\n", $rutaJson);
}

/* --- ¿Salió el veredicto esperado en cada caso? -------------------------- */

$porClave = [];

foreach ($informe['documentos'] as $d) {
    $porClave[(string) $d['clave']] = $d;
}

$n = 0;

foreach ($esperados as $clave => $esperado) {
    $n++;
    $doc = $porClave[$clave] ?? null;

    comprobar(
        sprintf('caso %2d  %s', $n, str_replace('|', ' · ', $clave)),
        $doc === null ? '(no salió en el informe)' : (string) $doc['clase'],
        $esperado
    );
}

/* --- ¿Y los números del resumen? ---------------------------------------- */

printf("\n--- El resumen ------------------------------------------------\n");

$r = $informe['resumen'];

comprobar('documentos', (int) $r['documentos'], $casosDificiles + $relleno);
comprobar('a revisar', (int) $r['revisar'], 3);
comprobar('redondeo', (int) $r['redondeo'], 1);
comprobar('no aplica (ajustes NC-2)', (int) $r['no_aplica'], 1);
comprobar('anuladas', (int) $r['anuladas'], 1);
comprobar('sin una línea de pago', (int) $r['sin_pagos'], 3);
comprobar('sin líneas de detalle', (int) $r['sin_lineas'], 1);
comprobar('abonos NC-3', (int) $r['abonos'], 1);
comprobar('ajustes NC-2', (int) $r['ajustes'], 1);
comprobar('facturas manuales', (int) $r['manuales'], 1);
comprobar('detalle no aplica (abono + ajuste)', (int) $r['detalle_no_aplica'], 2);
comprobar('detalle descuadrado', (int) $r['detalle_descuadrado'], 2);

/* El total de la fórmula, sobre el caso 3, que es el que falta dinero. */
$caso3 = $porClave[ModeloAuditoria::clave('2026-11-05', 73, 'FC', 122003)];
comprobar('caso 3: total = bruto - dscto + IVA + IGTF', (float) $caso3['total_factura'], 116000.00);
comprobar('caso 3: falta por asentar', (float) $caso3['dif_pago'], 23200.00);
comprobar('caso 3: % pagado', (float) $caso3['pct_pagado'], 80.0);
comprobar('caso 3: el diagnóstico nombra el financiamiento',
    str_contains((string) $caso3['diagnostico'], 'financiamiento'), true);

/* El ajuste, que es el que se descubrió tarde. */
$ajuste = $porClave[ModeloAuditoria::clave('2026-11-18', 47, 'NC', 26829)];
comprobar('ajuste: el contraste del detalle NO APLICA', $ajuste['dif_detalle'], null);
comprobar('ajuste: el diagnóstico dice que no hay nada que contrastar',
    str_contains((string) $ajuste['diagnostico'], 'nada que contrastar'), true);

/* --- Las formas de pago -------------------------------------------------- */

printf("\n--- Las formas de pago ----------------------------------------\n");

$formasPorCodigo = [];

foreach ($informe['formas'] as $f) {
    $formasPorCodigo[(string) $f['forma_pago']] = $f;
}

comprobar('CASHEA está marcada como financiamiento',
    (bool) $formasPorCodigo['CR']['es_financiamiento'], true);
comprobar('EFECTIVO no está marcada como financiamiento',
    (bool) $formasPorCodigo['EF']['es_financiamiento'], false);
comprobar('«OT» se detecta como fuera del catálogo',
    (bool) $formasPorCodigo['OT']['en_catalogo'], false);
comprobar('«OT» se nombra por lo que es',
    str_contains((string) $formasPorCodigo['OT']['descripcion'], 'OTROS PAGOS'), true);

/* La suma de las formas tiene que ser el total pagado del resumen: si no, el
 * informe se contradice entre dos pestañas. */
$sumaFormas = 0.0;

foreach ($informe['formas'] as $f) {
    $sumaFormas += (float) $f['bs'];
}

comprobar('las formas suman el total pagado del resumen',
    round($sumaFormas, 2), round((float) $r['total_pagado'], 2));

/* --- Los avisos ---------------------------------------------------------- */

printf("\n--- Los avisos ------------------------------------------------\n");

$textos = implode(' | ', array_column($informe['avisos'], 'texto'));

comprobar('avisa del descuento SENIAT', str_contains($textos, 'DESCUENTO SENIAT'), true);
comprobar('avisa de la clase 2', str_contains($textos, 'CLASE 2'), true);
comprobar('avisa de «OT» sin dar de alta', str_contains($textos, 'IDTA116'), true);
comprobar('avisa de los pagos huérfanos', str_contains($textos, 'SIN encabezado'), true);
comprobar('avisa de las fechas imposibles', str_contains($textos, 'no existe en el calendario'), true);

printf("\n  Los %d avisos, tal como saldrán:\n\n", count($informe['avisos']));

foreach ($informe['avisos'] as $aviso) {
    printf("    [%-5s] %s\n\n", $aviso['nivel'],
        wordwrap((string) $aviso['texto'], 68, "\n            ", false));
}

/* =========================================================================
 *  El Excel
 * ========================================================================= */

printf("--- El Excel --------------------------------------------------\n");

/*
 * EL ARCHIVO DE PRUEBA NO VA DONDE VAN LOS INFORMES DE VERDAD
 * -----------------------------------------------------------
 * Antes se escribía en `almacen/auditoria/`, junto a las auditorías reales.
 * El 19/11/2026 eso costó un informe: un `rm almacen/auditoria/*.xlsx` que
 * pretendía borrar ESTE archivo se llevó por delante la auditoría de
 * noviembre recién generada contra producción.
 *
 * Mezclar lo desechable con lo que cuesta veinte segundos de AS400 es pedir
 * que algún día se borre lo que no toca, y un comodín no distingue. Así que
 * va a su propia carpeta: lo de aquí dentro se puede borrar entero sin
 * mirarlo, que es justo lo que no pasaba antes.
 */
$salida = (string) arg('salida', __DIR__ . '/../almacen/pruebas/PRUEBA-sin-as400.xlsx');
$carpeta = dirname($salida);

if (!is_dir($carpeta) && !@mkdir($carpeta, 0777, true) && !is_dir($carpeta)) {
    fwrite(STDERR, "No se pudo crear la carpeta {$carpeta}.\n");
    exit(1);
}

$memoriaAntes = memory_get_peak_usage(true);
$t = microtime(true);

try {
    InformeExcel::escribir($informe, $salida);
} catch (Throwable $e) {
    printf("  [FALLO] %s\n", $e->getMessage());
    exit(1);
}

$segundos = microtime(true) - $t;

comprobar('el archivo existe', is_file($salida), true);
comprobar('pesa más de 4 KB (no está vacío)', filesize($salida) > 4096, true);

/* --- ¿Es un .xlsx de verdad, con sus cinco hojas y XML válido? ----------- */

$zip = new ZipArchive();

if ($zip->open($salida) !== true) {
    printf("  [FALLO] el archivo no es un ZIP válido, así que Excel no lo abrirá.\n");
    exit(1);
}

comprobar('es un ZIP con las partes obligatorias',
    $zip->locateName('[Content_Types].xml') !== false
    && $zip->locateName('xl/workbook.xml') !== false
    && $zip->locateName('xl/styles.xml') !== false, true);

comprobar('tiene las cinco hojas', count(array_filter(
    array_map(static fn($i) => $zip->statIndex($i)['name'], range(0, $zip->numFiles - 1)),
    static fn($n) => str_starts_with($n, 'xl/worksheets/sheet')
)), 5);

/*
 * El XML de cada parte se valida de verdad. Un solo carácter mal escapado hace
 * que Excel abra el archivo «reparándolo» y se coma lo que no entendió sin
 * decir qué: es el fallo más caro de este tipo de escritor, porque el archivo
 * parece existir y estar bien.
 */
libxml_use_internal_errors(true);
$xmlRoto = [];

for ($i = 0; $i < $zip->numFiles; $i++) {
    $nombre = $zip->statIndex($i)['name'];

    if (!str_ends_with($nombre, '.xml') && !str_ends_with($nombre, '.rels')) {
        continue;
    }

    $doc = new DOMDocument();

    if (!$doc->loadXML((string) $zip->getFromName($nombre))) {
        $xmlRoto[] = $nombre;
    }

    libxml_clear_errors();
}

comprobar('el XML de todas las partes es válido', $xmlRoto, []);

/*
 * Y que ninguna hoja repita un número de fila ni los saque de orden.
 *
 * El XML de una hoja es una lista de `<row r="N">` y cada N tiene que
 * aparecer UNA vez, en orden creciente. Un `<row r="7">` escrito dos veces
 * —lo que pasa en cuanto alguien escribe una fila en dos trozos— produce un
 * archivo que Excel abre «reparado», comiéndose una de las dos sin decir
 * cuál. No da error al generarlo, y el archivo pesa lo que tiene que pesar:
 * sólo se nota abriéndolo, y para entonces ya está entregado.
 */
$desordenadas = [];

for ($i = 1; $i <= 5; $i++) {
    preg_match_all('/<row r="(\d+)"/',
        (string) $zip->getFromName('xl/worksheets/sheet' . $i . '.xml'), $m);

    $filas = array_map('intval', $m[1]);
    $ordenadas = $filas;
    sort($ordenadas);

    $repetidas = array_filter(array_count_values($filas), static fn($c) => $c > 1);

    if ($repetidas !== [] || $filas !== $ordenadas) {
        $desordenadas[] = 'hoja ' . $i
            . ($repetidas !== [] ? ' (repite ' . implode(',', array_keys($repetidas)) . ')' : '')
            . ($filas !== $ordenadas ? ' (fuera de orden)' : '');
    }
}

comprobar('ninguna hoja repite ni desordena filas', $desordenadas, []);

/* La hoja grande tiene que tener una fila por documento, más la cabecera. */
$hojaGrande = (string) $zip->getFromName('xl/worksheets/sheet3.xml');
$filas = substr_count($hojaGrande, '<row ');

/*
 * Una fila por documento, mas la cabecera de marca y la de la tabla. El
 * desplazamiento sale de `InformeExcel::PRIMERA_FILA` y no de un numero escrito
 * aqui: con el numero a mano, cambiar el diseno de la cabecera rompia esta
 * comprobacion por algo que no era un fallo, y una prueba que falla cuando todo
 * esta bien es una prueba que se acaba ignorando.
 */
comprobar('la pestaña «Auditoría» tiene una fila por documento',
    $filas, (int) $r['documentos'] + InformeExcel::PRIMERA_FILA);

/*
 * EL LOGOTIPO Y LOS AJUSTES DE IMPRESIÓN
 * --------------------------------------
 * Una imagen en un `.xlsx` no es un archivo: son CUATRO piezas que tienen que
 * existir a la vez y apuntarse entre sí —el PNG, el dibujo, las relaciones del
 * dibujo y las relaciones de la hoja— más la declaración del tipo de contenido
 * y la etiqueta `<drawing>` al final de la hoja. Si falta una, Excel abre el
 * archivo sin decir nada y el logotipo sencillamente no está. Por eso se
 * comprueban las cinco, y no sólo que el PNG esté dentro.
 */
$partes = array_map(static fn($i) => $zip->statIndex($i)['name'], range(0, $zip->numFiles - 1));

comprobar('el logotipo está incrustado',
    count(array_filter($partes, static fn($n) => str_starts_with($n, 'xl/media/'))) > 0, true);
comprobar('el dibujo que lo coloca existe',
    count(array_filter($partes, static fn($n) => str_starts_with($n, 'xl/drawings/drawing'))), 5);
comprobar('cada dibujo tiene sus relaciones',
    count(array_filter($partes, static fn($n) => str_starts_with($n, 'xl/drawings/_rels/'))), 5);
comprobar('cada hoja apunta a su dibujo',
    count(array_filter($partes, static fn($n) => str_starts_with($n, 'xl/worksheets/_rels/'))), 5);
comprobar('el tipo PNG está declarado',
    str_contains((string) $zip->getFromName('[Content_Types].xml'), 'Extension="png"'), true);
comprobar('la hoja grande enlaza el dibujo',
    str_contains($hojaGrande, '<drawing '), true);

comprobar('el filo de marca es un degradado',
    str_contains((string) $zip->getFromName('xl/styles.xml'), '<gradientFill'), true);

/* Que se imprima bien no es un adorno: este informe se lleva a la tienda. */
comprobar('la hoja grande sale apaisada y ajustada al ancho',
    str_contains($hojaGrande, 'orientation="landscape"')
    && str_contains($hojaGrande, 'fitToWidth="1"'), true);
comprobar('lleva pie de página con numeración',
    str_contains($hojaGrande, '<oddFooter>') && str_contains($hojaGrande, 'Página &amp;P'), true);
comprobar('la cabecera se repite en cada página impresa',
    substr_count((string) $zip->getFromName('xl/workbook.xml'), '_xlnm.Print_Titles'), 3);

/* Las pestañas de colores: las cinco, cada una con el suyo. */
$colores = [];

for ($i = 1; $i <= 5; $i++) {
    if (preg_match('/<tabColor rgb="([^"]+)"/',
            (string) $zip->getFromName('xl/worksheets/sheet' . $i . '.xml'), $m) === 1) {
        $colores[] = $m[1];
    }
}

comprobar('las cinco pestañas llevan color', count($colores), 5);
comprobar('y los cinco son distintos', count(array_unique($colores)), 5);

comprobar('la cuadrícula está quitada', str_contains($hojaGrande, 'showGridLines="0"'), true);
comprobar('tiene el panel fijo', str_contains($hojaGrande, 'state="frozen"'), true);
comprobar('tiene el autofiltro', str_contains($hojaGrande, '<autoFilter'), true);

$zip->close();

printf("\n  %-30s %s\n", 'archivo', realpath($salida) ?: $salida);
printf("  %-30s %s KB\n", 'tamaño', number_format(filesize($salida) / 1024, 0, ',', '.'));
printf("  %-30s %s\n", 'documentos', number_format((int) $r['documentos'], 0, ',', '.'));
printf("  %-30s %s s\n", 'cálculo', number_format((float) $informe['segundos'], 2, ',', '.'));
printf("  %-30s %s s\n", 'escritura del Excel', number_format($segundos, 2, ',', '.'));
printf("  %-30s %s MB\n", 'memoria máxima',
    number_format(memory_get_peak_usage(true) / 1048576, 1, ',', '.'));

/* =========================================================================
 *  El veredicto de la prueba
 * ========================================================================= */

printf("\n=== %s ===\n", $fallos === 0
    ? 'Todo bien: el cálculo y el Excel hacen lo que dicen'
    : $fallos . ' COMPROBACIÓN(ES) FALLARON');

if ($fallos === 0) {
    printf("\nAbra el archivo para ver cómo queda. Lo que falta por probar es lo\n");
    printf("único que esto no puede: que los campos del AS400 se llamen como\n");
    printf("creemos y que las claves crucen. Eso lo dice:\n\n");
    printf("    php cli/probar-as400.php\n\n");
}

exit($fallos === 0 ? 0 : 1);
