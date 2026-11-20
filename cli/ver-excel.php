<?php

declare(strict_types=1);

/**
 * Mira un `.xlsx` en el navegador, sin Excel.
 *
 *     php cli/ver-excel.php almacen/auditoria/Auditoria-....xlsx
 *     php cli/ver-excel.php ruta.xlsx --hojas=1,2
 *     php cli/ver-excel.php ruta.xlsx --salida=C:\temp\vista.html
 *
 * ===========================================================================
 *  PARA QUÉ SIRVE
 * ---------------------------------------------------------------------------
 *  El equipo donde se genera este informe no tiene Excel ni LibreOffice —no
 *  los necesita, porque `servicios/LibroExcel.php` escribe el archivo sin
 *  ellos— y eso deja un problema concreto: no hay forma de VER cómo queda
 *  antes de dárselo a alguien, y los fallos de diseño no se ven en el XML.
 *
 *  Esto lo resuelve a medias y a propósito: lee el `.xlsx` generado y lo pinta
 *  como una página web usando los anchos, los altos, los rellenos, las
 *  fuentes, los bordes y las celdas combinadas que el propio archivo declara.
 *  Contesta las preguntas que cuesta ver de otra forma: ¿el logotipo pisa el
 *  título?, ¿una tarjeta queda estrecha?, ¿se corta una observación larga?,
 *  ¿este color se lee?
 *
 *  Con esto se encontró que las filas de «A revisar» cortaban el diagnóstico
 *  por la mitad: la altura estaba fija en 34 puntos y el texto pedía cuatro
 *  líneas. En el XML no se ve; mirándolo, salta a la vista.
 *
 *  LO QUE NO REPRODUCE, Y NO HAY QUE CREERLE
 *  -----------------------------------------
 *   · Los FORMATOS NUMÉRICOS. Una fecha sale como su número de serie (46.343)
 *     y un importe sin sus dos decimales. Excel los pinta bien; esto no.
 *   · El autofiltro, los paneles fijos y los saltos de página.
 *   · El tipografiado exacto: las medidas son aproximadas.
 *
 *  Para comprobar que el archivo es VÁLIDO está `cli/probar-excel.php`, que
 *  abre el ZIP y valida cada parte. Esto es para mirarlo, no para validarlo.
 * ===========================================================================
 */

if (PHP_SAPI !== 'cli') {
    http_response_code(404);
    exit;
}

/** Un argumento `--clave=valor`. */
function argVer(string $clave, ?string $porDefecto = null): ?string
{
    foreach ($GLOBALS['argv'] as $a) {
        if (str_starts_with($a, '--' . $clave . '=')) {
            return substr($a, strlen($clave) + 3);
        }
    }

    return $porDefecto;
}

/** `AB` -> 28. */
function columnaVer(string $letras): int
{
    $n = 0;

    for ($i = 0; $i < strlen($letras); $i++) {
        $n = $n * 26 + (ord($letras[$i]) - 64);
    }

    return $n;
}

$ruta = $argv[1] ?? '';

if ($ruta === '' || str_starts_with($ruta, '--') || !is_file($ruta)) {
    fwrite(STDERR, "Uso: php cli/ver-excel.php <archivo.xlsx> [--hojas=1,2] [--salida=vista.html]\n");
    exit(1);
}

$hojas  = explode(',', (string) argVer('hojas', '1,2,4,5'));
$salida = (string) argVer('salida', sys_get_temp_dir() . '/vista-excel.html');

$z = new ZipArchive();

if ($z->open($ruta) !== true) {
    fwrite(STDERR, "No es un .xlsx legible: {$ruta}\n");
    exit(1);
}

/* --- Los estilos del libro ---------------------------------------------- */

$st = new SimpleXMLElement((string) $z->getFromName('xl/styles.xml'));

$fuentes = [];

foreach ($st->fonts->font as $fo) {
    $fuentes[] = [
        // Los puntos de Excel a píxeles de pantalla: 96/72.
        'px'      => (float) ($fo->sz['val'] ?? 10) * 4 / 3,
        'negrita' => isset($fo->b),
        'cursiva' => isset($fo->i),
        'color'   => isset($fo->color['rgb']) ? '#' . substr((string) $fo->color['rgb'], 2) : '#0F172A',
        'familia' => (string) ($fo->name['val'] ?? 'Segoe UI'),
    ];
}

$rellenos = [];

