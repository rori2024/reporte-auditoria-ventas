#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
generate_manual.py — los manuales en PDF de la casa, portables y sin IA.

Hace a mano lo que pide el agente `manual-pdf` (.claude/agents/ManualPDF.md):
el Markdown de docs/ es la fuente y de él salen los PDF —manual de usuario,
manual técnico y guía de instalación— con el diseño de roriApp: portada con
logotipo, cabecera y pie en cada página, avisos en ámbar, tablas y código.

  * Un solo archivo y sólo la biblioteca estándar de Python 3.7+ (el PDF lo
    escribe él mismo: no necesita Node, pdfkit ni nada que instalar).
  * Sin IA y sin red: no consume tokens ni llama a ningún servicio.
  * Portable: se copia dentro del proyecto y se ejecuta desde ahí.
  * No inventa: la identidad sale del proyecto o te la pregunta; si falta un
    manual, crea su .md con la estructura de la casa y huecos «POR ESCRIBIR».
  * Enseña el plan y pregunta antes de escribir. Guarda copia de lo que
    cambia en .generate_manual/ y `deshacer` lo deja todo como estaba.

Uso:
    python3 generate_manual.py                      (Windows: py generate_manual.py)
    python3 generate_manual.py --solo MANUAL-USUARIO
    python3 generate_manual.py --salida public/docs
    python3 generate_manual.py deshacer
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import shutil
import struct
import subprocess
import sys
import time
import unicodedata
import zlib
from pathlib import Path

VERSION = "1.0.0"
CARPETA_ESTADO = ".generate_manual"
DIR_IMG = "docs/img"
MARCA = "generate_manual"

DIRS_IGNORADOS = {
    "node_modules", "vendor", "dist", "build", "out", "target", "bin", "obj", "storage",
    "cache", "tmp", "temp", "logs", "coverage", "__pycache__", "venv", "env", "site-packages",
    "bower_components", "jspm_packages", "Pods", "DerivedData", "public_html",
}

# Cuentas que firman commits pero no son personas
_BOTS = re.compile(r"noreply@anthropic\.com|\[bot\]|github-actions|dependabot|renovate|noreply@github\.com$", re.I)


# ===========================================================================
#  Utilidades comunes (las mismas que generate_icon.py: este archivo es
#  autónomo a propósito, para poder copiarlo solo)
# ===========================================================================


class ErrorManual(Exception):
    """Un error que se le explica al usuario, sin traza."""


def _consola_segura():
    for flujo in (sys.stdout, sys.stderr):
        try:
            flujo.reconfigure(errors="replace")  # type: ignore[attr-defined]
        except Exception:
            pass


_PROPIO = Path(__file__).resolve()


def _llamada(orden=""):
    """Cómo volver a escribir esta herramienta en la terminal, tal como se usó."""
    try:
        ruta = os.path.relpath(str(_PROPIO), os.getcwd())
    except ValueError:
        ruta = str(_PROPIO)
    if ruta.startswith(".." + os.sep + ".." + os.sep):
        ruta = str(_PROPIO)
    if " " in ruta:
        ruta = '"%s"' % ruta
    return (("py " if os.name == "nt" else "python3 ") + ruta + " " + orden).strip()


_MARCADORES_PROYECTO = (
    ".git", "composer.json", "package.json", "artisan", "manage.py", "pyproject.toml",
    "requirements.txt", "Gemfile", "pom.xml", "build.gradle", "build.gradle.kts", "go.mod",
    "angular.json", "wp-config.php", "index.php", "index.html", "index.htm", "README.md",
)


def _parece_proyecto(d):
    try:
        if any((d / m).exists() for m in _MARCADORES_PROYECTO):
            return True
        return any(d.glob("*.csproj")) or any(d.glob("*.sln"))
    except OSError:
        return False


def raiz_del_proyecto(desde=None):
    """La carpeta más cercana, subiendo desde donde se ejecuta, que parece un proyecto."""
    inicio = Path(desde or os.getcwd()).resolve()
    casa = Path.home().resolve()
    d = inicio
    while d != casa and d.parent != d:
        if _parece_proyecto(d):
            # Si hay un .git más arriba, la raíz es la del repositorio
            g = d
            while g != casa and g.parent != g:
                if (g / ".git").exists():
                    return g
                g = g.parent
            return d
        d = d.parent
    raise ErrorManual("No encuentro ningún proyecto en %s ni en las carpetas de encima. Copia "
                      "generate_manual.py dentro de la carpeta de tu proyecto y ejecútalo desde ahí." % inicio)


def _sin_tildes(texto):
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


def _archivos(raiz, extensiones, max_archivos=20000):
    """Recorre el proyecto saltándose dependencias, compilados, ocultos y esta herramienta."""
    n = 0
    for dp, dns, fns in os.walk(str(raiz)):
        dns[:] = sorted(d for d in dns if d not in DIRS_IGNORADOS and not d.startswith(".")
                                and not _es_de_terceros(dp, d))
        for fn in sorted(fns):
            if fn.lower().endswith(extensiones):
                ruta = Path(dp) / fn
                if ruta.resolve() == _PROPIO:
                    continue
                n += 1
                if n > max_archivos:
                    return
                yield ruta


def _preguntar(texto, defecto=None):
    try:
        r = input("%s%s: " % (texto, " [%s]" % defecto if defecto else "")).strip()
    except EOFError:
        print()
        raise ErrorManual("No hay nadie para responder a las preguntas, así que no se ha escrito nada. "
                          "Para usarlo sin preguntas, añade --si.")
    return r or defecto


_PASO = [0]


def explicar(titulo, que, ejemplo=None):
    """Antes de cada pregunta: qué va ahí y un ejemplo, para que nadie tenga que adivinarlo."""
    _PASO[0] += 1
    print("\n%d. %s" % (_PASO[0], titulo))
    print("   Qué va: " + que)
    if ejemplo:
        print("   Ejemplo: " + ejemplo)


def _preguntar_obligatorio(texto, defecto=None):
    while True:
        r = (_preguntar(texto, defecto) or "").strip()
        if r:
            return r
        print("   Hace falta una respuesta: escribe el nombre.")


def _si_no(texto, defecto=False):
    r = _preguntar(texto + (" [S/n]" if defecto else " [s/N]"))
    return defecto if not r else _sin_tildes(r).startswith(("s", "y"))


def _sha(datos):
    return hashlib.sha256(datos).hexdigest()


