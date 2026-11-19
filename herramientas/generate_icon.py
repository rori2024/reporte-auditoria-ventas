#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
generate_icon.py — el icono de una aplicación, en local y sin dependencias.

Hace a mano lo que pide el agente `GenerateIcon` (.claude/agents/GenerateIcon.md):
un SVG maestro con la composición de la casa —mosaico redondeado, degradado en
diagonal, símbolo blanco centrado— y los PNG que salen de él, con las esquinas
transparentes. Además los verifica.

  * Sólo la biblioteca estándar de Python 3.7+. Nada que instalar.
  * Sin navegador, sin ImageMagick, sin Inkscape: trae su propio rasterizador
    SVG, pensado para el subconjunto que usa un icono (rect, circle, ellipse,
    line, polyline, polygon, path con todos sus comandos, g, transform,
    degradados lineales y radiales, opacidad, trazos discontinuos).
  * Sin IA y sin red: no consume tokens ni llama a ningún servicio.
  * No toca plantillas, vistas ni configuración del proyecto: sólo escribe los
    archivos del icono en la carpeta que le digas, y te imprime las etiquetas
    <link> para que las pegues tú donde corresponda.

Uso rápido
----------
    python3 generate_icon.py simbolos
    python3 generate_icon.py crear --nombre "Mi App" --simbolo caja \\
        --primario "#0369a1" --oscuro "#0f172a" --destino public/img
    python3 generate_icon.py rasterizar public/img/icono.svg
    python3 generate_icon.py verificar public/img
    python3 generate_icon.py vista-previa public/img

`python3 generate_icon.py <orden> --help` explica cada orden. El manual de
integración está en MANUAL.md, junto a este archivo.

Los trazados de los símbolos del catálogo son de Lucide (https://lucide.dev),
licencia ISC: Copyright (c) Lucide Contributors.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import shutil
import struct
import sys
import tempfile
import unicodedata
import time
import zlib
import xml.etree.ElementTree as ET
from pathlib import Path
from xml.sax.saxutils import escape, quoteattr

VERSION = "2.0.0"

# ---------------------------------------------------------------------------
#  La composición de la casa. Son las medidas que el agente dice que no se
#  tocan: si un símbolo no cabe, se elige otro símbolo.
# ---------------------------------------------------------------------------
LIENZO = 64
RADIO = 14              # mosaico cuadrado redondeado
RADIO_REDONDO = 32      # variante para tarjetas que recortan en círculo
TRAZO = 2.1
TRANSFORMACION_SIMBOLO = "translate(16 14) scale(1.45)"
TAMANOS_PNG = (512, 192, 180, 64, 32, 16)
TAMANOS_ICO = (16, 32, 48)
PREFIJO = "icono"


def nombre_png(base, n):
    """Nombre del PNG de `n` px. Con palabra: icono-tienda -> icono-16-tienda.png.
    Sin palabra (o con un --prefijo propio): icono -> icono-16.png."""
    if base.startswith(PREFIJO + "-"):
        return "%s-%d-%s.png" % (PREFIJO, n, base[len(PREFIJO) + 1:])
    return "%s-%d.png" % (base, n)


def palabra_de(texto):
    """Primera palabra útil de un nombre, apta para un archivo: «Gestión de Asistencia» -> gestion."""
    t = unicodedata.normalize("NFKD", texto or "").encode("ascii", "ignore").decode().lower()
    for w in re.findall(r"[a-z0-9]+", t):
        if len(w) >= 2:
            return w
    return ""


def limpiar_palabra(texto):
    t = unicodedata.normalize("NFKD", texto or "").encode("ascii", "ignore").decode().lower()
    return "-".join(re.findall(r"[a-z0-9]+", t))[:30]
TOKEN_PRIMARIO = "primary"
TOKEN_OSCURO = "navy"

# ---------------------------------------------------------------------------
#  Catálogo de símbolos (Lucide, lienzo 24x24, sin atributos: el grupo del
#  icono pone el trazo blanco). Los primeros son los de `vistas/iconos.php`
#  de la plantilla, así el icono de la pestaña puede ser el mismo dibujo que
#  ya usa la interfaz.
# ---------------------------------------------------------------------------
SIMBOLOS = {
    # --- Dominio y documentos
    "tijeras": '<circle cx="6" cy="6" r="3"/><circle cx="6" cy="18" r="3"/><path d="M8.12 8.12 12 12M20 4 8.12 15.88M14.8 14.8 20 20"/>',
    "prenda": '<path d="M20.38 3.46 16 2a4 4 0 0 1-8 0L3.62 3.46a2 2 0 0 0-1.34 2.23l.58 3.47a1 1 0 0 0 .99.84H6v10c0 1.1.9 2 2 2h8a2 2 0 0 0 2-2V10h2.15a1 1 0 0 0 .99-.84l.58-3.47a2 2 0 0 0-1.34-2.23z"/>',
    "regla": '<path d="M21.3 8.7 8.7 21.3a1 1 0 0 1-1.4 0l-4.6-4.6a1 1 0 0 1 0-1.4L15.3 2.7a1 1 0 0 1 1.4 0l4.6 4.6a1 1 0 0 1 0 1.4Z"/><path d="m7.5 10.5 2 2M10.5 7.5l2 2M13.5 4.5l2 2M4.5 13.5l2 2"/>',
    "etiqueta": '<path d="M12.59 2.59A2 2 0 0 0 11.17 2H4a2 2 0 0 0-2 2v7.17a2 2 0 0 0 .59 1.41l8.7 8.71a2.43 2.43 0 0 0 3.42 0l6.58-6.59a2.43 2.43 0 0 0 0-3.41z"/><path d="M7.5 7.5h.01"/>',
    "capas": '<path d="M12.83 2.18a2 2 0 0 0-1.66 0L2.6 6.08a1 1 0 0 0 0 1.83l8.58 3.91a2 2 0 0 0 1.66 0l8.58-3.9a1 1 0 0 0 0-1.83Z"/><path d="m22 17.65-9.17 4.16a2 2 0 0 1-1.66 0L2 17.65"/><path d="m22 12.65-9.17 4.16a2 2 0 0 1-1.66 0L2 12.65"/>',
    "nota": '<rect width="8" height="4" x="8" y="2" rx="1"/><path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2"/><path d="M12 11h4M12 16h4M8 11h.01M8 16h.01"/>',
    "archivo": '<path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z"/><path d="M14 2v4a2 2 0 0 0 2 2h4"/>',
    "documento": '<path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z"/><path d="M14 2v4a2 2 0 0 0 2 2h4"/><path d="M10 9H8M16 13H8M16 17H8"/>',
    "libro": '<path d="M4 19.5v-15A2.5 2.5 0 0 1 6.5 2H19a1 1 0 0 1 1 1v18a1 1 0 0 1-1 1H6.5a1 1 0 0 1 0-5H20"/>',
    "factura": '<path d="M4 2v20l2-1 2 1 2-1 2 1 2-1 2 1 2-1 2 1V2l-2 1-2-1-2 1-2-1-2 1-2-1-2 1Z"/><path d="M16 8h-6a2 2 0 1 0 0 4h4a2 2 0 1 1 0 4H8"/><path d="M12 17.5v-11"/>',
    "hoja-calculo": '<rect width="18" height="18" x="3" y="3" rx="2"/><path d="M3 9h18M3 15h18M9 3v18M15 3v18"/>',
    "calendario": '<path d="M8 2v4M16 2v4"/><rect width="18" height="18" x="3" y="4" rx="2"/><path d="M3 10h18"/>',
    "impresora": '<path d="M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2"/><path d="M6 9V3a1 1 0 0 1 1-1h10a1 1 0 0 1 1 1v6"/><rect x="6" y="14" width="12" height="8" rx="1"/>',
    # --- Logística, comercio, producción
    "caja": '<path d="M11 21.73a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73z"/><path d="M12 22V12"/><path d="m3.3 7 7.703 4.734a2 2 0 0 0 1.994 0L20.7 7"/><path d="m7.5 4.27 9 5.15"/>',
    "camion": '<path d="M14 18V6a2 2 0 0 0-2-2H4a2 2 0 0 0-2 2v11a1 1 0 0 0 1 1h2"/><path d="M15 18H9"/><path d="M19 18h2a1 1 0 0 0 1-1v-3.65a1 1 0 0 0-.22-.624l-3.48-4.35A1 1 0 0 0 17.52 8H14"/><circle cx="17" cy="18" r="2"/><circle cx="7" cy="18" r="2"/>',
    "almacen": '<path d="M22 8.35V20a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V8.35A2 2 0 0 1 3.26 6.5l8-3.2a2 2 0 0 1 1.48 0l8 3.2A2 2 0 0 1 22 8.35Z"/><path d="M6 18h12M6 14h12"/><rect width="12" height="12" x="6" y="10"/>',
    "fabrica": '<path d="M2 20a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2V8l-7 5V8l-7 5V4a2 2 0 0 0-2-2H4a2 2 0 0 0-2 2Z"/><path d="M17 18h1M12 18h1M7 18h1"/>',
    "carrito": '<circle cx="8" cy="21" r="1"/><circle cx="19" cy="21" r="1"/><path d="M2.05 2.05h2l2.66 12.42a2 2 0 0 0 2 1.58h9.78a2 2 0 0 0 1.95-1.57l1.65-7.43H5.12"/>',
    "dinero": '<rect width="20" height="12" x="2" y="6" rx="2"/><circle cx="12" cy="12" r="2"/><path d="M6 12h.01M18 12h.01"/>',
    "grafico": '<path d="M3 3v16a2 2 0 0 0 2 2h16"/><path d="M18 17V9M13 17V5M8 17v-3"/>',
    "base-datos": '<ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M3 5V19A9 3 0 0 0 21 19V5"/><path d="M3 12A9 3 0 0 0 21 12"/>',
    "herramienta": '<path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"/>',
    # --- Personas, comunicación, sistema
    "usuario": '<path d="M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/>',
    "personas": '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75"/>',
    "correo": '<rect x="2" y="4" width="20" height="16" rx="2"/><path d="m22 7-8.97 5.7a1.94 1.94 0 0 1-2.06 0L2 7"/>',
    "telefono": '<path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72 12.84 12.84 0 0 0 .7 2.81 2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45 12.84 12.84 0 0 0 2.81.7A2 2 0 0 1 22 16.92z"/>',
    "auricular": '<path d="M3 14h3a2 2 0 0 1 2 2v3a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-7a9 9 0 0 1 18 0v7a2 2 0 0 1-2 2h-1a2 2 0 0 1-2-2v-3a2 2 0 0 1 2-2h3"/>',
    "reloj": '<circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/>',
    "ubicacion": '<path d="M20 10c0 4.993-5.539 10.193-7.399 11.799a1 1 0 0 1-1.202 0C9.539 20.193 4 14.993 4 10a8 8 0 0 1 16 0Z"/><circle cx="12" cy="10" r="3"/>',
    "globo": '<circle cx="12" cy="12" r="10"/><path d="M12 2a14.5 14.5 0 0 0 0 20 14.5 14.5 0 0 0 0-20M2 12h20"/>',
    "lupa": '<circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/>',
    "escudo": '<path d="M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z"/>',
    "servidor": '<rect width="20" height="8" x="2" y="2" rx="2"/><rect width="20" height="8" x="2" y="14" rx="2"/><path d="M6 6h.01M6 18h.01"/>',
    "navegador": '<rect width="20" height="16" x="2" y="4" rx="2"/><path d="M2 9h20M6 6.5h.01M9 6.5h.01"/>',
    "codigo": '<path d="m16 18 6-6-6-6M8 6l-6 6 6 6"/>',
    # --- Animales y cuidado
    "huella": '<circle cx="11" cy="4" r="2"/><circle cx="18" cy="8" r="2"/><circle cx="20" cy="16" r="2"/><path d="M9 10a5 5 0 0 1 5 5v3.5a3.5 3.5 0 0 1-6.84 1.045Q6.52 17.48 4.46 16.84A3.5 3.5 0 0 1 5.5 10Z"/>',
    "corazon": '<path d="M19 14c1.49-1.46 3-3.21 3-5.5A5.5 5.5 0 0 0 16.5 3c-1.76 0-3 .5-4.5 2-1.5-1.5-2.74-2-4.5-2A5.5 5.5 0 0 0 2 8.5c0 2.3 1.5 4.05 3 5.5l7 7Z"/>',
}

# ===========================================================================
#  Utilidades generales
# ===========================================================================


class ErrorIcono(Exception):
    """Un error que se le explica al usuario, sin traza."""


def _consola_segura():
    """Evita que una consola de Windows sin UTF-8 tumbe el programa por una tilde."""
    for flujo in (sys.stdout, sys.stderr):
        try:
            flujo.reconfigure(errors="replace")  # type: ignore[attr-defined]
        except Exception:
            pass


def _aviso(msg):
    print("  [aviso] " + msg, file=sys.stderr)


def _kb(ruta):
    return "%.1f KB" % (os.path.getsize(ruta) / 1024.0)


def _sin_ns(tag):
    return tag.split("}", 1)[1] if "}" in tag else tag


_RE_HEX = re.compile(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")


def normalizar_hex(valor, campo="color"):
    v = (valor or "").strip()
    if not _RE_HEX.match(v):
        raise ErrorIcono(
            "%s: '%s' no es un hexadecimal (#rrggbb). En el SVG van los valores, "
            "nunca var(--token): un icono no hereda las variables CSS de la página." % (campo, valor)
        )
    v = v.lower()
    if len(v) == 4:
        v = "#" + "".join(c * 2 for c in v[1:])
    return v


def _seguro_comentario(texto):
    """Un comentario XML no admite `--`: el navegador dejaría de pintar el SVG sin avisar."""
    t = str(texto)
    while "--" in t:
        t = t.replace("--", "-")
    return t.rstrip("-")


def leer_tokens(ruta):
    """Lee `--nombre: valor;` de un CSS, un tailwind.config o un DESIGN-SYSTEM.md."""
    try:
        texto = Path(ruta).read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        raise ErrorIcono("No pude leer %s: %s" % (ruta, e))
    tokens = {}
    for m in re.finditer(r"--([A-Za-z0-9_-]+)\s*:\s*([^;}\n]+)", texto):
        nombre, valor = m.group(1), m.group(2).strip().strip("`'\"")
        tokens.setdefault(nombre, valor)  # la primera definición (tema claro) manda

    def resolver(v, prof=0):
        m = re.match(r"var\(\s*--([A-Za-z0-9_-]+)\s*(?:,\s*([^)]+))?\)", v)
        if m and prof < 8:
            if m.group(1) in tokens:
                return resolver(tokens[m.group(1)], prof + 1)
            if m.group(2):
                return resolver(m.group(2).strip(), prof + 1)
        return v

    return {k: resolver(v) for k, v in tokens.items()}


# ===========================================================================
#  Construcción del SVG maestro
# ===========================================================================


def _validar_fragmento(fragmento, que):
    bajo = fragmento.lower()
    if "<script" in bajo or "foreignobject" in bajo or re.search(r"\son[a-z]+\s*=", bajo):
        raise ErrorIcono("%s: no se admiten scripts, foreignObject ni atributos on*." % que)
    if "var(" in bajo:
        raise ErrorIcono("%s: no uses var(--token); escribe los colores en hexadecimal." % que)
    try:
        ET.fromstring('<g xmlns="http://www.w3.org/2000/svg">%s</g>' % fragmento)
    except ET.ParseError as e:
        raise ErrorIcono("%s no es XML válido: %s" % (que, e))


def simbolo_desde_svg(ruta):
    """Extrae el dibujo de un SVG de Lucide (o cualquiera en un lienzo de 24x24)."""
    try:
        raiz = ET.parse(str(ruta)).getroot()
    except (OSError, ET.ParseError) as e:
        raise ErrorIcono("No pude leer el símbolo %s: %s" % (ruta, e))
    vb = (raiz.get("viewBox") or "0 0 24 24").replace(",", " ").split()
    if [float(x) for x in vb] != [0.0, 0.0, 24.0, 24.0]:
        _aviso("el símbolo no está en un lienzo 0 0 24 24 (viewBox=%s); puede quedar descentrado." % " ".join(vb))
    partes = []
    for hijo in raiz:
        for el in hijo.iter():
            el.tag = _sin_ns(el.tag)
        if hijo.tag in ("title", "desc", "metadata", "defs"):
            continue
        partes.append(ET.tostring(hijo, encoding="unicode").strip())
    if not partes:
        raise ErrorIcono("El SVG %s no tiene ningún trazado." % ruta)
    return "".join(partes)


def construir_svg(nombre, simbolo, primario, oscuro, nombre_simbolo="", motivo="",
                  token_primario=TOKEN_PRIMARIO, token_oscuro=TOKEN_OSCURO,
                  extra="", redondo=False):
    """Devuelve el SVG maestro con la plantilla del agente GenerateIcon."""
    primario = normalizar_hex(primario, "color primario")
    oscuro = normalizar_hex(oscuro, "color oscuro")
    _validar_fragmento(simbolo, "El símbolo")
    if extra:
        _validar_fragmento(extra, "El detalle secundario (--extra)")

    nom = _seguro_comentario(nombre)
    desc_simbolo = _seguro_comentario(nombre_simbolo or "símbolo propio")
    if motivo:
        desc_simbolo += ": " + _seguro_comentario(motivo)
    tp = _seguro_comentario(token_primario.lstrip("-")) or TOKEN_PRIMARIO
    to = _seguro_comentario(token_oscuro.lstrip("-")) or TOKEN_OSCURO
    radio = RADIO_REDONDO if redondo else RADIO

    lineas = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        "<!--",
        "  Icono de %s." % nom,
        "",
        "  Símbolo: %s." % desc_simbolo,
        ("  Colores: elegidos a mano, de %s a %s." % (primario, oscuro) if tp == "elegido a mano" else
         "  Colores: del token `%s` (%s) al `%s` (%s)." % (tp, primario, to, oscuro)),
        "",
        "  Pieza maestra: de aquí salen los PNG. Si hay que cambiar algo, se cambia",
        "  aquí y se regeneran con:  python3 generate_icon.py rasterizar <este archivo>",
        "  Generado por generate_icon.py %s%s." % (VERSION, " (variante redonda)" if redondo else ""),
        "-->",
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %d %d" width="%d" height="%d"' % (LIENZO, LIENZO, LIENZO, LIENZO),
        "     role=\"img\" aria-label=%s>" % quoteattr(nombre),
        "",
        "    <defs>",
        '        <linearGradient id="marca" x1="0" y1="0" x2="1" y2="1">',
        '            <stop offset="0" stop-color="%s"/>' % primario,
        '            <stop offset="1" stop-color="%s"/>' % oscuro,
        "        </linearGradient>",
        "    </defs>",
        "",
        '    <rect width="%d" height="%d" rx="%d" fill="url(#marca)"/>' % (LIENZO, LIENZO, radio),
        "",
    ]
    if extra:
        lineas += ["    <!-- Detalle secundario -->", "    " + extra.strip(), ""]
    lineas += [
        "    <!-- %s -->" % (_seguro_comentario(nombre_simbolo) or "Símbolo"),
        '    <g id="simbolo" transform="%s" fill="none"' % TRANSFORMACION_SIMBOLO,
        '       stroke="#ffffff" stroke-width="%s" stroke-linecap="round" stroke-linejoin="round">' % TRAZO,
        "        " + simbolo.strip(),
        "    </g>",
        "</svg>",
        "",
    ]
    return "\n".join(lineas)


# ===========================================================================
#  Rasterizador SVG en Python puro
# ===========================================================================

_IDENT = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)
_K = 0.5522847498307936  # control de Bézier para un cuarto de círculo
_RE_NUM = re.compile(r"[+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?")


def _mult(m, n):
    """m ∘ n: primero se aplica n y después m."""
    a, b, c, d, e, f = m
    A, B, C, D, E, F = n
    return (a * A + c * B, b * A + d * B, a * C + c * D, b * C + d * D,
            a * E + c * F + e, b * E + d * F + f)


def _aplicar(m, x, y):
    return (m[0] * x + m[2] * y + m[4], m[1] * x + m[3] * y + m[5])


def _inversa(m):
    a, b, c, d, e, f = m
    det = a * d - b * c
    if abs(det) < 1e-12:
        return None
    return (d / det, -b / det, -c / det, a / det, (c * f - d * e) / det, (b * e - a * f) / det)


def _numeros(texto):
    return [float(x) for x in _RE_NUM.findall(texto or "")]


def _transformacion(texto):
    m = _IDENT
    for nombre, args in re.findall(r"([a-zA-Z]+)\s*\(([^)]*)\)", texto or ""):
        v = _numeros(args)
        nombre = nombre.lower()
        if nombre == "translate" and v:
            t = (1, 0, 0, 1, v[0], v[1] if len(v) > 1 else 0)
        elif nombre == "scale" and v:
            t = (v[0], 0, 0, v[1] if len(v) > 1 else v[0], 0, 0)
        elif nombre == "rotate" and v:
            r = math.radians(v[0])
            co, si = math.cos(r), math.sin(r)
            t = (co, si, -si, co, 0, 0)
            if len(v) >= 3:
                t = _mult(_mult((1, 0, 0, 1, v[1], v[2]), t), (1, 0, 0, 1, -v[1], -v[2]))
        elif nombre == "skewx" and v:
            t = (1, 0, math.tan(math.radians(v[0])), 1, 0, 0)
        elif nombre == "skewy" and v:
            t = (1, math.tan(math.radians(v[0])), 0, 1, 0, 0)
        elif nombre == "matrix" and len(v) == 6:
            t = tuple(v)
        else:
            continue
        m = _mult(m, t)
    return m


def _longitud(valor, defecto=0.0, referencia=LIENZO):
    if valor is None:
        return defecto
    v = str(valor).strip()
    m = _RE_NUM.match(v)
    if not m:
        return defecto
    n = float(m.group(0))
    return n * referencia / 100.0 if v.endswith("%") else n


_NOMBRES_COLOR = {
    "black": (0, 0, 0), "white": (255, 255, 255), "red": (255, 0, 0), "green": (0, 128, 0),
    "blue": (0, 0, 255), "gray": (128, 128, 128), "grey": (128, 128, 128), "yellow": (255, 255, 0),
    "orange": (255, 165, 0), "silver": (192, 192, 192), "navy": (0, 0, 128), "teal": (0, 128, 128),
    "purple": (128, 0, 128), "maroon": (128, 0, 0), "lime": (0, 255, 0), "aqua": (0, 255, 255),
    "cyan": (0, 255, 255), "fuchsia": (255, 0, 255), "magenta": (255, 0, 255), "olive": (128, 128, 0),
}


def _color(valor, actual="#000000", _prof=0):
    """Devuelve (r, g, b, a) en 0..1, o None para 'none'."""
    v = (valor or "").strip().lower()
    if v in ("", "none"):
        return None
    if v == "transparent":
        return (0.0, 0.0, 0.0, 0.0)
    if v == "currentcolor":
        return _color(actual, "#000000", _prof + 1) if _prof < 4 else (0.0, 0.0, 0.0, 1.0)
    if v.startswith("#"):
        h = v[1:]
        if len(h) in (3, 4):
            h = "".join(c * 2 for c in h)
        if len(h) in (6, 8) and all(c in "0123456789abcdef" for c in h):
            r, g, b = (int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4))
            a = int(h[6:8], 16) / 255.0 if len(h) == 8 else 1.0
            return (r, g, b, a)
        return None
    m = re.match(r"rgba?\(([^)]*)\)", v)
    if m:
        partes = [p.strip() for p in re.split(r"[,\s/]+", m.group(1)) if p.strip()]
        canal = []
        for i, p in enumerate(partes[:4]):
            n = float(_RE_NUM.match(p).group(0)) if _RE_NUM.match(p) else 0.0
            if p.endswith("%"):
                n = n / 100.0 * (255.0 if i < 3 else 1.0)
            canal.append(n)
        while len(canal) < 3:
            canal.append(0.0)
        a = canal[3] if len(canal) > 3 else 1.0
        return (canal[0] / 255.0, canal[1] / 255.0, canal[2] / 255.0, max(0.0, min(1.0, a)))
    if v in _NOMBRES_COLOR:
        r, g, b = _NOMBRES_COLOR[v]
        return (r / 255.0, g / 255.0, b / 255.0, 1.0)
    return None


