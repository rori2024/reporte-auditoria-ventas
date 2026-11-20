<?php

declare(strict_types=1);

/**
 * Un libro de Excel escrito desde PHP, sin Excel y sin dependencias.
 *
 * ===========================================================================
 *  POR QUÉ ESTO EXISTE Y NO SE LLAMA A POWERSHELL
 * ---------------------------------------------------------------------------
 *  La primera versión de esta auditoría montaba el Excel con un script de
 *  PowerShell que maneja Excel por COM. Funciona muy bien **en el equipo de
 *  quien lo corre a mano**, y es completamente inviable desde una página web:
 *
 *   · Hace falta Microsoft Excel INSTALADO en el servidor. En un servidor web
 *     no lo está, y licenciarlo para eso no tiene sentido.
 *   · Excel por COM desde un servicio sin sesión de escritorio falla con un
 *     error de permisos que hay que arreglar en la configuración DCOM, y que
 *     vuelve a aparecer en cada actualización de Office.
 *   · Dos personas pidiendo el informe a la vez son dos instancias de Excel
 *     peleándose por el mismo proceso. La que pierde deja un `EXCEL.EXE`
 *     colgado que nadie cierra.
 *
 *  Un `.xlsx` es un ZIP con unos XML dentro. Escribirlo directamente no
 *  necesita nada que el servidor no tenga ya: `ZipArchive`, que viene con
 *  XAMPP activado.
 *
 *  Y NO SE USA UNA LIBRERÍA PORQUE NO HAY NINGUNA INSTALADA
 *  --------------------------------------------------------
 *  PhpSpreadsheet haría esto y mucho más, pero este proyecto no tiene
 *  Composer ni carpeta `vendor`, igual que el resto de las aplicaciones de la
 *  casa. Meter un gestor de dependencias para cinco pestañas es cambiar la
 *  forma de desplegar de toda la empresa.
 * ===========================================================================
 *
 * LA MEMORIA: LAS FILAS NO SE GUARDAN, SE ESCRIBEN
 * ------------------------------------------------
 * Un mes son del orden de 4.000 filas por 28 columnas: 112.000 celdas. Armar
 * el XML de una hoja como una cadena en memoria pide decenas de megas y crece
 * con el rango que se pida. Aquí cada hoja escribe sus filas a un archivo
 * temporal en cuanto las recibe, así que la memoria no depende del tamaño del
 * informe. `memory_limit` deja de ser parte del problema.
 *
 * LOS ESTILOS SE DECLARAN UNA VEZ Y SE USAN POR NOMBRE
 * ----------------------------------------------------
 * `$libro->estilo('moneda', [...])` y luego `$hoja->celda(…, 'moneda')`. El
 * formato de un `.xlsx` obliga a numerar fuentes, rellenos, bordes y
 * combinaciones en cuatro listas separadas y referenciarlas por índice; esos
 * índices no aparecen en el código que escribe el informe, que es lo que hace
 * que se pueda cambiar un color sin contar nada.
 *
 * EL ORDEN DE LOS ELEMENTOS DE UNA HOJA NO ES NEGOCIABLE
 * ------------------------------------------------------
 * El formato fija en qué orden van: `sheetPr`, `dimension`, `sheetViews`,
 * `sheetFormatPr`, `cols`, `sheetData`, `autoFilter`, `mergeCells`,
 * `printOptions`, `pageMargins`, `pageSetup`, `headerFooter` y, al final de
 * todo, `drawing`. Puestos en otro orden, Excel abre el archivo
 * «reparándolo» y se come lo que no entendió sin decir qué. Por eso `volcar()`
 * los escribe siempre en esa secuencia y la API no deja elegir.
 */
final class LibroExcel
{
    /** @var list<HojaExcel> */
    private array $hojas = [];

    /** nombre del estilo => índice en `cellXfs`. @var array<string,int> */
    private array $estilos = [];

    /** @var list<string> XML de cada fuente */
    private array $fuentes = [];

    /** @var list<string> XML de cada relleno */
    private array $rellenos = [];

    /** @var list<string> XML de cada borde */
    private array $bordes = [];

    /** código de formato => id. @var array<string,int> */
    private array $formatos = [];

    /** @var list<string> XML de cada combinación de la lista `cellXfs` */
    private array $combinaciones = [];

    private string $titulo = '';
    private string $autor  = '';

    /**
     * Los formatos numéricos que Excel ya trae, por si alguien los busca aquí.
     *
     * Los `id` por debajo de 164 están reservados y definidos por el formato:
     * no se declaran, se usan. Los propios empiezan en 164, que es lo que dice
     * la especificación.
     */
    private const FORMATOS_INTERNOS = [
        'general' => 0,
        'entero'  => 3,   // #,##0
        'moneda'  => 4,   // #,##0.00
    ];

    private const PRIMER_FORMATO_PROPIO = 164;

    /**
     * Unidades inglesas por píxel (English Metric Units).
     *
     * El dibujo de un `.xlsx` no mide en píxeles ni en puntos: mide en EMU,
     * que son 914.400 por pulgada. A 96 puntos por pulgada, un píxel son
     * 9.525. Es el factor que convierte «el logotipo mide 132 px» en algo que
     * Excel entiende.
     */
    public const EMU_POR_PIXEL = 9525;

