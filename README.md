# Rama `datos-demanda` (solo datos)

Demanda del día por región, leída cada hora de la Gráfica de Demanda pública del CENACE
(https://www.cenace.gob.mx/graficademanda.aspx) por el Mac mini y publicada aquí por `pml-bot` (Issue #32).

- `demanda/AAAA-MM-DD.csv`: 10 gerencias × 24 horas (SIN, BCA, BCS y las 7 regiones del SIN), en MW.
- `demanda/metadata.json`: días publicados, última lectura, estados y aviso.

Esta rama no tiene la app: Streamlit Cloud despliega `main`, así que aquí los commits no provocan despliegues.
Información indicativa de la operación, no para liquidación. Contrato completo: `docs/demanda-contrato.md` en
`edarji/power-market-lab`.
