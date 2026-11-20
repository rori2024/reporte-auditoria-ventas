<?php

declare(strict_types=1);

/**
 * La ventana «Acerca de» — DESIGN-SYSTEM.md §11.
 *
 * Es la misma ventana de todos los sistemas de la casa: el diseño no cambia,
 * sólo los datos. Los propios de este proyecto están en `config/acerca.php`;
 * la empresa, el soporte, el desarrollador y la versión salen de
 * `config/pie.php`, sin copiarse.
 *
 * SE ABRE DESDE EL PIE, Y EL PIE YA LA ESPERABA
 * ---------------------------------------------
 * `vistas/modulos/pie.php` pinta el botón `[data-acerca]` sólo si 'acerca'
 * está en `capas` de `config/app.php`. Es decir: esta ventana es la pieza
 * que faltaba de un enganche que ya estaba escrito —el botón, su estilo en
 * `estilos.css` y los iconos `info`, `cerrar`, `personas`, `codigo`,
 * `llaves`, `navegador`, `servidor` y `herramienta` del catálogo, que no los
 * usa ninguna otra pantalla—.
 *
 * VA EN `capas`, NO EN `modulos`
 * -----------------------------
 * Tiene `position: fixed` y cubre la pantalla entera. Dentro del `<main>`
 * heredaría sus márgenes y su recorte, y el fondo oscuro se quedaría corto
 * por los lados. Por eso se pinta después del pie, igual que el asistente.
 *
 * Y por eso TAMPOCO está en la lista blanca de `ControladorPlantilla`: esa
 * lista es para lo que se pide por `?m=`, y a esto no se llega por URL. No
 * es un olvido.
 *
 * SE PINTA SIEMPRE, OCULTA
 * ------------------------
 * El contenido es texto y entra en el HTML de cada página con `hidden`. No
 * hay petición al abrirla, así que abre instantánea y funciona igual si la
 * red se cayó —que es cuando alguien busca el teléfono del soporte—.
 */

require_once __DIR__ . '/../iconos.php';

/** @var array<string,mixed> $acApp */
$acApp = require __DIR__ . '/../../config/app.php';
/** @var array<string,mixed> $acPie */
$acPie = require __DIR__ . '/../../config/pie.php';
/** @var array<string,mixed> $acDat */
$acDat = require __DIR__ . '/../../config/acerca.php';

$acE = static fn (?string $v): string => htmlspecialchars((string) $v, ENT_QUOTES, 'UTF-8');

$acEmpresa = (array) ($acPie['empresa'] ?? []);
$acSoporte = (array) ($acPie['soporte'] ?? []);
$acDev     = (array) ($acPie['desarrollador'] ?? []);

$acNombre      = (string) ($acApp['nombre'] ?? '');
$acDescripcion = (string) ($acApp['descripcion'] ?? '');
$acVersion     = trim((string) ($acPie['version'] ?? ''));
$acBuild       = trim((string) ($acDat['build'] ?? ''));

/*
 * La foto del desarrollador sólo si el archivo está de verdad. Un `<img>`
 * roto en una ventana que habla de quién mantiene el sistema es la peor
 * primera impresión posible, y en la intranet hay perfiles que apuntan a
 * archivos que ya no existen.
 */
$acFoto    = (string) ($acDev['foto'] ?? '');
$acHayFoto = $acFoto !== '' && is_file(__DIR__ . '/../../' . $acFoto);

/** Las iniciales, para cuando no hay foto. Mismo criterio que la cabecera. */
$acPartes    = preg_split('/\s+/u', (string) ($acDev['nombre'] ?? ''), -1, PREG_SPLIT_NO_EMPTY) ?: [];
$acIniciales = mb_strtoupper(
    mb_substr($acPartes[0] ?? '', 0, 1) . mb_substr($acPartes[1] ?? '', 0, 1)
);

/**
 * Una píldora de contacto del desarrollador: enlace si hay a dónde ir.
 * Cadena vacía si no hay dato, que es lo que la omite.
 */
$acContacto = static function (string $icono, ?string $texto, ?string $url) use ($acE): string {
    if ($texto === null || trim($texto) === '') {
        return '';
    }

    $dentro = icono($icono, 13) . '<span>' . $acE($texto) . '</span>';

    return $url !== null && trim($url) !== ''
        ? '<a class="acerca__contacto" href="' . $acE($url) . '">' . $dentro . '</a>'
        : '<span class="acerca__contacto">' . $dentro . '</span>';
};

$acContactos = $acContacto('correo', $acDev['email'] ?? '', ($acDev['email'] ?? '') !== '' ? 'mailto:' . $acDev['email'] : null)
    . $acContacto('telefono', $acDev['telefono'] ?? '', null)
    . $acContacto('github', $acDev['github'] ?? '', $acDev['github'] ?? null);