    public function __construct(string $titulo = '', string $autor = '')
    {
        $this->titulo = $titulo;
        $this->autor  = $autor;

        /*
         * Los tres primeros elementos de cada lista NO son decorativos.
         *
         * El formato exige que el relleno 0 sea «ninguno» y el 1 «gray125»: si
         * no están, Excel considera el archivo dañado y se ofrece a repararlo,
         * que para quien recibe el informe es lo mismo que si no funcionara.
         * El borde 0 y la fuente 0 son los predeterminados, y el estilo 0 es el
         * que Excel aplica a toda celda que no diga otra cosa.
         */
        $this->fuentes[]  = '<font><sz val="10"/><color theme="1"/><name val="Segoe UI"/><family val="2"/></font>';
        $this->rellenos[] = '<fill><patternFill patternType="none"/></fill>';
        $this->rellenos[] = '<fill><patternFill patternType="gray125"/></fill>';
        $this->bordes[]   = '<border><left/><right/><top/><bottom/><diagonal/></border>';

        $this->estilo('normal', []);
    }

    /**
     * Declara un estilo con nombre.
     *
     * Claves admitidas, todas opcionales:
     *
     *      negrita    bool
     *      cursiva    bool
     *      tamanio    int        puntos
     *      color      'FFFFFF'   color del texto, sin almohadilla
     *      fuente     'Consolas'
     *      fondo      '1E293B'   relleno sólido
     *      degradado  ['0369A1', '0F172A']   relleno en degradado horizontal
     *      formato    'moneda' | 'entero' | 'general' | un código propio
     *      h          'left' | 'center' | 'right'
     *      v          'top' | 'center' | 'bottom'
     *      ajustar    bool       parte el texto en varias líneas
     *      sangria    int
     *      borde      'abajo' | 'arriba' | 'caja' | 'izquierda' | 'lados'
     *      borde_color '0369A1'
     *
     * @param array<string,mixed> $def
     */
    public function estilo(string $nombre, array $def): void
    {
        $idFuente  = $this->idFuente($def);
        $idRelleno = $this->idRelleno($def);
        $idBorde   = $this->idBorde($def);
        $idFormato = $this->idFormato((string) ($def['formato'] ?? 'general'));

        $xf = '<xf numFmtId="' . $idFormato . '" fontId="' . $idFuente
            . '" fillId="' . $idRelleno . '" borderId="' . $idBorde . '" xfId="0"';

        $xf .= ' applyFont="1" applyNumberFormat="1"';

        if ($idRelleno > 1) { $xf .= ' applyFill="1"'; }
        if ($idBorde > 0)   { $xf .= ' applyBorder="1"'; }

        $alineacion = '';

        if (isset($def['h']))        { $alineacion .= ' horizontal="' . $def['h'] . '"'; }
        if (isset($def['v']))        { $alineacion .= ' vertical="' . $def['v'] . '"'; }
        if (!empty($def['ajustar'])) { $alineacion .= ' wrapText="1"'; }
        if (isset($def['sangria']))  { $alineacion .= ' indent="' . (int) $def['sangria'] . '"'; }

        if ($alineacion !== '') {
            $xf .= ' applyAlignment="1"><alignment' . $alineacion . '/></xf>';
        } else {
            $xf .= '/>';
        }

        $this->estilos[$nombre] = count($this->combinaciones);
        $this->combinaciones[] = $xf;
    }

    /** @param array<string,mixed> $def */
    private function idFuente(array $def): int
    {
        $xml = '<font><sz val="' . (int) ($def['tamanio'] ?? 10) . '"/>';

        if (!empty($def['negrita'])) { $xml .= '<b/>'; }
        if (!empty($def['cursiva'])) { $xml .= '<i/>'; }

        $xml .= isset($def['color'])
            ? '<color rgb="FF' . strtoupper((string) $def['color']) . '"/>'
            : '<color theme="1"/>';

        $xml .= '<name val="' . ($def['fuente'] ?? 'Segoe UI') . '"/><family val="2"/></font>';

        $i = array_search($xml, $this->fuentes, true);

        if ($i !== false) {
            return (int) $i;
        }

        $this->fuentes[] = $xml;

        return count($this->fuentes) - 1;
    }

    /** @param array<string,mixed> $def */
    private function idRelleno(array $def): int
    {
        $xml = null;

        if (isset($def['degradado'])) {
            /*
             * UN DEGRADADO SE PINTA DENTRO DE CADA CELDA, NO A LO LARGO DEL
             * RANGO
             * --------------------------------------------------------------
             * Un relleno de Excel es una propiedad de LA CELDA. Si se pone un
             * degradado a veintiocho celdas seguidas no sale un degradado de
             * veintiocho columnas: salen veintiocho degraditos pequeños, uno
             * por celda, y queda como una cebra. Para que el degradado recorra
             * todo el ancho hay que COMBINAR las celdas primero, y entonces es
             * una sola celda y un solo relleno.
             *
             * Por eso en este informe el degradado se usa sólo en el filo de
             * marca de la cabecera, que va combinado de lado a lado, y nunca
             * en la fila de títulos de una tabla.
             */
            [$desde, $hasta] = $def['degradado'];

            $xml = '<fill><gradientFill degree="0">'
                . '<stop position="0"><color rgb="FF' . strtoupper((string) $desde) . '"/></stop>'
                . '<stop position="1"><color rgb="FF' . strtoupper((string) $hasta) . '"/></stop>'
                . '</gradientFill></fill>';
        } elseif (isset($def['fondo'])) {
            $xml = '<fill><patternFill patternType="solid"><fgColor rgb="FF'
                . strtoupper((string) $def['fondo']) . '"/><bgColor indexed="64"/></patternFill></fill>';
        }

        if ($xml === null) {
            return 0;
        }

        $i = array_search($xml, $this->rellenos, true);

        if ($i !== false) {
            return (int) $i;
        }

        $this->rellenos[] = $xml;

        return count($this->rellenos) - 1;
    }

