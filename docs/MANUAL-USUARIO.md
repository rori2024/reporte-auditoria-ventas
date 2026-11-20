<p align="center">
  <img src="../vistas/img/industrias-rrc.png" alt="Industrias RRC, C.A." width="150">
</p>

# Manual de usuario · Auditoría de Formas de Pago

Para quien audita lo que cobran las tiendas: contabilidad, auditoría interna y
quien tenga que responder por el dinero de un período.

No hace falta saber de computación ni de AS400. La aplicación tiene una sola
pantalla, se usa con dos fechas y un botón, y todo lo que decide está explicado
en este manual. Si algo no le sale, al final está el teléfono de soporte.

## Qué contesta esta aplicación

Una pregunta que hoy no contesta nadie: **¿cuadra cada factura con lo que se
cobró por ella?**

Una factura del AS400 vive repartida en tres archivos, y los tres tienen que
contar lo mismo:

| Archivo | Qué guarda | Dice |
|---|---|---|
| `IDP210` | el encabezado | cuánto se vendió |
| `RTP325` | el detalle | qué se vendió |
| `IDP116N` | las formas de pago | con qué se pagó |

Si la suma de las formas de pago no llega al total de la factura, **falta un
cobro por asentar**: dinero que entró y que no quedó registrado, o una parte
financiada que nadie anotó.

A mano nadie lo mira, y no es por desidia: son del orden de 3.800 documentos al
mes contra 5.200 líneas de pago. La aplicación los contrasta uno a uno y le
señala los pocos que hay que ir a ver.

> **Esto no acusa a nadie.** El informe dice lo que se ve en el archivo —«se
> registró el 80 % del total y la forma es CASHEA»— y nada más. Por qué pasó lo
> decide quien tenga la factura delante.

---

## Antes de empezar

### Cómo se entra

La aplicación se abre desde la intranet, como los demás programas de la casa.
No tiene usuario ni clave propios: entra con el suyo y la intranet comprueba
que tenga concedida esta aplicación.

Si junto al nombre de la aplicación ve un distintivo **PRUEBAS**, está en un
equipo donde la comprobación de permisos está apagada a propósito. En el equipo
de verdad ese distintivo no aparece.

### Cómo es la pantalla

Hay una sola pantalla y se lee de arriba abajo, en el orden en que se decide:

1. **Qué período se audita** — las dos fechas y el botón `Auditar`.
2. **El veredicto** — las cifras grandes: ¿hay algo que revisar?
3. **Lo que hay que revisar** — lo único sobre lo que hay que hacer algo.
4. **Lo que este informe advierte de sí mismo** — los avisos.
5. **En qué se cobró** — las formas de pago del período.
6. **Documento a documento** — todo, filtrable y buscable.

Mientras no pida un período, debajo del formulario no hay nada. Es a propósito:
cada consulta hace trabajar al AS400 entre veinte segundos y un minuto, y una
pantalla que consulta sola gastaría eso cada vez que alguien la abre por error.

### Lo que conviene mirar

Lo normal es auditar **un mes cerrado** cuando se cierra, y **el mes en curso**
una vez por semana para no acumular. Lo primero que hay que mirar siempre es la
cifra **A REVISAR**: si está en cero, ese período no necesita nada más.

### Dos cosas que ahorran un disgusto

- **Con la VPN activa no se llega al AS400.** Es, con diferencia, el motivo
  número uno de las llamadas a soporte. Si la consulta falla con «No se pudo
  conectar con el servidor AS400», desconecte la VPN y vuelva a intentarlo.
- **Una consulta tarda entre veinte segundos y un minuto**, lo mismo un día que un mes
  entero. No es que esté colgada; está leyendo. Más abajo se explica por qué.

---

## 1. Elegir el período y auditar

### Poner las fechas a mano

