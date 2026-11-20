<?php

declare(strict_types=1);

/**
 * Auditoría de formas de pago: ¿cuadra cada factura con lo que se pagó?
 *
 * ===========================================================================
 *  LA PREGUNTA
 * ---------------------------------------------------------------------------
 *  Un documento del AS400 vive en tres archivos:
 *
 *      IDP210    el ENCABEZADO: cuánto se vendió
 *      RTP325    el DETALLE:    qué se vendió
 *      IDP116N   los PAGOS:     con qué se pagó
 *
 *  Los tres tienen que contar lo mismo. Si la suma de las formas de pago no
 *  llega al total de la factura, falta un pago por asentar: dinero cobrado que
 *  no está registrado, o un financiamiento que nadie anotó.
 *
 *  Nadie lo mira hoy. No porque no importe, sino porque a mano son del orden
 *  de 3.800 documentos al mes contra 5.200 líneas de pago.
 * ===========================================================================
 *
 * ESTO SE LEE DEL AS400 EN VIVO
 * -----------------------------
 * La primera versión de este informe leía de un MySQL que el ETL carga de
 * madrugada, y por eso tenía que avisar de los días que todavía no se habían
 * descargado: lo que no estaba cargado no se auditaba, y un informe vacío no
 * es un informe de que todo está bien. Aquí ese problema no existe —se
 * pregunta al AS400 y contesta el AS400— y el aviso correspondiente se ha
 * quitado en lugar de dejarlo diciendo algo que ya no es verdad.
 *
 * Lo que sí se conserva entero es el JUICIO, porque el juicio no salió de la
 * base de datos: salió de medir. Todo lo que viene a continuación está medido
 * sobre los 3.626 documentos de noviembre de 2026 y, donde se dice, sobre los
 * tres años cargados.
 *
 * EL TOTAL DE LA FACTURA NO SE SUPUSO: SE MIDIÓ
 * ---------------------------------------------
 * `IDP210` trae seis importes y ninguno se llama «total». Se probaron las diez
 * combinaciones razonables contra la suma de pagos de los 3.626 documentos, y
 * el resultado no deja lugar a duda:
 *
 *      monto_bruto                                 124 de 3.626    3,4 %
 *      monto_bruto - descuento                     186 de 3.626    5,1 %
 *      monto_bruto - descuento + iva             3.551 de 3.626   97,9 %
 *      monto_bruto - descuento + iva + igtf      3.571 de 3.626   98,5 %   <-
 *      venta_bs + iva + igtf                     3.476 de 3.626   95,9 %
 *
 * Y el IGTF no es opcional: añadirlo arregla 20 documentos y **no rompe ni
 * uno**. Eso es lo que lo convierte en parte de la fórmula y no en una
 * corrección a ojo.
 *
 * LOS DOS IMPORTES QUE NO ENTRAN, Y EL AVISO QUE LO VIGILA
 * --------------------------------------------------------
 * `dscto_seniat` (NMODC7) y `abono` (NMOABO) valen CERO en los 3.626
 * documentos del período medido, así que sumarlos o no da exactamente el mismo
 * resultado y meterlos en la fórmula sería adivinar su signo con cero
 * evidencia. Se quedan fuera — y `avisos()` comprueba que sigan en cero. El
 * día que uno aparezca, el informe lo dice en lugar de callárselo: la fórmula
 * habría que revisarla, y nadie se enteraría.
 *
 * LAS TRES CLASES, Y POR QUÉ EL CORTE ESTÁ DONDE ESTÁ
 * ---------------------------------------------------
 * Las diferencias de noviembre no se reparten por una pendiente: forman dos
 * grupos separados por un abismo.
 *
 *      47 documentos entre 0,02 y 4,38 Bs   <- 45 de ellos con IGTF
 *       8 documentos entre 2.000,00 y 168.136,17 Bs
 *
 * Entre 4,38 y 2.000,00 no hay NADA. Por eso el corte en 5 Bs no es un número
 * elegido para que salgan pocos avisos: cae dentro de un hueco de tres órdenes
 * de magnitud, y moverlo a 10, a 100 o a 1.000 clasificaría exactamente igual.
 *
 * El grupo pequeño tiene causa conocida: el IGTF es el 3 % y el AS400 lo
 * calcula sobre el total del documento, mientras que las líneas de pago lo
 * guardan redondeado por línea. Son céntimos de redondeo, no dinero perdido.
 *
 * LO QUE NO SE MARCA EN AMARILLO, AUNQUE LO PAREZCA
 * -------------------------------------------------
 * 1. Las 98 ANULADAS del período (`NSTEVT = '9'`) llevan cero piezas y cero
 *    venta en el encabezado pero conservan sus líneas de detalle. Es el
 *    comportamiento correcto del AS400, no un descuadre — y de hecho las 98
 *    cuadran en pagos. Marcarlas sería hacer el informe falso en 98 filas.
 *
 * 2. Las NOTAS DE CRÉDITO DE CLASE 3 (`NTPDNC = '3'`, «ABON») no mueven
 *    mercancía: mueven DINERO. Se midió, y en las 31 del período el
 *    comportamiento es idéntico y sin una excepción:
 *
 *        abono == monto_bruto                      31 de 31
 *        IVA, descuento e IGTF en cero             31 de 31
 *        cuadran con sus formas de pago            31 de 31
 *        su detalle cuadra con el encabezado        0 de 31
 *
 *    Sus líneas de detalle son la mercancía de la factura original, que no
 *    tiene por qué sumar el importe abonado. Así que para esta clase el
 *    contraste del detalle NO APLICA, y decir que «descuadra» sería un error
 *    del informe y no del dato. En todo lo demás el detalle cuadra 3.724 de
 *    3.724.
 *
 *    Y su `abono` no es un importe que la fórmula se deje fuera: es el mismo
 *    `monto_bruto` repetido. Sumarlo contaría el movimiento dos veces.
 */

