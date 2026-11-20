<p align="center">
  <img src="../vistas/img/industrias-rrc.png" alt="Industrias RRC, C.A." width="150">
</p>

# Manual técnico · Auditoría de Formas de Pago

Para quien mantiene el sistema: qué hace, cómo está armado, por qué está
armado así y qué no hay que tocar sin entender antes el motivo.

Casi todo lo que sigue está medido contra producción, no supuesto. Donde una
cifra viene de una medición, se dice de cuándo es y sobre cuántos documentos.

---

## 1. Qué es esto y por qué está hecho así

La aplicación contesta una pregunta: **¿cuadra cada factura con lo que se cobró
por ella?** Un documento del AS400 vive en tres archivos y los tres tienen que
contar lo mismo:

| Alias | Archivo real | Qué guarda |
|---|---|---|
| `IDP210` | `RORILBRA.IDP210` | el encabezado: cuánto se vendió |
| `RTP325` | `RORIVENTAA.RTP325` | el detalle: qué se vendió |
| `IDP116N` | `RORIVENTAA.IDP116N` | los pagos: con qué se pagó |
| `IDTA116` | `RORIVENTAA.IDTA116` | catálogo de formas de pago |
| `ETP045` | `RORIVENTAA.ETP045` | maestro de tiendas |

Si la suma de las formas de pago no llega al total de la factura, falta un
cobro por asentar.

### 1.1 Qué cambia respecto de la versión que ya existía

En `ventas-ia-agentes` hay una auditoría equivalente. **El juicio es el mismo,
portado entero con sus justificaciones**; lo que cambia es de dónde salen los
datos y cómo se usa.

| | `ventas-ia-agentes` | esta aplicación |
|---|---|---|
| Origen | MySQL, cargado por el ETL de madrugada | **AS400 en vivo** |
| Retraso | lo que no se cargó, no se audita | ninguno |
| Cómo se pide | un comando y después un `.ps1` | una pantalla con dos fechas |
| Se ve antes de descargar | no | **sí** |
| Excel | PowerShell manejando Excel por COM | PHP escribiendo el `.xlsx` |
| Hace falta Excel instalado | sí | no |

Las dos consecuencias que importan:

1. **Desaparece el aviso «estos días no están cargados».** Aquí pregunta y
   contesta el AS400, así que ese aviso se quitó en lugar de dejarlo diciendo
   algo que ya no es verdad. Lo que sí queda es el aviso del futuro: pedir
   noviembre el día 19 no deja once días sin auditar, deja once días sin
   ocurrir, y decirlo de otra forma hace que quien lea el informe se pregunte
   qué se le está ocultando.
2. **El Excel ya no necesita Excel.** Un `.xlsx` es un ZIP con unos XML dentro,
   y `servicios/LibroExcel.php` lo escribe directamente. Office en el servidor
   web no estaba, ni tenía sentido ponerlo: dos personas pidiendo el informe a
   la vez son dos instancias de Excel peleándose, y la que pierde deja un
   `EXCEL.EXE` colgado que nadie cierra.

### 1.2 Dos divisiones que no son de estilo

- **`Auditoria::correr()` lee; `Auditoria::informar()` juzga.** Con la VPN
  activa no se llega al AS400, así que durante buena parte del desarrollo no
  hay servidor al que preguntar. Partido así, `cli/probar-excel.php` comprueba
  el juicio entero y las cinco pestañas del Excel sin conexión, y lo que queda
  es exactamente lo que sólo el servidor puede contestar.
- **`InformeExcel` no decide nada.** Recibe lo que devolvió `correr()` y lo
  pinta. Si el formato y el cálculo vivieran juntos, no se podría comprobar
  ninguno de los dos por separado — y lo que se descarga dejaría de ser,
  garantizadamente, lo que se vio en pantalla.

---

## 2. Requisitos

| Qué | Cuál, y por qué |
|---|---|
| PHP | **8.2** o superior, con `declare(strict_types=1)` en todo el código |
| Extensiones | `odbc` (el AS400) y `zip` (el `.xlsx`) |
| Servidor | Apache con `.htaccess` habilitado (`AllowOverride All`) |
| Driver ODBC | iSeries Access / Client Access, registrado en 64 bits |
| Composer | **no hace falta**: no hay `vendor/` ni una sola dependencia de terceros |
| Base de datos | MySQL sólo para la intranet (permisos y bitácora); los datos de ventas salen del AS400 |
| Node | sólo en el equipo que genera los manuales en PDF (ver §9.3) |

El acceso al AS400 es **de sólo lectura**. Esta aplicación no escribe ni una
fila en el servidor.

---

## 3. Estructura