def _xml(t):
    return (str(t).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;"))


def _md_celda(t):
    return str(t).replace("|", "\\|").replace("\r", "").replace("\n", "<br>")


# ===========================================================================
#  Lectura del proyecto. Cada dato guarda de qué archivo sale.
# ===========================================================================


class Dato:
    """Un valor con su fuente: así el informe dice de dónde salió cada cosa."""

    def __init__(self, valor, fuente):
        self.valor = valor
        self.fuente = fuente

    def __bool__(self):
        return bool(self.valor)

    def __repr__(self):
        return "%r (%s)" % (self.valor, self.fuente)


def _php_bloque(texto, clave):
    """El contenido del array `'clave' => [ ... ]` de un archivo de configuración PHP."""
    m = re.search(r"['\"]%s['\"]\s*=>\s*(\[|array\s*\()" % re.escape(clave), texto)
    if not m:
        return None
    abre = m.group(1)[-1]
    cierra = "]" if abre == "[" else ")"
    i, prof = m.end(), 1
    while i < len(texto) and prof:
        if texto[i] == abre:
            prof += 1
        elif texto[i] == cierra:
            prof -= 1
        i += 1
    return texto[m.end():i - 1]


def _php_valor(texto, *ruta):
    """`'a' => ['b' => 'valor']` → _php_valor(texto, 'a', 'b'). Une concatenaciones de literales."""
    for clave in ruta[:-1]:
        texto = _php_bloque(texto, clave)
        if texto is None:
            return None
    m = re.search(r"['\"]%s['\"]\s*=>\s*((?:'(?:[^'\\]|\\.)*'|\"(?:[^\"\\]|\\.)*\")(?:\s*\.\s*(?:'(?:[^'\\]|\\.)*'|\"(?:[^\"\\]|\\.)*\"))*)"
                  % re.escape(ruta[-1]), texto)
    if not m:
        return None
    partes = re.findall(r"'((?:[^'\\]|\\.)*)'|\"((?:[^\"\\]|\\.)*)\"", m.group(1))
    valor = "".join(a or b for a, b in partes).replace("\\'", "'").replace('\\"', '"')
    return valor.strip() or None


def _env(ruta):
    """{CLAVE: valor} de un .env, sin comillas."""
    valores = {}
    for linea in _texto(ruta).splitlines():
        m = re.match(r"\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_.\-]*)\s*=\s*(.*)$", linea)
        if m:
            v = m.group(2).strip()
            if len(v) >= 2 and v[0] == v[-1] and v[0] in "'\"":
                v = v[1:-1]
            valores[m.group(1)] = v
    return valores


def _git(raiz, *args):
    try:
        r = subprocess.run(["git", "-C", str(raiz)] + list(args), stdout=subprocess.PIPE,
                           stderr=subprocess.DEVNULL, timeout=20)
        return r.stdout.decode("utf-8", "replace") if r.returncode == 0 else ""
    except (OSError, subprocess.SubprocessError):
        return ""


def _remoto_limpio(url):
    """URL pública del repositorio, sin usuario ni token aunque los lleve."""
    url = url.strip()
    if not url:
        return ""
    m = re.match(r"git@([^:]+):(.+?)(?:\.git)?$", url)
    if m:
        return "https://%s/%s" % (m.group(1), m.group(2))
    m = re.match(r"(https?)://(?:[^@/]+@)?([^/]+)/(.+?)(?:\.git)?/?$", url)
    if m:
        return "%s://%s/%s" % (m.group(1), m.group(2), m.group(3))
    return ""


def _primera_frase_doc(texto):
    """Primera frase del primer comentario de documentación de un archivo.

    Se salta las cabeceras de licencia («This file is part of CodeIgniter 4…»): no
    dicen qué hace el archivo.
    """
    licencia = re.compile(r"This file is part of|Copyright|@license|For the full copyright", re.I)
    bloques = [b for b in re.findall(r"/\*\*(.*?)\*/", texto, re.S) if not licencia.search(b)]
    if not bloques:
        m = re.search(r'^\s*(?:"""|\'\'\')(.*?)(?:"""|\'\'\')', texto, re.S)
        bloques = [m.group(1)] if m and not licencia.search(m.group(1)) else []
    if not bloques:
        return ""
    parrafo = []
    for l in (re.sub(r"^\s*\*\s?", "", x).strip() for x in bloques[0].splitlines()):
        if not l:
            if parrafo:
                break
            continue
        if l.startswith("@"):
            break
        parrafo.append(l)
    frase = " ".join(parrafo)
    corte = re.search(r"(?<=[.:])\s", frase)
    return (frase[:corte.start()] if corte else frase).strip()


# Lo que traen de serie las plantillas de los frameworks: no dice nada del proyecto
_NOMBRES_DE_SERIE = {"laravel", "laravel/laravel", "symfony/skeleton", "symfony/website-skeleton",
                     "codeigniter4/appstarter", "codeigniter4/framework", "codeigniter/framework", "framework",
                     "cakephp/app", "slim/slim-skeleton", "my-app", "my-project",
                     "vite-project", "react-app", "vue-project", "app", "project", "web", "frontend",
                     "nuxt-app", "next-app", "sveltekit", "astro", "angular"}
_FRASES_DE_SERIE = re.compile(r"skeleton application|the laravel framework|a new symfony project|"
                              r"the codeigniter framework|codeigniter4? (starter|application starter)|"
                              r"starter (app|kit|template)|bootstrapped with|^\s*$", re.I)


# Lo que significan las variables de entorno habituales (Laravel, Node, Django…), para
# cuando el .env.example no trae comentarios. Sólo nombres estándar; lo propio del
# proyecto se queda como «Propia del proyecto».
_VARIABLES = {
    "APP_NAME": "nombre de la aplicación", "APP_ENV": "entorno (local, production…)",
    "APP_KEY": "clave de cifrado (php artisan key:generate)", "APP_DEBUG": "errores detallados en pantalla (sólo en desarrollo)",
    "APP_URL": "dirección de la aplicación", "APP_LOCALE": "idioma", "APP_FALLBACK_LOCALE": "idioma de reserva",
    "APP_FAKER_LOCALE": "idioma de los datos de prueba", "APP_MAINTENANCE_DRIVER": "cómo se guarda el modo mantenimiento",
    "APP_TIMEZONE": "zona horaria", "BCRYPT_ROUNDS": "coste del cifrado de contraseñas",
    "DB_CONNECTION": "tipo de base de datos", "DB_HOST": "servidor de la base de datos", "DB_PORT": "puerto",
    "DB_DATABASE": "nombre de la base de datos", "DB_USERNAME": "usuario", "DB_PASSWORD": "contraseña",
    "DATABASE_URL": "conexión a la base de datos", "SESSION_DRIVER": "dónde se guardan las sesiones",
    "SESSION_LIFETIME": "minutos que dura una sesión", "SESSION_ENCRYPT": "cifrar las sesiones",
    "SESSION_PATH": "ruta de la cookie de sesión", "SESSION_DOMAIN": "dominio de la cookie de sesión",
    "BROADCAST_CONNECTION": "difusión de eventos en tiempo real", "BROADCAST_DRIVER": "difusión de eventos en tiempo real",
    "FILESYSTEM_DISK": "dónde se guardan los archivos", "QUEUE_CONNECTION": "cola de tareas en segundo plano",
    "CACHE_STORE": "dónde se guarda la caché", "CACHE_DRIVER": "dónde se guarda la caché", "CACHE_PREFIX": "prefijo de la caché",
    "MEMCACHED_HOST": "servidor de Memcached", "NODE_ENV": "entorno de Node (development, production)",
    "PORT": "puerto en el que escucha la aplicación", "HOST": "dirección en la que escucha la aplicación",
    "SECRET_KEY": "clave secreta de la aplicación", "DEBUG": "modo depuración", "ALLOWED_HOSTS": "dominios permitidos",
    "JWT_SECRET": "clave para firmar los tokens", "LOG_LEVEL": "nivel de detalle del registro",
    "CI_ENVIRONMENT": "entorno de CodeIgniter (development, production)", "app.baseURL": "dirección base de la aplicación",
    "app_baseURL": "dirección base de la aplicación", "encryption.key": "clave de cifrado",
}
_PREFIJOS_VARIABLES = [
    ("DB_", "Conexión a la base de datos"), ("MAIL_", "Envío de correo"), ("REDIS_", "Conexión a Redis"),
    ("AWS_", "Almacenamiento en Amazon S3"), ("SESSION_", "Sesiones de usuario"), ("LOG_", "Registro de errores y avisos"),
    ("PUSHER_", "Notificaciones en tiempo real (Pusher)"), ("VITE_", "Valores que llegan al JavaScript (Vite)"),
    ("MEMCACHED_", "Conexión a Memcached"), ("CACHE_", "Caché"), ("STRIPE_", "Pagos con Stripe"),
    ("GOOGLE_", "Servicios de Google"), ("SMTP_", "Envío de correo"), ("NEXT_PUBLIC_", "Valores que llegan al navegador (Next.js)"),
    ("REACT_APP_", "Valores que llegan al navegador (React)"),
    ("database.default.", "Conexión a la base de datos"), ("database.tests.", "Base de datos de las pruebas"),
    ("session.", "Sesiones de usuario"), ("cookie.", "Cookies"), ("security.", "Protección contra CSRF"),
    ("logger.", "Registro de errores"), ("email.", "Envío de correo"), ("encryption.", "Cifrado"),
    ("honeypot.", "Trampa anti-bots de los formularios"), ("app.", "Configuración de la aplicación"),
]


def describir_variables(nombres):
    """Qué hace un grupo de variables estándar. "" si no son conocidas."""
    for prefijo, que in _PREFIJOS_VARIABLES:
        if len(nombres) > 1 and all(n.startswith(prefijo) for n in nombres):
            return que
    partes = []
    for n in nombres:
        d = _VARIABLES.get(n) or next((q[:1].lower() + q[1:] for pre, q in _PREFIJOS_VARIABLES if n.startswith(pre)), "")
        if not d:
            return ""   # si una no se conoce, mejor no adivinar el grupo
        if d not in partes:
            partes.append(d)
    texto = "; ".join(partes)
    return texto[:1].upper() + texto[1:]


def _de_serie_nombre(n):
    return (n or "").strip().lower() in _NOMBRES_DE_SERIE


def _de_serie_frase(t):
    return bool(_FRASES_DE_SERIE.search(t or ""))


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


class Proyecto:
    def __init__(self, raiz):
        self.raiz = Path(raiz).resolve()
        self.composer = _json(self.raiz / "composer.json")
        self.package = _json(self.raiz / "package.json")
        self.cfg_app = _texto(self.raiz / "config" / "app.php")
        self.cfg_pie = _texto(self.raiz / "config" / "pie.php")
        self.env_ejemplo = next((self.raiz / f for f in (".env.example", ".env.sample", ".env.dist", "env.example")
                                 if (self.raiz / f).is_file()), None)
        self.env = _env(self.raiz / ".env.example") if self.env_ejemplo else {}
        self._php = None

    # ---------------------------------------------------------------- básicos
    def archivos_php(self):
        """El código PHP del proyecto, sin los scripts sueltos de depuración de la carpeta pública."""
        if self._php is None:
            sueltos = {self.raiz / x for x in self.expuestos_en_web()}
            self._php = [f for f in _archivos(self.raiz, (".php",), 3000) if f not in sueltos]
        return self._php

    def nombre(self):
        v = _php_valor(self.cfg_app, "nombre")
        if v:
            return Dato(v, "config/app.php")
        for clave in ("APP_NAME",):
            for f in (".env", ".env.example"):
                e = _env(self.raiz / f)
                if e.get(clave) and e[clave] != "Laravel":
                    return Dato(e[clave], f)
        for k in ("displayName", "productName"):
            if self.package.get(k):
                return Dato(self.package[k], "package.json")
        if self.ecosistema()["nombre"]:
            return self.ecosistema()["nombre"]
        paginas = _archivos(self.raiz, (".html", ".htm", ".php", ".twig", ".erb", ".cshtml", ".hbs", ".ejs",
                                        ".njk", ".astro", ".vue", ".svelte"), 400)
        hallado = nombre_de_titulos(_texto(f, 400000) for f in paginas)
        if hallado:
            return Dato(hallado[0], "los títulos de las páginas")
        if self.package.get("name") and not _de_serie_nombre(self.package["name"]):
            n = self.package["name"].split("/")[-1].replace("-", " ").replace("_", " ")
            return Dato(n[:1].upper() + n[1:], "package.json")
        if self.composer.get("name") and not _de_serie_nombre(self.composer["name"]):
            n = self.composer["name"].split("/")[-1].replace("-", " ")
            return Dato(n[:1].upper() + n[1:], "composer.json")
        # Sin una fuente fiable no hay propuesta: el nombre de la carpeta no lo es, y se pregunta
        return Dato("", "")

    def frase(self):
        for clave in ("subtitulo", "descripcion"):
            v = _php_valor(self.cfg_app, clave)
            if v:
                return Dato(v, "config/app.php")
        for f, d in (("package.json", self.package), ("composer.json", self.composer)):
            if d.get("description") and not _de_serie_frase(d["description"]):
                return Dato(d["description"], f)
        return self.ecosistema()["frase"] or Dato("", "")

    def descripcion(self):
        v = _php_valor(self.cfg_app, "descripcion") or _php_valor(self.cfg_pie, "empresa", "descripcion")
        if v:
            return Dato(v, "config/app.php" if _php_valor(self.cfg_app, "descripcion") else "config/pie.php")
        return self.frase()

    def version(self):
        v = _php_valor(self.cfg_pie, "version") or _php_valor(self.cfg_app, "version")
        if v:
            return Dato(re.sub(r"\(\s*", "(", re.sub(r"\s*\)", ")", v)), "config/pie.php" if _php_valor(self.cfg_pie, "version") else "config/app.php")
        for f, d in (("package.json", self.package), ("composer.json", self.composer)):
            if d.get("version"):
                return Dato(d["version"], f)
        m = re.search(r'^\s*version\s*=\s*["\']([^"\']+)', _texto(self.raiz / "pyproject.toml"), re.M)
        if m:
            return Dato(m.group(1), "pyproject.toml")
        for cs in self.raiz.glob("*.csproj"):
            m = re.search(r"<Version>([^<]+)</Version>", _texto(cs))
            if m:
                return Dato(m.group(1), cs.name)
        return self.ecosistema()["version"] or Dato("", "")

    def empresa(self):
        e = {}
        for k in ("nombre", "logo", "web"):
            v = _php_valor(self.cfg_pie, "empresa", k)
            if v:
                e[k] = v
        if e.get("logo") and not (self.raiz / e["logo"]).is_file():
            del e["logo"]
        if "logo" not in e:
            for f in _archivos(self.raiz, (".png", ".svg", ".jpg", ".jpeg"), 3000):
                n = _sin_tildes(f.stem)
                if ("logo" in n or "empresa" in n) and DIR_IMG not in _rel(self.raiz, f):
                    e["logo"] = _rel(self.raiz, f)
                    break
        email = _php_valor(self.cfg_pie, "soporte", "email")
        if email:
            e["soporte"] = email
        return Dato(e, "config/pie.php" if self.cfg_pie else "archivos de imagen")

    def desarrollador(self):
        d = {}
        for k in ("nombre", "cargo", "github"):
            v = _php_valor(self.cfg_pie, "desarrollador", k)
            if v:
                d[k] = v
        return d

    def remoto(self):
        return Dato(_remoto_limpio(_git(self.raiz, "remote", "get-url", "origin")), "git remote")

    def licencia(self):
        for f in ("LICENSE", "LICENSE.md", "LICENSE.txt", "LICENCIA", "LICENCIA.md", "COPYING"):
            t = _texto(self.raiz / f)
            # El LICENSE que trae copiado un framework (CodeIgniter, Laravel…) es el suyo, no el del proyecto
            if t and re.search(r"CodeIgniter Foundation|British Columbia Institute of Technology|Taylor Otwell|"
                               r"Fabien Potencier|Cake Software Foundation|Slim Framework Team|EllisLab", t):
                continue
            if t:
                for patron, nombre in ((r"MIT License", "MIT"), (r"Apache License", "Apache-2.0"),
                                       (r"GNU GENERAL PUBLIC LICENSE", "GPL"), (r"BSD", "BSD"),
                                       (r"Mozilla Public License", "MPL-2.0"), (r"ISC License", "ISC")):
                    if re.search(patron, t, re.I):
                        return Dato(nombre, f)
                return Dato("ver " + f, f)
        # La licencia que trae de serie una plantilla (laravel/laravel dice «MIT») no la eligió el proyecto
        lic = None
        for d in (self.package, self.composer):
            if d.get("license") and not _de_serie_nombre(d.get("name", "")):
                lic = d["license"]
                break
        if isinstance(lic, list):
            lic = ", ".join(lic)
        if lic and str(lic).upper() not in ("UNLICENSED", "PROPRIETARY"):
            return Dato(str(lic), "package.json" if lic == self.package.get("license") else "composer.json")
        return Dato("", "")

    # ------------------------------------------------------------ tecnología
    def php_minimo(self):
        req = (self.composer.get("require") or {}).get("php")
        if req:
            m = re.search(r"(\d+\.\d+)", req)
            return Dato((m.group(1) + "+") if m else req, "composer.json (%s)" % req)
        if not self.archivos_php():
            return Dato("", "")
        rasgos = [
            ("8.1", r"\breadonly\s+(?:class|public|private|protected|[A-Za-z?\\])|\b(?:public|private|protected)\s+readonly\b", "propiedades readonly"),
            ("8.1", r"^\s*enum\s+\w+", "enum"),
            ("8.1", r"\)\s*:\s*never\b", "el tipo never"),
            ("8.0", r"(?<![\w$>:])match\s*\(", "match"),
            ("8.0", r"\?->", "el operador ?->"),
            ("8.0", r"\bstr_(?:contains|starts_with|ends_with)\s*\(", "str_contains / str_starts_with"),
            ("7.4", r"\bfn\s*\(", "funciones flecha fn()"),
            ("7.0", r"declare\s*\(\s*strict_types", "strict_types"),
        ]
        mejor = None
        for f in self.archivos_php():
            t = _texto(f, 800000)
            for ver, patron, que in rasgos:
                if mejor and tuple(map(int, ver.split("."))) <= tuple(map(int, mejor[0].split("."))):
                    break
                if re.search(patron, t, re.M):
                    mejor = (ver, que, _rel(self.raiz, f))
                    break
        if mejor:
            return Dato(mejor[0] + "+", "%s usa %s" % (mejor[2], mejor[1]))
        return Dato("", "archivos .php")

    def extensiones_php(self):
        """[(extensión, función que la delata, archivo)]."""
        patrones = [
            ("odbc", r"\bodbc_connect\s*\("), ("pdo_mysql", r"mysql:host"), ("mysqli", r"\bmysqli_connect\s*\(|new\s+mysqli\b"),
            ("pdo_pgsql", r"pgsql:host"), ("pgsql", r"\bpg_connect\s*\("), ("sqlsrv", r"\bsqlsrv_connect\s*\(|sqlsrv:Server"),
            ("pdo_sqlite", r"sqlite:"), ("mbstring", r"\bmb_[a-z_]+\s*\("), ("curl", r"\bcurl_init\s*\("),
            ("gd", r"\bimagecreate[a-z]*\s*\("), ("intl", r"\bnew\s+(?:NumberFormatter|IntlDateFormatter|Collator)\b"),
            ("openssl", r"\bopenssl_[a-z_]+\s*\("), ("ldap", r"\bldap_connect\s*\("), ("zip", r"\bnew\s+ZipArchive\b"),
            ("iconv", r"\biconv\s*\("), ("soap", r"\bnew\s+SoapClient\b"),
        ]
        hallado = {}
        for f in self.archivos_php():
            t = _texto(f, 800000)
            for ext, pat in patrones:
                if ext not in hallado:
                    m = re.search(pat, t)
                    if m:
                        hallado[ext] = (m.group(0).rstrip("( "), _rel(self.raiz, f))
        for ext in (self.composer.get("require") or {}):
            if ext.startswith("ext-") and ext[4:] not in hallado:
                hallado[ext[4:]] = ("composer.json", "composer.json")
        return [(k, v[0], v[1]) for k, v in hallado.items()]

    def tecnologias(self):
        """[(nombre, versión, fuente, logo de shields, rol)] — rol: lenguaje, framework, base."""
        out = []
        deps = {}
        for k in ("dependencies", "devDependencies"):
            deps.update(self.package.get(k) or {})
        req = {}
        for k in ("require", "require-dev"):
            req.update(self.composer.get(k) or {})
        py = " ".join(_texto(self.raiz / f) for f in ("requirements.txt", "pyproject.toml", "Pipfile")).strip().lower()
        fuente_py = next((f for f in ("pyproject.toml", "requirements.txt", "Pipfile") if (self.raiz / f).is_file()), "manage.py")

        def ver(v):
            m = re.search(r"(\d+(?:\.\d+)?)", v or "")
            return (m.group(1) + "+") if m else ""

        php = self.php_minimo()
        if self.composer or self.archivos_php():
            out.append(("PHP", php.valor, php.fuente, "php", "lenguaje"))
        for paquete, nombre, logo in (("laravel/framework", "Laravel", "laravel"),
                                      ("symfony/framework-bundle", "Symfony", "symfony"),
                                      ("codeigniter4/framework", "CodeIgniter", "codeigniter")):
            if paquete in req:
                out.append((nombre, ver(req[paquete]), "composer.json", logo, "framework"))
        nucleo = self.raiz / "system" / "CodeIgniter.php"
        if not any(o[0] == "CodeIgniter" for o in out) and (
                nucleo.is_file() or str(self.composer.get("name", "")).startswith("codeigniter4/")):
            m = re.search(r"CI_VERSION\s*=\s*['\"]([\d.]+)", _texto(nucleo))
            out.append(("CodeIgniter", m.group(1) if m else "", "system/CodeIgniter.php" if m else "composer.json",
                        "codeigniter", "framework"))
        if self.package:
            motor = (self.package.get("engines") or {}).get("node", "")
            # Con un servidor en PHP o Python, Node sólo compila los estilos y scripts
            de_apoyo = bool(out)
            out.append(("Node.js", ver(motor), "package.json" + (" (engines)" if motor else ""), "nodedotjs",
                        "herramienta" if de_apoyo else "lenguaje"))
            for paquete, nombre, logo in (("next", "Next.js", "nextdotjs"), ("nuxt", "Nuxt", "nuxtdotjs"),
                                          ("@nestjs/core", "NestJS", "nestjs"), ("@remix-run/react", "Remix", "remix"),
                                          ("astro", "Astro", "astro"), ("gatsby", "Gatsby", "gatsby"),
                                          ("@angular/core", "Angular", "angular"), ("@sveltejs/kit", "SvelteKit", "svelte"),
                                          ("svelte", "Svelte", "svelte"), ("solid-js", "Solid", "solid"),
                                          ("react", "React", "react"), ("vue", "Vue", "vuedotjs"),
                                          ("fastify", "Fastify", "fastify"), ("koa", "Koa", "koa"), ("hono", "Hono", "hono"),
                                          ("express", "Express", "express")):
                if paquete in deps:
                    out.append((nombre, ver(deps[paquete]), "package.json", logo, "framework"))
                    break
            for paquete, nombre, logo in (("vite", "Vite", "vite"), ("webpack", "Webpack", "webpack"),
                                          ("laravel-mix", "Laravel Mix", "laravel")):
                if paquete in deps:
                    out.append((nombre, ver(deps[paquete]), "package.json", logo, "herramienta"))
                    break
        if py or (self.raiz / "manage.py").exists():
            m = re.search(r"requires-python\s*=\s*[\"']([^\"']+)", py)
            out.append(("Python", ver(m.group(1)) if m else "", fuente_py, "python", "lenguaje"))
        for cs in sorted(self.raiz.glob("*.csproj")) + sorted(self.raiz.glob("*/*.csproj")):
            m = re.search(r"<TargetFramework>net(\d+\.\d+)", _texto(cs))
            out.append((".NET", (m.group(1) + "+") if m else "", cs.name, "dotnet", "lenguaje"))
            break
        # Python, Go, Rust, Java, .NET, Ruby, Dart y WordPress: lo que digan sus archivos
        for t in self.ecosistema()["tecnologias"]:
            if t[0] not in [o[0] for o in out]:
                out.append(t)
        # Primero los lenguajes, después los frameworks y las herramientas
        orden = {"lenguaje": 0, "framework": 1, "herramienta": 2}
        out.sort(key=lambda t: orden.get(t[4], 3))
        out += self.bases_de_datos()
        return out

    # ----------------------------------------------------------- ecosistemas
    def ecosistema(self):
        """Lo que dicen los archivos de cada lenguaje: Python, Go, Rust, Java, .NET, Ruby, Dart y WordPress.

        Devuelve {"tecnologias", "bases", "pasos", "nombre", "frase", "version"}; cada dato con su
        fuente. Se calcula una vez.
        """
        if getattr(self, "_eco", None) is not None:
            return self._eco
        raiz = self.raiz
        tec, bases, pasos = [], [], []
        nombre = frase = version = None

        def ver(v, exacta=False):
            m = re.search(r"(\d+(?:\.\d+){0,2})", v or "")
            if not m:
                return ""
            return m.group(1) if exacta else re.match(r"\d+(?:\.\d+)?", m.group(1)).group(0) + "+"

        def base(n, logo, fuente):
            if n not in [b[0] for b in bases]:
                bases.append((n, "", fuente, logo, "base"))

        def toml(texto, seccion, clave):
            m = re.search(r"^\[%s\]\s*$(.*?)(?=^\[|\Z)" % re.escape(seccion), texto, re.M | re.S)
            if m:
                mm = re.search(r'^\s*%s\s*=\s*["\']([^"\']+)["\']' % re.escape(clave), m.group(1), re.M)
                return mm.group(1) if mm else None
            return None

        # ---- Python (requirements.txt, pyproject.toml, Pipfile)
        pyproject = _texto(raiz / "pyproject.toml")
        py = (" ".join(_texto(raiz / f) for f in ("requirements.txt", "Pipfile", "setup.py")) + " " + pyproject).lower()
        if py.strip():
            fuente = next(f for f in ("pyproject.toml", "requirements.txt", "Pipfile", "setup.py") if (raiz / f).is_file())
            for paquete, n, logo in (("fastapi", "FastAPI", "fastapi"), ("django", "Django", "django"),
                                     ("flask", "Flask", "flask")):
                m = re.search(r"(?m)^\s*[\"']?%s\b\s*(?:[=<>~!]=?\s*([\d.]+))?" % paquete, py)
                if m:
                    tec.append((n, ver(m.group(1)) if m.group(1) else "", fuente, logo, "framework"))
                    break
            for paquete, n, logo in (("psycopg", "PostgreSQL", "postgresql"), ("asyncpg", "PostgreSQL", "postgresql"),
                                     ("mysqlclient", "MySQL", "mysql"), ("pymysql", "MySQL", "mysql"),
                                     ("mysql-connector", "MySQL", "mysql"), ("pymongo", "MongoDB", "mongodb"),
                                     ("motor", "MongoDB", "mongodb"), ("pyodbc", "ODBC", "")):
                if re.search(r"(?m)^\s*[\"']?%s" % re.escape(paquete), py):
                    base(n, logo, fuente)
            if "[tool.poetry]" in pyproject:
                pasos.append("poetry install")
            elif (raiz / "requirements.txt").is_file():
                pasos.append("pip install -r requirements.txt")
            elif pyproject:
                pasos.append("pip install .")
            if (raiz / "manage.py").is_file():
                pasos.append("python manage.py migrate")
            n = toml(pyproject, "project", "name") or toml(pyproject, "tool.poetry", "name")
            if n:
                nombre = Dato(n, "pyproject.toml")
            d = toml(pyproject, "project", "description") or toml(pyproject, "tool.poetry", "description")
            if d:
                frase = Dato(d, "pyproject.toml")
            for f in _archivos(raiz, (".py",), 400):
                m = re.search(r"FastAPI\([^)]*title\s*=\s*[\"']([^\"']+)", _texto(f, 200000))
                if m:
                    nombre = Dato(m.group(1), "%s (FastAPI title)" % _rel(raiz, f))
                    break
        # ---- Go (go.mod)
        gomod = _texto(raiz / "go.mod")
        if gomod:
            m = re.search(r"(?m)^go\s+([\d.]+)", gomod)
            tec.append(("Go", ver(m.group(1)) if m else "", "go.mod", "go", "lenguaje"))
            for paquete, n in (("gin-gonic/gin", "Gin"), ("labstack/echo", "Echo"), ("gofiber/fiber", "Fiber"),
                               ("go-chi/chi", "Chi"), ("gorilla/mux", "Gorilla Mux")):
                m = re.search(re.escape(paquete) + r"\S*\s+v([\d.]+)", gomod)
                if m:
                    tec.append((n, ver(m.group(1)), "go.mod", "go", "framework"))
                    break
            for paquete, n, logo in (("lib/pq", "PostgreSQL", "postgresql"), ("jackc/pgx", "PostgreSQL", "postgresql"),
                                     ("go-sql-driver/mysql", "MySQL", "mysql"), ("mongo-driver", "MongoDB", "mongodb"),
                                     ("go-sqlite3", "SQLite", "sqlite"), ("modernc.org/sqlite", "SQLite", "sqlite")):
                if paquete in gomod:
                    base(n, logo, "go.mod")
            pasos += ["go mod download", "go run ."]
            m = re.search(r"(?m)^module\s+(\S+)", gomod)
            if m:
                nombre = Dato(m.group(1).rstrip("/").split("/")[-1], "go.mod")
        # ---- Rust (Cargo.toml)
        cargo = _texto(raiz / "Cargo.toml")
        if cargo:
            rv = toml(cargo, "package", "rust-version")
            tec.append(("Rust", ver(rv) if rv else "", "Cargo.toml", "rust", "lenguaje"))
            for paquete, n in (("axum", "Axum"), ("actix-web", "Actix Web"), ("rocket", "Rocket"), ("warp", "Warp")):
                m = re.search(r"(?m)^%s\s*=\s*(?:\"([\d.]+)\"|\{[^}]*version\s*=\s*\"([\d.]+)\")" % re.escape(paquete), cargo)
                if m:
                    tec.append((n, ver(m.group(1) or m.group(2)), "Cargo.toml", "rust", "framework"))
                    break
            for clave, n, logo in (("postgres", "PostgreSQL", "postgresql"), ("mysql", "MySQL", "mysql"),
                                   ("sqlite", "SQLite", "sqlite"), ("mongodb", "MongoDB", "mongodb")):
                if re.search(r"(sqlx|diesel|sea-orm|mongodb)[^\n]*%s|^%s" % (clave, clave), cargo, re.M):
                    base(n, logo, "Cargo.toml")
            pasos += ["cargo build", "cargo run"]
            n = toml(cargo, "package", "name")
            if n:
                nombre = Dato(n, "Cargo.toml")
            d = toml(cargo, "package", "description")
            if d:
                frase = Dato(d, "Cargo.toml")
            v = toml(cargo, "package", "version")
            if v:
                version = Dato(v, "Cargo.toml")
        # ---- Java / Kotlin (pom.xml, build.gradle)
        pom = _texto(raiz / "pom.xml")
        gradle = _texto(raiz / "build.gradle") + _texto(raiz / "build.gradle.kts")
        if pom or gradle:
            fuente = "pom.xml" if pom else ("build.gradle.kts" if (raiz / "build.gradle.kts").is_file() else "build.gradle")
            sin_padre = re.sub(r"<parent>.*?</parent>", "", pom, flags=re.S)
            m = (re.search(r"<(?:java\.version|maven\.compiler\.(?:source|release))>([\d.]+)<", pom)
                 or re.search(r"(?:sourceCompatibility\s*=\s*['\"]?|VERSION_|JavaLanguageVersion\.of\(|jvmToolchain\()(\d+)", gradle))
            lenguaje = "Kotlin" if any(_archivos(raiz, (".kt",), 50)) else "Java"
            tec.append((lenguaje, ver(m.group(1)) if m else "", fuente, "kotlin" if lenguaje == "Kotlin" else "openjdk",
                        "lenguaje"))
            m = (re.search(r"spring-boot-starter-parent</artifactId>\s*<version>([\d.]+)", pom)
                 or re.search(r"org\.springframework\.boot['\"]\)?\s*version\s*['\"]([\d.]+)", gradle))
            if m or "spring-boot" in pom + gradle:
                tec.append(("Spring Boot", ver(m.group(1)) if m else "", fuente, "springboot", "framework"))
            texto = pom + gradle + _texto(raiz / "src" / "main" / "resources" / "application.properties") \
                + _texto(raiz / "src" / "main" / "resources" / "application.yml")
            for clave, n, logo in (("postgresql", "PostgreSQL", "postgresql"), ("mysql", "MySQL", "mysql"),
                                   ("mssql", "SQL Server", "microsoftsqlserver"), ("sqlserver", "SQL Server", "microsoftsqlserver"),
                                   ("ojdbc", "Oracle", "oracle"), ("oracle", "Oracle", "oracle"),
                                   ("mongodb", "MongoDB", "mongodb"), ("h2database", "H2", "")):
                if clave in texto.lower():
                    base(n, logo, fuente if clave in (pom + gradle).lower() else "application.properties")
            if pom:
                pasos.append("./mvnw spring-boot:run" if (raiz / "mvnw").is_file() and "spring-boot" in pom
                             else ("./mvnw install" if (raiz / "mvnw").is_file() else "mvn install"))
                m = re.search(r"<name>([^<]+)</name>", sin_padre)
                if m:
                    nombre = Dato(m.group(1).strip(), "pom.xml")
                m = re.search(r"<description>([^<]+)</description>", sin_padre)
                if m:
                    frase = Dato(m.group(1).strip(), "pom.xml")
                m = re.search(r"</artifactId>\s*<version>([^<$]+)</version>", sin_padre)
                if m:
                    version = Dato(m.group(1).strip(), "pom.xml")
            else:
                pasos.append("./gradlew build" if (raiz / "gradlew").is_file() else "gradle build")
        # ---- .NET (*.csproj, también en una subcarpeta)
        csproj = sorted(raiz.glob("*.csproj")) + sorted(raiz.glob("*/*.csproj"))
        if csproj:
            cs = csproj[0]
            t = _texto(cs)
            if 'Sdk="Microsoft.NET.Sdk.Web"' in t:
                m = re.search(r"<TargetFramework>net(\d+\.\d+)", t)
                tec.append(("ASP.NET Core", (m.group(1) + "+") if m else "", cs.name, "dotnet", "framework"))
            todos = " ".join(_texto(c) for c in csproj)
            for clave, n, logo in (("SqlServer", "SQL Server", "microsoftsqlserver"), ("Npgsql", "PostgreSQL", "postgresql"),
                                   ("MySql", "MySQL", "mysql"), ("Sqlite", "SQLite", "sqlite"),
                                   ("MongoDB.Driver", "MongoDB", "mongodb"), ("Oracle", "Oracle", "oracle")):
                if clave in todos:
                    base(n, logo, cs.name)
            pasos += ["dotnet restore", "dotnet run" + ("" if cs.parent == raiz else " --project %s" % _rel(raiz, cs))]
            m = re.search(r"<(?:Product|AssemblyTitle|AssemblyName)>([^<]+)<", t)
            nombre = Dato(m.group(1).strip() if m else cs.stem, cs.name)
            m = re.search(r"<Description>([^<]+)<", t)
            if m:
                frase = Dato(m.group(1).strip(), cs.name)
        # ---- Ruby (Gemfile)
        gemfile = _texto(raiz / "Gemfile")
        if gemfile:
            m = re.search(r"(?m)^ruby\s+['\"]([\d.]+)", gemfile)
            tec.append(("Ruby", ver(m.group(1)) if m else "", "Gemfile", "ruby", "lenguaje"))
            m = re.search(r"(?m)^gem\s+['\"]rails['\"]\s*,\s*['\"][^\d]*([\d.]+)", gemfile)
            if m or re.search(r"(?m)^gem\s+['\"]rails['\"]", gemfile):
                tec.append(("Ruby on Rails", ver(m.group(1)) if m else "", "Gemfile", "rubyonrails", "framework"))
            elif re.search(r"(?m)^gem\s+['\"]sinatra['\"]", gemfile):
                tec.append(("Sinatra", "", "Gemfile", "ruby", "framework"))
            for gema, n, logo in (("pg", "PostgreSQL", "postgresql"), ("mysql2", "MySQL", "mysql"),
                                  ("sqlite3", "SQLite", "sqlite"), ("mongoid", "MongoDB", "mongodb")):
                if re.search(r"(?m)^gem\s+['\"]%s['\"]" % gema, gemfile):
                    base(n, logo, "Gemfile")
            pasos.append("bundle install")
            if (raiz / "bin" / "rails").is_file() or "rails" in gemfile:
                pasos.append("bin/rails db:setup")
        # ---- Dart / Flutter (pubspec.yaml)
        pubspec = _texto(raiz / "pubspec.yaml")
        if pubspec:
            m = re.search(r"(?m)^\s+sdk:\s*['\"]?[>=^]*\s*([\d.]+)", pubspec)
            tec.append(("Dart", ver(m.group(1)) if m else "", "pubspec.yaml", "dart", "lenguaje"))
            flutter = re.search(r"(?m)^\s+flutter:\s*$\s+sdk:\s*flutter", pubspec) is not None or "flutter:" in pubspec
            if flutter:
                tec.append(("Flutter", "", "pubspec.yaml", "flutter", "framework"))
            pasos.append("flutter pub get" if flutter else "dart pub get")
            for clave, n in (("name", "nombre"), ("description", "frase"), ("version", "version")):
                m = re.search(r"(?m)^%s:\s*['\"]?([^'\"\n#]+)" % clave, pubspec)
                if m:
                    valor = Dato(m.group(1).strip().split("+")[0] if clave == "version" else m.group(1).strip(),
                                 "pubspec.yaml")
                    if n == "nombre":
                        nombre = valor
                    elif n == "frase":
                        frase = valor
                    else:
                        version = valor
        # ---- WordPress (tema o plugin)
        if (raiz / "wp-config.php").is_file() or (raiz / "wp-content").is_dir() or (raiz / "wp-includes").is_dir():
            m = re.search(r"\$wp_version\s*=\s*'([\d.]+)'", _texto(raiz / "wp-includes" / "version.php"))
            tec.append(("WordPress", m.group(1) if m else "", "wp-includes/version.php" if m else "wp-config.php",
                        "wordpress", "framework"))
        for f in [raiz / "style.css"] + sorted(raiz.glob("wp-content/themes/*/style.css")) + sorted(raiz.glob("*.php"))[:20]:
            m = re.search(r"(?:Theme|Plugin) Name:\s*(.+)", _texto(f, 20000))
            if m:
                nombre = Dato(m.group(1).strip(), _rel(raiz, f))
                mm = re.search(r"Description:\s*(.+)", _texto(f, 20000))
                if mm:
                    frase = Dato(mm.group(1).strip(), _rel(raiz, f))
                break
        if nombre is not None and _de_serie_nombre(nombre.valor):
            nombre = None
        # «nomina-cli», «mi_app»: nombres de paquete, no de aplicación; se dejan legibles
        if nombre is not None and re.fullmatch(r"[a-z0-9]+(?:[-_.][a-z0-9]+)*", nombre.valor):
            legible = re.sub(r"[-_.]+", " ", nombre.valor)
            nombre = Dato(legible[:1].upper() + legible[1:], nombre.fuente)
        if frase is not None and _de_serie_frase(frase.valor):
            frase = None
        self._eco = {"tecnologias": tec, "bases": bases, "pasos": pasos, "nombre": nombre, "frase": frase,
                     "version": version}
        return self._eco

    def bases_de_datos(self):
        out = []
        # Lo que dice la configuración del proyecto manda sobre lo que se adivina del código
        driver = self.env.get("database.default.DBDriver") or self.env.get("database_default_DBDriver")
        if not driver:
            bloque = _php_bloque(_texto(self.raiz / "app" / "Config" / "Database.php"), "default") or ""
            m = re.search(r"^\s*['\"]DBDriver['\"]\s*=>\s*['\"](\w+)", bloque, re.M)
            driver = m.group(1) if m else ""
        nombres_ci = {"mysqli": ("MySQL", "mysql"), "postgre": ("PostgreSQL", "postgresql"),
                      "sqlite3": ("SQLite", "sqlite"), "sqlsrv": ("SQL Server", "microsoftsqlserver"),
                      "oci8": ("Oracle", "oracle")}
        if driver.lower() in nombres_ci:
            n, logo = nombres_ci[driver.lower()]
            return [(n, "", "configuración de la base de datos (DBDriver %s)" % driver, logo, "base")]
        claves = " ".join(self.env)
        exts = {e for e, _f, _a in self.extensiones_php()} if self.archivos_php() else set()
        if re.search(r"\bAS400_|\bIBMI_|\bDB2_", claves) or (self.raiz / "config" / "as400.php").exists():
            fuente = ".env.example" if re.search(r"\bAS400_", claves) else "config/as400.php"
            out.append(("IBM AS400", "DB2 for i", fuente + (" + odbc_connect" if "odbc" in exts else ""), "ibm", "base"))
        if "pdo_mysql" in exts or "mysqli" in exts or self.env.get("DB_CONNECTION") == "mysql":
            out.append(("MySQL", "", "código PHP" if exts & {"pdo_mysql", "mysqli"} else ".env.example", "mysql", "base"))
        if exts & {"pdo_pgsql", "pgsql"} or self.env.get("DB_CONNECTION") == "pgsql":
            out.append(("PostgreSQL", "", "código" if exts & {"pdo_pgsql", "pgsql"} else ".env.example", "postgresql", "base"))
        if "sqlsrv" in exts:
            out.append(("SQL Server", "", "código PHP", "microsoftsqlserver", "base"))
        deps = " ".join(list((self.package.get("dependencies") or {}).keys()))
        for paquete, nombre, logo in (("mongoose", "MongoDB", "mongodb"), ("mongodb", "MongoDB", "mongodb"),
                                      ("pg", "PostgreSQL", "postgresql"), ("mysql2", "MySQL", "mysql"),
                                      ("mysql", "MySQL", "mysql"), ("sqlite3", "SQLite", "sqlite"),
                                      ("better-sqlite3", "SQLite", "sqlite"), ("mssql", "SQL Server", "microsoftsqlserver"),
                                      ("oracledb", "Oracle", "oracle"), ("prisma", "Prisma", "prisma")):
            if re.search(r"(^|\s)%s(\s|$)" % re.escape(paquete), deps) and nombre not in [o[0] for o in out]:
                out.append((nombre, "", "package.json", logo, "base"))
        for b in self.ecosistema()["bases"]:
            if b[0] not in [o[0] for o in out]:
                out.append(b)
        return out

    # --------------------------------------------------------------- colores
    def colores(self):
        """(principal, oscuro) del sistema de diseño del proyecto, cada uno con su fuente.

        Si el proyecto no tiene colores, el valor lleva `supuesto = True` y el
        asistente los pregunta: no se inventan.
        """
        if getattr(self, "_colores", None):
            return self._colores
        extras = []
        tema = _php_valor(self.cfg_app, "tema")
        if tema:
            extras.append((4, "theme-color", tema, self.raiz / "config" / "app.php"))
        det = paleta_del_proyecto(self.raiz, extras)
        self.paleta = det
        if det["supuesto"]:
            pr = Dato("#475569", "no hay colores en el proyecto: gris neutro")
            os_ = Dato("#0f172a", "no hay colores en el proyecto: gris neutro")
            pr.supuesto = os_.supuesto = True
        else:
            def dato(c):
                return Dato(c[0], "%s (`%s`)" % (c[2], c[1]) if c[1] else c[2])
            pr, os_ = dato(det["primario"]), dato(det["oscuro"])
        self._colores = (pr, os_)
        return self._colores

    def icono(self):
        # El de generate_icon lleva una palabra en el nombre (icono-inventario.svg): se busca primero, y
        # sólo si lo generó esa herramienta, para no confundirlo con iconos de la interfaz (icono-buscar.svg).
        for f in _archivos(self.raiz, (".svg",), 3000):
            if re.fullmatch(r"icono-[a-z0-9][a-z0-9-]*", f.stem) and "generate_icon" in _texto(f, 200000)[:1500]:
                return f
        for f in ("vistas/img/icono.svg", "public/img/icono.svg", "public/icono.svg", "assets/img/icono.svg",
                  "img/icono.svg", "static/img/icono.svg", "wwwroot/img/icono.svg", "public/favicon.svg",
                  "app/icon.svg", "src/app/icon.svg", "public/icon.svg"):
            if (self.raiz / f).is_file():
                return self.raiz / f
        for f in _archivos(self.raiz, (".svg",), 3000):
            if f.stem.lower() in ("icono", "icon", "favicon"):
                return f
        return None

    # ---------------------------------------------------------- contenido
    def capturas(self):
        d = self.raiz / DIR_IMG
        existe = {f for f in d.iterdir() if f.is_file()} if d.is_dir() else set()
        pantallas = sorted(f for f in existe if f.name.lower().startswith("pantalla")
                           and f.suffix.lower() in (".png", ".jpg", ".jpeg", ".gif", ".webp"))
        temas = None
        for ext in (".png", ".jpg", ".webp"):
            c, o = d / ("tema-claro" + ext), d / ("tema-oscuro" + ext)
            if c in existe and o in existe:
                temas = (c, o)
        return pantallas, temas

    def variables(self):
        """Bloques de .env.example: [(título, [(comentario, [variables], valores)])], aviso inicial.

        Entiende los dos estilos de título habituales: «# --- Base de datos ---» y el de
        CodeIgniter, con el título entre dos líneas de guiones. Las variables comentadas
        (# app.baseURL = …) están desactivadas: no son explicaciones y no se listan.
        """
        if not self.env_ejemplo:
            return [], ""
        lineas = _texto(self.env_ejemplo).splitlines()

        def regla(t):
            return re.match(r"#\s*[=\-*_#~]{5,}\s*$", t.strip())

        def desactivada(t):
            return re.match(r"#\s*(?:export\s+)?[A-Za-z_][\w.\-]*\s*=", t.strip())

        bloques, actual, comentario, grupo, aviso = [], None, [], None, []
        antes_de_todo = True
        for i, linea in enumerate(lineas):
            s = linea.strip()
            titulo = None
            cab = re.match(r"#\s*-{2,}\s*(.+?)\s*-*\s*$", s)
            if cab and not regla(s):
                titulo = cab.group(1).strip("- ")
            elif (s.startswith("#") and not regla(s) and not desactivada(s) and 0 < i < len(lineas) - 1
                  and regla(lineas[i - 1]) and regla(lineas[i + 1]) and len(s) < 70):
                titulo = s.lstrip("#").strip()
            if titulo:
                if titulo.isupper():
                    titulo = titulo.capitalize()
                actual = (titulo, [])
                bloques.append(actual)
                comentario, grupo, antes_de_todo = [], None, False
                continue
            if regla(s) or desactivada(s):
                continue
            if s.startswith("#"):
                texto = re.sub(r"^#\s?", "", s)
                if antes_de_todo and not bloques:
                    aviso.append(texto)
                else:
                    grupo = None
                    comentario.append(texto)
                continue
            m = re.match(r"\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_.\-]*)\s*=\s*(.*)$", linea)
            if m:
                antes_de_todo = False
                if actual is None:
                    actual = ("General", [])
                    bloques.append(actual)
                if grupo is None:
                    grupo = ([c for c in comentario if c.strip()], [], [])
                    actual[1].append(grupo)
                    comentario = []
                grupo[1].append(m.group(1))
                grupo[2].append(m.group(2).strip().strip("'\""))
                continue
            if not s:
                grupo = None
                if antes_de_todo and aviso and aviso[-1] != "":
                    aviso.append("")
        return [(t, g) for t, g in bloques if g], "\n".join(aviso).strip()

    def expuestos_en_web(self):
        """Scripts de depuración, pruebas o respaldos dentro de la raíz web (se pueden abrir por URL)."""
        web = self.raiz / "public" if (self.raiz / "public").is_dir() else self.raiz
        patron = re.compile(r"(^|[_.-])(debug|depura|test|prueba|fix|phpinfo|info|backup|respaldo|dump|old|copia)"
                            r"([_.-]|$)|\.(sql|bak|log|old|orig)$|^debug|^test", re.I)
        salida = []
        for f in sorted(web.iterdir()) if web.is_dir() else []:
            if f.is_file() and f.suffix.lower() in (".php", ".sql", ".log", ".txt", ".bak", ".old", ".orig", ".zip") \
                    and f.name.lower() not in ("robots.txt", "humans.txt", "license.txt") and patron.search(f.stem + f.suffix):
                salida.append(_rel(self.raiz, f))
        return salida

    def gitignore_env(self):
        t = _texto(self.raiz / ".gitignore")
        return bool(re.search(r"^/?\.env\s*$", t, re.M))

    def contribuidores(self):
        crudo = _git(self.raiz, "log", "--format=%aN\t%aE")
        por_correo = {}
        for linea in crudo.splitlines():
            if "\t" not in linea:
                continue
            nombre, email = (x.strip() for x in linea.split("\t", 1))
            if _BOTS.search(email) or _BOTS.search(nombre):
                continue
            nombres = por_correo.setdefault(email.lower(), {})
            nombres[nombre] = nombres.get(nombre, 0) + 1
        cuenta = {}
        for email, nombres in por_correo.items():
            # El nombre más completo con el que firmó («Isabella Pernia» mejor que «Isabella»)
            nombre = sorted(nombres, key=lambda n: (-len(n.split()), -nombres[n], n))[0]
            c = cuenta.setdefault(_sin_tildes(nombre), {"nombre": nombre, "emails": set(), "commits": 0})
            c["emails"].add(email)
            c["commits"] += sum(nombres.values())
        dev = self.desarrollador()
        salida = []
        for c in sorted(cuenta.values(), key=lambda x: -x["commits"]):
            usuario = ""
            for e in c["emails"]:
                m = re.match(r"(?:\d+\+)?([A-Za-z0-9-]+)@users\.noreply\.github\.com$", e)
                if m:
                    usuario = m.group(1)
            if not usuario and dev.get("github") and _sin_tildes(dev.get("nombre", "")) == _sin_tildes(c["nombre"]):
                usuario = dev["github"]
            papel = dev.get("cargo") if _sin_tildes(dev.get("nombre", "")) == _sin_tildes(c["nombre"]) else ""
            salida.append({"nombre": c["nombre"], "usuario": usuario, "commits": c["commits"], "papel": papel})
        return salida

    def documentos(self):
        out = []
        d = self.raiz / "docs"
        if d.is_dir():
            for f in sorted(d.rglob("*")):
                if not f.is_file() or DIR_IMG in _rel(self.raiz, f) or f.name.startswith("."):
                    continue
                if f.suffix.lower() == ".md":
                    m = re.search(r"^#\s+(.+)$", _texto(f), re.M)
                    out.append((_rel(self.raiz, f), m.group(1).strip() if m else f.stem))
                elif f.suffix.lower() == ".pdf":
                    out.append((_rel(self.raiz, f), f.stem.replace("-", " ").replace("_", " ").capitalize()))
        for f in ("CHANGELOG.md", "CONTRIBUTING.md", "MANUAL.md"):
            if (self.raiz / f).is_file():
                m = re.search(r"^#\s+(.+)$", _texto(self.raiz / f), re.M)
                out.append((f, m.group(1).strip() if m else f))
        return out

    def guia_instalacion(self):
        for rel, _t in self.documentos():
            if re.search(r"instala|install|despliegue|deploy", _sin_tildes(rel)):
                return rel
        return None

    def ordenes(self):
        """[(orden, qué hace, fuente)] de package.json, composer.json y Makefile."""
        out = []
        for k, v in (self.package.get("scripts") or {}).items():
            out.append(("npm run " + k, v, "package.json"))
        for k, v in (self.composer.get("scripts") or {}).items():
            if not k.startswith(("pre-", "post-")):
                out.append(("composer run " + k, v if isinstance(v, str) else " && ".join(map(str, v)), "composer.json"))
        mk = _texto(self.raiz / "Makefile")
        for m in re.finditer(r"^([A-Za-z][\w-]*):(?!=)", mk, re.M):
            out.append(("make " + m.group(1), "", "Makefile"))
        return out[:12]

    def interruptores_desarrollo(self):
        """Variables de .env.example cuyo comentario habla de desarrollo o pruebas."""
        bloques, _aviso = self.variables()
        out = []
        for _titulo, grupos in bloques:
            for comentario, nombres, valores in grupos:
                t = _sin_tildes(" ".join(comentario))
                if re.search(r"desarrollo|pruebas|debug|depuraci|local|demo", t):
                    out.append((nombres, valores, comentario))
        return out

    # ------------------------------------------------------------ arquitectura
    DESCRIPCIONES = {
        "config": "Configuración", "controladores": "Controladores", "controllers": "Controladores",
        "modelos": "Modelos: acceso a datos", "models": "Modelos: acceso a datos",
        "vistas": "Vistas: plantillas, estilos, scripts e imágenes", "views": "Vistas",
        "servicios": "Servicios compartidos", "services": "Servicios compartidos",
        "public": "Raíz web pública", "src": "Código fuente", "app": "Código de la aplicación",
        "routes": "Rutas", "resources": "Recursos: vistas y estilos", "database": "Migraciones y semillas",
        "tests": "Pruebas", "pruebas": "Pruebas", "docs": "Documentación", "herramientas": "Herramientas de desarrollo",
        "tools": "Herramientas de desarrollo", "scripts": "Scripts", "assets": "Recursos estáticos",
        "static": "Archivos estáticos", "templates": "Plantillas", "components": "Componentes",
        "pages": "Páginas", "lib": "Bibliotecas propias", "api": "API", "ajax": "Puntos de entrada AJAX",
        "migrations": "Migraciones", "wwwroot": "Raíz web pública", "modulos": "Módulos de la interfaz",
        "css": "Hojas de estilo", "js": "Scripts", "img": "Imágenes", "helpers": "Funciones de apoyo",
        "middleware": "Middleware", "includes": "Archivos incluidos", "inc": "Archivos incluidos",
        "bootstrap": "Arranque de la aplicación", "http": "Controladores, middleware y peticiones",
        "providers": "Proveedores de servicios", "console": "Órdenes de consola", "exceptions": "Gestión de errores",
        "jobs": "Tareas en segundo plano", "mail": "Correos", "events": "Eventos", "listeners": "Oyentes de eventos",
        "policies": "Reglas de permisos", "notifications": "Notificaciones", "requests": "Validación de formularios",
        "images": "Imágenes", "imagenes": "Imágenes", "fonts": "Tipografías", "icons": "Iconos", "uploads": "Archivos subidos",
        "lang": "Traducciones", "locales": "Traducciones", "seeders": "Datos de prueba", "factories": "Fábricas de datos de prueba",
        "layouts": "Plantillas base", "partials": "Fragmentos de vistas", "utils": "Utilidades", "hooks": "Hooks",
        "store": "Estado de la aplicación", "styles": "Hojas de estilo", "auth": "Autenticación", "admin": "Administración",
        "writable": "Lo que escribe la aplicación: caché, registros y subidas", "filters": "Filtros de las peticiones",
        "language": "Traducciones", "libraries": "Bibliotecas propias", "thirdparty": "Librerías de terceros",
        "third_party": "Librerías de terceros",
        "cmd": "Programas ejecutables", "internal": "Código interno del módulo", "pkg": "Paquetes reutilizables",
        "spec": "Pruebas", "test": "Pruebas", "android": "Proyecto de Android", "ios": "Proyecto de iOS",
        "macos": "Proyecto de macOS", "windows": "Proyecto de Windows", "linux": "Proyecto de Linux",
        "web": "Versión web", "properties": "Configuración de .NET", "wp-content": "Temas, plugins y archivos subidos",
        "themes": "Temas", "migrations": "Migraciones", "handlers": "Manejadores de las peticiones",
        "routers": "Rutas", "schemas": "Esquemas de datos", "entities": "Entidades", "repositories": "Repositorios de datos",
        "dto": "Objetos de transferencia de datos", "domain": "Dominio", "infrastructure": "Infraestructura",
        "scripts": "Scripts", "bin": "Ejecutables", "db": "Base de datos",
    }
    # Dentro de otra carpeta, estos nombres pueden ser cualquier cosa (public/app no es el código de la app)
    AMBIGUOS_DENTRO = {"app", "src", "public", "static", "api", "lib", "admin", "auth", "assets", "store", "pages"}
    ARCHIVOS_CONOCIDOS = {
        "composer.json": "Dependencias de PHP", "package.json": "Dependencias y órdenes de JavaScript",
        "package-lock.json": "Versiones exactas de las dependencias de JavaScript", "vite.config.js": "Configuración de Vite",
        "vite.config.ts": "Configuración de Vite", "webpack.mix.js": "Configuración de Laravel Mix",
        "tailwind.config.js": "Configuración de Tailwind", "postcss.config.js": "Configuración de PostCSS",
        "tsconfig.json": "Configuración de TypeScript", "next.config.js": "Configuración de Next.js",
        "manage.py": "Órdenes de Django", "angular.json": "Configuración de Angular",
        "preload.php": "Precarga de PHP (OPcache)", "phpunit.xml": "Configuración de las pruebas",
        "phpunit.xml.dist": "Configuración de las pruebas",
        "go.mod": "Módulo y dependencias de Go", "go.sum": "Versiones exactas de las dependencias de Go",
        "main.go": "Punto de entrada", "cargo.toml": "Paquete y dependencias de Rust",
        "cargo.lock": "Versiones exactas de las dependencias de Rust", "pom.xml": "Proyecto y dependencias de Maven",
        "build.gradle": "Proyecto y dependencias de Gradle", "build.gradle.kts": "Proyecto y dependencias de Gradle",
        "settings.gradle": "Módulos de Gradle", "gemfile": "Dependencias de Ruby", "gemfile.lock": "Versiones exactas de las gemas",
        "rakefile": "Tareas de Ruby", "pubspec.yaml": "Paquete y dependencias de Dart/Flutter",
        "requirements.txt": "Dependencias de Python", "pyproject.toml": "Proyecto y dependencias de Python",
        "pipfile": "Dependencias de Python (Pipenv)", "setup.py": "Instalación del paquete de Python",
        "program.cs": "Punto de entrada", "appsettings.json": "Configuración de la aplicación",
        "dockerfile": "Imagen de Docker", "docker-compose.yml": "Servicios de Docker",
        "docker-compose.yaml": "Servicios de Docker", "makefile": "Tareas (make)", "composer.lock": "Versiones exactas de PHP",
        "wp-config.php": "Configuración de WordPress", "functions.php": "Funciones del tema de WordPress",
        "index.php": "Punto de entrada", "app.py": "Punto de entrada", "main.py": "Punto de entrada",
        "server.js": "Punto de entrada", "index.js": "Punto de entrada", "app.js": "Punto de entrada",
    }
    HERRAMIENTAS_PROPIAS = {"generate_icon.py", "generate_readme.py", "generate_manual.py"}

    def arbol(self):
        lineas = []
        entradas = sorted((e for e in self.raiz.iterdir()
                           if not e.name.startswith(".") and e.name not in DIRS_IGNORADOS
                           and e.resolve() != _PROPIO and e.name != "README.md"
                           and e.name not in self.HERRAMIENTAS_PROPIAS),
                          key=lambda e: (e.is_file(), e.name.lower()))
        dirs = [e for e in entradas if e.is_dir()]
        # Primero los archivos que definen el proyecto (go.mod, pom.xml, Cargo.toml…), luego el código
        conocidos = [e for e in entradas if e.is_file() and e.name.lower() in self.ARCHIVOS_CONOCIDOS]
        codigo = [e for e in entradas if e.is_file() and e not in conocidos and e.suffix.lower() in
                  (".php", ".js", ".ts", ".py", ".html", ".json", ".cs", ".rb", ".go", ".java", ".kt", ".rs", ".dart")]
        archivos = (conocidos + codigo)[:8]
        todo = dirs + archivos
        for i, e in enumerate(todo):
            ultimo = i == len(todo) - 1
            rama = "└── " if ultimo else "├── "
            desc = self.DESCRIPCIONES.get(e.name.lower(), "")
            if e.is_dir() and e.name == "lib" and (self.raiz / "pubspec.yaml").is_file():
                desc = "Código de la aplicación (Dart)"
            if e.is_dir() and _es_de_terceros(self.raiz, e.name):
                desc = ("Núcleo de CodeIgniter (no se modifica)" if e.name == "system"
                        else "Librería de terceros")
            if e.is_file():
                desc = self.ARCHIVOS_CONOCIDOS.get(e.name.lower()) or _primera_frase_doc(_texto(e, 300000)) or desc
            lineas.append((rama + e.name + ("/" if e.is_dir() else ""), desc))
            if e.is_dir() and e.name.lower() in ("vistas", "views", "app", "src", "resources", "public", "lib", "cmd",
                                                 "internal", "pages", "wwwroot"):
                hijos = sorted((h for h in e.iterdir() if h.is_dir() and not h.name.startswith(".")), key=lambda h: h.name)[:7]
                for j, h in enumerate(hijos):
                    sub = ("    " if ultimo else "│   ") + ("└── " if j == len(hijos) - 1 else "├── ")
                    if _es_de_terceros(e, h.name):
                        dh = "Librería de terceros"
                    elif h.name.lower() in self.AMBIGUOS_DENTRO:
                        dh = ""
                    else:
                        dh = self.DESCRIPCIONES.get(h.name.lower(), "")
                    lineas.append((sub + h.name + "/", dh))
        ancho = max((len(a) for a, _d in lineas), default=0) + 3
        return "\n".join((a.ljust(ancho) + d).rstrip() for a, d in lineas)

    def recorrido(self):
        """Cadena de require/include desde el punto de entrada, con la primera frase de cada archivo."""
        entrada = next((self.raiz / f for f in ("index.php", "public/index.php") if (self.raiz / f).is_file()), None)
        if not entrada:
            return []
        pasos = []
        vistos = set()

        def seguir(f, prof):
            if f in vistos or prof > 2 or len(pasos) > 8:
                return
            vistos.add(f)
            t = _texto(f, 500000)
            pasos.append((prof, _rel(self.raiz, f), _primera_frase_doc(t)))
            for m in re.finditer(r"(?:require|include)(?:_once)?\s*\(?\s*__DIR__\s*\.\s*['\"]([^'\"]+)['\"]", t):
                destino = (f.parent / m.group(1).lstrip("/")).resolve()
                if destino.is_file() and self.raiz in destino.parents:
                    seguir(destino, prof + 1)

        seguir(entrada.resolve(), 0)
        return pasos if len(pasos) > 1 else []

    def endpoints(self):
        out = []
        for f in _archivos(self.raiz, (".php", ".js", ".ts", ".py", ".go", ".rs", ".java", ".kt", ".cs", ".rb"), 3000):
            rel = _rel(self.raiz, f)
            t = _texto(f, 500000)
            if f.suffix == ".go":
                for m in re.finditer(r"\.(GET|POST|PUT|PATCH|DELETE)\(\s*\"([^\"]+)\"", t):
                    out.append((m.group(1), m.group(2), rel))
                for m in re.finditer(r"HandleFunc\(\s*\"(?:(GET|POST|PUT|PATCH|DELETE)\s+)?([^\"]+)\"", t):
                    out.append((m.group(1) or "—", m.group(2), rel))
                continue
            if f.suffix == ".rs":
                for m in re.finditer(r"\.route\(\s*\"([^\"]+)\"\s*,\s*(get|post|put|patch|delete)", t):
                    out.append((m.group(2).upper(), m.group(1), rel))
                for m in re.finditer(r"#\[(get|post|put|patch|delete)\(\s*\"([^\"]+)\"", t):
                    out.append((m.group(1).upper(), m.group(2), rel))
                continue
            if f.suffix in (".java", ".kt"):
                for m in re.finditer(r"@(Get|Post|Put|Patch|Delete|Request)Mapping\(\s*(?:value\s*=\s*|path\s*=\s*)?"
                                     r"\{?\s*\"([^\"]*)\"", t):
                    if not re.search(r"@RequestMapping[^\n]*\n\s*(public\s+)?(class|interface)", t[m.start():m.start() + 200]):
                        out.append((m.group(1).upper() if m.group(1) != "Request" else "—", m.group(2) or "/", rel))
                continue
            if f.suffix == ".cs":
                for m in re.finditer(r"\.Map(Get|Post|Put|Patch|Delete)\(\s*\"([^\"]+)\"", t):
                    out.append((m.group(1).upper(), m.group(2), rel))
                for m in re.finditer(r"\[Http(Get|Post|Put|Patch|Delete)\(\s*\"([^\"]*)\"\s*\)\]", t):
                    out.append((m.group(1).upper(), m.group(2) or "/", rel))
                continue
            if f.suffix == ".rb":
                if rel.endswith("config/routes.rb"):
                    for m in re.finditer(r"(?m)^\s*(get|post|put|patch|delete)\s+['\"]([^'\"]+)", t):
                        out.append((m.group(1).upper(), m.group(2), rel))
                    for m in re.finditer(r"(?m)^\s*resources?\s+:(\w+)", t):
                        out.append(("REST", "/" + m.group(1), rel))
                continue
            if f.suffix == ".py":
                for m in re.finditer(r"@\w+\.(get|post|put|patch|delete)\(\s*[\"']([^\"']+)", t):
                    out.append((m.group(1).upper(), m.group(2), rel))
            if f.suffix == ".php":
                for m in re.finditer(r"Route::(get|post|put|patch|delete|any)\(\s*['\"]([^'\"]+)", t):
                    out.append((m.group(1).upper(), m.group(2), rel))
            elif f.suffix in (".js", ".ts"):
                for m in re.finditer(r"\b(?:app|router)\.(get|post|put|patch|delete)\(\s*['\"`]([^'\"`]+)", t):
                    out.append((m.group(1).upper(), m.group(2), rel))
            else:
                for m in re.finditer(r"@\w+\.route\(\s*['\"]([^'\"]+)['\"](?:[^)]*methods\s*=\s*\[([^\]]*)\])?", t):
                    metodos = re.findall(r"[A-Z]+", m.group(2) or "GET")
                    out.append(("/".join(metodos) or "GET", m.group(1), rel))
                for m in re.finditer(r"\bpath\(\s*['\"]([^'\"]*)['\"]", t):
                    if rel.endswith("urls.py"):
                        out.append(("—", "/" + m.group(1), rel))
            if len(out) >= 25:
                break
        if not out:
            for nombre in ("ajax", "api", "endpoints"):
                d = self.raiz / nombre
                if d.is_dir():
                    for f in sorted(d.glob("*.php")):
                        out.append(("POST/GET", _rel(self.raiz, f), _primera_frase_doc(_texto(f)) or ""))
        return out[:25]

    # ----------------------------------------------------------- seguridad
    def seguridad(self):
        """Afirmaciones comprobadas: [(texto, archivo)]."""
        out = []
        htaccess = set(_archivos(self.raiz, (".htaccess",), 500))
        htaccess |= {d / ".htaccess" for d in self.raiz.iterdir()
                     if d.is_dir() and not d.name.startswith(".") and (d / ".htaccess").is_file()}
        for ht in sorted(htaccess):
            t = _texto(ht)
            sin_files = re.sub(r"<FilesMatch.*?</FilesMatch>|<Files\b.*?</Files>", "", t, flags=re.S | re.I)
            carpeta = _rel(self.raiz, ht.parent)
            if re.search(r"Require\s+all\s+denied|Deny\s+from\s+all", sin_files, re.I) and carpeta != ".":
                out.append(("`%s/` no se sirve por web: su `.htaccess` deniega el acceso entero." % carpeta, _rel(self.raiz, ht)))
            for m in re.finditer(r"<FilesMatch\s+\"([^\"]+)\"\s*>(.*?)</FilesMatch>", t, re.S | re.I):
                if re.search(r"Require\s+all\s+denied|Deny\s+from\s+all", m.group(2), re.I):
                    out.append(("Se deniegan los archivos que coinciden con `%s`%s." % (
                        m.group(1), "" if carpeta == "." else " en `%s/`" % carpeta), _rel(self.raiz, ht)))
            if re.search(r"^\s*Options\s+-Indexes", t, re.M | re.I) and carpeta == ".":
                out.append(("Sin listado de carpetas (`Options -Indexes`).", _rel(self.raiz, ht)))
            if re.search(r"display_errors\s+off", t, re.I):
                out.append(("PHP no muestra los errores en la respuesta: van al registro (`display_errors off`).",
                            _rel(self.raiz, ht)))
        if self.gitignore_env():
            out.append(("El `.env`, con las credenciales, no se versiona.", ".gitignore"))
        php = self.archivos_php()
        for patron, texto in ((r"\bodbc_prepare\s*\(|->prepare\s*\(|\bmysqli_prepare\s*\(", "Consultas preparadas"),
                              (r"\bhtmlspecialchars\s*\(", "Salida HTML escapada con `htmlspecialchars`"),
                              (r"csrf_field\s*\(|@csrf\b|csrf_token\s*\(|csrf_hash\s*\(|name=[\"']_token[\"']|"
                               r"name=[\"']csrf[\w-]*[\"']", "Token CSRF en los formularios"), (r"\bpassword_hash\s*\(", "Contraseñas con `password_hash`"),
                              (r"session_regenerate_id\s*\(", "Regenera el id de sesión (`session_regenerate_id`)")):
            donde = [_rel(self.raiz, f) for f in php if re.search(patron, _texto(f, 800000), re.I)]
            if donde:
                extra = " y %d más" % (len(donde) - 2) if len(donde) > 2 else ""
                out.append(("%s: en %s%s." % (texto, ", ".join("`%s`" % d for d in donde[:2]), extra), donde[0]))
        return out

    # ------------------------------------------------------------- trampas
    def candidatas_trampa(self, maximo=10):
        """Comentarios largos del código que explican algo que se rompe. Se copian tal cual."""
        claves = re.compile(r"\b(rompe|romper|falla|fallar|trampa|ojo|cuidado|nunca|no es opcional|sin avisar|"
                            r"silencio|por eso|ni error|se pierde|error|peligro|no se ve|opaca|ojo:)\b", re.I)
        candidatas = []
        # La configuración de serie de los frameworks viene muy comentada, pero esos comentarios son
        # su documentación (config/ de Laravel, app/Config/ de CodeIgniter), no trampas del proyecto.
        de_serie = []
        if (self.raiz / "artisan").is_file():
            de_serie.append(self.raiz / "config")
        if (self.raiz / "system" / "CodeIgniter.php").is_file() or (self.raiz / "spark").is_file():
            de_serie.append(self.raiz / "app" / "Config")
        if (self.raiz / "symfony.lock").is_file():
            de_serie.append(self.raiz / "config")
        for f in _archivos(self.raiz, (".php", ".js", ".ts", ".py", ".css", ".htaccess", ".sql", ".rb", ".cs", ".java", ".go"), 2000):
            if any(d in f.parents for d in de_serie):
                continue
            lineas = _texto(f, 500000).splitlines()
            i = 0
            while i < len(lineas):
                s = lineas[i].strip()
                bloque, ini = [], i
                if s.startswith("/*"):
                    while i < len(lineas):
                        bloque.append(lineas[i])
                        if "*/" in lineas[i]:
                            break
                        i += 1
                    texto = [re.sub(r"^\s*(/\*\*?|\*/|\*)\s?", "", l).replace("*/", "").rstrip() for l in bloque]
                elif s.startswith(("//", "#")) and not s.startswith(("#!", "#include", "#region")):
                    pre = "//" if s.startswith("//") else "#"
                    while i < len(lineas) and lineas[i].strip().startswith(pre):
                        bloque.append(lineas[i])
                        i += 1
                    i -= 1
                    texto = [re.sub(r"^\s*(//|#)\s?", "", l).rstrip() for l in bloque]
                else:
                    i += 1
                    continue
                i += 1
                texto = [t for t in texto if not re.match(r"^[=\-_*#\s]+$", t)]
                while texto and not texto[0].strip():
                    texto.pop(0)
                while texto and not texto[-1].strip():
                    texto.pop()
                if len(texto) < 3 or any(t.strip().startswith("@") for t in texto[:1]):
                    continue
                # Los bloques «|----- Título -----|» son la documentación de serie de Laravel y
                # compañía (config/*.php): no son una trampa de ESTE proyecto.
                if any(re.match(r"^\s*\|\s*-{8,}", t) for t in texto):
                    continue
                # Código comentado (=>, ;, llaves…) no es una explicación
                codigo = sum(1 for t in texto if re.search(r"=>|;\s*$|^\s*[{}\])]|\$\w+\s*=|^\s*'[\w\\]+'\s*=>", t))
                if codigo * 3 >= len([t for t in texto if t.strip()]):
                    continue
                # Un comentario con @var, @param… documenta una API: no cuenta una trampa
                if any(re.match(r"^\s*@(var|param|return|property|see|package|deprecated|throws|method)\b", t)
                       for t in texto):
                    continue
                cuerpo = "\n".join(texto)
                puntos = len(claves.findall(cuerpo))
                if puntos == 0 or len(cuerpo) < 140:
                    continue
                candidatas.append((puntos * 10 + min(len(texto), 12), _rel(self.raiz, f), ini + 1, cuerpo))
        candidatas.sort(key=lambda c: -c[0])
        return [(r, l, c) for _p, r, l, c in candidatas[:maximo]]


# ===========================================================================
#  Imágenes: dimensiones y el banner
# ===========================================================================


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


def _dimensiones(ruta):
    datos = ruta.read_bytes()[:65536]
    if datos[:8] == b"\x89PNG\r\n\x1a\n":
        return struct.unpack(">II", datos[16:24])
    if datos[:2] == b"\xff\xd8":
        i = 2
        while i < len(datos) - 9:
            if datos[i] != 0xFF:
                i += 1
                continue
            marca = datos[i + 1]
            lon = struct.unpack(">H", datos[i + 2:i + 4])[0]
            if 0xC0 <= marca <= 0xCF and marca not in (0xC4, 0xC8, 0xCC):
                h, w = struct.unpack(">HH", datos[i + 5:i + 9])
                return w, h
            i += 2 + lon
    if ruta.suffix.lower() == ".svg":
        t = datos.decode("utf-8", "replace")
        m = re.search(r"viewBox\s*=\s*[\"']\s*[-\d.]+[\s,]+[-\d.]+[\s,]+([\d.]+)[\s,]+([\d.]+)", t)
        if m:
            return float(m.group(1)), float(m.group(2))
    return None


def _data_uri(ruta):
    tipo = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".svg": "image/svg+xml",
            ".gif": "image/gif", ".webp": "image/webp"}.get(ruta.suffix.lower())
    if not tipo:
        return None
    return "data:%s;base64,%s" % (tipo, base64.b64encode(ruta.read_bytes()).decode("ascii"))


