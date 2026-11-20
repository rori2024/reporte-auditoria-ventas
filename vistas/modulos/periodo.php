<?php

declare(strict_types=1);

/**
 * El selector del período: lo primero y lo único que hay que rellenar.
 *
 * ===========================================================================
 *  POR QUÉ NO CONSULTA AL CARGAR LA PÁGINA
 * ---------------------------------------------------------------------------
 *  Lo cómodo sería abrir la pantalla con el mes en curso ya consultado. No se
 *  hace, y es a propósito: cada consulta son tres lecturas al AS400 y unos
 *  veinte segundos de sesión ODBC —`RTP325` no tiene índice por fecha y hay
 *  que barrerlo entero—. Una pantalla que consulta sola gasta eso cada vez que
 *  alguien la abre por error, la recarga o la deja en una pestaña de fondo.
 *  Aquí se pide, y mientras no se pida no se molesta al servidor.
 *
 *  Lo que sí está hecho es que pedir el mes en curso sea un solo clic: los
 *  atajos rellenan las dos fechas y lanzan la consulta.
 * ===========================================================================
 *
 * DOS COLUMNAS, Y NO POR ADORNO
 * ------------------------------
 * La primera versión apilaba todo —texto, fechas, atajos, advertencia— en una
 * sola columna. En un monitor de escritorio eso dejaba el contenido amontonado
 * en los primeros 450 px y dos tercios de la pantalla en blanco: el panel
 * ocupaba todo el ancho y no usaba nada.
 *
 * Ahora la explicación va a la izquierda, con su medida de lectura, y el
 * formulario a la derecha dentro de su propia tarjeta. Eso reparte el ancho y,
 * de paso, separa lo que se LEE de lo que se USA, que es la distinción que
 * importa en una pantalla donde sólo hay una acción posible.
 *
 * El hueco de la izquierda se gana explicando los tres archivos, que es el
 * concepto entero de la aplicación: quien entra por primera vez necesita saber
 * qué se está contrastando contra qué, y si no está aquí no está en ningún
 * sitio.
 *
 * Los `max` de los dos campos son HOY. No se puede auditar el futuro, y un
 * campo que admite una fecha imposible obliga a explicar el error después en
 * lugar de evitarlo antes. El servidor lo valida igual —`Periodo::de()`—
 * porque el navegador no es una autoridad.
 */

require_once __DIR__ . '/../iconos.php';
require_once __DIR__ . '/../../servicios/Periodo.php';

$e = static fn (?string $t): string => htmlspecialchars((string) $t, ENT_QUOTES, 'UTF-8');

$hoy        = date('Y-m-d');
$primeroMes = date('Y-m-01');
$mesPasado  = date('Y-m-01', strtotime('first day of last month'));
$finPasado  = date('Y-m-t', strtotime('first day of last month'));
$ayer       = date('Y-m-d', strtotime('-1 day'));

/**
 * Los tres archivos que se contrastan, y qué dice cada uno.
 *
 * Están aquí y no en el CSS ni en el JavaScript porque son contenido: el día
 * que cambie el archivo de formas de pago —ya pasó una vez, de `IDP405` a
 * `IDP116N`— esto se cambia en un sitio.
 */
$archivos = [
    ['codigo' => 'IDP210',  'que' => 'el encabezado', 'dice' => 'cuánto se vendió'],
    ['codigo' => 'RTP325',  'que' => 'el detalle',    'dice' => 'qué se vendió'],
    ['codigo' => 'IDP116N', 'que' => 'las formas de pago', 'dice' => 'con qué se pagó'],
];

?>
<section class="panel anim-entrada" aria-labelledby="titulo-periodo">
    <header class="panel__cabecera">
        <h2 class="panel__titulo" id="titulo-periodo">
            <?= icono('calendario', 18) ?> Qué período se audita
        </h2>
        <span class="panel__meta">se lee del AS400 en vivo</span>
    </header>

    <div class="panel__cuerpo aud-inicio">

        <!-- Izquierda: lo que hay que entender ------------------------- -->
        <div class="aud-explica">
            <p class="aud-intro">
                Una factura del AS400 vive repartida en <strong>tres archivos</strong>, y
                los tres tienen que contar lo mismo. Si la suma de las formas de pago no
                llega al total de la factura, falta un cobro por asentar.
            </p>

            <ul class="aud-archivos">
<?php foreach ($archivos as $a): ?>
                <li class="aud-archivo">
                    <span class="aud-archivo__codigo"><?= $e($a['codigo']) ?></span>
                    <span class="aud-archivo__que"><?= $e($a['que']) ?></span>
                    <span class="aud-archivo__dice"><?= $e($a['dice']) ?></span>
                </li>
<?php endforeach; ?>
            </ul>

            <p class="nota aud-tope">
                El tope es <?= Periodo::MAXIMO_DIAS ?> días de una vez, y un mes tarda
                <strong>entre veinte segundos y un minuto</strong>: <code>RTP325</code> tiene
                6,6 millones de líneas y ningún índice por fecha, así que el servidor lo
                recorre entero y lo que cambia no es el rango, es cómo esté de cargado. Para
                un año, mes a mes.
            </p>
        </div>

        <!-- Derecha: lo único que hay que hacer ------------------------ -->
        <form class="aud-form" id="formAuditoria" novalidate>
            <div class="aud-form__fechas">
                <div class="aud-campo">
                    <label class="etiqueta" for="desde">Desde</label>
                    <input class="campo num" type="date" id="desde" name="desde"
                           value="<?= $e($primeroMes) ?>" max="<?= $e($hoy) ?>" required>
                </div>

                <div class="aud-campo">
                    <label class="etiqueta" for="hasta">Hasta</label>
                    <input class="campo num" type="date" id="hasta" name="hasta"
                           value="<?= $e($hoy) ?>" max="<?= $e($hoy) ?>" required>
                </div>
            </div>

            <button class="btn btn--primario aud-form__enviar" type="submit" id="btnAuditar">
                <?= icono('balanza', 18) ?> Auditar
            </button>

            <div class="aud-atajos" role="group" aria-label="Períodos de uso frecuente">
                <span class="aud-atajos__rotulo">Atajos</span>

                <div class="aud-atajos__botones">
                    <button class="btn btn--tenue" type="button"
                            data-desde="<?= $e($primeroMes) ?>" data-hasta="<?= $e($hoy) ?>">
                        Este mes
                    </button>
                    <button class="btn btn--tenue" type="button"
                            data-desde="<?= $e($mesPasado) ?>" data-hasta="<?= $e($finPasado) ?>">
                        Mes pasado
                    </button>
                    <button class="btn btn--tenue" type="button"
                            data-desde="<?= $e($ayer) ?>" data-hasta="<?= $e($ayer) ?>">
                        Ayer
                    </button>
                    <button class="btn btn--tenue" type="button"
                            data-desde="<?= $e($hoy) ?>" data-hasta="<?= $e($hoy) ?>">
                        Hoy
                    </button>
                </div>
            </div>
        </form>

        <!--
          El sitio donde van los errores. Vive aquí y no se crea al vuelo para
          que el lector de pantalla lo tenga ya anunciado cuando aparezca el
          texto: un `aria-live` que se inserta junto con su contenido no se
          lee, y entonces quien no ve la pantalla no se entera de que la
          consulta falló. Ocupa las dos columnas.
        -->
        <div class="alerta alerta--error aud-oculto aud-ancho-total"
             id="errorAuditoria" role="alert"></div>
    </div>
</section>
