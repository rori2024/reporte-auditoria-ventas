<?php

declare(strict_types=1);

/**
 * El Excel de la auditoría: cinco pestañas, a partir del informe ya calculado.
 *
 * ===========================================================================
 *  ESTA CLASE NO DECIDE NADA
 * ---------------------------------------------------------------------------
 *  Recibe lo que devolvió `Auditoria::correr()` y lo pinta. No suma, no
 *  clasifica y no vuelve a preguntar al AS400. Es la misma división que había
 *  entre el PHP y el PowerShell de la primera versión, y por el mismo motivo:
 *  si el formato y el cálculo viven juntos, no se puede comprobar ninguno de
 *  los dos por separado.
 *
 *  La consecuencia práctica importa: lo que se descarga es EXACTAMENTE lo que
 *  se vio en la pantalla, porque las dos cosas salen de la misma corrida.
 * ===========================================================================
 *
 * EL DISEÑO, Y POR QUÉ LA CABECERA ES BLANCA Y NO MARINO
 * -------------------------------------------------------
 * La primera versión llevaba una banda marino de cuatro filas con el título en
 * blanco encima. Se cambió por dos razones concretas, no por gusto:
 *
 * 1. **El logotipo de la casa es azul marino sobre fondo claro.** Puesto sobre
 *    una banda marino desaparece. Y el logotipo tenía que entrar: un informe
 *    que sale de la empresa y se entrega va firmado.
 *
 * 2. **Esto se imprime.** Alguien se lleva el informe a la tienda a buscar la
 *    factura. Una banda de color a sangre en la cabecera de cinco pestañas es
 *    tóner gastado en decoración, y en una impresora láser de oficina sale
 *    sucia.
 *
 * Así que la cabecera es blanca —logotipo a la izquierda, título a la
 * derecha— y la marca la pone un filo de 4 píxeles en degradado de azul a
 * marino, que es exactamente lo que manda el sistema de diseño (§3) cuando el
 * bloque lleva texto pequeño o atenuado encima: filo, no fondo.
 *
 * EL LOGOTIPO VA ENCIMA DEL TÍTULO, Y NO AL LADO
 * -----------------------------------------------
 * Al lado sería más compacto, y se intentó: logotipo a la izquierda y título
 * apartado con sangría. El problema es que la sangría de Excel se mide en
 * caracteres de la fuente normal, no en píxeles, y cuántos píxeles son
 * exactamente depende de la fuente y de la versión. Si el cálculo se queda
 * corto, el título se monta ENCIMA del logotipo, y eso no se ve hasta que
 * alguien abre el archivo.
 *
 * Como aquí no hay Excel con el que comprobarlo, se elige la disposición que
 * no puede fallar: logotipo arriba a la izquierda, en su propia fila, y el
 * bloque de título debajo. Es además la disposición de un papel con membrete
 * de toda la vida, y se lee igual en la pestaña de tres columnas y en la de
 * veintiocho — cosa que la versión «al lado» tampoco conseguía, porque el
 * ancho de la primera columna cambia en cada pestaña.
 *
 * LAS CINCO PESTAÑAS, Y POR QUÉ ESE ORDEN
 * ---------------------------------------
 *   1. Resumen         lo que hay que saber si sólo se mira una cosa
 *   2. A revisar       lo que hay que hacer, y nada más
 *   3. Auditoría       las 4.000 filas, filtrables, para quien quiera buscar
 *   4. Formas de pago  en qué se cobró el período
 *   5. Método          cómo se calculó, para que el informe se pueda discutir
 *
 * La pestaña «Método» no es relleno. Este informe afirma que faltan 203.239 Bs
 * por asentar en una factura concreta; quien lo reciba tiene derecho a saber de
 * dónde sale el total contra el que se compara, por qué el corte está en 5 Bs y
 * qué documentos no se juzgan. Si eso no viaja con el archivo, vive sólo en la
 * cabeza de quien lo escribió.
 */

require_once __DIR__ . '/LibroExcel.php';
require_once __DIR__ . '/Auditoria.php';
require_once __DIR__ . '/Periodo.php';

final class InformeExcel
{
    /* --- Los colores de la casa (DESIGN-SYSTEM.md §3) -------------------- */

    private const MARINO   = '0F172A';  // texto de títulos, extremo del filo
    private const AZUL     = '0369A1';  // acento, cabeceras de tabla
    private const AMBAR    = 'FFF7E6';  // fondo de las filas a revisar
    private const AMBARDUR = '92400E';  // su texto
    private const AMBARBOR = 'F3D08A';  // su borde
    private const GRISCLA  = 'F8FAFC';  // bandas alternas
    private const GRISMED  = 'F1F5F9';  // fondo de tarjeta
    private const GRISTXT  = '64748B';  // texto secundario
    private const ROJO     = 'B91C1C';  // lo que falta
    private const VERDE    = '15803D';  // lo que cuadra
    private const BLANCO   = 'FFFFFF';
    private const BORDE    = 'E2E8F0';

    /** El logotipo, relativo a la raíz del proyecto. */
    private const LOGO = '/vistas/img/industrias-rrc.png';

    /** Lo que ocupa el logotipo en la cabecera, en píxeles. */
    private const LOGO_ANCHO = 132;
    private const LOGO_ALTO  = 63;

    /**
     * La fila en la que empieza el contenido, bajo la cabecera de marca.
     *
     * Es publica porque `cli/probar-excel.php` comprueba que la pestana grande
     * tenga una fila por documento, y para eso necesita saber cuantas ocupa la
     * cabecera. Con el numero escrito a mano en los dos sitios, cambiar el
     * diseno rompia la prueba por un motivo que no era un fallo.
     */
    public const PRIMERA_FILA = 8;

