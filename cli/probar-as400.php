<?php

declare(strict_types=1);

/**
 * Comprueba que el AS400 contesta lo que esta aplicación necesita.
 *
 *     php cli/probar-as400.php
 *     php cli/probar-as400.php --fecha=2026-11-17
 *
 * ===========================================================================
 *  PARA QUÉ SIRVE
 * ---------------------------------------------------------------------------
 *  Se corre ANTES de abrir la pantalla por primera vez, y cada vez que algo
 *  falle y no se sepa si es la aplicación o el servidor. Comprueba, en este
 *  orden y parándose en el primer fallo real:
 *
 *      1. Que el .env está relleno y qué mapa de bibliotecas se está usando
 *      2. Que la conexión ODBC con el AS400 se abre
 *      3. Que los cinco archivos existen donde el mapa dice
 *      4. Que los campos que la aplicación lee están en cada archivo
 *      5. Que una consulta de verdad devuelve filas, y las pinta
 *
 *  Cada paso dice qué hacer si falla. Un «no se pudo conectar» sin más es lo
 *  que convierte un problema de diez minutos en una tarde.
 * ===========================================================================
 */

if (PHP_SAPI !== 'cli') {
    http_response_code(404);
    exit;
}

require_once __DIR__ . '/../config/env.php';
require_once __DIR__ . '/../config/as400.php';
require_once __DIR__ . '/../config/librerias.php';
require_once __DIR__ . '/../modelos/auditoria.modelo.php';
require_once __DIR__ . '/../servicios/Periodo.php';

/** Un argumento `--clave=valor`. */
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
    printf("\n%s\n%s\n", $texto, str_repeat('-', max(10, mb_strlen($texto))));
}

function bien(string $texto): void { printf("  [ok]    %s\n", $texto); }
function mal(string $texto): void  { printf("  [FALLO] %s\n", $texto); }
function ojo(string $texto): void  { printf("  [aviso] %s\n", $texto); }

function queHacer(string $texto): void
{
    printf("\n  Qué hacer:\n    %s\n", wordwrap($texto, 72, "\n    ", false));
}

printf("=== Comprobación del AS400 ====================================\n");
printf("    %s\n", date('d/m/Y H:i:s'));

/* --- 1. La configuración -------------------------------------------------- */

titulo('1. El archivo .env');

$faltan = [];

foreach (['AS400_HOST', 'AS400_USER', 'AS400_PASS'] as $clave) {
    if (trim((string) env($clave, '')) === '') {
        $faltan[] = $clave;
    }
}

if ($faltan !== []) {
    mal('Falta(n) en el .env: ' . implode(', ', $faltan));
    queHacer('Copie `.env.example` a `.env` y rellene esas claves con los valores '
        . 'que da el departamento de sistemas. El .env no se versiona a propósito.');
    exit(1);
}

bien('AS400_HOST = ' . env('AS400_HOST'));
bien('AS400_USER = ' . env('AS400_USER'));
bien('AS400_PASS = (puesta, ' . strlen((string) env('AS400_PASS', '')) . ' caracteres)');
bien('AS400_DRIVER = ' . env('AS400_DRIVER', '(el predeterminado)'));

$entorno = strtolower(trim((string) env('AS400_LIBRERIAS', 'desarrollo')));

if ($entorno === 'produccion') {
    bien('AS400_LIBRERIAS = produccion  ->  config/librerias.txt');
} else {
    ojo('AS400_LIBRERIAS = ' . $entorno . '  ->  config/libreriasDevs.txt');
    printf("          OJO: el mapa de desarrollo apunta IDP210 a `CFLORES.IDP210` y\n");
    printf("          IDP116N a `AGARAY.IDP116N`, que son COPIAS. Una auditoría «en\n");
    printf("          vivo» contra una copia de hace un mes es una auditoría falsa, y\n");
    printf("          no se nota mirando los números: salen, y están mal.\n");
    printf("          Para auditar de verdad: AS400_LIBRERIAS=produccion\n");
}

printf("\n  El mapa dice que los archivos de la auditoría son:\n");

global $archivos;

foreach (['IDP210', 'RTP325', 'IDP116N', 'IDTA116', 'ETP045'] as $alias) {
    printf("      %-9s -> %s\n", $alias, $archivos[$alias] ?? '(SIN DECLARAR)');
}