```
index.php                     entrada: resuelve quién entra y pinta la plantilla
controladores/
  plantilla.controlador.php   carga vistas/plantilla.php; no hay enrutador
vistas/
  plantilla.php               la única página; nombre y módulos salen de config/app.php
  modulos/periodo.php         el formulario: dos fechas y los atajos
  modulos/resultado.php       los huecos que llena el navegador
  modulos/pie.php             el pie corporativo
  iconos.php                  los SVG en línea
  js/auditoria.js             pide, pinta y filtra. NO calcula nada
  js/loader.js, js/tema.js    el cargador y el tema claro/oscuro
  css/                        tokens, estilos, tablas, loader, auditoria
  manuales/                   los PDF de este manual y los otros dos
php/auditoria/
  consultar.php               POST desde+hasta  ->  JSON con el informe
  excel.php                   GET token (o fechas)  ->  el .xlsx
servicios/
  Periodo.php                 valida el rango y lo parte en meses
  Auditoria.php               EL JUICIO: el total, las tolerancias, los avisos
  CacheAuditoria.php          guarda la corrida para que el Excel sea lo visto
  LibroExcel.php              escribe un .xlsx sin dependencias
  InformeExcel.php            las cinco pestañas del informe
  SesionIntranet.php          quién entra y qué puede
modelos/
  as400.modelo.php            conexión, conversión de códigos, filas
  auditoria.modelo.php        las cinco consultas al AS400
  intranet.modelo.php         usuario y permisos
config/
  app.php                     nombre, subtítulo, css, js, módulos
  pie.php                     empresa, soporte, desarrollador, manuales, versión
  as400.php                   CONECTARAS400() / DESCONECTARAS400()
  librerias.php + .txt        el mapa alias -> BIBLIOTECA.ARCHIVO
  env.php, texto.php          el .env y la conversión ANSI -> UTF-8
  bitacora.php, respuesta.php
cli/
  auditoria.php               la auditoría entera desde la consola
  probar-as400.php            comprueba el servidor paso a paso
  probar-excel.php            comprueba el cálculo y el Excel SIN servidor
  diagnostico-consultas.php   por qué tarda, y cuál de las consultas
  ver-excel.php               mira un .xlsx en el navegador, sin Excel
almacen/auditoria/            las corridas guardadas y los Excel. Denegado por web
docs/                         este manual y los demás. Denegado por web
```

**Una sola página.** Las pantallas que la aplicación aparenta tener se arman en
el navegador con el JSON de `php/`, así que no hay enrutador: no hay a dónde
enrutar.

**Cada carpeta de código trae su propio `.htaccess` que la deniega entera**
(`config/`, `controladores/`, `modelos/`, `servicios/`, `cli/`, `docs/`,
`almacen/`). En `vistas/` se deniega sólo `*.php`: los `css`, `js`, `img` y
`manuales` sí son URLs. Y en la raíz se deniega el `.env`, que lleva usuario y
clave del AS400.

---

## 4. Configuración

### 4.1 El `.env`

Se copia de `.env.example` y se rellena. No se versiona.

```ini
AS400_HOST=
AS400_USER=
AS400_PASS=
AS400_DRIVER=Client Access ODBC Driver (32-bit)
AS400_LIBRERIAS=produccion

INTRANET_VALIDAR=no
INTRANET_USUARIO_PRUEBAS=
INTRANET_APP_ID=
INTRANET_DB_HOST=
INTRANET_DB_PORT=3306
INTRANET_DB_NAME=intranet
INTRANET_DB_USER=
INTRANET_DB_PASS=
INTRANET_URL_PERFILES=
```

> **`AS400_LIBRERIAS=produccion` no es un detalle.** Con `desarrollo`, el mapa
> apunta `IDP210` a `CFLORES.IDP210` y `IDP116N` a `AGARAY.IDP116N`, que son
> **copias**. Una auditoría «en vivo» contra una copia de hace un mes da
> números, y están mal, y no se nota mirándolos. `cli/probar-as400.php` dice en
> su primer paso qué mapa está en uso, precisamente por esto.

`AS400_DRIVER` tiene que coincidir **exactamente** con el nombre registrado en
el equipo. El de IBM se llama «(32-bit)» pero está registrado también en 64
bits, que es lo que usa PHP.

Las credenciales no tienen valor por omisión en el código, y es a propósito:
antes lo tenían y eso era la credencial publicada en el repositorio. Además, con
un valor por defecto puesto, un `.env` mal leído no se notaba — la aplicación
conectaba igual.

### 4.2 El mapa de bibliotecas

`config/librerias.php` lee `librerias.txt` (producción) o `libreriasDevs.txt`
(desarrollo) según el `.env`, y deja el mapa en el global `$archivos`. Cada
línea es `ALIAS;BIBLIOTECA.ARCHIVO`. Los modelos nunca escriben el nombre real:
piden el alias con `ModeloAS400::archivo('IDP210')`, que falla ruidosamente si
no está declarado. La alternativa —un nombre vacío— produce un SQL roto y un
mensaje del AS400 que no menciona la causa.

Esta aplicación añadió al mapa una sola línea, `ETP045`, marcada como de sólo
lectura.

### 4.3 Identidad y pie

- `config/app.php`: nombre, subtítulo, color del tema, qué CSS y qué JS se
  cargan y en qué orden, y qué módulos se pintan. La plantilla no nombra a esta
  aplicación en ningún sitio.
- `config/pie.php`: empresa, soporte, desarrollador, **la versión** y las rutas
  de los manuales. Lo que esté vacío no se pinta, y una columna sin contenido
  no se pinta entera: un dato que no se sabe se queda en blanco en vez de salir
  inventado.

> **La versión vive en `config/pie.php` y también en `docs/manuales.json`**, que
> es de donde la toman las portadas y las cabeceras de los PDF. Son dos sitios
> y hay que subirla en los dos. Lo correcto a medio plazo es un archivo
> `VERSION` en la raíz que lean ambos: el generador de manuales ya lo busca
> solo.

---

## 5. El AS400: cinco consultas y el cruce en PHP

### 5.1 Por qué cinco consultas y no una con joins

La versión de MySQL resuelve todo en una sentencia con dos subconsultas
agregadas y un `GROUP_CONCAT`. Aquí no:

1. **`GROUP_CONCAT` no existe en DB2 for i.** Su equivalente es `LISTAGG`, que
   está desde la 7.2 y necesita que la consulta la resuelva el motor SQL. No se
   podía probar contra el servidor mientras se escribía esto, así que apostar
   el informe a eso era apostar a ciegas. El desglose se arma en PHP, que no
   depende de la versión de nada.
2. **Cinco consultas simples son cinco planes triviales.** Un `LEFT JOIN`
   contra dos agregados sobre 170.000 filas es el tipo de consulta que el AS400
   resuelve con una tabla temporal y un plan que desde aquí no se puede ver.
