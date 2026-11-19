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
        'descripcion' => 'Datos complementarios de la tela en el pedido de corte.',
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
     * Vacío hasta que los manuales existan. En cuanto se generen a
     * `vistas/manuales/`, se ponen las rutas aquí y los botones aparecen
     * solos; mientras tanto la columna no se pinta, que es mejor que un
     * enlace que da 404.
     *
     * Van a `vistas/manuales/` y no a `docs/`, porque `docs/` tiene un
     * .htaccess que deniega el acceso por web y el enlace daría un 403.
     */
    'manuales' => [
        'texto'   => '',
        'usuario' => '',
        'tecnico' => '',
    ],
];
