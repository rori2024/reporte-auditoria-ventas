<?php

declare(strict_types=1);

/**
 * El asistente flotante — «Carlos Flores Bot».
 *
 * Es el mismo asistente de los demás sistemas de la casa: el diseño no
 * cambia, sólo cambia lo que sabe. Lo que sabe está en
 * `vistas/js/asistente.js`; aquí va el armazón, que es siempre éste.
 *
 * VA EN `capas`, NO EN `modulos`
 * -----------------------------
 * Tiene `position: fixed` y vive pegado a la esquina inferior derecha. Dentro
 * del `<main>` heredaría sus márgenes y su recorte, igual que la ventana
 * «Acerca de». Por eso se pinta después del pie.
 *
 * Y por eso tampoco está en ninguna lista blanca de `?m=`: a esto no se llega
 * por URL.
 *
 * NO SE PINTA EN `errorAcceso.php`
 * --------------------------------
 * Esa página se pinta cuando no hay sesión que pintar, y sólo incluye el pie.
 * Un asistente que explica una pantalla a la que no se ha entrado no tiene
 * nada que explicar.
 *
 * LOS DATOS SALEN DE DONDE YA ESTABAN
 * -----------------------------------
 * El nombre y la foto del desarrollador, de `config/pie.php`; el nombre de la
 * aplicación, de `config/app.php`; quién tiene la sesión abierta y qué puede,
 * de `SesionIntranet`. Ni un dato repetido: el día que cambie la extensión de
 * soporte o la foto, esto sigue correcto sin tocarlo.
 *
 * LOS ICONOS, EN `<template>`
 * ---------------------------
 * Los chips de la conversación los crea el JavaScript, y sus iconos tienen
 * que salir de `vistas/iconos.php`, que es la única lista de iconos de la
 * aplicación —`config/app.php` deja Font Awesome apagado a propósito—. Así
 * que los SVG se pintan aquí, una vez, dentro de `<template>`, y el
 * JavaScript los clona por nombre. Mismo recurso que usa `vistas/plantilla.php`
 * con los dos iconos del interruptor de tema: el catálogo sigue en un sitio y
 * ningún trazado SVG acaba escrito dentro de un `.js`.
 */

require_once __DIR__ . '/../iconos.php';
require_once __DIR__ . '/../../servicios/SesionIntranet.php';

/** @var array<string,mixed> $asApp */
$asApp = require __DIR__ . '/../../config/app.php';
/** @var array<string,mixed> $asPie */
$asPie = require __DIR__ . '/../../config/pie.php';

$asE = static fn (?string $v): string => htmlspecialchars((string) $v, ENT_QUOTES, 'UTF-8');

$asDev     = (array) ($asPie['desarrollador'] ?? []);
$asSesion  = SesionIntranet::actual();
$asNombre  = trim((string) ($asDev['nombre'] ?? '')) !== ''
    ? trim((string) $asDev['nombre']) . ' Bot'
    : 'Asistente';
$asSistema = (string) ($asApp['nombre'] ?? '');

/*
 * La foto sólo si el archivo está de verdad, igual que en la ventana «Acerca
 * de». Un `<img>` roto en el botón que invita a pedir ayuda es la peor
 * primera impresión posible. Sin foto van las iniciales, que es lo que hace
 * la cabecera con los perfiles de la intranet que apuntan a un archivo que ya
 * no existe.
 */
$asFoto    = (string) ($asDev['foto'] ?? '');
$asHayFoto = $asFoto !== '' && is_file(__DIR__ . '/../../' . $asFoto);

/** Las dos primeras iniciales del nombre. Mismo criterio que la cabecera. */
$asPartes    = preg_split('/\s+/u', (string) ($asDev['nombre'] ?? ''), -1, PREG_SPLIT_NO_EMPTY) ?: [];
$asIniciales = mb_strtoupper(
    mb_substr($asPartes[0] ?? 'A', 0, 1) . mb_substr($asPartes[1] ?? '', 0, 1)
);

/*
 * Los permisos de la sesión, para el `data-permisos`. Hoy ningún tema del
 * asistente declara permiso —quien entra tiene `visualizar` y la pantalla es
 * una sola—, pero el enganche va puesto: si algún día un tema habla de algo
 * que no todos pueden hacer, se filtra con la MISMA clave que exige el
 * servidor.
 */
$asPermisos = [];

foreach (['visualizar', 'crear', 'editar', 'anular'] as $asAccion) {
    if ($asSesion->puede($asAccion)) {
        $asPermisos[] = $asAccion;
    }
}

