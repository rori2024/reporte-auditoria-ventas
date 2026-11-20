/* ===========================================================================
   La pantalla de la auditoría de formas de pago.

   Pide un período, lo consulta contra el AS400 y pinta el informe. No calcula
   NADA: el veredicto de cada documento, las tolerancias y los avisos vienen
   decididos del servidor (`servicios/Auditoria.php`), donde están medidos y
   razonados. Aquí sólo se da formato.

   Eso no es purismo: si el navegador decidiera, por ejemplo, cuál es el corte
   entre «redondeo» y «revisar», habría dos reglas —la del JavaScript y la del
   Excel— y el día que una cambiara, la pantalla y el archivo descargado
   dirían cosas distintas sobre la misma factura.

   ---------------------------------------------------------------------------
   POR QUÉ LA TABLA SE PINTA POR TRAMOS
   ------------------------------------
   Un mes son del orden de 3.800 documentos por catorce columnas: 53.000
   celdas. Creadas de golpe, el navegador se queda bloqueado un par de
   segundos —no responde al ratón ni al teclado— y parece que se ha colgado
   justo después de una espera de varios segundos por el AS400. Se pintan los
   primeros 300 y el resto a petición. Quien busca algo concreto usa el filtro,
   que es más rápido que desplazarse por tres mil filas.
   =========================================================================== */