foreach ($st->fills->fill as $fi) {
    if (isset($fi->gradientFill)) {
        $paradas = [];

        foreach ($fi->gradientFill->stop as $sp) {
            $paradas[] = '#' . substr((string) $sp->color['rgb'], 2);
        }

        $rellenos[] = 'linear-gradient(90deg,' . implode(',', $paradas) . ')';
    } elseif (isset($fi->patternFill->fgColor['rgb'])) {
        $rellenos[] = '#' . substr((string) $fi->patternFill->fgColor['rgb'], 2);
    } else {
        $rellenos[] = '';
    }
}

$bordes = [];

foreach ($st->borders->border as $bo) {
    $lados = [];

    foreach (['bottom' => 'border-bottom', 'left' => 'border-left',
              'top' => 'border-top', 'right' => 'border-right'] as $lado => $css) {
        if (!isset($bo->$lado['style'])) {
            continue;
        }

        $grosor = (string) $bo->$lado['style'] === 'medium' ? '2px' : '1px';
        $color  = isset($bo->$lado->color['rgb'])
            ? '#' . substr((string) $bo->$lado->color['rgb'], 2)
            : '#E2E8F0';

        $lados[] = $css . ':' . $grosor . ' solid ' . $color;
    }

    $bordes[] = implode(';', $lados);
}

$xfs = [];

foreach ($st->cellXfs->xf as $xf) {
    $xfs[] = [
        'fuente'  => $fuentes[(int) $xf['fontId']] ?? $fuentes[0],
        'relleno' => $rellenos[(int) $xf['fillId']] ?? '',
        'borde'   => $bordes[(int) $xf['borderId']] ?? '',
        'h'       => (string) ($xf->alignment['horizontal'] ?? ''),
        'v'       => (string) ($xf->alignment['vertical'] ?? ''),
        'sangria' => (int) ($xf->alignment['indent'] ?? 0),
        'ajustar' => (string) ($xf->alignment['wrapText'] ?? '') === '1',
    ];
}

/* --- La página ----------------------------------------------------------- */

ob_start();

echo '<!doctype html><html lang="es"><meta charset="utf-8">';
echo '<title>Vista del Excel · ' . htmlspecialchars(basename($ruta)) . '</title>';
echo '<style>body{margin:0;background:#64748B;font-family:"Segoe UI",sans-serif}'
   . '.aviso{color:#fff;font:13px/1.5 "Segoe UI",sans-serif;padding:16px 24px 0}'
   . '.hoja{background:#fff;margin:24px;display:inline-block;position:relative;'
   . 'box-shadow:0 8px 28px rgba(0,0,0,.35);vertical-align:top}'
   . 'table{border-collapse:collapse;table-layout:fixed}'
   . 'td{overflow:hidden;padding:0 4px;vertical-align:middle;white-space:nowrap}'
   . 'img{position:absolute;z-index:5}</style>';

echo '<p class="aviso">Vista aproximada de <b>' . htmlspecialchars(basename($ruta))
   . '</b>. Las fechas salen como su número de serie y los importes sin decimales: '
   . 'eso es cosa del visor, no del Excel.</p>';

