<?php

declare(strict_types=1);

/**
 * Lector del archivo de entorno.
 *
 * La ruta es una constante única y explícita: así no hay forma de editar un
 * .env y estar leyendo otro (ver PHPDev.md §11.2). Si alguna vez hace falta
 * apuntar a otro archivo —pruebas, un segundo despliegue— se define ENV_FILE
 * antes de incluir este archivo.
 *
 * El .env NUNCA se sirve por web: el .htaccess de la raíz lo deniega.
 */

if (!defined('ENV_FILE')) {
    define('ENV_FILE', dirname(__DIR__) . DIRECTORY_SEPARATOR . '.env');
}

/**
 * Lee y cachea el archivo de entorno. Devuelve un mapa clave => valor.
 *
 * Formato aceptado, una pareja por línea:
 *   CLAVE=valor
 *   CLAVE="valor con espacios"
 *   # comentario
 *
 * Una clave sin signo igual se ignora en silencio; una contraseña vacía es un
 * valor válido (DB_PASS= significa sin contraseña, no "falta la clave").
 */
function env_cargar(): array
{
    static $valores = null;

    if ($valores !== null) {
        return $valores;
    }

    $valores = [];

    if (!is_readable(ENV_FILE)) {
        error_log('[env] No se puede leer el archivo de entorno: ' . ENV_FILE);
        return $valores;
    }

    $lineas = file(ENV_FILE, FILE_IGNORE_NEW_LINES | FILE_SKIP_EMPTY_LINES);
    if ($lineas === false) {
        error_log('[env] Fallo al leer el archivo de entorno: ' . ENV_FILE);
        return $valores;
    }

    foreach ($lineas as $i => $linea) {
        // Quitar el BOM que dejan algunos editores en la primera línea
        if ($i === 0) {
            $linea = preg_replace('/^\xEF\xBB\xBF/', '', $linea);
        }

        $linea = trim($linea);

        if ($linea === '' || $linea[0] === '#' || $linea[0] === ';') {
            continue;
        }

        $corte = strpos($linea, '=');
        if ($corte === false) {
            continue;
        }

        $clave = trim(substr($linea, 0, $corte));
        $valor = trim(substr($linea, $corte + 1));

        if ($clave === '') {
            continue;
        }

        // Valor entrecomillado: se quitan las comillas, no se recorta dentro
        $largo = strlen($valor);
        if ($largo >= 2
            && (($valor[0] === '"' && $valor[$largo - 1] === '"')
                || ($valor[0] === "'" && $valor[$largo - 1] === "'"))) {
            $valor = substr($valor, 1, -1);
        }

        $valores[$clave] = $valor;
    }

    return $valores;
}

/**
 * Devuelve un valor del entorno, o $porDefecto si no está declarado.
 */
function env(string $clave, ?string $porDefecto = null): ?string
{
    $valores = env_cargar();

    return array_key_exists($clave, $valores) ? $valores[$clave] : $porDefecto;
}

/**
 * Igual que env(), pero falla si la clave no está declarada.
 *
 * Se usa para lo que no tiene valor por defecto razonable: sin nombre de base
 * de datos no hay aplicación, y arrancar con uno inventado da un error mucho
 * más confuso que decirlo aquí.
 */
function env_requerido(string $clave): string
{
    $valores = env_cargar();

    if (!array_key_exists($clave, $valores) || $valores[$clave] === '') {
        error_log('[env] Falta la clave obligatoria ' . $clave . ' en ' . ENV_FILE);
        throw new RuntimeException('Configuración incompleta del servidor.');
    }

    return $valores[$clave];
}

/**
 * Valor de entorno interpretado como entero, acotado.
 */
function env_entero(string $clave, int $porDefecto, int $min, int $max): int
{
    $bruto = env($clave);

    if ($bruto === null || !preg_match('/^-?\d+$/', trim($bruto))) {
        return $porDefecto;
    }

    $n = (int) $bruto;

    return ($n < $min || $n > $max) ? $porDefecto : $n;
}

/**
 * Un interruptor del .env.
 *
 * Se aceptan las formas que la gente escribe de verdad: 1/0, si/no, true/false,
 * on/off. Cualquier otra cosa —incluida una clave ausente o con una errata— se
 * queda con el valor por omisión, que es el comportamiento de siempre: un
 * ajuste mal escrito no debe cambiar cómo funciona la caja sin avisar.
 */
function env_bool(string $clave, bool $porDefecto): bool
{
    $bruto = env($clave);

    if ($bruto === null) {
        return $porDefecto;
    }

    $v = strtolower(trim($bruto));

    if (in_array($v, ['1', 'si', 'sí', 'true', 'on', 'yes'], true)) {
        return true;
    }

    if (in_array($v, ['0', 'no', 'false', 'off'], true)) {
        return false;
    }

    return $porDefecto;
}