3. **Si una falla, se sabe cuál.** Con una sentencia de sesenta líneas, un
   «columna no encontrada» no dice de qué archivo viene.

El cruce son tres `foreach` sobre arrays indexados por la clave del documento:
nada que el AS400 haga mejor.

### 5.2 El filtro de fecha no es un `BETWEEN`

En el AS400 **no hay campo fecha** en ninguno de los tres archivos. Hay cuatro
campos numéricos: siglo, año de dos cifras, mes y día (`NFCEDC`, `NFAÑDC`,
`NFMSDC`, `NFDIDC`; en `RTP325` con `R` en vez de `N`).

Componer un número con los cuatro y comparar el número funcionaría y le quitaría
al servidor cualquier posibilidad de usar un camino de acceso. Así que
`Periodo::tramos()` parte el rango en meses y cada mes aporta su condición con
los campos tal cual:

```sql
   (NFCEDC = 20 AND NFAÑDC = 26 AND NFMSDC = 11 AND NFDIDC BETWEEN  1 AND 30)
OR (NFCEDC = 20 AND NFAÑDC = 26 AND NFMSDC = 12 AND NFDIDC BETWEEN  1 AND  5)
```

Los números van incrustados y no con marcadores `?` a propósito: salen de
`Periodo`, que ya los validó como enteros, y el driver manda los parámetros como
carácter — comparar un carácter contra una columna numérica del AS400 **no
encuentra nada y no da error**, que es la peor forma de fallar que tiene este
servidor.

### 5.3 La trampa de la eñe

El campo del año **se llama con eñe**: `NFAÑDC`. En un archivo PHP guardado en
UTF-8 esa eñe son dos bytes (`0xC3 0xB1`) donde el AS400 espera uno (`0xF1`), así
que el nombre que recibe el servidor no es el del campo y la consulta se rechaza
con «columna no encontrada» señalando un campo que sí existe.

Lo arregla `ModeloAS400::ejecutar()`, que pasa el SQL entero por
`utf8_a_as400()` antes de prepararlo. **Esa línea no es cosmética**: sin ella no
funciona ninguna de las tres consultas principales.

La misma trampa aparece al revés en el sentido de vuelta: el driver entrega el
texto en Windows-1252, y `json_encode()` rechaza lo que no sea UTF-8 válido
—devuelve `false`, y un `echo false` imprime cero bytes—. Por eso
`ModeloAS400::filas()` convierte en la frontera, con `as400_a_utf8()`.

### 5.4 La clave del documento, y por qué se normaliza

Un documento es `fecha + tienda + tipo + número`. Los tres archivos la guardan
con los mismos valores, pero el driver ODBC no los entrega iguales: `NNMDOC` es
`DECIMAL(8,0)` y puede llegar como `26829`, `26829.` o `00026829` según el
archivo y el controlador.

Si no cruzan, **el informe sale con todo descuadrado y sin un solo error que lo
delate**: las facturas salen con «pagado 0,00» y «falta todo». Por eso cada
parte numérica pasa por `(int)` antes de componer la clave, y por eso
`cli/probar-as400.php` dedica su paso 7 a comprobarlo. Confirmado el
19/11/2026: **209 de 210 con detalle, 208 de 210 con pagos, cero huérfanos**.

### 5.5 Las filas vienen por posición, no por nombre

Es la norma de `ModeloAS400` y aquí importa el doble: dos de estas consultas
llevan `COUNT(*)` y `SUM(...)` sin alias, y el nombre que el driver les inventa
no es estable. Cada modelo traduce posiciones a nombres en el mismo método que
lanza la consulta, para que el orden del `SELECT` y el del array se lean juntos.

### 5.6 El catálogo se lee agrupado, y eso cuesta dinero si se olvida

`IDTA116` tiene **varias filas por forma de pago**, una por combinación de marca
y divisa. Un `JOIN` por `FFORPA` contra las líneas de pago duplicaría cada línea
tantas veces como filas tenga su forma e inflaría el total pagado sin que nada
avisara: el informe diría que todo cuadra de más. De ahí que el catálogo se lea
aparte, con `GROUP BY FFORPA`, y que la consulta de pagos no una con nada.

El catálogo devuelve además `COUNT(DISTINCT FFORPT)`: si una forma tuviera más
de un tipo, «¿es financiamiento?» dejaría de tener respuesta, y hay un aviso que
lo dice en lugar de elegir una.

### 5.7 El nombre de la tienda sale de `ENBTDA`, no de `ENBRZS`

`ENBRZS` es la **razón social** —la empresa que opera el local— y `ENBTDA` es el
nombre de la tienda. El programa que lleva años en producción
(`reporteVentasDiariasV5`) llena su combo con `ENBRZS` porque le basta, y de ahí
salió la confusión. El código 12 lo deja claro:

```
ENBTDA  RORI PORLAMAR            <- el nombre
ENBRZS  COMERCIAL NEW MAR, C.A.  <- la empresa
```

Se leen **todas** las tiendas, activas y cerradas: una tienda que cerró en marzo
tiene facturas en febrero, y auditar febrero con la tienda sin nombre sería peor
informe por nada.

---

## 6. El juicio

Todo lo de esta sección está medido sobre los 3.626 documentos de noviembre de
2026 y, donde se dice, sobre los tres años cargados en el proyecto hermano. La
fuente de verdad es la cabecera de `servicios/Auditoria.php`.

### 6.1 El total de la factura no se supuso: se midió

`IDP210` trae seis importes y ninguno se llama «total». Se probaron las diez
combinaciones razonables contra la suma de pagos:

