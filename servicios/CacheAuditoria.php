<?php

declare(strict_types=1);

/**
 * Guarda una corrida de la auditoría para que el Excel sea lo que se vio.
 *
 * ===========================================================================
 *  EL PROBLEMA, QUE NO ES EL RENDIMIENTO
 * ---------------------------------------------------------------------------
 *  La pantalla pide el informe, lo pinta, y la persona lo mira. Luego pulsa
 *  «Descargar Excel». Si ese botón vuelve a preguntarle al AS400, el archivo
 *  que se descarga NO es el que se acaba de revisar: entre mirar y descargar
 *  pasan minutos, y en esos minutos las tiendas siguen facturando. Dos
 *  informes del «mismo» período con cifras distintas, y nadie sabría cuál
 *  creer ni por qué difieren.
 *
 *  Esa es la razón de que esto exista. Que además se ahorre una consulta de
 *  varios segundos es una ventaja, no el motivo: si el motivo fuera la
 *  velocidad, sería legítimo saltarse la caché cuando conviniera, y no lo es.
 *
 *  Toda la pantalla está construida sobre esa idea: SE MIRA ANTES DE
 *  DESCARGAR, y lo que se descarga es lo que se miró.
 * ===========================================================================
 *
 * POR QUÉ UN ARCHIVO Y NO LA SESIÓN DE PHP
 * ----------------------------------------
 * Un informe de un mes son unos pocos megas de JSON. Metido en `$_SESSION` se
 * carga y se vuelve a escribir en CADA petición de esa persona, incluida la que
 * sólo pide un icono, y bloquea el archivo de sesión mientras lo hace. Un
 * archivo aparte se lee sólo cuando hace falta.
 *
 * LA CADUCIDAD ES CORTA Y ES A PROPÓSITO
 * --------------------------------------
 * Media hora. Pasada, el botón vuelve a consultar el AS400 — porque a esa
 * altura ya no se está descargando «lo que se acaba de mirar», se está
 * descargando algo viejo, y entonces lo honesto es ir a buscar el dato de
 * nuevo. Una caché que no caduca convierte una auditoría en vivo en una
 * auditoría de cuando a nadie le importaba.
 */
final class CacheAuditoria
{
    /** Minutos que vive una corrida guardada. Ver la cabecera. */
    public const MINUTOS = 30;

    /** Dónde se guardan. Cuelga de `almacen/`, que el .htaccess deniega. */
    private static function carpeta(): string
    {
        $carpeta = dirname(__DIR__) . '/almacen/auditoria/cache';

        if (!is_dir($carpeta) && !@mkdir($carpeta, 0777, true) && !is_dir($carpeta)) {
            throw new RuntimeException(
                'No se pudo crear la carpeta de la caché: ' . $carpeta
            );
        }

        return $carpeta;
    }

    /**
     * Guarda el informe y devuelve su ficha.
     *
     * @param  array<string,mixed> $informe
     * @return string el token con el que se vuelve a pedir
     */
    public static function guardar(array $informe): string
    {
        $carpeta = self::carpeta();

        /*
         * El token lo genera `random_bytes` y no un hash del período.
         *
         * Con un hash del período, el token de «noviembre» sería adivinable, y
         * cualquiera que pudiera llamar al endpoint se descargaría la corrida
         * de otra persona sin haberla pedido. Siendo aleatorio, el token sólo
         * lo tiene quien hizo la consulta. Y aun así el endpoint comprueba el
         * permiso de la intranet: el token no es la autorización, es el
         * identificador.
         */
        $token = bin2hex(random_bytes(16));

        $json = json_encode($informe, JSON_UNESCAPED_UNICODE | JSON_INVALID_UTF8_SUBSTITUTE);

        if ($json === false) {
            throw new RuntimeException(
                'No se pudo guardar la corrida: ' . json_last_error_msg()
            );
        }

        /*
         * Se escribe a un temporal y se renombra. Un `file_put_contents` que se
         * queda a medias —disco lleno, PHP que se corta— deja un JSON
         * truncado que al leerse falla con «error de sintaxis» y no con «no
         * está»; el renombrado es atómico, así que el archivo o está completo o
         * no está.
         */
        $destino = $carpeta . '/' . $token . '.json';
        $temporal = $destino . '.tmp';

        if (@file_put_contents($temporal, $json) === false || !@rename($temporal, $destino)) {
            @unlink($temporal);

            throw new RuntimeException('No se pudo escribir la corrida en la caché.');
        }

        self::limpiar();

        return $token;
    }

    /**
     * Recupera una corrida, o null si ya no está o caducó.
     *
     * @return array<string,mixed>|null
     */
    public static function recuperar(string $token): ?array
    {
        /*
         * El token viene de la URL, así que se valida con una expresión
         * estricta ANTES de tocar el sistema de archivos. Sin esto, un token
         * como `../../../config/.env` compondría una ruta fuera de la carpeta:
         * es la inyección de ruta clásica, y aquí sería grave porque el archivo
         * que se intentaría leer es el de las credenciales del AS400.
         */
        if (preg_match('/^[0-9a-f]{32}$/', $token) !== 1) {
            return null;
        }

        $ruta = self::carpeta() . '/' . $token . '.json';

        if (!is_file($ruta)) {
            return null;
        }

        if (time() - (int) filemtime($ruta) > self::MINUTOS * 60) {
            @unlink($ruta);

            return null;
        }

        $json = @file_get_contents($ruta);

        if ($json === false) {
            return null;
        }

        $informe = json_decode($json, true);

        return is_array($informe) ? $informe : null;
    }

    /**
     * Borra las corridas caducadas.
     *
     * Se llama al guardar y no por una tarea programada: sin esto la carpeta
     * crece sin fin con informes de megas que ya no sirven, y nadie se acuerda
     * de mirarla hasta que el disco se llena.
     */
    public static function limpiar(): void
    {
        $limite = time() - self::MINUTOS * 60;

        foreach (glob(self::carpeta() . '/*.json') ?: [] as $archivo) {
            if ((int) filemtime($archivo) < $limite) {
                @unlink($archivo);
            }
        }

        // Y los temporales que se quedaron por el camino, que no llevan .json.
        foreach (glob(self::carpeta() . '/*.tmp') ?: [] as $archivo) {
            if ((int) filemtime($archivo) < $limite) {
                @unlink($archivo);
            }
        }
    }
}
