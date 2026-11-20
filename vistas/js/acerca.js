/* ===========================================================================
 *  Ventana «Acerca de» — abrir, cerrar y teclado (DESIGN-SYSTEM.md §11)
 *
 *  No pide nada al servidor: el contenido ya está en el HTML de la página,
 *  oculto. Abre instantánea, y sigue abriendo si la red se cayó —que es
 *  justo cuando alguien la abre para buscar el teléfono del soporte—.
 *
 *  Si la capa no está en la página, este archivo no hace nada y se calla.
 *  No avisa por consola: `config/app.php` manda, y una aplicación que
 *  todavía no tiene la ventana no tiene por qué ensuciar la consola.
 * ======================================================================== */
(function () {
    'use strict';

    const capa = document.getElementById('acerca');
    if (capa === null) {
        return;
    }

    const ventana = capa.querySelector('.acerca__ventana');
    const cerrarBtn = capa.querySelector('.acerca__cerrar');

    /*
     * A dónde vuelve el foco al cerrar. Se guarda el elemento que la abrió,
     * no el botón del pie: la ventana puede abrirse desde más de un sitio
     * —hoy el pie, mañana el menú del avatar— y devolver el foco a un botón
     * que no se pulsó deja a quien navega con el teclado en otro sitio del
     * que estaba.
     */
    let quienAbrio = null;
    let cerrando = null;

    const abierta = () => !capa.hasAttribute('hidden');

    function abrir(origen) {
        if (abierta()) {
            return;
        }

        if (cerrando !== null) {
            window.clearTimeout(cerrando);
            cerrando = null;
            capa.classList.remove('acerca--cerrando');
        }

        quienAbrio = origen instanceof HTMLElement ? origen : null;

        capa.removeAttribute('hidden');

        /*
         * Se bloquea el scroll de la página. Sin esto, la rueda del ratón
         * sobre el fondo mueve el reporte de detrás y al cerrar la ventana
         * la pantalla ya no está donde se dejó.
         */
        document.body.classList.add('sin-scroll');

        if (cerrarBtn !== null) {
            cerrarBtn.focus();
        }
    }

    function cerrar() {
        if (!abierta()) {
            return;
        }

        capa.classList.add('acerca--cerrando');

        /*
         * 160 ms, los de la §11. Es el único número de aquí que también está
         * en el CSS; si allí cambia, cambia aquí. Se acepta la duplicación
         * porque la alternativa —esperar `animationend`— se queda colgada
         * cuando el navegador no anima (movimiento reducido, pestaña en
         * segundo plano) y entonces la ventana no se cierra nunca.
         */
        cerrando = window.setTimeout(function () {
            capa.setAttribute('hidden', '');
            capa.classList.remove('acerca--cerrando');
            document.body.classList.remove('sin-scroll');
            cerrando = null;

            if (quienAbrio !== null && document.contains(quienAbrio)) {
                quienAbrio.focus();
            }

            quienAbrio = null;
        }, 160);
    }

    /* Abre: cualquier elemento con `data-acerca`. Hoy, el botón del pie. */
    document.addEventListener('click', function (ev) {
        const disparador = ev.target.closest('[data-acerca]');
        if (disparador !== null) {
            ev.preventDefault();
            abrir(disparador);
        }
    });

    /* Cierra: la ✕ y el fondo, ambos marcados en la vista. */
    capa.addEventListener('click', function (ev) {
        if (ev.target.closest('[data-acerca-cerrar]') !== null) {
            cerrar();
        }
    });

    document.addEventListener('keydown', function (ev) {
        if (!abierta()) {
            return;
        }

        if (ev.key === 'Escape') {
            cerrar();

            return;
        }

        /*
         * El foco se queda dentro mientras está abierta. Sin esto, el
         * tabulador se va a los enlaces del reporte de detrás —que está
         * visible y es lo que hay debajo del fondo—, y quien navega con el
         * teclado se pierde en una pantalla que no puede ver entera.
         */
        if (ev.key !== 'Tab' || ventana === null) {
            return;
        }

        const enfocables = ventana.querySelectorAll(
            'a[href], button:not([disabled]), [tabindex]:not([tabindex="-1"])',
        );
        if (enfocables.length === 0) {
            return;
        }

        const primero = enfocables[0];
        const ultimo = enfocables[enfocables.length - 1];

        if (ev.shiftKey && document.activeElement === primero) {
            ev.preventDefault();
            ultimo.focus();
        } else if (!ev.shiftKey && document.activeElement === ultimo) {
            ev.preventDefault();
            primero.focus();
        }
    });
}());
