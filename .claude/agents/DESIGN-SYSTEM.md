# Sistema de diseño — Azul Corporativo

> Fuente única de verdad visual para todos los proyectos. Colócalo en la raíz del repositorio como `DESIGN-SYSTEM.md`.
> Cualquier pantalla, componente o agente de IA que genere interfaz debe usar estos tokens y reglas. No se escriben colores hex sueltos en los componentes: siempre variables.
>
> Generado con el plugin **ui-ux-pro-max** (patrón *Trust & Authority*, estilo *Accessible & Ethical*, paleta *B2B navy + azul*). Versión 7 · octubre 2026.

---

## 1. Principios

1. **Confianza antes que decoración.** Navy y azul transmiten orden y profesionalismo; el color se reserva para la acción y el estado, nunca para adornar.
2. **Se lee de un vistazo.** Jerarquía clara: un título principal por pantalla, acciones evidentes.
3. **El estado se nota por forma, no solo por color.** Íconos, texto o relleno acompañan siempre al color.
4. **Los datos son datos.** Horas, fechas, montos y contadores en fuente monoespaciada para que alineen en columna.
5. **Responsive en todo dispositivo.** Cada pantalla funciona y se ve profesional de 320px a monitores grandes, en vertical y horizontal (sección 13).
6. **Accesible por defecto.** Texto 4.5:1 en ambos temas, foco visible, objetivos táctiles de 44×44px, `prefers-reduced-motion` respetado.

## 2. Voz y contenido

- Español neutro, tuteo, tono profesional y directo.
- Botones con verbo de acción: «Guardar», «Crear proyecto», «Exportar».
- Fechas y horas: `mié 14 oct · 08:30`. Duraciones siempre con unidad: `5 min`.
- Sin signos de exclamación ni emojis en la interfaz.

---

## 3. Color

Dos temas: **Claro** (por defecto) y **Oscuro**. Cada token tiene un valor para cada tema.

| Token | Claro | Oscuro | Uso |
| --- | --- | --- | --- |
| `surface-100` | `#F8FAFC` | `#0B1220` | Fondo de página |
| `surface-200` | `#FFFFFF` | `#131C2E` | Tarjetas, filas, modales, menús |
| `surface-300` | `#E8ECF1` | `#1E293B` | Fondos atenuados: hover, encabezados de tabla, pista de progreso |
| `ink` | `#0F172A` | `#F1F5F9` | Texto principal y títulos |
| `ink-muted` | `#475569` | `#94A3B8` | Texto secundario, ayudas, metadatos |
| `border` | `#E2E8F0` | `#263247` | Separadores y contorno de tarjetas (decorativo) |
| `border-strong` | `#64748B` | `#64748B` | Borde de campos, casillas y botón secundario |
| `navy` | `#0F172A` | `#1E3A8A` | Barra lateral y cabecera institucional |
| `on-navy` | `#FFFFFF` | `#FFFFFF` | Texto e íconos sobre `navy` |
| `on-navy-muted` | `#BFDBFE` | `#BFDBFE` | Ítems inactivos y grupos sobre `navy` |
| `primary` | `#0369A1` | `#38BDF8` | Acción principal, enlaces, selección, progreso |
| `on-primary` | `#FFFFFF` | `#0B1220` | Texto sobre `primary` |
| `primary-subtle` | `#E0F2FE` | `#0C2A43` | Fila seleccionada, elemento activo, chips |
| `ring` | `#0369A1` | `#38BDF8` | Anillo de foco (= `primary`) |
| `danger` | `#DC2626` | `#F87171` | Error, atrasado, acción destructiva |
| `on-danger` | `#FFFFFF` | `#0B1220` | Texto sobre `danger` |
| `footer-bg` | `#0F172A` | `#131C2E` | Fondo del footer |
| `footer-ink` | `#F8FAFC` | `#F1F5F9` | Títulos y nombres en el footer |
| `footer-muted` | `#CBD5E1` | `#94A3B8` | Texto, enlaces e íconos del footer |
| `footer-border` | `#1E293B` | `#263247` | Separadores y contorno de botones del footer |
| `footer-hover` | `#1E293B` | `#1E293B` | Fondo hover de botones del footer |
| `sidebar-bg` | `#0F172A` | `#131C2E` | Fondo del sidebar (siempre oscuro) |
| `sidebar-border` | `#1E293B` | `#263247` | Separadores y borde del sidebar |
| `sidebar-ink` | `#F8FAFC` | `#F1F5F9` | Nombre del sistema, usuario, ítem en hover |
| `sidebar-muted` | `#CBD5E1` | `#CBD5E1` | Ítems del menú en reposo |
| `sidebar-label` | `#94A3B8` | `#94A3B8` | Títulos de grupo, @usuario, versión |
| `sidebar-hover` | `#1E293B` | `#1E293B` | Fondo hover de ítems; pista del interruptor apagado |
| `sidebar-active-bg` | `#0C4A6E` | `#0C2A43` | Fondo del ítem activo |
| `sidebar-active-ink` | `#E0F2FE` | `#E0F2FE` | Texto del ítem activo |
| `sidebar-indicator` | `#38BDF8` | `#38BDF8` | Barra e ícono del ítem activo, foco y botón Acerca de |
| `sidebar-danger` | `#F87171` | `#F87171` | Botón Cerrar sesión |
| `gradient-brand` | `#0369A1 → #0F172A` | `#0369A1 → #1E3A8A` | Degradado diagonal (135°) de cabeceras de modales; texto encima `#FFFFFF` |

**Contraste verificado (WCAG AA):** todos los pares de texto cumplen 4.5:1 en ambos temas; `border-strong` cumple 3:1 sobre `surface-200`.

### Reglas de color

- **Un solo azul de acción por pantalla:** `primary` marca lo que se puede hacer; no se usa para títulos ni decoración.
- `navy` es estructura (navegación, cabecera), nunca un botón. Quién lo lleva depende de la pantalla: con sidebar, el sidebar; sin él, la cabecera (sección 9). Alguno de los dos tiene que llevarlo.
- `border` no delimita controles (no llega a 3:1); los campos llevan `border-strong`.
- `danger` siempre va con texto o ícono, nunca solo el color.
- En oscuro la elevación la dan las superficies (`surface-200` sobre `surface-100`), no las sombras.
- **`gradient-brand` de fondo sólo si sus DOS extremos pasan** con el texto que va encima. Es un degradado de `primary` a `navy`: el extremo navy sobra de contraste, pero el azul está cerca del límite y con texto pequeño o atenuado no llega. Vale de fondo en encabezados de tabla y de modal, donde el texto es blanco y de cuerpo. **No vale** donde haya texto en `on-navy-muted` o por debajo de 14px —una cabecera con subtítulo, por ejemplo—: ahí va como **filo de 2-3px** al borde del bloque, que da la misma presencia de marca y no lleva texto encima.
- **Un degradado no se mide en `backgroundColor`.** Ahí aparece transparente, y un comprobador ingenuo da un 1:1 falso o lee el fondo de la tarjeta de debajo. Se lee `backgroundImage`, se extraen las paradas y se comprueba **cada una** contra el color del texto.

---

## 4. Tipografía

- **Plus Jakarta Sans** (400–700) para toda la interfaz.
- **IBM Plex Mono** (500) solo para datos: horas, fechas, montos, contadores.

```css
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700&family=IBM+Plex+Mono:wght@500&display=swap');
```

| Estilo | Tamaño / interlineado | Peso | Fuente | Uso |
| --- | --- | --- | --- | --- |
| `display` | 36 / 44px, -0.02em | 700 | Sans | Título principal. Uno por pantalla |
| `title` | 24 / 32px, -0.01em | 600 | Sans | Título de página y de sección |
| `heading` | 18 / 26px | 600 | Sans | Título de tarjeta o de fila |
| `body` | 16 / 24px | 400 | Sans | Texto corrido y campos |
| `body-sm` | 14 / 20px | 400 | Sans | Celdas de tabla, ayudas |
| `label` | 14 / 20px | 600 | Sans | Botones, etiquetas, pestañas |
| `overline` | 12 / 16px, 0.06em, MAYÚSCULAS | 600 | Sans | Grupos de navegación, encabezados de columna |
| `meta` | 13 / 18px | 500 | Mono | Horas, fechas, duraciones, números |

El texto corrido nunca baja de 14px.

**Columnas de cifras en `tabular-nums`.** Cualquier columna numérica —cantidades,
totales, contadores— lleva `font-variant-numeric: tabular-nums`. Sin eso los
dígitos tienen anchos distintos, las cifras no alinean en vertical y, si además
la cifra cambia sola (ver el contador de la sección 8), la fila da un salto en
cada paso.

---

## 5. Espaciado, radios, sombras y movimiento

| Token | Valor | Uso |
| --- | --- | --- |
| `space-1` | 4px | Entre ícono y texto |
| `space-2` | 8px | Entre controles agrupados y chips |
| `space-3` | 12px | Relleno vertical de filas y botones |
| `space-4` | 16px | Relleno de tarjetas; márgenes en móvil |
| `space-6` | 24px | Entre secciones; relleno de modales |
| `space-8` | 32px | Márgenes de página en escritorio |
| `radius-sm` | 4px | Casillas, chips |
| `radius-md` | 8px | Botones, campos, filas, menús |
| `radius-lg` | 12px | Tarjetas, modales |
| `radius-pill` | 999px | Progreso, insignias |
| `shadow-sm` | claro `0 1px 2px rgba(15,23,42,.06)` · oscuro `none` | Tarjetas en reposo |
| `shadow-md` | claro `0 8px 24px rgba(15,23,42,.12)` · oscuro `0 8px 24px rgba(0,0,0,.5)` | Menús y modales |

Movimiento: ver la sección 8.

---

## 6. Componentes base

El orden de una pantalla es siempre: **Header (sección 9) → contenido → Footer (sección 10)**, y los tres se montan sobre el esqueleto de página de la sección 13 (regla 11), que mantiene el footer abajo aunque el contenido sea corto. La ventana «Acerca de» (sección 11) se abre desde el menú del avatar o desde el sidebar (sección 12), que es opcional.

- **Estructura:** barra lateral `navy`, grupos en `overline` color `on-navy-muted`, ítem activo `on-navy` con indicador `primary`. Contenido sobre `surface-100`.
- **Botón primario:** fondo `primary`, texto `on-primary`, `label`, `radius-md`, alto mínimo 44px.
- **Botón secundario:** fondo `surface-200`, borde `border-strong`, texto `ink`.
- **Botón destructivo:** fondo `danger`, texto `on-danger`.
- **Campo de texto:** fondo `surface-200`, borde `border-strong`, `radius-md`; etiqueta visible en `label` (nunca solo placeholder); error en `danger` debajo del campo.
- **Casilla:** `radius-sm`, borde `border-strong`; marcada con fondo `primary` y check `on-primary`.
- **Tarjeta:** `surface-200`, borde `border`, `radius-lg`, `shadow-sm`, relleno `space-4`.
- **Tabla:** encabezado `surface-300` en `overline`; filas separadas por `border`; hover `surface-300`; selección `primary-subtle`. En pantallas que son **sólo tablas** —un informe, una consulta— el encabezado puede ir en `navy` con texto `on-navy`: ahí la tabla es la pantalla, no un elemento dentro de ella, y el gris la deja sin jerarquía. Si además hay un grupo de columnas combinado encima, va en `primary` con `on-primary` para distinguirse del encabezado.
- **Barra de progreso:** `radius-pill`, pista `surface-300`, relleno `primary`, con texto en `meta`.
- **Título de sección:** `heading`, con una **marca de acento** de 4px en `primary` (`border-radius: pill`) a la izquierda y, opcionalmente, un ícono de 18px también en `primary`. Es lo que da jerarquía sin meter otra franja de color a lo ancho de la pantalla.
- **Tarjeta de tabla:** el título y su tabla van en la MISMA tarjeta (título dentro, tabla debajo, `overflow: hidden` para que la tabla respete el radio). Un título suelto encima de una caja aparte convierte cada tabla en una franja independiente; en pantallas con tres o cuatro tablas seguidas eso se lee como barras apiladas, no como secciones.
- **Ficha de contexto:** el dato que acompaña al título de la pantalla (partida, fecha, filtros) va en `meta` sobre `primary-subtle` con `radius-pill`, al lado del título y no debajo.
- **Campo de sólo lectura:** `surface-100` con borde `border`. Si además es un dato que no se teclea nunca —un identificador, un total traído de otro sistema— `primary-subtle` con borde `primary` al 35%.
- **Foco:** anillo `ring` de 2px separado 2px del control. Nunca se elimina.

## 7. Iconografía

Íconos lineales SVG de **Lucide** (trazo 2px, 20px en botones y filas), coloreados con `ink`, `ink-muted`, `primary` u `on-navy`. Nunca emojis como íconos; los botones solo con ícono llevan `aria-label`.

---

