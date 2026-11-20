# Auditoría de formas de pago, leída del AS400 en vivo

Esta aplicación contesta una pregunta que hoy no contesta nadie: **¿cuadra cada
factura con lo que se cobró por ella?**

Un documento del AS400 vive repartido en tres archivos, y los tres tienen que
contar lo mismo:

| Archivo | Qué guarda | Dice |
|---|---|---|
| `RORILBRA.IDP210` | el **encabezado** | cuánto se vendió |
| `RORIVENTAA.RTP325` | el **detalle** | qué se vendió |
| `RORIVENTAA.IDP116N` | los **pagos** | con qué se pagó |

Si la suma de las formas de pago no llega al total de la factura, falta un pago
por asentar: dinero cobrado que no está registrado, o un financiamiento que
nadie anotó.

Nadie lo mira a mano. No porque no importe, sino porque son del orden de 3.800
documentos al mes contra 5.200 líneas de pago.

---

## 1. Qué cambia respecto de la versión que ya existía

En `ventas-ia-agentes` ya hay una auditoría equivalente. **El juicio es el
mismo, portado entero y con sus justificaciones**; lo que cambia es de dónde
salen los datos y cómo se usa.

| | `ventas-ia-agentes` | esta aplicación |
|---|---|---|
| Origen | MySQL, cargado por el ETL de madrugada | **AS400 en vivo** |
| Retraso | lo que no se cargó, no se audita | ninguno |
| Cómo se pide | `php cli/auditoria-pagos.php --mes=2026-11` y después un `.ps1` | una pantalla con dos fechas |
| Se ve antes de descargar | no | **sí** |
| Excel | PowerShell manejando Excel por COM | PHP escribiendo el `.xlsx` |
| Hace falta Excel instalado | sí | no |

Las dos consecuencias que importan:

1. **Desaparece el aviso «estos días no están cargados».** Aquí se pregunta al
   AS400 y contesta el AS400, así que ese aviso se ha quitado en lugar de
   dejarlo diciendo algo que ya no es verdad. Lo que sí queda es el aviso del
   futuro: pedir noviembre el día 19 no deja once días sin auditar, deja once
   días sin ocurrir, y decirlo de otra forma hace que quien lea el informe se
   pregunte qué se le está ocultando.

2. **El Excel ya no necesita Excel.** Un `.xlsx` es un ZIP con unos XML dentro,
   y `servicios/LibroExcel.php` lo escribe directamente. Office en el servidor
   web no estaba, ni tenía sentido ponerlo: dos personas pidiendo el informe a
   la vez son dos instancias de Excel peleándose, y la que pierde deja un
   `EXCEL.EXE` colgado que nadie cierra.

---

## 2. Cómo está armado

```
index.php
  └── vistas/plantilla.php
        ├── vistas/modulos/periodo.php     el formulario: dos fechas y los atajos
        └── vistas/modulos/resultado.php   los huecos que llena el navegador

vistas/js/auditoria.js   pide, pinta y filtra. NO calcula nada.

php/auditoria/consultar.php   POST desde+hasta  ->  JSON con el informe
php/auditoria/excel.php       GET  token        ->  el .xlsx

servicios/Periodo.php         valida el rango y lo parte en meses
servicios/Auditoria.php       EL JUICIO: el total, las tolerancias, los avisos
servicios/CacheAuditoria.php  guarda la corrida para que el Excel sea lo visto
servicios/LibroExcel.php      escribe un .xlsx sin dependencias
servicios/InformeExcel.php    las cinco pestañas del informe

modelos/auditoria.modelo.php  las cinco consultas al AS400
modelos/as400.modelo.php      la base: conexión, conversión de códigos, filas

cli/probar-as400.php          comprueba el servidor paso a paso
cli/probar-excel.php          comprueba el cálculo y el Excel SIN servidor
cli/auditoria.php             la auditoría entera desde la consola
```

### 2.1 Cinco consultas y el cruce en PHP

