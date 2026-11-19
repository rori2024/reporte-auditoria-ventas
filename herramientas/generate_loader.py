#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
generate_loader.py — el Loader RORI en cualquier proyecto web, portable y sin IA.

Hace a mano lo que pide el agente `loader-rori` (.claude/agents/LoaderRORI.md):
pone el indicador de espera de la casa —las letras R-O-R-I con las dos barras
del logotipo encima y el texto de espera debajo— con los colores del proyecto.

  * Un solo archivo y sólo la biblioteca estándar de Python 3.7+.
  * Sin IA y sin red: no consume tokens ni llama a ningún servicio.
  * Portable: se copia dentro del proyecto y se ejecuta desde ahí.
  * El diseño se copia tal cual. Sólo se adapta lo que el agente permite:
    los colores, el tema oscuro y dónde se enganchan los dos archivos.
  * Cambia por loaderRori() las copias del loader pegadas a mano en el JS.
  * Enseña el plan y pregunta antes de escribir. Guarda copia de lo que
    cambia en .generate_loader/ y `deshacer` lo deja todo como estaba.

Uso:
    python3 generate_loader.py              (Windows: py generate_loader.py)
    python3 generate_loader.py detectar     qué entiende del proyecto
    python3 generate_loader.py verificar    comprueba el loader puesto
    python3 generate_loader.py deshacer     vuelve atrás
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


def explicar(titulo, que, ejemplo=None):
    print("\n%s" % titulo)
    print("   Qué va: %s" % que)
    if ejemplo:
        print("   Ejemplo: %s" % ejemplo)

# ===========================================================================
#  Utilidades generales
# ===========================================================================


