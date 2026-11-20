<?php

declare(strict_types=1);

/**
 * Lo que la auditoría lee del AS400, en vivo.
 *
 * ===========================================================================
 *  EL DOCUMENTO VIVE EN TRES ARCHIVOS, Y LOS TRES TIENEN QUE CONTAR LO MISMO
 * ---------------------------------------------------------------------------
 *      IDP210    el ENCABEZADO: cuánto se vendió
 *      RTP325    el DETALLE:    qué se vendió
 *      IDP116N   los PAGOS:     con qué se pagó
 *
 *  Más dos maestros para poder nombrar lo que se encuentra:
 *
 *      IDTA116   el catálogo de formas de pago
 *      ETP045    el maestro de tiendas
 * ===========================================================================
 *
 * CINCO CONSULTAS Y EL CRUCE EN PHP, NO UNA CONSULTA CON JOINS
 * ------------------------------------------------------------
 * La versión de este informe que lee de MySQL lo hace en una sola sentencia
 * con dos subconsultas agregadas y un `GROUP_CONCAT`. Aquí no, y por razones
 * concretas:
 *
 * 1. `GROUP_CONCAT` **no existe en DB2 for i**. Su equivalente es `LISTAGG`,
 *    que está desde la 7.2 y necesita que la consulta la resuelva el motor SQL
 *    y no el acceso nativo. Apostar el informe a eso, sin poder probarlo
 *    contra el servidor, es apostar a ciegas. El desglose de formas de pago se
 *    arma en PHP, que no depende de la versión de nada.
 *
 * 2. Un `LEFT JOIN` contra dos subconsultas agregadas sobre 170.000 filas, en
 *    una sesión ODBC, es exactamente el tipo de consulta que el AS400 resuelve
 *    con una tabla temporal y un plan que no se puede ver desde aquí. Cinco
 *    consultas simples —tres filtradas por fecha y dos maestros completos— son
 *    cinco planes triviales.
 *
 * 3. Si una falla, se sabe cuál. Con una sentencia de sesenta líneas, un
 *    «columna no encontrada» no dice de qué archivo viene.
 *
 * El cruce son tres `foreach` sobre arrays indexados por la clave del
 * documento: nada que el AS400 haga mejor.
 *
 * LA CLAVE DEL DOCUMENTO, Y POR QUÉ SE NORMALIZA
 * ----------------------------------------------
 * Un documento es `fecha + tienda + tipo + número`. Los tres archivos la
 * guardan con los mismos valores pero el driver ODBC no los entrega iguales:
 * `NNMDOC` es `DECIMAL(8,0)` y puede llegar como `26829`, `26829.` o
 * `00026829` según el archivo y el controlador. Comparar esos textos entre sí
 * **no empareja**, y el informe saldría con todo descuadrado y sin un error que
 * lo delate. Por eso cada parte numérica de la clave pasa por `(int)` antes de
 * componerla.
 *
 * LAS FILAS VIENEN POR POSICIÓN, NO POR NOMBRE
 * --------------------------------------------
 * Es la norma de `ModeloAS400` y aquí importa el doble: dos de estas consultas
 * llevan `COUNT(*)` y `SUM(...)` sin alias, y el nombre que el driver les
 * inventa no es estable. Cada consulta traduce sus posiciones a nombres en el
 * mismo método que la lanza, para que el orden del `SELECT` y el del array se
 * lean juntos.
 */

require_once __DIR__ . '/as400.modelo.php';
require_once __DIR__ . '/../servicios/Periodo.php';

final class ModeloAuditoria extends ModeloAS400
{
    /**
     * Los tipos de documento que son venta.
     *
     * Los mismos cuatro que usa el ETL del proyecto hermano: facturas (`FC`
     * normal, `FE` electrónica) y notas de crédito (`NC`, `NE`).
     */
    public const TIPOS = ['FC', 'FE', 'NC', 'NE'];