| Fórmula | Aciertos | |
|---|---:|---:|
| `monto bruto` | 124 de 3.626 | 3,4 % |
| `bruto - descuento` | 186 de 3.626 | 5,1 % |
| `bruto - descuento + IVA` | 3.551 de 3.626 | 97,9 % |
| **`bruto - descuento + IVA + IGTF`** | **3.571 de 3.626** | **98,5 %** |
| `venta Bs + IVA + IGTF` | 3.476 de 3.626 | 95,9 % |

```
TOTAL = NMODC1 - NMODC2 + NMODC6 + NMOOCG
      =  bruto  - dscto. +  IVA   +  IGTF
```

El IGTF no es opcional: añadirlo arregla 20 documentos y **no rompe ni uno**.
Eso es lo que lo convierte en parte de la fórmula y no en una corrección a ojo.

### 6.2 Los dos importes que quedan fuera, y el aviso que los vigila

`NMODC7` (descuento SENIAT) y `NMOABO` (monto abono) no entran:

- El primero vale **cero en todo el período medido**, así que sumarlo o no da el
  mismo resultado y meterlo sería adivinar su signo con cero evidencia.
- El segundo **no vale cero**, pero en las notas de crédito de clase 3 repite el
  propio bruto (medido, 31 de 31) y sumarlo contaría el movimiento dos veces.

Los dos están vigilados por `Auditoria::avisos()`. El día que uno aparezca donde
no se espera, el informe lo dice en lugar de callárselo.

### 6.3 Las tolerancias, y por qué el corte cae en un hueco

```
  47 documentos entre     0,02 y      4,38 Bs     (45 de ellos con IGTF)
   8 documentos entre 2.000,00 y 168.136,17 Bs
```

Entre 4,38 y 2.000,00 **no hay nada**. Moverlo a 10, a 100 o a 1.000
clasificaría exactamente igual.

| Constante | Valor | Clase |
|---|---|---|
| `TOLERANCIA_EXACTA` | 0,01 Bs | `CUADRA` |
| `TOLERANCIA_REDONDEO` | 5,00 Bs | `REDONDEO` |
| — | por encima | `REVISAR` |
| — | nada que contrastar | `NO APLICA` |

El grupo pequeño tiene causa conocida: el IGTF es el 3 % y el AS400 lo calcula
sobre el total del documento, mientras que las líneas de pago lo guardan
redondeado por línea.

### 6.4 Lo que NO se marca, aunque lo parezca

**1. Las anuladas** (`NSTEVT = '9'`) llevan cero piezas y cero venta en el
encabezado pero conservan sus líneas de detalle. Es el comportamiento correcto
del AS400 — y de hecho cuadran en pagos. Marcarlas haría el informe falso en
casi cien filas.

**2. Las notas de crédito de clase 3** (`NTPDNC = '3'`, «ABON») no mueven
mercancía: mueven dinero. Es un abono que el cliente entrega a cuenta de un
apartado, y sus líneas de detalle son la mercancía de la factura original:

```
abono == monto_bruto                 31 de 31
IVA, descuento e IGTF en cero        31 de 31
cuadran con sus formas de pago       31 de 31
su detalle cuadra con el encabezado   0 de 31
```

Para esta clase el contraste del detalle **no aplica** y vale `null`, no cero:
un cero diría «cuadra», que es mentira, y la diferencia diría «descuadra», que
es peor.

**3. Las notas de crédito de clase 2** (`NTPDNC = '2'`, «AJUS») son un ajuste que
se descuenta de la factura que corrigen. Medido sobre tres años:

| clase | docs | apunta a factura | detalle | pagos |
|---|---:|---|---|---|
| 1 (DEV) | 4.670 | 4.670 de 4.670 | sí | sí |
| 2 (AJUS) | 55 | 55 de 55 | **nunca** | **nunca** |
| 3 (ABON) | 1.403 | 0 de 1.403 | no cuadra | sí |

> **La encontró el verificador el 19/11/2026**, con `CCCT · NC 26829`: 42,40 Bs,
> siete piezas en el encabezado, cero líneas de detalle y cero formas de pago.
> Con las reglas de entonces salía como «falta por asentar 42,40 Bs». No faltaba
> nada.
>
> Y no hacía falta deducirlo: ya estaba escrito. `NTPDNC` vale **1 = DEV, 2 =
> AJUS, 3 = ABON**, y llevaba meses en la documentación del proyecto hermano.
> Deducirlo de los datos salió bien, pero por no usar el nombre del AS400 la
> clase 3 quedó llamada «devolución de dinero» cuando es un ABONO —dinero que
> ENTRA— y eso sí hizo daño en otro informe.

### 6.5 El diagnóstico describe el patrón, no la causa

`Auditoria::diagnostico()` escribe la frase que acaba en la columna
«Observación». La regla es explícita: «se registró el 80 % y la forma es CASHEA»
es un hecho; «el cajero no asentó la inicial» sería una acusación sin pruebas.
Quien revise la factura en la tienda tiene el papel delante y decide; el informe
le dice dónde mirar.

El ajuste se explica **primero y solo**: todo lo demás que se dijera de él —«no
tiene líneas de pago», «no tiene detalle»— es cierto y da a entender que falta
algo.

### 6.6 Los avisos

`Auditoria::avisos()` es lo que el informe advierte de sí mismo: supuestos que
podrían haber dejado de ser verdad, y hallazgos que no caben en ninguna columna.
Tres niveles: `alto`, `medio`, `bajo`.

