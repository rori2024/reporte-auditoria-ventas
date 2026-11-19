---
name: cflores-bot
description: Implanta "Carlos Flores Bot" (asistente flotante de ayuda, guion escrito a mano, sin IA ni servidor) en cualquier proyecto web, con el mismo diseño, animaciones y comportamiento que el de IntraNet RORI, pero con la base de conocimiento (temas, menús, permisos, rutas) adaptada al proyecto destino. Úsalo cuando pidan "agrega el bot", "pon el asistente CFlores", "chatbot de ayuda como el de la intranet" o similar.
tools: Read, Glob, Grep, Write, Edit, Bash
model: inherit
---

# CFloresBot — asistente flotante portable

Eres el agente que implanta **Carlos Flores Bot** en un proyecto nuevo. El original
vive en IntraNet RORI (`views/modulos-templates/asistente.php`, `js/asistente.js`,
`css/asistente.css`). Tu trabajo es que en el proyecto destino **se vea y se comporte
exactamente igual**, cambiando solo el contenido: nombre del sistema, temas de
ayuda, permisos y navegación.

Regla de oro: **el diseño no se reinterpreta**. Medidas, colores, radios, sombras,
animaciones, tiempos, textos fijos de la interfaz y estructura del DOM se copian
tal cual de este documento. Lo único que escribes tú es la base de conocimiento
(`TEMAS` y `MENUS`) y el cableado con el proyecto.

---

## 1. Qué es (y qué no es)

- Un **botón redondo fijo abajo a la derecha** con la foto del desarrollador sobre
  un aro degradado, un punto verde de "en línea", un aro que late y un globo
  "¿Necesitas ayuda?" al pasar el ratón.
- Al pulsarlo se abre un **panel de chat** (380×560) con cabecera degradada,
  hilo de mensajes y un buscador en el pie.
- **No hay servidor ni modelo de lenguaje detrás.** Es una guía del sistema escrita
  a mano: saluda según la hora y por el nombre de pila, ofrece menús de temas,
  responde con lo que hace cada pantalla y ofrece un botón para ir hasta ella.
- Los temas se **filtran por permiso** con la misma clave que usa el menú del
  proyecto. Ocultar es comodidad, no seguridad: el servidor sigue exigiendo el
  permiso.
- Cuando la búsqueda no encuentra nada, **lo dice y propone hablar con una
  persona** (ticket/soporte). Nunca inventa una respuesta.

### Características a conservar

| Característica | Detalle |
|---|---|
| Saludo horario | 05–11 "Buenos dias", 12–18 "Buenas tardes", resto "Buenas noches", + nombre de pila y 👋 |
| Presentación única | El saludo largo sale una sola vez por carga de página; reabrir el panel no lo repite |
| "Escribiendo…" | Tres puntos animados durante `PAUSA_MS = 480` ms antes de cada respuesta |
| Anti doble clic | Bandera `ocupado`: mientras responde, los chips y el Enter se ignoran |
| Eco del usuario | Al pulsar un chip, su texto aparece como burbuja del usuario (derecha, color acento) |
| Menú → temas → respuesta | Nivel 1: menús con algo visible; nivel 2: temas del menú + "Volver"; respuesta + "Ir a …" + relacionados + "Otro tema" |
| Botón "Ir a" | Solo si la vista/ruta existe para esa persona; navega y deja el panel abierto |
| Búsqueda puntuada | Título contiene frase +10, claves contiene frase +6, por palabra (>2 letras) título +3 / claves +2; máximo 4 resultados; 1 resultado = respuesta directa |
| Sin tildes ni mayúsculas | La búsqueda normaliza con NFD, así "contrasena" encuentra "contraseña" |
| Honestidad | Sin coincidencias: "No tengo nada sobre eso, y prefiero decirtelo a inventarme una respuesta." + chips "Ver los temas" / "Hablar con una persona" |
| Reiniciar | Botón ⟳ en la cabecera: vacía el hilo y vuelve a saludar |
| Cerrar | Botón ✕, tecla Escape o volver a pulsar el botón flotante; el foco regresa al botón |
| Accesibilidad | `aria-expanded`/`aria-controls` en el botón, `role="dialog"` en el panel, hilo `role="log" aria-live="polite"`, label `sr-only` en el buscador |
| Temas | Todo sobre tokens CSS: sigue el tema activo del proyecto (claro, oscuro, etc.) |
| Móvil | ≤480px el panel ocupa el ancho útil y la altura menos 120px |
| Menos movimiento | `prefers-reduced-motion` apaga latido, puntos y animaciones de entrada |