    /**
     * La condición de fecha del rango, con el prefijo de campos que toque.
     *
     * `IDP210` e `IDP116N` nombran sus campos de fecha con `N` —`NFCEDC`,
     * `NFAÑDC`, `NFMSDC`, `NFDIDC`— y `RTP325` con `R`. Es el único sitio
     * donde esa diferencia aparece, y por eso el prefijo es un parámetro y no
     * tres consultas copiadas.
     *
     * Los números van incrustados y no con marcadores `?` a propósito: salen
     * de `Periodo`, que ya los validó como enteros, y el driver manda los
     * parámetros como carácter — comparar un carácter contra una columna
     * numérica del AS400 **no encuentra nada y no da error**, que es la peor
     * forma de fallar que tiene este servidor.
     */
    private static function filtroFecha(Periodo $periodo, string $p): string
    {
        $trozos = [];

        foreach ($periodo->tramos() as $t) {
            $trozos[] = sprintf(
                '(%1$sFCEDC = %2$d AND %1$sFAÑDC = %3$d AND %1$sFMSDC = %4$d'
                . ' AND %1$sFDIDC BETWEEN %5$d AND %6$d)',
                $p, $t['siglo'], $t['anio'], $t['mes'], $t['dia_desde'], $t['dia_hasta']
            );
        }

        return '(' . implode(' OR ', $trozos) . ')';
    }

    /** `'FC','FE','NC','NE'`, listo para un `IN`. */
    private static function tiposSql(): string
    {
        return "'" . implode("','", self::TIPOS) . "'";
    }

    /**
     * La clave del documento, igual se mire desde donde se mire.
     *
     * Ver la cabecera: las partes numéricas pasan por `(int)` porque el driver
     * no entrega el mismo texto para el mismo número en los tres archivos.
     */
    public static function clave(string $fecha, int $tienda, string $tipo, int $numero): string
    {
        return $fecha . '|' . $tienda . '|' . strtoupper(trim($tipo)) . '|' . $numero;
    }

    /**
     * La fecha ISO de los cuatro campos del AS400, o null si es imposible.
     *
     * Un día imposible no se adivina ni se descarta en silencio: se devuelve
     * null y quien agrega lo cuenta aparte. Un documento con la fecha mal es
     * un hallazgo de la auditoría, no una fila que estorba.
     */
    private static function fecha(int $siglo, int $anio2, int $mes, int $dia): ?string
    {
        $anio = $siglo * 100 + $anio2;

        return checkdate($mes, $dia, $anio)
            ? sprintf('%04d-%02d-%02d', $anio, $mes, $dia)
            : null;
    }

    /* =====================================================================
     *  1. Encabezados — IDP210
     * ===================================================================== */

