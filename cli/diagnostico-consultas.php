<?php

declare(strict_types=1);

/**
 * Por qué `RTP325` tarda cuarenta segundos y los otros dos medio.
 *
 *     php cli/diagnostico-consultas.php
 *     php cli/diagnostico-consultas.php --fecha=2026-11-18
 *
 * ===========================================================================
 *  QUÉ SE ESTÁ MIDIENDO Y POR QUÉ
 * ---------------------------------------------------------------------------
 *  La primera corrida contra producción dio esto, para UN día:
 *
 *      IDP210  encabezados                   210 filas    0,47 s
 *      RTP325  detalle (agrupado)            209 docs    40,67 s   <-
 *      IDP116N formas de pago                208 docs     0,55 s
 *
 *  Ochenta veces más lento que sus dos hermanas, con el mismo filtro de fecha
 *  y sobre un archivo del mismo orden de tamaño. Eso no es «el archivo es
 *  grande»: es que esa consulta concreta está haciendo algo que las otras dos
 *  no hacen.
 *
 *  Hay tres sospechosos y este archivo los separa en lugar de elegir uno:
 *
 *    1. El `GROUP BY` de siete columnas. Puede estar obligando al servidor a
 *       construir un índice temporal sobre el archivo entero.
 *    2. El filtro de fecha no encuentra índice en ESTE archivo, aunque sí en
 *       los otros dos, y acaba leyendo medio millón de filas.
 *    3. El `RTPDOC IN ('FC','FE','NC','NE')` sobre un CHAR(2).
 *
 *  Cada variante de abajo quita UNA cosa respecto de la de al lado. Lo que se
 *  busca no es la consulta más rápida: es saber cuál de los tres es, porque
 *  el arreglo de cada uno es distinto y dos de ellos no se pueden adivinar.
 *
 *  TARDA. Son del orden de cinco minutos, y la mitad se va en las variantes
 *  lentas: es el precio de no tener que probar a ciegas tres veces.
 * ===========================================================================
 */

if (PHP_SAPI !== 'cli') {
    http_response_code(404);
    exit;
}

require_once __DIR__ . '/../config/as400.php';
require_once __DIR__ . '/../config/librerias.php';
require_once __DIR__ . '/../servicios/Periodo.php';

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

function titulo(string $texto): void
{
    printf("\n%s\n%s\n", $texto, str_repeat('=', max(10, mb_strlen($texto))));
}

/**
 * Ejecuta una consulta midiendo el tiempo y devuelve la primera columna de la
 * primera fila, o el número de filas si se pide así.
 *
 * @return array{segundos:float,valor:string,filas:int,error:?string}
 */
function medir(string $sql, bool $contarFilas = false): array
{
    global $dbconect;

    $inicio = microtime(true);

    $st = @odbc_exec($dbconect, (string) utf8_a_as400($sql));

    if ($st === false) {
        return [
            'segundos' => microtime(true) - $inicio,
            'valor' => '', 'filas' => 0,
            'error' => as400_a_utf8(odbc_errormsg($dbconect)),
        ];
    }

    $valor = '';
    $filas = 0;

    while (odbc_fetch_row($st)) {
        if ($filas === 0) {
            $v = odbc_result($st, 1);
            $valor = $v === false ? '' : trim((string) $v);
        }

        $filas++;

        /*
         * Se recorren TODAS las filas aunque no se usen. El driver trae los
         * resultados por bloques: parar en la primera mediría lo que tarda el
         * primer bloque, no la consulta, y las variantes que devuelven miles
         * de filas saldrían falsamente rápidas.
         */
        if (!$contarFilas && $filas > 200000) {
            break;
        }
    }

    odbc_free_result($st);

    return [
        'segundos' => microtime(true) - $inicio,
        'valor' => $valor, 'filas' => $filas, 'error' => null,
    ];
}

/** Pinta el resultado de una variante. */
function variante(string $nombre, string $explica, string $sql, bool $contar = false): float
{
    printf("\n  %s\n", $nombre);
    printf("    %s\n", wordwrap($explica, 72, "\n    ", false));

    $r = medir($sql, $contar);

    if ($r['error'] !== null) {
        printf("    -> ERROR: %s\n", $r['error']);

        return -1.0;
    }

    printf("    -> %7.2f s   %s\n", $r['segundos'],
        $contar ? number_format($r['filas'], 0, ',', '.') . ' filas'
                : 'devuelve ' . $r['valor']);

    return $r['segundos'];
}

/* --- Conectar ------------------------------------------------------------- */

try {
    CONECTARAS400();
} catch (Throwable $e) {
    fwrite(STDERR, $e->getMessage() . "\n");
    exit(1);
}

global $archivos;

$fecha = (string) arg('fecha', date('Y-m-d', strtotime('-1 day')));