El recuadro de la derecha trae dos campos, **Desde** y **Hasta**. Vienen
puestos en el primer día del mes en curso y en hoy. Ninguno de los dos admite
una fecha posterior a hoy: el futuro no se audita porque todavía no ha
ocurrido.

Puestas las dos fechas, pulse **Auditar**.

### Usar un atajo

Debajo del botón hay cuatro atajos: **Este mes**, **Mes pasado**, **Ayer** y
**Hoy**. Cada uno rellena las dos fechas y lanza la consulta de una vez; no hace
falta pulsar `Auditar` después.

### El tope de 93 días

De una vez se pueden pedir hasta **93 días**. Si pide más, la aplicación se lo
dice con el número exacto de días que pidió y no consulta. Un año se pide mes a
mes, y así además un fallo no se lleva por delante lo que ya había salido bien.

### Mientras espera

Durante la espera aparece el cargador de la casa y debajo va diciendo qué está
leyendo:

```
leyendo el maestro de tiendas y el catálogo de formas de pago
leyendo el encabezado de factura, IDP210
leyendo el detalle de factura, RTP325 · es el paso largo,
son 6,6 millones de líneas sin índice por fecha
leyendo las formas de pago, IDP116N
cruzando los tres archivos documento a documento
```

El paso largo es siempre el mismo, y por un motivo conocido: el archivo del
detalle tiene 6.595.139 líneas y el AS400 no tiene ninguna forma rápida de
buscar en él por fecha, así que lo recorre entero. Por eso **un día tarda lo
mismo que un mes**. Hay una petición hecha a sistemas para arreglarlo; mientras
tanto, son entre veinte segundos y un minuto, según cómo esté de cargado el
servidor.

> No vuelva a pulsar mientras espera. Cada pulsación abre otra consulta al
> AS400 sobre el mismo período, y las dos compiten entre sí: se tarda más, no
> menos. El botón `Auditar` se deshabilita solo mientras hay una consulta en
> marcha.

### Volver a consultar

En la cabecera del veredicto, el botón **Volver a consultar** repite la consulta
con las mismas fechas. Se usa cuando se acaba de corregir algo en la tienda y
quiere comprobar que ya cuadra.

Al lado, en letra pequeña, está la ficha de la corrida: el período en palabras,
la hora exacta a la que se leyó el AS400 y lo que tardó. Si pasa el ratón por
encima de esa línea, verá cuánto tardó cada uno de los archivos.

---

## 2. El veredicto

### Las cinco cifras grandes

| Cifra | Qué cuenta |
|---|---|
| **Documentos auditados** | todos los del período, y cuántos días tuvieron movimiento |
| **Cuadran al céntimo** | los que no hay ni que mirar, y qué porcentaje son |
| **Diferencia de redondeo** | céntimos del IGTF; debajo, cuántos bolívares suman en total |
| **A REVISAR** | los que hay que ir a ver, y cuánto dinero falta por asentar |
| **Total facturado** | lo vendido en el período y, debajo, lo registrado en formas de pago |

La ficha de **A REVISAR** se marca en ámbar cuando hay alguno. Si no hay
ninguno, dice «ni uno: todo cuadra».

### La frase del veredicto

Justo debajo de las cifras hay una frase que responde a «¿hay algo mal?» sin
tener que interpretar ningún número. Cuando hay algo, dice cuántos documentos
son, cuántos bolívares faltan y que están en la tabla de abajo, ordenados por
tamaño.

### La línea de contrastes

Más abajo, en una sola línea, el resto de las cuentas del período: en cuántos
documentos el detalle cuadra con el encabezado, en cuántos no, en cuántos no
aplica, cuántas anuladas hay, cuántas no tienen ni una línea de pago y cuántas
son facturas manuales.

---

## 3. Qué significa cada resultado

Cada documento sale con uno de estos cuatro resultados. Es la columna
**Resultado** de la tabla grande, y el primer dato de la ficha.