    /**
     * Un encabezado por documento del rango.
     *
     * Los campos y lo que significa cada uno están en el doc 10 del proyecto
     * hermano, §1.1, sacados del volcado del catálogo del AS400:
     *
     *      NSTEVT  estatus; '9' es ANULADO
     *      NTPDNC  clase de nota de crédito: 1=DEV 2=AJUS 3=ABON
     *      NMODC1  monto bruto          NMODC2  descuentos
     *      NMODC6  I.V.A.               NMODC7  descuento SENIAT
     *      NMOOCG  otros cargos, que es el IGTF
     *      NMOABO  monto abono          NPZDC1  piezas
     *      FLA002  la tasa BCV con la que se generó
     *      FLA011  'M' si la factura es manual
     *      NFCAPL / NTDAPL  la factura a la que aplica la nota de crédito
     *
     * @return array{documentos:list<array<string,mixed>>,sin_fecha:int}
     */
    public static function encabezados(Periodo $periodo): array
    {
        $idp210 = self::archivo('IDP210');

        $filas = self::filas(
            'SELECT NFCEDC, NFAÑDC, NFMSDC, NFDIDC,
                    NCDTDA, NTPDOC, NNMDOC,
                    NSTEVT, NTPDNC, NFCAPL, NTDAPL,
                    NMODC1, NMODC2, NMODC6, NMODC7, NMOOCG, NMOABO,
                    NPZDC1, FLA002, FLA011,
                    NCDVND, NHORAV, NCEDUL, NNBCLI
               FROM ' . $idp210 . '
              WHERE ' . self::filtroFecha($periodo, 'N') . '
                AND NTPDOC IN (' . self::tiposSql() . ')
              ORDER BY NFAÑDC, NFMSDC, NFDIDC, NCDTDA, NTPDOC, NNMDOC'
        );

        $documentos = [];
        $sinFecha   = 0;

        foreach ($filas as $f) {
            $fecha = self::fecha((int) $f[0], (int) $f[1], (int) $f[2], (int) $f[3]);

            if ($fecha === null) {
                $sinFecha++;
                continue;
            }

            $tienda = (int) $f[4];
            $tipo   = strtoupper(trim((string) $f[5]));
            $numero = (int) $f[6];

            $documentos[] = [
                'clave'            => self::clave($fecha, $tienda, $tipo, $numero),
                'fecha'            => $fecha,
                'codigo_as400'     => $tienda,
                'tipo_doc'         => $tipo,
                'numero_doc'       => $numero,
                'estatus'          => trim((string) $f[7]),
                'tipo_nc'          => trim((string) $f[8]),
                'factura_aplicada' => (int) $f[9],
                'tienda_aplicada'  => (int) $f[10],
                'monto_bruto'      => (float) $f[11],
                'descuento'        => (float) $f[12],
                'iva'              => (float) $f[13],
                'dscto_seniat'     => (float) $f[14],
                'igtf'             => (float) $f[15],
                'abono'            => (float) $f[16],
                'unidades'         => (int) $f[17],
                'tasa_bcv_doc'     => (float) $f[18],
                'manual'           => strtoupper(trim((string) $f[19])) === 'M',
                'vendedor'         => trim((string) $f[20]),
                'hora'             => self::hora((string) $f[21]),
                'cliente_cedula'   => trim((string) $f[22]),
                'cliente_nombre'   => trim((string) $f[23]),
            ];
        }

        return ['documentos' => $documentos, 'sin_fecha' => $sinFecha];
    }

    /* =====================================================================
     *  2. Detalle — RTP325, ya agregado por el AS400
     * ===================================================================== */

    /**
     * Cuántas líneas, cuánto bruto, cuánto descuento y cuántas piezas por
     * documento.
     *
     * Esto sí se agrupa en el servidor, y no por elegancia: son del orden de
     * 12.000 líneas por mes y de cada una sólo interesan cuatro sumas. Traerlas
     * enteras para sumarlas aquí sería mover cuarenta veces más datos por la
     * red para llegar al mismo número.
     *
     * No se filtra por estatus, igual que en la versión de MySQL: un documento
     * anulado conserva sus líneas, y eso —que parece un descuadre y no lo es—
     * es precisamente uno de los casos que el informe tiene que saber explicar.
     *
     * @return array<string,array{lineas:int,bruto:float,descuento:float,piezas:int}>
     */
    public static function detalle(Periodo $periodo): array
    {
        $rtp325 = self::archivo('RTP325');

        $filas = self::filas(
            'SELECT RFCEDC, RFAÑDC, RFMSDC, RFDIDC,
                    RCDTDA, RTPDOC, RNMDOC,
                    COUNT(*), SUM(RMOND1), SUM(RMOND2), SUM(RPZDT1)
               FROM ' . $rtp325 . '
              WHERE ' . self::filtroFecha($periodo, 'R') . '
                AND RTPDOC IN (' . self::tiposSql() . ')
              GROUP BY RFCEDC, RFAÑDC, RFMSDC, RFDIDC, RCDTDA, RTPDOC, RNMDOC'
        );

        $porDocumento = [];

        foreach ($filas as $f) {
            $fecha = self::fecha((int) $f[0], (int) $f[1], (int) $f[2], (int) $f[3]);

            if ($fecha === null) {
                continue;
            }

            $clave = self::clave($fecha, (int) $f[4], (string) $f[5], (int) $f[6]);

            $porDocumento[$clave] = [
                'lineas'    => (int) $f[7],
                'bruto'     => (float) $f[8],
                'descuento' => (float) $f[9],
                'piezas'    => (int) $f[10],
            ];
        }

        return $porDocumento;
    }