    /** @param array<string,mixed> $def */
    private function idBorde(array $def): int
    {
        if (!isset($def['borde'])) {
            return 0;
        }

        $c = '<color rgb="FF' . strtoupper((string) ($def['borde_color'] ?? 'E2E8F0')) . '"/>';
        $g = (string) ($def['borde_grosor'] ?? 'thin');

        $xml = match ($def['borde']) {
            'abajo' => '<border><left/><right/><top/><bottom style="' . $g . '">' . $c
                . '</bottom><diagonal/></border>',
            'arriba' => '<border><left/><right/><top style="' . $g . '">' . $c
                . '</top><bottom/><diagonal/></border>',
            'izquierda' => '<border><left style="' . $g . '">' . $c
                . '</left><right/><top/><bottom/><diagonal/></border>',
            'lados' => '<border><left style="' . $g . '">' . $c . '</left>'
                . '<right style="' . $g . '">' . $c . '</right><top/><bottom/><diagonal/></border>',
            'caja' => '<border><left style="' . $g . '">' . $c . '</left>'
                . '<right style="' . $g . '">' . $c . '</right>'
                . '<top style="' . $g . '">' . $c . '</top>'
                . '<bottom style="' . $g . '">' . $c . '</bottom><diagonal/></border>',
            default => '<border><left/><right/><top/><bottom/><diagonal/></border>',
        };

        $i = array_search($xml, $this->bordes, true);

        if ($i !== false) {
            return (int) $i;
        }

        $this->bordes[] = $xml;

        return count($this->bordes) - 1;
    }

    private function idFormato(string $codigo): int
    {
        if (isset(self::FORMATOS_INTERNOS[$codigo])) {
            return self::FORMATOS_INTERNOS[$codigo];
        }

        if (isset($this->formatos[$codigo])) {
            return $this->formatos[$codigo];
        }

        $id = self::PRIMER_FORMATO_PROPIO + count($this->formatos);
        $this->formatos[$codigo] = $id;

        return $id;
    }

    /** El índice de un estilo, o el normal si no está declarado. */
    public function indiceEstilo(string $nombre): int
    {
        return $this->estilos[$nombre] ?? 0;
    }

    /**
     * Añade una hoja.
     *
     * El nombre se limpia aquí y no en quien llama: Excel no admite
     * `: \ / ? * [ ]` ni más de 31 caracteres en el nombre de una pestaña, y un
     * nombre inválido no da un error legible — hace que el archivo se abra
     * «reparado» y sin la hoja.
     */
    public function hoja(string $nombre): HojaExcel
    {
        $limpio = str_replace([':', '\\', '/', '?', '*', '[', ']'], ' ', $nombre);
        $limpio = mb_substr(trim($limpio), 0, 31);

        if ($limpio === '') {
            $limpio = 'Hoja' . (count($this->hojas) + 1);
        }

        $hoja = new HojaExcel($this, $limpio);
        $this->hojas[] = $hoja;

        return $hoja;
    }

    /**
     * Escribe el `.xlsx` en disco.
     *
     * @throws RuntimeException si el ZIP no se puede crear o cerrar. Un libro a
     *         medias no se deja en disco: se borra, porque un archivo que
     *         existe y no abre es peor que uno que no existe.
     */
    public function guardar(string $ruta): void
    {
        if (!class_exists('ZipArchive')) {
            throw new RuntimeException(
                'El servidor no tiene habilitada la extensión ZIP de PHP, y un .xlsx es '
                . 'un ZIP. Hay que activar `extension=zip` en el php.ini.'
            );
        }

        if ($this->hojas === []) {
            throw new RuntimeException('El libro no tiene ni una hoja.');
        }

        /*
         * Los dibujos se numeran ANTES de escribir nada: cada hoja con imagen
         * necesita saber su número para referenciarlo desde su propio XML, y
         * su archivo de relaciones tiene que existir con ese mismo número.
         */
        $dibujos = [];

        foreach ($this->hojas as $i => $hoja) {
            if ($hoja->imagenes() !== []) {
                $dibujos[$i] = count($dibujos) + 1;
            }
        }

        $zip = new ZipArchive();

        if ($zip->open($ruta, ZipArchive::CREATE | ZipArchive::OVERWRITE) !== true) {
            throw new RuntimeException('No se pudo crear el archivo ' . basename($ruta) . '.');
        }

        $zip->addFromString('[Content_Types].xml', $this->contentTypes($dibujos));
        $zip->addFromString('_rels/.rels', $this->relsRaiz());
        $zip->addFromString('docProps/core.xml', $this->core());
        $zip->addFromString('xl/workbook.xml', $this->workbook());
        $zip->addFromString('xl/_rels/workbook.xml.rels', $this->relsWorkbook());
        $zip->addFromString('xl/styles.xml', $this->styles());

        /*
         * Los temporales se guardan en una lista y se borran DESPUÉS de cerrar
         * el ZIP: `addFile` no copia el archivo, lo apunta, y `close()` es quien
         * lo lee de verdad. Borrarlos antes deja hojas vacías sin ningún error.
         */
        $temporales = [];
        $medios = [];

        foreach ($this->hojas as $i => $hoja) {
            $tmp = $hoja->volcar($dibujos[$i] ?? null);
            $temporales[] = $tmp;
            $zip->addFile($tmp, 'xl/worksheets/sheet' . ($i + 1) . '.xml');

            if (!isset($dibujos[$i])) {
                continue;
            }

            $n = $dibujos[$i];

            $zip->addFromString(
                'xl/worksheets/_rels/sheet' . ($i + 1) . '.xml.rels',
                '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                . '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                . '<Relationship Id="rIdDib" Type="http://schemas.openxmlformats.org/'
                . 'officeDocument/2006/relationships/drawing" Target="../drawings/drawing'
                . $n . '.xml"/></Relationships>'
            );

            $rels = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                . '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">';

            foreach ($hoja->imagenes() as $j => $img) {
                $destino = 'xl/media/imagen' . $n . '_' . ($j + 1) . '.png';

                // Cada imagen se guarda una vez por hoja que la use. Un
                // logotipo de 3 KB repetido cinco veces son 15 KB: no vale la
                // pena la complicación de compartirlo entre hojas.
                if (!isset($medios[$destino])) {
                    $zip->addFile($img['ruta'], $destino);
                    $medios[$destino] = true;
                }

                $rels .= '<Relationship Id="rIdImg' . ($j + 1) . '" Type="http://schemas.'
                    . 'openxmlformats.org/officeDocument/2006/relationships/image"'
                    . ' Target="../media/imagen' . $n . '_' . ($j + 1) . '.png"/>';
            }

            $zip->addFromString('xl/drawings/_rels/drawing' . $n . '.xml.rels',
                $rels . '</Relationships>');

            $zip->addFromString('xl/drawings/drawing' . $n . '.xml',
                $this->drawing($hoja->imagenes()));
        }

        $cerrado = $zip->close();

        foreach ($temporales as $tmp) {
            @unlink($tmp);
        }

        if (!$cerrado) {
            @unlink($ruta);

            throw new RuntimeException(
                'No se pudo terminar de escribir ' . basename($ruta) . '.'
            );
        }
    }

