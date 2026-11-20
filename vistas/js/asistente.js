/* ===========================================================================
 *  Asistente flotante — «Carlos Flores Bot»
 *
 *  No hay servidor detrás, y eso es lo que lo hace fiable. Es una guía de esta
 *  pantalla escrita a mano: saluda según la hora, ofrece los temas y responde
 *  con lo que la aplicación hace DE VERDAD, con un botón para llevar a la
 *  parte de la pantalla de la que habla.
 *
 *  LO QUE NO SABE, LO DICE
 *  -----------------------
 *  Esto audita dinero. Un asistente que improvisa sobre una auditoría es peor
 *  que no tenerlo: si la búsqueda no encuentra nada, contesta que no tiene
 *  nada sobre eso y remite al manual de usuario o a soporte. Cada afirmación
 *  de `TEMAS` sale de un archivo del repositorio —`servicios/Auditoria.php`,
 *  `servicios/Periodo.php`, `vistas/modulos/periodo.php`, `resultado.php`,
 *  `docs/MANUAL-USUARIO.md`— y usa los MISMOS rótulos que la pantalla, no
 *  sinónimos.
 *
 *  TRES ADAPTACIONES A ESTA CASA
 *  -----------------------------
 *  1. ICONOS. El original tira de Font Awesome. Aquí toda la interfaz usa los
 *     SVG en línea de `vistas/iconos.php`, que es la única lista de iconos de
 *     la aplicación, y `config/app.php` deja Font Awesome apagado a propósito
 *     —una petición más a un CDN que la intranet no siempre alcanza—. Así que
 *     los iconos de los chips se leen de los `<template>` que pinta
 *     `vistas/modulos/asistente.php`: el catálogo sigue estando en un solo
 *     sitio y este archivo no lleva ni un trazado SVG dentro.
 *  2. NAVEGACIÓN. No hay módulos ni rutas: hay UNA pantalla. Así que `vista`
 *     es un selector de la propia página y «Ir a …» desplaza hasta ese sitio
 *     en vez de cambiar de vista. El botón sólo se pinta si ese sitio existe
 *     y está visible: los paneles del informe no existen hasta que alguien
 *     pide un período, y ofrecer «Ir a Lo que hay que revisar» cuando todavía
 *     no se ha auditado nada sería mentir.
 *  3. ACENTOS. El original los evita dentro del JavaScript. Esta aplicación
 *     escribe español con tildes en todas sus pantallas, y un «Buenos dias»
 *     al lado de «Auditoría de Formas de Pago» se lee como un error. Los
 *     archivos están en UTF-8, así que se usan.
 * ======================================================================== */
