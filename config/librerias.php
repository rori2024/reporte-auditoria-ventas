<?php

/**
 * Mapa de archivos del AS400: alias => BIBLIOTECA.ARCHIVO.
 *
 * Deja el mapa en el global `$archivos`, que es de donde lo leen los modelos
 * al armar cada consulta remota. Sin él, ninguna subida al AS400 puede saber a
 * qué archivo escribir.
 *
 * Qué archivo se lee lo decide `AS400_LIBRERIAS` en el .env:
 *
 *   desarrollo  config/libreriasDevs.txt   bibliotecas de pruebas
 *   produccion  config/librerias.txt       las de verdad (predeterminado)
 *
 * OJO: lo de abajo es el valor POR DEFECTO, y sólo se usa cuando el .env no
 * declara la clave. Si el .env la trae, manda el .env. Cambiar aquí y seguir
 * viendo el otro entorno es exactamente eso: el .env ganando.
 *
 * ---------------------------------------------------------------------------
 * Este archivo estaba escrito para ejecutarse desde `php/<modulo>/algo.php` y
 * nadie lo incluía: la ruta era relativa ("../../config/…"), el archivo de
 * producción no se leía nunca y, sobre todo, `$archivos` se quedaba vacío. Con
 * el mapa vacío cada INSERT remoto fallaba con "La tabla X no está definida en
 * los archivos"… y la pantalla decía "actualizada satisfactoriamente", porque
 * el resultado del INSERT no se miraba. Ahora la ruta es absoluta, el destino
 * se elige por configuración y un mapa vacío se queda anotado en el registro.
 */

require_once __DIR__ . '/env.php';

/** @var array<string,string> alias del archivo => BIBLIOTECA.ARCHIVO */
$archivos = [];

$entorno = strtolower(trim((string) env('AS400_LIBRERIAS', 'desarrollo')));
$ruta    = __DIR__ . ($entorno === 'produccion' ? '/librerias.txt' : '/libreriasDevs.txt');

if (!is_readable($ruta)) {
    error_log('[librerias] No se puede leer ' . $ruta
        . '. Ninguna subida al AS400 funcionará hasta que exista.');
} else {
    foreach (file($ruta, FILE_IGNORE_NEW_LINES | FILE_SKIP_EMPTY_LINES) as $numero => $linea) {
        $linea = trim($linea);

        // Una línea en blanco o un comentario no son un error
        if ($linea === '' || str_starts_with($linea, '#')) {
            continue;
        }

        $partes = explode(';', $linea, 2);

        if (count($partes) !== 2 || trim($partes[0]) === '' || trim($partes[1]) === '') {
            error_log('[librerias] Línea ' . ($numero + 1) . ' de ' . basename($ruta)
                . ' mal formada, se ignora: ' . $linea);
            continue;
        }

        // Se recortan los dos: antes el valor conservaba el salto de línea y
        // viajaba dentro del nombre del archivo en cada consulta
        $archivos[trim($partes[0])] = trim($partes[1]);
    }

    if ($archivos === []) {
        error_log('[librerias] ' . basename($ruta) . ' no declara ningún archivo.');
    }
}
