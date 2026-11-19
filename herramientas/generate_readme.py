#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
generate_readme.py — la portada (README) de una aplicación, portable y sin IA.

Hace a mano lo que pide el agente `GenerateReadme` (.claude/agents/GenerateReadme.md):
un README con la portada de la casa —banner con el logotipo de la empresa,
distintivos, capturas, requisitos, configuración, arquitectura, trampas,
seguridad, contribuidores y pie— sacando cada dato de los archivos del
proyecto. No inventa: lo que no puede comprobar en un archivo, o te lo pregunta
o no lo escribe.

  * Un solo archivo y sólo la biblioteca estándar de Python 3.7+.
  * Sin IA y sin red: no consume tokens ni llama a ningún servicio.
  * Portable: se copia dentro del proyecto y se ejecuta desde ahí.
  * Enseña el plan y pregunta antes de escribir. Guarda copia de lo que
    cambia en .generate_readme/ y `deshacer` lo deja todo como estaba.

Uso:
    python3 generate_readme.py              (Windows: py generate_readme.py)
    python3 generate_readme.py detectar     qué datos encuentra y de dónde
    python3 generate_readme.py verificar    comprueba el README.md
    python3 generate_readme.py deshacer     vuelve atrás

Al volver a ejecutarlo, actualiza las secciones automáticas y respeta lo que
escribiste tú (las secciones marcadas como `manual` y todo lo que esté fuera
de las marcas `generate_readme`).
"""

from __future__ import annotations

import argparse
import base64
import difflib
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
from pathlib import Path
from urllib.parse import quote

VERSION = "1.0.0"
CARPETA_ESTADO = ".generate_readme"
DIR_IMG = "docs/img"
MARCA = "generate_readme"

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


class ErrorReadme(Exception):
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
    raise ErrorReadme("No encuentro ningún proyecto en %s ni en las carpetas de encima. Copia "
                      "generate_readme.py dentro de la carpeta de tu proyecto y ejecútalo desde ahí." % inicio)


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
        raise ErrorReadme("No hay nadie para responder a las preguntas, así que no se ha escrito nada. "
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
    HERRAMIENTAS_PROPIAS = {"generate_icon.py", "generate_readme.py"}

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


def _mezclar(a, b, f):
    a = [int(a[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(b[i:i + 2], 16) for i in (1, 3, 5)]
    return "#%02x%02x%02x" % tuple(int(round(x + (y - x) * f)) for x, y in zip(a, b))


def _ancho_texto(texto, tam):
    """Estimación del ancho de un texto en una sans-serif: suficiente para no salirse."""
    ancho = 0.0
    for c in texto:
        if c in "il.,:;|!'`":
            ancho += 0.28
        elif c in "mwMW@":
            ancho += 0.86
        elif c.isupper():
            ancho += 0.66
        elif c == " ":
            ancho += 0.28
        else:
            ancho += 0.55
    return ancho * tam


def construir_banner(nombre, frase, etiquetas, primario, oscuro, icono=None, logo=None):
    """SVG de 2400x640 con la composición del agente. Sin navegador: lo pinta GitHub."""
    W, H = 2400, 640
    if primario.startswith("__"):   # vista previa: los colores los pone la ventana
        acento, fondo3 = primario, oscuro
    else:
        acento = _mezclar(primario, "#ffffff", 0.35)
        fondo3 = _mezclar(oscuro, primario, 0.45)
    fuente = "system-ui, -apple-system, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif"
    p = []
    p.append('<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
             'viewBox="0 0 %d %d" width="%d" height="%d" role="img" aria-label="%s">' % (W, H, W, H, _xml(nombre)))
    p.append('<!-- Banner de %s, generado por generate_readme.py. Se rehace al volver a ejecutarlo. -->'
             % _xml(nombre).replace("--", "-"))
    p.append("""<defs>
  <linearGradient id="fondo" x1="0" y1="0" x2="1" y2="0.55">
    <stop offset="0" stop-color="#0b1220"/><stop offset="0.42" stop-color="%(oscuro)s"/>
    <stop offset="0.78" stop-color="%(fondo3)s"/><stop offset="1" stop-color="%(primario)s"/>
  </linearGradient>
  <radialGradient id="luz1" cx="0.86" cy="1.12" r="0.42"><stop offset="0" stop-color="%(acento)s" stop-opacity="0.34"/><stop offset="0.7" stop-color="%(acento)s" stop-opacity="0"/></radialGradient>
  <radialGradient id="luz2" cx="0.12" cy="-0.12" r="0.38"><stop offset="0" stop-color="%(primario)s" stop-opacity="0.46"/><stop offset="0.68" stop-color="%(primario)s" stop-opacity="0"/></radialGradient>
  <pattern id="reticula" width="80" height="80" patternUnits="userSpaceOnUse"><path d="M80 0H0V80" fill="none" stroke="#ffffff" stroke-opacity="0.055" stroke-width="2"/></pattern>
  <linearGradient id="desvanecer" x1="0" y1="0" x2="1" y2="0.2"><stop offset="0" stop-color="#ffffff" stop-opacity="0.95"/><stop offset="0.72" stop-color="#ffffff" stop-opacity="0"/></linearGradient>
  <mask id="mascara"><rect width="%(W)d" height="%(H)d" fill="url(#desvanecer)"/></mask>
  <linearGradient id="filo" x1="0" x2="1"><stop offset="0" stop-color="%(acento)s" stop-opacity="0"/><stop offset="0.35" stop-color="%(acento)s"/><stop offset="0.6" stop-color="#7dd3fc"/><stop offset="1" stop-color="#7dd3fc" stop-opacity="0"/></linearGradient>
  <clipPath id="esquinas"><rect width="%(W)d" height="%(H)d" rx="28"/></clipPath>