require_once __DIR__ . '/../modelos/auditoria.modelo.php';
require_once __DIR__ . '/Periodo.php';

final class Auditoria
{
    /** Igualdad al céntimo. Por debajo de esto, cuadra. */
    public const TOLERANCIA_EXACTA = 0.01;

    /**
     * Hasta aquí, redondeo del IGTF; por encima, dinero.
     *
     * Justificado arriba: cae en un hueco entre 4,38 y 2.000,00 Bs.
     */
    public const TOLERANCIA_REDONDEO = 5.00;

    public const CUADRA    = 'CUADRA';
    public const REDONDEO  = 'REDONDEO';
    public const REVISAR   = 'REVISAR';
    public const NO_APLICA = 'NO APLICA';

    /**
     * La clase de nota de crédito que mueve DINERO y no mercancía.
     *
     * Está aquí y no escrita suelta en tres sitios porque de ella dependen dos
     * decisiones del informe —el contraste del detalle y el aviso del abono— y
     * tienen que cambiar juntas.
     */
    public const NC_ABONO = '3';

    /**
     * La clase que se ajusta CONTRA LA FACTURA, sin detalle y sin pago.
     *
     * ===================================================================
     *  LA ENCONTRÓ EL VERIFICADOR, EL 19/11/2026
     * -------------------------------------------------------------------
     *  La comprobación «el detalle de líneas cuadra con el encabezado» se
     *  puso roja por un documento: `CCCT · NC 26829`, 42,40 Bs, siete
     *  piezas en el encabezado, CERO líneas de detalle y CERO formas de
     *  pago. Con las reglas de entonces salía como REVISAR: «falta por
     *  asentar 42,40 Bs».
     *
     *  No faltaba nada. Las tres clases de nota de crédito del AS400 son
     *  estructuralmente distintas, y medidas sobre los tres años cargados
     *  no admiten ninguna excepción:
     *
     *      clase  docs    apunta a factura   detalle   pagos
     *      1     4.670       4.670 de 4.670     sí       sí
     *      2        55          55 de 55      NUNCA    NUNCA
     *      3     1.403           0 de 1.403  no cuadra   sí
     *
     *  La clase 2 apunta SIEMPRE a la factura que corrige —`NFCAPL`— y
     *  nunca lleva IVA, descuento, IGTF ni abono. Es un ajuste que se
     *  descuenta de esa factura: no mueve mercancía propia ni dinero
     *  propio, así que **no hay nada que contrastar**, ni en el detalle ni
     *  en los pagos.
     *
     *  Por eso no se marca CUADRA (no cuadra nada, no hay con qué) ni
     *  REVISAR (no falta nada): se marca NO APLICA, que es lo que es. Las
     *  otras dos opciones mienten en direcciones distintas.
     *
     *  Y NO HACÍA FALTA DEDUCIRLO: YA ESTABA ESCRITO. `NTPDNC` vale
     *  **1 = DEV (devolución), 2 = AJUS (ajuste), 3 = ABON (abono)**, y
     *  llevaba meses en la documentación del proyecto hermano. Deducirlo de
     *  los datos salió bien, pero por no usar el nombre del AS400 la clase 3
     *  quedó llamada «devolución de dinero» cuando es un ABONO —dinero que
     *  ENTRA— y eso sí hizo daño en otro informe.
     * ===================================================================
     */
    public const NC_AJUSTE = '2';

    /** El tipo que `IDTA116` usa para marcar una forma como financiamiento. */
    public const TIPO_FINANCIAMIENTO = 'FI';

    /**
     * Formas de pago que se usan y que `IDTA116` NO tiene dadas de alta.
     *
     * `OT` apareció en la primera corrida contra producción del proyecto
     * hermano: 18 líneas por 2.195.060,76 Bs en octubre y noviembre de 2026.
     * Carlos la reconoció —son «otros pagos»— y confirmó que **no tiene nada
     * que ver con financiamiento**.
     *
     * Eso último es lo único que no se puede deducir del archivo: sin catálogo
     * no hay `FFORPT`, así que sin esta línea el programa no sabría si `OT` es
     * financiamiento o no. Si algún día se usara para financiar, esta
     * declaración sería mentira — por eso está escrita donde se encuentra y no
     * repartida por el código.
     *
     * Carlos Flores confirmó el 20/11/2026 que la dará de alta en `IDTA116`
     * cuando pueda. El día que lo haga, esta entrada deja de hacer falta: el
     * catálogo contestará por sí solo y el aviso correspondiente dejará de
     * salir, sin tocar nada. Hasta entonces el informe la nombra por lo que es
     * en lugar de dejarla sin clasificar.
     *
     * @var array<string,string>
     */
    public const FUERA_DEL_CATALOGO = [
        'OT' => 'OTROS PAGOS (sin dar de alta en IDTA116)',
    ];

