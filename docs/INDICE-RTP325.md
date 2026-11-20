# Petición a sistemas: un índice por fecha sobre `RORIVENTAA.RTP325`

**Qué se pide:** un camino de acceso por fecha sobre el archivo de detalle de
facturas. Una sentencia, sin cambiar el archivo ni ningún programa.

**Qué se gana:** una consulta que hoy tarda **entre veinte segundos y un
minuto** pasa a tardar
**décimas**, y deja de leer 6,6 millones de filas cada vez que alguien pide un
informe.

---

## El problema, medido

Medición del 19/11/2026 contra producción, pidiendo **un solo día**
(18/11/2026) a los tres archivos del documento de venta:

| Archivo | Filas en el archivo | Camino de acceso por fecha | Tardó |
|---|---:|---|---:|
| `RORILBRA.IDP210` | 3.149.280 | **sí** — `INDICE1` y el lógico `IDP210V0L1` | **0,06 s** |
| `RORIVENTAA.IDP116N` | 444.044 | no, pero el archivo es pequeño | **0,18 s** |
| `RORIVENTAA.RTP325` | **6.595.139** | **ninguno** | **17 – 22 s** |

`RTP325` no tiene ni un índice SQL ni un archivo lógico por fecha. Lo
comprobamos contra `QSYS2.SYSINDEXES`, `QSYS2.SYSKEYS` y `QSYS2.SYSTABLES`:

```
  --- RTP325 (RORIVENTAA.RTP325) ---
    índices SQL: ninguno
    archivos lógicos que empiezan igual: ninguno
```

### La prueba de que es el camino de acceso y no el tamaño

Dos medidas que lo dejan sin ninguna otra explicación posible:

**1. El tiempo no depende de cuántas filas se piden.**

| Lo que se pidió | Filas que devolvió | Tardó |
|---|---:|---:|
| un día | 449 | 22,22 s |
| un mes entero | 8.547 | 17,11 s |

Diecinueve veces más datos **en el mismo tiempo**. Eso sólo pasa cuando el
servidor lee el archivo entero las dos veces y descarta a mano lo que no
cumple: el filtro de fecha no le sirve para nada.

**2. En cuanto el filtro puede usar un camino de acceso, el tiempo se
desploma.**

| Filtro | Tardó |
|---|---:|
| sólo por fecha | 22,22 s |
| por fecha **y tienda** (`RCDTDA`) | **1,08 s** |
| por tienda, tipo y número de documento | **0,12 s** |

El archivo sí tiene por dónde entrar — por tienda y por documento— y por ahí va
doscientas veces más rápido. Lo que no tiene es por dónde entrar por fecha, que
es justamente como se pide un informe.

> También se descartaron, midiéndolos uno a uno, el `GROUP BY` de la consulta
> (6,76 s **con** agrupar contra 7,65 s **sin** agrupar: no es eso), el filtro
> `RTPDOC IN (...)` y el campo del siglo. Ninguno de los tres explica nada.

---

## Lo que se pide, exactamente

```sql
CREATE INDEX RORIVENTAA.RTP325X1
    ON RORIVENTAA.RTP325 (RFCEDC, RFAÑDC, RFMSDC, RFDIDC, RCDTDA, RTPDOC, RNMDOC);
```

Son los cuatro campos de la fecha —siglo, año, mes y día— seguidos de la clave
del documento. Ese orden es el que importa: así el mismo índice sirve para
filtrar por un rango de días **y** para agrupar por documento, que es
exactamente lo que hace el informe.

> **Cuidado con la eñe.** El campo se llama `RFAÑDC`, con Ñ. Si la sentencia se
> escribe desde un editor en UTF-8 y se manda sin convertir, el AS400 no
> reconoce el nombre. Desde una sesión 5250 o desde Run SQL Scripts de ACS no
> hay problema.

### Si se prefiere un archivo lógico en vez de un índice SQL

Es equivalente para lo que nos hace falta, y encaja con cómo está hecho el
resto: `IDP210` ya se apoya en `IDP210V0L1`, que es exactamente esto mismo
—año, tipo, código, mes, día, documento— sobre el encabezado. Lo que pedimos es
el hermano de ése para el detalle.

---

## Lo que esto cuesta y lo que no

| | |
|---|---|
| ¿Cambia el archivo `RTP325`? | **No.** Un índice es un objeto aparte. |
| ¿Hay que recompilar algún programa? | **No.** Ninguno lo nombra; el optimizador lo usa solo. |
| ¿Afecta a lo que ya funciona? | Sólo para bien: cualquier consulta por fecha sobre ese archivo mejora. |
| ¿Qué ocupa? | Siete campos cortos sobre 6,6 millones de filas. Del orden de 150 MB. |
| ¿Qué cuesta al grabar? | Una entrada de índice por línea de factura nueva. Es lo mismo que ya paga `IDP210` por los suyos. |

---

## Mientras tanto

La aplicación funciona: el barrido tarda lo mismo para un día que para un mes,
así que un informe mensual sale en el mismo tiempo que uno de un día y la
pantalla avisa de que `RTP325` es el paso largo. Lo que sí cambia es la carga
del servidor: el mismo mes tardó **9,67 s el 19/11 y 42,03 s el 20/11**. No
está roto; está pagando entre veinte segundos y un minuto por algo que debería
costar décimas.

Lo que **no** se puede hacer mientras tanto es quitar la espera reescribiendo la
consulta. Se probaron las seis variantes razonables y ninguna mejora: sin
camino de acceso por fecha, el servidor tiene que mirar las 6,6 millones de
filas, y eso no depende de cómo esté escrito el `SELECT`.

---

*Medición reproducible: `php cli\diagnostico-consultas.php --fecha=2026-11-18`
en `reporte-auditoria-ventas`. Imprime los índices de cada archivo y cronometra
las nueve variantes.*
