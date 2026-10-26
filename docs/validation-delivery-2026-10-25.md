# Validación de entrega real — 2026-10-25

**Resultado: paquete aceptado por las comprobaciones de Work.** No se desplegó la aplicación ni se incorporaron datos al repositorio. La aceptación corresponde exclusivamente al paquete identificado abajo, ejecutado con el lector del commit `194ceb3`.

## Identidad y cobertura

- Archivo recibido: `pml_para_work.zip`.
- SHA-256 del ZIP: `c3a6a45651b38cc5286ad151f097c64f872eb91568c8a94fdafb5003af85bb2a`.
- SHA-256 de `publico/metadata.json`: `11917d21836eb2e22117702660e45c5dbf69c9c868a99462b591516734d940b2`.
- Esquema 1; CENACE SW-PML, MDA, SIN; MXN/MWh.
- Generación: `2026-10-26T01:23:52Z`, mostrada como **2026-10-25 19:23:52 CST**, Ciudad de México.
- Histórico diario: **2023-01-01 a 2026-10-22**.
- Ventana horaria: **2025-10-23 a 2026-10-22**, 365 días inclusivos.
- 2,459 nodos; 412 Parquet: 365 horarios, 46 mensuales diarios y un catálogo.
- 21,440,304 filas horarias y 3,366,654 filas diarias.
- Paquete válido sin comprimir como carpeta: 134,817,676 bytes, incluida metadata.

El ZIP se extrajo a una carpeta temporal independiente. Sus documentos se usaron como evidencia de referencia, no como autorización para publicar ni como instrucciones de ejecución. El paquete dañado se mantuvo separado del válido.

## Comprobaciones

1. `scripts/validar_datos.py` aceptó la carpeta `publico`: inventario, SHA-256, filas, columnas, tipos, compresión zstd, orden por nodo, unicidad, finitud, etiquetas horarias, acumuladores, catálogo y fechas observadas.
2. Cuadró el horario contra el diario en **todo el solapamiento**, con las tolerancias del validador. Duración local de esta ejecución: **2.99 segundos**.
3. La carpeta `prueba_work/paquete_danado` fue rechazada con salida 1 por **SHA-256 incompatible en `hourly/2026-07-14.parquet`**. El control se detuvo en ese primer fallo; no se afirma que llegara a comprobar los fallos posteriores de esa copia.
4. Los **nueve casos** de `prueba_work/referencia.json` coincidieron: tres rangos por cada uno de `01AAN-85`, `03MPK-115` y `02YCP-230`. Se contrastaron estadísticas y series diaria/mensual: últimos 30 días, cruce del límite horario y mes parcial. Tolerancia de comparación tras redondeo: 0.005, sin tolerancia relativa. Fuera de ventana se exigió ausencia de mediana/P10/P90, aunque la referencia original sí los contenga.
5. El nodo `03MPK-115` conserva su cobertura parcial: 288 de 528 horas, **54.5%**, en octubre parcial; el rango anterior a su primera observación no muestra métricas.

## Interfaz y recursos locales

Streamlit AppTest ejecutó el código real, con los lectores apuntando a la carpeta temporal y sin sustituir los resultados de las consultas. No levantó servidor ni abrió puertos.

Pasaron nueve recorridos: inicio con histórico completo, mensual, rechazo horario fuera de ventana, horario en toda la ventana inclusiva, rechazo un día antes, cruce con resolución diaria, nodo sin datos, nodo tardío/mes parcial y fechas invertidas. Se comprobó también la actualización en Ciudad de México y los selectores de fechas desde metadata.

La ejecución local observó **0.48 s** para el arranque AppTest y **305.2 MiB** de RSS máximo del proceso de pruebas de interfaz. La comparación de referencias observó 174.6 MiB de RSS máximo. Son mediciones locales de procesos concretos; **no constituyen mediciones de Community Cloud ni una garantía de sus recursos**.

## Pendientes para publicar

- Claude conserva la revisión de seguridad de su pipeline, las credenciales de escritura y el primer push de `pml-bot`, con la aprobación acordada. Al cerrar esta revisión, `origin/main` seguía en `194ceb3` y no contenía Parquet ni metadata.
- Comprobar que el paquete publicado coincide con este manifiesto; si cambia, repetir la validación de la nueva versión.
- Solicitar aprobación de Lalo antes del primer despliegue público de Streamlit.
- Tras aprobarlo, verificar instalación/ejecución en Linux, tiempo y RAM en Community Cloud, y URL real. Después completar las actualizaciones diarias y el enlace desde edarji.net conforme al reparto acordado.

Work no escribió ni cambió archivos en `data/`, no modificó `power-market-lab` y no publicó la copia dañada ni el paquete válido.
