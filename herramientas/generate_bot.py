#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
generate_bot.py — CFloresBot, el asistente flotante de la casa, portable y sin IA.

Hace a mano lo que pide el agente `cflores-bot` (.claude/agents/CFloresBot.md):
pone el asistente de la casa, con el nombre que tú elijas —botón redondo abajo a la derecha que abre un panel de
chat con guía del sistema— con el mismo diseño, animaciones y comportamiento
que el de IntraNet RORI, y una base de conocimiento (menús y temas) escrita a
partir de lo que el código del proyecto dice: su menú, sus pantallas, sus
formularios, sus mensajes y sus permisos.

  * Un solo archivo y sólo la biblioteca estándar de Python 3.7+.
  * Sin IA y sin red: el bot tampoco usa IA ni servidor; responde con un guion.
  * El CSS y el motor JS se copian literales del agente. Sólo se adapta lo que
    el agente permite: CONFIG, TEMAS, MENUS, los tokens y el cableado.
  * Enseña el plan y pregunta antes de escribir. Guarda copia de lo que
    cambia en .generate_bot/ y `deshacer` lo deja todo como estaba.

Uso:
    python3 generate_bot.py              (Windows: py generate_bot.py)
    python3 generate_bot.py detectar     qué entiende del proyecto
    python3 generate_bot.py verificar    comprueba el bot puesto
    python3 generate_bot.py deshacer     vuelve atrás
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

VERSION = "1.0.0"
PREFIJO = "icono"


def _preguntar_obligatorio(texto, defecto=None):
    while True:
        r = (_preguntar(texto, defecto) or "").strip()
        if r:
            return r
        print("   Hace falta una respuesta.")


def explicar(titulo, que, ejemplo=None):
    print("\n%s" % titulo)
    print("   Qué va: %s" % que)
    if ejemplo:
        print("   Ejemplo: %s" % ejemplo)

# ===========================================================================
#  Utilidades generales
# ===========================================================================


