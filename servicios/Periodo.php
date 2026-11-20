<?php

declare(strict_types=1);

/**
 * El rango de fechas que se audita, validado y troceado por meses.
 *
 * ===========================================================================
 *  POR QUÉ ESTO EXISTE Y NO ES UN `BETWEEN`
 * ---------------------------------------------------------------------------
 *  En el AS400 **no hay campo fecha** en ninguno de los tres archivos del
 *  documento. Hay cuatro campos numéricos separados: siglo, año de dos cifras,
 *  mes y día (`NFCEDC`, `NFAÑDC`, `NFMSDC`, `NFDIDC` en el encabezado y en los
 *  pagos; `RF…` en el detalle). No se puede escribir
 *
 *      WHERE fecha BETWEEN '2026-11-01' AND '2026-12-05'
 *
 *  porque esa columna no existe. Y la forma obvia de arreglarlo —componer un
 *  número con los cuatro campos y comparar el número— convierte el filtro en
 *  una expresión sobre cada fila y le quita al servidor cualquier posibilidad
 *  de usar un índice. Sobre tres años de facturas eso es la diferencia entre
 *  una consulta y una espera.
 *
 *  Así que el rango se parte en meses y cada mes aporta su propia condición
 *  con los campos tal cual:
 *
 *      (NFCEDC=20 AND NFAÑDC=26 AND NFMSDC=11 AND NFDIDC BETWEEN 1 AND 30)
 *   OR (NFCEDC=20 AND NFAÑDC=26 AND NFMSDC=12 AND NFDIDC BETWEEN 1 AND  5)
 *
 *  Comparaciones de igualdad sobre los campos reales, que es lo que el
 *  servidor sabe resolver rápido.
 * ===========================================================================
 */
final class Periodo
{
    /**
     * Tope de días que se admite de una vez.
     *
     * No es una limitación de diseño, es una medida de cortesía con el AS400:
     * un mes son del orden de 3.800 encabezados, 12.000 líneas de detalle y
     * 5.200 líneas de pago, y esta pantalla las trae TODAS y en vivo, mientras
     * alguien espera delante. Tres meses es lo que cabe en una espera
     * razonable; un año hay que pedirlo mes a mes, y eso además hace que un
     * fallo no se lleve por delante lo que ya había salido bien.
     */
    public const MAXIMO_DIAS = 93;

    public readonly string $desde;
    public readonly string $hasta;

    private function __construct(string $desde, string $hasta)
    {
        $this->desde = $desde;
        $this->hasta = $hasta;
    }

    /**
     * Construye el período, o explica por qué no se puede.
     *
     * @throws InvalidArgumentException con un mensaje que se puede mostrar tal
     *         cual en la pantalla. Quien llama no tiene que redactar nada.
     */
    public static function de(string $desde, string $hasta): self
    {
        foreach (['desde' => $desde, 'hasta' => $hasta] as $cual => $valor) {
            if (preg_match('/^\d{4}-\d{2}-\d{2}$/', $valor) !== 1) {
                throw new InvalidArgumentException(
                    'La fecha «' . $cual . '» no viene en formato AAAA-MM-DD.'
                );
            }

            [$a, $m, $d] = array_map('intval', explode('-', $valor));

            if (!checkdate($m, $d, $a)) {
                throw new InvalidArgumentException(
                    'La fecha «' . $valor . '» no existe en el calendario.'
                );
            }

            /*
             * El AS400 guarda el siglo en dos cifras (`NFCEDC` = 20). Un año
             * fuera de 1900-2099 no se puede ni representar en el filtro, así
             * que se corta aquí con el motivo real y no con un «no hay datos».
             */
            if ($a < 1900 || $a > 2099) {
                throw new InvalidArgumentException(
                    'El año ' . $a . ' queda fuera de lo que el AS400 puede filtrar '
                    . '(el siglo se guarda en dos cifras).'
                );
            }
        }

        if ($desde > $hasta) {
            throw new InvalidArgumentException(
                'El «desde» (' . self::corta($desde) . ') es posterior al «hasta» ('
                . self::corta($hasta) . ').'
            );
        }

        $dias = (int) ((strtotime($hasta) - strtotime($desde)) / 86400) + 1;

        if ($dias > self::MAXIMO_DIAS) {
            throw new InvalidArgumentException(sprintf(
                'El rango pedido son %d días y el tope es %d. Esta auditoría lee el '
                . 'AS400 en vivo —encabezados, detalle y formas de pago— mientras usted '
                . 'espera, así que se pide por tramos. Pruebe mes a mes.',
                $dias, self::MAXIMO_DIAS
            ));
        }

        return new self($desde, $hasta);
    }

