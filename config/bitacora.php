<?php

declare(strict_types=1);

/**
 * La bitácora del sistema: lo que pasó, dónde queda escrito y por qué ahí.
 *
 * Hay tres tablas y no una, porque no todos los sucesos se miran en el mismo
 * momento ni por la misma razón:
 *
 *   logs_acceso            quién entró, quién lo intentó y falló. Se mira
 *                          cuando se sospecha de un acceso o hay que saber
 *                          quién estaba en la caja a las once.
 *
 *   logs_eventos_criticos  lo que IMPIDE trabajar: sin base de datos, sin
 *                          permisos, un error que corta la petición. Si esta
 *                          tabla tiene filas de hoy, la tienda está parada.
 *
 *   logs_registro_eventos  lo que salió mal y NO detuvo nada: el AS400 que no
 *                          contesta, una descarga que vuelve vacía. La tienda
 *                          sigue vendiendo; esto se revisa al día siguiente.
 *
 * Las tres existían ya: las escribe el sistema de Visual Basic desde hace
 * años. Aquí se escriben con el MISMO formato para que el historial de un
 * equipo sea uno solo y no dos mitades que hay que cruzar a mano.
 *
 * ---------------------------------------------------------------------------
 * REGLA DE ORO: LA BITÁCORA NO PUEDE TUMBAR LA APLICACIÓN
 *
 * Todo lo de aquí traga sus propios errores. Un registro que falla se pierde;
 * una venta que se cae porque no se pudo registrar algo es un problema mucho
 * peor que la línea que falta.
 *
 * Y por eso todo se escribe TAMBIÉN en `logs/seguridad.log`, que es un
 * archivo: el día que la base no esté —que es justo cuando más importa saber
 * qué pasó— la tabla no se puede escribir, y el archivo sí.
 */

require_once __DIR__ . '/env.php';

/** Los niveles, de menos a más grave. Los mismos que usa el Visual Basic. */
const BITACORA_NIVELES = ['INFO', 'AVISO', 'ERROR', 'CRITICO'];

/**
 * La conexión para escribir la bitácora, o null si no se puede.
 *
 * No usa `Conexion::getInstance()` a propósito. Un evento crítico es muchas
 * veces «no hay base de datos», y pedirle la conexión al singleton que acaba
 * de fallar volvería a lanzar la misma excepción dentro del manejador de
 * errores. Aquí se intenta una vez, en silencio, y si no sale se sigue.
 */
function bitacora_conexion(): ?mysqli
{
    static $db = null;
    static $intentado = false;

    if ($intentado) {
        return $db;
    }

    $intentado = true;

    // Si la aplicación ya tiene una conexión viva, se aprovecha: abrir otra
    // por cada registro sería pagar un saludo TCP por línea escrita.
    if (class_exists('Conexion', false)) {
        try {
            $db = Conexion::getInstance()->getConnection();

            return $db;
        } catch (Throwable $e) {
            // Sigue abajo: se intenta por cuenta propia
        }
    }

    /*
     * No se toca `mysqli_report()`.
     *
     * La tentación es apagarlo aquí y restaurarlo después, pero en PHP 8 esa
     * función devuelve `true`, no el modo que había: restaurarlo con lo que
     * devuelve dejaría el modo global en MYSQLI_REPORT_ERROR para el resto de
     * la petición, y la aplicación entera cambiaría de comportamiento por
     * culpa de una línea de bitácora.
     *
     * Con el modo estricto que pone `database.php`, el constructor lanza en
     * vez de devolver un objeto roto — y para eso está el `catch`.
     */
    try {
        $propia = @new mysqli(
            (string) env('DB_HOST', 'localhost'),
            (string) env('DB_USER', ''),
            (string) (env('DB_PASS', '') ?? ''),
            (string) env('DB_NAME', 'rori'),
            env_entero('DB_PORT', 3306, 1, 65535)
        );

        $db = $propia->connect_error ? null : $propia;
    } catch (Throwable $e) {
        $db = null;
    }

    return $db;
}

/**
 * ¿Está encendido el guardado de esta bitácora?
 *
 * Las cuatro preferencias viven en CONFIGURACION_APP y se cambian desde
 * Configuración › Bitácoras, con permiso de administrador.
 *
 * Tres decisiones que no son obvias:
 *
 *   1. Se leen UNA VEZ por petición. Sin esto, cada línea de bitácora
 *      costaría una consulta más, y en una caja que trabaja contra el
 *      servidor de la tienda eso es una ida y vuelta por la red.
 *
 *   2. Si no se pueden leer —no hay base, la tabla no existe— se asume que
 *      están ENCENDIDAS. El momento en que no se puede consultar la
 *      configuración es justo el momento en que más falta hace el registro;
 *      apagarlo por no poder preguntar sería perder la única pista.
 *
 *   3. El archivo `logs/seguridad.log` NO se apaga nunca. Estos interruptores
 *      deciden si la línea va a una tabla, no si se deja constancia. Un
 *      sistema del que no queda rastro en ningún sitio no es una opción que
 *      esta aplicación deba ofrecer.
 */