    /**
     * Corre la auditoría entera contra el AS400 y devuelve el informe.
     *
     * Devuelve UNA estructura con todo lo que el informe necesita —los
     * documentos juzgados, el resumen, las formas de pago y los avisos— porque
     * la pantalla y el Excel tienen que mostrar exactamente lo mismo. Si cada
     * uno lo pidiera por su cuenta, con dos consultas separadas al AS400 en
     * momentos distintos, podrían no coincidir: entre una y otra alguien
     * factura.
     *
     * @return array<string,mixed>
     */
    public static function correr(Periodo $periodo): array
    {
        $inicio = microtime(true);

        /*
         * CADA LECTURA SE CRONOMETRA POR SEPARADO, Y NO ES CURIOSIDAD
         * -----------------------------------------------------------------
         * Medido contra producción el 19/11/2026, para un día:
         *
         *      IDP210    0,06 s     3.149.280 filas, con índice por fecha
         *      IDP116N   0,18 s       444.044 filas, pequeño
         *      RTP325   17-22 s     6.595.139 filas, SIN NINGÚN ÍNDICE
         *
         * `RTP325` se lleva el 98 % de la espera, y se la lleva porque el
         * AS400 no tiene ningún camino de acceso por fecha sobre ese archivo:
         * lo barre entero, las seis millones y medio de filas, cada vez. Eso
         * tiene arreglo y no es nuestro (ver `docs/INDICE-RTP325.md`).
         *
         * Mientras no lo tenga, este desglose es lo que permite saber si la
         * espera cambió y por cuál de los tres. Sin él, «hoy va lento» no es
         * un dato: es una sensación, y con una sensación no se abre un ticket
         * a sistemas.
         */
        $tiempos = [];

        $t = microtime(true);
        $tiendas = ModeloAuditoria::tiendas();
        $tiempos['ETP045 · tiendas'] = round(microtime(true) - $t, 2);

        $t = microtime(true);
        $catalogo = ModeloAuditoria::catalogoFormas();
        $tiempos['IDTA116 · formas de pago'] = round(microtime(true) - $t, 2);

        $t = microtime(true);
        $enc = ModeloAuditoria::encabezados($periodo);
        $tiempos['IDP210 · encabezados'] = round(microtime(true) - $t, 2);

        $t = microtime(true);
        $detalle = ModeloAuditoria::detalle($periodo);
        $tiempos['RTP325 · detalle'] = round(microtime(true) - $t, 2);

        $t = microtime(true);
        $pagos = ModeloAuditoria::pagos($periodo);
        $tiempos['IDP116N · formas de pago'] = round(microtime(true) - $t, 2);

        $tLectura = array_sum($tiempos);

        $informe = self::informar($periodo, $tiendas, $catalogo, $enc, $detalle, $pagos);

        $informe['segundos'] = round(microtime(true) - $inicio, 2);
        $informe['tiempos']  = $tiempos;
        $informe['tiempos']['(el cruce y el juicio, aquí)'] =
            round($informe['segundos'] - $tLectura, 2);

        return $informe;
    }

    /**
     * El informe a partir de los datos ya leídos, sin tocar el AS400.
     *
     * ===================================================================
     *  ESTO ESTÁ SEPARADO DE `correr()` A PROPÓSITO
     * -------------------------------------------------------------------
     *  Al AS400 de esta casa no se llega desde cualquier sitio: con la VPN
     *  activa la red no lo alcanza, y eso significa que durante buena parte
     *  del desarrollo NO se puede consultar. Si el juicio estuviera metido
     *  dentro de la función que consulta, no habría forma de comprobar
     *  ninguna de las reglas —el total medido, el corte en 5 Bs, las tres
     *  clases de nota de crédito, los avisos— sin estar en la red buena.
     *
     *  Partido así, `cli/probar-excel.php` le da datos inventados que cubren
     *  todos los casos y comprueba el cálculo entero y las cinco pestañas
     *  del Excel sin conexión. Lo único que queda por probar contra el
     *  servidor es lo que sólo el servidor puede contestar: que los campos
     *  se llamen como creemos y que las claves crucen.
     * ===================================================================
     *
     * @param  array<int,array<string,mixed>>    $tiendas
     * @param  array<string,array<string,mixed>> $catalogo
     * @param  array{documentos:list<array<string,mixed>>,sin_fecha:int} $enc
     * @param  array<string,array<string,mixed>> $detalle
     * @param  array<string,array<string,mixed>> $pagos
     * @return array<string,mixed>
     */
    public static function informar(
        Periodo $periodo, array $tiendas, array $catalogo, array $enc, array $detalle, array $pagos
    ): array {
        $documentos = [];

        foreach ($enc['documentos'] as $d) {
            $documentos[] = self::juzgar($d, $detalle, $pagos, $tiendas, $catalogo);
        }

        /*
         * Ordenado como se lee: por fecha, tienda, tipo y número. El AS400 ya
         * lo devuelve casi así, pero ordena por CÓDIGO de tienda y el informe
         * la nombra, así que dentro del día el orden cambia al traducir.
         */
        usort($documentos, static function (array $a, array $b): int {
            return [$a['fecha'], $a['tienda'], $a['tipo_doc'], $a['numero_doc']]
               <=> [$b['fecha'], $b['tienda'], $b['tipo_doc'], $b['numero_doc']];
        });

        $resumen = self::resumen($documentos);
        $formas  = self::porForma($documentos, $catalogo);
        $avisos  = self::avisos($documentos, $periodo, $enc['sin_fecha'], $detalle, $pagos, $formas);

        /*
         * Fuera las líneas de pago en crudo, ya sumadas.
         *
         * Son del orden de 5.200 por mes y lo que aportan —el desglose legible
         * y el reparto por forma— ya está calculado. Dejarlas dentro
         * multiplicaría por tres el JSON que viaja al navegador para que nadie
         * lo mire.
         */
        foreach ($documentos as &$doc) {
            unset($doc['lineas_pago']);
        }

        unset($doc);

        return [
            'generado_en' => date('Y-m-d H:i:s'),
            'desde'       => $periodo->desde,
            'hasta'       => $periodo->hasta,
            'rotulo'      => $periodo->rotulo(),
            'origen'      => 'AS400 en vivo',
            'tolerancias' => [
                'exacta'   => self::TOLERANCIA_EXACTA,
                'redondeo' => self::TOLERANCIA_REDONDEO,
            ],
            // Los pone `correr()`, que es quien cronometra las lecturas. Una
            // corrida con datos fabricados (`cli/probar-excel.php`) no las
            // tiene, y por eso el informe no da por supuesto que estén.
            'segundos'    => 0.0,
            'tiempos'     => [],
            'resumen'     => $resumen,
            'formas'      => $formas,
            'avisos'      => $avisos,
            'documentos'  => $documentos,
        ];
    }