class ErrorBot(Exception):
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
        raise ErrorBot(
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
        raise ErrorBot("No pude leer %s: %s" % (ruta, e))
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
#  Reconocer el proyecto: tipo, carpeta pública y plantillas con <head>
# ---------------------------------------------------------------------------
#  Todo lo que se escribe pasa por una transacción: antes de tocar un archivo
#  que ya existe se guarda una copia en `.generate_bot/respaldos/`, y
#  `deshacer` deja el proyecto como estaba. Nada se escribe sin enseñar antes
#  el plan, salvo con --si.
# ===========================================================================

DIRS_IGNORADOS = {
    "node_modules", "vendor", "dist", "build", "out", "target", "bin", "obj", "storage",
    "cache", "tmp", "temp", "logs", "coverage", "__pycache__", "venv", "env", "site-packages",
    "bower_components", "jspm_packages", "Pods", "DerivedData",
}
CARPETA_ESTADO = ".generate_bot"
MARCA_INI = "generate_bot:inicio"
MARCA_FIN = "generate_bot:fin"

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

    Portable (el .py copiado dentro del proyecto): `python3 ruta/generate_bot.py`.
    Compilada: `generate_bot`.
    """
    if getattr(sys, "frozen", False) or _PROPIO.suffix.lower() != ".py":
        base = "generate_bot"
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
    raise ErrorBot(
        "No encuentro ningún proyecto en %s ni en las carpetas de encima. Copia generate_bot.py "
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
        raise ErrorBot("La carpeta del proyecto %s no existe." % raiz)
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
#  Este bloque es idéntico en generate_icon.py, generate_readme.py, generate_loader.py y generate_bot.py: cada
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
        tmp = ruta.with_name(ruta.name + ".generate_bot.tmp")
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
        raise ErrorBot("No hay nadie para responder a las preguntas, así que no se ha escrito nada. "
                         "Para usarlo sin preguntas, añade --si.")
    return r or defecto


def _si_no(texto, defecto=False):
    r = _preguntar(texto + (" [S/n]" if defecto else " [s/N]"))
    return defecto if not r else _sin_tildes(r).startswith(("s", "y"))


def _pedir_hex(texto, defecto=None):
    while True:
        r = _preguntar(texto, defecto)
        try:
            return normalizar_hex(r or "", texto)
        except ErrorBot:
            print("  Escríbelo en hexadecimal, por ejemplo #0369a1.")


def orden_deshacer(a):
    raiz = Path(a.proyecto).resolve() if a.proyecto else raiz_del_proyecto()
    ruta_man = raiz / CARPETA_ESTADO / "ultimo.json"
    if not ruta_man.is_file():
        raise ErrorBot("No hay ninguna instalación que deshacer en %s." % raiz)
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




_RE_VAR = re.compile(r"--([A-Za-z0-9_-]+)\s*:\s*([^;{}]+)")


_RE_OSCURO = [
    (r"\[data-theme=[\"']?dark[\"']?\]", '[data-theme="dark"]'),
    (r"\[data-bs-theme=[\"']?dark[\"']?\]", '[data-bs-theme="dark"]'),
    (r"\[data-mode=[\"']?dark[\"']?\]", '[data-mode="dark"]'),
    (r"(?<![\w-])\.dark(?=[\s{,.:]|$)", ".dark"),
    (r"(?<![\w-])\.theme-dark(?=[\s{,.:]|$)", ".theme-dark"),
    (r"(?<![\w-])\.dark-mode(?=[\s{,.:]|$)", ".dark-mode"),
    (r"(?<![\w-])\.modo-oscuro(?=[\s{,.:]|$)", ".modo-oscuro"),
    (r"prefers-color-scheme\s*:\s*dark", "@media"),
]


class Estilos:
    """Las hojas de estilo propias del proyecto (sin librerías) y lo que se lee en ellas."""

    def __init__(self, p):
        self.p = p
        self.hojas = [f for f in _archivos(p.raiz, (".css", ".scss", ".sass", ".less"))
                      if f.name not in (NOMBRE_CSS,) and FIRMA not in _texto(f, 300000)[:600]]
        self.vars = {}          # nombre -> (valor, archivo)
        self.oscuro = {}        # nombre -> valor bajo el selector oscuro
        self.selectores = []    # selectores del tema oscuro que usa el proyecto
        for f in self.hojas:
            t = re.sub(r"/\*[\s\S]*?\*/", "", _texto(f, 1500000))
            for patron, sel in _RE_OSCURO:
                if re.search(patron, t) and sel not in self.selectores:
                    self.selectores.append(sel)
            for bloque in re.finditer(r"([^{}]+)\{([^{}]*)\}", t):
                cab, cuerpo = bloque.group(1), bloque.group(2)
                es_oscuro = any(re.search(pt, cab) for pt, _s in _RE_OSCURO[:-1]) or (
                    "prefers-color-scheme" in t[max(0, bloque.start() - 200):bloque.start()]
                    and re.search(r"prefers-color-scheme\s*:\s*dark", t[max(0, bloque.start() - 200):bloque.start()]))
                for m in _RE_VAR.finditer(cuerpo):
                    nombre, valor = m.group(1).lower(), m.group(2).strip()
                    if es_oscuro:
                        self.oscuro.setdefault(nombre, valor)
                    else:
                        self.vars.setdefault(nombre, (valor, _rel(p.raiz, f)))
        self.poppins = any("poppins" in _texto(f, 300000).lower() for f in self.hojas) or any(
            "poppins" in _texto(pl, 300000).lower() for pl in p.plantillas)
        self.hidden_global = [_rel(p.raiz, f) for f in self.hojas
                              if re.search(r"(^|[\s,}])\.hidden\s*[{,]", _texto(f, 1500000))]

    def primero(self, nombres):
        for n in nombres:
            if n in self.vars:
                return n, self.vars[n][0], self.vars[n][1]
        return None

    def valor_hex(self, nombre, prof=0):
        """El color de una variable, resolviendo var(--otra)."""
        v = self.vars.get(nombre, ("", ""))[0]
        m = re.match(r"var\(\s*--([\w-]+)", v)
        if m and prof < 5:
            return self.valor_hex(m.group(1).lower(), prof + 1)
        return _a_hex(v) if v else None


def _carpeta_de(p, extension, preferidas):
    """La carpeta servida que ya guarda los CSS (o los JS) del proyecto. No se inventa ninguna."""
    base = p.publico if p.publico.is_dir() else p.raiz
    cuenta = {}
    for f in _archivos(base, (extension,)):
        if f.name in (NOMBRE_CSS, NOMBRE_JS):
            continue
        rel = _rel(base, f.parent)
        if re.search(r"(^|/)(src|node_modules|vendor|tests?|config|\.)", rel) and base == p.raiz:
            continue
        cuenta[f.parent] = cuenta.get(f.parent, 0) + 1
    for nombre in preferidas:
        if (base / nombre).is_dir() and (base / nombre) in cuenta:
            return base / nombre
    if cuenta:
        return max(cuenta, key=lambda d: (cuenta[d], -len(d.parts)))
    for nombre in preferidas:
        if (base / nombre).is_dir():
            return base / nombre
    return None     # el proyecto no tiene: se pregunta, no se inventa


def _carpeta_o_preguntar(p, que, extension, preferidas, hermana, interactivo):
    """La carpeta de los CSS (o de los JS). Si el proyecto no tiene ninguna, se pregunta."""
    d = _carpeta_de(p, extension, preferidas)
    if d:
        return d
    base = p.publico if p.publico.is_dir() else p.raiz
    propuesta = (hermana.parent / ("css" if extension == ".css" else "js")) if hermana else \
        next((base / x for x in ("vistas", "views", "assets", "static") if (base / x).is_dir()), base) / \
        ("css" if extension == ".css" else "js")
    if not interactivo:
        raise ErrorBot("El proyecto no tiene carpeta de %s. Indícala con --%s (por ejemplo --%s %s)."
                          % (que, extension[1:], extension[1:], _rel(p.raiz, propuesta)))
    explicar("Carpeta de los %s" % que,
             "El proyecto no tiene ninguna carpeta con archivos %s. Dime dónde poner el del bot "
             "(relativa al proyecto; tiene que ser una carpeta que el servidor publique)." % extension,
             "«%s»" % _rel(p.raiz, propuesta))
    r = (_preguntar("   Carpeta", _rel(p.raiz, propuesta)) or "").strip().strip("/\\")
    return (p.raiz / r).resolve()


CARPETAS_CSS = ["css", "styles", "estilos", "assets/css", "static/css", "dist/css", "dist/assets/css",
                "vistas/css", "vistas/dist/assets/css", "views/css", "public/css", "resources/css"]


CARPETAS_JS = ["js", "scripts", "assets/js", "static/js", "dist/js", "dist/assets/js", "vistas/js",
               "views/js", "public/js"]


def _imitar_enlace(p, plantilla, texto, destino, css):
    """Si la plantilla enlaza sus recursos con una función propia (recurso('…'), asset('…'),
    versión con la fecha…), el enlace nuevo se escribe igual. None si no hay nada que imitar."""
    etiqueta = r"<link\b[^>]*\bhref=([\"'])(.*?)\1[^>]*>" if css else r"<script\b[^>]*\bsrc=([\"'])(.*?)\1[^>]*>"
    for m in re.finditer(etiqueta, texto, re.I | re.S):
        valor = m.group(2)
        if css and "stylesheet" not in m.group(0).lower():
            continue
        if not re.search(r"<\?|\{\{|\{%|@", valor):
            continue
        interior = re.search(r"([\"'])([^\"']+\.%s)(\?[^\"']*)?\1" % ("css" if css else "js"), valor)
        if not interior:
            continue
        ruta = interior.group(2)
        for base in (p.publico, p.raiz, plantilla.parent):
            if (base / ruta).is_file():
                nueva = _rel(base, destino)
                return ('href="%s"' if css else 'src="%s"') % valor.replace(ruta, nueva, 1)
    return None



# ===========================================================================
#  Las pantallas del proyecto (las mismas piezas que generate_manual.py)
# ===========================================================================

_EXT_VISTAS = (".php", ".html", ".htm", ".twig", ".jinja", ".jinja2", ".j2", ".ejs", ".hbs", ".handlebars",
               ".vue", ".svelte", ".jsx", ".tsx", ".cshtml", ".razor", ".erb", ".jsp", ".astro")


_NO_SON_PANTALLAS = re.compile(r"(^|/)(errors?|emails?|mail|layouts?|partials?|components?|includes?|inc|"
                               r"vendor|node_modules|tests?|migrations?|config)(/|$)|(^|/)_|welcome_message|"
                               r"(header|footer|sidebar|topbar|navbar|menu|nav|head|layout|base|app)\.", re.I)


_ICONOS_ACCION = [(r"pen|edit|pencil|modificar", "modificar (el lápiz)"),
                  (r"trash|minus|delete|remove|eliminar|borrar|times-circle|xmark", "eliminar (la papelera)"),
                  (r"eye|view|ver\b|show", "ver"), (r"print|imprimir", "imprimir"),
                  (r"download|descargar", "descargar"), (r"qr", "ver el código QR")]


_BOTONES_NEUTROS = re.compile(r"^(cerrar|close|cancelar|cancel|x|×|volver|back|no|ok)$", re.I)


def _limpio(html):
    """Texto visible de un trozo de plantilla: sin código, sin etiquetas y sin espacios de más."""
    t = re.sub(r"\[\[[\s\S]*?\]\]|<\?(?:php|=)?[\s\S]*?\?>|\{\{[\s\S]*?\}\}|\{%[\s\S]*?%\}|\{#[\s\S]*?#\}|<%[\s\S]*?%>|"
               r"@\w+(\([^)]*\))?|\{[^{}]*\}", " ", html)
    t = re.sub(r"<(script|style)[\s\S]*?</\1>|<!--[\s\S]*?-->|<[^>]+>", " ", t)
    for a, b in (("&nbsp;", " "), ("&amp;", "&"), ("&times;", "×"), ("&lt;", "<"), ("&gt;", ">"),
                 ("&quot;", '"'), ("&#39;", "'"), ("&aacute;", "á"), ("&eacute;", "é"), ("&iacute;", "í"),
                 ("&oacute;", "ó"), ("&uacute;", "ú"), ("&ntilde;", "ñ")):
        t = t.replace(a, b)
    t = re.sub(r"\(\s*[\w ]*:?\s*\)", " ", re.sub(r"\s+", " ", t))
    return re.sub(r"\s+", " ", t).strip(" :")


def _frase(t):
    """«LISTA DE ESTUDIANTES» -> «Lista de estudiantes». Lo que no está en mayúsculas se deja."""
    t = t.strip()
    if t and t.upper() == t and re.search(r"[A-ZÁÉÍÓÚÑ]{3}", t):
        t = t[:1] + t[1:].lower()
    return t


def _lista_y(cosas):
    cosas = [c for c in dict.fromkeys(cosas) if c]
    return cosas[0] if len(cosas) == 1 else ", ".join(cosas[:-1]) + " y " + cosas[-1] if cosas else ""


def _enmascarar(html):
    """El código de plantilla dentro de las etiquetas («href="<?= base_url('x') ?>"») rompe la lectura del HTML:
    se cambia por [[…]] sin < > ni comillas, y así cada etiqueta se lee entera."""
    def cambio(m):
        return "[[" + m.group(1).replace(">", " ").replace("<", " ").replace('"', "'") + "]]"
    return re.sub(r"<\?(?:php|=)?([\s\S]*?)\?>", cambio, html)


def analizar_pantalla(html):
    """Lo que ve el usuario en una plantilla: título, columnas, botones, formularios (con cada campo: tipo,
    si es obligatorio y sus opciones), confirmaciones, mensajes y si la lista tiene buscador."""
    limpio = re.sub(r"<!--[\s\S]*?-->|<script[\s\S]*?</script>|<style[\s\S]*?</style>", " ", _enmascarar(html))
    p = {"titulo": "", "columnas": [], "acciones": [], "iconos": [], "formularios": [], "confirmaciones": [],
         "enlaces": [], "vinculos": [], "mensajes": [], "buscador": False, "ayuda": "", "pestana": set()}
    for m in re.finditer(r"<h([1-4])\b[^>]*>([\s\S]*?)</h\1>", limpio):
        t = _frase(_limpio(m.group(2)))
        if 2 < len(t) < 80:
            p["titulo"] = t
            break
    # Un texto de ayuda que la propia pantalla enseña («Aquí puedes ver el listado…»)
    m = re.search(r"<(?:div|p|small|span)\b[^>]*class=[\"'][^\"']*\b(?:info-msg|ayuda|help|descripcion|description|"
                  r"intro)\b[^\"']*[\"'][^>]*>([\s\S]{8,400}?)</", limpio)
    if m and 8 < len(_limpio(m.group(1))) < 300 and len(_limpio(m.group(1)).split()) >= 4:
        p["ayuda"] = _limpio(m.group(1))
    p["columnas"] = [c for c in (_frase(_limpio(m.group(1))) for m in re.finditer(r"<th\b[^>]*>([\s\S]*?)</th>", limpio))
                     if c and len(c) < 40]
    p["buscador"] = bool(re.search(r"\.DataTable\(|dataTable\(|class=[\"'][^\"']*\bdatatable|type=[\"']search", html, re.I))
    for m in re.finditer(r"<(a|button)\b([^>]*)>([\s\S]*?)</\1>", limpio):
        attrs, texto = m.group(2), _limpio(m.group(3))
        if m.group(1) == "a" and texto and len(texto) < 60:
            p["vinculos"].append(_frase(texto))
        if "data-dismiss" in attrs or "data-bs-dismiss" in attrs or (texto and _BOTONES_NEUTROS.match(texto)):
            continue
        es_boton = m.group(1) == "button" or re.search(r"class=[\"'][^\"']*\bbtn\b", attrs)
        if not es_boton:
            continue
        if re.search(r"type=[\"']submit", attrs):
            continue    # los de enviar van con su formulario
        if texto and len(texto) < 40:
            p["acciones"].append(_frase(texto))
            href = re.search(r"href=([\"'])(.+?)\1", attrs)
            if href:
                p["enlaces"].append((_frase(texto), href.group(2)))
            if re.search(r"target=[\"']_blank", attrs):
                p["pestana"].add(_frase(texto))
        elif not texto:
            for patron, nombre in _ICONOS_ACCION:
                if re.search(patron, attrs + m.group(3), re.I):
                    p["iconos"].append(nombre)
                    break
    p["confirmaciones"] = list(dict.fromkeys(
        m.group(2) for m in re.finditer(r"confirm\(\s*([\"'])(.+?)\1", html) if len(m.group(2)) < 120))
    p["confirmaciones"] += [m.group(2) for m in re.finditer(r"title\s*:\s*([\"'])(¿[^\"']+\?)\1", html)]
    p["mensajes"] = mensajes_en(html)
    for m in re.finditer(r"<form\b[^>]*>([\s\S]*?)</form>", limpio):
        cuerpo = m.group(1)
        por_id = {x.group(2): _limpio(x.group(3)) for x in
                  re.finditer(r"<label\b[^>]*\bfor=([\"'])([^\"']+)\1[^>]*>([\s\S]*?)</label>", cuerpo)}
        detalles = []
        for c in re.finditer(r"<(input|select|textarea)\b([^>]*)>", cuerpo):
            etiqueta, a = c.group(1), c.group(2)
            if re.search(r"type=[\"'](hidden|submit|button|reset)[\"']|\bhidden\b", a) or \
                    re.search(r"<div\b[^>]*\shidden\b[^>]*>\s*$", cuerpo[max(0, c.start() - 300):c.start()]):
                continue
            atr = lambda n: (re.search(r"\b%s=([\"'])(.*?)\1" % n, a) or [None, None, ""])[2]   # noqa: E731
            ph = atr("placeholder") or atr("aria-label")
            nombre = por_id.get(atr("id"), "")
            if not nombre and ph and "[[" not in ph:
                nombre = ph
            if not nombre:
                cerca = re.findall(r"<(?:h[1-6]|label|span|p|strong|b|div)\b[^>]*>([^<]{2,40})</",
                                   cuerpo[max(0, c.start() - 400):c.start()])
                nombre = cerca[-1] if cerca and _limpio(cerca[-1]) else (atr("title") if "[[" not in atr("title") else "")
            nombre = _frase(_limpio(nombre)).rstrip(" *")
            if not nombre:
                continue
            tipo = (atr("type") or ("lista" if etiqueta == "select" else "texto largo" if etiqueta == "textarea"
                                    else "text")).lower()
            opciones = []
            if etiqueta == "select":
                fin = cuerpo.find("</select>", c.end())
                for o in re.findall(r"<option\b[^>]*>([\s\S]*?)</option>", cuerpo[c.end():fin if fin > 0 else c.end()]):
                    o = _limpio(o)
                    if o and not re.match(r"^(selec|elij|escoj|choose|select|--)", _sin_tildes(o)) and "[[" not in o:
                        opciones.append(o)
            detalles.append({"nombre": nombre, "name": atr("name"), "tipo": tipo, "obligatorio": bool(
                re.search(r"\brequired\b", a)), "opciones": opciones[:12],
                "ejemplo": ph if ph and _sin_tildes(ph) != _sin_tildes(nombre) and "[[" not in ph else "",
                "max": atr("maxlength"), "min_n": atr("min"), "max_n": atr("max")})
        boton = ""
        for b in re.finditer(r"<button\b([^>]*)>([\s\S]*?)</button>|<input\b([^>]*type=[\"']submit[\"'][^>]*)>", cuerpo):
            if b.group(1) is not None and ("dismiss" in b.group(1) or _BOTONES_NEUTROS.match(_limpio(b.group(2)) or "x")):
                continue
            boton = _limpio(b.group(2)) if b.group(1) is not None else \
                (re.search(r"value=[\"']([^\"']+)", b.group(3)) or [None, ""])[1]
            if boton:
                break
        antes = limpio[max(0, m.start() - 1500):m.start()]
        titulos = re.findall(r"<(?:h[1-6]|legend)\b[^>]*>([\s\S]*?)</(?:h[1-6]|legend)>", antes)
        titulo = _frase(_limpio(titulos[-1])) if titulos else ""
        vistos, unicos = set(), []
        for d in detalles:
            if d["nombre"] not in vistos:
                vistos.add(d["nombre"])
                unicos.append(d)
        if unicos or boton:
            p["formularios"].append({"titulo": titulo, "campos": [d["nombre"] for d in unicos], "detalles": unicos,
                                     "boton": _frase(boton)})
    p["acciones"] = list(dict.fromkeys(p["acciones"]))
    p["iconos"] = list(dict.fromkeys(p["iconos"]))
    return p


_RE_MENSAJE = re.compile(
    r"setFlashdata\(\s*['\"](\w+)['\"]\s*,\s*(['\"])(.{6,160}?)\2"
    r"|->with\(\s*['\"](\w+)['\"]\s*,\s*(['\"])(.{6,160}?)\5"
    r"|\b(alert)\(\s*(['\"`])(.{6,160}?)\8"
    r"|Swal\.fire\(\s*(['\"`])(.{6,160}?)\10"
    r"|\b(?:title|text)\s*:\s*(['\"`])(.{6,160}?)\12"
    r"|toastr\.(\w+)\(\s*(['\"`])(.{6,160}?)\15"
    r"|['\"](mensaje|message|msg|error|success|exito)['\"]\s*=>\s*(['\"])(.{6,160}?)\18", re.S)


def mensajes_en(texto):
    """[(mensaje, tipo)] que el código enseña al usuario: avisos, confirmaciones, alertas."""
    out = []
    for m in _RE_MENSAJE.finditer(texto):
        g = m.groups()
        clave, msg = next(((g[i], g[i + 2]) for i in (0, 3, 6, 13, 16) if g[i + 2]), (None, None))
        if msg is None:
            msg = g[10] or g[12]
            clave = "aviso"
        if not msg or re.search(r"\$\{|\$\w|<\?|\{\{|\+\s*\w|\w+\s*\+|^\s*¿", msg) or len(_limpio(msg)) < 6:
            continue
        msg = _limpio(msg)
        k = _sin_tildes(clave or "")
        tipo = "Error" if re.search(r"error|fail|danger|warn|invalid", k) else \
            "Confirmación" if re.search(r"success|exito|ok|info|mensaje|message|msg", k) else "Aviso"
        if re.search(r"\b(error|no se pudo|no existe|incorrect|invalid|fall)", _sin_tildes(msg)):
            tipo = "Error"
        out.append((msg, tipo))
    return list(dict.fromkeys(out))[:15]


def _segmento(href):
    """La ruta a la que apunta un enlace de plantilla: base_url('salas') -> salas."""
    m = re.search(r"(?:base_url|site_url|url|route|asset|path|url_for)\(\s*['\"]([^'\"]*)", href) or \
        re.search(r"\{%\s*url\s+['\"]([^'\"]+)", href)
    ruta = m.group(1) if m else re.sub(r"<\?[\s\S]*?\?>|\{\{[\s\S]*?\}\}", "", href)
    ruta = ruta.split("?")[0].split("#")[0].strip("/ ")
    if re.match(r"^(https?:|mailto:|tel:|javascript:)", ruta) or not ruta:
        return ""
    return re.sub(r"\.(php|html?)$", "", ruta)


def _parecido(a, b):
    import difflib
    a, b = _sin_tildes(a).replace("-", "").replace("_", ""), _sin_tildes(b).replace("-", "").replace("_", "")
    for x in (a, a.rstrip("s"), a[:-2] if a.endswith("es") else a):
        if x == b or x == b.rstrip("s"):
            return 1.0
    return difflib.SequenceMatcher(None, a, b).ratio()


class Pantallas:
    """Las plantillas del proyecto, el menú y qué pantalla abre cada opción."""

    def __init__(self, p):
        self.p = p
        self.vistas = [f for f in _archivos(p.raiz, _EXT_VISTAS)
                       if f.resolve() != _PROPIO and re.search(r"<(form|table|h[1-4]|nav|button)\b", _texto(f, 400000))
                       and not f.name.startswith("generate_")]
        self.rutas = self._rutas()
        self.todas = list(_archivos(p.raiz, _EXT_VISTAS))
        self.archivo_menu = None

    def _rutas(self):
        """{segmento: (controlador, método)} de CodeIgniter y Laravel: para saber qué vista abre cada enlace."""
        out = {}
        for f in (self.p.raiz / "app/Config/Routes.php", self.p.raiz / "routes/web.php"):
            for m in re.finditer(r"(?:\$routes->|Route::)(?:get|match|add|any)\(\s*['\"]/?([^'\"]*)['\"]\s*,\s*"
                                 r"(?:['\"]\\?([\w\\]+)::(\w+)|\[\s*([\w\\]+)::class\s*,\s*['\"](\w+))", _texto(f)):
                ctl, met = (m.group(2), m.group(3)) if m.group(2) else (m.group(4), m.group(5))
                out.setdefault(m.group(1).strip("/"), (ctl.split("\\")[-1], met))
            for m in re.finditer(r"Route::view\(\s*['\"]/?([^'\"]*)['\"]\s*,\s*['\"]([^'\"]+)", _texto(f)):
                out.setdefault(m.group(1).strip("/"), ("", m.group(2)))
        return out

    def menu(self):
        """[(texto, segmento, solo_con_permiso)] del menú principal, en su orden."""
        candidatos = []
        for f in self.vistas + [x for x in _archivos(self.p.raiz, _EXT_VISTAS) if x not in self.vistas]:
            t = _texto(f, 400000)
            if re.search(r"(sidebar|menu|nav|header|topbar|layout|base)", f.stem, re.I) or "<nav" in t:
                candidatos.append((f, t))
        mejor = []
        for f, t in candidatos:
            t = _enmascarar(t)
            zona = t
            m = re.search(r"<nav\b[\s\S]*?</nav>", t)
            if m and not re.search(r"sidebar|menu", f.stem, re.I):
                zona = m.group(0)
            items = []
            for a in re.finditer(r"<a\b([^>]*)>([\s\S]*?)</a>", zona):
                href = re.search(r"href=([\"'])(.*?)\1", a.group(1))
                texto = _frase(_limpio(a.group(2)))
                seg = _segmento(href.group(2)) if href else ""
                if not texto or not seg or len(texto) > 30 or re.search(r"logout|salir|login|perfil|profile", seg, re.I):
                    continue
                previo = zona[max(0, a.start() - 400):a.start()]
                abiertos = previo.rfind("if") > max(previo.rfind("endif"), previo.rfind("}]]"), previo.rfind("} ]]"),
                                                    previo.rfind("{% endif"), previo.rfind("@endif"))
                permiso = bool(re.search(r"(if|@can|@role|\{%\s*if)[^\n]*(cargo|rol|role|admin|perm|can|user|is_)",
                                         previo[previo.rfind("if") - 5:] if abiertos else ""))
                items.append((texto, seg, permiso))
            items = list({(t, s): (t, s, pm) for t, s, pm in items}.values())
            if len(items) > len(mejor):
                mejor = items
                self.archivo_menu = f
        return mejor[:14]

    def vista_de(self, segmento):
        """La plantilla que se ve al abrir esa ruta, o None si no se puede saber con seguridad."""
        if not segmento:
            return None
        ruta = self.rutas.get(segmento)
        if ruta:
            ctl, met = ruta
            if not ctl:
                return self._vista_por_nombre(met.replace(".", "/"))
            for f in _archivos(self.p.raiz, (".php",)):
                if f.stem == ctl:
                    t = _texto(f)
                    m = re.search(r"function\s+%s\s*\([\s\S]*?(?=\n\s*(?:public|private|protected)\s+function|\Z)" % met, t)
                    v = re.search(r"view\(\s*['\"]([^'\"]+)", m.group(0) if m else "")
                    if v:
                        return self._vista_por_nombre(v.group(1).replace(".", "/"))
        mejor, nota = None, 0.0
        ultimo = segmento.split("/")[-1]
        for f in self.vistas:
            n = _parecido(ultimo, f.stem.split(".")[0])
            if n > nota:
                mejor, nota = f, n
        return mejor if nota >= 0.8 else None

    def _vista_por_nombre(self, nombre):
        for f in self.vistas:
            rel = _rel(self.p.raiz, f)
            if re.sub(r"\.(blade\.php|html\.twig|php|html|twig)$", "", rel).endswith(nombre):
                return f
        return None

    def entrada(self):
        """La pantalla para entrar (login), si la hay."""
        for f in self.vistas:
            if re.search(r"login|signin|sign-in|ingres|acceso|iniciar", f.stem, re.I) and "<form" in _texto(f):
                return f
        return None

    def sueltas(self):
        """Sin menú: las pantallas que tienen algo que hacer (formularios o listas)."""
        out = []
        for f in self.vistas:
            if _NO_SON_PANTALLAS.search(_rel(self.p.raiz, f)):
                continue
            a = analizar_pantalla(_texto(f, 400000))
            if a["titulo"] and (a["formularios"] or a["columnas"]):
                out.append((a["titulo"], f))
        return out[:12]


def _codigo_del_modulo(p, pan, segmento):
    """El texto del controlador que atiende esa opción del menú (para sus mensajes y validaciones)."""
    ruta = pan.rutas.get(segmento)
    if not ruta or not ruta[0]:
        return ""
    for f in _archivos(p.raiz, (".php",)):
        if f.stem == ruta[0]:
            return _texto(f)
    return ""




TOKENS_CSS = r"""/* Tokens de CFloresBot (valores originales de IntraNet RORI) */
:root {
    --font-sans: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    --fs-xs: 0.75rem;
    --fs-sm: 0.8125rem;
    --fs-md: 1rem;
    --sp-2: 8px;
    --r-sm: 6px;
    --r-lg: 14px;
    --r-xl: 20px;
    --r-full: 999px;
    --t-fast: 140ms cubic-bezier(0.4, 0, 0.2, 1);
    --t-base: 220ms cubic-bezier(0.4, 0, 0.2, 1);
    --t-slow: 380ms cubic-bezier(0.16, 1, 0.3, 1);
    --z-panel: 80;

    --bg-primary: #f1f5f9;
    --bg-subtle: #f8fafc;
    --text-primary: #0f172a;
    --text-secondary: #64748b;
    --text-muted: #94a3b8;
    --border-color: #e2e8f0;
    --card-bg: #ffffff;
    --hover-bg: #f1f5f9;
    --accent-color: #1d4ed8;
    --accent-rgb: 29, 78, 216;
    --accent-light: #dbeafe;
    --success: #059669;
    --scroll-thumb: #cbd5e1;
    --shadow: 0 4px 12px rgba(15, 23, 42, 0.07), 0 1px 3px rgba(15, 23, 42, 0.05);
    --shadow-lg: 0 12px 32px rgba(15, 23, 42, 0.11), 0 4px 8px rgba(15, 23, 42, 0.05);
    --shadow-accent: 0 6px 18px rgba(29, 78, 216, 0.24);
    --brand-gradient: linear-gradient(135deg, #1d4ed8, #0ea5e9);
}

/* Oscuro: engánchalo al mecanismo de tema oscuro del proyecto
   (clase en body, [data-theme="dark"], .dark de Tailwind o prefers-color-scheme). */
body.theme-dark {
    --bg-primary: #0b1120;
    --bg-subtle: #161f2e;
    --text-primary: #e8eef7;
    --text-secondary: #94a3b8;
    --text-muted: #64748b;
    --border-color: #23304a;
    --card-bg: #131c2b;
    --hover-bg: #1c2740;
    --accent-color: #4f8dfb;
    --accent-rgb: 79, 141, 251;
    --accent-light: #17264a;
    --success: #34d399;
    --scroll-thumb: #2c3a55;
    --shadow: 0 4px 14px rgba(0, 0, 0, 0.55);
    --shadow-lg: 0 16px 40px rgba(0, 0, 0, 0.65);
    --shadow-accent: 0 6px 18px rgba(79, 141, 251, 0.3);
    --brand-gradient: linear-gradient(135deg, #4f8dfb, #22d3ee);
}

/* Solo si el proyecto no la tiene ya. */
.asistente .sr-only {
    position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px;
    overflow: hidden; clip: rect(0, 0, 0, 0); white-space: nowrap; border: 0;
}
"""

CSS_BOT = r"""/* ==========================================================================
   Asistente flotante (CFloresBot)

   Usa los tokens del sistema de diseño, asi que sigue al tema activo sin
   reglas propias para claro y oscuro salvo donde hace falta mas contraste.
   ========================================================================== */

.asistente {
    position: fixed;
    right: 24px;
    bottom: 24px;
    z-index: var(--z-panel, 80);
    display: flex;
    flex-direction: column;
    align-items: flex-end;
    gap: 14px;
    font-family: var(--font-sans);
}

/* --------------------------------------------------------------------------
   Boton flotante
   -------------------------------------------------------------------------- */

.asis-fab {
    position: relative;
    width: 62px;
    height: 62px;
    padding: 0;
    border: 0;
    border-radius: 50%;
    cursor: pointer;
    background: var(--brand-gradient, linear-gradient(135deg, #1d4ed8, #22d3ee));
    box-shadow: var(--shadow-lg);
    display: flex;
    align-items: center;
    justify-content: center;
    transition: transform var(--t-base), box-shadow var(--t-base);
    order: 2;
}

.asis-fab:hover,
.asis-fab:focus-visible {
    transform: translateY(-3px) scale(1.04);
    box-shadow: var(--shadow-lg), var(--shadow-accent);
}

.asis-fab:active { transform: translateY(0) scale(0.98); }

/* La cara va sobre el degradado: quedan 3px de aro enmarcando la foto. */
.asis-fab-cara {
    position: relative;
    z-index: 1;
    width: 56px;
    height: 56px;
    border-radius: 50%;
    overflow: hidden;
    background: var(--card-bg);
    color: var(--accent-color);
    display: flex;
    align-items: center;
    justify-content: center;
    font-weight: 700;
    font-size: 1.05rem;
}

.asis-fab-cara img {
    width: 100%;
    height: 100%;
    object-fit: cover;
    display: block;
}

/* Punto verde de "en linea". */
.asis-fab-punto {
    position: absolute;
    z-index: 2;
    right: 3px;
    bottom: 3px;
    width: 14px;
    height: 14px;
    border-radius: 50%;
    background: var(--success, #10b981);
    border: 2.5px solid var(--card-bg);
}

/* Aro que late para que se note sin llegar a molestar. */
.asis-fab-aro {
    position: absolute;
    inset: -4px;
    border-radius: 50%;
    border: 2px solid var(--accent-color);
    opacity: 0;
    animation: asis-latido 2.8s ease-out infinite;
}

@keyframes asis-latido {
    0%   { transform: scale(0.94); opacity: 0.55; }
    70%  { transform: scale(1.25); opacity: 0; }
    100% { transform: scale(1.25); opacity: 0; }
}

/* Con el panel abierto el boton deja de llamar la atencion. */
.asistente.abierto .asis-fab-aro { animation: none; }
.asistente.abierto .asis-fab-globo { display: none; }

.asis-fab-globo {
    position: absolute;
    right: calc(100% + 12px);
    top: 50%;
    transform: translateY(-50%);
    white-space: nowrap;
    padding: 8px 14px;
    border-radius: var(--r-full);
    background: var(--card-bg);
    color: var(--text-primary);
    border: 1px solid var(--border-color);
    box-shadow: var(--shadow);
    font-size: var(--fs-sm);
    font-weight: 600;
    opacity: 0;
    pointer-events: none;
    transition: opacity var(--t-fast), transform var(--t-fast);
}

.asis-fab:hover .asis-fab-globo,
.asis-fab:focus-visible .asis-fab-globo {
    opacity: 1;
    transform: translateY(-50%) translateX(-4px);
}

/* --------------------------------------------------------------------------
   Panel
   -------------------------------------------------------------------------- */

.asis-panel {
    order: 1;
    width: 380px;
    max-width: calc(100vw - 32px);
    height: 560px;
    max-height: calc(100vh - 130px);
    display: flex;
    flex-direction: column;
    overflow: hidden;
    background: var(--card-bg);
    border: 1px solid var(--border-color);
    border-radius: var(--r-xl);
    box-shadow: var(--shadow-lg);
    transform-origin: bottom right;
    animation: asis-entrar var(--t-slow) both;
}

/* El display:flex de arriba gana al display:none que el navegador le da a
   [hidden], asi que sin esta regla el panel sale abierto y la X no lo cierra. */
.asis-panel[hidden] { display: none; }

@keyframes asis-entrar {
    from { opacity: 0; transform: translateY(16px) scale(0.96); }
    to   { opacity: 1; transform: translateY(0) scale(1); }
}

.asis-cabecera {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 14px 12px 14px 16px;
    background: var(--brand-gradient, linear-gradient(135deg, #1d4ed8, #22d3ee));
    color: #fff;
}

.asis-cabecera-cara {
    width: 42px;
    height: 42px;
    flex-shrink: 0;
    border-radius: 50%;
    overflow: hidden;
    background: rgba(255, 255, 255, 0.2);
    border: 2px solid rgba(255, 255, 255, 0.55);
    display: flex;
    align-items: center;
    justify-content: center;
    font-weight: 700;
    font-size: 0.9rem;
}

.asis-cabecera-cara img { width: 100%; height: 100%; object-fit: cover; }

.asis-cabecera-texto { flex: 1; min-width: 0; }

.asis-cabecera-texto h3 {
    margin: 0;
    font-size: var(--fs-md);
    font-weight: 700;
    color: #fff;
}

.asis-cabecera-texto p {
    display: flex;
    align-items: center;
    gap: 6px;
    margin: 2px 0 0;
    font-size: var(--fs-xs);
    color: rgba(255, 255, 255, 0.85);
}

.asis-en-linea {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: #4ade80;
    box-shadow: 0 0 0 2px rgba(74, 222, 128, 0.3);
}

.asis-btn-icono {
    width: 32px;
    height: 32px;
    flex-shrink: 0;
    border: 0;
    border-radius: 50%;
    background: rgba(255, 255, 255, 0.16);
    color: #fff;
    cursor: pointer;
    transition: background var(--t-fast);
}

.asis-btn-icono:hover { background: rgba(255, 255, 255, 0.3); }

/* --------------------------------------------------------------------------
   Hilo de mensajes
   -------------------------------------------------------------------------- */

.asis-hilo {
    flex: 1;
    overflow-y: auto;
    padding: 18px 16px;
    display: flex;
    flex-direction: column;
    gap: 12px;
    background: var(--bg-subtle);
    scrollbar-width: thin;
}

.asis-hilo::-webkit-scrollbar { width: 6px; }
.asis-hilo::-webkit-scrollbar-thumb {
    background: var(--scroll-thumb, #cbd5e1);
    border-radius: var(--r-full);
}

.asis-msg {
    max-width: 88%;
    padding: 11px 14px;
    font-size: var(--fs-sm);
    line-height: 1.5;
    border-radius: var(--r-lg);
    animation: asis-msg-entrar var(--t-base) both;
}

@keyframes asis-msg-entrar {
    from { opacity: 0; transform: translateY(8px); }
    to   { opacity: 1; transform: translateY(0); }
}

.asis-msg-bot {
    align-self: flex-start;
    background: var(--card-bg);
    color: var(--text-primary);
    border: 1px solid var(--border-color);
    border-bottom-left-radius: var(--r-sm);
}

.asis-msg-yo {
    align-self: flex-end;
    background: var(--accent-color);
    color: #fff;
    border-bottom-right-radius: var(--r-sm);
    font-weight: 600;
}

.asis-msg p { margin: 0 0 8px; }
.asis-msg p:last-child { margin-bottom: 0; }
.asis-msg strong { color: inherit; font-weight: 700; }

.asis-msg ul {
    margin: 0 0 8px;
    padding-left: 18px;
}

.asis-msg li { margin-bottom: 4px; }
.asis-msg li:last-child { margin-bottom: 0; }

/* Puntos de "escribiendo". */
.asis-escribiendo {
    align-self: flex-start;
    display: flex;
    gap: 4px;
    padding: 13px 16px;
    background: var(--card-bg);
    border: 1px solid var(--border-color);
    border-radius: var(--r-lg);
    border-bottom-left-radius: var(--r-sm);
}

.asis-escribiendo span {
    width: 7px;
    height: 7px;
    border-radius: 50%;
    background: var(--text-secondary);
    animation: asis-punto 1.3s infinite ease-in-out;
}

.asis-escribiendo span:nth-child(2) { animation-delay: 0.18s; }
.asis-escribiendo span:nth-child(3) { animation-delay: 0.36s; }

@keyframes asis-punto {
    0%, 60%, 100% { transform: translateY(0); opacity: 0.4; }
    30%           { transform: translateY(-5px); opacity: 1; }
}

/* --------------------------------------------------------------------------
   Opciones
   -------------------------------------------------------------------------- */

.asis-opciones {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    align-self: flex-start;
    max-width: 100%;
    animation: asis-msg-entrar var(--t-base) both;
}

.asis-chip {
    display: inline-flex;
    align-items: center;
    gap: 7px;
    padding: 8px 14px;
    border: 1px solid var(--accent-color);
    border-radius: var(--r-full);
    background: var(--card-bg);
    color: var(--accent-color);
    font-family: inherit;
    font-size: var(--fs-xs);
    font-weight: 600;
    cursor: pointer;
    text-align: left;
    transition: background var(--t-fast), color var(--t-fast), transform var(--t-fast);
}

.asis-chip:hover {
    background: var(--accent-color);
    color: #fff;
    transform: translateY(-1px);
}

/* Chip de accion: lleva a un modulo, asi que va relleno de entrada. */
.asis-chip-ir {
    background: var(--accent-light);
    border-color: transparent;
}

.asis-chip-suave {
    border-color: var(--border-color);
    color: var(--text-secondary);
}

.asis-chip-suave:hover {
    background: var(--hover-bg, var(--bg-primary));
    color: var(--text-primary);
}

/* --------------------------------------------------------------------------
   Pie
   -------------------------------------------------------------------------- */

.asis-pie {
    padding: 12px 16px 14px;
    border-top: 1px solid var(--border-color);
    background: var(--card-bg);
}

/* En el original el buscador lleva ademas la clase compartida .search-box del
   sistema de diseño; sus reglas van aqui integradas para no depender de ella. */
.asis-buscador {
    position: relative;
    display: flex;
    align-items: center;
    gap: 8px;
    width: 280px;
    min-width: 0;
    height: 40px;
    padding: 9px 14px;
    border: 1px solid var(--border-color);
    border-radius: var(--r-full);
    background: var(--bg-subtle);
    transition: border-color var(--t-fast), box-shadow var(--t-fast), background-color var(--t-fast);
}

.asis-buscador:focus-within {
    border-color: var(--accent-color);
    background-color: var(--card-bg);
    box-shadow: 0 0 0 3px rgba(var(--accent-rgb), 0.13);
}

.asis-buscador i { color: var(--text-secondary); font-size: 0.85rem; flex-shrink: 0; }

.asis-buscador input {
    flex: 1;
    min-width: 0;
    height: 100%;
    padding: 0 var(--sp-2);
    border: 0;
    outline: 0;
    background: transparent;
    color: var(--text-primary);
    font-family: inherit;
    font-size: var(--fs-sm);
}

.asis-buscador input::placeholder { color: var(--text-muted); }

.asis-nota {
    margin: 8px 2px 0;
    font-size: var(--fs-xs);
    color: var(--text-secondary);
    text-align: center;
}

/* --------------------------------------------------------------------------
   Pantallas pequenas: el panel ocupa el ancho util
   -------------------------------------------------------------------------- */

@media (max-width: 480px) {
    .asistente { right: 16px; bottom: 16px; }

    .asis-panel {
        width: calc(100vw - 32px);
        height: calc(100vh - 120px);
    }
}

/* Quien pide menos movimiento no ve el latido ni las entradas. */
@media (prefers-reduced-motion: reduce) {
    .asis-fab-aro,
    .asis-escribiendo span,
    .asis-panel,
    .asis-msg,
    .asis-opciones { animation: none; }
}
"""

JS_BOT = r"""// asistente.js
//
// Asistente flotante (CFloresBot).
//
// No hay servidor detras. Es una guia del sistema escrita a mano: saluda segun
// la hora, ofrece los temas de los modulos que la persona puede ver y responde
// con lo que hace cada pantalla, con un boton para ir hasta ella.
//
// Los temas se filtran con CONFIG.puede(), la misma clave de permiso que usa el
// menu. Ocultar es comodidad: quien no tenga permiso se topa igual con la
// comprobacion del servidor.
const AsistenteModule = (function () {
    'use strict';

    // =====================================================================
    //  Adaptacion al proyecto (lo unico que cambia entre proyectos)
    // =====================================================================

    const CONFIG = {
        /** Nombre del producto tal como lo conoce la gente. */
        nombreSistema: 'NOMBRE DEL SISTEMA',

        /** Nombre completo del usuario con sesion ('' si no se sabe). */
        nombreUsuario: () => String(window.APP?.usuario?.nombre || ''),

        /**
         * Orden del nombre en la base: 'nombre-apellido' (Ana Perez Gil) o
         * 'apellido-nombre' (Perez Gil Ana Maria; el de pila es la 3a palabra).
         */
        ordenNombre: 'nombre-apellido',

        /** Clave de permiso -> bool. Sin sistema de permisos: todo visible. */
        puede: (clave) => (typeof window.puede === 'function' ? window.puede(clave) : true),

        /** Si la vista/ruta existe para esta persona (para pintar "Ir a"). */
        existeVista: (vista) => !!document.getElementById('view-' + vista),

        /** Navega a la vista sin cerrar el panel. */
        irA: (vista) => {
            if (typeof showView === 'function') {
                showView(vista);
                history.pushState({ view: vista }, '', '#' + vista);
            } else {
                window.location.hash = '#' + vista;
            }
        },
    };

    const $ = (id) => document.getElementById(id);
    const esc = (v) => (typeof escapeHtml === 'function'
        ? escapeHtml(v)
        : String(v ?? '')
            .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;').replace(/'/g, '&#039;'));
    const normalizar = (v) => (typeof normalizarTexto === 'function'
        ? normalizarTexto(v)
        : String(v ?? '').normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase().trim());

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
     * Cada tema: a que menu pertenece, que permiso lo destapa, que responde,
     * a donde lleva y con que palabras se encuentra desde el buscador.
     *
     * 'permiso' vacio = lo ve cualquiera con sesion.
     * 'ir' opcional = texto del boton ("Ir a ..."); sin el, la primera palabra del titulo.
     */
    const TEMAS = [
        // Rellenar segun la seccion 6.
    ];

    /** Menus del nivel de arriba. */
    const MENUS = [
        // Rellenar segun la seccion 6.
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
     * Se puntua para que "ticket" saque primero "Crear un ticket" y no un tema
     * donde la palabra solo aparece de pasada.
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
     * @param {Array} opciones  {texto, icono, clase, alPulsar}
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
            boton.innerHTML = (op.icono ? `<i class="fas ${esc(op.icono)}" aria-hidden="true"></i>` : '')
                + esc(op.texto);
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

    /** Buenos dias / buenas tardes / buenas noches. */
    function saludoHorario() {
        const h = new Date().getHours();
        if (h >= 5 && h < 12) return 'Buenos dias';
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
                { texto: 'Volver', icono: 'fa-arrow-left', clase: 'asis-chip-suave', alPulsar: volverAlMenu },
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

            // Ir al modulo solo si esa vista existe para esta persona.
            if (tema.vista && CONFIG.existeVista(tema.vista)) {
                const destino = tema.ir
                    || tema.titulo.split(' ')[0].toLowerCase().replace(/^./, c => c.toUpperCase());
                botones.push({
                    texto: 'Ir a ' + destino,
                    icono: 'fa-arrow-right',
                    clase: 'asis-chip-ir',
                    alPulsar: () => irA(tema.vista, tema.titulo),
                });
            }

            (tema.relacionados || []).forEach(id => {
                const rel = buscarTema(id);
                if (rel && permitido(rel)) {
                    botones.push({ texto: rel.titulo, icono: rel.icono, alPulsar: () => abrirTema(rel.id) });
                }
            });

            botones.push({
                texto: 'Otro tema', icono: 'fa-list', clase: 'asis-chip-suave', alPulsar: volverAlMenu,
            });

            opciones(botones);
        });
    }

    function irA(vista, titulo) {
        CONFIG.irA(vista);
        decirYo('Llevame ahi');
        responder(() => {
            decir(`<p>Listo, ya estas en <strong>${esc(titulo)}</strong>. Te dejo el panel abierto por si necesitas otra cosa.</p>`);
            opciones([{ texto: 'Otro tema', icono: 'fa-list', clase: 'asis-chip-suave', alPulsar: volverAlMenu }]);
        });
    }

    function volverAlMenu() {
        responder(() => menuPrincipal('<p>Claro. Elige por donde seguimos:</p>'));
    }

    /** Texto libre del buscador del pie. */
    function preguntar(texto) {
        const limpio = texto.trim();
        if (limpio === '') return;

        decirYo(limpio);
        const encontrados = coincidencias(limpio);

        responder(() => {
            if (!encontrados.length) {
                decir(`<p>No tengo nada sobre eso, y prefiero decirtelo a inventarme una respuesta.</p>
                       <p>Prueba con otra palabra, mira el menu, o pide ayuda a una persona.</p>`);
                const botones = [{ texto: 'Ver los temas', icono: 'fa-list', alPulsar: volverAlMenu }];
                if (buscarTema('soporte')) {
                    botones.push({ texto: 'Hablar con una persona', icono: 'fa-headset', clase: 'asis-chip-suave',
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
                { texto: 'Ver todos los temas', icono: 'fa-list', clase: 'asis-chip-suave', alPulsar: volverAlMenu },
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
               <p>Soy <strong>${esc(nombreBot())}</strong>, el asistente de ${esc(CONFIG.nombreSistema)}. Te explico como funciona cualquier parte del sistema y te llevo hasta ella.</p>
               <p>Dime por donde empezamos, o escribeme tu duda ahi abajo.</p>`);

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

        // Escape cierra, como el resto de paneles de la aplicacion.
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && estaAbierto()) cerrar();
        });
    }

    return { enlazar, abrir, cerrar };
})();

document.addEventListener('DOMContentLoaded', AsistenteModule.enlazar);
"""


# ===========================================================================
#  CFloresBot: el asistente de la casa (CFloresBot.md)
#
#  El CSS y el motor JS se copian literales del agente (secciones 4 y 5). Lo
#  único que se escribe para cada proyecto es lo que el agente permite: CONFIG,
#  TEMAS, MENUS, los tokens (colores, fuente, tema oscuro) y el cableado.
#  Los tokens del bot llevan el prefijo --cfb- para no chocar con los del
#  proyecto (CFloresBot.md, paso 3).
# ===========================================================================

NOMBRE_CSS = "asistente.css"
NOMBRE_JS = "asistente.js"
FIRMA = "generate_bot"
ACENTO, DEGRADADO = "#1d4ed8", "#0ea5e9"          # los originales (CFloresBot.md, paso 3)
TOKENS = ["font-sans", "fs-xs", "fs-sm", "fs-md", "sp-2", "r-sm", "r-lg", "r-xl", "r-full", "t-fast", "t-base", "t-slow",
          "z-panel", "bg-primary", "bg-subtle", "text-primary", "text-secondary", "text-muted", "border-color", "card-bg",
          "hover-bg", "accent-color", "accent-rgb", "accent-light", "success", "scroll-thumb", "shadow", "shadow-lg",
          "shadow-accent", "brand-gradient"]
FA6 = "https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.2/css/all.min.css"
INTER = "https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap"


def _con_prefijo(css):
    """--card-bg -> --cfb-card-bg en todo el CSS (sólo los tokens del bot)."""
    return re.sub(r"--(%s)\b" % "|".join(re.escape(t) for t in sorted(TOKENS, key=len, reverse=True)), r"--cfb-\1", css)


def _rgb_de(h):
    h = h.lstrip("#")
    return "%d, %d, %d" % tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _aclarar(h, f):
    return _mezcla_hex(h, "#ffffff", f)


def construir_css(acento, degradado, fuente, selectores_oscuros):
    """Los tokens (con prefijo) + el CSS literal del agente."""
    tokens = TOKENS_CSS
    if acento.lower() != ACENTO or degradado.lower() != DEGRADADO:
        claro_acento = _aclarar(acento, 0.85)
        osc_acento, osc_degr = _aclarar(acento, 0.3), _aclarar(degradado, 0.3)
        for a, b in (("--accent-color: #1d4ed8;", "--accent-color: %s;" % acento),
                     ("--accent-rgb: 29, 78, 216;", "--accent-rgb: %s;" % _rgb_de(acento)),
                     ("--accent-light: #dbeafe;", "--accent-light: %s;" % claro_acento),
                     ("--shadow-accent: 0 6px 18px rgba(29, 78, 216, 0.24);",
                      "--shadow-accent: 0 6px 18px rgba(%s, 0.24);" % _rgb_de(acento)),
                     ("--brand-gradient: linear-gradient(135deg, #1d4ed8, #0ea5e9);",
                      "--brand-gradient: linear-gradient(135deg, %s, %s);" % (acento, degradado)),
                     ("--accent-color: #4f8dfb;", "--accent-color: %s;" % osc_acento),
                     ("--accent-rgb: 79, 141, 251;", "--accent-rgb: %s;" % _rgb_de(osc_acento)),
                     ("--shadow-accent: 0 6px 18px rgba(79, 141, 251, 0.3);",
                      "--shadow-accent: 0 6px 18px rgba(%s, 0.3);" % _rgb_de(osc_acento)),
                     ("--brand-gradient: linear-gradient(135deg, #4f8dfb, #22d3ee);",
                      "--brand-gradient: linear-gradient(135deg, %s, %s);" % (osc_acento, osc_degr))):
            tokens = tokens.replace(a, b)
    if fuente:
        tokens = re.sub(r"--font-sans: [^;]+;", "--font-sans: %s;" % fuente, tokens, count=1)
    # El tema oscuro, con el selector que usa el proyecto. Sin tema oscuro, no se añade.
    m = re.search(r"\n/\* Oscuro:[\s\S]*?\nbody\.theme-dark \{([\s\S]*?)\n\}\n", tokens)
    cuerpo_oscuro = m.group(1) if m else ""
    tokens = tokens[:m.start()] + "\n" + tokens[m.end():] if m else tokens
    if selectores_oscuros and cuerpo_oscuro:
        sel = [s for s in selectores_oscuros if s != "@media"]
        bloque = "/* Tema oscuro: con el selector que ya usa el proyecto */\n"
        if sel:
            bloque += "%s {%s\n}\n" % (", ".join(sel), cuerpo_oscuro)
        if "@media" in selectores_oscuros:
            bloque += "@media (prefers-color-scheme: dark) {\n    :root:not([data-theme=\"light\"]) {%s\n    }\n}\n" % \
                cuerpo_oscuro.replace("\n", "\n    ")
        tokens += "\n" + bloque
    cabecera = ("/* Puesto por generate_bot.py (CFloresBot). El diseño es el de la casa, copiado literal del agente;\n"
                "   sólo se adaptan los tokens de abajo (prefijo --cfb- para no chocar con los del proyecto). */\n")
    return cabecera + _con_prefijo(tokens) + "\n" + _con_prefijo(CSS_BOT)


# ---------------------------------------------------------------- qué páginas llevan el bot
_RE_NO_BOT = re.compile(r"login|signin|sign-in|registro|register|recuper|forgot|reset|password/|publico|public/|"
                        r"(^|/)(errors?|errores|emails?|mail)(/|$)|welcome|landing|auth/", re.I)


def _resolver_include(pan, nombre):
    nombre = nombre.replace(".", "/").strip("/")
    for f in pan.todas:
        rel = re.sub(r"\.(blade\.php|html\.twig|php|html|twig|jinja2?|j2|ejs|hbs)$", "", _rel(pan.p.raiz, f))
        if rel.endswith(nombre):
            return f
    return None


def _incluidos(pan, f):
    t = _texto(f, 600000)
    nombres = re.findall(r"(?:include|extends|require(?:_once)?|include_once|view)\s*\(?\s*['\"]([\w./-]+)['\"]", t)
    nombres += re.findall(r"@(?:include|extends)\(\s*['\"]([\w./-]+)['\"]", t)
    nombres += re.findall(r"\{%\s*(?:include|extends)\s+['\"]([\w./-]+)['\"]", t)
    out = []
    for n in nombres:
        g = _resolver_include(pan, re.sub(r"\.(php|html|twig)$", "", n))
        if g and g != f:
            out.append(g)
    return out


def paginas_del_bot(p, pan):
    """(archivos donde va el armazón y el JS — los que cierran </body> —, archivos con <head> para el CSS).
    Sólo las pantallas con sesión: nunca el login ni las páginas públicas."""
    pan.menu()
    menu_archivo = pan.archivo_menu
    if menu_archivo and _RE_NO_BOT.search(_rel(p.raiz, menu_archivo)):
        menu_archivo = None     # el menú que encontró es el de una página pública: no sirve de guía
    if menu_archivo:
        paginas = [f for f in pan.todas if f != menu_archivo and any(g == menu_archivo for g in _incluidos(pan, f))]
        if not paginas and "</body>" in _texto(menu_archivo, 600000).lower():
            paginas = [menu_archivo]
    else:
        paginas = [f for f in pan.todas if "</body>" in _texto(f, 600000).lower()]
    cuerpos, cabezas = [], []
    for f in paginas:
        if _RE_NO_BOT.search(_rel(p.raiz, f)):
            continue
        # Primero lo que la página incluye (el pie y la cabecera compartidos), luego la página: así el bot va
        # una sola vez aunque la página cierre también su propio </body>.
        directos = _incluidos(pan, f)
        grupo = directos + [h for g in directos for h in _incluidos(pan, g)] + [f]
        cuerpo = next((g for g in grupo if "</body>" in _texto(g, 600000).lower()), None)
        cabeza = next((g for g in grupo if re.search(r"<head\b", _texto(g, 600000), re.I)), None)
        if cuerpo and cuerpo not in cuerpos:
            cuerpos.append(cuerpo)
        if cabeza and cabeza not in cabezas:
            cabezas.append(cabeza)
    return cuerpos, cabezas


# ---------------------------------------------------------------- el nombre del usuario
_EXPRESIONES_USUARIO = [
    # (patrón en las plantillas, motor, cómo se escribe en el atributo)
    (r"session\(\)->get\(\s*['\"](nombres?|name|usuario|user(?:name)?|nombre_completo)['\"]\s*\)", "php"),
    (r"\$_SESSION\[\s*['\"](nombres?|name|usuario|user(?:name)?|nombre_completo)['\"]\s*\]", "php"),
    (r"(?:auth\(\)|Auth::)->?user\(\)->(name|nombre)", "blade"),
    (r"app\.user\.(username|name|nombre)", "twig"),
    (r"request\.user\.(get_full_name|first_name|username)", "django"),
]


def expresion_usuario(p, pan):
    """(expresión lista para el atributo data-usuario, de dónde sale, orden del nombre) o (None, None, …)."""
    for f in pan.todas:
        t = _texto(f, 600000)
        for patron, motor in _EXPRESIONES_USUARIO:
            m = re.search(patron, t)
            if not m:
                continue
            campo = m.group(1)
            if motor == "php":
                base = m.group(0).replace(campo, "%s", 1)
                apellido = re.search(re.escape(base).replace("%s", r"(apellidos?|last_name|surname)"), t)
                expr = "(%s)" % m.group(0) + ((" . ' ' . (%s)" % apellido.group(0)) if apellido else "")
                html = "<?= htmlspecialchars(trim((string)%s), ENT_QUOTES) ?>" % expr
                visto = m.group(0) + ((" + " + apellido.group(0)) if apellido else "")
            elif motor == "blade":
                html, visto = "{{ %s ?? '' }}" % m.group(0), m.group(0)
            elif motor == "twig":
                html, visto = "{{ %s|default('') }}" % m.group(0), m.group(0)
            else:
                html, visto = "{{ %s }}" % m.group(0), m.group(0)
            return html, "%s (%s)" % (visto, _rel(p.raiz, f)), "nombre-apellido"
    return None, None, "nombre-apellido"


# ---------------------------------------------------------------- la base de conocimiento
ICONOS_MODULO = [("asistencia|marcacion|sala", "fa-clipboard-check"), ("usuario|cuenta|personal", "fa-users"),
                 ("estudiante|alumno", "fa-user-graduate"), ("profesor|docente", "fa-chalkboard-user"),
                 ("materia|curso|asignatura", "fa-book"), ("acerca|about|informacion|institucion", "fa-circle-info"),
                 ("reporte|informe|estadistic|dashboard|tablero", "fa-chart-column"), ("inventario|producto|stock", "fa-boxes-stacked"),
                 ("pedido|venta|compra|tienda|carrito", "fa-cart-shopping"), ("cliente|contacto", "fa-address-book"),
                 ("config|ajuste|parametro", "fa-gear"), ("mascota|animal|adop", "fa-paw"), ("refugio", "fa-house"),
                 ("donativo|donacion", "fa-hand-holding-heart"), ("publicacion|noticia|blog", "fa-newspaper"),
                 ("factura|cobro|pago", "fa-file-invoice-dollar"), ("ticket|soporte|incidencia", "fa-headset"),
                 ("calendario|agenda|cita|evento", "fa-calendar-days"), ("documento|archivo", "fa-folder-open"),
                 ("inicio|home|escritorio", "fa-house")]
SINONIMOS = {"ver": "ver lista listado consultar buscar mostrar", "crear": "crear nuevo registrar agregar anadir alta",
             "modificar": "modificar editar cambiar actualizar corregir", "eliminar": "eliminar borrar quitar suprimir baja",
             "reporte": "reporte informe pdf imprimir descargar exportar"}


def _icono_de(texto, defecto="fa-folder-open"):
    t = _sin_tildes(texto)
    return next((ic for patron, ic in ICONOS_MODULO if re.search(patron, t)), defecto)


def _h(t):
    return (str(t).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def _claves(*partes):
    palabras = []
    for x in partes:
        palabras += re.findall(r"[a-z0-9]{3,}", _sin_tildes(x or ""))
    vistas = [w for w in dict.fromkeys(palabras) if w not in ("los", "las", "del", "con", "para", "una", "uno", "que")]
    return " ".join(vistas[:16])


def _lista_campos(fo):
    filas = []
    for d in fo.get("detalles", []):
        extra = []
        if d["obligatorio"]:
            extra.append("obligatorio")
        if d["opciones"]:
            extra.append("eliges entre " + ", ".join(d["opciones"][:6]))
        filas.append("<li><strong>%s</strong>%s</li>" % (_h(d["nombre"]), (" (" + _h("; ".join(extra)) + ")") if extra else ""))
    return "<ul>%s</ul>" % "".join(filas) if filas else ""


def base_de_conocimiento(p, pan, nombre_sistema, soporte_texto):
    """(MENUS, TEMAS) para el motor del bot, escritos con lo que el código dice. Tuteo, como CFloresBot."""
    menus = [{"id": "basico", "icono": "fa-compass", "titulo": "Primeros pasos"}]
    temas = []
    menu = pan.menu()
    nombres = [t for t, _s, _p in menu]
    con_permiso = [t for t, _s, pm in menu if pm]

    temas.append({"id": "que-es", "menu": "basico", "icono": "fa-circle-question", "titulo": "Que es %s" % nombre_sistema,
                  "claves": _claves("que es sistema para que sirve modulos ayuda", nombre_sistema, *nombres),
                  "texto": "<p><strong>%s</strong> reune en un solo sitio %s.</p>%s<p>%s</p>" % (
                      _h(nombre_sistema), "estos modulos" if nombres else "sus pantallas",
                      ("<ul>%s</ul>" % "".join("<li><strong>%s</strong></li>" % _h(n) for n in nombres)) if nombres else "",
                      "Lo que ves en el menu depende de tu usuario: si te falta algo, mira <strong>Por que no veo un "
                      "modulo</strong>." if con_permiso else "Elige un tema y te explico como funciona esa parte."),
                  "relacionados": ["permisos-mios", "soporte"] if con_permiso else ["soporte"]})
    if con_permiso:
        temas.append({"id": "permisos-mios", "menu": "basico", "icono": "fa-lock", "titulo": "Por que no veo un modulo",
                      "claves": "permiso permisos acceso no veo falta modulo menu rol",
                      "texto": "<p>%s solo aparece%s si tu usuario tiene permiso.</p><p>Si lo necesitas para tu "
                               "trabajo, pidelo a quien administra %s. Ocultarlo es comodidad: el sistema comprueba el "
                               "permiso igual.</p>" % (_lista_y(["<strong>%s</strong>" % _h(x) for x in con_permiso]),
                                                       "n" if len(con_permiso) > 1 else "", _h(nombre_sistema)),
                      "relacionados": ["soporte"]})
    temas.append({"id": "soporte", "menu": "basico", "icono": "fa-headset", "titulo": "Hablar con una persona",
                  "claves": "ayuda soporte persona humano contacto problema error falla ticket correo",
                  "texto": "<p>Yo te explico como funciona el sistema, pero no veo tus datos ni puedo arreglar un caso "
                           "concreto.</p><p>%s</p><p>Cuenta que estabas haciendo y que paso: una captura ahorra media "
                           "conversacion.</p>" % soporte_texto})

    # --- un menú por opción del menú del proyecto (hasta 6; el resto, en «Otros modulos»)
    temas_cuenta = []
    vistos_c = set()
    for f in pan.todas:
        if not re.search(r"topbar|header|nav|menu|sidebar|layout|cabecera", f.stem, re.I):
            continue
        arriba = bool(re.search(r"topbar|header|nav|cabecera", f.stem, re.I))
        for m in re.finditer(r"<a\b([^>]*)>([\s\S]*?)</a>", _enmascarar(_texto(f, 400000))):
            t_enlace = _frase(_limpio(m.group(2)))
            href = re.search(r"href=([\"'])(.*?)\1", m.group(1))
            seg = _segmento(href.group(2)) if href else ""
            clave = _sin_tildes(t_enlace + " " + seg)
            if not t_enlace or not seg or seg in vistos_c or not re.search(r"perfil|profile|mi cuenta|clave|contrasen|password|seguridad|preguntas",
                                                                         clave):
                continue
            vistos_c.add(seg)
            es_clave = bool(re.search(r"clave|contrasen|password", clave))
            id_t = "contrasena" if es_clave and not any(x["id"] == "contrasena" for x in temas_cuenta) else \
                "perfil" if not es_clave and not any(x["id"] == "perfil" for x in temas_cuenta) else "cuenta-" + seg.replace("/", "-")
            donde = "En la barra de arriba" if arriba else "En el menu"
            texto_t = "<p>%s, pulsa <strong>%s</strong>.</p>" % (donde, _h(t_enlace))
            vista_c = pan.vista_de(seg)
            ac = analizar_pantalla(_texto(vista_c, 400000)) if vista_c else None
            if ac and ac["formularios"]:
                fo = ac["formularios"][0]
                if fo.get("detalles"):
                    texto_t += "<p>Rellena:</p>" + _lista_campos(fo)
                if fo["boton"]:
                    texto_t += "<p>Y pulsa <strong>%s</strong>.</p>" % _h(fo["boton"])
            elif ac and ac["titulo"]:
                texto_t += "<p>Se abre <strong>%s</strong>.</p>" % _h(ac["titulo"])
            temas_cuenta.append({"id": id_t, "menu": "cuenta", "icono": "fa-key" if es_clave else "fa-id-card",
                                 "titulo": t_enlace, "claves": _claves(t_enlace, "cuenta usuario mis datos",
                                                                      "contrasena clave password cambiar olvide" if es_clave
                                                                      else "perfil datos personales"),
                                 "texto": texto_t, "vista": seg, "ir": t_enlace})
    for i, (texto, seg, pm) in enumerate(menu):
        vista = pan.vista_de(seg)
        a = analizar_pantalla(_texto(vista, 400000)) if vista else None
        if not a or not (a["titulo"] or a["columnas"] or a["formularios"] or a["acciones"]):
            continue
        id_menu = re.sub(r"[^a-z0-9]+", "-", _sin_tildes(texto)).strip("-") or "mod%d" % i
        if i < 6:
            menus.append({"id": id_menu, "icono": _icono_de(texto), "titulo": texto})
            menu_de = id_menu
        else:
            if not any(m["id"] == "otros" for m in menus):
                menus.append({"id": "otros", "icono": "fa-ellipsis", "titulo": "Otros modulos"})
            menu_de = "otros"
        base = {"menu": menu_de, "vista": seg, "ir": texto}
        if pm:
            base["permiso"] = seg
        ruta = "<strong>%s</strong>" % _h(texto)
        propios = []
        # Qué hay
        cuerpo = "<p>En %s, en el menu, %s.</p>" % (ruta, ("ves la pantalla <strong>%s</strong>" % _h(a["titulo"]))
                                                      if a["titulo"] else "tienes su pantalla")
        if a["ayuda"]:
            cuerpo += "<p>%s</p>" % _h(a["ayuda"])
        if a["columnas"]:
            cuerpo += "<p>La lista muestra:</p><ul>%s</ul>" % "".join("<li><strong>%s</strong></li>" % _h(c)
                                                                        for c in a["columnas"][:10])
        consejo = []
        if a["buscador"]:
            consejo.append("Usa el buscador de la lista para encontrar una fila sin recorrerla entera")
        if a["acciones"]:
            consejo.append("desde aqui tienes %s" % _lista_y(["<strong>%s</strong>" % _h(x) for x in a["acciones"]]))
        if consejo:
            cuerpo += "<p>%s.</p>" % "; ".join(consejo).capitalize() if not consejo[0][0].isupper() else \
                "<p>%s.</p>" % "; ".join(consejo)
        propios.append(dict(base, id=id_menu + "-ver", icono="fa-eye", titulo="Que hay en %s" % texto,
                            claves=_claves(SINONIMOS["ver"], texto, a["titulo"], *a["columnas"][:6]), texto=cuerpo))
        # Formularios (los de la pantalla y los de las pantallas a las que llevan sus botones)
        tareas = list(a["formularios"])
        for t_boton, href in a["enlaces"]:
            destino = pan.vista_de(_segmento(href))
            if destino and destino != vista:
                for fo in analizar_pantalla(_texto(destino, 400000))["formularios"]:
                    tareas.append(dict(fo, titulo=fo["titulo"] or t_boton, desde=t_boton))
        codigo = _codigo_del_modulo(p, pan, seg)
        msgs = mensajes_en(codigo) + a["mensajes"]
        vistos = set()
        for fo in tareas:
            titulo = fo["titulo"] or fo["boton"]
            if not titulo or titulo in vistos or not (fo["campos"] or fo["boton"]):
                continue
            vistos.add(titulo)
            es_mod = bool(re.search(r"modific|editar|actualiz", _sin_tildes(titulo + fo["boton"])))
            accion = "modificar" if es_mod else "crear"
            if fo.get("desde"):
                como = "En %s pulsa <strong>%s</strong>." % (ruta, _h(fo["desde"]))
            elif es_mod and "modificar (el lápiz)" in a["iconos"]:
                como = "En %s, pulsa el lapiz de la fila que quieres cambiar: se abre una ventana con sus datos." % ruta
            else:
                como = "Esta en %s." % ruta
            ok = next((m for m, tipo in msgs if tipo == "Confirmación" and re.search(
                r"modific|actualiz" if es_mod else r"registr|cread|guardad|agregad|añadid", _sin_tildes(m))), "")
            texto_t = "<p>%s</p>" % como
            if fo.get("detalles"):
                texto_t += "<p>Rellena estos campos:</p>" + _lista_campos(fo)
            texto_t += "<p>%s%s</p>" % (("Pulsa <strong>%s</strong>." % _h(fo["boton"])) if fo["boton"] else "",
                                        (" Si todo va bien veras <strong>%s</strong>" % _h(ok.rstrip("."))) + "." if ok else "")
            id_t = "%s-%s" % (id_menu, accion)
            n = 2
            while any(x["id"] == id_t for x in propios):
                id_t = "%s-%s-%d" % (id_menu, accion, n)
                n += 1
            propios.append(dict(base, id=id_t, icono="fa-pen-to-square" if es_mod else "fa-plus",
                                titulo=titulo if len(titulo) < 40 else (accion.capitalize() + " en " + texto),
                                claves=_claves(SINONIMOS[accion], texto, titulo, *fo["campos"][:6]), texto=texto_t))
        if "eliminar (la papelera)" in a["iconos"]:
            conf = a["confirmaciones"][0] if a["confirmaciones"] else ""
            propios.append(dict(base, id=id_menu + "-eliminar", icono="fa-trash", titulo="Eliminar en %s" % texto,
                                claves=_claves(SINONIMOS["eliminar"], texto),
                                texto="<p>En %s, pulsa la papelera de la fila que quieres borrar.</p>%s<p>Revisa bien "
                                      "la fila antes de aceptar: lo que se borra desaparece de la lista.</p>" % (
                                          ruta, ("<p>El sistema pregunta <strong>%s</strong>: <strong>Aceptar</strong> "
                                                 "borra, <strong>Cancelar</strong> lo deja como estaba.</p>" % _h(conf))
                                          if conf else "")))
        for t_boton, _href in a["enlaces"]:
            if re.search(r"report|pdf|excel|export|imprim|descarg", _sin_tildes(t_boton)):
                propios.append(dict(base, id=id_menu + "-reporte", icono="fa-file-pdf", titulo="%s de %s" % (t_boton, texto),
                                    claves=_claves(SINONIMOS["reporte"], texto, t_boton),
                                    texto="<p>En %s pulsa <strong>%s</strong>. Se abre el documento para verlo, "
                                          "descargarlo o imprimirlo.</p>" % (ruta, _h(t_boton))))
                break
        ids = [x["id"] for x in propios]
        for x in propios:
            x["relacionados"] = [i for i in ids if i != x["id"]][:3]
        temas += propios
    if temas_cuenta:
        ids_c = [x["id"] for x in temas_cuenta]
        for x in temas_cuenta:
            x["relacionados"] = [i for i in ids_c if i != x["id"]][:2]
        menus.append({"id": "cuenta", "icono": "fa-id-card", "titulo": "Mi cuenta"})
        temas += temas_cuenta
    return menus, temas


# ---------------------------------------------------------------- búsqueda (la misma del motor, para verificar)
def coincidencias(temas, texto):
    aguja = _sin_tildes(texto).strip()
    if len(aguja) < 2:
        return []
    palabras = [w for w in aguja.split() if len(w) > 2]
    puntos = []
    for t in temas:
        titulo, claves = _sin_tildes(t["titulo"]), _sin_tildes(t.get("claves", ""))
        n = (10 if aguja in titulo else 0) + (6 if aguja in claves else 0)
        n += sum((3 if w in titulo else 0) + (2 if w in claves else 0) for w in palabras)
        if n:
            puntos.append((n, t["id"]))
    return [i for _n, i in sorted(puntos, key=lambda x: -x[0])[:4]]


# ---------------------------------------------------------------- el JS y el armazón
def construir_js(nombre_sistema, orden, spa, menus, temas):
    js = JS_BOT
    if spa:
        navegacion = None
    else:
        navegacion = """
        /** Si la opcion esta en el menu de esta pagina (asi se respetan los permisos del menu). */
        existeVista: (vista) => !!document.querySelector(`a[href$="/${vista}"], a[href="${vista}"]`),

        /** Navega a la pagina de esa opcion del menu. */
        irA: (vista) => {
            const enlace = document.querySelector(`a[href$="/${vista}"], a[href="${vista}"]`);
            window.location.href = enlace ? enlace.href : vista;
        },"""
    config = js[js.index("    const CONFIG = {"):js.index("    };", js.index("    const CONFIG = {")) + 6]
    nueva = config.replace("nombreSistema: 'NOMBRE DEL SISTEMA',", "nombreSistema: %s," % json.dumps(nombre_sistema, ensure_ascii=False))
    nueva = nueva.replace("nombreUsuario: () => String(window.APP?.usuario?.nombre || ''),",
                          "nombreUsuario: () => String(document.getElementById('asistente')?.dataset.usuario || ''),")
    nueva = nueva.replace("ordenNombre: 'nombre-apellido',", "ordenNombre: '%s'," % orden)
    if not spa:
        nueva = nueva.replace("puede: (clave) => (typeof window.puede === 'function' ? window.puede(clave) : true),",
                              "puede: (clave) => (typeof window.puede === 'function' ? window.puede(clave)\n"
                              "            : !!document.querySelector(`a[href$=\"/${clave}\"], a[href=\"${clave}\"]`)),")
        ini = nueva.index("        /** Si la vista/ruta existe")
        nueva = nueva[:ini].rstrip() + navegacion + "\n    };"
    js = js.replace(config, nueva)
    datos = lambda x: json.dumps(x, ensure_ascii=False, indent=4).replace("\n", "\n    ")   # noqa: E731
    js = js.replace("    const TEMAS = [\n        // Rellenar segun la seccion 6.\n    ];",
                    "    /* TEMAS:inicio — escrito por generate_bot.py a partir del codigo del proyecto */\n"
                    "    const TEMAS = %s;\n    /* TEMAS:fin */" % datos(temas))
    js = js.replace("    const MENUS = [\n        // Rellenar segun la seccion 6.\n    ];",
                    "    /* MENUS:inicio */\n    const MENUS = %s;\n    /* MENUS:fin */" % datos(menus))
    return "// Puesto por generate_bot.py (CFloresBot). Motor literal del agente; CONFIG, TEMAS y MENUS de este proyecto.\n" + js


def armazon(nombre_bot, nombre_sistema, foto_attr, iniciales, placeholder, nota, usuario_html):
    cara = '<img %s alt="" aria-hidden="true">' % foto_attr if foto_attr else '<span aria-hidden="true">%s</span>' % _h(iniciales)
    cara2 = '<img %s alt="">' % foto_attr if foto_attr else '<span>%s</span>' % _h(iniciales)
    usuario = ' data-usuario="%s"' % usuario_html if usuario_html else ""
    e = lambda t: _h(t).replace('"', "&quot;")   # noqa: E731
    return ARMAZON.replace("{{NOMBRE_BOT}}", e(nombre_bot)).replace("{{NOMBRE_SISTEMA}}", _h(nombre_sistema)) \
        .replace("{{PLACEHOLDER}}", e(placeholder)).replace("{{NOTA_PIE}}", _h(nota)) \
        .replace("{{CARA_FAB}}", cara).replace("{{CARA_CAB}}", cara2).replace("{{USUARIO}}", usuario)


ARMAZON = """<!-- generate_bot:inicio · CFloresBot (generate_bot.py) -->
<div id="asistente" class="asistente" data-nombre="{{NOMBRE_BOT}}"{{USUARIO}}>
    <button type="button" class="asis-fab" id="asis-fab"
            aria-expanded="false" aria-controls="asis-panel"
            aria-label="Abrir el asistente {{NOMBRE_BOT}}">
        <span class="asis-fab-aro" aria-hidden="true"></span>
        <span class="asis-fab-cara">
            {{CARA_FAB}}
        </span>
        <span class="asis-fab-punto" aria-hidden="true"></span>
        <span class="asis-fab-globo" aria-hidden="true">¿Necesitas ayuda?</span>
    </button>
    <section class="asis-panel" id="asis-panel" role="dialog" aria-modal="false"
             aria-labelledby="asis-titulo" hidden>
        <header class="asis-cabecera">
            <span class="asis-cabecera-cara">
                {{CARA_CAB}}
            </span>
            <div class="asis-cabecera-texto">
                <h3 id="asis-titulo">{{NOMBRE_BOT}}</h3>
                <p><span class="asis-en-linea"></span> Asistente de {{NOMBRE_SISTEMA}}</p>
            </div>
            <button type="button" class="asis-btn-icono" id="asis-reiniciar"
                    title="Empezar de nuevo" aria-label="Empezar de nuevo">
                <i class="fas fa-rotate-right" aria-hidden="true"></i>
            </button>
            <button type="button" class="asis-btn-icono" id="asis-cerrar"
                    title="Cerrar" aria-label="Cerrar el asistente">
                <i class="fas fa-times" aria-hidden="true"></i>
            </button>
        </header>
        <div class="asis-hilo" id="asis-hilo" role="log" aria-live="polite" aria-atomic="false"></div>
        <footer class="asis-pie">
            <div class="asis-buscador">
                <i class="fas fa-search" aria-hidden="true"></i>
                <label class="sr-only" for="asis-buscar">Buscar un tema de ayuda</label>
                <input type="text" id="asis-buscar" autocomplete="off"
                       placeholder="{{PLACEHOLDER}}">
            </div>
            <p class="asis-nota">{{NOTA_PIE}}</p>
        </footer>
    </section>
</div>
<!-- generate_bot:fin -->"""


def enganchar_cabeza(texto, lineas):
    nl = "\r\n" if "\r\n" in texto else "\n"
    bloque = lambda s: "".join(s + x + nl for x in ["<!-- generate_bot:estilos -->"] + lineas +   # noqa: E731
                               ["<!-- generate_bot:fin-estilos -->"])
    previo = re.search(r"^([ \t]*)<!-- generate_bot:estilos -->.*?<!-- generate_bot:fin-estilos -->[ \t]*\r?\n?", texto,
                       re.S | re.M)
    if previo:
        nuevo = bloque(previo.group(1))
        return (texto, "ya_enganchado") if previo.group(0) == nuevo else \
            (texto[:previo.start()] + nuevo + texto[previo.end():], "actualizado")
    cierra = re.search(r"</head\s*>", texto, re.I)
    if not cierra:
        return texto, "sin_head"
    ini = texto.rfind("\n", 0, cierra.start()) + 1
    sangria = re.match(r"[ \t]*", texto[ini:]).group(0) + "    "
    return texto[:ini] + bloque(sangria) + texto[ini:], "insertado"


def enganchar_cuerpo(texto, html, script):
    """El armazón justo antes de los <script> finales y el JS justo antes de </body> (detrás de los helpers)."""
    nl = "\r\n" if "\r\n" in texto else "\n"
    texto_sin = re.sub(r"[ \t]*<!-- generate_bot:inicio[\s\S]*?<!-- generate_bot:fin -->[ \t]*\r?\n?", "", texto)
    texto_sin = re.sub(r"[ \t]*<script[^>]*%s[^>]*></script>[ \t]*<!-- generate_bot -->\r?\n?" % re.escape(NOMBRE_JS), "",
                       texto_sin)
    cierra = list(re.finditer(r"</body\s*>", texto_sin, re.I))
    if not cierra:
        return texto, "sin_body"
    fin = cierra[-1].start()
    # Retroceder por los <script> finales para poner el armazón delante de ellos
    pos = fin
    while True:
        previo = texto_sin[:pos].rstrip()
        m = re.search(r"(<script\b[^>]*>[\s\S]*?</script>|<!--[\s\S]*?-->|<\?php[\s\S]*?\?>|\{\{-?[\s\S]*?\}\})\s*$", previo)
        if not m or "generate_bot" in m.group(0) or len(m.group(0)) > 6000:
            break
        pos = m.start()
    ini = texto_sin.rfind("\n", 0, pos) + 1
    sangria = re.match(r"[ \t]*", texto_sin[ini:]).group(0)
    bloque_html = "".join(sangria + x + nl for x in html.split("\n"))
    nuevo = texto_sin[:ini] + bloque_html + texto_sin[ini:]
    fin = list(re.finditer(r"</body\s*>", nuevo, re.I))[-1].start()
    ini_fin = nuevo.rfind("\n", 0, fin) + 1
    sangria_s = re.match(r"[ \t]*", nuevo[ini_fin:]).group(0) + ("    " if nuevo[ini_fin:fin].strip() == "" else "")
    nuevo = nuevo[:ini_fin] + sangria_s + script + " <!-- generate_bot -->" + nl + nuevo[ini_fin:]
    if nuevo == texto:
        return texto, "ya_enganchado"
    return nuevo, ("actualizado" if "generate_bot:inicio" in texto else "insertado")


def _carga_de(p, plantillas, patron):
    for f in p.plantillas + plantillas:
        if re.search(patron, _texto(f, 600000), re.I):
            return _rel(p.raiz, f)
    for f in _archivos(p.raiz, (".css",)):
        if re.search(patron, _texto(f, 300000)[:20000], re.I):
            return _rel(p.raiz, f)
    return None


def _foto_candidatas(p):
    base = p.publico if p.publico.is_dir() else p.raiz
    out = []
    for f in _archivos(base, (".png", ".jpg", ".jpeg", ".webp")):
        if re.search(r"asistente|bot|avatar|mascota-bot|desarrollador|developer|dev[-_]|perfil|foto", _sin_tildes(f.stem)):
            out.append(f)
    return out[:6]


# ===========================================================================
#  Órdenes
# ===========================================================================

def orden_instalar(a):
    interactivo = not a.si
    raiz = Path(a.proyecto).resolve() if a.proyecto else raiz_del_proyecto()
    p = detectar_proyecto(raiz)
    print("\nProyecto: %s  ·  %s" % (p.raiz, p.descripcion))
    pan = Pantallas(p)
    est = Estilos(p)

    # 1. Dónde va
    cuerpos, cabezas = paginas_del_bot(p, pan)
    claro = bool(pan.archivo_menu) and not _RE_NO_BOT.search(_rel(p.raiz, pan.archivo_menu))
    if cuerpos and not claro and not a.plantilla:
        # Sin un layout compartido claro: se pregunta en qué páginas va (nunca se ponen todas a ciegas)
        if not interactivo:
            raise ErrorBot("No encuentro un layout común para las pantallas con sesión. Indica dónde va el bot con "
                           "--plantilla (candidatas: %s)." % ", ".join(_rel(p.raiz, f) for f in cuerpos[:8]))
        explicar("Páginas donde va el bot", "No encuentro una plantilla común para las pantallas con sesión. Elige las "
                 "páginas de la parte privada (no el login ni las públicas). Números separados por comas.",
                 "«2,5,7»")
        for i, f in enumerate(cuerpos, 1):
            print("   %d. %s" % (i, _rel(p.raiz, f)))
        r = _preguntar_obligatorio("   Páginas")
        elegidas = [cuerpos[int(x) - 1] for x in re.findall(r"\d+", r) if 1 <= int(x) <= len(cuerpos)]
        if not elegidas:
            raise ErrorBot("No elegiste ninguna página: no se ha escrito nada.")
        cuerpos = elegidas
        cabezas = [g for f in cuerpos for g in [f] + _incluidos(pan, f) if re.search(r"<head\b", _texto(g), re.I)]
        cabezas = list(dict.fromkeys(cabezas))
    if a.plantilla:
        cuerpos = [(p.raiz / x.strip()).resolve() for x in a.plantilla.split(",") if x.strip()]
        cabezas = list(dict.fromkeys(g for f in cuerpos for g in [f] + _incluidos(pan, f)
                                     if re.search(r"<head\b", _texto(g), re.I)))
    if not cuerpos:
        raise ErrorBot("No encontré la plantilla de las pantallas con sesión (la que cierra </body>). Este bot es para "
                       "aplicaciones web con menú; si la tuya lo es, indica el archivo con --plantilla.")
    print("\nDónde va el bot (una vez, en las pantallas con sesión; nunca en el login ni en las públicas):")
    for f in cuerpos:
        print("   armazón y JS  →  %s" % _rel(p.raiz, f))
    for f in cabezas:
        print("   CSS           →  %s" % _rel(p.raiz, f))
    if interactivo and not _si_no("¿Es ahí?", True):
        r = _preguntar_obligatorio("   Archivo donde va el bot (el que cierra </body>)")
        cuerpos = [(p.raiz / r).resolve()]
        cabezas = [g for g in [cuerpos[0]] + _incluidos(pan, cuerpos[0]) if re.search(r"<head\b", _texto(g), re.I)][:1]

    carpeta_css = (p.raiz / a.css).resolve() if a.css else _carpeta_o_preguntar(p, "estilos", ".css", CARPETAS_CSS, None, interactivo)
    carpeta_js = (p.raiz / a.js).resolve() if a.js else _carpeta_o_preguntar(p, "scripts", ".js", CARPETAS_JS, carpeta_css, interactivo)

    # 2. Identidad
    nombre, origen = (a.nombre, "indicado") if a.nombre else detectar_nombre(p)
    if interactivo and not a.nombre:
        explicar("Nombre del sistema", "Cómo se llama tu aplicación: el bot dice «Soy el asistente de …».",
                 "«Gestión de Asistencia»")
        if nombre:
            print("   En %s aparece «%s». Enter para usarlo o escribe otro." % (origen, nombre))
        nombre = _preguntar_obligatorio("   Nombre", nombre or None)
    elif not nombre:
        raise ErrorBot("No encontré el nombre del sistema. Indícalo con --nombre \"Mi sistema\".")
    dev = (a.asistente or "").strip()
    if interactivo and not dev:
        explicar("Nombre del asistente", "Cómo se llama el asistente. Sale en el botón, en la cabecera del panel y en "
                 "su saludo («Soy …, el asistente de %s»). Se escribe tal cual." % nombre,
                 "«Asistente Asistencia», «Ana», «Ayuda UMC»")
        dev = _preguntar_obligatorio("   Nombre del asistente")
    elif not dev:
        raise ErrorBot("Falta el nombre del asistente. Indícalo con --asistente \"Ayuda UMC\".")
    partes = dev.split()
    iniciales = ((partes[0][:1] if partes else "A") + (partes[1][:1] if len(partes) > 1 else "")).upper()
    foto = Path(a.foto).resolve() if a.foto else None
    if interactivo and not a.foto:
        cands = _foto_candidatas(p)
        explicar("Imagen del asistente", "Una imagen cuadrada dentro de la carpeta pública del proyecto. Sin imagen, el "
                 "bot enseña las iniciales (%s)." % iniciales, "«public/img/asistente.png»")
        for i, f in enumerate(cands, 1):
            print("   %d. %s" % (i, _rel(p.raiz, f)))
        r = (_preguntar("   Imagen (número, ruta o Enter vacío = iniciales)", "") or "").strip()
        if r:
            foto = cands[int(r) - 1] if r.isdigit() and 1 <= int(r) <= len(cands) else (p.raiz / r).resolve()
    if foto and not foto.is_file():
        print("  [aviso] No existe %s: el bot enseña las iniciales." % foto)
        foto = None
    soporte = a.soporte or ""
    if interactivo and not a.soporte:
        explicar("A quién acudir", "Para el tema «Hablar con una persona» y el pie del panel: el canal real de soporte.",
                 "«escribe a soporte@empresa.com o llama a la extensión 1234»")
        soporte = _preguntar("   Soporte (Enter vacío = quien administra el sistema)", "") or ""
    soporte_texto = ("Para tu caso concreto, %s." % soporte.rstrip(".")) if soporte else \
        "Para tu caso concreto, habla con quien administra %s." % nombre
    nota = "Guía del sistema. Para un caso concreto, %s." % (soporte.rstrip(".") if soporte else "pide ayuda a quien lo administra")

    # 3. Usuario y navegación
    expr, de_donde, orden = expresion_usuario(p, pan)
    if interactivo:
        explicar("Nombre del usuario para el saludo", "El bot saluda por el nombre de pila («Buenas tardes, Ana»). Sale de "
                 "la sesión, como en tus plantillas.", "Enter = usar lo que encontré; «-» = saludar sin nombre")
        if expr:
            print("   En tus plantillas: %s" % de_donde)
        r = (_preguntar("   ¿Usarlo? (Enter = sí, - = sin nombre)", "") or "").strip()
        if r == "-":
            expr = None
        if expr:
            r = _preguntar("   Orden del nombre: 1 = «Ana Pérez», 2 = «Pérez Gil Ana»", "1")
            orden = "apellido-nombre" if (r or "1").strip() == "2" else "nombre-apellido"
    spa = bool(re.search(r"function\s+showView\b", " ".join(_texto(f, 300000) for f in _archivos(p.raiz, (".js",)))))

    # 4. Colores y fuente
    det = paleta_del_proyecto(p.raiz)
    acento, degradado = (a.acento or ACENTO), (a.degradado or "")
    if not a.acento and det.get("primario") and not det.get("supuesto"):
        acento = det["primario"][0]
    degradado = degradado or (DEGRADADO if acento.lower() == ACENTO else _aclarar(acento, 0.45))
    if interactivo and not a.acento:
        vista = vista_previa_bot(nombre, dev, iniciales)
        det_bot = {"primario": (acento, "", det["primario"][2] if det.get("primario") else "el original"),
                   "oscuro": (degradado, "", "a juego"), "candidatos": det["candidatos"], "supuesto": False}
        global _PAGINA_COLORES
        guardada = _PAGINA_COLORES
        _PAGINA_COLORES = _pagina_bot()
        try:
            acento, degradado, _m = confirmar_colores(det_bot, "Colores del bot · %s" % nombre, vista,
                                                      "El color del bot: aro, cabecera y botones.",
                                                      "El final del degradado de la cabecera.", sin_ventana=a.sin_ventana)
        finally:
            _PAGINA_COLORES = guardada
    tok_fuente = est.primero(["font-sans", "font-family", "fuente", "font-body", "font-base", "bs-font-sans-serif"])
    fuente = "var(--%s, 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif)" % tok_fuente[0] \
        if tok_fuente else None
    css = construir_css(acento, degradado, fuente, est.selectores)

    # 5. Base de conocimiento y archivos
    menus, temas = base_de_conocimiento(p, pan, nombre, soporte_texto)
    js = construir_js(nombre, orden, spa, menus, temas)
    plan = Plan()
    for ruta, datos, etq in ((carpeta_css / NOMBRE_CSS, css, "estilos del bot"),
                             (carpeta_js / NOMBRE_JS, js, "motor + %d temas en %d menús" % (len(temas), len(menus)))):
        if ruta.is_file() and FIRMA not in _texto(ruta, 400000)[:600] and not a.sobrescribir:
            if not interactivo or not _si_no("\nYa existe %s y no lo puso esta herramienta. ¿Sustituirlo? (se guarda "
                                              "copia)" % _rel(p.raiz, ruta), False):
                raise ErrorBot("No se toca %s. Para sustituirlo, añade --sobrescribir." % _rel(p.raiz, ruta))
        plan.escrituras.append((ruta, datos.encode("utf-8"), etq))
    fa = _carga_de(p, cabezas + cuerpos, r"font-?awesome|fontawesome")
    fa6 = _carga_de(p, cabezas + cuerpos, r"font-?awesome[^\"']*6\.|fontawesome-free-6|font-awesome/6")
    inter = _carga_de(p, cabezas + cuerpos, r"family=Inter|['\"]Inter['\"]")
    original = p.destino
    for f in cabezas:
        try:
            antes = f.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            plan.estados.append((f, "no_utf8"))
            continue
        p.destino = carpeta_css
        href = _imitar_enlace(p, f, antes, carpeta_css / NOMBRE_CSS, True) or p.href(f, NOMBRE_CSS)
        p.destino = original
        lineas = []
        if not fa6:
            lineas.append('<link rel="stylesheet" href="%s">' % FA6)
        if not inter and not tok_fuente:
            lineas.append('<link rel="stylesheet" href="%s">' % INTER)
        lineas.append('<link rel="stylesheet" %s>' % href)
        despues, acc = enganchar_cabeza(antes, lineas)
        plan.estados.append((f, acc))
        if despues != antes:
            plan.textos[f] = (antes, despues)
            plan.escrituras.append((f, despues.encode("utf-8"), "estilos en el <head>"))
    for f in cuerpos:
        try:
            antes = next((d.decode("utf-8") for r, d, _e in plan.escrituras if r == f), None) or f.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            plan.estados.append((f, "no_utf8"))
            continue
        foto_attr = None
        if foto:
            p.destino = foto.parent
            foto_attr = re.sub(r"^href=", "src=", p.href(f, foto.name))
            p.destino = original
        p.destino = carpeta_js
        src = _imitar_enlace(p, f, antes, carpeta_js / NOMBRE_JS, False) or re.sub(r"^href=", "src=", p.href(f, NOMBRE_JS))
        p.destino = original
        placeholder = "Escribe tu duda: %s..." % ", ".join(m["titulo"].lower() for m in menus[1:4]) if len(menus) > 1 \
            else "Escribe tu duda..."
        html = armazon(dev, nombre, foto_attr, iniciales, placeholder, nota, expr)
        despues, acc = enganchar_cuerpo(antes, html, "<script %s></script>" % src)
        plan.estados.append((f, acc))
        if despues != antes:
            plan.textos[f] = (antes, despues)
            plan.escrituras = [(r, d, e) for r, d, e in plan.escrituras if r != f]
            plan.escrituras.append((f, despues.encode("utf-8"), "armazón y JS antes de </body>"))

    # --- plan
    print("\nAsistente «%s» · asistente de %s" % (dev, nombre))
    print("  Base de conocimiento: %d menús, %d temas (sacados del código)" % (len(menus), len(temas)))
    for m in menus:
        dentro = [t["titulo"] for t in temas if t["menu"] == m["id"]]
        print("    %-22s %s" % (m["titulo"], " · ".join(dentro)))
    print("  Colores: %s → %s   Tema oscuro: %s" % (acento, degradado, ", ".join(est.selectores) or "el proyecto no tiene"))
    print("  Navegación: %s" % ("por vistas (showView)" if spa else "por las páginas del menú; los temas de opciones con "
                                                                    "permiso solo salen si el menú las muestra"))
    print("  Saludo: %s" % ("con el nombre (%s)" % orden if expr else "sin nombre"))
    print("\nArchivos")
    for ruta, datos, etq in plan.escrituras:
        marca = "+" if not ruta.exists() else ("=" if ruta.read_bytes() == datos else "~")
        print("  %s %-44s %s" % (marca, _rel(p.raiz, ruta), etq))
    print("\n  + nuevo   ~ cambia (con respaldo)   = sin cambios")
    if not fa6:
        print("  · Se enlaza Font Awesome 6 (CDN), que usan los iconos del bot.%s" % (
            " El proyecto ya carga otra versión (%s): revisa que sus iconos se sigan viendo." % fa if fa else ""))
    if not inter and not tok_fuente:
        print("  · Se enlaza la fuente Inter (Google Fonts), la del original.")
    if any(re.search(r"\.sr-only\s*\{", _texto(h, 300000)) for h in est.hojas):
        pass
    print("  · La ayuda dice lo que el código muestra. Revisa los textos en %s (TEMAS) y añade el porqué de cada "
          "pantalla, que el código no lo dice." % _rel(p.raiz, carpeta_js / NOMBRE_JS))
    if a.simulacro:
        print("\n(simulacro) No se ha escrito nada.")
        return 0
    if all(r.exists() and r.read_bytes() == d for r, d, _e in plan.escrituras):
        print("\nTodo estaba ya al día.")
        return 0
    if interactivo:
        if plan.textos and _si_no("\n¿Ver exactamente qué líneas cambian en las plantillas?", False):
            _diff(p, plan)
        if not _si_no("\n¿Aplicar estos cambios?", False):
            print("Cancelado. No se ha escrito nada.")
            return 1
    man = aplicar_plan(p, plan)
    print("\nHecho: %d archivo(s) nuevo(s), %d cambiado(s) con respaldo en %s/."
          % (len(man["creados"]), len(man["modificados"]), CARPETA_ESTADO))
    print("Para dejarlo todo como estaba:  %s" % _llamada("deshacer"))
    print("Comprobar:  %s   (y mírala en el navegador: arranca cerrado, la ✕ lo cierra, tema oscuro y móvil)"
          % _llamada("verificar"))
    return 0


_PAGINA_BOT = None


def _pagina_bot():
    global _PAGINA_BOT
    if _PAGINA_BOT is None:
        pag = _PAGINA_COLORES
        for x, y in (("<h2>Color principal</h2>", "<h2>Color del bot</h2>"), ("<h2>Color oscuro</h2>", "<h2>Final del degradado</h2>"),
                     ("Elige el color <b>principal</b> y el <b>oscuro</b>.", "Elige el <b>color del bot</b> y el <b>final de "
                      "su degradado</b>.")):
            pag = pag.replace(x, y)
        pag = pag.replace("const a = document.getElementById('aviso'); a.hidden = !av.length;",
                          "av.length = 0; const a = document.getElementById('aviso'); a.hidden = true;")
        _PAGINA_BOT = pag
    return _PAGINA_BOT


def vista_previa_bot(nombre, dev, iniciales):
    return ('<div style="display:flex;gap:18px;align-items:center;flex-wrap:wrap;font-family:Inter,system-ui,sans-serif">'
            '<div style="width:64px;height:64px;border-radius:50%%;padding:3px;background:linear-gradient(135deg,__P__,__O__)">'
            '<div style="width:100%%;height:100%%;border-radius:50%%;background:#fff;display:grid;place-items:center;'
            'font-weight:700;color:__P__">%s</div></div><div style="width:300px;border-radius:14px;overflow:hidden;'
            'box-shadow:0 12px 32px rgba(15,23,42,.15)"><div style="background:linear-gradient(135deg,__P__,__O__);color:#fff;'
            'padding:14px 16px;font-weight:700">%s<div style="font-weight:400;font-size:12px;opacity:.9">Asistente de %s'
            '</div></div><div style="background:#f8fafc;padding:12px"><span style="display:inline-block;border:1px solid __P__;'
            'color:__P__;border-radius:999px;padding:5px 12px;font-size:13px">Primeros pasos</span></div></div></div>'
            % (_h(iniciales), _h(dev), _h(nombre)))


def _leer_bloque(js, nombre):
    m = re.search(r"/\* %s:inicio[^*]*\*/\s*const %s = ([\s\S]*?);\s*/\* %s:fin \*/" % (nombre, nombre, nombre), js)
    return json.loads(m.group(1)) if m else None


def orden_verificar(a):
    raiz = Path(a.proyecto).resolve() if a.proyecto else raiz_del_proyecto()
    p = detectar_proyecto(raiz)
    fallos = 0

    def linea(ok, texto):
        nonlocal fallos
        fallos += 0 if ok else 1
        print("  [%s] %s" % ("ok" if ok else "MAL", texto))
    css = [f for f in _archivos(p.raiz, (".css",)) if f.name == NOMBRE_CSS and FIRMA in _texto(f)[:600]]
    js = [f for f in _archivos(p.raiz, (".js",)) if f.name == NOMBRE_JS and FIRMA in _texto(f)[:600]]
    linea(bool(css), "%s: %s" % (NOMBRE_CSS, ", ".join(_rel(p.raiz, f) for f in css) or "no está"))
    linea(bool(js), "%s: %s" % (NOMBRE_JS, ", ".join(_rel(p.raiz, f) for f in js) or "no está"))
    for f in css:
        linea(".asis-panel[hidden]" in _texto(f), "el panel arranca cerrado (.asis-panel[hidden])")
    for f in js:
        t = _texto(f)
        node = shutil.which("node")
        if node:
            r = subprocess.run([node, "--check", str(f)], capture_output=True, text=True)
            linea(r.returncode == 0, "sintaxis del JS (node --check)" + ("" if r.returncode == 0 else ": " + r.stderr[:200]))
        temas, menus = _leer_bloque(t, "TEMAS") or [], _leer_bloque(t, "MENUS") or []
        ids = {x["id"] for x in temas}
        linea(bool(temas) and bool(menus), "%d menús y %d temas" % (len(menus), len(temas)))
        linea("soporte" in ids, "existe el tema «soporte» (lo usa la respuesta de «no encontrado»)")
        rotos = sorted({r for x in temas for r in x.get("relacionados", []) if r not in ids})
        linea(not rotos, "relacionados que existen%s" % (": faltan " + ", ".join(rotos) if rotos else ""))
        vacios = [m["titulo"] for m in menus if not any(x["menu"] == m["id"] for x in temas)]
        linea(not vacios, "cada menú tiene temas%s" % (": vacíos " + ", ".join(vacios) if vacios else ""))
        for m in menus[1:]:
            linea(bool(coincidencias(temas, m["titulo"])), "buscar «%s» encuentra su tema" % m["titulo"])
        linea(not coincidencias(temas, "xyzzy"), "buscar «xyzzy» da la respuesta honesta (no hay nada)")
    plantillas = [f for f in _archivos(p.raiz, (".php", ".html", ".twig", ".ejs", ".hbs", ".cshtml", ".erb", ".jinja",
                                                ".j2", ".blade.php")) if "generate_bot:inicio" in _texto(f, 600000)]
    for f in plantillas:
        n = _texto(f, 600000).count('id="asistente"')
        linea(n == 1, "%s: un solo #asistente" % _rel(p.raiz, f))
        linea(not _RE_NO_BOT.search(_rel(p.raiz, f)), "%s no es el login ni una página pública" % _rel(p.raiz, f))
    linea(bool(plantillas), "plantillas con el bot: %d" % len(plantillas))
    print("\n%s: %d fallo(s). Míralo en el navegador: arranca cerrado, la ✕ y Escape lo cierran, tema oscuro y móvil."
          % ("BIEN" if not fallos else "REVISAR", fallos))
    return 1 if fallos else 0


def orden_detectar(a):
    raiz = Path(a.proyecto).resolve() if a.proyecto else raiz_del_proyecto()
    p = detectar_proyecto(raiz)
    pan = Pantallas(p)
    cuerpos, cabezas = paginas_del_bot(p, pan)
    print("Proyecto:      %s  ·  %s" % (p.raiz, p.descripcion))
    print("Menú:          %s" % (_rel(p.raiz, pan.archivo_menu) if pan.archivo_menu else "no encontrado"))
    print("Armazón y JS:  %s" % (", ".join(_rel(p.raiz, f) for f in cuerpos) or "—"))
    print("CSS:           %s" % (", ".join(_rel(p.raiz, f) for f in cabezas) or "—"))
    expr, de_donde, _o = expresion_usuario(p, pan)
    print("Usuario:       %s" % (de_donde or "no encontrado (saludo sin nombre)"))
    menus, temas = base_de_conocimiento(p, pan, "el sistema", "")
    print("Temas:         %d en %d menús" % (len(temas), len(menus)))
    for m in menus:
        print("               %-20s %s" % (m["titulo"], " · ".join(t["titulo"] for t in temas if t["menu"] == m["id"])))
    return 0


def _argumentos():
    p = argparse.ArgumentParser(prog="generate_bot", description="Pone CFloresBot (asistente de ayuda flotante, sin IA "
                                "ni servidor) en el proyecto, con su base de conocimiento sacada del código.")
    p.add_argument("--version", action="version", version="%(prog)s " + VERSION)
    s = p.add_subparsers(dest="orden", metavar="ORDEN")
    s.required = True
    i = s.add_parser("instalar", help="pone el bot (lo que hace sin argumentos)")
    i.add_argument("proyecto", nargs="?")
    i.add_argument("--si", action="store_true", help="no preguntar")
    i.add_argument("--simulacro", action="store_true", help="enseña lo que haría sin escribir nada")
    i.add_argument("--nombre", help="nombre del sistema")
    i.add_argument("--asistente", help="nombre del asistente (sale en el botón, la cabecera y el saludo)")
    i.add_argument("--foto", help="imagen del asistente (dentro de la carpeta pública); sin ella, las iniciales")
    i.add_argument("--soporte", help="a quién acudir, p. ej. \"escribe a soporte@empresa.com\"")
    i.add_argument("--acento", help="color del bot (#rrggbb); por omisión, el del proyecto o el original")
    i.add_argument("--degradado", help="final del degradado de la cabecera (#rrggbb)")
    i.add_argument("--plantilla", help="archivo(s) donde va el bot, separados por comas, si no lo encuentra solo")
    i.add_argument("--css", help="carpeta donde poner asistente.css")
    i.add_argument("--js", help="carpeta donde poner asistente.js")
    i.add_argument("--sobrescribir", action="store_true")
    i.add_argument("--sin-ventana", action="store_true", help="elegir los colores en la terminal")
    i.set_defaults(fn=orden_instalar)
    d = s.add_parser("detectar", help="enseña lo que entiende del proyecto, sin tocar nada")
    d.add_argument("proyecto", nargs="?")
    d.set_defaults(fn=orden_detectar)
    v = s.add_parser("verificar", help="comprueba el bot puesto (sale con 1 si algo falla)")
    v.add_argument("proyecto", nargs="?")
    v.set_defaults(fn=orden_verificar)
    u = s.add_parser("deshacer", help="deja el proyecto como estaba")
    u.add_argument("proyecto", nargs="?")
    u.add_argument("--forzar", action="store_true")
    u.set_defaults(fn=orden_deshacer)
    return p


def main(argv=None):
    _consola_segura()
    args = list(sys.argv[1:] if argv is None else argv)
    if not args or (args[0].startswith("--") and args[0] not in ("--help", "-h", "--version")):
        print("generate_bot %s · CFloresBot en tu proyecto, sin internet ni IA" % VERSION)
        args = ["instalar"] + args
    a = _argumentos().parse_args(args)
    try:
        return a.fn(a)
    except ErrorBot as e:
        print("Error: %s" % e, file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("\nCancelado.")
        return 130
    except BrokenPipeError:
        return 0


if __name__ == "__main__":
    sys.exit(main())