try {
    $periodo = Periodo::de($fecha, $fecha);
} catch (Throwable $e) {
    fwrite(STDERR, $e->getMessage() . "\n");
    DESCONECTARAS400();
    exit(1);
}

$t = $periodo->tramos()[0];

printf("=== Por qué RTP325 tarda ======================================\n");
printf("    día de prueba: %s\n", Periodo::corta($fecha));
printf("    esto tarda varios minutos; es a propósito\n");

/* =========================================================================
 *  1. El tamaño de cada archivo, sin contar una fila
 * ========================================================================= */

titulo('1. Cuántas filas tiene cada archivo');

printf("\n  Del catálogo del servidor, no con un COUNT(*): es un dato que el AS400\n");
printf("  ya tiene apuntado, así que es instantáneo y no ensucia la medición.\n\n");

foreach (['IDP210', 'RTP325', 'IDP116N', 'IDTA116', 'ETP045'] as $alias) {
    $archivo = $archivos[$alias];
    $punto   = (int) strpos($archivo, '.');

    $r = medir(
        "SELECT COALESCE(SUM(NUMBER_ROWS), -1)
           FROM QSYS2.SYSPARTITIONSTAT
          WHERE TABLE_SCHEMA = '" . substr($archivo, 0, $punto) . "'
            AND TABLE_NAME   = '" . substr($archivo, $punto + 1) . "'"
    );

    printf("    %-9s %-26s %16s filas%s\n", $alias, $archivo,
        $r['error'] !== null ? '?' : number_format((float) $r['valor'], 0, ',', '.'),
        $r['error'] !== null ? '  (' . $r['error'] . ')' : '');
}

/* =========================================================================
 *  2. Qué índices hay
 * ========================================================================= */

titulo('2. Por qué campos está indexado cada archivo');

printf("\n  Esto es LO QUE DECIDE si un filtro de fecha se resuelve leyendo tres\n");
printf("  páginas o medio millón de filas. Si IDP210 tiene índice por fecha y\n");
printf("  RTP325 no, ya está explicado todo.\n");

foreach (['IDP210', 'RTP325', 'IDP116N'] as $alias) {
    $archivo = $archivos[$alias];
    $punto   = (int) strpos($archivo, '.');
    $biblio  = substr($archivo, 0, $punto);
    $nombre  = substr($archivo, $punto + 1);

    printf("\n  --- %s (%s) ---\n", $alias, $archivo);

    /*
     * Dos sitios donde mirar, y hacen falta los dos:
     *
     *   · `SYSINDEXES` + `SYSKEYS` tiene los índices SQL.
     *   · Los archivos lógicos —la forma antigua de indexar en el AS400, y la
     *     que tienen casi todos estos archivos— son TABLAS de tipo 'L' que
     *     dependen del físico. No salen en SYSINDEXES.
     */
    $st = @odbc_exec($GLOBALS['dbconect'], utf8_a_as400(
        "SELECT i.INDEX_NAME, k.COLUMN_NAME, k.ORDINAL_POSITION
           FROM QSYS2.SYSINDEXES i
           JOIN QSYS2.SYSKEYS k ON k.INDEX_NAME = i.INDEX_NAME
                               AND k.INDEX_SCHEMA = i.INDEX_SCHEMA
          WHERE i.TABLE_SCHEMA = '$biblio' AND i.TABLE_NAME = '$nombre'
          ORDER BY i.INDEX_NAME, k.ORDINAL_POSITION"
    ));

    $porIndice = [];

    if ($st !== false) {
        while (odbc_fetch_row($st)) {
            $idx = trim((string) odbc_result($st, 1));
            $porIndice[$idx][] = as400_a_utf8(trim((string) odbc_result($st, 2)));
        }

        odbc_free_result($st);
    }

    if ($porIndice === []) {
        printf("    índices SQL: ninguno\n");
    } else {
        foreach ($porIndice as $idx => $campos) {
            printf("    %-20s %s\n", $idx, implode(', ', $campos));
        }
    }

    /* Los archivos lógicos, que es donde suele estar la clave de verdad. */
    $st = @odbc_exec($GLOBALS['dbconect'], utf8_a_as400(
        "SELECT TABLE_NAME, TABLE_TEXT
           FROM QSYS2.SYSTABLES
          WHERE TABLE_SCHEMA = '$biblio'
            AND TABLE_TYPE = 'L'
            AND TABLE_NAME LIKE '" . substr($nombre, 0, 5) . "%'
          ORDER BY TABLE_NAME"
    ));

    $logicos = [];

    if ($st !== false) {
        while (odbc_fetch_row($st)) {
            $logicos[] = trim((string) odbc_result($st, 1))
                . '  ' . as400_a_utf8(trim((string) odbc_result($st, 2)));
        }

        odbc_free_result($st);
    }

    printf("    archivos lógicos que empiezan igual: %s\n",
        $logicos === [] ? 'ninguno' : '');

    foreach ($logicos as $l) {
        printf("      %s\n", $l);
    }
}