    /**
     * Las columnas de la pestaña grande: rótulo, ancho y cómo se trata.
     *
     * Están aquí, juntas y en orden, para que mover una columna sea mover una
     * línea. Los tipos: `t` texto, `n` número entero, `b` bolívares con dos
     * decimales, `d` fecha, `p` porcentaje.
     *
     * @var list<array{clave:string,rotulo:string,ancho:float,tipo:string}>
     */
    private const COLUMNAS = [
        ['clave' => 'fecha',         'rotulo' => 'Fecha',          'ancho' => 11, 'tipo' => 'd'],
        ['clave' => 'tienda',        'rotulo' => 'Tienda',         'ancho' => 28, 'tipo' => 't'],
        ['clave' => 'tipo_doc',      'rotulo' => 'Tipo',           'ancho' => 6,  'tipo' => 't'],
        ['clave' => 'numero_doc',    'rotulo' => 'Documento',      'ancho' => 11, 'tipo' => 'n'],
        ['clave' => 'estado',        'rotulo' => 'Estado',         'ancho' => 10, 'tipo' => 't'],
        ['clave' => 'clase_doc',     'rotulo' => 'Clase',          'ancho' => 15, 'tipo' => 't'],
        ['clave' => 'cliente_nombre','rotulo' => 'Cliente',        'ancho' => 30, 'tipo' => 't'],
        ['clave' => 'cliente_cedula','rotulo' => 'Cédula / RIF',   'ancho' => 14, 'tipo' => 't'],
        ['clave' => 'vendedor',      'rotulo' => 'Vendedor',       'ancho' => 10, 'tipo' => 't'],
        ['clave' => 'caja',          'rotulo' => 'Caja',           'ancho' => 7,  'tipo' => 't'],
        ['clave' => 'hora',          'rotulo' => 'Hora',           'ancho' => 9,  'tipo' => 't'],
        ['clave' => 'lineas',        'rotulo' => 'Líneas',         'ancho' => 8,  'tipo' => 'n'],
        ['clave' => 'unidades',      'rotulo' => 'Piezas enc.',    'ancho' => 10, 'tipo' => 'n'],
        ['clave' => 'det_piezas',    'rotulo' => 'Piezas det.',    'ancho' => 10, 'tipo' => 'n'],
        ['clave' => 'monto_bruto',   'rotulo' => 'Bruto',          'ancho' => 14, 'tipo' => 'b'],
        ['clave' => 'descuento',     'rotulo' => 'Descuento',      'ancho' => 13, 'tipo' => 'b'],
        ['clave' => 'iva',           'rotulo' => 'IVA',            'ancho' => 13, 'tipo' => 'b'],
        ['clave' => 'igtf',          'rotulo' => 'IGTF',           'ancho' => 12, 'tipo' => 'b'],
        ['clave' => 'total_factura', 'rotulo' => 'Total factura',  'ancho' => 15, 'tipo' => 'b'],
        ['clave' => 'detalle_neto',  'rotulo' => 'Detalle neto',   'ancho' => 15, 'tipo' => 'b'],
        ['clave' => 'dif_detalle',   'rotulo' => 'Dif. detalle',   'ancho' => 13, 'tipo' => 'b'],
        ['clave' => 'formas',        'rotulo' => 'Formas',         'ancho' => 8,  'tipo' => 'n'],
        ['clave' => 'pagado',        'rotulo' => 'Pagado',         'ancho' => 15, 'tipo' => 'b'],
        ['clave' => 'dif_pago',      'rotulo' => 'Dif. pago',      'ancho' => 14, 'tipo' => 'b'],
        ['clave' => 'pct_pagado',    'rotulo' => '% pagado',       'ancho' => 10, 'tipo' => 'p'],
        ['clave' => 'clase',         'rotulo' => 'Resultado',      'ancho' => 12, 'tipo' => 't'],
        ['clave' => 'desglose',      'rotulo' => 'Formas de pago', 'ancho' => 46, 'tipo' => 't'],
        ['clave' => 'diagnostico',   'rotulo' => 'Observación',    'ancho' => 70, 'tipo' => 't'],
    ];

    /**
     * Escribe el `.xlsx`.
     *
     * @param array<string,mixed> $informe lo que devolvió `Auditoria::correr()`
     */
    public static function escribir(array $informe, string $ruta): void
    {
        $libro = new LibroExcel(
            'Auditoría de formas de pago · ' . (string) $informe['rotulo'],
            'Industrias RRC, C.A.'
        );

        self::declararEstilos($libro);

        self::hojaResumen($libro, $informe);
        self::hojaARevisar($libro, $informe);
        self::hojaAuditoria($libro, $informe);
        self::hojaFormas($libro, $informe);
        self::hojaMetodo($libro, $informe);

        $libro->guardar($ruta);
    }

    /** Un nombre de archivo que dice qué es y de cuándo, sin espacios raros. */
    public static function nombreArchivo(array $informe): string
    {
        return sprintf(
            'Auditoria-formas-de-pago_%s_%s.xlsx',
            str_replace('-', '', (string) $informe['desde']),
            str_replace('-', '', (string) $informe['hasta'])
        );
    }

    /* =====================================================================
     *  Los estilos, todos declarados en un sitio
     * ===================================================================== */