(function () {
    'use strict';

    /** Cuántas filas se pintan de una vez. */
    var TRAMO = 300;

    /* --- Lo que hay en pantalla ahora mismo ----------------------------- */

    var estado = {
        informe: null,   // el último informe recibido, tal cual
        token: null,     // su ficha en la caché del servidor
        filtradas: [],   // los documentos que pasan los filtros
        pintadas: 0,     // cuántas de ésas están ya en el DOM
        clase: '',       // filtro por resultado
        tienda: '',      // filtro por tienda
        texto: '',       // filtro por texto
        pidiendo: false, // hay una consulta en vuelo
    };

    /* --- Atajos del DOM -------------------------------------------------- */

    function $(id) { return document.getElementById(id); }

    /** Crea un elemento con clase y texto. El texto va por `textContent`. */
    function el(etiqueta, clase, texto) {
        var n = document.createElement(etiqueta);

        if (clase) { n.className = clase; }

        /*
         * SIEMPRE `textContent` y NUNCA `innerHTML` para los datos.
         *
         * Lo que se pinta aquí sale del AS400: nombres de cliente, cédulas,
         * descripciones de formas de pago. Son campos de texto que lleva
         * grabando gente desde hace años y que nadie ha validado nunca. Un
         * nombre con `<` dentro rompería la fila con `innerHTML`, y uno con
         * una etiqueta `<script>` haría bastante más que romperla.
         */
        if (texto !== undefined && texto !== null) { n.textContent = String(texto); }

        return n;
    }

    /* --- Formato de cifras ---------------------------------------------- */

    /*
     * Los separadores son los de aquí: punto para los miles y coma para los
     * decimales. `toLocaleString` con 'es-VE' lo hace, y se fija el locale
     * explícitamente en lugar de dejar el del navegador — si alguien tiene el
     * suyo en inglés, «46.916,44» le saldría como «46,916.44» y en un informe
     * de bolívares eso se lee como cuarenta y seis mil con coma.
     */
    function bs(n) {
        if (n === null || n === undefined || n === '') { return ''; }

        return Number(n).toLocaleString('es-VE', {
            minimumFractionDigits: 2, maximumFractionDigits: 2,
        });
    }

    function cant(n) {
        if (n === null || n === undefined || n === '') { return ''; }

        return Number(n).toLocaleString('es-VE', { maximumFractionDigits: 0 });
    }

    /** `2026-11-17` -> `17/11/2026`, partiendo el texto y sin `new Date()`. */
    function fecha(iso) {
        if (!iso) { return ''; }

        var p = String(iso).slice(0, 10).split('-');

        /*
         * Sin `new Date('2026-11-17')` a propósito: eso se interpreta como
         * medianoche UTC y en una zona al oeste de Greenwich —aquí lo somos—
         * `getDate()` devuelve el día ANTERIOR. Todas las fechas del informe
         * saldrían corridas un día, y ningún error lo diría.
         */
        return p.length === 3 ? p[2] + '/' + p[1] + '/' + p[0] : String(iso);
    }

    /** `17/11` para la tabla, donde el año se repite en todas las filas. */
    function fechaCorta(iso) {
        if (!iso) { return ''; }

        var p = String(iso).slice(0, 10).split('-');

        return p.length === 3 ? p[2] + '/' + p[1] : String(iso);
    }

    /* =====================================================================
     *  Pedir el informe
     * ===================================================================== */

    function auditar() {
        if (estado.pidiendo) { return; }

        var desde = $('desde').value;
        var hasta = $('hasta').value;

        if (!desde || !hasta) {
            fallar('Hay que indicar las dos fechas.');
            return;
        }

        estado.pidiendo = true;
        esconder($('errorAuditoria'));
        $('btnAuditar').disabled = true;
        $('resultado').hidden = true;

        mostrarEspera(desde, hasta);

        var cuerpo = new URLSearchParams();
        cuerpo.set('desde', desde);
        cuerpo.set('hasta', hasta);

        fetch('php/auditoria/consultar.php', {
            method: 'POST',
            headers: { 'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8' },
            body: cuerpo.toString(),
            credentials: 'same-origin',
        })
            .then(function (res) {
                /*
                 * El JSON se lee aunque el estado no sea 200: el servidor manda
                 * el motivo DENTRO del cuerpo —«el rango son 365 días y el tope
                 * es 93»— y tirarlo para poner «error 422» cambiaría una
                 * explicación por un número.
                 */
                return res.json().then(function (datos) {
                    return { ok: res.ok, datos: datos };
                }).catch(function () {
                    /*
                     * Si no hay JSON, el servidor contestó algo que no era de
                     * esta aplicación: casi siempre una página de error de PHP
                     * o de Apache. Eso tiene su propio mensaje, porque la
                     * solución es otra.
                     */
                    throw new Error(
                        'El servidor contestó algo que no es una respuesta de esta '
                        + 'aplicación (estado ' + res.status + '). Suele ser un error de '
                        + 'PHP: mírelo en el registro de Apache.'
                    );
                });
            })
            .then(function (r) {
                if (!r.ok || !r.datos.ok) {
                    throw new Error(
                        (r.datos && r.datos.mensaje) || 'La consulta no se pudo completar.'
                        + (r.datos && r.datos.pista ? ' ' + r.datos.pista : '')
                    );
                }

                estado.informe = r.datos.informe;
                estado.token = r.datos.token || null;

                pintar();

                if (r.datos.aviso_cache) {
                    avisar(r.datos.aviso_cache);
                }
            })
            .catch(function (err) {
                fallar(err.message || String(err));
            })
            .then(function () {
                estado.pidiendo = false;
                $('btnAuditar').disabled = false;
                ocultarEspera();
            });
    }

    /* --- La espera -------------------------------------------------------- */

    var relojEspera = null;

    function mostrarEspera(desde, hasta) {
        var panel = $('panelEspera');
        panel.classList.remove('aud-oculto');

        /*
         * El texto va cambiando mientras se espera, y no es decoración: dice
         * cuál de los tres archivos se está leyendo. Si la espera se atasca
         * siempre en el mismo, eso es la primera pista de dónde está el
         * problema — y es una pista que el usuario puede dar por teléfono.
         *
         * LOS TIEMPOS SON LOS MEDIDOS, NO UN REPARTO A PARTES IGUALES
         * -----------------------------------------------------------
         * La primera versión cambiaba de paso cada 1,8 s, repartiendo la
         * espera en cinco trozos iguales. Medido contra producción el
         * 19/11/2026, la espera NO se reparte así ni de lejos:
         *
         *      ETP045 + IDTA116   ~0,2 s
         *      IDP210             ~0,1 s
         *      RTP325            17-22 s     <- el 98 % de la espera
         *      IDP116N            ~0,2 s
         *
         * `RTP325` tiene 6,6 millones de filas y ningún índice por fecha, así
         * que el AS400 lo barre entero cada vez. Con los pasos a 1,8 s, el
         * cargador pasaba de largo por el único que tarda y se quedaba veinte
         * segundos diciendo «cruzando los tres archivos», que es justo lo que
         * NO estaba pasando. Un indicador que miente sobre dónde está parado
         * es peor que no tener ninguno: manda a buscar el problema al sitio
         * equivocado.
         *
         * Y EL BARRIDO NO TARDA SIEMPRE LO MISMO
         * ---------------------------------------
         * Dos corridas del mismo mes contra el mismo servidor, con un día de
         * diferencia: `RTP325` tardó 9,67 s el 19/11 y 42,03 s el 20/11. No
         * depende del rango —ya se midió— sino de cómo esté el servidor y de
         * si conserva caliente el camino de acceso temporal que se construye
         * al vuelo. Así que este paso dura 45 s y no 20: quedarse corto
         * devolvía el cargador a «cruzando los tres archivos» cuando todavía
         * faltaba la mitad de la lectura.
         *
         * Sigue siendo una estimación —el servidor no informa del avance, eso
         * sería otra conexión— pero ahora es una estimación de lo que se midió.
         */
        var pasos = [
            { texto: 'leyendo el maestro de tiendas y el catálogo de formas de pago', ms: 600 },
            { texto: 'leyendo el encabezado de factura, IDP210', ms: 900 },
            {
                texto: 'leyendo el detalle de factura, RTP325 · es el paso largo, '
                    + 'son 6,6 millones de líneas sin índice por fecha',
                ms: 45000,
            },
            { texto: 'leyendo las formas de pago, IDP116N', ms: 900 },
            { texto: 'cruzando los tres archivos documento a documento', ms: 4000 },
        ];

        var i = -1;

        var siguiente = function () {
            i++;

            if (i >= pasos.length) {
                relojEspera = null;

                if (window.loaderRori) {
                    window.loaderRori.mostrar(
                        'el AS400 sigue trabajando, del ' + fecha(desde) + ' al ' + fecha(hasta)
                    );
                }

                return;
            }

            if (window.loaderRori) { window.loaderRori.mostrar(pasos[i].texto); }

            relojEspera = setTimeout(siguiente, pasos[i].ms);
        };

        siguiente();
    }

    function ocultarEspera() {
        // `clearTimeout` y no `clearInterval`: los pasos ya no van a intervalo
        // fijo, se encadenan con el tiempo medido de cada uno.
        if (relojEspera) { clearTimeout(relojEspera); relojEspera = null; }

        $('panelEspera').classList.add('aud-oculto');

        if (window.loaderRori) { window.loaderRori.ocultar(); }
    }

    /* --- Errores y avisos de la propia pantalla -------------------------- */

    function fallar(mensaje) {
        var caja = $('errorAuditoria');
        caja.className = 'alerta alerta--error';
        caja.textContent = mensaje;
        caja.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }

    function avisar(mensaje) {
        var caja = $('errorAuditoria');
        caja.className = 'alerta alerta--aviso';
        caja.textContent = mensaje;
    }

    function esconder(caja) {
        caja.className = 'alerta alerta--error aud-oculto';
        caja.textContent = '';
    }

    /* =====================================================================
     *  Pintar el informe
     * ===================================================================== */

    function pintar() {
        var inf = estado.informe;
        var r = inf.resumen;

        $('resultado').hidden = false;

        /* --- La ficha de la corrida ------------------------------------- */

        var meta = $('metaCorrida');

        meta.textContent = inf.rotulo
            + '  ·  leído del AS400 a las ' + String(inf.generado_en).slice(11, 16)
            + '  ·  ' + bs(inf.segundos) + ' s';

        /*
         * El desglose por archivo, en el `title`. No ocupa sitio en la
         * cabecera y está a un segundo de distancia el día que alguien
         * pregunte por qué tarda: casi toda la espera es `RTP325`, que no
         * tiene índice por fecha, y eso se ve en cuanto se pasa el ratón por
         * encima en lugar de tener que abrir la consola.
         */
        if (inf.tiempos && Object.keys(inf.tiempos).length > 0) {
            meta.title = Object.keys(inf.tiempos).map(function (k) {
                return k + ': ' + bs(inf.tiempos[k]) + ' s';
            }).join('\n');
        } else {
            meta.removeAttribute('title');
        }

        /* --- El enlace del Excel ---------------------------------------- */

        var url = 'php/auditoria/excel.php?' + new URLSearchParams(
            estado.token
                ? { token: estado.token }
                : { desde: inf.desde, hasta: inf.hasta }
        ).toString();

        $('btnExcel').href = url;
        $('btnExcelPie').href = url;

        pintarKpis(r);
        pintarVeredicto(r);
        pintarContraste(r);
        pintarRevisar(inf);
        pintarAvisos(inf);
        pintarFormas(inf);
        prepararTienda(inf);
        filtrar();
    }

    /* --- Las cifras grandes --------------------------------------------- */

    function pintarKpis(r) {
        var caja = $('kpis');
        caja.textContent = '';

        var fichas = [
            {
                icono: 'hoja-calculo', rotulo: 'Documentos auditados',
                cifra: cant(r.documentos),
                pie: cant(r.dias) + (r.dias === 1 ? ' día' : ' días') + ' con movimiento',
            },
            {
                icono: 'visto', rotulo: 'Cuadran al céntimo',
                cifra: cant(r.cuadran),
                pie: r.documentos > 0
                    ? bs(r.cuadran / r.documentos * 100) + ' % del total'
                    : '',
            },
            {
                icono: 'balanza', rotulo: 'Diferencia de redondeo',
                cifra: cant(r.redondeo),
                pie: bs(r.redondeo_bs) + ' Bs en total, no es dinero que falte',
            },
            {
                icono: 'aviso', rotulo: 'A REVISAR',
                cifra: cant(r.revisar),
                pie: r.revisar > 0
                    ? bs(r.falta_bs) + ' Bs por asentar'
                    : 'ni uno: todo cuadra',
                alerta: r.revisar > 0,
            },
            {
                icono: 'dinero', rotulo: 'Total facturado',
                cifra: bs(r.total_facturado), unidad: 'Bs',
                pie: 'en formas de pago: ' + bs(r.total_pagado) + ' Bs',
            },
        ];

        fichas.forEach(function (f) {
            caja.appendChild(ficha(f));
        });
    }

    function ficha(f) {
        var art = el('article', 'kpi');

        var cab = el('header', 'kpi__cabecera');
        cab.appendChild(el('span', 'kpi__acento'));
        cab.lastChild.setAttribute('aria-hidden', 'true');

        var ic = el('span', 'kpi__icono');
        ic.innerHTML = svg(f.icono);          // SVG propio, no dato del AS400
        cab.appendChild(ic);

        cab.appendChild(el('span', 'kpi__rotulo', f.rotulo));
        art.appendChild(cab);

        var linea = el('div', 'kpi__linea');
        linea.appendChild(el('span', 'kpi__cifra', f.cifra));

        if (f.unidad) { linea.appendChild(el('span', 'kpi__unidad', f.unidad)); }

        art.appendChild(linea);

        if (f.pie) {
            var pie = el('div', 'kpi__pie');
            pie.appendChild(el('span', 'kpi__pie-valor', f.pie));
            art.appendChild(pie);
        }

        if (f.alerta) { art.dataset.alerta = 'si'; }

        return art;
    }

    /*
     * Los iconos van aquí en lugar de pedirlos a PHP porque estas tarjetas se
     * crean en el navegador. Son los mismos trazados de Lucide que usa
     * `vistas/iconos.php`: si cambia uno, cambia en los dos sitios.
     */
    var TRAZADOS = {
        'hoja-calculo': '<rect width="18" height="18" x="3" y="3" rx="2"/><path d="M3 9h18M3 15h18M9 3v18M15 3v18"/>',
        'visto': '<path d="M21.8 10A10 10 0 1 1 17 3.3"/><path d="m9 11 3 3L22 4"/>',
        'balanza': '<path d="M12 3v18M7 21h10M5 7h14M5 7l-3 7a4 4 0 0 0 6 0Zm14 0 3 7a4 4 0 0 1-6 0Z"/>',
        'aviso': '<path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/><path d="M12 9v4M12 17h.01"/>',
        'dinero': '<rect width="20" height="12" x="2" y="6" rx="2"/><circle cx="12" cy="12" r="2"/><path d="M6 12h.01M18 12h.01"/>',
    };

    function svg(nombre) {
        var t = TRAZADOS[nombre];

        if (!t) { return ''; }

        return '<svg class="icono" width="18" height="18" viewBox="0 0 24 24" fill="none"'
            + ' stroke="currentColor" stroke-width="2" stroke-linecap="round"'
            + ' stroke-linejoin="round" aria-hidden="true" focusable="false">' + t + '</svg>';
    }

    /* --- La frase que contesta la pregunta ------------------------------ */

    function pintarVeredicto(r) {
        var p = $('veredicto');

        if (r.revisar === 0) {
            p.dataset.tono = 'bien';
            p.textContent = 'No hay nada que revisar: los ' + cant(r.documentos)
                + ' documentos del período cuadran con sus formas de pago, al céntimo o '
                + 'dentro del redondeo del IGTF.';

            return;
        }

        p.dataset.tono = 'revisar';
        p.textContent = 'Hay ' + cant(r.revisar)
            + (r.revisar === 1 ? ' documento' : ' documentos')
            + ' con ' + bs(r.falta_bs) + ' Bs cobrados que no están registrados en las '
            + 'formas de pago'
            + (r.sobra_bs > 0 ? ', y ' + bs(r.sobra_bs) + ' Bs registrados de más' : '')
            + '. Están abajo, ordenados por tamaño.';
    }

    function pintarContraste(r) {
        var caja = $('contraste');
        caja.textContent = '';

        [
            ['El detalle cuadra con el encabezado en', cant(r.detalle_cuadra), 'documentos'],
            ['NO cuadra en', cant(r.detalle_descuadrado), ''],
            ['No aplica (abonos y ajustes)', cant(r.detalle_no_aplica), ''],
            ['Anuladas', cant(r.anuladas), ''],
            ['Sin una línea de pago', cant(r.sin_pagos), ''],
            ['Facturas manuales', cant(r.manuales), ''],
        ].forEach(function (par) {
            var span = el('span');
            span.appendChild(document.createTextNode(par[0] + ' '));
            span.appendChild(el('strong', null, par[1]));

            if (par[2]) { span.appendChild(document.createTextNode(' ' + par[2])); }

            caja.appendChild(span);
        });
    }

    /* --- Lo que hay que revisar ----------------------------------------- */

    function pintarRevisar(inf) {
        var panel = $('panelRevisar');
        var cuerpo = $('cuerpoRevisar');
        cuerpo.textContent = '';

        var docs = inf.documentos.filter(function (d) { return d.clase === 'REVISAR'; });

        if (docs.length === 0) {
            panel.hidden = true;

            return;
        }

        panel.hidden = false;

        docs.sort(function (a, b) {
            return Math.abs(b.dif_pago) - Math.abs(a.dif_pago);
        });

        $('metaRevisar').textContent = docs.length
            + (docs.length === 1 ? ' documento' : ' documentos')
            + '  ·  ordenados por tamaño de la diferencia';

        docs.forEach(function (d) {
            var tr = el('tr');

            tr.appendChild(el('td', 'aud-num', fecha(d.fecha)));
            tr.appendChild(el('td', null, d.tienda));
            tr.appendChild(el('td', 'aud-num', d.tipo_doc + ' ' + d.numero_doc));
            tr.appendChild(el('td', 'aud-num', bs(d.total_factura)));
            tr.appendChild(el('td', 'aud-num', bs(d.pagado)));
            tr.appendChild(el('td', 'aud-num aud-falta', bs(d.dif_pago)));
            tr.appendChild(el('td', 'aud-num',
                d.pct_pagado === null ? '—' : bs(d.pct_pagado) + ' %'));
            tr.appendChild(el('td', 'aud-desglose', d.desglose || '(ninguna)'));
            tr.appendChild(el('td', 'aud-observacion', d.diagnostico));

            cuerpo.appendChild(tr);
        });
    }

    /* --- Los avisos ------------------------------------------------------ */

    function pintarAvisos(inf) {
        var panel = $('panelAvisos');
        var lista = $('listaAvisos');
        lista.textContent = '';

        if (!inf.avisos || inf.avisos.length === 0) {
            panel.hidden = true;

            return;
        }

        panel.hidden = false;
        $('metaAvisos').textContent = inf.avisos.length
            + (inf.avisos.length === 1 ? ' aviso' : ' avisos');

        inf.avisos.forEach(function (a) {
            var li = el('li', null, a.texto);
            li.dataset.nivel = a.nivel;

            // La marca es una letra y no un color: este informe se imprime, y
            // en blanco y negro el color no sobrevive.
            li.dataset.marca = a.nivel === 'alto' ? '!' : (a.nivel === 'medio' ? 'i' : '·');

            lista.appendChild(li);
        });
    }

    /* --- En qué se cobró ------------------------------------------------- */

    function pintarFormas(inf) {
        var cuerpo = $('cuerpoFormas');
        cuerpo.textContent = '';

        var total = inf.formas.reduce(function (s, f) { return s + Number(f.bs); }, 0);

        $('metaFormas').textContent = inf.formas.length
            + (inf.formas.length === 1 ? ' forma en uso' : ' formas en uso')
            + '  ·  ' + bs(total) + ' Bs';

        inf.formas.forEach(function (f) {
            var tr = el('tr', f.en_catalogo ? null : 'aud-sin-catalogo');

            tr.appendChild(el('td', 'aud-num', f.forma_pago));
            tr.appendChild(el('td', null, f.descripcion));

            var tipo = el('td');
            tipo.appendChild(document.createTextNode(f.tipo));

            if (f.es_financiamiento) {
                tipo.appendChild(document.createTextNode(' '));
                tipo.appendChild(el('span', 'aud-marca', 'financiamiento'));
            }

            tr.appendChild(tipo);
            tr.appendChild(el('td', 'aud-num', cant(f.lineas)));
            tr.appendChild(el('td', 'aud-num', cant(f.docs)));
            tr.appendChild(el('td', 'aud-num', bs(f.bs)));
            tr.appendChild(el('td', 'aud-num',
                total !== 0 ? bs(Number(f.bs) / total * 100) + ' %' : ''));

            cuerpo.appendChild(tr);
        });
    }

    /* =====================================================================
     *  La tabla grande: filtros y pintado por tramos
     * ===================================================================== */

    function prepararTienda(inf) {
        var sel = $('filtroTienda');
        var nombres = {};

        inf.documentos.forEach(function (d) { nombres[d.tienda] = true; });

        sel.textContent = '';
        sel.appendChild(el('option', null, 'Todas las tiendas'));
        sel.lastChild.value = '';

        Object.keys(nombres).sort().forEach(function (n) {
            var o = el('option', null, n);
            o.value = n;
            sel.appendChild(o);
        });

        sel.value = '';
        estado.tienda = '';
    }

    function filtrar() {
        var inf = estado.informe;

        if (!inf) { return; }

        var texto = estado.texto.trim().toLowerCase();

        estado.filtradas = inf.documentos.filter(function (d) {
            if (estado.clase && d.clase !== estado.clase) { return false; }
            if (estado.tienda && d.tienda !== estado.tienda) { return false; }

            if (texto) {
                /*
                 * Se busca en lo que una persona teclearía para encontrar un
                 * documento concreto: el número, el cliente, el vendedor, la
                 * caja. NO en el diagnóstico — ahí aparecen palabras como
                 * «factura» o «pago» en casi todas las filas, y el filtro
                 * dejaría de filtrar.
                 */
                var heno = [
                    d.numero_doc, d.tipo_doc, d.cliente_nombre, d.cliente_cedula,
                    d.vendedor, d.caja, d.tienda, d.desglose,
                ].join(' ').toLowerCase();

                if (heno.indexOf(texto) === -1) { return false; }
            }

            return true;
        });

        $('cuerpoTabla').textContent = '';
        estado.pintadas = 0;

        pintarTramo();
    }

    function pintarTramo() {
        var cuerpo = $('cuerpoTabla');
        var hasta = Math.min(estado.pintadas + TRAMO, estado.filtradas.length);

        /*
         * Un fragmento y un solo `appendChild`: añadir 300 filas una a una al
         * documento provoca 300 recálculos de diseño. Dentro del fragmento no
         * hay ninguno, y al insertarlo hay uno.
         */
        var frag = document.createDocumentFragment();

        for (var i = estado.pintadas; i < hasta; i++) {
            frag.appendChild(fila(estado.filtradas[i], i));
        }

        cuerpo.appendChild(frag);
        estado.pintadas = hasta;

        var quedan = estado.filtradas.length - estado.pintadas;

        $('btnMas').hidden = quedan <= 0;

        if (quedan > 0) {
            $('btnMas').textContent = 'Ver ' + cant(Math.min(quedan, TRAMO))
                + ' filas más  (quedan ' + cant(quedan) + ')';
        }

        $('contadorFilas').textContent = estado.filtradas.length === estado.informe.documentos.length
            ? 'Mostrando ' + cant(estado.pintadas) + ' de ' + cant(estado.filtradas.length)
              + ' documentos.'
            : 'Mostrando ' + cant(estado.pintadas) + ' de ' + cant(estado.filtradas.length)
              + ' documentos filtrados, de ' + cant(estado.informe.documentos.length)
              + ' del período.';

        $('metaTabla').textContent = cant(estado.informe.documentos.length) + ' documentos';
    }

    var MARCAS = {
        'CUADRA': ['aud-marca--cuadra', 'cuadra'],
        'REDONDEO': ['aud-marca--redondeo', 'redondeo'],
        'REVISAR': ['aud-marca--revisar', 'REVISAR'],
        'NO APLICA': ['aud-marca--noaplica', 'no aplica'],
    };

    function fila(d, indice) {
        var tr = el('tr', d.clase === 'REVISAR'
            ? 'aud-fila--revisar'
            : (d.clase === 'REDONDEO' ? 'aud-fila--redondeo' : null));

        /*
         * La fila se puede abrir, así que tiene que ser alcanzable con el
         * teclado y anunciarse como lo que es. Una fila que sólo responde al
         * ratón deja la ficha —donde está el diagnóstico entero— fuera del
         * alcance de quien no usa ratón.
         */
        tr.tabIndex = 0;
        tr.setAttribute('role', 'button');
        tr.setAttribute('aria-label', 'Ver el detalle de ' + d.tipo_doc + ' ' + d.numero_doc
            + ' de ' + d.tienda);
        tr.dataset.indice = String(indice);

        tr.appendChild(el('td', 'aud-num', fechaCorta(d.fecha)));
        tr.appendChild(el('td', null, d.tienda));
        tr.appendChild(el('td', 'aud-num', d.tipo_doc + ' ' + d.numero_doc));
        tr.appendChild(el('td', null, d.clase_doc));
        tr.appendChild(el('td', null, d.anulada ? 'ANULADA' : 'Vigente'));
        tr.appendChild(el('td', 'aud-num', cant(d.lineas)));
        tr.appendChild(el('td', 'aud-num', bs(d.total_factura)));
        tr.appendChild(el('td', 'aud-num', bs(d.detalle_neto)));

        // Vacío y no cero: en un abono o un ajuste el contraste del detalle NO
        // APLICA, y un cero ahí diría «cuadra», que es mentira.
        tr.appendChild(el('td', 'aud-num',
            d.dif_detalle === null ? '—' : bs(d.dif_detalle)));

        tr.appendChild(el('td', 'aud-num', cant(d.formas)));
        tr.appendChild(el('td', 'aud-num', bs(d.pagado)));
        tr.appendChild(el('td', 'aud-num' + (d.clase === 'REVISAR' ? ' aud-falta' : ''),
            bs(d.dif_pago)));

        var marca = MARCAS[d.clase] || ['aud-marca', d.clase];
        var celda = el('td');
        celda.appendChild(el('span', 'aud-marca ' + marca[0], marca[1]));
        tr.appendChild(celda);

        tr.appendChild(el('td', 'aud-desglose', d.desglose || '(ninguna)'));

        return tr;
    }

    /* =====================================================================
     *  La ficha de un documento
     * ===================================================================== */

    function abrirFicha(indice) {
        var d = estado.filtradas[indice];

        if (!d) { return; }

        $('fichaTitulo').textContent = d.tipo_doc + ' ' + d.numero_doc + '  ·  ' + d.tienda;

        var cuerpo = $('fichaCuerpo');
        cuerpo.textContent = '';

        /* --- Qué le pasa, primero: es la razón de abrir la ficha -------- */

        var bloque = el('div', 'aud-ficha__bloque');
        bloque.appendChild(el('h3', null, 'Qué se ve en el archivo'));
        bloque.appendChild(el('p', null, d.diagnostico));
        cuerpo.appendChild(bloque);

        /* --- El contraste, que es la cuenta que se hizo ----------------- */

        cuerpo.appendChild(definiciones([
            ['Resultado', (MARCAS[d.clase] || [null, d.clase])[1], true],
            ['Total de la factura', bs(d.total_factura) + ' Bs'],
            ['Suma de formas de pago', bs(d.pagado) + ' Bs'],
            ['Diferencia', bs(d.dif_pago) + ' Bs'],
            ['Registrado', d.pct_pagado === null ? '—' : bs(d.pct_pagado) + ' %'],
        ]));

        /* --- De dónde sale el total, importe por importe ---------------- */

        var formula = el('div', 'aud-ficha__bloque');
        formula.appendChild(el('h3', null, 'De dónde sale el total (IDP210)'));
        formula.appendChild(definiciones([
            ['Bruto  NMODC1', bs(d.monto_bruto)],
            ['− Descuento  NMODC2', bs(d.descuento)],
            ['+ IVA  NMODC6', bs(d.iva)],
            ['+ IGTF  NMOOCG', bs(d.igtf)],
            ['= Total', bs(d.total_factura)],
            ['Dscto. SENIAT  NMODC7', bs(d.dscto_seniat) + '  (fuera de la fórmula)'],
            ['Abono  NMOABO', bs(d.abono) + '  (fuera de la fórmula)'],
        ]));
        cuerpo.appendChild(formula);

        /* --- El detalle contra el encabezado ---------------------------- */

        var det = el('div', 'aud-ficha__bloque');
        det.appendChild(el('h3', null, 'El detalle (RTP325)'));
        det.appendChild(definiciones([
            ['Líneas', cant(d.lineas)],
            ['Piezas en el encabezado', cant(d.unidades)],
            ['Piezas en el detalle', cant(d.det_piezas)],
            ['Detalle neto', bs(d.detalle_neto) + ' Bs'],
            ['Diferencia', d.dif_detalle === null
                ? 'no aplica en esta clase de documento'
                : bs(d.dif_detalle) + ' Bs'],
        ]));
        cuerpo.appendChild(det);

        /* --- Las formas de pago ----------------------------------------- */

        var pag = el('div', 'aud-ficha__bloque');
        pag.appendChild(el('h3', null, 'Las formas de pago (IDP116N)'));
        pag.appendChild(el('p', null, d.desglose || 'No tiene ni una línea de pago registrada.'));
        cuerpo.appendChild(pag);

        /* --- Y lo demás del documento ----------------------------------- */

        cuerpo.appendChild(definiciones([
            ['Fecha', fecha(d.fecha)],
            ['Tienda', d.tienda + '  (código ' + d.codigo_as400 + ')'],
            ['Clase', d.clase_doc, true],
            ['Estado', d.anulada ? 'ANULADA' : 'Vigente', true],
            ['Cliente', d.cliente_nombre + '  (' + d.cliente_cedula + ')', true],
            ['Vendedor', d.vendedor],
            ['Caja', d.caja || '—'],
            ['Hora', d.hora || '—'],
            ['Tasa BCV del documento', bs(d.tasa_bcv_doc)],
            ['Factura manual', d.manual ? 'sí (FLA011 = M)' : 'no', true],
            ['Aplica a la factura', d.factura_aplicada ? String(d.factura_aplicada) : '—'],
        ]));

        $('ficha').showModal();
    }

    /** Una lista de pares rótulo/valor. El tercer campo pide tipografía de texto. */
    function definiciones(pares) {
        var dl = el('dl');

        pares.forEach(function (p) {
            dl.appendChild(el('dt', null, p[0]));
            dl.appendChild(el('dd', p[2] ? 'aud-texto' : null, p[1]));
        });

        return dl;
    }

    /* =====================================================================
     *  Enganchar todo
     * ===================================================================== */

    function iniciar() {
        $('formAuditoria').addEventListener('submit', function (ev) {
            ev.preventDefault();
            auditar();
        });

        /* Los atajos rellenan las fechas y lanzan la consulta. */
        document.querySelectorAll('.aud-atajos .btn').forEach(function (b) {
            b.addEventListener('click', function () {
                $('desde').value = b.dataset.desde;
                $('hasta').value = b.dataset.hasta;
                auditar();
            });
        });

        $('btnRecargar').addEventListener('click', auditar);

        /* --- Los filtros ----------------------------------------------- */

        $('filtroClase').addEventListener('click', function (ev) {
            var b = ev.target.closest('button[data-clase]');

            if (!b) { return; }

            estado.clase = b.dataset.clase;

            // `aria-pressed` y no una clase: es un grupo de botones de
            // alternancia, y eso es lo que hace que un lector de pantalla diga
            // cuál está puesto.
            $('filtroClase').querySelectorAll('button').forEach(function (otro) {
                otro.setAttribute('aria-pressed', String(otro === b));
            });

            filtrar();
        });

        $('filtroTienda').addEventListener('change', function () {
            estado.tienda = $('filtroTienda').value;
            filtrar();
        });

        /*
         * El teclear se deja reposar: con 3.800 documentos, filtrar en cada
         * pulsación hace que la escritura se note a saltos.
         */
        var reloj = null;

        $('filtroTexto').addEventListener('input', function () {
            clearTimeout(reloj);

            reloj = setTimeout(function () {
                estado.texto = $('filtroTexto').value;
                filtrar();
            }, 180);
        });

        $('btnMas').addEventListener('click', pintarTramo);

        /* --- Abrir la ficha -------------------------------------------- */

        var cuerpo = $('cuerpoTabla');

        /*
         * Un solo escuchador en el `tbody` y no uno por fila: con tres mil
         * filas, tres mil escuchadores son tres mil cierres vivos que hay que
         * soltar cada vez que se filtra. Así no hay nada que soltar.
         */
        cuerpo.addEventListener('click', function (ev) {
            var tr = ev.target.closest('tr[data-indice]');

            if (tr) { abrirFicha(Number(tr.dataset.indice)); }
        });

        cuerpo.addEventListener('keydown', function (ev) {
            if (ev.key !== 'Enter' && ev.key !== ' ') { return; }

            var tr = ev.target.closest('tr[data-indice]');

            if (!tr) { return; }

            // El espacio desplaza la página por omisión, y aquí abre la ficha.
            ev.preventDefault();
            abrirFicha(Number(tr.dataset.indice));
        });

        $('btnCerrarFicha').addEventListener('click', function () { $('ficha').close(); });

        /* Pulsar el fondo cierra, que es lo que todo el mundo intenta. */
        $('ficha').addEventListener('click', function (ev) {
            if (ev.target === $('ficha')) { $('ficha').close(); }
        });

        /* --- Que el «hasta» no pueda ser anterior al «desde» ----------- */

        $('desde').addEventListener('change', function () {
            $('hasta').min = $('desde').value;
        });

        $('hasta').min = $('desde').value;
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', iniciar);
    } else {
        iniciar();
    }
})();