    /**
     * Pone a un documento su detalle, sus pagos, sus diferencias y su
     * veredicto.
     *
     * @param  array<string,mixed>                     $d
     * @param  array<string,array<string,mixed>>       $detalle
     * @param  array<string,array<string,mixed>>       $pagos
     * @param  array<int,array<string,mixed>>          $tiendas
     * @param  array<string,array<string,mixed>>       $catalogo
     * @return array<string,mixed>
     */
    private static function juzgar(
        array $d, array $detalle, array $pagos, array $tiendas, array $catalogo
    ): array {
        $clave = (string) $d['clave'];
        $codigo = (int) $d['codigo_as400'];

        $d['tienda'] = $tiendas[$codigo]['nombre'] ?? ('(tienda ' . $codigo . ')');

        /* --- El detalle --------------------------------------------------- */

        $det = $detalle[$clave] ?? ['lineas' => 0, 'bruto' => 0.0, 'descuento' => 0.0, 'piezas' => 0];

        $d['lineas']     = (int) $det['lineas'];
        $d['det_piezas'] = (int) $det['piezas'];

        /* --- Los pagos ---------------------------------------------------- */

        $pg = $pagos[$clave] ?? ['formas' => 0, 'pagado' => 0.0, 'caja' => '', 'lineas' => []];

        $d['formas']   = (int) $pg['formas'];
        $d['caja']     = (string) $pg['caja'];
        $d['desglose'] = self::desglose($pg['lineas'], $catalogo);

        /*
         * Las líneas en crudo viajan con el documento SÓLO hasta que
         * `porForma()` las suma, y `correr()` las quita antes de devolver nada.
         * Es la alternativa a preguntarle otra vez al AS400 por lo mismo: si la
         * pestaña de formas de pago saliera de una segunda lectura, podría no
         * sumar lo mismo que la tabla de documentos y el informe se
         * contradiría a sí mismo entre dos pestañas.
         */
        $d['lineas_pago'] = $pg['lineas'];

        /* --- El total medido. Ver la cabecera de la clase. ---------------- */

        $bruto     = (float) $d['monto_bruto'];
        $descuento = (float) $d['descuento'];
        $iva       = (float) $d['iva'];
        $igtf      = (float) $d['igtf'];

        $total  = round($bruto - $descuento + $iva + $igtf, 2);
        $pagado = round((float) $pg['pagado'], 2);

        /* --- El detalle contra el encabezado, en neto -------------------- */

        $detNeto = round((float) $det['bruto'] - (float) $det['descuento'], 2);
        $encNeto = round($bruto - $descuento, 2);

        $esAbono  = (string) $d['tipo_nc'] === self::NC_ABONO;
        $esAjuste = (string) $d['tipo_nc'] === self::NC_AJUSTE;

        /*
         * En un abono y en un ajuste el detalle es la mercancía de la factura
         * original y no tiene por qué sumar el importe del documento. El
         * contraste no aplica, y `null` lo dice; un cero diría «cuadra», que es
         * mentira, y la diferencia diría «descuadra», que es peor.
         */
        $difDetalle = ($esAbono || $esAjuste) ? null : round($encNeto - $detNeto, 2);

        $difPago = round($total - $pagado, 2);
        $anulada = (string) $d['estatus'] === '9';

        $d['total_factura'] = $total;
        $d['detalle_neto']  = $detNeto;
        $d['pagado']        = $pagado;
        $d['dif_pago']      = $difPago;
        $d['dif_detalle']   = $difDetalle;
        $d['anulada']       = $anulada;
        $d['es_abono']      = $esAbono;
        $d['es_ajuste']     = $esAjuste;
        $d['pct_pagado']    = $total != 0.0 ? round($pagado / $total * 100, 1) : null;

        $d['clase_doc'] = match (true) {
            $esAbono  => 'Abono',
            $esAjuste => 'Ajuste',
            (string) $d['tipo_nc'] === '1' => 'Nota de crédito',
            default   => 'Factura',
        };

        /*
         * Un ajuste no mueve dinero propio, así que la diferencia entre su
         * importe y «lo pagado» no es un descuadre: es que no hay nada que
         * contrastar. Ver NC_AJUSTE.
         */
        $d['clase'] = $esAjuste ? self::NO_APLICA : self::clase($difPago);

        $d['diagnostico'] = self::diagnostico($d, $difPago, $difDetalle, $anulada);

        return $d;
    }

    /** CUADRA, REDONDEO o REVISAR, según el tamaño de la diferencia. */
    public static function clase(float $difPago): string
    {
        $d = abs($difPago);

        if ($d <= self::TOLERANCIA_EXACTA) {
            return self::CUADRA;
        }

        return $d <= self::TOLERANCIA_REDONDEO ? self::REDONDEO : self::REVISAR;
    }

