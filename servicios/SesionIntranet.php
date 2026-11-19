<?php

declare(strict_types=1);

/**
 * Quién está usando la aplicación y si puede.
 *
 * La intranet abre esta aplicación con `index.php?user=…&idapp=…`, los dos
 * valores en base64. A partir de ahí la identidad vive en la sesión de PHP y
 * los `?user=` dejan de hacer falta: las llamadas internas (`php/combos.php` y
 * compañía) leen la sesión, no la URL.
 *
 * ---------------------------------------------------------------------------
 * AVISO sobre lo que esto es y lo que no
 *
 * Un usuario en un parámetro de la URL NO es autenticación: cualquiera en la
 * red puede escribir el nombre de otro en base64 y entrar como él. Esto
 * comprueba PERMISOS —que a ese usuario le han concedido esta aplicación—,
 * que es justo lo que pide el encargo y lo que hacen los demás módulos de la
 * casa. Para que fuera también autenticación haría falta que la intranet
 * firmara el enlace (un HMAC con caducidad, por ejemplo) y que aquí se
 * verificara la firma. Queda anotado en docs/PLAN.md.
 * ---------------------------------------------------------------------------
 *
 * Para llevar esto a otra aplicación sólo se cambia `INTRANET_APP_ID` en el
 * .env. Y para trabajar sin la intranet delante, `INTRANET_VALIDAR=no`.
 */

require_once __DIR__ . '/../config/intranet.php';
require_once __DIR__ . '/../modelos/intranet.modelo.php';

/** El acceso se deniega. El código dice por qué, para la página de error. */
final class AccesoDenegado extends RuntimeException
{
    public function __construct(public readonly string $codigo, string $mensaje)
    {
        parent::__construct($mensaje);
    }
}

final class SesionIntranet
{
    /**
     * Versión del perfil guardado en la sesión.
     *
     * Se sube cuando cambia CÓMO se arma el perfil, no cuando cambian los
     * datos. Una sesión guardada con una versión anterior se vuelve a pedir
     * en la siguiente carga, en vez de arrastrar lo viejo hasta que la
     * persona cierre el navegador.
     *
     *   1 -> la foto colgaba directamente de la carpeta de perfiles
     *   2 -> la foto cuelga de la subcarpeta del usuario
     */
    private const VERSION_PERFIL = 2;

    /** La sesión ya resuelta en esta petición. */
    private static ?self $actual = null;

    private function __construct(
        public readonly string $usuario,
        public readonly string $nombre,
        public readonly string $imagen,
        public readonly string $iniciales,
        /** @var array{crear:bool,editar:bool,anular:bool,visualizar:bool} */
        public readonly array $permisos,
        /** true cuando la validación está apagada: se está trabajando en pruebas */
        public readonly bool $simulada,
    ) {
    }

    // ------------------------------------------------------------- entradas

    /**
     * Entrada principal, desde `index.php`. Acepta los parámetros de la URL.
     *
     * @throws AccesoDenegado
     */
    public static function abrir(): self
    {
        self::iniciarSesionPhp();

        $validando = intranet_validando();
        $idApp     = intranet_id_app();

        if ($validando && $idApp === 0) {
            throw new AccesoDenegado(
                'sin-id',
                'Esta aplicación todavía no tiene asignado un identificador en la intranet.'
            );
        }

        /*
         * La identidad SIEMPRE se lee de la URL cuando viene, valide o no.
         *
         * El interruptor `INTRANET_VALIDAR` sirve para no depender de los
         * permisos mientras se desarrolla, no para fingir que siempre entra
         * la misma persona: con él apagado, abrir la aplicación desde la
         * intranet con otro usuario seguía mostrando al de pruebas, que es
         * justo lo contrario de lo que hace falta para probar.
         */
        $usuarioUrl = null;

        if (isset($_GET['user']) || isset($_GET['idapp'])) {
            [$usuarioUrl, $idAppUrl] = self::leerDeLaUrl($validando);

            if ($validando && $idAppUrl !== $idApp) {
                throw new AccesoDenegado('otra-app', 'El enlace no corresponde a esta aplicación.');
            }
        }

        if (!$validando) {
            // Orden: lo que traiga la URL, lo que hubiera en la sesión, y por
            // último el usuario de pruebas del .env
            $usuario = $usuarioUrl
                ?? (string) ($_SESSION['intranet']['usuario'] ?? '')
                ?: intranet_usuario_de_pruebas();

            self::guardarIdentidad($usuario, $idApp, [
                'crear' => true, 'editar' => true, 'anular' => true, 'visualizar' => true,
            ]);

            return self::$actual = self::deLaSesion($idApp, true);
        }

        if ($usuarioUrl !== null) {
            self::validarYGuardar($usuarioUrl, $idApp);
        }

        return self::$actual = self::deLaSesion($idApp, false);
    }