| Resultado | Cuándo | Qué significa para usted |
|---|---|---|
| `cuadra` | la diferencia no pasa de **0,01 Bs** | nada que hacer |
| `redondeo` | no pasa de **5,00 Bs** | céntimos del IGTF; no es dinero que falte |
| `REVISAR` | pasa de **5,00 Bs** | hay que ir a ver esa factura |
| `no aplica` | no hay nada que contrastar | nada que hacer |

### Por qué el corte está en 5 bolívares

No es un número elegido para que salgan pocos avisos. Se midieron las
diferencias reales y no se reparten poco a poco: forman dos grupos separados por
un abismo.

```
  47 documentos entre     0,02 y      4,38 Bs   (45 de ellos con IGTF)
   8 documentos entre 2.000,00 y 168.136,17 Bs
```

Entre 4,38 y 2.000,00 bolívares **no hay nada**. El corte cae dentro de ese
hueco, así que ponerlo en 10, en 100 o en 1.000 clasificaría exactamente igual.
En la primera corrida contra producción el reparto se repitió: los 46 de
«redondeo» sumaban 92,33 Bs entre todos —dos bolívares de media— y los seis «a
revisar» empezaban en 2.000.

### De dónde sale el total contra el que se compara

El AS400 guarda seis importes en el encabezado y ninguno se llama «total». El
que usa este informe se midió contra los pagos reales de 3.626 documentos, y
acierta en el **98,5 %**; en la primera corrida contra producción, sobre 4.004
documentos, acertó en el **98,7 %**.

```
TOTAL = bruto - descuento + IVA + IGTF
```

En la ficha de cada documento verá esa cuenta hecha, importe por importe, con el
nombre que tiene cada uno en el AS400. Y verá también los dos importes que
quedan **fuera** de la fórmula —el descuento SENIAT y el abono—, marcados como
tales, para que nadie tenga que fiarse de que están donde se dice.

---

## 4. Lo que NO es un descuadre, aunque lo parezca

Hay tres clases de documento que parecen descuadrados y no lo están. El informe
los conoce y no los marca. Conviene saberlo, porque son los que más preguntas
generan.

### Las facturas anuladas

Una factura anulada queda con cero piezas y cero venta en el encabezado, pero
**conserva sus líneas de detalle**. Es el comportamiento correcto del AS400, no
un error. Y además cuadran en pagos: en la primera corrida contra producción,
las 110 anuladas del mes cuadraron todas.

Salen en la tabla grande con el estado `ANULADA`, y no se marcan a revisar.
Marcarlas haría el informe falso en casi cien filas.

### Los abonos: notas de crédito de clase «ABON»

Un abono no mueve mercancía: mueve **dinero**. Es lo que el cliente entrega a
cuenta de un apartado. Sus líneas de detalle son la mercancía de la factura
original, que no tiene por qué sumar lo que se abonó.

Así que en un abono **el contraste del detalle no aplica** —en la tabla verá un
guion en la columna «Dif. det.», no un cero— pero el dinero sí entró y sí tiene
forma de pago. Los 31 abonos del mes medido cuadraron los 31.

### Los ajustes: notas de crédito de clase «AJUS»

Un ajuste se descuenta de la factura que corrige. No lleva mercancía propia ni
movimiento de dinero propio: de las 55 que hay desde enero de 2024, **ni una
tiene detalle ni forma de pago**. No hay nada que contrastar, así que salen como
`no aplica`.

> Esta regla salió de un caso real: `CCCT · NC 26829`, 42,40 Bs, siete piezas en
> el encabezado, cero líneas de detalle y cero formas de pago. Con las reglas de
> antes salía como «falta por asentar 42,40 Bs». No faltaba nada.

---

## 5. Lo que hay que revisar

Este panel sólo aparece cuando hay algo. Es la única parte del informe sobre la
que hay que hacer algo, y por eso va arriba.

### Cómo se lee la tabla

Las filas vienen ordenadas **de mayor a menor diferencia**: lo primero que ve es
lo más caro.