    private static function declararEstilos(LibroExcel $libro): void
    {
        /* --- La cabecera de marca ---------------------------------------- */

        $libro->estilo('papel', ['fondo' => self::BLANCO]);

        $libro->estilo('titulo', [
            'negrita' => true, 'tamanio' => 17, 'color' => self::MARINO,
            'fondo' => self::BLANCO, 'v' => 'bottom', 'h' => 'left', 'sangria' => 1,
        ]);

        $libro->estilo('subtitulo', [
            'tamanio' => 11, 'color' => self::AZUL, 'fondo' => self::BLANCO,
            'v' => 'center', 'h' => 'left', 'sangria' => 1,
        ]);

        $libro->estilo('sello', [
            'tamanio' => 9, 'color' => self::GRISTXT, 'fondo' => self::BLANCO,
            'v' => 'top', 'h' => 'left', 'sangria' => 1,
        ]);

        /*
         * El filo de marca: degradado de azul a marino, de lado a lado. Va
         * SIEMPRE sobre una celda combinada; sobre celdas sueltas el degradado
         * se repite en cada una y queda como una cebra (ver `LibroExcel`).
         */
        $libro->estilo('filo', ['degradado' => [self::AZUL, self::MARINO]]);

        /* --- Cabecera de tabla ------------------------------------------- */

        $libro->estilo('cabecera', [
            'negrita' => true, 'tamanio' => 10, 'color' => self::BLANCO,
            'fondo' => self::AZUL, 'h' => 'center', 'v' => 'center', 'ajustar' => true,
        ]);

        /* --- Cuerpo, por tipo de dato y por banda ------------------------ */

        foreach (['', 'gris', 'ambar'] as $banda) {
            $fondo = match ($banda) {
                'gris'  => ['fondo' => self::GRISCLA],
                'ambar' => ['fondo' => self::AMBAR, 'color' => self::AMBARDUR],
                default => ['fondo' => self::BLANCO],
            };

            $borde = ['borde' => 'abajo', 'borde_color' => self::BORDE];
            $sufijo = $banda === '' ? '' : '-' . $banda;

            $libro->estilo('t' . $sufijo, $fondo + $borde + ['v' => 'center']);
            $libro->estilo('n' . $sufijo, $fondo + $borde
                + ['formato' => '#,##0', 'h' => 'center', 'v' => 'center']);
            $libro->estilo('b' . $sufijo, $fondo + $borde
                + ['formato' => '#,##0.00', 'h' => 'right', 'v' => 'center', 'fuente' => 'Consolas']);
            $libro->estilo('d' . $sufijo, $fondo + $borde
                + ['formato' => 'dd/mm/yyyy', 'h' => 'center', 'v' => 'center']);
            $libro->estilo('p' . $sufijo, $fondo + $borde
                + ['formato' => '#,##0.0"%"', 'h' => 'right', 'v' => 'center', 'fuente' => 'Consolas']);
            $libro->estilo('obs' . $sufijo, $fondo + $borde
                + ['tamanio' => 9, 'ajustar' => true, 'v' => 'top']);

            /*
             * EL MISMO TEXTO SIN AJUSTAR, PARA LA PESTAÑA GRANDE
             * ---------------------------------------------------
             * «Ajustar» reparte el texto en varias líneas DENTRO de la celda,
             * y entonces la fila tiene que ser lo bastante alta o el texto se
             * CORTA: Excel no avisa, sencillamente no se ve el final. Con
             * cuatro mil filas no se puede dar a cada una la altura que pida
             * —la hoja se vuelve inmanejable—, así que ahí el texto va en una
             * línea y la última columna lo desborda hacia la derecha, donde no
             * hay nada. Se lee entero y la fila sigue midiendo una línea.
             */
            $libro->estilo('obs1' . $sufijo, $fondo + $borde
                + ['tamanio' => 9, 'ajustar' => false, 'v' => 'center']);
        }

        /*
         * La diferencia en rojo cuando falta dinero. DOS señales y no una: el
         * color solo no vale (DESIGN-SYSTEM §3, «el estado se nota por forma,
         * no sólo por color»), y la columna «Resultado» con la palabra REVISAR
         * es la otra.
         */
        $libro->estilo('b-falta', [
            'negrita' => true, 'color' => self::ROJO, 'fondo' => self::AMBAR,
            'formato' => '#,##0.00', 'h' => 'right', 'v' => 'center', 'fuente' => 'Consolas',
            'borde' => 'abajo', 'borde_color' => self::BORDE,
        ]);

        $libro->estilo('res-revisar', [
            'negrita' => true, 'tamanio' => 9, 'color' => self::AMBARDUR, 'fondo' => self::AMBAR,
            'h' => 'center', 'v' => 'center', 'borde' => 'abajo', 'borde_color' => self::BORDE,
        ]);
        $libro->estilo('res-cuadra', [
            'tamanio' => 9, 'color' => self::VERDE, 'fondo' => self::BLANCO,
            'h' => 'center', 'v' => 'center', 'borde' => 'abajo', 'borde_color' => self::BORDE,
        ]);
        $libro->estilo('res-cuadra-gris', [
            'tamanio' => 9, 'color' => self::VERDE, 'fondo' => self::GRISCLA,
            'h' => 'center', 'v' => 'center', 'borde' => 'abajo', 'borde_color' => self::BORDE,
        ]);
        $libro->estilo('res-redondeo', [
            'tamanio' => 9, 'color' => self::GRISTXT, 'fondo' => self::GRISCLA,
            'h' => 'center', 'v' => 'center', 'borde' => 'abajo', 'borde_color' => self::BORDE,
        ]);
        $libro->estilo('res-noaplica', [
            'tamanio' => 9, 'cursiva' => true, 'color' => self::GRISTXT, 'fondo' => self::BLANCO,
            'h' => 'center', 'v' => 'center', 'borde' => 'abajo', 'borde_color' => self::BORDE,
        ]);
        $libro->estilo('res-noaplica-gris', [
            'tamanio' => 9, 'cursiva' => true, 'color' => self::GRISTXT, 'fondo' => self::GRISCLA,
            'h' => 'center', 'v' => 'center', 'borde' => 'abajo', 'borde_color' => self::BORDE,
        ]);

        /* --- El resumen: secciones y tarjetas ---------------------------- */

        $libro->estilo('seccion', [
            'negrita' => true, 'tamanio' => 11, 'color' => self::MARINO,
            'fondo' => self::BLANCO, 'v' => 'bottom',
            'borde' => 'abajo', 'borde_color' => self::AZUL, 'borde_grosor' => 'medium',
        ]);

        /*
         * Una «tarjeta» son tres celdas apiladas con el mismo relleno: rótulo,
         * cifra y pie. No hay cajas en Excel, así que la tarjeta se hace con
         * un filo de color arriba y un borde a los lados, que es lo que la
         * separa de la de al lado.
         */
        $libro->estilo('tarjeta-filo', ['fondo' => self::AZUL]);
        $libro->estilo('tarjeta-filo-aviso', ['fondo' => self::AMBARDUR]);

        $libro->estilo('tarjeta-rotulo', [
            'negrita' => true, 'tamanio' => 8, 'color' => self::GRISTXT, 'fondo' => self::GRISMED,
            'h' => 'center', 'v' => 'center',
        ]);
        $libro->estilo('tarjeta-cifra', [
            'negrita' => true, 'tamanio' => 20, 'color' => self::MARINO, 'fondo' => self::GRISMED,
            'h' => 'center', 'v' => 'center', 'formato' => '#,##0',
        ]);
        $libro->estilo('tarjeta-cifra-bs', [
            'negrita' => true, 'tamanio' => 14, 'color' => self::MARINO, 'fondo' => self::GRISMED,
            'h' => 'center', 'v' => 'center', 'formato' => '#,##0.00',
        ]);
        $libro->estilo('tarjeta-cifra-aviso', [
            'negrita' => true, 'tamanio' => 20, 'color' => self::AMBARDUR, 'fondo' => self::AMBAR,
            'h' => 'center', 'v' => 'center', 'formato' => '#,##0',
        ]);
        $libro->estilo('tarjeta-rotulo-aviso', [
            'negrita' => true, 'tamanio' => 8, 'color' => self::AMBARDUR, 'fondo' => self::AMBAR,
            'h' => 'center', 'v' => 'center',
        ]);
        $libro->estilo('tarjeta-pie', [
            'tamanio' => 8, 'color' => self::GRISTXT, 'fondo' => self::GRISMED,
            'h' => 'center', 'v' => 'top', 'ajustar' => true,
            'borde' => 'abajo', 'borde_color' => self::BORDE,
        ]);
        $libro->estilo('tarjeta-pie-aviso', [
            'tamanio' => 8, 'color' => self::AMBARDUR, 'fondo' => self::AMBAR,
            'h' => 'center', 'v' => 'top', 'ajustar' => true,
            'borde' => 'abajo', 'borde_color' => self::AMBARBOR,
        ]);
        $libro->estilo('hueco', ['fondo' => self::BLANCO]);

        /* --- Listas de rótulo y valor ------------------------------------ */

        $libro->estilo('rotulo', [
            'tamanio' => 10, 'fondo' => self::BLANCO, 'v' => 'center', 'sangria' => 1,
            'borde' => 'abajo', 'borde_color' => self::BORDE,
        ]);
        $libro->estilo('rotulo-sangrado', [
            'tamanio' => 9, 'color' => self::GRISTXT, 'fondo' => self::BLANCO,
            'v' => 'center', 'sangria' => 3, 'borde' => 'abajo', 'borde_color' => self::BORDE,
        ]);
        $libro->estilo('valor', [
            'negrita' => true, 'tamanio' => 10, 'fondo' => self::BLANCO, 'formato' => '#,##0',
            'h' => 'right', 'v' => 'center', 'fuente' => 'Consolas',
            'borde' => 'abajo', 'borde_color' => self::BORDE,
        ]);
        $libro->estilo('valor-bs', [
            'negrita' => true, 'tamanio' => 10, 'fondo' => self::BLANCO, 'formato' => '#,##0.00',
            'h' => 'right', 'v' => 'center', 'fuente' => 'Consolas',
            'borde' => 'abajo', 'borde_color' => self::BORDE,
        ]);
        $libro->estilo('valor-rojo', [
            'negrita' => true, 'tamanio' => 10, 'color' => self::ROJO, 'fondo' => self::BLANCO,
            'formato' => '#,##0.00', 'h' => 'right', 'v' => 'center', 'fuente' => 'Consolas',
            'borde' => 'abajo', 'borde_color' => self::BORDE,
        ]);
        $libro->estilo('valor-verde', [
            'negrita' => true, 'tamanio' => 10, 'color' => self::VERDE, 'fondo' => self::BLANCO,
            'formato' => '#,##0', 'h' => 'right', 'v' => 'center', 'fuente' => 'Consolas',
            'borde' => 'abajo', 'borde_color' => self::BORDE,
        ]);
        $libro->estilo('valor-texto', [
            'tamanio' => 10, 'fondo' => self::BLANCO, 'h' => 'right', 'v' => 'center',
            'borde' => 'abajo', 'borde_color' => self::BORDE,
        ]);

        /* --- Texto corrido ----------------------------------------------- */

        $libro->estilo('nota', [
            'tamanio' => 9, 'color' => self::GRISTXT, 'fondo' => self::BLANCO,
            'ajustar' => true, 'v' => 'top',
        ]);
        $libro->estilo('parrafo', [
            'tamanio' => 10, 'fondo' => self::BLANCO, 'ajustar' => true, 'v' => 'top',
        ]);
        $libro->estilo('mono', [
            'fuente' => 'Consolas', 'tamanio' => 9, 'color' => self::MARINO,
            'fondo' => self::GRISMED, 'v' => 'center', 'ajustar' => false, 'sangria' => 1,
        ]);
        $libro->estilo('aviso', [
            'tamanio' => 10, 'ajustar' => true, 'v' => 'top',
            'fondo' => self::AMBAR, 'color' => self::AMBARDUR,
            'borde' => 'izquierda', 'borde_color' => self::AMBARDUR, 'borde_grosor' => 'medium',
        ]);
        $libro->estilo('aviso-bajo', [
            'tamanio' => 10, 'ajustar' => true, 'v' => 'top', 'fondo' => self::GRISMED,
            'borde' => 'izquierda', 'borde_color' => self::GRISTXT, 'borde_grosor' => 'medium',
        ]);
        $libro->estilo('total', [
            'negrita' => true, 'tamanio' => 11, 'color' => self::BLANCO, 'fondo' => self::MARINO,
            'formato' => '#,##0.00', 'h' => 'right', 'v' => 'center', 'fuente' => 'Consolas',
        ]);
        $libro->estilo('total-rotulo', [
            'negrita' => true, 'tamanio' => 11, 'color' => self::BLANCO, 'fondo' => self::MARINO,
            'v' => 'center', 'sangria' => 1,
        ]);
    }