| Aviso | Nivel |
|---|---|
| Documentos con `NMODC7` distinto de cero | alto |
| Abonos que no se explican por ser una NC-3 que repite el bruto | alto |
| Encabezados con fecha imposible (no entran en el informe) | alto |
| Pagos en `IDP116N` sin encabezado en `IDP210` | alto |
| Una forma con más de un tipo en `IDTA116` | alto |
| Líneas en `RTP325` sin encabezado | medio |
| Una forma de pago desconocida y fuera del catálogo | medio |
| Notas de crédito de clase 2 en el período | bajo |
| La forma `OT`, conocida y fuera del catálogo | bajo |
| El período llega al futuro, o faltan días dentro del tramo | bajo |

La distinción entre una forma **conocida** fuera del catálogo y una
**desconocida** es deliberada. De `OT` ya se sabe lo que hace falta saber: son
«otros pagos» y no son financiamiento — lo confirmó Carlos Flores, y el
20/11/2026 quedó en darla de alta en `IDTA116` cuando pueda. Eso no es un
hallazgo, es una tarea abierta, y repetirlo cada mes con la misma urgencia que
un dato desconocido es la forma más segura de que un día nadie lea los avisos.
Ese caso está declarado en una constante, `Auditoria::FUERA_DEL_CATALOGO`, y no
repartido por el código: el día que se dé de alta, el catálogo contesta solo y
la entrada deja de hacer falta.

---

## 7. La pantalla

### 7.1 El reparto

```
index.php -> vistas/plantilla.php -> modulos/periodo.php + modulos/resultado.php
vistas/js/auditoria.js  pide, pinta y filtra
php/auditoria/consultar.php   POST desde+hasta  ->  JSON
php/auditoria/excel.php       GET  token        ->  .xlsx
```

**El navegador no calcula nada.** Si decidiera, por ejemplo, el corte entre
«redondeo» y «revisar», habría dos reglas —la del JavaScript y la del Excel— y
el día que una cambiara, la pantalla y el archivo descargado dirían cosas
distintas sobre la misma factura.

### 7.2 `consultar.php` va por POST aunque sólo lea

Por la letra de HTTP sería un GET. Va por POST por dos razones prácticas: un GET
lo guardan en caché el navegador y cualquier intermediario, y lo reintentan
solos al volver atrás — una auditoría en vivo que devuelve la respuesta de hace
media hora deja de ser en vivo y nadie se entera; y un GET se pone en un enlace,
y un enlace se pulsa por accidente, y cada pulsación son varios segundos de
sesión ODBC.

El límite de tiempo se sube a **180 segundos** en ese archivo y no en el
`php.ini`, porque es esa página la que lo necesita. La respuesta va con
`Cache-Control: no-store`.

Los errores se devuelven con el estado que les toca y el motivo **dentro** del
cuerpo: 422 cuando el período no vale —el mensaje de `Periodo` está escrito para
que lo lea una persona—, 503 cuando no hay AS400 (con la pista de la VPN), 500
cuando el servidor rechaza la consulta. El mensaje del driver no sale nunca a la
pantalla: lleva el nombre del servidor y del usuario, y eso va al registro.

### 7.3 Por qué hay una caché

La pantalla pide el informe, lo pinta, y la persona lo mira. Luego pulsa
«Descargar Excel». Si ese botón volviera a preguntarle al AS400, el archivo
descargado **no sería el que se acaba de revisar**: entre mirar y descargar pasan
minutos, y en esos minutos las tiendas siguen facturando.

Esa es la razón de `CacheAuditoria`. Que además se ahorre una consulta de varios
segundos es una ventaja, no el motivo: si el motivo fuera la velocidad, sería
legítimo saltarse la caché cuando conviniera, y no lo es.

- **Un archivo y no `$_SESSION`**: un informe de un mes son unos megas de JSON;
  en la sesión se carga y se reescribe en cada petición, incluida la del icono,
  y bloquea el archivo de sesión mientras lo hace.
- **El token lo genera `random_bytes`**, no un hash del período: con un hash, el
  token de «noviembre» sería adivinable. Y aun así el endpoint comprueba el
  permiso: el token no es la autorización, es el identificador.
- **Caduca a los 30 minutos.** Pasada, ya no se está descargando «lo que se
  acaba de mirar», y entonces lo honesto es ir a buscar el dato de nuevo.

Si guardar la corrida falla, la consulta **no** se cae: el informe ya está
calculado y la pantalla lo pinta. Lo que se pierde es la garantía, y eso se dice
con un aviso en pantalla en lugar de dejar que se descubra comparando dos
archivos que no coinciden.

### 7.4 Detalles del navegador que ya costaron un rato

- **La tabla se pinta por tramos de 300 filas.** Un mes son 3.800 documentos por
  catorce columnas: 53.000 celdas. Creadas de golpe, el navegador se queda
  bloqueado un par de segundos justo después de una espera de veinte.
- **Siempre `textContent`, nunca `innerHTML`** para los datos. Lo que se pinta
  sale del AS400: nombres de cliente y descripciones que lleva grabando gente
  desde hace años y que nadie validó nunca.
- **Nada de `new Date('2026-11-17')`**: eso se interpreta como medianoche UTC y
  aquí estamos al oeste de Greenwich, así que `getDate()` devolvería el día
  anterior. Todas las fechas saldrían corridas un día y ningún error lo diría.
  Las fechas se parten como texto.
- **El locale es `es-VE` explícito.** Con el del navegador en inglés,
  «46.916,44» saldría «46,916.44», y en un informe de bolívares eso se lee como
  cuarenta y seis mil con coma.
- **Un solo escuchador en el `tbody`**, no uno por fila: con tres mil filas,
  tres mil escuchadores son tres mil cierres vivos que soltar en cada filtrado.
- Los huecos con `aria-live` están en el HTML desde el primer byte: una región
  que se inserta junto con su contenido **no se anuncia**.

### 7.5 El acceso

`SesionIntranet` resuelve quién entra. La intranet abre la aplicación con
`index.php?user=…&idapp=…` en base64; a partir de ahí la identidad vive en la
sesión de PHP.

