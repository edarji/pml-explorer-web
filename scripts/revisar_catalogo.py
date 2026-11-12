"""Revisión semanal del Catálogo de NodosP de CENACE (v0.6.1): detecta, valida y PROPONE; nunca publica.

Pensado para correr en el Mac mini con launchd (lunes 08:15), desde un clon de solo lectura de este
repo. No usa credenciales, no escribe en GitHub y no toca referencia/, data/ ni la app.

Uso:
    python scripts/revisar_catalogo.py                       # revisión real (lee la página de CENACE)
    python scripts/revisar_catalogo.py --simular RUTA.xlsx   # sin internet: usa un Excel local
    python scripts/revisar_catalogo.py --forzar              # descarga aunque la versión no haya cambiado

Detección en tres niveles:
    1. Versión en el nombre del archivo más reciente de la página contra la última revisada/aprobada.
    2. SHA-256 del Excel descargado (CENACE puede reemplazar un archivo sin cambiar la versión).
    3. Huella del contenido ya limpio (archivo distinto con los mismos datos = nada que proponer).

Resultados: sin_cambios, archivo_distinto_mismo_contenido, propuesta (lista para revisión),
bloqueado (hay un motivo de bloqueo) o error (red, formato de la página, otra ejecución en curso).

Carpeta de trabajo (por defecto ~/catalogo-nodosp, fuera de los repos):
    estado.json                 última revisión y su resultado
    originales/                 cada Excel descargado, con su versión; nunca se sobrescribe
    informes/                   un informe.md por revisión con contenido nuevo
    pendiente/                  la propuesta: nodos_catalogo.parquet, .json e informe.md
    PENDIENTE_DE_REVISION.txt   aviso para Lalo cuando hay propuesta
    logs/catalogo.log           una línea por ejecución

Código de salida: 0 sin bloqueo, 2 bloqueado, 1 error.
"""
import argparse
import fcntl
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import quote, urljoin, urlsplit, urlunsplit

import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "scripts"))
import catalogo as cat  # noqa: E402
import catalogo_diferencias as dif  # noqa: E402
import preparar_catalogo as prep  # noqa: E402

PAGINA = prep.PAGINA
BASE = Path.home() / "catalogo-nodosp"
ESPERAS = (60, 300, 900)  # reintentos tras 1, 5 y 15 minutos
ENLACE = re.compile(r"""[^"'<>]*CatalogoNodosP/\d{4}/[^"'<>]*?\(v(\d{4}-\d{2}-\d{2})\)\.xlsx""")


class ErrorRevision(Exception):
    """Falla que impide revisar (red, página sin enlaces, candado). No es un bloqueo de contenido."""


# --------------------------------------------------------------------------- red

def descargar(url, destino, esperas=ESPERAS, dormir=time.sleep):
    """Descarga con curl (el mismo que se probó en el Mac mini) y reintentos. Devuelve la ruta."""
    destino = Path(destino)
    tmp = destino.with_name(destino.name + ".parcial")
    ultimo = ""
    for intento, espera in enumerate((0, *esperas)):
        if espera:
            dormir(espera)
        r = subprocess.run(["curl", "-sS", "-f", "-L", "--max-time", "120", "-o", str(tmp), url],
                           capture_output=True, text=True)
        if r.returncode == 0 and tmp.is_file() and tmp.stat().st_size > 0:
            os.replace(tmp, destino)
            return destino
        ultimo = (r.stderr or f"código {r.returncode}").strip()
    tmp.unlink(missing_ok=True)
    raise ErrorRevision(f"No se pudo descargar {url} tras {1 + len(esperas)} intentos: {ultimo}")


def enlaces(html, pagina=PAGINA):
    """[(versión, url)] de los Excel del catálogo en la página, del más reciente al más viejo."""
    vistos = {}
    for m in ENLACE.finditer(html):
        url = urljoin(pagina, m.group(0).strip())
        partes = urlsplit(url)
        url = urlunsplit(partes._replace(path=quote(partes.path, safe="/%")))
        vistos.setdefault(m.group(1), url)
    return sorted(vistos.items(), reverse=True)


# ------------------------------------------------------------------- utilidades

def sha256(ruta):
    return hashlib.sha256(Path(ruta).read_bytes()).hexdigest()


