# PML Explorer v0.1

Primer producto de **Electricity Markets Monitor**: evolución histórica del Precio Marginal Local del Mercado del Día en Adelanto (MDA), Sistema Interconectado Nacional (SIN) de México. Fuente: CENACE. Unidades: MXN/MWh.

**Estado al 2026-10-25:** código real de la vista 1 preparado para publicación; paquete de datos públicos pendiente. Esta versión inicia con un aviso cuando no hay datos; no incluye precios de ejemplo. El despliegue funcional con datos y su URL pública todavía requieren validación.

La vista conserva selección de nodo y fechas, resolución horaria/diaria/mensual, cobertura, indicadores, gráfica y tabla de estadísticas. Las adaptaciones se limitan al empaquetado: punto de entrada en raíz, rutas basadas en el archivo, catálogo obtenido del paquete público y aviso sin datos. No se añaden vistas nuevas.

## Archivos

- `app.py`: aplicación Streamlit real.
- `vista1.py`: consultas DuckDB de la vista 1.
- `requirements.txt`: cuatro dependencias fijadas a las versiones del entorno validado.
- `data/public/`: exclusivamente derivados públicos revisados, actualmente vacío.
- [Metodología](docs/methodology.md), [contrato de datos](data/README.md) y [despliegue](docs/deployment.md).

## Ejecutar en un entorno independiente

Python 3.14 es la versión de referencia del código inspeccionado. Crear un entorno nuevo en esta copia pública:

```bash
python3.14 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

Para ejecutar en una máquina de desarrollo aislada, sin exposición externa:

```bash
.venv/bin/python -m streamlit run app.py --server.address 127.0.0.1
```

No se necesita arrancar un servidor en el Mac mini para publicar. Streamlit Community Cloud ejecutará su propia copia del repositorio. No requiere conexión entrante, túnel, acceso remoto ni base DuckDB persistente.

## Datos y alcance

Cobertura histórica prevista desde **2023-01-01**, sujeta a disponibilidad real por nodo. El repositorio no distribuye una base operativa ni el histórico de trabajo. El paquete público debe prepararse separadamente y satisfacer [este contrato](data/README.md). La aplicación no descarga datos, no actualiza archivos ni conecta al equipo de origen.

No se deben sustituir observaciones horarias por promedios diarios/mensuales: se perderían la resolución horaria y los cálculos exactos de mediana y percentiles.

## Publicación

Destino: `edarji/pml-explorer-web`, rama `main`, entrada `app.py`, Streamlit Community Cloud. No requiere secretos. Enlazar desde [edarji.net/mercados](https://edarji.net/mercados) una vez verificada la URL real del despliegue y su paquete de datos. No se asigna una URL de aplicación hasta que el servicio la confirme.