    /**
     * El desglose legible de las formas de pago de un documento.
     *
     * `PAGO MOVIL 46.916,44  +  PUNTO DE VENTA 12.000,00`, por monto
     * descendente. Con la DESCRIPCIÓN del catálogo y no con el código: `CR` no
     * le dice nada a nadie, `CASHEA` sí — y es justo lo que hace falta leer
     * para entender por qué falta el 20 % de una factura.
     *
     * @param  list<array{forma:string,monto:float}> $lineas
     * @param  array<string,array<string,mixed>>     $catalogo
     */
    private static function desglose(array $lineas, array $catalogo): string
    {
        if ($lineas === []) {
            return '';
        }

        usort($lineas, static fn($a, $b) => $b['monto'] <=> $a['monto']);

        $partes = [];

        foreach ($lineas as $l) {
            $forma = $l['forma'];
            $nombre = $catalogo[$forma]['descripcion'] ?? '';

            if ($nombre === '') {
                $nombre = isset(self::FUERA_DEL_CATALOGO[$forma])
                    ? $forma . ' (otros pagos)'
                    : $forma;
            }

            $partes[] = $nombre . ' ' . number_format($l['monto'], 2, ',', '.');
        }

        return implode('  +  ', $partes);
    }

    /**
     * Qué le pasa a este documento, en una frase que se pueda entregar.
     *
     * El diagnóstico describe el PATRÓN que se observa, no la causa que se
     * imagina: «se cobró el 80 % y la forma registrada es CASHEA» es un hecho;
     * «el cajero no asentó la inicial» sería una acusación sin pruebas. Quien
     * revise la factura en la tienda tiene el papel delante y puede decidir;
     * este informe le dice dónde mirar.
     *
     * @param array<string,mixed> $f
     */
    private static function diagnostico(
        array $f, float $difPago, ?float $difDetalle, bool $anulada
    ): string {
        $partes = [];

        /*
         * El ajuste se explica solo y se explica primero: todo lo demás que se
         * dijera de él —«no tiene líneas de pago», «no tiene detalle»— es
         * cierto y da a entender que falta algo.
         */
        if ((bool) ($f['es_ajuste'] ?? false)) {
            $aplica = (int) ($f['factura_aplicada'] ?? 0);

            return 'Nota de crédito de clase 2 («AJUS»): un ajuste que se descuenta de la '
                . ($aplica > 0 ? 'factura ' . $aplica : 'factura que corrige')
                . ', sin mercancía propia y sin movimiento de dinero. No hay nada que '
                . 'contrastar: las 55 de este tipo que hay desde enero de 2024 no llevan '
                . 'detalle ni forma de pago, ni una. '
                . ($anulada ? 'Además está ANULADA. ' : '')
                . 'Es la clase «AJUS» de `NTPDNC`.';
        }

        if ((int) $f['formas'] === 0) {
            $partes[] = 'No tiene ni una línea de pago registrada.';
        } elseif (abs($difPago) > self::TOLERANCIA_REDONDEO) {
            if ($difPago > 0) {
                $partes[] = sprintf(
                    'Falta por asentar %s Bs: se registró el %s %% del total con %d forma(s) de pago.',
                    number_format($difPago, 2, ',', '.'),
                    number_format((float) $f['pct_pagado'], 1, ',', '.'),
                    (int) $f['formas']
                );

                $desglose = strtoupper((string) ($f['desglose'] ?? ''));

                if (str_contains($desglose, 'CASHEA') || str_contains($desglose, 'VIBES')) {
                    $partes[] = 'Lo registrado es financiamiento, así que lo que falta '
                        . 'sería la inicial que paga el cliente.';
                } else {
                    $partes[] = 'Lo registrado no es financiamiento, así que lo que falta '
                        . 'sería la parte financiada o un segundo cobro.';
                }
            } else {
                $partes[] = sprintf(
                    'Se registró %s Bs MÁS que el total de la factura.',
                    number_format(abs($difPago), 2, ',', '.')
                );
            }
        } elseif (abs($difPago) > self::TOLERANCIA_EXACTA) {
            $partes[] = ((float) $f['igtf'] != 0.0)
                ? 'Diferencia de redondeo del IGTF (3 % calculado sobre el documento '
                  . 'y guardado por línea de pago). No es dinero que falte.'
                : 'Diferencia de céntimos por redondeo. No es dinero que falte.';
        }

        if ($difDetalle !== null && abs($difDetalle) > self::TOLERANCIA_EXACTA) {
            $partes[] = sprintf(
                'Además el detalle de líneas no cuadra con el encabezado: %s Bs.',
                number_format($difDetalle, 2, ',', '.')
            );
        }

        if ((int) $f['lineas'] === 0) {
            $partes[] = 'No tiene líneas de detalle.';
        }

        if ($anulada) {
            $partes[] = 'Documento ANULADO: el encabezado queda en cero piezas '
                . 'y cero venta, y conserva sus líneas. Es lo correcto.';
        }

        if ((bool) $f['es_abono']) {
            $partes[] = 'Nota de crédito de clase 3 («ABON»): un ABONO, dinero que el '
                . 'cliente ENTREGA a cuenta de un apartado. No es una venta —se cuenta '
                . 'cuando el abono se aplica a una factura— pero el dinero sí entró, y '
                . 'por eso tiene forma de pago. El contraste del detalle no aplica: sus '
                . 'líneas son la mercancía de la factura original.';
        }

        if ((bool) ($f['manual'] ?? false)) {
            $partes[] = 'Factura MANUAL (`FLA011 = M`): la emitió la tienda a mano '
                . 'porque el punto de venta no podía facturar.';
        }

        return $partes === [] ? 'Cuadra en los tres niveles.' : implode(' ', $partes);
    }

