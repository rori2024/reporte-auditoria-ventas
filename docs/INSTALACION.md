<p align="center">
  <img src="../vistas/img/industrias-rrc.png" alt="Industrias RRC, C.A." width="150">
</p>

# Guía de instalación · Auditoría de Formas de Pago

Para quien monta el equipo desde el que se consulta el AS400: un servidor con
Apache y PHP, o un puesto de trabajo para probar.

Son unos veinte minutos. La primera parte se puede seguir sin leer nada más; la
segunda explica cada paso para quien necesite entenderlo o hacerlo a mano.

---

## Lo que necesita antes de empezar

| Qué | Cuál, y para qué |
|---|---|
| Windows | con acceso de administrador para instalar el driver |
| PHP | **8.2** o superior, con las extensiones `odbc` y `zip` |
| Apache | con `AllowOverride All` en la carpeta donde cuelgue la aplicación |
| Driver ODBC | IBM i Access Client Solutions (o Client Access), registrado en 64 bits |
| Del AS400 | servidor, usuario y clave, que los da sistemas |
| De la intranet | el id de esta aplicación y los datos de su base de datos |
| La red | sin VPN. **Con la VPN activa no se llega al AS400** |

**No** hace falta Composer, ni `vendor/`, ni Excel instalado, ni Node (salvo que
vaya a regenerar los manuales en PDF, y eso es el paso 8, que es opcional).

---

## Los pasos

### Paso 1 · Comprobar PHP y sus dos extensiones

```
php -v
php -m | findstr /i "odbc zip"
```

La primera orden tiene que decir 8.2 o más. La segunda tiene que imprimir
`odbc` y `zip`. Si falta alguna, vaya al paso 1 de la segunda parte.

### Paso 2 · Instalar el driver ODBC del AS400

Instale **IBM i Access Client Solutions** (el paquete «Windows Application
Package»). Después, compruebe cómo quedó registrado:

```
odbcad32.exe
```

En la pestaña **Controladores** anote el nombre **exacto**. Suele ser:

```
Client Access ODBC Driver (32-bit)
```

> Ese nombre lleva «(32-bit)» pero el instalador lo registra también en 64 bits,
> que es lo que usa PHP. Lo que hay que copiar es el texto literal de esa lista,
> tal cual, con sus paréntesis.

### Paso 3 · Poner la aplicación en su sitio

Copie la carpeta del proyecto bajo el directorio que sirve Apache. En el equipo
de referencia:

```
C:\xampp\htdocs\AppWeb\IndustriasRRC\reporte-auditoria-ventas
```

### Paso 4 · Crear el `.env`

```
cd C:\xampp\htdocs\AppWeb\IndustriasRRC\reporte-auditoria-ventas
copy .env.example .env
notepad .env
```

Rellene estas líneas con lo que le dio sistemas:

```ini
AS400_HOST=192.1.1.2
AS400_USER=SUUSUARIO
AS400_PASS=SUCLAVE
AS400_DRIVER=Client Access ODBC Driver (32-bit)
AS400_LIBRERIAS=produccion
```

> **`AS400_LIBRERIAS=produccion` es obligatorio para auditar de verdad.** Con
> `desarrollo`, el mapa apunta `IDP210` a `CFLORES.IDP210` y `IDP116N` a
> `AGARAY.IDP116N`, que son **copias**. Una auditoría «en vivo» contra una copia
> de hace un mes da números, y están mal, y no se nota mirándolos.

El `.env` no se versiona y el `.htaccess` de la raíz impide que se sirva por
web. La clave no sale del equipo.

### Paso 5 · Comprobar que el AS400 contesta

**Desconecte la VPN** y ejecute:

```
php cli\probar-as400.php
```

Comprueba siete cosas en orden y se para en el primer fallo real. Las dos que
importan de verdad:

- **El paso 5** tiene que encontrar todos los campos de los cinco archivos.
- **El paso 7** tiene que decir algo parecido a esto:

```
  Encabezados del día                    120
  ...que encuentran su detalle           118 de 120  (98,3 %)
  ...que encuentran sus formas de pago   119 de 120  (99,2 %)
```

Si dice `0 de 120`, **pare aquí**: el informe no serviría aunque luego salgan
números bonitos. Llame a soporte con la salida completa.

