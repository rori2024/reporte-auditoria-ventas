<?php

declare(strict_types=1);

/**
 * Base de los modelos que consultan el AS400.
 *
 * Aporta dos cosas que todos necesitan: resolver el nombre real de un archivo
 * a partir del mapa de bibliotecas, y ejecutar una consulta devolviendo las
 * filas ya materializadas.
 *
 * Las filas se devuelven con índices NUMÉRICOS, no asociativos. No es pereza:
 * en cuanto una consulta selecciona expresiones sin alias —concatenaciones
 * con `||`, un `CASE`, un `MIN()`— el nombre que el driver les inventa no es
 * estable entre versiones. Los programas de los que se migra también leen los
 * campos por posición, así que mantener la posición es además la forma de
 * comprobar que la migración dice lo mismo que el programa viejo. Cada modelo
 * traduce esas posiciones a nombres en cuanto las recibe.
 */

require_once __DIR__ . '/../config/as400.php';
require_once __DIR__ . '/../config/librerias.php';
require_once __DIR__ . '/../config/texto.php';

abstract class ModeloAS400
{
    /**
     * Nombre completo BIBLIOTECA.ARCHIVO de un alias del mapa de bibliotecas.
     *
     * Falla ruidosamente si el alias no está declarado. La alternativa —dejar
     * el nombre vacío— produce un SQL sintácticamente roto y un mensaje del
     * AS400 que no menciona la causa real.
     */
    protected static function archivo(string $alias): string
    {
        global $archivos;

        if (!isset($archivos[$alias]) || trim((string) $archivos[$alias]) === '') {
            throw new RuntimeException(
                'El archivo ' . $alias . ' no está declarado en el mapa de bibliotecas '
                . '(config/librerias.txt o config/libreriasDevs.txt).'
            );
        }

        return trim((string) $archivos[$alias]);
    }

    /**
     * Varios alias de una vez, para no repetir la llamada en cada consulta.
     *
     * @param  string[] $alias
     * @return array<string,string> alias => BIBLIOTECA.ARCHIVO
     */
    protected static function archivos(array $alias): array
    {
        $mapa = [];

        foreach ($alias as $uno) {
            $mapa[$uno] = self::archivo($uno);
        }

        return $mapa;
    }

    /**
     * Un texto listo para incrustar en el SQL, entre comillas simples.
     *
     * Las tres consultas dependientes —taller, forros y ancho— arman sus
     * filtros así y no con marcadores `?`, porque es lo que hace el VB6 y
     * porque con marcadores el ancho venía NULL: el driver manda el parámetro
     * como carácter y la comparación contra una columna numérica del AS400 no
     * encuentra nada, sin dar error. No hay riesgo de inyección: estos valores
     * no los escribe nadie, los devuelve el propio AS400 en una consulta
     * anterior. Aun así se duplica la comilla, que es como DB2 la escapa.
     */
    protected static function literalTexto(string $valor): string
    {
        return "'" . str_replace("'", "''", $valor) . "'";
    }

    /**
     * Un número listo para incrustar en el SQL, sin comillas.
     *
     * Si lo que llega no es un número se corta aquí con un mensaje claro, en
     * lugar de dejar que se cuele en el SQL y el AS400 conteste con un error
     * de sintaxis que no dice de dónde salió.
     */
    protected static function literalNumero(string $valor, string $campo): string
    {
        $limpio = trim($valor);

        if (!preg_match('/^-?\d+(\.\d+)?$/', $limpio)) {
            throw new RuntimeException(
                'El valor de ' . $campo . ' no es numérico: "' . $limpio . '".'
            );
        }

        return $limpio;
    }

    /**
     * Ejecuta una consulta y devuelve todas sus filas.
     *
     * Los parámetros van con marcadores `?`. Las consultas se filtran por
     * datos que escribe el usuario, y los programas de los que se migra los
     * concatenaban directamente en el SQL.
     *
     * Los campos CHAR del AS400 vienen rellenos con espacios hasta su longitud
     * declarada. Se recortan por la derecha al leerlos, que es lo que hacía el
     * `Trim()` del VB6 — pero aquí de forma uniforme, no campo por campo.
     *
     * Y se pasan a UTF-8: el driver los entrega en la página ANSI de Windows,
     * y un solo acento sin convertir basta para que `json_encode()` falle y la
     * respuesta salga vacía. Ver config/texto.php.
     *
     * @param  list<scalar> $parametros
     * @return list<array<int,string|null>>
     */
    protected static function filas(string $sql, array $parametros = []): array
    {
        $sentencia = self::ejecutar($sql, $parametros);

        $columnas = odbc_num_fields($sentencia);
        $filas    = [];

        while (odbc_fetch_row($sentencia)) {
            $fila = [];

            for ($i = 1; $i <= $columnas; $i++) {
                $valor = odbc_result($sentencia, $i);
                // odbc_result devuelve false cuando el campo es NULL
                $fila[$i - 1] = ($valor === false || $valor === null)
                    ? null
                    : as400_a_utf8(rtrim((string) $valor));
            }

            $filas[] = $fila;
        }

        odbc_free_result($sentencia);

        return $filas;
    }

    /**
     * Prepara y ejecuta, devolviendo la sentencia lista para recorrer.
     *
     * Los mensajes del driver también llegan en ANSI —"Anomal\xEDa de enlace"—
     * así que se convierten antes de meterlos en una excepción: si acaban en
     * una respuesta JSON sin convertir, la rompen igual que un dato.
     *
     * @param  list<scalar> $parametros
     * @return resource|object
     */
    private static function ejecutar(string $sql, array $parametros)
    {
        global $dbconect;

        if (!$dbconect) {
            throw new RuntimeException('No hay conexión abierta con el AS400.');
        }

        $sentencia = @odbc_prepare($dbconect, $sql);

        if ($sentencia === false) {
            throw new RuntimeException(
                'El AS400 rechazó la consulta: ' . as400_a_utf8(odbc_errormsg($dbconect))
            );
        }

        if (!@odbc_execute($sentencia, $parametros)) {
            throw new RuntimeException(
                'Fallo al ejecutar la consulta en el AS400: ' . as400_a_utf8(odbc_errormsg($dbconect))
            );
        }

        return $sentencia;
    }

    /**
     * Igual que filas(), pero devolviendo cada fila por NOMBRE de columna.
     *
     * Sólo para los dos combos, que en el VB6 se leían así (`ds!COD_DESTINO`).
     * Ahí los nombres sí son estables porque son columnas reales del archivo,
     * no expresiones calculadas.
     *
     * @param  list<scalar> $parametros
     * @return list<array<string,string|null>>
     */
    protected static function filasPorNombre(string $sql, array $parametros = []): array
    {
        $sentencia = self::ejecutar($sql, $parametros);

        $filas = [];

        while ($fila = odbc_fetch_array($sentencia)) {
            $limpia = [];

            foreach ($fila as $columna => $valor) {
                $limpia[strtoupper(trim((string) $columna))] = $valor === null
                    ? null
                    : as400_a_utf8(rtrim((string) $valor));
            }

            $filas[] = $limpia;
        }

        odbc_free_result($sentencia);

        return $filas;
    }

    /**
     * La primera fila de una consulta, o null si no hay ninguna.
     *
     * @param  list<scalar> $parametros
     * @return array<int,string|null>|null
     */
    protected static function primeraFila(string $sql, array $parametros = []): ?array
    {
        $filas = self::filas($sql, $parametros);

        return $filas[0] ?? null;
    }
}