/* =========================================================================
 *  3. Las variantes, que es lo que de verdad decide
 * ========================================================================= */

$rtp325  = $archivos['RTP325'];
$idp210  = $archivos['IDP210'];
$idp116n = $archivos['IDP116N'];

/** El filtro de fecha de un día, con el prefijo que toque. */
$fFecha = static fn(string $p): string => sprintf(
    '%1$sFCEDC = %2$d AND %1$sFAÑDC = %3$d AND %1$sFMSDC = %4$d AND %1$sFDIDC = %5$d',
    $p, $t['siglo'], $t['anio'], $t['mes'], $t['dia_desde']
);

$tipos = "'FC','FE','NC','NE'";

titulo('3. Las variantes sobre RTP325');

printf("\n  Cada una quita UNA cosa respecto de la de arriba. Lo que se busca es\n");
printf("  dónde está el salto de tiempo, no cuál es la más rápida.\n");

$tiempos = [];

$tiempos['A · la consulta actual'] = variante(
    'A · LA CONSULTA ACTUAL (GROUP BY de 7 columnas + filtro de tipo)',
    'Es exactamente la que corre hoy la aplicación. Es la que tardó 40,67 s.',
    "SELECT RFCEDC, RFAÑDC, RFMSDC, RFDIDC, RCDTDA, RTPDOC, RNMDOC,
            COUNT(*), SUM(RMOND1), SUM(RMOND2), SUM(RPZDT1)
       FROM $rtp325
      WHERE (" . $fFecha('R') . ")
        AND RTPDOC IN ($tipos)
      GROUP BY RFCEDC, RFAÑDC, RFMSDC, RFDIDC, RCDTDA, RTPDOC, RNMDOC",
    true
);

$tiempos['B · sin GROUP BY'] = variante(
    'B · SIN GROUP BY: las líneas en crudo, para sumarlas en PHP',
    'Mismo filtro, mismas filas leídas, pero sin agrupar. Si esto es rápido y '
    . 'A es lento, el culpable es el GROUP BY y el arreglo es trivial: traer '
    . 'las líneas y sumarlas aquí, que son unas doce mil al mes.',
    "SELECT RFCEDC, RFAÑDC, RFMSDC, RFDIDC, RCDTDA, RTPDOC, RNMDOC,
            RMOND1, RMOND2, RPZDT1
       FROM $rtp325
      WHERE (" . $fFecha('R') . ")
        AND RTPDOC IN ($tipos)",
    true
);

$tiempos['C · sólo contar con el filtro'] = variante(
    'C · SÓLO CONTAR, con el mismo filtro de fecha y tipo',
    'Ni agrupa ni devuelve filas: mide lo que cuesta ENCONTRAR las filas. Si '
    . 'esto ya es lento, el problema es el filtro —no hay índice por fecha en '
    . 'este archivo— y agrupar o no da igual.',
    "SELECT COUNT(*) FROM $rtp325
      WHERE (" . $fFecha('R') . ") AND RTPDOC IN ($tipos)"
);

$tiempos['D · contar sin el filtro de tipo'] = variante(
    'D · CONTAR, pero sin el `RTPDOC IN (...)`',
    'Igual que C quitando el filtro de tipo. Si C es lento y D rápido, el '
    . 'culpable es el IN sobre un CHAR(2).',
    "SELECT COUNT(*) FROM $rtp325 WHERE (" . $fFecha('R') . ")"
);

$tiempos['E · contar sin el siglo'] = variante(
    'E · CONTAR, sin el campo del siglo (RFCEDC)',
    'Si el índice del archivo empieza por el AÑO y no por el siglo, meter '
    . 'RFCEDC delante puede estar impidiendo usarlo.',
    sprintf("SELECT COUNT(*) FROM %s
      WHERE RFAÑDC = %d AND RFMSDC = %d AND RFDIDC = %d",
        $rtp325, $t['anio'], $t['mes'], $t['dia_desde'])
);

$tiempos['F · contar añadiendo la tienda'] = variante(
    'F · CONTAR, añadiendo una tienda concreta (RCDTDA = 12)',
    'Si el índice empieza por la tienda, esto será instantáneo y la fecha sola '
    . 'no. Eso cambiaría la estrategia: habría que consultar tienda por tienda.',
    "SELECT COUNT(*) FROM $rtp325 WHERE RCDTDA = 12 AND (" . $fFecha('R') . ")"
);