    /**
     * La cabecera de marca que llevan las cinco pestañas.
     *
     * Devuelve la primera fila libre. Que la devuelva —en vez de ser una
     * constante que se copia— evita el error clásico de cambiar la cabecera y
     * dejar la tabla pisada.
     */
    private static function encabezar(
        HojaExcel $hoja, array $informe, string $titulo, string $subtitulo, int $columnas
    ): int {
        $hoja->sinRejilla();

        $ultima = LibroExcel::columna($columnas);

        /*
         * Las seis filas de la cabecera van COMBINADAS de lado a lado. Dos
         * razones: el título puede ser más largo que la primera columna y así
         * no se corta, y el filo de marca de la fila 6 necesita ser UNA sola
         * celda para que el degradado la recorra entera en vez de repetirse en
         * cada columna (ver `LibroExcel::idRelleno()`).
         */
        for ($f = 1; $f <= 6; $f++) {
            $hoja->combinar('A' . $f . ':' . $ultima . $f);
        }

        /* Fila 1: aire. Fila 2: sólo el logotipo, que flota encima. */
        $hoja->fila(1, [null], 'papel', 4);
        $hoja->fila(2, [null], 'papel', 52);

        $hoja->fila(3, [$titulo], 'titulo', 24);
        $hoja->fila(4, [$subtitulo], 'subtitulo', 16);
        $hoja->fila(5, [sprintf(
            'Industrias RRC, C.A.  ·  leído del AS400 en vivo el %s  ·  %s s de consulta',
            date('d/m/Y \a \l\a\s H:i', (int) strtotime((string) $informe['generado_en'])),
            number_format((float) $informe['segundos'], 2, ',', '.')
        )], 'sello', 14);

        /* El filo de marca, en degradado de azul a marino. */
        $hoja->fila(6, [null], 'filo', 4);

        $hoja->fila(7, array_fill(0, $columnas, null), 'papel', 6);

        /*
         * El logotipo, anclado a la celda A2 y con su tamaño natural.
         *
         * La fila 2 mide 52 puntos, que son unos 69 píxeles, y el logotipo 63:
         * entra con holgura y no pisa el título de la fila 3. Va anclado a una
         * celda (`oneCellAnchor`) y no estirado entre dos, así que cambiar el
         * ancho de una columna lo mueve pero no lo deforma.
         */
        $hoja->imagen(
            dirname(__DIR__) . self::LOGO,
            2, 1, self::LOGO_ANCHO, self::LOGO_ALTO, 7, 3,
            'Industrias RRC', 'Logotipo de Industrias RRC, C.A.'
        );

        return self::PRIMERA_FILA;
    }

    /** El pie de página impreso, igual en las cinco pestañas. */
    private static function pieImpreso(array $informe): string
    {
        return '&L&8Industrias RRC, C.A.  ·  Auditoría de formas de pago'
            . '&C&8' . (string) $informe['rotulo']
            . '&R&8Página &P de &N';
    }

    /* =====================================================================
     *  1. Resumen
     * ===================================================================== */