# ===========================================================================
#  Plan, respaldo y deshacer (igual que generate_icon.py)
# ===========================================================================


def aplicar(raiz, escrituras):
    estado = raiz / CARPETA_ESTADO
    marca = time.strftime("%Y%m%d-%H%M%S")
    respaldo = estado / "respaldos" / marca
    man = {"version": VERSION, "fecha": marca, "creados": [], "modificados": [], "borrados": [], "carpetas": []}
    for ruta, datos in escrituras:
        rel = _rel(raiz, ruta)
        if datos is None:
            if ruta.exists():
                copia = respaldo / (rel + ".bak")
                copia.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(str(ruta), str(copia))
                ruta.unlink()
                man["borrados"].append({"ruta": rel, "respaldo": _rel(raiz, copia)})
            continue
        if ruta.exists():
            if ruta.read_bytes() == datos:
                continue
            copia = respaldo / (rel + ".bak")
            copia.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(str(ruta), str(copia))
            man["modificados"].append({"ruta": rel, "respaldo": _rel(raiz, copia), "sha256": _sha(datos)})
        else:
            faltan, d = [], ruta.parent
            while not d.exists():
                faltan.append(d)
                d = d.parent
            for d in reversed(faltan):
                d.mkdir()
                man["carpetas"].append(_rel(raiz, d))
            man["creados"].append({"ruta": rel, "sha256": _sha(datos)})
        tmp = ruta.with_name(ruta.name + ".generate_manual.tmp")
        tmp.write_bytes(datos)
        os.replace(str(tmp), str(ruta))
    estado.mkdir(exist_ok=True)
    (estado / ".gitignore").write_text("*\n", encoding="utf-8")
    (estado / ".htaccess").write_text(
        "<IfModule mod_authz_core.c>\n    Require all denied\n</IfModule>\n"
        "<IfModule !mod_authz_core.c>\n    Order allow,deny\n    Deny from all\n</IfModule>\n", encoding="utf-8")
    (estado / "ultimo.json").write_text(json.dumps(man, indent=2, ensure_ascii=False), encoding="utf-8")
    return man