$tiempos['G · un documento por su clave'] = variante(
    'G · UN DOCUMENTO por tienda + tipo + número, sin fecha',
    'Si esto es instantáneo, el archivo está indexado POR DOCUMENTO y no por '
    . 'fecha. Entonces la salida es pedir el detalle de los documentos que ya '
    . 'nos dio IDP210, por su clave, en lotes.',
    "SELECT COUNT(*) FROM $rtp325
      WHERE RCDTDA = 12 AND RTPDOC = 'FC' AND RNMDOC BETWEEN 54240 AND 54340"
);

/* --- ¿El tiempo depende del rango, o es fijo? ---------------------------- */

/*
 * ESTA ES LA MEDICIÓN QUE DICE SI UN MES ES VIABLE
 * ------------------------------------------------
 * Si contar UN día tarda lo mismo que contar UN MES, el servidor está
 * barriendo el archivo entero las dos veces y el filtro no sirve de nada: un
 * mes costaría lo mismo que un día, cuarenta segundos, y la pantalla es
 * usable. Si el mes tarda treinta veces más, el coste es por fila encontrada
 * y un mes son veinte minutos: inviable, hay que cambiar la estrategia.
 *
 * Las dos respuestas llevan a sitios opuestos, y sin medirlo hay un 50 % de
 * probabilidad de reescribir la consulta para nada.
 */
$mes = Periodo::delMes(substr($fecha, 0, 7));
$tm  = $mes->tramos()[0];

$filtroMes = sprintf(
    'RFCEDC = %d AND RFAÑDC = %d AND RFMSDC = %d AND RFDIDC BETWEEN %d AND %d',
    $tm['siglo'], $tm['anio'], $tm['mes'], $tm['dia_desde'], $tm['dia_hasta']
);

$tiempos['J · contar UN MES entero'] = variante(
    'J · CONTAR el MES ENTERO, con el mismo filtro',
    'Comparada con C (un día): si tardan lo mismo, el servidor barre el archivo '
    . 'entero en los dos casos y un mes también costará cuarenta segundos, que '
    . 'se aguanta. Si el mes tarda treinta veces más, un mes son veinte minutos '
    . 'y hay que cambiar de estrategia, no de consulta.',
    "SELECT COUNT(*) FROM $rtp325 WHERE ($filtroMes) AND RTPDOC IN ($tipos)"
);

/* --- Y las dos rápidas, para tener con qué comparar ---------------------- */

titulo('4. Las dos que SÍ van rápidas, para comparar');

$tiempos['H · IDP210 (rápida)'] = variante(
    'H · IDP210, el mismo filtro de fecha',
    'La referencia: esta tardó 0,47 s.',
    "SELECT COUNT(*) FROM $idp210
      WHERE (" . $fFecha('N') . ") AND NTPDOC IN ($tipos)"
);

$tiempos['I · IDP116N (rápida)'] = variante(
    'I · IDP116N, el mismo filtro de fecha',
    'La otra referencia: 0,55 s.',
    "SELECT COUNT(*) FROM $idp116n
      WHERE (" . $fFecha('N') . ") AND FTPDOC IN ($tipos)"
);

/* =========================================================================
 *  Lo que dicen los números
 * ========================================================================= */

titulo('5. Resumen');

printf("\n");

foreach ($tiempos as $nombre => $segundos) {
    printf("    %-44s %8s\n", $nombre,
        $segundos < 0 ? 'ERROR' : number_format($segundos, 2, ',', '.') . ' s');
}

printf("\n  Cómo se lee esto:\n\n");
printf("    B rápida y A lenta .......... es el GROUP BY. Arreglo trivial:\n");
printf("                                  traer las líneas y sumarlas en PHP.\n");
printf("    C ya lenta .................. es el filtro: no hay índice por fecha\n");
printf("                                  en RTP325. Hay que mirar el paso 2.\n");
printf("    D rápida y C lenta .......... es el `IN` del tipo de documento.\n");
printf("    E rápida y C lenta .......... es el campo del siglo.\n");
printf("    F o G rápidas y C lenta ..... el archivo está indexado por tienda o\n");
printf("                                  por documento, no por fecha: hay que\n");
printf("                                  pedir el detalle por la clave de los\n");
printf("                                  documentos que ya dio IDP210.\n");
printf("    J parecida a C .............. el servidor barre el archivo entero\n");
printf("                                  igual: un mes cuesta lo mismo que un\n");
printf("                                  día y la pantalla es usable.\n");
printf("    J mucho mayor que C ......... el coste es por fila: un mes son\n");
printf("                                  minutos y hay que cambiar de\n");
printf("                                  estrategia, no de consulta.\n");
printf("\n  Todas lentas, incluidas F y G: el archivo no tiene ningún índice\n");
printf("  aprovechable y hay que pedirle uno a sistemas. Eso no se arregla\n");
printf("  desde aquí, y conviene saberlo antes de reescribir la consulta tres\n");
printf("  veces.\n");

DESCONECTARAS400();

printf("\n=== Terminado =================================================\n");

exit(0);