## 8. Movimiento y animaciones

El movimiento es **sutil, corto y con propósito**: confirma una acción, orienta o muestra jerarquía. Nunca decora ni retrasa al usuario.

### Tokens de movimiento

| Token | Valor | Uso |
| --- | --- | --- |
| `duration-fast` | 120ms | Hover, presión de botón, cambio de color |
| `duration-base` | 200ms | Menús, tooltips, casillas, acordeones |
| `duration-slow` | 320ms | Entrada de página, modales, paneles |
| `ease-standard` | `cubic-bezier(0.2, 0, 0, 1)` | Cambios dentro de la pantalla |
| `ease-enter` | `cubic-bezier(0.05, 0.7, 0.1, 1)` | Elementos que aparecen (desaceleran al llegar) |
| `ease-exit` | `cubic-bezier(0.3, 0, 1, 1)` | Elementos que se van (más rápidos que la entrada) |
| `stagger` | 40ms | Retraso entre elementos de una lista al entrar |

### Catálogo de animaciones

| Animación | Dónde | Cómo |
| --- | --- | --- |
| `fade-up` | Entrada de página y de tarjetas | opacidad 0→1 y `translateY(8px)`→0, `duration-slow`, `ease-enter` |
| Escalonado | Listas, filas de tabla, tarjetas en grilla | `fade-up` con `animation-delay: calc(var(--i) * var(--stagger))`, máximo 8 elementos |
| Elevación en hover | Tarjetas y elementos clicables | `translateY(-2px)` + `shadow-md`, `duration-fast` |
| Presión | Botones | `scale(0.98)` en `:active`, `duration-fast` |
| `pop-in` | Menús desplegables, tooltips, popovers | opacidad 0→1 y `scale(0.96)`→1 desde el origen del disparador, `duration-base` |
| Modal | Diálogos | fondo con fade `duration-base`; panel `fade-up` `duration-slow`; salida con `ease-exit` en 200ms |
| Casilla | Marcar una tarea | relleno `primary` con `duration-base` y trazo del check dibujado (`stroke-dashoffset`) |
| Progreso | Barras de avance | `transform: scaleX()` con `duration-slow`, nunca animar `width` |
| Skeleton | Carga de datos | brillo lineal de `surface-300` a `surface-200`, 1.2s en bucle |
| Header al hacer scroll | Header fijo | aparece `shadow-sm` y borde con `duration-base` |
| Footer | Al entrar en pantalla | `fade-up` de columnas con escalonado (una vez) |
| Contador | Cantidades y totales al aparecer | la cifra sube de 0 a su valor en `duration-slow`, con desaceleración al final |

### Reglas

- Solo se animan `opacity` y `transform` (rendimiento y sin saltos de diseño).
- La salida siempre es más rápida que la entrada.
- Nada dura más de 400ms, salvo el skeleton.
- Ninguna animación bloquea la interacción ni se repite sin motivo.
- Con `prefers-reduced-motion: reduce` se eliminan desplazamientos y escalas; quedan solo cambios de opacidad instantáneos.
- **El contador es la excepción a «sólo `opacity` y `transform`»**, porque cambia texto. Por eso lleva condiciones propias:
  1. Sólo sobre **cantidades**: unidades, totales, importes, contadores. **Nunca** sobre identificadores, referencias, códigos ni números de documento. Ver contar un número de factura no informa de nada. Se eligen las celdas por posición de columna, no por «parece un número».
  2. La celda se escribe **con su valor final** y el contador la pone a cero justo antes de empezar: si el script no llega a ejecutarse, el dato correcto ya está puesto.
  3. La columna va en `tabular-nums` (sección 4) para que la fila no salte.
  4. Con `prefers-reduced-motion: reduce` no corre: la cifra se queda en su valor final desde el principio.
  5. Arranca cuando su fila ya ha entrado; contar sobre algo que aún no se ve no se ve.

```css
@keyframes fade-up {
  from { opacity: 0; transform: translateY(8px); }
  to   { opacity: 1; transform: none; }
}
@keyframes pop-in {
  from { opacity: 0; transform: scale(0.96); }
  to   { opacity: 1; transform: none; }
}
@keyframes shimmer {
  from { background-position: -200% 0; }
  to   { background-position: 200% 0; }
}

.animate-fade-up {
  animation: fade-up var(--duration-slow) var(--ease-enter) both;
  animation-delay: calc(var(--i, 0) * var(--stagger));
}
.animate-pop-in {
  animation: pop-in var(--duration-base) var(--ease-enter) both;
  transform-origin: top right;
}

.interactive {
  transition:
    transform var(--duration-fast) var(--ease-standard),
    box-shadow var(--duration-fast) var(--ease-standard),
    background-color var(--duration-fast) var(--ease-standard),
    border-color var(--duration-fast) var(--ease-standard);
}
.card.interactive:hover { transform: translateY(-2px); box-shadow: var(--shadow-md); }
.btn:active { transform: scale(0.98); }

.skeleton {
  border-radius: var(--radius-md);
  background: linear-gradient(90deg, var(--surface-300) 25%, var(--surface-200) 50%, var(--surface-300) 75%);
  background-size: 200% 100%;
  animation: shimmer 1.2s linear infinite;
}

.progress__bar {
  transform-origin: left;
  transition: transform var(--duration-slow) var(--ease-standard);
}

@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 1ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 1ms !important;
  }
  .card.interactive:hover, .btn:active { transform: none; }
}
```

En React, para listas: `<li className="animate-fade-up" style={{ '--i': index }}>`.

### Sin framework (PHP, HTML servido, plantillas)

No hace falta que nadie añada clases desde el script. Basta con que el bloque
**se renderice por primera vez**: al quitar el atributo `hidden` de una
sección, sus hijos se pintan y la animación arranca sola.

```css
/* Entrada escalonada de los bloques de una pantalla */
#pantalla > * { animation: fade-up 380ms var(--ease-enter) both; }

#pantalla > *:nth-child(1) { animation-delay: 0ms; }
#pantalla > *:nth-child(2) { animation-delay: 70ms; }
#pantalla > *:nth-child(3) { animation-delay: 140ms; }
#pantalla > *:nth-child(4) { animation-delay: 210ms; }
#pantalla > *:nth-child(5) { animation-delay: 280ms; }
#pantalla > *:nth-child(6) { animation-delay: 350ms; }
#pantalla > *:nth-child(n + 7) { animation-delay: 420ms; }   /* se corta aquí */

/* Filas de una tabla, una detrás de otra */
.data-table tbody tr { animation: fade-up var(--duration-base) var(--ease-enter) both; }
.data-table tbody tr:nth-child(1) { animation-delay: 200ms; }
.data-table tbody tr:nth-child(2) { animation-delay: 245ms; }
/* … hasta la 7 … */
.data-table tbody tr:nth-child(n + 8) { animation-delay: 515ms; }

@media (prefers-reduced-motion: reduce) {
  #pantalla > *,
  .data-table tbody tr { animation: none !important; opacity: 1; transform: none; }
}
```

El corte del escalonado (`nth-child(n + 7)`, `nth-child(n + 8)`) no es un
detalle: sin él, la fila 40 de una tabla entraría a los dos segundos y lo que
se percibe no es una entrada, es que la pantalla va lenta.

Y el contador, también sin framework:

```js
/* Sólo cantidades: se pasan los índices de columna, no se adivina. */
function animarCifras(fila, desde, hasta) {
  if (matchMedia('(prefers-reduced-motion: reduce)').matches) return;

  const celdas = [];
  for (let i = desde; i <= hasta && i < fila.cells.length; i++) {
    const destino = parseInt(fila.cells[i].textContent, 10);
    if (!Number.isNaN(destino) && destino > 0) celdas.push({ nodo: fila.cells[i], destino });
  }
  if (!celdas.length) return;

  const DURACION = 380, inicio = performance.now();
  celdas.forEach(c => { c.nodo.textContent = '0'; });

  (function paso(ahora) {
    const t = Math.min(1, (ahora - inicio) / DURACION);
    const suave = 1 - Math.pow(1 - t, 3);          // frena al llegar
    celdas.forEach(c => { c.nodo.textContent = String(Math.round(c.destino * suave)); });
    if (t < 1) requestAnimationFrame(paso);
  })(performance.now());
}
```

---

## 9. Header

Barra superior fija en todas las pantallas. A la **izquierda**: logo de la empresa y título de la aplicación. A la **derecha**: botón de cambio de tema y usuario (avatar, nombre y cargo debajo).

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ [LOGO] │ IntraNet RORI                                 [☾]  (CF) Carlos Flores ⌄ │
│        │ Sistema integral de gestión                         Desarrollador FS    │
└──────────────────────────────────────────────────────────────────────────────┘
```

| Parte | Especificación |
| --- | --- |
| Contenedor | Alto 64px, relleno horizontal `space-6` (`space-4` en móvil), `position: sticky; top: 0`. Fondo `surface-200` **cuando hay sidebar** (sección 12): la estructura navy ya la pone el sidebar. **Sin sidebar, el fondo es `navy`** con texto `on-navy`, subtítulo y cargo en `on-navy-muted`, botón de tema con borde `rgb(255 255 255 / 30%)` sobre transparente, y el logo siempre sobre su placa blanca. De lo contrario la pantalla se queda sin la estructura que pide la sección 3 («navy es estructura: navegación, cabecera») y la aplicación pierde identidad |
| Al hacer scroll | Aparecen borde inferior `border` y `shadow-sm`, transición `duration-base` |
| Logo | Alto 36px, `alt` con el nombre de la empresa, enlaza al inicio. Si el logo es de fondo blanco, en tema oscuro va sobre una placa `#FFFFFF` con `radius-md` y relleno `space-1` |
| Divisor | Línea vertical de 1px × 32px en `border`, con `space-4` a cada lado |
| Título de la aplicación | Dos líneas: **nombre** en 16px / 22px, 700, `-0.01em`, color `ink` (ej. «IntraNet RORI»); **subtítulo** en 12px / 16px, 500, color `ink-muted` (ej. «Sistema integral de gestión»). Una sola línea cada uno, cortada con «…». Opcional a la derecha del nombre: insignia de entorno («PRUEBAS») en `overline` sobre `primary-subtle` / `primary`, `radius-pill` — nunca en producción |
| Botón de tema | Botón de ícono 40×40, `radius-md`, borde 1px `border`, fondo `surface-200`, ícono 18px `ink-muted`. Muestra la **luna** en tema claro y el **sol** en oscuro (el tema al que vas a cambiar). Hover: fondo `surface-300` e ícono `ink`. `aria-label` «Cambiar a tema oscuro / claro» y `title` igual |
| Animación del tema | El ícono nuevo entra girando desde 90° con fundido (`duration-base`, `ease-enter`); los colores de toda la interfaz cambian con un fundido de 200ms |
| Usuario | Botón: avatar 40px + nombre en `label` color `ink` + cargo en 12px color `ink-muted` + chevron 16px. Separado del botón de tema por `space-3` |
| Avatar | Círculo 40px, foto con `object-fit: cover`, anillo de 2px `surface-200` y contorno 1px `border`. Sin foto: iniciales en `label` sobre `primary-subtle` con texto `primary` |
| Estado (opcional) | Punto de 10px abajo a la derecha del avatar, `#16A34A` (en línea), con borde 2px `surface-200` |
| Menú del usuario | Hover: fondo `surface-300`, `radius-md`. Clic: menú (`pop-in`) con Mi perfil, Acerca de y Cerrar sesión |
| Tableta (< 1024px) | Se oculta el subtítulo |
| Móvil (< 640px) | Se ocultan divisor, nombre y cargo del usuario; quedan logo, nombre de la app (cortado), botón de tema y avatar |
| Con sidebar (sección 12) | El logo y el nombre pasan al sidebar; a la izquierda va el título de la **página** en `heading` y, por debajo de 1024px, el botón ☰ (44×44, `aria-label="Abrir menú"`). El interruptor de tema vive en el sidebar: el header usa `themeToggle={false}` |
| Accesibilidad | `<header role="banner">`, botón de usuario con `aria-haspopup="menu"` y `aria-expanded`; todos los botones con foco visible |

### Tema compartido

Un solo hook para el header y el sidebar; se mantienen sincronizados entre sí.

```jsx
// src/hooks/useTheme.js
import { useEffect, useState } from 'react';

const current = () => document.documentElement.dataset.theme || 'light';

export function useTheme() {
  const [theme, setTheme] = useState(current);

  useEffect(() => {
    const sync = () => setTheme(current());
    window.addEventListener('themechange', sync);
    return () => window.removeEventListener('themechange', sync);
  }, []);

  const toggle = () => {
    const next = current() === 'dark' ? 'light' : 'dark';
    const root = document.documentElement;
    root.classList.add('theme-transition');           // fundido de colores
    root.dataset.theme = next;
    try { localStorage.setItem('theme', next); } catch {}
    window.dispatchEvent(new Event('themechange'));
    setTimeout(() => root.classList.remove('theme-transition'), 250);
  };

  return [theme, toggle];
}
```

