# Preparación de Streamlit Community Cloud

Revisión: **2026-10-25**. No se ha creado ni desplegado una aplicación pública de Streamlit durante esta preparación. **El primer despliegue requiere aprobación explícita de Lalo.** Crear/actualizar este repositorio público es una acción distinta, ya autorizada.

## Configuración lista

| Campo | Valor |
| --- | --- |
| Repositorio | `edarji/pml-explorer-web`, público |
| Rama | `main` |
| Entrada | `app.py` |
| Python | 3.14 en Advanced settings; entorno de referencia 3.14.7 |
| Dependencias | `requirements.txt` en raíz, versiones del visor validado |
| Configuración | `.streamlit/config.toml` |
| Secrets | Vacío; la lectura de este paquete público no necesita secretos |
| Datos | `data/hourly/`, `data/daily/`, `nodes.parquet`, `metadata.json` |
| URL de aplicación | Pendiente; no se anuncia una URL supuesta |

La [guía oficial](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy) permite elegir repositorio, rama, entrada y versión de Python. El valor predeterminado de Python del servicio puede ser distinto; seleccionar explícitamente 3.14. Falta comprobar la instalación real en Linux/Community Cloud. La resolución Linux con pip dry-run se había comprobado para estas mismas cuatro versiones en la preparación anterior; no sustituye una construcción real.

La [configuración TOML](https://docs.streamlit.io/develop/api-reference/configuration/config.toml) mantiene las protecciones CORS/XSRF y desactiva estadísticas de uso. No fija dirección ni puertos de una máquina de desarrollo. Para pruebas locales usar `--server.address 127.0.0.1`; las pruebas automatizadas AppTest no levantan servidor.

## Preparación y estado antes de pedir aprobación de despliegue

1. **Completado:** paquete real recibido y validado conforme al [contrato v1](data-contract.md); ver [informe de entrega](validation-delivery-2026-10-25.md).
2. **Completado para esa entrega:** validador aprobado y nueve casos de referencia de tres nodos cuadrados. Para futuras versiones, ejecutar `python scripts/validar_datos.py --data-dir /ruta/al/paquete` y repetir el cuadre. Probar rangos largos, límites inclusivos de la ventana, rango vacío de un nodo, fechas invertidas y las tres resoluciones. Mediana/P10/P90 deben estar ausentes fuera de la ventana.
3. Claude verifica la seguridad del paquete, prueba el rechazo de una copia dañada y obtiene la aprobación acordada para su primer push manual. Work no exporta datos ni configura deploy keys.
4. Revisar el commit final, repetir la validación del paquete versionado y presentar a Lalo los resultados y los pendientes. Solicitar su aprobación para la primera publicación de la aplicación.

## Después de la aprobación

1. En Community Cloud, crear la aplicación con los campos anteriores, sin pegar secretos innecesarios. Si el servicio solicita nuevos permisos, revisarlos en ese momento.
2. Medir instalación, arranque en frío, RAM y consulta de histórico completo, especialmente el coste de abrir unas 410 particiones. La partición semanal es un plan B de Claude que requeriría nuevo acuerdo y medición; no se cambia aquí.
3. Confirmar con Lalo las cifras y la URL real `*.streamlit.app` antes de anunciarla. Claude prepara el enlace desde `https://edarji.net/mercados` mediante PR según el reparto acordado.
4. Claude configura `launchd` de las 23:00 y verifica tres días de commits de `pml-bot`. Esa automatización no forma parte del visor ni se configura aquí.

## Operación del visor

Las rutas parten de `vista1.py`. No hay dependencia de una ruta personal, base de datos persistente ni descarga desde CENACE al atender consultas. Un paquete ausente/incompatible detiene la vista. El validador de filas se ejecuta como paso previo a aceptar datos; la aplicación verifica inventario, SHA-256, conteos, esquema y compresión al cargar una nueva versión, mientras que el validador realiza la auditoría completa de filas.

La caché incluye la huella de los archivos y metadata, con límites de entradas. Cambiar el paquete invalida las consultas sin servir indefinidamente resultados anteriores. El pipeline debe publicar archivos y metadata consistentes en un solo commit. La revisión de procedencia y el cuadre de todas las filas corresponden al proceso de aceptación del paquete.

El Mac mini no abre puertos, túneles ni conexiones entrantes. La nube sirve su propia copia. Las credenciales de escritura de `pml-bot` permanecen fuera del repositorio y del visor.
