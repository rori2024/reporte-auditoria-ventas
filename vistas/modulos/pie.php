<?php

declare(strict_types=1);

/**
 * Pie corporativo — DESIGN-SYSTEM.md §10.
 *
 * Los datos salen de `config/pie.php`. Lo que esté vacío no se pinta, y una
 * columna sin nada no se pinta entera: así un dato que todavía no se sabe
 * —el correo del desarrollador, los manuales que aún no existen— se queda
 * fuera en lugar de aparecer inventado o como un enlace roto.
 */

require_once __DIR__ . '/../iconos.php';

/** @var array<string,mixed> $pie */
$pie = require __DIR__ . '/../../config/pie.php';

/*
 * El botón «Acerca de» sólo se pinta si la ventana existe, y de eso manda
 * `config/app.php`. Un botón que no abre nada es peor que no tener botón, y
 * en una copia recién hecha de la plantilla la ventana todavía no está.
 */
/** @var array<string,mixed> $pie_app */
$pie_app    = require __DIR__ . '/../../config/app.php';
$pie_acerca = in_array('acerca', (array) ($pie_app['capas'] ?? []), true);

/** Escapa para HTML; todo lo del pie pasa por aquí. */
$e = static fn(?string $v): string => htmlspecialchars((string) $v, ENT_QUOTES, 'UTF-8');

/**
 * Una línea de la lista: icono + texto, opcionalmente enlazado.
 * Devuelve cadena vacía si no hay texto, que es lo que la omite.
 */
$linea = static function (string $nombreIcono, ?string $texto, ?string $url = null) use ($e): string {
    if ($texto === null || trim($texto) === '') {
        return '';
    }

    $contenido = $url !== null && $url !== ''
        ? '<a class="footer__link" href="' . $e($url) . '">' . $e($texto) . '</a>'
        : '<span>' . $e($texto) . '</span>';

    return '<li class="footer__item">' . icono($nombreIcono, 14) . $contenido . '</li>';
};

/**
 * Un botón de manual: píldora contorneada con icono, como pide la §10.
 * Devuelve cadena vacía si no hay ruta, que es lo que lo omite.
 *
 * Se abre en una pestaña nueva —no `download`— porque quien consulta el manual
 * suele estar a mitad de una consulta y perderla para leer un PDF es peor que
 * tener dos pestañas. `rel="noopener"` va siempre con `target="_blank"`.
 */
$pildora = static function (?string $ruta, string $texto) use ($e): string {
    if ($ruta === null || trim($ruta) === '') {
        return '';
    }

    return '<a class="footer__pill" href="' . $e($ruta) . '" target="_blank" rel="noopener">'
        . icono('archivo', 14) . $e($texto) . '</a>';
};

$empresa       = $pie['empresa'] ?? [];
$soporte       = $pie['soporte'] ?? [];
$desarrollador = $pie['desarrollador'] ?? [];
$manuales      = $pie['manuales'] ?? [];

// Columna 2
$lineasSoporte = $linea('correo', $soporte['email'] ?? '', ($soporte['email'] ?? '') !== '' ? 'mailto:' . $soporte['email'] : null)
    . $linea('telefono', $soporte['telefono'] ?? '')
    . $linea('reloj', $soporte['horario'] ?? '');

// Columna 3
$lineasDesarrollador = $linea('correo', $desarrollador['email'] ?? '', ($desarrollador['email'] ?? '') !== '' ? 'mailto:' . $desarrollador['email'] : null)
    . $linea('telefono', $desarrollador['telefono'] ?? '')
    . $linea('github', $desarrollador['github'] ?? '', $desarrollador['github'] ?? null);

$hayDesarrollador = trim((string) ($desarrollador['nombre'] ?? '')) !== '' || $lineasDesarrollador !== '';

// Columna 4
$botonesManuales = $pildora($manuales['usuario'] ?? '', 'Manual de usuario (PDF)')
    . $pildora($manuales['tecnico'] ?? '', 'Manual técnico (PDF)');

