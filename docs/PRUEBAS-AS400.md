# Pruebas contra el AS400 — instrucciones

## Lo que ya quedó confirmado (corrida del 19/11/2026, producción)

El paso 1 se corrió y salió bien en lo que importaba:

| | |
|---|---|
| Conexión con `192.1.1.2` | 0,38 s |
| Los cinco archivos existen | sí, en las bibliotecas del mapa de producción |
| Los campos de `IDTA116` y `ETP045` | los cuatro de cada uno |
| **Las claves cruzan** | 209 de 210 con detalle, 208 de 210 con pagos, **cero huérfanos** |
| El nombre de la tienda sale de `ENBTDA` | sí: `12 -> RORI PORLAMAR` |
| La fórmula del total | cuadra al céntimo en los tres documentos revisados a mano |

El cruce de claves era el riesgo grande y está descartado. Las tres consultas
principales leen bien, así que la conversión de la eñe (`NFAÑDC`) funciona.

> **El «FALLO» del paso 4 era del comprobador, no del programa.** Leía el
> nombre del campo del catálogo sin convertirlo a UTF-8, así que comparaba
> `NFA·DC` contra `NFAÑDC` y decía que faltaba un campo que estaba. Arreglado:
> al volver a correrlo, los cinco archivos tienen que salir en verde.

### El mes entero: hecho

`php cli\auditoria.php --mes=2026-11 --excel`, el 19/11/2026:

```
  4.004 documentos  ·  19 días  ·  537.165.668,58 Bs  ·  18,26 s

  cuadran al céntimo   3.951 (98,7 %)     el detalle cuadra   3.972 de 3.972
  redondeo                46 (92,33 Bs)   NO cuadra                        0
  A REVISAR                6 (535.586,27 Bs por asentar)
```

Todas las reglas aguantaron, y los totales cuadran solos al céntimo. El detalle
está en [`PLAN.md`](PLAN.md) §3.6.

### La pantalla: hecha

El 20/11/2026 a las 08:43, del 1 al 20 de noviembre: **4.196 documentos en
52,60 s**, 98,7 % cuadran, cero descuadres de detalle. La interfaz funciona con
el AS400 detrás.

De ahí salió una corrección: `RTP325` tardó 42,03 s frente a los 9,67 s de la
víspera. El barrido no depende del rango sino de la carga del servidor, así que
donde se decía «unos veinte segundos» ahora se dice un rango. Ver
[`PLAN.md`](PLAN.md) §3.6.

**Los cuatro pasos están hechos.** Lo único que queda es la petición a sistemas
de [`INDICE-RTP325.md`](INDICE-RTP325.md).

### La lentitud de `RTP325`: medida y explicada

`RTP325` tardaba 40 s para un solo día. `php cli\diagnostico-consultas.php` lo
cerró: el archivo tiene **6.595.139 filas y ningún índice por fecha**, así que
el AS400 lo barre entero cada vez.

Dos medidas que no dejan otra lectura posible:

- Un día (449 filas) tardó 22,22 s; **el mes entero (8.547 filas) tardó 17,11 s**.
  Diecinueve veces más datos en el mismo tiempo.
- Por fecha, 22,22 s. Añadiendo la tienda, **1,08 s**. Por la clave del
  documento, **0,12 s**.

Se descartaron el `GROUP BY` (6,76 s agrupando contra 7,65 s sin agrupar), el
filtro de tipo y el campo del siglo. **La consulta no tiene arreglo desde aquí**
y se queda como está: un mes cuesta lo mismo que un día, entre veinte segundos
y un minuto según la carga del servidor.

**Lo que sí hay que hacer: pasarle a sistemas
[`INDICE-RTP325.md`](INDICE-RTP325.md).** Es una sentencia, no cambia el
archivo ni ningún programa, y convierte esa espera en décimas.

---

## El resto de las instrucciones

Lo que queda es lo que **sólo el AS400 puede contestar**, y necesita que lo
corras tú desde un equipo con la VPN **desconectada**.

Son tres pasos y unos minutos. Después de cada uno, pásame la salida **completa**
tal cual sale por pantalla: no la resumas, porque lo que hay que mirar suele ser
justo el detalle que parece irrelevante.

```
cd C:\xampp\htdocs\AppWeb\IndustriasRRC\reporte-auditoria-ventas
```

---

## Antes de empezar: el `.env`

