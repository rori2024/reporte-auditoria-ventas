<?php

declare(strict_types=1);

/**
 * Donde se pinta el informe: resumen, avisos, formas de pago y la tabla.
 *
 * ===========================================================================
 *  TODO EL CONTENIDO LO PONE EL NAVEGADOR, Y ESTO ES EL ARMAZÓN
 * ---------------------------------------------------------------------------
 *  No hay nada que PHP pueda pintar aquí: el informe no existe hasta que
 *  alguien pide un período. Así que este archivo declara los huecos —con sus
 *  rótulos, sus `aria-live` y su orden— y `vistas/js/auditoria.js` los llena
 *  con el JSON de `php/auditoria/consultar.php`.
 *
 *  Los huecos están en el HTML y no se crean al vuelo por accesibilidad: una
 *  región `aria-live` que se inserta junto con su contenido NO se anuncia, y
 *  entonces quien usa lector de pantalla no se entera de que la consulta
 *  terminó ni de cuántos documentos hay que revisar.
 * ===========================================================================
 *
 * EL ORDEN DE LA PANTALLA ES EL ORDEN DE LA DECISIÓN
 * --------------------------------------------------
 *   1. El veredicto, en cifras grandes: ¿hay algo que revisar?
 *   2. Lo que hay que revisar, que es lo único accionable.
 *   3. Los avisos, que es lo que el informe no se calla de sí mismo.
 *   4. Las formas de pago, el contexto.
 *   5. La tabla completa, para quien quiera buscar algo concreto.
 *
 * El botón de descargar está arriba Y abajo a propósito: la pantalla es larga,
 * y quien llega al final de la tabla no debería tener que subir para bajarse el
 * archivo.
 */

require_once __DIR__ . '/../iconos.php';

?>
<!--
  La espera. Son varios segundos de verdad —tres lecturas al AS400— y durante
  ellos hay que decir qué está pasando: una pantalla que no se mueve hace que
  la gente vuelva a pulsar, y cada pulsación abre OTRA sesión ODBC sobre el
  mismo rango. El texto lo va cambiando `auditoria.js`.
-->
<section class="panel aud-oculto" id="panelEspera" aria-labelledby="titulo-espera">
    <header class="panel__cabecera">
        <h2 class="panel__titulo" id="titulo-espera">Consultando el AS400</h2>
    </header>
    <div class="panel__cuerpo">
        <!--
          El mismo DOM que genera `loaderRori()` en `vistas/js/loader.js`, pero
          escrito aquí: así existe desde el primer byte de HTML y `mostrar()` /
          `ocultar()` lo encuentran sin tener que inyectarlo. El `role="status"`
          tiene que estar en la página ANTES de que llegue el texto, o el lector
          de pantalla no anuncia nada.
        -->
        <div id="loader" class="loader-container hidden" role="status" aria-live="polite">
            <div class="loader loader-1" aria-hidden="true">
                <div class="tildes">''</div>
                <span>R</span><span>O</span><span>R</span><span>I</span>
            </div>
            <div class="loader-text">leyendo el encabezado de factura</div>
        </div>
    </div>
</section>

<!--
  Mientras no haya informe, esto no existe para nadie: ni se ve ni lo lee un
  lector de pantalla. `hidden` y no sólo `display:none` por lo segundo.