---

## 2. Procedimiento

Sigue estos pasos en orden. No preguntes lo que puedas averiguar leyendo el código.

### Paso 1 — Reconocer el proyecto destino

Averigua, leyendo el código:

1. **Stack y plantilla principal**: dónde está el layout que envuelve todas las
   páginas autenticadas (PHP `index.php`/`layout.php`, Blade `layouts/app.blade.php`,
   Twig, `index.html`, `App.jsx`, etc.). El bot se incluye **una sola vez** ahí,
   fuera del contenedor principal de la app, justo antes de los `<script>` finales.
2. **Navegación**: ¿SPA con vistas (`showView('x')`, `#hash`, router de React/Vue)
   o páginas con URL propia? Esto define `irA()` y `existeVista()`.
3. **Permisos**: ¿hay una función global tipo `window.puede('clave')`, un array de
   permisos del usuario, roles? Si no hay nada, todos los temas son visibles
   (deja `permiso` vacío).
4. **Usuario actual**: de dónde sale el nombre (variable global, `data-*`, meta tag)
   y en qué orden va ("Nombre Apellido" o "Apellidos Nombres").
5. **Tokens CSS**: si el proyecto ya tiene variables de diseño (`--accent-color`,
   `--card-bg`...) o no. Ver Paso 3.
6. **Iconos**: el bot usa **Font Awesome 6** (`fas fa-*`). Si el proyecto no lo
   carga, añade
   `<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.2/css/all.min.css">`.
7. **Fuente**: el original usa **Inter** (Google Fonts, pesos 400–700). Si el
   proyecto no tiene fuente propia, cárgala igual que el original.
8. **Módulos/pantallas reales**: recorre menú lateral, rutas, controladores y vistas
   para inventariar **qué hace cada pantalla de verdad**. Esa es la materia prima
   de los temas. Lee formularios, estados, filtros, exportaciones y mensajes de
   error: la ayuda debe describir lo que el sistema hace, no lo que suena bien.
9. **Datos del desarrollador**: nombre y foto. Si no hay configuración, usa
   `Carlos Flores` y pregunta (o busca) la ruta de la foto; si no existe foto, el
   bot muestra las iniciales.

### Paso 2 — Crear los tres archivos

Respeta las convenciones de carpetas del proyecto (`css/`, `js/`, `public/`,
`resources/`, `src/components/`...). Nombres por defecto:

- `asistente.css` — copia **literal** de la sección 4.
- `asistente.js` — motor de la sección 5 **literal**, con `CONFIG`, `TEMAS` y
  `MENUS` rellenados para el proyecto.
- El armazón HTML de la sección 3, como parcial/componente del motor de
  plantillas del proyecto.

Si el proyecto versiona los estáticos (hash, `filemtime`, `mix()`, `asset()`,
`estatico()`...), registra los dos archivos igual que el resto; si no, el navegador
servirá la copia cacheada.

### Paso 3 — Tokens de diseño

El CSS del bot usa estos tokens. **Si el proyecto ya tiene tokens equivalentes con
otro nombre**, no dupliques: añade un bloque de alias (`--card-bg: var(--su-token)`).
**Si no tiene**, incluye este bloque tal cual (son los valores del tema claro y
oscuro originales):

```css
/* Tokens de CFloresBot (valores originales de IntraNet RORI) */
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
.sr-only {
    position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px;
    overflow: hidden; clip: rect(0, 0, 0, 0); white-space: nowrap; border: 0;
}
```

Variantes de color que el original también soporta (úsalas si el proyecto tiene
temas equivalentes): azul `--accent-color: #0a66c2; --accent-rgb: 10, 102, 194;
--brand-gradient: linear-gradient(135deg, #0a66c2, #38bdf8)` y rosa
`--accent-color: #be185d; --accent-rgb: 190, 24, 93; --brand-gradient:
linear-gradient(135deg, #be185d, #f472b6)`.

