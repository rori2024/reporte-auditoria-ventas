<?php

declare(strict_types=1);

/**
 * Carga la única plantilla de la aplicación.
 *
 * Hay una sola página. Las pantallas que la aplicación aparenta tener se
 * arman en el navegador con el JSON que devuelven los puntos de entrada de
 * `php/`, así que no hay enrutador: no hay a dónde enrutar.
 *
 * Qué módulos pinta esa página no se decide aquí, sino en `config/app.php`.
 */
final class ControladorPlantilla
{
    public static function ctrPlantilla(): void
    {
        require_once __DIR__ . '/../vistas/plantilla.php';
    }
}