class _Trazado:
    """Construye subtrazados ya aplanados y en coordenadas de píxel."""

    def __init__(self, m, tol=0.08):
        self.m = m
        self.tol = tol
        self.subs = []          # [[puntos, cerrado], ...]
        self.act = None
        self.ini = (0.0, 0.0)
        self.caja = [math.inf, math.inf, -math.inf, -math.inf]  # en coordenadas de usuario

    def _c(self, x, y):
        c = self.caja
        if x < c[0]: c[0] = x
        if y < c[1]: c[1] = y
        if x > c[2]: c[2] = x
        if y > c[3]: c[3] = y

    def mover(self, x, y):
        self._c(x, y)
        self.ini = (x, y)
        self.act = [_aplicar(self.m, x, y)]
        self.subs.append([self.act, False])

    def _asegurar(self):
        if self.act is None:
            self.mover(*self.ini)

    def linea(self, x, y):
        self._asegurar()
        self._c(x, y)
        self.act.append(_aplicar(self.m, x, y))

    def cubica(self, x1, y1, x2, y2, x, y):
        self._asegurar()
        for px, py in ((x1, y1), (x2, y2), (x, y)):
            self._c(px, py)
        p0 = self.act[-1]
        p1 = _aplicar(self.m, x1, y1)
        p2 = _aplicar(self.m, x2, y2)
        p3 = _aplicar(self.m, x, y)
        ddx = max(abs(p0[0] - 2 * p1[0] + p2[0]), abs(p1[0] - 2 * p2[0] + p3[0]))
        ddy = max(abs(p0[1] - 2 * p1[1] + p2[1]), abs(p1[1] - 2 * p2[1] + p3[1]))
        n = int(math.ceil(math.sqrt(6.0 * math.hypot(ddx, ddy) / (8.0 * self.tol))))
        n = max(1, min(n, 256))
        for i in range(1, n):
            t = i / float(n)
            u = 1.0 - t
            a, b, c, d = u * u * u, 3 * u * u * t, 3 * u * t * t, t * t * t
            self.act.append((a * p0[0] + b * p1[0] + c * p2[0] + d * p3[0],
                             a * p0[1] + b * p1[1] + c * p2[1] + d * p3[1]))
        self.act.append(p3)

    def cerrar(self):
        if self.act is not None:
            self.subs[-1][1] = True
            self.act = None


def _arco_a_cubicas(x1, y1, rx, ry, phi, fa, fs, x2, y2):
    """Arco elíptico de SVG (forma de extremos) a curvas cúbicas. None = recta."""
    if x1 == x2 and y1 == y2:
        return []
    rx, ry = abs(rx), abs(ry)
    if rx < 1e-12 or ry < 1e-12:
        return None
    phi = math.radians(phi % 360)
    co, si = math.cos(phi), math.sin(phi)
    dx2, dy2 = (x1 - x2) / 2.0, (y1 - y2) / 2.0
    x1p = co * dx2 + si * dy2
    y1p = -si * dx2 + co * dy2
    lam = (x1p * x1p) / (rx * rx) + (y1p * y1p) / (ry * ry)
    if lam > 1:
        s = math.sqrt(lam)
        rx, ry = rx * s, ry * s
    num = rx * rx * ry * ry - rx * rx * y1p * y1p - ry * ry * x1p * x1p
    den = rx * rx * y1p * y1p + ry * ry * x1p * x1p
    coef = math.sqrt(max(0.0, num / den)) if den else 0.0
    if fa == fs:
        coef = -coef
    cxp = coef * rx * y1p / ry
    cyp = -coef * ry * x1p / rx
    cx = co * cxp - si * cyp + (x1 + x2) / 2.0
    cy = si * cxp + co * cyp + (y1 + y2) / 2.0

    def ang(ux, uy, vx, vy):
        return math.atan2(ux * vy - uy * vx, ux * vx + uy * vy)

    ux, uy = (x1p - cxp) / rx, (y1p - cyp) / ry
    vx, vy = (-x1p - cxp) / rx, (-y1p - cyp) / ry
    th1 = ang(1.0, 0.0, ux, uy)
    dth = ang(ux, uy, vx, vy)
    if not fs and dth > 0:
        dth -= 2 * math.pi
    elif fs and dth < 0:
        dth += 2 * math.pi
    segs = max(1, int(math.ceil(abs(dth) / (math.pi / 2) - 1e-9)))
    delta = dth / segs
    k = 4.0 / 3.0 * math.tan(delta / 4.0)

    def mapa(ex, ey):
        return (cx + co * rx * ex - si * ry * ey, cy + si * rx * ex + co * ry * ey)

    out = []
    t = th1
    for i in range(segs):
        c1, s1 = math.cos(t), math.sin(t)
        t2 = t + delta
        c2, s2 = math.cos(t2), math.sin(t2)
        a = mapa(c1 - k * s1, s1 + k * c1)
        b = mapa(c2 + k * s2, s2 - k * c2)
        e = (x2, y2) if i == segs - 1 else mapa(c2, s2)
        out.append((a, b, e))
        t = t2
    return out


def _leer_trazado(d, b):
    """Interpreta el atributo `d` de un <path> sobre el constructor `b`."""
    pos = 0
    L = len(d)
    cx = cy = sx = sy = 0.0
    ultimo_c = None   # segundo control de la última C/S, para S
    ultimo_q = None   # control de la última Q/T, para T

    def saltar():
        nonlocal pos
        while pos < L and d[pos] in " \t\r\n,":
            pos += 1

    def numero():
        nonlocal pos
        saltar()
        m = _RE_NUM.match(d, pos)
        if not m:
            raise ValueError("se esperaba un número en la posición %d" % pos)
        pos = m.end()
        return float(m.group(0))

    def bandera():
        nonlocal pos
        saltar()
        if pos >= L or d[pos] not in "01":
            raise ValueError("bandera de arco inválida en la posición %d" % pos)
        pos += 1
        return d[pos - 1] == "1"

    def hay_numero():
        saltar()
        return pos < L and d[pos] in "+-.0123456789"

    while True:
        saltar()
        if pos >= L:
            break
        c = d[pos]
        if not c.isalpha():
            raise ValueError("se esperaba un comando en la posición %d" % pos)
        pos += 1
        C = c.upper()
        rel = c != C
        if C == "Z":
            b.cerrar()
            cx, cy = sx, sy
            ultimo_c = ultimo_q = None
            continue
        primero = True
        while primero or hay_numero():
            ox, oy = (cx, cy) if rel else (0.0, 0.0)
            nc = nq = None
            if C == "M":
                x, y = numero() + ox, numero() + oy
                if primero:
                    b.mover(x, y)
                    sx, sy = x, y
                else:
                    b.linea(x, y)
                cx, cy = x, y
            elif C == "L":
                cx, cy = numero() + ox, numero() + oy
                b.linea(cx, cy)
            elif C == "H":
                cx = numero() + ox
                b.linea(cx, cy)
            elif C == "V":
                cy = numero() + oy
                b.linea(cx, cy)
            elif C in ("C", "S"):
                if C == "C":
                    x1, y1 = numero() + ox, numero() + oy
                else:
                    x1, y1 = (2 * cx - ultimo_c[0], 2 * cy - ultimo_c[1]) if ultimo_c else (cx, cy)
                x2, y2 = numero() + ox, numero() + oy
                x, y = numero() + ox, numero() + oy
                b.cubica(x1, y1, x2, y2, x, y)
                nc = (x2, y2)
                cx, cy = x, y
            elif C in ("Q", "T"):
                if C == "Q":
                    qx, qy = numero() + ox, numero() + oy
                else:
                    qx, qy = (2 * cx - ultimo_q[0], 2 * cy - ultimo_q[1]) if ultimo_q else (cx, cy)
                x, y = numero() + ox, numero() + oy
                b.cubica(cx + 2.0 / 3 * (qx - cx), cy + 2.0 / 3 * (qy - cy),
                         x + 2.0 / 3 * (qx - x), y + 2.0 / 3 * (qy - y), x, y)
                nq = (qx, qy)
                cx, cy = x, y
            elif C == "A":
                rx, ry, rot = numero(), numero(), numero()
                fa, fs = bandera(), bandera()
                x, y = numero() + ox, numero() + oy
                curvas = _arco_a_cubicas(cx, cy, rx, ry, rot, fa, fs, x, y)
                if curvas is None:
                    b.linea(x, y)
                else:
                    for (a1, a2, a3) in curvas:
                        b.cubica(a1[0], a1[1], a2[0], a2[1], a3[0], a3[1])
                cx, cy = x, y
            else:
                raise ValueError("comando de trazado desconocido: %s" % c)
            ultimo_c, ultimo_q = nc, nq
            if C == "M":
                C = "L"
            primero = False


def _rect(b, x, y, w, h, rx, ry):
    if w <= 0 or h <= 0:
        return
    if rx <= 0 or ry <= 0:
        b.mover(x, y); b.linea(x + w, y); b.linea(x + w, y + h); b.linea(x, y + h); b.cerrar()
        return
    rx, ry = min(rx, w / 2.0), min(ry, h / 2.0)
    kx, ky = _K * rx, _K * ry
    b.mover(x + rx, y)
    b.linea(x + w - rx, y)
    b.cubica(x + w - rx + kx, y, x + w, y + ry - ky, x + w, y + ry)
    b.linea(x + w, y + h - ry)
    b.cubica(x + w, y + h - ry + ky, x + w - rx + kx, y + h, x + w - rx, y + h)
    b.linea(x + rx, y + h)
    b.cubica(x + rx - kx, y + h, x, y + h - ry + ky, x, y + h - ry)
    b.linea(x, y + ry)
    b.cubica(x, y + ry - ky, x + rx - kx, y, x + rx, y)
    b.cerrar()


def _elipse(b, cx, cy, rx, ry):
    if rx <= 0 or ry <= 0:
        return
    kx, ky = _K * rx, _K * ry
    b.mover(cx + rx, cy)
    b.cubica(cx + rx, cy + ky, cx + kx, cy + ry, cx, cy + ry)
    b.cubica(cx - kx, cy + ry, cx - rx, cy + ky, cx - rx, cy)
    b.cubica(cx - rx, cy - ky, cx - kx, cy - ry, cx, cy - ry)
    b.cubica(cx + kx, cy - ry, cx + rx, cy - ky, cx + rx, cy)
    b.cerrar()


def _discontinuar(pts, cerrado, patron, desfase):
    """Parte una polilínea según stroke-dasharray. Devuelve [(puntos, False), ...]."""
    if cerrado:
        pts = pts + [pts[0]]
    if len(patron) % 2:
        patron = patron * 2
    total = sum(patron)
    if total <= 0 or len(pts) < 2:
        return [(pts, False)]
    off = desfase % total
    idx = 0
    while off >= patron[idx]:
        off -= patron[idx]
        idx = (idx + 1) % len(patron)
    resto = patron[idx] - off
    activo = idx % 2 == 0
    piezas = []
    cur = [pts[0]] if activo else None
    for i in range(len(pts) - 1):
        a, b = pts[i], pts[i + 1]
        lon = math.hypot(b[0] - a[0], b[1] - a[1])
        p = 0.0
        guarda = 0
        while lon - p > resto and guarda < 100000:
            guarda += 1
            p += resto
            f = p / lon
            q = (a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f)
            if activo:
                cur.append(q)
                piezas.append((cur, False))
                cur = None
            else:
                cur = [q]
            activo = not activo
            idx = (idx + 1) % len(patron)
            resto = patron[idx]
        resto -= lon - p
        if activo and cur is not None:
            cur.append(b)
    if activo and cur and len(cur) >= 2:
        piezas.append((cur, False))
    return piezas


class _Degradado:
    def __init__(self, tipo, attrs, paradas):
        self.tipo = tipo
        self.attrs = attrs
        self.paradas = paradas  # [(offset, (r,g,b,a))]
        self.lut = self._lut()

    def _lut(self):
        p = self.paradas
        if not p:
            return None
        lut = []
        for i in range(256):
            t = i / 255.0
            if t <= p[0][0]:
                lut.append(p[0][1]); continue
            if t >= p[-1][0]:
                lut.append(p[-1][1]); continue
            for j in range(len(p) - 1):
                o0, c0 = p[j]
                o1, c1 = p[j + 1]
                if o0 <= t <= o1:
                    f = 0.0 if o1 == o0 else (t - o0) / (o1 - o0)
                    lut.append(tuple(c0[k] + (c1[k] - c0[k]) * f for k in range(4)))
                    break
        return lut