Te dejé un `.env` creado a partir de `.env.example`, **sin credenciales**.
Rellena estas tres líneas:

```ini
AS400_HOST=
AS400_USER=
AS400_PASS=
```

Y comprueba esta, que es la que más daño puede hacer:

```ini
AS400_LIBRERIAS=produccion
```

> **Por qué importa.** Con `desarrollo`, el mapa apunta `IDP210` a
> `CFLORES.IDP210` y `IDP116N` a `AGARAY.IDP116N`, que son **copias**. Una
> auditoría «en vivo» contra una copia de hace un mes da números, y están mal,
> y no se nota mirándolos. Te lo dejé en `produccion` por eso. Si prefieres
> probar primero contra las copias, ponlo en `desarrollo` — pero entonces los
> números de la prueba no significan nada más que «la mecánica funciona».

El `.env` no se versiona (está en el `.gitignore`), así que la clave no sale de
tu equipo.

---

## Paso 1 — ¿Contesta el AS400 lo que esperamos?

```
php cli\probar-as400.php
```

Comprueba siete cosas, en orden, y se para en el primer fallo real:

1. Que el `.env` está relleno, y **te dice qué mapa de bibliotecas está usando**.
2. Que la extensión ODBC de PHP está habilitada.
3. Que la conexión se abre, y cuánto tarda.
4. Que los cinco archivos existen donde el mapa dice:
   `IDP210`, `RTP325`, `IDP116N`, `IDTA116`, `ETP045`.
5. **Que cada archivo tiene los campos que la aplicación lee.** Si falta alguno,
   te lista los campos reales que empiezan parecido, para poder elegir el bueno.
6. Que una consulta de verdad devuelve filas, con el tiempo de cada una.
7. **Que las claves cruzan entre los tres archivos.**

### Lo que más me interesa de esa salida

**El paso 5.** Los nombres de los campos de `IDP210` y de `IDP116N` salen del
volcado del catálogo que hicimos en el proyecto hermano, así que *deberían*
estar. Pero `ETP045` nunca se llegó a leer desde PHP: sus cuatro campos
(`ECDTDA`, `ENBTDA`, `ENBRZS`, `ESTTDA`) salen de un sondeo, y si uno se llama
distinto, el informe saldría con todas las tiendas como «(tienda 47)».

**El paso 7, que es el que de verdad importa.** Tiene que decir algo así:

```
  Encabezados del día                    120
  …que encuentran su detalle             118 de 120  (98,3 %)
  …que encuentran sus formas de pago     119 de 120  (99,2 %)
```

Si en vez de eso dice `0 de 120`, **el informe no sirve** aunque luego salgan
números bonitos: significa que el número de documento llega con formatos
distintos desde cada archivo y no empareja. Es el fallo más caro de todos
porque no da ningún error — las facturas salen con «pagado 0,00» y «falta todo».
Si pasa eso, pásame la salida entera: lo que hay que mirar es cómo llega
`NNMDOC` desde `IDP210` y `FNMDOC` desde `IDP116N`.

### Si falla

Cada paso dice qué hacer. Los tres fallos probables:

| Mensaje | Qué suele ser |
|---|---|
| No se pudo conectar | la VPN está activa, o `AS400_DRIVER` no coincide con el instalado |
| Columna no encontrada, y el nombre lleva **ñ** | la conversión de códigos; dímelo, es cosa mía |
| El AS400 no tiene ese archivo en esa biblioteca | el mapa de `config/librerias.txt` |

Para probar otro día (por si el de ayer fue domingo):

```
php cli\probar-as400.php --fecha=2026-11-17
```

---

## Paso 2 — Un día entero, de principio a fin

```
php cli\auditoria.php --desde=2026-11-17 --hasta=2026-11-17
```

Esto ya es la auditoría de verdad: lee, cruza, juzga y te lo cuenta por
pantalla. Un día es poco dato y rápido, así que es el primer sitio donde mirar
si los números tienen sentido.

### Lo que hay que mirar

- **«cuadran al céntimo»** tiene que ser la inmensa mayoría. En noviembre de
  2026 fue el 98,5 %. Si sale el 3 % o el 50 %, algo está mal en la fórmula del
  total o en el cruce de claves, no en las tiendas.
