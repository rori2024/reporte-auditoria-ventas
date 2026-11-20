<?php

declare(strict_types=1);

/**
 * Datos del pie corporativo (DESIGN-SYSTEM.md §10).
 *
 * El pie es igual en todos los sistemas de la casa; lo único que cambia son
 * estos datos, y por eso viven aquí y no dentro de la vista.
 *
 * Lo que esté vacío NO se pinta: la vista omite el dato, y si una columna
 * entera queda sin contenido, omite la columna. Así un campo que todavía no
 * se sabe se queda en blanco en vez de salir inventado en la pantalla.
 */

require_once __DIR__ . '/env.php';

/* ===========================================================================
 *  LA VERSIÓN Y EL ENTORNO, QUE SON DOS COSAS Y SE CONFUNDÍAN
 * ---------------------------------------------------------------------------
 *  Aquí ponía, escrito a mano, `'0.1.0 ( en desarrollo )'`. Y ahí estaba el
 *  problema: el `.env` llevaba días en producción —`INTRANET_VALIDAR=si`,
 *  `AS400_LIBRERIAS=produccion`— y el pie seguía anunciando que esto era un
 *  desarrollo, porque ese texto no lo lee de ningún sitio: lo escribe una
 *  persona y se queda viejo el día que se despliega.
 *
 *  Un rótulo de entorno que no se saca del entorno siempre acaba mintiendo, y
 *  miente en la dirección peor: el día que de verdad se esté en pruebas, nadie
 *  se lo creerá porque lleva meses diciendo lo mismo.
 *
 *  Así que son dos cosas separadas y ninguna se teclea aquí:
 *
 *   · LA VERSIÓN es un número de entrega y vive en el archivo `VERSION` de la
 *     raíz, una línea. Lo lee esto y lo lee también el generador de los
 *     manuales en PDF, así que no hay dos sitios que puedan discrepar.
 *
 *   · EL ENTORNO se deduce del `.env`, que es quien lo sabe. Y se nombra el
 *     interruptor concreto que está apagado, no un «desarrollo» genérico: si
 *     alguien ve «bibliotecas de pruebas» sabe exactamente qué mirar.
 *
 *  ESTO SE COPIA TAL CUAL AL PROYECTO SIGUIENTE. Un programa que no hable con
 *  el AS400 no declara `AS400_LIBRERIAS` en su `.env`, y entonces ese aviso no
 *  aparece: lo que no se declara no se comprueba, en lugar de dar por supuesto
 *  que falta.
 * ======================================================================== */

/** El número de entrega, del archivo `VERSION` de la raíz. */
$pie_version = trim((string) @file_get_contents(dirname(__DIR__) . '/VERSION'));

if ($pie_version === '') {
    // Sin archivo no se inventa un número: se dice que falta, que es lo que
    // hace que alguien lo cree. Un «0.0.0» silencioso no lo arregla nadie.
    $pie_version = '(sin archivo VERSION)';
}

/** Lo que está en pruebas, con el nombre del interruptor que lo pone así. */
$pie_pruebas = [];

if (!env_bool('INTRANET_VALIDAR', false)) {
    $pie_pruebas[] = 'sin validar accesos';
}

$pie_librerias = strtolower(trim((string) env('AS400_LIBRERIAS', '')));

if ($pie_librerias !== '' && $pie_librerias !== 'produccion') {
    $pie_pruebas[] = 'bibliotecas de pruebas';
}

return [
    /*
     * Versión de la aplicación. La muestran dos páginas distintas —la
     * aplicación y la de acceso denegado—, así que vive aquí y no en una
     * vista: una constante definida en una de ellas no existe en la otra.
     */
    'version' => $pie_version
        . ($pie_pruebas === [] ? '' : ' ( ' . implode(' · ', $pie_pruebas) . ' )'),

    'empresa' => [
        'nombre'      => 'Industrias RRC, C.A.',
        'logo'        => 'vistas/img/industrias-rrc.png',
        'descripcion' => 'Auditoría de formas de pago: contrasta el encabezado de factura, su
            detalle y sus pagos contra el AS400, en vivo.',
        'direccion'   => 'Av. Ppal. de Los Cortijos',
        'web'         => 'https://www.rori.com',
    ],

    'soporte' => [
        'email'    => 'soporte@rori.com',
        'telefono' => 'Ext. 2309 / +58 412-333-0319',
        'horario'  => 'Lun a Vie, 7:30 - 16:00',
    ],

    'desarrollador' => [
        'nombre'   => 'Carlos Flores',
        'cargo'    => 'Desarrollador Web Full Stack',
        'foto'     => 'vistas/img/devcflores.png',
        'email'    => 'cflores@rori.com',
        'telefono' => 'Ext. 2309 / +58 412-333-0319',
        'github'   => '',
    ],

    /*
     * Los manuales, ya generados. Las rutas se ponen aquí y los botones
     * aparecen solos; lo que se deje vacío no se pinta, que es mejor que un
     * enlace que da 404.
     *
     * Van a `vistas/manuales/` y no a `docs/`, porque `docs/` tiene un
     * .htaccess que deniega el acceso por web y el enlace daría un 403. La
     * FUENTE sigue siendo el Markdown de `docs/`: los PDF se regeneran desde
     * allí con `docs/_herramientas/generar-manuales.mjs` y no se editan a
     * mano.
     *
     * La guía de instalación (`vistas/manuales/INSTALACION.pdf`) también se
     * genera, pero no se enlaza aquí: el pie sólo tiene sitio para los dos
     * manuales y esa guía es para quien monta el servidor, no para quien usa
     * la pantalla.
     */
    'manuales' => [
        'texto'   => 'Cómo se usa esta auditoría y cómo está hecha por dentro. Se abren en
            una pestaña nueva.',
        'usuario' => 'vistas/manuales/MANUAL-USUARIO.pdf',
        'tecnico' => 'vistas/manuales/MANUAL-TECNICO.pdf',
    ],
];
