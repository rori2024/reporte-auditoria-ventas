# Plan de migración — Asignación de Datos Complementarios de Tela (VARPG → PHP 8.2 MVC)

Programa de origen: **OPPA64** — *«Asignación datos complementarios tela / código
de corte y rapor»*, de Fernando Monasterio (14/Mar/2006), última compilación
18/Jun/2018, versión en pantalla «V. 04.04.18».

| Archivo del proyecto VARPG | Qué aporta |
|---|---|
| `H:\App Carlos\Programas Visual Age\telas\OPPA64\OPPA64\OPPA64.VPG` | Todo el código: 17 rutinas de evento y 3 subrutinas |
| `…\OPPA64.ODF` | Las 4 ventanas, sus controles y de qué campo del AS400 sale cada uno |
| `…\OPPA64.LST` | Listado de compilación: el **layout completo de los 6 archivos** con tipos y posiciones |
| `…\OPPA64.rst` | Biblioteca real de cada archivo (`RORIVENTAA`) y el servidor (`192.1.1.2`) |
| `…\OPPA64.txm` + `.ipm` | Los 10 mensajes de validación, con su texto y su ayuda |

`OPPA26Applet.java` y `RT_WIN32\` son restos del programa del que se copió este
(OPPA26) y del ejecutable compilado. No aportan nada a la migración.

---

## 1. Qué hace el programa

Sirve para **completar dos datos de la tela de un pedido de compra** que no se
capturan cuando se crea el pedido:

1. El **código de corte RAPOR**, compuesto de tres partes: `Diseño-Ancho-Largo`
   (`A-BBB-CCC`, p. ej. `3-519-018`).
2. El **porcentaje de prueba de encogimiento**, ancho y largo.

Y, de paso, el nombre de la **sastrería express** asignada a esa tela.

Se trabaja por **código de tela RORI**: se escribe uno, el programa lista todas
las líneas de pedido de esa tela que están en inventario, y se editan una a una.

### Las cuatro ventanas y el recorrido real

| Ventana | Título | Para qué |
|---|---|---|
| `OPPA6403` | *Ingrese el Codigo Tela RORI* | Pide el código de tela y lo valida contra `OMP013` |
| `OPPA6401` | *Seleccione un registro* | Lista (subfile `SFL2`) las líneas de tela del pedido |
| `OPPA6402` | *Adición/Modificación* | Formulario de edición de una línea |
| `OPPA6400` | *Detalle* | Lista de pedidos (subfile `SFL1`) — **camino muerto, ver §4.1** |

El recorrido vivo es **`OPPA6403` → `OPPA6401` → `OPPA6402`** y de vuelta. Lo
confirman los eventos: el «<< Regresar» de `OPPA6401` y su `CLOSE` reactivan
`OPPA6403`, no `OPPA6400`.

---

## 2. Los datos: archivos, campos y claves

Servidor `192.1.1.2`, biblioteca **`RORIVENTAA`** en los seis casos.

| Alias | Archivo | Uso en el programa | Modo |
|---|---|---|---|
| `OMP004` | `RORIVENTAA/OMP004` | Encabezado de pedido (sólo `OPPA6400`) | Lectura |
| `OMP012` | `RORIVENTAA/OMP012` | Detalle de tela del pedido — **es el que se actualiza** | Lectura y **escritura** |
| `OML0121` | `RORIVENTAA/OML0121` | Lógico sobre `OMP012` por código de tela; de aquí sale el listado | Lectura |
| `OMP013` | `RORIVENTAA/OMP013` | Inventario por tela; valida que el código exista | Lectura |
| `OTP038` | `RORIVENTAA/OTP038` | Tabla de códigos de corte | Lectura |
| `ETL0850` | `RORIVENTAA/ETL0850` | Lógico de tipos de tela; de aquí salen los nombres de sastrería | Lectura |

### Campos que intervienen

De `OMP012` / `OML0121` (formato `OMP012R`), los tipos salen del listado de
compilación; el tamaño de los empaquetados se deduce de los bytes que ocupan:

| Campo | Posición | Tipo | Significado |
|---|---|---|---|
| `OSTDTL` | 1-1 | `CHAR(1)` | Estado. **El listado filtra por `'8'`** (inventario) |
| `ONRODC` | 2-7 | `DEC(6,0)` zoned | Nº de orden de compra — **parte 1 de la clave** |
| `OCDTRO` | 8-17 | `CHAR(10)` | Código de tela RORI — **parte 2 de la clave** |
| `ONBTPR` | 18-47 | `CHAR(30)` | Código/nombre de tela del proveedor |
| `ODSACH` | 48-51 | `CHAR(4)` | Ancho de tela |
| `ODSDTL` | 52-81 | `CHAR(30)` | Descripción de la tela |
| `ODSTJD` | 187-206 | `CHAR(20)` | Descripción del tejido |
| `ONBSAS` | 207-236 | `CHAR(30)` | **Nombre de sastrería** (se escribe) |
| `OCDCTA` | 509-509 | `CHAR(1)` | **Código de corte A — «Diseño»** (se escribe) |
| `OCDCTB` | 510-511 | `DEC(3,0)` packed | **Código de corte B — «Ancho»** (se escribe) |
| `OCDCTC` | 512-513 | `DEC(3,0)` packed | **Código de corte C — «Largo»** (se escribe) |
| `OPRBEA` | 514-516 | `DEC(5,2)` packed | **% encogimiento ancho** (se escribe) |
| `OPRBEL` | 517-519 | `DEC(5,2)` packed | **% encogimiento largo** (se escribe) |

De `OTP038` (combo «Cd.corte»): `OSTCRT CHAR(1)` estado —se filtra `'1'`=activo—,
`OCDCRT CHAR(1)` código, `ONBCRT CHAR(20)` nombre.

De `ETL0850` (combo «Sastrería Express»): `ECDTTL DEC(3,0)` código,
`ENBTEL CHAR(30)` nombre, `ESTTEL CHAR(1)` estado —se filtra `'A'`=activo—.

De `OMP013` (validación del código de tela): `OSTINV CHAR(1)`, `OCDPRO CHAR(6)`,
`OCDTRO CHAR(10)`.

De `OMP004` (sólo la pantalla muerta): `OSTODC`, `ONRODC`, `OPRFAC`, `OTOTTL`,
`ODSUMD`, `ODIAPD`/`OMESPD`/`OANOPD`.

### Claves — **pendiente de confirmar**

El listado de compilación no imprime las claves. Del código RPG se deducen:

| Archivo | Clave deducida | De dónde se deduce |
|---|---|---|
| `OMP012` | `ONRODC` + `OCDTRO` | `KEY012 KLIST` con esos dos `KFLD` |
| `OML0121` | `OCDTRO` | `CHAIN WCDTRO` + `READE WCDTRO` |
| `OMP013` | `OCDTRO` | `CHAIN WCDTRO` |
| `OTP038` | `OCDCRT` | `CHAIN WCDCRT` |
| `ETL0850` | — | se recorre secuencialmente, sin clave |

Hay que comprobarlas con `QSYS2.SYSKEYS` antes de dar por bueno el `WHERE` del
`UPDATE` (§7.3). **No se pudo verificar ahora**: ver §10.

### El mapa de bibliotecas está incompleto

`config/librerias.txt` y `config/libreriasDevs.txt` sólo declaran `OMP012`.
Faltan **`OMP004`, `OML0121`, `OMP013`, `OTP038` y `ETL0850`**, y sin ellos
`ModeloAS400::archivo()` lanza excepción (por diseño: falla ruidosamente).

Y un detalle que importa más: en `libreriasDevs.txt` la línea es
`OMP012;RORIVENTAA.OMP012`, **la biblioteca de producción**. Para la hoja de
corte da igual porque sólo lee; aquí **se escribe**. Hay que apuntar el alias de
desarrollo a una copia de pruebas (`CFLORES.OMP012` o similar) antes de probar
el guardado, o las pruebas modificarán datos reales de producción.

---

## 3. Lógica que hay que replicar

### 3.1 El código de tela RORI se arma con dos campos

`OPPA6403` tiene dos entradas, y el código es la concatenación de ambas:

```
WCDTRO = '0000000000'              (10 caracteres)
WCDTRO = WMAQUI (1 car.)  +  WMAQUI1 (9 dígitos, rellenos con ceros)
```

Si `WMAQUI` está vacío, el primer carácter queda en blanco: `" 000012345"`.
Si trae una letra: `"A000012345"`. Después se valida con `CHAIN OMP013`; si no
existe → **MSG0009** «Codigo de tela no existe».

En web se puede mantener el prefijo separado (es lo que la gente ya conoce) y
armar el código de 10 posiciones en el servidor. El formato es
`1 carácter + 9 dígitos a la derecha con ceros`, y eso **no** se puede dejar al
navegador: un código mal rellenado no encuentra nada y parece «no hay datos».

Nota: **MSG0010** («Debe colocar el codigo de tela RORI») es inalcanzable en el
original, porque `WMAQUI1` es numérico y nunca queda en blanco. En web sí tiene
sentido: se usa cuando no se escribe nada.

### 3.2 El código de corte RAPOR

Se muestra como `A-BBB-CCC` y se compone de `OCDCTA` (1 carácter, de `OTP038`),
`OCDCTB` y `OCDCTC` (3 dígitos cada uno):

```
WSCRAPOR = OCDCTA + '-' + OCDCTB(3) + '-' + OCDCTC(3)
```

Cuando `OCDCTA` está en blanco, el listado muestra `0` en su lugar (`SFL2`
`CREATE`). Eso **no es un formato**, es un parche para un dato corrompido: ver
§4.2.

Las etiquetas de `OPPA6402` dicen qué es cada parte: `Diseño` / `Ancho` /
`Largo`, igual que la cabecera del listado («Codigo de Corte Rapor · Dis / Ach /
Lar»).

### 3.3 Las validaciones (`SRVAL1` y `SRVAL2`)

| Regla | Mensaje | Texto |
|---|---|---|
| Código de corte (combo) sin elegir | MSG0001 | «Codigo de corte incompleto» |
| `OCDCTA` en blanco | MSG0002 | «Codigo de corte incompleto.» |
| `A='1'` (Unicolor) y `B≠0` o `C≠0` | MSG0006 | «Si el codigo de corte es 1=Unicolor, el resto debe ser igual a 0» — ej. `1-000-000` |
| `A='2'` (Rayas) y (`B=0` o `C≠0`) | MSG0007 | «…los siguientes 3 digitos deben ser diferente de 0 y los ultimos digitos deben ser igual a 0» — ej. `2-012-000`, `2-815-000` |
| Cualquier otro `A` (3, 4…) y (`B=0` o `C=0`) | MSG0008 | «Si el codigo es 3 ó 4, los siguientes digitos deben ser diferente de 0» — ej. `3-519-018`, `4-217-631` |

Los mensajes MSG0003, MSG0004 y MSG0005 (porcentajes obligatorios y no
negativos) están **comentados** en el fuente, bajo el rótulo «Campos no
obligatorios». Los porcentajes, por tanto, son opcionales.

**Lo importante: en el programa que está en producción estas validaciones no se
ejecutan.** La línea que las llama está comentada:

```rpg
C* ojo desbloquear  EXSR      SRVAL1                                       VALIDACION
```

Como `*IN90` nunca se enciende, `SRACT1` graba siempre, sin comprobar nada. Esa
nota del propio autor —«ojo desbloquear»— es la que hay que atender al migrar.

### 3.4 Lo que se graba (`SRACT1`)

```rpg
KEY012 = ONRODC + OCDTRO
CHAIN OMP012 → UPDATE OMP012R con:
    OCDCTA = WCDCRT      (el código de corte elegido en el combo)
    OCDCTB = WCDCTB
    OCDCTC = WCDCTC
    OPRBEA = WPRBEA
    OPRBEL = WPRBEL
    ONBSAS = WNBTEL      (el nombre de sastrería elegido en el combo)