| Columna | Qué es |
|---|---|
| Fecha, Tienda, Documento | dónde está la factura que hay que buscar |
| Total | lo que dice el encabezado que se vendió |
| Pagado | la suma de todas sus formas de pago |
| Falta | la diferencia; es el dinero que no está asentado |
| % | qué parte del total sí quedó registrada |
| Formas registradas | con qué se cobró lo que sí se registró |
| Qué se ve en el archivo | la observación, explicada abajo |

Un número **negativo** en «Falta» no significa que falte: significa que se
registró de **más** que el total de la factura. También hay que mirarlo, pero es
otra cosa.

### Cómo se lee la columna «Observación»

En la pantalla esta columna se titula **«Qué se ve en el archivo»**, y en el
Excel, **«Observación»**. El nombre no es casualidad: lo que dice es el patrón
que se observa, no la causa.

- «Falta por asentar 35.835,12 Bs: se registró el 80,0 % del total con 1 forma
  de pago» es **un hecho** que está en el archivo.
- «El cajero no asentó la inicial» sería **una acusación** que el archivo no
  respalda.

Cuando lo registrado es financiamiento —CASHEA o VIBES—, la observación añade
que lo que falta *sería* la inicial que paga el cliente. Cuando no lo es, que lo
que falta *sería* la parte financiada o un segundo cobro. En los dos casos está
en condicional a propósito: es la lectura más probable de lo que se ve, no un
veredicto.

Los patrones que más se repiten:

| Lo que dice | Lo que suele haber detrás |
|---|---|
| «No tiene ni una línea de pago registrada» | la factura se emitió y el cobro no se asentó nunca |
| «se registró el 80 %» con una forma de financiamiento | se asentó la parte financiada y falta la inicial |
| «se registró el 20 %» sin financiamiento | se asentó la inicial y falta la parte financiada |
| «Se registró X Bs MÁS que el total» | un cobro duplicado, o un importe tecleado de más |

### Qué hacer con un documento «A REVISAR»

1. **Ábralo.** Pulse su fila en la tabla «Documento a documento» para ver la
   ficha completa. Ahí está el diagnóstico entero y la cuenta de dónde sale el
   total.
2. **Anote** la fecha, la tienda, el tipo y el número del documento, lo que
   falta y el porcentaje registrado.
3. **Busque la factura**, en la tienda o en el AS400, y mire cómo se cobró de
   verdad.
4. **Decida**, que es lo que ningún programa puede hacer:
   - si se cobró y no se asentó, hay que asentar el cobro que falta;
   - si está financiada, mire si falta la inicial o la parte financiada;
   - si el cobro sí está y la aplicación no lo ve, avísele a soporte: eso sí
     sería un fallo del informe y hay que mirarlo.
5. **Compruebe.** Una vez corregido, pulse **Volver a consultar** con el mismo
   período: ese documento tiene que pasar a `cuadra`.

> Lo que encontró el primer mes contra producción: **535.586,27 Bs cobrados y
> sin asentar** en seis facturas. Una de ellas, `RORI PORLAMAR · FC 54250`, eran
> 203.239,63 Bs facturados sin una sola línea de pago registrada. Nadie lo
> miraba.

---

## 6. Los avisos

El panel **«Lo que este informe advierte de sí mismo»** es lo que el informe no
se calla: supuestos que podrían haber dejado de ser verdad desde que se
midieron, y cosas que se encontraron y no caben en ninguna columna.

Los que más se ven:

| Aviso | Qué quiere decir |
|---|---|
| Documentos con **descuento SENIAT** distinto de cero | la fórmula del total se midió donde ese importe era siempre cero; hay que revisarla antes de dar las cifras por buenas |
| Encabezados con una **fecha imposible** | el AS400 trae un día que no existe en el calendario; esos documentos NO están en el informe |
| Formas de pago **sin encabezado** en el archivo de facturas | cobros registrados contra un documento que no existe; no salen en la tabla porque la tabla es una fila por factura |
| La forma de pago `OT` | son «otros pagos»; está confirmado que no tienen que ver con financiamiento, y queda pendiente darla de alta en el catálogo |
| El período llega a un día que **todavía no ha ocurrido** | pedir el mes entero el día 20 no deja diez días sin auditar: los deja sin ocurrir |
| Días sin documentos dentro del tramo | pueden ser cierres legítimos: domingos, feriados |

Un aviso **no** significa que el informe esté mal. Significa que hay algo que
mirar antes de firmarlo. Los dos primeros de la tabla son los serios: si
aparecen, consulte con soporte antes de entregar las cifras.

---

## 7. En qué se cobró

La tabla de formas de pago del período: código, descripción, tipo, cuántas
líneas, en cuántos documentos, cuántos bolívares y qué porcentaje del total
representa cada una. Ordenadas de mayor a menor.

La descripción y el tipo salen del catálogo de formas de pago del AS400. Las
formas que **no** están dadas de alta en ese catálogo salen marcadas, con su
propio aviso: de una forma que no está en el catálogo no se puede saber, leyendo
el archivo, si es financiamiento o no, y eso cambia cómo se lee la factura donde
aparece. Hoy la única en ese caso es `OT`.

Cuando una forma es de financiamiento, la columna **Tipo** lo dice con una
marca.

---

## 8. Documento a documento

Aquí está todo el período, una fila por documento.

### Filtrar por resultado

Los botones **Todo · A revisar · Redondeo · Cuadran · No aplica** dejan a la
vista sólo lo que elija. El que está puesto se ve hundido.

### Filtrar por tienda

La lista desplegable trae las tiendas que tienen documentos en el período, no
todas las de la empresa.

### Buscar

El campo de búsqueda mira en el número de documento, el tipo, el cliente, la
cédula o RIF, el vendedor, la caja, la tienda y el desglose de formas de pago.
**No** busca dentro de la observación: ahí hay palabras como «factura» o «pago»
en casi todas las filas, y el filtro dejaría de filtrar.

### Ver más filas

La tabla pinta **300 filas** y el resto a petición, con el botón **Ver 300 filas
más**, que dice cuántas quedan. No es un tope: es que crear tres mil filas de
golpe deja el navegador bloqueado un par de segundos. Si busca algo concreto, el
filtro es más rápido que bajar.

Debajo de los filtros, una línea dice siempre cuántas filas está viendo, cuántas
pasan el filtro y cuántas tiene el período entero.

### Las columnas que menos se explican solas

| Columna | Qué es |
|---|---|
| Clase | Factura, Nota de crédito, Abono o Ajuste |
| Estado | `Vigente` o `ANULADA` |
| Detalle | lo que suman las líneas de la factura, en neto |
| Dif. det. | la diferencia entre el encabezado y el detalle; un guion significa que en esa clase no aplica |
| Dif. pago | lo que falta por asentar; es la cifra del veredicto |

---

## 9. La ficha de un documento

Pulse cualquier fila de la tabla —con el ratón, o con Enter si va con el
teclado— y se abre la ficha del documento. Trae cuatro bloques:

1. **Qué se ve en el archivo** — el diagnóstico completo, sin recortar.
2. **El contraste** — resultado, total de la factura, suma de formas de pago,
   diferencia y porcentaje registrado.
3. **De dónde sale el total** — la cuenta importe por importe, con el nombre de
   cada campo del AS400, y los dos importes que quedan fuera de la fórmula.
4. **El detalle y las formas de pago** — líneas, piezas en el encabezado y en el
   detalle, y el desglose de con qué se pagó.

Al final están la fecha, la tienda con su código, la clase de documento y, si lo
tiene, el cliente, el vendedor, la caja y la hora.

Se cierra con la equis, pulsando fuera de la ficha o con la tecla `Esc`.

---

## 10. Descargar el Excel

