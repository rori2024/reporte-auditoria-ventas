<?php

declare(strict_types=1);

/**
 * Entrada de la aplicación.
 *
 * Primero se resuelve quién entra y si puede; sólo después se pinta algo. El
 * `exit` tras la redirección NO es opcional: sin él, PHP sigue ejecutando y
 * manda el HTML entero detrás de la cabecera `Location`, así que el contenido
 * llega igual a quien no debía verlo.
 */

require_once __DIR__ . '/servicios/SesionIntranet.php';
require_once __DIR__ . '/controladores/plantilla.controlador.php';

try {
    SesionIntranet::abrir();
} catch (AccesoDenegado $e) {
    header('Location: errorAcceso.php?motivo=' . rawurlencode($e->codigo));
    exit;
}

ControladorPlantilla::ctrPlantilla();