foreach ($hojas as $num) {
    $num = trim($num);
    $xml = (string) $z->getFromName('xl/worksheets/sheet' . $num . '.xml');

    if ($xml === '') {
        continue;
    }

    $x = new SimpleXMLElement($xml);

    /* Anchos de columna, de caracteres a píxeles. */
    $anchos = [];

    if (isset($x->cols)) {
        foreach ($x->cols->col as $c) {
            for ($i = (int) $c['min']; $i <= (int) $c['max']; $i++) {
                $anchos[$i] = (int) round((float) $c['width'] * 7) + 5;
            }
        }
    }

    /* Celdas combinadas: la primera manda y las demás no se pintan. */
    $combinadas = [];
    $saltar = [];

    if (isset($x->mergeCells)) {
        foreach ($x->mergeCells->mergeCell as $mc) {
            [$a, $b] = explode(':', (string) $mc['ref']);
            preg_match('/([A-Z]+)(\d+)/', $a, $m1);
            preg_match('/([A-Z]+)(\d+)/', $b, $m2);

            $c1 = columnaVer($m1[1]); $f1 = (int) $m1[2];
            $c2 = columnaVer($m2[1]); $f2 = (int) $m2[2];

            $combinadas[$f1 . '-' . $c1] = [$c2 - $c1 + 1, $f2 - $f1 + 1];

            for ($f = $f1; $f <= $f2; $f++) {
                for ($c = $c1; $c <= $c2; $c++) {
                    if ($f !== $f1 || $c !== $c1) {
                        $saltar[$f . '-' . $c] = true;
                    }
                }
            }
        }
    }

    $maxCol = max(array_keys($anchos) ?: [8]);

    echo '<div class="hoja">';

    /* Las imágenes, situadas en píxeles sumando columnas y filas. */
    if (isset($x->drawing)) {
        $rels = (string) $z->getFromName('xl/worksheets/_rels/sheet' . $num . '.xml.rels');

        if (preg_match('/drawings\/(drawing\d+)\.xml/', $rels, $md) === 1) {
            $dw = new SimpleXMLElement((string) $z->getFromName('xl/drawings/' . $md[1] . '.xml'));
            $ns = $dw->getNamespaces(true);

            foreach ($dw->children($ns['xdr'])->oneCellAnchor as $an) {
                $de = $an->children($ns['xdr'])->from;
                $cx = (int) $an->children($ns['xdr'])->ext->attributes()['cx'] / 9525;
                $cy = (int) $an->children($ns['xdr'])->ext->attributes()['cy'] / 9525;

                $izq = (int) $de->colOff / 9525;

                for ($c = 1; $c <= (int) $de->col; $c++) {
                    $izq += $anchos[$c] ?? 64;
                }

                $arr = (int) $de->rowOff / 9525;

                foreach ($x->sheetData->row as $r) {
                    if ((int) $r['r'] > (int) $de->row) {
                        break;
                    }

                    $arr += isset($r['ht']) ? (float) $r['ht'] * 4 / 3 : 20;
                }

                $png = (string) $z->getFromName(
                    'xl/media/imagen' . substr($md[1], 7) . '_1.png');

                printf('<img src="data:image/png;base64,%s" style="left:%dpx;top:%dpx;'
                    . 'width:%dpx;height:%dpx">', base64_encode($png), $izq, $arr, $cx, $cy);
            }
        }
    }

    echo '<table>';

    foreach ($anchos as $a) {
        printf('<col style="width:%dpx">', $a);
    }

    foreach ($x->sheetData->row as $r) {
        $nf = (int) $r['r'];
        $alto = isset($r['ht']) ? (float) $r['ht'] * 4 / 3 : 20;

        printf('<tr style="height:%.1fpx">', $alto);

        $celdas = [];

        foreach ($r->c as $c) {
            preg_match('/([A-Z]+)(\d+)/', (string) $c['r'], $m);
            $celdas[columnaVer($m[1])] = $c;
        }

        for ($nc = 1; $nc <= $maxCol; $nc++) {
            if (isset($saltar[$nf . '-' . $nc])) {
                continue;
            }

            $c = $celdas[$nc] ?? null;
            $s = $xfs[(int) ($c['s'] ?? 0)] ?? $xfs[0];

            $txt = '';

            if ($c !== null) {
                if ((string) $c['t'] === 'inlineStr') {
                    $txt = (string) $c->is->t;
                } elseif (isset($c->v)) {
                    $v = (float) $c->v;
                    $txt = $v == (int) $v
                        ? number_format($v, 0, ',', '.')
                        : number_format($v, 2, ',', '.');
                }
            }

            $css = 'font-size:' . round($s['fuente']['px']) . 'px'
                . ';color:' . $s['fuente']['color']
                . ';font-family:' . $s['fuente']['familia'] . ',sans-serif'
                . ($s['fuente']['negrita'] ? ';font-weight:700' : '')
                . ($s['fuente']['cursiva'] ? ';font-style:italic' : '')
                . ($s['relleno'] !== '' ? ';background:' . $s['relleno'] : '')
                . ($s['borde'] !== '' ? ';' . $s['borde'] : '')
                . ($s['h'] !== '' ? ';text-align:' . $s['h'] : '')
                . ($s['v'] === 'center' ? ';vertical-align:middle'
                    : ($s['v'] === 'top' ? ';vertical-align:top' : ''))
                // Un nivel de sangría de Excel son unos tres caracteres.
                . ($s['sangria'] > 0 ? ';padding-left:' . ($s['sangria'] * 21 + 4) . 'px' : '')
                . ($s['ajustar'] ? ';white-space:normal' : '');

            $span = $combinadas[$nf . '-' . $nc] ?? [1, 1];

            printf('<td%s%s style="%s">%s</td>',
                $span[0] > 1 ? ' colspan="' . $span[0] . '"' : '',
                $span[1] > 1 ? ' rowspan="' . $span[1] . '"' : '',
                $css, htmlspecialchars($txt));
        }

        echo '</tr>';
    }

    echo '</table></div>';
}

$html = (string) ob_get_clean();

if (@file_put_contents($salida, $html) === false) {
    fwrite(STDERR, "No se pudo escribir {$salida}\n");
    exit(1);
}

printf("Escrito: %s\n", realpath($salida) ?: $salida);
printf("Ábralo en el navegador. OJO: las fechas salen como número y los importes\n");
printf("sin decimales; eso es cosa del visor, no del Excel.\n");