function bitacora_activa(string $cual): bool
{
    static $prefs = null;

    if ($prefs === null) {
        $prefs = [];
        $db = bitacora_conexion();

        if ($db instanceof mysqli) {
            try {
                /*
                 * La de la tienda manda sobre la de la cadena (tienda 0). El
                 * ORDER BY asc + sobrescritura deja arriba la más específica,
                 * igual que hace `ctrParametrosVenta`.
                 */
                $r = @$db->query("SELECT clave, valor FROM configuracion_app
                                   WHERE clave LIKE 'logs.%'
                                   ORDER BY tienda ASC");

                while ($r && $fila = $r->fetch_assoc()) {
                    $prefs[(string) $fila['clave']] = (string) $fila['valor'] === '1';
                }
            } catch (Throwable $e) {
                $prefs = [];
            }
        }
    }

    return $prefs['logs.' . $cual] ?? true;
}

/** El equipo desde el que se hizo. Con varias cajas, saber cuál importa. */
function bitacora_estacion(): string
{
    $nombre = (string) (gethostname() ?: '');
    $caja = function_exists('seg_caja') ? seg_caja() : (int) env('CAJA', '1');

    return mb_substr(trim($nombre . ' · caja ' . $caja), 0, 100);
}

/**
 * Escribe en una de las dos tablas de eventos, que comparten esquema.
 *
 * @param string $tabla       logs_eventos_criticos o logs_registro_eventos
 * @param array  $d           tipo, modulo, accion, descripcion, nivel,
 *                            resultado, extra, referencia, tabla_referencia
 */
function bitacora_evento_en(string $tabla, array $d): void
{
    // La tabla no llega de fuera nunca, pero un nombre de tabla no se puede
    // enlazar como parámetro: se comprueba contra la lista y se acabó.
    if (!in_array($tabla, ['logs_eventos_criticos', 'logs_registro_eventos'], true)) {
        return;
    }

    $nivel = strtoupper((string) ($d['nivel'] ?? 'INFO'));

    if (!in_array($nivel, BITACORA_NIVELES, true)) {
        $nivel = 'INFO';
    }

    // Al archivo SIEMPRE, y primero: si la base no está, esto es lo único que
    // queda, y es justo el caso en que hace falta. El interruptor de más abajo
    // decide si además va a una tabla; nunca si queda constancia.
    if (function_exists('seg_registrar')) {
        seg_registrar('bitacora:' . $nivel, [
            'tabla'  => $tabla,
            'tipo'   => $d['tipo'] ?? '',
            'modulo' => $d['modulo'] ?? '',
            'que'    => mb_substr((string) ($d['descripcion'] ?? ''), 0, 300),
        ]);
    }

    if (!bitacora_activa($tabla === 'logs_eventos_criticos' ? 'criticos' : 'eventos')) {
        return;
    }

    $db = bitacora_conexion();

    if (!$db instanceof mysqli) {
        return;
    }

    try {
        $sql = "INSERT INTO `$tabla`
                    (fecha_evento, tipo_evento, modulo, accion, descripcion, usuario,
                     nivel, resultado, ip_origen, estacion_trabajo, datos_adicionales,
                     id_referencia, tabla_referencia)
                 VALUES (NOW(), ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)";

        $stmt = @$db->prepare($sql);

        if ($stmt === false) {
            return;
        }

        $tipo        = mb_substr((string) ($d['tipo'] ?? 'EVENTO'), 0, 50);
        $modulo      = mb_substr((string) ($d['modulo'] ?? 'roriApp'), 0, 50);
        $accion      = mb_substr((string) ($d['accion'] ?? ''), 0, 100);
        $descripcion = (string) ($d['descripcion'] ?? '');
        $usuario     = mb_substr((string) ($d['usuario'] ?? ($_SESSION['usuario'] ?? '')), 0, 50);
        $resultado   = mb_substr((string) ($d['resultado'] ?? 'FALLO'), 0, 20);
        $ip          = mb_substr(function_exists('seg_ipCliente') ? seg_ipCliente()
                            : (string) ($_SERVER['REMOTE_ADDR'] ?? ''), 0, 45);
        $estacion    = bitacora_estacion();
        $extra       = $d['extra'] ?? [];
        $extra       = is_array($extra)
            ? (string) json_encode($extra, JSON_UNESCAPED_UNICODE) : (string) $extra;
        $referencia  = (int) ($d['referencia'] ?? 0);
        $tablaRef    = mb_substr((string) ($d['tabla_referencia'] ?? ''), 0, 50);

        $stmt->bind_param('ssssssssssis',
            $tipo, $modulo, $accion, $descripcion, $usuario, $nivel,
            $resultado, $ip, $estacion, $extra, $referencia, $tablaRef);
        @$stmt->execute();
        $stmt->close();
    } catch (Throwable $e) {
        // Se pierde la línea, no la petición. Ver la regla de oro de arriba.
    }
}

/**
 * Algo IMPIDE trabajar: sin base, sin permisos, la petición se corta.
 *
 * Si esta tabla tiene filas de hoy, alguien en una tienda está mirando una
 * pantalla que no funciona.
 */
function bitacora_critico(string $tipo, string $descripcion, array $d = []): void
{
    bitacora_evento_en('logs_eventos_criticos', $d + [
        'tipo'        => $tipo,
        'descripcion' => $descripcion,
        'nivel'       => 'CRITICO',
        'resultado'   => 'FALLO',
    ]);
}

/**
 * Algo salió mal y la tienda SIGUE trabajando.
 *
 * El caso típico es el AS400: no contesta, y facturar no depende de él. Se
 * anota para mirarlo después, no para parar a nadie.
 */
function bitacora_evento(string $tipo, string $descripcion, array $d = []): void
{
    bitacora_evento_en('logs_registro_eventos', $d + [
        'tipo'        => $tipo,
        'descripcion' => $descripcion,
        'nivel'       => $d['nivel'] ?? 'AVISO',
        'resultado'   => $d['resultado'] ?? 'FALLO',
    ]);
}

/**
 * Quién entró, quién lo intentó y falló.
 *
 * `logs_acceso` es más estrecha que las otras dos —la heredamos así— y exige
 * un `usuario_id` numérico. En un intento fallido muchas veces no hay usuario
 * que valga: se escribe 0, y el nombre tecleado va al detalle, en
 * `logs_registro_eventos`. Sin eso, «alguien intentó entrar como admin
 * catorce veces» no se podría reconstruir.
 *
 * @param string $tipo     uno de los de la columna ENUM de la tabla
 * @param int    $usuarioId 0 si no se sabe
 */
function bitacora_acceso(string $tipo, int $usuarioId = 0, array $d = []): void
{
    $permitidos = ['login_exitoso', 'login_fallido', 'logout', 'bloqueo',
                   'desbloqueo', 'cambio_password', 'token_generado', 'token_usado'];

    if (!in_array($tipo, $permitidos, true)) {
        return;
    }

    if (function_exists('seg_registrar')) {
        seg_registrar('acceso:' . $tipo, $d);
    }

    if (!bitacora_activa('acceso')) {
        return;
    }

    $db = bitacora_conexion();

    if ($db instanceof mysqli) {
        try {
            $stmt = @$db->prepare('INSERT INTO logs_acceso
                        (usuario_id, usuario_nombre, tienda, tipo_evento,
                         ip_address, motivo, estacion_trabajo, fecha_evento)
                     VALUES (?, ?, ?, ?, ?, ?, ?, NOW())');

            if ($stmt !== false) {
                $ip = mb_substr(function_exists('seg_ipCliente') ? seg_ipCliente()
                        : (string) ($_SERVER['REMOTE_ADDR'] ?? ''), 0, 45);
                $nombre   = mb_substr((string) ($d['usuario'] ?? ''), 0, 60);
                $tienda   = (int) ($d['tienda'] ?? ($_SESSION['tienda'] ?? 0));
                $motivo   = mb_substr((string) ($d['motivo'] ?? ''), 0, 200);
                $estacion = bitacora_estacion();

                $stmt->bind_param('isissss',
                    $usuarioId, $nombre, $tienda, $tipo, $ip, $motivo, $estacion);
                @$stmt->execute();
                $stmt->close();
            }
        } catch (Throwable $e) {
            // Igual que arriba: la línea se pierde, la petición no
        }
    }

    /*
     * El detalle, aparte.
     *
     * `logs_acceso` sólo guarda id, tipo e IP: no cabe el usuario que se
     * tecleó ni el motivo. Un fallido sin eso no sirve para nada —no se sabe
     * si alguien se equivocó de tecla o si están probando contraseñas— así
     * que lo que importa va al registro de eventos.
     */
    if (str_ends_with($tipo, 'fallido') || $tipo === 'bloqueo') {
        bitacora_evento_en('logs_registro_eventos', [
            'tipo'        => strtoupper($tipo),
            'modulo'      => 'Acceso',
            'accion'      => (string) ($d['accion'] ?? 'login'),
            'descripcion' => (string) ($d['motivo'] ?? 'Intento de acceso rechazado'),
            'usuario'     => mb_substr((string) ($d['usuario'] ?? ''), 0, 50),
            'nivel'       => $tipo === 'bloqueo' ? 'ERROR' : 'AVISO',
            'resultado'   => 'FALLO',
            'extra'       => $d,
        ]);
    }
}