Si el día que probó fue domingo y no hay documentos, pruebe con otro:

```
php cli\probar-as400.php --fecha=2026-11-17
```

### Paso 6 · Un día entero, de principio a fin

```
php cli\auditoria.php --desde=2026-11-17 --hasta=2026-11-17
```

«Cuadran al céntimo» tiene que ser la inmensa mayoría: en lo medido, el 98,5 %.
Si sale el 3 % o el 50 %, algo está mal en la fórmula del total o en el cruce de
claves, no en las tiendas.

Y el Excel de un mes, que escribe el archivo en `almacen\auditoria\` y le dice
la ruta:

```
php cli\auditoria.php --mes=2026-11 --excel
```

> Un mes tarda **entre veinte segundos y un minuto**, lo mismo que un día: lo
> que cambia no es el rango, es la carga del servidor. No está colgado:
> el archivo del detalle tiene 6,6 millones de líneas y ningún índice por fecha,
> así que el AS400 lo recorre entero. Está medido y explicado en
> `docs/INDICE-RTP325.md`.

### Paso 7 · Conectar con la intranet

En el `.env`, rellene el bloque de la intranet con lo que le dé quien la
administra:

```ini
INTRANET_VALIDAR=si
INTRANET_APP_ID=42
INTRANET_DB_HOST=192.168.1.10
INTRANET_DB_PORT=3306
INTRANET_DB_NAME=intranet
INTRANET_DB_USER=usuario_intranet
INTRANET_DB_PASS=clave_intranet
INTRANET_URL_PERFILES=http://intranet.rori.com/perfiles
```

Abra la aplicación desde la intranet y compruebe que entra con su usuario y que
no aparece el distintivo **PRUEBAS** en la cabecera.

> **`INTRANET_VALIDAR=si` sólo en el servidor de verdad.** Con `no` se trabaja
> como el usuario de pruebas y no se comprueba ningún permiso; eso es para el
> equipo de desarrollo, y la cabecera lo avisa con un distintivo que no se puede
> pasar por alto.
>
> Si `INTRANET_APP_ID` se queda vacío con la validación encendida, la aplicación
> se cierra a propósito: es preferible a dejar la puerta abierta.

### Paso 8 · Los manuales en PDF (opcional)

Sólo si va a cambiar la documentación. Hace falta **Node 18 o superior**,
únicamente en el equipo donde se generen:

```
cd docs\_herramientas
npm install
node generar-manuales.mjs --salida ..\..\vistas\manuales
```

Los PDF quedan en `vistas\manuales\` y los botones del pie los enlazan desde
`config\pie.php`. Si no va a tocar la documentación, los PDF ya están en el
repositorio y no hay nada que hacer.

---

## Casos especiales

### El equipo no tiene Apache sirviendo esa carpeta

Pasa en el equipo de referencia: `http://localhost/AppWeb/...` devuelve 404
aunque la carpeta esté ahí. Para mirar la pantalla mientras se aclara, el
servidor propio de PHP basta:

```
cd C:\xampp\htdocs\AppWeb\IndustriasRRC\reporte-auditoria-ventas
php -S 127.0.0.1:8899
```

y abrir `http://127.0.0.1:8899/`. Sirve para probarla, **no** para que la use la
gente: no aplica los `.htaccess`, así que las carpetas de código quedarían al
alcance de cualquiera que escriba la URL.

### Sólo quiere probar, sin AS400

```
php cli\probar-excel.php
```

No toca el servidor: fabrica los casos difíciles y comprueba que cada uno saca
el veredicto que tiene que sacar, y que el `.xlsx` sale válido. Es la forma de
comprobar la instalación con la VPN puesta.

### Quiere mirar el Excel y el equipo no tiene Excel

```
php cli\ver-excel.php almacen\auditoria\Auditoria-formas-de-pago_20261101_20261130.xlsx
```

Lo pinta en el navegador. No reproduce los formatos numéricos —una fecha sale
como su número de serie— ni el autofiltro, pero contesta las preguntas de
diseño.

---

## Cuando algo no sale