    private static function hojaResumen(LibroExcel $libro, array $informe): void
    {
        $r = $informe['resumen'];

        $hoja = $libro->hoja('Resumen');

        /* Siete columnas: un margen, cinco tarjetas y otro margen. */
        $hoja->anchos([2.5, 19, 19, 19, 19, 19, 2.5]);
        $hoja->color(self::AZUL);
        $hoja->impresion(['orientacion' => 'portrait', 'ajustar' => true,
            'pie' => self::pieImpreso($informe)]);

        $f = self::encabezar($hoja, $informe, 'Auditoría de formas de pago',
            (string) $informe['rotulo'], 7);

        /* --- Las cinco tarjetas ------------------------------------------ */

        $pctCuadran = $r['documentos'] > 0
            ? number_format($r['cuadran'] / $r['documentos'] * 100, 1, ',', '.') . ' % del total'
            : '';

        $tarjetas = [
            ['rotulo' => 'DOCUMENTOS',  'cifra' => (int) $r['documentos'],
             'pie' => (int) $r['dias'] . ($r['dias'] === 1 ? ' día' : ' días') . ' con movimiento'],
            ['rotulo' => 'CUADRAN',     'cifra' => (int) $r['cuadran'], 'pie' => $pctCuadran],
            ['rotulo' => 'REDONDEO',    'cifra' => (int) $r['redondeo'],
             'pie' => number_format((float) $r['redondeo_bs'], 2, ',', '.') . ' Bs, no es dinero que falte'],
            ['rotulo' => 'A REVISAR',   'cifra' => (int) $r['revisar'],
             'pie' => $r['revisar'] > 0
                ? number_format((float) $r['falta_bs'], 2, ',', '.') . ' Bs por asentar'
                : 'ni uno: todo cuadra',
             'aviso' => $r['revisar'] > 0],
            ['rotulo' => 'NO APLICA',   'cifra' => (int) $r['no_aplica'],
             'pie' => 'ajustes NC-2, sin nada que contrastar'],
        ];

        /* El filo superior de las cinco tarjetas, en su propia fila. */
        $filo = [null];

        foreach ($tarjetas as $t) {
            $filo[] = ['v' => null, 'e' => !empty($t['aviso']) ? 'tarjeta-filo-aviso' : 'tarjeta-filo'];
        }

        $filo[] = null;
        $hoja->fila($f++, $filo, 'hueco', 3);

        foreach (['rotulo', 'cifra', 'pie'] as $parte) {
            $fila = [null];

            foreach ($tarjetas as $t) {
                $aviso = !empty($t['aviso']) ? '-aviso' : '';

                $fila[] = match ($parte) {
                    'rotulo' => ['v' => $t['rotulo'], 'e' => 'tarjeta-rotulo' . $aviso],
                    'cifra'  => ['v' => $t['cifra'],  'e' => 'tarjeta-cifra' . $aviso],
                    default  => ['v' => $t['pie'],    'e' => 'tarjeta-pie' . $aviso],
                };
            }

            $fila[] = null;

            $hoja->fila($f++, $fila, 'hueco', match ($parte) {
                'rotulo' => 15.0, 'cifra' => 32.0, default => 26.0,
            });
        }

        $f++;

        /* --- El dinero, que es la cifra que se cuenta por teléfono ------- */

        $hoja->combinar('B' . $f . ':D' . $f);
        $hoja->combinar('E' . $f . ':F' . $f);
        $hoja->filaDesde($f, 2, [
            ['v' => 'TOTAL FACTURADO EN EL PERÍODO', 'e' => 'total-rotulo'],
            null, null,
            ['v' => round((float) $r['total_facturado'], 2), 'e' => 'total'],
        ], 'total-rotulo', 24);
        $f++;

        $hoja->combinar('B' . $f . ':D' . $f);
        $hoja->combinar('E' . $f . ':F' . $f);
        $hoja->filaDesde($f, 2, [
            ['v' => 'Total registrado en formas de pago', 'e' => 'rotulo'],
            null, null,
            ['v' => round((float) $r['total_pagado'], 2), 'e' => 'valor-bs'],
        ], 'rotulo', 20);
        $f += 2;

        /* --- El detalle contra el encabezado ----------------------------- */

        $f = self::seccion($hoja, $f, 'El detalle de líneas contra el encabezado');
        $f = self::dato($hoja, $f, 'Cuadra', (int) $r['detalle_cuadra'], 'valor-verde');
        $f = self::dato($hoja, $f, 'NO cuadra', (int) $r['detalle_descuadrado'],
            $r['detalle_descuadrado'] > 0 ? 'valor-rojo' : 'valor');
        $f = self::dato($hoja, $f, 'No aplica (abonos y ajustes)', (int) $r['detalle_no_aplica'], 'valor');
        $f++;

        /* --- Lo que no se marca, y por qué ------------------------------- */

        $f = self::seccion($hoja, $f, 'Lo que no se marca, y por qué');
        $f = self::dato($hoja, $f, 'Sin una línea de pago', (int) $r['sin_pagos'], 'valor');
        $f = self::dato($hoja, $f, 'Sin líneas de detalle', (int) $r['sin_lineas'], 'valor');
        $f = self::dato($hoja, $f, 'Anuladas (cuadran todas)', (int) $r['anuladas'], 'valor');
        $f = self::dato($hoja, $f, 'Abonos NC-3 (cuadran todas)', (int) $r['abonos'], 'valor');
        $f = self::dato($hoja, $f, 'Ajustes NC-2 (nada que contrastar)', (int) $r['ajustes'], 'valor');
        $f = self::dato($hoja, $f, 'Facturas manuales (FLA011 = M)', (int) $r['manuales'], 'valor');
        $f++;

        /* --- Por tipo de documento --------------------------------------- */

        if ($r['tipos'] !== []) {
            $f = self::seccion($hoja, $f, 'Por tipo de documento');

            foreach ($r['tipos'] as $tipo => $n) {
                $f = self::dato($hoja, $f, (string) $tipo, (int) $n, 'valor');
            }

            $f++;
        }

        /* --- Las tiendas con dinero por asentar -------------------------- */

        if ($r['tiendas'] !== []) {
            $f = self::seccion($hoja, $f, 'Dónde está el dinero por asentar');

            foreach ($r['tiendas'] as $tienda => $bs) {
                $f = self::dato($hoja, $f, (string) $tienda, round((float) $bs, 2), 'valor-rojo');
            }

            $f++;
        }

        /* --- Los avisos, que es lo que el informe no se calla ------------ */

        if ($informe['avisos'] !== []) {
            $f = self::seccion($hoja, $f, 'Avisos');

            $hoja->combinar('B' . $f . ':F' . $f);
            $hoja->filaDesde($f++, 2, [
                'Lo que este informe advierte de sí mismo: supuestos que podrían haber '
                . 'dejado de ser verdad desde que se midieron, y lo que se encontró y no '
                . 'cabe en ninguna columna.',
            ], 'nota', 28);

            $f++;

            foreach ($informe['avisos'] as $aviso) {
                $texto = is_array($aviso) ? (string) $aviso['texto'] : (string) $aviso;
                $nivel = is_array($aviso) ? (string) $aviso['nivel'] : 'medio';

                $hoja->combinar('B' . $f . ':F' . $f);
                $hoja->filaDesde($f++, 2, [$texto],
                    $nivel === 'bajo' ? 'aviso-bajo' : 'aviso',
                    (float) max(30, 13 * ceil(mb_strlen($texto) / 92)));

                $hoja->fila($f++, array_fill(0, 7, null), 'papel', 4);
            }
        }
    }

    /** Un título de sección, con su filo azul debajo. Devuelve la fila siguiente. */
    private static function seccion(HojaExcel $hoja, int $fila, string $texto): int
    {
        $hoja->combinar('B' . $fila . ':F' . $fila);
        $hoja->filaDesde($fila, 2, [$texto], 'seccion', 22);

        return $fila + 1;
    }

    /** Una línea «rótulo … valor» del resumen. Devuelve la fila siguiente. */
    private static function dato(
        HojaExcel $hoja, int $fila, string $rotulo, mixed $valor, string $estilo = 'valor'
    ): int {
        $hoja->combinar('B' . $fila . ':D' . $fila);
        $hoja->combinar('E' . $fila . ':F' . $fila);

        $hoja->filaDesde($fila, 2, [
            ['v' => $rotulo, 'e' => 'rotulo'],
            null, null,
            ['v' => $valor, 'e' => $estilo],
        ], 'rotulo', 18);

        return $fila + 1;
    }

    /* =====================================================================
     *  2. A revisar
     * ===================================================================== */