class ErrorLoader(Exception):
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
        raise ErrorLoader(
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
        raise ErrorLoader("No pude leer %s: %s" % (ruta, e))
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
#  que ya existe se guarda una copia en `.generate_loader/respaldos/`, y
#  `deshacer` deja el proyecto como estaba. Nada se escribe sin enseñar antes
#  el plan, salvo con --si.
# ===========================================================================

DIRS_IGNORADOS = {
    "node_modules", "vendor", "dist", "build", "out", "target", "bin", "obj", "storage",
    "cache", "tmp", "temp", "logs", "coverage", "__pycache__", "venv", "env", "site-packages",
    "bower_components", "jspm_packages", "Pods", "DerivedData",
}
CARPETA_ESTADO = ".generate_loader"
MARCA_INI = "generate_loader:inicio"
MARCA_FIN = "generate_loader:fin"

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

    Portable (el .py copiado dentro del proyecto): `python3 ruta/generate_loader.py`.
    Compilada: `generate_loader`.
    """
    if getattr(sys, "frozen", False) or _PROPIO.suffix.lower() != ".py":
        base = "generate_loader"
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
    raise ErrorLoader(
        "No encuentro ningún proyecto en %s ni en las carpetas de encima. Copia generate_loader.py "
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
        raise ErrorLoader("La carpeta del proyecto %s no existe." % raiz)
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
#  Este bloque es idéntico en generate_icon.py, generate_readme.py y generate_loader.py: cada
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
        tmp = ruta.with_name(ruta.name + ".generate_loader.tmp")
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
        raise ErrorLoader("No hay nadie para responder a las preguntas, así que no se ha escrito nada. "
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
        except ErrorLoader:
            print("  Escríbelo en hexadecimal, por ejemplo #0369a1.")


def orden_deshacer(a):
    raiz = Path(a.proyecto).resolve() if a.proyecto else raiz_del_proyecto()
    ruta_man = raiz / CARPETA_ESTADO / "ultimo.json"
    if not ruta_man.is_file():
        raise ErrorLoader("No hay ninguna instalación que deshacer en %s." % raiz)
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
#  El loader: los dos archivos de la casa (LoaderRORI.md §2 y §3)
#
#  Se copian tal cual. Lo único que cambia de un proyecto a otro es lo que el
#  agente permite (§4): los dos colores, su versión para el tema oscuro y la
#  fuente, que toma la del proyecto si la tiene y si no la de la casa.
# ===========================================================================

NOMBRE_CSS = "style-loader.css"
NOMBRE_JS = "loader.js"
FIRMA = "generate_loader"                 # marca que dejan los archivos que escribe esta herramienta
COLOR_CLARO, COLOR_OSCURO = "#3e3e3e", "#ffffff"   # los del original (§4)

CSS_LOADER = """/* ==========================================================================
   Loader RORI — las letras R-O-R-I con las dos barras del logotipo encima y
   el texto de espera debajo (.claude/agents/LoaderRORI.md).

   Solo para esperas largas (generar, grabar en el servidor, restaurar, subir
   un archivo grande). Las esperas cortas llevan un spinner pequeño en línea.

   Puesto por generate_loader.py. Lo único adaptado a este proyecto son los
   colores (--loader-color, --tilde-color) y la fuente; el resto es el de la casa.
   ========================================================================== */
:root {
  --loader-color: __CLARO__;
  --tilde-color: __CLARO__;
  --loader-text-color: __TEXTO__;
}
__OSCURO__
.loader-container {
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  gap: 6px; padding: 24px;
}
.loader-container.hidden { display: none; }

.loader {
  position: relative; display: flex; align-items: flex-end; gap: 6px;
  font: 700 44px/1 __FUENTE__;
  color: var(--loader-color);
}

.loader .tildes {
  position: absolute; top: -18px; left: 50%; transform: translateX(-40%) skewX(-20deg);
  font: 700 34px/1 __FUENTE__; letter-spacing: -2px; color: var(--tilde-color);
}

.loader span {
  display: inline-block; opacity: 0.2;
  text-shadow: 0 2px 6px rgba(0, 0, 0, 0.12);
  animation: rori-onda 1.2s ease-in-out infinite;
}
.loader span:nth-child(2) { animation-delay: 0s; }
.loader span:nth-child(3) { animation-delay: 0.15s; }
.loader span:nth-child(4) { animation-delay: 0.3s; }
.loader span:nth-child(5) { animation-delay: 0.45s; }

@keyframes rori-onda {
  0%, 100% { opacity: 0.2; }
  40%      { opacity: 1; }
}

.loader-text {
  font: 500 14px/20px __FUENTE__;
  color: var(--loader-text-color);
}

@media (prefers-reduced-motion: reduce) {
  .loader span { animation: none !important; opacity: 1; }
}
"""

JS_LOADER = r"""/**
 * Loader RORI (.claude/agents/LoaderRORI.md). Puesto por generate_loader.py.
 *
 *   contenedor.innerHTML = loaderRori();                       // oculto, id="loader"
 *   contenedor.innerHTML = loaderRori('grabando...!', { id: 'loaderX', oculto: false });
 *   loaderRori.mostrar('Grabando en el servidor…');
 *   loaderRori.ocultar();
 *
 * Solo para esperas largas; las cortas llevan un spinner pequeño en línea.
 */
(function () {
    'use strict';

    const escapar = (texto) => String(texto).replace(/[&<>"']/g, (c) => (
        { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]
    ));

    function loaderRori(texto, opciones) {
        const o = Object.assign({ id: 'loader', oculto: true }, opciones || {});
        return '<div id="' + escapar(o.id) + '" class="loader-container' + (o.oculto ? ' hidden' : '')
            + '" role="status" aria-live="polite">'
            + '<div class="loader loader-1" aria-hidden="true">'
            + '<div class="tildes">\'\'</div>'
            + '<span>R</span><span>O</span><span>R</span><span>I</span>'
            + '</div>'
            + '<div class="loader-text">' + escapar(texto || 'por favor espere...!') + '</div>'
            + '</div>';
    }

    loaderRori.mostrar = function (texto, id) {
        const nodo = document.getElementById(id || 'loader');
        if (!nodo) { return; }
        if (texto) { nodo.querySelector('.loader-text').textContent = texto; }
        nodo.classList.remove('hidden');
    };

    loaderRori.ocultar = function (id) {
        const nodo = document.getElementById(id || 'loader');
        if (nodo) { nodo.classList.add('hidden'); }
    };

    window.loaderRori = loaderRori;
}());
"""

TEXTO_POR_OMISION = "por favor espere...!"


def html_loader(texto=None, id_="loader", oculto=True):
    """El mismo HTML que genera loaderRori() en el navegador (para comparar y para la vista previa)."""
    esc = lambda s: (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")   # noqa: E731
                     .replace('"', "&quot;").replace("'", "&#39;"))
    return ('<div id="%s" class="loader-container%s" role="status" aria-live="polite">'
            '<div class="loader loader-1" aria-hidden="true"><div class="tildes">\'\'</div>'
            '<span>R</span><span>O</span><span>R</span><span>I</span></div>'
            '<div class="loader-text">%s</div></div>') % (esc(id_), " hidden" if oculto else "",
                                                          esc(texto or TEXTO_POR_OMISION))


# ---------------------------------------------------------------- lo que hay en el proyecto
# Nombres habituales del gris de texto y del texto apagado, por orden de preferencia.
TOKENS_TEXTO = ["ink", "text", "texto", "color-text", "text-color", "body-color", "bs-body-color", "foreground",
                "fg", "color-fg", "text-primary", "color-texto", "gray-700", "grey-700", "neutral-700", "slate-700",
                "gray-800", "neutral-800", "slate-800"]
TOKENS_APAGADO = ["ink-muted", "text-muted", "muted", "texto-suave", "color-text-muted", "muted-foreground",
                  "bs-secondary-color", "text-secondary", "gray-500", "neutral-500", "slate-500", "gray-600"]
TOKENS_FUENTE = ["font-sans", "font-family", "font", "fuente", "bs-font-sans-serif", "font-body", "font-base"]

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


# ---------------------------------------------------------------- carpetas y enlaces
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
        raise ErrorLoader("El proyecto no tiene carpeta de %s. Indícala con --%s (por ejemplo --%s %s)."
                          % (que, extension[1:], extension[1:], _rel(p.raiz, propuesta)))
    explicar("Carpeta de los %s" % que,
             "El proyecto no tiene ninguna carpeta con archivos %s. Dime dónde poner el del loader "
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


def lineas_enlace(p, plantilla, texto, carpeta_css, carpeta_js):
    original = p.destino
    try:
        p.destino = carpeta_css
        h_css = _imitar_enlace(p, plantilla, texto, carpeta_css / NOMBRE_CSS, True) or p.href(plantilla, NOMBRE_CSS)
        p.destino = carpeta_js
        h_js = _imitar_enlace(p, plantilla, texto, carpeta_js / NOMBRE_JS, False) or \
            re.sub(r"^href=", "src=", p.href(plantilla, NOMBRE_JS))
    finally:
        p.destino = original
    return ['<link rel="stylesheet" %s>' % h_css, '<script %s></script>' % h_js]


def enganchar(texto, lineas, formato="html", django=False):
    """Pone el bloque marcado en el <head>, justo después del <title>: así el CSS está en el <head> y el
    JS queda antes que los scripts que lo usan. Si el bloque ya estaba, lo actualiza."""
    nl = "\r\n" if "\r\n" in texto else "\n"
    if formato == "jsx":
        ci, cf = "{/* ", " */}"
        re_abre, re_cierra = re.compile(r"<Head\b[^/>]*>"), re.compile(r"</Head>")
    else:
        ci, cf = "<!-- ", " -->"
        re_abre, re_cierra = re.compile(r"<head\b[^>]*>", re.I), re.compile(r"</head\s*>", re.I)

    def bloque(sangria):
        cuerpo = [ci + MARCA_INI + " · Loader RORI (generate_loader.py)" + cf] + lineas + [ci + MARCA_FIN + cf]
        return "".join(sangria + x + nl for x in cuerpo)

    previo = re.compile(r"^([ \t]*)" + re.escape(ci + MARCA_INI) + r".*?" + re.escape(MARCA_FIN + cf)
                        + r"[ \t]*(?:\r?\n)?", re.S | re.M).search(texto)
    if previo:
        nuevo = bloque(previo.group(1))
        if previo.group(0) == nuevo:
            return texto, "ya_enganchado"
        return _con_static(texto[:previo.start()] + nuevo + texto[previo.end():], django, nl), "actualizado"
    if re.search(r"[\"'/]" + re.escape(NOMBRE_CSS) + r"\b", texto) and re.search(r"[\"'/]" + re.escape(NOMBRE_JS)
                                                                             + r"\b", texto):
        return texto, "ya_lo_tenia"
    abre = re_abre.search(texto)
    cierra = re_cierra.search(texto, abre.end()) if abre else None
    if not abre or not cierra:
        return texto, "sin_head"
    cabeza = texto[abre.end():cierra.start()]
    t = re.search(r"</title\s*>", cabeza, re.I)
    if t:
        pos = abre.end() + t.end()
        ini_linea = texto.rfind("\n", 0, abre.end() + t.start()) + 1
        sangria = re.match(r"[ \t]*", texto[ini_linea:]).group(0)
    else:
        pos = abre.end()
        sig = re.search(r"\n([ \t]*)\S", texto[pos:])
        sangria = sig.group(1) if sig else "    "
    fin_linea = texto.find("\n", pos)
    if fin_linea != -1 and not texto[pos:fin_linea].strip():
        nuevo = texto[:fin_linea + 1] + bloque(sangria) + texto[fin_linea + 1:]
    else:
        nuevo = texto[:pos] + nl + bloque(sangria) + texto[pos:]
    return _con_static(nuevo, django, nl), "insertado"


# ---------------------------------------------------------------- copias pegadas a mano (§3, paso 4)
_RE_INICIO_COPIA = re.compile(r"<div\b[^>]*\bclass=([\"'])(?:(?!\1).)*\bloader-container\b(?:(?!\1).)*\1[^>]*>", re.S)


def _fin_del_div(texto, inicio):
    """Posición tras el </div> que cierra el <div> que empieza en `inicio` (cuenta los anidados)."""
    nivel = 0
    for m in re.compile(r"<div\b[^>]*>|</div\s*>", re.I).finditer(texto, inicio):
        nivel += -1 if m.group(0).startswith("</") else 1
        if nivel == 0:
            return m.end()
    return None


def _normalizar(html):
    """Para comparar: sin espacios entre etiquetas, sin role/aria (el helper los añade) y con las
    comillas unificadas."""
    h = re.sub(r"\s+(role|aria-[\w-]+)=([\"'])[^\"']*\2", "", html)
    h = re.sub(r">\s+<", "><", h.strip())
    h = re.sub(r"\s+", " ", h).replace("'", '"')
    return h


class Copia:
    def __init__(self, archivo, inicio, fin, html, en_plantilla_js):
        self.archivo, self.inicio, self.fin, self.html = archivo, inicio, fin, html
        self.en_plantilla_js = en_plantilla_js
        m = re.search(r"\bid=([\"'])([^\"']*)\1", html[:300])
        self.id = m.group(2) if m else "loader"
        self.oculto = bool(re.search(r"class=([\"'])[^\"']*\bhidden\b", html[:300]))
        t = re.search(r"class=([\"'])[^\"']*\bloader-text\b[^\"']*\1[^>]*>([\s\S]*?)</div>", html)
        self.texto = t.group(2).strip() if t else ""
        self.dinamico = bool(re.search(r"\$\{|<\?|\{\{|\{%", self.texto + self.id))
        self.es_rori = "loader-1" in html and ("tildes" in html or html.count("<span") >= 4)

    def llamada(self):
        texto = self.texto
        for a, b in (("&amp;", "&"), ("&lt;", "<"), ("&gt;", ">"), ("&quot;", '"'), ("&#39;", "'")):
            texto = texto.replace(a, b)
        args = []
        opciones = []
        if self.id != "loader":
            opciones.append("id: '%s'" % self.id.replace("'", "\\'"))
        if not self.oculto:
            opciones.append("oculto: false")
        if texto != TEXTO_POR_OMISION or opciones:
            args.append("'%s'" % texto.replace("\\", "\\\\").replace("'", "\\'") if texto != TEXTO_POR_OMISION
                        else "null")
        if opciones:
            args.append("{ %s }" % ", ".join(opciones))
        return "${loaderRori(%s)}" % ", ".join(args)

    def igual_que_helper(self):
        texto = self.texto
        for a, b in (("&amp;", "&"), ("&lt;", "<"), ("&gt;", ">"), ("&quot;", '"'), ("&#39;", "'")):
            texto = texto.replace(a, b)
        return _normalizar(self.html) == _normalizar(html_loader(texto, self.id, self.oculto))


def buscar_copias(p, carpeta_js):
    """Las copias del loader pegadas a mano en el código del proyecto."""
    copias = []
    ext = (".js", ".mjs", ".ts", ".jsx", ".tsx", ".vue", ".svelte", ".php", ".html", ".htm", ".twig", ".blade.php",
           ".ejs", ".hbs", ".cshtml", ".erb", ".jinja", ".j2")
    for f in _archivos(p.raiz, ext):
        if f.name in (NOMBRE_JS, NOMBRE_CSS):
            continue
        t = _texto(f, 1500000)
        if "loader-container" not in t:
            continue
        for m in _RE_INICIO_COPIA.finditer(t):
            fin = _fin_del_div(t, m.start())
            if not fin:
                continue
            antes = t[:m.start()]
            en_js = f.suffix in (".js", ".mjs", ".ts", ".jsx", ".tsx") and antes.count("`") % 2 == 1
            c = Copia(f, m.start(), fin, t[m.start():fin], en_js)
            if c.es_rori:
                copias.append(c)
    return copias


def ids_buscados(p):
    """Los id del loader que busca el código: getElementById('loader…'), $('#loader…'), querySelector."""
    ids = {}
    for f in _archivos(p.raiz, (".js", ".mjs", ".ts", ".jsx", ".tsx", ".vue", ".php", ".html", ".twig")):
        if f.name == NOMBRE_JS:
            continue
        t = _texto(f, 1500000)
        for m in re.finditer(r"getElementById\(\s*[\"'](loader[A-Za-z0-9_]*)[\"']\s*\)|"
                             r"(?:querySelector(?:All)?|\$|jQuery)\(\s*[\"']#(loader[A-Za-z0-9_]*)[\"']", t):
            ids.setdefault(m.group(1) or m.group(2), _rel(p.raiz, f))
    return ids


# ---------------------------------------------------------------- colores
_PAGINA_LOADER = None


def _pagina_loader():
    """La ventana de colores de las otras herramientas, con las etiquetas del loader."""
    global _PAGINA_LOADER
    if _PAGINA_LOADER is None:
        pag = _PAGINA_COLORES
        for a, b in (("<h2>Color principal</h2>", "<h2>Tema claro</h2>"), ("<h2>Color oscuro</h2>", "<h2>Tema oscuro</h2>"),
                     ("Elige el color <b>principal</b> y el <b>oscuro</b>.",
                      "Elige el color de las letras en el tema <b>claro</b> y en el <b>oscuro</b>."),
                     ("aria-label=\"Principal en hexadecimal\"", "aria-label=\"Tema claro en hexadecimal\""),
                     ("aria-label=\"Oscuro en hexadecimal\"", "aria-label=\"Tema oscuro en hexadecimal\"")):
            pag = pag.replace(a, b)
        # Sin los avisos del icono (símbolo blanco): aquí un gris claro en el tema oscuro es lo correcto
        pag = pag.replace("const a = document.getElementById('aviso'); a.hidden = !av.length;",
                          "av.length = 0; const a = document.getElementById('aviso'); a.hidden = true;")
        pag = pag.replace("k === 'o' ? luz(a.hex) - luz(b.hex) : 0", "k === 'o' ? luz(b.hex) - luz(a.hex) : luz(a.hex) - luz(b.hex)")
        _PAGINA_LOADER = pag
    return _PAGINA_LOADER


def vista_previa_loader():
    letras = ('<div style="position:relative;display:inline-flex;align-items:flex-end;gap:6px;font:700 40px/1 '
              'Poppins,system-ui,sans-serif;color:__C__;margin-top:16px"><div style="position:absolute;top:-16px;'
              'left:50%;transform:translateX(-40%) skewX(-20deg);font:700 30px/1 Poppins,system-ui,sans-serif;'
              'letter-spacing:-2px">\'\'</div><span>R</span><span style="opacity:.25">O</span><span style="opacity'
              ':.25">R</span><span style="opacity:.25">I</span></div><div style="font:500 14px/20px system-ui,'
              'sans-serif;color:__C__;opacity:.8;margin-top:6px">por favor espere...!</div>')
    caja = ('<div style="flex:1;min-width:200px;text-align:center;padding:22px;border-radius:12px;background:%s">%s'
            '</div>')
    return ('<div style="display:flex;gap:14px;flex-wrap:wrap;width:100%%">%s%s</div>'
            % (caja % ("#ffffff;border:1px solid #e2e8f0", letras.replace("__C__", "__P__")),
               caja % ("#0f172a", letras.replace("__C__", "__O__"))))


def elegir_colores(p, est, a, interactivo):
    """(claro como CSS, oscuro como CSS o None, texto como CSS, explicación). Primero lo del proyecto."""
    tok = est.primero(TOKENS_TEXTO)
    apagado = est.primero(TOKENS_APAGADO)
    if a.color:
        claro_hex, origen = _a_hex(a.color), "indicado"
        if not claro_hex:
            raise ErrorLoader("--color espera un color, por ejemplo #3e3e3e.")
        claro = claro_hex
    elif tok:
        claro_hex = est.valor_hex(tok[0]) or COLOR_CLARO
        claro, origen = "var(--%s, %s)" % (tok[0], claro_hex), "`--%s` de %s" % (tok[0], tok[2])
    else:
        claro_hex, claro, origen = COLOR_CLARO, COLOR_CLARO, "el del original (el proyecto no declara su gris de texto)"
    if a.color_oscuro:
        oscuro_hex = _a_hex(a.color_oscuro)
        if not oscuro_hex:
            raise ErrorLoader("--color-oscuro espera un color, por ejemplo #ffffff.")
    elif tok and tok[0] in est.oscuro:
        oscuro_hex = _a_hex(est.oscuro[tok[0]]) or COLOR_OSCURO
    else:
        oscuro_hex = COLOR_OSCURO
    if interactivo and not (a.color or a.color_oscuro):
        explicar("Color de las letras",
                 "El de las letras R-O-R-I y sus tildes: el gris de texto de tu proyecto. En el tema oscuro se usa "
                 "otro, claro, para que no quede negro sobre negro.",
                 "#3e3e3e en claro y #ffffff en oscuro (los del original)")
        print("   tema claro   %s   ← %s" % (claro_hex, origen))
        print("   tema oscuro  %s   ← %s" % (oscuro_hex, "el del proyecto" if tok and tok[0] in est.oscuro
                                               else "el del original" + ("" if est.selectores else
                                                                         " (el proyecto no tiene tema oscuro)")))
        if not _si_no("¿Son esos los colores?", True):
            elegidos = None
            if not a.sin_ventana:
                det = paleta_del_proyecto(p.raiz)
                global _PAGINA_COLORES
                guardada, _PAGINA_COLORES = _PAGINA_COLORES, _pagina_loader()
                try:
                    elegidos = elegir_colores_en_ventana("Colores del loader", det["candidatos"], claro_hex, oscuro_hex,
                                                         vista_previa_loader(),
                                                         "Las letras sobre el fondo claro de tus páginas.",
                                                         "Las letras sobre el fondo oscuro, si tu proyecto tiene tema "
                                                         "oscuro.")
                finally:
                    _PAGINA_COLORES = guardada
            if elegidos:
                claro_hex, oscuro_hex = elegidos
            else:
                print("  Escríbelos aquí, entonces.")
                claro_hex = _pedir_color_texto("  Tema claro", claro_hex)
                oscuro_hex = _pedir_color_texto("  Tema oscuro", oscuro_hex)
            claro, origen = claro_hex, "elegido a mano"
    texto = "var(--%s, var(--loader-color))" % apagado[0] if apagado and claro != claro_hex else "var(--loader-color)"
    return claro, claro_hex, oscuro_hex, texto, origen


def fuente_del_proyecto(est):
    tok = est.primero(TOKENS_FUENTE)
    if tok and not re.match(r"^\d", tok[1]):
        return "var(--%s, 'Poppins', sans-serif)" % tok[0], "`--%s` de %s" % (tok[0], tok[2])
    return "'Poppins', sans-serif", "la de la casa (Poppins; si la página no la carga, la genérica del navegador)"


def construir_css(claro, oscuro_hex, texto, fuente, selectores):
    reglas = ""
    if selectores:
        sel = [s for s in selectores if s != "@media"]
        partes = []
        if sel:
            partes.append("%s {\n  --loader-color: %s;\n  --tilde-color: %s;\n}\n" % (", ".join(sel), oscuro_hex, oscuro_hex))
        if "@media" in selectores:
            partes.append("@media (prefers-color-scheme: dark) {\n  :root:not([data-theme=\"light\"]) {\n"
                          "    --loader-color: %s;\n    --tilde-color: %s;\n  }\n}\n" % (oscuro_hex, oscuro_hex))
        reglas = "/* Tema oscuro: con el selector que ya usa el proyecto */\n" + "".join(partes)
    return (CSS_LOADER.replace("__CLARO__", claro).replace("__TEXTO__", texto)
            .replace("__OSCURO__", reglas).replace("__FUENTE__", fuente))


# ===========================================================================
#  Órdenes
# ===========================================================================

_RE_NO_LOADER = re.compile(r"(^|/)(errors?|errores|emails?|mail)(/|$)|welcome_message|(^|/)(40[0-9]|50[0-9])\.", re.I)


def plantillas_utiles(p):
    """Las plantillas donde tiene sentido el loader: no las páginas de error ni las de ejemplo del framework."""
    return [pl for pl in p.plantillas if not _RE_NO_LOADER.search(_rel(p.raiz, pl))]


def _propio(ruta):
    return ruta.is_file() and FIRMA in _texto(ruta, 400000)[:1500]


def orden_instalar(a):
    interactivo = not a.si
    raiz = Path(a.proyecto).resolve() if a.proyecto else raiz_del_proyecto()
    p = detectar_proyecto(raiz)
    print("\nProyecto: %s  ·  %s" % (p.raiz, p.descripcion))
    if p.tipo in ("otro",) or (not p.plantillas and p.tipo not in ("wordpress",)):
        print("  No encuentro páginas web con <head> en este proyecto: el loader es para aplicaciones web.")
    est = Estilos(p)
    carpeta_css = (p.raiz / a.css).resolve() if a.css else \
        _carpeta_o_preguntar(p, "estilos", ".css", CARPETAS_CSS, None, interactivo)
    carpeta_js = (p.raiz / a.js).resolve() if a.js else \
        _carpeta_o_preguntar(p, "scripts", ".js", CARPETAS_JS, carpeta_css, interactivo)

    claro, claro_hex, oscuro_hex, texto_color, origen = elegir_colores(p, est, a, interactivo)
    fuente, origen_fuente = fuente_del_proyecto(est)
    css = construir_css(claro, oscuro_hex, texto_color, fuente, est.selectores)

    plan = Plan()
    for ruta, datos, etq in ((carpeta_css / NOMBRE_CSS, css, "estilos del loader"),
                             (carpeta_js / NOMBRE_JS, JS_LOADER, "helper loaderRori()")):
        if ruta.is_file() and not _propio(ruta) and not a.sobrescribir:
            if not interactivo or not _si_no("\nYa existe %s y no lo puso esta herramienta. ¿Sustituirlo? "
                                              "(se guarda copia)" % _rel(p.raiz, ruta), False):
                raise ErrorLoader("No se toca %s. Para sustituirlo, añade --sobrescribir." % _rel(p.raiz, ruta))
        plan.escrituras.append((ruta, datos.encode("utf-8"), etq))

    if not a.sin_enganchar:
        for pl in plantillas_utiles(p):
            try:
                bruto = pl.read_bytes()
                bom = bruto.startswith(b"\xef\xbb\xbf")
                antes = bruto.decode("utf-8-sig" if bom else "utf-8")
            except (OSError, UnicodeDecodeError):
                plan.estados.append((pl, "no_utf8"))
                continue
            despues, accion = enganchar(antes, lineas_enlace(p, pl, antes, carpeta_css, carpeta_js), p.formato, p.django)
            plan.estados.append((pl, accion))
            if despues != antes:
                plan.textos[pl] = (antes, despues)
                plan.escrituras.append((pl, (b"\xef\xbb\xbf" if bom else b"") + despues.encode("utf-8"),
                                        "<link> y <script> del loader"))

    # Copias pegadas a mano: las de las plantillas de JS se cambian por el helper
    copias = buscar_copias(p, carpeta_js)
    sustituibles = [c for c in copias if c.en_plantilla_js and not c.dinamico]
    otras = [c for c in copias if c not in sustituibles]
    if sustituibles and not a.sin_sustituir:
        print("\nCopias del loader pegadas a mano en el JS (se cambian por loaderRori()):")
        for c in sustituibles:
            n_linea = _texto(c.archivo)[:c.inicio].count("\n") + 1
            print("  %s:%d  →  %s%s" % (_rel(p.raiz, c.archivo), n_linea, c.llamada(),
                                       "" if c.igual_que_helper() else "   (ojo: su HTML no era idéntico)"))
        if interactivo and not _si_no("¿Sustituirlas?", True):
            sustituibles = []
        por_archivo = {}
        for c in sustituibles:
            por_archivo.setdefault(c.archivo, []).append(c)
        for f, lista in por_archivo.items():
            t = next((x for r, x, _e in plan.escrituras if r == f), None)
            t = t.decode("utf-8") if t else _texto(f)
            for c in sorted(lista, key=lambda c: -c.inicio):
                t = t[:c.inicio] + c.llamada() + t[c.fin:]
            # Comprobación: tantas llamadas nuevas como copias quitadas
            if t.count("${loaderRori(") - _texto(f).count("${loaderRori(") != len(lista):
                raise ErrorLoader("Al sustituir las copias de %s no salen las cuentas: no se toca nada." % _rel(p.raiz, f))
            plan.escrituras = [(r, d, e) for r, d, e in plan.escrituras if r != f]
            plan.escrituras.append((f, t.encode("utf-8"), "%d copia(s) → loaderRori()" % len(lista)))
    elif a.sin_sustituir:
        sustituibles = []

    # --- plan
    print("\nLoader RORI")
    print("  Colores:  %s (claro) · %s (oscuro)  ← %s" % (claro_hex, oscuro_hex, origen))
    print("  Tema oscuro: %s" % (", ".join("prefers-color-scheme" if s == "@media" else s for s in est.selectores)
                                 if est.selectores else "el proyecto no tiene; no se añade"))
    print("  Fuente:   %s" % origen_fuente)
    print("\nArchivos")
    textos = {"insertado": "se añaden el <link> y el <script>", "actualizado": "se actualizan",
              "ya_enganchado": "ya los tenía", "ya_lo_tenia": "ya enlazaba el loader (a mano): no se toca",
              "sin_head": "no se encontró el <head>", "no_utf8": "no está en UTF-8: no se toca"}
    for ruta, datos, etq in plan.escrituras:
        if ruta in plan.textos and etq.startswith("<link"):
            continue
        marca = "+" if not ruta.exists() else ("=" if ruta.read_bytes() == datos else "~")
        print("  %s %-40s %s" % (marca, _rel(p.raiz, ruta), etq))
    if plan.estados:
        print("\nPlantillas")
        for pl, acc in plan.estados:
            marca = "~" if pl in plan.textos else ("=" if acc in ("ya_enganchado", "ya_lo_tenia") else "!")
            print("  %s %-40s %s" % (marca, _rel(p.raiz, pl), textos.get(acc, acc)))
    print("\n  + nuevo   ~ cambia (con respaldo)   = sin cambios   ! no se toca")
    avisos = []
    if otras:
        avisos.append("Hay %d copia(s) del loader que no se cambian (en HTML/PHP o con texto que se calcula): %s. "
                      "Ya usan las mismas clases, así que se verán con los estilos nuevos."
                      % (len(otras), ", ".join(sorted({_rel(p.raiz, c.archivo) for c in otras}))))
    ids = ids_buscados(p)
    puestos = {"loader"} | {c.id for c in copias}
    faltan = {i: f for i, f in ids.items() if i not in puestos}
    if faltan:
        avisos.append("El código busca %s y no encuentro dónde se crea: pásalo como id, loaderRori('…', { id: '%s' })."
                      % (", ".join("#%s (%s)" % kv for kv in faltan.items()), next(iter(faltan))))
    if est.poppins:
        avisos.append("El proyecto carga Poppins: el loader se verá con esa fuente. En el original no llegaba a "
                      "cargarse y caía en la genérica del navegador.")
    if est.hidden_global:
        avisos.append("El proyecto ya define .hidden (%s). El loader usa .loader-container.hidden, más concreta: "
                      "no choca." % ", ".join(est.hidden_global[:3]))
    for x in avisos:
        print("  · " + x)

    if a.simulacro:
        print("\n(simulacro) No se ha escrito nada.")
        return 0
    cambios = [x for x in plan.escrituras if not (x[0].exists() and x[0].read_bytes() == x[1])]
    if not cambios:
        print("\nTodo estaba ya al día. No hay nada que escribir.")
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
    print("\nCómo se usa (en tu JS):")
    print("  contenedor.innerHTML = `... ${loaderRori()} ...`;        // nace oculto, con id=\"loader\"")
    print("  loaderRori.mostrar('Grabando…');   loaderRori.ocultar();")
    print("Sólo para esperas largas (más de dos segundos). Un botón o una tabla llevan un spinner pequeño.")
    print("Míralo en el navegador: el aspecto no se puede comprobar desde aquí.")
    print("Comprobar:  %s" % _llamada("verificar"))
    return 0


def orden_verificar(a):
    raiz = Path(a.proyecto).resolve() if a.proyecto else raiz_del_proyecto()
    p = detectar_proyecto(raiz)
    fallos = 0
    css = [f for f in _archivos(p.raiz, (".css",)) if f.name == NOMBRE_CSS]
    todos_js = [f for f in _archivos(p.raiz, (".js",)) if f.name == NOMBRE_JS]
    js = [f for f in todos_js if "loaderRori" in _texto(f, 400000)]
    for f in todos_js:
        if f not in js:
            print("  [--] %s es otro loader.js (no el del Loader RORI): no se mira" % _rel(p.raiz, f))
    def linea(ok, texto):
        nonlocal fallos
        fallos += 0 if ok else 1
        print("  [%s] %s" % ("ok" if ok else "MAL", texto))
    linea(bool(css), "%s: %s" % (NOMBRE_CSS, ", ".join(_rel(p.raiz, f) for f in css) or "no está"))
    linea(bool(js), "%s: %s" % (NOMBRE_JS, ", ".join(_rel(p.raiz, f) for f in js) or "no está"))
    for f in js:
        t = _texto(f)
        linea("window.loaderRori" in t and "loader-1" in t, "%s define loaderRori()" % _rel(p.raiz, f))
        node = shutil.which("node")
        if node:
            r = subprocess.run([node, "--check", str(f)], capture_output=True, text=True)
            linea(r.returncode == 0, "sintaxis de %s (node --check)%s" % (_rel(p.raiz, f), "" if r.returncode == 0
                                                                          else ": " + r.stderr.strip()[:200]))
        else:
            print("  [--] sin Node: no se comprueba la sintaxis del JS")
    for f in css:
        t = _texto(f)
        usados = set(re.findall(r"var\(\s*--([\w-]+)\s*\)", t))
        definidos = set(re.findall(r"--([\w-]+)\s*:", t))
        est = Estilos(p)
        sueltos = sorted(u for u in usados if u not in definidos and u not in est.vars)
        linea(not sueltos, "variables del CSS definidas%s" % (": faltan " + ", ".join("--" + s for s in sueltos)
                                                             if sueltos else ""))
    copias = [c for c in buscar_copias(p, None) if c.en_plantilla_js]
    linea(not copias, "sin copias pegadas a mano en el JS%s" % (
        "" if not copias else ": " + ", ".join(sorted({_rel(p.raiz, c.archivo) for c in copias}))))
    utiles = plantillas_utiles(p)
    enganchadas = [pl for pl in utiles if MARCA_INI in _texto(pl)]
    linea(bool(enganchadas) or not utiles, "plantillas con el loader: %d de %d" % (len(enganchadas), len(utiles)))
    ids = ids_buscados(p)
    if ids:
        print("  [--] el código busca estos id: %s (deben existir en el HTML o pasarse a loaderRori)"
              % ", ".join(sorted(ids)))
    print("\n%s: %d fallo(s). El aspecto hay que mirarlo en el navegador." % ("BIEN" if not fallos else "REVISAR", fallos))
    return 1 if fallos else 0


def orden_detectar(a):
    raiz = Path(a.proyecto).resolve() if a.proyecto else raiz_del_proyecto()
    p = detectar_proyecto(raiz)
    est = Estilos(p)
    print("Proyecto:        %s  ·  %s" % (p.raiz, p.descripcion))
    for que, ext, pref in (("CSS", ".css", CARPETAS_CSS), ("JS", ".js", CARPETAS_JS)):
        d = _carpeta_de(p, ext, pref)
        print("Carpeta de %-4s  %s" % (que + ":", _rel(p.raiz, d) if d else "no tiene (se preguntará)"))
    tok = est.primero(TOKENS_TEXTO)
    print("Gris de texto:   %s" % ("--%s = %s (%s)" % tok if tok else "no declarado: se usa #3e3e3e"))
    print("Tema oscuro:     %s" % (", ".join(est.selectores) or "no tiene"))
    print("Fuente:          %s" % fuente_del_proyecto(est)[1])
    print("Plantillas:      %d con <head> (sin páginas de error)" % len(plantillas_utiles(p)))
    for pl in plantillas_utiles(p)[:12]:
        print("                 %s" % _rel(p.raiz, pl))
    copias = buscar_copias(p, None)
    print("Copias a mano:   %d" % len(copias))
    for c in copias:
        print("                 %s  id=%s  «%s»%s" % (_rel(p.raiz, c.archivo), c.id, c.texto[:40],
                                                    "" if c.en_plantilla_js else "  (no es JS: no se cambia)"))
    return 0


def _argumentos():
    p = argparse.ArgumentParser(prog="generate_loader", description="Pone el Loader RORI en el proyecto, con sus "
                                "colores. Sin IA, sin red y sin dependencias. Sin argumentos abre el asistente.")
    p.add_argument("--version", action="version", version="%(prog)s " + VERSION)
    s = p.add_subparsers(dest="orden", metavar="ORDEN")
    s.required = True
    i = s.add_parser("instalar", help="pone el loader (lo que hace sin argumentos)")
    i.add_argument("proyecto", nargs="?", help="carpeta del proyecto (por defecto la encuentra sola)")
    i.add_argument("--si", action="store_true", help="no preguntar")
    i.add_argument("--simulacro", action="store_true", help="enseña lo que haría sin escribir nada")
    i.add_argument("--color", help="color de las letras en el tema claro (por defecto, el gris de texto del proyecto)")
    i.add_argument("--color-oscuro", help="color de las letras en el tema oscuro (por defecto, #ffffff)")
    i.add_argument("--css", help="carpeta donde poner style-loader.css (relativa al proyecto)")
    i.add_argument("--js", help="carpeta donde poner loader.js (relativa al proyecto)")
    i.add_argument("--sin-enganchar", action="store_true", help="sólo los archivos: no tocar las plantillas")
    i.add_argument("--sin-sustituir", action="store_true", help="no cambiar las copias pegadas a mano")
    i.add_argument("--sobrescribir", action="store_true", help="sustituir un style-loader.css o loader.js que no puso esta herramienta")
    i.add_argument("--sin-ventana", action="store_true", help="elegir los colores en la terminal")
    i.set_defaults(fn=orden_instalar)
    d = s.add_parser("detectar", help="enseña lo que entiende del proyecto, sin tocar nada")
    d.add_argument("proyecto", nargs="?")
    d.set_defaults(fn=orden_detectar)
    v = s.add_parser("verificar", help="comprueba el loader puesto (sale con 1 si algo falla)")
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
        print("generate_loader %s · el Loader RORI en tu proyecto, sin internet ni IA" % VERSION)
        args = ["instalar"] + args
    a = _argumentos().parse_args(args)
    try:
        return a.fn(a)
    except ErrorLoader as e:
        print("Error: %s" % e, file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("\nCancelado.")
        return 130
    except BrokenPipeError:
        return 0


if __name__ == "__main__":
    sys.exit(main())
