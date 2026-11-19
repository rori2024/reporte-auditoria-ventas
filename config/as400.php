<?php

/**
 * Conexión ODBC con el AS400.
 *
 * Las credenciales y la dirección salen del .env, como las de MySQL.
 *
 * Al fallar se lanza una excepción, no se redirige: estas funciones se llaman
 * desde endpoints JSON, y el `header("Location: errorAS400.php")` anterior
 * devolvía un 302 hacia un archivo que no existe. El navegador recibía HTML
 * donde esperaba JSON y el módulo se quedaba colgado sin decir por qué.
 */

require_once __DIR__ . '/env.php';
require_once __DIR__ . '/bitacora.php';
require_once __DIR__ . '/texto.php';

global $dbconect;

/**
 * Abre la conexión con el AS400 y la deja en el global $dbconect.
 *
 * @throws RuntimeException si no se puede conectar
 */
function CONECTARAS400()
{
	global $dbconect;

	/*
	 * Sin valores por defecto, y es a propósito.
	 *
	 * Antes llevaban el usuario y la clave reales como segundo argumento de
	 * `env()`: la credencial escrita en el código, es decir, publicada en el
	 * repositorio aunque el `.env` no se suba. Un valor por omisión para una
	 * contraseña no es una comodidad, es una filtración. (Y no se repite aquí
	 * ni como ejemplo, por el mismo motivo.)
	 *
	 * Además, con el valor por defecto puesto, un `.env` mal leído no se
	 * notaba: la aplicación conectaba igual y nadie se enteraba de que la
	 * configuración no se estaba aplicando. Ahora falta la clave y se dice.
	 */
	$user   = (string) env('AS400_USER', '');
	$pass   = (string) env('AS400_PASS', '');
	$ip     = (string) env('AS400_HOST', '');
	$driver = env('AS400_DRIVER', 'Client Access ODBC Driver (32-bit)');

	if ($user === '' || $pass === '' || $ip === '') {
		error_log('[as400] Faltan AS400_HOST, AS400_USER o AS400_PASS en el .env.');

		throw new RuntimeException(
			'La conexión con el AS400 no está configurada. Revise el archivo .env.'
		);
	}

	if (!function_exists('odbc_connect')) {
		error_log('[as400] La extensión ODBC de PHP no está habilitada.');

		/*
		 * Al registro de eventos, NO al de críticos.
		 *
		 * Sin AS400 la tienda sigue vendiendo: se factura, se imprime y se
		 * cobra igual. Lo que no se puede es descargar catálogos ni subir lo
		 * del día, y eso se hace al final de la jornada. Meterlo entre lo
		 * crítico haría que esa tabla dejara de significar «la tienda está
		 * parada», que es justo para lo que sirve.
		 */
		if (function_exists('bitacora_evento')) {
			bitacora_evento('AS400_SIN_ODBC',
				'La extensión ODBC de PHP no está habilitada en este equipo.', [
					'modulo' => 'AS400',
					'accion' => 'conectar',
					'nivel'  => 'ERROR',
				]);
		}

		throw new RuntimeException('El servidor no tiene habilitada la conexión con el AS400.');
	}

	//	Driver de Conexion
	$dsn = "Driver={" . $driver . "};System=" . $ip . ";Uid=" . $user . ";Pwd=" . $pass . ";";

	//	Conexion
	$dbconect = @odbc_connect($dsn, $user, $pass);

	if (!$dbconect) {
		// El driver contesta en ANSI: sin convertir, el registro guarda
		// "Anomal\xEDa de enlace" y se vuelve ilegible
		$motivo = (string) as400_a_utf8(odbc_errormsg());
		error_log('[as400] No se pudo conectar con ' . $ip . ': ' . $motivo);

		// La contraseña NO entra aquí: va en el DSN, y una bitácora que guarda
		// credenciales es un problema nuevo, no un registro.
		if (function_exists('bitacora_evento')) {
			bitacora_evento('AS400_SIN_CONEXION',
				'No se pudo conectar con el AS400 en ' . $ip . ': ' . trim($motivo), [
					'modulo' => 'AS400',
					'accion' => 'conectar',
					'nivel'  => 'ERROR',
					'extra'  => [
						'servidor'   => $ip,
						'usuario'    => $user,
						'driver'     => $driver,
						'librerias'  => env('AS400_LIBRERIAS', 'desarrollo'),
					],
				]);
		}

		throw new RuntimeException('No se pudo conectar con el servidor AS400. Compruebe la red e inténtelo de nuevo.');
	}

	return $dbconect;
}

/**
 * Cierra la conexión si está abierta. Es seguro llamarla dos veces, por eso
 * puede ir en un `finally`.
 */
function DESCONECTARAS400()
{
	global $dbconect;

	if ($dbconect) {
		@odbc_close($dbconect);
		$dbconect = null;
	}
}
