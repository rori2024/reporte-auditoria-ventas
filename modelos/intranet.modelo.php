<?php

declare(strict_types=1);

/**
 * Las tres consultas que esta aplicación le hace a la intranet.
 *
 * Todas con sentencias preparadas y todas devolviendo el valor más restrictivo
 * cuando algo falla: si no se puede comprobar un permiso, la respuesta es que
 * no lo tiene. Un error de base de datos no debe convertirse en un acceso
 * concedido.
 *
 * Las tres tablas llevan una columna `estatus`. Hoy todas las filas valen '1',
 * pero se filtra igualmente: el día que alguien desactive un permiso poniendo
 * otro valor, esta aplicación debe enterarse sin que haya que tocarla.
 */

require_once __DIR__ . '/../config/intranet.php';

final class ModeloIntranet
{
    /** ¿Tiene el usuario concedida esta aplicación? */
    public static function tienePermiso(string $usuario, int $idApp): bool
    {
        $conexion = intranet_conexion();

        if ($conexion === null) {
            return false;
        }

        $sql = 'SELECT permiso
                  FROM app_externa_permisos
                 WHERE usuario = ? AND id_app = ? AND estatus = ?
                 LIMIT 1';

        $sentencia = @$conexion->prepare($sql);

        if ($sentencia === false) {
            error_log('[intranet] No se pudo preparar la consulta de permiso: ' . $conexion->error);
            return false;
        }

        $estatus = '1';
        $sentencia->bind_param('sis', $usuario, $idApp, $estatus);
        $sentencia->execute();
        $sentencia->bind_result($permiso);
        $hay = $sentencia->fetch();
        $sentencia->close();

        return $hay === true && strtoupper(trim((string) $permiso)) === 'SI';
    }

    /**
     * Permisos especiales. Ausentes equivale a no concedidos.
     *
     * @return array{crear:bool,editar:bool,anular:bool,visualizar:bool}
     */
    public static function permisosEspeciales(string $usuario, int $idApp): array
    {
        $ninguno = ['crear' => false, 'editar' => false, 'anular' => false, 'visualizar' => false];

        $conexion = intranet_conexion();

        if ($conexion === null) {
            return $ninguno;
        }

        $sql = 'SELECT crear, editar, anular, visualizar
                  FROM app_externa_permisos_especiales
                 WHERE usuario = ? AND id_app = ? AND estatus = ?
                 LIMIT 1';

        $sentencia = @$conexion->prepare($sql);

        if ($sentencia === false) {
            error_log('[intranet] No se pudo preparar la consulta de permisos especiales: ' . $conexion->error);
            return $ninguno;
        }

        $estatus = '1';
        $sentencia->bind_param('sis', $usuario, $idApp, $estatus);
        $sentencia->execute();
        $sentencia->bind_result($crear, $editar, $anular, $visualizar);
        $hay = $sentencia->fetch();
        $sentencia->close();

        if ($hay !== true) {
            return $ninguno;
        }

        $si = static fn ($v): bool => strtoupper(trim((string) $v)) === 'SI';

        return [
            'crear'      => $si($crear),
            'editar'     => $si($editar),
            'anular'     => $si($anular),
            'visualizar' => $si($visualizar),
        ];
    }

    /**
     * Nombre y foto de perfil.
     *
     * `profile_pic` guarda sólo el nombre del archivo ("default.png"), así que
     * se le pasa `basename()` antes de construir la URL: un valor con "../"
     * en la base de datos no debe poder apuntar fuera de la carpeta de fotos.
     *
     * @return array{nombre:string,imagen:string}
     */
    public static function perfil(string $usuario): array
    {
        $vacio = ['nombre' => $usuario, 'imagen' => ''];

        $conexion = intranet_conexion();

        if ($conexion === null) {
            return $vacio;
        }

        $sentencia = @$conexion->prepare('SELECT nombre, profile_pic FROM usuarios WHERE usuario = ? LIMIT 1');

        if ($sentencia === false) {
            error_log('[intranet] No se pudo preparar la consulta de perfil: ' . $conexion->error);
            return $vacio;
        }

        $sentencia->bind_param('s', $usuario);
        $sentencia->execute();
        $sentencia->bind_result($nombre, $foto);
        $hay = $sentencia->fetch();
        $sentencia->close();

        if ($hay !== true) {
            return $vacio;
        }

        /*
         * La foto NO cuelga directamente de la carpeta de perfiles: cada
         * usuario tiene la suya, con su código por nombre.
         *
         *     .../images/profiles/CFLORES/mi-foto.jpeg
         *
         * En la raíz sólo está `default.png`, que es el avatar genérico de la
         * intranet. Para esta aplicación eso significa «sin foto», y en ese
         * caso el sistema de diseño pide las iniciales, que dicen más que una
         * silueta igual para todos. Así además se ahorra un 404 por carga.
         *
         * `basename()` sigue puesto: un valor con "../" en la base de datos
         * no debe poder apuntar fuera de la carpeta del usuario.
         */
        $archivo = basename(trim((string) $foto));
        $sinFoto = $archivo === '' || strcasecmp($archivo, 'default.png') === 0;

        return [
            'nombre' => trim((string) $nombre) !== '' ? trim((string) $nombre) : $usuario,
            'imagen' => $sinFoto
                ? ''
                : intranet_url_perfiles() . rawurlencode($usuario) . '/' . rawurlencode($archivo),
        ];
    }
}