    private static function hojaARevisar(LibroExcel $libro, array $informe): void
    {
        $hoja = $libro->hoja('A revisar');
        $hoja->anchos([11, 26, 6, 11, 8, 15, 15, 14, 10, 40, 64]);
        $hoja->color(self::AMBARDUR);
        $hoja->impresion(['orientacion' => 'landscape', 'ajustar' => true,
            'pie' => self::pieImpreso($informe)]);

        $aRevisar = array_values(array_filter(
            $informe['documentos'],
            static fn($d) => (string) $d['clase'] === Auditoria::REVISAR
        ));

        usort($aRevisar, static fn($a, $b) => abs((float) $b['dif_pago']) <=> abs((float) $a['dif_pago']));

        $falta = 0.0;

        foreach ($aRevisar as $d) {
            if ((float) $d['dif_pago'] > 0) {
                $falta += (float) $d['dif_pago'];
            }
        }

        $f = self::encabezar($hoja, $informe, 'Lo que hay que revisar',
            count($aRevisar) === 0
                ? 'Ni un documento: todo cuadra'
                : sprintf('%s documento(s) · %s Bs cobrados y sin asentar',
                    number_format(count($aRevisar), 0, ',', '.'),
                    number_format($falta, 2, ',', '.')),
            11);

        if ($aRevisar === []) {
            $hoja->combinar('A' . $f . ':K' . $f);
            $hoja->fila($f, [
                'No hay ni un documento a revisar en este período: todas las facturas '
                . 'cuadran con sus formas de pago al céntimo o dentro del redondeo del '
                . 'IGTF. Las demás pestañas tienen el detalle de la comprobación.',
            ], 'parrafo', 40);

            return;
        }

        $hoja->combinar('A' . $f . ':K' . $f);
        $hoja->fila($f++, [
            'Ordenado por tamaño de la diferencia. La observación describe el patrón que '
            . 'se ve en el archivo, no la causa: quien revise la factura en la tienda '
            . 'tiene el papel delante y decide. Esto le dice dónde mirar.',
        ], 'nota', 30);

        $f++;

        $filaCabecera = $f;

        $hoja->fila($f++, ['Fecha', 'Tienda', 'Tipo', 'Documento', 'Caja', 'Total factura',
            'Pagado', 'Falta (Bs)', '% pagado', 'Formas de pago registradas',
            'Qué se ve en el archivo'], 'cabecera', 30);

        foreach ($aRevisar as $d) {
            /*
             * LA ALTURA SE CALCULA; UNA FIJA CORTARÍA EL DIAGNÓSTICO
             * -------------------------------------------------------
             * Esta pestaña es la accionable: son seis filas en un mes y cada
             * una tiene que leerse ENTERA, porque el diagnóstico es lo que
             * dice dónde mirar. Con una altura fija —34 puntos, que es lo que
             * había— un diagnóstico de cuatro líneas se corta por la mitad y
             * Excel no avisa de nada: simplemente no se ve el final.
             *
             * Así que se cuenta cuántas líneas necesita el texto más largo de
             * la fila. Los divisores son los anchos de esas dos columnas en
             * caracteres (40 y 64), menos un poco de holgura para que una
             * palabra larga que salta de línea no deje la última cortada.
             */
            $lineas = max(
                (int) ceil(mb_strlen((string) $d['desglose']) / 37),
                (int) ceil(mb_strlen((string) $d['diagnostico']) / 60),
                1
            );

            $hoja->fila($f++, [
                ['v' => LibroExcel::serieFecha((string) $d['fecha']), 'e' => 'd-ambar'],
                ['v' => $d['tienda'],      'e' => 't-ambar'],
                ['v' => $d['tipo_doc'],    'e' => 't-ambar'],
                ['v' => (int) $d['numero_doc'], 'e' => 'n-ambar'],
                ['v' => $d['caja'],        'e' => 't-ambar'],
                ['v' => (float) $d['total_factura'], 'e' => 'b-ambar'],
                ['v' => (float) $d['pagado'],        'e' => 'b-ambar'],
                ['v' => (float) $d['dif_pago'],      'e' => 'b-falta'],
                ['v' => $d['pct_pagado'] === null ? null : (float) $d['pct_pagado'], 'e' => 'p-ambar'],
                ['v' => $d['desglose'],    'e' => 'obs-ambar'],
                ['v' => $d['diagnostico'], 'e' => 'obs-ambar'],
            ], 't-ambar', (float) max(22, $lineas * 11.5 + 5));
        }

        $hoja->congelar($filaCabecera);
        $hoja->repetirCabecera($filaCabecera);
        $hoja->filtrar('A' . $filaCabecera . ':K' . ($f - 1));
    }

    /* =====================================================================
     *  3. Auditoría — la rejilla entera
     * ===================================================================== */

    private static function hojaAuditoria(LibroExcel $libro, array $informe): void
    {
        $hoja = $libro->hoja('Auditoría');
        $hoja->anchos(array_map(static fn($c) => $c['ancho'], self::COLUMNAS));
        $hoja->color(self::MARINO);
        $hoja->zoom(85);
        $hoja->impresion(['orientacion' => 'landscape', 'ajustar' => true,
            'pie' => self::pieImpreso($informe)]);

        $n = count(self::COLUMNAS);

        $f = self::encabezar($hoja, $informe, 'Auditoría, documento a documento',
            number_format((int) $informe['resumen']['documentos'], 0, ',', '.')
            . ' documentos  ·  ' . (string) $informe['rotulo'], $n);

        $filaCabecera = $f;
        $hoja->fila($f++, array_map(static fn($c) => $c['rotulo'], self::COLUMNAS), 'cabecera', 34);

        $banda = 0;

        foreach ($informe['documentos'] as $d) {
            $clase = (string) $d['clase'];

            /*
             * La banda de color la decide el resultado, y sólo cuando dice
             * algo: ámbar lo que hay que revisar, gris claro el redondeo, y
             * para lo que cuadra se alternan las filas para poder seguirlas
             * con el dedo en una pantalla de 28 columnas.
             */
            $sufijo = match ($clase) {
                Auditoria::REVISAR  => '-ambar',
                Auditoria::REDONDEO => '-gris',
                default             => ($banda % 2 === 1) ? '-gris' : '',
            };

            $banda++;

            $celdas = [];

            foreach (self::COLUMNAS as $c) {
                $celdas[] = self::celdaDeColumna($d, $c, $sufijo);
            }

            // Una línea por documento: con el texto sin ajustar no hay nada
            // que cortar, y cuatro mil filas de una línea se recorren.
            $hoja->fila($f++, $celdas, 't' . $sufijo, 19);
        }

        $hoja->congelar($filaCabecera, 4);
        $hoja->repetirCabecera($filaCabecera);

        if ($f - 1 >= $filaCabecera) {
            $hoja->filtrar('A' . $filaCabecera . ':' . LibroExcel::columna($n) . ($f - 1));
        }
    }