/*
 * Los iconos que el JavaScript necesita clonar: los de los menús, los de los
 * temas y los cuatro fijos de la conversación (volver, ir, otro tema, hablar
 * con una persona). Si se añade un tema con un icono nuevo, va aquí y en
 * `vistas/iconos.php`; un nombre que falte deja el chip sin icono, no rompe
 * nada.
 */
$asIconos = [
    // Menús
    'brujula', 'calendario', 'balanza', 'aviso', 'visto', 'hoja-calculo', 'herramienta',
    // Temas
    'info', 'usuario', 'luna', 'libro', 'auricular', 'recargar', 'regla', 'reloj',
    'dinero', 'nota', 'archivo', 'filtro', 'descargar', 'servidor', 'lupa', 'tienda',
    'etiqueta',
    // Fijos de la conversación
    'flecha-izquierda', 'flecha-derecha', 'lista',
];

?>
<!-- ================= ASISTENTE ================= -->
<div id="asistente" class="asistente"
     data-nombre="<?= $asE($asNombre) ?>"
     data-usuario="<?= $asE($asSesion->nombre) ?>"
     data-permisos="<?= $asE(implode(',', $asPermisos)) ?>">

    <!-- Botón flotante -->
    <button type="button" class="asis-fab" id="asis-fab"
            aria-expanded="false" aria-controls="asis-panel"
            aria-label="Abrir el asistente <?= $asE($asNombre) ?>">
        <span class="asis-fab-aro" aria-hidden="true"></span>
        <span class="asis-fab-cara">
<?php if ($asHayFoto): ?>
            <img src="<?= $asE($asFoto) ?>" alt="" aria-hidden="true">
<?php else: ?>
            <span aria-hidden="true"><?= $asE($asIniciales) ?></span>
<?php endif; ?>
        </span>
        <span class="asis-fab-punto" aria-hidden="true"></span>
        <span class="asis-fab-globo" aria-hidden="true">¿Necesitas ayuda?</span>
    </button>

    <!-- Panel de conversación -->
    <section class="asis-panel" id="asis-panel" role="dialog" aria-modal="false"
             aria-labelledby="asis-titulo" hidden>

        <header class="asis-cabecera">
            <span class="asis-cabecera-cara">
<?php if ($asHayFoto): ?>
                <img src="<?= $asE($asFoto) ?>" alt="">
<?php else: ?>
                <span><?= $asE($asIniciales) ?></span>
<?php endif; ?>
            </span>
            <div class="asis-cabecera-texto">
                <h3 id="asis-titulo"><?= $asE($asNombre) ?></h3>
                <!--
                  El artículo va aquí y no en el nombre de la aplicación:
                  «Asistente de Auditoría de Formas de Pago» se lee mal, y
                  `config/app.php` guarda el nombre, no la frase.
                -->
                <p><span class="asis-en-linea"></span> Asistente de la <?= $asE($asSistema) ?></p>
            </div>
            <button type="button" class="asis-btn-icono" id="asis-reiniciar"
                    title="Empezar de nuevo" aria-label="Empezar de nuevo">
                <?= icono('recargar', 16) ?>
            </button>
            <button type="button" class="asis-btn-icono" id="asis-cerrar"
                    title="Cerrar" aria-label="Cerrar el asistente">
                <?= icono('cerrar', 16) ?>
            </button>
        </header>

        <!--
          Conversación. `aria-live` para que un lector de pantalla anuncie las
          respuestas que van entrando.
        -->
        <div class="asis-hilo" id="asis-hilo" role="log" aria-live="polite" aria-atomic="false"></div>

        <footer class="asis-pie">
            <div class="asis-buscador">
                <?= icono('lupa', 16) ?>
                <label class="sr-solo" for="asis-buscar">Buscar un tema de ayuda</label>
                <input type="text" id="asis-buscar" autocomplete="off"
                       placeholder="Escribe tu duda: VPN, redondeo, Excel...">
            </div>
            <p class="asis-nota">
                Guía de esta pantalla. Para un caso concreto, escribe a soporte@rori.com.
            </p>
        </footer>
    </section>

    <!--
      Los iconos de los chips, para que `vistas/js/asistente.js` los clone por
      nombre sin llevar ni un trazado SVG dentro. Van a 14 px, el tamaño del
      texto de un chip.
    -->
    <div id="asis-iconos" hidden>
<?php foreach ($asIconos as $asNombreIcono): ?>
        <template data-icono="<?= $asE($asNombreIcono) ?>"><?= icono($asNombreIcono, 14) ?></template>
<?php endforeach; ?>
    </div>
</div>