La versión de MySQL resuelve todo en una sentencia con dos subconsultas
agregadas y un `GROUP_CONCAT`. Aquí no, y por razones concretas:

1. **`GROUP_CONCAT` no existe en DB2 for i.** Su equivalente es `LISTAGG`, que
   está desde la 7.2 y necesita que la consulta la resuelva el motor SQL. Y no
   se podía probar contra el servidor mientras se escribía esto, así que
   apostar el informe a eso era apostar a ciegas. El desglose de formas de pago
   se arma en PHP, que no depende de la versión de nada.
2. **Cinco consultas simples son cinco planes triviales**; un `LEFT JOIN` contra
   dos agregados sobre 170.000 filas es el tipo de consulta que el AS400
   resuelve con una tabla temporal y un plan que desde aquí no se puede ver.
3. **Si una falla, se sabe cuál.**

### 2.2 El filtro de fecha no es un `BETWEEN`

En el AS400 **no hay campo fecha** en ninguno de los tres archivos. Hay cuatro
campos numéricos: siglo, año de dos cifras, mes y día (`NFCEDC`, `NFAÑDC`,
`NFMSDC`, `NFDIDC`; en `RTP325` con `R` en vez de `N`).

Componer un número con los cuatro y comparar el número funcionaría y le quitaría
al servidor cualquier posibilidad de usar un índice. Así que `Periodo::tramos()`
parte el rango en meses y cada mes aporta su condición con los campos tal cual:

```sql
   (NFCEDC = 20 AND NFAÑDC = 26 AND NFMSDC = 11 AND NFDIDC BETWEEN  1 AND 30)
OR (NFCEDC = 20 AND NFAÑDC = 26 AND NFMSDC = 12 AND NFDIDC BETWEEN  1 AND  5)
```

### 2.3 Por qué `RTP325` tarda, y por qué no se arregla aquí

Medido contra producción el 19/11/2026, pidiendo **un solo día**:

| Archivo | Filas | Índice por fecha | Tardó |
|---|---:|---|---:|
| `IDP210` | 3.149.280 | sí (`INDICE1`, `IDP210V0L1`) | 0,06 s |
| `IDP116N` | 444.044 | no, pero es pequeño | 0,18 s |
| **`RTP325`** | **6.595.139** | **ninguno** | **17–22 s** |

`RTP325` se lleva el 98 % de la espera. La causa está medida y no admite otra
lectura:

- **El tiempo no depende de cuántas filas se piden.** Un día (449 filas) tardó
  22,22 s; el mes entero (8.547 filas) tardó 17,11 s. Diecinueve veces más
  datos en el mismo tiempo: el servidor barre el archivo completo las dos
  veces.
- **En cuanto el filtro puede usar un camino de acceso, se desploma.** Por
  fecha, 22,22 s; añadiendo la tienda, 1,08 s; por la clave del documento,
  0,12 s.

Se descartaron los otros tres sospechosos midiéndolos uno a uno: el `GROUP BY`
(6,76 s agrupando contra 7,65 s sin agrupar — **no es el GROUP BY**), el
`RTPDOC IN (...)` y el campo del siglo. Ninguno explica nada.

**Consecuencia práctica:** la consulta actual ya es tan buena como se puede sin
índice, así que se queda como está. Un mes cuesta lo mismo que un día —unos
entre veinte segundos y un minuto—, que es lento pero usable, y el cargador de
la pantalla lo dice
en lugar de fingir que avanza. El arreglo de verdad es una sentencia que no nos
toca ejecutar: está en [`INDICE-RTP325.md`](INDICE-RTP325.md), lista para
sistemas.

> La tentación de «optimizar la consulta» aquí sale cara: seis variantes
> probadas, cero mejoras. Lo que falta no está en el `SELECT`.

### 2.4 La trampa de la eñe

