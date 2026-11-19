<?php

declare(strict_types=1);

/**
 * Conversión del texto que llega del AS400.
 *
 * El driver de iSeries Access entrega las cadenas en la página de códigos
 * ANSI de Windows, no en UTF-8: un "í" viaja como el byte 0xED. Se ve incluso
 * en sus propios mensajes de error, que llegan como "Anomal\xEDa de enlace".
 *
 * Eso no es un detalle estético. `json_encode()` RECHAZA un texto que no sea
 * UTF-8 válido: devuelve `false`, y un `echo false` imprime cero bytes. El
 * navegador recibe entonces una respuesta vacía y falla con "Unexpected end of
 * JSON input", sin rastro de cuál era el problema real. Por eso la conversión
 * se hace aquí, en la frontera, y no cuando ya es tarde.
 *
 * Se convierte desde Windows-1252 y no desde ISO-8859-1 porque es lo que
 * manda el driver en un Windows en español: 1252 es un superconjunto de
 * 8859-1 y además cubre las comillas y guiones que el AS400 arrastra en
 * algunas descripciones.
 */

/**
 * Devuelve el texto en UTF-8.
 *
 * Lo que ya es UTF-8 válido se deja intacto —el ASCII puro lo es, así que la
 * inmensa mayoría de los campos no se tocan— y sólo se convierte lo que no lo
 * es. Así la función es idempotente y da igual llamarla de más.
 */
function as400_a_utf8(?string $texto): ?string
{
    if ($texto === null || $texto === '') {
        return $texto;
    }

    if (mb_check_encoding($texto, 'UTF-8')) {
        return $texto;
    }

    $convertido = @mb_convert_encoding($texto, 'UTF-8', 'Windows-1252');

    /*
     * Si ni así sale, se sustituyen los bytes imposibles en vez de devolver
     * algo que volvería a romper json_encode. Un carácter raro en una
     * descripción es un defecto menor; una pantalla en blanco, no.
     */
    if ($convertido === false || !mb_check_encoding($convertido, 'UTF-8')) {
        return mb_convert_encoding($texto, 'UTF-8', 'UTF-8');
    }

    return $convertido;
}

/**
 * Devuelve el texto en la página de códigos que espera el AS400.
 *
 * Es la inversa de `as400_a_utf8()`, y hace falta porque esta aplicación no
 * sólo lee: graba `ONBSAS` —el nombre de la sastrería— en `OMP012`. Un nombre
 * con tilde escrito en UTF-8 ocupa dos bytes donde el archivo espera uno, así
 * que entra partido: "Sastrería" se guarda como "SastrerÃ­a" y ya no coincide
 * con el de la tabla de donde salió. El fallo no da error, sólo deja el dato
 * mal, que es peor.
 *
 * Se convierte a Windows-1252 por el mismo motivo que se lee desde ahí: es lo
 * que maneja el driver de iSeries Access en un Windows en español, y cubre las
 * comillas y guiones que el AS400 arrastra en algunas descripciones.
 *
 * Lo que no sea UTF-8 válido se devuelve tal cual: o ya está en la página de
 * destino, o convertirlo otra vez lo rompería. Igual que su pareja, da igual
 * llamarla de más.
 *
 * OJO: esto arregla la codificación, no el contenido. Lo que se graba en un
 * campo de texto del AS400 debe salir del propio AS400 (se manda el código, se
 * busca el nombre y se graba el que devuelve), no de lo que escriba el
 * navegador. Esta función es la última red, no la primera.
 */
function utf8_a_as400(?string $texto): ?string
{
    if ($texto === null || $texto === '') {
        return $texto;
    }

    if (!mb_check_encoding($texto, 'UTF-8')) {
        return $texto;
    }

    $convertido = @mb_convert_encoding($texto, 'Windows-1252', 'UTF-8');

    /*
     * Un carácter que no exista en 1252 —una comilla de otro alfabeto pegada
     * desde cualquier sitio— sale como "?". Se pierde ese carácter, no el
     * campo entero ni la operación.
     */
    return $convertido === false ? $texto : $convertido;
}