    /**
     * El valor y el estilo de una celda de la rejilla.
     *
     * @param array<string,mixed>                                      $d
     * @param array{clave:string,rotulo:string,ancho:float,tipo:string} $c
     * @return array{v:mixed,e:string}
     */
    private static function celdaDeColumna(array $d, array $c, string $sufijo): array
    {
        $clave = $c['clave'];

        /* Las tres columnas que se calculan aquí y no están en el documento. */
        if ($clave === 'estado') {
            return ['v' => $d['anulada'] ? 'ANULADA' : 'Vigente', 'e' => 't' . $sufijo];
        }

        if ($clave === 'clase') {
            return ['v' => $d['clase'], 'e' => match ((string) $d['clase']) {
                Auditoria::REVISAR   => 'res-revisar',
                Auditoria::REDONDEO  => 'res-redondeo',
                Auditoria::NO_APLICA => $sufijo === '-gris' ? 'res-noaplica-gris' : 'res-noaplica',
                default              => $sufijo === '-gris' ? 'res-cuadra-gris' : 'res-cuadra',
            }];
        }

        if ($clave === 'dif_pago') {
            // En rojo y en negrita sólo cuando es dinero de verdad; si no, la
            // columna entera grita y deja de señalar nada.
            return ['v' => (float) $d['dif_pago'], 'e' => (string) $d['clase'] === Auditoria::REVISAR
                ? 'b-falta'
                : 'b' . $sufijo];
        }

        $valor = $d[$clave] ?? null;

        return match ($c['tipo']) {
            'd' => ['v' => $valor === null ? null : LibroExcel::serieFecha((string) $valor),
                    'e' => 'd' . $sufijo],
            'n' => ['v' => $valor === null ? null : (int) $valor, 'e' => 'n' . $sufijo],
            // `null` y no cero: en un abono o un ajuste el contraste del
            // detalle NO APLICA, y un cero ahí diría «cuadra», que es mentira.
            'b' => ['v' => $valor === null ? null : (float) $valor, 'e' => 'b' . $sufijo],
            'p' => ['v' => $valor === null ? null : (float) $valor, 'e' => 'p' . $sufijo],
            default => ['v' => $valor, 'e' => in_array($clave, ['desglose', 'diagnostico'], true)
                ? 'obs1' . $sufijo
                : 't' . $sufijo],
        };
    }

    /* =====================================================================
     *  4. Formas de pago
     * ===================================================================== */

    private static function hojaFormas(LibroExcel $libro, array $informe): void
    {
        $hoja = $libro->hoja('Formas de pago');
        $hoja->anchos([10, 34, 22, 16, 12, 12, 18, 14]);
        $hoja->color('38BDF8');
        $hoja->impresion(['orientacion' => 'portrait', 'ajustar' => true,
            'pie' => self::pieImpreso($informe)]);

        $totalBs = 0.0;

        foreach ($informe['formas'] as $forma) {
            $totalBs += (float) $forma['bs'];
        }

        $f = self::encabezar($hoja, $informe, 'En qué se cobró el período',
            sprintf('%d forma(s) de pago en uso  ·  %s Bs',
                count($informe['formas']), number_format($totalBs, 2, ',', '.')),
            8);

        $hoja->combinar('A' . $f . ':H' . $f);
        $hoja->fila($f++, [
            'La descripción y el tipo salen de `IDTA116`, el catálogo del AS400. Se lee '
            . 'AGRUPADO por forma a propósito: el catálogo tiene varias filas por forma '
            . '—una por marca y divisa— y unirlo sin agrupar duplicaría cada línea de pago '
            . 'e inflaría los bolívares sin que nada avisara. Las filas en ámbar son '
            . 'formas que se usan y que el catálogo no tiene dadas de alta.',
        ], 'nota', 44);

        $f++;

        $filaCabecera = $f;
        $hoja->fila($f++, ['Código', 'Descripción (IDTA116)', 'Tipo', '¿Financiamiento?',
            'Líneas', 'Documentos', 'Bolívares', '% del total'], 'cabecera', 34);

        $banda = 0;

        foreach ($informe['formas'] as $forma) {
            $sufijo = (!$forma['en_catalogo']) ? '-ambar' : (($banda % 2 === 1) ? '-gris' : '');
            $banda++;

            $hoja->fila($f++, [
                ['v' => $forma['forma_pago'],  'e' => 't' . $sufijo],
                ['v' => $forma['descripcion'], 'e' => 't' . $sufijo],
                ['v' => $forma['tipo'],        'e' => 't' . $sufijo],
                ['v' => $forma['es_financiamiento'] ? 'Sí' : 'No', 'e' => 't' . $sufijo],
                ['v' => (int) $forma['lineas'], 'e' => 'n' . $sufijo],
                ['v' => (int) $forma['docs'],   'e' => 'n' . $sufijo],
                ['v' => (float) $forma['bs'],   'e' => 'b' . $sufijo],
                ['v' => $totalBs != 0.0 ? round((float) $forma['bs'] / $totalBs * 100, 1) : null,
                 'e' => 'p' . $sufijo],
            ], 't' . $sufijo, 22);
        }

        /*
         * La última fila de datos, antes del total.
         *
         * El autofiltro llega hasta AQUÍ y no hasta el total: un autofiltro que
         * incluye la fila de totales la esconde en cuanto alguien filtra por
         * una forma de pago, y entonces la suma que se ve no es la de lo
         * filtrado ni la de todo. No cuadra con nada.
         */
        $ultimaDeDatos = $f - 1;

        $hoja->fila($f++, [
            ['v' => null,     'e' => 'total-rotulo'],
            ['v' => 'TOTAL',  'e' => 'total-rotulo'],
            ['v' => null,     'e' => 'total-rotulo'],
            ['v' => null,     'e' => 'total-rotulo'],
            ['v' => null,     'e' => 'total-rotulo'],
            ['v' => null,     'e' => 'total-rotulo'],
            ['v' => round($totalBs, 2), 'e' => 'total'],
            ['v' => null,     'e' => 'total-rotulo'],
        ], 'total-rotulo', 26);

        $f++;

        $hoja->combinar('A' . $f . ':H' . $f);
        $hoja->fila($f, [sprintf(
            'Este total (%s Bs) es el mismo «Total registrado en formas de pago» del '
            . 'resumen, y sale de las mismas líneas: si no coincidiera, una de las dos '
            . 'pestañas estaría contando mal.',
            number_format($totalBs, 2, ',', '.')
        )], 'nota', 30);

        $hoja->congelar($filaCabecera);
        $hoja->repetirCabecera($filaCabecera);

        // Un rango de autofiltro al revés —cabecera en la 11 y fin en la 10—
        // basta para que Excel declare el libro dañado, y eso pasa con un
        // período sin ni una línea de pago. No es tan raro: un día de cierre.
        if ($ultimaDeDatos >= $filaCabecera) {
            $hoja->filtrar('A' . $filaCabecera . ':H' . $ultimaDeDatos);
        }
    }

    /* =====================================================================
     *  5. Método
     * ===================================================================== */