El campo del año **se llama con eñe**: `NFAÑDC`. En un archivo PHP guardado en
UTF-8 esa eñe son dos bytes (`0xC3 0xB1`) donde el AS400 espera uno (`0xF1`), así
que el nombre que recibe el servidor no es el del campo y la consulta se rechaza
con «columna no encontrada» señalando un campo que sí existe.

Lo arregla `ModeloAS400::ejecutar()`, que pasa el SQL entero por
`utf8_a_as400()` antes de prepararlo. **Esa línea no es cosmética**: sin ella no
funciona ninguna de las tres consultas principales.

### 2.5 La clave del documento, y por qué se normaliza

Un documento es `fecha + tienda + tipo + número`. Los tres archivos la guardan
con los mismos valores, pero el driver ODBC no los entrega iguales: `NNMDOC` es
`DECIMAL(8,0)` y puede llegar como `26829`, `26829.` o `00026829` según el
archivo y el controlador.

Si no cruzan, **el informe sale con todo descuadrado y sin un solo error que lo
delate**. Por eso cada parte numérica pasa por `(int)` antes de componer la
clave, y por eso `cli/probar-as400.php` dedica su sección 7 a comprobarlo: un
«0 de 120» ahí no es un detalle, es que el informe no sirve.

### 2.6 Por qué hay una caché

La pantalla pide el informe, lo pinta, y la persona lo mira. Luego pulsa
«Descargar Excel». Si ese botón volviera a preguntarle al AS400, el archivo
descargado **no sería el que se acaba de revisar**: entre mirar y descargar pasan
minutos, y en esos minutos las tiendas siguen facturando.

Esa es la razón de `CacheAuditoria`. Que además se ahorre una consulta de varios
segundos es una ventaja, no el motivo. Caduca a la media hora: pasada, ya no se
está descargando «lo que se acaba de mirar», y entonces lo honesto es ir a
buscar el dato de nuevo.

---

## 3. El juicio, y de dónde salió

Todo lo que sigue está medido sobre los 3.626 documentos de noviembre de 2026
y, donde se dice, sobre los tres años cargados en el proyecto hermano.

### 3.1 El total de la factura no se supuso: se midió

`IDP210` trae seis importes y ninguno se llama «total». Se probaron las diez
combinaciones razonables contra la suma de pagos:

| Fórmula | Aciertos | |
|---|---:|---:|
| `monto bruto` | 124 de 3.626 | 3,4 % |
| `bruto − descuento` | 186 de 3.626 | 5,1 % |
| `bruto − descuento + IVA` | 3.551 de 3.626 | 97,9 % |
| **`bruto − descuento + IVA + IGTF`** | **3.571 de 3.626** | **98,5 %** |
| `venta Bs + IVA + IGTF` | 3.476 de 3.626 | 95,9 % |

```
TOTAL = NMODC1 − NMODC2 + NMODC6 + NMOOCG
      =  bruto  − dscto. +  IVA   +  IGTF
```

El IGTF no es opcional: añadirlo arregla 20 documentos y **no rompe ni uno**. Eso
es lo que lo convierte en parte de la fórmula y no en una corrección a ojo.

### 3.2 Los dos importes que quedan fuera, y el aviso que los vigila

`NMODC7` (descuento SENIAT) y `NMOABO` (monto abono) no entran:

- El primero vale **cero en todo el período medido**, así que sumarlo o no da el
  mismo resultado y meterlo sería adivinar su signo con cero evidencia.
- El segundo **no vale cero**, pero en las notas de crédito de clase 3 repite el
  propio bruto (medido, 31 de 31) y sumarlo contaría el movimiento dos veces.

Los dos están vigilados por `Auditoria::avisos()`. El día que uno aparezca donde
no se espera, el informe lo dice en lugar de callárselo.

### 3.3 El corte en 5 Bs cae en un hueco, no en una pendiente

Las diferencias no se reparten gradualmente: forman dos grupos separados por un
abismo.