/* --- 2. La conexión ------------------------------------------------------- */

titulo('2. La conexión ODBC');

if (!function_exists('odbc_connect')) {
    mal('La extensión ODBC de PHP no está habilitada.');
    queHacer('En el php.ini de XAMPP, quite el punto y coma de `;extension=odbc` '
        . 'y reinicie Apache. Sin eso no hay forma de hablar con el AS400.');
    exit(1);
}

bien('La extensión ODBC de PHP está habilitada.');

try {
    $inicio = microtime(true);
    CONECTARAS400();
    bien(sprintf('Conectado con %s en %.2f s.', env('AS400_HOST'), microtime(true) - $inicio));
} catch (Throwable $e) {
    mal($e->getMessage());
    queHacer('Si el mensaje habla de la red: compruebe que puede llegar al servidor '
        . '(`ping ' . env('AS400_HOST') . '`). OJO con la VPN: mientras está activa, '
        . 'no se llega al AS400. Si habla del driver, compruebe que el nombre de '
        . 'AS400_DRIVER coincide EXACTAMENTE con el instalado (Panel de control -> '
        . 'Herramientas administrativas -> Origenes de datos ODBC -> Controladores).');
    exit(1);
}

/* --- 3. Los archivos ------------------------------------------------------ */

titulo('3. Los cinco archivos');

$comprobacion = ModeloAuditoria::comprobarArchivos();
$falla = false;

foreach ($comprobacion as $c) {
    if ($c['existe']) {
        bien(sprintf('%-9s %s', $c['alias'], $c['archivo']));
        continue;
    }

    $falla = true;
    mal(sprintf('%-9s %s  ·  %s', $c['alias'], $c['archivo'], $c['motivo']));
}

if ($falla) {
    queHacer('Corrija el mapa de bibliotecas: `config/librerias.txt` si '
        . 'AS400_LIBRERIAS=produccion, o `config/libreriasDevs.txt` si no. El formato '
        . 'de cada línea es `ALIAS;BIBLIOTECA.ARCHIVO`. Si el archivo existe con otro '
        . 'nombre, pregunte en sistemas en qué biblioteca está.');
    DESCONECTARAS400();
    exit(1);
}

/* --- 4. Los campos -------------------------------------------------------- */

titulo('4. Los campos que la aplicación lee');

/**
 * Qué campos necesita cada archivo.
 *
 * Esta lista es la especificación, y comprobarla cuesta una consulta al
 * catálogo del servidor. Convierte un «columna no encontrada» a mitad de la
 * descarga —con alguien esperando delante de la pantalla— en un aviso del
 * primer segundo que nombra el archivo y el campo. Importa de verdad porque el
 * mapa de desarrollo apunta a copias que pueden ser de otra versión.
 */
$necesarios = [
    'IDP210' => ['NFCEDC', 'NFAÑDC', 'NFMSDC', 'NFDIDC', 'NCDTDA', 'NTPDOC', 'NNMDOC',
        'NSTEVT', 'NTPDNC', 'NFCAPL', 'NTDAPL', 'NMODC1', 'NMODC2', 'NMODC6', 'NMODC7',
        'NMOOCG', 'NMOABO', 'NPZDC1', 'FLA002', 'FLA011', 'NCDVND', 'NHORAV', 'NCEDUL',
        'NNBCLI'],
    'RTP325' => ['RFCEDC', 'RFAÑDC', 'RFMSDC', 'RFDIDC', 'RCDTDA', 'RTPDOC', 'RNMDOC',
        'RMOND1', 'RMOND2', 'RPZDT1'],
    'IDP116N' => ['NFCEDC', 'NFAÑDC', 'NFMSDC', 'NFDIDC', 'FCDTDA', 'FTPDOC', 'FNMDOC',
        'FFMPGO', 'FMOFPG', 'F116CJ', 'FSTFPG', 'FCODDI', 'FMOFDI'],
    'IDTA116' => ['FFORPA', 'FFORPT', 'FDESPA', 'FDESPT'],
    'ETP045'  => ['ECDTDA', 'ENBTDA', 'ENBRZS', 'ESTTDA'],
];

