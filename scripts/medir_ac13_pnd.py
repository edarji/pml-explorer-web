"""AC-13 local: tiempos y RSS máximo con el paquete PND real (pnd/ del repo). Un escenario por proceso.

Uso, desde la raíz del repo con el venv activo:
     python scripts/medir_ac13_pnd.py .                (orquesta los 10 escenarios)
     python scripts/medir_ac13_pnd.py . <escenario>    (un escenario; imprime JSON)

Medición local de procesos concretos: no es una medición de Community Cloud.
"""
import json
import os
import resource
import subprocess
import sys
import time

RAIZ = os.path.abspath(sys.argv[1])
ZONA = "MONTERREY"
APP_ESC = {
    "app_pml_inicio": {},
    "app_pnd_mensual_todo": dict(modalidad="pnd", zona=ZONA, desde="2023-01-01", hasta="2026-11-19", resolucion="mensual"),
    "app_pnd_diaria_todo": dict(modalidad="pnd", zona=ZONA, desde="2023-01-01", hasta="2026-11-19", resolucion="diaria"),
    "app_pnd_horaria_366": dict(modalidad="pnd", zona=ZONA, desde="2025-11-19", hasta="2026-11-19", resolucion="horaria"),
    "app_pnd_dia_sin_dato": dict(modalidad="pnd", zona=ZONA, desde="2026-05-08", hasta="2026-05-08", resolucion="diaria"),
}
FUN_ESC = ["fn_inspeccionar", "fn_serie_mensual_todo", "fn_serie_diaria_todo", "fn_serie_horaria_366",
           "fn_estadisticas_todo"]


def rss_mib():
    r = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return round(r / 2**20 if sys.platform == "darwin" else r / 2**10, 1)  # macOS: bytes; Linux: KiB


def correr(nombre):
    os.chdir(RAIZ)
    sys.path.insert(0, RAIZ)
    t0 = time.perf_counter()
    if nombre in APP_ESC:
        from streamlit.testing.v1 import AppTest
        app = AppTest.from_file(os.path.join(RAIZ, "app.py"), default_timeout=300)
        for k, v in APP_ESC[nombre].items():
            app.query_params[k] = v
        app.run()
        t1 = time.perf_counter()
        app.run()  # segunda corrida: con caché
        t2 = time.perf_counter()
        r = {"primera_s": round(t1 - t0, 2), "segunda_s": round(t2 - t1, 2), "excepcion": bool(app.exception),
             "metricas": len(app.metric), "avisos": [w.value[:90] for w in app.warning][:2]}
    else:
        import pnd
        if nombre == "fn_inspeccionar":
            i = pnd.inspeccionar_pnd()
            r = {"desde": str(i["desde"]), "hasta": str(i["hasta"]), "zonas": i["zonas"],
                 "dias_sin_dato": [str(d) for d in i["dias_sin_dato"]]}
        elif nombre == "fn_estadisticas_todo":
            r = {"horas": int(pnd.estadisticas_pnd(ZONA, "2023-01-01", "2026-11-19").iloc[0]["horas_con_dato"])}
        else:
            res = {"mensual": "mensual", "diaria": "diaria", "horaria": "horaria"}[nombre.split("_")[2]]
            ini = "2025-11-19" if res == "horaria" else "2023-01-01"
            r = {"filas": len(pnd.serie_pnd(ZONA, ini, "2026-11-19", res))}
        r["s"] = round(time.perf_counter() - t0, 3)
    r["rss_max_mib"] = rss_mib()
    print(json.dumps(r, ensure_ascii=False))


if __name__ == "__main__":
    if len(sys.argv) > 2:
        correr(sys.argv[2])
    else:
        for nombre in list(APP_ESC) + FUN_ESC:
            salida = subprocess.run([sys.executable, __file__, RAIZ, nombre], capture_output=True, text=True)
            linea = (salida.stdout.strip().splitlines() or [salida.stderr.strip()[-300:]])[-1]
            print(f"{nombre}: {linea}", flush=True)