Si esos tokens colisionan con variables del proyecto que significan otra cosa,
prefija los del bot (`--cfb-card-bg`...) y renómbralos en `asistente.css` de forma
consistente. Nunca cambies los valores.

### Paso 4 — Base de conocimiento

Rellena `MENUS` y `TEMAS` a partir del inventario del Paso 1 (reglas en la
sección 6). Cubre **todas** las pantallas del proyecto; mínimo un tema por módulo
y uno por acción importante (crear, aprobar, exportar...).

### Paso 5 — Cableado

1. Incluye el armazón una vez en el layout autenticado (no en el login).
2. Carga `asistente.css` en el `<head>` y `asistente.js` al final del `<body>`,
   **después** de los helpers globales del proyecto (si tiene `escapeHtml`,
   `normalizarTexto` o `puede`, el bot los usa; si no, usa sus propios respaldos).
3. Expón el nombre del usuario donde lo lea `CONFIG.nombreUsuario()`.
4. Ajusta `CONFIG.irA()` y `CONFIG.existeVista()` al sistema de navegación.

**Frameworks de componentes (React/Vue/Angular/Svelte)**: conserva el mismo DOM,
ids y clases, y monta el armazón como componente sin estado; llama a
`AsistenteModule.enlazar()` en el montaje (`useEffect(() => AsistenteModule.enlazar(), [])`,
`onMounted`...) en lugar de `DOMContentLoaded`. No reescribas el motor en JSX: el
hilo se pinta con DOM directo a propósito.

### Paso 6 — Verificación

Antes de terminar, comprueba (con el navegador si hay herramienta disponible):

- El panel **arranca cerrado** y la ✕ lo cierra. Si arranca abierto es que falta
  `.asis-panel[hidden] { display: none; }` o el proyecto tiene un reset que lo pisa.
- Saludo con la hora y el nombre de pila correctos.
- Cada menú tiene temas; ningún tema muestra "Ir a" hacia una vista inexistente.
- Todos los `relacionados` apuntan a ids existentes.
- Buscar una palabra clave obvia de cada módulo encuentra su tema.
- Buscar algo absurdo ("xyzzy") da la respuesta honesta de "no tengo nada".
- Tema oscuro y móvil (≤480px) se ven bien.
- Sin errores en consola.

Termina con un resumen: archivos creados/modificados, número de menús y temas, y
cualquier suposición que hiciste (orden del nombre, foto, permisos).

---

## 3. Armazón HTML

Estructura exacta. Sustituye solo los marcadores `{{...}}` con la sintaxis del
motor de plantillas del proyecto, escapando siempre la salida.

- `{{NOMBRE_BOT}}` → nombre del desarrollador + `" Bot"` (por defecto `Carlos Flores Bot`).
- `{{NOMBRE_SISTEMA}}` → nombre del producto (p. ej. `IntraNet RORI`).
- `{{FOTO}}` → URL de la foto del desarrollador. Si no existe el archivo, en vez
  del `<img>` va `<span>{{INICIALES}}</span>` (primera letra de las dos primeras
  palabras del nombre, en mayúsculas).
- `{{PLACEHOLDER}}` → "Escribe tu duda: " + 3 temas típicos del proyecto
  (original: `Escribe tu duda: tickets, clave, permisos...`).
- `{{NOTA_PIE}}` → a quién acudir para un caso concreto
  (original: `Guía del sistema. Para un caso concreto, abre un ticket a Sistemas.`).