    /**
     * El XML de los dibujos de una hoja.
     *
     * Se usa `oneCellAnchor`: la imagen se ancla a una celda y conserva su
     * tamaño. La alternativa, `twoCellAnchor`, la estira entre dos celdas y
     * deforma el logotipo en cuanto alguien cambia el ancho de una columna.
     *
     * @param list<array<string,mixed>> $imagenes
     */
    private function drawing(array $imagenes): string
    {
        $xml = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            . '<xdr:wsDr xmlns:xdr="http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing"'
            . ' xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"'
            . ' xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">';

        foreach ($imagenes as $j => $img) {
            $cx = (int) $img['ancho'] * self::EMU_POR_PIXEL;
            $cy = (int) $img['alto'] * self::EMU_POR_PIXEL;

            $xml .= '<xdr:oneCellAnchor>'
                . '<xdr:from>'
                . '<xdr:col>' . ((int) $img['columna'] - 1) . '</xdr:col>'
                . '<xdr:colOff>' . ((int) $img['dx'] * self::EMU_POR_PIXEL) . '</xdr:colOff>'
                . '<xdr:row>' . ((int) $img['fila'] - 1) . '</xdr:row>'
                . '<xdr:rowOff>' . ((int) $img['dy'] * self::EMU_POR_PIXEL) . '</xdr:rowOff>'
                . '</xdr:from>'
                . '<xdr:ext cx="' . $cx . '" cy="' . $cy . '"/>'
                . '<xdr:pic>'
                . '<xdr:nvPicPr>'
                . '<xdr:cNvPr id="' . ($j + 2) . '" name="' . self::x((string) $img['nombre']) . '"'
                . ' descr="' . self::x((string) $img['alt']) . '"/>'
                . '<xdr:cNvPicPr><a:picLocks noChangeAspect="1"/></xdr:cNvPicPr>'
                . '</xdr:nvPicPr>'
                . '<xdr:blipFill><a:blip r:embed="rIdImg' . ($j + 1) . '"/>'
                . '<a:stretch><a:fillRect/></a:stretch></xdr:blipFill>'
                . '<xdr:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="' . $cx . '" cy="' . $cy . '"/>'
                . '</a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom></xdr:spPr>'
                . '</xdr:pic>'
                . '<xdr:clientData/>'
                . '</xdr:oneCellAnchor>';
        }

        return $xml . '</xdr:wsDr>';
    }

    /** @param array<int,int> $dibujos */
    private function contentTypes(array $dibujos): string
    {
        $xml = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            . '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            . '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            . '<Default Extension="xml" ContentType="application/xml"/>'
            . '<Default Extension="png" ContentType="image/png"/>'
            . '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
            . '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
            . '<Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>';

        foreach (array_keys($this->hojas) as $i) {
            $xml .= '<Override PartName="/xl/worksheets/sheet' . ($i + 1) . '.xml"'
                . ' ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>';
        }

        foreach ($dibujos as $n) {
            $xml .= '<Override PartName="/xl/drawings/drawing' . $n . '.xml"'
                . ' ContentType="application/vnd.openxmlformats-officedocument.drawing+xml"/>';
        }

        return $xml . '</Types>';
    }

    private function relsRaiz(): string
    {
        return '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            . '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            . '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
            . '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>'
            . '</Relationships>';
    }

    private function core(): string
    {
        $ahora = gmdate('Y-m-d\TH:i:s\Z');

        return '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            . '<cp:coreProperties'
            . ' xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties"'
            . ' xmlns:dc="http://purl.org/dc/elements/1.1/"'
            . ' xmlns:dcterms="http://purl.org/dc/terms/"'
            . ' xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
            . '<dc:title>' . self::x($this->titulo) . '</dc:title>'
            . '<dc:creator>' . self::x($this->autor) . '</dc:creator>'
            . '<cp:lastModifiedBy>' . self::x($this->autor) . '</cp:lastModifiedBy>'
            . '<dcterms:created xsi:type="dcterms:W3CDTF">' . $ahora . '</dcterms:created>'
            . '<dcterms:modified xsi:type="dcterms:W3CDTF">' . $ahora . '</dcterms:modified>'
            . '</cp:coreProperties>';
    }