    /**
     * Los totales del informe, ya contados.
     *
     * @param  list<array<string,mixed>> $docs
     * @return array<string,mixed>
     */
    public static function resumen(array $docs): array
    {
        $r = [
            'documentos' => count($docs),
            'cuadran' => 0, 'redondeo' => 0, 'revisar' => 0, 'no_aplica' => 0,
            'anuladas' => 0, 'sin_pagos' => 0, 'sin_lineas' => 0, 'manuales' => 0,
            'detalle_cuadra' => 0, 'detalle_descuadrado' => 0, 'detalle_no_aplica' => 0,
            'abonos' => 0, 'ajustes' => 0,
            'total_facturado' => 0.0, 'total_pagado' => 0.0,
            'falta_bs' => 0.0, 'sobra_bs' => 0.0, 'redondeo_bs' => 0.0,
            'tipos' => [], 'tiendas' => [], 'dias' => 0,
        ];

        $dias = [];

        foreach ($docs as $d) {
            $clase = (string) $d['clase'];
            $dif   = (float) $d['dif_pago'];

            $dias[(string) $d['fecha']] = true;

            $r['total_facturado'] += (float) $d['total_factura'];
            $r['total_pagado']    += (float) $d['pagado'];

            $tipo = (string) $d['tipo_doc'];
            $r['tipos'][$tipo] = ($r['tipos'][$tipo] ?? 0) + 1;

            if ($clase === self::CUADRA)    { $r['cuadran']++; }
            if ($clase === self::NO_APLICA) { $r['no_aplica']++; }
            if ($clase === self::REDONDEO)  { $r['redondeo']++; $r['redondeo_bs'] += abs($dif); }

            if ($clase === self::REVISAR) {
                $r['revisar']++;

                if ($dif > 0) { $r['falta_bs'] += $dif; }
                else          { $r['sobra_bs'] += abs($dif); }

                $t = (string) $d['tienda'];
                $r['tiendas'][$t] = ($r['tiendas'][$t] ?? 0) + $dif;
            }

            if ($d['anulada'])             { $r['anuladas']++; }
            if ((int) $d['formas'] === 0)  { $r['sin_pagos']++; }
            if ((int) $d['lineas'] === 0)  { $r['sin_lineas']++; }
            if ($d['manual'])              { $r['manuales']++; }
            if ($d['es_abono'])            { $r['abonos']++; }
            if ($d['es_ajuste'])           { $r['ajustes']++; }

            if ($d['dif_detalle'] === null) {
                $r['detalle_no_aplica']++;
            } elseif (abs((float) $d['dif_detalle']) > self::TOLERANCIA_EXACTA) {
                $r['detalle_descuadrado']++;
            } else {
                $r['detalle_cuadra']++;
            }
        }

        $r['dias'] = count($dias);

        arsort($r['tiendas']);
        ksort($r['tipos']);

        return $r;
    }

    /**
     * Las formas de pago del período, con lo que movió cada una.
     *
     * Se calcula sobre los documentos ya juzgados y no con otra consulta al
     * AS400, por la misma razón que todo lo demás sale de una sola corrida: si
     * fuesen dos lecturas distintas podrían no sumar lo mismo, y entonces el
     * informe se contradice a sí mismo en dos pestañas.
     *
     * @param  list<array<string,mixed>>         $docs
     * @param  array<string,array<string,mixed>> $catalogo
     * @return list<array<string,mixed>>
     */
    public static function porForma(array $docs, array $catalogo): array
    {
        /*
         * El desglose del documento ya está escrito como texto legible, así que
         * para sumar por forma hacen falta las líneas en crudo. Las deja puestas
         * `juzgar()` en `lineas_pago` justamente para esto, y `correr()` las
         * quita en cuanto este método termina.
         */
        $porForma = [];

        foreach ($docs as $d) {
            foreach (($d['lineas_pago'] ?? []) as $l) {
                $forma = (string) $l['forma'];

                if (!isset($porForma[$forma])) {
                    $porForma[$forma] = [
                        'forma_pago' => $forma,
                        'lineas'     => 0,
                        'docs'       => [],
                        'bs'         => 0.0,
                    ];
                }

                $porForma[$forma]['lineas']++;
                $porForma[$forma]['bs'] += (float) $l['monto'];
                $porForma[$forma]['docs'][(string) $d['clave']] = true;
            }
        }

        $salida = [];

        foreach ($porForma as $forma => $f) {
            $ficha = $catalogo[$forma] ?? null;

            $salida[] = [
                'forma_pago'  => $forma,
                'descripcion' => $ficha['descripcion'] ?? (
                    self::FUERA_DEL_CATALOGO[$forma] ?? '(no está en IDTA116)'
                ),
                'tipo' => $ficha === null
                    ? '--'
                    : ($ficha['tipo_nombre'] !== '' ? $ficha['tipo_nombre'] : ($ficha['tipo'] ?: '--')),
                'es_financiamiento' => ($ficha['tipo'] ?? '') === self::TIPO_FINANCIAMIENTO,
                'en_catalogo'       => $ficha !== null,
                // Cuántos tipos distintos tiene esta forma en `IDTA116`. Más de
                // uno y «¿es financiamiento?» deja de tener respuesta; el aviso
                // correspondiente lo mira.
                'tipos'             => (int) ($ficha['tipos'] ?? 1),
                'lineas'            => $f['lineas'],
                'docs'              => count($f['docs']),
                'bs'                => round($f['bs'], 2),
            ];
        }

        usort($salida, static fn($a, $b) => $b['bs'] <=> $a['bs']);

        return $salida;
    }