El botón **Descargar Excel** está arriba, en la cabecera del veredicto, y abajo,
al final de la tabla. Los dos descargan lo mismo.

### Lo que se descarga es lo que está viendo

El botón **no** vuelve a consultar el AS400: descarga la corrida que tiene en
pantalla. Si volviera a consultar, el archivo no sería el que acaba de revisar
—entre mirar y descargar pasan minutos, y en esos minutos las tiendas siguen
facturando—, y usted tendría dos informes del mismo período con cifras distintas
sin saber cuál creer.

La corrida se guarda **media hora**. Pasada, el botón vuelve a consultar el
AS400, porque a esa altura ya no estaría descargando lo que miró. Si quiere el
archivo exacto que tiene delante y ha pasado un rato largo, pulse **Volver a
consultar** y descargue enseguida.

### Las cinco pestañas

| Pestaña | Qué trae |
|---|---|
| **Resumen** | las cifras del período, los contrastes, el reparto por tipo, dónde está el dinero por asentar y los avisos |
| **A revisar** | sólo lo accionable, una fila por documento, con su observación entera |
| **Auditoría** | todos los documentos, con filtros y las dos primeras columnas fijas |
| **Formas de pago** | en qué se cobró el período |
| **Método** | cómo se calculó: la fórmula, el corte en 5 Bs y qué documentos no se juzgan |

La pestaña **Método** no es relleno. Este informe afirma que faltan cientos de
miles de bolívares por asentar en una factura concreta; quien lo reciba tiene
derecho a saber de dónde sale ese número sin tener que preguntárselo a nadie.

### Para imprimir

El archivo sale listo para llevar a la tienda: apaisado donde hace falta,
ajustado al ancho, con la fila de títulos repetida en cada página y la
numeración en el pie. No hace falta tocar nada antes de imprimir.

El nombre del archivo lleva el período dentro, así:

```
Auditoria-formas-de-pago_20261101_20261120.xlsx
```

---

## Problemas frecuentes

| Lo que ve | Qué hacer |
|---|---|
| «No se pudo conectar con el servidor AS400» | desconecte la VPN y vuelva a intentarlo; es la causa número uno |
| La espera pasa de medio minuto | normal si es la primera consulta del día; el paso largo es el detalle. Si pasa de tres minutos, avise a soporte |
| «El rango pedido son N días y el tope es 93» | pida el período mes a mes |
| «No hay ni un documento» en esas fechas | o son días sin facturación, o el rango está mal. No es que «falte cargar»: esto lee el AS400 en vivo |
| Un aviso ámbar sobre la corrida que no se pudo guardar | el informe en pantalla es bueno; para que el Excel sea exactamente ése, vuelva a consultar y descargue enseguida |
| «El servidor contestó algo que no es una respuesta de esta aplicación» | avise a soporte con la hora exacta: hay que mirar el registro del servidor |
| El Excel no coincide con lo que vio | pasaron más de treinta minutos; vuelva a consultar y descargue de nuevo |
| Una tienda sale como «(tienda 47)» | esa tienda no está en el maestro de tiendas del AS400; avise a soporte |
| Un documento sale «A REVISAR» y en la tienda el cobro sí está | avise a soporte con el documento: eso sí sería un fallo del informe |
| El distintivo **PRUEBAS** junto al título | está en un equipo de pruebas; los números pueden no ser los de producción |

---

## Soporte técnico

| Para qué | A dónde |
|---|---|
| Correo | soporte@rori.com |
| Teléfono | Ext. 2309 / +58 412-333-0319 |
| Horario | Lunes a viernes, de 7:30 a 16:00 |

Desarrollo: Carlos Flores, cflores@rori.com.

Cuando escriba, diga **el período que pidió**, **la hora** a la que lo pidió y,
si es por un documento concreto, **la tienda, el tipo y el número**. Con eso la
consulta se reproduce; sin eso, hay que adivinar.