> **Esto comprueba permisos, no autentica.** Un usuario en un parámetro de la
> URL no es autenticación: cualquiera en la red puede escribir el nombre de otro
> en base64. Es lo que hacen los demás módulos de la casa y lo que pide el
> encargo. Para que fuera autenticación haría falta que la intranet firmara el
> enlace —un HMAC con caducidad— y que aquí se verificara la firma.

Con `INTRANET_VALIDAR=no` se trabaja como el usuario de pruebas y la cabecera
muestra un distintivo **PRUEBAS** que no se puede pasar por alto. Si no se puede
conectar con la base de la intranet, la respuesta correcta es **cerrar** la
puerta: no se puede comprobar el permiso.

---

## 8. El Excel sin Excel

`servicios/LibroExcel.php` escribe el `.xlsx` directamente: un `.xlsx` es un ZIP
con unos XML dentro, y `ZipArchive` ya está en el servidor. Sin Office, sin
LibreOffice y sin Composer.

`servicios/InformeExcel.php` pone las cinco pestañas:

| Pestaña | Qué trae |
|---|---|
| Resumen | las cifras del período, los contrastes y los avisos |
| A revisar | sólo lo accionable |
| Auditoría | una fila por documento, con autofiltro y panel fijo |
| Formas de pago | en qué se cobró |
| Método | la fórmula, el corte en 5 Bs y qué no se juzga |

**La pestaña «Método» no es relleno.** El informe afirma que faltan 203.239 Bs
por asentar en una factura concreta; quien lo reciba tiene derecho a saber de
dónde sale el total contra el que se compara. Si eso no viaja con el archivo,
vive sólo en la cabeza de quien lo escribió.

### 8.1 Decisiones de diseño que ya se discutieron

- **La cabecera es blanca, no marino.** El logotipo de la casa es azul marino
  sobre fondo claro: sobre una banda marino desaparece. Y esto se imprime —
  alguien se lleva el informe a la tienda a buscar la factura— y una banda a
  sangre en cinco pestañas es tóner gastado en decoración. La marca la pone un
  filo de 4 px en degradado de `0369A1` a `0F172A`.
- **El logotipo va encima del título, no al lado.** La sangría de Excel se mide
  en caracteres de la fuente, no en píxeles, y si el cálculo se queda corto el
  título se monta sobre el logotipo. Como aquí no hay Excel con el que
  comprobarlo, se eligió la disposición que no puede fallar.
- **`InformeExcel::PRIMERA_FILA` es pública** porque `cli/probar-excel.php`
  comprueba que la pestaña grande tenga una fila por documento. Con el número
  escrito a mano en los dos sitios, cambiar el diseño rompía la prueba por algo
  que no era un fallo.

### 8.2 `excel.php` no escribe nada hasta el final

Un `.xlsx` es binario. Un aviso de PHP, un salto de línea de más o un mensaje de
error impreso antes de las cabeceras se cuelan **dentro** del archivo y Excel
dice «formato no válido» sin más pistas. Por eso el libro se escribe primero a
un temporal y sólo cuando está completo se mandan las cabeceras; y por eso se
vacían todos los búferes de salida antes de la primera cabecera. Si algo falla
antes de ese punto, lo que sale es una página de error en HTML, que al menos se
puede leer.

---

## 9. Las herramientas de consola

### 9.1 Las cuatro de siempre

```
php cli\auditoria.php                               el mes en curso
php cli\auditoria.php --mes=2026-11
php cli\auditoria.php --desde=2026-11-01 --hasta=2026-11-17
php cli\auditoria.php --mes=2026-11 --excel
php cli\auditoria.php --mes=2026-11 --excel --salida=C:\ruta\Auditoria.xlsx
php cli\auditoria.php --mes=2026-11 --json

php cli\probar-as400.php                 ¿contesta el servidor lo que esperamos?
php cli\probar-as400.php --fecha=2026-11-17
php cli\probar-excel.php                 ¿el cálculo y el Excel hacen lo que dicen?
php cli\diagnostico-consultas.php        ¿por qué tarda, y cuál de las consultas?
php cli\ver-excel.php <archivo.xlsx>     mira un .xlsx en el navegador, sin Excel
```

Todas se niegan a correr fuera de CLI: si llegan por web devuelven 404.

- **`auditoria.php`** usa el mismo servicio que la pantalla, así que da los
  mismos números. Sirve para comprobar antes de que alguien lo use, para sacar
  el Excel de un mes cerrado sin pantalla delante y para **ver el error
  completo**, que en la pantalla llega resumido a propósito.
- **`probar-as400.php`** comprueba siete cosas en orden y se para en el primer
  fallo real: el `.env` y qué mapa usa, la extensión ODBC, la conexión, que los
  cinco archivos existen, que cada archivo tiene los campos que se leen, que una
  consulta de verdad devuelve filas con su tiempo, y **que las claves cruzan**.
  Un «0 de 120» en el paso 7 no es un detalle: es que el informe no sirve.
- **`probar-excel.php` no toca el AS400.** Fabrica los casos difíciles —el que
  cuadra al céntimo, el de redondeo del IGTF, el que falta dinero, el ajuste que
  no se contrasta, el abono, el anulado, la forma fuera del catálogo— y
  comprueba que cada uno saca el veredicto que tiene que sacar. Son 12 casos y
  17 comprobaciones más sobre el resumen, los avisos y el `.xlsx`.
- **`diagnostico-consultas.php`** cronometra nueve variantes de la consulta del
  detalle e imprime los índices de cada archivo. Tarda del orden de cinco
  minutos; es el precio de no probar a ciegas tres veces.