```

Seis campos de un solo registro, identificado por orden + código de tela. Nada
más. No hay bitácora, no hay marca de quién cambió qué ni cuándo.

---

## 4. Defectos del original, y qué hacemos con ellos

Esto es la parte que más conviene leer antes de escribir código, porque **copiar
el comportamiento al pie de la letra sería copiar tres fallos de datos**.

### 4.1 `OPPA6400` no lleva a ninguna parte

La ventana lista pedidos de `OMP004` con estado `'7'` u `'8'`, y al pulsar Enter
sobre una fila hace `SHOWWIN 'OPPA6401'` **sin asignar `WCDTRO`**. El listado de
`OPPA6401` se arma con `CHAIN OML0121` por ese campo, así que entrando por ahí
sale vacío o con la tela de la consulta anterior.

→ **Decidido: no se migra.** Es resto del programa del que se copió este
(`OPPA26`). Si de verdad hace falta buscar por pedido en vez de por tela, es una
función nueva y se diseña como tal.

### 4.2 Guardar sin tocar el combo borra el dígito de diseño

`RC01` (el combo «Cd.corte») tiene tres eventos:

- `CREATE` lee el valor actual y lo guarda en **`WCDCTA`**.
- `SELECT` guarda lo elegido en **`WCDCRT`**.
- `SRACT1` graba `OCDCTA = `**`WCDCRT`**.

`WCDCRT` sólo se rellena al desplegar y elegir. Si se abre una línea, se cambia
sólo el porcentaje y se pulsa Aceptar, **se graba `OCDCTA` en blanco** y se
pierde el dígito de diseño. Con `SRVAL1` desactivado (§3.3) nada lo impide.

Eso explica el parche del listado: `OCDCTA IFEQ *BLANKS → MOVE '0' WA`. El
programa ya convive con registros a los que les falta ese dígito.

→ **Decidido: se corrige.** El diseño es obligatorio, viaja con su valor actual
preseleccionado y se valida contra la lista real de `OTP038`.

### 4.3 La edición puede grabar sobre la línea equivocada

En el evento `ENTER` de `SFL2`, `READS SFL2` recupera la fila marcada, pero
**`ONRODC` no es un campo del subfile** (`SFL2` sólo lleva `OCDTRO`, `ONBTPR`,
`ODSDTL`, `ODSTJD`, `ODSACH`, `WSCRAPOR`, `OPRBEA`, `OPRBEL`, `ONBSAS`).

Así que `ONRODC` conserva el valor de la **última** lectura del `READE` que llenó
la lista. Y `KEY012` se arma con él. Si una tela aparece en varios pedidos,
editar la primera línea graba en la última.

Lo mismo ocurre con `WA`/`WB`/`WC`: son subcampos de la estructura `WCRAPOR`, y
`READS SFL2` carga `WSCRAPOR`, que es otro campo. Al abrir `OPPA6402` se muestra
el código de corte del último registro de la lista, no el de la fila elegida.

→ **Decidido: se corrige.** Cada fila del listado viaja con su clave completa
(`ONRODC` + `OCDTRO`) y con sus propios valores. En web esto sale gratis: es la
forma natural de hacerlo.

### 4.4 El listado escribe filas que no ha procesado

En `SFL2 CREATE`, el `WRITE SFL2` está **fuera** del `IF OSTDTL = '8'`:

```rpg
C     OSTDTL        IFEQ      '8'
C                   … calcula WSCRAPOR …
C                   END
C                   WRITE     SFL2          ← se escriben todas las filas
```

Las líneas con otro estado se listan igual, pero con el código de corte de la
fila anterior. Tampoco hay `CLEAR SFL2` al principio, así que al volver a entrar
las filas se acumulan.

→ **Decidido: filtrar en el `WHERE` (`OSTDTL = '8'`) y calcular el código por
fila.** Queda por confirmar si el filtro debe ser `'8'` o si hay que mostrar
otros estados: §10.

### 4.5 El `% de encogimiento` admite más de lo que la pantalla deja ver

`OPRBEA` y `OPRBEL` son `DEC(5,2)` en el archivo (hasta `999.99`), el subfile
los pinta con 4 dígitos y 2 decimales (`99.99`) y la entrada de `OPPA6402` con
3 (`9.99`). Son tres límites distintos para el mismo dato.

→ **Propuesta: validar `0.00`–`99.99`** (el ancho del listado), pendiente de
confirmar con quien usa el programa: §10.

---

## 5. Arquitectura destino

Se sigue la base que ya está en el proyecto y el patrón de `hoja-corte-digital`,
que es de donde viene esta plantilla: tres capas, endpoints JSON en `php/`, una
sola plantilla y la pantalla armada en el navegador.

```
index.php                         ← ya está: abre sesión de intranet y carga la plantilla
errorAcceso.php                   ← ya está, y ya pinta (§8.2)
.htaccess                         ← ya está (fase 0)