def orden_deshacer(a):
    raiz = Path(a.proyecto).resolve() if a.proyecto else raiz_del_proyecto()
    ruta_man = raiz / CARPETA_ESTADO / "ultimo.json"
    if not ruta_man.is_file():
        raise ErrorManual("No hay nada que deshacer en %s." % raiz)
    man = json.loads(ruta_man.read_text(encoding="utf-8"))
    print("Deshaciendo lo escrito el %s" % man.get("fecha", "?"))
    saltados = 0
    for item in man.get("modificados", []):
        ruta, copia = raiz / item["ruta"], raiz / item["respaldo"]
        if ruta.exists() and _sha(ruta.read_bytes()) != item["sha256"] and not a.forzar:
            print("  ! %s se editó después (¿a mano?): no lo toco para no perder esos cambios. "
                  "Si quieres volver igualmente a la versión anterior: %s"
                  % (item["ruta"], _llamada("deshacer --forzar")))
            saltados += 1
            continue
        shutil.copy2(str(copia), str(ruta))
        print("  ↺ %s restaurado" % item["ruta"])
    for item in man.get("creados", []):
        ruta = raiz / item["ruta"]
        if not ruta.exists():
            continue
        if _sha(ruta.read_bytes()) != item["sha256"] and not a.forzar:
            print("  ! %s cambió después: no lo borro (usa --forzar)" % item["ruta"])
            saltados += 1
            continue
        ruta.unlink()
        print("  − %s borrado" % item["ruta"])
    for item in man.get("borrados", []):
        ruta = raiz / item["ruta"]
        if ruta.exists() and not a.forzar:
            print("  ! %s existe otra vez: no lo piso (usa --forzar)" % item["ruta"])
            saltados += 1
            continue
        ruta.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(str(raiz / item["respaldo"]), str(ruta))
        print("  ↺ %s recuperado" % item["ruta"])
    for d in reversed(man.get("carpetas", [])):
        try:
            (raiz / d).rmdir()
        except OSError:
            pass
    if saltados:
        print("\n%d archivo(s) no se tocaron." % saltados)
        return 1
    os.replace(str(ruta_man), str(ruta_man.with_name("deshecho-%s.json" % man.get("fecha", "x"))))
    print("\nListo: el proyecto está como antes.")
    return 0




# ===========================================================================
#  PDF en Python puro: Helvetica y Courier (las 14 fuentes de serie de PDF),
#  WinAnsiEncoding, imágenes PNG/JPG y enlaces. Sin pdfkit, sin Node.
# ===========================================================================

_ANCHO_HELV = [278, 278, 355, 556, 556, 889, 667, 191, 333, 333, 389, 584, 278, 333, 278, 278, 556, 556, 556, 556, 556, 556, 556, 556, 556, 556, 278, 278, 584, 584, 584, 556, 1015, 667, 667, 722, 722, 667, 611, 778, 722, 278, 500, 667, 556, 833, 722, 778, 667, 778, 722, 667, 611, 722, 667, 944, 667, 667, 611, 278, 278, 278, 469, 556, 333, 556, 556, 500, 556, 556, 278, 556, 556, 222, 222, 500, 222, 833, 556, 556, 556, 556, 333, 500, 278, 556, 500, 722, 500, 500, 500, 334, 260, 334, 584, 0, 556, 0, 222, 556, 333, 1000, 556, 556, 333, 1000, 667, 333, 1000, 0, 611, 0, 0, 222, 222, 333, 333, 350, 556, 1000, 333, 1000, 500, 333, 944, 0, 500, 667, 278, 333, 556, 556, 556, 556, 260, 556, 333, 737, 370, 556, 584, 333, 737, 333, 400, 584, 333, 333, 333, 556, 537, 278, 333, 333, 365, 556, 834, 834, 834, 611, 667, 667, 667, 667, 667, 667, 1000, 722, 667, 667, 667, 667, 278, 278, 278, 278, 722, 722, 778, 778, 778, 778, 778, 584, 778, 722, 722, 722, 722, 667, 667, 611, 556, 556, 556, 556, 556, 556, 889, 500, 556, 556, 556, 556, 278, 278, 278, 278, 556, 556, 556, 556, 556, 556, 556, 584, 611, 556, 556, 556, 556, 500, 556, 500]
_ANCHO_HELV_B = [278, 333, 474, 556, 556, 889, 722, 238, 333, 333, 389, 584, 278, 333, 278, 278, 556, 556, 556, 556, 556, 556, 556, 556, 556, 556, 333, 333, 584, 584, 584, 611, 975, 722, 722, 722, 722, 667, 611, 778, 722, 278, 556, 722, 611, 833, 722, 778, 667, 778, 722, 667, 611, 722, 667, 944, 667, 667, 611, 333, 278, 333, 584, 556, 333, 556, 611, 556, 611, 556, 333, 611, 611, 278, 278, 556, 278, 889, 611, 611, 611, 611, 389, 556, 333, 611, 556, 778, 556, 556, 500, 389, 280, 389, 584, 0, 556, 0, 278, 556, 500, 1000, 556, 556, 333, 1000, 667, 333, 1000, 0, 611, 0, 0, 278, 278, 500, 500, 350, 556, 1000, 333, 1000, 556, 333, 944, 0, 500, 667, 278, 333, 556, 556, 556, 556, 280, 556, 333, 737, 370, 556, 584, 333, 737, 333, 400, 584, 333, 333, 333, 611, 556, 278, 333, 333, 365, 556, 834, 834, 834, 611, 722, 722, 722, 722, 722, 722, 1000, 722, 667, 667, 667, 667, 278, 278, 278, 278, 722, 722, 778, 778, 778, 778, 778, 584, 778, 722, 722, 722, 722, 667, 667, 611, 556, 556, 556, 556, 556, 556, 889, 556, 556, 556, 556, 556, 278, 278, 278, 278, 611, 611, 611, 611, 611, 611, 611, 584, 611, 611, 611, 611, 611, 556, 611, 556]
# Nombre interno en el PDF, fuente de serie y tabla de anchos (Courier: todo 600)
_FUENTES = {"normal": ("F1", "Helvetica", _ANCHO_HELV), "negrita": ("F2", "Helvetica-Bold", _ANCHO_HELV_B),
            "cursiva": ("F3", "Helvetica-Oblique", _ANCHO_HELV), "negritaCursiva": ("F4", "Helvetica-BoldOblique", _ANCHO_HELV_B),
            "codigo": ("F5", "Courier", None)}

MM = 72 / 25.4
PAG_ANCHO, PAG_ALTO = 210 * MM, 297 * MM
MARGEN = {"izq": 18 * MM, "der": 18 * MM, "arriba": 24 * MM, "abajo": 20 * MM}
ANCHO_UTIL = PAG_ANCHO - MARGEN["izq"] - MARGEN["der"]
GRIS = {"texto": "#2b2b33", "titulo": "#333340", "portadaTitulo": "#282832", "suave": "#6e6e78",
        "cabecera": "#8c8c96", "generado": "#9696a0", "linea": "#dcdce4", "borde": "#d4d4dc",
        "cabeceraTabla": "#eef0fb", "fondoCodigo": "#f4f4f8", "codigo": "#1f2430", "codigoEnLinea": "#b1256b",
        "avisoFondo": "#fdf6e3", "avisoTexto": "#6b5514"}
TAM = {"h1": 17, "h2": 14, "h3": 12, "h4": 11, "p": 10, "tabla": 9, "codigo": 8.5, "aviso": 9.5}

# Helvetica sólo trae Windows-1252: lo demás se cambia aquí (en el .md se ven bien) o se avisa
SUSTITUCIONES = {"→": "->", "←": "<-", "⇒": "=>", "↔": "<->", "✓": "(sí)", "✔": "(sí)", "✗": "(no)", "✘": "(no)",
                 "≥": ">=", "≤": "<=", "≠": "!=", "≈": "~", "└": "`", "├": "|", "│": "|", "─": "-", " ": " "}


def _rgb(h):
    h = h.lstrip("#")
    return "%.3f %.3f %.3f" % tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))


def limpiar_caracteres(texto):
    for a, b in SUSTITUCIONES.items():
        texto = texto.replace(a, b)
    return re.sub(r" ?[\U0001F000-\U0001FAFF☀-➿️]+", "", texto)