    private function workbook(): string
    {
        $xml = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            . '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"'
            . ' xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
            . '<workbookPr date1904="false"/><sheets>';

        foreach ($this->hojas as $i => $hoja) {
            $xml .= '<sheet name="' . self::x($hoja->nombre) . '" sheetId="' . ($i + 1)
                . '" r:id="rId' . ($i + 1) . '"/>';
        }

        $xml .= '</sheets>';

        /*
         * `Print_Titles` es lo que hace que la fila de títulos se repita en
         * CADA página impresa. Sin él, la segunda hoja de papel son cifras sin
         * encabezado, y un informe de cuatro mil filas tiene muchas segundas
         * hojas. Se declara aquí, como nombre definido del libro atado a una
         * hoja concreta, que es el único sitio donde el formato lo admite.
         */
        $nombres = '';

        foreach ($this->hojas as $i => $hoja) {
            $fila = $hoja->filaQueSeRepite();

            if ($fila <= 0) {
                continue;
            }

            // El nombre de la hoja va entre comillas simples y las que lleve
            // dentro se duplican, igual que en SQL.
            $ref = "'" . str_replace("'", "''", $hoja->nombre) . "'!$" . $fila . ':$' . $fila;

            $nombres .= '<definedName name="_xlnm.Print_Titles" localSheetId="' . $i . '">'
                . self::x($ref) . '</definedName>';
        }

        if ($nombres !== '') {
            $xml .= '<definedNames>' . $nombres . '</definedNames>';
        }

        return $xml . '</workbook>';
    }

    private function relsWorkbook(): string
    {
        $xml = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            . '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">';

        foreach (array_keys($this->hojas) as $i) {
            $xml .= '<Relationship Id="rId' . ($i + 1) . '"'
                . ' Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet"'
                . ' Target="worksheets/sheet' . ($i + 1) . '.xml"/>';
        }

        $n = count($this->hojas) + 1;

        return $xml . '<Relationship Id="rId' . $n . '"'
            . ' Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles"'
            . ' Target="styles.xml"/></Relationships>';
    }

    private function styles(): string
    {
        $xml = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            . '<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">';

        if ($this->formatos !== []) {
            $xml .= '<numFmts count="' . count($this->formatos) . '">';

            foreach ($this->formatos as $codigo => $id) {
                $xml .= '<numFmt numFmtId="' . $id . '" formatCode="' . self::x($codigo) . '"/>';
            }

            $xml .= '</numFmts>';
        }

        $xml .= '<fonts count="' . count($this->fuentes) . '">' . implode('', $this->fuentes) . '</fonts>';
        $xml .= '<fills count="' . count($this->rellenos) . '">' . implode('', $this->rellenos) . '</fills>';
        $xml .= '<borders count="' . count($this->bordes) . '">' . implode('', $this->bordes) . '</borders>';

        // `cellStyleXfs` tiene que existir y tener al menos una entrada, y las
        // de `cellXfs` la referencian con xfId="0".
        $xml .= '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>';
        $xml .= '<cellXfs count="' . count($this->combinaciones) . '">'
            . implode('', $this->combinaciones) . '</cellXfs>';
        $xml .= '<cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>';

        return $xml . '</styleSheet>';
    }

    /** Escapa texto para XML. Lo que no sea UTF-8 válido se sustituye. */
    public static function x(?string $texto): string
    {
        $t = (string) $texto;

        if (!mb_check_encoding($t, 'UTF-8')) {
            $t = mb_convert_encoding($t, 'UTF-8', 'UTF-8');
        }

        /*
         * Los caracteres de control por debajo de 0x20 —salvo tabulador, salto
         * y retorno— NO son XML válido, y uno solo basta para que Excel declare
         * el archivo dañado. El AS400 arrastra alguno en campos de texto
         * antiguos, así que se quitan antes de escribir y no después de que
         * alguien se encuentre el aviso.
         */
        $t = preg_replace('/[\x00-\x08\x0B\x0C\x0E-\x1F]/u', '', $t) ?? $t;

        return htmlspecialchars($t, ENT_QUOTES | ENT_XML1, 'UTF-8');
    }

    /** `A`, `B`, … `AA`, para una columna 1-based. */
    public static function columna(int $n): string
    {
        $letras = '';

        while ($n > 0) {
            $resto = ($n - 1) % 26;
            $letras = chr(65 + $resto) . $letras;
            $n = (int) (($n - $resto - 1) / 26);
        }

        return $letras;
    }