def escribir_json(ruta, datos):
    tmp = Path(ruta).with_suffix(".tmp")
    tmp.write_text(json.dumps(datos, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, ruta)


def leer_estado(base):
    ruta = base / "estado.json"
    return json.loads(ruta.read_text(encoding="utf-8")) if ruta.is_file() else {}


def guardar_original(base, origen, version):
    """Copia el Excel a originales/ sin sobrescribir nunca uno anterior con otro contenido."""
    carpeta = base / "originales"
    carpeta.mkdir(parents=True, exist_ok=True)
    huella = sha256(origen)
    destino = carpeta / f"catalogo_v{version}.xlsx"
    if destino.is_file() and sha256(destino) != huella:
        destino = carpeta / f"catalogo_v{version}__{huella[:8]}.xlsx"
    if not destino.is_file():
        shutil.copy2(origen, destino)
    return destino, huella


def explicadas_por_control(ruta_excel, despues_de, hasta):
    """Claves que «Control de Cambios» menciona en versiones > despues_de y <= hasta (AAAA-MM-DD)."""
    try:
        hoja = pd.read_excel(ruta_excel, sheet_name="Control de Cambios", header=None)
    except Exception:  # sin la hoja no hay explicación; los cambios quedan como advertencia
        return set()
    textos = []
    for fila in hoja.itertuples(index=False):
        fechas = [v for v in fila if isinstance(v, (datetime, pd.Timestamp))]
        if fechas and despues_de < fechas[0].strftime("%Y-%m-%d") <= hasta:
            textos += [v for v in fila if isinstance(v, str)]
    return dif.claves_mencionadas(textos)


def publicar_pendiente(base, df, manifiesto, texto):
    """Escribe la propuesta en una carpeta temporal y la cambia por pendiente/ al final (atómico)."""
    tmp, vieja, final = base / ".pendiente_tmp", base / ".pendiente_vieja", base / "pendiente"
    for d in (tmp, vieja):
        shutil.rmtree(d, ignore_errors=True)
    prep.escribir(df, manifiesto, tmp)  # incluye la relectura con catalogo.cargar()
    (tmp / "informe.md").write_text(texto, encoding="utf-8")
    if final.exists():
        os.replace(final, vieja)
    os.replace(tmp, final)
    shutil.rmtree(vieja, ignore_errors=True)


# ---------------------------------------------------------------------- revisión

def revisar(base=BASE, repo=RAIZ, simular=None, forzar=False, obtener_pagina=None, bajar=None,
            ahora=None):
    """Una revisión completa. Devuelve el dict que se guarda en estado.json."""
    base, repo = Path(base), Path(repo)
    ahora = ahora or datetime.now()
    revision = ahora.strftime("%Y-%m-%d %H:%M")
    for d in ("originales", "informes", "logs"):
        (base / d).mkdir(parents=True, exist_ok=True)
    estado = leer_estado(base)

    aprobado, m_aprobado = cat.cargar(repo / "referencia")
    v_aprobada = m_aprobado["version_catalogo"]
    ruta_nodos = repo / "data" / "nodes.parquet"
    con_precio = (pd.read_parquet(ruta_nodos, columns=["nodo"])["nodo"].tolist()
                  if ruta_nodos.is_file() else aprobado["nodo"].tolist())

    res = {"revision": revision, "simulacion": bool(simular), "version_aprobada": v_aprobada}

    # Nivel 1: versión en el nombre.
    if simular:
        excel, url = Path(simular), "(simulación con archivo local)"
        if not excel.is_file():
            raise ErrorRevision(f"No existe el archivo {excel}")
        try:
            hoja = pd.ExcelFile(excel).sheet_names[0]
        except Exception as e:
            raise cat.CatalogoInvalido(f"El archivo no es un Excel legible: {e}") from e
        version = prep.version_de(hoja, excel)
    else:
        html = (obtener_pagina or _pagina)()
        lista = enlaces(html)
        if not lista:
            raise ErrorRevision("La página de CENACE no trae enlaces al catálogo (¿cambió el formato?). "
                                "Descarga manual y usa --simular.")
        version, url = lista[0]
        revisada = max(v_aprobada, estado.get("version_revisada", ""))
        if version <= revisada and not forzar:
            return res | {"resultado": "sin_cambios", "version_nueva": version, "url": url,
                          "detalle": f"La versión más reciente ({version}) ya se revisó."}
        excel = (bajar or descargar)(url, base / "originales" / ".descarga.xlsx")

    original, sha_excel = guardar_original(base, excel, version)
    if not simular:
        Path(excel).unlink(missing_ok=True)
    res |= {"version_nueva": version, "url": url, "archivo": original.name, "sha256_excel": sha_excel}

    # Nivel 2: SHA-256 del archivo.
    if sha_excel in (m_aprobado.get("sha256_origen"), estado.get("sha256_excel")):
        return res | {"resultado": "sin_cambios", "version_revisada": version,
                      "detalle": "Mismo archivo que el ya aprobado o revisado."}

    # Validación completa (formato, claves, regiones, tensión).
    try:
        nuevo, manifiesto, _, _ = prep.construir(original)
    except cat.CatalogoInvalido as e:
        evaluacion = {"bloqueos": [f"Formato o contrato: {e}"], "advertencias": [], "informacion": []}
        vacio = {"altas": [], "bajas": [], "cambios": pd.DataFrame(columns=["nodo", "campo", "antes", "despues"])}
        _informe(base, res | {"resultado": "bloqueado"}, vacio, evaluacion)
        return res | {"resultado": "bloqueado", "version_revisada": version, "motivos": evaluacion["bloqueos"]}

    # Nivel 3: huella del contenido.
    huella = dif.huella_contenido(nuevo)
    res |= {"huella_contenido": huella, "filas": len(nuevo)}
    if huella == dif.huella_contenido(aprobado):
        return res | {"resultado": "archivo_distinto_mismo_contenido", "version_revisada": version,
                      "detalle": "El Excel cambió pero los datos son los mismos: nada que proponer."}

    diferencias = dif.comparar(aprobado, nuevo)
    explicadas = explicadas_por_control(original, v_aprobada, version)
    evaluacion = dif.evaluar(aprobado, nuevo, diferencias, con_precio, explicadas)
    resultado = "bloqueado" if evaluacion["bloqueos"] else "propuesta"
    res |= {"resultado": resultado, "version_revisada": version,
            "altas": len(diferencias["altas"]), "bajas": len(diferencias["bajas"]),
            "cambios": len(diferencias["cambios"]), "motivos": evaluacion["bloqueos"],
            "advertencias": len(evaluacion["advertencias"])}
    texto = _informe(base, res, diferencias, evaluacion)
    if resultado == "propuesta":
        publicar_pendiente(base, nuevo, manifiesto, texto)
        aviso = ("SIMULACIÓN: " if simular else "") + (
            f"Catálogo v{version} listo para revisión ({revision}).\n"
            f"Lee {base / 'pendiente' / 'informe.md'} antes de aprobar. Nada se ha publicado.\n")
        (base / "PENDIENTE_DE_REVISION.txt").write_text(aviso, encoding="utf-8")
    return res


def _informe(base, res, diferencias, evaluacion):
    texto = dif.informe(res, diferencias, evaluacion)
    if res.get("simulacion"):
        texto = "> SIMULACIÓN con archivo local: no es una publicación de CENACE.\n\n" + texto
    nombre = f"{res['revision'][:10]}_v{res.get('version_nueva', 'x')}{'_simulacion' if res.get('simulacion') else ''}.md"
    (base / "informes" / nombre).write_text(texto, encoding="utf-8")
    return texto


def _pagina():
    r = subprocess.run(["curl", "-sS", "-f", "-L", "--max-time", "60", PAGINA],
                       capture_output=True, text=True)
    if r.returncode != 0:
        raise ErrorRevision(f"No se pudo leer la página de CENACE: {r.stderr.strip()}")
    return r.stdout


PERSISTENTES = ("version_revisada", "sha256_excel", "huella_contenido", "ultimo_hallazgo")


def combinar_estado(anterior, res):
    """estado.json = esta revisión + lo que hay que recordar de las anteriores.

    Se conservan la versión y el archivo ya revisados (para no proponer lo mismo cada lunes) y el
    último hallazgo (propuesta o bloqueo), para que un «sin_cambios» posterior no lo oculte.
    """
    nuevo = dict(res)
    for clave in PERSISTENTES:
        if clave not in nuevo and clave in anterior:
            nuevo[clave] = anterior[clave]
    if res.get("resultado") in ("propuesta", "bloqueado"):
        nuevo["ultimo_hallazgo"] = {"resultado": res["resultado"], "version": res.get("version_nueva"),
                                    "revision": res.get("revision"), "motivos": res.get("motivos", [])}
    return nuevo


def registrar(base, res):
    linea = (f"{res.get('revision', datetime.now().strftime('%Y-%m-%d %H:%M'))} "
             f"{res.get('resultado')} v{res.get('version_nueva', '?')} "
             f"{'(simulación) ' if res.get('simulacion') else ''}{res.get('detalle', '')}"
             f"{' ' + '; '.join(res.get('motivos', [])) if res.get('motivos') else ''}").rstrip()
    with open(base / "logs" / "catalogo.log", "a", encoding="utf-8") as f:
        f.write(linea + "\n")
    return linea


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--base", type=Path, default=BASE, help="Carpeta de trabajo (por defecto ~/catalogo-nodosp)")
    p.add_argument("--repo", type=Path, default=RAIZ, help="Clon del repo con referencia/ y data/")
    p.add_argument("--simular", type=Path, help="Usa este Excel local en vez de CENACE")
    p.add_argument("--forzar", action="store_true", help="Descarga aunque la versión ya se haya revisado")
    args = p.parse_args(argv)

    args.base.mkdir(parents=True, exist_ok=True)
    (args.base / "logs").mkdir(exist_ok=True)
    candado = open(args.base / ".candado", "w")
    try:
        fcntl.flock(candado, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        print("Otra revisión está en curso; termino sin hacer nada.")
        return 1
    try:
        res = revisar(args.base, args.repo, args.simular, args.forzar)
        codigo = 2 if res["resultado"] == "bloqueado" else 0
    except (ErrorRevision, cat.CatalogoInvalido) as e:
        res = {"resultado": "error", "detalle": str(e), "simulacion": bool(args.simular)}
        codigo = 1
    if not args.simular:  # una simulación no cambia lo que la revisión real ya vio
        escribir_json(args.base / "estado.json", combinar_estado(leer_estado(args.base), res))
    print(registrar(args.base, res))
    return codigo


if __name__ == "__main__":
    sys.exit(main())
