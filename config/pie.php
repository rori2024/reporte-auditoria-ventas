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

return [
    /*
     * Versión de la aplicación. Vive aquí y no en una vista porque la
     * muestran dos páginas distintas —la aplicación y la de acceso
     * denegado— y una constante definida en una de ellas no existe en la
     * otra.
     */
    'version' => '0.1.0 ( en desarrollo )',

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