En `index.html`, antes del bundle (aplica el tema guardado sin parpadeo):

```html
<script>try{document.documentElement.dataset.theme=localStorage.getItem('theme')||(matchMedia('(prefers-color-scheme: dark)').matches?'dark':'light')}catch(e){document.documentElement.dataset.theme='light'}</script>
```

### Componente

```jsx
// src/components/AppHeader.jsx
import { useEffect, useRef, useState } from 'react';
import { ChevronDown, Sun, Moon } from 'lucide-react';
import { useTheme } from '../hooks/useTheme';

export default function AppHeader({
  logo, companyName,
  appName, appSubtitle, envBadge,          // título de la aplicación
  user, onAbout, onLogout, onProfile,
  themeToggle = true,
}) {
  const [scrolled, setScrolled] = useState(false);
  const [open, setOpen] = useState(false);
  const [theme, toggleTheme] = useTheme();
  const wrapRef = useRef(null);
  const dark = theme === 'dark';

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 4);
    onScroll();
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => window.removeEventListener('scroll', onScroll);
  }, []);

  useEffect(() => {
    if (!open) return;
    const onDoc = (e) => !wrapRef.current?.contains(e.target) && setOpen(false);
    const onKey = (e) => e.key === 'Escape' && setOpen(false);
    document.addEventListener('mousedown', onDoc);
    window.addEventListener('keydown', onKey);
    return () => { document.removeEventListener('mousedown', onDoc); window.removeEventListener('keydown', onKey); };
  }, [open]);

  const initials = user.name.split(' ').map((p) => p[0]).slice(0, 2).join('').toUpperCase();
  const pick = (fn) => () => { setOpen(false); fn?.(); };

  return (
    <header className={`app-header ${scrolled ? 'is-scrolled' : ''}`} role="banner">
      <a href="/" className="app-header__brand" aria-label={`${appName} — inicio`}>
        <span className="app-header__logo"><img src={logo} alt={companyName} /></span>
        <span className="app-header__divider" aria-hidden="true" />
        <span className="app-header__title">
          <span className="app-header__app">
            {appName}
            {envBadge && <span className="app-header__env">{envBadge}</span>}
          </span>
          {appSubtitle && <span className="app-header__subtitle">{appSubtitle}</span>}
        </span>
      </a>

      <div className="app-header__actions">
        {themeToggle && (
          <button
            className="icon-btn"
            onClick={toggleTheme}
            aria-label={dark ? 'Cambiar a tema claro' : 'Cambiar a tema oscuro'}
            title={dark ? 'Cambiar a tema claro' : 'Cambiar a tema oscuro'}
          >
            <span key={theme} className="icon-btn__swap">
              {dark ? <Sun size={18} aria-hidden="true" /> : <Moon size={18} aria-hidden="true" />}
            </span>
          </button>
        )}

        <div className="app-header__user-wrap" ref={wrapRef}>
          <button className="app-header__user" aria-haspopup="menu" aria-expanded={open} onClick={() => setOpen((v) => !v)}>
            <span className="avatar">
              {user.photo ? <img src={user.photo} alt="" /> : <span className="avatar__initials">{initials}</span>}
              {user.online && <span className="avatar__status" aria-label="En línea" />}
            </span>
            <span className="app-header__identity">
              <span className="app-header__name">{user.name}</span>
              <span className="app-header__role">{user.role}</span>
            </span>
            <ChevronDown size={16} aria-hidden="true" className={`app-header__chevron ${open ? 'is-open' : ''}`} />
          </button>

          {open && (
            <div className="menu animate-pop-in" role="menu">
              <button role="menuitem" className="menu__item" onClick={pick(onProfile)}>Mi perfil</button>
              <button role="menuitem" className="menu__item" onClick={pick(onAbout)}>Acerca de</button>
              <div className="menu__sep" role="separator" />
              <button role="menuitem" className="menu__item menu__item--danger" onClick={pick(onLogout)}>Cerrar sesión</button>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}
```

Uso:

```jsx
<AppHeader
  logo="/logo-empresa.png" companyName="Industrias RRC, C.A."
  appName="IntraNet RORI" appSubtitle="Sistema integral de gestión"
  user={{ name: 'Carlos Flores', role: 'Desarrollador Full Stack', photo: '/dev.jpg', online: true }}
  onAbout={() => setAbout(true)} onLogout={logout}
/>
```

### Estilos

```css
.app-header {
  position: sticky; top: 0; z-index: 50;
  height: calc(64px + env(safe-area-inset-top));
  padding: env(safe-area-inset-top) max(var(--space-6), env(safe-area-inset-right)) 0 max(var(--space-6), env(safe-area-inset-left));
  display: flex; align-items: center; justify-content: space-between; gap: var(--space-4);
  background: var(--surface-200);
  border-bottom: 1px solid transparent;
  transition: box-shadow var(--duration-base) var(--ease-standard), border-color var(--duration-base) var(--ease-standard);
}
.app-header.is-scrolled { border-bottom-color: var(--border); box-shadow: var(--shadow-sm); }

.app-header__brand { display: flex; align-items: center; min-width: 0; text-decoration: none; color: inherit; border-radius: var(--radius-md); }
.app-header__brand:focus-visible { outline: 2px solid var(--ring); outline-offset: 4px; }
.app-header__logo { flex: none; }
.app-header__logo img { height: 36px; width: auto; display: block; }
[data-theme="dark"] .app-header__logo { background: #ffffff; border-radius: var(--radius-md); padding: var(--space-1); }
.app-header__divider { flex: none; width: 1px; height: 32px; margin: 0 var(--space-4); background: var(--border); }

.app-header__title { display: flex; flex-direction: column; min-width: 0; }
.app-header__app {
  display: flex; align-items: center; gap: var(--space-2); min-width: 0;
  font: 700 16px/22px var(--font-sans); letter-spacing: -0.01em; color: var(--ink);
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.app-header__subtitle { font: 500 12px/16px var(--font-sans); color: var(--ink-muted); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.app-header__env { flex: none; padding: 2px var(--space-2); border-radius: var(--radius-pill); background: var(--primary-subtle); color: var(--primary); font: 600 10px/14px var(--font-sans); letter-spacing: 0.06em; text-transform: uppercase; }

.app-header__actions { display: flex; align-items: center; gap: var(--space-3); flex: none; }

.icon-btn {
  display: grid; place-items: center; width: 40px; height: 40px; padding: 0;
  border: 1px solid var(--border); border-radius: var(--radius-md);
  background: var(--surface-200); color: var(--ink-muted); cursor: pointer; overflow: hidden;
  transition: background-color var(--duration-fast) var(--ease-standard), color var(--duration-fast) var(--ease-standard), transform var(--duration-fast) var(--ease-standard);
}
.icon-btn:hover { background: var(--surface-300); color: var(--ink); }
.icon-btn:active { transform: scale(0.96); }
.icon-btn:focus-visible { outline: 2px solid var(--ring); outline-offset: 2px; }
.icon-btn__swap { display: grid; animation: icon-swap var(--duration-base) var(--ease-enter) both; }
@keyframes icon-swap { from { opacity: 0; transform: rotate(90deg) scale(0.6); } to { opacity: 1; transform: none; } }

.app-header__user-wrap { position: relative; }
.app-header__user {
  display: flex; align-items: center; gap: var(--space-3);
  min-height: 48px; padding: var(--space-1) var(--space-2) var(--space-1) var(--space-1);
  border: 0; border-radius: var(--radius-md); background: transparent; color: var(--ink); cursor: pointer;
  transition: background-color var(--duration-fast) var(--ease-standard);
}
.app-header__user:hover { background: var(--surface-300); }
.app-header__user:focus-visible { outline: 2px solid var(--ring); outline-offset: 2px; }
.app-header__identity { display: flex; flex-direction: column; align-items: flex-start; text-align: left; }
.app-header__name { font: 600 14px/20px var(--font-sans); color: var(--ink); }
.app-header__role { font: 400 12px/16px var(--font-sans); color: var(--ink-muted); }
.app-header__chevron { color: var(--ink-muted); transition: transform var(--duration-base) var(--ease-standard); }
.app-header__chevron.is-open { transform: rotate(180deg); }

.avatar { position: relative; width: 40px; height: 40px; flex: none; border-radius: 50%; box-shadow: 0 0 0 2px var(--surface-200), 0 0 0 3px var(--border); }
.avatar img { width: 100%; height: 100%; border-radius: 50%; object-fit: cover; display: block; }
.avatar__initials { display: grid; place-items: center; width: 100%; height: 100%; border-radius: 50%; background: var(--primary-subtle); color: var(--primary); font: 600 14px/1 var(--font-sans); }
.avatar__status { position: absolute; right: -1px; bottom: -1px; width: 10px; height: 10px; border-radius: 50%; background: #16a34a; border: 2px solid var(--surface-200); }

.menu {
  position: absolute; right: 0; top: calc(100% + var(--space-2)); min-width: 200px; z-index: 60;
  padding: var(--space-1); background: var(--surface-200); border: 1px solid var(--border);
  border-radius: var(--radius-md); box-shadow: var(--shadow-md);
}
.menu__item { display: block; width: 100%; min-height: 40px; padding: 0 var(--space-3); border: 0; border-radius: var(--radius-sm); background: none; text-align: left; font: 400 14px/20px var(--font-sans); color: var(--ink); cursor: pointer; }
.menu__item:hover, .menu__item:focus-visible { background: var(--surface-300); outline: none; }
.menu__item--danger { color: var(--danger); }
.menu__sep { height: 1px; margin: var(--space-1) 0; background: var(--border); }

/* Fundido de colores al cambiar de tema */
.theme-transition, .theme-transition *, .theme-transition *::before, .theme-transition *::after {
  transition: background-color 200ms var(--ease-standard), color 200ms var(--ease-standard),
              border-color 200ms var(--ease-standard), fill 200ms var(--ease-standard) !important;
}

@media (max-width: 1023px) { .app-header__subtitle { display: none; } }
@media (max-width: 640px) {
  .app-header { padding-inline: max(var(--space-4), env(safe-area-inset-left)) max(var(--space-4), env(safe-area-inset-right)); }
  .app-header__divider, .app-header__identity { display: none; }
  .app-header__logo { margin-right: var(--space-3); }
}
@media (prefers-reduced-motion: reduce) {
  .icon-btn__swap { animation: none; }
  .theme-transition, .theme-transition * { transition: none !important; }
}
```

---

## 10. Footer

Pie corporativo en cuatro columnas, igual en todos los sistemas. **Solo cambian los datos** (empresa, soporte y, sobre todo, el desarrollador de cada proyecto), que se pasan como configuración.

| Columna | Contenido |
| --- | --- |
| 1 · Empresa | Logo sobre placa blanca (`radius-md`), nombre de la empresa en `label` color `footer-ink`, descripción del sistema, dirección (ícono ubicación) y sitio web (ícono globo) |
| 2 · Soporte técnico | Título con ícono auricular; correo, extensión / teléfono y horario de atención, cada uno con su ícono |
| 3 · Desarrollador | Título con ícono usuario; **avatar de 44px** con nombre (`label`) y cargo (`body-sm`) al lado; correo, teléfono y GitHub con íconos. El avatar **no es opcional**: esta columna dice quién mantiene el sistema, y una cara hace que se sepa a quién buscar. Si `foto` viene vacío se omite la imagen —nunca un cuadro gris ni una silueta genérica— y el nombre sube a ocupar su sitio |
| 4 · Manuales y accesos | Título con ícono libro; texto breve; botones contorneados tipo píldora: Manual de usuario (PDF), Manual técnico (PDF), Acceso directo al escritorio |
| Barra inferior | Separador `footer-border` y «© {año} {Empresa} – Todos los derechos reservados.» en `body-sm` color `footer-muted` |

**Estilo:**
- Fondo `footer-bg` (azul marino en claro, superficie elevada en oscuro), borde superior `footer-border`, `radius-lg` en las esquinas superiores si la página tiene márgenes laterales.
- Títulos de columna en `label` (14px, 600) color `footer-ink`, con ícono 16px.
- Texto y enlaces en `body-sm` color `footer-muted`; los íconos en `footer-muted`, alineados al texto con `space-2`.
- Enlaces: hover a `footer-ink` con subrayado, `duration-fast`.
- **Avatar del desarrollador:** 44px, `border-radius: 50%`, `object-fit: cover` y un anillo de 2px. Lleva **un fondo propio** (`primary-subtle` o `footer-hover`): los avatares suelen ser PNG con transparencia, y contra el azul marino del footer las zonas claras del pelo o la ropa desaparecen. Con fondo detrás se ve entero y además se lee como una ficha, no como un recorte pegado.
- **El avatar va sin `alt`** (`alt=""`): el nombre está escrito justo al lado. Describirlo haría que un lector de pantalla dijera el nombre dos veces.
- Botones de manuales: borde 1px `footer-border`, `radius-pill`, texto `label` 13px color `footer-ink`, ícono a la izquierda; hover con fondo `footer-hover` y borde `footer-muted`.
- Grilla: 4 columnas en escritorio (`1.2fr 1fr 1fr 1.2fr`), 2 en tableta, 1 en móvil; separación `space-8`; relleno `space-8` arriba y `space-6` abajo.
- Animación: columnas con `fade-up` escalonado la primera vez que el footer entra en pantalla.