    /**
     * Entrada de los endpoints. NO acepta parámetros de la URL: para entonces
     * la identidad ya tiene que estar validada en la sesión.
     *
     * @throws AccesoDenegado
     */
    public static function continuar(): self
    {
        self::iniciarSesionPhp();

        $validando = intranet_validando();

        if (!$validando && !isset($_SESSION['intranet'])) {
            // Se llamó a un endpoint sin haber abierto la pantalla; con las
            // validaciones apagadas eso no debe estorbar
            self::guardarIdentidad(intranet_usuario_de_pruebas(), intranet_id_app(), [
                'crear' => true, 'editar' => true, 'anular' => true, 'visualizar' => true,
            ]);
        }

        return self::$actual = self::deLaSesion(intranet_id_app(), !$validando);
    }

    /**
     * Una sesión inventada, para los archivos de `pruebas/`.
     *
     * Es explícita a propósito: la simulación se pide, no se hereda.
     */
    public static function simular(string $usuario = 'PRUEBAS', string $nombre = 'Usuario de pruebas'): self
    {
        return self::$actual = new self(
            usuario:   $usuario,
            nombre:    $nombre,
            imagen:    '',
            iniciales: self::iniciales($nombre),
            permisos:  ['crear' => true, 'editar' => true, 'anular' => true, 'visualizar' => true],
            simulada:  true,
        );
    }

    /** La sesión de esta petición. Las vistas la piden por aquí. */
    public static function actual(): self
    {
        if (self::$actual === null) {
            throw new RuntimeException('No se ha resuelto la sesión antes de usarla.');
        }

        return self::$actual;
    }

    // -------------------------------------------------------------- consulta

    /** ¿Puede el usuario hacer esto? ('crear', 'editar', 'anular', 'visualizar') */
    public function puede(string $accion): bool
    {
        return $this->permisos[$accion] ?? false;
    }

    /** El enlace de vuelta a esta aplicación, con sus credenciales. */
    public static function enlaceDeRegreso(): string
    {
        $usuario = $_SESSION['user'] ?? '';
        $idapp   = $_SESSION['idapp'] ?? '';

        if ($usuario === '' || $idapp === '') {
            return 'index.php';
        }

        return 'index.php?user=' . rawurlencode((string) $usuario)
            . '&idapp=' . rawurlencode((string) $idapp);
    }

    // -------------------------------------------------------------- internas

    private static function iniciarSesionPhp(): void
    {
        if (session_status() === PHP_SESSION_ACTIVE) {
            return;
        }

        // La cookie de sesión no la necesita ningún JavaScript ni ningún
        // tercero: fuera del alcance del script y fuera de peticiones cruzadas
        session_set_cookie_params([
            'httponly' => true,
            'samesite' => 'Lax',
            'secure'   => !empty($_SERVER['HTTPS']),
        ]);

        session_start();
    }

    /**
     * Usuario e id de aplicación de la URL, ya descodificados y comprobados.
     *
     * @return array{0:string,1:int}
     * @throws AccesoDenegado
     */
    private static function leerDeLaUrl(bool $estricto): array
    {
        $fallo = static function (bool $estricto): ?array {
            if ($estricto) {
                throw new AccesoDenegado('sin-datos', 'El enlace de acceso no es válido.');
            }

            return null;   // sin validar, un enlace raro simplemente se ignora
        };

        // strict: un base64 mal formado devuelve false en vez de basura
        $usuario = base64_decode((string) ($_GET['user'] ?? ''), true);
        $idapp   = base64_decode((string) ($_GET['idapp'] ?? ''), true);

        if ($usuario === false || $idapp === false) {
            return $fallo($estricto) ?? [null, 0];
        }

        $usuario = strtoupper(trim($usuario));
        $idapp   = trim($idapp);

        // Los usuarios de la intranet son `varchar(30)` alfanuméricos
        if (preg_match('/^[A-Z0-9._-]{1,30}$/', $usuario) !== 1) {
            return $fallo($estricto) ?? [null, 0];
        }

        if (preg_match('/^\d{1,10}$/', $idapp) !== 1) {
            return $fallo($estricto) ?? [null, 0];
        }

        return [$usuario, (int) $idapp];
    }