config/
  as400.php      env.php      texto.php      bitacora.php     ← ya están
  .htaccess                       ← ya está (fase 0; faltaba, ver §8.1)
  librerias.php                   ← ya está
  intranet.php                    ← ya está (fase 0; faltaba, ver §8.1)
  respuesta.php                   ← ya está (fase 0)
  texto.php → utf8_a_as400()      ← ya está (fase 0, §7.4)
  app.php                         ← ya está (§8.2): identidad de la app y qué carga la plantilla
  pie.php                         ← ya está (§8.2): datos del pie corporativo
  csrf.php                        ← CREAR en fase 3 (el original no escribía; esto sí)
  librerias.txt / libreriasDevs.txt  ← ya están, con los 5 alias (§9.1)

modelos/
  as400.modelo.php                ← ya está; AÑADIR helper de escritura (§7.3)
  intranet.modelo.php             ← ya está
  tela.modelo.php                 ← CREAR: listado + validación de código + UPDATE
  combos.modelo.php               ← CREAR: cortes (OTP038) y sastrerías (ETL0850)

controladores/
  plantilla.controlador.php       ← ya está
  tela.controlador.php            ← CREAR: abre/cierra AS400, orquesta, no imprime

php/
  combos.php                      ← CREAR (GET)  listas de los dos desplegables
  consultar.php                   ← CREAR (POST) líneas de una tela
  guardar.php                     ← CREAR (POST) actualiza una línea

