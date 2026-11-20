/* =========================================================================
   LOADER RORI
   ---------------------------------------------------------------------------
   Un sitio para el marcado del loader, en vez de las ocho copias literales
   que había repartidas por `gestion-data.js` en roriApp. Copiado a mano,
   cambiarle una palabra obligaba a encontrarlas todas y siempre quedaba
   alguna atrás.

   El marcado y el diseño son los de siempre: esto no cambia cómo se ve,
   sólo deja de repetirlo. Ver `vistas/css/style-loader.css`.

   Cuándo usarlo: esperas largas de pantalla o de panel. En esta aplicación
   son dos, y están medidas:

     · `?m=agente`  la respuesta de VERA, entre 13 y 98 segundos
     · `?m=etl`     correr la cadena del AS400, minutos

   Y donde NO: los `guardar-…php` de `php/carga/` contestan en décimas y
   cada uno apaga su botón mientras va. Lo mismo el correo del día (`?m=correo`),
   que se arma en el servidor en menos de un segundo. El loader grande en una
   espera corta lo abarata y deja de significar «esto va a tardar».

       // Al pintar una plantilla
       contenedor.innerHTML = `... ${loaderRori()} ...`;

       // Con texto propio y sin `id` —uno por fila, como en el hilo de VERA—
       caja.innerHTML = loaderRori('pensando...!', { id: '', oculto: false });

       // Mostrar y ocultar
       loaderRori.mostrar('corriendo facturas...!', 'loaderEtl');
       loaderRori.ocultar('loaderEtl');
   ========================================================================= */

(function (global) {
    'use strict';

    /*
     * ESCAPAR, Y DE VERDAD
     * --------------------
     * El original se apoya en el `esc` global de roriApp y, si no lo
     * encuentra, hacía `String(v)` a secas: devolvía el texto tal cual para
     * meterlo en un `innerHTML`.
     *
     * Esta aplicación NO tiene ningún `esc` global —su JS pinta todo con
     * `textContent`—, así que ese respaldo no era el raro: era el único
     * camino, y el loader no escapaba nada. Con los textos fijos de ahora no
     * se nota; el día que alguien le pase el mensaje de un servidor o el
     * nombre de un archivo, se nota mucho y tarde.
     *
     * Las comillas se escapan también, no sólo `& < >`: el `id` se pinta
     * dentro de un atributo y un `"` lo partiría en dos.
     *
     * Si un día esta hoja vuelve a un proyecto que sí tiene `esc` global,
     * sigue mandando el del proyecto.
     */
    const propio = (v) => String(v === null || v === undefined ? '' : v)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');

    const esc = (v) => (typeof global.esc === 'function' ? global.esc(v) : propio(v));

    const POR_DEFECTO = 'por favor espere...!';

    /**
     * El marcado del loader, letra por letra igual que el original.
     *
     * @param {string} [texto]  lo que se lee debajo de las letras
     * @param {object} [o]
     * @param {string} [o.id]       id del contenedor; `loader` por omisión,
     *                              que es el que buscan los módulos de siempre
     * @param {boolean} [o.oculto]  nace escondido y se enseña al empezar
     */
    function loaderRori(texto, o) {
        const op = o || {};
        const id = op.id === undefined ? 'loader' : op.id;

        return `
        <div ${id ? `id="${esc(id)}" ` : ''}`
            + `class="loader-container${op.oculto === false ? '' : ' hidden'}"
             role="status" aria-live="polite">
            <div class="loader loader-1" aria-hidden="true">
                <div class="tildes">''</div>
                <span>R</span>
                <span>O</span>
                <span>R</span>
                <span>I</span>
            </div>
            <div class="loader-text">${esc(texto || POR_DEFECTO)}</div>
        </div>`;
    }

    /**
     * Enseña el loader y, si se le da, le cambia el texto.
     *
     * El texto es lo que convierte una espera en una explicación: «Grabando
     * RTP325…» dice qué se está haciendo; una rueda girando, no.
     */
    loaderRori.mostrar = function (texto, id) {
        const caja = document.getElementById(id || 'loader');
        if (!caja) return;

        if (texto) {
            const linea = caja.querySelector('.loader-text');
            if (linea) linea.textContent = texto;
        }

        caja.classList.remove('hidden');
    };

    /** Lo esconde y devuelve el texto a lo de siempre. */
    loaderRori.ocultar = function (id) {
        const caja = document.getElementById(id || 'loader');
        if (!caja) return;

        caja.classList.add('hidden');

        const linea = caja.querySelector('.loader-text');
        if (linea) linea.textContent = POR_DEFECTO;
    };

    global.loaderRori = loaderRori;
})(window);
