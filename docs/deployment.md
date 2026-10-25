# Preparación para Streamlit Community Cloud

Revisión: **2026-10-25**. El lanzamiento funcional está pendiente del paquete público y de la validación del despliegue.

## Configuración prevista

| Campo | Valor |
| --- | --- |
| Repositorio | `edarji/pml-explorer-web` (público e independiente) |
| Rama | `main` |
| Entrada | `app.py` |
| Python | Seleccionar 3.14 en Advanced settings; referencia local 3.14.7 |
| Dependencias | `requirements.txt` en raíz |
| Secrets | Vacío: no se necesitan |
| Datos | `data/public/*.parquet` aprobados y versionados |
| URL pública | Pendiente de asignación y comprobación por Streamlit |

La [documentación oficial de despliegue](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy) indica que se eligen repositorio, rama, entrada y versión de Python. Se comprobó con pip en modo dry-run la resolución de dependencias y disponibilidad de ruedas Linux x86_64 para CPython 3.14 el 2026-10-25; falta confirmar la construcción y ejecución efectivas en Community Cloud. No cambiar versiones silenciosamente para resolver una incompatibilidad: validar y registrar cualquier ajuste.

Se fijaron Streamlit 1.66.1, DuckDB 1.5.6, pandas 3.0.6 y PyArrow 26.0.0, presentes en el entorno local inspeccionado. Son dependencias del visor y del intercambio de tablas. No se copió el congelado completo del laboratorio, que incluye paquetes de otros procesos. No se identificaron dependencias de sistema que justifiquen `packages.txt`.

## Comportamiento y rutas

`app.py` carga `vista1.py`. Los datos se resuelven respecto a la ubicación de ese archivo, sin rutas personales ni dependencia del directorio de trabajo. El catálogo se obtiene del propio paquete público. DuckDB consulta Parquet sin una base persistente. La vista detiene la ejecución con un aviso si el paquete está ausente.

No se incluye la configuración de servicio del equipo de desarrollo, programadores de tareas, descargadores, entorno virtual, archivos crudos ni bases operativas. El código web no hace solicitudes a CENACE ni al equipo de origen. Las actualizaciones requieren preparar y revisar una nueva versión del paquete y volver a desplegar/reiniciar para invalidar cachés.

## Secuencia de lanzamiento pendiente

1. Preparar y aprobar el paquete descrito en [data/README.md](../data/README.md); registrar corte y fecha de extracción reales.
2. Revisar las limitaciones metodológicas de cobertura y catálogo. Confirmar que el paquete cumple el esquema para que `COUNT(*)` cuente horas válidas.
3. Crear la aplicación en Community Cloud con la configuración anterior. No hace falta un secreto para leer archivos de este repositorio público. Si el inicio de sesión solicita nuevos permisos, revisarlos en ese momento.
4. Revisar instalación en Linux y logs. Probar un nodo con historia, otro de incorporación posterior, un rango sin datos, fechas inválidas y las tres resoluciones; contrastar con las observaciones horarias. Medir memoria, carga inicial y consultas del histórico completo.
5. Confirmar la URL real `*.streamlit.app` y acceso público. Solo entonces añadir en `https://edarji.net/mercados` un enlace «Abrir PML Explorer» y el corte de datos. No se modificó el sitio durante esta preparación.

La nube sirve la aplicación desde su infraestructura. El Mac mini no debe abrir puertos ni recibir conexiones entrantes, túneles o acceso remoto. Ningún paso necesita exponerlo a internet.

Referencias: [organización de archivos](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/file-organization) y [dependencias](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/app-dependencies).

## Comprobaciones de preparación realizadas

- Sintaxis Python verificada en ambos archivos.
- Comparación estructural de funciones: `serie` y `estadisticas` conservan las consultas originales salvo la ruta parametrizada de Parquet.
- Streamlit AppTest ejecutado desde un directorio distinto a la raíz: aviso de paquete ausente, sin excepciones ni métricas inventadas. No se arrancó un servidor ni se abrieron puertos.
- Versiones fijadas presentes en el entorno inspeccionado; resolución de dependencias Linux/Python 3.14 comprobada con pip dry-run, sin instalación en el entorno de trabajo.
- Revisión de los archivos de publicación: solo código del visor y documentación; sin datos, credenciales, rutas personales ni configuración de servicios locales. La revisión por patrones no sustituye la revisión del futuro paquete.

No se ha validado la vista con derivados públicos porque todavía no existe un paquete aprobado. Tampoco se ha ejecutado la aplicación en Community Cloud ni se ha probado consumo de memoria del histórico completo.