$faltanCampos = false;

foreach ($necesarios as $alias => $campos) {
    $archivo = $archivos[$alias];
    $punto   = (int) strpos($archivo, '.');

    try {
        $sql = "SELECT COLUMN_NAME, DATA_TYPE, LENGTH, COALESCE(NUMERIC_SCALE, 0),
                       COALESCE(COLUMN_TEXT, '')
                  FROM QSYS2.SYSCOLUMNS
                 WHERE TABLE_SCHEMA = '" . substr($archivo, 0, $punto) . "'
                   AND TABLE_NAME   = '" . substr($archivo, $punto + 1) . "'
                 ORDER BY ORDINAL_POSITION";

        $st = odbc_exec($GLOBALS['dbconect'], utf8_a_as400($sql));

        if ($st === false) {
            throw new RuntimeException(as400_a_utf8(odbc_errormsg($GLOBALS['dbconect'])));
        }

        $existen = [];
        $total   = 0;

        while (odbc_fetch_row($st)) {
            /*
             * EL NOMBRE DEL CAMPO TAMBIÉN SE CONVIERTE, Y ESTO YA DIO UN
             * FALSO FALLO
             * -------------------------------------------------------------
             * `NFAÑDC` y `RFAÑDC` LLEVAN EÑE. El catálogo los devuelve en la
             * página de códigos del AS400 —la Ñ es un solo byte, 0xD1— y la
             * lista de más abajo está escrita en UTF-8, donde son dos. Sin
             * convertir, la comparación dice que el campo «falta» y el
             * informe imprime `NFA?DC` como campo parecido: el campo parecido
             * ES el campo, y lo único que había de distinto era la
             * codificación.
             *
             * La primera corrida contra producción dio exactamente eso: tres
             * archivos marcados en rojo por un campo que estaba, mientras el
             * paso 5 —que usa las consultas de verdad— leía los tres sin un
             * problema. Un comprobador que da un fallo donde no lo hay es
             * peor que no tenerlo: la próxima vez nadie se lo cree.
             */
            $campo = as400_a_utf8(trim((string) odbc_result($st, 1)));
            $campo = mb_strtoupper((string) $campo, 'UTF-8');

            $existen[$campo] = [
                'tipo'   => trim((string) odbc_result($st, 2)),
                'largo'  => (int) odbc_result($st, 3),
                'escala' => (int) odbc_result($st, 4),
                'texto'  => as400_a_utf8(trim((string) odbc_result($st, 5))),
            ];
            $total++;
        }

        odbc_free_result($st);

        $ausentes = [];

        foreach ($campos as $campo) {
            if (!isset($existen[$campo])) {
                $ausentes[] = $campo;
            }
        }

        if ($ausentes === []) {
            bien(sprintf('%-9s los %d campos que hacen falta están (el archivo tiene %d)',
                $alias, count($campos), $total));
        } else {
            $faltanCampos = true;
            mal(sprintf('%-9s FALTAN %d: %s', $alias, count($ausentes), implode(', ', $ausentes)));

            printf("            El archivo tiene %d campos. Los que empiezan parecido:\n", $total);

            foreach ($ausentes as $campo) {
                $parecidos = [];

                foreach (array_keys($existen) as $real) {
                    if (substr($real, 0, 3) === substr($campo, 0, 3)) {
                        $parecidos[] = $real;
                    }
                }

                printf("              %s  ->  %s\n", $campo,
                    $parecidos === [] ? '(ninguno)' : implode(' ', array_slice($parecidos, 0, 12)));
            }
        }
    } catch (Throwable $e) {
        $faltanCampos = true;
        mal(sprintf('%-9s no se pudo leer el catálogo: %s', $alias, $e->getMessage()));
    }
}

if ($faltanCampos) {
    queHacer('Si falta un campo, hay dos posibilidades. La primera, y la más probable '
        . 'con el mapa de desarrollo: se está mirando OTRO archivo (una copia vieja). '
        . 'La segunda: el campo se llama distinto, y entonces hay que corregir su '
        . 'nombre en `modelos/auditoria.modelo.php` y en la lista de este script. La '
        . 'lista de campos parecidos de arriba es para eso.');
}

