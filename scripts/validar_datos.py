"""Validación de solo lectura del paquete que entregue Claude / pml-bot.

Uso: python scripts/validar_datos.py --data-dir /ruta/al/paquete
No genera ni modifica archivos de datos. Salida 1 si falta o falla el paquete.
"""
import argparse
from datetime import date
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import duckdb
from vista1 import DATA_DIR, MAX_DIARIO, MIN_DIARIO, inspeccionar_paquete


def validar(root):
    t0 = time.perf_counter()
    limites = inspeccionar_paquete(root)
    with duckdb.connect(":memory:") as con:
        nodos = str(root / "nodes.parquet")
        if con.execute("""SELECT COUNT(*) FROM (
                SELECT nodo FROM read_parquet(?) GROUP BY nodo
                HAVING nodo IS NULL OR trim(nodo) = '' OR COUNT(*) > 1)
                """, [nodos]).fetchone()[0]:
            raise ValueError("Catálogo con claves vacías o duplicadas")
        con.read_parquet(nodos).create_view("nodos")
        total = {"hourly": 0, "daily": 0}
        for tipo in total:
            for p in sorted((root / tipo).glob("*.parquet")):
                con.read_parquet(str(p)).create_view("particion", replace=True)
                if tipo == "hourly":
                    dia = date.fromisoformat(p.stem)
                    condicion = """fecha::DATE != ? OR fecha != date_trunc('day', fecha)
                        OR fecha IS NULL OR hora IS NULL OR hora NOT BETWEEN 1 AND 24
                        OR pml IS NULL OR NOT isfinite(pml)"""
                    parametros = [dia]
                    claves = "nodo, fecha, hora"
                    if not limites["horario_desde"] <= dia <= limites["horario_hasta"]:
                        raise ValueError("Partición fuera de la ventana horaria declarada")
                else:
                    condicion = f"""strftime(fecha, '%Y-%m') != ? OR fecha IS NULL
                        OR fecha != date_trunc('day', fecha)
                        OR horas_validas IS NULL OR horas_validas NOT BETWEEN 1 AND 24
                        OR horas_negativas IS NULL OR horas_negativas NOT BETWEEN 0 AND horas_validas
                        OR suma_pml IS NULL OR NOT isfinite(suma_pml)
                        OR suma_pml_cuadrado IS NULL OR NOT isfinite(suma_pml_cuadrado) OR suma_pml_cuadrado < 0
                        OR {MIN_DIARIO} IS NULL OR NOT isfinite({MIN_DIARIO})
                        OR {MAX_DIARIO} IS NULL OR NOT isfinite({MAX_DIARIO}) OR {MIN_DIARIO} > {MAX_DIARIO}
                        OR suma_pml / horas_validas < {MIN_DIARIO} - 0.000001
                        OR suma_pml / horas_validas > {MAX_DIARIO} + 0.000001
                        OR suma_pml_cuadrado - suma_pml*suma_pml/horas_validas < -0.000001 * greatest(1, suma_pml_cuadrado)
                    """
                    parametros = [p.stem]
                    claves = "nodo, fecha"
                malas = con.execute(f"""SELECT COUNT(*) FROM particion
                    WHERE nodo IS NULL OR trim(nodo) = '' OR ({condicion})""", parametros).fetchone()[0]
                duplicadas = con.execute(f"SELECT COUNT(*) FROM (SELECT {claves} FROM particion GROUP BY {claves} HAVING COUNT(*) > 1)").fetchone()[0]
                desconocidas = con.execute("SELECT COUNT(*) FROM particion ANTI JOIN nodos USING (nodo)").fetchone()[0]
                filas = con.execute("SELECT COUNT(*) FROM particion").fetchone()[0]
                if malas or duplicadas or desconocidas or not filas:
                    raise ValueError(f"Partición inválida: {tipo}/{p.name} (filas, claves o catálogo)")
                total[tipo] += filas
        # Comparar TODO el solapamiento sin sumar dos veces horario + diario.
        con.read_parquet([str(p) for p in sorted((root / 'hourly').glob('*.parquet'))]).create_view('horario')
        con.read_parquet([str(p) for p in sorted((root / 'daily').glob('*.parquet'))]).create_view('diario')
        dias = con.execute("SELECT COUNT(DISTINCT fecha::DATE) FROM diario").fetchone()[0]
        if dias != (limites['hasta'] - limites['desde']).days + 1:
            raise ValueError("El resumen diario contiene fechas completas ausentes")
        diferencias = con.execute(f"""
            WITH h AS (
                SELECT nodo, fecha::DATE AS fecha, COUNT(*) AS n, SUM(pml) AS s,
                    SUM(pml*pml) AS q, MIN(pml) AS lo, MAX(pml) AS hi,
                    COUNT(*) FILTER (WHERE pml < 0) AS neg
                FROM horario GROUP BY nodo, fecha::DATE
            ), d AS (
                SELECT * FROM diario WHERE fecha BETWEEN ? AND ?
            )
            SELECT COUNT(*) FROM h FULL OUTER JOIN d USING (nodo, fecha)
            WHERE h.n IS NULL OR d.horas_validas IS NULL OR h.n != d.horas_validas
               OR h.neg != d.horas_negativas OR h.lo != d.{MIN_DIARIO} OR h.hi != d.{MAX_DIARIO}
               OR abs(h.s - d.suma_pml) > 1e-8 * greatest(1, abs(h.s))
               OR abs(h.q - d.suma_pml_cuadrado) > 1e-8 * greatest(1, abs(h.q))
        """, [limites['horario_desde'], limites['horario_hasta']]).fetchone()[0]
        if diferencias:
            raise ValueError("El resumen diario no cuadra con el horario en el solapamiento")
    print(f"Paquete válido: {total}; {time.perf_counter()-t0:.2f} s")
    print(f"Cobertura declarada/verificada: {limites}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=DATA_DIR)
    args = parser.parse_args()
    try:
        validar(args.data_dir.resolve())
    except (ValueError, OSError, duckdb.Error) as exc:
        print(f"NO APTO para publicación: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