| Lo que ve | Qué suele ser |
|---|---|
| «No se pudo conectar con el servidor AS400» | la VPN está activa, o `AS400_DRIVER` no coincide con el instalado |
| «El servidor no tiene habilitada la conexión con el AS400» | falta `extension=odbc` en el `php.ini` |
| «La conexión con el AS400 no está configurada» | faltan `AS400_HOST`, `AS400_USER` o `AS400_PASS` en el `.env` |
| «Columna no encontrada» y el nombre lleva **ñ** | avise a desarrollo: es la conversión de códigos |
| «El AS400 no tiene ese archivo en esa biblioteca» | el mapa de `config\librerias.txt` |
| «0 de 120» en el paso 7 | las claves no cruzan: no siga, avise a desarrollo |
| El `.xlsx` no abre o Excel dice «contenido ilegible» | avise con el texto exacto del aviso |
| La pantalla da 404 | Apache no está sirviendo esa carpeta; vea los casos especiales |
| Aparece el distintivo **PRUEBAS** en el servidor de verdad | `INTRANET_VALIDAR` está en `no` |

Si un paso falla, pare ahí y mande **la salida completa** tal cual sale por
pantalla. No la resuma: lo que hay que mirar suele ser justo el detalle que
parece irrelevante.

---

# Segunda parte · el detalle, paso a paso

Lo mismo de arriba, explicado. Para quien necesite entender cada paso, hacerlo a
mano o arreglar algo que no salió.

## 1. PHP y sus extensiones

La aplicación usa `declare(strict_types=1)` y sintaxis de PHP 8 —enumeraciones
de `match`, propiedades promocionadas, `never`— así que **8.2 es un mínimo
real**, no una recomendación.

Hacen falta dos extensiones y nada más:

- **`odbc`**, que es por donde se habla con el AS400.
- **`zip`**, que es con lo que se escribe el `.xlsx`. Un `.xlsx` es un ZIP con
  unos XML dentro, y por eso no hace falta Excel en el servidor.

Para habilitarlas, en el `php.ini` (en XAMPP, `C:\xampp\php\php.ini`) quite el
punto y coma de estas dos líneas y reinicie Apache:

```ini
extension=odbc
extension=zip
```

Compruebe cuál es el `php.ini` que se está leyendo de verdad:

```
php --ini
```

> La consola y Apache pueden estar usando **php.ini distintos**. Si
> `php cli\probar-as400.php` funciona y la pantalla dice que no hay ODBC, es
> eso.

## 2. El driver ODBC

El driver lo instala el paquete de IBM i Access Client Solutions. No hay que
crear ningún DSN: la aplicación arma la cadena de conexión a mano con lo que
hay en el `.env`.

```
Driver={<AS400_DRIVER>};System=<AS400_HOST>;Uid=<AS400_USER>;Pwd=<AS400_PASS>;
```

Por eso lo único que tiene que coincidir **exactamente** es el nombre del
driver. Un espacio de más o un paréntesis distinto y la conexión falla con un
mensaje que no dice que el problema sea el nombre.

El usuario del AS400 sólo necesita **lectura** sobre los cinco archivos:
`RORILBRA.IDP210`, `RORIVENTAA.RTP325`, `RORIVENTAA.IDP116N`,
`RORIVENTAA.IDTA116` y `RORIVENTAA.ETP045`. Esta aplicación no escribe ni una
fila en el servidor.

## 3. Dónde se copia, y qué tiene que poder escribir

La raíz del proyecto es la raíz web: todo archivo es una URL a menos que algo lo
impida. Las carpetas de código traen su propio `.htaccess` que las deniega
enteras, así que **Apache tiene que leer los `.htaccess`**:

```apache
<Directory "C:/xampp/htdocs/AppWeb">
    AllowOverride All
    Require all granted
</Directory>
```

> Si `AllowOverride` está en `None`, los `.htaccess` se ignoran y quedan al
> alcance de cualquiera que escriba la URL: el `.env` con la clave del AS400,
> las corridas guardadas en `almacen\` con nombres de cliente y cédulas, y el
> código de `config\`. Compruébelo pidiendo
> `http://<servidor>/.../config/app.php`: tiene que devolver **403**.

Dos carpetas tienen que ser **escribibles** por el usuario de Apache:

| Carpeta | Para qué |
|---|---|
| `almacen\auditoria\` | los Excel que genera la consola |
| `almacen\auditoria\cache\` | las corridas guardadas, para que el Excel sea lo que se vio |

Las crea la aplicación sola si puede. Si no puede, la consulta no se cae: lo que
se pierde es la garantía de que el Excel sea exactamente la corrida que se miró,
y eso sale avisado en la pantalla.

## 4. El `.env`, línea por línea

```ini
AS400_HOST=192.1.1.2
```
El servidor. Lo da sistemas.

```ini
AS400_USER=
AS400_PASS=
```
Usuario y clave. **No tienen valor por omisión en el código**, y es a propósito:
antes lo tenían, y una contraseña escrita en el código es una contraseña
publicada. Además, con el valor por defecto puesto, un `.env` mal leído no se
notaba —la aplicación conectaba igual— y nadie se enteraba de que la
configuración no se estaba aplicando.

```ini
AS400_DRIVER=Client Access ODBC Driver (32-bit)
```
El nombre exacto de la lista de `odbcad32.exe`.

```ini
AS400_LIBRERIAS=produccion
```
Qué mapa de archivos se usa:

| Valor | Archivo | Qué apunta |
|---|---|---|
| `produccion` | `config\librerias.txt` | los archivos de verdad |
| `desarrollo` | `config\libreriasDevs.txt` | copias de `IDP210` y de `IDP116N` |

`php cli\probar-as400.php` dice en su primer paso cuál está en uso,
precisamente porque la diferencia no se nota mirando los números.

El bloque de la intranet ya está en el paso 7 de la primera parte. `env.php` lee
el `.env` de la raíz y sólo ése: la ruta es una constante explícita, para que no
haya forma de editar un `.env` y estar leyendo otro.

## 5. Qué hace cada comprobación, y qué mirar

### `php cli\probar-as400.php`

Siete pasos, parándose en el primer fallo real:

1. Que el `.env` está relleno, y **qué mapa de bibliotecas está usando**.
2. Que la extensión ODBC está habilitada.
3. Que la conexión se abre, y cuánto tarda.
4. Que los cinco archivos existen donde el mapa dice.
5. **Que cada archivo tiene los campos que la aplicación lee.** Si falta alguno,
   lista los campos reales que empiezan parecido, para poder elegir el bueno.
6. Que una consulta de verdad devuelve filas, con el tiempo de cada una.
7. **Que las claves cruzan entre los tres archivos.**

El paso 7 es el que de verdad importa. Un documento es `fecha + tienda + tipo +
número`, y el driver ODBC no entrega el número igual desde los tres archivos:
`26829`, `26829.` o `00026829` según el archivo y el controlador. Si no cruzan,
las facturas salen con «pagado 0,00» y «falta todo», **sin un solo error que lo
delate**. Es el fallo más caro de todos.

En la corrida del 19/11/2026 contra producción salió: 209 de 210 con detalle,
208 de 210 con pagos, **cero huérfanos**.

### `php cli\auditoria.php --mes=2026-11 --excel`

La auditoría entera: lee, cruza, juzga, lo cuenta por pantalla y escribe el
`.xlsx`. Qué mirar:

- **«cuadran al céntimo»** tiene que ser la inmensa mayoría.
- **El desglose de tiempos** que sale arriba: dice cuánto tardó cada archivo. El
  del detalle se lleva el 98 % de la espera, y eso es lo normal hoy.
- **Los avisos del final.** Si aparece «ATENCIÓN: ... DESCUENTO SENIAT distinto
  de cero», hay que revisar la fórmula del total antes de usar el informe: ese
  importe valía cero en todo lo que se midió.

Después, abra el `.xlsx` y compruebe:

1. Que abre **sin** el aviso de «Excel encontró contenido ilegible».
2. Que están las cinco pestañas: Resumen, A revisar, Auditoría, Formas de pago,
   Método.
3. Que las fechas de la columna «Fecha» **son fechas**: ordene por esa columna y
   mire si ordena bien.
4. Que el autofiltro funciona en «Auditoría» y que las dos primeras columnas
   quedan fijas al desplazar.
5. Que la pestaña «Formas de pago» **suma lo mismo** que el «Total en formas de
   pago» del Resumen. Si no coincidieran, una de las dos estaría contando mal.

### `php cli\probar-excel.php`

No toca el AS400. Fabrica los casos difíciles —el que cuadra al céntimo, el de
redondeo del IGTF, el que falta dinero, el ajuste que no se contrasta, el abono,
el anulado, la forma de pago que no está en el catálogo— y comprueba que cada
uno saca el veredicto que tiene que sacar. Existe porque con la VPN activa no
hay servidor al que preguntar, y un informe que sólo se puede comprobar «cuando
se pueda» es un informe que no se comprueba.

## 6. La pantalla, con el AS400 detrás

Abra la aplicación, elija un rango y pulse **Auditar**. Lo que hay que mirar la
primera vez:

- **Cuánto se tarda de verdad.** Mientras espera, el cargador va diciendo qué
  archivo está leyendo. Si se queda siempre atascado en el mismo, ésa es la
  pista — y lo normal es que sea el detalle.
- **Si se agota el tiempo.** El límite está en 180 segundos, fijado en
  `php\auditoria\consultar.php`. Si un mes no cabe, hay que subirlo o bajar el
  tope de días.
- **Que el Excel descargado sea el que se ve.** Audite un rango, mire el número
  de «documentos auditados» en pantalla, descargue y compruebe que el Resumen
  del archivo dice lo mismo. Para eso está la corrida guardada, que dura media
  hora.

## 7. Los manuales en PDF, con detalle

El Markdown de `docs\` es la fuente y los PDF se derivan de él. El generador
vive en su propia carpeta, con sus propias dependencias, y **no toca nada del
proyecto**:

```
docs\
  manuales.json            la identidad, los colores, el logotipo y qué manuales hay
  MANUAL-USUARIO.md        las fuentes
  MANUAL-TECNICO.md
  INSTALACION.md
  _herramientas\
    package.json           sólo para el generador
    generar-manuales.mjs