```
  47 documentos entre     0,02 y      4,38 Bs     (45 de ellos con IGTF)
   8 documentos entre 2.000,00 y 168.136,17 Bs
```

Entre 4,38 y 2.000,00 **no hay nada**. Moverlo a 10, a 100 o a 1.000
clasificaría exactamente igual.

| Clase | Condición | Qué significa |
|---|---|---|
| `CUADRA` | ≤ 0,01 Bs | igual al céntimo |
| `REDONDEO` | ≤ 5,00 Bs | redondeo del IGTF, no es dinero |
| `REVISAR` | > 5,00 Bs | hay que ir a ver la factura |
| `NO APLICA` | — | no hay nada que contrastar |

El grupo pequeño tiene causa conocida: el IGTF es el 3 % y el AS400 lo calcula
sobre el total del documento, mientras que las líneas de pago lo guardan
redondeado por línea.

### 3.4 Lo que NO se marca, aunque lo parezca

**1. Las anuladas** (`NSTEVT = '9'`) llevan cero piezas y cero venta en el
encabezado pero conservan sus líneas de detalle. Es el comportamiento correcto
del AS400 — y de hecho cuadran en pagos. Marcarlas haría el informe falso en
casi cien filas.

**2. Las notas de crédito de clase 3** (`NTPDNC = '3'`, «ABON») no mueven
mercancía: mueven dinero. Es un abono que el cliente entrega a cuenta de un
apartado, y sus líneas de detalle son la mercancía de la factura original, que no
tiene por qué sumar el importe abonado:

```
abono == monto_bruto                 31 de 31
IVA, descuento e IGTF en cero        31 de 31
cuadran con sus formas de pago       31 de 31
su detalle cuadra con el encabezado   0 de 31
```

Para esta clase el contraste del detalle **no aplica**. En todo lo demás el
detalle cuadra 3.724 de 3.724.

**3. Las notas de crédito de clase 2** (`NTPDNC = '2'`, «AJUS») son un ajuste que
se descuenta de la factura que corrigen. Medido sobre tres años:

| clase | docs | apunta a factura | detalle | pagos |
|---|---:|---|---|---|
| 1 | 4.670 | 4.670 de 4.670 | sí | sí |
| 2 | 55 | 55 de 55 | **nunca** | **nunca** |
| 3 | 1.403 | 0 de 1.403 | no cuadra | sí |

No mueven mercancía propia ni dinero propio, así que no hay nada que contrastar:
se marcan `NO APLICA`. Marcarlas `CUADRA` o `REVISAR` mentiría en direcciones
distintas.

> Esta regla la encontró el verificador del proyecto hermano el 19/11/2026, con
> `CCCT · NC 26829`: 42,40 Bs, siete piezas en el encabezado, cero líneas de
> detalle y cero formas de pago. Con las reglas de entonces salía como
> «falta por asentar 42,40 Bs». No faltaba nada.

### 3.5 Dónde está el límite de lo que esto sabe

- La columna «Observación» describe el **patrón** que se ve en el archivo, no la
  causa. «Se registró el 80 % y la forma es CASHEA» es un hecho; «el cajero no
  asentó la inicial» sería una acusación sin pruebas. Quien revise la factura en
  la tienda tiene el papel delante y decide; el informe le dice dónde mirar.
- La forma de pago `OT` se usa y **no está dada de alta en `IDTA116`**. Que no
  tiene nada que ver con financiamiento lo confirmó Carlos; del archivo no se
  puede deducir. Lo correcto sería darla de alta.

---

### 3.6 La primera corrida contra producción, y lo que confirma

Noviembre de 2026, del 1 al 19, leído del AS400 el 19/11/2026 en **18,26 s**.