    /* =====================================================================
     *  3. Formas de pago — IDP116N, línea a línea
     * ===================================================================== */

    /**
     * Las líneas de pago del rango, SIN agrupar.
     *
     * Aquí no se agrupa, al contrario que el detalle, y es deliberado: el
     * informe tiene que escribir el desglose —«PAGO MOVIL 46.916,44 + PUNTO
     * 12.000,00»— y para eso necesita las líneas. Son del orden de 5.200 al
     * mes: traerlas cuesta nada y permite además contar las formas tal como las
     * cuenta la versión de MySQL, por LÍNEA y no por forma distinta.
     *
     * Y por eso mismo **no se agrupa por `FCONSC`**: parecía el renglón, y al
     * cargar tres años en el proyecto hermano aparecieron once documentos donde
     * dos pagos comparten consecutivo. Contar líneas no depende de eso.
     *
     *      FFMPGO  la forma de pago       FMOFPG  su monto en bolívares
     *      F116CJ  la caja                FSTFPG  el estatus de la línea
     *      FCODDI  la divisa              FMOFDI  el monto en divisa
     *
     * @return array<string,array{formas:int,pagado:float,caja:string,lineas:list<array{forma:string,monto:float}>}>
     */
    public static function pagos(Periodo $periodo): array
    {
        $idp116n = self::archivo('IDP116N');

        $filas = self::filas(
            'SELECT NFCEDC, NFAÑDC, NFMSDC, NFDIDC,
                    FCDTDA, FTPDOC, FNMDOC,
                    FFMPGO, FMOFPG, F116CJ, FSTFPG, FCODDI, FMOFDI
               FROM ' . $idp116n . '
              WHERE ' . self::filtroFecha($periodo, 'N') . '
                AND FTPDOC IN (' . self::tiposSql() . ')
              ORDER BY FCDTDA, NFDIDC, FTPDOC, FNMDOC, FMOFPG DESC'
        );

        $porDocumento = [];

        foreach ($filas as $f) {
            $fecha = self::fecha((int) $f[0], (int) $f[1], (int) $f[2], (int) $f[3]);

            if ($fecha === null) {
                continue;
            }

            $clave = self::clave($fecha, (int) $f[4], (string) $f[5], (int) $f[6]);
            $forma = strtoupper(trim((string) $f[7]));
            $monto = (float) $f[8];

            if (!isset($porDocumento[$clave])) {
                $porDocumento[$clave] = [
                    'formas' => 0,
                    'pagado' => 0.0,
                    'caja'   => trim((string) $f[9]),
                    'lineas' => [],
                ];
            }

            $porDocumento[$clave]['formas']++;
            $porDocumento[$clave]['pagado'] += $monto;
            $porDocumento[$clave]['lineas'][] = ['forma' => $forma, 'monto' => $monto];

            /*
             * La caja: la primera que aparezca y que no venga vacía. La
             * versión de MySQL usa `MIN(caja)`, que es lo mismo cuando todas
             * las líneas del documento traen la misma —que es lo normal— y no
             * vale la pena hacerlo coincidir cuando no, porque entonces el
             * dato es ambiguo en el origen.
             */
            if ($porDocumento[$clave]['caja'] === '' && trim((string) $f[9]) !== '') {
                $porDocumento[$clave]['caja'] = trim((string) $f[9]);
            }
        }

        return $porDocumento;
    }