const AsistenteModule = (function () {
    'use strict';

    // =====================================================================
    //  Adaptacion al proyecto (lo unico que cambia entre proyectos)
    // =====================================================================

    const CONFIG = {
        /** Nombre del producto tal como lo conoce la gente. */
        nombreSistema: 'la Auditoría de Formas de Pago',

        /**
         * Nombre completo del usuario con sesión.
         *
         * Lo pone PHP en el `data-usuario` del armazón, de la misma sesión de
         * intranet que pinta la cabecera. No se lee del DOM de la cabecera:
         * ese marcado puede cambiar y esto se quedaría mudo sin avisar.
         */
        nombreUsuario: () => String(document.getElementById('asistente')?.dataset.usuario || ''),

        /**
         * La intranet guarda «APELLIDOS NOMBRES» —«FLORES HENRIQUEZ CARLOS
         * LUIS»—, así que el nombre de pila es la tercera palabra.
         */
        ordenNombre: 'apellido-nombre',

        /**
         * Permisos de la sesión, los mismos que exigen los puntos de entrada
         * de `php/`. Hoy ningún tema declara permiso —quien entra tiene
         * `visualizar` y la pantalla es una sola—, pero el enganche está
         * puesto para el día que haya uno.
         */
        puede: (clave) => {
            const lista = String(document.getElementById('asistente')?.dataset.permisos || '');

            return lista.split(',').map(p => p.trim()).filter(Boolean).includes(clave);
        },

        /**
         * Si el sitio del que habla el tema existe Y está a la vista.
         *
         * `offsetParent` es nulo cuando el elemento o alguno de sus padres
         * está oculto, que es justo el caso de los paneles del informe antes
         * de la primera consulta y de los que llevan `hidden` porque no hay
         * nada que mostrar («Lo que hay que revisar» sin nada que revisar).
         */
        existeVista: (vista) => {
            const nodo = document.querySelector(vista);

            return nodo !== null && nodo.offsetParent !== null;
        },

        /**
         * Lleva hasta ese sitio de la pantalla, sin cerrar el panel.
         *
         * Se resta la altura de la cabecera, que es `sticky`: sin eso el
         * destino queda justo debajo de la barra y parece que no se movió.
         */
        irA: (vista) => {
            const nodo = document.querySelector(vista);
            if (nodo === null) return;

            const alto = document.getElementById('cabecera')?.offsetHeight || 0;
            const arriba = nodo.getBoundingClientRect().top + window.scrollY - alto - 16;

            window.scrollTo({ top: Math.max(arriba, 0), behavior: 'smooth' });

            // Si el destino es un control, además se le da el foco: quien va
            // con el teclado tiene que quedarse donde lo llevamos.
            if (nodo.matches('button, a[href], input, select, textarea')) {
                nodo.focus({ preventScroll: true });
            }
        },
    };

    const $ = (id) => document.getElementById(id);
    const esc = (v) => String(v ?? '')
        .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;').replace(/'/g, '&#039;');
    const normalizar = (v) => String(v ?? '')
        .normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase().trim();

    /**
     * El SVG de un icono, del catálogo de `vistas/iconos.php`.
     *
     * Los `<template>` los pinta el armazón, así que aquí no hay trazados
     * escritos: un icono que cambie se cambia en `vistas/iconos.php` y ya.
     * Un nombre que no esté devuelve cadena vacía — un icono que falta no
     * debe tumbar el chip.
     */
    const svgIcono = (nombre) => {
        if (!nombre) return '';

        return $('asis-iconos')?.querySelector('[data-icono="' + nombre + '"]')?.innerHTML || '';
    };

    // Ritmo de la conversacion: lo justo para que se lea como una respuesta y
    // no como un volcado instantaneo.
    const PAUSA_MS = 480;

    let arrancado = false;
    let presentado = false;   // el saludo largo va una sola vez por sesion
    let ocupado = false;      // evita encadenar respuestas si se pulsa rapido

    // =====================================================================
    //  Temas
    // =====================================================================

    /**
     * Cada tema: a qué menú pertenece, qué responde, a dónde lleva y con qué
     * palabras se encuentra desde el buscador.
     *
     * 'permiso' vacío = lo ve cualquiera con sesión.
     * 'vista' = selector de esta misma página; sin él, no se ofrece «Ir a».
     * 'ir' = texto del botón; sin él, la primera palabra del título.
     */
    const TEMAS = [

        // --- Primeros pasos ----------------------------------------------

        {
            id: 'que-es',
            menu: 'basico',
            icono: 'info',
            titulo: 'Qué es esta aplicación',
            claves: 'que es para que sirve auditoria formas de pago cuadra factura cobro asentar '
                + 'idp210 rtp325 idp116n tres archivos encabezado detalle pagos as400 en vivo',
            texto: `<p>Contesta una pregunta que antes no contestaba nadie: <strong>¿cuadra cada
                    factura con lo que se cobró por ella?</strong> Una factura del AS400 vive
                    repartida en tres archivos, y los tres tienen que contar lo mismo:</p>
                    <ul>
                        <li><code>IDP210</code>, el encabezado: cuánto se vendió.</li>
                        <li><code>RTP325</code>, el detalle: qué se vendió.</li>
                        <li><code>IDP116N</code>, las formas de pago: con qué se pagó.</li>
                    </ul>
                    <p>Si la suma de las formas de pago no llega al total de la factura,
                    <strong>falta un cobro por asentar</strong>. Se lee el AS400 en vivo: no hay
                    copia intermedia ni carga de madrugada que pueda estar vieja.</p>`,
            relacionados: ['como-se-usa', 'clases'],
        },
        {
            id: 'como-se-usa',
            menu: 'basico',
            icono: 'brujula',
            titulo: 'Cómo se usa, de principio a fin',
            claves: 'como se usa empezar primeros pasos auditar boton paso a paso que hago '
                + 'guia rapida usar pantalla',
            texto: `<p>Una sola pantalla y cuatro pasos:</p>
                    <ul>
                        <li>Ponga <strong>Desde</strong> y <strong>Hasta</strong>, o pulse un atajo.</li>
                        <li>Pulse <strong>Auditar</strong> y espere entre veinte segundos y un minuto.</li>
                        <li>Mire la cifra <strong>A REVISAR</strong>. Si está en cero, ese período no
                        necesita nada más.</li>
                        <li>Si hay algo, el panel <strong>Lo que hay que revisar</strong> lo lista
                        ordenado de mayor a menor diferencia.</li>
                    </ul>
                    <p>Cuando ya lo revisó, <strong>Descargar Excel</strong> baja exactamente lo que
                    tiene en pantalla.</p>`,
            vista: '#formAuditoria',
            ir: 'Qué período se audita',
            relacionados: ['periodo-fechas', 'cuanto-tarda', 'cifras'],
        },
        {
            id: 'pantalla-orden',
            menu: 'basico',
            icono: 'hoja-calculo',
            titulo: 'Qué hay en la pantalla',
            claves: 'pantalla secciones orden paneles donde esta cada cosa veredicto avisos '
                + 'tabla formas de pago arriba abajo',
            texto: `<p>Se lee de arriba abajo, en el orden en que se decide:</p>
                    <ul>
                        <li><strong>Qué período se audita</strong>: las dos fechas y el botón.</li>
                        <li><strong>El veredicto</strong>: las cifras grandes.</li>
                        <li><strong>Lo que hay que revisar</strong>: lo único accionable.</li>
                        <li><strong>Lo que este informe advierte de sí mismo</strong>: los avisos.</li>
                        <li><strong>En qué se cobró</strong>: las formas de pago del período.</li>
                        <li><strong>Documento a documento</strong>: todo, filtrable y buscable.</li>
                    </ul>
                    <p>Mientras no pida un período, debajo del formulario no hay nada. Es a
                    propósito: cada consulta hace trabajar al AS400 casi un minuto, y una pantalla
                    que consulta sola gastaría eso cada vez que alguien la abre por error.</p>`,
            relacionados: ['cifras', 'tabla-filtros'],
        },
        {
            id: 'acceso',
            menu: 'basico',
            icono: 'usuario',
            titulo: 'Cómo se entra y el distintivo PRUEBAS',
            claves: 'entrar acceso intranet usuario clave contrasena permiso pruebas distintivo '
                + 'quien soy sesion mi nombre foto perfil',
            texto: `<p>La aplicación se abre <strong>desde la intranet</strong>, como los demás
                    programas de la casa. No tiene usuario ni clave propios: entra con el suyo y la
                    intranet comprueba que tenga concedida esta aplicación. Su nombre y su foto,
                    arriba a la derecha, salen de ahí.</p>
                    <p>Si junto al nombre de la aplicación ve el distintivo <strong>PRUEBAS</strong>,
                    está en un equipo donde la comprobación de permisos está apagada a propósito y
                    los números pueden no ser los de producción. En el equipo de verdad ese
                    distintivo no aparece.</p>`,
            relacionados: ['soporte'],
        },
        {
            id: 'tema',
            menu: 'basico',
            icono: 'luna',
            titulo: 'Cambiar entre tema claro y oscuro',
            claves: 'tema oscuro claro luna sol color noche apariencia cambiar vista cansa',
            texto: `<p>Arriba a la derecha, el botón con la luna o el sol cambia el tema de la
                    pantalla entera. La elección se guarda en el navegador, así que la próxima vez
                    abre como lo dejó.</p>
                    <p>Mientras no elija ninguno, sigue al tema del sistema operativo.</p>`,
            vista: '#btnTema',
            ir: 'el interruptor de tema',
        },
        {
            id: 'manuales',
            menu: 'basico',
            icono: 'libro',
            titulo: 'Los manuales en PDF',
            claves: 'manual manuales pdf documentacion ayuda usuario tecnico instrucciones leer',
            texto: `<p>En el pie de la página, columna <strong>Manuales</strong>, hay dos: el
                    <strong>Manual de usuario (PDF)</strong> —cómo se usa esta auditoría, escrito
                    para quien la usa— y el <strong>Manual técnico (PDF)</strong>, para quien
                    mantiene el programa. Se abren en una pestaña nueva, así que no pierde la
                    consulta que tenga en pantalla.</p>
                    <p>Lo que yo cuento es un resumen de ese manual. Si necesita el detalle, o algo
                    que yo no sepa, está allí.</p>`,
            vista: '#pieManuales',
            ir: 'los manuales',
            relacionados: ['soporte'],
        },
        {
            id: 'soporte',
            menu: 'basico',
            icono: 'auricular',
            titulo: 'Hablar con una persona',
            claves: 'soporte ayuda persona telefono correo extension horario llamar escribir '
                + 'reportar avisar sistemas contacto',
            texto: `<p>Yo sólo explico cómo funciona esta pantalla. Para un caso concreto —una
                    factura que usted sabe que sí se cobró, un número que no le cuadra, un
                    permiso— hablan las personas:</p>
                    <ul>
                        <li><strong>soporte@rori.com</strong></li>
                        <li><strong>Ext. 2309 / +58 412-333-0319</strong></li>
                        <li>Lunes a viernes, de <strong>7:30 a 16:00</strong></li>
                    </ul>
                    <p>Cuando escriba, diga <strong>el período que pidió</strong>, <strong>la
                    hora</strong> a la que lo pidió y, si es por un documento, <strong>la tienda, el
                    tipo y el número</strong>. Con eso la consulta se reproduce; sin eso, hay que
                    adivinar.</p>`,
            vista: '#pieSoporte',
            ir: 'Soporte técnico',
            relacionados: ['manuales'],
        },

        // --- Pedir un período --------------------------------------------

        {
            id: 'periodo-fechas',
            menu: 'auditar',
            icono: 'calendario',
            titulo: 'Poner las dos fechas',
            claves: 'fechas desde hasta periodo rango dia mes elegir poner calendario futuro hoy',
            texto: `<p>En el recuadro de la derecha están <strong>Desde</strong> y
                    <strong>Hasta</strong>. Vienen puestos en el primer día del mes en curso y en
                    hoy.</p>
                    <p>Ninguno de los dos admite una fecha posterior a hoy: el futuro no se audita
                    porque todavía no ha ocurrido. Puestas las dos, pulse
                    <strong>Auditar</strong>.</p>`,
            vista: '#formAuditoria',
            ir: 'las fechas',
            relacionados: ['atajos', 'tope-93', 'cuanto-tarda'],
        },
        {
            id: 'atajos',
            menu: 'auditar',
            icono: 'recargar',
            titulo: 'Los cuatro atajos',
            claves: 'atajos este mes pasado ayer hoy rapido un clic botones frecuente',
            texto: `<p>Debajo del botón hay cuatro: <strong>Este mes</strong>, <strong>Mes
                    pasado</strong>, <strong>Ayer</strong> y <strong>Hoy</strong>.</p>
                    <p>Cada uno rellena las dos fechas <strong>y lanza la consulta de una
                    vez</strong>: no hace falta pulsar <strong>Auditar</strong> después.</p>`,
            vista: '#formAuditoria',
            ir: 'los atajos',
            relacionados: ['periodo-fechas', 'cada-cuanto'],
        },
        {
            id: 'tope-93',
            menu: 'auditar',
            icono: 'regla',
            titulo: 'El tope de 93 días',
            claves: 'tope limite 93 dias rango pedido ano trimestre mes a mes demasiado largo '
                + 'el rango pedido son y el tope es',
            texto: `<p>De una vez se pueden pedir hasta <strong>93 días</strong>. Si pide más, la
                    aplicación se lo dice con el número exacto de días que pidió y no consulta.</p>
                    <p>Un año se pide <strong>mes a mes</strong>. Así, además, un fallo a mitad de
                    camino no se lleva por delante lo que ya había salido bien.</p>`,
            relacionados: ['periodo-fechas', 'cuanto-tarda'],
        },
        {
            id: 'cuanto-tarda',
            menu: 'auditar',
            icono: 'reloj',
            titulo: 'Por qué tarda tanto',
            claves: 'tarda lento espera segundos minuto colgado trabado indice rtp325 detalle '
                + 'cargador cuanto falta',
            texto: `<p>Entre <strong>veinte segundos y un minuto</strong>, y lo mismo un día que un
                    mes entero. No está colgada: está leyendo.</p>
                    <p>El paso largo es siempre el mismo. <code>RTP325</code>, el detalle, tiene 6,6
                    millones de líneas y el AS400 no tiene ninguna forma rápida de buscar en él por
                    fecha, así que lo recorre entero. Mientras espera, el cargador va diciendo cuál
                    de los archivos está leyendo.</p>
                    <p>Hay una petición hecha a Sistemas para arreglarlo: con un camino de acceso
                    por fecha, esto bajaría a décimas de segundo.</p>`,
            relacionados: ['no-insistir', 'tarda-mucho'],
        },
        {
            id: 'no-insistir',
            menu: 'auditar',
            icono: 'aviso',
            titulo: 'No vuelva a pulsar mientras espera',
            claves: 'volver a pulsar dos veces doble clic insistir boton apagado deshabilitado '
                + 'no responde nada pasa',
            texto: `<p>Cada pulsación abre <strong>otra</strong> consulta al AS400 sobre el mismo
                    período, y las dos compiten entre sí: se tarda más, no menos.</p>
                    <p>El botón <strong>Auditar</strong> se deshabilita solo mientras hay una
                    consulta en marcha. Si lo ve apagado, es que la suya sigue viva: espere.</p>`,
            relacionados: ['cuanto-tarda'],
        },
        {
            id: 'volver-a-consultar',
            menu: 'auditar',
            icono: 'recargar',
            titulo: 'Volver a consultar el mismo período',
            claves: 'volver a consultar repetir recargar refrescar comprobar corregido otra vez '
                + 'hora de la corrida cuanto tardo',
            texto: `<p>En la cabecera de <strong>El veredicto</strong>, el botón <strong>Volver a
                    consultar</strong> repite la consulta con las mismas fechas. Se usa cuando se
                    acaba de corregir algo en la tienda y quiere comprobar que ya cuadra.</p>
                    <p>Al lado, en letra pequeña, está la ficha de la corrida: el período en
                    palabras, la hora exacta a la que se leyó el AS400 y lo que tardó. Si pasa el
                    ratón por encima de esa línea, verá cuánto tardó cada archivo.</p>`,
            vista: '#btnRecargar',
            ir: 'Volver a consultar',
            relacionados: ['que-hacer', 'excel-media-hora'],
        },
        {
            id: 'cada-cuanto',
            menu: 'auditar',
            icono: 'visto',
            titulo: 'Cada cuánto conviene auditar',
            claves: 'cada cuanto frecuencia cuando mes cerrado semana rutina conviene mirar '
                + 'acumular costumbre',
            texto: `<p>Lo normal es auditar <strong>un mes cerrado</strong> cuando se cierra, y
                    <strong>el mes en curso</strong> una vez por semana para no acumular.</p>
                    <p>Lo primero que hay que mirar siempre es la cifra <strong>A REVISAR</strong>:
                    si está en cero, ese período no necesita nada más.</p>`,
            relacionados: ['atajos', 'cifras'],
        },

        // --- Entender el resultado ---------------------------------------

        {
            id: 'cifras',
            menu: 'veredicto',
            icono: 'balanza',
            titulo: 'Las cinco cifras grandes',
            claves: 'cifras veredicto kpi documentos auditados cuadran redondeo a revisar total '
                + 'facturado resumen porcentaje ambar',
            texto: `<p>Arriba, en <strong>El veredicto</strong>:</p>
                    <ul>
                        <li><strong>Documentos auditados</strong>: todos los del período, y cuántos
                        días tuvieron movimiento.</li>
                        <li><strong>Cuadran al céntimo</strong>: los que no hay ni que mirar.</li>
                        <li><strong>Diferencia de redondeo</strong>: céntimos del IGTF, y cuántos
                        bolívares suman entre todos.</li>
                        <li><strong>A REVISAR</strong>: los que hay que ir a ver, y cuánto dinero
                        falta por asentar. Se marca en ámbar cuando hay alguno; si no hay ninguno,
                        dice «ni uno: todo cuadra».</li>
                        <li><strong>Total facturado</strong>: lo vendido en el período y, debajo, lo
                        registrado en formas de pago.</li>
                    </ul>
                    <p>Debajo hay una frase que contesta «¿hay algo mal?» sin tener que interpretar
                    ningún número, y una línea con el resto de los contrastes: el detalle, las
                    anuladas, las que no tienen ni una línea de pago y las manuales.</p>`,
            vista: '#kpis',
            ir: 'El veredicto',
            relacionados: ['clases', 'revisar-lista'],
        },
        {
            id: 'clases',
            menu: 'veredicto',
            icono: 'visto',
            titulo: 'Qué significa cada resultado',
            claves: 'resultado cuadra redondeo revisar no aplica clase significa columna '
                + 'tolerancia centimo diferencia',
            texto: `<p>Cada documento sale con uno de estos cuatro, en la columna
                    <strong>Resultado</strong>:</p>
                    <ul>
                        <li><strong>cuadra</strong>: la diferencia no pasa de 0,01 Bs. Nada que
                        hacer.</li>
                        <li><strong>redondeo</strong>: no pasa de 5,00 Bs. Céntimos del IGTF; no es
                        dinero que falte.</li>
                        <li><strong>REVISAR</strong>: pasa de 5,00 Bs. Hay que ir a ver esa
                        factura.</li>
                        <li><strong>no aplica</strong>: no hay nada que contrastar. Nada que
                        hacer.</li>
                    </ul>
                    <p>De los cuatro, sólo <strong>REVISAR</strong> pide algo de usted. Los otros
                    tres están cerrados.</p>`,
            relacionados: ['corte-5-bs', 'ajustes', 'revisar-lista'],
        },
        {
            id: 'corte-5-bs',
            menu: 'veredicto',
            icono: 'regla',
            titulo: 'Por qué el corte está en 5 bolívares',
            claves: 'corte 5 bolivares tolerancia redondeo igtf umbral porque ese numero hueco '
                + 'medido justificacion',
            texto: `<p>No es un número elegido para que salgan pocos avisos. Se midieron las
                    diferencias reales y no se reparten poco a poco: forman dos grupos separados por
                    un abismo.</p>
                    <ul>
                        <li>47 documentos entre 0,02 y 4,38 Bs, 45 de ellos con IGTF.</li>
                        <li>8 documentos entre 2.000,00 y 168.136,17 Bs.</li>
                        <li>Entre 4,38 y 2.000,00 Bs, <strong>nada</strong>.</li>
                    </ul>
                    <p>El corte cae dentro de ese hueco, así que ponerlo en 10, en 100 o en 1.000
                    clasificaría exactamente igual. En la primera corrida contra producción el
                    reparto se repitió: los 46 de redondeo sumaban 92,33 Bs entre todos y los seis a
                    revisar empezaban en 2.000.</p>`,
            relacionados: ['clases', 'formula-total'],
        },
        {
            id: 'formula-total',
            menu: 'veredicto',
            icono: 'dinero',
            titulo: 'De dónde sale el total',
            claves: 'total formula bruto descuento iva igtf seniat abono importes encabezado '
                + 'de donde sale 98 por ciento medido',
            texto: `<p>El AS400 guarda seis importes en el encabezado y <strong>ninguno se llama
                    «total»</strong>. El que usa este informe es
                    <strong>bruto − descuento + IVA + IGTF</strong>.</p>
                    <p>Se eligió probando las diez combinaciones razonables contra la suma de pagos
                    de 3.626 documentos: acierta el <strong>98,5 %</strong>, y el 98,7 % en la
                    primera corrida contra producción, sobre 4.004 documentos.</p>
                    <p>En la ficha de cada documento verá esa cuenta hecha importe por importe, con
                    el nombre que tiene cada campo en el AS400, y también los dos que quedan
                    <strong>fuera</strong> de la fórmula —el descuento SENIAT y el abono—, marcados
                    como tales. Así nadie tiene que fiarse de que están donde se dice.</p>`,
            relacionados: ['ficha', 'corte-5-bs', 'avisos'],
        },
        {
            id: 'avisos',
            menu: 'veredicto',
            icono: 'info',
            titulo: 'Los avisos del informe',
            claves: 'avisos advierte supuestos seniat fecha imposible sin encabezado ot dias sin '
                + 'documentos futuro ambar que significa',
            texto: `<p>El panel <strong>Lo que este informe advierte de sí mismo</strong> es lo que
                    no se calla: supuestos que podrían haber dejado de ser verdad desde que se
                    midieron, y lo que se encontró y no cabe en ninguna columna. Los que más se
                    ven:</p>
                    <ul>
                        <li>Documentos con <strong>descuento SENIAT</strong> distinto de cero, o
                        encabezados con una <strong>fecha imposible</strong>. Éstos son los serios.</li>
                        <li>Formas de pago registradas contra un documento que no existe en el
                        archivo de facturas.</li>
                        <li>La forma de pago <code>OT</code>, que se usa y no está dada de alta en el
                        catálogo.</li>
                        <li>Que el período llega a un día que todavía no ha ocurrido, o que hay días
                        sin documentos dentro del tramo.</li>
                    </ul>
                    <p>Un aviso <strong>no</strong> significa que el informe esté mal: significa que
                    hay algo que mirar antes de firmarlo. Si salen los dos primeros, consulte con
                    soporte antes de entregar las cifras.</p>`,
            vista: '#panelAvisos',
            ir: 'los avisos',
            relacionados: ['forma-ot', 'soporte'],
        },

        // --- Lo que hay que revisar --------------------------------------

        {
            id: 'revisar-lista',
            menu: 'revisar',
            icono: 'aviso',
            titulo: 'La tabla de lo que hay que revisar',
            claves: 'revisar tabla falta pagado total porcentaje formas registradas negativo '
                + 'de mas ordenadas diferencia accionable',
            texto: `<p>Ese panel sólo aparece cuando hay algo, y va arriba porque es la única parte
                    del informe sobre la que hay que hacer algo. Las filas vienen ordenadas <strong>de
                    mayor a menor diferencia</strong>: lo primero que ve es lo más caro.</p>
                    <ul>
                        <li><strong>Total</strong>: lo que dice el encabezado que se vendió.</li>
                        <li><strong>Pagado</strong>: la suma de todas sus formas de pago.</li>
                        <li><strong>Falta</strong>: la diferencia, el dinero que no está asentado.</li>
                        <li><strong>%</strong>: qué parte del total sí quedó registrada.</li>
                    </ul>
                    <p>Un número <strong>negativo</strong> en «Falta» no significa que falte:
                    significa que se registró de <strong>más</strong> que el total de la factura.
                    También hay que mirarlo, pero es otra cosa.</p>`,
            vista: '#panelRevisar',
            ir: 'Lo que hay que revisar',
            relacionados: ['observacion', 'que-hacer'],
        },
        {
            id: 'observacion',
            menu: 'revisar',
            icono: 'nota',
            titulo: 'Cómo se lee «Qué se ve en el archivo»',
            claves: 'observacion que se ve en el archivo patron hecho acusacion cashea vibes '
                + 'inicial financiado duplicado columna diagnostico',
            texto: `<p>Esa columna —en el Excel se llama <strong>Observación</strong>— dice el patrón
                    que se observa, no la causa. «Se registró el 80,0 % del total con 1 forma de
                    pago» es un hecho que está en el archivo; «el cajero no asentó la inicial» sería
                    una acusación que el archivo no respalda.</p>
                    <ul>
                        <li>«No tiene ni una línea de pago registrada»: la factura se emitió y el
                        cobro no se asentó nunca.</li>
                        <li>«se registró el 80 %» con una forma de financiamiento: se asentó la parte
                        financiada y falta la inicial.</li>
                        <li>«se registró el 20 %» sin financiamiento: se asentó la inicial y falta la
                        parte financiada.</li>
                        <li>«Se registró X Bs MÁS que el total»: un cobro duplicado, o un importe
                        tecleado de más.</li>
                    </ul>
                    <p>Cuando la observación habla de la inicial o de la parte financiada va
                    <strong>en condicional</strong> a propósito: es la lectura más probable de lo que
                    se ve, no un veredicto. Quien tenga la factura delante decide.</p>`,
            relacionados: ['que-hacer', 'formas-de-pago'],
        },
        {
            id: 'que-hacer',
            menu: 'revisar',
            icono: 'herramienta',
            titulo: 'Qué hacer con un documento a revisar',
            claves: 'que hago que hacer pasos buscar factura tienda anotar decidir asentar cobro '
                + 'comprobar corregir seguimiento',
            texto: `<p>Cinco pasos:</p>
                    <ul>
                        <li><strong>Ábralo</strong>: pulse su fila en <strong>Documento a
                        documento</strong> y lea la ficha completa.</li>
                        <li><strong>Anote</strong> la fecha, la tienda, el tipo y el número, lo que
                        falta y el porcentaje registrado.</li>
                        <li><strong>Busque la factura</strong>, en la tienda o en el AS400, y mire
                        cómo se cobró de verdad.</li>
                        <li><strong>Decida</strong>, que es lo que ningún programa puede hacer: si se
                        cobró y no se asentó, hay que asentar el cobro que falta; si está financiada,
                        mire si falta la inicial o la parte financiada.</li>
                        <li><strong>Compruebe</strong>: pulse <strong>Volver a consultar</strong> con
                        el mismo período y ese documento tiene que pasar a <strong>cuadra</strong>.</li>
                    </ul>
                    <p>Si el cobro sí está y la aplicación no lo ve, eso sería un fallo del informe:
                    avise a soporte con el documento.</p>`,
            relacionados: ['ficha', 'volver-a-consultar', 'falso-positivo'],
        },
        {
            id: 'ficha',
            menu: 'revisar',
            icono: 'archivo',
            titulo: 'La ficha de un documento',
            claves: 'ficha fila abrir detalle documento diagnostico contraste desglose cliente '
                + 'vendedor caja hora cerrar esc enter',
            texto: `<p>Pulse cualquier fila de la tabla —con el ratón, o con Enter si va con el
                    teclado— y se abre la ficha. Trae cuatro bloques: <strong>Qué se ve en el
                    archivo</strong> con el diagnóstico sin recortar, <strong>El contraste</strong>,
                    <strong>De dónde sale el total</strong> importe por importe y <strong>El detalle
                    y las formas de pago</strong>.</p>
                    <p>Al final están la fecha, la tienda con su código, la clase de documento y, si
                    lo tiene, el cliente, el vendedor, la caja y la hora. Se cierra con la equis,
                    pulsando fuera de la ficha o con la tecla <strong>Esc</strong>.</p>`,
            vista: '#titulo-tabla',
            ir: 'Documento a documento',
            relacionados: ['formula-total', 'tabla-filtros'],
        },
        {
            id: 'falso-positivo',
            menu: 'revisar',
            icono: 'auricular',
            titulo: 'El cobro sí está y el informe lo marca',
            claves: 'falso error del informe cobro si esta pero sale a revisar equivocado fallo '
                + 'no lo ve avisar soporte',
            texto: `<p>Eso sí sería un fallo del informe, y hay que mirarlo. Avise a soporte con
                    <strong>la tienda, el tipo y el número</strong> del documento y la hora a la que
                    pidió la consulta.</p>
                    <p>Antes de llamar, una comprobación que ahorra la llamada: abra la ficha del
                    documento y mire el bloque <strong>El detalle y las formas de pago</strong>. Si
                    el cobro aparece ahí con otro importe, no es que no se vea: es que no
                    coincide.</p>`,
            vista: '#pieSoporte',
            ir: 'Soporte técnico',
            relacionados: ['ficha', 'soporte'],
        },

        // --- Lo que parece un error --------------------------------------

        {
            id: 'anuladas',
            menu: 'casos',
            icono: 'visto',
            titulo: 'Una factura ANULADA no es un descuadre',
            claves: 'anulada anuladas estado cero piezas cero venta conserva lineas detalle '
                + 'parece error vigente',
            texto: `<p>Una factura anulada queda con <strong>cero piezas y cero venta</strong> en el
                    encabezado, pero conserva sus líneas de detalle. Es el comportamiento correcto
                    del AS400, no un error.</p>
                    <p>Y además cuadran en pagos: en la primera corrida contra producción, las 110
                    anuladas del mes cuadraron todas. Salen en la tabla con el estado
                    <strong>ANULADA</strong> y no se marcan a revisar — marcarlas haría el informe
                    falso en casi cien filas.</p>`,
            relacionados: ['clases', 'tabla-filtros'],
        },
        {
            id: 'abonos',
            menu: 'casos',
            icono: 'dinero',
            titulo: 'Las notas de crédito ABON (abonos)',
            claves: 'abono abon nota de credito clase 3 apartado dinero entra detalle no cuadra '
                + 'guion dif det mercancia',
            texto: `<p>Un abono no mueve mercancía: mueve <strong>dinero</strong>. Es lo que el
                    cliente entrega a cuenta de un apartado. Sus líneas de detalle son la mercancía
                    de la factura original, que no tiene por qué sumar lo que se abonó.</p>
                    <p>Así que en un abono <strong>el contraste del detalle no aplica</strong> —en la
                    columna «Dif. det.» verá un guion, no un cero— pero el dinero sí entró y sí tiene
                    forma de pago. Los 31 abonos del mes medido cuadraron los 31.</p>`,
            relacionados: ['ajustes', 'clases'],
        },
        {
            id: 'ajustes',
            menu: 'casos',
            icono: 'nota',
            titulo: 'Las notas de crédito AJUS (ajustes)',
            claves: 'ajuste ajus nota de credito clase 2 no aplica sin detalle sin forma de pago '
                + 'corrige factura 26829 ccct',
            texto: `<p>Un ajuste se descuenta de la factura que corrige. No lleva mercancía propia ni
                    movimiento de dinero propio: de las 55 que hay desde enero de 2024, <strong>ni
                    una tiene detalle ni forma de pago</strong>. No hay nada que contrastar, así que
                    salen como <strong>no aplica</strong>.</p>
                    <p>La regla salió de un caso real: <strong>CCCT · NC 26829</strong>, 42,40 Bs,
                    siete piezas en el encabezado, cero líneas de detalle y cero formas de pago. Con
                    las reglas de antes salía como «falta por asentar 42,40 Bs». No faltaba nada.</p>`,
            relacionados: ['abonos', 'clases'],
        },
        {
            id: 'forma-ot',
            menu: 'casos',
            icono: 'etiqueta',
            titulo: 'La forma de pago OT',
            claves: 'ot otros pagos forma de pago sin catalogo idta116 no esta dada de alta '
                + 'marcada aviso financiamiento',
            texto: `<p><code>OT</code> son «otros pagos». Se usa y <strong>no está dada de alta</strong>
                    en el catálogo de formas de pago (<code>IDTA116</code>), así que el informe no
                    puede saber, leyendo el archivo, si es financiamiento o no. Está confirmado que
                    no tiene que ver con financiamiento, y queda pendiente darla de alta.</p>
                    <p>Mientras eso no pase sale marcada en <strong>En qué se cobró</strong>, con su
                    propio aviso. El día que entre en el catálogo, el aviso dejará de salir solo, sin
                    tocar nada.</p>`,
            relacionados: ['formas-de-pago', 'avisos'],
        },

        // --- La tabla y el Excel -----------------------------------------

        {
            id: 'tabla-filtros',
            menu: 'informe',
            icono: 'filtro',
            titulo: 'Filtrar y buscar en la tabla',
            claves: 'filtrar buscar filtro tienda texto documento cliente vendedor caja 300 filas '
                + 'ver mas contador todo cuadran',
            texto: `<p>En <strong>Documento a documento</strong> está todo el período, una fila por
                    documento. Para acotarlo:</p>
                    <ul>
                        <li>Los botones <strong>Todo · A revisar · Redondeo · Cuadran · No
                        aplica</strong>. El que está puesto se ve hundido.</li>
                        <li>La lista de tiendas, que trae sólo las que tienen documentos en el
                        período.</li>
                        <li>El campo de búsqueda: mira en el número de documento, el tipo, el
                        cliente, la cédula o RIF, el vendedor, la caja, la tienda y el desglose de
                        formas de pago. <strong>No</strong> busca dentro de la observación, porque
                        ahí hay palabras como «factura» o «pago» en casi todas las filas y el filtro
                        dejaría de filtrar.</li>
                    </ul>
                    <p>La tabla pinta <strong>300 filas</strong> y el resto a petición, con el botón
                    del final. No es un tope: crear tres mil filas de golpe deja el navegador
                    bloqueado un par de segundos. Si busca algo concreto, el filtro es más rápido que
                    bajar.</p>`,
            vista: '#filtroClase',
            ir: 'los filtros',
            relacionados: ['ficha', 'formas-de-pago'],
        },
        {
            id: 'formas-de-pago',
            menu: 'informe',
            icono: 'dinero',
            titulo: 'En qué se cobró',
            claves: 'formas de pago en que se cobro catalogo idta116 descripcion tipo lineas '
                + 'documentos bolivares porcentaje financiamiento fi efectivo',
            texto: `<p>La tabla de formas de pago del período: código, descripción, tipo, cuántas
                    líneas, en cuántos documentos, cuántos bolívares y qué porcentaje del total
                    representa cada una. Ordenadas de mayor a menor.</p>
                    <p>La descripción y el tipo salen del catálogo del AS400 (<code>IDTA116</code>).
                    Cuando una forma es de <strong>financiamiento</strong>, la columna «Tipo» lo dice
                    con una marca, y eso cambia cómo se lee una factura a la que le falta dinero. Las
                    que no están dadas de alta en el catálogo salen marcadas, con su propio
                    aviso.</p>`,
            vista: '#titulo-formas',
            ir: 'En qué se cobró',
            relacionados: ['forma-ot', 'observacion'],
        },
        {
            id: 'excel-descargar',
            menu: 'informe',
            icono: 'descargar',
            titulo: 'Descargar el Excel',
            claves: 'excel descargar xlsx archivo bajar informe boton arriba abajo lo que veo '
                + 'no consulta de nuevo',
            texto: `<p>El botón <strong>Descargar Excel</strong> está arriba, en la cabecera del
                    veredicto, y abajo, al final de la tabla. Los dos descargan lo mismo.</p>
                    <p>Y lo que descargan es <strong>lo que está viendo</strong>: la corrida que
                    tiene en pantalla, no una consulta nueva. Si volviera a consultar, el archivo no
                    sería el que acaba de revisar —entre mirar y descargar las tiendas siguen
                    facturando— y tendría dos informes del mismo período con cifras distintas sin
                    saber cuál creer.</p>`,
            vista: '#btnExcelPie',
            ir: 'Descargar Excel',
            relacionados: ['excel-pestanas', 'excel-media-hora'],
        },
        {
            id: 'excel-pestanas',
            menu: 'informe',
            icono: 'hoja-calculo',
            titulo: 'Las cinco pestañas del Excel',
            claves: 'pestanas hojas resumen a revisar auditoria formas de pago metodo que trae '
                + 'columnas fijas',
            texto: `<ul>
                        <li><strong>Resumen</strong>: las cifras del período, los contrastes, el
                        reparto por tipo, dónde está el dinero por asentar y los avisos.</li>
                        <li><strong>A revisar</strong>: sólo lo accionable, una fila por documento,
                        con su observación entera.</li>
                        <li><strong>Auditoría</strong>: todos los documentos, con filtros y las dos
                        primeras columnas fijas.</li>
                        <li><strong>Formas de pago</strong>: en qué se cobró el período.</li>
                        <li><strong>Método</strong>: cómo se calculó, el corte en 5 Bs y qué
                        documentos no se juzgan.</li>
                    </ul>
                    <p>La pestaña <strong>Método</strong> no es relleno: este informe afirma que
                    faltan cientos de miles de bolívares en una factura concreta, y quien lo reciba
                    tiene derecho a saber de dónde sale ese número sin tener que preguntárselo a
                    nadie.</p>`,
            relacionados: ['excel-descargar', 'formula-total'],
        },
        {
            id: 'excel-media-hora',
            menu: 'informe',
            icono: 'reloj',
            titulo: 'La corrida se guarda media hora',
            claves: 'media hora 30 minutos caduca cache token corrida guardada vuelve a consultar '
                + 'descargar enseguida',
            texto: `<p>La corrida que está en pantalla se guarda <strong>media hora</strong>.
                    Pasada, el botón vuelve a consultar el AS400, porque a esa altura ya no estaría
                    descargando lo que usted miró. El archivo dice dentro a qué hora se leyó el
                    AS400.</p>
                    <p>Si quiere el archivo exacto que tiene delante y ha pasado un rato largo, pulse
                    <strong>Volver a consultar</strong> y descargue enseguida.</p>`,
            relacionados: ['excel-no-coincide', 'volver-a-consultar'],
        },
        {
            id: 'excel-imprimir',
            menu: 'informe',
            icono: 'archivo',
            titulo: 'Imprimir y llevar el informe',
            claves: 'imprimir papel apaisado titulos repetidos numeracion nombre del archivo '
                + 'llevar a la tienda',
            texto: `<p>El archivo sale listo para llevar a la tienda: apaisado donde hace falta,
                    ajustado al ancho, con la fila de títulos repetida en cada página y la numeración
                    en el pie. No hace falta tocar nada antes de imprimir.</p>
                    <p>El nombre lleva el período dentro, así:
                    <code>Auditoria-formas-de-pago_20261101_20261120.xlsx</code>.</p>`,
            relacionados: ['excel-descargar'],
        },

        // --- Si algo va mal ----------------------------------------------

        {
            id: 'vpn',
            menu: 'problemas',
            icono: 'servidor',
            titulo: 'No se pudo conectar con el AS400',
            claves: 'no se pudo conectar as400 servidor vpn conexion red error odbc falla '
                + 'desconectar intentar de nuevo',
            texto: `<p>Casi siempre es la <strong>VPN</strong>: mientras está activa no se llega al
                    servidor. Es, con diferencia, el motivo número uno de las llamadas a soporte.</p>
                    <p>Desconéctela y vuelva a intentarlo. Si sin VPN sigue sin conectar, entonces sí
                    es para soporte: diga la hora a la que lo intentó.</p>`,
            relacionados: ['soporte', 'tarda-mucho'],
        },
        {
            id: 'tarda-mucho',
            menu: 'problemas',
            icono: 'reloj',
            titulo: 'La espera pasa de medio minuto',
            claves: 'tarda mucho medio minuto tres minutos lento primera consulta del dia '
                + 'servidor cargado rtp325 paciencia',
            texto: `<p>Es normal si es la primera consulta del día. El paso largo es el detalle,
                    <code>RTP325</code>, y lo que tarda no depende del rango sino de cómo esté de
                    cargado el servidor: dos corridas del mismo mes tardaron 9,67 s y 42,03 s con un
                    día de diferencia.</p>
                    <p>Si pasa de <strong>tres minutos</strong>, avise a soporte. Y no vuelva a
                    pulsar: dos consultas sobre el mismo período compiten entre sí.</p>`,
            relacionados: ['cuanto-tarda', 'no-insistir'],
        },
        {
            id: 'sin-documentos',
            menu: 'problemas',
            icono: 'lupa',
            titulo: 'No sale ningún documento',
            claves: 'no hay ni un documento vacio ningun resultado sin ventas fechas al reves '
                + 'rango mal domingo feriado falta cargar',
            texto: `<p>«No hay ni un documento» en esas fechas significa una de dos: o son días sin
                    facturación —un domingo, un feriado—, o el rango está mal puesto.</p>
                    <p>Lo que <strong>no</strong> es: que falte cargar algo. Esto lee el AS400 en
                    vivo, así que no hay nada pendiente de cargar.</p>`,
            relacionados: ['periodo-fechas', 'avisos'],
        },
        {
            id: 'respuesta-rara',
            menu: 'problemas',
            icono: 'aviso',
            titulo: 'El servidor contestó algo que no es una respuesta',
            claves: 'el servidor contesto algo que no es una respuesta de esta aplicacion error '
                + 'php apache registro json estado',
            texto: `<p>Eso quiere decir que llegó una página de error de PHP o de Apache en lugar del
                    informe. No se arregla desde la pantalla.</p>
                    <p>Avise a soporte con <strong>la hora exacta</strong> a la que ocurrió: hay que
                    mirar el registro del servidor, y sin la hora hay que adivinar.</p>`,
            relacionados: ['soporte'],
        },
        {
            id: 'cache-aviso',
            menu: 'problemas',
            icono: 'aviso',
            titulo: 'Un aviso ámbar sobre la corrida que no se pudo guardar',
            claves: 'aviso ambar corrida no se pudo guardar cache token excel enseguida informe '
                + 'bueno en pantalla',
            texto: `<p>El informe que tiene en pantalla es bueno: lo que falló es guardar la corrida
                    para el Excel.</p>
                    <p>Para que el archivo sea exactamente ése, pulse <strong>Volver a
                    consultar</strong> y descargue enseguida.</p>`,
            relacionados: ['excel-media-hora', 'soporte'],
        },
        {
            id: 'tienda-sin-nombre',
            menu: 'problemas',
            icono: 'tienda',
            titulo: 'Una tienda sale como «(tienda 47)»',
            claves: 'tienda sin nombre codigo maestro etp045 parentesis no aparece sucursal '
                + 'numero en vez del nombre',
            texto: `<p>Esa tienda no está en el maestro de tiendas del AS400, así que el informe la
                    nombra por su código en lugar de dejarla en blanco.</p>
                    <p>Las cifras de esa fila son buenas: lo que falta es el nombre. Avise a soporte
                    con el código.</p>`,
            relacionados: ['soporte'],
        },
        {
            id: 'excel-no-coincide',
            menu: 'problemas',
            icono: 'hoja-calculo',
            titulo: 'El Excel no coincide con lo que vi',
            claves: 'excel no coincide distinto cifras diferentes archivo otra lectura treinta '
                + 'minutos caducada descargue de nuevo',
            texto: `<p>Pasaron más de <strong>treinta minutos</strong> entre mirar y descargar, así
                    que el botón volvió a consultar el AS400 y el archivo trae otra lectura. Dentro,
                    el archivo dice a qué hora se leyó.</p>
                    <p>Vuelva a consultar y descargue de nuevo, esta vez enseguida.</p>`,
            relacionados: ['excel-media-hora', 'excel-descargar'],
        },
    ];

    /** Menús del nivel de arriba, en el orden en que se usa la pantalla. */
    const MENUS = [
        { id: 'basico',    icono: 'brujula',      titulo: 'Primeros pasos' },
        { id: 'auditar',   icono: 'calendario',   titulo: 'Pedir un período' },
        { id: 'veredicto', icono: 'balanza',      titulo: 'Entender el resultado' },
        { id: 'revisar',   icono: 'aviso',        titulo: 'Lo que hay que revisar' },
        { id: 'casos',     icono: 'visto',        titulo: 'Lo que parece un error' },
        { id: 'informe',   icono: 'hoja-calculo', titulo: 'La tabla y el Excel' },
        { id: 'problemas', icono: 'herramienta',  titulo: 'Si algo va mal' },
    ];

    // =====================================================================
    //  Permisos y busqueda
    // =====================================================================

    /** Un tema sin permiso declarado lo ve cualquiera con sesion. */
    function permitido(tema) {
        if (!tema.permiso) return true;
        return CONFIG.puede(tema.permiso);
    }

    const temasVisibles = () => TEMAS.filter(permitido);
    const buscarTema = (id) => TEMAS.find(t => t.id === id);

    /** Menus que le quedan algo dentro a esta persona. */
    function menusVisibles() {
        const vivos = temasVisibles();
        return MENUS.filter(m => vivos.some(t => t.menu === m.id));
    }

    /**
     * Temas que casan con lo escrito.
     *
     * Se puntua para que "excel" saque primero "Descargar el Excel" y no un
     * tema donde la palabra solo aparece de pasada.
     */
    function coincidencias(texto) {
        const aguja = normalizar(texto);
        if (aguja.length < 2) return [];

        const palabras = aguja.split(/\s+/).filter(p => p.length > 2);

        return temasVisibles()
            .map(tema => {
                const titulo = normalizar(tema.titulo);
                const claves = normalizar(tema.claves || '');
                let punto = 0;

                if (titulo.includes(aguja)) punto += 10;
                if (claves.includes(aguja)) punto += 6;
                palabras.forEach(p => {
                    if (titulo.includes(p)) punto += 3;
                    if (claves.includes(p)) punto += 2;
                });
                return { tema, punto };
            })
            .filter(r => r.punto > 0)
            .sort((a, b) => b.punto - a.punto)
            .slice(0, 4)
            .map(r => r.tema);
    }

    // =====================================================================
    //  Pintado del hilo
    // =====================================================================

    function alFinal() {
        const hilo = $('asis-hilo');
        if (hilo) hilo.scrollTop = hilo.scrollHeight;
    }

    /** Mensaje del bot. El HTML es nuestro, no viene de la base. */
    function decir(html) {
        const hilo = $('asis-hilo');
        if (!hilo) return;
        const div = document.createElement('div');
        div.className = 'asis-msg asis-msg-bot';
        div.innerHTML = html;
        hilo.appendChild(div);
        alFinal();
    }

    /** Lo que "dice" la persona al pulsar una opcion. */
    function decirYo(texto) {
        const hilo = $('asis-hilo');
        if (!hilo) return;
        const div = document.createElement('div');
        div.className = 'asis-msg asis-msg-yo';
        div.textContent = texto;
        hilo.appendChild(div);
        alFinal();
    }

    function escribiendo(mostrar) {
        const hilo = $('asis-hilo');
        if (!hilo) return;

        const previo = hilo.querySelector('.asis-escribiendo');
        if (previo) previo.remove();
        if (!mostrar) return;

        const div = document.createElement('div');
        div.className = 'asis-escribiendo';
        div.innerHTML = '<span></span><span></span><span></span>';
        hilo.appendChild(div);
        alFinal();
    }

    /**
     * Fila de botones.
     *
     * @param {Array} lista  {texto, icono, clase, alPulsar}
     */
    function opciones(lista) {
        const hilo = $('asis-hilo');
        if (!hilo || !lista.length) return;

        const caja = document.createElement('div');
        caja.className = 'asis-opciones';

        lista.forEach(op => {
            const boton = document.createElement('button');
            boton.type = 'button';
            boton.className = 'asis-chip' + (op.clase ? ' ' + op.clase : '');
            boton.innerHTML = svgIcono(op.icono) + esc(op.texto);
            boton.addEventListener('click', () => {
                if (ocupado) return;
                op.alPulsar();
            });
            caja.appendChild(boton);
        });

        hilo.appendChild(caja);
        alFinal();
    }

    /** Responde con la pausa de "escribiendo" delante. */
    function responder(pintar) {
        ocupado = true;
        escribiendo(true);
        setTimeout(() => {
            escribiendo(false);
            pintar();
            ocupado = false;
        }, PAUSA_MS);
    }

    // =====================================================================
    //  Conversacion
    // =====================================================================

    /** Buenos días / buenas tardes / buenas noches. */
    function saludoHorario() {
        const h = new Date().getHours();
        if (h >= 5 && h < 12) return 'Buenos días';
        if (h >= 12 && h < 19) return 'Buenas tardes';
        return 'Buenas noches';
    }

    /** Nombre de pila, capitalizado, segun CONFIG.ordenNombre. */
    function primerNombre() {
        const completo = CONFIG.nombreUsuario().trim();
        if (completo === '') return '';
        const partes = completo.split(/\s+/);
        const pila = (CONFIG.ordenNombre === 'apellido-nombre' && partes.length >= 3)
            ? partes[2]
            : partes[0];
        return pila.charAt(0).toUpperCase() + pila.slice(1).toLowerCase();
    }

    function nombreBot() {
        return $('asistente')?.dataset.nombre || 'Asistente';
    }

    function menuPrincipal(intro) {
        if (intro) decir(intro);

        opciones(menusVisibles().map(m => ({
            texto: m.titulo,
            icono: m.icono,
            alPulsar: () => abrirMenu(m.id),
        })));
    }

    function abrirMenu(idMenu) {
        const menu = MENUS.find(m => m.id === idMenu);
        const dentro = temasVisibles().filter(t => t.menu === idMenu);
        if (!menu) return;

        decirYo(menu.titulo);
        responder(() => {
            decir(`<p>Esto es lo que te puedo contar de <strong>${esc(menu.titulo.toLowerCase())}</strong>:</p>`);
            opciones([
                ...dentro.map(t => ({
                    texto: t.titulo,
                    icono: t.icono,
                    alPulsar: () => abrirTema(t.id),
                })),
                { texto: 'Volver', icono: 'flecha-izquierda', clase: 'asis-chip-suave', alPulsar: volverAlMenu },
            ]);
        });
    }

    function abrirTema(idTema, saltarEco) {
        const tema = buscarTema(idTema);
        if (!tema || !permitido(tema)) return;

        if (!saltarEco) decirYo(tema.titulo);

        responder(() => {
            decir(tema.texto);

            const botones = [];

            // Llevar hasta ese sitio sólo si está en la pantalla ahora mismo.
            if (tema.vista && CONFIG.existeVista(tema.vista)) {
                const destino = tema.ir
                    || tema.titulo.split(' ')[0].toLowerCase().replace(/^./, c => c.toUpperCase());
                botones.push({
                    texto: 'Ir a ' + destino,
                    icono: 'flecha-derecha',
                    clase: 'asis-chip-ir',
                    alPulsar: () => irA(tema.vista, destino),
                });
            }

            (tema.relacionados || []).forEach(id => {
                const rel = buscarTema(id);
                if (rel && permitido(rel)) {
                    botones.push({ texto: rel.titulo, icono: rel.icono, alPulsar: () => abrirTema(rel.id) });
                }
            });

            botones.push({
                texto: 'Otro tema', icono: 'lista', clase: 'asis-chip-suave', alPulsar: volverAlMenu,
            });

            opciones(botones);
        });
    }

    function irA(vista, titulo) {
        CONFIG.irA(vista);
        decirYo('Llévame ahí');
        responder(() => {
            decir(`<p>Listo, ahí tienes <strong>${esc(titulo)}</strong>. Te dejo el panel abierto por si necesitas otra cosa.</p>`);
            opciones([{ texto: 'Otro tema', icono: 'lista', clase: 'asis-chip-suave', alPulsar: volverAlMenu }]);
        });
    }

    function volverAlMenu() {
        responder(() => menuPrincipal('<p>Claro. Elige por dónde seguimos:</p>'));
    }

    /** Texto libre del buscador del pie. */
    function preguntar(texto) {
        const limpio = texto.trim();
        if (limpio === '') return;

        decirYo(limpio);
        const encontrados = coincidencias(limpio);

        responder(() => {
            if (!encontrados.length) {
                decir(`<p>No tengo nada sobre eso, y prefiero decírtelo a inventarme una respuesta:
                       esto audita dinero.</p>
                       <p>Prueba con otra palabra, mira el menú, o pregúntale a una persona. El
                       <strong>Manual de usuario (PDF)</strong> del pie trae el detalle completo.</p>`);
                const botones = [{ texto: 'Ver los temas', icono: 'lista', alPulsar: volverAlMenu }];
                if (buscarTema('manuales')) {
                    botones.push({ texto: 'Los manuales en PDF', icono: 'libro', clase: 'asis-chip-suave',
                                   alPulsar: () => abrirTema('manuales') });
                }
                if (buscarTema('soporte')) {
                    botones.push({ texto: 'Hablar con una persona', icono: 'auricular', clase: 'asis-chip-suave',
                                   alPulsar: () => abrirTema('soporte') });
                }
                opciones(botones);
                return;
            }

            // Una sola coincidencia clara: se responde directo.
            if (encontrados.length === 1) {
                abrirTema(encontrados[0].id, true);
                return;
            }

            decir('<p>Puede que te sirva alguno de estos:</p>');
            opciones([
                ...encontrados.map(t => ({
                    texto: t.titulo, icono: t.icono, alPulsar: () => abrirTema(t.id),
                })),
                { texto: 'Ver todos los temas', icono: 'lista', clase: 'asis-chip-suave', alPulsar: volverAlMenu },
            ]);
        });
    }

    // =====================================================================
    //  Apertura y cierre
    // =====================================================================

    function presentarse() {
        const nombre = primerNombre();
        const saludo = saludoHorario() + (nombre ? ', ' + nombre : '');

        decir(`<p><strong>${esc(saludo)}</strong> &#128075;</p>
               <p>Soy <strong>${esc(nombreBot())}</strong>, el asistente de ${esc(CONFIG.nombreSistema)}. Te explico cómo funciona cualquier parte de esta pantalla y te llevo hasta ella.</p>
               <p>Dime por dónde empezamos, o escríbeme tu duda ahí abajo.</p>`);

        opciones(menusVisibles().map(m => ({
            texto: m.titulo,
            icono: m.icono,
            alPulsar: () => abrirMenu(m.id),
        })));
    }

    function abrir() {
        const caja = $('asistente');
        const panel = $('asis-panel');
        const fab = $('asis-fab');
        if (!caja || !panel) return;

        caja.classList.add('abierto');
        panel.hidden = false;
        fab?.setAttribute('aria-expanded', 'true');

        if (!presentado) {
            presentado = true;
            responder(presentarse);
        }
        setTimeout(() => $('asis-buscar')?.focus(), 260);
    }

    function cerrar() {
        const caja = $('asistente');
        const panel = $('asis-panel');
        const fab = $('asis-fab');
        if (!caja || !panel) return;

        caja.classList.remove('abierto');
        panel.hidden = true;
        fab?.setAttribute('aria-expanded', 'false');
        fab?.focus();
    }

    const estaAbierto = () => $('asistente')?.classList.contains('abierto');

    /** Borra la conversacion y vuelve a saludar. */
    function reiniciar() {
        const hilo = $('asis-hilo');
        if (hilo) hilo.innerHTML = '';
        const buscar = $('asis-buscar');
        if (buscar) buscar.value = '';
        ocupado = false;
        responder(presentarse);
    }

    function enlazar() {
        if (arrancado || !$('asistente')) return;
        arrancado = true;

        $('asis-fab')?.addEventListener('click', () => (estaAbierto() ? cerrar() : abrir()));
        $('asis-cerrar')?.addEventListener('click', cerrar);
        $('asis-reiniciar')?.addEventListener('click', reiniciar);

        $('asis-buscar')?.addEventListener('keydown', (e) => {
            if (e.key !== 'Enter') return;
            e.preventDefault();
            if (ocupado) return;
            preguntar(e.target.value);
            e.target.value = '';
        });

        /*
         * Escape cierra, como el resto de los paneles de la aplicación. Pero
         * sólo si no hay nada por encima: la ficha de un documento es un
         * `<dialog>` modal y la ventana «Acerca de» cubre la pantalla, y en
         * los dos casos Escape es suyo. Sin esta comprobación, una tecla
         * cerraría dos cosas a la vez.
         */
        document.addEventListener('keydown', (e) => {
            if (e.key !== 'Escape' || !estaAbierto()) return;
            if (document.querySelector('dialog[open]') !== null) return;
            if (document.getElementById('acerca')?.hasAttribute('hidden') === false) return;

            cerrar();
        });
    }

    return { enlazar, abrir, cerrar };
})();

document.addEventListener('DOMContentLoaded', AsistenteModule.enlazar);