/* Las tres líneas de soporte, cada una omitida si no se sabe. */
$acLineasSoporte = [
    ['correo',    'Correo',  (string) ($acSoporte['email'] ?? ''),    ($acSoporte['email'] ?? '') !== '' ? 'mailto:' . $acSoporte['email'] : ''],
    ['telefono',  'Teléfono', (string) ($acSoporte['telefono'] ?? ''), ''],
    ['reloj',     'Horario', (string) ($acSoporte['horario'] ?? ''),  ''],
];
$acLineasSoporte = array_values(array_filter(
    $acLineasSoporte,
    static fn (array $l): bool => trim($l[2]) !== '',
));

$acTrabajo       = (array) ($acDat['trabajo'] ?? []);
$acTecnologias   = (array) ($acDat['tecnologias'] ?? []);
$acColaboradores = (array) ($acDat['colaboradores'] ?? []);
$acHayDev        = trim((string) ($acDev['nombre'] ?? '')) !== '' || $acContactos !== '';

/*
 * El escalonado de la animación. Un contador en vez de un número escrito en
 * cada bloque: las secciones se omiten solas cuando no hay datos, y con
 * índices a fuego quedarían huecos en la secuencia —el bloque cuarto
 * esperando su turno aunque el tercero no exista—.
 *
 * Se corta en 8, que es el máximo que admite la §8 para un escalonado.
 */
$acOrden = 0;
$acPaso  = static function () use (&$acOrden): string {
    return ' style="--i:' . min($acOrden++, 8) . '"';
};

?>
<div class="acerca" id="acerca" hidden>
    <!--
      El fondo. Es un hermano de la ventana y no su padre: así un clic en él
      cierra sin que haya que comprobar si el clic venía de dentro, y el
      desenfoque no se aplica al contenido de la ventana.
    -->
    <div class="acerca__fondo" data-acerca-cerrar></div>

    <div class="acerca__ventana" role="dialog" aria-modal="true" aria-labelledby="acercaTitulo">

        <header class="acerca__cabecera">
            <h2 class="acerca__titulo" id="acercaTitulo">
                <?= icono('info', 20) ?>Acerca de
            </h2>
            <button class="acerca__cerrar" type="button" data-acerca-cerrar
                    aria-label="Cerrar" title="Cerrar">
                <?= icono('cerrar', 18) ?>
            </button>
        </header>

        <div class="acerca__cuerpo">

            <section class="acerca__identidad"<?= $acPaso() ?>>
                <span class="acerca__sello" aria-hidden="true">
                    <?= icono((string) ($acDat['icono'] ?? 'grafica'), 40) ?>
                </span>
                <h3 class="acerca__sistema"><?= $acE($acNombre) ?></h3>
<?php if ($acDescripcion !== ''): ?>
                <p class="acerca__descripcion"><?= $acE($acDescripcion) ?></p>
<?php endif; ?>
<?php if ($acVersion !== '' || $acBuild !== ''): ?>
                <p class="acerca__chips">
<?php if ($acVersion !== ''): ?>
                    <span class="acerca__chip acerca__chip--version">Versión <?= $acE($acVersion) ?></span>
<?php endif; ?>
<?php if ($acBuild !== ''): ?>
                    <span class="acerca__chip">Build: <?= $acE($acBuild) ?></span>
<?php endif; ?>
                </p>
<?php endif; ?>
            </section>

<?php if (trim((string) ($acDat['destacado'] ?? '')) !== ''): ?>
            <p class="acerca__destacado"<?= $acPaso() ?>><?= $acE((string) $acDat['destacado']) ?></p>
<?php endif; ?>

<?php if ($acTrabajo !== []): ?>
            <!--
              «Cómo se trabaja» no está en la §11, y se añade a propósito.
              Quien abre esto trabaja en la empresa: su pregunta no es qué
              versión es, es si se puede fiar de la cifra que acaba de leer.
            -->
            <section class="acerca__bloque"<?= $acPaso() ?>>
                <h3 class="acerca__seccion"><?= icono('llaves', 18) ?>Cómo se trabaja</h3>
                <ul class="acerca__trabajo">
<?php foreach ($acTrabajo as $acT): ?>
                    <li class="acerca__regla">
                        <span class="acerca__regla-icono" aria-hidden="true">
                            <?= icono((string) ($acT['icono'] ?? 'info'), 18) ?>
                        </span>
                        <div>
                            <h4 class="acerca__regla-titulo"><?= $acE((string) ($acT['titulo'] ?? '')) ?></h4>
                            <p class="acerca__regla-texto"><?= $acE((string) ($acT['texto'] ?? '')) ?></p>
                        </div>
                    </li>