def _pintable(c):
    try:
        c.encode("cp1252")
        return True
    except UnicodeEncodeError:
        return c in "\n\r"


def ancho_texto(texto, fuente, tam):
    tabla = _FUENTES[fuente][2]
    if tabla is None:
        return len(texto) * 600 * tam / 1000
    total = 0
    for b in texto.encode("cp1252", "replace"):
        total += tabla[b - 32] if 32 <= b <= 255 and tabla[b - 32] else 556
    return total * tam / 1000


def _cadena_pdf(texto):
    datos = texto.encode("cp1252", "replace")
    return "(" + datos.decode("latin-1").replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)") + ")"


def _leer_png(datos):
    """(ancho, alto, rgb, alfa | None) de un PNG de 8 bits sin entrelazar."""
    pos, ihdr, idat, paleta, trns = 8, None, bytearray(), b"", b""
    while pos < len(datos):
        n = struct.unpack(">I", datos[pos:pos + 4])[0]
        tipo, cuerpo = datos[pos + 4:pos + 8], datos[pos + 8:pos + 8 + n]
        pos += 12 + n
        if tipo == b"IHDR":
            ihdr = struct.unpack(">IIBBBBB", cuerpo)
        elif tipo == b"IDAT":
            idat += cuerpo
        elif tipo == b"PLTE":
            paleta = cuerpo
        elif tipo == b"tRNS":
            trns = cuerpo
    w, h, prof, ctipo, _c, _f, entre = ihdr
    canales = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}.get(ctipo)
    if prof != 8 or entre or canales is None:
        raise ErrorManual("El logotipo es un PNG que no sé leer (debe ser de 8 bits y sin entrelazar).")
    crudo, paso, p, prev = zlib.decompress(bytes(idat)), w * canales, 0, bytearray(w * canales)
    pix = bytearray()
    for _ in range(h):
        f, fila = crudo[p], bytearray(crudo[p + 1:p + 1 + paso])
        p += 1 + paso
        for i in range(paso):
            a = fila[i - canales] if i >= canales else 0
            b, c = prev[i], (prev[i - canales] if i >= canales else 0)
            if f == 1:
                fila[i] = (fila[i] + a) & 255
            elif f == 2:
                fila[i] = (fila[i] + b) & 255
            elif f == 3:
                fila[i] = (fila[i] + ((a + b) >> 1)) & 255
            elif f == 4:
                q = a + b - c
                pa, pb, pc = abs(q - a), abs(q - b), abs(q - c)
                fila[i] = (fila[i] + (a if pa <= pb and pa <= pc else b if pb <= pc else c)) & 255
        pix += fila
        prev = fila
    rgb, alfa = bytearray(), bytearray()
    for i in range(w * h):
        px = pix[i * canales:(i + 1) * canales]
        if ctipo == 6:
            rgb += px[:3]; alfa.append(px[3])
        elif ctipo == 2:
            rgb += px
        elif ctipo == 4:
            rgb += bytes([px[0]] * 3); alfa.append(px[1])
        elif ctipo == 0:
            rgb += bytes([px[0]] * 3)
        else:
            k = px[0]
            rgb += paleta[k * 3:k * 3 + 3] or b"\0\0\0"
            if trns:
                alfa.append(trns[k] if k < len(trns) else 255)
    return w, h, bytes(rgb), (bytes(alfa) if alfa else None)


class Logotipo:
    def __init__(self, ruta):
        datos = Path(ruta).read_bytes()
        self.jpeg = datos[:2] == b"\xff\xd8"
        if self.jpeg:
            dim = _dimensiones(Path(ruta))
            if not dim:
                raise ErrorManual("No pude leer las medidas del logotipo %s." % ruta)
            self.ancho, self.alto = dim
            self.datos, self.alfa = datos, None
        elif datos[:8] == b"\x89PNG\r\n\x1a\n":
            self.ancho, self.alto, self.datos, self.alfa = _leer_png(datos)
        else:
            raise ErrorManual("El logotipo tiene que ser PNG o JPG: %s" % ruta)

    def claro(self):
        """¿Es casi blanco? Un logotipo para pantalla oscura no se ve en papel."""
        if self.jpeg:
            return False
        luz, n = 0, 0
        for i in range(0, len(self.datos) // 3, max(1, len(self.datos) // 3 // 4000)):
            if self.alfa is not None and self.alfa[i] < 128:
                continue
            r, g, b = self.datos[i * 3:i * 3 + 3]
            luz += (r + g + b) / 765
            n += 1
        return n > 0 and luz / n > 0.85


class PDF:
    """Un documento de páginas A4. Coordenadas en puntos desde arriba a la izquierda."""

    def __init__(self, titulo, autor):
        self.paginas, self.enlaces, self.titulo, self.autor = [], [], titulo, autor
        self.logo = None

    def nueva_pagina(self):
        self.paginas.append([])
        self.enlaces.append([])

    def op(self, s, pagina=None):
        self.paginas[-1 if pagina is None else pagina].append(s)

    def rect(self, x, y, w, h, relleno=None, borde=None, pagina=None):
        partes = ["q"]
        if relleno:
            partes.append("%s rg" % _rgb(relleno))
        if borde:
            partes.append("0.5 w %s RG" % _rgb(borde))
        partes.append("%.2f %.2f %.2f %.2f re %s Q" % (x, PAG_ALTO - y - h, w, h,
                                                      "B" if relleno and borde else "f" if relleno else "S"))
        self.op(" ".join(partes), pagina)

    def linea(self, x1, y1, x2, y2, color, pagina=None):
        self.op("q 0.5 w %s RG %.2f %.2f m %.2f %.2f l S Q" % (_rgb(color), x1, PAG_ALTO - y1, x2, PAG_ALTO - y2), pagina)

    def texto(self, x, y, s, fuente, tam, color, pagina=None):
        """`y` es el borde de arriba de la línea, como en pdfkit."""
        base = PAG_ALTO - y - tam * 0.718
        self.op("BT /%s %.2f Tf %s rg %.2f %.2f Td %s Tj ET" % (_FUENTES[fuente][0], tam, _rgb(color), x, base,
                                                              _cadena_pdf(s)), pagina)

    def enlace(self, x, y, w, h, url, pagina=None):
        self.enlaces[-1 if pagina is None else pagina].append((x, PAG_ALTO - y - h, x + w, PAG_ALTO - y, url))

    def imagen(self, x, y, w, h, pagina=None):
        self.op("q %.2f 0 0 %.2f %.2f %.2f cm /Im1 Do Q" % (w, h, x, PAG_ALTO - y - h), pagina)

    def guardar(self, ruta):
        objs = []

        def nuevo(contenido):
            objs.append(contenido)
            return len(objs)

        fuentes = {}
        for clave, (nombre, base, _t) in _FUENTES.items():
            fuentes[nombre] = nuevo(b"<< /Type /Font /Subtype /Type1 /BaseFont /" + base.encode() +
                                    b" /Encoding /WinAnsiEncoding >>")
        recursos = b"/Font << " + b" ".join(b"/%s %d 0 R" % (k.encode(), v) for k, v in fuentes.items()) + b" >>"
        if self.logo is not None:
            lg = self.logo
            if lg.jpeg:
                im = nuevo(b"<< /Type /XObject /Subtype /Image /Width %d /Height %d /ColorSpace /DeviceRGB "
                           b"/BitsPerComponent 8 /Filter /DCTDecode /Length %d >>\nstream\n" % (lg.ancho, lg.alto, len(lg.datos))
                           + lg.datos + b"\nendstream")
            else:
                smask = b""
                if lg.alfa is not None:
                    a = zlib.compress(lg.alfa, 9)
                    sm = nuevo(b"<< /Type /XObject /Subtype /Image /Width %d /Height %d /ColorSpace /DeviceGray "
                               b"/BitsPerComponent 8 /Filter /FlateDecode /Length %d >>\nstream\n" % (lg.ancho, lg.alto, len(a))
                               + a + b"\nendstream")
                    smask = b" /SMask %d 0 R" % sm
                c = zlib.compress(lg.datos, 9)
                im = nuevo(b"<< /Type /XObject /Subtype /Image /Width %d /Height %d /ColorSpace /DeviceRGB "
                           b"/BitsPerComponent 8 /Filter /FlateDecode%s /Length %d >>\nstream\n" % (lg.ancho, lg.alto, smask, len(c))
                           + c + b"\nendstream")
            recursos += b" /XObject << /Im1 %d 0 R >>" % im
        id_paginas = nuevo(b"")   # se rellena al final
        kids = []
        for i, ops in enumerate(self.paginas):
            flujo = zlib.compress("\n".join(ops).encode("latin-1"), 9)
            cont = nuevo(b"<< /Length %d /Filter /FlateDecode >>\nstream\n" % len(flujo) + flujo + b"\nendstream")
            anots = []
            for (x1, y1, x2, y2, url) in self.enlaces[i]:
                anots.append(nuevo(b"<< /Type /Annot /Subtype /Link /Rect [%.2f %.2f %.2f %.2f] /Border [0 0 0] "
                                   b"/A << /S /URI /URI %s >> >>" % (x1, y1, x2, y2, _cadena_pdf(url).encode("latin-1"))))
            kids.append(nuevo(b"<< /Type /Page /Parent %d 0 R /MediaBox [0 0 %.2f %.2f] /Resources << %s >> "
                              b"/Contents %d 0 R%s >>" % (id_paginas, PAG_ANCHO, PAG_ALTO, recursos, cont,
                                                          (b" /Annots [" + b" ".join(b"%d 0 R" % a for a in anots) + b"]")
                                                          if anots else b"")))
        objs[id_paginas - 1] = b"<< /Type /Pages /Kids [" + b" ".join(b"%d 0 R" % k for k in kids) + \
            b"] /Count %d >>" % len(kids)
        catalogo = nuevo(b"<< /Type /Catalog /Pages %d 0 R >>" % id_paginas)
        info = nuevo(b"<< /Title %s /Author %s /Producer (generate_manual.py) >>" % (
            _cadena_pdf(self.titulo).encode("latin-1"), _cadena_pdf(self.autor).encode("latin-1")))
        salida, offsets = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n"), []
        for i, o in enumerate(objs, 1):
            offsets.append(len(salida))
            salida += b"%d 0 obj\n" % i + o + b"\nendobj\n"
        xref = len(salida)
        salida += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1)
        salida += b"".join(b"%010d 00000 n \n" % o for o in offsets)
        salida += b"trailer\n<< /Size %d /Root %d 0 R /Info %d 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (
            len(objs) + 1, catalogo, info, xref)
        return bytes(salida)


# ===========================================================================
#  Markdown: lo justo para los manuales (apartado 6 del agente)
# ===========================================================================

def en_linea(texto, base=None):
    base = base or {}
    trozos, desde = [], 0
    patron = re.compile(r"`([^`]+)`|\*\*(.+?)\*\*|(?<![\w*])\*([^*\n]+)\*(?![\w*])|\[([^\]]+)\]\(([^)]+)\)", re.S)
    for m in patron.finditer(texto):
        if m.start() > desde:
            trozos.append(dict(base, texto=texto[desde:m.start()]))
        if m.group(1) is not None:
            trozos.append(dict(base, texto=m.group(1), codigo=True))
        elif m.group(2) is not None:
            trozos += en_linea(m.group(2), dict(base, negrita=True))
        elif m.group(3) is not None:
            trozos += en_linea(m.group(3), dict(base, cursiva=True))
        else:
            # Un enlace a una web se conserva; uno a un archivo, en negrita: en papel no lleva a ningún sitio
            trozos += en_linea(m.group(4), dict(base, enlace=m.group(5)) if m.group(5).startswith("http")
                               else dict(base, negrita=True))
        desde = m.end()
    if desde < len(texto):
        trozos.append(dict(base, texto=texto[desde:]))
    return [t for t in trozos if t["texto"]]


def _celdas(linea):
    s = re.sub(r"^\||\|$", "", linea.strip())
    return [c.replace("\\|", "|").strip() for c in re.split(r"(?<!\\)\|", s)]


def bloques_md(texto):
    salida, parrafo, lista, item, tabla, aviso, codigo = [], [], None, None, None, None, None

    def cerrar_item():
        nonlocal item
        if item:
            lista["items"].append({"nivel": item["nivel"], "ordenada": item["ordenada"],
                                   "trozos": en_linea(" ".join(item["lineas"]))})
            item = None

    def volcar_aviso():
        if aviso and aviso["lineas"]:
            aviso["parrafos"].append(en_linea(" ".join(aviso["lineas"])))
            aviso["lineas"] = []

    def cerrar():
        nonlocal parrafo, lista, tabla, aviso
        if parrafo:
            salida.append({"tipo": "p", "trozos": en_linea(" ".join(parrafo))})
            parrafo = []
        if lista:
            cerrar_item()
            salida.append(lista)
            lista = None
        if tabla:
            salida.append(tabla)
            tabla = None
        if aviso:
            volcar_aviso()
            salida.append({"tipo": "aviso", "parrafos": aviso["parrafos"]})
            aviso = None

    for original in texto.splitlines():
        linea = original.rstrip()
        if linea.lstrip().startswith("```"):
            if codigo:
                salida.append(codigo)
                codigo = None
            else:
                cerrar()
                codigo = {"tipo": "codigo", "lineas": []}
            continue
        if codigo:
            codigo["lineas"].append(linea)
            continue
        if not linea.strip():
            cerrar()
            continue
        if re.match(r"^\s*(-{3,}|\*{3,}|_{3,})\s*$", linea):
            cerrar()
            salida.append({"tipo": "hr"})
            continue
        m = re.match(r"^(#{1,6})\s+(.*)$", linea)
        if m:
            cerrar()
            salida.append({"tipo": "h", "nivel": len(m.group(1)), "trozos": en_linea(m.group(2).strip())})
            continue
        if linea.lstrip().startswith("|"):
            fila = _celdas(linea)
            if fila and all(re.match(r"^:?-{2,}:?$", c) for c in fila):
                continue
            if not tabla:
                cerrar()
                tabla = {"tipo": "tabla", "filas": []}
            tabla["filas"].append([en_linea(c) for c in fila])
            continue
        if tabla:
            cerrar()
        m = re.match(r"^\s*>\s?(.*)$", linea)
        if m:
            if not aviso:
                cerrar()
                aviso = {"parrafos": [], "lineas": []}
            if m.group(1).strip():
                aviso["lineas"].append(m.group(1).strip())
            else:
                volcar_aviso()
            continue
        if aviso:
            cerrar()
        m = re.match(r"^(\s*)([-*+]|\d+\.)\s+(.*)$", linea)
        if m:
            ordenada, nivel = bool(re.match(r"^\d+\.$", m.group(2))), len(m.group(1)) // 2
            if not lista or (nivel == 0 and lista["ordenada"] != ordenada):
                cerrar()
                lista = {"tipo": "lista", "ordenada": ordenada, "items": []}
            else:
                cerrar_item()
            item = {"nivel": nivel, "ordenada": ordenada, "lineas": [m.group(3).strip()]}
            continue
        if lista and item:
            item["lineas"].append(linea.strip())
            continue
        if lista:
            cerrar()
        parrafo.append(linea.strip())
    cerrar()
    if codigo:
        salida.append(codigo)
    return salida


# ===========================================================================
#  El manual: el diseño de roriApp, con sus medidas (apartado 5 del agente)
# ===========================================================================

def _fuente_de(t):
    if t.get("codigo"):
        return "codigo"
    if t.get("negrita") and t.get("cursiva"):
        return "negritaCursiva"
    return "negrita" if t.get("negrita") else "cursiva" if t.get("cursiva") else "normal"