```
  documentos auditados       4.004        días con documentos    19
  por tipo                   FC 3.832 · FE 34 · NC 136 · NE 2
  total facturado            537.165.668,58 Bs
  total en formas de pago    536.630.053,16 Bs

  cuadran al céntimo         3.951   (98,7 %)
  redondeo del IGTF             46   (92,33 Bs en total)
  no aplica (ajuste NC-2)        1
  A REVISAR                      6   (535.586,27 Bs por asentar)

  el detalle cuadra          3.972      NO cuadra: 0      no aplica: 32
  anuladas                     110   (cuadran todas)
  abonos NC-3                   31   (cuadran todas)
  facturas manuales             34
```

**Todas las reglas aguantaron contra datos reales**, y ahora tienen evidencia
propia en lugar de prestada del proyecto hermano:

| Regla | Lo que predecía | Lo que salió |
|---|---|---|
| La fórmula del total | ~98,5 % de aciertos | **98,7 %** (3.951 de 4.004) |
| El contraste del detalle | cuadra siempre salvo abonos y ajustes | **3.972 de 3.972, cero fallos** |
| Las anuladas cuadran | sí, no son un descuadre | **110 de 110** |
| Los abonos NC-3 cuadran en pagos | 31 de 31 | **31 de 31** |
| El corte en 5 Bs cae en un hueco | 46 céntimos contra 6 de miles | **46 suman 92,33 Bs; los 6 suman 535.586** |

Esa última fila es la que más dice: los 46 de «redondeo» suman **dos bolívares
de media**, y los 6 «a revisar» empiezan en 2.000. El abismo sigue donde estaba,
y el corte sigue cayendo dentro.

Y los totales cuadran solos, que es la comprobación que no se puede falsear:

```
  537.165.668,58 − 536.630.053,16  =  535.615,42
  535.586,27 (lo que falta)  +  29,15 (neto del redondeo)  =  535.615,42
```

#### Lo que encontró

Seis documentos con **535.586,27 Bs cobrados y sin asentar**. El patrón de
cuatro de ellos es de libro:

| | Registrado | Falta |
|---|---:|---:|
| `RORI PORLAMAR · FC 54250` | **0,0 %** | 203.239,63 |
| `LOS CORTIJOS · FC 293743` | 20,0 % | 143.846,52 |
| `PTO. LA CRUZ · FC 176543` | 21,3 % | 140.000,00 |
| `ORINOKIA · FC 167121` | 80,0 % | 35.835,12 |
| `SAMBIL LA CANDELARIA · FC 25862` | 80,0 % | 10.665,00 |
| `RORI VALENCIA · FC 128063` | 99,0 % | 2.000,00 |

Los de 80 % y los de 20 % son las dos caras de lo mismo: una factura financiada
donde se asentó sólo una de las dos partes. El de **0,0 %** no tiene ni una línea
de pago: 203.239,63 Bs facturados sin ninguna forma de cobro registrada.

Nada de esto lo miraba nadie. Es el primer mes.

#### La segunda corrida, por la pantalla, y lo que corrige

El 20/11/2026 a las 08:43 se pidió el 1 al 20 **desde la pantalla**, contra
producción. Salió, y con ella se cierra el último punto que quedaba del
programa: la interfaz funciona con el AS400 detrás.

```
  4.196 documentos  ·  19 días  ·  561.843.402,30 Bs  ·  52,60 s

  cuadran al céntimo   4.140 (98,7 %)     el detalle cuadra, 0 descuadres
  A REVISAR                6 (535.586,27 Bs, los mismos de la víspera)
```

Las reglas vuelven a aguantar sobre 4.196 documentos. Pero **el tiempo no**:

| | 19/11, por consola | 20/11, por la pantalla |
|---|---:|---:|
| `IDP210` | 2,80 s | 4,50 s |
| **`RTP325`** | **9,67 s** | **42,03 s** |
| `IDP116N` | 5,20 s | 5,55 s |
| **total** | **18,26 s** | **52,60 s** |

Mismo servidor, un día de diferencia y cuatro veces más lento en el archivo que
no tiene índice. No es el rango —eso ya estaba medido, §2.3— sino la carga del
servidor y si conserva caliente el camino de acceso temporal que construye al
vuelo.