    /**
     * Deja la identidad en la sesión: usuario, aplicación, perfil y permisos.
     *
     * El perfil se vuelve a pedir cada vez que cambia el usuario, no se hereda
     * de la sesión anterior.
     *
     * @param array{crear:bool,editar:bool,anular:bool,visualizar:bool} $permisos
     */
    private static function guardarIdentidad(string $usuario, int $idApp, array $permisos): void
    {
        $yaEstaba = (string) ($_SESSION['intranet']['usuario'] ?? '');
        $mismo    = $yaEstaba === $usuario;

        // Sólo se rehace el identificador de sesión cuando cambia la persona
        if (!$mismo) {
            session_regenerate_id(true);
        }

        /*
         * El perfil se guarda en la sesión para no pedirlo en cada pantalla:
         * la base de la intranet puede estar en otro servidor y el nombre no
         * cambia entre una carga y la siguiente.
         *
         * Pero sólo se reaprovecha si lo guardado es un perfil DE VERDAD.
         *
         * Cuando `perfil()` no puede leer —la base caída, el puerto mal
         * puesto— devuelve un respaldo: el propio código de usuario como
         * nombre y la foto vacía. Antes aquí sólo se miraba que el nombre no
         * estuviera en blanco, y ese respaldo no lo está: la sesión se
         * quedaba pegada a «CFLORES / CFLORES» y, aunque la base volviera,
         * no se volvía a preguntar nunca. Reconocer la firma del respaldo
         * hace que se repare solo en la siguiente carga.
         */
        $guardado   = $_SESSION['intranet'] ?? [];
        $nombreYa   = (string) ($guardado['nombre'] ?? '');
        $imagenYa   = (string) ($guardado['imagen'] ?? '');
        $esRespaldo = $nombreYa === '' || ($nombreYa === $usuario && $imagenYa === '');
        $alDia      = (int) ($guardado['perfilV'] ?? 0) === self::VERSION_PERFIL;

        $perfil = $mismo && !$esRespaldo && $alDia
            ? ['nombre' => $nombreYa, 'imagen' => $imagenYa]
            : ModeloIntranet::perfil($usuario);

        $_SESSION['intranet'] = [
            'usuario'  => $usuario,
            'idapp'    => $idApp,
            'nombre'   => $perfil['nombre'],
            'imagen'   => $perfil['imagen'],
            'permisos' => $permisos,
            'perfilV'  => self::VERSION_PERFIL,
        ];
    }

    /**
     * Comprueba el permiso contra la intranet y deja la identidad en la sesión.
     *
     * @throws AccesoDenegado
     */
    private static function validarYGuardar(string $usuario, int $idApp): void
    {
        /*
         * Si el enlace presenta a OTRA persona, la sesión que hubiera deja de
         * valer ahora mismo, antes de saber si la nueva pasa o no.
         *
         * Sin esto quedaba un flanco: entra A, luego llega un enlace de B, a B
         * se le deniega… y la sesión de A sigue viva, así que basta con quitar
         * los parámetros de la URL para seguir trabajando como A. El intento
         * fallido de B no debe dejar la puerta de A abierta.
         */
        if ((string) ($_SESSION['intranet']['usuario'] ?? '') !== $usuario) {
            unset($_SESSION['intranet'], $_SESSION['user'], $_SESSION['idapp']);
        }

        if (!ModeloIntranet::tienePermiso($usuario, $idApp)) {
            error_log('[intranet] Acceso denegado a ' . $usuario . ' en la app ' . $idApp);

            throw new AccesoDenegado(
                'sin-permiso',
                'No tiene concedida esta aplicación. Solicítela al administrador de la intranet.'
            );
        }

        self::guardarIdentidad($usuario, $idApp, ModeloIntranet::permisosEspeciales($usuario, $idApp));

        // Los valores tal como llegaron, sólo para rehacer el enlace de vuelta
        $_SESSION['user']  = (string) ($_GET['user'] ?? '');
        $_SESSION['idapp'] = (string) ($_GET['idapp'] ?? '');
    }

    /**
     * Reconstruye la sesión ya validada.
     *
     * @throws AccesoDenegado
     */
    private static function deLaSesion(int $idApp, bool $simulada): self
    {
        $guardada = $_SESSION['intranet'] ?? null;

        if (!is_array($guardada) || ($guardada['usuario'] ?? '') === '') {
            throw new AccesoDenegado('sin-sesion', 'Entre a esta aplicación desde la intranet.');
        }

        // Una sesión abierta para otra aplicación no vale para ésta. Sin
        // validar no se comprueba: ahí el id puede ni estar configurado.
        if (!$simulada && (int) ($guardada['idapp'] ?? 0) !== $idApp) {
            throw new AccesoDenegado('otra-app', 'Entre a esta aplicación desde la intranet.');
        }

        $nombre = (string) ($guardada['nombre'] ?? $guardada['usuario']);

        return new self(
            usuario:   (string) $guardada['usuario'],
            nombre:    $nombre,
            imagen:    (string) ($guardada['imagen'] ?? ''),
            iniciales: self::iniciales($nombre),
            permisos:  is_array($guardada['permisos'] ?? null)
                ? $guardada['permisos']
                : ['crear' => false, 'editar' => false, 'anular' => false, 'visualizar' => false],
            simulada:  $simulada,
        );
    }

    /** Las dos primeras iniciales del nombre, para cuando no hay foto. */
    private static function iniciales(string $nombre): string
    {
        $palabras = preg_split('/\s+/', trim($nombre), -1, PREG_SPLIT_NO_EMPTY) ?: [];
        $letras   = '';

        foreach (array_slice($palabras, 0, 2) as $palabra) {
            $letras .= mb_strtoupper(mb_substr($palabra, 0, 1));
        }

        return $letras !== '' ? $letras : '?';
    }
}