/*
 * Cuatro columnas sólo cuando hay manuales. Con tres, la rejilla de
 * 1.2fr 1fr 1fr 1.2fr dejaría una columna vacía al final en vez de repartir
 * el ancho entre las que sí tienen contenido.
 */
$clasesCols = 'footer__cols' . ($botonesManuales !== '' ? ' footer__cols--4' : '');

?>
<footer class="app-footer">
    <div class="container">
        <div class="<?= $clasesCols ?>">

            <section aria-labelledby="pieEmpresa">
                <div class="footer__marca">
                    <?php if (($empresa['logo'] ?? '') !== ''): ?>
                        <span class="footer__logo">
                            <img src="<?= $e($empresa['logo']) ?>" alt="" width="107" height="32">
                        </span>
                    <?php endif; ?>
                    <span class="footer__empresa" id="pieEmpresa"><?= $e($empresa['nombre'] ?? '') ?></span>
                </div>

                <?php if (($empresa['descripcion'] ?? '') !== ''): ?>
                    <p style="margin:0 0 var(--space-3)"><?= $e($empresa['descripcion']) ?></p>
                <?php endif; ?>

                <ul class="footer__lista">
                    <?= $linea('ubicacion', $empresa['direccion'] ?? '') ?>
                    <?= $linea('globo', $empresa['web'] ?? '', $empresa['web'] ?? null) ?>
                </ul>
            </section>

            <?php if ($lineasSoporte !== ''): ?>
                <section aria-labelledby="pieSoporte">
                    <h2 class="footer__titulo" id="pieSoporte">
                        <?= icono('auricular', 16) ?>Soporte técnico
                    </h2>
                    <ul class="footer__lista"><?= $lineasSoporte ?></ul>
                </section>
            <?php endif; ?>

            <?php if ($hayDesarrollador): ?>
                <section aria-labelledby="pieDesarrollador">
                    <h2 class="footer__titulo" id="pieDesarrollador">
                        <?= icono('usuario', 16) ?>Desarrollo
                    </h2>
                    <div class="footer__dev">
                        <?php if (($desarrollador['foto'] ?? '') !== ''): ?>
                            <!--
                          Sin `alt`: el nombre va justo al lado, en texto. Una
                          descripción aquí haría que el lector de pantalla
                          dijera el nombre dos veces.
                        -->
                            <img class="footer__dev-photo" src="<?= $e($desarrollador['foto']) ?>"
                                alt="" width="44" height="44" loading="lazy">
                        <?php endif; ?>
                        <div>
                            <div class="footer__dev-name"><?= $e($desarrollador['nombre'] ?? '') ?></div>
                            <div class="footer__dev-role"><?= $e($desarrollador['cargo'] ?? '') ?></div>
                        </div>
                    </div>
                    <?php if ($lineasDesarrollador !== ''): ?>
                        <ul class="footer__lista"><?= $lineasDesarrollador ?></ul>
                    <?php endif; ?>
                </section>
            <?php endif; ?>

            <?php if ($botonesManuales !== ''): ?>
                <section aria-labelledby="pieManuales">
                    <h2 class="footer__titulo" id="pieManuales">
                        <?= icono('libro', 16) ?>Manuales
                    </h2>
                    <?php if (trim((string) ($manuales['texto'] ?? '')) !== ''): ?>
                        <p style="margin:0 0 var(--space-3)"><?= $e($manuales['texto']) ?></p>
                    <?php endif; ?>
                    <div class="footer__manuales"><?= $botonesManuales ?></div>
                </section>
            <?php endif; ?>

        </div>

        <div class="footer__barra">
            <span>
                © <?= date('Y') ?> <?= $e($empresa['nombre'] ?? '') ?> — Todos los derechos reservados.
            </span>
            <span class="footer__acciones">
                <?php if ($pie_acerca): ?>
                    <button class="footer__acerca" type="button" data-acerca>
                        <?= icono('info', 14) ?>Acerca de
                    </button>
                <?php endif; ?>
                <span class="footer__version">
                    Versión <?= $e($pie['version'] ?? '') ?>
                </span>
            </span>
        </div>
    </div>
</footer>