    /**
     * Una fecha ISO como número de serie de Excel.
     *
     * Escribir la fecha como texto sería más fácil, y dejaría una columna que
     * no se puede ordenar ni filtrar por fecha — que es justo para lo que se
     * abre este informe.
     *
     * EL CÁLCULO VA EN UTC Y ANCLADO EN UN NÚMERO COMPROBABLE
     * -------------------------------------------------------
     * La forma «obvia» —restar `strtotime('1899-12-30')` y dividir por 86.400—
     * da un día MENOS, y se midió: para el 17/11/2026 devolvía 46.342 cuando
     * Excel dice 46.343. El motivo es que en 1899 muchas zonas horarias tenían
     * un desfase de minutos respecto a su hora actual (en PHP, la hora local
     * media del lugar), así que la resta no son días enteros y el `floor` se
     * cae al día anterior. Un informe con todas las fechas corridas un día es
     * un informe peor que ninguno, porque parece correcto.
     *
     * Así que se cuenta desde la época Unix, en UTC, y se suma el desplazamiento
     * fijo de 25.569 días que separa el 1/1/1970 del origen del calendario de
     * Excel. Ese número incluye ya el 29 de febrero de 1900 que Excel cuenta y
     * que no existió —un fallo de Lotus 1-2-3 que se copió a propósito por
     * compatibilidad— y se comprueba contra un valor conocido: 1/1/2024 son
     * 19.723 días de época más 25.569, es decir 45.292, que es exactamente lo
     * que Excel muestra.
     */
    public const DIAS_EPOCA_A_EXCEL = 25569;

    public static function serieFecha(string $iso): ?int
    {
        $fecha = DateTimeImmutable::createFromFormat(
            '!Y-m-d', substr($iso, 0, 10), new DateTimeZone('UTC')
        );

        if ($fecha === false) {
            return null;
        }

        return intdiv($fecha->getTimestamp(), 86400) + self::DIAS_EPOCA_A_EXCEL;
    }

}

/**
 * Una pestaña del libro.
 *
 * Las filas se escriben a un temporal en cuanto llegan (ver la cabecera de
 * `LibroExcel`), así que el orden de las llamadas importa para las filas pero
 * no para lo demás: anchos, celdas combinadas, panel fijo, autofiltro,
 * imágenes y ajustes de impresión se pueden declarar antes o después, porque
 * se colocan en su sitio del XML al volcar.
 */
final class HojaExcel
{
    public readonly string $nombre;

    private LibroExcel $libro;

    /** @var resource */
    private $filas;

    private int $ultimaFila = 0;
    private int $ultimaColumna = 0;

    /** @var list<array{desde:int,hasta:int,ancho:float}> */
    private array $anchos = [];

    /** @var list<string> */
    private array $combinadas = [];

    /** @var list<array<string,mixed>> */
    private array $imagenes = [];

    private int $congelarFilas = 0;
    private int $congelarColumnas = 0;
    private string $autofiltro = '';
    private bool $rejilla = true;
    private string $colorPestania = '';
    private int $zoom = 100;
    private int $filaRepetida = 0;

    /** @var array<string,mixed> */
    private array $impresion = [];

    public function __construct(LibroExcel $libro, string $nombre)
    {
        $this->libro  = $libro;
        $this->nombre = $nombre;

        /*
         * `php://temp` vive en memoria hasta 2 MB y a partir de ahí se pasa a
         * disco él solo. Es exactamente el comportamiento que hace falta: las
         * hojas pequeñas no tocan el disco y la grande no se come la memoria.
         */
        $f = fopen('php://temp/maxmemory:2097152', 'r+');

        if ($f === false) {
            throw new RuntimeException('No se pudo abrir el temporal de la hoja ' . $nombre . '.');
        }

        $this->filas = $f;
    }

    /** Ancho de un tramo de columnas, en caracteres. */
    public function ancho(int $desde, int $hasta, float $ancho): self
    {
        $this->anchos[] = ['desde' => $desde, 'hasta' => $hasta, 'ancho' => $ancho];

        return $this;
    }

    /**
     * Los anchos de las primeras columnas, de una lista.
     *
     * @param list<float> $anchos
     */
    public function anchos(array $anchos): self
    {
        foreach ($anchos as $i => $a) {
            $this->ancho($i + 1, $i + 1, (float) $a);
        }

        return $this;
    }

    /** Fija las primeras `$filas` filas (y opcionalmente columnas) al desplazar. */
    public function congelar(int $filas, int $columnas = 0): self
    {
        $this->congelarFilas = $filas;
        $this->congelarColumnas = $columnas;

        return $this;
    }

    /** Combina un rango, `A1:F1`. */
    public function combinar(string $rango): self
    {
        $this->combinadas[] = $rango;

        return $this;
    }

    /** Pone el autofiltro en un rango, `A6:AB3800`. */
    public function filtrar(string $rango): self
    {
        $this->autofiltro = $rango;

        return $this;
    }

    /** Quita las líneas de la cuadrícula: el informe trae sus propios bordes. */
    public function sinRejilla(): self
    {
        $this->rejilla = false;

        return $this;
    }

    /** El color de la lengüeta de la pestaña, sin almohadilla. */
    public function color(string $hex): self
    {
        $this->colorPestania = strtoupper($hex);

        return $this;
    }

    /** El nivel de ampliación con el que se abre la hoja. */
    public function zoom(int $porciento): self
    {
        $this->zoom = max(10, min(400, $porciento));

        return $this;
    }

    /**
     * La fila de títulos que se repite en cada página impresa.
     *
     * Sin esto, la página dos de un informe de cuatro mil filas son cifras sin
     * encabezado, y nadie sabe qué columna es cuál.
     */
    public function repetirCabecera(int $fila): self
    {
        $this->filaRepetida = $fila;

        return $this;
    }

    public function filaQueSeRepite(): int
    {
        return $this->filaRepetida;
    }

    /**
     * Cómo se imprime esta hoja.
     *
     *      orientacion  'landscape' | 'portrait'
     *      ajustar      true  -> encoge hasta que quepa a lo ancho en una hoja
     *      pie          el texto del pie, con los códigos de Excel
     *
     * @param array<string,mixed> $opciones
     */
    public function impresion(array $opciones): self
    {
        $this->impresion = $opciones;

        return $this;
    }