class Manual:
    def __init__(self, conf, defi, logo):
        self.conf, self.defi, self.logo = conf, defi, logo
        self.marca = conf.get("colores", {}).get("marca") or "#6366f1"
        self.oscuro = conf.get("colores", {}).get("marcaOscuro") or "#4338ca"
        idn = conf["identidad"]
        self.pdf = PDF("%s · %s" % (defi["titulo"], idn.get("nombre", "")), idn.get("empresa", ""))
        self.pdf.logo = logo
        self.y = MARGEN["arriba"]

    @property
    def fondo(self):
        return PAG_ALTO - MARGEN["abajo"]

    def asegurar(self, alto):
        if self.y + alto > self.fondo:
            self.pdf.nueva_pagina()
            self.y = MARGEN["arriba"]

    # ---- texto con formato, partido en líneas
    def _lineas(self, trozos, ancho, tam):
        palabras = []   # (texto, estilo) con los espacios pegados al final
        for t in trozos or [{"texto": " "}]:
            for pal in re.findall(r"\S+\s*|\s+", t["texto"]):
                palabras.append((pal, t))
        lineas, actual, w = [], [], 0.0
        for pal, t in palabras:
            tam_t = max(tam - 1, 7.5) if t.get("codigo") else tam
            ancho_pal = ancho_texto(pal.rstrip(), _fuente_de(t), tam_t)
            ancho_esp = ancho_texto(pal[len(pal.rstrip()):], _fuente_de(t), tam_t)
            if actual and w + ancho_pal > ancho:
                lineas.append(actual)
                actual, w = [], 0.0
                if not pal.strip():
                    continue
            actual.append((pal, t, tam_t))
            w += ancho_pal + ancho_esp
        if actual:
            lineas.append(actual)
        return lineas

    def alto_de(self, trozos, ancho, tam, gap):
        return len(self._lineas(trozos, ancho, tam)) * (tam * 0.925 + gap)

    def trozos(self, trozos, x, y, ancho, tam, color, gap=0.0, centrar=False):
        alto_linea = tam * 0.925 + gap
        for i, linea in enumerate(self._lineas(trozos, ancho, tam)):
            if linea and not linea[-1][0].strip() == linea[-1][0]:
                linea[-1] = (linea[-1][0].rstrip(), linea[-1][1], linea[-1][2])
            total = sum(ancho_texto(p, _fuente_de(t), tt) for p, t, tt in linea)
            cx = x + ((ancho - total) / 2 if centrar else 0)
            for pal, t, tt in linea:
                col = GRIS["codigoEnLinea"] if t.get("codigo") else self.oscuro if t.get("enlace") else color
                w = ancho_texto(pal, _fuente_de(t), tt)
                self.pdf.texto(cx, y + i * alto_linea, pal, _fuente_de(t), tt, col)
                if t.get("enlace"):
                    self.pdf.enlace(cx, y + i * alto_linea, w, tt, t["enlace"])
                cx += w
        return y + len(self._lineas(trozos, ancho, tam)) * alto_linea

    # ---- portada
    def portada(self):
        idn = self.conf["identidad"]
        self.pdf.nueva_pagina()
        y = MARGEN["arriba"]

        def celda(texto, alto, fuente, tam, color):
            nonlocal y
            if texto:
                self.trozos([{"texto": texto, "negrita": fuente == "negrita", "cursiva": fuente == "cursiva"}],
                            MARGEN["izq"], y + (alto * MM - tam * 0.925) / 2, ANCHO_UTIL, tam, color, centrar=True)
            y += alto * MM

        if self.logo:
            y += 32 * MM
            # Cabe en un cuadro de 46 mm: un logotipo ancho ocupa el ancho; uno cuadrado o alto, el alto
            esc = 46 * MM / max(self.logo.ancho, self.logo.alto * 46 / 34)
            w, h = self.logo.ancho * esc, self.logo.alto * esc
            self.pdf.imagen((PAG_ANCHO - w) / 2, y, w, h)
            y += h + 8 * MM
        else:
            y += 55 * MM
        celda(idn.get("nombre", ""), 14, "negrita", 30, self.marca)
        celda(idn.get("lema", ""), 8, "normal", 12, GRIS["suave"])
        y += 18 * MM
        celda(self.defi["titulo"], 12, "negrita", 20, GRIS["portadaTitulo"])
        y += 8 * MM
        y += 22 * MM
        celda("Versión %s%s" % (idn.get("version", ""), (" · " + idn["build"]) if idn.get("build") else ""), 6,
              "normal", 10, GRIS["suave"])
        celda(idn.get("empresa", ""), 6, "normal", 10, GRIS["suave"])
        y += 10 * MM
        celda("Generado el %s desde %s/%s.md" % (time.strftime("%d/%m/%Y"), self.conf.get("_carpeta", "docs"),
                                                 self.defi["archivo"]), 5, "cursiva", 8, GRIS["generado"])

    # ---- el cuerpo
    def cuerpo(self, lista):
        self.pdf.nueva_pagina()
        self.y = MARGEN["arriba"]
        anterior = None
        for b in lista:
            self.bloque(b, anterior)
            anterior = b["tipo"]

    def bloque(self, b, anterior):
        x = MARGEN["izq"]
        t = b["tipo"]
        if t == "h":
            tam = TAM["h%d" % min(b["nivel"], 4)]
            color = self.oscuro if b["nivel"] <= 2 else GRIS["titulo"]
            antes = 0 if anterior is None else (6 * MM if b["nivel"] <= 2 else 4.5 * MM)
            trozos = [dict(z, negrita=True) for z in b["trozos"]]
            # Un título nunca se queda solo al pie de una página
            self.asegurar(antes + self.alto_de(trozos, ANCHO_UTIL, tam, 0) + 12 * MM)
            self.y += 0 if self.y == MARGEN["arriba"] else antes
            self.y = self.trozos(trozos, x, self.y, ANCHO_UTIL, tam, color) + 2.8 * MM
        elif t == "p":
            gap = TAM["p"] * 0.42
            self.asegurar(min(self.alto_de(b["trozos"], ANCHO_UTIL, TAM["p"], gap), 15 * MM))
            self._texto_largo(b["trozos"], x, ANCHO_UTIL, TAM["p"], GRIS["texto"], gap)
            self.y += 3.4 * MM
        elif t == "lista":
            gap, cuenta = TAM["p"] * 0.3, []
            for it in b["items"]:
                del cuenta[it["nivel"] + 1:]
                while len(cuenta) <= it["nivel"]:
                    cuenta.append(0)
                cuenta[it["nivel"]] += 1
                sangria = 5 * MM + it["nivel"] * 6 * MM
                marcador = "%d." % cuenta[it["nivel"]] if it["ordenada"] else "•"
                ancho = ANCHO_UTIL - sangria - 4 * MM
                self.asegurar(min(self.alto_de(it["trozos"], ancho, TAM["p"], gap), 12 * MM))
                self.pdf.texto(x + sangria - 4 * MM, self.y, marcador, "normal", TAM["p"], GRIS["texto"])
                self._texto_largo(it["trozos"], x + sangria, ancho, TAM["p"], GRIS["texto"], gap)
                self.y += 0.4 * MM
            self.y += 3 * MM
        elif t == "tabla":
            self.tabla(b["filas"])
        elif t == "aviso":
            pad, ancho, gap = 2.5 * MM, ANCHO_UTIL - 5 * MM, TAM["aviso"] * 0.35
            altos = [self.alto_de(p, ancho, TAM["aviso"], gap) for p in b["parrafos"]]
            total = sum(altos) + (len(altos) - 1) * 1.5 * MM + 2 * pad
            self.asegurar(min(total, self.fondo - MARGEN["arriba"]))
            y0 = self.y
            self.pdf.rect(x, y0, ANCHO_UTIL, total, relleno=GRIS["avisoFondo"])
            y = y0 + pad
            for p, h in zip(b["parrafos"], altos):
                self.trozos(p, x + pad, y, ancho, TAM["aviso"], GRIS["avisoTexto"], gap)
                y += h + 1.5 * MM
            self.y = y0 + total + 4 * MM
        elif t == "codigo":
            self.codigo(b["lineas"])
        elif t == "hr":
            self.asegurar(6 * MM)
            self.y += 2 * MM
            self.pdf.linea(x, self.y, x + ANCHO_UTIL, self.y, GRIS["borde"])
            self.y += 4 * MM

    def _texto_largo(self, trozos, x, ancho, tam, color, gap):
        """Un párrafo que puede seguir en la página siguiente, línea a línea."""
        alto_linea = tam * 0.925 + gap
        for linea in self._lineas(trozos, ancho, tam):
            self.asegurar(alto_linea)
            cx = x
            for pal, t, tt in linea:
                col = GRIS["codigoEnLinea"] if t.get("codigo") else self.oscuro if t.get("enlace") else color
                self.pdf.texto(cx, self.y, pal, _fuente_de(t), tt, col)
                w = ancho_texto(pal, _fuente_de(t), tt)
                if t.get("enlace"):
                    self.pdf.enlace(cx, self.y, w, tt, t["enlace"])
                cx += w
            self.y += alto_linea

    def codigo(self, lineas):
        x, alto, pad = MARGEN["izq"], TAM["codigo"] * 1.35, 2 * MM
        caben = int((ANCHO_UTIL - 2 * pad) / (TAM["codigo"] * 0.6))
        partidas = []
        for l in lineas:
            resto = l
            while len(resto) > caben:
                esp = resto.rfind(" ", 0, caben)
                corte = esp if esp > caben / 2 else caben
                partidas.append(resto[:corte])
                resto = "    " + resto[corte:].lstrip(" ")
            partidas.append(resto)
        self.asegurar(alto * min(len(partidas), 3) + 2 * pad)
        primera = True
        for linea in partidas:
            if self.y + alto + pad > self.fondo:
                self.pdf.rect(x, self.y, ANCHO_UTIL, pad, relleno=GRIS["fondoCodigo"])
                self.pdf.nueva_pagina()
                self.y, primera = MARGEN["arriba"], True
            if primera:
                self.pdf.rect(x, self.y, ANCHO_UTIL, pad, relleno=GRIS["fondoCodigo"])
                self.y += pad
                primera = False
            self.pdf.rect(x, self.y, ANCHO_UTIL, alto, relleno=GRIS["fondoCodigo"])
            self.pdf.texto(x + pad, self.y + 1, linea or " ", "codigo", TAM["codigo"], GRIS["codigo"])
            self.y += alto
        self.pdf.rect(x, self.y, ANCHO_UTIL, pad, relleno=GRIS["fondoCodigo"])
        self.y += pad + 4 * MM

    def tabla(self, filas):
        x, pad = MARGEN["izq"], 1.6 * MM
        columnas = max(len(f) for f in filas)
        plano = lambda c: "".join(t["texto"] for t in (c or []))   # noqa: E731
        natural, minimo = [], []
        for c in range(columnas):
            n = w = 0
            for i, f in enumerate(filas):
                fuente = "negrita" if i == 0 else "normal"
                texto = plano(f[c] if c < len(f) else [])
                n = max(n, ancho_texto(texto, fuente, TAM["tabla"]) + 2 * pad)
                for pal in texto.split():
                    w = max(w, ancho_texto(pal, fuente, TAM["tabla"]) + 2 * pad)
            natural.append(n)
            minimo.append(min(w, ANCHO_UTIL / columnas * 1.6))
        if sum(natural) <= ANCHO_UTIL:
            anchos = [n * ANCHO_UTIL / sum(natural) for n in natural]
        else:
            resto = max(ANCHO_UTIL - sum(minimo), 0)
            extra = [max(n - m, 0) for n, m in zip(natural, minimo)]
            anchos = [m + resto * e / (sum(extra) or 1) for m, e in zip(minimo, extra)]
            anchos = [a * ANCHO_UTIL / sum(anchos) for a in anchos]
        for i, f in enumerate(filas):
            celdas = [[dict(t, negrita=True) if i == 0 else t for t in (f[c] if c < len(f) else [])]
                      for c in range(columnas)]
            alto = max(self.alto_de(c, anchos[k] - 2 * pad, TAM["tabla"], 1.5) for k, c in enumerate(celdas)) + 2 * pad
            self.asegurar(alto)
            cx = x
            for k, c in enumerate(celdas):
                self.pdf.rect(cx, self.y, anchos[k], alto, relleno=GRIS["cabeceraTabla"] if i == 0 else None,
                              borde=GRIS["borde"])
                self.trozos(c, cx + pad, self.y + pad, anchos[k] - 2 * pad, TAM["tabla"], GRIS["texto"], 1.5)
                cx += anchos[k]
            self.y += alto
        self.y += 4 * MM

    def cabeceras_y_pies(self):
        idn = self.conf["identidad"]
        total = len(self.pdf.paginas)
        for i in range(1, total):
            if self.logo:
                w, h = 14 * MM, 8 * MM
                esc = min(w / self.logo.ancho, h / self.logo.alto)
                self.pdf.imagen(MARGEN["izq"], 9 * MM, self.logo.ancho * esc, self.logo.alto * esc, pagina=i)
            xt = 35 * MM if self.logo else MARGEN["izq"]
            self.pdf.texto(xt, 10.6 * MM, "%s · %s" % (idn.get("nombre", ""), self.defi["titulo"]), "normal", 8,
                           GRIS["cabecera"], pagina=i)
            v = "v%s" % idn.get("version", "")
            self.pdf.texto(PAG_ANCHO - MARGEN["der"] - ancho_texto(v, "normal", 8), 10.6 * MM, v, "normal", 8,
                           GRIS["cabecera"], pagina=i)
            self.pdf.linea(MARGEN["izq"], 18 * MM, PAG_ANCHO - MARGEN["der"], 18 * MM, GRIS["linea"], pagina=i)
            y_pie = PAG_ALTO - 14 * MM + 0.6 * MM
            self.pdf.texto(MARGEN["izq"], y_pie, idn.get("empresa", ""), "normal", 8, GRIS["cabecera"], pagina=i)
            pg = "Página %d de %d" % (i + 1, total)
            self.pdf.texto(PAG_ANCHO - MARGEN["der"] - ancho_texto(pg, "normal", 8), y_pie, pg, "normal", 8,
                           GRIS["cabecera"], pagina=i)

    def generar(self, markdown):
        """Devuelve (bytes del PDF, avisos)."""
        avisos = []
        texto = re.sub(r"^\s*<p align=\"center\">[\s\S]*?</p>\s*", "", markdown)
        texto = re.sub(r"<!--[\s\S]*?-->", "", texto).lstrip()
        texto = re.sub(r"^#\s+.*(\r?\n)+", "", texto)
        texto = limpiar_caracteres(texto)
        faltan = sorted({c for c in texto if not _pintable(c)})
        if faltan:
            avisos.append("caracteres que la fuente no tiene: %s — salen como «?»; cámbialos en el .md o añádelos "
                          "a SUSTITUCIONES" % " ".join(faltan))
        huecos = len(re.findall(r"POR ESCRIBIR", re.sub(r"`[^`\n]*`", "", texto)))
        if huecos:
            avisos.append("quedan %d hueco%s «POR ESCRIBIR» sin rellenar" % (huecos, "" if huecos == 1 else "s"))
        self.portada()
        self.cuerpo(bloques_md(texto))
        self.cabeceras_y_pies()
        return self.pdf.guardar(None), avisos


# ===========================================================================
#  Los manuales del proyecto: manuales.json, plantillas y versión
# ===========================================================================

MANUALES_DE_LA_CASA = [
    ("MANUAL-USUARIO", "Manual de usuario", "Para quien usa la aplicación",
     "«Para quien trabaja en la tienda», «Para el personal de la clínica»"),
    ("MANUAL-TECNICO", "Manual técnico", "Para quien mantiene el sistema",
     "«Para quien mantiene el sistema»"),
    ("INSTALACION", "Guía de instalación", "Para quien instala la aplicación",
     "«Para quien monta una caja», «Para quien prepara el servidor»"),
]

def version_del_proyecto(raiz):
    """Apartado 7 del agente: la versión sale del manifiesto del proyecto, no de manuales.json."""
    for f in ("package.json", "composer.json"):
        v = _json(raiz / f).get("version")
        if v:
            return v, f
    for f, patron in (("pyproject.toml", r"(?m)^\s*version\s*=\s*[\"']([^\"']+)"), ("setup.cfg", r"(?m)^\s*version\s*=\s*(\S+)"),
                      ("build.gradle", r"(?m)^\s*version\s*=?\s*[\"']([^\"']+)"), ("Cargo.toml", r"(?m)^\s*version\s*=\s*\"([^\"]+)\""),
                      ("pubspec.yaml", r"(?m)^version:\s*([^\s+]+)")):
        m = re.search(patron, _texto(raiz / f))
        if m:
            return m.group(1), f
    m = re.search(r"<version>([^<]+)</version>", re.sub(r"<parent>.*?</parent>", "", _texto(raiz / "pom.xml"), flags=re.S))
    if m:
        return m.group(1), "pom.xml"
    if (raiz / "VERSION").is_file():
        return _texto(raiz / "VERSION").strip(), "VERSION"
    for cs in sorted(raiz.glob("*.csproj")):
        m = re.search(r"<Version>([^<]+)</Version>", _texto(cs))
        if m:
            return m.group(1), cs.name
    v = Proyecto(raiz).version()
    return (v.valor, v.fuente) if v.valor else ("", "")


def carpeta_docs(raiz, indicada=None):
    if indicada:
        return (raiz / indicada).resolve()
    for d in ("docs", "doc", "documentation", "documentacion"):
        if (raiz / d).is_dir():
            return raiz / d
    return raiz / "docs"


def _mes_actual():
    meses = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre",
             "Octubre", "Noviembre", "Diciembre"]
    return "%s %s" % (meses[time.localtime().tm_mon - 1], time.localtime().tm_year)


def _candidatos_logo(p):
    out = []
    for f in _archivos(p.raiz, (".png", ".jpg", ".jpeg"), 4000):
        n = _sin_tildes(f.stem)
        if "logo" in n or "empresa" in n or "marca" in n:
            out.append(f)
    nuevos, antiguos = [], []
    for f in _archivos(p.raiz, (".png",), 4000):
        m = re.fullmatch(r"icono-(512|192)-([a-z0-9][a-z0-9-]*)", f.stem)
        if m and "generate_icon" in _texto(f.parent / ("icono-%s.svg" % m.group(2)), 200000)[:1500]:
            nuevos.append(f)     # el de generate_icon con palabra: icono-512-inventario.png
        elif f.stem in ("icono-512", "icon-512", "icono-192"):
            antiguos.append(f)
    iconos = sorted(nuevos, key=lambda f: "-192-" in f.name) + antiguos
    return (out + iconos[:1])[:8]


def pedir_soporte():
    explicar("Soporte técnico", "A quién llama el usuario si algo falla. Va al final del manual de usuario. "
             "Enter vacío en lo que no quieras poner.", "«soporte@empresa.com», «0212-555-1234», «Lunes a viernes, 8 a 5»")
    return {"correo": _preguntar("   Correo", "") or "", "telefono": _preguntar("   Teléfono", "") or "",
            "horario": _preguntar("   Horario", "") or ""}


def pedir_version():
    explicar("Versión", "No encontré el número de versión en el proyecto (ni en su manifiesto ni en un archivo "
             "VERSION). Va en la portada y en la cabecera de cada página.", "«1.0.0»")
    return _preguntar_obligatorio("   Versión")


def configurar(p, docs, a, interactivo):
    """Crea manuales.json preguntando lo que no esté en el proyecto. Devuelve el diccionario."""
    if not interactivo:
        raise ErrorManual("No existe %s. Ejecuta la herramienta sin --si la primera vez para crearlo."
                          % _rel(p.raiz, docs / "manuales.json"))
    print("\nNo hay %s: lo preparo contigo. Se pregunta una sola vez; luego queda guardado." % _rel(p.raiz, docs / "manuales.json"))
    nombre = p.nombre()
    explicar("Nombre del sistema", "Sale grande en la portada y en la cabecera de cada página.",
             "«roriApp», «Control de Inventario»")
    if nombre.valor:
        print("   En %s aparece «%s». Enter para usarlo o escribe otro." % (nombre.fuente, nombre.valor))
    nom = _preguntar_obligatorio("   Nombre", nombre.valor or None)
    frase = p.frase()
    explicar("Lema", "Una línea, debajo del nombre en la portada, que diga qué hace el sistema.",
             "«Punto de venta y gestión para las tiendas Rori»")
    if frase.valor:
        print("   En %s pone «%s». Enter para usarla." % (frase.fuente, frase.valor))
    lema = _preguntar("   Lema (Enter vacío = sin lema)", frase.valor or None) or ""
    explicar("Empresa", "De quién es el sistema. Va en la portada y en el pie de cada página.",
             "«Industrias RRC, C.A.», «Universidad Monteávila»")
    det = p.empresa().valor.get("nombre", "")
    if det:
        print("   En %s aparece «%s». Enter para usarla." % (p.empresa().fuente, det))
    empresa = _preguntar_obligatorio("   Empresa", det or None)
    explicar("Fecha de esta versión (build)", "Cuándo salió la versión que documentan los manuales. Va en la portada.",
             "«%s»" % _mes_actual())
    build = _preguntar("   Build", _mes_actual()) or ""

    # Colores: los del proyecto, confirmados o elegidos en la ventana
    det_col = paleta_del_proyecto(p.raiz)
    vista = ('<div style="background:#fff;border-radius:12px;padding:28px 20px;text-align:center;font-family:Helvetica,'
             'Arial,sans-serif;min-width:320px"><div style="font:bold 30px Helvetica,Arial;color:__P__">%s</div>'
             '<div style="color:#6e6e78;margin:6px 0 22px">%s</div><div style="font:bold 20px Helvetica,Arial;'
             'color:#282832">Manual de usuario</div><div style="margin-top:22px;font:bold 15px Helvetica,Arial;'
             'color:__O__">1. Un título de sección</div></div>' % (_escapar_html(nom), _escapar_html(lema)))
    if a.marca and a.marca_oscuro:
        marca, oscuro = _a_hex(a.marca), _a_hex(a.marca_oscuro)
    elif det_col["supuesto"]:
        print("\nColores de la marca\n   El proyecto no tiene colores propios: se usan los de la casa (#6366f1 y #4338ca),")
        print("   como dice el agente. Si quieres otros, contesta que no.")
        det_col = dict(det_col, primario=("#6366f1", "", "los de la casa"), oscuro=("#4338ca", "", "los de la casa"),
                       supuesto=False)
        marca, oscuro, _m = confirmar_colores(det_col, "Colores de los manuales · %s" % nom, vista,
                                              "El del nombre en la portada.", "El de los títulos y los enlaces.",
                                              sin_ventana=a.sin_ventana)
    else:
        marca, oscuro, _m = confirmar_colores(det_col, "Colores de los manuales · %s" % nom, vista,
                                              "El del nombre en la portada.", "El de los títulos y los enlaces.",
                                              sin_ventana=a.sin_ventana)

    # Logotipo para papel
    explicar("Logotipo para papel",
             "Un PNG o JPG OSCURO (para papel blanco) y más ancho que alto. Los logotipos de pantalla suelen ser "
             "blancos: en papel no se ven. Escribe su ruta, o Enter vacío para no poner ninguno.",
             "«public/img/logo-oscuro.png»")
    candidatos = _candidatos_logo(p)
    for i, f in enumerate(candidatos, 1):
        print("   %d. %s" % (i, _rel(p.raiz, f)))
    logo = ""
    if candidatos:
        print("   0. Ninguno")
    while True:
        r = (_preguntar("   Logotipo (número o ruta)", "1" if candidatos else "") or "").strip().strip("\"'")
        if not r or r == "0":
            break
        ruta = candidatos[int(r) - 1] if r.isdigit() and 1 <= int(r) <= len(candidatos) else (p.raiz / r)
        try:
            lg = Logotipo(ruta)
        except (OSError, ErrorManual) as e:
            print("   No sirve: %s" % e)
            continue
        if lg.claro() and not _si_no("   Ese logotipo es casi blanco: en papel no se verá. ¿Usarlo igualmente?", False):
            continue
        logo = Path(os.path.relpath(str(Path(ruta).resolve()), str(docs.resolve()))).as_posix()
        break

    explicar("Qué manuales", "Los de la casa son tres. Escribe los números de los que quieras, separados por comas.",
             "«1,3» = manual de usuario y guía de instalación")
    for i, (_a, t, _s, _e) in enumerate(MANUALES_DE_LA_CASA, 1):
        print("   %d. %s" % (i, t))
    while True:
        r = _preguntar("   Manuales", "1,2,3")
        elegidos = [int(x) for x in re.findall(r"\d+", r or "") if 1 <= int(x) <= 3]
        if elegidos:
            break
        print("   Elige al menos uno (1, 2 o 3).")
    manuales = []
    for k in dict.fromkeys(elegidos):
        archivo, titulo, _sub, _ejemplo = MANUALES_DE_LA_CASA[k - 1]
        manuales.append({"archivo": archivo, "titulo": titulo})
    soporte = pedir_soporte()
    return {"identidad": {"nombre": nom, "lema": lema, "version": "", "build": build, "empresa": empresa},
            "soporte": soporte,
            "colores": {"marca": marca, "marcaOscuro": oscuro}, "logo": logo,
            "raiz": Path(os.path.relpath(str(p.raiz), str(docs))).as_posix(), "manuales": manuales}


# ===========================================================================
#  Contenido sacado del código: menú, pantallas, formularios, rutas y tablas.
#  Todo lo que se escribe en los borradores sale de un archivo del proyecto.
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


_REGLAS = [(r"required", "obligatorio"), (r"min_length\[(\d+)\]|min:(\d+)", "al menos {} caracteres"),
           (r"max_length\[(\d+)\]|max:(\d+)", "como mucho {} caracteres"),
           (r"exact_length\[(\d+)\]|size:(\d+)", "exactamente {} caracteres"),
           (r"valid_email|\bemail\b", "un correo válido"), (r"\bnumeric\b|\binteger\b|is_natural|digits", "solo números"),
           (r"is_unique|\bunique\b", "no puede repetirse"), (r"matches\[(\w+)\]|\bconfirmed\b", "hay que escribirlo dos veces"),
           (r"valid_date|\bdate\b", "una fecha"), (r"alpha_space|alpha\b", "solo letras")]


def reglas_de_validacion(texto):
    """{nombre del campo: ['obligatorio', 'al menos 3 caracteres']} de CodeIgniter y Laravel."""
    out = {}
    for m in re.finditer(r"['\"]([\w.]+)['\"]\s*=>\s*(?:\[\s*['\"]?rules['\"]?\s*=>\s*)?['\"]([a-z_|\[\],:0-9 .]+)['\"]",
                         texto):
        campo, reglas = m.group(1), m.group(2)
        if "|" not in reglas and not re.match(r"^(required|min|max|valid|numeric|is_|email)", reglas):
            continue
        dichas = []
        for patron, texto_regla in _REGLAS:
            r = re.search(patron, reglas)
            if r:
                n = next((x for x in r.groups() if x), "") if r.groups() else ""
                dichas.append(texto_regla.format(n) if "{}" in texto_regla else texto_regla)
        if dichas:
            out.setdefault(campo, dichas)
    return out


def _tipo_legible(d):
    t = d["tipo"]
    return {"email": "correo", "password": "contraseña (no se ve al escribir)", "number": "número", "date": "fecha",
            "datetime-local": "fecha y hora", "time": "hora", "tel": "teléfono", "file": "archivo (se adjunta)",
            "checkbox": "casilla para marcar", "radio": "una de varias opciones", "lista": "lista para elegir",
            "texto largo": "texto largo", "url": "dirección web", "search": "búsqueda"}.get(t, "texto")


def tabla_campos(f, reglas=None):
    """La tabla «Campo | Qué escribir» de un formulario, con lo que se sabe de cada campo."""
    reglas = reglas or {}
    filas = []
    for d in f.get("detalles", []):
        partes = [_tipo_legible(d)]
        r = reglas.get(d["name"]) or []
        if d["obligatorio"] or "obligatorio" in r:
            partes.append("obligatorio")
        partes += [x for x in r if x != "obligatorio"]
        if d["max"] and not any("como mucho" in x for x in r):
            partes.append("como mucho %s caracteres" % d["max"])
        if d["min_n"] and d["max_n"]:
            partes.append("entre %s y %s" % (d["min_n"], d["max_n"]))
        if d["opciones"]:
            partes.append("opciones: " + ", ".join(d["opciones"]))
        if d["ejemplo"]:
            partes.append("ejemplo: «%s»" % d["ejemplo"])
        filas.append("| **%s** | %s |" % (_md_celda(d["nombre"]), _md_celda("; ".join(dict.fromkeys(partes)))))
    if not filas:
        return []
    return ["| Campo | Qué poner |", "|---|---|"] + filas + [""]



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
        self.vistas = [f for f in _archivos(p.raiz, _EXT_VISTAS, 4000)
                       if f.resolve() != _PROPIO and re.search(r"<(form|table|h[1-4]|nav|button)\b", _texto(f, 400000))
                       and not f.name.startswith("generate_")]
        self.rutas = self._rutas()

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
        for f in self.vistas + [x for x in _archivos(self.p.raiz, _EXT_VISTAS, 4000) if x not in self.vistas]:
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
            for f in _archivos(self.p.raiz, (".php",), 3000):
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


def _texto_formulario(f, como_entrar=False):
    pasos = []
    if f["campos"]:
        pasos.append("%s %s." % ("Escriba" if como_entrar else "Rellene", _lista_y(["**%s**" % c for c in f["campos"]])))
    if f["boton"]:
        pasos.append("Pulse **%s**." % f["boton"])
    return pasos


def _codigo_del_modulo(p, pan, segmento):
    """El texto del controlador que atiende esa opción del menú (para sus mensajes y validaciones)."""
    ruta = pan.rutas.get(segmento)
    if not ruta or not ruta[0]:
        return ""
    for f in _archivos(p.raiz, (".php",), 3000):
        if f.stem == ruta[0]:
            return _texto(f)
    return ""


