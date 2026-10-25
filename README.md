# PML Explorer v0.1

Vista 1 de **Electricity Markets Monitor**: evolución histórica del Precio Marginal Local de un nodo, Mercado del Día en Adelanto (MDA), Sistema Interconectado Nacional (SIN) de México. Fuente: CENACE. Unidades: MXN/MWh.

**Estado al 25 de octubre de 2026:** repositorio público preparado para integrar el paquete de Claude. Se conserva la vista validada y se añade lectura del particionado aprobado. Falta cotejar el esquema final del exportador y probar sus archivos reales. **No se ha realizado el primer despliegue en Streamlit Community Cloud; requiere aprobación de Lalo.** Sin paquete, la aplicación muestra un aviso y no publica cifras.

## Estructura aprobada

```text
app.py                     # explorer.py adaptado, misma vista 1
vista1.py                  # consultas validadas + lectura del resumen diario
requirements.txt
.streamlit/config.toml
.gitignore
README.md
docs/methodology.md

data/                      # solo lo escribe el pipeline de Claude / pml-bot
  hourly/AAAA-MM-DD.parquet # ventana móvil de hasta 365 días
  daily/AAAA-MM.parquet     # histórico diario desde enero de 2023
  nodes.parquet
  metadata.json
```

`docs/data-contract.md`, `docs/deployment.md` y `docs/validation.md` registran la interfaz de integración, el procedimiento de despliegue y las pruebas/pendientes. `scripts/validar_datos.py` es un verificador de solo lectura; `tests/` comprueba las fórmulas sin generar precios ficticios.

**Work no crea, edita, elimina ni versiona cambios de `data/`.** No incluye muestras ni exporta datos operativos. Las carpetas y archivos de datos de la estructura los creará exclusivamente el pipeline. Los dos archivos heredados `data/README.md` y `data/public/.gitkeep` se conservaron intactos para respetar esa separación; su contrato anterior queda reemplazado por [docs/data-contract.md](docs/data-contract.md). El visor ya no lee `data/public/`.

## Ejecución

Usar un entorno independiente con Python 3.14, versión de referencia del visor original:

```bash
python3.14 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m streamlit run app.py --server.address 127.0.0.1
```

Las cuatro versiones fijadas corresponden al entorno validado. No se requiere base DuckDB persistente, conexión al equipo de origen ni secretos. Las rutas se resuelven respecto al código. La nube ejecutará su propia copia; el Mac mini no recibe conexiones entrantes.

## Integrar la entrega de Claude

1. Cotejar el [contrato](docs/data-contract.md), en particular nombres de columnas de extremos diarios y metadatos de extracción. Ajustar el lector al contrato final, sin cambiar el exportador ni los cálculos aprobados.
2. Validar la carpeta temporal **sin copiarla al repositorio**:

   ```bash
   .venv/bin/python scripts/validar_datos.py --data-dir /ruta/al/paquete-publico
   ```

3. Comparar contra los resultados de Claude en tres nodos, incluido uno de alta posterior; probar la vista y medir recursos. El validador no equivale a comprobar toda la procedencia ni a la revisión de seguridad del pipeline.
4. Claude realiza la revisión de seguridad y el primer push de datos con la aprobación acordada. A partir de ahí, `data/` solo se actualiza mediante `pml-bot`.
5. Solicitar aprobación de Lalo para el primer despliegue público. Los campos de Community Cloud están en [despliegue](docs/deployment.md).

## Reglas de interpretación

El promedio siempre es simple por hora válida, sin ponderación de demanda. El diario permite reconstruir promedio, extremos, conteo de horas negativas y desviación muestral; **mediana/P10/P90 solo se muestran si todo el rango cae dentro de `horario_desde..horario_hasta`**. Fuera de esa ventana se ofrecen gráfica diaria/mensual y estadísticas reconstruibles, sin imputar precios ni estimar cuantiles. Consultar [metodología y limitaciones](docs/methodology.md).

Los cambios económicos se validan primero en `power-market-lab`; después se trasladan aquí con sus pruebas. Este repositorio no modifica el laboratorio privado ni contiene su configuración operativa.

Destino posterior al despliegue aprobado: enlace desde [edarji.net/mercados](https://edarji.net/mercados). No hay todavía una URL de aplicación confirmada.