    /* =====================================================================
     *  4. El catálogo de formas de pago — IDTA116
     * ===================================================================== */

    /**
     * Una fila por forma de pago, con su descripción y su tipo.
     *
     * AGRUPADO A PROPÓSITO, Y ESTO CUESTA DINERO SI SE OLVIDA
     * -------------------------------------------------------
     * `IDTA116` tiene **varias filas por forma de pago**, una por combinación
     * de marca y divisa. Un `JOIN` por `FFORPA` contra las líneas de pago
     * duplicaría cada línea tantas veces como filas tenga su forma, e inflaría
     * el total pagado sin que nada avisara: el informe diría que todo cuadra
     * de más. De ahí que el catálogo se lea aparte y agrupado, y que la
     * consulta de pagos no una con nada.
     *
     * Devuelve además cuántos tipos distintos tiene cada forma. Si alguna
     * tuviera más de uno, «¿esta forma es financiamiento?» dejaría de tener
     * respuesta, y quien llama tiene que decirlo en lugar de elegir una.
     *
     * @return array<string,array{codigo:string,tipo:string,descripcion:string,tipo_nombre:string,tipos:int,filas:int}>
     */
    public static function catalogoFormas(): array
    {
        $idta116 = self::archivo('IDTA116');

        $filas = self::filas(
            'SELECT FFORPA, MIN(FFORPT), MIN(FDESPA), MIN(FDESPT),
                    COUNT(DISTINCT FFORPT), COUNT(*)
               FROM ' . $idta116 . '
              GROUP BY FFORPA
              ORDER BY FFORPA'
        );

        $catalogo = [];

        foreach ($filas as $f) {
            $codigo = strtoupper(trim((string) $f[0]));

            if ($codigo === '') {
                continue;
            }

            $catalogo[$codigo] = [
                'codigo'      => $codigo,
                'tipo'        => strtoupper(trim((string) $f[1])),
                'descripcion' => trim((string) $f[2]),
                'tipo_nombre' => trim((string) $f[3]),
                'tipos'       => (int) $f[4],
                'filas'       => (int) $f[5],
            ];
        }

        return $catalogo;
    }

    /* =====================================================================
     *  5. El maestro de tiendas — ETP045
     * ===================================================================== */

    /**
     * Código de tienda => su nombre.
     *
     * EL NOMBRE ESTÁ EN `ENBTDA`, NO EN `ENBRZS`
     * ------------------------------------------
     * `ENBRZS` es la RAZÓN SOCIAL —la empresa que opera el local— y `ENBTDA`
     * es el nombre de la tienda. El programa que lleva años en producción
     * (`reporteVentasDiariasV5`) llena su combo con `ENBRZS` porque le basta
     * para identificar el local, y de ahí salió la confusión que el sondeo del
     * 10/11/2026 del proyecto hermano desmintió. El código 12 lo deja claro:
     *
     *      ENBTDA  RORI PORLAMAR            <- el nombre
     *      ENBRZS  COMERCIAL NEW MAR, C.A.  <- la empresa
     *
     * Se leen TODAS, activas y cerradas, no sólo las de `ESTTDA = 'A'`: una
     * tienda que cerró en marzo tiene facturas en febrero, y auditar febrero
     * con la tienda sin nombre sería peor informe por nada.
     *
     * @return array<int,array{nombre:string,razon_social:string,activa:bool}>
     */
    public static function tiendas(): array
    {
        $etp045 = self::archivo('ETP045');

        $filas = self::filas(
            'SELECT ECDTDA, ENBTDA, ENBRZS, ESTTDA
               FROM ' . $etp045 . '
              ORDER BY ECDTDA'
        );

        $tiendas = [];

        foreach ($filas as $f) {
            $codigo = (int) $f[0];
            $nombre = trim((string) $f[1]);
            $razon  = trim((string) $f[2]);

            $tiendas[$codigo] = [
                // Si el nombre viene vacío, la razón social al menos identifica
                // el local; un hueco no identifica nada.
                'nombre'       => $nombre !== '' ? $nombre : $razon,
                'razon_social' => $razon,
                'activa'       => strtoupper(trim((string) $f[3])) === 'A',
            ];
        }

        return $tiendas;
    }