def manual_usuario(p, conf, defi):
    pan = Pantallas(p)
    idn = conf["identidad"]
    out = ["# %s · %s" % (defi["titulo"], idn["nombre"]), "",
           "Este manual explica cómo usar **%s**%s. Cada apartado corresponde a una opción del menú: qué se ve en "
           "esa pantalla, qué se puede hacer en ella y cómo, paso a paso, con el nombre que tienen los botones y los "
           "campos en la pantalla." % (idn["nombre"], (", " + idn["lema"][:1].lower() + idn["lema"][1:].rstrip("."))
                                       if idn.get("lema") else ""), ""]
    problemas = []

    # --- Antes de empezar
    out += ["## Antes de empezar", ""]
    out += ["Para usar %s solo necesita un navegador actualizado (Chrome, Edge o Firefox) y la dirección de la "
            "aplicación que le haya dado su empresa." % idn["nombre"], ""]
    ent = pan.entrada()
    menu = pan.menu()
    if ent:
        a = analizar_pantalla(_texto(ent))
        form = a["formularios"][0] if a["formularios"] else None
        out += ["### Entrar en el sistema", ""]
        pasos = ["Abra la dirección de la aplicación en el navegador. Aparece la pantalla de entrada."] + \
            (_texto_formulario(form, True) if form else [])
        if menu:
            pasos.append("Si los datos son correctos, se abre la pantalla principal con el menú.")
        out += ["%d. %s" % (i, x) for i, x in enumerate(pasos, 1)] + [""]
        if form and form.get("detalles"):
            out += tabla_campos(form)
        otros = list(dict.fromkeys(t for t in a["vinculos"] + a["acciones"] if (not form or t != form["boton"]) and t != "#"))
        olvido = [t for t in otros if re.search(r"olvid|recuper|forgot|reset|tarjeta|preguntas", _sin_tildes(t))]
        registro = [t for t in otros if re.search(r"registr|crear cuenta|sign up", _sin_tildes(t))]
        if registro:
            out += ["Si todavía no tiene cuenta, pulse **%s** en la pantalla de entrada y rellene sus datos." % registro[0], ""]
        if olvido:
            out += ["### Si olvidó sus datos de acceso", "",
                    "En la pantalla de entrada tiene %s. Pulse la opción que corresponda y siga los pasos que "
                    "aparecen." % _lista_y(["**%s**" % t for t in olvido]), ""]
            problemas.append(("Olvidó la contraseña o no puede entrar", "En la pantalla de entrada, pulse %s y siga "
                              "los pasos." % " o ".join("**%s**" % t for t in olvido)))
        for msg, tipo in a["mensajes"][:4]:
            if tipo == "Error":
                problemas.append(("Al entrar aparece «%s»" % msg, "Revise el usuario y la contraseña (mayúsculas y "
                                  "minúsculas cuentan) y vuelva a intentarlo."))
    salir = [t for t in sum((analizar_pantalla(_texto(f, 300000))["vinculos"] for f in pan.vistas
                             if re.search(r"topbar|header|nav|sidebar|layout|menu", f.stem, re.I)), [])
             if re.search(r"salir|cerrar sesion|logout|log out|desconect", _sin_tildes(t))]
    if menu:
        out += ["### La pantalla principal", "",
                "Una vez dentro, el menú tiene estas opciones: %s. Cada una tiene su apartado en este manual, en el "
                "mismo orden." % _lista_y(["**%s**" % t for t, _s, _p in menu]), ""]
        if any(pm for _t, _s, pm in menu):
            solo = [t for t, _s, pm in menu if pm]
            out += ["> %s solo aparece%s si su usuario tiene permiso. Si no lo ve y lo necesita, pídalo a quien "
                    "administra la aplicación." % (_lista_y(["**%s**" % t for t in solo]), "n" if len(solo) > 1 else ""),
                    ""]
            problemas.append(("No veo una opción del menú (%s)" % _lista_y(solo), "Su usuario no tiene permiso para "
                              "esa opción. Pida acceso a quien administra la aplicación."))
    if salir:
        out += ["### Salir del sistema", "", "Cuando termine, pulse **%s**. Así nadie puede usar su sesión si deja el "
                "equipo encendido." % salir[0], ""]

    # --- Un apartado por módulo
    modulos = [(t, pan.vista_de(s), s) for t, s, _p in menu] if menu else [(t, f, "") for t, f in pan.sueltas()]
    n = 0
    for nombre, vista, seg in modulos:
        a = analizar_pantalla(_texto(vista, 400000)) if vista else None
        if a and not (a["titulo"] or a["columnas"] or a["formularios"] or a["acciones"]):
            a = None
        if not a:
            continue
        codigo = _codigo_del_modulo(p, pan, seg)
        reglas = reglas_de_validacion(codigo)
        n += 1
        out += ["## %d. %s" % (n, nombre), ""]
        intro = []
        if a["titulo"] and _sin_tildes(a["titulo"]) != _sin_tildes(nombre):
            intro.append("Al pulsar **%s** en el menú se abre la pantalla **%s**." % (nombre, a["titulo"]))
        else:
            intro.append("Al pulsar **%s** en el menú se abre su pantalla." % nombre)
        if a["ayuda"]:
            intro.append("La propia pantalla lo resume así: «%s»" % a["ayuda"].rstrip(".") + ".")
        out += [" ".join(intro), ""]
        if a["columnas"]:
            out += ["### Qué se ve", "", "Una lista con estas columnas:", ""]
            out += ["- **%s**" % c for c in a["columnas"]] + [""]
            if a["buscador"]:
                out += ["La lista tiene un **buscador**: escriba cualquier dato (un nombre, un número) y se queda solo "
                        "con las filas que lo contienen. También puede ordenarla pulsando el título de una columna.", ""]
        if a["acciones"] or a["iconos"]:
            out += ["### Qué se puede hacer", ""]
            out += ["- **%s**" % x for x in a["acciones"]]
            out += ["- En cada fila: el botón para %s." % x for x in a["iconos"]] + [""]
        tareas = list(a["formularios"])
        for texto, href in a["enlaces"]:
            destino = pan.vista_de(_segmento(href))
            if destino and destino != vista:
                for fo in analizar_pantalla(_texto(destino, 400000))["formularios"]:
                    tareas.append(dict(fo, titulo=fo["titulo"] or texto, desde=texto))
                if re.search(r"report|pdf|excel|export|imprim|descarg", _sin_tildes(texto)):
                    tareas.append({"titulo": texto, "campos": [], "detalles": [], "boton": "", "desde": texto,
                                   "abre": True})
            elif re.search(r"report|pdf|excel|export|imprim|descarg", _sin_tildes(texto)):
                tareas.append({"titulo": texto, "campos": [], "detalles": [], "boton": "", "desde": texto, "abre": True})
        vistos = set()
        for fo in tareas:
            titulo = fo["titulo"] or fo["boton"] or nombre
            if titulo in vistos:
                continue
            vistos.add(titulo)
            pasos = []
            if fo.get("abre"):
                pasos = ["Pulse **%s**." % fo["desde"],
                         ("El documento se abre en una pestaña nueva del navegador: desde ahí puede verlo, descargarlo "
                          "o imprimirlo.") if fo["desde"] in a["pestana"] else
                         "Se abre el documento: desde el navegador puede descargarlo o imprimirlo."]
            else:
                if fo.get("desde"):
                    pasos.append("Pulse **%s**." % fo["desde"])
                elif re.search(r"modific|editar|actualiz", _sin_tildes(titulo + fo["boton"])) and \
                        "modificar (el lápiz)" in a["iconos"]:
                    pasos.append("En la fila que quiere cambiar, pulse el botón de modificar (el lápiz). Se abre una "
                                 "ventana con los datos actuales.")
                pasos += _texto_formulario(fo)
            if not pasos:
                continue
            out += ["### %s" % titulo, ""] + ["%d. %s" % (i, x) for i, x in enumerate(pasos, 1)] + [""]
            out += tabla_campos(fo, reglas)
            if any(d["obligatorio"] for d in fo.get("detalles", [])) or any("obligatorio" in v for v in reglas.values()):
                out += ["Si falta un campo obligatorio, la pantalla no deja guardar y le indica cuál falta.", ""]
        if "eliminar (la papelera)" in a["iconos"]:
            out += ["### Eliminar", "", "1. En la fila que quiere borrar, pulse el botón de eliminar (la papelera)."]
            if a["confirmaciones"]:
                out += ["2. La aplicación pregunta «%s». Pulse **Aceptar** para borrar o **Cancelar** para dejarlo como "
                        "estaba." % a["confirmaciones"][0], "", "> Revise bien la fila antes de aceptar: lo que se "
                        "borra desaparece de la lista.", ""]
            else:
                out += [""]
        mensajes = list(dict.fromkeys(a["mensajes"] + mensajes_en(codigo)))
        if mensajes:
            out += ["### Mensajes que puede ver", "", "| Mensaje | Qué indica |", "|---|---|"]
            out += ["| «%s» | %s |" % (_md_celda(m), {"Error": "Algo no se pudo hacer: revise los datos y vuelva a "
                                                      "intentarlo.", "Confirmación": "La operación se hizo bien."}
                                       .get(t, "Un aviso de la aplicación.")) for m, t in mensajes[:10]] + [""]
    if not n:
        out += ["## 1. Las pantallas", "", "POR ESCRIBIR: no encontré el menú ni las pantallas en el código. Escriba "
                "aquí cada módulo, con el nombre que tiene en el menú y sus pasos.", ""]
    problemas += [("La página no carga o se queda en blanco", "Compruebe la conexión a internet y recargue con **F5**. "
                   "Si sigue igual, avise a soporte."),
                  ("Un dato guardado no aparece en la lista", "Recargue la página con **F5**.")]
    out += ["## Problemas frecuentes", "", "| Lo que pasa | Qué hacer |", "|---|---|"]
    out += ["| %s | %s |" % (_md_celda(x), _md_celda(y)) for x, y in problemas] + [""]
    out += ["## Soporte técnico", "", texto_soporte(conf), ""]
    return "\n".join(out)



def texto_soporte(conf):
    s = conf.get("soporte") or {}
    partes = [("Correo", s.get("correo")), ("Teléfono", s.get("telefono")), ("Horario", s.get("horario"))]
    lineas = ["- **%s:** %s" % (k, v) for k, v in partes if v]
    empresa = conf["identidad"].get("empresa", "")
    if lineas:
        return "Si algo no le sale o ve un error, escriba o llame a soporte%s. Diga qué estaba haciendo y, si puede, " \
               "envíe una captura de la pantalla.\n\n%s" % ((" de " + empresa) if empresa else "", "\n".join(lineas))
    return "Si algo no le sale o ve un error, avise a quien administra la aplicación%s. Diga qué estaba haciendo y, " \
           "si puede, envíe una captura de la pantalla." % ((" en " + empresa) if empresa else "")


def tablas_de_datos(p):
    """[(tabla, [columnas], archivo)] de las migraciones, los volcados .sql o los modelos de Django."""
    out = {}
    for f in _archivos(p.raiz, (".sql", ".php", ".py"), 4000):
        rel = _rel(p.raiz, f)
        if re.search(r"(^|/)(tests?|spec|fixtures?)/", rel):
            continue
        t = _texto(f, 3000000)
        if f.suffix == ".sql":
            for m in re.finditer(r"CREATE TABLE\s+(?:IF NOT EXISTS\s+)?[`\"]?(\w+)[`\"]?\s*\(([\s\S]*?)\)\s*(?:ENGINE|;)", t, re.I):
                cols = [c for c in re.findall(r"(?m)^\s*[`\"]?(\w+)[`\"]?\s+[a-zA-Z]", m.group(2))
                        if c.upper() not in ("PRIMARY", "KEY", "UNIQUE", "CONSTRAINT", "INDEX", "FOREIGN")]
                out.setdefault(m.group(1), (cols, rel))
        elif f.suffix == ".php" and re.search(r"migrations?", rel, re.I):
            for m in re.finditer(r"Schema::create\(\s*['\"](\w+)['\"][\s\S]*?\n\s*\}\);", t):
                cols = re.findall(r"\$table->\w+\(\s*['\"](\w+)", m.group(0))
                out.setdefault(m.group(1), (cols, rel))
            m = re.search(r"createTable\(\s*['\"](\w+)", t)
            if m:
                campos = re.search(r"addField\(\s*\[([\s\S]*?)\]\s*\);", t)
                out.setdefault(m.group(1), (re.findall(r"(?m)^\s*['\"](\w+)['\"]\s*=>\s*\[", campos.group(1)) if campos else [], rel))
        elif f.name == "models.py":
            for m in re.finditer(r"class\s+(\w+)\((?:models\.)?Model\):([\s\S]*?)(?=\nclass |\Z)", t):
                out.setdefault(m.group(1), (re.findall(r"(?m)^\s+(\w+)\s*=\s*models\.", m.group(2)), rel))
    return [(k, v[0], v[1]) for k, v in out.items()][:40]


def tablas_usadas(p):
    """Tablas que el código consulta, aunque no haya migraciones: {tabla: archivo donde aparece primero}."""
    out = {}
    orm = re.compile(r"->(?:table|from|join)\(\s*['\"](\w+)|\$table\s*=\s*['\"](\w+)|__tablename__\s*=\s*['\"](\w+)|"
                     r"db_table\s*=\s*['\"](\w+)")
    cadena = re.compile(r"\"((?:SELECT|INSERT|UPDATE|DELETE)\b[^\"]*)\"|'((?:SELECT|INSERT|UPDATE|DELETE)\b[^']*)'", re.I)
    sql = re.compile(r"\b(?:FROM|INTO|JOIN|UPDATE)\s+`?(\w+)", re.I)
    for f in _archivos(p.raiz, (".php", ".py", ".js", ".ts", ".java", ".cs", ".go", ".rb"), 4000):
        rel = _rel(p.raiz, f)
        if f.resolve() == _PROPIO or f.name.startswith("generate_") or \
                re.search(r"(^|/)(tests?|spec|views?|templates?|public|static|assets|config)/", rel, re.I):
            continue
        t = _texto(f, 1000000)
        nombres = [next(g for g in m.groups() if g) for m in orm.finditer(t)]
        for m in cadena.finditer(t):
            nombres += sql.findall(m.group(1) or m.group(2))
        for n in nombres:
            if not n.isdigit() and n.lower() not in ("set", "select", "where", "dual", "values"):
                out.setdefault(n, rel)
    return out


def rutas_de(p):
    out = list(p.endpoints())
    for f in (p.raiz / "app/Config/Routes.php",):
        for m in re.finditer(r"\$routes->(get|post|put|patch|delete|match|add)\(\s*['\"]([^'\"]+)['\"]\s*,\s*['\"]([^'\"]+)",
                             _texto(f)):
            out.append((m.group(1).upper(), "/" + m.group(2).strip("/"), m.group(3)))
    vistos, limpio = set(), []
    for met, ruta, dest in out:
        if (met, ruta) not in vistos:
            vistos.add((met, ruta))
            limpio.append((met, ruta, dest))
    return limpio[:80]


_SECRETO_NOMBRE = re.compile(r"PASS|PWD|SECRET|TOKEN|KEY|SALT|PRIVATE", re.I)


def _tabla_variables(p):
    bloques, _cab = p.variables()
    filas = []
    for titulo, grupo in bloques:
        for _com, nombres, valores in grupo:
            desc = describir_variables(nombres)
            for n, v in zip(nombres, valores):
                v = "(la suya)" if _SECRETO_NOMBRE.search(n) and v else (v or "(vacío)")
                filas.append((titulo, n, v, desc))
    return filas


def _framework(p):
    return next((n for n, _v, _f, _l, rol in p.tecnologias() if rol == "framework"), "")


def _requisitos(p, extra=True):
    lineas = ["- **%s**%s" % (n, (" " + v.replace("+", " o superior")) if v else "") for n, v, _f, _l, _r in p.tecnologias()]
    if extra:
        if p.composer:
            lineas.append("- **Composer** (instala las librerías de PHP)")
        if p.package and not any(l.startswith("- **Node.js**") for l in lineas):
            lineas.append("- **Node.js** con **npm** (instala las librerías de JavaScript)")
        lineas.append("- **Git** (para descargar el proyecto)")
    exts = p.extensiones_php()
    if exts:
        lineas.append("- Extensiones de PHP: %s" % ", ".join("`%s`" % e[0] for e in exts))
    return "\n".join(lineas) or "- Lo que pida el lenguaje del proyecto."


def _historial(p, idn, version):
    tags = _git(p.raiz, "for-each-ref", "--sort=-creatordate", "--format=%(refname:short)|%(creatordate:short)|%(subject)",
                "refs/tags")
    filas = [l.split("|", 2) for l in (tags or "").splitlines() if l.count("|") >= 2][:15]
    if filas:
        return ["| Versión | Cuándo | Qué trajo |", "|---|---|---|"] + \
            ["| %s | %s | %s |" % (_md_celda(a), b, _md_celda(c)) for a, b, c in filas]
    log = _git(p.raiz, "log", "-12", "--no-merges", "--date=short", "--format=%ad|%s")
    filas = [l.split("|", 1) for l in (log or "").splitlines() if "|" in l]
    cab = ["Versión actual: **%s** (%s)." % (version or "sin número", idn.get("build") or "sin fecha"), ""]
    if filas:
        return cab + ["Los últimos cambios, según git:", "", "| Cuándo | Qué cambió |", "|---|---|"] + \
            ["| %s | %s |" % (a, _md_celda(b)) for a, b in filas]
    return cab


# ---------------------------------------------------------------- manual técnico: más detalle
def modulos_tecnicos(p, pan):
    """[(opción del menú, ruta, controlador::método, vista)] de cada opción del menú."""
    out = []
    for texto, seg, _pm in pan.menu():
        ctl = pan.rutas.get(seg)
        vista = pan.vista_de(seg)
        out.append((texto, "/" + seg, ("%s::%s" % ctl) if ctl and ctl[0] else "—",
                    _rel(p.raiz, vista) if vista else "—"))
    return out


def controladores(p):
    """[(archivo, [métodos públicos])] de los controladores del proyecto."""
    out = []
    for f in _archivos(p.raiz, (".php", ".py", ".js", ".ts", ".java", ".cs", ".rb")):
        rel = _rel(p.raiz, f)
        if not re.search(r"(^|/)(controllers?|controladores)/", rel, re.I) or re.search(r"(^|/)(tests?|vendor)/", rel):
            continue
        t = _texto(f)
        if f.suffix == ".php":
            mets = re.findall(r"public\s+function\s+(\w+)\s*\(", t)
        elif f.suffix == ".py":
            mets = re.findall(r"^\s*def\s+([a-z]\w*)\s*\(", t, re.M)
        else:
            mets = re.findall(r"^\s*(?:public\s+|async\s+|export\s+)*(?:function\s+)?([a-z]\w*)\s*\([^)]*\)\s*\{", t, re.M)
        mets = [m for m in dict.fromkeys(mets) if not m.startswith("__") and m not in ("if", "for", "while", "switch",
                                                                                  "catch", "function")]
        if mets:
            out.append((rel, mets[:15]))
    return out[:40]


def modelos(p):
    """[(archivo, tabla, [campos permitidos])] de los modelos (CodeIgniter, Laravel)."""
    out = []
    for f in _archivos(p.raiz, (".php",)):
        rel = _rel(p.raiz, f)
        if not re.search(r"(^|/)(models?|modelos)/", rel, re.I):
            continue
        t = _texto(f)
        tabla = re.search(r"\$table\s*=\s*['\"](\w+)", t)
        campos = re.search(r"\$(?:allowedFields|fillable)\s*=\s*\[([^\]]*)\]", t)
        out.append((rel, tabla.group(1) if tabla else "—",
                    re.findall(r"['\"](\w+)['\"]", campos.group(1)) if campos else []))
    return out[:40]


def dependencias(p):
    """[(paquete, versión, archivo)] de composer.json y package.json (las que necesita en producción)."""
    out = []
    for k, v in (p.composer.get("require") or {}).items():
        if k != "php" and not k.startswith("ext-"):
            out.append((k, v, "composer.json"))
    for k, v in (p.package.get("dependencies") or {}).items():
        out.append((k, v, "package.json"))
    req = _texto(p.raiz / "requirements.txt")
    for linea in req.splitlines():
        m = re.match(r"^\s*([A-Za-z0-9_.\-\[\]]+)\s*([=<>~!].*)?$", linea)
        if m and not linea.strip().startswith("#"):
            out.append((m.group(1), (m.group(2) or "").strip() or "—", "requirements.txt"))
    return out[:40]


def filtros_de_acceso(p):
    """[(nombre, qué clase, dónde se aplica)] de los filtros de CodeIgniter y el middleware de Laravel."""
    out = []
    t = _texto(p.raiz / "app/Config/Filters.php")
    if t:
        de_serie = set(re.findall(r"use\s+CodeIgniter\\[\w\\]*\\(\w+)\s*;", t))
        for m in re.finditer(r"['\"](\w+)['\"]\s*=>\s*\\?([\w\\]+)::class", t):
            if m.group(2).split("\\")[0] != "CodeIgniter" and m.group(2) not in de_serie:
                out.append((m.group(1), m.group(2).split("\\")[-1], "app/Config/Filters.php"))
    for f in (p.raiz / "app/Config/Routes.php", p.raiz / "routes/web.php"):
        for m in re.finditer(r"['\"]filter['\"]\s*=>\s*['\"]([\w:,]+)|->middleware\(\s*\[?\s*['\"]([\w:,]+)", _texto(f)):
            out.append((m.group(1) or m.group(2), "aplicado a rutas", _rel(p.raiz, f)))
    return list(dict.fromkeys(out))[:20]


def secciones_tecnicas_extra(p, pan):
    out = []
    mods = modulos_tecnicos(p, pan)
    if mods:
        out += [("Módulos", ["Cada opción del menú, con la ruta que abre, el código que la atiende y la plantilla que "
                             "pinta:", "", "| Opción | Ruta | Controlador | Vista |", "|---|---|---|---|"]
                 + ["| %s | `%s` | %s | `%s` |" % tuple(_md_celda(x) for x in fila) for fila in mods] + [""])]
    ctl = controladores(p)
    if ctl:
        out += [("Controladores", ["| Archivo | Métodos públicos |", "|---|---|"]
                 + ["| `%s` | %s |" % (f, _md_celda(", ".join("`%s`" % m for m in mets))) for f, mets in ctl] + [""])]
    mds = modelos(p)
    if mds:
        out += [("Modelos", ["| Archivo | Tabla | Campos que se pueden guardar |", "|---|---|---|"]
                 + ["| `%s` | `%s` | %s |" % (f, t, _md_celda(", ".join(c)) or "—") for f, t, c in mds] + [""])]
    flt = filtros_de_acceso(p)
    if flt:
        out += [("Control de acceso", ["Filtros o middleware que protegen las rutas:", "",
                                       "| Nombre | Clase / uso | Dónde |", "|---|---|---|"]
                 + ["| `%s` | %s | `%s` |" % f for f in flt] + [""])]
    dep = dependencias(p)
    if dep:
        out += [("Dependencias", ["| Paquete | Versión | Archivo |", "|---|---|---|"]
                 + ["| `%s` | `%s` | `%s` |" % d for d in dep] + [""])]
    return out