```jsx
// src/config/footer.config.js — lo único que se cambia en cada proyecto
export const footerConfig = {
  empresa: {
    nombre: 'Industrias RRC, C.A.',
    logo: '/logo-empresa.png',
    descripcion: 'Sistema integral de gestión empresarial',
    direccion: 'Av Ppal de los Cortijos',
    web: 'https://www.rori.com',
  },
  soporte: {
    email: 'soporte@rori.com',
    telefono: 'Ext. 2309 / +58 412-333-0319',
    horario: 'Lun a Vie, 7:30 - 16:00',
  },
  desarrollador: {
    nombre: 'Nombre Apellido',          // ← cambia en cada proyecto
    cargo: 'Desarrollador Full Stack',
    foto: '/dev-avatar.jpg',
    email: 'correo@rori.com',
    telefono: '+58 4xx-xxx-xxxx',
    github: 'https://github.com/usuario',
  },
  manuales: {
    texto: 'Los manuales salen en PDF con lo que hay hoy en el sistema.',
    usuario: '/manuales/manual-usuario.pdf',
    tecnico: '/manuales/manual-tecnico.pdf',
    escritorio: '/acceso-directo',
  },
};
```

```jsx
// src/components/AppFooter.jsx
import { useEffect, useRef, useState } from 'react';
import {
  Headset, Mail, Phone, Clock, MapPin, Globe, UserCog, Github,
  BookOpen, FileText, Monitor,
} from 'lucide-react';
import { footerConfig as c } from '../config/footer.config';

const Item = ({ icon: Icon, children, href }) => (
  <li className="footer__item">
    <Icon size={14} aria-hidden="true" />
    {href ? <a href={href} className="footer__link">{children}</a> : <span>{children}</span>}
  </li>
);

export default function AppFooter() {
  const ref = useRef(null);
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const io = new IntersectionObserver(([e]) => { if (e.isIntersecting) { setVisible(true); io.disconnect(); } }, { threshold: 0.15 });
    if (ref.current) io.observe(ref.current);
    return () => io.disconnect();
  }, []);

  const col = (i) => ({ className: `footer__col ${visible ? 'animate-fade-up' : 'is-hidden'}`, style: { '--i': i } });
  const d = c.desarrollador;

  return (
    <footer className="footer" ref={ref} role="contentinfo">
      <div className="footer__grid">
        <section {...col(0)}>
          <span className="footer__logo"><img src={c.empresa.logo} alt={c.empresa.nombre} /></span>
          <p className="footer__company">{c.empresa.nombre}</p>
          <p className="footer__text">{c.empresa.descripcion}</p>
          <ul className="footer__list">
            <Item icon={MapPin}>{c.empresa.direccion}</Item>
            <Item icon={Globe} href={c.empresa.web}>{c.empresa.web}</Item>
          </ul>
        </section>

        <section {...col(1)}>
          <h2 className="footer__title"><Headset size={16} aria-hidden="true" /> Soporte técnico</h2>
          <ul className="footer__list">
            <Item icon={Mail} href={`mailto:${c.soporte.email}`}>{c.soporte.email}</Item>
            <Item icon={Phone}>{c.soporte.telefono}</Item>
            <Item icon={Clock}>{c.soporte.horario}</Item>
          </ul>
        </section>

        <section {...col(2)}>
          <h2 className="footer__title"><UserCog size={16} aria-hidden="true" /> Desarrollador</h2>
          <div className="footer__dev">
            <img className="footer__dev-photo" src={d.foto} alt="" />
            <div>
              <p className="footer__dev-name">{d.nombre}</p>
              <p className="footer__dev-role">{d.cargo}</p>
            </div>
          </div>
          <ul className="footer__list">
            <Item icon={Mail} href={`mailto:${d.email}`}>{d.email}</Item>
            <Item icon={Phone}>{d.telefono}</Item>
            <Item icon={Github} href={d.github}>GitHub</Item>
          </ul>
        </section>

        <section {...col(3)}>
          <h2 className="footer__title"><BookOpen size={16} aria-hidden="true" /> Manuales y accesos</h2>
          <p className="footer__text">{c.manuales.texto}</p>
          <div className="footer__actions">
            <a className="footer__pill" href={c.manuales.usuario} download><FileText size={14} aria-hidden="true" /> Manual de usuario (PDF)</a>
            <a className="footer__pill" href={c.manuales.tecnico} download><FileText size={14} aria-hidden="true" /> Manual técnico (PDF)</a>
            <a className="footer__pill" href={c.manuales.escritorio}><Monitor size={14} aria-hidden="true" /> Acceso directo al escritorio</a>
          </div>
        </section>
      </div>

      <div className="footer__bottom">
        © {new Date().getFullYear()} {c.empresa.nombre} – Todos los derechos reservados.
      </div>
    </footer>
  );
}
```

```css
.footer {
  margin-top: var(--space-8);
  padding: var(--space-8) var(--space-8) var(--space-6);
  background: var(--footer-bg);
  border-top: 1px solid var(--footer-border);
  border-radius: var(--radius-lg) var(--radius-lg) 0 0;
  color: var(--footer-muted);
  font: 400 14px/20px var(--font-sans);
}
.footer__grid { display: grid; grid-template-columns: 1.2fr 1fr 1fr 1.2fr; gap: var(--space-8); }
.footer__col.is-hidden { opacity: 0; }

.footer__logo { display: inline-block; padding: var(--space-1) var(--space-2); background: #ffffff; border-radius: var(--radius-md); }
.footer__logo img { height: 44px; width: auto; display: block; }
.footer__company { margin: var(--space-4) 0 var(--space-2); font: 600 14px/20px var(--font-sans); color: var(--footer-ink); }
.footer__text { margin: 0 0 var(--space-3); max-width: 28ch; }

.footer__title { display: flex; align-items: center; gap: var(--space-2); margin: 0 0 var(--space-4); font: 600 14px/20px var(--font-sans); color: var(--footer-ink); }
.footer__list { list-style: none; margin: 0; padding: 0; display: grid; gap: var(--space-2); }
.footer__item { display: flex; align-items: center; gap: var(--space-2); }
.footer__item svg { flex: none; color: var(--footer-muted); }
.footer__link { color: var(--footer-muted); text-decoration: none; transition: color var(--duration-fast) var(--ease-standard); }
.footer__link:hover { color: var(--footer-ink); text-decoration: underline; text-underline-offset: 3px; }

.footer__dev { display: flex; align-items: center; gap: var(--space-3); margin-bottom: var(--space-3); }
.footer__dev-photo {
  width: 44px; height: 44px; flex: none;
  border-radius: 50%; object-fit: cover;
  /* Fondo propio: la mayoría de los avatares son PNG con transparencia y
     sobre el navy del footer se pierden las zonas claras */
  background: var(--primary-subtle);
  box-shadow: 0 0 0 2px rgb(255 255 255 / 20%);
}
.footer__dev-name { margin: 0; font: 600 14px/20px var(--font-sans); color: var(--footer-ink); }
.footer__dev-role { margin: 0; font: 400 12px/16px var(--font-sans); color: var(--footer-muted); }

.footer__actions { display: flex; flex-direction: column; align-items: flex-start; gap: var(--space-2); }
.footer__pill {
  display: inline-flex; align-items: center; gap: var(--space-2);
  min-height: 36px; padding: 0 var(--space-4);
  border: 1px solid var(--footer-border); border-radius: var(--radius-pill);
  font: 600 13px/1 var(--font-sans); color: var(--footer-ink); text-decoration: none;
  transition: background-color var(--duration-fast) var(--ease-standard), border-color var(--duration-fast) var(--ease-standard), transform var(--duration-fast) var(--ease-standard);
}
.footer__pill:hover { background: var(--footer-hover); border-color: var(--footer-muted); }
.footer__pill:active { transform: scale(0.98); }
.footer a:focus-visible { outline: 2px solid var(--footer-ink); outline-offset: 2px; }

.footer__bottom { margin-top: var(--space-8); padding-top: var(--space-4); border-top: 1px solid var(--footer-border); font-size: 13px; }

@media (max-width: 1024px) { .footer__grid { grid-template-columns: 1fr 1fr; } }
@media (max-width: 640px)  { .footer { padding: var(--space-6) var(--space-4); } .footer__grid { grid-template-columns: 1fr; gap: var(--space-6); } }
```

---

## 11. Acerca de (modal)

Ventana «Acerca de» común a todos los sistemas. Se abre desde el menú del avatar del header o desde un enlace del footer. **El diseño no cambia; solo los datos**, que salen de `about.config.js` (y reutiliza empresa, soporte y desarrollador de `footer.config.js` para no duplicarlos).

### Estructura (de arriba a abajo)

| Bloque | Especificación |
| --- | --- |
| Ventana | Ancho 540px (100% − `space-8` en móvil), alto máx. 85vh con scroll interno, fondo `surface-200`, borde `border`, radio 16px, `shadow-md`. Fondo de pantalla `rgba(2, 6, 23, 0.6)` con desenfoque 4px |
| Cabecera | Alto 72px, degradado `gradient-brand` (azul de acción → navy) en diagonal, ícono «info» 20px + «Acerca de» en `heading` color `#FFFFFF`; botón cerrar ✕ a la derecha (40×40, hover fondo blanco 15%) |
| Identidad | Centrada: círculo de 80px fondo `primary-subtle` con el ícono del sistema 40px en `primary`; nombre del sistema en `title` (24px, 700) `ink`; descripción en `body-sm` `ink-muted` |
| Versión | Dos chips píldora centrados: «Versión x.y.z» (fondo `primary-subtle`, texto `primary`, 600) y «Build: Mes Año» (fondo `surface-100`, borde `border`, texto `ink-muted`) |
| Destacado | Panel `surface-100`, `radius-lg`, relleno `space-4`, texto `body` centrado en `ink` (600) con la propuesta de valor |
| Títulos de sección | Ícono 18px en `primary` + texto `heading` (18px, 700) en `ink`; margen superior `space-6` |
| Tecnologías | Píldoras con ícono de marca 16px en `primary` + nombre en `label` (14px, 600) `ink`; fondo `surface-100`, borde `border`, `radius-pill`, alto 36px; envuelven en varias filas con `space-2` |
| Desarrollador | Tarjeta `surface-100`, `radius-lg`, relleno `space-4`: foto 72px circular con anillo 2px `primary`; nombre en `heading` (18px, 700), cargo en `body-sm` `ink-muted`; contactos como píldoras pequeñas (fondo `surface-300`, ícono + texto 13px) que son enlaces (mailto, tel, GitHub) |
| Colaboradores | Grilla de 2 columnas (1 en móvil): tarjetas `surface-100` con borde `border` y `radius-lg`; avatar 40px de iniciales (fondo `primary`, texto `on-primary`, 700) + nombre en `label` y cargo en 12px `ink-muted` |
| Soporte técnico | Grilla de 2 columnas: tarjetas `surface-100` con ícono 24px en `primary` a la izquierda, etiqueta en `label` `ink` y valor en `body-sm` `ink-muted` (Email, Teléfono, Horario) |
| Pie | Separador `border`; «© {año} {Empresa} – Todos los derechos reservados.» y una línea de agradecimiento, centrados, 12–13px `ink-muted` |

### Animación

- Apertura: fondo con fade `duration-base`; ventana `fade-up` + `scale(0.98 → 1)` en `duration-slow` con `ease-enter`.
- Contenido: cada bloque entra con `fade-up` escalonado (`--i` de 0 a 7).
- Cierre: ventana y fondo se desvanecen en 160ms con `ease-exit`.
- Hover: tarjetas de colaboradores y soporte suben 2px y su borde pasa a `border-strong`; píldoras de contacto pasan a `primary-subtle`.
- Con movimiento reducido: solo opacidad.

### Accesibilidad

`role="dialog"`, `aria-modal="true"`, `aria-labelledby` al título; Esc y clic en el fondo cierran; al abrir, el foco va al botón cerrar y al cerrar vuelve al botón que lo abrió; el scroll de la página se bloquea mientras está abierto; los íconos son decorativos (`aria-hidden`).

### Configuración (lo único que cambia por proyecto)

Íconos de interfaz con `lucide-react`; logos de tecnologías con `react-icons` (`npm install lucide-react react-icons`).