- **`ver-excel.php`** pinta el `.xlsx` como una página web con los anchos,
  altos, rellenos y fuentes que declara el propio archivo. **No** reproduce los
  formatos numéricos —una fecha sale como su número de serie—, ni el autofiltro,
  ni los paneles fijos. Con él se encontró que las filas de «A revisar»
  cortaban el diagnóstico por la mitad.

### 9.2 Qué se corre y cuándo

| Situación | Qué correr |
|---|---|
| Antes de tocar nada | `php cli\probar-excel.php` |
| Después de tocar el juicio o el Excel | `php cli\probar-excel.php` |
| Al instalar en un equipo nuevo | `php cli\probar-as400.php` |
| «Hoy va lento» | `php cli\diagnostico-consultas.php` |
| Hay que ver cómo quedó el Excel | `php cli\ver-excel.php` |

### 9.3 Los manuales en PDF

El Markdown de `docs/` es la fuente; los PDF se generan desde él y nunca al
revés.

```
cd docs\_herramientas
npm install                  (sólo la primera vez)
node generar-manuales.mjs --salida ..\..\vistas\manuales
```

El generador es autónomo: vive en `docs/_herramientas/` con su propio
`package.json` y sus dependencias, no toca nada del proyecto y lo único que pide
es **Node 18 o superior en el equipo que genera**. La identidad, los colores, el
logotipo y la lista de manuales están en `docs/manuales.json`.

Los PDF se dejan en `vistas/manuales/` y **no** en `docs/`, porque `docs/` tiene
un `.htaccess` que deniega el acceso por web y el enlace del pie daría un 403.
Las rutas se declaran en `config/pie.php`, bajo `manuales`.

Cada manual tiene que decir `ok` y ninguna línea `aviso`. Un aviso de caracteres
significa que el `.md` lleva algo que Helvetica no sabe pintar: se añade a
`SUSTITUCIONES` en `generar-manuales.mjs` y se vuelve a generar.

**Se regeneran los PDF cada vez que se toca un `.md`, en el mismo cambio.** Un
PDF que se queda atrás es peor que no tenerlo: es lo que se imprime y se manda.

---

## 10. Rendimiento: `RTP325`

Medido contra producción el 19/11/2026, pidiendo **un solo día**:

| Archivo | Filas | Camino de acceso por fecha | Tardó |
|---|---:|---|---:|
| `IDP210` | 3.149.280 | sí (`INDICE1`, `IDP210V0L1`) | 0,06 s |
| `IDP116N` | 444.044 | no, pero es pequeño | 0,18 s |
| **`RTP325`** | **6.595.139** | **ninguno** | **17 - 22 s** |

`RTP325` se lleva el 98 % de la espera, y la causa no admite otra lectura:

- **El tiempo no depende de cuántas filas se piden.** Un día (449 filas) tardó
  22,22 s; el mes entero (8.547 filas) tardó 17,11 s. Diecinueve veces más datos
  en el mismo tiempo: el servidor barre el archivo completo las dos veces.
- **En cuanto el filtro puede usar un camino de acceso, se desploma.** Por
  fecha, 22,22 s; añadiendo la tienda, 1,08 s; por la clave del documento,
  0,12 s.

Se descartaron los otros tres sospechosos midiéndolos uno a uno: el `GROUP BY`
(6,76 s agrupando contra 7,65 s sin agrupar — **no es el GROUP BY**), el
`RTPDOC IN (...)` y el campo del siglo.

> **La tentación de «optimizar la consulta» aquí sale cara: seis variantes
> probadas, cero mejoras.** Lo que falta no está en el `SELECT`. El arreglo es
> una sentencia que no nos toca ejecutar y está lista para sistemas en
> `docs/INDICE-RTP325.md`:
>
> `CREATE INDEX RORIVENTAA.RTP325X1 ON RORIVENTAA.RTP325 (RFCEDC, RFAÑDC, RFMSDC, RFDIDC, RCDTDA, RTPDOC, RNMDOC);`

Mientras tanto: un mes cuesta lo mismo que un día, el tope de `Periodo` está en
**93 días** y el cargador de la pantalla dice qué archivo está leyendo en lugar
de fingir que avanza.

El tope no es por el AS400 —el barrido no depende del rango— sino por el JSON
que viaja al navegador, que sí crece.

---

## 11. Qué está probado y qué no

| | Cómo se comprueba | Estado |
|---|---|---|
| El total, las tolerancias, las clases | `php cli/probar-excel.php`, 12 casos | **probado** |
| El resumen, los avisos, las formas de pago | el mismo script, 17 comprobaciones | **probado** |
| El `.xlsx`: cinco hojas, XML válido, filtros, panel fijo | el mismo script abre el ZIP | **probado** |
| La pantalla: pintado, filtros, ficha, móvil, tema oscuro | navegador con respuesta simulada | **probado** |
| Que los campos se llamen como creemos | `probar-as400.php`, paso 4 | **confirmado 19/11/2026** |
| Que las claves crucen | `probar-as400.php`, paso 7 | **confirmado**: cero huérfanos |
| Que la fórmula cuadre con los pagos reales | tres documentos a mano | **confirmado** al céntimo |
| De dónde sale la espera | `diagnostico-consultas.php` | **medido** (§10) |
| Un mes entero de principio a fin | `auditoria.php --mes=2026-11 --excel` | **confirmado** (§12) |
| Que el `.xlsx` de producción abra limpio | a mano | **pendiente** |
| La pantalla con el AS400 detrás | a mano | **pendiente** |

El procedimiento completo, paso a paso y con lo que hay que mirar en cada
salida, está en `docs/PRUEBAS-AS400.md`.

---

## 12. La primera corrida contra producción

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

