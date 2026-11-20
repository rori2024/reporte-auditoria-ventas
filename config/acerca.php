<?php

declare(strict_types=1);

/**
 * Los datos de la ventana «Acerca de» (DESIGN-SYSTEM.md §11).
 *
 * El diseño de esa ventana es el mismo en todos los sistemas de la casa; lo
 * único que cambia por proyecto son estos datos, y por eso viven aquí.
 *
 * NO SE REPITE NADA DE `config/pie.php`. La empresa, el soporte, el
 * desarrollador y la versión salen de allí: dos copias del teléfono de
 * soporte acaban siendo dos teléfonos distintos el día que cambia la
 * extensión, y el que se queda viejo es siempre el que nadie recuerda que
 * existe.
 *
 * Lo que esté vacío NO se pinta —misma regla que el pie—, así que una
 * sección que todavía no se sabe se deja en blanco y desaparece de la
 * ventana, en vez de salir con un hueco o con algo inventado.
 */

return [
    /*
     * El «Build» del chip de la derecha. Es el mes del último cambio
     * entregado, a mano y a propósito: sacarlo de la fecha del archivo haría
     * que cambiara solo al copiar la carpeta, y sacarlo de git obligaría a
     * que la aplicación supiera de git, que no sabe ni tiene por qué.
     */
    'build' => 'Noviembre 2026',

    /*
     * El icono del círculo de identidad, del catálogo de `vistas/iconos.php`.
     *
     * Tiene que ser EL MISMO SÍMBOLO que el de la pestaña del navegador
     * (`vistas/img/icono.svg`): si en la pestaña hay una cosa y en esta
     * ventana otra, parecen dos sistemas. Aquí la balanza, que es además la
     * del botón «Auditar» y la del panel «El veredicto».
     */
    'icono' => 'balanza',

    /* El panel destacado: para qué existe esto, en una frase. */
    'destacado' => 'Contesta una pregunta que antes no contestaba nadie: '
        . '¿cuadra cada factura con lo que se cobró por ella? A mano son casi '
        . 'cuatro mil documentos al mes contra cinco mil líneas de pago; aquí '
        . 'son veinte segundos y una lista de lo que hay que ir a mirar.',

    /*
     * CÓMO SE TRABAJA
     * ---------------
     * Esta sección no está en la §11, y se añade a propósito. Es una
     * herramienta interna: quien la abre trabaja en la empresa y la pregunta
     * que trae no es «qué versión es» sino «¿de dónde salió este número y me
     * puedo fiar?». Esto contesta eso.
     *
     * Las seis son comprobables en el repositorio, no intenciones: la fórmula
     * medida y las tolerancias con su justificación (`servicios/Auditoria.php`),
     * el autodiagnóstico sin servidor (`cli/probar-excel.php`), la lectura de
     * sólo lectura al AS400 (`modelos/auditoria.modelo.php`), la caché que
     * ata el Excel a lo que se vio (`servicios/CacheAuditoria.php`) y la
     * pestaña «Método» del propio informe.
     */
    'trabajo' => [
        [
            'icono'  => 'servidor',
            'titulo' => 'Se lee el AS400 en vivo, y sólo se lee',
            'texto'  => 'No hay copia intermedia ni carga nocturna: lo que se '
                . 've es lo que el servidor tiene en ese instante. Y la '
                . 'aplicación no escribe nada en él — una auditoría que puede '
                . 'tocar lo que audita no es una auditoría.',
        ],
        [
            'icono'  => 'llaves',
            'titulo' => 'Nada se da por sabido: se mide',
            'texto'  => 'La fórmula del total se eligió probando las diez '
                . 'combinaciones posibles contra los pagos reales, y el corte '
                . 'entre «céntimos de redondeo» y «dinero que falta» cae en un '
                . 'hueco medido de tres órdenes de magnitud. Cada regla lleva '
                . 'escrita al lado la cifra que la justifica.',
        ],
        [
            'icono'  => 'herramienta',
            'titulo' => 'El cálculo se comprueba sin el servidor',
            /*
             * Sin número a propósito. Aquí decía «62 comprobaciones», y esa
             * cifra sube con cada caso nuevo: una pantalla que presume de
             * rigor y publica un dato viejo se desmiente a sí misma. El
             * recuento del día lo da `php cli/probar-excel.php`, que es donde
             * no puede quedarse viejo.
             */
            'texto'  => 'Al AS400 no se llega con la VPN puesta, así que las '
                . 'reglas se prueban con casos fabricados que cubren los '
                . 'difíciles —el anulado, el abono, el ajuste, el que falta '
                . 'dinero— y cada uno declara de antemano qué veredicto tiene '
                . 'que salir.',
        ],
        [
            'icono'  => 'info',
            'titulo' => 'El informe dice lo que NO sabe',
            'texto'  => 'Cada corrida trae sus avisos: los supuestos que '
                . 'podrían haber dejado de ser verdad, las formas de pago que '
                . 'el catálogo no tiene dadas de alta y los documentos que no '
                . 'se pueden contrastar. Un informe que se calla eso convence '
                . 'más y vale menos.',
        ],
        [
            'icono'  => 'balanza',
            'titulo' => 'Se describe el patrón, no se acusa a nadie',
            'texto'  => '«Se registró el 80 % y la forma es CASHEA» es un '
                . 'hecho; «el cajero no asentó la inicial» sería una acusación '
                . 'sin pruebas. Quien revise la factura en la tienda tiene el '
                . 'papel delante y decide: esto le dice dónde mirar.',
        ],
        [
            'icono'  => 'hoja-calculo',
            'titulo' => 'Se descarga lo que se vio',
            'texto'  => 'El Excel sale de la misma corrida que está en '
                . 'pantalla, no de una consulta nueva. Entre mirar y descargar '
                . 'las tiendas siguen facturando, y dos informes del mismo '
                . 'período con cifras distintas no los sabría explicar nadie.',
        ],
    ],

    /*
     * Las píldoras de tecnologías. Sólo lo que la aplicación usa de verdad.
     * No hay framework de JavaScript, ni Composer, ni librería de Excel: son
     * decisiones, no carencias — la intranet no siempre alcanza un CDN, y un
     * gestor de dependencias cambiaría la forma de desplegar de toda la casa.
     */
    'tecnologias' => [
        ['icono' => 'codigo',       'nombre' => 'PHP 8.2 · sin Composer'],
        ['icono' => 'servidor',     'nombre' => 'AS400 · DB2 for i por ODBC'],
        ['icono' => 'navegador',    'nombre' => 'JavaScript sin framework'],
        ['icono' => 'hoja-calculo', 'nombre' => 'Excel escrito sin Excel'],
        ['icono' => 'herramienta',  'nombre' => 'Apache (XAMPP)'],
    ],

    /*
     * Colaboradores: vacío todavía, y por eso la sección no se pinta.
     *
     * Aquí van las personas que aportan al sistema sin escribir código —quien
     * revisa en la tienda las facturas que el informe marca, quien confirma
     * qué significa una forma de pago que el catálogo no tiene—. Para
     * añadirlas: ['nombre' => '…', 'cargo' => '…'].
     */
    'colaboradores' => [],

    /* La línea de agradecimiento del pie de la ventana. */
    'gracias' => 'Gracias a quien va a la tienda a buscar la factura que este '
        . 'informe señala: sin esa comprobación, esto sólo sería una lista.',
];