    /**
     * Coloca una imagen anclada a una celda, conservando su tamaño.
     *
     * `$dx` y `$dy` son el desplazamiento en píxeles dentro de la celda, que es
     * lo que permite separarla un poco del borde sin depender del ancho de la
     * columna.
     */
    public function imagen(
        string $ruta, int $fila, int $columna,
        ?int $ancho = null, ?int $alto = null,
        int $dx = 0, int $dy = 0,
        string $nombre = 'Imagen', string $alt = ''
    ): self {
        if (!is_file($ruta)) {
            /*
             * Una imagen que falta NO tumba el informe: se omite y se anota.
             * El informe sin logotipo sigue siendo el informe; sin informe no
             * hay nada. Y el registro dice cuál faltó, que es lo que hace que
             * se arregle.
             */
            error_log('[excel] No se encontró la imagen ' . $ruta . ', se omite.');

            return $this;
        }

        $medidas = @getimagesize($ruta);

        if ($medidas === false) {
            error_log('[excel] ' . $ruta . ' no es una imagen legible, se omite.');

            return $this;
        }

        $this->imagenes[] = [
            'ruta'    => $ruta,
            'fila'    => $fila,
            'columna' => $columna,
            'ancho'   => $ancho ?? $medidas[0],
            'alto'    => $alto ?? $medidas[1],
            'dx'      => $dx,
            'dy'      => $dy,
            'nombre'  => $nombre,
            'alt'     => $alt,
        ];

        return $this;
    }

    /** @return list<array<string,mixed>> */
    public function imagenes(): array
    {
        return $this->imagenes;
    }

    /**
     * Escribe una fila entera.
     *
     * Cada valor puede ser:
     *
     *   · un escalar, que se escribe con el estilo `$estilo`
     *   · `['v' => valor, 'e' => 'estilo']`, para una celda que se sale
     *   · `null`, que deja la celda vacía de verdad (no un cero ni un "")
     *
     * @param list<mixed> $valores
     */
    public function fila(int $numero, array $valores, string $estilo = 'normal', ?float $alto = null): self
    {
        $celdas = '';
        $col = 0;

        foreach ($valores as $valor) {
            $col++;

            $estiloCelda = $estilo;
            $v = $valor;

            if (is_array($valor)) {
                $v = $valor['v'] ?? null;
                $estiloCelda = (string) ($valor['e'] ?? $estilo);
            }

            if ($v === null || $v === '') {
                // Una celda con estilo y sin valor: hace falta para que la
                // banda de color llegue hasta el final de la fila.
                $celdas .= '<c r="' . LibroExcel::columna($col) . $numero . '" s="'
                    . $this->libro->indiceEstilo($estiloCelda) . '"/>';
                continue;
            }

            $celdas .= $this->celdaXml($col, $numero, $v, $estiloCelda);
        }

        if ($col > $this->ultimaColumna) {
            $this->ultimaColumna = $col;
        }

        if ($numero > $this->ultimaFila) {
            $this->ultimaFila = $numero;
        }

        $atributos = ' r="' . $numero . '"';

        if ($alto !== null) {
            $atributos .= ' ht="' . $alto . '" customHeight="1"';
        }

        fwrite($this->filas, '<row' . $atributos . '>' . $celdas . '</row>');

        return $this;
    }

    /**
     * Una fila que no empieza en la columna A.
     *
     * Hay una sola forma de escribir una fila y es ésta, y no hay un método
     * «escribe una celda» a propósito: el XML de una hoja es una lista de
     * `<row>`, cada una con sus celdas dentro y cada número de fila UNA sola
     * vez. Un método por celda invita a escribir dos veces la misma fila, y el
     * resultado es un archivo que Excel abre «reparado» y con filas perdidas,
     * sin decir cuáles. Si una fila se escribe en dos trozos, se junta antes.
     *
     * @param list<mixed> $valores
     */
    public function filaDesde(
        int $numero, int $primeraColumna, array $valores, string $estilo = 'normal', ?float $alto = null
    ): self {
        $relleno = array_fill(0, max(0, $primeraColumna - 1), null);

        return $this->fila($numero, array_merge($relleno, $valores), $estilo, $alto);
    }

    private function celdaXml(int $col, int $fila, mixed $valor, string $estilo): string
    {
        $ref = LibroExcel::columna($col) . $fila;
        $s   = $this->libro->indiceEstilo($estilo);

        if (is_int($valor) || is_float($valor)) {
            // Un NAN o un INF escritos como número hacen que Excel declare el
            // archivo dañado; se convierten en celda vacía, que es la verdad.
            if (is_float($valor) && !is_finite($valor)) {
                return '<c r="' . $ref . '" s="' . $s . '"/>';
            }

            return '<c r="' . $ref . '" s="' . $s . '"><v>'
                . rtrim(rtrim(number_format((float) $valor, 6, '.', ''), '0'), '.') . '</v></c>';
        }

        if (is_bool($valor)) {
            return '<c r="' . $ref . '" s="' . $s . '" t="b"><v>' . ($valor ? 1 : 0) . '</v></c>';
        }

        /*
         * `inlineStr` y no la tabla de cadenas compartidas.
         *
         * La tabla compartida ahorra espacio cuando el mismo texto se repite
         * mucho, y aquí el texto que se repite —el resultado, el tipo— es
         * corto, mientras que el que ocupa —el diagnóstico— es distinto en cada
         * fila. A cambio obliga a tener el diccionario entero en memoria hasta
         * el final, que es justo lo que esta clase evita.
         */
        return '<c r="' . $ref . '" s="' . $s . '" t="inlineStr"><is><t xml:space="preserve">'
            . LibroExcel::x((string) $valor) . '</t></is></c>';
    }