Todas las reglas aguantaron contra datos reales, y los totales cuadran solos,
que es la comprobación que no se puede falsear:

```
  537.165.668,58 - 536.630.053,16  =  535.615,42
  535.586,27 (lo que falta)  +  29,15 (neto del redondeo)  =  535.615,42
```

Lo que encontró: seis documentos con **535.586,27 Bs cobrados y sin asentar**.
Los de 80 % y los de 20 % son las dos caras de lo mismo —una factura financiada
donde se asentó sólo una de las dos partes— y el de 0,0 %,
`RORI PORLAMAR · FC 54250`, son 203.239,63 Bs facturados sin ninguna forma de
cobro registrada.

---

## 13. Trampas que ya costaron caro

Si va a tocar algo, lea esto antes. Todas pasaron.

| La trampa | Qué provoca | Dónde está el remedio |
|---|---|---|
| La eñe de `NFAÑDC` | «columna no encontrada» señalando un campo que existe | `ModeloAS400::ejecutar()` |
| La clave sin normalizar | todo descuadrado, sin un solo error | `(int)` en `ModeloAuditoria::clave()` |
| `IDTA116` unido sin agrupar | el total pagado inflado; «cuadra de más» | `catalogoFormas()` con `GROUP BY` |
| Marcadores `?` contra columnas numéricas | cero filas y cero errores | números incrustados, ya validados |
| Texto ANSI sin convertir | `json_encode()` devuelve `false`; respuesta vacía | `as400_a_utf8()` |
| `AS400_LIBRERIAS=desarrollo` | auditar copias viejas sin notarlo | el paso 1 de `probar-as400.php` |
| Algo impreso antes del `.xlsx` | «Excel encontró contenido ilegible» | temporal + búferes vaciados |
| `new Date('2026-11-17')` en el navegador | todas las fechas corridas un día | partir el texto |
| Un aviso de PHP en medio de un JSON | «Unexpected token» sin pista | `display_errors off` en el `.htaccess` |

---

## 14. Lo que queda abierto

| | Pregunta | Quién la contesta |
|---|---|---|
| A | El índice de `RTP325`. Es lo único abierto que no es de programación | sistemas |
| B | ¿`OT` se da de alta en `IDTA116`? Mientras no, su columna «tipo» sale de una declaración en el código | sistemas |
| C | ¿La clase 2 («AJUS») se trata como `NO APLICA` con la bendición del negocio, o sólo porque se comporta así? | contabilidad |
| D | Los 6 documentos a revisar de noviembre, ¿son cobros que faltan de verdad? | la tienda, con la factura delante |
| E | Firmar el enlace de la intranet (HMAC con caducidad) para que esto autentique y no sólo autorice | pendiente de decidir |

Cerradas: el tope de 93 días se queda (un mes tardó 18,26 s y el barrido no
depende del rango); y no hace falta filtrar por tienda en la consulta (serían 55
consultas de 1 s contra un barrido de 10 s).

---

## 15. Cómo se toca esto sin romperlo

- **Si cambia el juicio** —la fórmula, una tolerancia, una clase— cámbielo en
  `servicios/Auditoria.php` y **sólo ahí**. La pantalla y el Excel no deciden
  nada; si acaba escribiendo un número en `auditoria.js`, hay dos reglas.
- **Si cambia una regla, cambie también la cabecera de la clase.** Esos
  comentarios son la fuente de verdad del negocio: llevan las mediciones que
  justifican cada decisión, y una regla nueva sin su medición es una opinión.
- **Corra `php cli\probar-excel.php` antes y después.** No necesita servidor.
- **Si toca el AS400** —un campo, un archivo, una consulta— corra
  `php cli\probar-as400.php` con la VPN desconectada y mire los pasos 5 y 7.
- **Si cambia la pantalla**, mírela en móvil y en tema oscuro. Las dos están
  probadas y conviene que sigan estándolo.
- **Si cambia algo que ve un usuario**, actualice `docs/MANUAL-USUARIO.md` y
  regenere los PDF en el mismo cambio. Si es una decisión técnica no evidente,
  este manual, con el porqué. Si es un paso de instalación,
  `docs/INSTALACION.md`.
- **Al subir la versión**: suba `version` en `config/pie.php`; suba
  `identidad.version` e `identidad.build` en `docs/manuales.json`; añada una
  fila al historial de abajo; y regenere los manuales.

Las capturas de pantalla de la aplicación y del Excel están en `docs/img/`
(`pantalla-inicio.png`, `pantalla-resultado.png`, `pantalla-oscuro.png`,
`pantalla-movil.png`, `ficha-documento.png`, `excel-resumen.png`,
`excel-a-revisar.png`, `excel-formas-de-pago.png`). Si la pantalla cambia, se
cambian.

---

## 16. Historial de versiones

| Versión | Cuándo | Qué trajo |
|---|---|---|
| 1.0.0 | Noviembre 2026 | Primera versión en producción. La auditoría contra el AS400 en vivo, con el juicio portado entero de `ventas-ia-agentes` y medido de nuevo; la pantalla de una sola página; el `.xlsx` de cinco pestañas escrito sin Excel ni Composer; las cuatro herramientas de consola; la regla de la nota de crédito de clase 2, encontrada el 19/11/2026; y la primera corrida contra producción —4.004 documentos en 18,26 s— que confirmó todas las reglas, y la segunda —4.196 documentos en 52,60 s— que la hizo desde la pantalla. |

> El número de versión sale del archivo `VERSION` de la raíz del proyecto: lo leen el pie de la aplicación (`config/pie.php`) y este generador de manuales, así que no hay dos sitios donde pueda discrepar. El rótulo de entorno —«sin validar accesos», «bibliotecas de pruebas»— no se escribe: lo deduce `config/pie.php` del `.env`.
