/* ===========================================================================
 *  Cambio de tema — DESIGN-SYSTEM.md §9 «Tema compartido»
 *
 *  El botón existía en la plantilla desde el principio y no hacía nada: no
 *  había ningún script que lo atendiera. Esto es ese script.
 *
 *  El tema ya se APLICA antes de pintar, en el `<script>` en línea de
 *  `vistas/plantilla.php`; sin eso, quien tiene el oscuro guardado ve un
 *  destello blanco en cada carga. Aquí sólo se cambia y se recuerda.
 * ======================================================================== */

(function () {
    'use strict';

    var CLAVE = 'tema';

    function actual() {
        return document.documentElement.dataset.theme || 'light';
    }

    /**
     * El icono muestra el tema al que VAS a cambiar, no en el que estás.
     * En claro se ve la luna (pulsa para oscuro); en oscuro, el sol.
     * Es la convención del sistema de diseño y la que espera la gente.
     */
    function pintarBoton(tema) {
        var boton = document.getElementById('btnTema');
        var hueco = document.getElementById('iconoTema');

        if (!boton || !hueco) { return; }

        var vaA = tema === 'dark' ? 'claro' : 'oscuro';
        var etiqueta = 'Cambiar a tema ' + vaA;

        boton.setAttribute('aria-label', etiqueta);
        boton.setAttribute('title', etiqueta);

        var plantilla = document.getElementById(
            tema === 'dark' ? 'plantillaIconoSol' : 'plantillaIconoLuna'
        );

        if (plantilla) {
            hueco.innerHTML = plantilla.innerHTML;
        }

        // El icono nuevo entra girando desde 90° con fundido.
        hueco.classList.remove('icon-btn__swap--entra');
        void hueco.offsetWidth;            // reinicia la animación
        hueco.classList.add('icon-btn__swap--entra');
    }

    function alternar() {
        var siguiente = actual() === 'dark' ? 'light' : 'dark';
        var raiz = document.documentElement;

        /*
         * `theme-transition` sólo mientras dura el cambio. Dejar una
         * transición de color permanente en todo el documento hace que cada
         * hover de tabla arrastre 200ms y la pantalla se sienta pastosa.
         */
        raiz.classList.add('theme-transition');
        raiz.dataset.theme = siguiente;

        try {
            localStorage.setItem(CLAVE, siguiente);
        } catch (e) { /* sin persistencia, y es aceptable */ }

        pintarBoton(siguiente);
        window.dispatchEvent(new Event('themechange'));

        setTimeout(function () { raiz.classList.remove('theme-transition'); }, 250);
    }

    /* -----------------------------------------------------------------
     *  Sombra de la cabecera al desplazar (DESIGN-SYSTEM §9)
     *
     *  La barra es fija: sin borde ni sombra, el contenido pasa por debajo y
     *  parece que floten juntos. Aparecen al separarse del inicio.
     * ----------------------------------------------------------------- */

    function iniciarSombra() {
        var cabecera = document.getElementById('cabecera');
        if (!cabecera) { return; }

        var pendiente = false;

        function revisar() {
            cabecera.classList.toggle('esta-desplazada', window.scrollY > 4);
            pendiente = false;
        }

        // Por `requestAnimationFrame`: el evento de scroll se dispara decenas
        // de veces por segundo y tocar clases en cada uno hace que la página
        // se sienta pesada justo mientras se desplaza.
        window.addEventListener('scroll', function () {
            if (!pendiente) {
                pendiente = true;
                window.requestAnimationFrame(revisar);
            }
        }, { passive: true });

        revisar();
    }

    function iniciar() {
        pintarBoton(actual());
        iniciarSombra();

        var boton = document.getElementById('btnTema');
        if (boton) { boton.addEventListener('click', alternar); }
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', iniciar);
    } else {
        iniciar();
    }
}());