<?php endforeach; ?>
                </ul>
            </section>
<?php endif; ?>

<?php if ($acTecnologias !== []): ?>
            <section class="acerca__bloque"<?= $acPaso() ?>>
                <h3 class="acerca__seccion"><?= icono('codigo', 18) ?>Tecnologías</h3>
                <ul class="acerca__tecnologias">
<?php foreach ($acTecnologias as $acTec): ?>
                    <li class="acerca__tec">
                        <?= icono((string) ($acTec['icono'] ?? 'codigo'), 16) ?>
                        <span><?= $acE((string) ($acTec['nombre'] ?? '')) ?></span>
                    </li>
<?php endforeach; ?>
                </ul>
            </section>
<?php endif; ?>

<?php if ($acHayDev): ?>
            <section class="acerca__bloque"<?= $acPaso() ?>>
                <h3 class="acerca__seccion"><?= icono('usuario', 18) ?>Desarrollo</h3>
                <div class="acerca__dev">
                    <span class="acerca__retrato">
                        <span class="acerca__retrato-iniciales" aria-hidden="true"><?= $acE($acIniciales) ?></span>
<?php if ($acHayFoto): ?>
                        <!-- Sin `alt`: el nombre va al lado en texto. -->
                        <img src="<?= $acE($acFoto) ?>" alt="" width="72" height="72"
                             loading="lazy" onerror="this.remove()">
<?php endif; ?>
                    </span>
                    <div class="acerca__dev-datos">
                        <h4 class="acerca__dev-nombre"><?= $acE((string) ($acDev['nombre'] ?? '')) ?></h4>
<?php if (trim((string) ($acDev['cargo'] ?? '')) !== ''): ?>
                        <p class="acerca__dev-cargo"><?= $acE((string) $acDev['cargo']) ?></p>
<?php endif; ?>
<?php if ($acContactos !== ''): ?>
                        <p class="acerca__contactos"><?= $acContactos ?></p>
<?php endif; ?>
                    </div>
                </div>
            </section>
<?php endif; ?>

<?php if ($acColaboradores !== []): ?>
            <section class="acerca__bloque"<?= $acPaso() ?>>
                <h3 class="acerca__seccion"><?= icono('personas', 18) ?>Colaboradores</h3>
                <ul class="acerca__rejilla">
<?php foreach ($acColaboradores as $acC): ?>
<?php
    $acCn = trim((string) ($acC['nombre'] ?? ''));
    $acCp = preg_split('/\s+/u', $acCn, -1, PREG_SPLIT_NO_EMPTY) ?: [];
?>
                    <li class="acerca__tarjeta">
                        <span class="acerca__avatar" aria-hidden="true"><?= $acE(mb_strtoupper(
                            mb_substr($acCp[0] ?? '', 0, 1) . mb_substr($acCp[1] ?? '', 0, 1),
                        )) ?></span>
                        <div>
                            <span class="acerca__tarjeta-titulo"><?= $acE($acCn) ?></span>
                            <span class="acerca__tarjeta-valor"><?= $acE((string) ($acC['cargo'] ?? '')) ?></span>
                        </div>
                    </li>
<?php endforeach; ?>
                </ul>
            </section>
<?php endif; ?>

<?php if ($acLineasSoporte !== []): ?>
            <section class="acerca__bloque"<?= $acPaso() ?>>
                <h3 class="acerca__seccion"><?= icono('auricular', 18) ?>Soporte técnico</h3>
                <ul class="acerca__rejilla">
<?php foreach ($acLineasSoporte as [$acIco, $acRot, $acVal, $acUrl]): ?>
                    <li class="acerca__tarjeta">
                        <span class="acerca__tarjeta-icono" aria-hidden="true"><?= icono($acIco, 24) ?></span>
                        <div>
                            <span class="acerca__tarjeta-titulo"><?= $acE($acRot) ?></span>
<?php if ($acUrl !== ''): ?>
                            <a class="acerca__tarjeta-valor" href="<?= $acE($acUrl) ?>"><?= $acE($acVal) ?></a>
<?php else: ?>
                            <span class="acerca__tarjeta-valor"><?= $acE($acVal) ?></span>
<?php endif; ?>
                        </div>
                    </li>
<?php endforeach; ?>
                </ul>
            </section>
<?php endif; ?>

            <footer class="acerca__pie"<?= $acPaso() ?>>
                <p>© <?= date('Y') ?> <?= $acE((string) ($acEmpresa['nombre'] ?? '')) ?> — Todos los derechos reservados.</p>
<?php if (trim((string) ($acDat['gracias'] ?? '')) !== ''): ?>
                <p><?= $acE((string) $acDat['gracias']) ?></p>
<?php endif; ?>
            </footer>

        </div>
    </div>
</div>