/* --- 5. Una consulta de verdad -------------------------------------------- */

titulo('5. Una consulta de verdad');

$fecha = (string) arg('fecha', date('Y-m-d', strtotime('-1 day')));

try {
    $periodo = Periodo::de($fecha, $fecha);
} catch (Throwable $e) {
    mal($e->getMessage());
    DESCONECTARAS400();
    exit(1);
}

printf("  Día de prueba: %s  (cámbielo con --fecha=AAAA-MM-DD)\n\n", Periodo::corta($fecha));

try {
    $t = microtime(true);
    $enc = ModeloAuditoria::encabezados($periodo);
    printf("  %-34s %6d filas   %5.2f s\n", 'IDP210  encabezados',
        count($enc['documentos']), microtime(true) - $t);

    if ($enc['sin_fecha'] > 0) {
        ojo($enc['sin_fecha'] . ' encabezado(s) con una fecha imposible, descartados.');
    }

    $t = microtime(true);
    $det = ModeloAuditoria::detalle($periodo);
    printf("  %-34s %6d docs    %5.2f s\n", 'RTP325  detalle (agrupado)',
        count($det), microtime(true) - $t);

    $t = microtime(true);
    $pag = ModeloAuditoria::pagos($periodo);
    printf("  %-34s %6d docs    %5.2f s\n", 'IDP116N formas de pago',
        count($pag), microtime(true) - $t);

    $t = microtime(true);
    $cat = ModeloAuditoria::catalogoFormas();
    printf("  %-34s %6d formas  %5.2f s\n", 'IDTA116 catálogo',
        count($cat), microtime(true) - $t);

    $t = microtime(true);
    $tie = ModeloAuditoria::tiendas();
    printf("  %-34s %6d tiendas %5.2f s\n", 'ETP045  tiendas',
        count($tie), microtime(true) - $t);
} catch (Throwable $e) {
    printf("\n");
    mal($e->getMessage());
    queHacer('Si el mensaje dice «columna no encontrada» y el paso 4 dio todo bien, '
        . 'mire si el nombre que aparece lleva EÑE: `NFAÑDC`. Ese campo existe y la '
        . 'consulta tiene que ir convertida a la página de códigos del AS400, lo que '
        . 'hace `ModeloAS400::ejecutar()`. Si el mensaje habla de tiempo de espera, el '
        . 'día de prueba puede ser uno con mucho movimiento: pruebe otro.');
    DESCONECTARAS400();
    exit(1);
}

if ($enc['documentos'] === []) {
    printf("\n");
    ojo('Ese día no tiene ni un documento en IDP210.');
    printf("          Puede ser un domingo o un feriado. Pruebe con otro día:\n");
    printf("          php cli/probar-as400.php --fecha=AAAA-MM-DD\n");
    DESCONECTARAS400();
    exit(0);
}

/* --- Lo que se leyó, para poder mirarlo ----------------------------------- */

titulo('6. Las tres primeras filas, tal como llegaron');

