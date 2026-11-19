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
    'nombre'    => 'Datos Complementarios de Tela',
    'subtitulo' => 'Tela, encogimiento y sastrería del pedido de corte',

    /*
     * Para el `<meta name="description">`. No se publica —es una herramienta
     * interna— pero es lo que se ve al compartir el enlace por el chat de la
     * casa.
     */
    'descripcion' => 'Completa los datos de tela de las líneas del pedido de corte: '
        . 'código de tela, código de corte, porcentaje de encogimiento y sastrería.',

    /* Color de la barra del navegador en móvil: el azul de la cabecera. */
    'tema' => '#0f172a',

    /*
     * Orden de carga de las hojas de estilo. `estilos.css` manda y va primero;
     * lo que venga después sólo añade. Las rutas van sin barra inicial porque
     * la aplicación cuelga de una subcarpeta.
     */
    'css' => [
        'vistas/css/estilos.css',
        'vistas/css/style-loader.css',
    ],

    /*
     * Los scripts, en orden. `loader.js` va antes que el de la aplicación
     * porque ésta lo llama en cuanto pinta algo.
     */
    'js' => [
        'vistas/js/loader.js',
        'vistas/js/tela.js',
    ],

    /*
     * Font Awesome sólo cuando algo lo use de verdad. El resto de la
     * interfaz tira de los SVG en línea de `vistas/iconos.php`, que no
     * añaden una petición más a una pantalla que ya espera por el AS400.
     */
    'font_awesome' => false,

    /*
     * Los módulos de `vistas/modulos/`, sin carpeta ni extensión, en el orden
     * en que se pintan dentro del `<main>`.
     */
    'modulos' => [
        'busqueda',
        'listado',
        'editor',
    ],

    /*
     * Lo que va DESPUÉS del `<main>`: ventanas y paneles que se superponen a
     * la página. El pie no se declara aquí, va siempre.
     */
    'capas' => [],
];