servicios/
  SesionIntranet.php              ← ya está
  DatosTela.php                   ← CREAR: validación de dominio (§3.3) sin SQL ni HTML

vistas/
  .htaccess                       ← ya está (§8.2): niega los .php, deja pasar css/js/img
  plantilla.php                   ← ya está (§8.2): genérica, se gobierna con config/app.php
  iconos.php                      ← ya está (§8.2)
  modulos/pie.php                 ← ya está (§8.2)
  modulos/busqueda.php            ← CREAR (OPPA6403)
  modulos/listado.php             ← CREAR (OPPA6401)
  modulos/editor.php              ← CREAR (OPPA6402, en diálogo modal)
  modulos/acerca.php              ← COPIAR y adaptar en fase 5 (+ config/acerca.php)
  css/  js/                       ← CREAR en fase 2 sobre la base de hoja-corte-digital
  img/                            ← ya está la base; el icono propio en fase 5

docs/                             ← este plan, y después los manuales
```

### Reparto de responsabilidades

| Capa | Hace | No hace |
|---|---|---|
| `php/*.php` | Sesión de intranet, método HTTP, CSRF, leer la entrada, serializar | Lógica, SQL |
| `tela.controlador.php` | `CONECTARAS400()`/`DESCONECTARAS400()` en `finally`, orquestar, traducir excepciones | SQL, `echo`, `header()` |
| `DatosTela.php` | Las reglas de §3.1 y §3.3 | SQL, entrada cruda |
| `*.modelo.php` | SQL preparado, una operación por método | Validar, reglas de negocio |

---

## 6. Las pantallas

Una sola página con tres zonas, como la hoja de corte. No hay enrutador porque
no hay a dónde enrutar.

### 6.1 Búsqueda (de `OPPA6403`)

Un campo de prefijo (1 carácter) y uno de 9 dígitos, más el botón *Consultar*.
Debajo, cuando hay resultado, el código completo y la descripción de la tela,
para que se vea que se consultó lo que se quería.

### 6.2 Listado (de `OPPA6401`)

Tabla `<table>` con `<thead>`/`<tbody>` y las columnas del subfile original:

| Columna | Campo |
|---|---|
| Código Tela RORI | `OCDTRO` |
| Código Tela Proveedor | `ONBTPR` |
| Descripción Tela | `ODSDTL` |
| Descripción Tejido | `ODSTJD` |
| Ancho | `ODSACH` |
| Código de Corte Rapor (Dis/Ach/Lar) | `A-BBB-CCC` |
| % Encogimiento Ancho | `OPRBEA` |
| % Encogimiento Largo | `OPRBEL` |
| Sastrería Express | `ONBSAS` |
| — | botón *Editar* |

Y una columna más que el original no tenía pero que hace falta para saber qué se
está editando: **Nº de orden** (`ONRODC`). Es la mitad de la clave; esconderla es
lo que permitió el fallo de §4.3.

### 6.3 Editor (de `OPPA6402`)

Diálogo modal con los seis campos editables:

| Control | Campo | Tipo |
|---|---|---|
| Diseño | `OCDCTA` | `<select>` con los activos de `OTP038`, etiqueta `código — nombre` |
| Ds. corte | `ONBCRT` | sólo lectura, se actualiza al cambiar el diseño |
| Ancho | `OCDCTB` | número entero 0-999 |
| Largo | `OCDCTC` | número entero 0-999 |
| Encogimiento Ancho | `OPRBEA` | decimal 0,00-99,99 |
| Encogimiento Largo | `OPRBEL` | decimal 0,00-99,99 |
| Sastrería Express | `ONBSAS` | `<select>` con los activos de `ETL0850` |

Botones *Aceptar* y *Cancelar*. Las reglas de §3.3 se avisan en el cliente
mientras se escribe —con el ejemplo del mensaje original (`1-000-000`,
`2-012-000`, `3-519-018`)— y **se vuelven a comprobar en el servidor**, que es
donde cuentan.

El diseño visual sale de `.claude/agents/DESIGN-SYSTEM.md` y las reglas de
`FrontEnd.md`: tokens, un solo `<h1>`, `<label for>` en cada campo, foco visible,
y el desplazamiento en el contenedor del módulo, no en el `body`.

---

## 7. Contratos y SQL

### 7.1 `php/combos.php` (GET)

```json
{ "ok": true,
  "cortes":     [ { "codigo": "1", "nombre": "UNICOLOR",  "etiqueta": "1 — UNICOLOR" } ],
  "sastrerias": [ { "codigo": "12", "nombre": "…", "etiqueta": "…" } ] }
```

```sql
SELECT OCDCRT, ONBCRT FROM {OTP038}  WHERE OSTCRT = '1' ORDER BY OCDCRT
SELECT ECDTTL, ENBTEL FROM {ETL0850} WHERE ESTTEL = 'A' ORDER BY ENBTEL
```

### 7.2 `php/consultar.php` (POST)

Entrada: `prefijo` (0-1 carácter) y `numero` (hasta 9 dígitos).

```json
{ "ok": true,
  "tela": { "codigo": " 000012345", "descripcion": "…" },
  "lineas": [ { "nroOrden": 123456, "codigoTela": " 000012345",
                "telaProveedor": "…", "descripcion": "…", "tejido": "…",
                "ancho": "…", "disenio": "3", "corteAncho": 519, "corteLargo": 18,
                "rapor": "3-519-018", "encogimientoAncho": 1.50,
                "encogimientoLargo": 0.75, "sastreria": "…" } ] }
```

```sql
-- existencia del código de tela (MSG0009)
SELECT OCDTRO FROM {OMP013} WHERE OCDTRO = ? FETCH FIRST 1 ROW ONLY

-- el listado
SELECT ONRODC, OCDTRO, ONBTPR, ODSDTL, ODSTJD, ODSACH,
       OCDCTA, OCDCTB, OCDCTC, OPRBEA, OPRBEL, ONBSAS
  FROM {OML0121}
 WHERE OCDTRO = ? AND OSTDTL = '8'
 ORDER BY ONRODC
```

Sin filas → `ok:false` con «No hay líneas de tela en inventario para ese
código», que es una respuesta normal, no un error: **HTTP 200**, como en la hoja
de corte.

### 7.3 `php/guardar.php` (POST)

Entrada: la clave (`nroOrden`, `codigoTela`), los seis valores nuevos, los seis
valores originales y el token CSRF.

```sql
UPDATE {OMP012}
   SET OCDCTA = ?, OCDCTB = ?, OCDCTC = ?, OPRBEA = ?, OPRBEL = ?, ONBSAS = ?
 WHERE ONRODC = ? AND OCDTRO = ?
   AND OCDCTA = ? AND OCDCTB = ? AND OCDCTC = ? AND OPRBEA = ? AND OPRBEL = ? AND ONBSAS = ?
```

**Por qué los valores viejos van en el `WHERE`.** El RPG abría el archivo en
actualización y mantenía el registro bloqueado entre el `CHAIN` y el `UPDATE`
(de ahí los `UNLOCK` del fuente). Una página web no puede sostener ese bloqueo:
entre consultar y guardar pasan minutos y la petición es otra. Con los valores
originales en el `WHERE`, si alguien cambió la línea mientras tanto el `UPDATE`
afecta **0 filas** y se puede avisar —«el registro cambió, vuelva a
consultar»— en vez de machacar su trabajo en silencio.

Hace falta, por tanto, un helper de escritura en `ModeloAS400` que devuelva el
número de filas afectadas (`odbc_num_rows` tras `odbc_execute`). Hoy la clase
sólo sabe leer. Si en el AS400 `odbc_num_rows` no resultara fiable para
`UPDATE`, la alternativa es releer la fila y comparar antes de grabar.

### 7.4 El AS400 habla Latin-1, también al escribir

`config/texto.php` resuelve la mitad del problema: `as400_a_utf8()` convierte lo
que **llega**. Falta la inversa, porque `ONBSAS` es texto y **se graba**: un
nombre de sastrería con tilde escrito en UTF-8 entra al archivo con dos bytes
raros donde iba un carácter.

→ Añadir `utf8_a_as400()` a `config/texto.php` y aplicarla al parámetro antes de
`odbc_execute`. Es lo que hace `cambio_precio/modelos/Precios.modelo.php` con su
`aLatin1()`; aquí queda en la frontera, no repartida por los modelos.

Mejor aún: el nombre de sastrería **no se acepta tal cual del navegador**. Llega
el código, se busca en `ETL0850` y se graba el `ENBTEL` que devuelve el AS400.
Así el texto que se escribe salió del propio AS400 y el problema se reduce.

### 7.5 Seguridad del endpoint que escribe

La hoja de corte sólo consulta, así que su patrón de endpoint no cubre esto:

1. **`SesionIntranet::continuar()`** al principio, como en los demás endpoints:
   proteger la página y dejar el JSON abierto no protege nada.
2. **Sólo POST**, con `header('Allow: POST')` y 405.
3. **CSRF**. La cookie de sesión ya es `HttpOnly` + `SameSite=Lax`
   (`SesionIntranet::iniciarSesionPhp`), lo que frena el caso básico, pero una
   acción que escribe en un maestro de producción lleva token. Va en
   `config/csrf.php`, se emite en la plantilla y se valida aquí.
4. **Un solo nivel de acceso**: quien tiene la aplicación concedida en la
   intranet puede consultar y guardar. `SesionIntranet::continuar()` del punto 1
   ya lo comprueba, así que no hace falta nada más —pero **sí hace falta que
   esté en los tres endpoints**, y en particular en éste: un `guardar.php` sin
   esa línea deja escribir en `OMP012` a cualquiera que alcance la URL, tenga la
   aplicación concedida o no.
5. **Bitácora**. `bitacora_evento()` ya está en el proyecto. Se registra cada
   guardado con usuario, orden, código de tela y el antes/después de los seis
   campos. El programa original no deja rastro de nada; esto se cambia a
   propósito, porque se está tocando un maestro.

---

## 8. Fases

| # | Fase | Entregable | Se puede dar por buena cuando |
|---|---|---|---|
| 0 | Base | **Hecha** (§8.1) | — |
| 1 | Lectura | `combos.modelo.php`, `tela.modelo.php` (sin `UPDATE`), controlador, `php/combos.php`, `php/consultar.php` | El JSON de una tela conocida coincide con lo que muestra el `.EXE` |
| 2 | Pantalla | Los tres módulos (`busqueda`, `listado`, `editor`), CSS, JS y loader. El armazón —plantilla, pie e iconos— ya está (§8.2) | Consultar y listar funciona de punta a punta, con teclado y en móvil |
| 3 | Escritura | `DatosTela.php`, `php/guardar.php`, helper de escritura, CSRF, bitácora | Las 5 reglas de §3.3 rechazan lo que deben y un cambio aparece en `OMP012` |
| 4 | Verificación | — | Comparado contra el `.EXE` con los mismos códigos de tela, campo por campo |
| 5 | Cierre | README, icono, «Acerca de», manuales PDF | Con los agentes `GenerateReadme`, `GenerateIcon`, `ManualPDF` |

### 8.1 Fase 0 — hecha (29/10/2026)

| Pieza | Qué es |
|---|---|
| `config/respuesta.php` | `responder_json()`, copiado de `hoja-corte-digital`. Independiente del dominio |
| `config/intranet.php` | Conexión con la base de la intranet. **Faltaba**, y la exigían `servicios/SesionIntranet.php:29` y `modelos/intranet.modelo.php`: sin él, `index.php` y `errorAcceso.php` daban error fatal |
| `config/.htaccess` | **Faltaba.** `modelos/`, `controladores/` y `servicios/` traían el suyo, pero `config/` no: `config/librerias.txt` se descargaba por web con un 200, y con él el mapa entero de bibliotecas del AS400 |
| `.htaccess` (raíz) | Deniega `.env`, `.git*` y los respaldos de editor (`*.bak`, `*.orig`, `*.sql`, `*.log`, `*~`), apaga `Indexes` y deja `display_errors` en el registro y fuera de la respuesta |
| `config/texto.php` | Añadida `utf8_a_as400()`, la inversa que faltaba para poder grabar texto (§7.4) |
| Mapa de bibliotecas | Los 5 alias, y corregida la errata del separador de `ETL0850` (§9.1) |

Comprobado:

- **Las rutas de código devuelven 403** por web: `.env`, `.gitignore`,
  `config/*`, `modelos/*`, `controladores/*`, `servicios/*`, `docs/*`.
- **Ningún `require` del proyecto apunta a un archivo que no exista**, salvo los
  dos de la capa de vista —`vistas/plantilla.php` y `vistas/modulos/pie.php`—,
  que se pusieron justo después (§8.2).
- **`utf8_a_as400()` y `as400_a_utf8()` son ida y vuelta exacta** para
  «Sastrería Niño», «Tejido 100% Algodón» y un guión largo; la doble llamada no
  rompe nada y `null` sigue siendo `null`.
- **El mapa de bibliotecas resuelve los 5 alias** en los dos entornos, 44 en
  total cada uno y ninguna línea descartada.

Lo que **no** se pudo comprobar: nada que toque el AS400. Sigue sin red (§10.1).

Las fases 1 y 3 son las que hay que probar contra datos reales. La 2 se puede
adelantar con datos de ejemplo.

### 8.2 El armazón de la vista, genérico (30/10/2026)

`vistas/plantilla.php` y `vistas/modulos/pie.php` se trajeron de
`hoja-corte-digital`. El pie ya era genérico —todo sale de `config/pie.php`—,
pero la plantilla no: nombraba a la hoja de corte en cuatro sitios y traía sus
módulos, sus hojas de estilo y sus scripts escritos a mano. Como esta carpeta
va a ser la plantilla de los próximos programas, **todo eso se sacó a
`config/app.php`**.

| Pieza | Qué es |
|---|---|
| `config/app.php` | Nombre, subtítulo, descripción, color de tema, y las listas de `css`, `js`, `modulos` y `capas`. Es lo único que hay que tocar al copiar el proyecto |
| `config/pie.php` | Datos del pie (DESIGN-SYSTEM.md §10). Versión `0.1.0 ( en desarrollo )` y `manuales` vacío, que es lo que hace que esa columna no se pinte todavía |
| `vistas/plantilla.php` | Reescrita: no nombra a ninguna aplicación. El logotipo y el nombre de la empresa los toma de `config/pie.php`; el resto, de `config/app.php` |
| `vistas/iconos.php` | Copiado. El catálogo de Lucide, con el comentario de las secciones ya neutro |
| `vistas/modulos/pie.php` | El botón «Acerca de» sólo se pinta si `acerca` está en `capas`: un botón que no abre nada es peor que no tener botón |
| `errorAcceso.php` | Ya no lleva el nombre escrito a mano. Lee los mismos dos archivos de configuración, que es lo que evita que una de las dos páginas se quede con el nombre del proyecto del que se copió |
| `vistas/.htaccess` | Niega los `.php` de `vistas/` y deja pasar `css/`, `js/`, `img/` y `manuales/`. Pedir `vistas/modulos/pie.php` por URL devolvía el pie suelto, con los datos de contacto |
| `controladores/plantilla.controlador.php`, `modelos/as400.modelo.php` | Sólo comentarios: hablaban de la hoja de corte y del VB6 del que venía aquélla |

Un módulo que todavía no existe **no tumba la página**: la plantilla deja un
aviso visible en su sitio y una línea en el registro. Una copia recién hecha se
abre y se ve el armazón mientras se escriben los módulos, y el aviso se ve, que
es lo que hace que no se olvide.

Comprobado: `index.php` y `errorAcceso.php` devuelven **200** y pintan el nombre
nuevo en la pestaña, en la cabecera y en el pie; los tres avisos de módulo que
falta salen en su sitio; `vistas/*.php` y `vistas/modulos/*.php` dan **403** y
`vistas/img/icono.svg` sigue dando 200; y en el registro de Apache no hay ni un
aviso de PHP. Las hojas de estilo todavía dan 404 —son de la fase 2—, así que la
página se ve sin estilo.

Queda para la fase 5, cuando haya icono propio: `vistas/img/icono.svg` sigue
siendo las tijeras de la hoja de corte, con su `aria-label`.

---

## 9. Decisiones tomadas

| Tema | Decisión | Motivo |
|---|---|---|
| Comportamiento general | Replicar OPPA64, **menos** los cuatro fallos de §4, que **se corrigen** | Copiarlos sería migrar la corrupción de datos |
| Validaciones `SRVAL1`/`SRVAL2` | **Se activan**, con los mensajes y ejemplos del original | Están escritas, documentadas en el `.txm` y el autor dejó nota de desbloquearlas |
| Porcentajes | Opcionales (como en el original), rango `0,00`–`99,99` | MSG0003/4/5 están comentados bajo «Campos no obligatorios» |
| `OPPA6400` (lista de pedidos) | **No se migra** | Camino muerto: §4.1 |
| Concurrencia | Control optimista con los valores originales en el `WHERE` | No hay forma de sostener el bloqueo del RPG en web |
| Bitácora | Se registra cada guardado | El original no deja rastro y aquí se escribe en un maestro |
| Acceso | Intranet (`INTRANET_APP_ID=39`), **un solo nivel**: quien tiene la aplicación concedida consulta y guarda | Es lo que hace el `.EXE` de hoy; no hay dos perfiles que distinguir |
| Mapa de bibliotecas | **Hecho**: los cuatro alias están en los dos archivos y en desarrollo lo que se escribe apunta a `DESARROLLO`. Ver §9.1 | En desarrollo no se puede escribir en producción |

### 9.1 El mapa de bibliotecas (hecho, 29/10/2026)

Los alias que faltaban ya están en `config/librerias.txt` y
`config/libreriasDevs.txt`, y el parser los resuelve en los dos entornos (44
alias cada uno, ninguna línea descartada):

| Alias | Producción | Desarrollo | Para qué |
|---|---|---|---|
| `OMP012` | `RORIVENTAA.OMP012` | `DESARROLLO.OMP012` | **el que se escribe** |
| `OML0121` | `RORIVENTAA.OML0121` | `DESARROLLO.OML0121` | el listado de telas |
| `OMP013` | `RORIVENTAA.OMP013` | `DESARROLLO.OMP013` | valida que el código de tela exista |
| `OTP038` | `RORIVENTAA.OTP038` | `RORIVENTAA.OTP038` | combo de códigos de corte (sólo lectura) |
| `ETL0850` | `RORIVENTAA.ETL0850` | `RORIVENTAA.ETL0850` | combo de sastrerías (sólo lectura) |

`OMP004` no se declara, porque la pantalla que lo usaba no se migra (§4.1).

Dos cosas que conviene no perder de vista:

1. La línea de `ETL0850` llegó con un **punto** donde va el punto y coma
   (`ETL0850.RORIVENTAA.ETL0850`). `config/librerias.php` parte por `;`, así que
   la descartaba en silencio —con su aviso en el registro, que nadie mira— y
   `archivo('ETL0850')` habría fallado al abrir el combo de sastrerías. Ya está
   corregido en los dos archivos.
2. **`OML0121` es un lógico sobre `OMP012`.** Para que desarrollo sea coherente,
   `DESARROLLO.OML0121` tiene que estar construido sobre `DESARROLLO.OMP012`. Si
   lo está sobre el de producción, el listado leería producción mientras el
   `UPDATE` escribe en desarrollo: los cambios no aparecerían nunca en pantalla
   y se perseguiría un fantasma. Hay que comprobarlo con `DSPDBR`/`DSPFD` en
   cuanto haya acceso al AS400 (§10.4).

---

## 10. Pendientes de confirmar

**Con sistemas / red:**

1. **El AS400 no responde desde este equipo.** `192.1.1.2:8471` está cerrado y
   el driver devuelve `comm rc=10013`. Nada de lo que toca datos se ha podido
   verificar. Es lo primero.
2. Las **claves** de los seis archivos (`QSYS2.SYSKEYS`), sobre todo que
   `ONRODC` + `OCDTRO` identifique una sola fila de `OMP012`.
3. Que los marcadores `?` funcionen con el driver de iSeries en el `UPDATE`, y
   que `odbc_num_rows` devuelva filas afectadas.
4. Que **`DESARROLLO.OML0121` sea el lógico de `DESARROLLO.OMP012`** y no el de
   producción (`DSPDBR`), y que `DESARROLLO.OMP012` y `DESARROLLO.OMP013`
   existan y tengan datos con los que probar. Es la condición para que la fase 3
   se pueda probar sin tocar producción. Ver §9.1.

**Con quien usa el programa:**

5. ¿El listado debe seguir mostrando **sólo** las líneas con `OSTDTL = '8'`
   (inventario)? ¿Qué significan los demás estados?
6. ¿Cuál es el **rango real** del % de encogimiento? El archivo admite hasta
   `999,99`, la pantalla vieja mostraba `99,99` y dejaba escribir `9,99`.
7. Hay registros con el **dígito de diseño en blanco** por §4.2. ¿Se dejan como
   están, se listan para revisarlos, o se corrigen?

Nada más queda sin decidir: lo del acceso se resolvió con un solo nivel (§9).