- **«A REVISAR»**, si hay alguno: coge uno, ábrelo en el AS400 y dime si de
  verdad le falta un pago. Esa es la comprobación que ningún script puede hacer.
- **Los avisos del final.** Si aparece «ATENCIÓN: … DESCUENTO SENIAT distinto de
  cero», hay que revisar la fórmula antes de usar el informe: ese importe valía
  cero en todo lo que se midió.
- **Cuánto tardó.** Sale arriba. Me hace falta para saber si el tope de 93 días
  es razonable.

---

## Paso 3 — Un mes, y el Excel

```
php cli\auditoria.php --mes=2026-11 --excel
```

Escribe el `.xlsx` en `almacen\auditoria\` y te dice la ruta. Ábrelo.

### Lo que hay que mirar

1. **Que abre sin el aviso de «Excel encontró contenido ilegible»**. Si sale ese
   aviso, el archivo tiene un XML mal escrito y hay que arreglarlo; dímelo con
   el texto exacto del aviso.
2. **Las cinco pestañas**: Resumen, A revisar, Auditoría, Formas de pago,
   Método.
3. **Que las fechas de la columna «Fecha» sean fechas**, no texto: ordena por
   esa columna y mira si ordena bien.
4. **Que los filtros funcionen** en la pestaña «Auditoría» (la cabecera tiene
   autofiltro y las dos primeras columnas quedan fijas al desplazar).
5. **Que la pestaña «Formas de pago» sume lo mismo** que el «Total en formas de
   pago» del Resumen. Si no coincidieran, una de las dos estaría contando mal.

**Compáralo con el de siempre.** Corre el mismo mes en el proyecto hermano:

```
cd ..\ventas-ia-agentes
php cli\auditoria-pagos.php --mes=2026-11
```

Los dos leen lo mismo de sitios distintos —uno del MySQL cargado, el otro del
AS400 en vivo— así que **no tienen por qué dar idénticos**: el nuevo verá lo que
se facturó después de la última carga. Pero el número de documentos, el total
facturado y la lista de «a revisar» tienen que parecerse mucho. Si no se parecen
en nada, pásame las dos salidas.

---

## Paso 4 — La pantalla

Abre la aplicación en el navegador, elige un rango y pulsa **Auditar**.

La pantalla ya está probada con datos simulados: pinta, filtra, abre la ficha de
cada documento, funciona en móvil y en tema oscuro, y no da un solo error de
consola. Lo que falta por ver es el comportamiento con el AS400 detrás:

- **Cuánto se tarda de verdad.** Mientras espera, el loader va diciendo qué
  archivo está leyendo. Si se queda siempre atascado en el mismo, ésa es la
  pista.
- **Si se agota el tiempo.** El límite está en 180 segundos
  (`php/auditoria/consultar.php`). Si un mes no cabe, dímelo y lo subimos o
  bajamos el tope de días.
- **Que el Excel descargado sea el que se ve.** Audita un rango, mira el número
  de «documentos auditados» en pantalla, descarga, y comprueba que el Resumen
  del archivo dice lo mismo. Para eso está la caché.

### Si la pantalla no se abre

En este equipo, el Apache de XAMPP **no está sirviendo**
`htdocs\AppWeb\IndustriasRRC\`: probé `http://localhost/AppWeb/...` y devuelve
404, aunque la carpeta está ahí. Puede ser que el Apache que está corriendo sea
otro (en los documentos del proyecto hermano aparece un `C:\AppServ\www`), o que
falte un alias.

Mientras lo aclaramos, para verla basta con:

```
cd C:\xampp\htdocs\AppWeb\IndustriasRRC\reporte-auditoria-ventas
php -S 127.0.0.1:8899
```

y abrir `http://127.0.0.1:8899/`. Es el servidor propio de PHP: sirve para
mirarla y probarla, no para que la use la gente.

---

## Resumen de qué pasarme

| Paso | Qué necesito |
|---|---|
| 1 | La salida **completa** de `probar-as400.php`, sobre todo los pasos 5 y 7 |
| 2 | La salida completa del día, y si un «A REVISAR» es de verdad |
| 3 | Si el `.xlsx` abre limpio, y qué tal se parece al del proyecto hermano |
| 4 | Cuánto tarda un mes en la pantalla |

Con eso cierro lo que queda. Si algo falla antes de llegar al final, para ahí y
mándame lo que salió: cada paso está pensado para que el fallo diga de qué va.
