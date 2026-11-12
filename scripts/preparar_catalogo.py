"""Convierte el Catálogo de NodosP de CENACE (.xlsx) en el catálogo de referencia de la app.

Uso (en la MacBook o el Mac mini, con el venv activo y openpyxl instalado):
    python scripts/preparar_catalogo.py RUTA/AL/catalogo.xlsx            # valida y muestra diferencias
    python scripts/preparar_catalogo.py RUTA/AL/catalogo.xlsx --escribir # además escribe referencia/

Qué hace, en orden:
1. Lee la hoja del catálogo (encabezado en la 2.ª fila) y comprueba que estén las columnas esperadas.
2. Se queda con el sistema SIN (el paquete público solo tiene el SIN) y con 7 columnas.
3. Limpia sin inventar: recorta espacios, junta espacios dobles y convierte «No Aplica» en vacío.
4. Valida claves (vacías, duplicadas, con espacios), tensión contra el sufijo de la clave, etc.
5. Compara con los nodos del paquete de precios (data/nodes.parquet) en ambos sentidos.
6. Compara con el catálogo publicado antes (altas, bajas, cambios de nombre, región o zona).
7. Solo con --escribir: guarda referencia/nodos_catalogo.parquet y su manifiesto .json.

No descarga nada de internet, no toca data/ y no corrige claves. Sale con código 1 si algo falla.
"""
import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
import catalogo as cat  # noqa: E402

PAGINA = "https://www.cenace.gob.mx/Paginas/SIM/NodosP.aspx"
# Nombre oficial de la columna (fila 2 del Excel) -> nombre en nuestro catálogo.
ORIGEN = {
    "SISTEMA": "sistema",
    "CENTRO DE CONTROL REGIONAL": "region_control",
    "ZONA DE CARGA": "zona_carga",
    "CLAVE": "nodo",
    "NOMBRE": "nombre",
    "NIVEL DE TENSIÓN (kV)": "tension_kv",
    "CLAVE DE ENTIDAD FEDERATIVA (INEGI)": "estado_inegi",
    "ENTIDAD FEDERATIVA (INEGI)": "estado",
}
NO_APLICA = "No Aplica"


def version_de(nombre_hoja, archivo):
    """Versión del catálogo: sale del nombre de la hoja («... V20261023») y se coteja con el archivo."""
    m = re.search(r"V(\d{4})(\d{2})(\d{2})\s*$", nombre_hoja)
    if not m:
        raise SystemExit(f"No encuentro la versión en el nombre de la hoja: «{nombre_hoja}».")
    version = "-".join(m.groups())
    en_archivo = re.search(r"v(\d{4}-\d{2}-\d{2})", archivo.name)
    if en_archivo and en_archivo.group(1) != version:
        raise SystemExit(f"La hoja dice {version} y el archivo dice {en_archivo.group(1)}.")
    return version


def leer_excel(ruta):
    hojas = pd.ExcelFile(ruta)
    hoja = hojas.sheet_names[0]
    crudo = pd.read_excel(ruta, sheet_name=hoja, header=1, dtype=str)
    faltan = [c for c in ORIGEN if c not in crudo.columns]
    if faltan:
        raise SystemExit(f"El Excel no trae las columnas esperadas {faltan}. ¿Cambió el formato de CENACE?")
    return crudo[list(ORIGEN)].rename(columns=ORIGEN), version_de(hoja, ruta), len(crudo)


def limpiar(df):
    """Reglas de limpieza documentadas; ninguna cambia una clave."""
    df = df.copy()
    for c in df.columns:
        df[c] = df[c].str.strip()
    df["nombre"] = df["nombre"].str.replace(r"\s+", " ", regex=True)
    for c in ("region_control", "zona_carga", "estado_inegi", "estado"):
        df[c] = df[c].mask(df[c] == NO_APLICA)
    df["estado_inegi"] = df["estado_inegi"].str.zfill(2)  # clave INEGI de 2 dígitos: 5 -> 05
    df["tension_kv"] = pd.to_numeric(df["tension_kv"], errors="raise").astype("float64")
    return df


def revisar_tension(df):
    """La tensión del catálogo debe coincidir con el sufijo de la clave cuando lo hay (01AAN-85 -> 85)."""
    sufijo = pd.to_numeric(df["nodo"].str.extract(r"-(\d+(?:\.\d+)?)$")[0], errors="coerce")
    malas = df[sufijo.notna() & (sufijo != df["tension_kv"])]
    if len(malas):
        raise SystemExit(f"Tensión distinta del sufijo de la clave en {malas['nodo'].tolist()[:5]}.")


