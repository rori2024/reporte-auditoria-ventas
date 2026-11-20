#!/usr/bin/env node
/* =============================================================================
   generar-manuales.mjs — Los manuales en PDF, a partir de su Markdown.

   El Markdown de docs/ es la fuente: se edita, se versiona y se lee en el
   repositorio. El PDF es lo que se imprime y se manda, y se genera desde
   aquél. Nunca al revés.

       cd docs/_herramientas
       npm install            (la primera vez)
       node generar-manuales.mjs

   No depende del lenguaje ni del código del proyecto: lee docs/manuales.json
   y los .md, y escribe los .pdf al lado. Sirve igual en un proyecto PHP, Python,
   .NET, Java o Node. Lo único que pide es Node 18+ en el equipo que genera.

   El diseño es el de los manuales de roriApp (TCPDF): portada con logotipo,
   cabecera y pie en cada página, avisos en ámbar, tablas y código. Las medidas
   de abajo son las suyas, en milímetros, para que el resultado sea el mismo.

   Opciones:
       --docs <carpeta>      dónde están los .md y manuales.json (por omisión, ..)
       --salida <carpeta>    dónde dejar los PDF (por omisión, la de --docs)
       --solo <NOMBRE>       generar sólo ese manual
   ========================================================================== */

import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import PDFDocument from 'pdfkit';

const AQUI = path.dirname(fileURLToPath(import.meta.url));

/* ---------------------------------------------------------------- opciones */

function opcion(nombre, porDefecto) {
    const i = process.argv.indexOf('--' + nombre);
    return i > -1 && process.argv[i + 1] ? process.argv[i + 1] : porDefecto;
}

const CARPETA = path.resolve(opcion('docs', path.join(AQUI, '..')));
const SALIDA = path.resolve(opcion('salida', CARPETA));
const SOLO = opcion('solo', null);

/* ------------------------------------------------------------------ medidas */

const MM = 72 / 25.4;                  // puntos por milímetro
const mm = n => n * MM;

const PAGINA = { ancho: mm(210), alto: mm(297) };
const MARGEN = { izq: mm(18), der: mm(18), arriba: mm(24), abajo: mm(20) };
const ANCHO_UTIL = PAGINA.ancho - MARGEN.izq - MARGEN.der;

/* La paleta. Sólo `marca` y `marcaOscuro` se adaptan a cada proyecto */
const GRIS = {
    texto: '#2b2b33', titulo: '#333340', portadaTitulo: '#282832',
    suave: '#6e6e78', cabecera: '#8c8c96', generado: '#9696a0',
    linea: '#dcdce4', borde: '#d4d4dc', cabeceraTabla: '#eef0fb',
    fondoCodigo: '#f4f4f8', codigo: '#1f2430', codigoEnLinea: '#b1256b',
    avisoFondo: '#fdf6e3', avisoTexto: '#6b5514',
};

const FUENTE = {
    normal: 'Helvetica', negrita: 'Helvetica-Bold',
    cursiva: 'Helvetica-Oblique', negritaCursiva: 'Helvetica-BoldOblique',
    codigo: 'Courier',
};

/* Tamaños del cuerpo, en puntos */
const TAM = { h1: 17, h2: 14, h3: 12, h4: 11, p: 10, tabla: 9, codigo: 8.5, aviso: 9.5 };

/* --------------------------------------------------------------- caracteres

   Helvetica sólo trae Windows-1252: tildes, ñ, la raya «—», «», · y €, sí;
   flechas, símbolos y emojis, no, y lo que falta sale como un carácter roto.
   Se cambia aquí y no en el Markdown, que se lee en el editor, donde la
   flecha se ve bien. Si aparece otro, se añade a la tabla. */

const SUSTITUCIONES = {
    '→': '->', '←': '<-', '⇒': '=>', '↔': '<->',
    '✓': '(sí)', '✔': '(sí)', '✗': '(no)', '✘': '(no)',
    '…': '...', '≥': '>=', '≤': '<=', '≠': '!=', '≈': '~',
    // Los árboles de carpetas de los bloques de código
    '└': '`', '├': '|', '│': '|', '─': '-',
};