    /** El mes natural completo de un `AAAA-MM`. */
    public static function delMes(string $mes): self
    {
        if (preg_match('/^\d{4}-\d{2}$/', $mes) !== 1) {
            throw new InvalidArgumentException('El mes «' . $mes . '» no es AAAA-MM.');
        }

        $primero = $mes . '-01';

        return self::de($primero, date('Y-m-t', (int) strtotime($primero)));
    }

    /**
     * El rango partido en tramos de un mes, cada uno con sus cuatro cifras.
     *
     * @return list<array{siglo:int,anio:int,mes:int,dia_desde:int,dia_hasta:int}>
     */
    public function tramos(): array
    {
        $tramos = [];

        $anioIni = (int) substr($this->desde, 0, 4);
        $mesIni  = (int) substr($this->desde, 5, 2);

        $anioFin = (int) substr($this->hasta, 0, 4);
        $mesFin  = (int) substr($this->hasta, 5, 2);

        $anio = $anioIni;
        $mes  = $mesIni;

        while ($anio * 100 + $mes <= $anioFin * 100 + $mesFin) {
            $ultimo = (int) date('t', (int) mktime(0, 0, 0, $mes, 1, $anio));

            $esPrimero = ($anio === $anioIni && $mes === $mesIni);
            $esUltimo  = ($anio === $anioFin && $mes === $mesFin);

            $tramos[] = [
                'siglo' => intdiv($anio, 100),
                'anio'  => $anio % 100,
                'mes'   => $mes,
                // El primer mes empieza en el día pedido; los siguientes, en 1.
                'dia_desde' => $esPrimero ? (int) substr($this->desde, 8, 2) : 1,
                // El último mes acaba en el día pedido; los anteriores, al final.
                'dia_hasta' => $esUltimo ? (int) substr($this->hasta, 8, 2) : $ultimo,
            ];

            $mes++;

            if ($mes > 12) {
                $mes = 1;
                $anio++;
            }
        }

        return $tramos;
    }

    /** Cuántos días naturales cubre el rango, el futuro incluido. */
    public function dias(): int
    {
        return (int) ((strtotime($this->hasta) - strtotime($this->desde)) / 86400) + 1;
    }

    /** `1 al 17 de noviembre de 2026`, para el rótulo del informe. */
    public function rotulo(): string
    {
        $meses = ['', 'enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio',
            'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre'];

        $d  = (int) substr($this->desde, 8, 2);
        $h  = (int) substr($this->hasta, 8, 2);
        $md = (int) substr($this->desde, 5, 2);
        $mh = (int) substr($this->hasta, 5, 2);
        $ad = (int) substr($this->desde, 0, 4);
        $ah = (int) substr($this->hasta, 0, 4);

        if ($ad === $ah && $md === $mh) {
            return ($d === $h)
                ? sprintf('%d de %s de %d', $d, $meses[$md], $ad)
                : sprintf('%d al %d de %s de %d', $d, $h, $meses[$md], $ad);
        }

        if ($ad === $ah) {
            return sprintf('%d de %s al %d de %s de %d', $d, $meses[$md], $h, $meses[$mh], $ad);
        }

        return sprintf('%d de %s de %d al %d de %s de %d',
            $d, $meses[$md], $ad, $h, $meses[$mh], $ah);
    }

    /** `dd/mm/aaaa`, que es como se escriben las fechas en los informes. */
    public static function corta(string $iso): string
    {
        $t = strtotime($iso);

        return $t === false ? $iso : date('d/m/Y', $t);
    }
}
