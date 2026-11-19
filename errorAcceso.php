<?php

declare(strict_types=1);

/**
 * Acceso denegado.
 *
 * Dice qué pasó y qué hacer, sin contar de más: no revela si el usuario
 * existe ni qué permisos tiene, sólo que por aquí no se entra.
 */

require_once __DIR__ . '/servicios/SesionIntranet.php';

/*
 * El nombre de la aplicación y el de la empresa salen de la configuración,
 * igual que en `vistas/plantilla.php`. Esta página no puede tirar de la
 * plantilla —se pinta cuando no hay sesión que pintar— pero sí de los mismos
 * datos, que es lo que evita que una de las dos se quede con el nombre del
 * proyecto del que se copió.
 */

/** @var array<string,mixed> $app */
$app = require __DIR__ . '/config/app.php';
/** @var array<string,mixed> $pie */
$pie = require __DIR__ . '/config/pie.php';

$empresa = $pie['empresa'] ?? [];

if (session_status() !== PHP_SESSION_ACTIVE) {
    session_start();
}

$motivos = [
    'sin-datos'   => ['Enlace no válido', 'El enlace con el que llegó no trae los datos de acceso o están mal formados. Vuelva a abrir la aplicación desde la intranet.'],
    'sin-sesion'  => ['Sesión no iniciada', 'Esta aplicación se abre desde la intranet, que es quien lo identifica. Entre desde allí.'],
    'sin-permiso' => ['Sin permiso', 'Su usuario no tiene concedida esta aplicación. Solicítela al administrador de la intranet.'],
    'otra-app'    => ['Enlace de otra aplicación', 'El enlace no corresponde a esta aplicación. Vuelva a abrirla desde la intranet.'],
    'sin-id'      => ['Aplicación sin configurar', 'Esta aplicación todavía no tiene asignado un identificador en la intranet. Avise al departamento de sistemas.'],
];

$codigo               = (string) ($_GET['motivo'] ?? '');
[$titulo, $explicacion] = $motivos[$codigo] ?? ['Acceso denegado', 'No es posible abrir esta aplicación con los datos recibidos.'];

// Se registra para poder mirarlo después; en pantalla no se dan detalles
error_log('[intranet] Acceso denegado (' . ($codigo !== '' ? $codigo : 'sin motivo') . ') desde '
    . ($_SERVER['REMOTE_ADDR'] ?? 'origen desconocido'));

$e = static fn (?string $v): string => htmlspecialchars((string) $v, ENT_QUOTES, 'UTF-8');

?>
<!doctype html>
<html lang="es">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
    <title>Acceso denegado · <?= $e($app['nombre'] ?? '') ?></title>
    <meta name="robots" content="noindex, nofollow">
    <!--
      El icono de la pestaña. El SVG manda donde se admite —es nítido a
      cualquier tamaño y pesa nada—; los PNG están para quien no lo acepta
      y para la tarjeta de la intranet.
    -->
    <link rel="icon" type="image/svg+xml" href="vistas/img/icono.svg">
    <link rel="icon" type="image/png" sizes="32x32" href="vistas/img/icono-32.png">
    <link rel="icon" type="image/png" sizes="16x16" href="vistas/img/icono-16.png">
    <link rel="apple-touch-icon" href="vistas/img/icono-180.png">
<?php foreach ($app['css'] ?? [] as $hoja): ?>
    <link rel="stylesheet" href="<?= $e($hoja) ?>">
<?php endforeach; ?>
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

<header class="app-header" role="banner">
    <span class="app-header__brand">
<?php if (($empresa['logo'] ?? '') !== ''): ?>
        <span class="app-header__logo">
            <img src="<?= $e($empresa['logo']) ?>" alt="<?= $e($empresa['nombre'] ?? '') ?>"
                 width="120" height="36">
        </span>
        <span class="app-header__divider" aria-hidden="true"></span>
<?php endif; ?>
        <span class="app-header__title">
            <span class="app-header__app"><?= $e($app['nombre'] ?? '') ?></span>
        </span>
    </span>
</header>

<main class="container contenido" id="contenido">
    <div class="card card-consulta">
        <div class="card-header">
            <h1 id="tituloError"><?= $e($titulo) ?></h1>
        </div>
        <div class="card-body">
            <p class="alerta" role="alert"><?= $e($explicacion) ?></p>

            <div class="form-actions">
                <a class="btn btn-primary" href="<?= $e(SesionIntranet::enlaceDeRegreso()) ?>">
                    Volver a intentarlo
                </a>
            </div>
        </div>
    </div>
</main>

<?php require __DIR__ . '/vistas/modulos/pie.php'; ?>

</body>
</html>