```jsx
// src/config/about.config.js
import { Box } from 'lucide-react';
import {
  FaHtml5, FaCss3Alt, FaJs, FaPhp, FaDatabase, FaCalendarDays,
  FaChartLine, FaFontAwesome, FaFilePdf, FaReact, FaNodeJs,
} from 'react-icons/fa6';
import { footerConfig } from './footer.config';

export const aboutConfig = {
  sistema: {
    nombre: 'IntraNet RORI',
    icono: Box,                                   // ícono lucide del sistema
    descripcion: 'Sistema integral de gestión empresarial',
    version: '2.0.0',
    build: 'Agosto 2026',
    destacado: 'Optimiza la comunicación, el seguimiento de tareas y el acceso a recursos corporativos en un solo lugar.',
  },
  tecnologias: [
    { nombre: 'HTML5', icono: FaHtml5 },
    { nombre: 'CSS3', icono: FaCss3Alt },
    { nombre: 'JavaScript', icono: FaJs },
    { nombre: 'PHP 7.4+', icono: FaPhp },
    { nombre: 'MySQL 8.0', icono: FaDatabase },
    { nombre: 'FullCalendar', icono: FaCalendarDays },
    { nombre: 'Chart.js', icono: FaChartLine },
    { nombre: 'FontAwesome 6', icono: FaFontAwesome },
    { nombre: 'html2pdf', icono: FaFilePdf },
  ],
  desarrollador: footerConfig.desarrollador,      // nombre, cargo, foto, email, telefono, github
  colaboradores: [
    { nombre: 'Nombre Apellido', cargo: 'Desarrollador Junior' },
    { nombre: 'Nombre Apellido', cargo: 'Gerente IT' },
    { nombre: 'Equipo Informática', cargo: 'Soporte técnico', iniciales: 'IT' },
  ],
  soporte: footerConfig.soporte,                  // email, telefono, horario
  empresa: footerConfig.empresa.nombre,
  agradecimiento: 'Este sistema utiliza software de código abierto. Agradecimientos a la comunidad de desarrollo.',
};
```

### Componente

```jsx
// src/components/AboutModal.jsx
import { useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { Info, X, Cpu, UserCog, Users, Headset, Mail, Phone, Clock, Github } from 'lucide-react';
import { aboutConfig as c } from '../config/about.config';

const initialsOf = (name) => name.split(' ').map((p) => p[0]).slice(0, 2).join('').toUpperCase();

function Section({ icon: Icon, title, i, children }) {
  return (
    <section className="about__section animate-fade-up" style={{ '--i': i }}>
      <h3 className="about__section-title"><Icon size={18} aria-hidden="true" /> {title}</h3>
      {children}
    </section>
  );
}

export default function AboutModal({ open, onClose }) {
  const [closing, setClosing] = useState(false);
  const closeRef = useRef(null);
  const lastFocus = useRef(null);

  const close = () => {
    setClosing(true);
    setTimeout(() => { setClosing(false); onClose(); }, 160);
  };

  useEffect(() => {
    if (!open) return;
    lastFocus.current = document.activeElement;
    closeRef.current?.focus();
    document.body.style.overflow = 'hidden';
    const onKey = (e) => e.key === 'Escape' && close();
    window.addEventListener('keydown', onKey);
    return () => {
      document.body.style.overflow = '';
      window.removeEventListener('keydown', onKey);
      lastFocus.current?.focus();
    };
  }, [open]);

  if (!open) return null;
  const { sistema: s, desarrollador: d, soporte: sp } = c;
  const SysIcon = s.icono;

  return createPortal(
    <div className={`about__backdrop ${closing ? 'is-closing' : ''}`} onMouseDown={(e) => e.target === e.currentTarget && close()}>
      <div className="about" role="dialog" aria-modal="true" aria-labelledby="about-title">
        <header className="about__header">
          <h2 id="about-title" className="about__title"><Info size={20} aria-hidden="true" /> Acerca de</h2>
          <button ref={closeRef} className="about__close" onClick={close} aria-label="Cerrar"><X size={20} /></button>
        </header>

        <div className="about__body">
          <div className="about__identity animate-fade-up" style={{ '--i': 0 }}>
            <span className="about__icon"><SysIcon size={40} aria-hidden="true" /></span>
            <p className="about__name">{s.nombre}</p>
            <p className="about__desc">{s.descripcion}</p>
            <div className="about__chips">
              <span className="chip chip--primary">Versión {s.version}</span>
              <span className="chip">Build: {s.build}</span>
            </div>
          </div>

          <p className="about__highlight animate-fade-up" style={{ '--i': 1 }}>{s.destacado}</p>

          <Section icon={Cpu} title="Tecnologías" i={2}>
            <ul className="about__techs">
              {c.tecnologias.map(({ nombre, icono: Icon }) => (
                <li key={nombre} className="tech"><Icon size={16} aria-hidden="true" /> {nombre}</li>
              ))}
            </ul>
          </Section>

          <Section icon={UserCog} title="Desarrollador" i={3}>
            <div className="dev-card">
              <img className="dev-card__photo" src={d.foto} alt="" />
              <div>
                <p className="dev-card__name">{d.nombre}</p>
                <p className="dev-card__role">{d.cargo}</p>
                <div className="dev-card__contacts">
                  <a className="contact" href={`mailto:${d.email}`}><Mail size={13} aria-hidden="true" /> {d.email}</a>
                  <a className="contact" href={`tel:${d.telefono.replace(/[^\d+]/g, '')}`}><Phone size={13} aria-hidden="true" /> {d.telefono}</a>
                  <a className="contact" href={d.github} target="_blank" rel="noreferrer"><Github size={13} aria-hidden="true" /> GitHub</a>
                </div>
              </div>
            </div>
          </Section>

          {c.colaboradores?.length > 0 && (
            <Section icon={Users} title="Colaboradores" i={4}>
              <ul className="about__grid">
                {c.colaboradores.map((p) => (
                  <li key={p.nombre + p.cargo} className="person interactive">
                    <span className="person__avatar" aria-hidden="true">{p.iniciales ?? initialsOf(p.nombre)}</span>
                    <span><span className="person__name">{p.nombre}</span><span className="person__role">{p.cargo}</span></span>
                  </li>
                ))}
              </ul>
            </Section>
          )}

          <Section icon={Headset} title="Soporte técnico" i={5}>
            <ul className="about__grid">
              <li className="support interactive"><Mail size={24} aria-hidden="true" /><span><span className="support__label">Email</span><a className="support__value" href={`mailto:${sp.email}`}>{sp.email}</a></span></li>
              <li className="support interactive"><Phone size={24} aria-hidden="true" /><span><span className="support__label">Teléfono</span><span className="support__value">{sp.telefono}</span></span></li>
              <li className="support interactive"><Clock size={24} aria-hidden="true" /><span><span className="support__label">Horario</span><span className="support__value">{sp.horario}</span></span></li>
            </ul>
          </Section>

          <footer className="about__footer animate-fade-up" style={{ '--i': 6 }}>
            <p>© {new Date().getFullYear()} {c.empresa} – Todos los derechos reservados.</p>
            <p>{c.agradecimiento}</p>
          </footer>
        </div>
      </div>
    </div>,
    document.body
  );
}
```

Uso: `const [about, setAbout] = useState(false);` … `<AboutModal open={about} onClose={() => setAbout(false)} />`, y en el menú del header un ítem «Acerca de» que hace `setAbout(true)`.

### Estilos

```css
@keyframes modal-in { from { opacity: 0; transform: translateY(12px) scale(0.98); } to { opacity: 1; transform: none; } }
@keyframes backdrop-in { from { opacity: 0; } to { opacity: 1; } }

.about__backdrop {
  position: fixed; inset: 0; z-index: 100;
  display: grid; place-items: center; padding: var(--space-4);
  background: rgba(2, 6, 23, 0.6); backdrop-filter: blur(4px);
  animation: backdrop-in var(--duration-base) var(--ease-standard) both;
}
.about__backdrop.is-closing { animation: none; opacity: 0; transition: opacity 160ms var(--ease-exit); }
.about__backdrop.is-closing .about { animation: none; opacity: 0; transform: translateY(8px) scale(0.98); transition: opacity 160ms var(--ease-exit), transform 160ms var(--ease-exit); }

.about {
  width: min(540px, 100%); max-height: 85vh;
  display: flex; flex-direction: column; overflow: hidden;
  background: var(--surface-200); color: var(--ink);
  border: 1px solid var(--border); border-radius: 16px; box-shadow: var(--shadow-md);
  animation: modal-in var(--duration-slow) var(--ease-enter) both;
}

.about__header {
  flex: none; height: 72px; padding: 0 var(--space-4) 0 var(--space-6);
  display: flex; align-items: center; justify-content: space-between;
  background: var(--gradient-brand); color: #ffffff;
}
.about__title { display: flex; align-items: center; gap: var(--space-2); margin: 0; font: 700 18px/26px var(--font-sans); }
.about__close { display: grid; place-items: center; width: 40px; height: 40px; border: 0; border-radius: var(--radius-md); background: transparent; color: #ffffff; cursor: pointer; transition: background-color var(--duration-fast) var(--ease-standard); }
.about__close:hover { background: rgba(255, 255, 255, 0.15); }
.about__close:focus-visible { outline: 2px solid #ffffff; outline-offset: 2px; }

.about__body { overflow-y: auto; padding: var(--space-6); scrollbar-width: thin; scrollbar-color: var(--border-strong) transparent; }

.about__identity { text-align: center; }
.about__icon { display: inline-grid; place-items: center; width: 80px; height: 80px; border-radius: 50%; background: var(--primary-subtle); color: var(--primary); }
.about__name { margin: var(--space-4) 0 var(--space-1); font: 700 24px/32px var(--font-sans); letter-spacing: -0.01em; }
.about__desc { margin: 0; font: 400 14px/20px var(--font-sans); color: var(--ink-muted); }
.about__chips { display: flex; justify-content: center; flex-wrap: wrap; gap: var(--space-2); margin-top: var(--space-4); }
.chip { display: inline-flex; align-items: center; min-height: 28px; padding: 0 var(--space-3); border: 1px solid var(--border); border-radius: var(--radius-pill); background: var(--surface-100); font: 500 13px/1 var(--font-sans); color: var(--ink-muted); }
.chip--primary { border-color: transparent; background: var(--primary-subtle); color: var(--primary); font-weight: 600; }

.about__highlight { margin: var(--space-6) 0 0; padding: var(--space-4); border-radius: var(--radius-lg); background: var(--surface-100); text-align: center; font: 600 15px/22px var(--font-sans); }

.about__section { margin-top: var(--space-6); }
.about__section-title { display: flex; align-items: center; gap: var(--space-2); margin: 0 0 var(--space-3); font: 700 18px/26px var(--font-sans); }
.about__section-title svg { color: var(--primary); }

.about__techs { list-style: none; margin: 0; padding: 0; display: flex; flex-wrap: wrap; gap: var(--space-2); }
.tech { display: inline-flex; align-items: center; gap: var(--space-2); min-height: 36px; padding: 0 var(--space-4); border: 1px solid var(--border); border-radius: var(--radius-pill); background: var(--surface-100); font: 600 14px/20px var(--font-sans); }
.tech svg { color: var(--primary); }

.dev-card { display: flex; gap: var(--space-4); align-items: flex-start; padding: var(--space-4); border-radius: var(--radius-lg); background: var(--surface-100); }
.dev-card__photo { width: 72px; height: 72px; flex: none; border-radius: 50%; object-fit: cover; box-shadow: 0 0 0 2px var(--primary); }
.dev-card__name { margin: var(--space-1) 0 0; font: 700 18px/26px var(--font-sans); }
.dev-card__role { margin: 0 0 var(--space-3); font: 400 14px/20px var(--font-sans); color: var(--ink-muted); }
.dev-card__contacts { display: flex; flex-wrap: wrap; gap: var(--space-2); }
.contact { display: inline-flex; align-items: center; gap: var(--space-1); min-height: 28px; padding: 0 var(--space-3); border-radius: var(--radius-pill); background: var(--surface-300); font: 500 13px/1 var(--font-sans); color: var(--ink); text-decoration: none; transition: background-color var(--duration-fast) var(--ease-standard), color var(--duration-fast) var(--ease-standard); }
.contact:hover { background: var(--primary-subtle); color: var(--primary); }

.about__grid { list-style: none; margin: 0; padding: 0; display: grid; grid-template-columns: 1fr 1fr; gap: var(--space-3); }
.person, .support { display: flex; align-items: center; gap: var(--space-3); padding: var(--space-3) var(--space-4); border: 1px solid var(--border); border-radius: var(--radius-lg); background: var(--surface-100); }
.person:hover, .support:hover { transform: translateY(-2px); border-color: var(--border-strong); }
.person__avatar { display: grid; place-items: center; width: 40px; height: 40px; flex: none; border-radius: 50%; background: var(--primary); color: var(--on-primary); font: 700 14px/1 var(--font-sans); }
.person__name, .support__label { display: block; font: 600 14px/20px var(--font-sans); color: var(--ink); }
.person__role { display: block; font: 400 12px/16px var(--font-sans); color: var(--ink-muted); }
.support { align-items: flex-start; padding: var(--space-4); }
.support > svg { flex: none; color: var(--primary); margin-top: 2px; }
.support__value { display: block; margin-top: var(--space-1); font: 400 14px/20px var(--font-sans); color: var(--ink-muted); text-decoration: none; overflow-wrap: anywhere; }
a.support__value:hover { color: var(--primary); }

.about__footer { margin-top: var(--space-6); padding-top: var(--space-4); border-top: 1px solid var(--border); text-align: center; font: 400 12px/18px var(--font-sans); color: var(--ink-muted); }
.about__footer p { margin: 0 0 var(--space-1); }

@media (max-width: 520px) {
  .about__body { padding: var(--space-4); }
  .about__grid { grid-template-columns: 1fr; }
  .dev-card { flex-direction: column; align-items: center; text-align: center; }
  .dev-card__contacts { justify-content: center; }
}
@media (prefers-reduced-motion: reduce) {
  .person:hover, .support:hover { transform: none; }
}
```