function limpiarCaracteres(texto) {
    for (const [a, b] of Object.entries(SUSTITUCIONES)) texto = texto.split(a).join(b);
    // El emoji se va con el espacio que lo separaba, para no dejar dos seguidos
    return texto.replace(/ ?[\u{1F000}-\u{1FAFF}\u{2600}-\u{27BF}\u{FE0F}]+/gu, '');
}

/* Lo que Windows-1252 tiene fuera del latín básico: si no está aquí ni en
   SUSTITUCIONES, Helvetica no lo sabe pintar */
const WIN1252 = new Set('€‚ƒ„…†‡ˆ‰Š‹ŒŽ‘’“”•–—˜™š›œžŸ');
const pintable = c => {
    const n = c.codePointAt(0);
    return n === 9 || (n >= 0x20 && n <= 0x7e) || (n >= 0xa0 && n <= 0xff) || WIN1252.has(c);
};

/** Los caracteres que siguen sin poder pintarse, para avisar (no en silencio). */
function sinPintar(texto) {
    return [...new Set([...texto].filter(c => c !== '\n' && c !== '\r' && !pintable(c)))];
}

/* ================================================================== MARKDOWN

   Lo justo para los manuales, a propósito: encabezados, párrafos, listas,
   tablas, avisos (>), bloques de código, reglas, negrita, cursiva, código en
   línea y enlaces. Si un manual usa algo que esto no entiende, se ve al
   momento en el PDF. Devuelve bloques, no HTML: los pinta pintarBloque(). */