</defs>""" % dict(oscuro=oscuro, fondo3=fondo3, primario=primario, acento=acento, W=W, H=H))
    p.append('<g clip-path="url(#esquinas)">')
    p.append('<rect width="%d" height="%d" fill="url(#fondo)"/>' % (W, H))
    p.append('<rect width="%d" height="%d" fill="url(#luz1)"/><rect width="%d" height="%d" fill="url(#luz2)"/>' % (W, H, W, H))
    p.append('<rect width="%d" height="%d" fill="url(#reticula)" mask="url(#mascara)"/>' % (W, H))
    p.append('<rect width="%d" height="6" fill="url(#filo)"/>' % W)

    x = 112
    if icono is not None:
        uri = _data_uri(icono)
        if uri:
            lado = 240
            p.append('<image x="%d" y="%d" width="%d" height="%d" href="%s" xlink:href="%s"/>'
                     % (x, (H - lado) // 2, lado, lado, uri, uri))
            x += lado + 64

    derecha = W - 112
    if logo is not None:
        dim = _dimensiones(logo)
        uri = _data_uri(logo)
        if dim and uri and dim[0] > 0 and dim[1] > 0:
            alto = 152.0
            ancho = alto * dim[0] / dim[1]
            if ancho > 520:
                ancho, alto = 520.0, 520.0 * dim[1] / dim[0]
            pw, ph = ancho + 92, alto + 68
            px, py = W - 112 - pw, (H - ph) / 2
            p.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" rx="34" fill="#ffffff"/>' % (px, py, pw, ph))
            p.append('<image x="%.1f" y="%.1f" width="%.1f" height="%.1f" href="%s" xlink:href="%s" '
                     'preserveAspectRatio="xMidYMid meet"/>' % (px + 46, py + 34, ancho, alto, uri, uri))
            derecha = px - 72

    disponible = max(400.0, derecha - x)
    tam = 112.0
    while tam > 56 and _ancho_texto(nombre, tam) > disponible:
        tam -= 4
    lineas = [frase] if frase else []
    tam_f = 44.0
    if frase and _ancho_texto(frase, tam_f) > disponible:
        palabras, lineas, actual = frase.split(), [], ""
        for w in palabras:
            prueba = (actual + " " + w).strip()
            if _ancho_texto(prueba, tam_f) > disponible and actual:
                lineas.append(actual)
                actual = w
            else:
                actual = prueba
        lineas.append(actual)
        if len(lineas) > 2:
            lineas = lineas[:2]
            lineas[1] = lineas[1].rstrip(" .,;") + "…"
    alto_bloque = tam + 24 + len(lineas) * (tam_f * 1.3) + (40 + 64 if etiquetas else 0)
    y = (H - alto_bloque) / 2 + tam * 0.82
    p.append('<text x="%d" y="%.1f" fill="#ffffff" font-family="%s" font-size="%d" font-weight="800" '
             'letter-spacing="-1">%s</text>' % (x, y, fuente, tam, _xml(nombre)))
    y += 24
    for l in lineas:
        y += tam_f * 1.3
        p.append('<text x="%d" y="%.1f" fill="#ffffff" fill-opacity="0.8" font-family="%s" font-size="%d">%s</text>'
                 % (x, y, fuente, tam_f, _xml(l)))
    if etiquetas:
        y += 40
        cx = x
        for e in etiquetas[:4]:
            w = _ancho_texto(e, 30) + 56
            if cx + w > derecha:
                break
            p.append('<rect x="%.1f" y="%.1f" width="%.1f" height="64" rx="32" fill="#ffffff" fill-opacity="0.1" '
                     'stroke="#ffffff" stroke-opacity="0.25" stroke-width="2"/>' % (cx, y, w))
            p.append('<text x="%.1f" y="%.1f" fill="#ffffff" font-family="%s" font-size="30" font-weight="600" '
                     'text-anchor="middle">%s</text>' % (cx + w / 2, y + 43, fuente, _xml(e)))
            cx += w + 20
    p.append("</g></svg>")
    return "\n".join(p) + "\n"


# ===========================================================================
#  El README: secciones con marcas para poder rehacerlas sin pisar lo tuyo
# ===========================================================================

ORDEN_SECCIONES = ["cabecera", "frase", "indice", "que-hace", "pantallas", "capturas-origen", "requisitos",
                   "instalacion", "configuracion", "arquitectura", "desarrollo", "trampas", "documentacion",
                   "seguridad", "contribuidores", "pie"]
MANUALES = {"frase", "que-hace", "capturas-origen", "trampas"}

_RE_BLOQUE = re.compile(r"<!-- %s:(auto|manual) ([a-z-]+) -->\n?(.*?)<!-- %s:fin \2 -->\n?" % (MARCA, MARCA), re.S)


def _bloque(nombre, contenido):
    tipo = "manual" if nombre in MANUALES else "auto"
    return "<!-- %s:%s %s -->\n%s\n<!-- %s:fin %s -->\n" % (MARCA, tipo, nombre, contenido.strip("\n"), MARCA, nombre)


def ancla_github(titulo):
    """Cómo construye GitHub el ancla de un título: minúsculas, sin signos, espacios a guiones."""
    t = re.sub(r"<[^>]+>", "", titulo).strip().lower()
    t = "".join(c for c in t if c.isalnum() or c in " -_")
    return t.replace(" ", "-")


def _escudo(etiqueta, mensaje, color, logo=None):
    def esc(s):
        return quote(str(s).replace("-", "--").replace("_", "__"), safe="")
    url = "https://img.shields.io/badge/%s-%s-%s?style=for-the-badge" % (esc(etiqueta), esc(mensaje), color.lstrip("#").upper())
    if logo:
        url += "&logo=%s&logoColor=white" % logo
    return "![%s](%s)" % (etiqueta, url)


class Respuestas:
    """Lo que no se puede sacar de los archivos y se pregunta (o se deja fuera)."""

    def __init__(self):
        self.nombre = ""
        self.frase = ""
        self.que_hace = ""
        self.capacidades = []
        self.uso_interno = False
        self.usuarios = {}       # nombre → usuario de GitHub
        self.trampas = []        # [(título, cuerpo, archivo, línea)]
        self.origen_capturas = ""
        self.colores = None      # (primario, oscuro) elegidos a mano, si no son los del proyecto
        self.empresa = None      # la del pie; "" = ninguna; None = la detectada
        self.rehacer_manuales = set()   # secciones «manual» guardadas con texto de serie: se vuelven a escribir


def secciones(p, r, previos):
    """{nombre: contenido} de cada sección que aplica. Lo que no aplica, no está."""
    s = {}
    primario, oscuro = p.colores()
    tecnologias = p.tecnologias()
    version = p.version()
    licencia = p.licencia()
    empresa = p.empresa().valor
    remoto = p.remoto().valor

    # ---- cabecera
    escudos = []
    vacio = {"lenguaje": "lenguaje", "framework": "framework", "base": "base de datos"}
    for nombre_t, ver, _f, logo, rol in tecnologias:
        if rol == "lenguaje" and len(escudos) < 1:
            escudos.append(_escudo(nombre_t, ver or vacio[rol], primario.valor, logo))
    for nombre_t, ver, _f, logo, rol in tecnologias:
        if rol == "framework" and len(escudos) < 2:
            escudos.append(_escudo(nombre_t, ver or vacio[rol], primario.valor, logo))
    for nombre_t, ver, _f, logo, rol in tecnologias:
        if rol == "base" and len(escudos) < 3:
            escudos.append(_escudo(nombre_t, ver or vacio[rol], oscuro.valor, logo))
    if version:
        escudos.append(_escudo("versión", version.valor, _mezclar(primario.valor, "#ffffff", 0.35)))
    if licencia:
        escudos.append(_escudo("licencia", licencia.valor, "#64748b"))
    elif r.uso_interno:
        escudos.append(_escudo("licencia", "uso interno", "#64748b"))
    datos = {}
    if r.colores:
        datos["colores"] = list(r.colores)
    if r.empresa is not None:
        datos["empresa"] = r.empresa
    if r.nombre:
        datos["nombre"] = r.nombre
    cab = (["<!-- %s:datos %s -->" % (MARCA, json.dumps(datos, ensure_ascii=True).replace("--", "-\\u002d"))]
           if datos else [])
    cab += ['<div align="center">', "",
           '<img src="%s/banner.svg" alt="%s" width="100%%">' % (DIR_IMG, _xml(r.nombre)), ""]
    if escudos:
        cab += ["", "\n".join(escudos[:5]), ""]
    cab.append("</div>")
    s["cabecera"] = "\n".join(cab)

    if r.frase:
        s["frase"] = '<div align="center">\n\n**%s**\n\n</div>' % r.frase.strip()

    # ---- qué hace (manual)
    if r.que_hace or r.capacidades:
        t = ["## Qué hace", ""]
        if r.que_hace:
            t += [r.que_hace.strip(), ""]
        if r.capacidades:
            filas = [(a.strip(), b.strip()) for a, _, b in (c.partition(":") for c in r.capacidades)]
            if any(b for _a, b in filas):
                t += ["| Qué puedes hacer | Cómo |", "|---|---|"]
                t += ["| **%s** | %s |" % (_md_celda(a), _md_celda(b) or "—") for a, b in filas]
            else:
                t += ["| Qué puedes hacer |", "|---|"]
                t += ["| %s |" % _md_celda(a) for a, _b in filas]
        s["que-hace"] = "\n".join(t)

    # ---- pantallas
    pantallas, temas = p.capturas()
    if pantallas or temas:
        t = ["## Pantallas", ""]
        for f in pantallas:
            titulo = re.sub(r"^pantalla[-_ ]*", "", f.stem).replace("-", " ").replace("_", " ").strip().capitalize() or "Pantalla"
            t += ['<p align="center"><img src="%s" alt="%s" width="100%%"></p>' % (_rel(p.raiz, f), _xml(titulo)),
                  '<p align="center"><sub>%s</sub></p>' % _xml(titulo), ""]
        if temas:
            t += ["<table>", "<tr>",
                  '<td align="center" width="50%%"><img src="%s" alt="Tema claro"><br><sub>Tema claro</sub></td>' % _rel(p.raiz, temas[0]),
                  '<td align="center" width="50%%"><img src="%s" alt="Tema oscuro"><br><sub>Tema oscuro</sub></td>' % _rel(p.raiz, temas[1]),
                  "</tr>", "</table>"]
        s["pantallas"] = "\n".join(t)
        if r.origen_capturas:
            s["capturas-origen"] = "> %s" % r.origen_capturas.strip()

    # ---- requisitos
    filas = []
    para_que = {"lenguaje": "Lenguaje", "framework": "Framework", "base": "Base de datos",
                "herramienta": "Compilar los estilos y scripts"}
    for nombre_t, ver, fuente, _logo, rol in tecnologias:
        if rol == "base":
            filas.append((nombre_t, ver or "sin versión fijada", para_que[rol]))
        else:
            filas.append((nombre_t, ver.replace("+", " o superior") if ver else "sin versión fijada", para_que[rol]))
    exts = p.extensiones_php() if p.archivos_php() else []
    if exts:
        filas.append(("Extensiones de PHP", ", ".join("`%s`" % e for e, _f, _a in exts), "Las usa el código"))
    if filas:
        t = ["## Requisitos", "", "| Qué | Versión | Para qué |", "|---|---|---|"]
        t += ["| %s | %s | %s |" % (_md_celda(a), _md_celda(b), _md_celda(c)) for a, b, c in filas]
        if any(e == "odbc" for e, _f, _a in exts) and p.env.get("AS400_DRIVER"):
            t += ["", "> [!IMPORTANT]", "> Además de la extensión `odbc`, el equipo necesita el driver ODBC instalado: "
                  "`%s` (lo indica `AS400_DRIVER` en `%s`)." % (p.env["AS400_DRIVER"], _rel(p.raiz, p.env_ejemplo))]
        s["requisitos"] = "\n".join(t)

    # ---- instalación
    pasos = []
    if remoto:
        carpeta = remoto.rstrip("/").split("/")[-1]
        pasos += ["git clone %s" % remoto, "cd %s" % carpeta]
    if p.composer:
        pasos.append("composer install")
    if p.package:
        pasos.append("npm install")
    es_arranque = re.compile(r"(^|\s)(run|serve)(\s|$)|:run$")
    arranque = [x for x in p.ecosistema()["pasos"] if es_arranque.search(x)]
    for paso in p.ecosistema()["pasos"]:
        if paso not in pasos and paso not in arranque:
            pasos.append(paso)
    if p.env_ejemplo:
        pasos.append("cp %s .env" % _rel(p.raiz, p.env_ejemplo))
    if (p.raiz / "artisan").exists():
        pasos.append("php artisan key:generate")
    if pasos:
        t = ["## Instalación", "", "```bash"] + pasos + ["```"]
        if arranque:
            t += ["", "Para arrancarla:", "", "```bash"] + arranque + ["```"]
        if p.env_ejemplo:
            t += ["", "Después rellena el `.env` con los valores de verdad (ver [Configuración](#configuración))."]
        guia = p.guia_instalacion()
        if guia:
            t += ["", "La guía completa está en [`%s`](%s)." % (guia, guia)]
        s["instalacion"] = "\n".join(t)

    # ---- configuración
    bloques, aviso = p.variables()
    if bloques:
        t = ["## Configuración", "", "Todo se configura en el `.env` (plantilla: [`%s`](%s))." % (
            _rel(p.raiz, p.env_ejemplo), _rel(p.raiz, p.env_ejemplo)), ""]
        if p.gitignore_env():
            t += ["> [!WARNING]", "> El `.env` lleva credenciales y **no se versiona** (está en `.gitignore`). "
                  "No escribas valores reales en `%s`." % _rel(p.raiz, p.env_ejemplo), ""]
        secreto = re.compile(r"PASS|PWD|SECRET|TOKEN|KEY|USER|HOST|URL|DSN|IP|MAIL", re.I)
        for titulo, grupos in bloques:
            if not grupos:
                continue
            # Cada variable lleva su valor por defecto al lado: así nunca se desalinean
            t += ["**%s**" % titulo, "", "| Variable (por defecto) | Para qué |", "|---|---|"]
            for comentario, nombres, valores in grupos:
                celdas = []
                for n, v in zip(nombres, valores):
                    if v and not secreto.search(n) and not re.search(r"\d+\.\d+\.\d+\.\d+|://", v):
                        celdas.append("`%s` = `%s`" % (n, v.replace("|", "\\|")))
                    else:
                        celdas.append("`%s`" % n)
                desc = "\n".join(c for c in comentario).strip() or describir_variables(nombres)
                t.append("| %s | %s |" % ("<br>".join(celdas), _md_celda(desc) or "Propia del proyecto"))
            t.append("")
        s["configuracion"] = "\n".join(t).rstrip()

    # ---- arquitectura
    arbol = p.arbol()
    if arbol:
        t = ["## Arquitectura", "", "```text", arbol, "```"]
        pasos = p.recorrido()
        if pasos and any(frase for _prof, _rel_, frase in pasos[1:]):
            t += ["", "### El recorrido de una petición", ""]
            for prof, rel, frase in pasos:
                t.append("%s- [`%s`](%s)%s" % ("  " * prof, rel, rel, (" — " + frase) if frase else ""))
        eps = p.endpoints()
        if eps:
            t += ["", "### Puntos de entrada", "", "| Método | Ruta | Archivo |", "|---|---|---|"]
            t += ["| %s | `%s` | `%s` |" % (_md_celda(a), _md_celda(b), _md_celda(c)) for a, b, c in eps]
        s["arquitectura"] = "\n".join(t)

    # ---- desarrollo (+ trampas, manual)
    ordenes = p.ordenes()
    interruptores = p.interruptores_desarrollo()
    hay_trampas = bool(r.trampas) or "trampas" in previos
    if ordenes or interruptores or hay_trampas:
        t = ["## Desarrollo", ""]
        if interruptores:
            t += ["Para trabajar sin tocar producción, en el `.env`:", "", "| Variable | Qué hace |", "|---|---|"]
            for nombres, valores, comentario in interruptores:
                t.append("| %s | %s |" % ("<br>".join("`%s`" % n for n in nombres), _md_celda("\n".join(comentario))))
            t.append("")
        if ordenes:
            t += ["| Orden | Qué ejecuta |", "|---|---|"]
            t += ["| `%s` | %s |" % (o, ("`%s`" % _md_celda(q)) if q else "—") for o, q, _f in ordenes]
        s["desarrollo"] = "\n".join(t).rstrip()
    if r.trampas:
        t = ["### Cosas que conviene saber antes de tocar el código", ""]
        for titulo, cuerpo, archivo, linea in r.trampas:
            t += ["<details>", "<summary><b>%s</b></summary>" % _xml(titulo), "", "<br>", "",
                  cuerpo.strip(), "", "Está en [`%s`](%s#L%d)." % (archivo, archivo, linea), "", "</details>", ""]
        s["trampas"] = "\n".join(t).rstrip()

    # ---- documentación
    docs = p.documentos()
    if docs:
        t = ["## Documentación", "", "| Documento | Qué es |", "|---|---|"]
        t += ["| [`%s`](%s) | %s |" % (rel, quote(rel), _md_celda(titulo)) for rel, titulo in docs]
        s["documentacion"] = "\n".join(t)

    # ---- seguridad
    seg = p.seguridad()
    if seg:
        t = ["## Seguridad", "", "Lo que el proyecto hace hoy, comprobado en sus archivos:", ""]
        t += ["- %s <sub>([`%s`](%s))</sub>" % (texto, f, f) for texto, f in seg]
        s["seguridad"] = "\n".join(t)

    # ---- contribuidores
    gente = p.contribuidores()
    if gente:
        t = ["## Contribuidores", "", "<table>", "<tr>"]
        for g in gente[:6]:
            usuario = r.usuarios.get(g["nombre"], g["usuario"])
            aporte = g["papel"]   # su papel si se conoce; nunca cuántos commits hizo
            t += ['<td align="center" width="260">']
            if usuario:
                t += ['<a href="https://github.com/%s">' % usuario,
                      '<img src="https://github.com/%s.png?size=200" width="100" alt="%s"><br>' % (usuario, _xml(g["nombre"])),
                      "<b>%s</b>" % _xml(g["nombre"]), "</a><br>", "<sub>@%s</sub><br>" % usuario]
            else:
                t += ["<b>%s</b>%s" % (_xml(g["nombre"]), "<br>" if aporte else "")]
            if aporte:
                t += ["<sub><i>%s</i></sub>" % _xml(aporte)]
            elif usuario:
                t[-1] = t[-1].replace("<br>", "")
            t += ["</td>"]
        t += ["</tr>", "</table>"]
        if len(gente) > 6:
            t += ["", "<sub>Y %d persona%s más en el historial de commits.</sub>" % (
                len(gente) - 6, "s" if len(gente) > 7 else "")]
        s["contribuidores"] = "\n".join(t)

    # ---- pie
    if r.empresa is not None:
        empresa = dict(empresa)
        if r.empresa:
            empresa["nombre"] = r.empresa
        else:
            empresa.pop("nombre", None)
    if empresa or version:
        t = ['<div align="center">', ""]
        quien = empresa.get("nombre") or r.nombre
        if empresa.get("logo"):
            t += ['<img src="%s" alt="%s" height="56">' % (empresa["logo"], _xml(quien)), ""]
        t.append("**%s**" % (("[%s](%s)" % (quien, empresa["web"])) if empresa.get("web") else quien))
        t.append("")
        partes = []
        if empresa.get("soporte"):
            partes.append("Soporte: [%s](mailto:%s)" % (empresa["soporte"], empresa["soporte"]))
        if version:
            partes.append("Versión %s" % version.valor)
        if partes:
            t += ["<sub>%s</sub>" % " · ".join(partes), ""]
        t.append("</div>")
        s["pie"] = "\n".join(t)
    return s


def _indice(texto):
    sin_details = re.sub(r"<details>.*?</details>", "", texto, flags=re.S)
    sin_codigo = re.sub(r"```.*?```", "", sin_details, flags=re.S)
    titulos = re.findall(r"^## (.+)$", sin_codigo, re.M)
    if len(titulos) < 3:
        return ""
    return '<div align="center">\n\n%s\n\n</div>' % " · ".join("[%s](#%s)" % (t.strip(), ancla_github(t)) for t in titulos)


def componer_readme(p, r, actual, rehacer=False, anadir=()):
    """Devuelve (texto nuevo, informe). Respeta los bloques manuales y lo escrito fuera de las marcas."""
    previos = {m.group(2): m for m in _RE_BLOQUE.finditer(actual or "")}
    nuevas = secciones(p, r, previos)
    informe = {"nuevas": [], "omitidas": [n for n in ORDEN_SECCIONES if n not in nuevas and n not in ("indice",)]}
    if previos and not rehacer:
        texto = actual
        for nombre, m in sorted(previos.items(), key=lambda kv: -kv[1].start()):
            if m.group(1) == "manual" and nombre in r.rehacer_manuales:
                nuevo = _bloque(nombre, nuevas[nombre]) if nombre in nuevas else ""
                texto = texto[:m.start()] + nuevo + texto[m.end():]
                continue
            if m.group(1) == "manual":
                continue
            if nombre == "indice":
                continue
            if nombre in nuevas:
                texto = texto[:m.start()] + _bloque(nombre, nuevas[nombre]) + texto[m.end():]
            else:
                texto = texto[:m.start()] + texto[m.end():]
        # Nuevas de verdad: ni con marcas ni con su título ya escrito (alguien
        # pudo quitarle las marcas a una sección para quedársela)
        titulos = set(re.findall(r"^##+ (.+?)\s*$", texto, re.M))
        informe["nuevas"] = [n for n in nuevas if n not in previos and n not in MANUALES and n not in anadir
                             and not (re.match(r"#+ (.+)", nuevas[n]) and
                                      re.match(r"#+ (.+)", nuevas[n]).group(1).strip() in titulos)]
        # Una sección manual que antes no estaba (p. ej. la frase), o una que se acaba
        # de pedir (las capturas), se coloca en su sitio
        for n in [n for n in ORDEN_SECCIONES if n in nuevas and n not in previos and n not in r.rehacer_manuales
                  and (n in MANUALES or n in anadir)]:
            texto = _insertar_en_orden(texto, n, _bloque(n, nuevas[n]))
    else:
        partes = []
        for n in ORDEN_SECCIONES:
            if n in previos and previos[n].group(1) == "manual" and n not in r.rehacer_manuales:
                partes.append(previos[n].group(0).rstrip("\n") + "\n")
            elif n == "indice":
                partes.append(_bloque("indice", "(índice)"))
            elif n in nuevas:
                partes.append(_bloque(n, nuevas[n]))
        texto = "\n".join(partes)
    indice = _indice(texto)
    m = re.search(r"<!-- %s:auto indice -->\n?.*?<!-- %s:fin indice -->\n?" % (MARCA, MARCA), texto, re.S)
    if m:
        texto = texto[:m.start()] + (_bloque("indice", indice) if indice else "") + texto[m.end():]
    texto = re.sub(r"\n{3,}", "\n\n", texto).strip() + "\n"
    return texto, informe


def _insertar_en_orden(texto, nombre, bloque):
    pos = ORDEN_SECCIONES.index(nombre)
    for anterior in reversed(ORDEN_SECCIONES[:pos]):
        m = re.search(r"<!-- %s:fin %s -->\n?" % (MARCA, re.escape(anterior)), texto)
        if m:
            return texto[:m.end()] + "\n" + bloque + texto[m.end():]
    return bloque + "\n" + texto


# ===========================================================================
#  Verificación (el apartado 10 del agente)
# ===========================================================================


def verificar_readme(raiz, texto=None, silencioso=False):
    """Devuelve (fallos, avisos) como listas de textos."""
    ruta = raiz / "README.md"
    if texto is None:
        if not ruta.is_file():
            return ["No hay README.md en %s" % raiz], []
        texto = _texto(ruta)
    fallos, avisos = [], []
    sin_codigo = re.sub(r"```.*?```", "", texto, flags=re.S)
    for src in sorted(set(re.findall(r'src="([^"]+)"', sin_codigo))):
        if not re.match(r"https?://|data:", src) and not (raiz / src.split("#")[0]).exists():
            fallos.append("Imagen que no existe: %s" % src)
    for enlace in sorted(set(re.findall(r"\]\(([^)\s]+)\)", sin_codigo))):
        if re.match(r"https?://|#|mailto:", enlace):
            continue
        from urllib.parse import unquote
        if not (raiz / unquote(enlace.split("#")[0])).exists():
            fallos.append("Enlace a un archivo que no existe: %s" % enlace)
    for t in ("div", "table", "tr", "td", "a", "details", "summary", "p"):
        a = len(re.findall(r"<%s[ >]" % t, sin_codigo))
        c = len(re.findall(r"</%s>" % t, sin_codigo))
        if a != c:
            fallos.append("Etiqueta <%s>: %d abiertas y %d cerradas" % (t, a, c))
    titulos = {ancla_github(t) for t in re.findall(r"^#{1,6} (.+)$", re.sub(r"```.*?```", "", texto, flags=re.S), re.M)}
    for ancla in sorted(set(re.findall(r"\]\(#([^)]+)\)", sin_codigo))):
        if ancla not in titulos:
            fallos.append("Ancla del índice que no lleva a ningún título: #%s" % ancla)
    d = raiz / DIR_IMG
    if d.is_dir():
        for f in sorted(d.iterdir()):
            if f.is_file() and f.name not in texto and not f.name.startswith("."):
                avisos.append("Imagen sin usar en %s/: %s" % (DIR_IMG, f.name))
    if re.search(r'\sstyle="', sin_codigo):
        avisos.append("Hay atributos style=\"…\": GitHub los borra.")
    for n, linea in enumerate(texto.splitlines(), 1):
        # Un secreto es un VALOR: «DB_PASSWORD» o la palabra «contraseña» no lo son
        sin_locales = re.sub(r"\b(?:127\.0\.0\.1|0\.0\.0\.0)\b", "", linea)
        if re.search(r"(?:password|passwd|pass|pwd|contraseña|clave|secret|token|api[_-]?key)\w*`?\s*(?:=|:)\s*`?"
                     r"[\"']?(?!\s|\||<|`?\s*$)[^\s\"'`|<>]{4,}", sin_locales, re.I) \
                or re.search(r"AKIA[0-9A-Z]{12}|-----BEGIN|\b\d{1,3}(?:\.\d{1,3}){3}\b", sin_locales):
            avisos.append("Posible secreto o IP en la línea %d: %s" % (n, linea.strip()[:90]))
    return fallos, avisos


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
        tmp = ruta.with_name(ruta.name + ".generate_readme.tmp")
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
        raise ErrorReadme("No hay nada que deshacer en %s." % raiz)
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
#  Órdenes
# ===========================================================================


def _elegir_trampas(p):
    candidatas = p.candidatas_trampa()
    if not candidatas:
        print("\nNo encontré comentarios en el código que expliquen trampas. La sección no se pone.")
        return []
    explicar("Cosas que conviene saber antes de tocar el código",
             "Avisos para quien vaya a modificar el proyecto: algo que falla de forma rara y cuesta horas descubrir. "
             "No se inventan: se eligen entre comentarios que ya escribió alguien en el código, y van al README "
             "copiados tal cual, en plegables. Elige 2 a 4, o ninguno.",
             "un comentario que explica por qué un texto con tildes deja el JSON vacío")
    print()
    for i, (rel, linea, cuerpo) in enumerate(candidatas, 1):
        primera = " ".join(cuerpo.split())[:96]
        print("  %2d. %s:%d\n      %s…" % (i, rel, linea, primera))
    while True:
        r = _preguntar("\nNúmeros separados por comas (2 a 4 es lo ideal), o Enter para ninguno", "")
        fuera = [n for n in re.findall(r"\d+", r or "") if not 1 <= int(n) <= len(candidatas)]
        if not fuera:
            break
        print("  No hay ninguna con el número %s: elige entre 1 y %d." % (", ".join(fuera), len(candidatas)))
    elegidas = []
    for n in re.findall(r"\d+", r or ""):
        k = int(n)
        if 1 <= k <= len(candidatas) and candidatas[k - 1] not in [e[1:] for e in elegidas]:
            rel, linea, cuerpo = candidatas[k - 1]
            sugerido = re.split(r"(?<=[.:])\s", " ".join(cuerpo.split()), maxsplit=1)[0].rstrip(".:")[:80]
            print("   Título del plegable de %s:%d: el síntoma que vería alguien, en una línea" % (rel, linea))
            print("   (p. ej. «El JSON llega vacío si un texto trae tildes»).")
            titulo = _preguntar("   Título", sugerido)
            elegidas.append((titulo, rel, linea, cuerpo))
    return [(t, c, rel, l) for t, rel, l, c in elegidas]


_RE_USUARIO = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9]|-(?=[A-Za-z0-9])){0,38}$")


def _usuario_github(texto):
    """'@ana', 'ana' o 'https://github.com/ana' → 'ana'. None si no es un usuario válido."""
    t = texto.strip().strip("<>").rstrip("/")
    m = re.match(r"(?:https?://)?(?:www\.)?github\.com/([^/?#\s]+)", t, re.I)
    if m:
        t = m.group(1)
    t = t.lstrip("@")
    return t if _RE_USUARIO.match(t) else None


def _pedir_usuarios(nombres):
    """{nombre: usuario} preguntando una vez. Con varias personas, explica el formato con sus nombres."""
    explicar("Usuarios de GitHub",
             "El usuario de GitHub de cada persona que ha hecho cambios en el proyecto, para poner su foto en "
             "«Contribuidores». Es lo que va detrás de github.com/ en su perfil, sin @.",
             "«anaruiz» (de https://github.com/anaruiz)")
    if len(nombres) == 1:
        while True:
            parece = nombres[0] if _RE_USUARIO.match(nombres[0]) else ""
            r = _preguntar("   Usuario de GitHub de %s (sin @; %s)" % (
                nombres[0], "Enter si es ése; «-» si no tiene" if parece else "Enter si no tiene o no lo sabes"), parece)
            if r and r.strip() == "-":
                return {}
            if not r:
                return {}
            u = _usuario_github(r)
            if u:
                return {nombres[0]: u}
            print("  «%s» no es un usuario de GitHub válido: solo letras, números y guiones." % r)
    print("Han hecho commits estas %d personas:\n" % len(nombres))
    for i, n in enumerate(nombres, 1):
        print("  %d. %s" % (i, n))
    # Los nombres de git sin espacios suelen ser ya el usuario de GitHub: se proponen
    parecen = [n if _RE_USUARIO.match(n) else "" for n in nombres]
    propuesta = ", ".join(parecen).rstrip(", ") if any(parecen) else ""
    if propuesta:
        print("\nAlgunos nombres en git ya parecen usuarios de GitHub. Te los propongo: pulsa Enter para")
        print("usarlos tal cual (mira que coincidan), o escribe la línea entera tú:")
    print("\nEscribe sus usuarios EN ESE MISMO ORDEN, separados por comas (sin @ ni paréntesis).")
    print("Si alguien no tiene cuenta o no lo sabes, deja su hueco vacío entre dos comas.")
    print("Ejemplo: «usuario1, , usuario3» = %s es usuario1, %s se queda sin avatar%s."
          % (nombres[0], nombres[1], (", %s es usuario3" % nombres[2]) if len(nombres) > 2 else ""))
    print("También vale pegar el enlace del perfil (https://github.com/usuario).%s"
          % ("" if propuesta else " Enter vacío = ninguno."))
    while True:
        r = _preguntar("Usuarios", propuesta)
        if r and r.strip() == "-":
            return {}
        if not r:
            return {}
        partes = [x.strip() for x in re.split(r"[,;]", r)]
        if len(partes) > len(nombres):
            print("  Has escrito %d y son %d personas. Uno por persona, separados por comas." % (len(partes), len(nombres)))
            continue
        malos = [x for x in partes if x and not _usuario_github(x)]
        if malos:
            print("  No son usuarios de GitHub válidos: %s (solo letras, números y guiones)." % ", ".join(malos))
            continue
        asignados = {n: _usuario_github(x) for n, x in zip(nombres, partes) if x}
        for n in nombres:
            print("    %-28s → %s" % (n, ("@" + asignados[n]) if n in asignados else "sin avatar"))
        if _si_no("  ¿Está bien así?", True):
            return asignados


def _respuestas_previas(actual):
    """Lo ya contestado en una ejecución anterior queda en el README: no se vuelve a preguntar."""
    previos = {m.group(2): m.group(3) for m in _RE_BLOQUE.finditer(actual or "")}
    usuarios = {}
    for m in re.finditer(r'github\.com/([A-Za-z0-9-]+)\.png\?size=200" width="100" alt="([^"]+)"', actual or ""):
        usuarios[m.group(2).replace("&amp;", "&")] = m.group(1)
    uso_interno = "uso%20interno" in (actual or "")
    datos = {}
    m = re.search(r"<!-- %s:datos (\{.*?\}) -->" % MARCA, actual or "")
    if m:
        try:
            datos = json.loads(m.group(1))
        except ValueError:
            datos = {}
    # Un README hecho antes de que se guardara el nombre: el del banner
    if not datos.get("nombre"):
        m = re.search(r'<img src="%s/banner\.svg" alt="([^"]+)"' % re.escape(DIR_IMG), actual or "")
        if m:
            datos["nombre"] = m.group(1).replace("&amp;", "&").replace("&quot;", '"')
    return previos, usuarios, uso_interno, datos


def elegir_colores(p, a, r, interactivo, datos_previos):
    """Los colores del banner y los distintivos: los del proyecto, confirmados; si no, se eligen en una ventana."""
    detectados = p.colores()
    if a.primario or a.oscuro:
        pr = _a_hex(a.primario) if a.primario else detectados[0].valor
        os_ = _a_hex(a.oscuro) if a.oscuro else detectados[1].valor
        if not pr or not os_:
            raise ErrorReadme("--primario y --oscuro esperan un color, por ejemplo #7c3aed.")
        r.colores = (pr, os_)
        p._colores = (Dato(pr, "indicado"), Dato(os_, "indicado"))
        return
    det = dict(getattr(p, "paleta", None) or paleta_del_proyecto(p.raiz))
    previos = datos_previos.get("colores") if isinstance(datos_previos.get("colores"), list) else None
    if previos and len(previos) == 2 and all(_a_hex(c) for c in previos):
        # Los que se eligieron a mano la otra vez mandan sobre los detectados
        det["primario"] = (_a_hex(previos[0]), "", "elegido a mano en una ejecución anterior")
        det["oscuro"] = (_a_hex(previos[1]), "", "elegido a mano en una ejecución anterior")
        det["supuesto"] = False
        r.colores = (det["primario"][0], det["oscuro"][0])
    if not interactivo:
        if det["supuesto"]:
            print("  [aviso] No encontré los colores del proyecto: el banner sale en gris. Usa --primario y --oscuro.")
        if r.colores:
            p._colores = (Dato(r.colores[0], "elegido a mano"), Dato(r.colores[1], "elegido a mano"))
        return
    etiquetas = [t[0] for t in p.tecnologias()][:4]
    logo = p.empresa().valor.get("logo")
    banner = construir_banner(r.nombre, r.frase, etiquetas, "__P__", "__O__", icono=p.icono(),
                              logo=(p.raiz / logo) if logo else None)
    vista = banner.replace('width="2400" height="640"', 'width="100%"', 1)
    principal, oscuro, a_mano = confirmar_colores(
        det, "Colores del README · %s" % r.nombre, vista,
        "El del degradado del banner y los distintivos de tecnología.",
        "El fondo del banner y el distintivo de la base de datos.", sin_ventana=getattr(a, "sin_ventana", False))
    if a_mano or r.colores:
        r.colores = (principal, oscuro)
        p._colores = (Dato(principal, "elegido a mano"), Dato(oscuro, "elegido a mano"))


def _manuales_de_serie(p, previos):
    """Secciones «manual» ya guardadas que en realidad tienen texto de serie de un framework.

    Pasa si se aceptó una propuesta antes de que la herramienta supiera reconocerlo
    («The CodeIgniter framework v4», una trampa sacada de la configuración de serie…).
    """
    malas = {}
    for nombre in ("frase", "que-hace"):
        if nombre in previos:
            texto = re.sub(r"<[^>]+>|^#+ .*$|[*|]", " ", previos[nombre], flags=re.M)
            texto = " ".join(texto.split())
            if texto and _de_serie_frase(texto):
                malas[nombre] = "«%s» es la descripción de serie del framework" % texto[:60]
    if "trampas" in previos:
        ajenas = []
        for rel in re.findall(r"Está en \[`([^`]+)`\]", previos["trampas"]):
            ruta = p.raiz / rel
            partes = list(Path(rel).parts[:-1])
            de_serie = rel.startswith(("app/Config/", "config/")) and (
                (p.raiz / "artisan").is_file() or (p.raiz / "spark").is_file()
                or (p.raiz / "system" / "CodeIgniter.php").is_file())
            ajena = any(_es_de_terceros(p.raiz.joinpath(*partes[:i]), partes[i]) for i in range(len(partes)))
            if de_serie or ajena or not ruta.is_file():
                ajenas.append(rel)
        if ajenas:
            malas["trampas"] = "salen de documentación o librerías de serie (%s)" % ", ".join(dict.fromkeys(ajenas))
    return malas


def recoger_respuestas(p, a, interactivo, actual):
    previos, usuarios_previos, uso_previo, datos_previos = _respuestas_previas(actual)
    r = Respuestas()
    for nombre, porque in _manuales_de_serie(p, previos).items():
        titulo = {"frase": "la frase de debajo del banner", "que-hace": "«Qué hace»",
                  "trampas": "«Cosas que conviene saber»"}[nombre]
        if interactivo:
            print("\nLo guardado en %s no es del proyecto: %s." % (titulo, porque))
            if _si_no("¿Lo vuelvo a preguntar? (si no, se queda como está)", True):
                r.rehacer_manuales.add(nombre)
                del previos[nombre]
        else:
            print("  [aviso] Lo guardado en %s no es del proyecto: %s. Vuelve a ejecutarlo sin --si para rehacerlo."
                  % (titulo, porque))
    r.usuarios = dict(usuarios_previos)

    # ---- Nombre: se pregunta siempre. Sólo se propone si sale de una fuente fiable del
    # proyecto; el nombre de la carpeta no lo es («gestion-asistencia-prueba», «src»…).
    nombre = p.nombre()
    if isinstance(datos_previos.get("nombre"), str) and datos_previos["nombre"].strip():
        nombre = Dato(datos_previos["nombre"].strip(), "el README actual (lo escribiste tú)")
    r.nombre = a.nombre or nombre.valor
    if interactivo and not a.nombre:
        explicar("Nombre de la aplicación",
                 "El nombre con el que la gente conoce la aplicación. Sale en el banner, en el título y en el pie.",
                 "«Control de Inventario», «PanitasPet», «Gestión de Asistencia»")
        if nombre.valor:
            print("   En %s aparece «%s». Pulsa Enter para usarlo o escribe otro." % (nombre.fuente, nombre.valor))
        r.nombre = _preguntar_obligatorio("   Nombre", nombre.valor or None)
    elif not r.nombre:
        raise ErrorReadme("No encontré el nombre de la aplicación en ningún archivo del proyecto. Indícalo con "
                          "--nombre \"Mi aplicación\" (el de la carpeta no se usa: no tiene por qué ser el nombre).")

    if "frase" not in previos:
        frase = p.frase()
        r.frase = a.frase or frase.valor
        if interactivo and not a.frase:
            explicar("Qué es, en una línea",
                     "Una sola frase para quien no la conoce: qué es y para quién. Va debajo del banner.",
                     "«Gestión de pedidos de las sucursales, del registro a la entrega»")
            if frase.valor:
                print("   En %s pone «%s». Enter para usarla, o escribe otra." % (frase.fuente, frase.valor))
            r.frase = _preguntar("   Frase (Enter vacío = sin frase)", frase.valor or None) or ""
    else:
        m = re.search(r"\*\*(.+?)\*\*", previos["frase"])
        r.frase = m.group(1) if m else ""

    if interactivo and not (a.primario or a.oscuro):
        _PASO[0] += 1
        print("\n%d." % _PASO[0], end="")
    elegir_colores(p, a, r, interactivo, datos_previos)

    if "que-hace" not in previos:
        desc = p.descripcion()
        r.que_hace = desc.valor if desc.valor != r.frase else ""
        if interactivo:
            explicar("Qué hace: de dónde viene y qué resuelve",
                     "Un párrafo corto. «De dónde viene»: qué se usaba antes (un Excel, un programa antiguo, papel, "
                     "nada). «Qué resuelve»: qué le facilita ahora a quien la usa.",
                     "«Sustituye la hoja de Excel en la que cada sucursal anotaba sus pedidos. Ahora los registran "
                     "en un formulario y el almacén los ve todos en una lista, sin duplicados ni pedidos perdidos.»")
            if r.que_hace:
                print("   En %s pone: «%s». Enter para usarlo, o escribe el tuyo." % (desc.fuente, r.que_hace))
            r.que_hace = _preguntar("   Párrafo (Enter vacío = no poner esta sección)", r.que_hace or None) or ""
            explicar("Qué se puede hacer con ella",
                     "Las tareas principales, una por línea, con el formato «Qué: cómo o dónde». Enter vacío para "
                     "terminar (o para no poner ninguna).",
                     "«Registrar pedidos: desde el formulario de cada sucursal»  ·  "
                     "«Consultar entregas: por fecha o por cliente»")
            while True:
                c = _preguntar("   Capacidad", "")
                if not c:
                    break
                r.capacidades.append(c)

    if not p.licencia():
        r.uso_interno = uso_previo or a.uso_interno
        if interactivo and not uso_previo and not a.uso_interno:
            explicar("¿Uso interno?",
                     "El proyecto no tiene archivo de licencia. Si la aplicación es sólo para la empresa o la "
                     "institución (no se reparte ni se publica para que otros la usen), el README lo dice con un "
                     "distintivo «uso interno». Si es software libre, mejor añade un archivo LICENSE.",
                     None)
            r.uso_interno = _si_no("   ¿Es de uso interno?", False)

    # La empresa u organización del pie: se pregunta una vez y queda guardada en el README
    if isinstance(datos_previos.get("empresa"), str):
        r.empresa = datos_previos["empresa"]
    elif interactivo:
        detectada = p.empresa().valor.get("nombre", "")
        explicar("Empresa u organización",
                 "Quién es el dueño de la aplicación. Va en el pie del README, junto al logotipo. Escribe «-» si no "
                 "quieres poner ninguna: entonces el pie lleva el nombre de la aplicación.",
                 "«Industrias RRC, C.A.», «Universidad Monteávila», «Departamento de Sistemas»")
        if detectada:
            print("   En %s aparece «%s». Enter para usarla." % (p.empresa().fuente, detectada))
        resp = _preguntar("   Empresa", detectada or None)
        r.empresa = "" if (resp or "").strip() in ("", "-") else resp.strip()

    faltan = [g["nombre"] for g in p.contribuidores() if not g["usuario"] and g["nombre"] not in r.usuarios]
    if interactivo and faltan:
        r.usuarios.update(_pedir_usuarios(faltan))

    if interactivo and "trampas" not in previos:
        r.trampas = _elegir_trampas(p)

    return r


def orden_generar(a):
    interactivo = not a.si
    raiz = Path(a.proyecto).resolve() if a.proyecto else raiz_del_proyecto()
    p = Proyecto(raiz)
    print("Proyecto: %s" % p.raiz)
    if interactivo and not a.proyecto:
        print("(Si no es éste, no pasa nada: al final te pregunta antes de escribir.)")
    ruta = p.raiz / "README.md"
    actual = _texto(ruta) if ruta.is_file() else ""
    tiene_marcas = bool(_RE_BLOQUE.search(actual))
    contenido_real = len([l for l in actual.splitlines() if l.strip()]) > 3
    if actual and not tiene_marcas and contenido_real and not a.sobrescribir:
        print("\nEl README.md actual tiene contenido escrito a mano (%d líneas)." % len(actual.splitlines()))
        if not interactivo or not _si_no("¿Sustituirlo por el nuevo? Se guarda copia y se puede deshacer", False):
            raise ErrorReadme("No se toca el README actual. Para sustituirlo, añade --sobrescribir "
                              "(queda copia en %s/ y se puede deshacer)." % CARPETA_ESTADO)
    if a.rehacer and tiene_marcas:
        fuera = _RE_BLOQUE.sub("", actual).strip()
        aviso = ("--rehacer compone el README desde cero: conserva las secciones «manual», pero se pierde "
                 "lo escrito fuera de las marcas%s (queda copia y se puede deshacer)."
                 % (" (%d líneas)" % len(fuera.splitlines()) if fuera else ""))
        print("\n" + aviso)
        if fuera and (not interactivo or not _si_no("¿Seguir?", False)):
            raise ErrorReadme("No se ha escrito nada. " + ("" if interactivo else aviso))
    print()
    r = recoger_respuestas(p, a, interactivo, actual)

    previos_txt = {m.group(2) for m in _RE_BLOQUE.finditer(actual)}
    pantallas, temas = p.capturas()
    if (pantallas or temas) and "capturas-origen" not in previos_txt and interactivo:
        explicar("De dónde salen las capturas",
                 "Una línea, debajo de las imágenes de %s/, que diga de dónde salieron: así nadie piensa que "
                 "son datos reales." % DIR_IMG,
                 "«Capturas de la versión de pruebas, con datos inventados»")
        r.origen_capturas = _preguntar("   Origen (Enter vacío = no decirlo)", "") or ""
    # Si se han añadido capturas a docs/img/, su sección entra sola en su sitio
    texto, informe = componer_readme(p, r, actual, a.rehacer, anadir=("pantallas", "capturas-origen"))

    primario, oscuro = p.colores()
    etiquetas = [t[0] for t in p.tecnologias()][:4]
    logo = p.empresa().valor.get("logo")
    banner = construir_banner(r.nombre, r.frase, etiquetas, primario.valor, oscuro.valor,
                              icono=p.icono(), logo=(p.raiz / logo) if logo else None)
    escrituras = [(p.raiz / DIR_IMG / "banner.svg", banner.encode("utf-8")), (ruta, texto.encode("utf-8"))]

    fallos, avisos = verificar_readme(p.raiz, texto)
    nuevos = {_rel(p.raiz, f) for f, d in escrituras if d is not None}
    fallos = [f for f in fallos if not any(n in f for n in nuevos)]  # se crean ahora mismo
    avisos = [x for x in avisos if not any(Path(n).name in x for n in nuevos)]
    print("\n— Plan —")
    for f, datos in escrituras:
        if datos is None:
            print("  - %-28s se borra: la sustituyen las capturas nuevas (con copia)" % _rel(p.raiz, f))
            continue
        marca = "+" if not f.exists() else ("=" if f.read_bytes() == datos else "~")
        print("  %s %-28s %s" % (marca, _rel(p.raiz, f), "%.1f KB" % (len(datos) / 1024)))
    secciones_txt = [m.group(2) for m in _RE_BLOQUE.finditer(texto)]
    print("\nSecciones: %s" % ", ".join(secciones_txt))
    omitidas = [n for n in informe["omitidas"] if n not in secciones_txt]
    if omitidas:
        print("No se ponen (no hay datos para ellas): %s" % ", ".join(omitidas))
    if informe["nuevas"]:
        print("Hay secciones nuevas que el README actual no tiene: %s. Para añadirlas: --rehacer"
              % ", ".join(informe["nuevas"]))
    for x in fallos:
        print("  [MAL]   " + x)
    for x in avisos:
        print("  [aviso] " + x)
    expuestos = p.expuestos_en_web()
    if expuestos:
        print("  [aviso] Estos archivos están en la carpeta pública y cualquiera puede abrirlos desde el navegador;")
        print("          parecen de depuración o pruebas. No se mencionan en el README, pero conviene quitarlos:")
        print("          " + ", ".join(expuestos[:8]) + (" y %d más" % (len(expuestos) - 8) if len(expuestos) > 8 else ""))
    print("\n  + nuevo   ~ cambia (con respaldo)   - se borra (con respaldo)   = sin cambios")
    if a.simulacro:
        print("\n(simulacro) No se ha escrito nada. Así quedaría el README:\n")
        print(texto)
        return 0
    if all((d is None and not f.exists()) or (d is not None and f.exists() and f.read_bytes() == d)
           for f, d in escrituras):
        print("\nTodo estaba ya al día. No hay nada que escribir.")
        return 0
    if interactivo:
        if actual and _si_no("\n¿Ver qué cambia en el README?", False):
            sys.stdout.writelines(difflib.unified_diff(actual.splitlines(True), texto.splitlines(True),
                                                       "a/README.md", "b/README.md"))
        if not _si_no("\n¿Escribir el README?", False):
            print("Cancelado. No se ha escrito nada.")
            return 1
    man = aplicar(p.raiz, escrituras)
    print("\nHecho: %d archivo(s) nuevo(s), %d cambiado(s), %d borrado(s)%s." % (
        len(man["creados"]), len(man["modificados"]), len(man["borrados"]),
        " con copia en %s/" % CARPETA_ESTADO if (man["modificados"] or man["borrados"]) else ""))
    print("Para dejarlo como estaba:  %s" % _llamada("deshacer"))
    pendientes = []
    if not pantallas and not temas:
        pendientes.append("Capturas: hazlas de la aplicación funcionando, con datos de muestra (nunca de clientes "
                          "reales), guárdalas en %s/ como pantalla-ALGO.png (y tema-claro.png / tema-oscuro.png "
                          "si tiene dos temas) y vuelve a ejecutarlo: las pone solo." % DIR_IMG)
    sin_usuario = [g["nombre"] for g in p.contribuidores() if not (g["usuario"] or r.usuarios.get(g["nombre"]))]
    if sin_usuario:
        pendientes.append("Sin usuario de GitHub (salen sin avatar): %s." % ", ".join(sin_usuario))
    if not r.trampas and "trampas" not in [m.group(2) for m in _RE_BLOQUE.finditer(actual)]:
        pendientes.append("Sin «Cosas que conviene saber»: vuelve a ejecutarlo y elige comentarios del código.")
    if pendientes:
        print("\nQueda por hacer a mano:")
        for x in pendientes:
            print("  · " + x)
    print("\nPuedes editar el README a mano: lo que esté fuera de las marcas generate_readme, y las secciones "
          "marcadas «manual», no se tocan al volver a ejecutarlo.")
    return 0


def orden_detectar(a):
    raiz = Path(a.proyecto).resolve() if a.proyecto else raiz_del_proyecto()
    p = Proyecto(raiz)
    n, f, v = p.nombre(), p.frase(), p.version()
    cp, co = p.colores()
    print("Proyecto:      %s" % p.raiz)
    print("Nombre:        %s  (de %s)" % (n.valor, n.fuente))
    print("Frase:         %s" % ("%s  (de %s)" % (f.valor, f.fuente) if f.valor else "— (se pregunta)"))
    print("Versión:       %s" % ("%s  (de %s)" % (v.valor, v.fuente) if v.valor else "—"))
    print("Colores:       %s (%s) → %s (%s)" % (cp.valor, cp.fuente, co.valor, co.fuente))
    print("Tecnología:")
    for nombre_t, ver, fuente, _l, rol in p.tecnologias():
        print("  · %-12s %-12s %s  (de %s)" % (nombre_t, ver or "—", rol, fuente))
    for e, func, archivo in (p.extensiones_php() if p.archivos_php() else []):
        print("  · ext-%-8s por %s en %s" % (e, func, archivo))
    e = p.empresa().valor
    print("Empresa:       %s · logo %s" % (e.get("nombre", "—"), e.get("logo", "—")))
    ic = p.icono()
    print("Icono:         %s" % (_rel(p.raiz, ic) if ic else "— (sin icono; el banner va sin él)"))
    pantallas, temas = p.capturas()
    print("Capturas:      %d%s" % (len(pantallas), " + pareja de temas" if temas else ""))
    bloques, _av = p.variables()
    print("Variables:     %d en %s" % (sum(len(n) for _t, g in bloques for _c, n, _v in g),
                                        _rel(p.raiz, p.env_ejemplo) if p.env_ejemplo else "— (no hay .env.example)"))
    print("Recorrido:     %s" % (" → ".join(r for _p, r, _f in p.recorrido()) or "—"))
    print("Documentos:    %s" % (", ".join(r for r, _t in p.documentos()) or "—"))
    print("Seguridad:     %d afirmaciones comprobadas" % len(p.seguridad()))
    gente = p.contribuidores()
    print("Contribuidores: %s" % (", ".join("%s%s" % (g["nombre"], " (@%s)" % g["usuario"] if g["usuario"] else "")
                                           for g in gente) or "—"))
    print("Trampas:       %d comentarios candidatos en el código" % len(p.candidatas_trampa()))
    return 0


def orden_verificar(a):
    raiz = Path(a.proyecto).resolve() if a.proyecto else raiz_del_proyecto()
    fallos, avisos = verificar_readme(raiz)
    for x in fallos:
        print("  [MAL]   " + x)
    for x in avisos:
        print("  [aviso] " + x)
    print("\n%s: %d fallo(s), %d aviso(s)." % ("BIEN" if not fallos else "HAY QUE CORREGIR", len(fallos), len(avisos)))
    print("Los avatares y distintivos (URL externas) míralos en GitHub: desde aquí no se comprueban.")
    return 1 if fallos else 0


def _opciones_colores(g):
    g.add_argument("--primario", help="color principal (si no, el del proyecto), p. ej. #7c3aed")
    g.add_argument("--oscuro", help="color oscuro (si no, el del proyecto), p. ej. #1e1b4b")
    g.add_argument("--sin-ventana", action="store_true",
                   help="si los colores no son esos, escribirlos en la terminal en vez de abrir la ventana")


def _argumentos():
    p = argparse.ArgumentParser(
        prog="generate_readme",
        description="Escribe el README de la aplicación con la portada de la casa, sacando los datos de "
                    "sus archivos. Sin IA ni red. Sin argumentos abre el asistente.")
    p.add_argument("--version", action="version", version="%(prog)s " + VERSION)
    s = p.add_subparsers(dest="orden", metavar="ORDEN")
    s.required = True
    g = s.add_parser("generar", help="escribe o actualiza el README (lo que hace sin argumentos)")
    g.add_argument("proyecto", nargs="?", help="carpeta del proyecto (por defecto, la encuentra sola)")
    g.add_argument("--si", action="store_true", help="no preguntar: usar sólo lo que se puede sacar de los archivos")
    g.add_argument("--simulacro", action="store_true", help="enseña el README sin escribir nada")
    g.add_argument("--nombre", help="nombre de la aplicación")
    g.add_argument("--frase", help="qué hace, en una línea")
    g.add_argument("--uso-interno", action="store_true", help="distintivo de licencia «uso interno»")
    g.add_argument("--rehacer", action="store_true", help="recomponer todas las secciones (respeta las manuales)")
    g.add_argument("--sobrescribir", action="store_true", help="sustituir un README escrito a mano (con copia)")
    _opciones_colores(g)
    g.set_defaults(fn=orden_generar)
    d = s.add_parser("detectar", help="enseña qué datos encuentra y de qué archivo, sin escribir nada")
    d.add_argument("proyecto", nargs="?")
    d.set_defaults(fn=orden_detectar)
    v = s.add_parser("verificar", help="comprueba el README.md (sale con código 1 si algo falla)")
    v.add_argument("proyecto", nargs="?")
    v.set_defaults(fn=orden_verificar)
    u = s.add_parser("deshacer", help="deja el README y el banner como estaban")
    u.add_argument("proyecto", nargs="?")
    u.add_argument("--forzar", action="store_true", help="restaurar aunque hayan cambiado después")
    u.set_defaults(fn=orden_deshacer)
    return p


def main(argv=None):
    _consola_segura()
    if sys.version_info < (3, 7):
        print("Hace falta Python 3.7 o superior.", file=sys.stderr)
        return 2
    args = list(sys.argv[1:] if argv is None else argv)
    if not args or args[0].startswith("--") and args[0] not in ("--help", "-h", "--version"):
        print("generate_readme %s · el README de tu aplicación, sin internet ni IA\n" % VERSION)
        args = ["generar"] + args
    a = _argumentos().parse_args(args)
    try:
        return a.fn(a)
    except ErrorReadme as e:
        print("Error: %s" % e, file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("\nCancelado.")
        return 130
    except BrokenPipeError:
        try:
            sys.stdout = open(os.devnull, "w")
        except OSError:
            pass
        return 1


if __name__ == "__main__":
    sys.exit(main())