---

## 12. Sidebar o menú lateral (opcional)

Solo si el sistema lo necesita (muchos módulos). Cuando hay sidebar, **la marca y el usuario viven en el sidebar**; el header (sección 9) muestra a la izquierda el título de la página y en móvil el botón ☰ que abre el menú. El sidebar siempre es oscuro, en los dos temas.

### Estructura (de arriba a abajo)

| Bloque | Especificación |
| --- | --- |
| Contenedor | Ancho 256px, alto 100dvh, `position: sticky; top: 0`, fondo `sidebar-bg`, borde derecho `sidebar-border`. Tres zonas: marca + usuario (fijas), navegación (con scroll propio), pie (fijo) |
| Marca | Alto 64px, relleno `space-4`: ícono del sistema en cuadro 36px `radius-md` fondo `primary` (ícono `on-primary`) + nombre en `label` 16px 700 `sidebar-ink`. Opcional debajo del nombre: un dato corto (RIF, sede) en `meta` 11px `sidebar-label` |
| Usuario | Separado por `sidebar-border`: avatar 44px con anillo 2px `sidebar-border`; nombre en 14px 700 `sidebar-ink` en MAYÚSCULAS, cortado con «…» en una línea; usuario `@usuario` en 12px `sidebar-label` |
| Grupos | Etiqueta en `overline` (12px, 600, mayúsculas, 0.06em) color `sidebar-label`, margen superior `space-4`: PRINCIPAL, RECURSOS, COMUNICACIÓN… |
| Ítem | Alto 40px, relleno `0 space-3`, `radius-md`, ícono 18px + texto 15px 500 en `sidebar-muted`, separación `space-3`. Hover: fondo `sidebar-hover` y texto `sidebar-ink` |
| Ítem activo | Fondo `sidebar-active-bg`, texto `sidebar-active-ink` 600, ícono `sidebar-indicator`, y barra de 3px `sidebar-indicator` pegada al borde izquierdo del sidebar. `aria-current="page"` |
| Submenú | El ítem padre lleva chevron 16px que gira 180° al abrir; los hijos van con sangría de 28px, alto 36px, texto 14px, unidos por una línea vertical de 1px `sidebar-border`. Se abre solo el grupo del ítem activo al cargar |
| Pie (fijo) | Separado por `sidebar-border`, relleno `space-4`, de arriba a abajo: **interruptor de tema** (☀ · switch · ☾ centrados), botón **Acerca de**, botón **Cerrar sesión** y **versión** |
| Interruptor de tema | Pista 44×24px `radius-pill`: apagado (claro) `sidebar-hover`, encendido (oscuro) `primary`; perilla blanca 18px que se desliza con `duration-base`; íconos sol y luna 16px en `sidebar-muted`, el activo en `sidebar-ink`. `role="switch"` y `aria-checked` |
| Botón Acerca de | Ancho completo, alto 44px, `radius-md`, fondo `sidebar-indicator` al 10%, borde `sidebar-indicator` al 30%, ícono «info» en `sidebar-indicator` + texto 14px 600 `sidebar-ink`. Abre el modal de la sección 11 |
| Botón Cerrar sesión | Igual, con `sidebar-danger`: fondo al 10%, borde al 35%, ícono y texto `sidebar-danger` |
| Versión | Centrada, ícono rama 14px + `v2.0.0` en `meta` color `sidebar-label` |

### Comportamiento y animación

- **Escritorio (≥ 1024px):** fijo a la izquierda; el contenido ocupa el resto (`grid-template-columns: 256px 1fr`).
- **Tableta y móvil (< 1024px):** oculto; el botón ☰ del header lo abre como panel deslizante desde la izquierda (`translateX(-100%) → 0`, `duration-slow`, `ease-enter`) sobre un fondo oscuro que lo cierra al pulsar. Esc también lo cierra. Al elegir un ítem se cierra solo.
- Submenú: altura animada con `grid-template-rows: 0fr → 1fr` en `duration-base` (única excepción a «solo transform/opacity», porque no provoca saltos) y opacidad de los hijos.
- Ítems: transición de fondo y color en `duration-fast`; la barra del activo aparece con `scaleY(0 → 1)`.
- Scroll de la navegación con barra fina `sidebar-border`.
- El tema elegido se guarda en `localStorage` y se aplica con `data-theme` en `<html>` antes de pintar.

### Configuración

```jsx
// src/config/sidebar.config.js
import { LayoutDashboard, Ticket, List, BarChart3, FilePen, Contact, LayoutGrid, Folder, CalendarDays, Megaphone, Mail } from 'lucide-react';

export const sidebarConfig = {
  sistema: { nombre: 'IntraNet RORI', subtitulo: null },   // subtitulo opcional: RIF, sede…
  version: '2.0.0',
  grupos: [
    {
      titulo: 'Principal',
      items: [
        { label: 'Escritorio', icon: LayoutDashboard, href: '/' },
        {
          label: 'Tickets', icon: Ticket,
          children: [
            { label: 'Lista de tickets', icon: List, href: '/tickets' },
            { label: 'Reportes', icon: BarChart3, href: '/tickets/reportes' },
          ],
        },
        { label: 'Solicitudes', icon: FilePen, href: '/solicitudes' },
      ],
    },
    {
      titulo: 'Recursos',
      items: [
        { label: 'Directorio', icon: Contact, href: '/directorio' },
        { label: 'Apps externas', icon: LayoutGrid, href: '/apps' },
        { label: 'Documentos', icon: Folder, href: '/documentos' },
        { label: 'Calendario', icon: CalendarDays, href: '/calendario' },
      ],
    },
    {
      titulo: 'Comunicación',
      items: [
        { label: 'Cartelera', icon: Megaphone, href: '/cartelera' },
        { label: 'Mensajes', icon: Mail, href: '/mensajes' },
      ],
    },
  ],
};
```

### Tema

Usa el mismo hook `useTheme` y el script de `index.html` de la sección 9, así el interruptor del sidebar y el botón del header quedan sincronizados.

### Componente

```jsx
// src/components/AppSidebar.jsx
import { useEffect, useState } from 'react';
import { ChevronDown, Sun, Moon, Info, LogOut, GitBranch } from 'lucide-react';
import { sidebarConfig as c } from '../config/sidebar.config';
import { useTheme } from '../hooks/useTheme';

const isActive = (item, path) => item.href === path || item.children?.some((ch) => ch.href === path);

function NavItem({ item, path, onNavigate }) {
  const active = isActive(item, path);
  const [open, setOpen] = useState(active);
  const Icon = item.icon;

  if (item.children) {
    return (
      <li>
        <button className={`side__item ${active ? 'is-parent-active' : ''}`} aria-expanded={open} onClick={() => setOpen((v) => !v)}>
          <Icon size={18} aria-hidden="true" /> <span>{item.label}</span>
          <ChevronDown size={16} className={`side__chevron ${open ? 'is-open' : ''}`} aria-hidden="true" />
        </button>
        <div className={`side__sub ${open ? 'is-open' : ''}`}>
          <ul>
            {item.children.map((ch) => <NavItem key={ch.href} item={ch} path={path} onNavigate={onNavigate} />)}
          </ul>
        </div>
      </li>
    );
  }
  return (
    <li>
      <a href={item.href} className={`side__item ${active ? 'is-active' : ''}`} aria-current={active ? 'page' : undefined}
         onClick={(e) => { if (onNavigate) { e.preventDefault(); onNavigate(item.href); } }}>
        <Icon size={18} aria-hidden="true" /> <span>{item.label}</span>
      </a>
    </li>
  );
}

export default function AppSidebar({ user, path, onNavigate, onAbout, onLogout, open, onClose }) {
  const [theme, toggleTheme] = useTheme();
  const dark = theme === 'dark';

  useEffect(() => {
    if (!open) return;
    const onKey = (e) => e.key === 'Escape' && onClose?.();
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open, onClose]);

  const navigate = (href) => { onNavigate?.(href); onClose?.(); };

  return (
    <>
      <div className={`side__overlay ${open ? 'is-open' : ''}`} onClick={onClose} aria-hidden="true" />
      <aside className={`side ${open ? 'is-open' : ''}`} aria-label="Menú principal">
        <div className="side__brand">
          <span className="side__logo" aria-hidden="true">{c.sistema.nombre[0]}</span>
          <span>
            <span className="side__name">{c.sistema.nombre}</span>
            {c.sistema.subtitulo && <span className="side__subtitle">{c.sistema.subtitulo}</span>}
          </span>
        </div>

        {user && (
          <div className="side__user">
            <img className="side__avatar" src={user.photo} alt="" />
            <span className="side__user-text">
              <span className="side__user-name" title={user.name}>{user.name}</span>
              <span className="side__user-handle">@{user.username}</span>
            </span>
          </div>
        )}

        <nav className="side__nav">
          {c.grupos.map((g) => (
            <div key={g.titulo} className="side__group">
              <p className="side__group-title">{g.titulo}</p>
              <ul>{g.items.map((it) => <NavItem key={it.label} item={it} path={path} onNavigate={navigate} />)}</ul>
            </div>
          ))}
        </nav>

        <div className="side__footer">
          <div className="side__theme">
            <Sun size={16} aria-hidden="true" className={!dark ? 'is-on' : ''} />
            <button className={`switch ${dark ? 'is-on' : ''}`} role="switch" aria-checked={dark} aria-label="Tema oscuro" onClick={toggleTheme}>
              <span className="switch__knob" />
            </button>
            <Moon size={16} aria-hidden="true" className={dark ? 'is-on' : ''} />
          </div>
          <button className="side__btn side__btn--info" onClick={onAbout}><Info size={16} aria-hidden="true" /> Acerca de</button>
          <button className="side__btn side__btn--danger" onClick={onLogout}><LogOut size={16} aria-hidden="true" /> Cerrar sesión</button>
          <p className="side__version"><GitBranch size={14} aria-hidden="true" /> v{c.version}</p>
        </div>
      </aside>
    </>
  );
}
```

Diseño de página con sidebar:

```jsx
<div className="layout">
  <AppSidebar user={user} path={location.pathname} onNavigate={navigate}
              onAbout={() => setAbout(true)} onLogout={logout}
              open={menuOpen} onClose={() => setMenuOpen(false)} />
  <div className="layout__main">
    <AppHeader … />            {/* con botón ☰ visible solo < 1024px: onClick={() => setMenuOpen(true)} */}
    <main className="layout__content">…</main>
    <AppFooter />
  </div>
  <AboutModal open={about} onClose={() => setAbout(false)} />
</div>
```

### Estilos

