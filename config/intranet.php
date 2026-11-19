<?php

declare(strict_types=1);

/**
 * Conexión con la base de datos de la intranet.
 *
 * De ahí salen dos cosas: quién es el usuario (nombre y foto) y si tiene
 * concedida esta aplicación. Es una base distinta de la del AS400 y se abre
 * sólo cuando hace falta.
 *
 * Todo lo configurable está en el .env. Para llevar esto a otra aplicación no
 * hay que tocar código: basta cambiar `INTRANET_APP_ID`.
 */

require_once __DIR__ . '/env.php';

/**
 * ¿Hay que validar el acceso?
 *
 * En desarrollo se apaga y se trabaja como el usuario de pruebas. No es un
 * atajo escondido: mientras esté apagado, la cabecera muestra un distintivo
 * «PRUEBAS» que no se puede pasar por alto.
 */
function intranet_validando(): bool
{
    return env_bool('INTRANET_VALIDAR', false);
}

/** Id de esta aplicación en la intranet; 0 si no está configurado. */
function intranet_id_app(): int
{
    $valor = trim((string) env('INTRANET_APP_ID', ''));

    return preg_match('/^\d+$/', $valor) === 1 ? (int) $valor : 0;
}

/** Usuario que se simula cuando la validación está apagada. */
function intranet_usuario_de_pruebas(): string
{
    return strtoupper(trim((string) env('INTRANET_USUARIO_PRUEBAS', 'PRUEBAS')));
}

/** Carpeta de la que cuelgan las fotos de perfil, vista desde esta aplicación. */
function intranet_url_perfiles(): string
{
    return rtrim((string) env('INTRANET_URL_PERFILES', ''), '/') . '/';
}

/**
 * La conexión con la intranet, abierta una sola vez por petición.
 *
 * Devuelve null si no se puede conectar, y quien llame decide. Dentro de una
 * validación de acceso ese null significa «no puedo comprobar el permiso», y
 * la respuesta correcta entonces es cerrar la puerta, no abrirla.
 */
function intranet_conexion(): ?mysqli
{
    static $conexion  = null;
    static $intentado = false;

    if ($intentado) {
        return $conexion;
    }

    $intentado = true;

    try {
        /*
         * Con un tiempo de espera corto, y a propósito.
         *
         * La base de la intranet está en otro servidor. Si ese servidor no
         * responde —o el puerto no es el que se cree— el `connect` por
         * omisión se queda esperando decenas de segundos, y como esto se
         * llama al abrir cada pantalla, la aplicación entera parecería
         * colgada. Mejor rendirse en unos segundos y seguir: en desarrollo se
         * trabaja sin foto, y en producción se deniega el acceso, que es la
         * respuesta correcta cuando no se puede comprobar un permiso.
         */
        $propia = mysqli_init();

        if ($propia === false) {
            throw new RuntimeException('No se pudo inicializar mysqli.');
        }

        $propia->options(MYSQLI_OPT_CONNECT_TIMEOUT, env_entero('INTRANET_DB_TIMEOUT', 4, 1, 60));
        $propia->options(MYSQLI_OPT_READ_TIMEOUT, env_entero('INTRANET_DB_TIMEOUT', 4, 1, 60));

        @$propia->real_connect(
            (string) env('INTRANET_DB_HOST', 'localhost'),
            (string) env('INTRANET_DB_USER', ''),
            (string) (env('INTRANET_DB_PASS', '') ?? ''),
            (string) env('INTRANET_DB_NAME', 'intranet'),
            env_entero('INTRANET_DB_PORT', 3306, 1, 65535)
        );

        if ($propia->connect_error) {
            error_log('[intranet] No se pudo conectar con la base de la intranet: ' . $propia->connect_error);
            $conexion = null;
        } else {
            $propia->set_charset('utf8mb4');
            $conexion = $propia;
        }
    } catch (Throwable $e) {
        error_log('[intranet] No se pudo conectar con la base de la intranet: ' . $e->getMessage());
        $conexion = null;
    }

    return $conexion;
}