def comparar_con_paquete(df, ruta_nodos):
    if not ruta_nodos.is_file():
        print(f"(No encuentro {ruta_nodos}; omito la comparación con el paquete de precios.)")
        return
    paquete = set(pd.read_parquet(ruta_nodos, columns=["nodo"])["nodo"])
    catalogo = set(df["nodo"])
    union = cat.unir(sorted(paquete), df)
    print(f"Nodos del paquete de precios: {len(paquete):,}")
    print(f"  con fila en el catálogo:     {len(paquete & catalogo):,}")
    print(f"  SIN fila en el catálogo:     {len(paquete - catalogo):,} {sorted(paquete - catalogo)[:10]}")
    print(f"  con región y zona:           {int(union['clasificado'].sum()):,}")
    print(f"Claves del catálogo SIN sin precios en el paquete: {len(catalogo - paquete):,} "
          f"{sorted(catalogo - paquete)[:10]}")


def comparar_con_anterior(df, directorio):
    ruta = Path(directorio) / cat.ARCHIVO
    if not ruta.is_file():
        print("No hay catálogo publicado antes: todo es alta.")
        return
    viejo = pd.read_parquet(ruta).set_index("nodo")
    nuevo = df.set_index("nodo")
    altas, bajas = sorted(set(nuevo.index) - set(viejo.index)), sorted(set(viejo.index) - set(nuevo.index))
    print(f"Contra el catálogo publicado ({len(viejo):,} nodos): {len(altas)} altas {altas[:10]}, "
          f"{len(bajas)} bajas {bajas[:10]}")
    comunes = sorted(set(nuevo.index) & set(viejo.index))
    for campo in ("nombre", "region_control", "zona_carga", "estado"):
        a, b = viejo.loc[comunes, campo], nuevo.loc[comunes, campo]
        cambios = [n for n in comunes if not (pd.isna(a[n]) and pd.isna(b[n])) and a[n] != b[n]]
        for n in cambios[:10]:
            print(f"  cambio de {campo} en {n}: «{a[n]}» -> «{b[n]}»")
        if len(cambios) > 10:
            print(f"  ... y {len(cambios) - 10} cambios más de {campo}")


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("excel", type=Path, help="Archivo .xlsx descargado de CENACE")
    p.add_argument("--nodos", type=Path, default=RAIZ / "data" / "nodes.parquet")
    p.add_argument("--salida", type=Path, default=cat.REFERENCIA_DIR)
    p.add_argument("--escribir", action="store_true", help="Escribe referencia/ si todo pasa")
    args = p.parse_args(argv)

    crudo, version, filas_excel = leer_excel(args.excel)
    print(f"Catálogo CENACE v{version}: {filas_excel:,} filas en el Excel "
          f"({', '.join(f'{k} {v:,}' for k, v in crudo['sistema'].value_counts().items())})")
    df = limpiar(crudo[crudo["sistema"].str.strip() == "SIN"]).drop(columns="sistema")
    df = df.sort_values("nodo").reset_index(drop=True)[list(cat.COLUMNAS)]
    revisar_tension(df)
    manifiesto = {
        "fuente": "CENACE · Catálogo de NodosP",
        "pagina": PAGINA,
        "archivo_origen": args.excel.name,
        "version_catalogo": version,
        "sha256_origen": hashlib.sha256(args.excel.read_bytes()).hexdigest(),
        "sistema": "SIN",
        "filas": len(df),
        "sin_region": sorted(df.loc[df["region_control"].isna(), "nodo"]),
        "reglas": ["Solo sistema SIN", "Espacios recortados y espacios dobles del nombre unidos",
                   "«No Aplica» convertido en vacío", "Clave INEGI con 2 dígitos",
                   "Claves sin cambios; nombres sin corregir"],
        "aviso": "La versión del catálogo no es la vigencia de cada NodoP (CENACE). La clasificación "
                 "corresponde a esta versión y no se aplica hacia atrás.",
    }
    try:
        cat.validar(df, manifiesto)
    except cat.CatalogoInvalido as e:
        raise SystemExit(f"Catálogo inválido: {e}")
    print(f"SIN: {len(df):,} nodos, {df['region_control'].nunique()} regiones, "
          f"{df['zona_carga'].nunique()} zonas, {df['estado'].nunique()} estados; "
          f"{len(manifiesto['sin_region'])} sin región: {manifiesto['sin_region']}")
    comparar_con_paquete(df, args.nodos)
    comparar_con_anterior(df, args.salida)

    if not args.escribir:
        print("Solo revisión: no se escribió nada. Repite con --escribir para guardar referencia/.")
        return
    args.salida.mkdir(exist_ok=True)
    ruta = args.salida / cat.ARCHIVO
    df.to_parquet(ruta, compression="zstd", index=False)
    manifiesto["sha256_parquet"] = hashlib.sha256(ruta.read_bytes()).hexdigest()
    manifiesto["generado_utc"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    (args.salida / cat.MANIFIESTO).write_text(json.dumps(manifiesto, ensure_ascii=False, indent=2) + "\n",
                                              encoding="utf-8")
    cat.cargar(args.salida)  # relectura: lo escrito debe pasar la misma validación que usará la app
    print(f"Escrito {ruta} ({ruta.stat().st_size:,} bytes) y {cat.MANIFIESTO}.")


if __name__ == "__main__":
    main()