    private static function hojaMetodo(LibroExcel $libro, array $informe): void
    {
        $hoja = $libro->hoja('Método');
        $hoja->anchos([2.5, 108, 2.5]);
        $hoja->color(self::GRISTXT);
        $hoja->impresion(['orientacion' => 'portrait', 'ajustar' => true,
            'pie' => self::pieImpreso($informe)]);

        $f = self::encabezar($hoja, $informe, 'Cómo se calculó esto',
            'Para que el informe se pueda discutir, y no sólo creer', 3);

        /**
         * Los bloques del método.
         *
         * Están aquí como texto y no generados de nada porque son el argumento
         * del informe, no un dato suyo: cada cifra que aparece se midió una vez
         * y se escribió. El día que se vuelva a medir, se cambia aquí.
         *
         * @var list<array{0:string,1:list<string>}>
         */
        $bloques = [
            ['De dónde salen los números', [
                'Los tres archivos del AS400 se leen EN VIVO, en el momento en que se pide '
                . 'el informe. No hay copia intermedia ni carga nocturna, así que lo que se '
                . 've es lo que el servidor tiene en ese instante.',
                '    IDP210     el ENCABEZADO: cuánto se vendió',
                '    RTP325     el DETALLE:    qué se vendió',
                '    IDP116N    los PAGOS:     con qué se pagó',
                '    IDTA116    el catálogo de formas de pago',
                '    ETP045     el maestro de tiendas (el nombre sale de ENBTDA)',
                'Los tres primeros tienen que contar lo mismo. Si la suma de las formas de '
                . 'pago no llega al total de la factura, falta un pago por asentar: dinero '
                . 'cobrado que no está registrado, o un financiamiento que nadie anotó.',
            ]],
            ['El total de la factura no se supuso: se midió', [
                'IDP210 trae seis importes y ninguno se llama «total». Se probaron las diez '
                . 'combinaciones razonables contra la suma de pagos de los 3.626 documentos '
                . 'de noviembre de 2026:',
                '    monto bruto                                 124 de 3.626     3,4 %',
                '    bruto − descuento                           186 de 3.626     5,1 %',
                '    bruto − descuento + IVA                   3.551 de 3.626    97,9 %',
                '    bruto − descuento + IVA + IGTF            3.571 de 3.626    98,5 %  <-',
                '    venta Bs + IVA + IGTF                     3.476 de 3.626    95,9 %',
                'La fórmula que usa este informe es la cuarta:',
                '    TOTAL = NMODC1 − NMODC2 + NMODC6 + NMOOCG',
                '          =  bruto  − dscto. +  IVA   +  IGTF',
                'Y el IGTF no es opcional: añadirlo arregla 20 documentos y NO rompe ni uno. '
                . 'Eso es lo que lo convierte en parte de la fórmula y no en una corrección '
                . 'a ojo. Corriendo contra producción el 19/11/2026 acertó en el 98,7 % de '
                . '4.004 documentos reales.',
            ]],
            ['Los dos importes que la fórmula deja fuera', [
                'NMODC7 (descuento SENIAT) y NMOABO (monto abono) no entran. El primero vale '
                . 'cero en todo el período medido, así que sumarlo o no da el mismo '
                . 'resultado y meterlo sería adivinar su signo con cero evidencia. El '
                . 'segundo no vale cero, pero en las notas de crédito de clase 3 repite el '
                . 'propio bruto —medido, 31 de 31— y sumarlo contaría el movimiento dos '
                . 'veces.',
                'Los dos están VIGILADOS: si en el período aparece un SENIAT distinto de '
                . 'cero, o un abono que no se explique así, el informe lo dice en la sección '
                . 'de avisos del Resumen en lugar de callárselo. La fórmula habría que '
                . 'revisarla, y nadie se enteraría.',
            ]],
            ['Las tres clases, y por qué el corte está en 5 Bs', [
                'Las diferencias no se reparten por una pendiente: forman dos grupos '
                . 'separados por un abismo.',
                '    47 documentos entre 0,02 y 4,38 Bs      (45 de ellos con IGTF)',
                '     8 documentos entre 2.000,00 y 168.136,17 Bs',
                'Entre 4,38 y 2.000,00 no hay NADA. Por eso el corte en 5 Bs no es un número '
                . 'elegido para que salgan pocos avisos: cae dentro de un hueco de tres '
                . 'órdenes de magnitud, y moverlo a 10, a 100 o a 1.000 clasificaría '
                . 'exactamente igual.',
                '    CUADRA      diferencia ≤ 0,01 Bs   igual al céntimo',
                '    REDONDEO    ≤ 5,00 Bs              redondeo del IGTF, no es dinero',
                '    REVISAR     > 5,00 Bs              hay que ir a ver la factura',
                '    NO APLICA                          no hay nada que contrastar',
                'El grupo pequeño tiene causa conocida: el IGTF es el 3 % y el AS400 lo '
                . 'calcula sobre el total del documento, mientras que las líneas de pago lo '
                . 'guardan redondeado por línea. Son céntimos de redondeo, no dinero '
                . 'perdido.',
            ]],
            ['Lo que NO se marca, aunque lo parezca', [
                '1. Las ANULADAS (NSTEVT = 9) llevan cero piezas y cero venta en el '
                . 'encabezado pero conservan sus líneas de detalle. Es el comportamiento '
                . 'correcto del AS400, no un descuadre, y de hecho cuadran en pagos: en '
                . 'noviembre de 2026, las 110 que hubo cuadraron. Marcarlas haría el informe '
                . 'falso en más de cien filas.',
                '2. Las notas de crédito de CLASE 3 (NTPDNC = 3, «ABON») no mueven '
                . 'mercancía: mueven dinero. Es un abono que el cliente entrega a cuenta de '
                . 'un apartado, y sus líneas de detalle son la mercancía de la factura '
                . 'original, que no tiene por qué sumar el importe abonado. Para esta clase '
                . 'el contraste del detalle NO APLICA, y decir que «descuadra» sería un '
                . 'error del informe y no del dato. Medido: 31 de 31 cuadran en pagos, 0 de '
                . '31 en detalle.',
                '3. Las notas de crédito de CLASE 2 (NTPDNC = 2, «AJUS») son un ajuste que '
                . 'se descuenta de la factura que corrigen. Medido sobre tres años: las 55 '
                . 'que hay apuntan SIEMPRE a su factura y no tienen NUNCA ni detalle ni '
                . 'forma de pago, ni una. No mueven mercancía propia ni dinero propio, así '
                . 'que no hay nada que contrastar: se marcan NO APLICA. Marcarlas CUADRA o '
                . 'REVISAR mentiría en direcciones distintas.',
            ]],
            ['Dónde está el límite de lo que esto sabe', [
                'La columna «Observación» describe el PATRÓN que se ve en el archivo, no la '
                . 'causa. «Se registró el 80 % y la forma es CASHEA» es un hecho; «el cajero '
                . 'no asentó la inicial» sería una acusación sin pruebas. Quien revise la '
                . 'factura en la tienda tiene el papel delante y puede decidir; este informe '
                . 'le dice dónde mirar.',
                'La forma de pago «OT» son OTROS PAGOS y no tiene nada que ver con '
                . 'financiamiento; lo confirmó Carlos Flores. Está pendiente de darla de '
                . 'alta en IDTA116, y mientras tanto el informe la nombra por lo que es en '
                . 'lugar de dejarla sin clasificar.',
                'Las tolerancias de esta corrida: ' . number_format(
                    (float) $informe['tolerancias']['exacta'], 2, ',', '.')
                . ' Bs para «cuadra» y ' . number_format(
                    (float) $informe['tolerancias']['redondeo'], 2, ',', '.')
                . ' Bs para «redondeo».',
            ]],
        ];

        foreach ($bloques as [$titulo, $parrafos]) {
            $f = self::seccionAncha($hoja, $f, $titulo);

            foreach ($parrafos as $parrafo) {
                $mono = str_starts_with($parrafo, '    ');

                $hoja->filaDesde($f++, 2, [$mono ? substr($parrafo, 2) : $parrafo],
                    $mono ? 'mono' : 'parrafo',
                    $mono ? 14 : (float) max(16, 12.5 * ceil(mb_strlen($parrafo) / 104)));
            }

            $hoja->fila($f++, [null, null, null], 'papel', 10);
        }
    }

    /** Un título de sección en la hoja del método, que sólo tiene una columna. */
    private static function seccionAncha(HojaExcel $hoja, int $fila, string $texto): int
    {
        $hoja->filaDesde($fila, 2, [$texto], 'seccion', 24);

        return $fila + 1;
    }
}