    /**
     * Arma el XML completo de la hoja en un archivo temporal y devuelve su ruta.
     *
     * El orden de los elementos lo fija el formato; ver la cabecera de
     * `LibroExcel`.
     */
    public function volcar(?int $numeroDibujo = null): string
    {
        $ruta = tempnam(sys_get_temp_dir(), 'xlsx');

        if ($ruta === false) {
            throw new RuntimeException('No se pudo crear el temporal de la hoja ' . $this->nombre . '.');
        }

        $salida = fopen($ruta, 'w');

        if ($salida === false) {
            throw new RuntimeException('No se pudo escribir el temporal de la hoja ' . $this->nombre . '.');
        }

        $ultima = LibroExcel::columna(max(1, $this->ultimaColumna)) . max(1, $this->ultimaFila);

        fwrite($salida, '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            . '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"'
            . ' xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">');

        /* --- sheetPr: va el PRIMERO o el archivo no vale ----------------- */

        $sheetPr = '';

        if ($this->colorPestania !== '') {
            $sheetPr .= '<tabColor rgb="FF' . $this->colorPestania . '"/>';
        }

        if (!empty($this->impresion['ajustar'])) {
            $sheetPr .= '<pageSetUpPr fitToPage="1"/>';
        }

        if ($sheetPr !== '') {
            fwrite($salida, '<sheetPr>' . $sheetPr . '</sheetPr>');
        }

        fwrite($salida, '<dimension ref="A1:' . $ultima . '"/>');

        /* --- sheetViews --------------------------------------------------- */

        fwrite($salida, '<sheetViews><sheetView workbookViewId="0"'
            . ($this->rejilla ? '' : ' showGridLines="0"')
            . ($this->zoom !== 100
                ? ' zoomScale="' . $this->zoom . '" zoomScaleNormal="' . $this->zoom . '"'
                : ''));

        if ($this->congelarFilas > 0 || $this->congelarColumnas > 0) {
            $celda = LibroExcel::columna($this->congelarColumnas + 1) . ($this->congelarFilas + 1);

            $panel = 'bottomRight';

            if ($this->congelarColumnas === 0) { $panel = 'bottomLeft'; }
            if ($this->congelarFilas === 0)    { $panel = 'topRight'; }

            fwrite($salida, '><pane'
                . ($this->congelarColumnas > 0 ? ' xSplit="' . $this->congelarColumnas . '"' : '')
                . ($this->congelarFilas > 0 ? ' ySplit="' . $this->congelarFilas . '"' : '')
                . ' topLeftCell="' . $celda . '" activePane="' . $panel . '" state="frozen"/>'
                . '<selection pane="' . $panel . '" activeCell="' . $celda
                . '" sqref="' . $celda . '"/></sheetView></sheetViews>');
        } else {
            fwrite($salida, '/></sheetViews>');
        }

        fwrite($salida, '<sheetFormatPr defaultRowHeight="15"/>');

        /* --- cols --------------------------------------------------------- */

        if ($this->anchos !== []) {
            fwrite($salida, '<cols>');

            foreach ($this->anchos as $a) {
                fwrite($salida, '<col min="' . $a['desde'] . '" max="' . $a['hasta']
                    . '" width="' . $a['ancho'] . '" customWidth="1"/>');
            }

            fwrite($salida, '</cols>');
        }

        /* --- sheetData ---------------------------------------------------- */

        fwrite($salida, '<sheetData>');

        rewind($this->filas);
        stream_copy_to_stream($this->filas, $salida);
        fclose($this->filas);

        fwrite($salida, '</sheetData>');

        if ($this->autofiltro !== '') {
            fwrite($salida, '<autoFilter ref="' . $this->autofiltro . '"/>');
        }

        if ($this->combinadas !== []) {
            fwrite($salida, '<mergeCells count="' . count($this->combinadas) . '">');

            foreach ($this->combinadas as $rango) {
                fwrite($salida, '<mergeCell ref="' . $rango . '"/>');
            }

            fwrite($salida, '</mergeCells>');
        }

        /* --- Impresión ---------------------------------------------------- */

        if ($this->impresion !== []) {
            $o = $this->impresion;

            // Centrado a lo ancho: una tabla estrecha impresa pegada al margen
            // izquierdo parece un error de impresión, no un informe.
            fwrite($salida, '<printOptions horizontalCentered="1"/>');

            fwrite($salida, '<pageMargins left="0.4" right="0.4" top="0.5" bottom="0.6"'
                . ' header="0.3" footer="0.3"/>');

            fwrite($salida, '<pageSetup paperSize="1" orientation="'
                . ($o['orientacion'] ?? 'portrait') . '"'
                . (!empty($o['ajustar']) ? ' fitToWidth="1" fitToHeight="0"' : '')
                . '/>');

            if (!empty($o['pie'])) {
                fwrite($salida, '<headerFooter><oddFooter>'
                    . LibroExcel::x((string) $o['pie']) . '</oddFooter></headerFooter>');
            }
        } else {
            fwrite($salida, '<pageMargins left="0.7" right="0.7" top="0.75" bottom="0.75"'
                . ' header="0.3" footer="0.3"/>');
        }

        /* --- Y al final de todo, el dibujo -------------------------------- */

        if ($numeroDibujo !== null) {
            fwrite($salida, '<drawing r:id="rIdDib"/>');
        }

        fwrite($salida, '</worksheet>');
        fclose($salida);

        return $ruta;
    }
}