    /* =====================================================================
     *  Comprobación previa
     * ===================================================================== */

    /**
     * ¿Están los cinco archivos donde el mapa dice que están?
     *
     * Cuesta una consulta trivial y convierte un «archivo no encontrado» a
     * mitad de la descarga —con el usuario esperando y sin saber cuál de los
     * cinco falló— en un mensaje del primer segundo que nombra el archivo y la
     * biblioteca. Importa de verdad en este proyecto: el mapa de desarrollo
     * apunta `IDP210` a `CFLORES.IDP210` y `IDP116N` a `AGARAY.IDP116N`, que
     * son COPIAS. Una auditoría «en vivo» contra una copia de hace un mes es
     * una auditoría falsa, y no se nota mirando los números.
     *
     * @return list<array{alias:string,archivo:string,existe:bool,motivo:string}>
     */
    public static function comprobarArchivos(): array
    {
        $resultado = [];

        foreach (['IDP210', 'RTP325', 'IDP116N', 'IDTA116', 'ETP045'] as $alias) {
            try {
                $archivo = self::archivo($alias);
            } catch (Throwable $e) {
                $resultado[] = [
                    'alias'   => $alias,
                    'archivo' => '(sin declarar)',
                    'existe'  => false,
                    'motivo'  => $e->getMessage(),
                ];
                continue;
            }

            $punto = strpos($archivo, '.');

            if ($punto === false) {
                $resultado[] = [
                    'alias'   => $alias,
                    'archivo' => $archivo,
                    'existe'  => false,
                    'motivo'  => 'El mapa de bibliotecas no lo declara como BIBLIOTECA.ARCHIVO.',
                ];
                continue;
            }

            try {
                $fila = self::primeraFila(
                    'SELECT COUNT(*)
                       FROM QSYS2.SYSTABLES
                      WHERE TABLE_SCHEMA = ' . self::literalTexto(substr($archivo, 0, $punto)) . '
                        AND TABLE_NAME   = ' . self::literalTexto(substr($archivo, $punto + 1))
                );

                $existe = ((int) ($fila[0] ?? 0)) > 0;

                $resultado[] = [
                    'alias'   => $alias,
                    'archivo' => $archivo,
                    'existe'  => $existe,
                    'motivo'  => $existe ? '' : 'El AS400 no tiene ese archivo en esa biblioteca.',
                ];
            } catch (Throwable $e) {
                $resultado[] = [
                    'alias'   => $alias,
                    'archivo' => $archivo,
                    'existe'  => false,
                    'motivo'  => $e->getMessage(),
                ];
            }
        }

        return $resultado;
    }

    /**
     * `NHORAV` es un número `HHMMSS`, no una hora.
     *
     * Devuelve `HH:MM:SS` o null si no es una hora válida. Un valor imposible
     * se deja en null y no tumba el documento: la hora no participa de ninguna
     * cifra del informe.
     */
    public static function hora(string $numero): ?string
    {
        $soloDigitos = preg_replace('/\D/', '', $numero) ?? '';

        if ($soloDigitos === '') {
            return null;
        }

        $limpio = str_pad($soloDigitos, 6, '0', STR_PAD_LEFT);

        if (strlen($limpio) !== 6) {
            return null;
        }

        $h = (int) substr($limpio, 0, 2);
        $m = (int) substr($limpio, 2, 2);
        $s = (int) substr($limpio, 4, 2);

        return ($h < 24 && $m < 60 && $s < 60)
            ? sprintf('%02d:%02d:%02d', $h, $m, $s)
            : null;
    }
}