    /**
     * Lo que el informe tiene que advertir de sí mismo.
     *
     * Un informe que se entrega no puede callarse lo que no sabe. Aquí van los
     * supuestos que podrían haber dejado de ser verdad desde que se midieron, y
     * lo que se ha encontrado y no encaja en ninguna columna.
     *
     * @param  list<array<string,mixed>>         $docs
     * @param  array<string,mixed>               $detalle
     * @param  array<string,mixed>               $pagos
     * @param  list<array<string,mixed>>         $formas
     * @return list<array{nivel:string,texto:string}>
     */
    public static function avisos(
        array $docs, Periodo $periodo, int $sinFecha, array $detalle, array $pagos, array $formas
    ): array {
        $avisos = [];

        /* --- Los dos importes que la fórmula deja fuera ------------------- */

        $seniat = 0;
        $abonosRaros = 0;

        foreach ($docs as $d) {
            if ((float) $d['dscto_seniat'] != 0.0) {
                $seniat++;
            }

            if ((float) $d['abono'] == 0.0) {
                continue;
            }

            /*
             * `abono` NO vale cero siempre: en las notas de crédito de clase 3
             * repite el `monto_bruto` —medido, 31 de 31— y sumarlo contaría el
             * movimiento dos veces. Eso está entendido y no es un aviso. Lo que
             * sí lo es: un abono en un documento que no sea de esa clase, o uno
             * que dentro de la clase no coincida con el bruto, porque entonces
             * el supuesto se rompió.
             */
            $esperado = (bool) $d['es_abono']
                && abs((float) $d['abono'] - (float) $d['monto_bruto']) <= self::TOLERANCIA_EXACTA;

            if (!$esperado) {
                $abonosRaros++;
            }
        }

        if ($seniat > 0) {
            $avisos[] = ['nivel' => 'alto', 'texto' => sprintf(
                'ATENCIÓN: %d documento(s) traen DESCUENTO SENIAT distinto de cero. La '
                . 'fórmula del total se midió sobre un período donde ese importe era '
                . 'siempre cero, así que hay que revisarla antes de dar por buenas estas '
                . 'cifras.', $seniat)];
        }

        if ($abonosRaros > 0) {
            $avisos[] = ['nivel' => 'alto', 'texto' => sprintf(
                'ATENCIÓN: %d documento(s) traen un ABONO que no se explica por ser una '
                . 'nota de crédito de clase 3 que repite el bruto. Ese es el único caso '
                . 'medido, así que la fórmula del total hay que revisarla antes de dar por '
                . 'buenas estas cifras.', $abonosRaros)];
        }

        /* --- Fechas imposibles en el propio archivo ----------------------- */

        if ($sinFecha > 0) {
            $avisos[] = ['nivel' => 'alto', 'texto' => sprintf(
                'ATENCIÓN: %d encabezado(s) de `IDP210` traen una fecha que no existe en '
                . 'el calendario (los cuatro campos siglo/año/mes/día no componen un día '
                . 'válido). NO están en este informe, porque no se les puede asignar un '
                . 'día sin inventárselo.', $sinFecha)];
        }

        /* --- Huérfanos: pagos y líneas sin encabezado --------------------- */

        $conEncabezado = [];

        foreach ($docs as $d) {
            $conEncabezado[(string) $d['clave']] = true;
        }

        $pagosHuerfanos = 0;
        $bsHuerfanos    = 0.0;

        foreach ($pagos as $clave => $p) {
            if (!isset($conEncabezado[$clave])) {
                $pagosHuerfanos++;
                $bsHuerfanos += (float) $p['pagado'];
            }
        }

        if ($pagosHuerfanos > 0) {
            $avisos[] = ['nivel' => 'alto', 'texto' => sprintf(
                'ATENCIÓN: hay %d documento(s) con formas de pago en `IDP116N` y SIN '
                . 'encabezado en `IDP210`, por %s Bs. Son cobros registrados contra un '
                . 'documento que no existe en el archivo de facturas; no salen en la tabla '
                . 'porque la tabla es una fila por encabezado.',
                $pagosHuerfanos, number_format($bsHuerfanos, 2, ',', '.'))];
        }

        $lineasHuerfanas = 0;

        foreach (array_keys($detalle) as $clave) {
            if (!isset($conEncabezado[$clave])) {
                $lineasHuerfanas++;
            }
        }

        if ($lineasHuerfanas > 0) {
            $avisos[] = ['nivel' => 'medio', 'texto' => sprintf(
                'Hay %d documento(s) con líneas en `RTP325` y sin encabezado en `IDP210`. '
                . 'En el proyecto hermano se midió lo mismo y resultó ser un hueco de '
                . 'numeración del detalle, no dinero: aun así queda dicho.',
                $lineasHuerfanas)];
        }

        /* --- La clase 2, que se da por buena sin que nadie lo confirme ---- */

        $ajustes = 0;

        foreach ($docs as $d) {
            if ($d['es_ajuste']) { $ajustes++; }
        }

        if ($ajustes > 0) {
            $avisos[] = ['nivel' => 'bajo', 'texto' => sprintf(
                'Hay %d nota(s) de crédito de CLASE 2 («AJUS») en el período. Se descuentan '
                . 'de la factura que corrigen y no llevan mercancía ni movimiento de dinero '
                . 'propios, así que no se contrastan: en las 55 que hay desde enero de 2024 '
                . 'no hay ni una con detalle o forma de pago. Marcarlas de otra forma sería '
                . 'decir que falta dinero donde no falta.', $ajustes)];
        }

        /* --- Formas de pago que el catálogo no tiene ---------------------- */

        foreach ($formas as $f) {
            if ($f['en_catalogo']) {
                continue;
            }

            /*
             * UNA FORMA CONOCIDA Y UNA DESCONOCIDA NO SON EL MISMO AVISO
             * ----------------------------------------------------------
             * De `OT` ya sabemos lo que hace falta saber: son «otros pagos» y
             * NO son financiamiento. Lo confirmó Carlos Flores, y queda
             * pendiente darla de alta en `IDTA116` cuando se pueda. Eso no es
             * un hallazgo, es una tarea abierta, y repetirlo cada mes con la
             * misma urgencia que un dato desconocido es la forma más segura de
             * que un día nadie lea los avisos.
             *
             * Una forma que NO esté en esta lista sí es un hallazgo: de ella
             * no se sabe si es financiamiento, y eso cambia cómo se lee su
             * columna. Esa va en «medio» y dice qué hay que preguntar.
             */
            $conocida = isset(self::FUERA_DEL_CATALOGO[$f['forma_pago']]);

            $avisos[] = [
                'nivel' => $conocida ? 'bajo' : 'medio',
                'texto' => $conocida
                    ? sprintf(
                        'La forma de pago «%s» —%d línea(s), %s Bs— son OTROS PAGOS y no '
                        . 'tienen nada que ver con financiamiento; está confirmado. Queda '
                        . 'pendiente darla de alta en `IDTA116`: mientras tanto su tipo no '
                        . 'sale del catálogo sino de esta declaración, que está escrita en '
                        . '`Auditoria::FUERA_DEL_CATALOGO`.',
                        $f['forma_pago'], $f['lineas'],
                        number_format((float) $f['bs'], 2, ',', '.'))
                    : sprintf(
                        'La forma de pago «%s» se usa —%d línea(s), %s Bs— y NO está dada de '
                        . 'alta en `IDTA116`. Sin catálogo no se puede saber desde el archivo '
                        . 'si es financiamiento, y de eso depende cómo se lee su columna. Hay '
                        . 'que preguntarlo antes de interpretarla.',
                        $f['forma_pago'], $f['lineas'],
                        number_format((float) $f['bs'], 2, ',', '.')),
            ];
        }

        /* --- Formas con más de un tipo en el catálogo --------------------- */

        foreach ($formas as $f) {
            if (!$f['en_catalogo']) {
                continue;
            }

            // El catálogo cuenta los tipos distintos de cada forma; si son más
            // de uno, «ser financiamiento» deja de ser una propiedad de la
            // forma de pago y no hay forma correcta de clasificarla.
            if ((int) ($f['tipos'] ?? 1) > 1) {
                $avisos[] = ['nivel' => 'alto', 'texto' => sprintf(
                    'La forma de pago «%s» tiene más de un tipo distinto en `IDTA116`. '
                    . 'Mientras eso sea así, «¿es financiamiento?» no tiene una respuesta '
                    . 'y la columna de tipo de esta forma no es de fiar.', $f['forma_pago'])];
            }
        }

        /* --- La cobertura real del período -------------------------------- */

        $dias = [];

        foreach ($docs as $d) {
            $dias[(string) $d['fecha']] = true;
        }

        if ($dias === []) {
            return $avisos;
        }

        $min = min(array_keys($dias));
        $max = max(array_keys($dias));
        $hoy = date('Y-m-d');

        /*
         * EL FUTURO NO ES UN HUECO, Y DECIRLO IGUAL SERÍA UN ERROR
         * --------------------------------------------------------
         * Pedir «noviembre» el día 19 no deja once días sin auditar: deja once
         * días sin ocurrir. Un aviso que los trate igual —«estos días no están»—
         * hace que quien lea el informe se pregunte qué se le está ocultando.
         */
        if ($periodo->hasta > $hoy) {
            $avisos[] = ['nivel' => 'bajo', 'texto' => sprintf(
                'El período pedido llega al %s, que todavía no ha ocurrido. La auditoría '
                . 'cubre lo que hay: del %s al %s.',
                Periodo::corta($periodo->hasta), Periodo::corta($min), Periodo::corta($max))];
        } elseif ($max < $periodo->hasta) {
            $avisos[] = ['nivel' => 'medio', 'texto' => sprintf(
                'El período pedido llega al %s y el último día con documentos es el %s. '
                . 'Los días posteriores no tienen ni una factura en `IDP210`: o la tienda '
                . 'no abrió, o algo no se facturó.',
                Periodo::corta($periodo->hasta), Periodo::corta($max))];
        }

        if ($min > $periodo->desde) {
            $avisos[] = ['nivel' => 'medio', 'texto' => sprintf(
                'El período pedido empieza el %s y el primer día con documentos es el %s.',
                Periodo::corta($periodo->desde), Periodo::corta($min))];
        }

        $esperados = (int) ((strtotime($max) - strtotime($min)) / 86400) + 1;

        if (count($dias) < $esperados) {
            $avisos[] = ['nivel' => 'bajo', 'texto' => sprintf(
                'Entre el %s y el %s hay %d días con documentos de los %d del tramo. Los '
                . 'días sin documentos pueden ser cierres legítimos (domingos, feriados).',
                Periodo::corta($min), Periodo::corta($max), count($dias), $esperados)];
        }

        return $avisos;
    }
}