function enLinea(texto, base = {}) {
    const trozos = [];
    const patron = /`([^`]+)`|\*\*(.+?)\*\*|(?<![\w*])\*([^*\n]+)\*(?![\w*])|\[([^\]]+)\]\(([^)]+)\)/gs;
    let desde = 0;
    let m;

    while ((m = patron.exec(texto)) !== null) {
        if (m.index > desde) trozos.push({ ...base, texto: texto.slice(desde, m.index) });

        if (m[1] !== undefined) {
            // Dentro del código no se interpreta nada
            trozos.push({ ...base, texto: m[1], codigo: true });
        } else if (m[2] !== undefined) {
            trozos.push(...enLinea(m[2], { ...base, negrita: true }));
        } else if (m[3] !== undefined) {
            trozos.push(...enLinea(m[3], { ...base, cursiva: true }));
        } else {
            // Un enlace a una web se conserva; uno a un archivo del proyecto,
            // en negrita: en papel no lleva a ninguna parte
            trozos.push(...enLinea(m[4], m[5].startsWith('http')
                ? { ...base, enlace: m[5] }
                : { ...base, negrita: true }));
        }

        desde = patron.lastIndex;
    }

    if (desde < texto.length) trozos.push({ ...base, texto: texto.slice(desde) });

    return trozos.filter(t => t.texto !== '');
}

function celdas(linea) {
    return linea.trim().replace(/^\||\|$/g, '')
        .split(/(?<!\\)\|/).map(c => c.replace(/\\\|/g, '|').trim());
}

function bloques(texto) {
    const lineas = texto.split(/\r\n|\r|\n/);
    const salida = [];

    let parrafo = [], lista = null, item = null, tabla = null, aviso = null, codigo = null;

    const cerrarItem = () => {
        if (item) { lista.items.push({ nivel: item.nivel, ordenada: item.ordenada, trozos: enLinea(item.lineas.join(' ')) }); item = null; }
    };
    const volcarAviso = () => {
        if (aviso && aviso.lineas.length) { aviso.parrafos.push(enLinea(aviso.lineas.join(' '))); aviso.lineas = []; }
    };
    const cerrar = () => {
        if (parrafo.length) { salida.push({ tipo: 'p', trozos: enLinea(parrafo.join(' ')) }); parrafo = []; }
        if (lista) { cerrarItem(); salida.push(lista); lista = null; }
        if (tabla) { salida.push(tabla); tabla = null; }
        if (aviso) { volcarAviso(); salida.push({ tipo: 'aviso', parrafos: aviso.parrafos }); aviso = null; }
    };

    for (const original of lineas) {
        const linea = original.replace(/\s+$/, '');

        if (linea.trimStart().startsWith('```')) {
            if (codigo) { salida.push(codigo); codigo = null; } else { cerrar(); codigo = { tipo: 'codigo', lineas: [] }; }
            continue;
        }
        if (codigo) { codigo.lineas.push(linea); continue; }

        if (linea.trim() === '') { cerrar(); continue; }

        if (/^\s*(-{3,}|\*{3,}|_{3,})\s*$/.test(linea)) { cerrar(); salida.push({ tipo: 'hr' }); continue; }

        let m;
        if ((m = linea.match(/^(#{1,6})\s+(.*)$/))) {
            cerrar();
            salida.push({ tipo: 'h', nivel: m[1].length, trozos: enLinea(m[2].trim()) });
            continue;
        }

        if (linea.trimStart().startsWith('|')) {
            const fila = celdas(linea);
            // La fila de guiones sólo separa la cabecera: no se pinta
            if (fila.length && fila.every(c => /^:?-{2,}:?$/.test(c))) continue;
            if (!tabla) { cerrar(); tabla = { tipo: 'tabla', filas: [] }; }
            tabla.filas.push(fila.map(c => enLinea(c)));
            continue;
        }
        if (tabla) cerrar();

        if ((m = linea.match(/^\s*>\s?(.*)$/))) {
            if (!aviso) { cerrar(); aviso = { parrafos: [], lineas: [] }; }
            // Una línea `>` vacía separa párrafos dentro del aviso
            if (m[1].trim() === '') volcarAviso(); else aviso.lineas.push(m[1].trim());
            continue;
        }
        if (aviso) cerrar();

        if ((m = linea.match(/^(\s*)([-*+]|\d+\.)\s+(.*)$/))) {
            const ordenada = /^\d+\.$/.test(m[2]);
            const nivel = Math.floor(m[1].length / 2);
            // Una sublista va dentro de la lista: así la numeración de fuera
            // sigue (1, 2, sublista, 3) en vez de volver a empezar. Sólo un
            // cambio de tipo en el primer nivel abre una lista nueva
            if (!lista || (nivel === 0 && lista.ordenada !== ordenada)) { cerrar(); lista = { tipo: 'lista', ordenada, items: [] }; }
            else cerrarItem();
            item = { nivel, ordenada, lineas: [m[3].trim()] };
            continue;
        }

        // Dentro de una lista, una línea sin marcador sigue el ítem anterior
        if (lista && item) { item.lineas.push(linea.trim()); continue; }
        if (lista) cerrar();

        parrafo.push(linea.trim());
    }

    cerrar();
    if (codigo) salida.push(codigo);

    return salida;
}

/* ================================================================== EL PDF */

function fuenteDe(t) {
    if (t.codigo) return FUENTE.codigo;
    if (t.negrita && t.cursiva) return FUENTE.negritaCursiva;
    if (t.negrita) return FUENTE.negrita;
    if (t.cursiva) return FUENTE.cursiva;
    return FUENTE.normal;
}

class Manual {
    constructor(conf, def, logo) {
        this.conf = conf;
        this.def = def;
        this.logo = logo;
        this.avisos = [];
        this.marca = conf.colores?.marca || '#6366f1';
        this.oscuro = conf.colores?.marcaOscuro || '#4338ca';

        const id = conf.identidad;
        this.doc = new PDFDocument({
            size: 'A4', autoFirstPage: false, bufferPages: true,
            margins: { top: MARGEN.arriba, bottom: MARGEN.abajo, left: MARGEN.izq, right: MARGEN.der },
            info: {
                Title: `${def.titulo} · ${id.nombre}`, Author: id.empresa,
                Subject: def.subtitulo, Creator: `${id.nombre} ${id.version}`,
            },
        });
    }

    /* ----------------------------------------------------------- utilidades */

    get y() { return this.doc.y; }
    set y(v) { this.doc.y = v; }
    get fondo() { return PAGINA.alto - MARGEN.abajo; }

    /** Si no cabe `alto`, a la página siguiente. */
    asegurar(alto) {
        if (this.y + alto > this.fondo) {
            this.doc.addPage();
            this.y = MARGEN.arriba;
        }
    }

    /** Alto que ocuparán unos trozos de texto en `ancho`. */
    altoDe(trozos, ancho, tam, gap) {
        const texto = trozos.map(t => t.texto).join('') || ' ';
        const negrita = trozos.length && trozos.every(t => t.negrita);
        this.doc.font(negrita ? FUENTE.negrita : FUENTE.normal).fontSize(tam);
        return this.doc.heightOfString(texto, { width: ancho, lineGap: gap });
    }

    /** Pinta trozos con su formato, seguidos, en una caja de `ancho`. */
    trozos(trozos, x, y, ancho, { tam, color, gap = 0, alinear = 'left' }) {
        const d = this.doc;
        if (!trozos.length) trozos = [{ texto: ' ' }];

        trozos.forEach((t, i) => {
            const ultimo = i === trozos.length - 1;
            d.font(fuenteDe(t))
                .fontSize(t.codigo ? Math.max(tam - 1, 7.5) : tam)
                .fillColor(t.codigo ? GRIS.codigoEnLinea : t.enlace ? this.oscuro : color);

            const op = { width: ancho, lineGap: gap, align: alinear, continued: !ultimo, link: t.enlace || null, underline: false };
            if (i === 0) d.text(t.texto, x, y, op); else d.text(t.texto, op);
        });

        d.fillColor('black');
    }

    /* -------------------------------------------------------------- portada */

    portada() {
        const d = this.doc;
        const id = this.conf.identidad;
        d.addPage();

        // Las mismas cotas que la de TCPDF: se escribe en «celdas» de alto fijo
        // con el texto centrado en vertical dentro de cada una
        let y = MARGEN.arriba;
        const celda = (texto, alto, fuente, tam, color) => {
            d.font(fuente).fontSize(tam).fillColor(color);
            const h = d.heightOfString(texto, { width: ANCHO_UTIL });
            // TCPDF centra con la altura de la letra; pdfkit mide la línea entera,
            // que deja el texto un poco más arriba: se compensa con el tamaño
            d.text(texto, MARGEN.izq, y + (mm(alto) - h) / 2 + tam * 0.27, { width: ANCHO_UTIL, align: 'center' });
            y += mm(alto);
        };

        if (this.logo) {
            y += mm(32);
            d.image(this.logo, (PAGINA.ancho - mm(46)) / 2, y, { width: mm(46) });
            y += mm(34);
        } else {
            y += mm(55);
        }

        celda(id.nombre, 14, FUENTE.negrita, 30, this.marca);
        celda(id.lema || '', 8, FUENTE.normal, 12, GRIS.suave);
        y += mm(18);
        celda(this.def.titulo, 12, FUENTE.negrita, 20, GRIS.portadaTitulo);
        celda(this.def.subtitulo || '', 8, FUENTE.normal, 12, GRIS.suave);
        y += mm(22);
        celda(`Versión ${id.version}${id.build ? ' · ' + id.build : ''}`, 6, FUENTE.normal, 10, GRIS.suave);
        celda(id.empresa || '', 6, FUENTE.normal, 10, GRIS.suave);
        y += mm(10);

        const hoy = new Date();
        const fecha = [hoy.getDate(), hoy.getMonth() + 1].map(n => String(n).padStart(2, '0')).join('/') + '/' + hoy.getFullYear();
        celda(`Generado el ${fecha} desde docs/${this.def.archivo}.md`, 5, FUENTE.cursiva, 8, GRIS.generado);

        d.fillColor('black');
    }

    /* ------------------------------------------------------------- el cuerpo */

    cuerpo(lista) {
        this.doc.addPage();
        this.y = MARGEN.arriba;
        let anterior = null;

        for (const b of lista) {
            this.pintarBloque(b, anterior);
            anterior = b.tipo;
        }
    }

    pintarBloque(b, anterior) {
        const d = this.doc;
        const x = MARGEN.izq;

        switch (b.tipo) {
            case 'h': {
                const tam = TAM['h' + Math.min(b.nivel, 4)];
                const color = b.nivel <= 2 ? this.oscuro : GRIS.titulo;
                const antes = anterior === null ? 0 : (b.nivel <= 2 ? mm(6) : mm(4.5));
                const trozos = b.trozos.map(t => ({ ...t, negrita: true }));
                const alto = this.altoDe(trozos, ANCHO_UTIL, tam, 0);

                // Un título no se queda solo al pie de una página
                this.asegurar(antes + alto + mm(12));
                this.y += this.y === MARGEN.arriba ? 0 : antes;
                this.trozos(trozos, x, this.y, ANCHO_UTIL, { tam, color });
                this.y += mm(2.8);
                return;
            }

            case 'p': {
                const gap = TAM.p * 0.42;
                const alto = this.altoDe(b.trozos, ANCHO_UTIL, TAM.p, gap);
                this.asegurar(Math.min(alto, mm(15)));
                this.trozos(b.trozos, x, this.y, ANCHO_UTIL, { tam: TAM.p, color: GRIS.texto, gap });
                this.y += mm(3.4);
                return;
            }

            case 'lista': {
                const gap = TAM.p * 0.3;
                const cuenta = [];               // un contador por nivel
                b.items.forEach(it => {
                    cuenta.length = it.nivel + 1;
                    cuenta[it.nivel] = (cuenta[it.nivel] || 0) + 1;
                    const sangria = mm(5) + it.nivel * mm(6);
                    const marcador = it.ordenada ? `${cuenta[it.nivel]}.` : '•';
                    const ancho = ANCHO_UTIL - sangria - mm(4);
                    const alto = this.altoDe(it.trozos, ancho, TAM.p, gap);

                    this.asegurar(Math.min(alto, mm(12)));
                    const y = this.y;
                    d.font(FUENTE.normal).fontSize(TAM.p).fillColor(GRIS.texto)
                        .text(marcador, x + sangria - mm(4), y, { width: mm(4), lineBreak: false });
                    this.trozos(it.trozos, x + sangria, y, ancho, { tam: TAM.p, color: GRIS.texto, gap });
                    this.y += mm(0.4);
                });
                this.y += mm(3);
                return;
            }

            case 'tabla':
                this.tabla(b.filas);
                return;

            case 'aviso': {
                const pad = mm(2.5);
                const ancho = ANCHO_UTIL - 2 * pad;
                const gap = TAM.aviso * 0.35;
                const altos = b.parrafos.map(p => this.altoDe(p, ancho, TAM.aviso, gap));
                const total = altos.reduce((s, h) => s + h, 0) + (altos.length - 1) * mm(1.5) + 2 * pad;

                this.asegurar(Math.min(total, this.fondo - MARGEN.arriba));
                const y0 = this.y;
                d.rect(x, y0, ANCHO_UTIL, total).fill(GRIS.avisoFondo);

                let y = y0 + pad;
                b.parrafos.forEach((p, i) => {
                    this.trozos(p, x + pad, y, ancho, { tam: TAM.aviso, color: GRIS.avisoTexto, gap });
                    y += altos[i] + mm(1.5);
                });
                this.y = y0 + total + mm(4);
                return;
            }

            case 'codigo': {
                const alto = TAM.codigo * 1.35;
                const pad = mm(2);
                d.font(FUENTE.codigo).fontSize(TAM.codigo);

                this.asegurar(alto * Math.min(b.lineas.length, 3) + 2 * pad);
                let primera = true;

                // Courier es de ancho fijo: lo que no cabe sigue en la línea de
                // abajo, con sangría, en vez de perderse por el margen
                const caben = Math.floor((ANCHO_UTIL - 2 * pad) / (TAM.codigo * 0.6));
                const partidas = b.lineas.flatMap(l => {
                    const trozos = [];
                    let resto = l, ancho = caben;

                    // Se corta en el último espacio que quepa, si lo hay; si no
                    // (una ruta larga), por donde toque
                    while (resto.length > ancho) {
                        const espacio = resto.lastIndexOf(' ', ancho);
                        const corte = espacio > ancho / 2 ? espacio : ancho;
                        trozos.push(resto.slice(0, corte));
                        resto = '    ' + resto.slice(corte).replace(/^ /, '');
                        ancho = caben;
                    }

                    trozos.push(resto);
                    return trozos;
                });

                for (const linea of partidas) {
                    if (this.y + alto + pad > this.fondo) {
                        d.rect(x, this.y, ANCHO_UTIL, pad).fill(GRIS.fondoCodigo);
                        d.addPage();
                        this.y = MARGEN.arriba;
                        primera = true;
                    }
                    if (primera) { d.rect(x, this.y, ANCHO_UTIL, pad).fill(GRIS.fondoCodigo); this.y += pad; primera = false; }

                    const yl = this.y;
                    d.rect(x, yl, ANCHO_UTIL, alto).fill(GRIS.fondoCodigo);
                    d.font(FUENTE.codigo).fontSize(TAM.codigo).fillColor(GRIS.codigo)
                        .text(linea || ' ', x + pad, yl + 1, { width: ANCHO_UTIL - 2 * pad, lineBreak: false, height: alto });
                    this.y = yl + alto;
                }

                d.rect(x, this.y, ANCHO_UTIL, pad).fill(GRIS.fondoCodigo);
                this.y += pad + mm(4);
                d.fillColor('black');
                return;
            }

            case 'hr':
                this.asegurar(mm(6));
                this.y += mm(2);
                d.moveTo(x, this.y).lineTo(x + ANCHO_UTIL, this.y).lineWidth(0.5).strokeColor(GRIS.borde).stroke();
                this.y += mm(4);
                return;
        }
    }

    /** Una tabla: la primera fila es la cabecera. */
    tabla(filas) {
        const d = this.doc;
        const x = MARGEN.izq;
        const pad = mm(1.6);
        const columnas = Math.max(...filas.map(f => f.length));
        const plano = c => (c || []).map(t => t.texto).join('');

        // Ancho de cada columna según lo que lleva, con un mínimo para la
        // palabra más larga, y repartido si no cabe todo en una línea
        d.font(FUENTE.normal).fontSize(TAM.tabla);
        const natural = [], minimo = [];
        for (let c = 0; c < columnas; c++) {
            let n = 0, w = 0;
            for (const [i, f] of filas.entries()) {
                d.font(i === 0 ? FUENTE.negrita : FUENTE.normal);
                const texto = plano(f[c]);
                n = Math.max(n, d.widthOfString(texto) + 2 * pad);
                for (const palabra of texto.split(/\s+/)) w = Math.max(w, d.widthOfString(palabra) + 2 * pad);
            }
            natural.push(n); minimo.push(Math.min(w, ANCHO_UTIL / columnas * 1.6));
        }

        let anchos;
        const sumaNatural = natural.reduce((s, n) => s + n, 0);
        if (sumaNatural <= ANCHO_UTIL) {
            anchos = natural.map(n => n * ANCHO_UTIL / sumaNatural);
        } else {
            const sumaMin = minimo.reduce((s, n) => s + n, 0);
            const resto = Math.max(ANCHO_UTIL - sumaMin, 0);
            const extra = natural.map((n, c) => Math.max(n - minimo[c], 0));
            const sumaExtra = extra.reduce((s, n) => s + n, 0) || 1;
            anchos = minimo.map((m, c) => m + resto * extra[c] / sumaExtra);
            const total = anchos.reduce((s, n) => s + n, 0);
            anchos = anchos.map(a => a * ANCHO_UTIL / total);
        }

        filas.forEach((f, i) => {
            const cabecera = i === 0;
            const celdas = Array.from({ length: columnas }, (_, c) =>
                (f[c] || []).map(t => (cabecera ? { ...t, negrita: true } : t)));
            const alto = Math.max(...celdas.map((c, k) => this.altoDe(c, anchos[k] - 2 * pad, TAM.tabla, 1.5))) + 2 * pad;

            this.asegurar(alto);
            // pdfkit mueve su cursor con cada texto: la fila va en una y fija
            const fy = this.y;
            let cx = x;
            celdas.forEach((c, k) => {
                if (cabecera) d.rect(cx, fy, anchos[k], alto).fill(GRIS.cabeceraTabla);
                d.rect(cx, fy, anchos[k], alto).lineWidth(0.5).strokeColor(GRIS.borde).stroke();
                this.trozos(c, cx + pad, fy + pad, anchos[k] - 2 * pad, { tam: TAM.tabla, color: GRIS.texto, gap: 1.5 });
                cx += anchos[k];
            });
            this.y = fy + alto;
        });

        this.y += mm(4);
    }

    /* ------------------------------------------------- cabecera y pie, al final */

    cabecerasYPies() {
        const d = this.doc;
        const id = this.conf.identidad;
        const { start, count } = d.bufferedPageRange();

        for (let i = start; i < start + count; i++) {
            if (i === 0) continue;              // la portada va limpia
            d.switchToPage(i);

            // Para escribir en los márgenes sin que pdfkit abra otra página
            const margenes = { ...d.page.margins };
            d.page.margins = { top: 0, bottom: 0, left: 0, right: 0 };

            if (this.logo) d.image(this.logo, MARGEN.izq, mm(9), { fit: [mm(14), mm(8)], align: 'left', valign: 'top' });

            const xTexto = this.logo ? mm(35) : MARGEN.izq;
            d.font(FUENTE.normal).fontSize(8).fillColor(GRIS.cabecera);
            d.text(`${id.nombre} · ${this.def.titulo}`, xTexto, mm(10.6), { lineBreak: false });
            d.text(`v${id.version}`, MARGEN.izq, mm(10.6), { width: ANCHO_UTIL, align: 'right', lineBreak: false });
            d.moveTo(MARGEN.izq, mm(18)).lineTo(PAGINA.ancho - MARGEN.der, mm(18)).lineWidth(0.5).strokeColor(GRIS.linea).stroke();

            const yPie = PAGINA.alto - mm(14) + mm(0.6);
            d.text(id.empresa || '', MARGEN.izq, yPie, { lineBreak: false });
            d.text(`Página ${i + 1} de ${count}`, MARGEN.izq, yPie, { width: ANCHO_UTIL, align: 'right', lineBreak: false });

            d.page.margins = margenes;
        }
    }

    async generar(markdown, destino) {
        // La cabecera del .md —el logotipo centrado y el título— ya va en la
        // portada: se quita del cuerpo para no repetirla
        let texto = markdown.replace(/^\s*<p align="center">[\s\S]*?<\/p>\s*/, '');
        texto = texto.replace(/^#\s+.*(\r?\n)+/, '');
        texto = limpiarCaracteres(texto);

        // Lo que queda sin poder pintarse se cambia por «?» y SE DICE: en
        // roriApp pasó meses imprimiéndose roto sin que nadie lo viera
        const faltan = sinPintar(texto);
        if (faltan.length) {
            this.avisos.push(`caracteres que la fuente no tiene: ${faltan.join(' ')} — añádalos a SUSTITUCIONES`);
            texto = [...texto].map(c => (c === '\n' || c === '\r' || pintable(c) ? c : '?')).join('');
        }

        this.portada();
        this.cuerpo(bloques(texto));
        this.cabecerasYPies();

        await new Promise((listo, falla) => {
            const flujo = fs.createWriteStream(destino);
            flujo.on('finish', listo).on('error', falla);
            this.doc.pipe(flujo);
            this.doc.end();
        });
    }
}

/* ============================================================== LA VERSIÓN

   La versión sale del manifiesto del proyecto, no de manuales.json: así no
   hay dos sitios donde subirla. Si `identidad.version` trae un valor, manda
   ése. Se busca en la raíz del proyecto (la carpeta de encima de docs/). */

function versionDelProyecto(raiz) {
    const leer = f => { try { return fs.readFileSync(path.join(raiz, f), 'utf8'); } catch { return null; } };
    let t;

    for (const f of ['package.json', 'composer.json']) {
        if ((t = leer(f))) { try { const v = JSON.parse(t).version; if (v) return v; } catch { /* sigue */ } }
    }
    if ((t = leer('pyproject.toml')) && (t = t.match(/^\s*version\s*=\s*["']([^"']+)["']/m))) return t[1];
    if ((t = leer('setup.cfg')) && (t = t.match(/^\s*version\s*=\s*(\S+)/m))) return t[1];
    if ((t = leer('pom.xml')) && (t = t.replace(/<parent>[\s\S]*?<\/parent>/, '').match(/<version>([^<]+)<\/version>/))) return t[1];
    if ((t = leer('build.gradle')) && (t = t.match(/^\s*version\s*=?\s*["']([^"']+)["']/m))) return t[1];
    if ((t = leer('Cargo.toml')) && (t = t.match(/^\s*version\s*=\s*"([^"]+)"/m))) return t[1];
    if ((t = leer('pubspec.yaml')) && (t = t.match(/^version:\s*([^\s+]+)/m))) return t[1];
    if ((t = leer('VERSION'))) return t.trim();

    try {
        for (const f of fs.readdirSync(raiz).filter(f => f.endsWith('.csproj'))) {
            const m = leer(f).match(/<Version>([^<]+)<\/Version>/);
            if (m) return m[1];
        }
    } catch { /* sigue */ }

    return null;
}

/* ================================================================ PRINCIPAL */

async function main() {
    const rutaConf = path.join(CARPETA, 'manuales.json');
    if (!fs.existsSync(rutaConf)) {
        console.error(`No se encuentra ${rutaConf}. Créelo (ver el ejemplo de la guía).`);
        process.exit(1);
    }

    const conf = JSON.parse(fs.readFileSync(rutaConf, 'utf8'));
    conf.identidad ??= {};
    conf.identidad.version ||= versionDelProyecto(path.resolve(CARPETA, conf.raiz || '..')) || '0.0.0';

    let logo = conf.logo ? path.resolve(CARPETA, conf.logo) : null;
    if (logo && !fs.existsSync(logo)) {
        console.warn(`Aviso: no se encuentra el logotipo ${logo}; los PDF salen sin él.`);
        logo = null;
    }

    fs.mkdirSync(SALIDA, { recursive: true });
    console.log(`Generando los manuales de ${conf.identidad.nombre} v${conf.identidad.version}\n`);

    let fallos = 0;

    for (const def of conf.manuales || []) {
        if (SOLO && def.archivo !== SOLO) continue;

        const fuente = path.join(CARPETA, def.archivo + '.md');
        const destino = path.join(SALIDA, def.archivo + '.pdf');
        const nombre = def.archivo.padEnd(16);

        if (!fs.existsSync(fuente)) {
            console.log(`  ${nombre} FALLO  No se encuentra ${path.basename(fuente)}`);
            fallos++;
            continue;
        }

        try {
            const manual = new Manual(conf, def, logo);
            await manual.generar(fs.readFileSync(fuente, 'utf8'), destino);
            console.log(`  ${nombre} ok     ${path.basename(destino)} · ${Math.round(fs.statSync(destino).size / 1024)} KB`);
            for (const a of manual.avisos) console.log(`  ${''.padEnd(16)} aviso  ${a}`);
        } catch (e) {
            console.log(`  ${nombre} FALLO  ${e.message}`);
            fallos++;
        }
    }

    console.log(fallos === 0 ? `\nListos en ${path.relative(process.cwd(), SALIDA) || '.'}.` : `\n${fallos} manual(es) sin generar.`);
    process.exit(fallos === 0 ? 0 : 1);
}

main();
