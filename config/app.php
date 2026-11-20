<?php

declare(strict_types=1);

/**
 * Identidad de la aplicación.
 *
 * `vistas/plantilla.php` no nombra a esta aplicación en ningún sitio. Todo lo
 * que cambia de un programa al siguiente —el nombre, el subtítulo, qué
 * módulos se pintan, qué hojas de estilo y qué scripts se cargan— está aquí.
 * Así la plantilla se copia tal cual al proyecto siguiente y lo único que hay
 * que tocar es este archivo.
 *
 * Los datos de la empresa, del soporte y del desarrollador NO se repiten
 * aquí: salen de `config/pie.php`, que ya los tiene, y de allí los toma
 * también la cabecera. Dos sitios con el mismo teléfono es un sitio que se
 * queda viejo.
 */

return [
    /*
     * El nombre va en la pestaña, en la cabecera y en la página de acceso
     * denegado. Corto: la cabecera lo pinta en una línea y en un móvil hay
     * poco sitio.
     */
    'nombre'    => 'Auditoría de Formas de Pago',
    'subtitulo' => 'Encabezado, detalle y pagos de cada factura, leídos del AS400 en vivo',

    /*
     * Para el `<meta name="description">`. No se publica —es una herramienta
     * interna— pero es lo que se ve al compartir el enlace por el chat de la
     * casa.
     */
    'descripcion' => 'Contrasta documento a documento el encabezado de factura (IDP210), '
        . 'su detalle (RTP325) y sus formas de pago (IDP116N) para encontrar los cobros '
        . 'que no están asentados. Se consulta el AS400 en vivo y se descarga en Excel.',

    /* Color de la barra del navegador en móvil: el azul de la cabecera. */
    'tema' => '#0f172a',

    /*
     * Orden de carga de las hojas de estilo. Manda el sistema de diseño y va
     * primero; lo que venga después sólo añade. Las rutas van sin barra
     * inicial porque la aplicación cuelga de una subcarpeta.
     *
     *   tokens.css   los colores, tipografías y medidas de la casa
     *   estilos.css  los componentes comunes: panel, botón, KPI, cabecera, pie
     *   tablas.css   las tablas de datos
     *   auditoria.css lo propio de esta pantalla, y sólo eso
     */
    'css' => [
        'vistas/css/tokens.css',
        'vistas/css/estilos.css',
        'vistas/css/tablas.css',
        'vistas/css/style-loader.css',
        'vistas/css/auditoria.css',
        'vistas/css/acerca.css',
        'vistas/css/asistente.css',
    ],

    /*
     * Los scripts, en orden. `loader.js` y `tema.js` van antes que el de la
     * aplicación porque ésta los llama en cuanto pinta algo.
     */
    'js' => [
        'vistas/js/loader.js',
        'vistas/js/tema.js',
        'vistas/js/auditoria.js',
        'vistas/js/acerca.js',
        'vistas/js/asistente.js',
    ],

    /*
     * Font Awesome sólo cuando algo lo use de verdad. Toda la interfaz tira
     * de los SVG en línea de `vistas/iconos.php`, que no añaden una petición
     * más a una pantalla que ya espera por el AS400.
     */
    'font_awesome' => false,

    /*
     * Los módulos de `vistas/modulos/`, sin carpeta ni extensión, en el orden
     * en que se pintan dentro del `<main>`.
     *
     * Son dos y el orden es el del uso: primero se dice qué período, y debajo
     * aparece el informe. No hay un tercer paso, y ésa es la idea — la
     * pantalla entera existe para que se MIRE el resultado antes de
     * descargarlo.
     */
    'modulos' => [
        'periodo',
        'resultado',
    ],

    /*
     * Lo que va DESPUÉS del `<main>`: ventanas y paneles que se superponen a
     * la página. El pie no se declara aquí, va siempre.
     *
     * `acerca` tiene que estar AQUÍ y no en `modulos`: cubre la pantalla
     * entera con `position: fixed`, y dentro del `<main>` heredaría sus
     * márgenes y su recorte, dejando el fondo oscuro corto por los lados.
     * Además es esta línea la que hace aparecer el botón «Acerca de» del pie
     * —`vistas/modulos/pie.php` sólo lo pinta si la capa está declarada—, así
     * que quitarla de aquí quita el botón y la ventana a la vez, sin dejar un
     * botón que no abre nada.
     *
     * La ficha de un documento es un `<dialog>` y vive dentro del módulo
     * `resultado`, no aquí: es parte de esa pantalla y no una capa de la
     * aplicación.
     *
     * El `asistente` está aquí por lo mismo: es un botón fijo pegado a la
     * esquina inferior derecha y dentro del `<main>` heredaría sus márgenes.
     * Va DESPUÉS de `acerca` porque la ventana «Acerca de» tiene que quedar
     * por encima de él —cubre la pantalla entera— y porque el asistente no
     * estorba a nada que se pinte antes.
     */
    'capas' => [
        'acerca',
        'asistente',
    ],
];