```css
.layout { display: grid; grid-template-columns: 256px 1fr; min-height: 100dvh; }
.layout__main { min-width: 0; display: flex; flex-direction: column; }
.layout__content { flex: 1; padding: var(--space-6) var(--space-8); }

.side {
  position: sticky; top: 0; height: 100dvh; width: 256px;
  padding-bottom: env(safe-area-inset-bottom);
  display: flex; flex-direction: column;
  background: var(--sidebar-bg); border-right: 1px solid var(--sidebar-border);
  color: var(--sidebar-muted); font-family: var(--font-sans);
}

.side__brand { flex: none; display: flex; align-items: center; gap: var(--space-3); height: 64px; padding: 0 var(--space-4); border-bottom: 1px solid var(--sidebar-border); }
.side__logo { display: grid; place-items: center; width: 36px; height: 36px; flex: none; border-radius: var(--radius-md); background: var(--primary); color: var(--on-primary); font: 700 16px/1 var(--font-sans); }
.side__name { display: block; font: 700 16px/22px var(--font-sans); color: var(--sidebar-ink); }
.side__subtitle { display: block; font: 500 11px/14px var(--font-mono); color: var(--sidebar-label); }

.side__user { flex: none; display: flex; align-items: center; gap: var(--space-3); padding: var(--space-4); border-bottom: 1px solid var(--sidebar-border); }
.side__avatar { width: 44px; height: 44px; flex: none; border-radius: 50%; object-fit: cover; box-shadow: 0 0 0 2px var(--sidebar-border); }
.side__user-text { min-width: 0; }
.side__user-name { display: block; overflow: hidden; white-space: nowrap; text-overflow: ellipsis; font: 700 14px/20px var(--font-sans); text-transform: uppercase; color: var(--sidebar-ink); }
.side__user-handle { display: block; font: 500 12px/16px var(--font-sans); text-transform: uppercase; color: var(--sidebar-label); }

.side__nav { flex: 1; overflow-y: auto; padding: var(--space-2) var(--space-3) var(--space-4); scrollbar-width: thin; scrollbar-color: var(--sidebar-border) transparent; }
.side__nav ul { list-style: none; margin: 0; padding: 0; display: grid; gap: 2px; }
.side__group-title { margin: var(--space-4) 0 var(--space-2) var(--space-2); font: 600 12px/16px var(--font-sans); letter-spacing: 0.06em; text-transform: uppercase; color: var(--sidebar-label); }

.side__item {
  position: relative; display: flex; align-items: center; gap: var(--space-3);
  width: 100%; min-height: 40px; padding: 0 var(--space-3);
  border: 0; border-radius: var(--radius-md); background: transparent;
  font: 500 15px/20px var(--font-sans); color: var(--sidebar-muted); text-align: left; text-decoration: none; cursor: pointer;
  transition: background-color var(--duration-fast) var(--ease-standard), color var(--duration-fast) var(--ease-standard);
}
.side__item:hover { background: var(--sidebar-hover); color: var(--sidebar-ink); }
.side__item:focus-visible { outline: 2px solid var(--sidebar-indicator); outline-offset: -2px; }
.side__item.is-active, .side__item.is-parent-active { color: var(--sidebar-ink); }
.side__item.is-active { background: var(--sidebar-active-bg); color: var(--sidebar-active-ink); font-weight: 600; }
.side__item.is-active svg { color: var(--sidebar-indicator); }
.side__item.is-active::before {
  content: ""; position: absolute; left: calc(-1 * var(--space-3)); top: 6px; bottom: 6px; width: 3px;
  border-radius: 0 3px 3px 0; background: var(--sidebar-indicator);
  animation: indicator-in var(--duration-base) var(--ease-enter) both;
}
@keyframes indicator-in { from { transform: scaleY(0); } to { transform: scaleY(1); } }

.side__chevron { margin-left: auto; transition: transform var(--duration-base) var(--ease-standard); }
.side__chevron.is-open { transform: rotate(180deg); }

.side__sub { display: grid; grid-template-rows: 0fr; transition: grid-template-rows var(--duration-base) var(--ease-standard); }
.side__sub.is-open { grid-template-rows: 1fr; }
.side__sub > ul { overflow: hidden; margin-left: 20px; padding-left: var(--space-2); border-left: 1px solid var(--sidebar-border); opacity: 0; transition: opacity var(--duration-base) var(--ease-standard); }
.side__sub.is-open > ul { opacity: 1; padding-top: 2px; }
.side__sub .side__item { min-height: 36px; font-size: 14px; }
.side__sub .side__item.is-active::before { left: calc(-1 * var(--space-2) - 1px); }

.side__footer { flex: none; display: grid; gap: var(--space-2); padding: var(--space-4); border-top: 1px solid var(--sidebar-border); }
.side__theme { display: flex; align-items: center; justify-content: center; gap: var(--space-2); padding-bottom: var(--space-2); color: var(--sidebar-muted); }
.side__theme svg { transition: color var(--duration-base) var(--ease-standard); }
.side__theme svg.is-on { color: var(--sidebar-ink); }

.switch { position: relative; width: 44px; height: 24px; padding: 0; border: 0; border-radius: var(--radius-pill); background: var(--sidebar-hover); cursor: pointer; transition: background-color var(--duration-base) var(--ease-standard); }
.switch.is-on { background: var(--primary); }
.switch__knob { position: absolute; top: 3px; left: 3px; width: 18px; height: 18px; border-radius: 50%; background: #ffffff; box-shadow: 0 1px 2px rgba(0, 0, 0, 0.3); transition: transform var(--duration-base) var(--ease-standard); }
.switch.is-on .switch__knob { transform: translateX(20px); }
.switch:focus-visible { outline: 2px solid var(--sidebar-indicator); outline-offset: 2px; }

.side__btn {
  display: flex; align-items: center; gap: var(--space-3);
  width: 100%; min-height: 44px; padding: 0 var(--space-4);
  border-radius: var(--radius-md); font: 600 14px/20px var(--font-sans); cursor: pointer;
  transition: background-color var(--duration-fast) var(--ease-standard), transform var(--duration-fast) var(--ease-standard);
}
.side__btn:active { transform: scale(0.98); }
.side__btn--info { border: 1px solid rgb(56 189 248 / 0.3); background: rgb(56 189 248 / 0.1); color: var(--sidebar-ink); }
.side__btn--info svg { color: var(--sidebar-indicator); }
.side__btn--info:hover { background: rgb(56 189 248 / 0.18); }
.side__btn--danger { border: 1px solid rgb(248 113 113 / 0.35); background: rgb(248 113 113 / 0.1); color: var(--sidebar-danger); }
.side__btn--danger:hover { background: rgb(248 113 113 / 0.18); }
.side__btn:focus-visible { outline: 2px solid var(--sidebar-indicator); outline-offset: 2px; }

.side__version { display: flex; align-items: center; justify-content: center; gap: var(--space-1); margin: var(--space-2) 0 0; font: 500 12px/16px var(--font-mono); color: var(--sidebar-label); }

.side__overlay { display: none; }

@media (max-width: 1023px) {
  .layout { grid-template-columns: 1fr; }
  .side { position: fixed; left: 0; top: 0; z-index: 90; transform: translateX(-100%); transition: transform var(--duration-slow) var(--ease-enter); box-shadow: var(--shadow-md); }
  .side.is-open { transform: none; }
  .side__overlay { display: block; position: fixed; inset: 0; z-index: 80; background: rgba(2, 6, 23, 0.55); opacity: 0; pointer-events: none; transition: opacity var(--duration-base) var(--ease-standard); }
  .side__overlay.is-open { opacity: 1; pointer-events: auto; }
  .layout__content { padding: var(--space-4); }
}
@media (prefers-reduced-motion: reduce) {
  .side, .side__sub, .side__sub > ul, .switch__knob, .side__chevron { transition: none; }
  .side__item.is-active::before { animation: none; }
}
```

---

## 13. Diseño responsive

**Toda la aplicación es responsive, sin excepción.** Cada pantalla se diseña primero para móvil (*mobile-first*) y se amplía hacia escritorio. Ninguna pantalla se entrega sin probarla en los seis anchos de referencia.

### Puntos de quiebre

| Nombre | Desde | Dispositivo típico | Columnas | Margen lateral | Separación |
| --- | --- | --- | --- | --- | --- |
| `xs` | 0 | Teléfono pequeño (320–374px) | 4 | `space-4` (16px) | `space-3` |
| `sm` | 375px | Teléfono estándar | 4 | `space-4` (16px) | `space-4` |
| `md` | 640px | Teléfono horizontal, tableta pequeña | 8 | `space-6` (24px) | `space-4` |
| `lg` | 1024px | Tableta horizontal, laptop | 12 | `space-8` (32px) | `space-6` |
| `xl` | 1280px | Escritorio | 12 | `space-8` (32px) | `space-6` |
| `2xl` | 1536px | Monitor grande | 12 | auto (contenido centrado, máx. 1440px) | `space-8` |

Media queries con estos mismos valores: `640px`, `1024px`, `1280px`, `1536px`. Se escriben de preferencia con `min-width` (de menor a mayor); `max-width: 639px` o `1023px` solo para transformar un componente en móvil (tablas a tarjetas, sidebar a panel deslizante).

### Reglas generales

1. **Meta viewport obligatorio:** `<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">`. Nunca se bloquea el zoom.
2. **Sin scroll horizontal** en ningún ancho, desde 320px. Todo contenedor flexible lleva `min-width: 0`.
3. **Anchos fluidos:** porcentajes, `fr`, `minmax()` y `clamp()`; nunca anchos fijos en px para contenedores.
4. **Objetivos táctiles de 44×44px** como mínimo, con `space-2` entre ellos. En pantallas táctiles no hay acciones que solo aparezcan con hover.
5. **Texto legible:** el cuerpo nunca baja de 16px en móvil (evita el zoom automático de iOS en campos); línea de lectura de 45–75 caracteres (`max-width: 70ch`).
6. **Tipografía fluida** solo en títulos grandes: `display` usa `clamp(28px, 4vw + 12px, 36px)` y `title` `clamp(20px, 2vw + 12px, 24px)`.
7. **Imágenes:** `max-width: 100%; height: auto`, con `width`/`height` o `aspect-ratio` declarados para no provocar saltos; formatos WebP/AVIF y `loading="lazy"` fuera de la primera pantalla.
8. **Zonas seguras** en teléfonos con muesca: `env(safe-area-inset-*)` en header, sidebar, barras fijas y modales.
9. **Altura de pantalla** con `100dvh` (no `100vh`) para que las barras del navegador móvil no corten el contenido.
10. **Orientación horizontal** en teléfonos: header y modales siguen siendo usables con 360px de alto.
11. **El footer siempre al fondo.** La página se monta como columna flexible de alto mínimo `100dvh`, con el contenido creciendo para ocupar el espacio sobrante. Sin esto, una pantalla con poco contenido —un formulario de cuatro campos, una ficha corta— deja el footer a media altura y debajo una franja de fondo vacío que **crece con el monitor**: unos 120px en una pantalla de 900 de alto y más de 600px en una de 1440. El defecto se escapa con facilidad porque sólo aparece en las pantallas cortas; las largas se ven bien. El esqueleto está en la primera utilidad CSS de esta misma sección.

### Comportamiento de cada componente

| Componente | Móvil (< 640px) | Tableta (640–1023px) | Escritorio (≥ 1024px) |
| --- | --- | --- | --- |
| Header (9) | Logo + nombre de la app cortado + tema + avatar | Sin subtítulo; con nombre y cargo | Completo |
| Sidebar (12) | Oculto; panel deslizante con ☰ | Oculto; panel deslizante con ☰ | Fijo, 256px |
| Contenido | 1 columna, margen 16px | 2 columnas donde aplique, margen 24px | Grilla de 12, margen 32px, máx. 1440px |
| Tarjetas | Apiladas, ancho completo | 2 por fila | 3–4 por fila (`auto-fill, minmax(280px, 1fr)`) |
| Tablas | Se convierten en **tarjetas apiladas** (cada fila es una tarjeta con etiqueta: valor) o scroll horizontal dentro de su contenedor con la 1.ª columna fija | Scroll horizontal dentro del contenedor | Tabla completa |
| Formularios | 1 columna; botones a ancho completo, el primario abajo | 2 columnas para campos cortos | 2–3 columnas; botones alineados a la derecha |
| Modales / Acerca de (11) | **Hoja inferior** a pantalla completa (sube desde abajo, esquinas superiores `radius-lg`), cabecera fija | Centrado, ancho 90% | Centrado, ancho fijo (540px) |
| Menús desplegables | Ancho completo bajo el disparador o como hoja inferior | Flotante | Flotante |
| Footer (10) | 1 columna | 2 columnas | 4 columnas |
| Acciones de página | Barra inferior fija con la acción principal (con zona segura) | En la cabecera de la página | En la cabecera de la página |
| Gráficas | Ancho completo, leyenda debajo, menos marcas en ejes | Leyenda a la derecha si cabe | Completa |

### Utilidades CSS