class Rasterizador:
    """Dibuja un SVG en un lienzo RGBA de n x n píxeles con antialias."""

    ELEMENTOS_IGNORADOS = {"defs", "title", "desc", "metadata", "linearGradient", "radialGradient",
                           "clipPath", "mask", "symbol", "pattern", "marker", "style", "script", "filter"}
    NO_SOPORTADOS = {"text", "image", "use", "foreignObject", "tspan", "switch"}
    HEREDABLES = ("fill", "stroke", "stroke-width", "stroke-linecap", "stroke-linejoin",
                  "stroke-dasharray", "stroke-dashoffset", "fill-rule", "fill-opacity",
                  "stroke-opacity", "color", "visibility")

    def __init__(self, texto_svg):
        try:
            self.raiz = ET.fromstring(texto_svg.encode("utf-8") if isinstance(texto_svg, str) else texto_svg)
        except ET.ParseError as e:
            raise ErrorIcono("El SVG no es XML válido (%s). Si tiene `--` dentro de un comentario, quítalo." % e)
        if _sin_ns(self.raiz.tag) != "svg":
            raise ErrorIcono("El archivo no es un SVG (la raíz es <%s>)." % _sin_ns(self.raiz.tag))
        self.avisos = set()
        self.por_id = {}
        for el in self.raiz.iter():
            if el.get("id"):
                self.por_id[el.get("id")] = el
            nombre = _sin_ns(el.tag)
            if nombre in self.NO_SOPORTADOS:
                self.avisos.add("<%s> no se dibuja en los PNG; usa sólo formas y trazados." % nombre)
            elif nombre in ("filter", "mask", "clipPath", "pattern"):
                self.avisos.add("<%s> no se aplica en los PNG; el resultado puede diferir del navegador." % nombre)
        vb = _numeros(self.raiz.get("viewBox"))
        if len(vb) == 4 and vb[2] > 0 and vb[3] > 0:
            self.vb = vb
        else:
            w = _longitud(self.raiz.get("width"), LIENZO)
            h = _longitud(self.raiz.get("height"), LIENZO)
            self.vb = [0.0, 0.0, w or LIENZO, h or LIENZO]
            self.avisos.add("el SVG no tiene viewBox; se usa 0 0 %g %g." % (self.vb[2], self.vb[3]))
        self._degradados = {}

    # ----------------------------------------------------------------- estilo
    @staticmethod
    def _propiedades(el):
        props = {}
        for k, v in el.attrib.items():
            props[_sin_ns(k)] = v.strip()
        estilo = el.get("style")
        if estilo:
            for decl in estilo.split(";"):
                if ":" in decl:
                    k, v = decl.split(":", 1)
                    props[k.strip()] = v.strip().replace("!important", "").strip()
        return props

    def _estilo(self, props, padre):
        est = dict(padre)
        for k in self.HEREDABLES:
            if k in props and props[k] != "inherit":
                est[k] = props[k]
        return est

    # ------------------------------------------------------------- degradados
    def _degradado(self, ident, prof=0):
        if ident in self._degradados:
            return self._degradados[ident]
        el = self.por_id.get(ident)
        if el is None or _sin_ns(el.tag) not in ("linearGradient", "radialGradient") or prof > 8:
            return None
        tipo = _sin_ns(el.tag)
        attrs = {}
        paradas = []
        href = el.get("href") or el.get("{http://www.w3.org/1999/xlink}href")
        if href and href.startswith("#"):
            base = self._degradado(href[1:], prof + 1)
            if base is not None:
                attrs.update(base.attrs)
                paradas = list(base.paradas)
        for k, v in el.attrib.items():
            attrs[_sin_ns(k)] = v
        propias = []
        for st in el:
            if _sin_ns(st.tag) != "stop":
                continue
            p = self._propiedades(st)
            off = p.get("offset", "0").strip()
            o = _longitud(off, 0.0, 1.0) if off.endswith("%") else _longitud(off, 0.0)
            o = max(0.0, min(1.0, o))
            if propias and o < propias[-1][0]:
                o = propias[-1][0]
            c = _color(p.get("stop-color", "black"), p.get("color", "#000000")) or (0.0, 0.0, 0.0, 0.0)
            a = c[3] * max(0.0, min(1.0, _longitud(p.get("stop-opacity"), 1.0)))
            propias.append((o, (c[0], c[1], c[2], a)))
        if propias:
            paradas = propias
        g = _Degradado(tipo, attrs, paradas)
        self._degradados[ident] = g
        return g

    def _pintura(self, valor, est, m, caja, opacidad):
        """('s', rgba) para un color liso, ('g', funcion(x, y)) para un degradado, o None."""
        v = (valor or "").strip()
        if v.startswith("url("):
            m_url = re.match(r"url\(\s*['\"]?#([^)'\"]+)['\"]?\s*\)\s*(.*)", v)
            g = self._degradado(m_url.group(1)) if m_url else None
            if g is None or not g.lut:
                return self._pintura(m_url.group(2) if m_url else "none", est, m, caja, opacidad)
            if len(g.paradas) == 1:
                r, gg, b, a = g.paradas[0][1]
                return ("s", (r, gg, b, a * opacidad))
            return self._funcion_degradado(g, m, caja, opacidad)
        c = _color(v, est.get("color", "#000000"))
        if c is None:
            return None
        return ("s", (c[0], c[1], c[2], c[3] * opacidad))

    def _funcion_degradado(self, g, m, caja, opacidad):
        at = g.attrs
        obb = at.get("gradientUnits", "objectBoundingBox") != "userSpaceOnUse"
        if obb:
            x0, y0, x1, y1 = caja
            bw, bh = x1 - x0, y1 - y0
            if bw <= 0 or bh <= 0:
                return None
            base = (bw, 0.0, 0.0, bh, x0, y0)
            ref_x = ref_y = 1.0
        else:
            base = _IDENT
            ref_x, ref_y = self.vb[2], self.vb[3]
        gm = _mult(m, _mult(base, _transformacion(at.get("gradientTransform", ""))))
        inv = _inversa(gm)
        if inv is None:
            return None

        def coord(nombre, defecto, ref):
            v = at.get(nombre)
            if v is None:
                return defecto * ref
            v = v.strip()
            return _longitud(v, 0.0, ref) if v.endswith("%") else _longitud(v, 0.0)

        lut = g.lut
        spread = at.get("spreadMethod", "pad")

        def ajustar(t):
            if spread == "repeat":
                t = t - math.floor(t)
            elif spread == "reflect":
                t = t % 2.0
                if t > 1.0:
                    t = 2.0 - t
            return 0.0 if t < 0.0 else (1.0 if t > 1.0 else t)

        a0, a1, a2, a3, a4, a5 = inv
        if g.tipo == "linearGradient":
            gx1, gy1 = coord("x1", 0.0, ref_x), coord("y1", 0.0, ref_y)
            gx2, gy2 = coord("x2", 1.0, ref_x), coord("y2", 0.0, ref_y)
            vx, vy = gx2 - gx1, gy2 - gy1
            vv = vx * vx + vy * vy
            if vv <= 0:
                r, gg, b, a = lut[255]
                return ("s", (r, gg, b, a * opacidad))
            A = (a0 * vx + a1 * vy) / vv
            B = (a2 * vx + a3 * vy) / vv
            Cc = ((a4 - gx1) * vx + (a5 - gy1) * vy) / vv

            def f(X, Y):
                r, gg, b, a = lut[int(ajustar(A * X + B * Y + Cc) * 255 + 0.5)]
                return (r, gg, b, a * opacidad)
        else:
            gcx, gcy = coord("cx", 0.5, ref_x), coord("cy", 0.5, ref_y)
            gr = coord("r", 0.5, min(ref_x, ref_y))
            if gr <= 0:
                r, gg, b, a = lut[255]
                return ("s", (r, gg, b, a * opacidad))

            def f(X, Y):
                gx = a0 * X + a2 * Y + a4
                gy = a1 * X + a3 * Y + a5
                r, gg, b, a = lut[int(ajustar(math.hypot(gx - gcx, gy - gcy) / gr) * 255 + 0.5)]
                return (r, gg, b, a * opacidad)
        return ("g", f)

    # -------------------------------------------------------------- dibujo
    def dibujar(self, n):
        """Devuelve los bytes RGBA (sin premultiplicar) de un lienzo de n x n."""
        self.n = n
        self.R = [0.0] * (n * n)
        self.G = [0.0] * (n * n)
        self.B = [0.0] * (n * n)
        self.A = [0.0] * (n * n)
        self.sub = max(4, min(16, 2048 // n))
        vx, vy, vw, vh = self.vb
        s = min(n / vw, n / vh)
        m = (s, 0.0, 0.0, s, (n - vw * s) / 2.0 - vx * s, (n - vh * s) / 2.0 - vy * s)
        est = {"fill": "black", "stroke": "none", "stroke-width": "1", "stroke-linecap": "butt",
               "stroke-linejoin": "miter", "fill-rule": "nonzero", "color": "#000000"}
        props = self._propiedades(self.raiz)
        est = self._estilo(props, est)
        for hijo in self.raiz:
            self._recorrer(hijo, est, m, 1.0)
        salida = bytearray(n * n * 4)
        R, G, B, A = self.R, self.G, self.B, self.A
        for i in range(n * n):
            a = A[i]
            if a <= 0.0:
                continue
            j = i * 4
            salida[j] = min(255, int(R[i] / a * 255 + 0.5))
            salida[j + 1] = min(255, int(G[i] / a * 255 + 0.5))
            salida[j + 2] = min(255, int(B[i] / a * 255 + 0.5))
            salida[j + 3] = min(255, int(a * 255 + 0.5))
        return bytes(salida)

    def _recorrer(self, el, est, m, op):
        tag = _sin_ns(el.tag)
        if tag in self.ELEMENTOS_IGNORADOS or tag in self.NO_SOPORTADOS:
            return
        props = self._propiedades(el)
        if props.get("display") == "none":
            return
        est = self._estilo(props, est)
        op = op * max(0.0, min(1.0, _longitud(props.get("opacity"), 1.0)))
        if op <= 0:
            return
        m = _mult(m, _transformacion(props.get("transform", "")))
        if tag in ("g", "svg", "a"):
            for hijo in el:
                self._recorrer(hijo, est, m, op)
        elif tag in ("rect", "circle", "ellipse", "line", "polyline", "polygon", "path"):
            if est.get("visibility") in ("hidden", "collapse"):
                return
            self._forma(tag, props, est, m, op)

    def _forma(self, tag, p, est, m, op):
        b = _Trazado(m)
        L = _longitud
        if tag == "rect":
            rx_a, ry_a = p.get("rx"), p.get("ry")
            rx = L(rx_a if rx_a not in (None, "auto") else ry_a, 0.0)
            ry = L(ry_a if ry_a not in (None, "auto") else rx_a, 0.0)
            _rect(b, L(p.get("x")), L(p.get("y")), L(p.get("width")), L(p.get("height")), rx, ry)
        elif tag == "circle":
            r = L(p.get("r"))
            _elipse(b, L(p.get("cx")), L(p.get("cy")), r, r)
        elif tag == "ellipse":
            _elipse(b, L(p.get("cx")), L(p.get("cy")), L(p.get("rx")), L(p.get("ry")))
        elif tag == "line":
            b.mover(L(p.get("x1")), L(p.get("y1")))
            b.linea(L(p.get("x2")), L(p.get("y2")))
        elif tag in ("polyline", "polygon"):
            v = _numeros(p.get("points"))
            if len(v) >= 2:
                b.mover(v[0], v[1])
                for i in range(2, len(v) - 1, 2):
                    b.linea(v[i], v[i + 1])
                if tag == "polygon":
                    b.cerrar()
        elif tag == "path":
            try:
                _leer_trazado(p.get("d", ""), b)
            except (ValueError, TypeError, IndexError) as e:
                self.avisos.add("trazado con errores (%s); se dibuja hasta donde se entiende." % e)
        if not b.subs:
            return
        caja = tuple(b.caja)

        if tag != "line":
            fo = max(0.0, min(1.0, L(est.get("fill-opacity"), 1.0)))
            pintura = self._pintura(est.get("fill"), est, m, caja, fo)
            if pintura is not None:
                region = self._relleno(b.subs, est.get("fill-rule", "nonzero"))
                if region:
                    self._componer(region, pintura, op)

        so = max(0.0, min(1.0, L(est.get("stroke-opacity"), 1.0)))
        pintura = self._pintura(est.get("stroke"), est, m, caja, so)
        escala = math.sqrt(abs(m[0] * m[3] - m[1] * m[2]))
        ancho = L(est.get("stroke-width"), 1.0) * escala
        if pintura is not None and ancho > 0:
            dash = None
            txt = (est.get("stroke-dasharray") or "none").strip()
            if txt != "none":
                vals = [abs(x) * escala for x in _numeros(txt)]
                if vals and sum(vals) > 0:
                    dash = vals
            desfase = L(est.get("stroke-dashoffset"), 0.0) * escala
            region = self._trazo(b.subs, ancho / 2.0, est.get("stroke-linecap", "butt"), dash, desfase)
            if region:
                self._componer(region, pintura, op)

    # -------------------------------------------------------------- relleno
    def _relleno(self, subs, regla):
        n = self.n
        aristas = []
        ymin = xmin = math.inf
        ymax = xmax = -math.inf
        for pts, _cerrado in subs:
            k = len(pts)
            if k < 2:
                continue
            for i in range(k):
                x0, y0 = pts[i]
                x1, y1 = pts[(i + 1) % k]
                xmin = min(xmin, x0); xmax = max(xmax, x0)
                ymin = min(ymin, y0); ymax = max(ymax, y0)
                if y0 == y1:
                    continue
                if y0 < y1:
                    aristas.append((y0, y1, x0, (x1 - x0) / (y1 - y0), 1))
                else:
                    aristas.append((y1, y0, x1, (x0 - x1) / (y0 - y1), -1))
        if not aristas:
            return None
        gx0, gx1 = max(0, int(math.floor(xmin))), min(n, int(math.ceil(xmax)))
        gy0, gy1 = max(0, int(math.floor(ymin))), min(n, int(math.ceil(ymax)))
        W, H = gx1 - gx0, gy1 - gy0
        if W <= 0 or H <= 0:
            return None
        aristas.sort()
        S = self.sub
        peso = 1.0 / S
        par = regla == "evenodd"
        cob = [0.0] * (W * H)
        for fila in range(gy0, gy1):
            activas = [a for a in aristas if a[0] < fila + 1 and a[1] > fila]
            if not activas:
                continue
            dif = [0.0] * (W + 2)
            frac = [0.0] * (W + 1)
            for k in range(S):
                y = fila + (k + 0.5) / S
                cortes = [(a[2] + (y - a[0]) * a[3], a[4]) for a in activas if a[0] <= y < a[1]]
                if len(cortes) < 2:
                    continue
                cortes.sort()
                w = 0
                for j in range(len(cortes) - 1):
                    w += cortes[j][1]
                    if (w & 1) if par else w:
                        xa = cortes[j][0] - gx0
                        xb = cortes[j + 1][0] - gx0
                        if xa < 0: xa = 0.0
                        if xb > W: xb = float(W)
                        if xb <= xa:
                            continue
                        ia, ib = int(xa), int(xb)
                        if ia == ib:
                            frac[ia] += (xb - xa) * peso
                        else:
                            frac[ia] += (ia + 1 - xa) * peso
                            dif[ia + 1] += peso
                            dif[ib] -= peso
                            if ib < W:
                                frac[ib] += (xb - ib) * peso
            acc = 0.0
            base = (fila - gy0) * W
            for i in range(W):
                acc += dif[i]
                v = acc + frac[i]
                if v > 0.0:
                    cob[base + i] = 1.0 if v > 1.0 else v
        return (gx0, gy0, W, H, cob)

    # ---------------------------------------------------------------- trazo
    def _trazo(self, subs, hw, remate, dash, desfase):
        n = self.n
        piezas = []
        for pts, cerrado in subs:
            if len(pts) < 2:
                continue
            if dash:
                piezas.extend(_discontinuar(pts, cerrado, dash, desfase))
            else:
                piezas.append((pts + [pts[0]] if cerrado else pts, cerrado))
        prims = []
        for pts, cerrado in piezas:
            limpios = [pts[0]]
            for q in pts[1:]:
                if abs(q[0] - limpios[-1][0]) > 1e-9 or abs(q[1] - limpios[-1][1]) > 1e-9:
                    limpios.append(q)
            if len(limpios) == 1:
                # Subtrazado de longitud cero: es un punto si el remate es redondo o cuadrado
                if remate in ("round", "square"):
                    x, y = limpios[0]
                    prims.append((x, y, x, y, remate, remate))
                continue
            ult = len(limpios) - 2
            for i in range(len(limpios) - 1):
                (ax, ay), (bx, by) = limpios[i], limpios[i + 1]
                ca = remate if (i == 0 and not cerrado) else "round"
                cb = remate if (i == ult and not cerrado) else "round"
                prims.append((ax, ay, bx, by, ca, cb))
        if not prims:
            return None
        ext = hw * 2 + 1.5
        gx0 = max(0, int(math.floor(min(min(p[0], p[2]) for p in prims) - ext)))
        gy0 = max(0, int(math.floor(min(min(p[1], p[3]) for p in prims) - ext)))
        gx1 = min(n, int(math.ceil(max(max(p[0], p[2]) for p in prims) + ext)))
        gy1 = min(n, int(math.ceil(max(max(p[1], p[3]) for p in prims) + ext)))
        W, H = gx1 - gx0, gy1 - gy0
        if W <= 0 or H <= 0:
            return None
        cob = [0.0] * (W * H)
        hypot = math.hypot

        def caja1d(d):
            v = (d + hw if d + hw < 0.5 else 0.5) - (d - hw if d - hw > -0.5 else -0.5)
            return 0.0 if v <= 0.0 else (1.0 if v > 1.0 else v)

        for ax, ay, bx, by, ca, cb in prims:
            dx, dy = bx - ax, by - ay
            lon = hypot(dx, dy)
            ea = hw if ca == "square" else 0.0
            eb = hw if cb == "square" else 0.0
            marg = hw + max(ea, eb) + 1.0
            x0 = max(gx0, int(math.floor(min(ax, bx) - marg)))
            x1 = min(gx1, int(math.ceil(max(ax, bx) + marg)))
            y0 = max(gy0, int(math.floor(min(ay, by) - marg)))
            y1 = min(gy1, int(math.ceil(max(ay, by) + marg)))
            if lon < 1e-9:
                for py in range(y0, y1):
                    fila = (py - gy0) * W - gx0
                    for px in range(x0, x1):
                        qx, qy = px + 0.5 - ax, py + 0.5 - ay
                        if ca == "round":
                            c = caja1d(hypot(qx, qy))
                        else:
                            c = caja1d(abs(qx)) * caja1d(abs(qy))
                        if c > cob[fila + px]:
                            cob[fila + px] = c
                continue
            ux, uy = dx / lon, dy / lon
            for py in range(y0, y1):
                fila = (py - gy0) * W - gx0
                qy0 = py + 0.5 - ay
                for px in range(x0, x1):
                    qx = px + 0.5 - ax
                    t = qx * ux + qy0 * uy
                    if t < 0.0 and ca == "round":
                        c = caja1d(hypot(qx, qy0))
                    elif t > lon and cb == "round":
                        c = caja1d(hypot(qx - dx, qy0 - dy))
                    else:
                        perp = qx * uy - qy0 * ux
                        c = caja1d(perp if perp >= 0 else -perp)
                        if c <= 0.0:
                            continue
                        if ca != "round":
                            f = t + ea + 0.5
                            c *= 0.0 if f <= 0 else (1.0 if f >= 1 else f)
                        if cb != "round":
                            f = lon - t + eb + 0.5
                            c *= 0.0 if f <= 0 else (1.0 if f >= 1 else f)
                    if c > cob[fila + px]:
                        cob[fila + px] = c
        return (gx0, gy0, W, H, cob)

    # ------------------------------------------------------------ composición
    def _componer(self, region, pintura, op):
        x0, y0, W, H, cob = region
        n = self.n
        R, G, B, A = self.R, self.G, self.B, self.A
        tipo, dato = pintura
        if tipo == "s":
            r, g, b, a0 = dato
            a0 *= op
            if a0 <= 0:
                return
        for fy in range(H):
            base = fy * W
            fila = (y0 + fy) * n + x0
            for fx in range(W):
                c = cob[base + fx]
                if c <= 0.0:
                    continue
                if tipo == "g":
                    r, g, b, a0 = dato(x0 + fx + 0.5, y0 + fy + 0.5)
                    a = c * a0 * op
                else:
                    a = c * a0
                if a <= 0.0:
                    continue
                i = fila + fx
                k = 1.0 - a
                R[i] = r * a + R[i] * k
                G[i] = g * a + G[i] * k
                B[i] = b * a + B[i] * k
                A[i] = a + A[i] * k


# ===========================================================================
#  PNG e ICO (escritura y lectura), sin dependencias
# ===========================================================================


def _bloque(tipo, datos):
    return struct.pack(">I", len(datos)) + tipo + datos + struct.pack(">I", zlib.crc32(tipo + datos) & 0xFFFFFFFF)


def codificar_png(ancho, alto, rgba):
    """PNG RGBA de 8 bits, eligiendo el filtro de cada fila para que pese menos."""
    paso = ancho * 4
    crudo = bytearray()
    previa = bytes(paso)
    cero4 = b"\x00\x00\x00\x00"

    def coste(fila):
        return sum(v if v < 128 else 256 - v for v in fila)

    for y in range(alto):
        fila = rgba[y * paso:(y + 1) * paso]
        izq = cero4 + fila[:-4]
        diag = cero4 + previa[:-4]
        candidatas = [
            (0, fila),
            (1, bytes((a - b) & 255 for a, b in zip(fila, izq))),
            (2, bytes((a - b) & 255 for a, b in zip(fila, previa))),
        ]
        pa = bytearray(paso)
        for i in range(paso):
            a, b, c = izq[i], previa[i], diag[i]
            p = a + b - c
            da, db, dc = abs(p - a), abs(p - b), abs(p - c)
            pred = a if (da <= db and da <= dc) else (b if db <= dc else c)
            pa[i] = (fila[i] - pred) & 255
        candidatas.append((4, bytes(pa)))
        filtro, datos = min(candidatas, key=lambda fd: coste(fd[1]))
        crudo.append(filtro)
        crudo.extend(datos)
        previa = fila
    ihdr = struct.pack(">IIBBBBB", ancho, alto, 8, 6, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n" + _bloque(b"IHDR", ihdr)
            + _bloque(b"IDAT", zlib.compress(bytes(crudo), 9)) + _bloque(b"IEND", b""))


def leer_png(ruta):
    """Devuelve (ancho, alto, pixel(x, y) -> (r, g, b, a) o None si no se puede decodificar)."""
    datos = Path(ruta).read_bytes()
    if datos[:8] != b"\x89PNG\r\n\x1a\n":
        raise ErrorIcono("%s no es un PNG." % ruta)
    pos = 8
    ihdr = None
    idat = bytearray()
    paleta = []
    trns = b""
    while pos + 8 <= len(datos):
        lon = struct.unpack(">I", datos[pos:pos + 4])[0]
        tipo = datos[pos + 4:pos + 8]
        cuerpo = datos[pos + 8:pos + 8 + lon]
        pos += 12 + lon
        if tipo == b"IHDR":
            ihdr = struct.unpack(">IIBBBBB", cuerpo)
        elif tipo == b"IDAT":
            idat.extend(cuerpo)
        elif tipo == b"PLTE":
            paleta = [tuple(cuerpo[i:i + 3]) for i in range(0, len(cuerpo), 3)]
        elif tipo == b"tRNS":
            trns = cuerpo
        elif tipo == b"IEND":
            break
    if ihdr is None:
        raise ErrorIcono("%s no tiene cabecera IHDR." % ruta)
    w, h, prof, ctipo, _c, _f, entrelazado = ihdr
    canales = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}.get(ctipo)
    if prof != 8 or entrelazado or canales is None:
        return w, h, None
    bpp = canales
    paso = w * bpp
    crudo = zlib.decompress(bytes(idat))
    pix = bytearray(paso * h)
    previa = bytearray(paso)
    p = 0
    for y in range(h):
        f = crudo[p]
        fila = bytearray(crudo[p + 1:p + 1 + paso])
        p += 1 + paso
        for i in range(paso):
            a = fila[i - bpp] if i >= bpp else 0
            b = previa[i]
            c = previa[i - bpp] if i >= bpp else 0
            if f == 1:
                fila[i] = (fila[i] + a) & 255
            elif f == 2:
                fila[i] = (fila[i] + b) & 255
            elif f == 3:
                fila[i] = (fila[i] + ((a + b) >> 1)) & 255
            elif f == 4:
                pp = a + b - c
                pa, pb, pc = abs(pp - a), abs(pp - b), abs(pp - c)
                fila[i] = (fila[i] + (a if (pa <= pb and pa <= pc) else (b if pb <= pc else c))) & 255
        pix[y * paso:(y + 1) * paso] = fila
        previa = fila

    def pixel(x, y):
        i = y * paso + x * bpp
        if ctipo == 6:
            return tuple(pix[i:i + 4])
        if ctipo == 2:
            return (pix[i], pix[i + 1], pix[i + 2], 255)
        if ctipo == 4:
            return (pix[i], pix[i], pix[i], pix[i + 1])
        if ctipo == 0:
            return (pix[i], pix[i], pix[i], 255)
        k = pix[i]
        r, g, b = paleta[k] if k < len(paleta) else (0, 0, 0)
        return (r, g, b, trns[k] if k < len(trns) else 255)

    return w, h, pixel


def codificar_ico(pngs):
    """favicon.ico con los PNG dentro (lo aceptan todos los navegadores actuales)."""
    cab = struct.pack("<HHH", 0, 1, len(pngs))
    entradas = b""
    cuerpo = b""
    desplaz = 6 + 16 * len(pngs)
    for tam, datos in pngs:
        lado = 0 if tam >= 256 else tam
        entradas += struct.pack("<BBBBHHII", lado, lado, 0, 0, 1, 32, len(datos), desplaz + len(cuerpo))
        cuerpo += datos
    return cab + entradas + cuerpo


# ===========================================================================
#  Operaciones
# ===========================================================================


def rasterizar(svg_texto, tamanos):
    """{tamaño: bytes PNG} a partir del texto del SVG."""
    r = Rasterizador(svg_texto)
    salida = {}
    for n in sorted(set(tamanos), reverse=True):
        salida[n] = codificar_png(n, n, r.dibujar(n))
    for a in sorted(r.avisos):
        _aviso(a)
    return salida


def _escribir(ruta, datos, simulacro):
    if simulacro:
        print("  (simulacro) escribiría %s" % ruta)
        return
    tmp = ruta.with_name(ruta.name + ".tmp")
    tmp.write_bytes(datos)
    os.replace(str(tmp), str(ruta))  # escritura atómica: nunca queda un archivo a medias
    print("  %-20s %s" % (ruta.name, _kb(ruta)))


def _tamanos(texto):
    try:
        v = sorted({int(x) for x in str(texto).replace(" ", "").split(",") if x}, reverse=True)
    except ValueError:
        raise ErrorIcono("--tamanos espera números separados por comas, p. ej. 512,192,32")
    if not v or any(x < 8 or x > 2048 for x in v):
        raise ErrorIcono("--tamanos: cada tamaño debe estar entre 8 y 2048 píxeles.")
    return v


def _generar_derivados(svg_texto, carpeta, prefijo, tamanos, ico, simulacro):
    pngs = rasterizar(svg_texto, set(tamanos) | (set(TAMANOS_ICO) if ico else set()))
    for n in tamanos:
        _escribir(carpeta / nombre_png(prefijo, n), pngs[n], simulacro)
    if ico:
        _escribir(carpeta / "favicon.ico", codificar_ico([(n, pngs[n]) for n in TAMANOS_ICO]), simulacro)


def _ruta_web(carpeta, ruta_web):
    if ruta_web is not None:
        return ruta_web.rstrip("/")
    try:
        rel = os.path.relpath(str(carpeta.resolve()), os.getcwd())
    except ValueError:
        rel = str(carpeta)
    return "" if rel == "." else Path(rel).as_posix()


def _enlaces(base, prefijo, ico):
    pre = (base + "/") if base else ""
    lineas = []
    if ico:
        lineas.append('<link rel="icon" href="%sfavicon.ico" sizes="any">' % pre)
    lineas += [
        '<link rel="icon" type="image/svg+xml" href="%s%s.svg">' % (pre, prefijo),
        '<link rel="icon" type="image/png" sizes="32x32" href="%s%s">' % (pre, nombre_png(prefijo, 32)),
        '<link rel="icon" type="image/png" sizes="16x16" href="%s%s">' % (pre, nombre_png(prefijo, 16)),
        '<link rel="apple-touch-icon" href="%s%s">' % (pre, nombre_png(prefijo, 180)),
    ]
    return "\n".join(lineas)


def orden_crear(a):
    if a.prefijo == PREFIJO:
        palabra = limpiar_palabra(a.palabra) if a.palabra else palabra_de(a.nombre)
        if palabra:
            a.prefijo = PREFIJO + "-" + palabra
    carpeta = Path(a.destino)
    if not carpeta.is_dir():
        if a.crear_carpeta:
            if not a.simulacro:
                carpeta.mkdir(parents=True, exist_ok=True)
        else:
            raise ErrorIcono(
                "La carpeta %s no existe. Usa la carpeta de imágenes que el proyecto ya tiene "
                "(vistas/img, public/img, assets/img, static/img…) o añade --crear-carpeta." % carpeta)

    # Colores: explícitos o sacados de los tokens del sistema de diseño
    tokens = leer_tokens(a.css) if a.css else {}
    tp, to = a.token_primario.lstrip("-"), a.token_oscuro.lstrip("-")
    primario = a.primario or tokens.get(tp)
    oscuro = a.oscuro or tokens.get(to)
    if not primario or not oscuro:
        faltan = [t for t, v in ((tp, primario), (to, oscuro)) if not v]
        raise ErrorIcono(
            "Faltan colores (%s). Pásalos con --primario/--oscuro o con --css apuntando al archivo "
            "de tokens. Si el proyecto no tiene tokens, pregunta por sus dos colores de marca: "
            "no los inventes." % ", ".join(faltan))

    # Símbolo
    fuentes = [x for x in (a.simbolo, a.simbolo_svg, a.trazado) if x]
    if len(fuentes) != 1:
        raise ErrorIcono("Indica exactamente uno: --simbolo NOMBRE, --simbolo-svg ARCHIVO o --trazado '<path …/>'.")
    if a.simbolo:
        if a.simbolo not in SIMBOLOS:
            raise ErrorIcono("No conozco el símbolo '%s'. Mira la lista con: %s" % (a.simbolo, _llamada("simbolos")))
        simbolo, nombre_simbolo = SIMBOLOS[a.simbolo], a.simbolo
    elif a.simbolo_svg:
        simbolo, nombre_simbolo = simbolo_desde_svg(a.simbolo_svg), Path(a.simbolo_svg).stem
    else:
        simbolo, nombre_simbolo = a.trazado, "propio"

    svg = construir_svg(a.nombre, simbolo, primario, oscuro, nombre_simbolo=nombre_simbolo,
                        motivo=a.motivo or "", token_primario=tp, token_oscuro=to,
                        extra=a.extra or "", redondo=a.redondo)
    ruta_svg = carpeta / (a.prefijo + ".svg")
    tamanos = _tamanos(a.tamanos)

    existentes = [p for p in [ruta_svg] + [carpeta / nombre_png(a.prefijo, n) for n in tamanos]
                  + ([carpeta / "favicon.ico"] if a.ico else []) if p.exists()]
    if existentes and not a.sobrescribir and not a.simulacro:
        raise ErrorIcono("Ya existen %s. No se toca nada. Si quieres reemplazarlos, añade --sobrescribir."
                         % ", ".join(p.name for p in existentes))

    print("Icono de %s  ·  símbolo %s  ·  %s → %s%s"
          % (a.nombre, nombre_simbolo, normalizar_hex(primario), normalizar_hex(oscuro),
             "  ·  variante redonda" if a.redondo else ""))
    if a.simulacro:
        print(svg)
    _escribir(ruta_svg, svg.encode("utf-8"), a.simulacro)
    _generar_derivados(svg, carpeta, a.prefijo, tamanos, a.ico, a.simulacro)

    print("\nPega esto en el <head> de tu plantilla y de las páginas que viven fuera de ella")
    print("(error, acceso denegado, mantenimiento). La herramienta no edita ningún archivo tuyo:\n")
    print(_enlaces(_ruta_web(carpeta, a.ruta_web), a.prefijo, a.ico))
    print("\nTarjeta de la intranet: %s (o %s si es grande). Si la tarjeta recorta en"
          "\ncírculo, genera la variante con --redondo en otra carpeta o con otro --prefijo."
          % (nombre_png(a.prefijo, 192), nombre_png(a.prefijo, 512)))
    if not a.simulacro:
        print("Revísalo a 160, 64, 32 y 16 px:  %s" % _llamada("vista-previa %s" % carpeta))
    return 0


def _resolver_svg(objetivo, prefijo):
    p = Path(objetivo)
    if p.is_dir():
        carpeta, p = p, p / (prefijo + ".svg")
        if not p.is_file() and prefijo == PREFIJO:
            # Los iconos con palabra: icono-<palabra>.svg (si hay uno solo, es ése)
            con_palabra = [f for f in sorted(carpeta.glob(PREFIJO + "-*.svg"))
                           if not re.fullmatch(re.escape(PREFIJO) + r"-\d+", f.stem)]
            if len(con_palabra) == 1:
                p = con_palabra[0]
            elif con_palabra:
                raise ErrorIcono("Hay varios iconos en %s (%s): indica el archivo .svg."
                                 % (carpeta, ", ".join(f.name for f in con_palabra)))
    if not p.is_file():
        raise ErrorIcono("No encuentro el SVG maestro en %s." % p)
    return p


def orden_rasterizar(a):
    ruta = _resolver_svg(a.objetivo, a.prefijo)
    prefijo = ruta.stem
    carpeta = Path(a.destino) if a.destino else ruta.parent
    if not carpeta.is_dir():
        raise ErrorIcono("La carpeta de destino %s no existe." % carpeta)
    print("Regenerando los PNG desde %s" % ruta)
    _generar_derivados(ruta.read_text(encoding="utf-8"), carpeta, prefijo, _tamanos(a.tamanos), a.ico, a.simulacro)
    return 0


def orden_verificar(a):
    ruta = _resolver_svg(a.objetivo, a.prefijo)
    carpeta = ruta.parent
    prefijo = ruta.stem
    fallos = 0
    avisos = 0

    def ok(msg):
        print("  [ok]    " + msg)

    def mal(msg):
        nonlocal fallos
        fallos += 1
        print("  [MAL]   " + msg)

    def ojo(msg):
        nonlocal avisos
        avisos += 1
        print("  [aviso] " + msg)

    print("Verificando %s" % ruta)
    texto = ruta.read_text(encoding="utf-8", errors="replace")
    for com in re.findall(r"<!--(.*?)-->", texto, re.S):
        if "--" in com:
            mal("hay `--` dentro de un comentario: el SVG es inválido y el navegador no lo pinta.")
            break
    try:
        raiz = ET.fromstring(texto.encode("utf-8"))
        ok("%s es XML válido" % ruta.name)
    except ET.ParseError as e:
        mal("%s no es XML válido: %s" % (ruta.name, e))
        raiz = None
    if raiz is not None:
        if _sin_ns(raiz.tag) != "svg":
            mal("la raíz no es <svg>")
        if not raiz.get("viewBox"):
            mal("falta viewBox")
        elif _numeros(raiz.get("viewBox")) != [0.0, 0.0, float(LIENZO), float(LIENZO)]:
            ojo("viewBox distinto de 0 0 %d %d (la plantilla de la casa usa ése)" % (LIENZO, LIENZO))
        if "var(" in texto:
            mal("usa var(--…): un SVG cargado como icono no hereda las variables CSS")
        if re.search(r"<script|\son[a-z]+\s*=", texto, re.I):
            mal("contiene scripts o manejadores on*")
        if not raiz.get("aria-label"):
            ojo("falta aria-label con el nombre de la aplicación")
    svg_mtime = ruta.stat().st_mtime

    for n in _tamanos(a.tamanos):
        p = carpeta / nombre_png(prefijo, n)
        if not p.is_file():
            mal("falta %s" % p.name)
            continue
        try:
            w, h, pixel = leer_png(p)
        except (ErrorIcono, zlib.error, struct.error) as e:
            mal("%s ilegible: %s" % (p.name, e))
            continue
        detalle = "%-16s %4dx%-4d %9s" % (p.name, w, h, _kb(p))
        if (w, h) != (n, n):
            mal(detalle + "  mide %dx%d y debería medir %dx%d" % (w, h, n, n))
            continue
        if pixel is None:
            ojo(detalle + "  formato no comprobable (no es PNG de 8 bits sin entrelazar)")
            continue
        esquina = pixel(0, 0)[3]
        centro = pixel(n // 2, n // 2)[3]
        if esquina > 8 and not a.esquinas_opacas:
            mal(detalle + "  esquina OPACA (alfa %d): ¿es una captura de pantalla?" % esquina)
        elif centro < 250:
            mal(detalle + "  el centro no es opaco (alfa %d)" % centro)
        else:
            ok(detalle + "  esquina transparente, centro opaco")
        if p.stat().st_mtime + 1 < svg_mtime:
            ojo("%s es más antiguo que el SVG: regenera con  %s" % (p.name, _llamada("rasterizar %s" % ruta)))
        if os.path.getsize(p) > 300 * 1024:
            ojo("%s pesa más de 300 KB" % p.name)

    ico = carpeta / "favicon.ico"
    if ico.is_file():
        d = ico.read_bytes()
        if len(d) >= 6 and struct.unpack("<HHH", d[:6])[:2] == (0, 1):
            ok("favicon.ico con %d imágenes" % struct.unpack("<H", d[4:6])[0])
        else:
            mal("favicon.ico no tiene una cabecera ICO válida")

    if a.url:
        import urllib.request
        import urllib.error
        base = a.url.rstrip("/") + "/"
        for nombre in [ruta.name] + [nombre_png(prefijo, n) for n in (32, 16, 180)]:
            try:
                req = urllib.request.Request(base + nombre, method="HEAD")
                with urllib.request.urlopen(req, timeout=10) as r:
                    tipo = r.headers.get("Content-Type", "")
                    esperado = "image/svg+xml" if nombre.endswith(".svg") else "image/png"
                    (ok if esperado in tipo else mal)("%s → %s %s" % (base + nombre, r.status, tipo))
            except (urllib.error.URLError, OSError) as e:
                mal("%s → %s" % (base + nombre, e))

    print("\n%s: %d fallo(s), %d aviso(s)." % ("BIEN" if not fallos else "HAY QUE CORREGIR", fallos, avisos))
    print("Esto no sustituye mirarlo: revisa a 16 px que se distinga (orden vista-previa).")
    return 1 if fallos else 0


def _html_pagina(titulo, cuerpo):
    return """<!doctype html>
<html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>%s</title>
<style>
 body{margin:0;font:14px/1.5 system-ui,sans-serif;background:#e2e8f0;color:#0f172a}
 h1{font-size:18px;margin:16px} h2{font-size:14px;margin:0 0 8px}
 .panel{margin:16px;padding:16px;border-radius:12px;display:flex;flex-wrap:wrap;gap:24px;align-items:flex-end}
 .claro{background:#f8fafc}.oscuro{background:#0f172a;color:#e2e8f0}
 figure{margin:0;text-align:center} figcaption{font-size:11px;opacity:.7;margin-top:4px}
 .tarjeta{width:120px;height:120px;display:grid;place-items:center;background:#fff;border-radius:16px;box-shadow:0 1px 4px #0003}
 .circulo{border-radius:50%%;overflow:hidden;width:96px;height:96px}.circulo img{display:block}
 img{image-rendering:auto}
</style></head><body>
<h1>%s</h1>
%s
</body></html>
""" % (escape(titulo), escape(titulo), cuerpo)


def orden_vista_previa(a):
    ruta = _resolver_svg(a.objetivo, a.prefijo)
    carpeta = ruta.parent
    prefijo = ruta.stem
    uri_svg = ruta.resolve().as_uri()
    comparar = [_resolver_svg(c, a.prefijo) for c in (a.comparar or [])]
    bloques = []
    for clase, titulo in (("claro", "Fondo claro"), ("oscuro", "Fondo oscuro")):
        figs = []
        for n in (160, 64, 32, 16):
            figs.append('<figure><img src="%s" width="%d" height="%d" alt=""><figcaption>SVG %d px</figcaption></figure>'
                        % (uri_svg, n, n, n))
        for n in (32, 16):
            p = carpeta / nombre_png(prefijo, n)
            if p.is_file():
                figs.append('<figure><img src="%s" width="%d" height="%d" alt=""><figcaption>PNG %d px</figcaption></figure>'
                            % (p.resolve().as_uri(), n, n, n))
        for otro in comparar:
            figs.append('<figure><img src="%s" width="16" height="16" alt=""><figcaption>%s 16 px</figcaption></figure>'
                        % (otro.resolve().as_uri(), escape(otro.parent.name)))
        bloques.append('<section class="panel %s"><h2 style="width:100%%">%s</h2>%s</section>' % (clase, titulo, "".join(figs)))
    p192 = carpeta / nombre_png(prefijo, 192)
    img_t = (p192 if p192.is_file() else ruta).resolve().as_uri()
    bloques.append(
        '<section class="panel claro"><h2 style="width:100%%">Montado en una tarjeta</h2>'
        '<figure><div class="tarjeta"><img src="%s" width="72" height="72" alt=""></div><figcaption>tarjeta cuadrada</figcaption></figure>'
        '<figure><div class="tarjeta"><div class="circulo"><img src="%s" width="96" height="96" alt=""></div></div>'
        '<figcaption>tarjeta que recorta en círculo</figcaption></figure></section>' % (img_t, img_t))
    salida = Path(a.salida) if a.salida else Path(tempfile.gettempdir()) / ("%s-vista-previa.html" % prefijo)
    salida.write_text(_html_pagina("Vista previa · %s" % ruta, "\n".join(bloques)), encoding="utf-8")
    print("Vista previa: %s" % salida.resolve())
    print("Ábrela en el navegador. No se ha escrito nada dentro del proyecto%s."
          % ("" if not a.salida else " salvo ese archivo"))
    return 0


def orden_simbolos(a):
    if not a.muestrario:
        for k in SIMBOLOS:
            print("  " + k)
        print("\n%d símbolos (Lucide). Para verlos dibujados: %s"
              % (len(SIMBOLOS), _llamada("simbolos --muestrario")))
        return 0
    primario = normalizar_hex(a.primario)
    oscuro = normalizar_hex(a.oscuro)
    figs = []
    for k, frag in SIMBOLOS.items():
        svg = construir_svg(k, frag, primario, oscuro, nombre_simbolo=k)
        svg = svg.split("-->", 1)[1].strip()  # en línea, sin la declaración XML ni el comentario
        svg = svg.replace('id="marca"', 'id="m-%s"' % k).replace("url(#marca)", "url(#m-%s)" % k)
        figs.append('<figure>%s<figcaption>%s</figcaption></figure>' % (svg, escape(k)))
    salida = Path(a.muestrario if a.muestrario is not True else
                  os.path.join(tempfile.gettempdir(), "generate_icon-simbolos.html"))
    salida.write_text(_html_pagina("Símbolos de generate_icon.py",
                                   '<section class="panel claro">%s</section>' % "".join(figs)), encoding="utf-8")
    print("Muestrario: %s" % salida.resolve())
    return 0


# ===========================================================================
#  Instalación automática: reconocer el proyecto y engancharle el icono
# ---------------------------------------------------------------------------
#  Todo lo que se escribe pasa por una transacción: antes de tocar un archivo
#  que ya existe se guarda una copia en `.generate_icon/respaldos/`, y
#  `deshacer` deja el proyecto como estaba. Nada se escribe sin enseñar antes
#  el plan, salvo con --si.
# ===========================================================================

DIRS_IGNORADOS = {
    "node_modules", "vendor", "dist", "build", "out", "target", "bin", "obj", "storage",
    "cache", "tmp", "temp", "logs", "coverage", "__pycache__", "venv", "env", "site-packages",
    "bower_components", "jspm_packages", "Pods", "DerivedData",
}
CARPETA_ESTADO = ".generate_icon"
MARCA_INI = "generate_icon:inicio"
MARCA_FIN = "generate_icon:fin"

# Carpetas de imágenes habituales, por orden de preferencia, relativas a la
# carpeta pública del proyecto.
CARPETAS_IMG = ["img", "images", "imagenes", "imgs", "assets/img", "assets/images",
                "assets/imagenes", "static/img", "static/images", "assets", "static"]
CARPETAS_IMG_PHP = ["vistas/img", "views/img", "vista/img", "view/img", "app/views/img",
                    "public/img", "public/images"] + CARPETAS_IMG
CARPETAS_VISTA = {"vistas", "vista", "views", "view", "templates", "plantillas", "layouts",
                  "includes", "include", "inc", "partials", "parciales", "modulos", "template",
                  "plantilla", "theme", "themes", "tema"}

# Palabras que delatan de qué va una aplicación, y el símbolo que les toca.
PISTAS_SIMBOLO = [
    ("huella", ["mascota", "adopcion", "adoptar", "adopta", "animal", "perro", "gato", "canino", "felino",
                "veterinari", "refugio", "pets"]),
    ("corazon", ["donacion", "donativo", "donar", "voluntari", "caridad", "fundacion", "solidari", "beneficen"]),
    ("tijeras", ["corte", "cortar", "costura", "sastre", "sastreria", "patron", "tizado"]),
    ("prenda", ["prenda", "ropa", "textil", "moda", "uniforme", "confeccion", "tela"]),
    ("caja", ["inventario", "stock", "existencia", "producto", "articulo", "paquete", "empaque"]),
    ("almacen", ["almacen", "bodega", "deposito", "warehouse"]),
    ("camion", ["envio", "despacho", "logistica", "transporte", "flota", "entrega", "distribucion", "ruta"]),
    ("factura", ["factura", "facturacion", "cobro", "recibo", "cuenta por cobrar", "invoice"]),
    ("dinero", ["pago", "tesoreria", "finanza", "presupuesto", "banco", "nomina", "salario", "caja chica"]),
    ("carrito", ["compra", "tienda", "pedido", "carrito", "ecommerce", "venta", "shop", "orden de compra"]),
    ("grafico", ["reporte", "informe", "estadistica", "dashboard", "tablero", "indicador", "kpi", "metrica", "analitica"]),
    ("calendario", ["agenda", "cita", "calendario", "reserva", "turno", "horario", "evento", "vacacion"]),
    ("personas", ["cliente", "empleado", "personal", "rrhh", "recursos humanos", "talento", "socio", "miembro", "usuarios"]),
    ("auricular", ["soporte", "ayuda", "helpdesk", "ticket", "incidencia", "mesa de ayuda", "call center"]),
    ("correo", ["correo", "email", "mensaje", "notificacion", "boletin", "newsletter"]),
    ("herramienta", ["mantenimiento", "taller", "reparacion", "servicio tecnico", "orden de trabajo"]),
    ("fabrica", ["produccion", "planta", "fabrica", "manufactura", "industrial", "maquila"]),
    ("escudo", ["seguridad", "acceso", "permiso", "auditoria", "riesgo", "cumplimiento"]),
    ("documento", ["documento", "expediente", "contrato", "gestion documental", "solicitud", "formulario"]),
    ("base-datos", ["base de datos", "datos maestros", "as400", "catalogo", "maestro", "etl", "integracion"]),
    ("ubicacion", ["mapa", "ubicacion", "sucursal", "geolocaliza", "tienda fisica", "zona"]),
    ("etiqueta", ["etiqueta", "precio", "codigo de barra", "rotulo", "marbete"]),
    ("impresora", ["impresion", "imprimir", "printer"]),
    ("libro", ["manual", "biblioteca", "curso", "capacitacion", "wiki", "conocimiento"]),
    ("reloj", ["asistencia", "marcacion", "tiempo", "reloj", "horas extra"]),
    ("lupa", ["consulta", "busqueda", "buscador", "rastreo", "trazabilidad"]),
]


_PROPIO = Path(__file__).resolve()


def _llamada(orden=""):
    """Cómo escribir esta herramienta en la terminal, tal como se ha usado ahora.

    Portable (el .py copiado dentro del proyecto): `python3 ruta/generate_icon.py`.
    Instalada como comando o compilada: `generate_icon`.
    """
    if getattr(sys, "frozen", False) or _PROPIO.suffix.lower() != ".py":
        base = "generate_icon"
    else:
        try:
            ruta = os.path.relpath(str(_PROPIO), os.getcwd())
        except ValueError:  # otra unidad en Windows
            ruta = str(_PROPIO)
        if ruta.startswith(".." + os.sep + ".." + os.sep):
            ruta = str(_PROPIO)
        if " " in ruta:
            ruta = '"%s"' % ruta
        base = ("py " if os.name == "nt" else "python3 ") + ruta
    return (base + " " + orden).strip()


_MARCADORES_PROYECTO = (
    ".git", "composer.json", "package.json", "artisan", "manage.py", "pyproject.toml",
    "requirements.txt", "Gemfile", "pom.xml", "build.gradle", "build.gradle.kts", "go.mod",
    "angular.json", "wp-config.php", "index.php", "index.html", "index.htm",
)


def _parece_proyecto(d):
    try:
        if any((d / m).exists() for m in _MARCADORES_PROYECTO):
            return True
        return any(d.glob("*.csproj")) or any(d.glob("*.sln"))
    except OSError:
        return False


def raiz_del_proyecto(desde=None):
    """La carpeta del proyecto: la más cercana, subiendo desde `desde`, que lo parezca.

    Así da igual si se ejecuta desde la raíz, desde una subcarpeta o desde la
    carpeta donde se dejó el .py (p. ej. `herramientas/`).
    """
    inicio = Path(desde or os.getcwd()).resolve()
    casa = Path.home().resolve()
    d = inicio
    while True:
        if d == casa or d.parent == d:
            break
        if _parece_proyecto(d):
            return d
        d = d.parent
    raise ErrorIcono(
        "No encuentro ningún proyecto en %s ni en las carpetas de encima. Copia generate_icon.py "
        "dentro de la carpeta de tu proyecto y ejecútalo desde ahí." % inicio)


def _sin_tildes(texto):
    import unicodedata
    t = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in t if not unicodedata.combining(c)).lower()


def _texto(ruta, limite=2000000):
    try:
        if ruta.stat().st_size > limite:
            return ""
        return ruta.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _json(ruta):
    try:
        datos = json.loads(_texto(ruta) or "null")
        return datos if isinstance(datos, dict) else {}
    except ValueError:
        return {}


def _rel(base, ruta):
    return Path(os.path.relpath(str(ruta), str(base))).as_posix()



# Código ajeno que viene copiado dentro del proyecto: el núcleo de un framework
# (CodeIgniter trae system/, WordPress wp-includes/) y librerías de terceros. No
# dice nada del proyecto: sus colores, extensiones, bases de datos o comentarios
# son los de la librería, así que no se leen.
_RE_LIBRERIA = re.compile(
    r"^(third[_-]?party|thirdparty|bower_components|bootstrap[-_.]?\d.*|font-?awesome.*|fontawesome.*|"
    r"fpdf|tcpdf|mpdf|dompdf|phpqrcode|phpmailer|phpexcel|phpspreadsheet|sweet(alert)?\d*|pnotify|"
    r"chart(js)?|jquery[\w.-]*|datatables?[\w.-]*|select2[\w.-]*|toastr|animate|plugins|libs|"
    r"ckeditor\d*|tinymce|summernote|leaflet|swiper|owl[\w.-]*|slick|aos|fancybox|lightbox\d*|"
    r"wp-includes|wp-admin)$", re.I)
_RE_CSS_LIBRERIA = re.compile(
    r"^(bootstrap|font-?awesome|fontawesome|all|normalize|reset|animate|sweetalert2?|select2|datatables?|"
    r"toastr|pnotify|jquery[-.]ui|materialize|bulma|foundation|fontawesome-all|adminlte|mdb)"
    r"([-.][\w.-]*)?\.(css|scss|less)$", re.I)


def _es_de_terceros(carpeta, nombre):
    """¿La carpeta `nombre` dentro de `carpeta` es código ajeno copiado en el proyecto?"""
    if _RE_LIBRERIA.match(nombre) or re.match(r"^blueimp[\w-]*$", nombre, re.I):
        return True
    # js/lib, assets/lib, public/vendor…: donde se dejan las librerías de JavaScript
    if nombre.lower() in ("lib", "vendor", "vendors") and Path(carpeta).name.lower() in (
            "js", "javascript", "scripts", "assets", "static", "public", "dist"):
        return True
    # El núcleo de CodeIgniter 4 (system/CodeIgniter.php) o de CodeIgniter 3 (system/core/)
    if nombre == "system" and ((Path(carpeta) / nombre / "CodeIgniter.php").is_file()
                               or (Path(carpeta) / nombre / "core" / "CodeIgniter.php").is_file()):
        return True
    return False


def _archivos(raiz, extensiones, dentro=None, max_archivos=20000):
    """Recorre el proyecto saltándose dependencias, compilados y carpetas ocultas."""
    bases = [raiz / d for d in dentro] if dentro else [raiz]
    vistos = set()
    for base in bases:
        if not base.is_dir():
            continue
        for dp, dns, fns in os.walk(str(base)):
            dns[:] = sorted(d for d in dns if d not in DIRS_IGNORADOS and not d.startswith(".")
                                    and not _es_de_terceros(dp, d))
            for fn in sorted(fns):
                if fn.lower().endswith(extensiones):
                    ruta = Path(dp) / fn
                    if ruta in vistos or ruta.resolve() == _PROPIO:
                        continue
                    vistos.add(ruta)
                    if len(vistos) > max_archivos:
                        return
                    yield ruta


class Proyecto:
    """Lo que la herramienta entiende de un proyecto antes de tocarlo."""

    def __init__(self, raiz):
        self.raiz = raiz
        self.tipo = "estatico"
        self.descripcion = "Sitio HTML"
        self.publico = raiz          # la carpeta que el servidor publica
        self.destino = raiz          # dónde van el SVG y los PNG
        self.plantillas = []         # archivos con <head> donde van los <link>
        self.formato = "html"        # html | jsx
        self.convenciones = {}       # {ruta: 'svg' | 'ico' | tamaño}: archivos que el framework recoge solo
        self.notas = []
        self.django = False
        self.ico_en_destino = True   # False si el framework ya sirve /favicon.ico por su cuenta
        self._href = lambda plantilla, archivo: 'href="%s"' % _rel(plantilla.parent, self.destino / archivo)

    def href(self, plantilla, archivo):
        return self._href(plantilla, archivo)


def _con_head(raiz, dentro, extensiones, jsx=False):
    patron = re.compile(r"<Head\b[^/>]*>") if jsx else re.compile(r"<head\b[^>]*>", re.I)
    cierre = "</Head>" if jsx else "</head"
    salida = []
    for ruta in _archivos(raiz, extensiones, dentro):
        t = _texto(ruta, 1000000)
        if patron.search(t) and cierre in (t if jsx else t.lower()):
            salida.append(ruta)
    return salida


def _elegir_destino(p, base, candidatos):
    for c in candidatos:
        if (base / c).is_dir():
            p.destino = base / c
            return
    p.destino = base


def _deps_node(raiz):
    pkg = _json(raiz / "package.json")
    deps = set()
    for k in ("dependencies", "devDependencies", "peerDependencies"):
        deps |= set((pkg.get(k) or {}).keys())
    return deps


def _en_carpeta_vista(p, plantilla):
    partes = {x.lower() for x in plantilla.relative_to(p.raiz).parts[:-1]}
    return bool(partes & CARPETAS_VISTA)


def detectar_proyecto(raiz):
    raiz = Path(raiz).resolve()
    if not raiz.is_dir():
        raise ErrorIcono("La carpeta del proyecto %s no existe." % raiz)
    p = Proyecto(raiz)
    deps = _deps_node(raiz)
    composer = _json(raiz / "composer.json")
    creq = set((composer.get("require") or {}).keys()) | set((composer.get("require-dev") or {}).keys())
    py = " ".join(_texto(raiz / f) for f in ("requirements.txt", "pyproject.toml", "Pipfile", "setup.py")).strip().lower()
    csproj = list(raiz.glob("*.csproj")) + list(raiz.glob("*/*.csproj"))
    gemfile = _texto(raiz / "Gemfile")
    java = _texto(raiz / "pom.xml") + _texto(raiz / "build.gradle") + _texto(raiz / "build.gradle.kts")
    rel_pub = lambda f: _rel(p.publico, p.destino / f)  # noqa: E731

    if (raiz / "wp-config.php").exists() or (raiz / "wp-content").is_dir():
        p.tipo, p.descripcion = "wordpress", "WordPress"
        temas = [d for d in sorted((raiz / "wp-content" / "themes").glob("*")) if (d / "style.css").is_file()] \
            if (raiz / "wp-content" / "themes").is_dir() else []
        if (raiz / "wp-content" / "uploads").is_dir():
            p.destino = raiz / "wp-content" / "uploads"
        elif temas:
            # Dentro del tema, junto a sus imágenes si las tiene
            p.destino = next((temas[0] / d for d in ("img", "images", "assets/img", "assets/images")
                              if (temas[0] / d).is_dir()), temas[0])
        else:
            p.destino = raiz
        p.notas.append("WordPress pone el icono desde «Apariencia › Personalizar › Identidad del sitio»: "
                       "sube allí el PNG de 512 px del icono. No se edita ningún tema.")
    elif (raiz / "artisan").exists() or "laravel/framework" in creq:
        p.tipo, p.descripcion = "laravel", "Laravel (PHP)"
        p.publico = raiz / "public"
        _elegir_destino(p, p.publico, CARPETAS_IMG)
        p.plantillas = _con_head(raiz, ["resources/views"], (".blade.php",))
        p._href = lambda pl, f: "href=\"{{ asset('%s') }}\"" % rel_pub(f)
    elif (raiz / "bin" / "console").exists() or "symfony/framework-bundle" in creq:
        p.tipo, p.descripcion = "symfony", "Symfony (PHP)"
        p.publico = raiz / "public"
        _elegir_destino(p, p.publico, CARPETAS_IMG)
        p.plantillas = _con_head(raiz, ["templates"], (".twig",))
        p._href = lambda pl, f: "href=\"{{ asset('%s') }}\"" % rel_pub(f)
    elif (raiz / "spark").exists() or "codeigniter4/framework" in creq or (raiz / "system" / "CodeIgniter.php").exists():
        p.tipo, p.descripcion = "codeigniter", "CodeIgniter (PHP)"
        p.publico = raiz / "public" if (raiz / "public").is_dir() else raiz
        _elegir_destino(p, p.publico, CARPETAS_IMG)
        p.plantillas = _con_head(raiz, ["app/Views", "application/views"], (".php",))
        p._href = lambda pl, f: "href=\"<?= base_url('%s') ?>\"" % rel_pub(f)
    elif "next" in deps:
        p.tipo, p.descripcion = "next", "Next.js"
        p.publico = raiz / "public"
        _elegir_destino(p, p.publico, CARPETAS_IMG)
        app = next((d for d in (raiz / "app", raiz / "src" / "app") if d.is_dir()), None)
        if app is not None:
            p.descripcion += " (App Router)"
            p.convenciones = {app / "icon.svg": "svg", app / "apple-icon.png": 180, app / "favicon.ico": "ico"}
            # Un favicon.ico en public/ y otro en app/ es un conflicto de rutas en Next.js
            p.ico_en_destino = False
            for viejo in ("icon.png", "icon.ico", "icon.jpg", "apple-icon.jpg"):
                if (app / viejo).exists():
                    p.notas.append("%s también es un icono para Next.js y competirá con el nuevo: bórralo tú si sobra."
                                   % _rel(raiz, app / viejo))
            p.notas.append("Next.js añade los <link> solo a partir de icon.svg, apple-icon.png y favicon.ico.")
        else:
            p.descripcion += " (Pages Router)"
            p.formato = "jsx"
            docs = []
            for base in (raiz / "pages", raiz / "src" / "pages"):
                docs += [x for x in sorted(base.glob("_document.*")) if x.suffix in (".js", ".jsx", ".ts", ".tsx")]
            p.plantillas = [x for x in docs if re.search(r"<Head\b[^/>]*>", _texto(x))]
            p._href = lambda pl, f: 'href="/%s"' % rel_pub(f)
            if not p.plantillas:
                p.notas.append("No hay pages/_document con <Head>: añade los <link> en tu _document o _app.")
    elif "nuxt" in deps or "nuxt3" in deps:
        p.tipo, p.descripcion = "nuxt", "Nuxt"
        p.publico = raiz / "public"
        _elegir_destino(p, p.publico, CARPETAS_IMG)
        p.notas.append("Nuxt declara los <link> en nuxt.config (app.head.link); la herramienta no edita "
                       "archivos de configuración: copia allí las rutas que se indican abajo.")
    elif "@sveltejs/kit" in deps:
        p.tipo, p.descripcion = "sveltekit", "SvelteKit"
        p.publico = raiz / "static"
        _elegir_destino(p, p.publico, CARPETAS_IMG)
        p.plantillas = [x for x in [raiz / "src" / "app.html"] if x.exists()]
        p._href = lambda pl, f: 'href="%%sveltekit.assets%%/%s"' % rel_pub(f)
    elif "astro" in deps:
        p.tipo, p.descripcion = "astro", "Astro"
        p.publico = raiz / "public"
        _elegir_destino(p, p.publico, CARPETAS_IMG)
        p.plantillas = _con_head(raiz, ["src"], (".astro",))
        p._href = lambda pl, f: 'href="/%s"' % rel_pub(f)
    elif "@angular/core" in deps:
        p.tipo, p.descripcion = "angular", "Angular"
        if (raiz / "public").is_dir():
            p.publico = raiz / "public"
            _elegir_destino(p, p.publico, CARPETAS_IMG)
        else:
            p.publico = raiz / "src"
            _elegir_destino(p, p.publico, ["assets/img", "assets/images", "assets"])
        p.plantillas = [x for x in [raiz / "src" / "index.html"] if x.exists()]
        p._href = lambda pl, f: 'href="%s"' % rel_pub(f)
    elif "react-scripts" in deps:
        p.tipo, p.descripcion = "cra", "Create React App"
        p.publico = raiz / "public"
        _elegir_destino(p, p.publico, CARPETAS_IMG)
        p.plantillas = [x for x in [raiz / "public" / "index.html"] if x.exists()]
        p._href = lambda pl, f: 'href="%%PUBLIC_URL%%/%s"' % rel_pub(f)
    elif "vite" in deps or list(raiz.glob("vite.config.*")):
        p.tipo, p.descripcion = "vite", "Vite"
        p.publico = raiz / "public"
        _elegir_destino(p, p.publico, CARPETAS_IMG)
        p.plantillas = [x for x in sorted(raiz.glob("*.html")) if re.search(r"<head\b", _texto(x), re.I)]
        p._href = lambda pl, f: 'href="/%s"' % rel_pub(f)
    elif (raiz / "manage.py").exists() or "django" in py:
        p.tipo, p.descripcion, p.django = "django", "Django (Python)", True
        estaticos = [d for d in [raiz / "static"] if d.is_dir()] or \
            [Path(dp) for dp, dns, _f in _recorrer_dirs(raiz) if Path(dp).name == "static"]
        p.publico = estaticos[0] if estaticos else raiz / "static"
        _elegir_destino(p, p.publico, CARPETAS_IMG)
        p.plantillas = [x for x in _con_head(raiz, None, (".html",)) if "templates" in x.parts]
        p._href = lambda pl, f: "href=\"{%% static '%s' %%}\"" % rel_pub(f)
    elif "flask" in py or re.search(r"from\s+flask\s+import", _texto(raiz / "app.py") + _texto(raiz / "main.py")):
        p.tipo, p.descripcion = "flask", "Flask (Python)"
        estaticos = [Path(dp) for dp, dns, _f in _recorrer_dirs(raiz) if Path(dp).name == "static"]
        p.publico = estaticos[0] if estaticos else raiz / "static"
        _elegir_destino(p, p.publico, CARPETAS_IMG)
        p.plantillas = [x for x in _con_head(raiz, None, (".html", ".jinja", ".j2")) if "templates" in x.parts]
        p._href = lambda pl, f: "href=\"{{ url_for('static', filename='%s') }}\"" % rel_pub(f)
    elif csproj and any("Microsoft.NET.Sdk.Web" in _texto(c) or "Microsoft.NET.Sdk.BlazorWebAssembly" in _texto(c)
                        for c in csproj):
        base = csproj[0].parent
        p.tipo, p.descripcion = "aspnet", "ASP.NET Core (.NET)"
        p.publico = base / "wwwroot"
        _elegir_destino(p, p.publico, CARPETAS_IMG)
        p.plantillas = [x for x in _con_head(base, None, (".cshtml", ".razor", ".html"))
                        if "lib" not in x.relative_to(base).parts]
        p._href = lambda pl, f: ('href="~/%s"' if pl.suffix == ".cshtml" else 'href="%s"') % rel_pub(f)
    elif "rails" in gemfile:
        p.tipo, p.descripcion = "rails", "Ruby on Rails"
        p.publico = raiz / "public"
        _elegir_destino(p, p.publico, CARPETAS_IMG)
        p.plantillas = _con_head(raiz, ["app/views/layouts"], (".erb", ".haml", ".slim"))
        p.plantillas = [x for x in p.plantillas if x.suffix == ".erb"]
        p._href = lambda pl, f: 'href="/%s"' % rel_pub(f)
    elif "spring-boot" in java:
        p.tipo, p.descripcion = "spring", "Spring Boot (Java)"
        p.publico = raiz / "src" / "main" / "resources" / "static"
        _elegir_destino(p, p.publico, CARPETAS_IMG)
        p.plantillas = _con_head(raiz, ["src/main/resources/templates", "src/main/resources/static"], (".html",))
        p._href = lambda pl, f: ('th:href="@{/%s}"' if "xmlns:th" in _texto(pl) else 'href="/%s"') % rel_pub(f)
    elif (raiz / "pubspec.yaml").exists():
        flutter = "flutter" in _texto(raiz / "pubspec.yaml")
        p.tipo, p.descripcion = "flutter", "Flutter (Dart)" if flutter else "Dart"
        if (raiz / "web" / "index.html").exists():
            # La versión web de Flutter sí tiene una página con <head>
            p.publico = raiz / "web"
            p.destino = raiz / "web" / "icons" if (raiz / "web" / "icons").is_dir() else raiz / "web"
            p.plantillas = [raiz / "web" / "index.html"]
        else:
            p.publico = p.destino = raiz / "assets" / "icon"
        if flutter:
            p.notas.append("Para el icono de la app en Android e iOS, usa el paquete flutter_launcher_icons con "
                           "image_path con el PNG de 512 px del icono (en %s/) en pubspec.yaml y ejecuta: "
                           "dart run flutter_launcher_icons" % _rel(raiz, p.destino))
    elif (raiz / "go.mod").exists() or (raiz / "Cargo.toml").exists() or "fastapi" in py or (
            py and not _con_head(raiz, None, (".html", ".jinja", ".j2"))):
        # Servicios y APIs (Go, Rust, FastAPI…): sin páginas propias, el icono va a sus estáticos si los
        # tienen y, si no, a docs/img, para el README y la documentación.
        lenguaje = ("Go" if (raiz / "go.mod").exists() else "Rust" if (raiz / "Cargo.toml").exists()
                    else "FastAPI (Python)" if "fastapi" in py else "Python")
        p.tipo, p.descripcion = "servicio", lenguaje
        estaticos = [raiz / d for d in ("static", "public", "assets", "web/static", "app/static", "src/static")
                     if (raiz / d).is_dir()]
        if estaticos:
            p.publico = estaticos[0]
            _elegir_destino(p, p.publico, CARPETAS_IMG)
        else:
            p.publico = p.destino = raiz / "docs" / "img"
            p.notas.append("El proyecto no tiene carpeta de archivos estáticos: el icono queda en docs/img, para "
                           "el README y la documentación.")
        p.plantillas = _con_head(raiz, None, (".html", ".tmpl", ".gohtml", ".jinja", ".j2", ".tera", ".hbs"))
        if p.plantillas:
            p.notas.append("Las plantillas de %s se sirven con la ruta que les dé el código: revisa que los <link> "
                           "apunten a donde se publican los estáticos." % lenguaje)
            p._href = lambda pl, f: 'href="/%s"' % rel_pub(f)
    elif (raiz / "package.json").exists():
        p.tipo, p.descripcion = "node", "Node.js"
        p.publico = next((raiz / d for d in ("public", "static", "www", "assets") if (raiz / d).is_dir()), raiz)
        _elegir_destino(p, p.publico, CARPETAS_IMG)
        p.plantillas = _con_head(raiz, None, (".html", ".ejs", ".hbs", ".handlebars", ".njk", ".mustache"))
        if p.publico != raiz:
            p._href = lambda pl, f: 'href="/%s"' % rel_pub(f)
        elif not p.plantillas and p.destino == raiz:
            # Una API sin carpeta pública ni páginas: el icono, para el README y la documentación
            p.publico = p.destino = raiz / "docs" / "img"
            p.notas.append("El proyecto no tiene carpeta pública ni páginas: el icono queda en docs/img, para el "
                           "README y la documentación.")
    elif composer or next(_archivos(raiz, (".php",)), None) is not None:
        p.tipo, p.descripcion = "php", "PHP"
        p.publico = raiz / "public" if (raiz / "public" / "index.php").exists() else raiz
        _elegir_destino(p, p.publico, CARPETAS_IMG_PHP)
        p.plantillas = _con_head(raiz, None, (".php", ".html", ".htm", ".phtml", ".tpl"))

        def href_php(pl, f):
            # Una vista incluida desde index.php resuelve las rutas desde la raíz
            # pública; una página suelta, desde su propia carpeta. Siempre relativo:
            # muchas aplicaciones cuelgan de una subcarpeta del servidor.
            base = p.publico if _en_carpeta_vista(p, pl) else pl.parent
            return 'href="%s"' % _rel(base, p.destino / f)
        p._href = href_php
    elif java:
        p.tipo, p.descripcion = "java", "Java"
        p.publico = raiz / "src" / "main" / "resources" / "static" if (raiz / "src" / "main" / "resources").is_dir() \
            else raiz / "docs" / "img"
        _elegir_destino(p, p.publico, CARPETAS_IMG)
        p.plantillas = _con_head(raiz, ["src/main/resources", "src/main/webapp"], (".html", ".jsp"))
    else:
        p.plantillas = _con_head(raiz, None, (".html", ".htm"))
        if p.plantillas:
            _elegir_destino(p, raiz, CARPETAS_IMG)
        else:
            # Sin páginas web (un programa de escritorio, una librería…): para el README y la documentación
            p.tipo, p.descripcion = "otro", "Proyecto sin páginas web"
            p.publico = raiz
            _elegir_destino(p, raiz, CARPETAS_IMG + ["docs/img"])
            if p.destino == raiz:
                p.destino = raiz / "docs" / "img"
            p.notas.append("No hay páginas web donde poner el icono: queda en %s, para el README y la "
                           "documentación." % _rel(raiz, p.destino))

    # Una carpeta pública que aún no existe sólo se crea si el framework la
    # espera ahí (public/ de Vite o Next, static/ de Django…).
    if not p.destino.exists():
        p.notas.append("Se creará la carpeta %s/." % _rel(raiz, p.destino))
    return p


def _recorrer_dirs(raiz, profundidad=5):
    base = len(raiz.parts)
    for dp, dns, fns in os.walk(str(raiz)):
        dns[:] = sorted(d for d in dns if d not in DIRS_IGNORADOS and not d.startswith("."))
        if len(Path(dp).parts) - base >= profundidad:
            dns[:] = []
        yield dp, dns, fns


# --------------------------------------------------------------- nombre/colores
# Palabras de página, no de aplicación: «Inicio - PanitasPet» → PanitasPet
_PAGINAS_GENERICAS = {"inicio", "home", "login", "entrar", "acceso", "registro", "register", "dashboard",
                      "panel", "admin", "administracion", "perfil", "profile", "index", "principal",
                      "bienvenido", "bienvenida", "welcome", "error", "404", "contacto", "ayuda", "pagina"}


def nombre_de_titulos(textos):
    """El nombre de la aplicación a partir de los <title> de sus páginas.

    Los títulos suelen ser «Página - Aplicación | lema»: el nombre es la parte
    que se repite en más páginas. Devuelve (nombre, cuántas páginas lo llevan)
    o None. Ignora los títulos que son código de plantilla ({{ }}, <?php…).
    """
    import unicodedata
    titulos = []
    for t in textos:
        for m in re.finditer(r"<title[^>]*>([^<]{2,160})</title>", t, re.I):
            crudo = m.group(1).strip()
            # Fuera los de serie de frameworks y librerías («Welcome to CodeIgniter 4!», «Sweet alert2»)
            if (crudo and not re.search(r"[{}<>%$@\[\]]|\?>", crudo)
                    and not re.search(r"codeigniter|laravel|symfony|wordpress|welcome to|sweet ?alert|bootstrap|"
                                      r"jquery|datatables|lorem ipsum|example|ejemplo|demo|test", crudo, re.I)):
                titulos.append(crudo)
    if not titulos:
        return None

    def norma(s):
        s = unicodedata.normalize("NFKD", s)
        return "".join(c for c in s if not unicodedata.combining(c)).lower().strip()

    cuenta, forma, puesto = {}, {}, {}
    for t in titulos:
        partes = [x.strip() for x in re.split(r"\s+[-|–—·:»/]\s+|\s*\|\s*", t) if x.strip()]
        for i, parte in enumerate(dict.fromkeys(partes)):
            k = norma(parte)
            if k in _PAGINAS_GENERICAS or len(k) < 2:
                continue
            cuenta[k] = cuenta.get(k, 0) + 1
            forma.setdefault(k, parte)
            puesto[k] = min(puesto.get(k, i), i)
    if not cuenta:
        return None
    # La que más se repite; a igualdad, la que va antes en el título (el nombre, no el lema)
    k = sorted(cuenta, key=lambda x: (-cuenta[x], puesto[x], len(x)))[0]
    # Con varias páginas, el nombre de la aplicación tiene que estar en la mitad al menos: si
    # cada página tiene su propio título («Registro», «Tarjeta de coordenadas»…), ninguno lo es.
    if len(titulos) >= 3 and cuenta[k] < max(2, (len(titulos) + 1) // 2):
        return None
    return forma[k], cuenta[k]


# Los nombres que trae de serie la plantilla de un framework no son el de la aplicación
_NOMBRES_DE_SERIE = {"laravel/laravel", "symfony/skeleton", "symfony/website-skeleton", "codeigniter4/appstarter",
                     "codeigniter4/framework", "codeigniter/framework", "cakephp/app", "slim/slim-skeleton",
                     "my-app", "my-project", "vite-project", "react-app", "vue-project", "nuxt-app", "next-app",
                     "app", "project", "web", "frontend", "laravel", "framework", "appstarter"}


def detectar_nombre(p):
    """(nombre, de dónde salió)."""
    raiz = p.raiz
    for f in ("config/app.php", "config/config.php", "app/Config/App.php"):
        m = re.search(r"['\"](?:nombre|name|app_name|appName)['\"]\s*=>\s*['\"]([^'\"]{2,80})['\"]", _texto(raiz / f))
        if m and "env(" not in m.group(0):
            return m.group(1).strip(), f
    env = _texto(raiz / ".env.example") + _texto(raiz / ".env")
    m = re.search(r"^APP_NAME\s*=\s*\"?([^\"\n]{2,80})\"?", env, re.M)
    if m and m.group(1).strip() not in ("Laravel", "Symfony", "App"):
        return m.group(1).strip(), ".env"
    pkg = _json(raiz / "package.json")
    for k in ("productName", "displayName"):
        if isinstance(pkg.get(k), str) and pkg[k].strip():
            return pkg[k].strip(), "package.json"
    hallado = nombre_de_titulos(_texto(pl, 400000) for pl in p.plantillas)
    if hallado:
        return hallado[0], "los títulos de las páginas"
    m = re.search(r"^\s*name\s*=\s*[\"']([^\"']+)[\"']", _texto(raiz / "pyproject.toml"), re.M)
    crudo = None
    if m:
        crudo, origen = m.group(1), "pyproject.toml"
    elif isinstance(pkg.get("name"), str) and pkg["name"].lower() not in _NOMBRES_DE_SERIE:
        crudo, origen = pkg["name"].split("/")[-1], "package.json"
    elif list(raiz.glob("*.csproj")) + list(raiz.glob("*/*.csproj")):
        crudo, origen = (list(raiz.glob("*.csproj")) + list(raiz.glob("*/*.csproj")))[0].stem, "archivo .csproj"
    elif (isinstance(_json(raiz / "composer.json").get("name"), str)
          and _json(raiz / "composer.json")["name"].lower() not in _NOMBRES_DE_SERIE):
        crudo, origen = _json(raiz / "composer.json")["name"].split("/")[-1], "composer.json"
    else:
        # Otros lenguajes: lo que diga su archivo de proyecto
        for f in _archivos(raiz, (".py",), max_archivos=300):
            m = re.search(r"FastAPI\([^)]*title\s*=\s*[\"']([^\"']+)", _texto(f, 200000))
            if m:
                return m.group(1).strip(), "%s (FastAPI title)" % _rel(raiz, f)
        temas = sorted(raiz.glob("wp-content/themes/*/style.css"))
        for f in temas[:5]:
            m = re.search(r"Theme Name:\s*(.+)", _texto(f, 20000))
            if m:
                return m.group(1).strip(), _rel(raiz, f)
        for archivo, patron in (("pubspec.yaml", r"(?m)^name:\s*['\"]?([\w.-]+)"),
                                ("Cargo.toml", r"(?ms)^\[package\].*?^name\s*=\s*\"([^\"]+)\""),
                                ("pom.xml", r"</parent>.*?<name>([^<]+)</name>|^(?:(?!<parent>).)*?<name>([^<]+)</name>"),
                                ("go.mod", r"(?m)^module\s+\S*?([\w.-]+)\s*$"),
                                ("style.css", r"Theme Name:\s*(.+)")):
            m = re.search(patron, _texto(raiz / archivo), re.S if archivo == "pom.xml" else 0)
            if m:
                crudo, origen = next(g for g in m.groups() if g).strip(), archivo
                break
        else:
            # El nombre de la carpeta no es una fuente fiable: no se propone, se pregunta
            return "", ""
    if crudo.lower() in _NOMBRES_DE_SERIE:
        return "", ""
    bonito = re.sub(r"[-_.]+", " ", crudo).strip()
    return (bonito[:1].upper() + bonito[1:]) if bonito else "", origen


# ===========================================================================
#  Colores del proyecto: detección y ventana para elegirlos
# ---------------------------------------------------------------------------
#  Este bloque es idéntico en generate_icon.py y generate_readme.py: cada
#  herramienta es un solo archivo, así que se copia en vez de importarse.
#
#  Los colores salen del proyecto, por orden de fiabilidad: el DESIGN-SYSTEM.md,
#  la configuración de Tailwind, las variables de CSS/SCSS/LESS, los temas de
#  MUI/Vuetify/Chakra y el theme-color. Si no hay nombres reconocibles, los
#  que más usan sus hojas de estilo. Si no hay ninguno, se preguntan.
#
#  La «ventana» es una página que se abre en el navegador del equipo, servida
#  desde aquí mismo (127.0.0.1, sin internet): funciona en cualquier sistema,
#  también donde Python no trae tkinter.
# ===========================================================================

_TOK_PRIMARIO = ["primary", "color-primary", "primary-color", "primary-500", "primary-600", "color-primary-500",
                 "color-primary-600", "brand", "brand-primary", "color-brand", "brand-color", "brand-500", "brand-600",
                 "color-brand-500", "color-brand-600", "accent", "accent-color", "color-accent", "main-color",
                 "theme-primary", "app-primary", "bs-primary", "mdc-theme-primary", "ion-color-primary",
                 "primario", "color-primario", "principal", "color-principal"]
_TOK_OSCURO = ["navy", "primary-dark", "brand-dark", "dark", "color-dark", "dark-color", "primary-900",
               "primary-950", "brand-900", "brand-950", "color-primary-900", "color-brand-900", "secondary",
               "text-primary", "ink", "foreground", "bs-dark", "oscuro", "color-oscuro", "slate-900", "gray-900",
               "zinc-900", "neutral-900"]

# Si el proyecto no tiene ningún color, la ventana ofrece estos (sólo como punto de partida)
_SUGERENCIAS = [("#0369a1", "azul"), ("#4f46e5", "índigo"), ("#7c3aed", "violeta"), ("#be123c", "carmesí"),
                ("#c2410c", "naranja"), ("#b45309", "ámbar"), ("#15803d", "verde"), ("#0f766e", "turquesa"),
                ("#0f172a", "pizarra oscuro"), ("#1e1b4b", "índigo oscuro"), ("#052e16", "verde oscuro"),
                ("#1c1917", "piedra oscuro")]


def _a_hex(valor):
    """Un color CSS (hex, rgb, hsl, oklch o el «H S% L%» de shadcn) en #rrggbb. None si no lo es."""
    import colorsys
    v = (valor or "").strip().strip("'\"").lower()
    m = re.match(r"^#([0-9a-f]{3}|[0-9a-f]{6})(?:[0-9a-f]{1,2})?$", v)
    if m:
        h = m.group(1)
        return "#" + ("".join(c * 2 for c in h) if len(h) == 3 else h)
    m = re.match(r"^rgba?\(\s*([\d.]+)(%?)[\s,]+([\d.]+)(%?)[\s,]+([\d.]+)(%?)", v)
    if m:
        canales = []
        for i in (1, 3, 5):
            x = float(m.group(i)) * (2.55 if m.group(i + 1) else 1)
            canales.append(max(0, min(255, int(round(x)))))
        return "#%02x%02x%02x" % tuple(canales)
    m = re.match(r"^(?:hsla?\()?\s*([\d.]+)(?:deg)?[\s,]+([\d.]+)%[\s,]+([\d.]+)%\s*(?:[/,].*)?\)?$", v)
    if m:
        r, g, b = colorsys.hls_to_rgb(float(m.group(1)) % 360 / 360, float(m.group(3)) / 100, float(m.group(2)) / 100)
        return "#%02x%02x%02x" % tuple(int(round(max(0, min(1, x)) * 255)) for x in (r, g, b))
    m = re.match(r"^oklch\(\s*([\d.]+)(%?)\s+([\d.]+)\s+([\d.]+)", v)
    if m:
        import math as _m
        L = float(m.group(1)) / (100 if m.group(2) else 1)
        C, H = float(m.group(3)), _m.radians(float(m.group(4)))
        a, b = C * _m.cos(H), C * _m.sin(H)
        l_ = (L + 0.3963377774 * a + 0.2158037573 * b) ** 3
        m_ = (L - 0.1055613458 * a - 0.0638541728 * b) ** 3
        s_ = (L - 0.0894841775 * a - 1.2914855480 * b) ** 3
        lin = (4.0767416621 * l_ - 3.3077115913 * m_ + 0.2309699292 * s_,
               -1.2684380046 * l_ + 2.6097574011 * m_ - 0.3413193965 * s_,
               -0.0041960863 * l_ - 0.7034186147 * m_ + 1.7076147010 * s_)

        def gamma(c):
            c = max(0.0, min(1.0, c))
            return 12.92 * c if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055
        return "#%02x%02x%02x" % tuple(int(round(gamma(c) * 255)) for c in lin)
    return None


def _rgb01(h):
    return [int(h[i:i + 2], 16) / 255.0 for i in (1, 3, 5)]


def _luz(h):
    r, g, b = _rgb01(h)
    return (max(r, g, b) + min(r, g, b)) / 2


def _saturacion(h):
    r, g, b = _rgb01(h)
    mx, mn = max(r, g, b), min(r, g, b)
    l = (mx + mn) / 2
    return 0.0 if mx == mn else (mx - mn) / (1 - abs(2 * l - 1))


def _mezcla_hex(a, b, f):
    a, b = _rgb01(a), _rgb01(b)
    return "#%02x%02x%02x" % tuple(int(round((x + (y - x) * f) * 255)) for x, y in zip(a, b))


def paleta_del_proyecto(raiz, extras=()):
    """Los colores del proyecto.

    Devuelve {"primario": (hex, token, archivo) | None, "oscuro": igual,
    "candidatos": [{"hex", "nombre", "fuente"}], "supuesto": bool}. `extras` son
    tuplas (prioridad, token, valor, ruta) que añade cada herramienta (p. ej. el
    color `tema` de su configuración).
    """
    raiz = Path(raiz)
    fuentes = []   # (prioridad, token, valor crudo, archivo relativo)

    def anotar(prio, token, valor, f):
        fuentes.append((prio, token.lower().strip("-$@"), str(valor).strip(), _rel(raiz, f)))

    for f in [raiz / x for x in (".claude/agents/DESIGN-SYSTEM.md", "DESIGN-SYSTEM.md", "docs/DESIGN-SYSTEM.md",
                                 "design-system.md", "docs/design-system.md")]:
        if f.is_file():
            for m in re.finditer(r"--([A-Za-z0-9_-]+)\s*:\s*([^;}\n]+)", _texto(f)):
                anotar(0, m.group(1), m.group(2), f)
            for m in re.finditer(r"\|\s*`-{0,2}([A-Za-z0-9_-]+)`\s*\|\s*`(#[0-9A-Fa-f]{3,8})`", _texto(f)):
                anotar(0, m.group(1), m.group(2), f)
    for f in sorted(raiz.glob("tailwind.config.*")):
        t = _texto(f)
        for m in re.finditer(r"['\"]?([A-Za-z][\w-]*)['\"]?\s*:\s*(['\"][^'\"]+['\"]|\{[^{}]*\})", t):
            nombre, cuerpo = m.group(1), m.group(2)
            if cuerpo.startswith("{"):
                for k in ("DEFAULT", "600", "500", "700"):
                    mm = re.search(r"['\"]?%s['\"]?\s*:\s*['\"]([^'\"]+)['\"]" % k, cuerpo)
                    if mm:
                        anotar(1, nombre, mm.group(1), f)
                        break
                for k in ("900", "950", "800"):
                    mm = re.search(r"['\"]?%s['\"]?\s*:\s*['\"]([^'\"]+)['\"]" % k, cuerpo)
                    if mm:
                        anotar(1, nombre + "-" + k, mm.group(1), f)
                        break
            else:
                anotar(1, nombre, cuerpo.strip("'\""), f)
    # Sin las hojas de las librerías: el --primary de bootstrap.css es el azul de Bootstrap, no el del proyecto
    hojas = [f for f in _archivos(raiz, (".css", ".scss", ".sass", ".less", ".vue", ".svelte"), max_archivos=600)
             if not f.name.endswith(".min.css") and not _RE_CSS_LIBRERIA.match(f.name)]
    for f in hojas:
        t = _texto(f, 1500000)
        crudo = {}
        for m in re.finditer(r"--([A-Za-z0-9_-]+)\s*:\s*([^;}\n]+)", t):
            crudo.setdefault(m.group(1), m.group(2))
        for k, v in crudo.items():
            for _ in range(5):   # var(--otra) se resuelve dentro del mismo archivo
                mm = re.match(r"\s*var\(\s*--([A-Za-z0-9_-]+)\s*(?:,\s*([^)]+))?\)", v)
                if not mm:
                    break
                v = crudo.get(mm.group(1)) or mm.group(2) or ""
            anotar(2, k, v, f)
        for m in re.finditer(r"(?m)^\s*[$@]([A-Za-z][\w-]*)\s*:\s*([^;!\n]+)", t):
            anotar(2, m.group(1), m.group(2), f)
    for f in _archivos(raiz, (".js", ".ts", ".jsx", ".tsx", ".mjs"), max_archivos=1500):
        t = _texto(f, 600000)
        if not re.search(r"createTheme|createVuetify|extendTheme|palette|themes\s*:", t):
            continue
        for nombre in ("primary", "secondary", "dark"):
            mm = re.search(r"\b%s\s*:\s*\{?\s*(?:main\s*:\s*|base\s*:\s*)?['\"]([^'\"]+)['\"]" % nombre, t)
            if mm:
                anotar(3, nombre, mm.group(1), f)
    for f in list(_archivos(raiz, (".html", ".php", ".twig", ".erb", ".cshtml"), max_archivos=800)) + \
            [x for x in (raiz / "manifest.json", raiz / "public" / "manifest.json",
                         raiz / "site.webmanifest", raiz / "public" / "site.webmanifest") if x.is_file()]:
        t = _texto(f, 400000)
        mm = (re.search(r"<meta[^>]+name=['\"]theme-color['\"][^>]+content=['\"]([^'\"<{]+)['\"]", t, re.I)
              or re.search(r"\"theme_color\"\s*:\s*\"([^\"]+)\"", t))
        if mm:
            anotar(4, "theme-color", mm.group(1), f)
    for prio, token, valor, ruta in extras:
        anotar(prio, token, valor, ruta)

    def elegir(nombres, filtro):
        for prio in range(5):
            for n in nombres:
                for pr, token, valor, f in fuentes:
                    if pr == prio and token == n:
                        h = _a_hex(valor)
                        if h and filtro(h):
                            return (h, token, f)
        return None

    primario = elegir(_TOK_PRIMARIO, lambda h: _luz(h) < 0.9)
    oscuro = elegir(_TOK_OSCURO, lambda h: _luz(h) < 0.35) or elegir(["theme-color"], lambda h: _luz(h) < 0.35)

    cuenta = {}
    for f in hojas:
        for mm in re.finditer(r"#[0-9A-Fa-f]{6}\b|#[0-9A-Fa-f]{3}\b|rgba?\([^)]*\)|hsla?\([^)]*\)|oklch\([^)]*\)",
                              _texto(f, 1500000)):
            h = _a_hex(mm.group(0))
            if h:
                cuenta[h] = cuenta.get(h, 0) + 1
    frecuentes = sorted(cuenta.items(), key=lambda kv: -kv[1])
    if not primario:
        for h, n in frecuentes:
            if _saturacion(h) >= 0.3 and 0.2 <= _luz(h) <= 0.72:
                primario = (h, "", "el color con más presencia en las hojas de estilo (%d uso%s)" % (n, "" if n == 1 else "s"))
                break
    if not oscuro:
        for h, n in frecuentes:
            if _luz(h) < 0.22 and h != "#000000":
                oscuro = (h, "", "el color oscuro con más presencia en las hojas de estilo (%d uso%s)" % (n, "" if n == 1 else "s"))
                break
    if primario and not oscuro:
        oscuro = (_mezcla_hex(primario[0], "#0b1220", 0.72), "", "derivado del principal (no hay un oscuro propio)")
    if oscuro and not primario:
        primario = (_mezcla_hex(oscuro[0], "#ffffff", 0.35), "", "derivado del oscuro (no hay un principal propio)")

    # Todos los colores del proyecto, para ofrecerlos en la ventana: primero los
    # que tienen nombre, después los más usados. Sin blancos ni casi blancos.
    candidatos, vistos = [], set()

    def ofrecer(h, nombre, fuente):
        if h and h not in vistos and _luz(h) < 0.93 and len(candidatos) < 30:
            vistos.add(h)
            candidatos.append({"hex": h, "nombre": nombre, "fuente": fuente})

    for c in (primario, oscuro):
        if c:
            ofrecer(c[0], c[1], c[2])
    for pr, token, valor, f in sorted(fuentes, key=lambda x: x[0]):
        ofrecer(_a_hex(valor), token, f)
    for h, n in frecuentes:
        ofrecer(h, "", "%d uso%s en las hojas de estilo" % (n, "" if n == 1 else "s"))
    supuesto = not primario
    if supuesto:
        for h, nombre in _SUGERENCIAS:
            ofrecer(h, nombre, "sugerencia (el proyecto no tiene colores)")
    return {"primario": primario, "oscuro": oscuro, "candidatos": candidatos, "supuesto": supuesto}


_PAGINA_COLORES = r"""<!doctype html>
<html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Elige los colores</title>
<style>
  :root { --fondo:#f1f5f9; --tarjeta:#fff; --texto:#0f172a; --suave:#64748b; --borde:#e2e8f0; }
  @media (prefers-color-scheme: dark) { :root { --fondo:#0b1220; --tarjeta:#111a2e; --texto:#e2e8f0; --suave:#94a3b8; --borde:#1e293b; } }
  * { box-sizing:border-box } body { margin:0; font:15px/1.5 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif; background:var(--fondo); color:var(--texto) }
  main { max-width:980px; margin:0 auto; padding:28px 16px 48px }
  h1 { font-size:22px; margin:0 0 4px } p.sub { margin:0 0 20px; color:var(--suave) }
  .vista { background:var(--tarjeta); border:1px solid var(--borde); border-radius:16px; padding:20px; display:flex; gap:24px; align-items:center; flex-wrap:wrap; margin-bottom:20px }
  #vista { display:flex; gap:16px; flex-wrap:wrap; align-items:stretch; width:100% }
  .vista .fondo { border-radius:12px; padding:16px; display:flex; gap:14px; align-items:flex-end }
  .vista .claro { background:#f8fafc } .vista .oscuro { background:#0f172a }
  .cols { display:grid; grid-template-columns:1fr 1fr; gap:20px } @media (max-width:720px){ .cols { grid-template-columns:1fr } }
  .col { background:var(--tarjeta); border:1px solid var(--borde); border-radius:16px; padding:18px }
  .col h2 { font-size:16px; margin:0 } .col p { margin:2px 0 14px; color:var(--suave); font-size:13px }
  .muestras { display:grid; grid-template-columns:repeat(auto-fill,minmax(92px,1fr)); gap:10px }
  .m { border:2px solid transparent; border-radius:12px; padding:6px; background:none; color:inherit; cursor:pointer; text-align:left; font:inherit }
  .m:hover { border-color:var(--borde) } .m[aria-pressed=true] { border-color:var(--texto) }
  .m:focus-visible { outline:3px solid #38bdf8; outline-offset:2px }
  .m i { display:block; height:44px; border-radius:8px; box-shadow:inset 0 0 0 1px rgba(0,0,0,.12) }
  .m b { display:block; font:600 12px ui-monospace,Menlo,Consolas,monospace; margin-top:5px }
  .m small { display:block; font-size:11px; color:var(--suave); overflow:hidden; text-overflow:ellipsis; white-space:nowrap }
  .otro { display:flex; gap:10px; align-items:center; margin-top:14px; font-size:14px; flex-wrap:wrap }
  .otro input[type=color] { width:48px; height:36px; border:1px solid var(--borde); border-radius:8px; padding:2px; background:none }
  .otro input[type=text] { width:110px; padding:7px 9px; border:1px solid var(--borde); border-radius:8px; background:var(--fondo); color:inherit; font:13px ui-monospace,Menlo,Consolas,monospace }
  .acciones { display:flex; gap:12px; justify-content:flex-end; margin-top:22px; flex-wrap:wrap }
  button.b { font:600 15px system-ui,sans-serif; border-radius:10px; padding:11px 20px; cursor:pointer; border:1px solid var(--borde) }
  button.ok { background:#0f172a; color:#fff; border-color:#0f172a } @media (prefers-color-scheme: dark) { button.ok { background:#e2e8f0; color:#0f172a } }
  button.no { background:none; color:inherit }
  .aviso { width:100%; margin:0; padding:10px 14px; border-radius:10px; background:#fef3c7; color:#78350f; font-size:14px }
  .hecho { text-align:center; padding:80px 16px } .hecho h1 { font-size:26px }
</style></head><body><main id="app">
<h1>__TITULO__</h1>
<p class="sub">Elige el color <b>principal</b> y el <b>oscuro</b>. Son los colores de tu proyecto; si ninguno te sirve, usa «Otro color».</p>
<section class="vista" aria-label="Vista previa"><div id="vista"></div>
  <p class="aviso" id="aviso" role="status" hidden></p></section>
<div class="cols">
  <section class="col"><h2>Color principal</h2><p>__AYUDA_P__</p><div class="muestras" id="m-p"></div>
    <label class="otro">Otro color: <input type="color" id="c-p"> <input type="text" id="t-p" aria-label="Principal en hexadecimal"></label></section>
  <section class="col"><h2>Color oscuro</h2><p>__AYUDA_O__</p><div class="muestras" id="m-o"></div>
    <label class="otro">Otro color: <input type="color" id="c-o"> <input type="text" id="t-o" aria-label="Oscuro en hexadecimal"></label></section>
</div>
<div class="acciones"><button class="b no" id="cancelar">Cancelar</button><button class="b ok" id="usar">Usar estos colores</button></div>
</main>
<script>
const DATOS = __DATOS__;
const sel = { p: DATOS.primario, o: DATOS.oscuro };
const luz = h => { const [r,g,b] = [1,3,5].map(i => parseInt(h.substr(i,2),16)/255); return (Math.max(r,g,b)+Math.min(r,g,b))/2; };
function pintar() {
  document.getElementById('vista').innerHTML = DATOS.vista.split('__P__').join(sel.p).split('__O__').join(sel.o);
  for (const k of ['p','o']) {
    document.getElementById('c-'+k).value = sel[k];
    const t = document.getElementById('t-'+k); if (document.activeElement !== t) t.value = sel[k];
    for (const b of document.querySelectorAll('#m-'+k+' .m')) b.setAttribute('aria-pressed', b.dataset.hex === sel[k]);
  }
  const av = [];
  if (luz(sel.o) > 0.45) av.push('El color oscuro (' + sel.o + ') es claro: el símbolo y el texto van en blanco y no se verían.');
  if (luz(sel.p) > 0.8) av.push('El color principal (' + sel.p + ') es casi blanco: el símbolo blanco no se vería.');
  const a = document.getElementById('aviso'); a.hidden = !av.length; a.textContent = '⚠ ' + av.join(' ');
}
for (const k of ['p','o']) {
  const lista = DATOS.candidatos.slice().sort((a,b) => k === 'o' ? luz(a.hex) - luz(b.hex) : 0);
  const cont = document.getElementById('m-'+k);
  for (const c of lista) {
    const b = document.createElement('button'); b.type = 'button'; b.className = 'm'; b.dataset.hex = c.hex;
    b.title = c.hex + (c.nombre ? ' · ' + c.nombre : '') + ' · ' + c.fuente;
    b.innerHTML = '<i></i><b></b><small></small>';
    b.querySelector('i').style.background = c.hex; b.querySelector('b').textContent = c.hex;
    b.querySelector('small').textContent = c.nombre || c.fuente.replace(/ en las hojas de estilo$/, '');
    b.onclick = () => { sel[k] = c.hex; pintar(); };
    cont.appendChild(b);
  }
  document.getElementById('c-'+k).oninput = e => { sel[k] = e.target.value; pintar(); };
  document.getElementById('t-'+k).oninput = e => { let v = e.target.value.trim(); if (!v.startsWith('#')) v = '#' + v;
    if (/^#[0-9a-fA-F]{6}$/.test(v)) { sel[k] = v.toLowerCase(); pintar(); } };
}
async function enviar(datos, texto) {
  try { await fetch('elegir', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(datos) }); }
  catch (e) { alert('No se pudo avisar a la terminal: ' + e); return; }
  document.getElementById('app').innerHTML = '<div class="hecho"><h1>' + texto + '</h1><p class="sub">Vuelve a la terminal. Ya puedes cerrar esta pestaña.</p></div>';
  setTimeout(() => window.close(), 600);
}
document.getElementById('usar').onclick = () => enviar({ primario: sel.p, oscuro: sel.o }, 'Colores elegidos');
document.getElementById('cancelar').onclick = () => enviar({ cancelar: true }, 'Cancelado');
pintar();
</script></body></html>"""


def elegir_colores_en_ventana(titulo, candidatos, primario, oscuro, vista, ayuda_p="", ayuda_o="", espera=900):
    """Abre la página de elegir colores en el navegador y espera la respuesta.

    `vista` es el HTML/SVG de la vista previa con __P__ y __O__ donde van los
    colores. Devuelve (principal, oscuro), o None si se canceló o no se pudo.
    """
    import http.server
    import secrets
    import threading
    import webbrowser
    resultado = {}
    listo = threading.Event()
    clave = secrets.token_urlsafe(12)
    datos = json.dumps({"primario": primario, "oscuro": oscuro, "candidatos": candidatos, "vista": vista})
    pagina = (_PAGINA_COLORES.replace("__TITULO__", _escapar_html(titulo))
              .replace("__AYUDA_P__", _escapar_html(ayuda_p)).replace("__AYUDA_O__", _escapar_html(ayuda_o))
              .replace("__DATOS__", datos.replace("</", "<\\/"))).encode("utf-8")

    class Manejador(http.server.BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _responder(self, codigo, cuerpo, tipo):
            self.send_response(codigo)
            self.send_header("Content-Type", tipo)
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(cuerpo)

        def do_GET(self):
            if self.path.split("?")[0] in ("/%s/" % clave, "/%s" % clave):
                self._responder(200, pagina, "text/html; charset=utf-8")
            else:
                self._responder(404, b"", "text/plain")

        def do_POST(self):
            if self.path != "/%s/elegir" % clave:
                return self._responder(404, b"", "text/plain")
            try:
                d = json.loads(self.rfile.read(int(self.headers.get("Content-Length", "0") or 0)) or b"{}")
            except ValueError:
                return self._responder(400, b"", "text/plain")
            if not d.get("cancelar"):
                p, o = _a_hex(d.get("primario", "")), _a_hex(d.get("oscuro", ""))
                if not (p and o):
                    return self._responder(400, b"", "text/plain")
                resultado["colores"] = (p, o)
            self._responder(200, b'{"ok":true}', "application/json")
            listo.set()

    try:
        servidor = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Manejador)
    except OSError:
        return None
    hilo = threading.Thread(target=servidor.serve_forever, daemon=True)
    hilo.start()
    url = "http://127.0.0.1:%d/%s/" % (servidor.server_address[1], clave)
    try:
        abierta = webbrowser.open(url)
    except Exception:
        abierta = False
    print("\n  Se ha abierto una ventana del navegador para elegir los colores.")
    print("  Si no la ves, abre esta dirección:  %s" % url)
    if not abierta:
        print("  (No pude abrir el navegador yo solo: copia la dirección en él.)")
    print("  O pulsa Ctrl+C para escribirlos aquí.")
    try:
        limite = time.time() + espera
        while not listo.is_set() and time.time() < limite:
            listo.wait(0.5)
    except KeyboardInterrupt:
        print()
        return None
    finally:
        servidor.shutdown()
        servidor.server_close()
    if not listo.is_set():
        print("  No llegó ninguna respuesta de la ventana.")
        return None
    return resultado.get("colores")


def _escapar_html(t):
    return (str(t).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;"))


def _pedir_color_texto(texto, defecto=None):
    while True:
        v = _preguntar(texto, defecto)
        h = _a_hex(v or "")
        if h:
            return h
        print("  No lo entiendo como color. Escríbelo como #7c3aed (también valen rgb(), hsl() u oklch()).")


# Colores que traen de serie las librerías: si salen, casi seguro no son los de la marca
_COLORES_DE_SERIE = {"#007bff": "el azul de serie de Bootstrap 4", "#0d6efd": "el azul de serie de Bootstrap 5",
                     "#343a40": "el gris oscuro de serie de Bootstrap 4", "#212529": "el gris oscuro de serie de Bootstrap 5",
                     "#6c757d": "el gris de serie de Bootstrap", "#1976d2": "el azul de serie de Material UI y Vuetify",
                     "#3490dc": "el azul de serie de Laravel (Bootstrap)", "#00d1b2": "el turquesa de serie de Bulma"}


def _nota_de_serie(h):
    return "   ← ¡ojo! es %s" % _COLORES_DE_SERIE[h] if h in _COLORES_DE_SERIE else ""


def confirmar_colores(det, titulo, vista, ayuda_p, ayuda_o, sin_ventana=False):
    """El paso de los colores del asistente: los enseña, pregunta y, si no, abre la ventana.

    `det` es lo que devuelve paleta_del_proyecto. Devuelve (principal, oscuro, elegidos_a_mano).
    """
    p, o = det["primario"], det["oscuro"]
    print("\nColores del proyecto")
    print("   Qué va: el principal es el color de acción de tu proyecto (botones, enlaces); el oscuro, el del")
    print("   fondo o la estructura. Salen de sus estilos; si no son, eliges otros en una ventana.")
    if det["supuesto"]:
        print("  No he encontrado colores propios en el proyecto (ni en su sistema de diseño, ni en Tailwind,")
        print("  ni en sus hojas de estilo).")
        cambiar = True
    else:
        print("  principal  %s   ← %s%s" % (p[0], p[2], " (`%s`)" % p[1] if p[1] else ""))
        print("  oscuro     %s   ← %s%s" % (o[0], o[2], " (`%s`)" % o[1] if o[1] else ""))
        notas = [x for x in (_nota_de_serie(p[0]), _nota_de_serie(o[0])) if x]
        if notas:
            print("  " + " · ".join(n.strip(" ←") for n in notas) + ": probablemente no son los de tu proyecto.")
        cambiar = not _si_no("¿Son esos los colores?", True)
    if not cambiar:
        return p[0], o[0], False
    inicial_p = p[0] if p else _SUGERENCIAS[0][0]
    inicial_o = o[0] if o else _SUGERENCIAS[8][0]
    while True:
        elegidos = None
        if not sin_ventana:
            elegidos = elegir_colores_en_ventana(titulo, det["candidatos"], inicial_p, inicial_o, vista, ayuda_p, ayuda_o)
        if elegidos:
            print("  Elegidos: principal %s · oscuro %s" % elegidos)
            np, no = elegidos
        else:
            print("  Escríbelos aquí, entonces.")
            np = _pedir_color_texto("  Color principal", None if det["supuesto"] else inicial_p)
            no = _pedir_color_texto("  Color oscuro", None if det["supuesto"] else inicial_o)
        avisos = avisos_de_contraste(np, no)
        if not avisos:
            return np, no, True
        for x in avisos:
            print("  ¡Ojo! " + x)
        if _si_no("  ¿Usarlos igualmente?", False):
            return np, no, True
        inicial_p, inicial_o = np, no
        print("  Vuelve a elegirlos.")


def avisos_de_contraste(principal, oscuro):
    """El texto y el símbolo van en blanco: con un fondo claro no se leen."""
    avisos = []
    if _luz(oscuro) > 0.45:
        avisos.append("El color oscuro (%s) es claro. Va de fondo detrás de un símbolo y un texto blancos, "
                      "que no se verían. Elige un color oscuro de verdad." % oscuro)
    if _luz(principal) > 0.8:
        avisos.append("El color principal (%s) es casi blanco: el símbolo blanco no se vería encima." % principal)
    return avisos


def detectar_colores(p):
    """((principal, token, archivo) | None, (oscuro, token, archivo) | None): los del proyecto."""
    det = paleta_del_proyecto(p.raiz)
    return det["primario"], det["oscuro"]


def _norm_svg(t):
    return re.sub(r"\s+", " ", t).replace(" />", "/>").replace("/>", "/>").strip()


def iconos_propios(p):
    """([icono-palabra.svg…], icono.svg antiguo o None) que ya hay en la carpeta del icono."""
    try:
        nuevos = sorted(f for f in p.destino.glob(PREFIJO + "-*.svg")
                        if re.fullmatch(re.escape(PREFIJO) + r"-[a-z0-9-]+", f.stem)
                        and not re.fullmatch(re.escape(PREFIJO) + r"-\d+", f.stem))
    except OSError:
        nuevos = []
    antiguo = p.destino / (PREFIJO + ".svg")
    return nuevos, (antiguo if antiguo.is_file() else None)


def elegir_palabra(propuesta, interactivo):
    """La palabra que distingue los archivos de este icono de los de otras aplicaciones."""
    if not interactivo:
        if not propuesta:
            raise ErrorIcono("No pude sacar una palabra del nombre para los archivos. Indícala con --palabra inventario.")
        return propuesta
    print("\nPalabra para los nombres de los archivos")
    print("   Qué va: una palabra que distinga este icono del de otras aplicaciones. Se añade al nombre de")
    print("   cada archivo para que no se repitan entre proyectos (por ejemplo, en la intranet).")
    print("   Ejemplo: «inventario» -> icono-inventario.svg, icono-16-inventario.png, icono-192-inventario.png")
    if propuesta:
        print("   Sale de la primera palabra del nombre: «%s». Pulsa Enter para usarla o escribe otra." % propuesta)
    while True:
        r = limpiar_palabra(_preguntar("   Palabra", propuesta or None) or "")
        if r:
            return r
        print("   Hace falta una palabra (letras o números, sin espacios).")


def _aviso_antiguos(p, antiguo, prefijo):
    """El icono antiguo (icono.svg, icono-16.png…) no se borra: algo fuera de las páginas puede usarlo."""
    if not antiguo or prefijo == PREFIJO:
        return
    viejos = [f for f in [antiguo] + [p.destino / nombre_png(PREFIJO, n) for n in TAMANOS_PNG] if f.is_file()]
    if viejos:
        print("\nLos archivos con el nombre antiguo siguen ahí: %s." % ", ".join(f.name for f in viejos))
        print("   Las páginas ya usan los nuevos. Si nada más los usa (por ejemplo, la tarjeta de la intranet),")
        print("   puedes borrarlos; si la tarjeta los usa, cámbiala a %s." % nombre_png(prefijo, 192))


def simbolo_existente(p, prefijo=PREFIJO):
    """El símbolo que la aplicación ya usa, si se puede saber: (nombre, de dónde)."""
    svg = next((f for f in [p.destino / (prefijo + ".svg")] + iconos_propios(p)[0] if f.is_file()),
               p.destino / (prefijo + ".svg"))
    texto = _norm_svg(_texto(svg)) if svg.is_file() else ""
    if texto:
        m = re.search(r"Símbolo: ([a-z0-9-]+)", texto)
        if m and m.group(1) in SIMBOLOS:
            return m.group(1), _rel(p.raiz, svg)
        for nombre, frag in SIMBOLOS.items():
            piezas = re.findall(r"<[^>]+>", _norm_svg(frag))
            if piezas and all(x in texto for x in piezas):
                return nombre, _rel(p.raiz, svg)
    for f in ("config/acerca.php", "config/app.php"):
        m = re.search(r"['\"]icono['\"]\s*=>\s*['\"]([a-z0-9-]+)['\"]", _texto(p.raiz / f))
        if m and m.group(1) in SIMBOLOS:
            return m.group(1), f
    return None, None


def sugerir_simbolo(p, nombre):
    """(símbolo, palabras que lo delataron) o (None, [])."""
    ya, origen = simbolo_existente(p)
    if ya:
        return ya, ["ya lo usa (%s)" % origen]
    trozos = [nombre]
    for f in ("config/app.php", "package.json", "composer.json", "pyproject.toml"):
        trozos.append(_texto(p.raiz / f, 200000)[:4000])
    for pl in p.plantillas[:20]:
        m = re.search(r"<title>(.*?)</title>", _texto(pl), re.I | re.S)
        if m:
            trozos.append(m.group(1))
    for f in ("README.md", "readme.md", "README"):
        trozos.append(_texto(p.raiz / f, 500000)[:4000])
    nombres = [r.stem for r in _archivos(p.raiz, (".php", ".py", ".js", ".ts", ".tsx", ".jsx", ".vue", ".cs", ".java",
                                                 ".rb", ".go", ".html"), max_archivos=3000)]
    trozos.append(" ".join(nombres))
    texto = _sin_tildes(" ".join(trozos))
    texto_nombre = _sin_tildes(nombre)
    mejor, puntos_mejor, pruebas = None, 0, []
    for simbolo, palabras in PISTAS_SIMBOLO:
        puntos, vistas = 0, []
        for w in palabras:
            n = len(re.findall(r"\b" + re.escape(w), texto))
            if n:
                puntos += min(n, 5) + (6 if re.search(r"\b" + re.escape(w), texto_nombre) else 0)
                vistas.append(w)
        if puntos > puntos_mejor:
            mejor, puntos_mejor, pruebas = simbolo, puntos, vistas
    return mejor, pruebas


# ------------------------------------------------------------------ enganche
_RE_LINK_ICONO = re.compile(
    r"<link\b[^>]*\brel\s*=\s*[\"']?(?:shortcut\s+)?(?:icon|apple-touch-icon(?:-precomposed)?|mask-icon)\b[^>]*>", re.I)


def _lineas_link(p, plantilla, prefijo, ico):
    filas = []
    if ico:
        filas.append('<link rel="icon" %s sizes="any">' % p.href(plantilla, "favicon.ico"))
    filas += [
        '<link rel="icon" type="image/svg+xml" %s>' % p.href(plantilla, prefijo + ".svg"),
        '<link rel="icon" type="image/png" sizes="32x32" %s>' % p.href(plantilla, nombre_png(prefijo, 32)),
        '<link rel="icon" type="image/png" sizes="16x16" %s>' % p.href(plantilla, nombre_png(prefijo, 16)),
        '<link rel="apple-touch-icon" %s>' % p.href(plantilla, nombre_png(prefijo, 180)),
    ]
    if p.formato == "jsx":
        filas = [f[:-1] + " />" for f in filas]
    return filas


def enganchar_texto(texto, lineas, formato="html", reemplazar=False, prefijo=PREFIJO, django=False):
    """Devuelve (texto nuevo, acción). No toca nada si no está seguro de dónde va."""
    nl = "\r\n" if "\r\n" in texto else "\n"
    if formato == "jsx":
        ci, cf = "{/* ", " */}"
        re_abre, re_cierra = re.compile(r"<Head\b[^/>]*>"), re.compile(r"</Head>")
    else:
        ci, cf = "<!-- ", " -->"
        re_abre, re_cierra = re.compile(r"<head\b[^>]*>", re.I), re.compile(r"</head\s*>", re.I)

    def bloque(sangria):
        cuerpo = [ci + MARCA_INI + " · icono de la aplicación (generate_icon.py)" + cf] + lineas + [ci + MARCA_FIN + cf]
        return "".join(sangria + x + nl for x in cuerpo)

    previo = re.compile(r"^([ \t]*)" + re.escape(ci + MARCA_INI) + r".*?" + re.escape(MARCA_FIN + cf) + r"[ \t]*(?:\r?\n)?",
                        re.S | re.M).search(texto)
    if previo:
        nuevo = bloque(previo.group(1))
        if previo.group(0) == nuevo:
            return texto, "ya_enganchado"
        return _con_static(texto[:previo.start()] + nuevo + texto[previo.end():], django, nl), "actualizado"

    abre = re_abre.search(texto)
    cierra = re_cierra.search(texto, abre.end()) if abre else None
    if not abre or not cierra:
        return texto, "sin_head"
    cabeza = texto[abre.end():cierra.start()]
    existentes = list(_RE_LINK_ICONO.finditer(cabeza))
    if existentes:
        if any(re.search(r"\b" + re.escape(prefijo) + r"\.svg\b", e.group(0)) for e in existentes):
            return texto, "ya_enganchado"
        if not reemplazar:
            return texto, "otros_iconos"
        for e in reversed(existentes):
            ini, fin = e.start(), e.end()
            linea_ini = cabeza.rfind("\n", 0, ini) + 1
            linea_fin = cabeza.find("\n", fin)
            linea_fin = len(cabeza) if linea_fin == -1 else linea_fin + 1
            if not cabeza[linea_ini:ini].strip() and not cabeza[fin:linea_fin].strip():
                ini, fin = linea_ini, linea_fin
            cabeza = cabeza[:ini] + cabeza[fin:]
        texto = texto[:abre.end()] + cabeza + texto[cierra.start():]
        cierra = re_cierra.search(texto, abre.end())
        cabeza = texto[abre.end():cierra.start()]

    # Va justo después del <title> si lo hay; si no, al principio del <head>.
    t = re.search(r"</title\s*>", cabeza, re.I)
    if t:
        pos = abre.end() + t.end()
        ini_linea = texto.rfind("\n", 0, abre.end() + t.start()) + 1
        sangria = re.match(r"[ \t]*", texto[ini_linea:]).group(0)
    else:
        pos = abre.end()
        sig = re.search(r"\n([ \t]*)\S", texto[pos:])
        sangria = sig.group(1) if sig else re.match(r"[ \t]*", texto[texto.rfind("\n", 0, abre.start()) + 1:]).group(0) + "    "
    fin_linea = texto.find("\n", pos)
    if fin_linea != -1 and not texto[pos:fin_linea].strip():
        pos = fin_linea + 1
        nuevo = texto[:pos] + bloque(sangria) + texto[pos:]
    else:
        nuevo = texto[:pos] + nl + bloque(sangria) + texto[pos:]
    return _con_static(nuevo, django, nl), ("reemplazado" if existentes else "insertado")


def _con_static(texto, django, nl):
    """Django necesita {% load static %} para que funcione {% static %}."""
    if not django or "{% static" not in texto or re.search(r"{%\s*load\s+[^%]*\bstatic\b", texto):
        return texto
    m = re.match(r"\s*{%\s*extends\b[^%]*%}[^\n]*\n?", texto)
    if m:
        return texto[:m.end()] + "{% load static %}" + nl + texto[m.end():]
    return "{% load static %}" + nl + texto


# ------------------------------------------------------------- plan y escritura
class Plan:
    def __init__(self):
        self.escrituras = []     # (ruta, bytes, etiqueta)
        self.estados = []        # (plantilla, acción)
        self.textos = {}         # plantilla -> (antes, después)


def preparar_plan(p, svg, prefijo=PREFIJO, ico=True, reemplazar=False, enganchar=True, conservado=None):
    """Si `conservado` es la ruta del SVG que ya tenía el proyecto, no se rehace
    ningún PNG que exista y no sea más antiguo que él: están bien como están."""
    plan = Plan()
    tamanos = set(TAMANOS_PNG) | (set(TAMANOS_ICO) if ico else set())
    for destino, tipo in p.convenciones.items():
        if tipo == "ico":
            tamanos |= set(TAMANOS_ICO)
        elif isinstance(tipo, int):
            tamanos.add(tipo)
    pngs = rasterizar(svg, tamanos)
    plan.escrituras.append((p.destino / (prefijo + ".svg"), svg.encode("utf-8"), "SVG maestro"))
    for n in TAMANOS_PNG:
        plan.escrituras.append((p.destino / nombre_png(prefijo, n), pngs[n], "PNG %d px" % n))
    ico_bytes = codificar_ico([(n, pngs[n]) for n in TAMANOS_ICO]) if (ico or "ico" in p.convenciones.values()) else None
    if ico and p.ico_en_destino:
        plan.escrituras.append((p.destino / "favicon.ico", ico_bytes, "favicon.ico"))
    for destino, tipo in p.convenciones.items():
        datos = svg.encode("utf-8") if tipo == "svg" else (ico_bytes if tipo == "ico" else pngs[tipo])
        plan.escrituras.append((destino, datos, "convención de %s" % p.descripcion))
    if enganchar:
        for pl in p.plantillas:
            try:
                bruto = pl.read_bytes()
                bom = bruto.startswith(b"\xef\xbb\xbf")
                antes = bruto.decode("utf-8-sig" if bom else "utf-8")
            except (OSError, UnicodeDecodeError):
                plan.estados.append((pl, "no_utf8"))
                continue
            despues, accion = enganchar_texto(antes, _lineas_link(p, pl, prefijo, ico), p.formato,
                                              reemplazar, prefijo, p.django)
            plan.estados.append((pl, accion))
            if despues != antes:
                plan.textos[pl] = (antes, despues)
                plan.escrituras.append((pl, (b"\xef\xbb\xbf" if bom else b"") + despues.encode("utf-8"),
                                        "<link> del icono"))
    if conservado is not None:
        t_svg = conservado.stat().st_mtime
        ico_destino = p.destino / "favicon.ico"
        # Si todas las páginas ya tenían el icono puesto, un favicon.ico nuevo
        # quedaría sin enlazar: no se crea.
        ico_sobra = (not ico_destino.exists() and "ico" not in p.convenciones.values()
                     and plan.estados and all(x == "ya_enganchado" for _pl, x in plan.estados))
        plan.escrituras = [
            (ruta, datos, etq) for ruta, datos, etq in plan.escrituras
            if ruta in plan.textos
            or not (ruta.exists() and ruta.stat().st_mtime + 1 >= t_svg)
            and not (ico_sobra and ruta == ico_destino)
        ]
    return plan


def _sha(datos):
    return hashlib.sha256(datos).hexdigest()


def aplicar_plan(p, plan):
    """Escribe el plan con respaldo de todo lo que ya existía. Devuelve el manifiesto."""
    estado = p.raiz / CARPETA_ESTADO
    marca = time.strftime("%Y%m%d-%H%M%S")
    respaldo = estado / "respaldos" / marca
    man = {"version": VERSION, "fecha": marca, "creados": [], "modificados": [], "carpetas": []}
    for ruta, datos, _etiqueta in plan.escrituras:
        rel = _rel(p.raiz, ruta)
        if ruta.exists():
            if ruta.read_bytes() == datos:
                continue
            # Con .bak: si la carpeta queda dentro de la raíz web, un respaldo
            # de un .php no se ejecuta ni se sirve como página.
            copia = respaldo / (rel + ".bak")
            copia.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(str(ruta), str(copia))
            man["modificados"].append({"ruta": rel, "respaldo": _rel(p.raiz, copia), "sha256": _sha(datos)})
        else:
            faltan = []
            d = ruta.parent
            while not d.exists():
                faltan.append(d)
                d = d.parent
            for d in reversed(faltan):
                d.mkdir()
                man["carpetas"].append(_rel(p.raiz, d))
            man["creados"].append({"ruta": rel, "sha256": _sha(datos)})
        tmp = ruta.with_name(ruta.name + ".generate_icon.tmp")
        tmp.write_bytes(datos)
        os.replace(str(tmp), str(ruta))
    estado.mkdir(exist_ok=True)
    # Se ignora a sí misma en git sin tocar el .gitignore del proyecto
    (estado / ".gitignore").write_text("*\n", encoding="utf-8")
    # Y que Apache no la entregue (en Nginx/IIS, la regla equivalente; ver MANUAL.md)
    (estado / ".htaccess").write_text(
        "<IfModule mod_authz_core.c>\n    Require all denied\n</IfModule>\n"
        "<IfModule !mod_authz_core.c>\n    Order allow,deny\n    Deny from all\n</IfModule>\n",
        encoding="utf-8")
    (estado / "ultimo.json").write_text(json.dumps(man, indent=2, ensure_ascii=False), encoding="utf-8")
    return man


def mostrar_plan(p, plan, cabecera):
    print(cabecera)
    print("\nArchivos del icono  →  %s/" % (_rel(p.raiz, p.destino) if p.destino != p.raiz else "."))
    for ruta, datos, etiqueta in plan.escrituras:
        if ruta in plan.textos:
            continue
        if ruta.exists():
            marca = "=" if ruta.read_bytes() == datos else "~"
        else:
            marca = "+"
        print("  %s %-34s %s" % (marca, _rel(p.raiz, ruta), etiqueta + (" (se respalda el actual)" if marca == "~" else "")))
    textos = {"insertado": "se añaden los <link>", "reemplazado": "se cambian los <link> del icono anterior",
              "actualizado": "se actualizan los <link>", "ya_enganchado": "ya tenía el icono puesto",
              "otros_iconos": "tiene OTRO icono: no se toca (usa --reemplazar-iconos)",
              "sin_head": "no se encontró dónde ponerlo", "no_utf8": "no está en UTF-8: no se toca"}
    if plan.estados:
        print("\nPlantillas")
        for pl, accion in plan.estados:
            marca = "~" if pl in plan.textos else ("=" if accion == "ya_enganchado" else "!")
            print("  %s %-34s %s" % (marca, _rel(p.raiz, pl), textos.get(accion, accion)))
    elif not p.convenciones and p.tipo != "wordpress":
        print("\nPlantillas: no se encontró ninguna con <head>. Pega los <link> a mano (se muestran al final).")
    for n in p.notas:
        print("  · " + n)
    print("\n  + nuevo   ~ cambia (con respaldo)   = sin cambios   ! no se toca")


def _diff(p, plan):
    import difflib
    for pl, (antes, despues) in plan.textos.items():
        rel = _rel(p.raiz, pl)
        sys.stdout.writelines(difflib.unified_diff(antes.splitlines(True), despues.splitlines(True),
                                                   "a/" + rel, "b/" + rel))


def _preguntar(texto, defecto=None):
    try:
        r = input("%s%s: " % (texto, " [%s]" % defecto if defecto else "")).strip()
    except EOFError:
        # Nadie puede responder (entrada cerrada o redirigida): no se supone
        # ninguna respuesta, y menos un «sí».
        print()
        raise ErrorIcono("No hay nadie para responder a las preguntas, así que no se ha escrito nada. "
                         "Para usarlo sin preguntas, añade --si.")
    return r or defecto


def _si_no(texto, defecto=False):
    r = _preguntar(texto + (" [S/n]" if defecto else " [s/N]"))
    return defecto if not r else _sin_tildes(r).startswith(("s", "y"))


def _elegir_simbolo_interactivo(sugerido, pruebas):
    nombres = list(SIMBOLOS)
    print("\nSímbolo del icono")
    print("   Qué va: el dibujo blanco del centro. Mejor el objeto con el que trabaja la aplicación que una")
    print("   idea abstracta: una caja para un inventario, un reloj para la asistencia, una huella para mascotas.")
    print("   Escribe su número o su nombre; también vale la ruta a un .svg descargado de lucide.dev.")
    print("\nSímbolos disponibles (Lucide):")
    ancho = max(len(x) for x in nombres) + 6
    columnas = 4
    for i in range(0, len(nombres), columnas):
        print("  " + "".join(("%2d %s" % (j + 1, nombres[j])).ljust(ancho)
                             for j in range(i, min(i + columnas, len(nombres)))))
    if sugerido:
        print("\nSugerido: %s  (por: %s)" % (sugerido, ", ".join(pruebas[:5])))
    while True:
        r = _preguntar("Número o nombre del símbolo, o ruta a un .svg de Lucide", sugerido)
        if not r:
            continue
        if r.isdigit() and 1 <= int(r) <= len(nombres):
            return nombres[int(r) - 1], None
        if r in SIMBOLOS:
            return r, None
        ruta = Path(r.strip("\"'"))
        if ruta.suffix.lower() == ".svg" and ruta.is_file():
            return ruta.stem, ruta
        print("  No lo reconozco. Escribe un número de la lista, un nombre o la ruta a un .svg.")


def _pedir_hex(texto, defecto=None):
    while True:
        r = _preguntar(texto, defecto)
        try:
            return normalizar_hex(r or "", texto)
        except ErrorIcono:
            print("  Escríbelo en hexadecimal, por ejemplo #0369a1.")


def orden_instalar(a):
    interactivo = not a.si
    raiz = Path(a.proyecto) if a.proyecto else raiz_del_proyecto()
    p = detectar_proyecto(raiz)
    if a.destino:
        p.destino = (p.raiz / a.destino).resolve()
    print("\nProyecto: %s  ·  %s" % (p.raiz, p.descripcion))
    if interactivo and not a.proyecto:
        print("(Si no es éste, no pasa nada: al final te pregunta antes de escribir.)")

    # Nombre de los archivos: icono-<palabra>.svg, icono-16-<palabra>.png… para que no se repitan entre
    # proyectos. Un --prefijo propio se respeta tal cual; si ya hay un icono con palabra, se sigue usando.
    antiguo = None
    if a.prefijo == PREFIJO:
        nuevos, antiguo = iconos_propios(p)
        if a.palabra:
            palabra = limpiar_palabra(a.palabra)
            if not palabra:
                raise ErrorIcono("--palabra necesita letras o números, por ejemplo --palabra inventario.")
            a.prefijo = PREFIJO + "-" + palabra
        elif len(nuevos) == 1:
            a.prefijo = nuevos[0].stem
            print("Archivos:   %s, %s… (los nombres que ya tiene)" % (nuevos[0].name, nombre_png(a.prefijo, 16)))
        elif len(nuevos) > 1:
            print("\nHay varios iconos con palabra: %s." % ", ".join(f.name for f in nuevos))
            print("   Dime cuál usar con --palabra (por ejemplo --palabra %s)." % nuevos[0].stem[len(PREFIJO) + 1:])
            raise ErrorIcono("No sé cuál de los iconos usar: indícalo con --palabra.")
    maestro = p.destino / (a.prefijo + ".svg")
    if a.prefijo == PREFIJO and antiguo:
        maestro = antiguo
    conservar = False
    if maestro.is_file() and not a.sobrescribir:
        if interactivo:
            print("\nEste proyecto ya tiene icono: %s" % _rel(p.raiz, maestro))
            print("   Si dices que no, se conserva tal cual y sólo se completan los PNG que falten y las líneas")
            print("   de las páginas. Si dices que sí, eliges dibujo y colores de nuevo (el anterior se guarda).")
            conservar = not _si_no("   ¿Hacer uno nuevo?", False)
        else:
            conservar = True
            print("Ya tiene icono (%s): se conserva. Para hacer uno nuevo, añade --sobrescribir." % _rel(p.raiz, maestro))
    if conservar:
        svg = maestro.read_text(encoding="utf-8")
        Rasterizador(svg)  # falla con un mensaje claro si el SVG está roto
        if a.prefijo == PREFIJO:
            # Icono antiguo sin palabra: se conserva el dibujo y se le dan los nombres nuevos
            a.prefijo = PREFIJO + "-" + elegir_palabra(palabra_de(detectar_nombre(p)[0] or ""), interactivo)
        r = _instalar_svg(a, p, svg, "\nIcono:      %s (se conserva el dibujo actual)" % _rel(p.raiz, maestro),
                          interactivo, conservado=maestro)
        _aviso_antiguos(p, antiguo, a.prefijo)
        return r

    # Nombre
    nombre, origen = (a.nombre, "indicado") if a.nombre else detectar_nombre(p)
    if interactivo and not a.nombre:
        print("\nNombre de la aplicación")
        print("   Qué va: el nombre con el que la gente la conoce. Va dentro del icono, como su descripción")
        print("   para lectores de pantalla, y en el comentario del SVG.")
        print("   Ejemplo: «Control de Inventario», «PanitasPet», «Gestión de Asistencia»")
        if nombre:
            print("   En %s aparece «%s». Pulsa Enter para usarlo o escribe otro." % (origen, nombre))
        while True:
            nombre = (_preguntar("   Nombre", nombre or None) or "").strip()
            if nombre:
                break
            print("   Hace falta una respuesta: escribe el nombre.")
    elif not nombre:
        raise ErrorIcono("No encontré el nombre de la aplicación en ningún archivo del proyecto. Indícalo con "
                         "--nombre \"Mi aplicación\" (el de la carpeta no se usa: no tiene por qué ser el nombre).")

    # Símbolo
    simbolo_svg = Path(a.simbolo_svg) if a.simbolo_svg else None
    if a.trazado:
        simbolo, nombre_simbolo, motivo = a.trazado, "propio", a.motivo or ""
    else:
        if a.simbolo or simbolo_svg:
            elegido = a.simbolo or simbolo_svg.stem
            pruebas = []
        else:
            elegido, pruebas = sugerir_simbolo(p, nombre)
            if interactivo:
                elegido, simbolo_svg = _elegir_simbolo_interactivo(elegido, pruebas)
            elif not elegido:
                raise ErrorIcono("No pude deducir un símbolo para «%s». Indícalo con --simbolo (ver orden simbolos)." % nombre)
        if simbolo_svg:
            simbolo, nombre_simbolo = simbolo_desde_svg(simbolo_svg), simbolo_svg.stem
        elif elegido in SIMBOLOS:
            simbolo, nombre_simbolo = SIMBOLOS[elegido], elegido
        else:
            raise ErrorIcono("No conozco el símbolo '%s'. Mira la lista con: %s" % (elegido, _llamada("simbolos")))
        motivo = a.motivo or ("sugerido por: " + ", ".join(pruebas[:4]) if pruebas else "")

    # Colores: los del proyecto. Se enseñan y se confirman; si no, se eligen en una ventana.
    if interactivo and not (a.primario or a.oscuro or a.css):
        det = paleta_del_proyecto(p.raiz)
        muestra = construir_svg(nombre, simbolo, "#000001", "#000002", nombre_simbolo=nombre_simbolo,
                                extra=a.extra or "", redondo=a.redondo)
        muestra = muestra.split("-->", 1)[1].replace("#000001", "__P__").replace("#000002", "__O__")
        vista = "".join(
            '<div class="fondo %s">%s</div>' % (fondo, "".join(
                muestra.replace('width="64" height="64"', 'width="%d" height="%d"' % (n, n), 1) for n in (128, 64, 32, 16)))
            for fondo in ("claro", "oscuro"))
        primario, oscuro, a_mano = confirmar_colores(
            det, "Colores del icono · %s" % nombre, vista,
            "Inicio del degradado: el color de acción de la aplicación.",
            "Final del degradado: el oscuro de estructura.", sin_ventana=a.sin_ventana)
        if a_mano:
            tp, to = "elegido a mano", "elegido a mano"
        else:
            tp = det["primario"][1] or det["primario"][2]
            to = det["oscuro"][1] or det["oscuro"][2]
    else:
        tokens = leer_tokens(a.css) if a.css else {}
        det_p, det_o = detectar_colores(p) if not (a.primario and a.oscuro) else (None, None)
        primario = a.primario or tokens.get(a.token_primario) or (det_p[0] if det_p else None)
        oscuro = a.oscuro or tokens.get(a.token_oscuro) or (det_o[0] if det_o else None)
        tp = (det_p[1] or "detectado") if (det_p and not a.primario) else a.token_primario
        to = (det_o[1] or "detectado") if (det_o and not a.oscuro) else a.token_oscuro
        if interactivo and not (primario and oscuro):
            primario = primario or _pedir_hex("Color principal (inicio del degradado, #rrggbb)")
            oscuro = oscuro or _pedir_hex("Color oscuro (final del degradado, #rrggbb)")
        elif not (primario and oscuro):
            raise ErrorIcono("No encontré los colores de marca. Pásalos con --primario y --oscuro (#rrggbb) o con --css. "
                             "No se inventan.")

    if a.prefijo == PREFIJO:
        a.prefijo = PREFIJO + "-" + elegir_palabra(palabra_de(nombre), interactivo)
    svg = construir_svg(nombre, simbolo, primario, oscuro, nombre_simbolo=nombre_simbolo, motivo=motivo,
                        token_primario=tp, token_oscuro=to, extra=a.extra or "", redondo=a.redondo)
    cab = "\nAplicación: %s\nSímbolo:    %s%s\nColores:    %s → %s\nArchivos:   %s, %s…" % (
        nombre, nombre_simbolo, ("  (%s)" % motivo) if motivo else "",
        normalizar_hex(primario), normalizar_hex(oscuro), a.prefijo + ".svg", nombre_png(a.prefijo, 16))
    r = _instalar_svg(a, p, svg, cab, interactivo)
    _aviso_antiguos(p, antiguo, a.prefijo)
    return r


def _instalar_svg(a, p, svg, cab, interactivo, conservado=None):
    ico = not a.sin_ico
    print("\nDibujando el icono…")
    plan = preparar_plan(p, svg, a.prefijo, ico, a.reemplazar_iconos, not a.sin_enganchar, conservado)
    if interactivo and not a.reemplazar_iconos and any(x == "otros_iconos" for _pl, x in plan.estados):
        print("\nAlgunas páginas ya tienen otro icono (por ejemplo, el logotipo de la empresa como favicon).")
        print("   Si dices que sí, sus líneas se cambian por las del icono nuevo (con copia de cada archivo).")
        print("   Si dices que no, esas páginas se quedan con el que tienen.")
        if _si_no("   ¿Sustituirlo por el nuevo?", False):
            plan = preparar_plan(p, svg, a.prefijo, ico, True, not a.sin_enganchar, conservado)

    mostrar_plan(p, plan, cab)
    if a.simulacro:
        print("\n(simulacro) Cambios en plantillas:\n")
        _diff(p, plan)
        print("\n(simulacro) No se ha escrito nada.")
        return 0
    cambios = [x for x in plan.escrituras if not (x[0].exists() and x[0].read_bytes() == x[1])]
    if not cambios:
        print("\nTodo estaba ya al día. No hay nada que escribir.")
        return 0
    if interactivo:
        if plan.textos and _si_no("\n¿Ver exactamente qué líneas cambian en las plantillas?", False):
            print()
            _diff(p, plan)
        if not _si_no("\n¿Aplicar estos cambios?", False):
            print("Cancelado. No se ha escrito nada.")
            return 1
    man = aplicar_plan(p, plan)
    print("\nHecho: %d archivo(s) nuevo(s), %d cambiado(s) con respaldo en %s/."
          % (len(man["creados"]), len(man["modificados"]), CARPETA_ESTADO))
    print("Para dejarlo todo como estaba:  %s" % _llamada("deshacer"))

    sin_enganche = not any(pl in plan.textos for pl, _x in plan.estados) and not p.convenciones \
        and not any(x == "ya_enganchado" for _pl, x in plan.estados)
    if sin_enganche and p.tipo != "wordpress":
        print("\nNo pude poner los <link> yo solo. Pega esto en el <head> de tu página:\n")
        print("\n".join(_lineas_link(p, p.publico / "index.html", a.prefijo, ico)))
    if p.tipo == "nuxt":
        rutas = ["/" + _rel(p.publico, p.destino / f) for f in (a.prefijo + ".svg", nombre_png(a.prefijo, 180))]
        print("\nEn nuxt.config, dentro de app.head.link:\n  { rel: 'icon', type: 'image/svg+xml', href: '%s' },\n"
              "  { rel: 'apple-touch-icon', href: '%s' }" % tuple(rutas))
    print("\nTarjeta de la intranet: %s." % _rel(p.raiz, p.destino / nombre_png(a.prefijo, 192)))
    return 0


def orden_detectar(a):
    p = detectar_proyecto(Path(a.proyecto) if a.proyecto else raiz_del_proyecto())
    nombre, origen = detectar_nombre(p)
    sim, pruebas = sugerir_simbolo(p, nombre)
    cp, co = detectar_colores(p)
    print("Proyecto:    %s" % p.raiz)
    print("Tipo:        %s" % p.descripcion)
    print("Nombre:      %s" % ("%s  (de %s)" % (nombre, origen) if nombre else "— (no hay una fuente fiable: se pregunta)"))
    print("Símbolo:     %s" % ("%s  (por: %s)" % (sim, ", ".join(pruebas[:5])) if sim else "sin sugerencia"))
    def _color(c):
        return ("%s (%s%s)" % (c[0], ("`%s` en " % c[1]) if c[1] else "", c[2])) if c else "no encontrado"
    print("Colores:     %s → %s" % (_color(cp),
                                    _color(co)))
    print("Imágenes en: %s" % _rel(p.raiz, p.destino))
    print("Plantillas:  %s" % (", ".join(_rel(p.raiz, x) for x in p.plantillas) or "ninguna con <head>"))
    for d in p.convenciones:
        print("Convención:  %s" % _rel(p.raiz, d))
    for n in p.notas:
        print("Nota:        %s" % n)
    return 0


def orden_deshacer(a):
    raiz = Path(a.proyecto).resolve() if a.proyecto else raiz_del_proyecto()
    ruta_man = raiz / CARPETA_ESTADO / "ultimo.json"
    if not ruta_man.is_file():
        raise ErrorIcono("No hay ninguna instalación que deshacer en %s." % raiz)
    man = json.loads(ruta_man.read_text(encoding="utf-8"))
    print("Deshaciendo la instalación del %s" % man.get("fecha", "?"))
    saltados = 0
    for item in man.get("modificados", []):
        ruta, copia = raiz / item["ruta"], raiz / item["respaldo"]
        if ruta.exists() and _sha(ruta.read_bytes()) != item["sha256"] and not a.forzar:
            print("  ! %s cambió después de instalar: no lo toco (usa --forzar)" % item["ruta"])
            saltados += 1
            continue
        shutil.copy2(str(copia), str(ruta))
        print("  ↺ %s restaurado" % item["ruta"])
    for item in man.get("creados", []):
        ruta = raiz / item["ruta"]
        if not ruta.exists():
            continue
        if _sha(ruta.read_bytes()) != item["sha256"] and not a.forzar:
            print("  ! %s cambió después de instalar: no lo borro (usa --forzar)" % item["ruta"])
            saltados += 1
            continue
        ruta.unlink()
        print("  − %s borrado" % item["ruta"])
    for d in reversed(man.get("carpetas", [])):
        try:
            (raiz / d).rmdir()
        except OSError:
            pass
    if saltados:
        print("\n%d archivo(s) no se tocaron. La instalación sigue registrada." % saltados)
        return 1
    os.replace(str(ruta_man), str(ruta_man.with_name("deshecho-%s.json" % man.get("fecha", "x"))))
    print("\nListo: el proyecto está como antes. Los respaldos siguen en %s/ por si acaso." % CARPETA_ESTADO)
    return 0


# ===========================================================================
#  Instalar el propio comando: escribir `generate_icon` en cualquier terminal
# ---------------------------------------------------------------------------
#  Se copia este mismo archivo a una carpeta personal de programas (sin
#  permisos de administrador) y esa carpeta se añade al PATH del usuario, si
#  hace falta y sólo si se acepta. No se instala nada más.
# ===========================================================================

NOMBRE_COMANDO = "generate_icon"
_MARCA_PATH = "# Añadido por generate_icon (instalar-comando)"


def _carpeta_comando(a):
    if getattr(a, "carpeta", None):
        return Path(a.carpeta).expanduser().resolve()
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        return Path(base) / "Programs" / NOMBRE_COMANDO
    return Path.home() / ".local" / "bin"


def _en_path(carpeta):
    actual = os.path.normcase(str(carpeta))
    for d in os.environ.get("PATH", "").split(os.pathsep):
        try:
            if d and os.path.normcase(str(Path(d).expanduser().resolve())) == actual:
                return True
        except OSError:
            pass
    return False


def _perfil_shell():
    shell = os.path.basename(os.environ.get("SHELL", ""))
    if shell == "zsh":
        return Path.home() / ".zshrc"
    if shell == "bash":
        mac = sys.platform == "darwin"
        return Path.home() / (".bash_profile" if mac else ".bashrc")
    if shell == "fish":
        return None  # otra sintaxis: se explica en vez de tocar su configuración
    return Path.home() / ".profile"


def _path_windows(carpeta, quitar=False):
    """Añade (o quita) la carpeta del PATH del usuario en el registro. Devuelve True si cambió."""
    import winreg  # sólo existe en Windows
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment", 0,
                        winreg.KEY_READ | winreg.KEY_WRITE) as k:
        try:
            valor, tipo = winreg.QueryValueEx(k, "Path")
        except FileNotFoundError:
            valor, tipo = "", winreg.REG_EXPAND_SZ
        partes = [x for x in valor.split(";") if x]
        objetivo = os.path.normcase(str(carpeta))
        presentes = [x for x in partes if os.path.normcase(os.path.expandvars(x).rstrip("\\")) == objetivo]
        if quitar:
            if not presentes:
                return False
            partes = [x for x in partes if x not in presentes]
        else:
            if presentes:
                return False
            partes.append(str(carpeta))
        winreg.SetValueEx(k, "Path", 0, tipo if tipo in (winreg.REG_SZ, winreg.REG_EXPAND_SZ)
                          else winreg.REG_EXPAND_SZ, ";".join(partes))
    try:  # avisa a Windows de que cambió el entorno (las terminales nuevas lo verán)
        import ctypes
        resultado = ctypes.c_ulong()
        ctypes.windll.user32.SendMessageTimeoutW(0xFFFF, 0x001A, 0, "Environment", 2, 5000,
                                                 ctypes.byref(resultado))
    except Exception:
        pass
    return True


def orden_instalar_comando(a):
    origen = Path(__file__).resolve()
    if getattr(sys, "frozen", False):
        raise ErrorIcono("Esto ya es un ejecutable compilado: basta con dejarlo en una carpeta del PATH.")
    carpeta = _carpeta_comando(a)
    windows = os.name == "nt"
    if windows:
        archivos = [carpeta / "generate_icon.py", carpeta / (NOMBRE_COMANDO + ".cmd")]
    else:
        archivos = [carpeta / NOMBRE_COMANDO]
    falta_path = not _en_path(carpeta)
    perfil = None if windows else _perfil_shell()

    print("Instalar el comando «%s» para este usuario (sin permisos de administrador):\n" % NOMBRE_COMANDO)
    for f in archivos:
        print("  %s %s" % ("~" if f.exists() else "+", f))
    if falta_path:
        if windows:
            print("  ~ PATH del usuario: se añade %s" % carpeta)
        elif perfil:
            print("  ~ %s: se añade %s al PATH (una línea, marcada)" % (perfil, carpeta))
        else:
            print("  ! Tu terminal es fish: añade tú  fish_add_path %s" % carpeta)
    if not a.si and not _si_no("\n¿Instalar?", False):
        print("Cancelado. No se ha escrito nada.")
        return 1

    carpeta.mkdir(parents=True, exist_ok=True)
    if windows:
        shutil.copyfile(str(origen), str(archivos[0]))
        # Lanzador: usa `py` (el lanzador oficial de Python en Windows) o, si no está, `python`
        archivos[1].write_text(
            "@echo off\r\n"
            "where py >nul 2>nul\r\n"
            "if %ERRORLEVEL%==0 (\r\n"
            "    py -3 \"%~dp0generate_icon.py\" %*\r\n"
            ") else (\r\n"
            "    python \"%~dp0generate_icon.py\" %*\r\n"
            ")\r\n", encoding="ascii")
        if falta_path:
            _path_windows(carpeta)
    else:
        destino = archivos[0]
        tmp = destino.with_name(destino.name + ".tmp")
        shutil.copyfile(str(origen), str(tmp))
        os.chmod(str(tmp), 0o755)
        os.replace(str(tmp), str(destino))
        if falta_path and perfil:
            previo = perfil.read_text(encoding="utf-8", errors="replace") if perfil.exists() else ""
            if _MARCA_PATH not in previo:
                with open(str(perfil), "a", encoding="utf-8") as f:
                    f.write("\n%s\nexport PATH=\"%s:$PATH\"\n" % (_MARCA_PATH, carpeta))
    print("\nListo. Abre una terminal NUEVA, entra en la carpeta de cualquier proyecto y escribe:\n")
    print("    %s\n" % NOMBRE_COMANDO)
    print("Para quitarlo:  %s desinstalar-comando" % NOMBRE_COMANDO)
    return 0


def orden_desinstalar_comando(a):
    carpeta = _carpeta_comando(a)
    windows = os.name == "nt"
    archivos = ([carpeta / "generate_icon.py", carpeta / (NOMBRE_COMANDO + ".cmd")] if windows
                else [carpeta / NOMBRE_COMANDO])
    existentes = [f for f in archivos if f.exists()]
    perfil = None if windows else _perfil_shell()
    con_linea = bool(perfil and perfil.exists()
                     and _MARCA_PATH in perfil.read_text(encoding="utf-8", errors="replace"))
    if not existentes and not con_linea:
        print("El comando no está instalado en %s." % carpeta)
        return 0
    print("Se quitará:\n")
    for f in existentes:
        print("  - %s" % f)
    if windows:
        print("  - %s del PATH del usuario (si está)" % carpeta)
    elif con_linea:
        print("  - la línea marcada de %s" % perfil)
    if not a.si and not _si_no("\n¿Desinstalar?", False):
        print("Cancelado.")
        return 1
    for f in existentes:
        f.unlink()
    if windows:
        _path_windows(carpeta, quitar=True)
        try:
            carpeta.rmdir()
        except OSError:
            pass
    elif con_linea:
        lineas = perfil.read_text(encoding="utf-8").split("\n")
        salida, saltar = [], False
        for ln in lineas:
            if ln == _MARCA_PATH:
                saltar = True
                if salida and salida[-1] == "":
                    salida.pop()
                continue
            if saltar and ln.startswith("export PATH="):
                saltar = False
                continue
            saltar = False
            salida.append(ln)
        perfil.write_text("\n".join(salida), encoding="utf-8")
    print("Desinstalado.")
    return 0


def _agregar_ordenes_instalacion(s):
    i = s.add_parser("instalar", help="detecta el proyecto, crea el icono y lo engancha solo (recomendado)")
    i.add_argument("proyecto", nargs="?", help="carpeta del proyecto (por defecto: la actual)")
    i.add_argument("--si", action="store_true", help="no preguntar nada: usar lo detectado")
    i.add_argument("--simulacro", action="store_true", help="enseña el plan y los cambios sin escribir nada")
    i.add_argument("--nombre", help="nombre de la aplicación (si no, se detecta)")
    i.add_argument("--simbolo", help="símbolo del catálogo (si no, se sugiere)")
    i.add_argument("--simbolo-svg", help="SVG de Lucide del que tomar el dibujo")
    i.add_argument("--trazado", help="fragmento SVG propio en lienzo 24x24")
    i.add_argument("--motivo", help="por qué ese símbolo")
    i.add_argument("--primario", help="color principal #rrggbb (si no, se busca en los tokens)")
    i.add_argument("--oscuro", help="color oscuro #rrggbb (si no, se busca en los tokens)")
    i.add_argument("--css", help="archivo de tokens concreto")
    i.add_argument("--sin-ventana", action="store_true",
                   help="si los colores no son esos, escribirlos en la terminal en vez de abrir la ventana")
    i.add_argument("--token-primario", default=TOKEN_PRIMARIO)
    i.add_argument("--token-oscuro", default=TOKEN_OSCURO)
    i.add_argument("--extra", help="detalle secundario en el lienzo 64x64")
    i.add_argument("--redondo", action="store_true", help="variante circular")
    i.add_argument("--destino", help="carpeta de imágenes, relativa al proyecto (si no, se elige sola)")
    i.add_argument("--prefijo", default=PREFIJO, help="nombre base propio de los archivos (sin palabra)")
    i.add_argument("--palabra", help="palabra para los nombres de los archivos (icono-16-PALABRA.png); "
                                     "por omisión, la primera del nombre de la aplicación")
    i.add_argument("--sin-ico", action="store_true", help="no generar favicon.ico")
    i.add_argument("--sobrescribir", action="store_true",
                   help="hacer un icono nuevo aunque ya exista uno (el anterior se respalda)")
    i.add_argument("--sin-enganchar", action="store_true", help="sólo crear los archivos, sin tocar plantillas")
    i.add_argument("--reemplazar-iconos", action="store_true",
                   help="sustituir los <link> de un icono anterior (con respaldo)")
    i.set_defaults(fn=orden_instalar)

    d = s.add_parser("detectar", help="enseña lo que la herramienta entiende del proyecto, sin tocar nada")
    d.add_argument("proyecto", nargs="?")
    d.set_defaults(fn=orden_detectar)

    u = s.add_parser("deshacer", help="deja el proyecto como estaba antes de la última instalación")
    u.add_argument("proyecto", nargs="?")
    u.add_argument("--forzar", action="store_true", help="restaurar aunque los archivos hayan cambiado después")
    u.set_defaults(fn=orden_deshacer)

    c = s.add_parser("instalar-comando",
                     help="instala el comando generate_icon para usarlo desde cualquier terminal")
    c.add_argument("--carpeta", help="dónde instalarlo (por defecto ~/.local/bin, o %%LOCALAPPDATA%%\\Programs en Windows)")
    c.add_argument("--si", action="store_true", help="no preguntar")
    c.set_defaults(fn=orden_instalar_comando)

    c = s.add_parser("desinstalar-comando", help="quita el comando generate_icon")
    c.add_argument("--carpeta")
    c.add_argument("--si", action="store_true", help="no preguntar")
    c.set_defaults(fn=orden_desinstalar_comando)


# ===========================================================================
#  Línea de órdenes
# ===========================================================================


def _argumentos():
    p = argparse.ArgumentParser(
        prog="generate_icon",
        description="Genera el icono de una aplicación (SVG maestro + PNG + favicon.ico) con la "
                    "composición de la casa. Sólo biblioteca estándar, sin red y sin IA.",
        epilog="Ejemplo: python3 generate_icon.py crear --nombre \"Inventario\" --simbolo caja "
               "--css public/css/tokens.css --destino public/img")
    p.add_argument("--version", action="version", version="%(prog)s " + VERSION)
    p.epilog = ("Sin argumentos (o con doble clic) abre el asistente, que detecta el proyecto y "
                "pone el icono solo. " + (p.epilog or ""))
    s = p.add_subparsers(dest="orden", metavar="ORDEN")
    s.required = True

    c = s.add_parser("crear", help="crea el SVG maestro y sus PNG")
    c.add_argument("--nombre", required=True, help="nombre de la aplicación (aria-label y comentario)")
    g = c.add_argument_group("símbolo (uno de los tres)")
    g.add_argument("--simbolo", help="nombre del catálogo (orden 'simbolos')")
    g.add_argument("--simbolo-svg", help="archivo SVG de Lucide (lienzo 24x24) del que tomar el dibujo")
    g.add_argument("--trazado", help="fragmento SVG en lienzo 24x24, p. ej. '<path d=\"M4 4h16\"/>'")
    c.add_argument("--motivo", help="por qué ese símbolo (una línea; queda en el comentario del SVG)")
    k = c.add_argument_group("colores (hex, o leídos de los tokens del sistema de diseño)")
    k.add_argument("--primario", help="principio del degradado: el color de acción (#rrggbb)")
    k.add_argument("--oscuro", help="final del degradado: el oscuro de estructura (#rrggbb)")
    k.add_argument("--css", help="CSS, tailwind.config o DESIGN-SYSTEM.md con los tokens")
    k.add_argument("--token-primario", default=TOKEN_PRIMARIO, help="token del primario (por defecto: primary)")
    k.add_argument("--token-oscuro", default=TOKEN_OSCURO, help="token del oscuro (por defecto: navy)")
    c.add_argument("--extra", help="detalle secundario en el lienzo 64x64, debajo del símbolo")
    c.add_argument("--redondo", action="store_true", help="variante circular para tarjetas que recortan en círculo")
    c.add_argument("--destino", required=True, help="carpeta de imágenes que el proyecto YA tiene")
    c.add_argument("--crear-carpeta", action="store_true", help="crea --destino si no existe")
    c.add_argument("--prefijo", default=PREFIJO, help="nombre base de los archivos (por defecto: icono)")
    c.add_argument("--palabra", help="palabra para los nombres (icono-16-PALABRA.png); por omisión, "
                                     "la primera de --nombre")
    c.add_argument("--tamanos", default=",".join(map(str, TAMANOS_PNG)), help="tamaños de los PNG")
    c.add_argument("--ico", action="store_true", help="genera también favicon.ico (16, 32 y 48 px)")
    c.add_argument("--ruta-web", help="ruta pública de la carpeta para las etiquetas <link>")
    c.add_argument("--sobrescribir", action="store_true", help="reemplaza un icono que ya existe")
    c.add_argument("--simulacro", action="store_true", help="enseña lo que haría sin escribir nada")
    c.set_defaults(fn=orden_crear)

    r = s.add_parser("rasterizar", help="regenera los PNG desde un SVG maestro (el SVG manda)")
    r.add_argument("objetivo", help="el SVG maestro o la carpeta que lo contiene")
    r.add_argument("--prefijo", default=PREFIJO, help="si 'objetivo' es carpeta: nombre del SVG sin extensión")
    r.add_argument("--destino", help="carpeta de salida (por defecto: la del SVG)")
    r.add_argument("--tamanos", default=",".join(map(str, TAMANOS_PNG)))
    r.add_argument("--ico", action="store_true", help="genera también favicon.ico")
    r.add_argument("--simulacro", action="store_true")
    r.set_defaults(fn=orden_rasterizar)

    v = s.add_parser("verificar", help="comprueba el SVG y los PNG (código de salida 1 si algo falla)")
    v.add_argument("objetivo", help="el SVG maestro o la carpeta que lo contiene")
    v.add_argument("--prefijo", default=PREFIJO)
    v.add_argument("--tamanos", default=",".join(map(str, TAMANOS_PNG)))
    v.add_argument("--url", help="URL pública de la carpeta, para comprobar que el servidor los entrega")
    v.add_argument("--esquinas-opacas", action="store_true", help="no exigir esquinas transparentes")
    v.set_defaults(fn=orden_verificar)

    w = s.add_parser("vista-previa", help="HTML para mirarlo a 160/64/32/16 px, en claro, oscuro y en tarjeta")
    w.add_argument("objetivo", help="el SVG maestro o la carpeta que lo contiene")
    w.add_argument("--prefijo", default=PREFIJO)
    w.add_argument("--comparar", nargs="*", help="otros iconos de la casa para comparar a 16 px")
    w.add_argument("--salida", help="dónde escribir el HTML (por defecto: carpeta temporal del sistema)")
    w.set_defaults(fn=orden_vista_previa)

    y = s.add_parser("simbolos", help="lista el catálogo de símbolos")
    y.add_argument("--muestrario", nargs="?", const=True, help="genera un HTML con todos dibujados")
    y.add_argument("--primario", default="#0369a1")
    y.add_argument("--oscuro", default="#0f172a")
    y.set_defaults(fn=orden_simbolos)

    _agregar_ordenes_instalacion(s)
    return p


def main(argv=None):
    _consola_segura()
    if sys.version_info < (3, 7):
        print("Hace falta Python 3.7 o superior.", file=sys.stderr)
        return 2
    args = list(sys.argv[1:] if argv is None else argv)
    # Doble clic (sin argumentos) o una carpeta arrastrada sobre el ejecutable:
    # se abre el asistente, que pregunta lo que no pueda deducir.
    asistente = not args or (len(args) == 1 and os.path.isdir(args[0]))
    if asistente:
        print("generate_icon %s · el icono de tu aplicación, sin internet ni IA\n" % VERSION)
        args = ["instalar"] + args
    try:
        return _ejecutar(args)
    finally:
        if asistente and (getattr(sys, "frozen", False) or os.name == "nt"):
            try:
                input("\nPulsa Enter para cerrar…")
            except (EOFError, KeyboardInterrupt):
                pass


def _ejecutar(args):
    a = _argumentos().parse_args(args)
    try:
        return a.fn(a)
    except ErrorIcono as e:
        print("Error: %s" % e, file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        return 130
    except BrokenPipeError:
        # La salida se cortó (p. ej. `| head`): se para sin traza, pero sin
        # fingir éxito, porque puede que no se hayan escrito todos los archivos.
        try:
            sys.stdout = open(os.devnull, "w")
        except OSError:
            pass
        return 1


if __name__ == "__main__":
    sys.exit(main())