-->
<div id="resultado" hidden>

    <!-- 1. El veredicto ------------------------------------------------- -->

    <section class="panel anim-entrada" aria-labelledby="titulo-veredicto">
        <header class="panel__cabecera">
            <h2 class="panel__titulo" id="titulo-veredicto">
                <?= icono('balanza', 18) ?> El veredicto
            </h2>
            <span class="panel__meta" id="metaCorrida"></span>

            <div class="panel__acciones">
                <button class="btn" type="button" id="btnRecargar"
                        title="Volver a consultar el AS400 con el mismo período">
                    <?= icono('recargar', 16) ?> Volver a consultar
                </button>
                <a class="btn btn--primario" id="btnExcel" href="#" download>
                    <?= icono('descargar', 16) ?> Descargar Excel
                </a>
            </div>
        </header>

        <div class="panel__cuerpo">
            <div class="kpis" id="kpis"></div>

            <!--
              La frase de una línea que resume el veredicto. Va DESPUÉS de las
              cifras en el HTML pero es lo que se anuncia al terminar la
              consulta: es la respuesta a «¿hay algo mal?», y las cifras son el
              detalle de esa respuesta.
            -->
            <p class="aud-veredicto" id="veredicto" aria-live="polite"></p>

            <div class="aud-contraste" id="contraste"></div>
        </div>
    </section>

    <!-- 2. Lo que hay que revisar --------------------------------------- -->

    <section class="panel anim-entrada" id="panelRevisar" aria-labelledby="titulo-revisar" hidden>
        <header class="panel__cabecera">
            <h2 class="panel__titulo" id="titulo-revisar">
                <?= icono('aviso', 18) ?> Lo que hay que revisar
            </h2>
            <span class="panel__meta" id="metaRevisar"></span>
        </header>

        <div class="panel__cuerpo panel__cuerpo--sin-relleno">
            <div class="tabla-envoltura">
                <table class="tabla aud-tabla-revisar">
                    <caption class="sr-solo">
                        Documentos cuya suma de formas de pago no cuadra con el total de la
                        factura, ordenados por tamaño de la diferencia
                    </caption>
                    <thead>
                        <tr>
                            <th scope="col">Fecha</th>
                            <th scope="col">Tienda</th>
                            <th scope="col">Documento</th>
                            <th scope="col" class="aud-der">Total</th>
                            <th scope="col" class="aud-der">Pagado</th>
                            <th scope="col" class="aud-der">Falta</th>
                            <th scope="col" class="aud-der">%</th>
                            <th scope="col">Formas registradas</th>
                            <th scope="col">Qué se ve en el archivo</th>
                        </tr>
                    </thead>
                    <tbody id="cuerpoRevisar"></tbody>
                </table>
            </div>
        </div>
    </section>

    <!-- 3. Los avisos --------------------------------------------------- -->

    <section class="panel anim-entrada" id="panelAvisos" aria-labelledby="titulo-avisos" hidden>
        <header class="panel__cabecera">
            <h2 class="panel__titulo" id="titulo-avisos">
                <?= icono('info', 18) ?> Lo que este informe advierte de sí mismo
            </h2>
            <span class="panel__meta" id="metaAvisos"></span>
        </header>

        <div class="panel__cuerpo">
            <p class="nota">
                Supuestos que podrían haber dejado de ser verdad desde que se midieron, y
                lo que se encontró y no cabe en ninguna columna. Un informe que se entrega
                no puede callarse lo que no sabe.
            </p>
            <ul class="aud-avisos" id="listaAvisos"></ul>
        </div>
    </section>

    <!-- 4. En qué se cobró ---------------------------------------------- -->

    <section class="panel anim-entrada" aria-labelledby="titulo-formas">
        <header class="panel__cabecera">
            <h2 class="panel__titulo" id="titulo-formas">
                <?= icono('dinero', 18) ?> En qué se cobró
            </h2>
            <span class="panel__meta" id="metaFormas"></span>
        </header>

        <div class="panel__cuerpo panel__cuerpo--sin-relleno">
            <div class="tabla-envoltura">
                <table class="tabla aud-tabla-formas">
                    <caption class="sr-solo">
                        Formas de pago usadas en el período, con lo que movió cada una
                    </caption>
                    <thead>
                        <tr>
                            <th scope="col">Código</th>
                            <th scope="col">Descripción (IDTA116)</th>
                            <th scope="col">Tipo</th>
                            <th scope="col" class="aud-der">Líneas</th>
                            <th scope="col" class="aud-der">Documentos</th>
                            <th scope="col" class="aud-der">Bolívares</th>
                            <th scope="col" class="aud-der">% del total</th>
                        </tr>
                    </thead>
                    <tbody id="cuerpoFormas"></tbody>
                </table>
            </div>
        </div>
    </section>

    <!-- 5. La tabla completa -------------------------------------------- -->

    <section class="panel anim-entrada" aria-labelledby="titulo-tabla">
        <header class="panel__cabecera">
            <h2 class="panel__titulo" id="titulo-tabla">
                <?= icono('hoja-calculo', 18) ?> Documento a documento
            </h2>
            <span class="panel__meta" id="metaTabla"></span>
        </header>

        <div class="panel__cuerpo">
            <div class="aud-filtros" role="group" aria-label="Filtros de la tabla">
                <span class="aud-filtros__rotulo"><?= icono('filtro', 16) ?> Filtrar</span>

                <div class="grupo-btn" id="filtroClase" role="group" aria-label="Por resultado">
                    <button class="btn" type="button" data-clase="" aria-pressed="true">Todo</button>
                    <button class="btn" type="button" data-clase="REVISAR">A revisar</button>
                    <button class="btn" type="button" data-clase="REDONDEO">Redondeo</button>
                    <button class="btn" type="button" data-clase="CUADRA">Cuadran</button>
                    <button class="btn" type="button" data-clase="NO APLICA">No aplica</button>
                </div>

                <select class="campo" id="filtroTienda" aria-label="Por tienda">
                    <option value="">Todas las tiendas</option>
                </select>

                <label class="sr-solo" for="filtroTexto">Buscar</label>
                <input class="campo" type="search" id="filtroTexto"
                       placeholder="Documento, cliente, vendedor…" autocomplete="off">
            </div>

            <!--
              La tabla se pinta por tramos, no entera: ver `auditoria.js`. El
              `aria-live` va en el contador de filas y no en la tabla, porque
              anunciar tres mil filas una a una no es accesibilidad, es ruido.
            -->
            <p class="nota aud-contador" id="contadorFilas" aria-live="polite"></p>
        </div>

        <div class="panel__cuerpo panel__cuerpo--sin-relleno">
            <div class="tabla-envoltura aud-envoltura-grande">
                <table class="tabla aud-tabla-grande">
                    <caption class="sr-solo">
                        Todos los documentos del período con su contraste de encabezado,
                        detalle y formas de pago
                    </caption>
                    <thead>
                        <tr>
                            <th scope="col">Fecha</th>
                            <th scope="col">Tienda</th>
                            <th scope="col">Doc.</th>
                            <th scope="col">Clase</th>
                            <th scope="col">Estado</th>
                            <th scope="col" class="aud-der">Líneas</th>
                            <th scope="col" class="aud-der">Total</th>
                            <th scope="col" class="aud-der">Detalle</th>
                            <th scope="col" class="aud-der">Dif. det.</th>
                            <th scope="col" class="aud-der">Formas</th>
                            <th scope="col" class="aud-der">Pagado</th>
                            <th scope="col" class="aud-der">Dif. pago</th>
                            <th scope="col">Resultado</th>
                            <th scope="col">Formas de pago</th>
                        </tr>
                    </thead>
                    <tbody id="cuerpoTabla"></tbody>
                </table>
            </div>
        </div>

        <footer class="panel__pie aud-pie">
            <button class="btn" type="button" id="btnMas" hidden>Ver más filas</button>
            <a class="btn btn--primario" id="btnExcelPie" href="#" download>
                <?= icono('descargar', 16) ?> Descargar Excel
            </a>
        </footer>
    </section>
</div>

<!--
  El detalle de un documento. Se abre al pulsar una fila de la tabla y es
  donde cabe lo que no cabe en una celda: el diagnóstico entero, los importes
  del encabezado uno a uno y el desglose de formas de pago.
-->
<dialog class="aud-ficha" id="ficha" aria-labelledby="fichaTitulo">
    <header class="aud-ficha__cabecera">
        <h2 class="aud-ficha__titulo" id="fichaTitulo"></h2>
        <button class="icon-btn" type="button" id="btnCerrarFicha" aria-label="Cerrar">
            <?= icono('cerrar', 18) ?>
        </button>
    </header>
    <div class="aud-ficha__cuerpo" id="fichaCuerpo"></div>
</dialog>