foreach (array_slice($enc['documentos'], 0, 3) as $i => $d) {
    printf("\n  --- documento %d ---------------------------------------------\n", $i + 1);
    printf("    clave           %s\n", $d['clave']);
    printf("    fecha           %s\n", $d['fecha']);
    printf("    tienda          %d  %s\n", $d['codigo_as400'],
        $tie[$d['codigo_as400']]['nombre'] ?? '(no está en ETP045)');
    printf("    documento       %s %d   estatus %s   clase NC «%s»\n",
        $d['tipo_doc'], $d['numero_doc'], $d['estatus'], $d['tipo_nc']);
    printf("    cliente         %s  (%s)\n", $d['cliente_nombre'], $d['cliente_cedula']);
    printf("    vendedor/hora   %s  %s\n", $d['vendedor'], $d['hora'] ?? '(sin hora válida)');
    printf("    bruto           %14s\n", number_format($d['monto_bruto'], 2, ',', '.'));
    printf("    descuento       %14s\n", number_format($d['descuento'], 2, ',', '.'));
    printf("    IVA             %14s\n", number_format($d['iva'], 2, ',', '.'));
    printf("    IGTF            %14s\n", number_format($d['igtf'], 2, ',', '.'));
    printf("    dscto SENIAT    %14s   <- tiene que ser 0,00\n",
        number_format($d['dscto_seniat'], 2, ',', '.'));
    printf("    abono           %14s   <- 0,00 salvo en NC clase 3\n",
        number_format($d['abono'], 2, ',', '.'));
    printf("    TOTAL calculado %14s   (bruto - dscto + IVA + IGTF)\n",
        number_format($d['monto_bruto'] - $d['descuento'] + $d['iva'] + $d['igtf'], 2, ',', '.'));

    $suDetalle = $det[$d['clave']] ?? null;
    $suPago    = $pag[$d['clave']] ?? null;

    printf("    detalle         %s\n", $suDetalle === null
        ? 'SIN LÍNEAS en RTP325'
        : sprintf('%d línea(s), bruto %s, dscto %s, %d piezas',
            $suDetalle['lineas'],
            number_format($suDetalle['bruto'], 2, ',', '.'),
            number_format($suDetalle['descuento'], 2, ',', '.'),
            $suDetalle['piezas']));

    if ($suPago === null) {
        printf("    pagos           SIN LÍNEAS en IDP116N\n");
    } else {
        printf("    pagos           %d línea(s), total %s, caja %s\n",
            $suPago['formas'], number_format($suPago['pagado'], 2, ',', '.'), $suPago['caja']);

        foreach ($suPago['lineas'] as $l) {
            printf("                      %-4s %-30s %14s\n", $l['forma'],
                $cat[$l['forma']]['descripcion'] ?? '(no está en IDTA116)',
                number_format($l['monto'], 2, ',', '.'));
        }
    }
}

/* --- El cruce, que es lo que de verdad hay que comprobar ------------------ */

titulo('7. ¿Cruzan las claves entre los tres archivos?');

/*
 * Esto es LA comprobación que importa, y la que no se puede hacer sin el
 * servidor. El número de documento es `DECIMAL(8,0)` y el driver ODBC no
 * entrega siempre el mismo texto para el mismo número: si no cruzan, el informe
 * sale con TODO descuadrado y sin un solo error que lo delate. Un «0 de 120»
 * aquí no es un detalle, es que el informe no sirve.
 */
$conDetalle = 0;
$conPago    = 0;

foreach ($enc['documentos'] as $d) {
    if (isset($det[$d['clave']])) { $conDetalle++; }
    if (isset($pag[$d['clave']])) { $conPago++; }
}

$total = count($enc['documentos']);

printf("  Encabezados del día                 %6d\n", $total);
printf("  …que encuentran su detalle          %6d de %d  (%.1f %%)\n",
    $conDetalle, $total, $total > 0 ? $conDetalle / $total * 100 : 0);
printf("  …que encuentran sus formas de pago  %6d de %d  (%.1f %%)\n",
    $conPago, $total, $total > 0 ? $conPago / $total * 100 : 0);

printf("\n  Y al revés, lo que sobra:\n");
printf("  Documentos con detalle y sin encabezado  %6d\n",
    count(array_diff_key($det, array_column($enc['documentos'], null, 'clave'))));
printf("  Documentos con pagos y sin encabezado    %6d\n",
    count(array_diff_key($pag, array_column($enc['documentos'], null, 'clave'))));

if ($total > 0 && $conPago / $total < 0.5) {
    printf("\n");
    mal('Menos de la mitad de los documentos encuentran sus formas de pago.');
    queHacer('Esto casi siempre es la clave que no cruza, no dinero que falte. '
        . 'Pásele a quien escribió esto la salida COMPLETA de este script: lo que hay '
        . 'que mirar es cómo llega `NNMDOC` desde IDP210 y `FNMDOC` desde IDP116N, '
        . 'porque el cruce se hace por ese número y el driver puede entregarlo con '
        . 'formatos distintos en cada archivo.');
} else {
    printf("\n");
    bien('Las claves cruzan. Es lo que de verdad había que comprobar.');
}

DESCONECTARAS400();

printf("\n=== Terminado =================================================\n");
printf("Si todo salió bien, la pantalla ya se puede abrir. Y para sacar el\n");
printf("Excel sin navegador:\n\n");
printf("    php cli/auditoria.php --mes=%s\n\n", date('Y-m'));

exit(0);