```css
/* Esqueleto de página: header arriba, contenido elástico, footer al fondo.
   `100dvh` y no `100vh`: en el móvil las barras del navegador aparecen y
   desaparecen, y con `vh` el footer queda cortado o sobra espacio.
   `overflow-x: clip` y no `hidden`: `hidden` convierte al body en contenedor
   de desplazamiento y rompe el `position: sticky` del header. */
html { min-height: 100%; }

body {
  display: flex;
  flex-direction: column;
  min-height: 100dvh;
  overflow-x: clip;
}

main { flex: 1 0 auto; min-width: 0; }
.app-header, .app-footer { flex: none; }

/* Contenedor de página */
.container {
  width: 100%;
  max-width: 1440px;
  margin-inline: auto;
  padding-inline: max(var(--space-4), env(safe-area-inset-left));
}
@media (min-width: 640px)  { .container { padding-inline: var(--space-6); } }
@media (min-width: 1024px) { .container { padding-inline: var(--space-8); } }

/* Grilla de tarjetas: se acomoda sola a cualquier ancho */
.grid-auto {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(min(280px, 100%), 1fr));
  gap: var(--space-4);
}
@media (min-width: 1024px) { .grid-auto { gap: var(--space-6); } }

/* Grilla de 12 columnas */
.grid-12 { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: var(--space-4); }
@media (min-width: 640px)  { .grid-12 { grid-template-columns: repeat(8, minmax(0, 1fr)); } }
@media (min-width: 1024px) { .grid-12 { grid-template-columns: repeat(12, minmax(0, 1fr)); gap: var(--space-6); } }
.span-full { grid-column: 1 / -1; }
@media (min-width: 1024px) { .lg\:span-4 { grid-column: span 4; } .lg\:span-6 { grid-column: span 6; } .lg\:span-8 { grid-column: span 8; } }

/* Pila vertical que pasa a fila */
.stack { display: flex; flex-direction: column; gap: var(--space-3); }
@media (min-width: 640px) { .stack--row-md { flex-direction: row; align-items: center; } }

/* Formularios */
.form-grid { display: grid; grid-template-columns: 1fr; gap: var(--space-4); }
@media (min-width: 640px) { .form-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
.form-grid .span-full { grid-column: 1 / -1; }
.form-actions { display: flex; flex-direction: column-reverse; gap: var(--space-2); }
.form-actions .btn { width: 100%; }
@media (min-width: 640px) {
  .form-actions { flex-direction: row; justify-content: flex-end; }
  .form-actions .btn { width: auto; }
}
input, select, textarea { font-size: 16px; } /* evita el zoom de iOS */

/* Tabla que se vuelve tarjetas en móvil */
.table-wrap { overflow-x: auto; border: 1px solid var(--border); border-radius: var(--radius-lg); }
@media (max-width: 639px) {
  .table--cards thead { display: none; }
  .table--cards, .table--cards tbody, .table--cards tr, .table--cards td { display: block; width: 100%; }
  .table--cards tr { margin-bottom: var(--space-3); padding: var(--space-3) var(--space-4); border: 1px solid var(--border); border-radius: var(--radius-lg); background: var(--surface-200); }
  .table--cards td { display: flex; justify-content: space-between; gap: var(--space-4); padding: var(--space-1) 0; border: 0; text-align: right; }
  .table--cards td::before { content: attr(data-label); font-weight: 600; color: var(--ink-muted); text-align: left; }
  .table-wrap:has(.table--cards) { border: 0; overflow: visible; }
}

/* Títulos fluidos */
.display { font-size: clamp(28px, 4vw + 12px, 36px); line-height: 1.2; }
.title   { font-size: clamp(20px, 2vw + 12px, 24px); line-height: 1.3; }
.prose   { max-width: 70ch; }

/* Barra de acción fija en móvil */
.mobile-action-bar {
  position: sticky; bottom: 0; z-index: 40;
  display: flex; gap: var(--space-2);
  padding: var(--space-3) var(--space-4) max(var(--space-3), env(safe-area-inset-bottom));
  background: var(--surface-200); border-top: 1px solid var(--border); box-shadow: var(--shadow-md);
}
.mobile-action-bar .btn { flex: 1; }
@media (min-width: 640px) { .mobile-action-bar { display: none; } }

/* Modal «Acerca de» como hoja inferior en móvil */
@media (max-width: 639px) {
  .about__backdrop { place-items: end stretch; padding: 0; }
  .about {
    width: 100%; max-height: 92dvh;
    border-radius: var(--radius-lg) var(--radius-lg) 0 0;
    padding-bottom: env(safe-area-inset-bottom);
    animation-name: sheet-in;
  }
}
@keyframes sheet-in { from { transform: translateY(100%); } to { transform: none; } }

/* Medios fluidos */
img, video { max-width: 100%; height: auto; }

/* Sin hover en pantallas táctiles */
@media (hover: none) {
  .card.interactive:hover, .person:hover, .support:hover { transform: none; }
}
```

Tabla con tarjetas en móvil — cada celda lleva su etiqueta:

```jsx
<div className="table-wrap">
  <table className="table table--cards">
    <thead><tr><th>Ticket</th><th>Estado</th><th>Fecha</th></tr></thead>
    <tbody>
      {tickets.map((t) => (
        <tr key={t.id}>
          <td data-label="Ticket">{t.titulo}</td>
          <td data-label="Estado">{t.estado}</td>
          <td data-label="Fecha">{t.fecha}</td>
        </tr>
      ))}
    </tbody>
  </table>
</div>
```

Hook para decidir en JavaScript (por ejemplo, mostrar hoja inferior o menú flotante):

```jsx
// src/hooks/useBreakpoint.js
import { useEffect, useState } from 'react';

const queries = { md: '(min-width: 640px)', lg: '(min-width: 1024px)', xl: '(min-width: 1280px)' };

export function useBreakpoint() {
  const read = () => Object.fromEntries(Object.entries(queries).map(([k, q]) => [k, matchMedia(q).matches]));
  const [bp, setBp] = useState(read);
  useEffect(() => {
    const lists = Object.values(queries).map((q) => matchMedia(q));
    const on = () => setBp(read());
    lists.forEach((l) => l.addEventListener('change', on));
    return () => lists.forEach((l) => l.removeEventListener('change', on));
  }, []);
  return { ...bp, isMobile: !bp.md, isTablet: bp.md && !bp.lg, isDesktop: bp.lg };
}
```

### Cómo se prueba

En las herramientas de desarrollador del navegador, cada pantalla se revisa en **320, 375, 768, 1024, 1280 y 1440px**, en tema claro y oscuro, y además en un teléfono real (Android e iPhone si es posible) en vertical y horizontal. Se verifica: sin scroll horizontal, nada cortado, botones alcanzables con el pulgar, textos sin zoom forzado y modales usables con el teclado del móvil abierto.

---

## 14. Variables CSS (copiar en `src/styles/tokens.css`)

```css
:root,
[data-theme="light"] {
  --surface-100: #f8fafc;
  --surface-200: #ffffff;
  --surface-300: #e8ecf1;
  --ink: #0f172a;
  --ink-muted: #475569;
  --border: #e2e8f0;
  --border-strong: #64748b;
  --navy: #0f172a;
  --on-navy: #ffffff;
  --on-navy-muted: #bfdbfe;
  --primary: #0369a1;
  --on-primary: #ffffff;
  --primary-subtle: #e0f2fe;
  --ring: var(--primary);
  --danger: #dc2626;
  --on-danger: #ffffff;
  --footer-bg: #0f172a;
  --footer-ink: #f8fafc;
  --footer-muted: #cbd5e1;
  --footer-border: #1e293b;
  --footer-hover: #1e293b;
  --sidebar-bg: #0f172a;
  --sidebar-border: #1e293b;
  --sidebar-ink: #f8fafc;
  --sidebar-muted: #cbd5e1;
  --sidebar-label: #94a3b8;
  --sidebar-hover: #1e293b;
  --sidebar-active-bg: #0c4a6e;
  --sidebar-active-ink: #e0f2fe;
  --sidebar-indicator: #38bdf8;
  --sidebar-danger: #f87171;
  --gradient-brand: linear-gradient(135deg, #0369a1 0%, #0f172a 100%);
  --shadow-sm: 0 1px 2px rgba(15, 23, 42, 0.06);
  --shadow-md: 0 8px 24px rgba(15, 23, 42, 0.12);
  color-scheme: light;
}

[data-theme="dark"] {
  --surface-100: #0b1220;
  --surface-200: #131c2e;
  --surface-300: #1e293b;
  --ink: #f1f5f9;
  --ink-muted: #94a3b8;
  --border: #263247;
  --border-strong: #64748b;
  --navy: #1e3a8a;
  --on-navy: #ffffff;
  --on-navy-muted: #bfdbfe;
  --primary: #38bdf8;
  --on-primary: #0b1220;
  --primary-subtle: #0c2a43;
  --danger: #f87171;
  --on-danger: #0b1220;
  --footer-bg: #131c2e;
  --footer-ink: #f1f5f9;
  --footer-muted: #94a3b8;
  --footer-border: #263247;
  --footer-hover: #1e293b;
  --sidebar-bg: #131c2e;
  --sidebar-border: #263247;
  --sidebar-ink: #f1f5f9;
  --sidebar-active-bg: #0c2a43;
  --gradient-brand: linear-gradient(135deg, #0369a1 0%, #1e3a8a 100%);
  --shadow-sm: none;
  --shadow-md: 0 8px 24px rgba(0, 0, 0, 0.5);
  color-scheme: dark;
}

/* Sigue el tema del sistema operativo si la app no fija uno */
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    --surface-100: #0b1220;
    --surface-200: #131c2e;
    --surface-300: #1e293b;
    --ink: #f1f5f9;
    --ink-muted: #94a3b8;
    --border: #263247;
    --navy: #1e3a8a;
    --primary: #38bdf8;
    --on-primary: #0b1220;
    --primary-subtle: #0c2a43;
    --danger: #f87171;
    --on-danger: #0b1220;
    --footer-bg: #131c2e;
    --footer-ink: #f1f5f9;
    --footer-muted: #94a3b8;
    --footer-border: #263247;
    --sidebar-bg: #131c2e;
    --sidebar-border: #263247;
    --sidebar-ink: #f1f5f9;
    --sidebar-active-bg: #0c2a43;
    --gradient-brand: linear-gradient(135deg, #0369a1 0%, #1e3a8a 100%);
    --shadow-sm: none;
    --shadow-md: 0 8px 24px rgba(0, 0, 0, 0.5);
    color-scheme: dark;
  }
}

:root {
  --font-sans: "Plus Jakarta Sans", system-ui, -apple-system, "Segoe UI", sans-serif;
  --font-mono: "IBM Plex Mono", ui-monospace, "SFMono-Regular", monospace;

  --space-1: 4px;
  --space-2: 8px;
  --space-3: 12px;
  --space-4: 16px;
  --space-6: 24px;
  --space-8: 32px;

  --radius-sm: 4px;
  --radius-md: 8px;
  --radius-lg: 12px;
  --radius-pill: 999px;

  --duration-fast: 120ms;
  --duration-base: 200ms;
  --duration-slow: 320ms;
  --ease-standard: cubic-bezier(0.2, 0, 0, 1);
  --ease-enter: cubic-bezier(0.05, 0.7, 0.1, 1);
  --ease-exit: cubic-bezier(0.3, 0, 1, 1);
  --stagger: 40ms;
}

body {
  margin: 0;
  background: var(--surface-100);
  color: var(--ink);
  font: 400 16px/24px var(--font-sans);
}

:focus-visible {
  outline: 2px solid var(--ring);
  outline-offset: 2px;
}

```

Para cambiar de tema desde React: `document.documentElement.dataset.theme = 'dark'` (o `'light'`).

---

## 15. Checklist antes de entregar una pantalla

- [ ] Solo variables, ningún hex suelto en componentes
- [ ] Revisada en tema claro **y** oscuro
- [ ] Texto 4.5:1; bordes de control e íconos 3:1
- [ ] Si hay degradados: medidos leyendo `backgroundImage`, con **cada parada** comprobada contra el texto (en `backgroundColor` no aparecen, y el comprobador da un 1:1 falso)
- [ ] Foco visible en todo lo interactivo; navegable con teclado
- [ ] Objetivos táctiles ≥ 44×44px
- [ ] Sin emojis como íconos; botones de solo ícono con `aria-label`
- [ ] El footer queda al fondo de la ventana también en las pantallas con poco contenido (regla 11 de la sección 13)
- [ ] Responsive probado en 320, 375, 768, 1024, 1280 y 1440px y en un teléfono real: sin scroll horizontal, nada cortado, tablas legibles, modales como hoja inferior en móvil
- [ ] Animaciones solo con `opacity`/`transform`, ≤ 400ms, y `prefers-reduced-motion` respetado
- [ ] Las animaciones **están aplicadas**, no sólo declaradas: declarar `@keyframes` y la clase y luego no ponérsela a nada deja la pantalla apareciendo de golpe
- [ ] Escalonados cortados en el octavo elemento
- [ ] Contadores sólo sobre cantidades, nunca sobre códigos ni identificadores, y con la columna en `tabular-nums`
- [ ] Cada tabla con su título **dentro de la misma tarjeta**, y títulos de sección con su marca de acento
- [ ] Header con logo + título de la aplicación a la izquierda; botón de tema y avatar + nombre + cargo a la derecha
- [ ] Footer con los datos del proyecto en `footer.config.js` (desarrollador actualizado) **y su avatar puesto**
- [ ] Si hay sidebar: grupos y rutas en `sidebar.config.js`, interruptor de tema, Acerca de, Cerrar sesión y versión en el pie
- [ ] Modal «Acerca de» con versión, build, tecnologías y colaboradores actualizados en `about.config.js`