# ---------------------------------------------------------------- guía de instalación: más pasos
def pasos_instalacion_extra(p, fw, filas, carpeta):
    """[(título, [líneas])] de los pasos que van después de arrancar."""
    out = []
    publica = "public/" if (p.raiz / "public" / "index.php").exists() else ""
    if p.archivos_php():
        lineas = ["Si la sirve con **Apache** (por ejemplo con XAMPP):", "",
                  "- Copie la carpeta del proyecto dentro de `htdocs` (en XAMPP, `C:\\xampp\\htdocs\\%s`)." % carpeta]
        if publica:
            lineas.append("- La carpeta que se publica es `public/`: abra `http://localhost/%s/public/`, o haga que el "
                          "sitio apunte a esa carpeta (DocumentRoot)." % carpeta)
        if (p.raiz / publica / ".htaccess").is_file() or (p.raiz / ".htaccess").is_file():
            lineas.append("- El proyecto trae `.htaccess`: active el módulo `mod_rewrite` de Apache para que las "
                          "direcciones funcionen.")
        out.append(("Configurar el servidor web", lineas))
    escribibles = [d for d in ("writable", "storage", "bootstrap/cache", "uploads", "public/uploads", "logs")
                   if (p.raiz / d).is_dir()]
    if escribibles:
        out.append(("Permisos de las carpetas", ["La aplicación necesita escribir en %s (caché, registros y archivos "
                                                 "subidos). En Linux:" % _lista_y(["`%s/`" % d for d in escribibles]),
                                                 "", "```", "chmod -R 775 %s" % " ".join(escribibles), "```", "",
                                                 "En Windows con XAMPP no suele hacer falta."]))
    semillas = [f for f in _archivos(p.raiz, (".php", ".py")) if re.search(r"(^|/)(seeds|seeders)/", _rel(p.raiz, f))]
    if semillas:
        orden = {"CodeIgniter": "php spark db:seed %s", "Laravel": "php artisan db:seed --class=%s"}.get(fw)
        lineas = ["El proyecto trae datos iniciales (%s)." % _lista_y(["`%s`" % _rel(p.raiz, f) for f in semillas[:5]])]
        if orden:
            lineas += ["", "```"] + [orden % f.stem for f in semillas[:5]] + ["```"]
        out.append(("Cargar los datos iniciales", lineas))
    out.append(("Comprobar que funciona", ["Abra la aplicación en el navegador. Si todo está bien, aparece su primera "
                                           "pantalla sin errores. Si sale un error, mire «Cuando algo no sale» más "
                                           "abajo."]))
    act = ["Para instalar una versión nueva sobre una que ya funciona:", "", "```"]
    if p.remoto().valor:
        act.append("git pull")
    if p.composer:
        act.append("composer install")
    if p.package:
        act.append("npm install")
    migra = {"CodeIgniter": "php spark migrate", "Laravel": "php artisan migrate", "Django": "python manage.py migrate"}.get(fw)
    if migra and any(re.search(r"migrations?", _rel(p.raiz, f), re.I) for f in _archivos(p.raiz, (".php", ".py"))
                     if not re.search(r"(^|/)tests?/", _rel(p.raiz, f))):
        act.append(migra)
    act += ["```", "", "Haga antes una copia de la base de datos y del `.env`: así puede volver atrás si algo falla."]
    if len(act) > 6:
        out.append(("Actualizar a una versión nueva", act))
    return out


def manual_tecnico(p, conf, defi, version):
    idn = conf["identidad"]
    pan = Pantallas(p)
    fw = _framework(p)
    out = ["# %s · %s" % (defi["titulo"], idn["nombre"]), "",
           "Lo que necesita saber un desarrollador para entender, mantener y ampliar %s: cómo está hecho, "
           "dónde está cada cosa y cómo se configura." % idn["nombre"], "",
           "## 1. Qué es", ""]
    desc = p.descripcion().valor or idn.get("lema", "")
    lenguajes = [n for n, _v, _f, _l, rol in p.tecnologias() if rol == "lenguaje"]
    out += ["**%s**%s. Está hecho en %s%s." % (idn["nombre"], (": " + desc[:1].lower() + desc[1:].rstrip(".")) if desc else "",
                                              _lista_y(lenguajes) or "—", (" con " + fw) if fw else ""), ""]
    menu = pan.menu()
    if menu:
        out += ["Sus módulos (las opciones del menú) son: %s." % _lista_y([t for t, _s, _p in menu]), ""]
    out += ["## 2. Requisitos", "", _requisitos(p), ""]
    arbol = p.arbol()
    if arbol:
        out += ["## 3. Estructura", "", "```", arbol, "```", ""]
    sec = 4 if arbol else 3
    for titulo, lineas in secciones_tecnicas_extra(p, pan):
        out += ["## %d. %s" % (sec, titulo), ""] + lineas
        sec += 1
    rutas = rutas_de(p)
    if rutas:
        out += ["## %d. Rutas" % sec, "", "| Método | Ruta | Qué la atiende |", "|---|---|---|"]
        out += ["| %s | `%s` | %s |" % (m, _md_celda(r), _md_celda(d)) for m, r, d in rutas] + [""]
        sec += 1
    tablas = tablas_de_datos(p)
    usadas = {} if tablas else tablas_usadas(p)
    bases = [n for n, *_r in p.bases_de_datos()]
    if tablas or bases or usadas:
        out += ["## %d. Base de datos" % sec, ""]
        if bases:
            out += ["Motor: %s." % _lista_y(bases), ""]
        if tablas:
            out += ["| Tabla | Columnas | Dónde se define |", "|---|---|---|"]
            out += ["| `%s` | %s | `%s` |" % (t, _md_celda(", ".join(c[:12]) + (" …" if len(c) > 12 else "")) or "—", f)
                    for t, c, f in tablas] + [""]
        elif usadas:
            out += ["No hay migraciones ni un volcado `.sql` en el proyecto. Estas son las tablas que usa el código:", "",
                    "| Tabla | Aparece en |", "|---|---|"]
            out += ["| `%s` | `%s` |" % (t, f) for t, f in sorted(usadas.items())] + [""]
        sec += 1
    filas = _tabla_variables(p)
    if filas:
        out += ["## %d. Configuración" % sec, "", "Se configura en `.env` (la plantilla es `%s`). El `.env` lleva "
                "contraseñas: no se sube al repositorio." % _rel(p.raiz, p.env_ejemplo), "",
                "| Variable | Por defecto | Para qué |", "|---|---|---|"]
        out += ["| `%s` | `%s` | %s |" % (n, _md_celda(v), _md_celda(d) or "—") for _t, n, v, d in filas] + [""]
        sec += 1
    ords = p.ordenes()
    if ords:
        out += ["## %d. Órdenes útiles" % sec, "", "| Orden | Qué hace |", "|---|---|"]
        out += ["| `%s` | `%s` |" % (o, _md_celda(c)) for o, c, _f in ords] + [""]
        sec += 1
    out += ["## %d. Historial" % sec, ""] + _historial(p, idn, version) + [""]
    return "\n".join(out)


def _orden_copiar(origen):
    return "copy %s .env        # Windows\ncp %s .env          # Mac y Linux" % (origen, origen)


def _arranque(p, fw):
    eco = p.ecosistema()
    scripts = p.package.get("scripts", {}) if p.package else {}
    if fw == "CodeIgniter":
        return ["php spark serve"], "http://localhost:8080"
    if fw == "Laravel":
        return ["php artisan serve"], "http://localhost:8000"
    if fw == "Symfony":
        return ["symfony server:start"], "http://localhost:8000"
    if fw == "Django":
        return ["python manage.py runserver"], "http://localhost:8000"
    if eco.get("pasos") and len(eco["pasos"]) > 1:
        return eco["pasos"][-1:], ""
    for s in ("dev", "start", "serve"):
        if s in scripts:
            return ["npm run %s" % s if s != "start" else "npm start"], ""
    if p.archivos_php():
        return [], ""
    return [], ""


def guia_instalacion(p, conf, defi):
    idn = conf["identidad"]
    fw = _framework(p)
    remoto = p.remoto().valor
    carpeta = remoto.rstrip("/").split("/")[-1].replace(".git", "") if remoto else p.raiz.name
    out = ["# %s · %s" % (defi["titulo"], idn["nombre"]), "",
           "Cómo poner en marcha %s en un equipo o servidor nuevo.%s" % (idn["nombre"],
                      " La primera parte son los pasos, en orden; la segunda explica la configuración en detalle."
                      if _tabla_variables(p) else " Siga los pasos en orden."), "",
           "## Lo que necesita antes de empezar", "", _requisitos(p), "", "## Los pasos", ""]
    n = 0

    def paso(titulo, *lineas):
        nonlocal n
        n += 1
        out.extend(["### Paso %d · %s" % (n, titulo), ""] + list(lineas) + [""])

    if remoto:
        paso("Descargar el proyecto", "```", "git clone %s" % remoto, "cd %s" % carpeta, "```")
    eco = p.ecosistema()
    instalar = (["composer install"] if p.composer else []) + (["npm install"] if p.package else []) + \
        [x for x in eco.get("pasos", [])[:-1] if x not in ("composer install", "npm install")]
    if instalar:
        paso("Instalar las librerías", "En la carpeta del proyecto:", "", "```", *instalar, "```")
    filas = _tabla_variables(p)
    if p.env_ejemplo:
        origen = _rel(p.raiz, p.env_ejemplo)
        lineas = ["Copie la plantilla de configuración:", "", "```", _orden_copiar(origen), "```", ""]
        if filas:
            lineas += ["Abra `.env` y cambie estos valores por los de su equipo:", "",
                       "| Variable | Valor de ejemplo |", "|---|---|"]
            lineas += ["| `%s` | `%s` |" % (nm, _md_celda(v)) for _t, nm, v, _d in filas]
        paso("Configurar", *lineas)
    bd = next((v for _t, nm, v, _d in filas if re.search(r"(database\.default\.database|DB_DATABASE|DB_NAME|"
                                                          r"DATABASE_NAME|MYSQL_DATABASE)$", nm) and v and v != "—"), "")
    tablas = tablas_de_datos(p)
    volcados = sorted({f for _t, _c, f in tablas if f.endswith(".sql")})
    migra = {"CodeIgniter": "php spark migrate", "Laravel": "php artisan migrate", "Django": "python manage.py migrate",
             "Symfony": "php bin/console doctrine:migrations:migrate", "Ruby on Rails": "bin/rails db:migrate"}.get(fw)
    tiene_migraciones = any(re.search(r"migrations?", f, re.I) and not f.endswith(".sql") for _t, _c, f in tablas)
    if p.bases_de_datos() or tablas:
        lineas = ["Cree una base de datos vacía%s (por ejemplo con phpMyAdmin o la consola de su motor)." %
                  (" llamada `%s`" % bd if bd else "")]
        if volcados:
            lineas += ["", "Después cargue las tablas:", "", "```"] + \
                ["mysql -u root -p %s < %s" % (bd or "NOMBRE_DE_LA_BASE", v) for v in volcados] + ["```"]
        elif migra and tiene_migraciones:
            lineas += ["", "Después cree las tablas:", "", "```", migra, "```"]
        else:
            lineas += ["", "> El proyecto no trae las tablas (ni migraciones ni un archivo `.sql`). Pida el volcado de la "
                       "base de datos a quien la administra e impórtelo en esa base."]
        paso("Preparar la base de datos", *lineas)
    orden, url = _arranque(p, fw)
    if orden:
        lineas = ["```"] + orden + ["```", ""] + (["Y abra %s en el navegador." % url] if url else [])
        if any(nm == "app.baseURL" for _t, nm, _v, _d in filas):
            lineas += ["", "> Si la sirve con XAMPP o Apache en vez de esta orden, ponga en `app.baseURL` la dirección "
                       "con la que la abre (terminada en `/public/`)."]
        paso("Arrancar", *lineas)
    elif p.archivos_php():
        paso("Arrancar", "Copie la carpeta del proyecto dentro de la carpeta web de su servidor (con XAMPP, `htdocs`) "
             "y abra `http://localhost/%s/` en el navegador." % carpeta)
    for titulo, lineas in pasos_instalacion_extra(p, fw, filas, carpeta):
        paso(titulo, *lineas)
    out += ["## Cuando algo no sale", "", "| Lo que pasa | Qué hacer |", "|---|---|"]
    filas_p = []
    if p.composer:
        filas_p.append(("Falta `vendor/autoload.php`", "No se instalaron las librerías: ejecute `composer install`."))
    if p.package:
        filas_p.append(("`Cannot find module`", "Ejecute `npm install`."))
    if bd or p.bases_de_datos():
        filas_p.append(("No conecta con la base de datos", "Compruebe que el motor está encendido y que los datos de "
                        "conexión del `.env` son correctos."))
    if fw == "CodeIgniter":
        filas_p += [("Error de permisos al escribir", "Dé permiso de escritura a la carpeta `writable/`."),
                    ("La página sale sin estilos o los enlaces fallan", "Revise `app.baseURL` en el `.env`.")]
    if fw == "Laravel":
        filas_p += [("No application encryption key", "Ejecute `php artisan key:generate`."),
                    ("Error de permisos al escribir", "Dé permiso de escritura a `storage/` y `bootstrap/cache/`.")]
    if fw == "Django":
        filas_p.append(("no such table", "Ejecute `python manage.py migrate`."))
    filas_p.append(("Otra cosa", "Lea el mensaje de error completo y avise a soporte con una captura."))
    out += ["| %s | %s |" % (a, b) for a, b in filas_p] + [""]
    if filas:
        out += ["# Segunda parte · la configuración en detalle", ""]
        grupo = None
        for t, nm, v, d in filas:
            if t != grupo:
                grupo = t
                out += ["", "## %s" % (t or "General"), ""]
            out += ["- `%s` (por defecto `%s`)%s" % (nm, v, (": " + d[:1].lower() + d[1:]) if d else "")]
        out += [""]
    return "\n".join(out)


def borrador(p, conf, defi, version):
    """El .md de un manual, sacado del código. Lleva una marca para saber si alguien lo ha tocado."""
    hacer = {"MANUAL-USUARIO": manual_usuario, "MANUAL-TECNICO": lambda a, b, c: manual_tecnico(a, b, c, version),
             "INSTALACION": guia_instalacion}.get(defi["archivo"])
    cuerpo = hacer(p, conf, defi) if hacer else "# %s\n\nPOR ESCRIBIR\n" % defi["titulo"]
    cuerpo = re.sub(r"\n{3,}", "\n\n", cuerpo).strip() + "\n"
    return "<!-- generate_manual:borrador %s · si lo editas, esta herramienta ya no lo reescribe -->\n%s" % (
        _sha(cuerpo.encode("utf-8"))[:12], cuerpo)


_FIRMAS_V1 = ("POR ESCRIBIR: el primer módulo", "POR ESCRIBIR: qué hace el sistema", "POR ESCRIBIR: lo mismo, explicado")


def es_borrador_intacto(md):
    """¿El .md es un borrador de la herramienta que nadie ha editado? Entonces se puede rehacer."""
    m = re.match(r"<!-- generate_manual:borrador (\w+) [^\n]*-->\n", md)
    if m:
        return _sha(md[m.end():].encode("utf-8"))[:12] == m.group(1)
    return any(f in md for f in _FIRMAS_V1) and md.count("POR ESCRIBIR") >= 4


# ===========================================================================
#  Órdenes
# ===========================================================================

def orden_generar(a):
    interactivo = not a.si
    raiz = Path(a.proyecto).resolve() if a.proyecto else raiz_del_proyecto()
    p = Proyecto(raiz)
    docs = carpeta_docs(raiz, a.docs)
    salida = (raiz / a.salida).resolve() if a.salida else docs
    print("Proyecto: %s\nDocumentación: %s/" % (raiz, _rel(raiz, docs)))
    escrituras = []
    ruta_conf = docs / "manuales.json"
    if ruta_conf.is_file():
        try:
            conf = json.loads(_texto(ruta_conf))
        except ValueError as e:
            raise ErrorManual("%s no es un JSON válido: %s" % (_rel(raiz, ruta_conf), e))
    else:
        conf = configurar(p, docs, a, interactivo)
        escrituras.append((ruta_conf, (json.dumps(conf, indent=4, ensure_ascii=False) + "\n").encode("utf-8")))
    conf.setdefault("identidad", {})
    cambio_conf = False
    if interactivo and "soporte" not in conf:
        conf["soporte"] = pedir_soporte()
        cambio_conf = True
    conf["_carpeta"] = _rel(raiz, docs)
    raiz_manifiesto = (docs / conf.get("raiz", "..")).resolve()
    version, fuente_v = (conf["identidad"].get("version"), "manuales.json") if conf["identidad"].get("version") \
        else version_del_proyecto(raiz_manifiesto)
    if not version and interactivo:
        version, fuente_v = pedir_version(), "tu respuesta"
        conf["identidad"]["version"] = version
        cambio_conf = True
    if cambio_conf:
        guardar = {k: v for k, v in conf.items() if not k.startswith("_")}
        escrituras = [(ruta_conf, (json.dumps(guardar, indent=4, ensure_ascii=False) + "\n").encode("utf-8"))]
    conf["identidad"]["version"] = version or "0.0.0"
    if not version:
        print("  [aviso] No encontré la versión en el proyecto: sale «0.0.0». Ponla en su manifiesto o en un archivo VERSION.")
    else:
        print("Versión: %s (de %s)" % (version, fuente_v))

    logo = None
    if conf.get("logo"):
        ruta_logo = (docs / conf["logo"]).resolve()
        if ruta_logo.is_file():
            logo = Logotipo(ruta_logo)
            if logo.claro():
                print("  [aviso] El logotipo es casi blanco: en papel no se verá. Pide uno oscuro.")
        else:
            print("  [aviso] No encuentro el logotipo %s: los PDF salen sin él." % conf["logo"])
    else:
        print("  [aviso] Sin logotipo para papel: los PDF salen sin él. Pídelo (oscuro, PNG, más ancho que alto).")

    resultados = []
    for defi in conf.get("manuales", []):
        if a.solo and defi["archivo"] != a.solo:
            continue
        fuente = docs / (defi["archivo"] + ".md")
        md = _texto(fuente) if fuente.is_file() else ""
        if not md.strip() or a.rehacer or es_borrador_intacto(md):
            md = borrador(p, conf, defi, version)
            escrituras.append((fuente, md.encode("utf-8")))
        elif "generate_manual:borrador" in md:
            print("  %s.md lo editaste tú: se respeta. (Con --rehacer se vuelve a escribir desde el código.)" % defi["archivo"])
        pdf, avisos = Manual(conf, defi, logo).generar(md)
        destino = salida / (defi["archivo"] + ".pdf")
        escrituras.append((destino, pdf))
        resultados.append((defi["archivo"], destino, len(pdf), avisos, any(f == fuente for f, _d in escrituras)))
    if not resultados:
        raise ErrorManual("No hay manuales que generar%s." % (" con el nombre %s" % a.solo if a.solo else ""))

    print("\n— Plan —")
    for f, datos in escrituras:
        marca = "+" if not f.exists() else ("=" if f.read_bytes() == datos else "~")
        print("  %s %-36s %.0f KB" % (marca, _rel(raiz, f), len(datos) / 1024))
    for nombre, _d, _t, avisos, nuevo in resultados:
        if nuevo:
            print("  [aviso] %s.md se escribe con lo que hay en el código: revísalo y completa lo que falte." % nombre)
        for x in avisos:
            print("  [aviso] %s: %s" % (nombre, x))
    print("\n  + nuevo   ~ cambia (con respaldo)   = sin cambios")
    if a.simulacro:
        print("\n(simulacro) No se ha escrito nada.")
        return 0
    if all(f.exists() and f.read_bytes() == d for f, d in escrituras):
        print("\nTodo estaba ya al día.")
        return 0
    if interactivo and not _si_no("\n¿Escribir los manuales?", False):
        print("Cancelado. No se ha escrito nada.")
        return 1
    man = aplicar(raiz, escrituras)
    print("\nHecho: %d archivo(s) nuevo(s), %d cambiado(s)." % (len(man["creados"]), len(man["modificados"])))
    for nombre, destino, tam, _a, _n in resultados:
        print("  %-16s ok  %s · %.0f KB" % (nombre, _rel(raiz, destino), tam / 1024))
    print("Para dejarlo como estaba:  %s" % _llamada("deshacer"))
    if any(r[4] for r in resultados):
        print("\nLos .md salen del código: revísalos y añade lo que el código no dice (para qué sirve cada cosa).")
        print("Cuando edites un .md, la herramienta lo respeta; vuelve a ejecutarla para regenerar los PDF.")
    print("\nEl .md es la fuente: el PDF no se edita, se regenera cada vez que cambia un .md.")
    return 0


def _argumentos():
    p = argparse.ArgumentParser(prog="generate_manual", description="Genera los manuales en PDF de la casa a partir "
                                "del Markdown de docs/. Sin IA, sin red y sin dependencias. Sin argumentos abre el asistente.")
    p.add_argument("--version", action="version", version="%(prog)s " + VERSION)
    s = p.add_subparsers(dest="orden", metavar="ORDEN")
    s.required = True
    g = s.add_parser("generar", help="genera los PDF (lo que hace sin argumentos); la primera vez prepara manuales.json")
    g.add_argument("proyecto", nargs="?")
    g.add_argument("--si", action="store_true", help="no preguntar")
    g.add_argument("--simulacro", action="store_true", help="enseña lo que haría sin escribir nada")
    g.add_argument("--docs", help="carpeta de la documentación (por omisión docs/)")
    g.add_argument("--salida", help="dónde dejar los PDF, relativa al proyecto (p. ej. public/docs)")
    g.add_argument("--solo", help="generar sólo ese manual (p. ej. MANUAL-USUARIO)")
    g.add_argument("--rehacer", action="store_true", help="volver a escribir los .md desde el código (con copia)")
    g.add_argument("--marca", help="color de la marca, la primera vez")
    g.add_argument("--marca-oscuro", help="color oscuro de la marca, la primera vez")
    g.add_argument("--sin-ventana", action="store_true", help="elegir los colores en la terminal")
    g.set_defaults(fn=orden_generar)
    u = s.add_parser("deshacer", help="deja los manuales como estaban")
    u.add_argument("proyecto", nargs="?")
    u.add_argument("--forzar", action="store_true")
    u.set_defaults(fn=orden_deshacer)
    return p


def main(argv=None):
    _consola_segura()
    args = list(sys.argv[1:] if argv is None else argv)
    if not args or args[0].startswith("--") and args[0] not in ("--help", "-h", "--version"):
        print("generate_manual %s · los manuales en PDF de tu aplicación, sin internet ni IA\n" % VERSION)
        args = ["generar"] + args
    a = _argumentos().parse_args(args)
    try:
        return a.fn(a)
    except ErrorManual as e:
        print("Error: %s" % e, file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("\nCancelado.")
        return 130


if __name__ == "__main__":
    sys.exit(main())