**Lo que esto obliga a corregir:** donde la documentación y la pantalla decían
«unos veinte segundos» ahora dicen «entre veinte segundos y un minuto», y el
paso de `RTP325` del cargador pasó de 20 a 45 segundos — con 20 se adelantaba y
anunciaba el archivo siguiente cuando todavía faltaba la mitad de la lectura.

Y refuerza la petición de [`INDICE-RTP325.md`](INDICE-RTP325.md): sin índice,
cuánto tarda el informe no lo decide esta aplicación.

---

## 4. Qué está probado y qué no

| | Cómo se comprueba | Estado |
|---|---|---|
| El total, las tolerancias, las tres clases | `php cli/probar-excel.php` — 12 casos difíciles, cada uno con el veredicto que tiene que salir | **probado** |
| El resumen, los avisos, las formas de pago | el mismo script, 17 comprobaciones más | **probado** |
| El `.xlsx`: cinco hojas, XML válido, filtros, panel fijo | el mismo script abre el ZIP y valida cada parte | **probado** |
| La pantalla: pintado, filtros, ficha, móvil, tema oscuro | navegador con la respuesta simulada, sin errores de consola | **probado** |
| Que los campos del AS400 se llamen como creemos | `php cli/probar-as400.php`, paso 4 | **confirmado 19/11/2026** |
| **Que las claves crucen entre los tres archivos** | `php cli/probar-as400.php`, paso 7 | **confirmado**: 209 de 210 con detalle, 208 de 210 con pagos, cero huérfanos |
| Que la fórmula del total cuadre con los pagos reales | tres documentos revisados a mano | **confirmado**: al céntimo |
| De dónde sale la espera | `php cli/diagnostico-consultas.php` | **medido**: `RTP325`, 6,6 M de filas sin índice (§2.3) |
| **Un mes entero de principio a fin** | `php cli/auditoria.php --mes=2026-11 --excel` | **confirmado**: 4.004 documentos en 18,26 s, todas las reglas aguantan (§3.6) |
| Que el `.xlsx` de producción abra limpio | a mano | **pendiente** |
| **La pantalla con el AS400 detrás** | a mano, 20/11/2026 | **confirmado**: 4.196 documentos en 52,60 s (§3.6) |

El cálculo está partido en dos (`Auditoria::correr()` lee, `informar()` juzga)
porque **con la VPN activa no se llega al AS400**: así todo lo que no depende
del servidor se comprueba sin él, y lo que queda es exactamente lo que sólo el
servidor puede contestar.

Las dos corridas del 19/11/2026 contra producción cerraron lo que más riesgo
tenía —el cruce de claves— y confirmaron el juicio entero sobre 4.004
documentos reales (§3.6). Lo único que queda abierto no es de programación: el
índice de `RTP325` (§2.3 y [`INDICE-RTP325.md`](INDICE-RTP325.md)).

---

## 5. Lo que queda por decidir

| | Pregunta | Quién la contesta |
|---|---|---|
| A | ¿`OT` se da de alta en `IDTA116`? Mientras no, su columna «tipo» no es de fiar | sistemas |
| B | ¿La clase 2 («AJUS») se trata como `NO APLICA` con la bendición del negocio, o sólo porque se comporta así? | contabilidad |
| C | ~~¿El tope de 93 días se queda?~~ **Sí.** El barrido de `RTP325` no depende del rango; lo que sí crece con el rango es el JSON que viaja al navegador | cerrada |
| D | ~~¿Hace falta filtrar por tienda en la consulta?~~ **No.** Filtrar por tienda haría una consulta por tienda: 55 × 1 s es peor que un barrido de 10 s | cerrada |
| E | Los 6 documentos a revisar de noviembre, ¿son cobros que faltan de verdad? Sobre todo `RORI PORLAMAR · FC 54250`, 203.239,63 Bs sin una sola línea de pago | la tienda, con la factura delante |