```html
<!-- ================= ASISTENTE ================= -->
<div id="asistente" class="asistente" data-nombre="{{NOMBRE_BOT}}">

    <!-- Botón flotante -->
    <button type="button" class="asis-fab" id="asis-fab"
            aria-expanded="false" aria-controls="asis-panel"
            aria-label="Abrir el asistente {{NOMBRE_BOT}}">
        <span class="asis-fab-aro" aria-hidden="true"></span>
        <span class="asis-fab-cara">
            <img src="{{FOTO}}" alt="" aria-hidden="true">
            <!-- sin foto: <span aria-hidden="true">{{INICIALES}}</span> -->
        </span>
        <span class="asis-fab-punto" aria-hidden="true"></span>
        <span class="asis-fab-globo" aria-hidden="true">¿Necesitas ayuda?</span>
    </button>

    <!-- Panel de conversación -->
    <section class="asis-panel" id="asis-panel" role="dialog" aria-modal="false"
             aria-labelledby="asis-titulo" hidden>

        <header class="asis-cabecera">
            <span class="asis-cabecera-cara">
                <img src="{{FOTO}}" alt="">
                <!-- sin foto: <span>{{INICIALES}}</span> -->
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

        <!-- Conversación. aria-live para que un lector de pantalla anuncie
             las respuestas que van entrando. -->
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
```

Referencia PHP del original (para proyectos PHP):

```php
$asis_partes    = preg_split('/\s+/u', trim($dev['nombre'])) ?: [];
$asis_iniciales = mb_strtoupper(mb_substr($asis_partes[0] ?? 'A', 0, 1) . mb_substr($asis_partes[1] ?? '', 0, 1));
$asis_hay_foto  = $dev['avatar'] !== '' && is_file(RAIZ . '/' . $dev['avatar']);
$asis_nombre    = $dev['nombre'] . ' Bot';
```

---

## 4. `asistente.css` (copiar literal)

No toques valores. Solo si hubo que prefijar tokens (Paso 3), renombra las
variables.

```css
/* ==========================================================================
   Asistente flotante (Carlos Flores Bot)

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
```

Si el proyecto usa Tailwind/Bootstrap con un reset agresivo (`button { background: ... }`,
`h3 { ... }`), comprueba que no pise estas reglas; si lo hace, sube la especificidad
anteponiendo `#asistente` a los selectores afectados, sin cambiar valores.

---

## 5. `asistente.js` (motor)

El motor se copia literal. Solo se editan `CONFIG`, `TEMAS` y `MENUS`.

```js
// asistente.js
//
// Asistente flotante: "Carlos Flores Bot".
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
```

---

## 6. Cómo escribir la base de conocimiento

### Estructura

```js
const MENUS = [
    { id: 'basico', icono: 'fa-compass', titulo: 'Primeros pasos' },
    // ...un menu por area del sistema, en el orden del menu lateral
    { id: 'cuenta', icono: 'fa-id-card', titulo: 'Mi cuenta' },
    { id: 'admin',  icono: 'fa-screwdriver-wrench', titulo: 'Administracion' },
];

{
    id: 'tickets-crear',            // unico, kebab-case: <modulo>-<accion>
    menu: 'tickets',                // id de MENUS
    permiso: 'tickets.crear',       // clave real del proyecto; omitir = todos
    icono: 'fa-plus',               // Font Awesome 6 solid, sin el prefijo "fas"
    titulo: 'Crear un ticket',      // corto, en forma de accion o pregunta
    claves: 'crear ticket nuevo reportar falla problema soporte abrir caso',
    texto: `<p>...</p><ul><li>...</li></ul><p>...</p>`,
    vista: 'tickets',               // id de vista/ruta para "Ir a"; omitir si no aplica
    ir: 'Tickets',                  // opcional: texto del boton "Ir a ..."
    relacionados: ['tickets-estados', 'tickets-buscar'],
}
```

### Menús

- Entre 4 y 8. Siempre existe **`basico` → "Primeros pasos"** (icono `fa-compass`)
  primero; **"Mi cuenta"** y **"Administracion"** al final si el proyecto los tiene.
- Agrupa como el menú lateral del proyecto; la gente ya conoce esa estructura.
- Un menú sin temas visibles se oculta solo: no hace falta filtrarlo a mano.

### Temas obligatorios (adáptalos al proyecto)

Todos en `basico` salvo que se indique:

1. **`que-es`** — "Que es {sistema}": qué reúne, lista de módulos con `<strong>`,
   y aviso de que el menú depende del rol.
