<?php

declare(strict_types=1);

/**
 * La página.
 *
 * Esta plantilla no nombra a ninguna aplicación en concreto: el nombre, el
 * subtítulo, los módulos, las hojas de estilo y los scripts salen de
 * `config/app.php`, y los datos de la empresa de `config/pie.php`. Se copia
 * tal cual al proyecto siguiente y lo único que se toca son esos dos
 * archivos.
 *
 * Los módulos de `vistas/modulos/` son fragmentos independientes: cada uno
 * pide los iconos que necesita y define su propio escapador. Por eso aquí se
 * incluyen desde una función y no en el ámbito de la plantilla —así ninguno
 * depende por accidente de una variable de aquí que el día que se mueva el
 * archivo deje de existir.
 */

require_once __DIR__ . '/iconos.php';
require_once __DIR__ . '/../servicios/SesionIntranet.php';

/** @var array<string,mixed> $app */
$app = require __DIR__ . '/../config/app.php';
/** @var array<string,mixed> $pie */
$pie = require __DIR__ . '/../config/pie.php';

$empresa = $pie['empresa'] ?? [];
$sesion  = SesionIntranet::actual();

/** Escapa para HTML; todo lo que se pinta aquí pasa por esto. */
$e = static fn (?string $v): string => htmlspecialchars((string) $v, ENT_QUOTES, 'UTF-8');

/**
 * Pinta un módulo de `vistas/modulos/`.
 *
 * Si el archivo no está, deja un aviso en la pantalla y una línea en el
 * registro, en vez de tumbar la página con un error fatal. La plantilla se
 * copia a un proyecto nuevo ANTES de que existan sus módulos, y conviene
 * poder abrirla y ver el armazón mientras se escriben. El aviso se ve, que es
 * lo que hace que no se olvide.
 */
$modulo = static function (string $nombre) use ($e): void {
    $ruta = __DIR__ . '/modulos/' . $nombre . '.php';

    if (is_file($ruta)) {
        require $ruta;

        return;
    }

    error_log('[vista] Falta el módulo vistas/modulos/' . $nombre . '.php');

    echo '<p class="alerta" role="alert">Falta el módulo <code>vistas/modulos/'
        . $e($nombre) . ".php</code>.</p>\n";
};

?>
<!doctype html>
<html lang="es">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">

    <title><?= $e($app['nombre'] ?? '') ?> · <?= $e($empresa['nombre'] ?? '') ?></title>
    <meta name="description" content="<?= $e($app['descripcion'] ?? '') ?>">

    <!-- Herramienta interna, se usa desde la red de la empresa y no se publica -->
    <meta name="robots" content="noindex, nofollow">
    <meta name="theme-color" content="<?= $e($app['tema'] ?? '#0f172a') ?>">

    <!--
      El icono de la pestaña. El SVG manda donde se admite —es nítido a
      cualquier tamaño y pesa nada—; los PNG están para quien no lo acepta
      y para la tarjeta de la intranet.
    -->
    <link rel="icon" type="image/svg+xml" href="vistas/img/icono.svg">
    <link rel="icon" type="image/png" sizes="32x32" href="vistas/img/icono-32.png">
    <link rel="icon" type="image/png" sizes="16x16" href="vistas/img/icono-16.png">
    <link rel="apple-touch-icon" href="vistas/img/icono-180.png">

<?php if (($app['font_awesome'] ?? false) === true): ?>
    <!-- Font Awesome 6, sólo para lo que no cubren los SVG de `vistas/iconos.php` -->
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.2/css/all.min.css">
<?php endif; ?>

<?php foreach ($app['css'] ?? [] as $hoja): ?>
    <link rel="stylesheet" href="<?= $e($hoja) ?>">
<?php endforeach; ?>

    <!--
      El tema se aplica ANTES de pintar nada. Si esperase al JavaScript del
      final, quien tiene el tema oscuro guardado vería un destello blanco en
      cada carga. Va en línea y sin depender de nada por el mismo motivo.
    -->
    <script>
        try {
            document.documentElement.dataset.theme =
                localStorage.getItem('tema')
                || (matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
        } catch (e) {
            document.documentElement.dataset.theme = 'light';
        }
    </script>
</head>
<body>

<a class="saltar-al-contenido" href="#contenido">Saltar al contenido</a>

<header class="app-header" id="cabecera" role="banner">
    <a class="app-header__brand" href="./">
<?php if (($empresa['logo'] ?? '') !== ''): ?>
        <span class="app-header__logo">
            <img src="<?= $e($empresa['logo']) ?>" alt="<?= $e($empresa['nombre'] ?? '') ?>"
                 width="120" height="36">
        </span>
        <span class="app-header__divider" aria-hidden="true"></span>
<?php endif; ?>
        <span class="app-header__title">
            <span class="app-header__app">
                <span class="app-header__app-nombre"><?= $e($app['nombre'] ?? '') ?></span>
<?php if ($sesion->simulada): ?>
                <span class="app-header__env" title="Las validaciones de acceso están apagadas">Pruebas</span>
<?php endif; ?>
            </span>
<?php if (($app['subtitulo'] ?? '') !== ''): ?>
            <span class="app-header__subtitle"><?= $e($app['subtitulo']) ?></span>
<?php endif; ?>
        </span>
    </a>

    <div class="app-header__actions">
        <button class="icon-btn" type="button" id="btnTema" aria-label="Cambiar a tema oscuro"
                title="Cambiar a tema oscuro">
            <span class="icon-btn__swap" id="iconoTema"><?= icono('luna', 18) ?></span>
        </button>

        <div class="app-header__user">
            <!--
              Las iniciales van SIEMPRE, y la foto encima. En la intranet hay
              perfiles que apuntan a un archivo que ya no está: si la foto es
              lo único que se pinta, el hueco queda vacío. Así, cuando la
              imagen no carga, debajo ya estaban las iniciales.
            -->
            <span class="avatar">
                <span class="avatar__initials" aria-hidden="true"><?= $e($sesion->iniciales) ?></span>
<?php if ($sesion->imagen !== ''): ?>
                <img src="<?= $e($sesion->imagen) ?>" alt="" width="40" height="40"
                     loading="lazy" onerror="this.remove()">
<?php endif; ?>
            </span>
            <span class="app-header__identity">
                <span class="app-header__name"><?= $e($sesion->nombre) ?></span>
                <span class="app-header__role"><?= $e($sesion->usuario) ?></span>
            </span>
        </div>
    </div>
</header>

<main class="container contenido" id="contenido" tabindex="-1">
<?php foreach ($app['modulos'] ?? [] as $nombreModulo) {
    $modulo($nombreModulo);
} ?>
</main>

<?php require __DIR__ . '/modulos/pie.php'; ?>
<?php foreach ($app['capas'] ?? [] as $nombreCapa) {
    $modulo($nombreCapa);
} ?>

<?php foreach ($app['js'] ?? [] as $script): ?>
<script src="<?= $e($script) ?>"></script>
<?php endforeach; ?>
</body>
</html>