```

```
cd C:\xampp\htdocs\AppWeb\IndustriasRRC\reporte-auditoria-ventas\docs\_herramientas
npm install
node generar-manuales.mjs --salida ..\..\vistas\manuales
```

Cada manual tiene que decir `ok` y la orden terminar sin ninguna línea `aviso`.
Un aviso de caracteres significa que el `.md` lleva algo que la fuente del PDF
no sabe pintar: se añade a `SUSTITUCIONES`, dentro de `generar-manuales.mjs`, y
se vuelve a generar.

Para generar uno solo:

```
node generar-manuales.mjs --solo MANUAL-USUARIO --salida ..\..\vistas\manuales
```

> **Los PDF van a `vistas\manuales\` y no a `docs\`.** `docs\` tiene un
> `.htaccess` que deniega el acceso por web, así que un enlace a un PDF de ahí
> daría 403. Las rutas que usan los botones del pie están en `config\pie.php`,
> bajo `manuales`.

La versión que sale en la portada y en la cabecera de cada PDF está en
`docs\manuales.json`, y la que sale en el pie de la aplicación, en
`config\pie.php`. **Son dos sitios**: al subir la versión hay que tocar los dos
y regenerar los PDF.

## 8. Actualizar una instalación que ya funciona

1. Copie los archivos nuevos encima. **No toque el `.env`**: no se versiona y es
   el único que lleva las credenciales de ese equipo.
2. Si el `.env.example` trae claves nuevas, añádalas al `.env`.
3. `php cli\probar-excel.php` — comprueba el cálculo y el Excel sin servidor.
4. `php cli\probar-as400.php` — con la VPN desconectada.
5. Un período corto por pantalla, y descargar el Excel.

No hay migraciones, ni dependencias que actualizar, ni caché que vaciar: las
corridas guardadas caducan solas a la media hora.

---

## A quién llamar

| Para qué | A dónde |
|---|---|
| Soporte | soporte@rori.com · Ext. 2309 / +58 412-333-0319 |
| Horario | Lunes a viernes, de 7:30 a 16:00 |
| Desarrollo | Carlos Flores · cflores@rori.com |

El procedimiento de pruebas contra el servidor, con lo que hay que mirar en cada
salida, está en `docs\PRUEBAS-AS400.md`. La arquitectura y el porqué de cada
decisión, en `docs\PLAN.md` y en el manual técnico.