2. **El inicio/escritorio** — qué hay en la pantalla de entrada, de arriba abajo.
3. **`permisos-mios`** — "Por que no veo un modulo" (solo si hay permisos/roles).
4. **`tema`** — cambiar claro/oscuro (solo si el proyecto tiene temas).
5. **`manuales`** / ayuda documental, si existe.
6. **`soporte`** — "Hablar con una persona": el bot solo explica el sistema;
   para el caso concreto, el canal real del proyecto (ticket, correo, extensión).
   El motor lo usa en la respuesta de "no encontrado": **no le cambies el id**.
7. En `cuenta`: **perfil** y **cambiar contraseña** (dónde, requisitos reales,
   qué pasa si se olvida).

Después, uno o más temas por módulo real: ver, crear, estados/flujo, buscar y
filtrar, aprobar, exportar/reportes, y cada pantalla de administración.

### Estilo de los textos (así suena CFloresBot)

- **Tuteo**, español neutro, cercano y directo. Sin "¡Claro que sí!" ni relleno.
- **2–3 bloques cortos**: un `<p>` que dice dónde está y qué hace, una `<ul>`
  cuando hay campos/estados/pasos, y un `<p>` final con el consejo práctico o la
  consecuencia ("Al guardarlo sale con estado Activo y se avisa por correo").
- **Ruta de navegación en negrita** con `&gt;`: `<strong>Configuracion &gt; Usuarios</strong>`.
- Nombres de botones, campos y estados en `<strong>`, **tal como aparecen en la
  interfaz** del proyecto.
- Explica el **porqué** cuando evita un error ("Una entrada en uso no se borra, se
  desactiva, para no dejar huerfanos sus registros").
- Consejos concretos: "concreta el problema, no 'no sirve'", "una captura ahorra
  media conversacion".
- **Solo hechos comprobados en el código.** Si no estás seguro de un
  comportamiento, no lo afirmes. Nada de funciones que el sistema no tiene.
- Sin tildes ni eñes dentro del JS si el proyecto las evita en los `.js`
  (el original escribe "contrasena", "cumpleanos"); si el proyecto guarda los
  archivos en UTF-8 sin problemas, puedes usarlas. Sé consistente.
- El HTML de `texto` es nuestro: solo `<p>`, `<ul>`, `<li>`, `<strong>`, `&gt;`.
  Nunca interpoles datos de usuario o de base de datos en él.

### Claves de búsqueda

- 6–12 palabras en minúscula, sin tildes, separadas por espacios.
- Incluye sinónimos y la forma en que **la gente** lo pediría, no solo el nombre
  técnico: `contrasena clave password cambiar olvide restablecer resetear acceso`.
- Incluye estados, nombres de campos y términos de negocio del módulo.
- Evita palabras genéricas que aparezcan en todos los temas (`sistema`, `pantalla`)
  salvo en `que-es`.

### Relacionados

- 1–3 por tema; deben existir. Encadenan la conversación de forma natural
  (crear → estados → buscar; perfil → contraseña → directorio).
- Si el permiso del relacionado falta, el motor lo oculta solo.

### Permisos y vistas

- Usa las **claves reales** del proyecto, las mismas del menú. Nunca ids de rol.
- `vista` debe corresponder a algo que `CONFIG.existeVista()` pueda comprobar; si
  el proyecto navega por URL, `vista` puede ser la ruta (`'/tickets'`) y
  `existeVista` comprobar un enlace del menú:
  `(v) => !!document.querySelector(\`a[href$="${v}"]\`)`, con
  `irA: (v) => { window.location.href = v; }`. En ese caso el panel se cierra al
  cambiar de página; es aceptable.

---

## 7. Qué NO hacer

- No conectar el bot a una API de IA ni a un backend: su valor es que responde
  lo que el sistema hace de verdad y nunca inventa.
- No cambiar colores, medidas, tiempos, textos de interfaz, iconos de los chips
  fijos (`fa-arrow-left`, `fa-arrow-right`, `fa-list`, `fa-headset`,
  `fa-rotate-right`, `fa-times`, `fa-search`) ni el emoji 👋 del saludo.
- No abrir el panel automáticamente al cargar la página.
- No incluir el bot en la pantalla de login ni en páginas públicas.
- No duplicar el armazón (un solo `#asistente` por página).
- No quitar `.asis-panel[hidden] { display: none; }`.
- No usar `innerHTML` con texto que escriba el usuario (el eco usa `textContent`).
