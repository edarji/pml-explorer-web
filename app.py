"""Entrada pública de PML Explorer."""
import base64
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

import altair as alt
import duckdb
import pandas as pd
import streamlit as st

import catalogo as cat_nodos
import ensemble as ens
import exportar
import pnd as pnd_zonas
import ticker

from enlaces import PARAMETROS, VISTAS_URL, construir_enlace, leer_enlace
from escena import ENSEMBLE, SOLO, enlace_ensemble, escena_de_enlace
from rangos import RANGOS_RAPIDOS, rango_rapido
from vista2 import diferencial, resumen
from vista3 import componentes, resumen_componentes
from vista1 import (DATA_DIR, RESOLUCIONES, UMBRAL_DESCUADRE, DatosNoDisponibles, actualizado_cdmx, catalogo,
                    cobertura_horaria, estadisticas, huella_paquete,
                    inspeccionar_paquete, marcar_periodos, metadata, observado, serie)

VERSION_APP = "v0.8.7 beta"  # versión de la aplicación; el esquema de datos y la fecha vienen del paquete
REPO = "https://github.com/edarji/pml-explorer-web/blob/main"
COBERTURA_ESCASA = 80  # % de horas con dato bajo el cual se advierte explícitamente
SITIO_MERCADOS = "https://edarji.net/mercados/"
URL_APP = "https://pml-explorer.streamlit.app/"  # base del enlace copiable junto a «Descargar CSV»
ZONA_MERCADO = ZoneInfo("America/Mexico_City")
AYUDA_NODO = ("Escribe la clave NodoP (por ejemplo 06ESC) o parte del nombre oficial. La clave identifica "
              "el nodo; el nombre solo ayuda a encontrarlo y puede repetirse en varias claves.")
SIN_RESULTADOS = ("¿Sin resultados? Prueba con la clave (por ejemplo 06ESC) o revisa Región, Estado y Zona. "
                  "Pulsa Esc o borra el texto para conservar el nodo elegido.")
# v0.6.0 · Sin catálogo de referencia válido la app vuelve al comportamiento de v0.5.1: solo claves.
AYUDA_SOLO_CLAVE = ("Escribe la clave NodoP o parte de ella, por ejemplo 06ESC. El catálogo de nombres y "
                    "ubicaciones no está disponible en esta publicación.")
TODAS = "Todas"
UBICACION = {}  # se llena al cargar el paquete: {"union": DataFrame, "nombres": dict, "manifiesto": dict}
# v0.7.0 · Precio de zona de carga. Se llena solo si la carpeta pública pnd/ pasa su contrato; si no, la app es
# exactamente la de PML (sin selector de modalidad). {"limites", "zonas", "regiones", "version"}
PND = {}
MODALIDADES = {"pml": "PML · NodoP", "pnd": "PND · Zona de carga"}
MODALIDADES_CORTAS = {"pml": "PML · nodo", "pnd": "PND · zona"}  # v0.8.2: barra superior compacta
ZONA_DEFECTO = "MONTERREY"
PND_HORARIA_MAX_DIAS = 366  # la gráfica horaria de más de un año no se lee y pesa en el navegador
# H03: los st.caption de Streamlit 1.66 usan opacidad 0.6 (≈3.70:1 sobre blanco). Con 0.8 el texto
# queda en ≈6.67:1 sobre blanco y ≈6.19:1 sobre gris claro, por debajo del texto principal (12.53:1).
ESTILOS = """<style>
/* v0.6.3 · Dark Trading (Bloomberg Black + Apple Bolsa). Solo colores y tipografía; la estructura es la de v0.5–v0.6.2.
   Paleta: negro #000, superficies #111113/#1C1C1E, bordes #2C2C2E, texto #F2F2F7, secundario #A1A1A6,
   ámbar #FFB000 (logo sax), azul #0A84FF, verde #30D158 / rojo #FF453A solo para cambios. */
[data-testid='stCaptionContainer']{opacity:0.8}
.block-container{max-width:1240px}
/* Cifras con ancho fijo por dígito, como en una pantalla de cotizaciones: las columnas no bailan. */
.precio,.st-key-ficha,.fila,.rango,[data-testid=stMetricValue],[data-testid=stDataFrame]{font-variant-numeric:tabular-nums}
/* v0.5 · Pestañas: el radio de vistas se dibuja como barra de pestañas subrayada (activa en ámbar). */
.st-key-pestanas div[role=radiogroup]{gap:0;border-bottom:1px solid #2C2C2E;flex-wrap:nowrap;overflow-x:auto}
.st-key-pestanas div[role=radiogroup] label{padding:.5rem 1.1rem .55rem;margin:0;border-bottom:3px solid transparent;
  white-space:nowrap}
.st-key-pestanas div[role=radiogroup] label > div > div:first-child{display:none}
.st-key-pestanas div[role=radiogroup] label p{font-size:1.02rem;color:#A1A1A6}
.st-key-pestanas label[data-selected=true]{box-shadow:inset 0 -3px 0 #FFB000}
.st-key-pestanas label[data-selected=true] p{font-weight:600;color:#F2F2F7}
/* v0.5.1 · Móvil: las tres pestañas no caben en una fila (≈526 px) y «Componentes» quedaba fuera de la
   pantalla. En pantallas angostas la barra pasa a dos filas en vez de desplazarse: todas siempre visibles. */
@media (max-width:640px){
.st-key-pestanas div[role=radiogroup]{flex-wrap:wrap;overflow-x:visible}
.st-key-pestanas div[role=radiogroup] label{padding:.45rem .6rem .5rem}
.st-key-pestanas div[role=radiogroup] label p{font-size:.92rem}
}
/* v0.6.2 · Descarga: en pantallas angostas el botón y el enlace ocupan todo el ancho, uno bajo otro. */
@media (max-width:640px){
.st-key-descarga{flex-direction:column;align-items:stretch}
.st-key-descarga button{width:100%}
}
/* v0.5.1 · Recuadro al pasar el mouse: pequeño para no tapar la gráfica; v0.6.3 en grafito. */
#vg-tooltip-element{font-size:11px;padding:4px 7px;background:#1C1C1E;color:#F2F2F7;border:1px solid #3A3A3C;
  box-shadow:0 4px 14px rgba(0,0,0,.6)}
#vg-tooltip-element td.key{padding-right:6px;color:#A1A1A6}
/* Botones de rango: pastillas pequeñas (como 1D/1S/1M de Bolsa); la activa en ámbar. */
.st-key-rangos button{min-height:2rem;padding:.1rem .85rem;border:1px solid #3A3A3C;background:#1C1C1E;
  border-radius:999px;color:#F2F2F7}
.st-key-rangos button p{font-size:.85rem;font-weight:600}
.st-key-rangos button[kind=primary]{background:#FFB000;border-color:#FFB000;color:#000}
/* Encabezado tipo cotización: cifra grande blanca y cambio en pastilla verde/roja (Apple Bolsa). */
.precio{display:flex;flex-wrap:wrap;align-items:baseline;gap:.35rem .8rem;margin:-.4rem 0 .2rem}
.precio .valor{font-size:2.6rem;font-weight:700;letter-spacing:-.02em;line-height:1.1;color:#FFFFFF}
.precio .unidad{font-size:1rem;font-weight:600;color:#A1A1A6}
.precio .cambio{font-size:1.15rem;font-weight:700;padding:.05rem .5rem;border-radius:.35rem}
.precio .cambio.sube{background:#30D158;color:#000}.precio .cambio.baja{background:#FF453A;color:#000}
.precio .cambio.igual{background:#3A3A3C;color:#F2F2F7}
.precio .fecha{font-size:.85rem;color:#A1A1A6}
.sube{color:#30D158}.baja{color:#FF453A}.igual{color:#A1A1A6}
.linea-meta{font-size:.85rem;color:#A1A1A6;margin-bottom:.4rem}
/* Tarjeta de gráfica + ficha de indicadores: superficie grafito con borde fino (terminal). */
.st-key-tarjeta{background:#111113;border:1px solid #2C2C2E;border-radius:.8rem;padding:1rem 1.1rem .9rem}
.st-key-ficha{border-left:1px solid #2C2C2E;padding-left:1rem}
.st-key-ficha [data-testid=stMetric]{padding:0}
.st-key-ficha [data-testid=stMetricLabel]{min-height:0;margin:0}
.st-key-ficha [data-testid=stMetric] > div{display:flex;justify-content:space-between;align-items:baseline;gap:.5rem}
.st-key-ficha [data-testid=stMetricLabel] p{font-size:.88rem;color:#A1A1A6}
.st-key-ficha [data-testid=stMetricValue], .st-key-ficha [data-testid=stMetricValue] p{font-size:.92rem;font-weight:600;line-height:1.6;height:auto;min-height:0;color:#F2F2F7}
.st-key-ficha [data-testid=stVerticalBlock]{gap:.1rem}
.fila{display:flex;justify-content:space-between;font-size:.88rem;line-height:1.75;border-top:1px solid #1C1C1E}
.fila span:first-child{color:#A1A1A6}
.rango{margin:.1rem 0 .7rem}.rango .et{font-size:.88rem;color:#A1A1A6}
.rango .barra{position:relative;height:3px;background:#3A3A3C;margin:.55rem 0 .3rem;border-radius:2px}
.rango .barra span{position:absolute;top:-4px;width:11px;height:11px;border-radius:50%;background:#FFB000;
  transform:translateX(-50%)}
.rango .ext{display:flex;justify-content:space-between;font-size:.75rem;color:#A1A1A6}
/* En una columna (móvil) la ficha va debajo de la gráfica: el separador pasa de vertical a horizontal. */
@media (max-width:640px){
.st-key-ficha{border-left:none;padding-left:0;border-top:1px solid #2C2C2E;padding-top:.6rem}
}
/* v0.6.4 · Pulido UX. Segunda tarjeta (vista 2: curvas de cada nodo) con el mismo estilo. */
.st-key-tarjeta_curvas{background:#111113;border:1px solid #2C2C2E;border-radius:.8rem;padding:1rem 1.1rem .6rem}
/* Marca: logo y título en una fila también en móvil (antes el logo ocupaba su propia fila). */
.st-key-marca{flex-wrap:nowrap}
.st-key-marca h1{padding:.2rem 0 0}
/* Foco visible con teclado en pestañas y pastillas. */
.st-key-pestanas label:has(input:focus-visible){outline:2px solid #FFB000;outline-offset:-2px;border-radius:.3rem}
.st-key-rangos button:focus-visible{outline:2px solid #FFB000;outline-offset:2px}
.st-key-rangos button{min-height:2.25rem;min-width:3.2rem}
@media (max-width:640px){
/* Primera pantalla compacta: marca, pestañas y pastillas ocupan menos alto para llegar antes a la cifra y la gráfica. */
.st-key-marca .logo-pml{width:52px}
.st-key-marca h1{font-size:1.75rem}
.block-container h3{font-size:1.2rem}
.precio .valor{font-size:2.1rem}
.precio .cambio{font-size:1rem}
/* Pastillas cómodas al tacto: 44 px de alto (guía de Apple). */
.st-key-rangos button{min-height:44px;min-width:56px}
}
/* v0.8.0 · Graphite Trading | Ensemble & Solo. Sin animaciones. */
.st-key-seccion_pml,.st-key-seccion_pnd,.st-key-atril{background:#F7F7F8;border:1px solid #D5D7DB;border-radius:.8rem;
  padding:.9rem 1rem .5rem}
.seccion-et{display:flex;flex-wrap:wrap;align-items:baseline;gap:.15rem .6rem;font-size:1.02rem}
.seccion-et span:last-child{font-size:.82rem;color:#5A5D63}
.seccion-et .marca{width:.6rem;height:.6rem;border-radius:2px;align-self:center}
.marca.pml{background:#FFB000}.marca.pnd{background:#0A84FF}
.kpis{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:.5rem;margin:.3rem 0 .2rem}
.kpi{background:#FFFFFF;border:1px solid #DADCE0;border-radius:.55rem;padding:.5rem .65rem;min-width:0}
.kpi .et{font-size:.78rem;color:#5A5D63}
.kpi .v{font-size:1.35rem;font-weight:700;color:#111720;font-variant-numeric:tabular-nums;line-height:1.3}
.kpi .nota{font-size:.75rem;color:#5A5D63;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.mini-et{font-size:.8rem;color:#5A5D63;margin:.35rem 0 -.2rem}
.lista-et{font-size:.8rem;color:#5A5D63;margin:.3rem 0 0}
[class*=st-key-rk_][data-testid=stVerticalBlock],[class*=st-key-wl_][data-testid=stVerticalBlock]{gap:.3rem}
[class*=st-key-rk_] button,[class*=st-key-wl_] button{justify-content:flex-start;min-height:2.25rem;padding:.2rem .7rem;background:#FFFFFF;
  border:1px solid #DADCE0;font-variant-numeric:tabular-nums;text-align:left}
[class*=st-key-rk_] button > div,[class*=st-key-wl_] button > div{justify-content:flex-start;width:100%}
[class*=st-key-rk_] button p,[class*=st-key-wl_] button p{font-size:.85rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
[class*=st-key-rk_] button:hover,[class*=st-key-wl_pml] button:hover{border-color:#E09A00;background:#FFF8E6}
[class*=st-key-rk_pnd] button:hover,[class*=st-key-wl_pnd] button:hover{border-color:#0A84FF;background:#EEF5FF}
.st-key-volver button{min-height:2.25rem;padding:.1rem .8rem;border:1px solid #C9CBD0;background:#FFFFFF;border-radius:999px}
.solista{display:flex;flex-wrap:wrap;align-items:baseline;gap:.1rem .7rem;margin:.1rem 0 .3rem;padding-left:.7rem;
  border-left:3px solid #FFB000}
.solista.pnd{border-left-color:#0A84FF}
.solista .et{flex-basis:100%;font-size:.74rem;letter-spacing:.06em;color:#5A5D63}
.solista .nombre{font-size:1.7rem;font-weight:700;color:#111720;letter-spacing:-.01em}
.solista .nombre .vs{font-size:1rem;color:#5A5D63;font-weight:600}
.solista .detalle{font-size:.86rem;color:#5A5D63}
/* Tableta y móvil (≤ 1024 px): el panel del solista (búsqueda y lista) va primero y el tablero debajo, ambos a todo el
   ancho (a 768 px una columna derecha quedaría en ≈190 px); ubicación y fechas van plegadas. KPI en 2 × 2. */
@media (max-width:1024px){
.st-key-ensemble > div > [data-testid=stHorizontalBlock],
.st-key-ensemble > [data-testid=stHorizontalBlock]{flex-direction:column-reverse}
.st-key-ensemble > div > [data-testid=stHorizontalBlock] > [data-testid=stColumn],
.st-key-ensemble > [data-testid=stHorizontalBlock] > [data-testid=stColumn]{width:100% !important;flex:1 1 100% !important}
.kpis{grid-template-columns:repeat(2,minmax(0,1fr))}
}
/* v0.8.0 · «Graphite híbrido»: fondo gris Bolsa #E8E9EC, tarjetas claras #F7F7F8, panel de análisis grafito #111720
   y serie ámbar. Estas reglas van al final y reemplazan los colores de Dark Trading de arriba; la estructura no cambia.
   Contraste: texto #1C1C1E sobre #E8E9EC 14:1; secundario #5A5D63 5.4:1; dentro del grafito, #A7AEB8 8:1. */
.st-key-pestanas div[role=radiogroup]{border-bottom-color:#C9CBD0}
.st-key-pestanas div[role=radiogroup] label p{color:#5A5D63}
.st-key-pestanas label[data-selected=true]{box-shadow:inset 0 -3px 0 #E09A00}
.st-key-pestanas label[data-selected=true] p{color:#1C1C1E}
.st-key-rangos button{border-color:#C9CBD0;background:#F7F7F8;color:#1C1C1E}
.st-key-rangos button[kind=primary]{background:#FFB000;border-color:#FFB000;color:#000}
button[kind=primary],button[kind=primary] p{color:#000}
.precio .valor{color:#111720}
.precio .unidad,.precio .fecha,.linea-meta{color:#5A5D63}
.precio .cambio.sube{background:#1E8E3E;color:#FFF}.precio .cambio.baja{background:#D70015;color:#FFF}
.precio .cambio.igual{background:#D5D7DB;color:#1C1C1E}
/* v0.8.1 · Un solo sistema claro: la gráfica y la ficha del solista van en tarjeta clara (ya no en grafito #111720).
   El solista es protagonista por escala, espacio y jerarquía, no por color de fondo. */
.st-key-tarjeta,.st-key-tarjeta_curvas{background:#FFFFFF;border-color:#D5D7DB;color:#1C1C1E;
  box-shadow:0 1px 2px rgba(17,23,32,.06)}
.st-key-ficha{border-left-color:#E3E5E9}
.st-key-ficha [data-testid=stMetricLabel] p,.fila span:first-child,.rango .et,.rango .ext span{color:#5A5D63 !important}
.st-key-ficha [data-testid=stMetricValue],.st-key-ficha [data-testid=stMetricValue] p,.fila span:last-child{color:#1C1C1E !important}
.fila{border-top-color:#EEF0F2}
.rango .barra{background:#D5D7DB}
.rango .barra span{background:#E09A00}
@media (max-width:640px){.st-key-ficha{border-top-color:#E3E5E9}}
#vg-tooltip-element{background:#FFFFFF;color:#1C1C1E;border-color:#D5D7DB;box-shadow:0 4px 14px rgba(17,23,32,.16)}
#vg-tooltip-element td.key{color:#5A5D63}
/* v0.8.1 · Solista al frente: el detalle aparece arriba, en una superficie clara con filo de color (ámbar PML, azul PND),
   y el ENSEMBLE sigue debajo en la misma página. */
.st-key-detalle_pml,.st-key-detalle_pnd{background:#F7F7F8;border:1px solid #D5D7DB;border-top:4px solid #FFB000;
  border-radius:.9rem;padding:.9rem 1.2rem 1rem;box-shadow:0 2px 12px rgba(17,23,32,.08);
  scroll-margin-top:calc(var(--alto-st) + var(--alto-barra) + var(--aire,.5rem))}
.st-key-detalle_pnd{border-top-color:#0A84FF}
.st-key-detalle_pnd .solista{border-left-color:#0A84FF}
.solista .nombre{font-size:2rem}
.banda-et{display:flex;flex-wrap:wrap;align-items:baseline;gap:.2rem .6rem;margin:1.4rem 0 .2rem;font-size:1.05rem}
.banda-et span{font-size:.82rem;color:#5A5D63}
[class*=st-key-rk_] button[kind=primary],[class*=st-key-wl_pml] button[kind=primary]{background:#FFF3D6;border-color:#E09A00}
[class*=st-key-rk_pnd] button[kind=primary],[class*=st-key-wl_pnd] button[kind=primary]{background:#E6F0FF;border-color:#0A84FF}
[class*=st-key-rk_] button[kind=primary] p,[class*=st-key-wl_] button[kind=primary] p{font-weight:600}
@media (max-width:640px){
.st-key-detalle_pml,.st-key-detalle_pnd{padding:.7rem .75rem .8rem;border-radius:.7rem}
}
@media (max-width:1024px){
.st-key-ensemble > div > [data-testid=stHorizontalBlock],.st-key-ensemble > [data-testid=stHorizontalBlock]{gap:1rem}
}
.st-key-nodo_tension button[aria-checked=true]{background:#FFB000;border-color:#FFB000;color:#000}
.st-key-nodo_tension button[aria-checked=true] p{color:#000;font-weight:600}
@media (max-width:640px){
.solista .nombre{font-size:1.4rem}
.kpi .v{font-size:1.15rem}
[class*=st-key-rk_] button,[class*=st-key-wl_] button{min-height:44px}
.st-key-volver button{min-height:44px}
}
/* v0.8.2 · Terminal persistente: barra superior fija (sticky) y «Elige otro solista» fijo a la derecha con su propio
   desplazamiento; el contenido central (detalle + ENSEMBLE) es lo único que se desplaza. --alto-barra lo fija un
   script con el alto real de la barra (puede ocupar dos filas). En ≤ 1024 px la lista no queda fija: va al final y la
   barra muestra «Cambiar nodo», que lleva a ella; así nunca tapa la gráfica. Sin animaciones. */
:root{--alto-st:3.75rem;--alto-barra:76px}
[data-testid=stHeader]{background:#E8E9EC}
/* Streamlit envuelve cada contenedor en stLayoutWrapper: lo fijo es esa envoltura (si no, no se pega al desplazarse). */
[data-testid=stLayoutWrapper]:has(> .st-key-barra){position:sticky;top:var(--alto-st);z-index:30}
.st-key-barra{background:#E8E9EC;border-bottom:1px solid #D5D7DB;padding:.55rem 0 .6rem;flex-wrap:wrap;row-gap:.35rem;
  box-shadow:0 6px 10px -8px rgba(17,23,32,.18)}
.st-key-barra .st-key-marca{width:auto;flex:0 1 auto;flex-wrap:nowrap;min-width:0}
.st-key-barra > [data-testid=stLayoutWrapper]:has(> .st-key-marca){flex:0 0 auto;width:auto;max-width:20rem}
.st-key-barra > [data-testid=stLayoutWrapper]:has(> .st-key-controles){flex:1 1 0;min-width:0}
.st-key-rangos button{min-width:2.9rem;padding:.1rem .65rem}
.st-key-barra .logo-pml{width:34px}
.st-key-barra .st-key-marca h1{font-size:1.3rem;padding:0;line-height:1.2}
.st-key-marca_texto{gap:0;min-width:0}
.st-key-marca_texto [data-testid=stMarkdownContainer],.st-key-marca_texto [data-testid=stCaptionContainer]{margin-bottom:0}
.st-key-marca_texto [data-testid=stHeaderActionElements]{display:none}
.st-key-marca_texto [data-testid=stCaptionContainer]{max-width:15rem;white-space:nowrap;overflow:hidden;
  text-overflow:ellipsis;font-size:.72rem}
.st-key-controles [data-testid=stElementContainer]:has(.estado-barra){flex:1 1 100%;width:100%}
.st-key-controles{flex:1 1 auto;flex-wrap:wrap;row-gap:.3rem;min-width:0}
.st-key-controles [data-testid=stRadio] label p{font-size:.85rem}
.st-key-controles [data-testid=stPopover] button{min-height:2rem;padding:.1rem .7rem;border-radius:999px;
  border:1px solid #C9CBD0;background:#F7F7F8}
.estado-barra{display:flex;flex-wrap:wrap;gap:.1rem .7rem;font-size:.76rem;color:#5A5D63;line-height:1.35}
.estado-barra .activo{font-weight:700;color:#1C1C1E}
.chip-cambiar{display:none;align-items:center;min-height:2rem;padding:.15rem .8rem;border-radius:999px;
  background:#FFB000;color:#000 !important;font-weight:600;font-size:.85rem;text-decoration:none !important}
#elige-solista{scroll-margin-top:calc(var(--alto-st) + var(--alto-barra) + 1.1rem)}
/* v0.8.5 · Ticker PND (Issue #34): una franja dentro de la barra fija, a todo el ancho, debajo de los controles. Como
   está dentro de .st-key-barra, el mismo ResizeObserver mide barra + cinta (--alto-barra): el rail y el enfoque del
   detalle quedan debajo de las dos. Desplazamiento continuo con CSS (dos copias, -50 %), pausa con el cursor o el foco;
   sin movimiento con «reducir movimiento» ni en ≤ 640 px (allí se desliza con el dedo). Los números no se animan. */
.st-key-barra > [data-testid=stLayoutWrapper]:has(> .st-key-ticker){flex:1 1 100%;width:100%;min-width:0}
.st-key-ticker{flex-wrap:nowrap;min-width:0;border-top:1px solid #D5D7DB;padding-top:.4rem;gap:.6rem}
.st-key-ticker > [data-testid=stElementContainer]:has(.tk-et){flex:0 0 auto;width:auto;max-width:19rem}
.tk-et{display:flex;flex-direction:column;font-size:.68rem;line-height:1.3;color:#5A5D63;white-space:nowrap}
.tk-et b{color:#1C1C1E;font-weight:700}
.st-key-ticker [data-testid=stMarkdownContainer]{margin-bottom:0}
.tk-et .tk-corto{display:none;font-style:normal}
.st-key-ticker > [data-testid=stLayoutWrapper]:has(> .st-key-cinta){flex:1 1 0;min-width:0}
.st-key-cinta{overflow:hidden;min-width:0;scroll-padding-inline:1.4rem;
  mask-image:linear-gradient(90deg,transparent 0,#000 1.2rem,#000 calc(100% - 1.2rem),transparent 100%)}
/* Pista y copias miden lo que su contenido (no se encogen al ancho de la cinta): -50 % es justo una copia. */
.st-key-cinta > [data-testid=stLayoutWrapper]:has(> .st-key-pista),.st-key-pista > [data-testid=stLayoutWrapper]{
  flex:0 0 auto !important;width:max-content !important;max-width:none !important}
.st-key-pista{flex:0 0 auto !important;flex-wrap:nowrap !important;width:max-content !important;gap:0 !important;
  animation:tk-desliza 48s linear infinite;will-change:transform}
.st-key-cinta:hover .st-key-pista,.st-key-cinta:focus-within .st-key-pista{animation-play-state:paused}
@keyframes tk-desliza{from{transform:translateX(0)}to{transform:translateX(-50%)}}
/* Con teclado (foco visible) la cinta se detiene y se vuelve desplazable: el navegador lleva la ficha enfocada a la vista. */
.st-key-cinta:has(:focus-visible){overflow-x:auto;mask-image:none}
.st-key-cinta:has(:focus-visible) .st-key-pista{animation:none}
.st-key-cinta:has(:focus-visible) .st-key-pista > [data-testid=stLayoutWrapper]:has(> .st-key-tk_copia_b){display:none}
[class*=st-key-tk_copia_]{flex:0 0 auto !important;flex-wrap:nowrap !important;width:max-content !important;
  padding-right:.5rem;gap:.5rem !important}
[class*=st-key-tk_copia_] > [data-testid=stElementContainer]{width:auto !important;flex:0 0 auto}
[class*=st-key-tka_] button,[class*=st-key-tkb_] button{min-height:2rem;padding:.1rem .7rem;border-radius:999px;
  border:1px solid #D5D7DB;background:#F7F7F8;white-space:nowrap}
[class*=st-key-tka_] button p,[class*=st-key-tkb_] button p{font-size:.8rem;white-space:nowrap;
  font-variant-numeric:tabular-nums}
[class*=st-key-tka_] button p em,[class*=st-key-tkb_] button p em{font-style:normal;font-weight:600;color:#3A3D42}
[class*=st-key-tka_] button p strong,[class*=st-key-tkb_] button p strong{font-weight:700;color:#1C1C1E}
[class*=st-key-tka_] button code,[class*=st-key-tkb_] button code{background:none;padding:0;font-family:inherit;
  font-size:.78rem;font-weight:600;color:#5A5D63}
[class*=st-key-tka_sube_] button code,[class*=st-key-tkb_sube_] button code{color:#B3261E}
[class*=st-key-tka_baja_] button code,[class*=st-key-tkb_baja_] button code{color:#1B7F3B}
@media (prefers-reduced-motion: reduce){
.st-key-pista{animation:none}
.st-key-cinta{overflow-x:auto;mask-image:none;scrollbar-width:thin}
.st-key-pista > [data-testid=stLayoutWrapper]:has(> .st-key-tk_copia_b){display:none}
}
@media (max-width:640px){
.st-key-ticker{flex-direction:column !important;align-items:stretch !important;gap:.2rem !important}
.st-key-ticker > [data-testid=stElementContainer]:has(.tk-et){flex:0 0 auto;width:100% !important;max-width:none}
.tk-et{flex-direction:row;flex-wrap:wrap;gap:0 .5rem;font-size:.66rem;white-space:normal}
.tk-et .tk-largo{display:none}
.tk-et .tk-corto{display:inline}
.st-key-ticker > [data-testid=stLayoutWrapper]:has(> .st-key-cinta){flex:0 0 auto;width:100%}
.st-key-pista{animation:none}
.st-key-cinta{overflow-x:auto;mask-image:none;scroll-snap-type:x proximity;scrollbar-width:none;
  -webkit-overflow-scrolling:touch}
.st-key-pista > [data-testid=stLayoutWrapper]:has(> .st-key-tk_copia_b){display:none}
[class*=st-key-tka_]{scroll-snap-align:start}
[class*=st-key-tka_] button{min-height:40px}
}
/* v0.8.7 · Drill-down de la distribución PND (Issue #36). */
.st-key-drill_pnd_ctl{flex-wrap:wrap;row-gap:.3rem;margin-top:-.2rem}
.st-key-drill_pnd_ctl [data-testid=stWidgetLabel] p{font-size:.78rem}
.st-key-drill_pnd_ctl [data-baseweb=select] > div{min-height:2.1rem;font-size:.82rem}
.st-key-quitar_barra_pnd button{min-height:2.1rem;padding:.1rem .7rem}
.st-key-drill_pnd{background:#F2F6FD;border:1px solid #CFE0FA;border-radius:10px;padding:.6rem .7rem .5rem;gap:.45rem}
.drill-et{display:flex;flex-wrap:wrap;gap:.1rem .6rem;font-size:.85rem;line-height:1.35}
.st-key-drill_pnd [data-testid=stMarkdownContainer]{margin-bottom:0}
.drill-et span{color:#5A5D63;font-size:.76rem}
.st-key-drill_lista{flex-wrap:wrap;gap:.35rem}
.st-key-drill_lista [data-testid=stElementContainer]{width:auto !important;flex:0 0 auto}
[class*=st-key-dz_pnd_] button{min-height:2rem;padding:.1rem .65rem;border-radius:999px}
[class*=st-key-dz_pnd_] button p{font-size:.8rem;white-space:nowrap;font-variant-numeric:tabular-nums}
@media (max-width:640px){
.st-key-drill_pnd_ctl [data-testid=stElementContainer]:has([data-testid=stSelectbox]){width:100% !important}
[class*=st-key-dz_pnd_] button,.st-key-quitar_barra_pnd button{min-height:40px}
}
/* v0.8.3 · Rail izquierdo compacto (Issue #29): «Elige el solista» pasa a la IZQUIERDA con ~la mitad del ancho anterior
   (245 px → 172–200 px; 187 px en 1440) y un solo panel con «Nodos» (PML) y «Zonas» (PND). El área principal gana el
   ancho. Más aire entre la cabecera fija y el contenido (--aire). Sin position:fixed: nada se superpone a la gráfica. */
:root{--ancho-rail:clamp(172px,13vw,200px);--aire:1.1rem}
.st-key-shell{margin-top:var(--aire)}
.st-key-shell > div > [data-testid=stHorizontalBlock],.st-key-shell > [data-testid=stHorizontalBlock]{gap:1.1rem}
.st-key-shell [data-testid=stColumn]:has(.st-key-atril){flex:0 0 var(--ancho-rail) !important;
  width:var(--ancho-rail) !important;min-width:0;position:sticky;
  top:calc(var(--alto-st) + var(--alto-barra) + var(--aire));align-self:flex-start;
  max-height:calc(100dvh - var(--alto-st) - var(--alto-barra) - var(--aire) - .6rem);overflow-y:auto;
  overscroll-behavior:contain;scrollbar-width:thin}
.st-key-shell [data-testid=stColumn]:not(:has(.st-key-atril)){flex:1 1 0 !important;width:auto !important;min-width:0}
.st-key-atril{padding:.65rem .6rem .5rem;gap:.8rem}
.st-key-atril .atril-et,.st-key-atril .lista-et{padding-bottom:.35rem}
.atril-et{font-weight:700;font-size:.95rem;line-height:1.25}
.st-key-atril [data-testid=stWidgetLabel] p{font-size:.78rem}
.st-key-rail_modo [data-testid=stButtonGroup] > div{flex-wrap:nowrap;width:100%}
.st-key-rail_modo button{flex:1 1 0;min-width:0;padding:.15rem .3rem;min-height:2.1rem}
.st-key-rail_modo button p{font-size:.85rem;font-weight:600}
.st-key-rail_modo button[aria-checked=true]{background:#1C1C1E !important;border-color:#1C1C1E !important}
.st-key-rail_modo button[aria-checked=true] p{color:#FFFFFF !important}
.st-key-nodo_tension [data-testid=stButtonGroup] > div{flex-wrap:nowrap;width:100%}
.st-key-nodo_tension button{flex:1 1 0;min-width:0;padding:.1rem .15rem;min-height:1.9rem}
.st-key-nodo_tension button p{font-size:.74rem}
.st-key-atril [data-testid=stSelectbox] [data-baseweb=select] > div{min-height:2.1rem;font-size:.8rem}
.st-key-atril [data-testid=stExpander] summary{padding:.35rem .55rem}
.st-key-atril [data-testid=stExpander] summary p{font-size:.8rem}
.st-key-atril .lista-et{font-size:.72rem;line-height:1.35;margin:0}
/* Lista de dos líneas: clave o zona arriba (recortada con «…»; el texto completo sigue en la etiqueta accesible y en
   la ayuda al pasar el cursor) y el precio del día abajo. */
[class*=st-key-wl_] button{min-height:0;padding:.3rem .55rem}
[class*=st-key-wl_] button p{white-space:normal;line-height:1.25;font-size:.8rem;text-align:left;min-width:0;width:100%}
[class*=st-key-wl_] button p em{display:block;font-style:normal;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
[class*=st-key-wl_] button p strong{display:block;font-weight:600;font-variant-numeric:tabular-nums;color:#3A3D42}
[class*=st-key-wl_] button[kind=primary] p strong{color:#1C1C1E}
/* La búsqueda es angosta: su lista desplegable se abre con el ancho suficiente para leer clave y nombre completos. */
[data-testid=stSelectboxVirtualDropdown]{min-width:min(22rem,calc(100vw - 2rem))}
[data-testid=stSelectboxVirtualDropdown] [role=listbox],[data-testid=stSelectboxVirtualDropdown] [role=listbox] > [role=presentation],
[data-testid=stSelectboxVirtualDropdown] [role=listbox] > [role=presentation] > [role=presentation]{width:100% !important}
@media (max-width:1024px){
.st-key-shell > div > [data-testid=stHorizontalBlock],.st-key-shell > [data-testid=stHorizontalBlock]{flex-direction:column-reverse;gap:1rem}
.st-key-shell [data-testid=stColumn],.st-key-shell [data-testid=stColumn]:not(:has(.st-key-atril)){width:100% !important;flex:1 1 100% !important}
.st-key-shell [data-testid=stColumn]:has(.st-key-atril){flex:1 1 100% !important;width:100% !important;position:static;
  max-height:none;overflow:visible}
.st-key-atril{padding:.8rem .9rem .6rem}
.chip-cambiar{display:inline-flex}
:root{--aire:.8rem}
}
.st-key-marca [data-testid=stElementContainer]:has(.chip-cambiar){margin-left:auto;width:auto}
@media (max-width:640px){
.estado-barra{display:none}
.st-key-controles [data-testid=stElementContainer]:has(.estado-barra){display:none}
.st-key-barra > [data-testid=stLayoutWrapper]:has(> .st-key-marca),
.st-key-barra > [data-testid=stLayoutWrapper]:has(> .st-key-controles){flex:1 1 100%;max-width:none}
.st-key-barra .logo-pml{width:26px}
.st-key-rangos button{min-width:2.75rem;padding:.1rem .5rem}
.st-key-controles [data-testid=stRadio] label{margin-right:.2rem}
.st-key-marca_texto [data-testid=stCaptionContainer]{display:none}
.st-key-barra .st-key-marca h1{font-size:1.15rem}
.estado-barra span:not(.activo){display:none}
.st-key-controles [data-testid=stPopover] button{min-height:44px}
.st-key-rangos button{min-height:40px}
}
.chip-cambiar{white-space:nowrap}
@media (max-width:400px){
.st-key-controles [data-testid=stPopover] button p{display:none}
.st-key-barra .st-key-marca h1{font-size:1.05rem}
.chip-cambiar{padding:.15rem .6rem;font-size:.8rem}
.st-key-rangos{gap:.3rem}
.st-key-rangos button{min-width:2.4rem;padding:.1rem .35rem}
.st-key-controles{column-gap:.3rem}
}
/* v0.8.2 · Solista compacto: la ficha de indicadores pasa debajo de la gráfica, en rejilla (la gráfica gana ancho y
   las etiquetas no se recortan en la columna central, más angosta por la lista fija). Mismos valores y textos. */
.st-key-tarjeta > div > [data-testid=stHorizontalBlock],.st-key-tarjeta > [data-testid=stHorizontalBlock]{flex-direction:column !important;
  flex-wrap:nowrap !important;gap:.4rem}
.st-key-tarjeta > div > [data-testid=stHorizontalBlock] > [data-testid=stColumn],
.st-key-tarjeta > [data-testid=stHorizontalBlock] > [data-testid=stColumn]{width:100% !important;flex:1 1 100% !important}
.st-key-ficha{border-left:none !important;padding-left:0;border-top:1px solid #E3E5E9;padding-top:.6rem;display:grid;
  grid-template-columns:repeat(auto-fill,minmax(9.5rem,1fr));column-gap:1rem;row-gap:.35rem}
.st-key-ficha > *:has(.rango),.st-key-ficha > *:has(.fila){grid-column:1 / -1}
.st-key-ficha [data-testid=stMetric] > div{flex-direction:column;align-items:flex-start;gap:0}
.st-key-ficha [data-testid=stMetricValue],.st-key-ficha [data-testid=stMetricValue] p{font-size:1.02rem;line-height:1.35}
.st-key-ficha .rango{display:inline-block;width:calc(50% - .8rem);margin:0 .8rem .8rem 0;vertical-align:top}
.st-key-ficha .fila{display:inline-flex;width:calc(25% - .9rem);margin-right:.9rem;vertical-align:top}
@media (max-width:640px){
.st-key-ficha .rango{width:100%;margin-right:0}
.st-key-ficha .fila{width:calc(50% - .6rem);margin-right:.6rem}
}
</style>"""
ASSETS = Path(__file__).resolve().parent / "assets"
NARANJA = "#FFB000"  # v0.6.3: ámbar del logo sax (nombre conservado: es la serie principal en las tres vistas)
AZUL = "#0A84FF"
GRIS = "#8E8E93"
FONDO = "#FFFFFF"  # contorno del punto resaltado, para que se separe de la línea (v0.8.1: fondo de la tarjeta clara)
EJE = "#C9CBD0"     # marcas del eje X
REJILLA = "#E3E5E9"  # rejilla horizontal, tenue sobre la tarjeta clara (v0.8.1: ya no hay panel grafito)
CERO = "#8E8E93"     # v0.6.4: línea de referencia en cero (spread, pérdidas y congestión)
# Fechas de los ejes en español (Vega-Lite usa inglés por defecto: «Thu 29», «November»).
LOCALE_ES = {"time": {
    "dateTime": "%A, %e de %B de %Y, %X", "date": "%d/%m/%Y", "time": "%H:%M:%S", "periods": ["AM", "PM"],
    "days": ["domingo", "lunes", "martes", "miércoles", "jueves", "viernes", "sábado"],
    "shortDays": ["dom", "lun", "mar", "mié", "jue", "vie", "sáb"],
    "months": ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre",
               "octubre", "noviembre", "diciembre"],
    "shortMonths": ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]},
    "number": {"decimal": ".", "thousands": ",", "grouping": [3], "currency": ["$", ""]}}
ETIQUETAS_RANGO = {"Último día": "1D", "Últimos 7 días": "7D", "Mes en curso": "Mes", "Año en curso": "YTD"}
# v0.8.0 · Graphite Trading | Ensemble & Solo.
ALTO_SOLO = 270        # px de la gráfica principal del solista (v0.8.2: compacta; v0.8.0: 380)
ALTO_DISTRIBUCION = 150  # px de las gráficas compactas de ENSEMBLE
ALTO_CONGESTION = 130  # px con título y eje (≈ 90 px de barras) bajo la gráfica del solista (v0.8.0: 150)
MEDIO_PERIODO = {"horaria": pd.Timedelta(minutes=30), "diaria": pd.Timedelta(hours=12),
                 "mensual": pd.Timedelta(days=15)}  # medio periodo: margen del eje de tiempo y ancho de las barras
EJE_Y_ANCHO = 52       # px fijos del eje Y derecho: la línea y las barras comparten el mismo ancho de trazo
TEXTO_GRAFITO, TEXTO_GRAFITO_2 = "#F2F2F7", "#A7AEB8"  # texto de las gráficas sobre el panel grafito
TEXTO_CLARO, TEXTO_CLARO_2 = "#1C1C1E", "#5A5D63"      # texto de las gráficas sobre tarjetas claras
# v0.8.1 · Degradado bajo la línea del solista: ámbar para PML, azul para PND. Sobre claro, más tenue que en grafito.
DEGRADADOS = {c: alt.Gradient(gradient="linear", x1=1, x2=1, y1=0, y2=1, stops=[
    alt.GradientStop(color=f"rgba({rgb},0.26)", offset=0), alt.GradientStop(color=f"rgba({rgb},0)", offset=1)])
    for c, rgb in (("#FFB000", "255,176,0"), ("#0A84FF", "10,132,255"))}
GRAFITO = "#3A4250"    # v0.8.1 · congestión positiva en PND: la línea ya es azul y las barras no deben confundirse
RANKING_N = 5          # filas de «Más caros» y «Más baratos»


def logo():
    """Logo animado del saxofón (mismo diseño que la app del laboratorio); al pasar el mouse crece y brilla."""
    svg = base64.b64encode((ASSETS / "logo_animado.svg").read_bytes()).decode()
    st.markdown(
        f'<img class="logo-pml" alt="PML Explorer: logo del saxofón" src="data:image/svg+xml;base64,{svg}">'
        "<style>.logo-pml {width: 84px; max-width: 22vw; display: block; transition: transform .3s, filter .3s;}"
        ".logo-pml:hover {transform: scale(1.12) rotate(-3deg); filter: drop-shadow(0 0 10px #FFB000);}"
        "@media (prefers-reduced-motion: reduce) {.logo-pml, .logo-pml:hover {transition: none; transform: none;}}</style>",
        unsafe_allow_html=True,
    )


@st.cache_data(max_entries=2, show_spinner=False)
def cargar_paquete(data_dir, version):
    return inspeccionar_paquete(data_dir), catalogo(data_dir), observado(data_dir)


@st.cache_data(max_entries=64, show_spinner=False)
def consultar_estadisticas(nodo, inicio, fin, data_dir, version):
    return estadisticas(nodo, inicio, fin, data_dir)


@st.cache_data(max_entries=32, show_spinner=False)
def consultar_serie(nodo, inicio, fin, resolucion, data_dir, version):
    return serie(nodo, inicio, fin, resolucion, data_dir)


@st.cache_data(max_entries=32, show_spinner=False)
def consultar_resumen(nodo_a, nodo_b, inicio, fin, data_dir, version):
    return resumen(nodo_a, nodo_b, inicio, fin, data_dir)


@st.cache_data(max_entries=32, show_spinner=False)
def consultar_diferencial(nodo_a, nodo_b, inicio, fin, resolucion, data_dir, version):
    return diferencial(nodo_a, nodo_b, inicio, fin, resolucion, data_dir)


@st.cache_data(max_entries=32, show_spinner=False)
def consultar_resumen_componentes(nodo, inicio, fin, data_dir, version):
    return resumen_componentes(nodo, inicio, fin, data_dir)


@st.cache_data(max_entries=32, show_spinner=False)
def consultar_componentes(nodo, inicio, fin, resolucion, data_dir, version):
    return componentes(nodo, inicio, fin, resolucion, data_dir)


@st.cache_data(max_entries=2, show_spinner=False)
def cargar_pnd(pnd_dir, version):
    """v0.7.0 · Límites y zonas del paquete PND. Lanza PndNoDisponible si no cumple el contrato."""
    return pnd_zonas.inspeccionar_pnd(pnd_dir), pnd_zonas.zonas(pnd_dir)


@st.cache_data(max_entries=64, show_spinner=False)
def consultar_estadisticas_pnd(zona, inicio, fin, pnd_dir, version):
    return pnd_zonas.estadisticas_pnd(zona, inicio, fin, pnd_dir)


@st.cache_data(max_entries=32, show_spinner=False)
def consultar_serie_pnd(zona, inicio, fin, resolucion, pnd_dir, version):
    return pnd_zonas.serie_pnd(zona, inicio, fin, resolucion, pnd_dir)


@st.cache_data(max_entries=16, show_spinner=False)
def consultar_ranking_pml(dia, data_dir, version):
    """v0.8.0 · ENSEMBLE: promedio del día de cada nodo (misma fórmula que SOLO), del más caro al más barato."""
    return ens.ranking_pml(dia, data_dir)


@st.cache_data(max_entries=16, show_spinner=False)
def consultar_ranking_pnd(dia, pnd_dir, version):
    """v0.8.0 · ENSEMBLE: promedio del día de cada zona de carga (misma fórmula que SOLO PND)."""
    return ens.ranking_pnd(dia, pnd_dir)


@st.cache_data(max_entries=2, show_spinner=False)
def consultar_ticker(desde, hasta, zonas, pnd_dir, version):
    """v0.8.5 · Cinta PND: dos lecturas pequeñas (D y D−1) con la consulta de ENSEMBLE; se invalida con el paquete."""
    return ticker.fichas({"desde": desde, "hasta": hasta}, pnd_dir, set(zonas))


def mxn(valor):
    """Precio con la misma precisión en indicadores y tablas: dos decimales."""
    return "—" if pd.isna(valor) else f"{valor:,.2f}"


def campos_recuadro(df, resolucion, nodo):
    """Columnas de texto para el recuadro que aparece al pasar el mouse. No tocan los valores.

    Convención de CENACE (hora final): el punto de las 00:00 es la hora 1, de 00:00 a 01:00.
    """
    df = df.copy()
    df["nodo_txt"] = nodo
    if resolucion == "horaria":
        horas = pd.to_datetime(df["periodo"]).dt.hour
        df["fecha_txt"] = pd.to_datetime(df["periodo"]).dt.strftime("%Y-%m-%d")
        df["hora_txt"] = [f"{h + 1} ({h:02d}:00–{h + 1:02d}:00)" for h in horas]
    else:
        df["fecha_txt"] = df["etiqueta"]  # día, o mes con su nota de periodo parcial
    return df


def configurar(grafica_, oscuro=False):
    """Estilo común de las gráficas: fechas en español y texto legible. v0.8.1: todas van sobre tarjetas claras."""
    texto, secundario = (TEXTO_GRAFITO, TEXTO_GRAFITO_2) if oscuro else (TEXTO_CLARO, TEXTO_CLARO_2)
    return (grafica_.configure_view(stroke=None).configure(locale=LOCALE_ES)
            .configure_axis(labelColor=secundario, titleColor=secundario)
            .configure_legend(labelColor=texto, titleColor=secundario)
            .configure_title(color=secundario, fontSize=12, fontWeight="normal", anchor="start"))


def barras_congestion(df, resolucion, etiqueta, dominio, positivo=AZUL):
    """v0.8.0 · Barras de congestión del mismo periodo bajo la gráfica principal de SOLO.

    `df` trae `periodo` y `congestion` ya calculados por la consulta de componentes de la vista (el mismo promedio
    sobre las horas con dato que muestra la vista 3 o la tabla PND); aquí solo se dibujan, con su signo y eje cero.
    """
    df = campos_recuadro(df.dropna(subset=["congestion"]), resolucion, etiqueta)
    # Cada barra ocupa el 80 % de su periodo, centrada en el mismo instante que el punto de la línea.
    medio = MEDIO_PERIODO[resolucion] * 0.8
    df["ini"], df["fin"] = pd.to_datetime(df["periodo"]) - medio, pd.to_datetime(df["periodo"]) + medio
    recuadro = [alt.Tooltip("nodo_txt:N", title="Elemento"), alt.Tooltip("fecha_txt:N", title="Fecha")]
    if resolucion == "horaria":
        recuadro.append(alt.Tooltip("hora_txt:N", title="Hora"))
    recuadro.append(alt.Tooltip("congestion:Q", title="Congestión (MXN/MWh)", format=",.2f"))
    barras = alt.Chart(df).mark_bar(opacity=.9).encode(
        x=alt.X("ini:T", title=None, scale=alt.Scale(domain=dominio),
                axis=alt.Axis(grid=False, domain=False, tickColor=EJE)),
        x2="fin:T", y2=alt.datum(0),
        y=alt.Y("congestion:Q", title=None,
                axis=alt.Axis(orient="right", domain=False, ticks=False, gridColor=REJILLA, tickCount=3,
                              minExtent=EJE_Y_ANCHO, maxExtent=EJE_Y_ANCHO)),
        color=alt.condition("datum.congestion >= 0", alt.value(positivo), alt.value(GRIS)),
        tooltip=recuadro)
    cero = alt.Chart(df).mark_rule(color=CERO, strokeWidth=1).encode(y=alt.datum(0))
    st.altair_chart(configurar((barras + cero).properties(
        background="transparent", height=ALTO_CONGESTION,
        title="Congestión del mismo periodo (MXN/MWh) · "
              + ("azul" if positivo == AZUL else "grafito") + " > 0, gris < 0")), width="stretch")


def grafica(df, y, titulo_y, resolucion, color=None, nodo="", cero=False, titulo_serie=None, congestion=None):
    """Línea con puntos; los periodos parciales se marcan con ▼.

    v0.5.1: al pasar el mouse cerca de la línea se marca el punto más cercano y aparece un recuadro pequeño
    con nodo, valor, fecha y hora (horaria) u horas con dato (diaria y mensual).
    """
    df = campos_recuadro(df, resolucion, nodo)
    recuadro = [alt.Tooltip("nodo_txt:N", title=titulo_serie or ("Nodos" if " − " in nodo else "Nodo")),
                alt.Tooltip("fecha_txt:N", title="Fecha")]
    if resolucion == "horaria":
        recuadro.append(alt.Tooltip("hora_txt:N", title="Hora"))
    recuadro.append(alt.Tooltip(f"{y}:Q", title=titulo_y, format=",.2f"))
    if resolucion != "horaria":
        recuadro.append(alt.Tooltip("horas:Q", title="Horas con dato", format=","))
    # v0.8.0 · Con barras de congestión debajo, las dos gráficas comparten el dominio de tiempo y el ancho del eje Y,
    # para que cada barra quede bajo su punto de la línea.
    medio = MEDIO_PERIODO[resolucion]
    dominio = ([(pd.to_datetime(df["periodo"]).min() - medio).isoformat(),
                (pd.to_datetime(df["periodo"]).max() + medio).isoformat()]
               if congestion is not None and len(df) else alt.Undefined)
    eje_y = alt.Axis(orient="right", domain=False, ticks=False, gridColor=REJILLA, tickCount=5,
                     minExtent=EJE_Y_ANCHO, maxExtent=EJE_Y_ANCHO)
    base = alt.Chart(df).encode(
        x=alt.X("periodo:T", title=None, scale=alt.Scale(domain=dominio),
                axis=alt.Axis(grid=False, domain=False, tickColor=EJE)),
        y=alt.Y(f"{y}:Q", title=None, scale=alt.Scale(zero=False), axis=eje_y),
    )
    # v0.8.0 · Línea ámbar marcada con un degradado debajo (solo presentación; los valores son los mismos).
    # El área baja hasta el borde inferior del trazo (y2 en píxeles): no obliga a la escala a incluir el cero.
    serie = color or NARANJA
    area = base.mark_area(clip=True, line=False, color=DEGRADADOS.get(serie, serie),
                          opacity=1 if serie in DEGRADADOS else .12).encode(
        y=alt.Y(f"{y}:Q", title=None, stack=None, scale=alt.Scale(zero=False), axis=eje_y), y2=alt.value(ALTO_SOLO))
    linea = base.mark_line(color=color or NARANJA, strokeWidth=2.4)
    # v0.6.4 · `cero=True` (spread): línea de referencia en 0 para leer el signo de un vistazo.
    capas = [area] + ([alt.Chart(df).mark_rule(color=CERO, strokeWidth=1, strokeDash=[4, 3]).encode(y=alt.datum(0))]
                      if cero else []) + [linea]
    # Con muchos periodos solo se dibujan los puntos parciales, para no saturar la gráfica.
    puntos = base if len(df) <= 400 else base.transform_filter("datum.parcial")
    if resolucion != "horaria":
        capas.append(puntos.mark_point(size=50, filled=True, color=color or NARANJA).encode(
            shape=alt.Shape("parcial:N", title="Periodo",
                            scale=alt.Scale(domain=[False, True], range=["circle", "triangle-down"]),
                            legend=alt.Legend(labelExpr="datum.value ? 'parcial' : 'completo'", orient="top",
                                              direction="horizontal")),
        ))
    # Punto más cercano al mouse: invisible hasta que se acerca el cursor, y lleva el recuadro.
    cerca = alt.selection_point(on="pointerover", nearest=True, fields=["periodo"], empty=False,
                                clear="pointerout")
    capas.append(base.mark_point(size=70, filled=True, color=color or NARANJA, stroke=FONDO, strokeWidth=1.5)
                 .encode(opacity=alt.condition(cerca, alt.value(1), alt.value(0)), tooltip=recuadro)
                 .add_params(cerca))
    # v0.8.0 · SOLO: la gráfica principal gana alto (protagonista); los datos y las marcas no cambian.
    st.altair_chart(configurar(alt.layer(*capas).properties(background="transparent", height=ALTO_SOLO)),
                    width="stretch")
    if congestion is not None and len(congestion):
        barras_congestion(congestion, resolucion, nodo, dominio, positivo=GRAFITO if serie == AZUL else AZUL)


def avisos_parciales(df, resolucion):
    parciales = df[df["parcial"]]
    if resolucion == "horaria" or parciales.empty:
        return
    lista = "; ".join(parciales["etiqueta"].head(6))
    extra = f" y {len(parciales) - 6} más" if len(parciales) > 6 else ""
    st.caption(f"▼ Periodos parciales (el promedio usa solo las horas con dato del rango elegido): {lista}{extra}.")


def metodologia():
    with st.expander("Metodología y definiciones"):
        st.markdown(f"""
- **Fuente:** CENACE, servicio SW-PML, Mercado del Día en Adelanto (MDA), Sistema Interconectado Nacional (SIN). Unidades: MXN/MWh.
- **Promedio:** promedio **simple** de las horas con dato (cada hora pesa igual; no se pondera por demanda ni volumen). Diario y mensual se calculan con la suma y el número de horas, nunca promediando promedios.
- **Indicadores (Promedio, Mediana, Mínimo, Máximo, Horas con PML < 0):** se calculan siempre sobre **las horas** del rango elegido, aunque la gráfica muestre promedios diarios o mensuales.
- **Convención horaria:** hora 1–24 de CENACE, hora final: la hora 1 es 00:00–01:00 del día de operación. En la gráfica horaria cada punto se dibuja al inicio de su hora. No hay conversión a UTC.
- **Faltantes:** una hora sin dato **no es un precio cero**; no se imputa ni se arrastra. La cobertura es horas con dato ÷ (24 × días del rango).
- **Periodos parciales:** un mes o día que el rango no cubre completo, o que tiene horas sin dato, se marca con ▼ y su promedio usa solo las horas disponibles.
- **Spread (vista 2):** PML_A − PML_B hora por hora, solo en las horas en que los dos nodos tienen dato; después se promedia por día o mes. Fuera de la ventana horaria se usan los días en que ambos nodos tienen las 24 horas (ahí todas las horas coinciden y el cálculo es exacto); un día incompleto en algún nodo se excluye.
- **Componentes (vista 3):** PML = energía + pérdidas + congestión, con sus signos (pérdidas y congestión pueden ser negativas). Todos se promedian sobre las mismas horas que el PML. El **descuadre** es |PML − (energía + pérdidas + congestión)| por hora y viene del redondeo de CENACE; se avisa cuando supera {UMBRAL_DESCUADRE} MXN/MWh.
- **Histórico horario y diario:** mediana y percentiles requieren que todo el rango esté dentro de la ventana horaria (último año). Fuera de ella se usan acumuladores diarios exactos para promedio, extremos, desviación y horas negativas.
- **Rangos rápidos:** se anclan en la última fecha de operación del paquete (igual para todos los nodos). *Último día* = ese día; *Últimos 7 días* = ese día y los 6 anteriores; *Mes en curso* = del día 1 de ese mes hasta ese día, por eso el mes aparece como parcial (▼). Solo cambian «Desde» y «Hasta».
- **Fechas:** “Desde/Hasta” son **fechas de operación** del mercado. “Actualización” es cuándo se generó el paquete público, no cuándo CENACE publicó cada día.
- **Precisión:** precios con dos decimales; la desviación estándar es muestral.
- **Descargar CSV (v0.6.2):** la serie de la gráfica en la resolución elegida, con los mismos valores: fecha (y hora CENACE si es horaria), nodo y precios en MXN/MWh. Coma como separador y punto decimal; una celda vacía no es cero. En la vista 2, PML A y PML B se promedian sobre las mismas horas comunes que el spread.
- **Nombres y ubicación (v0.6.0):** nombre oficial, Región de Control y Zona de carga vienen del [Catálogo de NodosP de CENACE](https://www.cenace.gob.mx/Paginas/SIM/NodosP.aspx), en la versión indicada al pie. CENACE aclara que la versión no es la vigencia de cada nodo: la clasificación corresponde a esa versión y no se aplica hacia atrás. Sirve para **localizar** nodos; no determina el nodo de liquidación de una instalación. El **estado** es la entidad federativa (clave INEGI) donde CENACE ubica cada nodo; se filtra nodo por nodo, porque una zona de carga puede abarcar varios estados, y no indica dónde está una instalación ni su nodo de liquidación. Los nodos de interconexión internacional no tienen región, zona ni estado («sin clasificación verificada»). Región, zona y estado no intervienen en ningún cálculo.

Documento completo: [metodología]({REPO}/docs/methodology.md) · [contrato de datos]({REPO}/docs/data-contract.md).
""")


def metodologia_pnd():
    """v0.7.0 · Metodología de la modalidad PND (decisión D: PEND/pz solo aquí y en los metadatos)."""
    with st.expander("Metodología y definiciones · PND"):
        st.markdown(f"""
- **Qué es:** el **precio de zona de carga (PND)** que publica CENACE para cada zona de carga del SIN en el Mercado del Día en Adelanto (MDA). Es el precio con que se liquida la demanda de la zona, no el de un nodo. Unidades: MXN/MWh.
- **Fuente:** CENACE, servicio SW-PEND (Precios de Energía en Nodos Distribuidos), campo `pz` (y `pz_ene`, `pz_per`, `pz_cng` para energía, pérdidas y congestión). Según el manual técnico de SW-PEND, es el promedio de los PML de los nodos de la zona **ponderado** por su factor de distribución de carga: no es un promedio simple de nodos, por eso la app lo toma tal cual lo publica CENACE y no lo recalcula.
- **Componentes:** PND = energía + pérdidas + congestión, con sus signos. Se revisa que |PND − suma| no supere 0.02 MXN/MWh antes de publicar.
- **Promedio:** promedio **simple** de las horas con dato, igual que en el PML. Diario y mensual se calculan sobre las horas, nunca promediando promedios.
- **Convención horaria:** hora 1–24 de CENACE, hora final (la hora 1 es 00:00–01:00 del día de operación). Sin conversión a UTC.
- **Faltantes:** una hora o un día sin dato **no es un precio cero**; no se imputa ni se arrastra. Si el servicio de CENACE no devolvió un día en una consulta verificada, el paquete lo declara «sin dato disponible» con la fecha y el resultado de esa consulta, y se vuelve a pedir en cada actualización. La cobertura es horas con dato ÷ (24 × días del rango), incluidos esos días.
- **Correcciones:** si CENACE corrige un día ya publicado, el paquete toma la versión nueva y el día queda listado como corregido; el original se conserva en el respaldo del laboratorio.
- **Zonas y regiones:** la lista de zonas viene del paquete; la Región de Control para filtrar viene del [Catálogo de NodosP de CENACE](https://www.cenace.gob.mx/Paginas/SIM/NodosP.aspx) (una zona puede estar en dos regiones). Solo ayuda a encontrar la zona; no interviene en ningún cálculo.
- **PML y PND no se mezclan:** cada modalidad tiene su propio paquete, sus fechas y su CSV.

Documento completo: [metodología]({REPO}/docs/methodology.md) · [contrato de datos]({REPO}/docs/data-contract.md).
""")


def ajustar_fechas_modalidad():
    """Callback del selector de modalidad: acota «Desde» y «Hasta» a las fechas del paquete elegido.

    PML y PND tienen paquetes distintos; un date_input con un valor fuera de sus límites fallaría.
    """
    limites = PND["limites"] if st.session_state.get("modalidad") == "pnd" else PND["limites_pml"]
    for clave in ("desde", "hasta"):
        if clave in st.session_state:
            st.session_state[clave] = min(max(st.session_state[clave], limites["desde"]), limites["hasta"])


def dia_de_consulta(limites):
    """Fecha de operación por defecto: hoy en Ciudad de México, acotada al rango del paquete.

    Solo elige el valor inicial de los selectores; los límites siguen saliendo de metadata.
    """
    hoy = datetime.now(ZONA_MERCADO).date()
    return min(max(hoy, limites["desde"]), limites["hasta"])


def aplicar_rango(opcion, limites):
    """Callback de los botones: Streamlit lo ejecuta antes de volver a dibujar la página.

    v0.8.2 · YTD en resolución horaria serían miles de puntos: pasa a diaria (los indicadores siguen siendo horarios).
    """
    st.session_state["desde"], st.session_state["hasta"] = rango_rapido(opcion, limites)
    if opcion == "Año en curso" and st.session_state.get("resolucion") == "horaria":
        st.session_state["resolucion"] = "diaria"


def fechas_elegidas():
    """v0.8.2 · Fechas y resolución elegidas en la barra superior (sus widgets se dibujan antes que las vistas)."""
    estado = st.session_state
    return estado["desde"], estado["hasta"], estado["resolucion"]


def controles_rango(limites, en_columnas=True):
    """Fechas y resolución, compartidas entre vistas. Por defecto, el día de la consulta en resolución horaria.

    v0.8.0: `en_columnas=False` las apila (panel derecho de ENSEMBLE, angosto). Mismas claves y valores.
    """
    dia = dia_de_consulta(limites)
    # v0.4.1: rangos rápidos. El botón solo escribe «Desde» y «Hasta» en session_state antes del siguiente
    # dibujo; nodo, resolución y cálculos no cambian. El ancla es la última fecha del paquete.
    # El valor inicial va en session_state y no como argumento del widget: así Streamlit no avisa de
    # «valor por defecto y Session State a la vez» cuando un botón de rango rápido cambia las fechas.
    st.session_state.setdefault("desde", dia)
    st.session_state.setdefault("hasta", dia)
    c1, c2, c3 = st.columns(3) if en_columnas else (st.container(), st.container(), st.container())
    inicio = c1.date_input("Desde", min_value=limites["desde"], max_value=limites["hasta"], key="desde")
    fin = c2.date_input("Hasta", min_value=limites["desde"], max_value=limites["hasta"], key="hasta")
    resolucion = c3.radio("Resolución de la gráfica", list(RESOLUCIONES), index=0, key="resolucion", horizontal=True,
                          help="Solo cambia la gráfica. Los indicadores siempre son horarios.")
    return inicio, fin, resolucion


def botones_rango(limites):
    """v0.5: rangos rápidos como pastillas (1D, 7D, Mes; v0.8.2: YTD) en la barra superior; la activa va resaltada."""
    actual = (st.session_state.get("desde"), st.session_state.get("hasta"))
    with st.container(key="rangos", horizontal=True, horizontal_alignment="left", gap="small", width="content"):
        for opcion in RANGOS_RAPIDOS:
            st.button(ETIQUETAS_RANGO[opcion], key=f"rango_{opcion}", on_click=aplicar_rango, args=(opcion, limites),
                      type="primary" if rango_rapido(opcion, limites) == actual else "secondary",
                      help=f"{opcion} (ancla: último día del paquete, {limites['hasta']})")


def leer_url(nodos, limites):
    """v0.5.1 · Una sola vez por sesión y antes de dibujar los filtros: copia el enlace recibido a session_state.

    Los widgets toman su valor de session_state por su clave, así que basta con escribirlo antes de crearlos.
    Lo inválido no se copia: queda anotado en «enlace_avisos» para explicarlo al usuario.
    """
    if "enlace_leido" in st.session_state:
        return
    st.session_state["enlace_leido"] = True
    parametros = {clave: st.query_params.get_all(clave) for clave in st.query_params}
    estado, problemas, faltantes = leer_enlace(parametros, nodos, limites, PND.get("zonas"), PND.get("limites"))
    # v0.8.0 · Un enlace con nodo, zona, vista o modalidad abre SOLO (igual que en v0.7.0); sin ellos, ENSEMBLE.
    st.session_state.setdefault("escena", escena_de_enlace(parametros))
    st.session_state.update(estado)
    st.session_state["enlace_avisos"] = (problemas, faltantes)
    st.session_state["panel_abierto"] = bool(problemas)  # fijo en la sesión: el panel no se cierra solo


def descartar_avisos():
    """Callback del botón «Continuar»: el usuario acepta la configuración que ve en el panel."""
    st.session_state["enlace_avisos"] = ([], [])


def actualizar_url(vista):
    """v0.5.1 · Refleja los filtros actuales en la URL. Se llama después del panel, antes de los avisos de la vista.

    Escribir st.query_params no provoca un rerun, y la URL solo se lee al abrir la sesión: no hay ciclos.
    Si el enlace recibido tenía problemas, la vista se detiene aquí sin cifras (y sin tocar la URL original)
    hasta que el usuario cambie un filtro o pulse «Continuar».
    """
    enlace = construir_enlace({clave: st.session_state.get(clave) for clave in PARAMETROS} | {"vista": vista})
    problemas, faltantes = st.session_state.get("enlace_avisos", ([], []))
    if problemas or faltantes:
        if enlace != st.session_state.setdefault("enlace_inicial", enlace):
            problemas, faltantes = [], []  # el usuario ya cambió un filtro: el aviso cumplió su función
            descartar_avisos()
    if problemas:
        st.error("Este enlace no se puede abrir tal cual:\n\n" + "\n".join(f"- {p}" for p in problemas)
                 + "\n\nNo se muestra ninguna cifra para no presentar un análisis distinto del compartido. "
                 "Corrige los filtros en «Vista y filtros» o continúa con la configuración que se ve ahí.")
        st.button("Continuar con la configuración mostrada", on_click=descartar_avisos)
        st.stop()
    if faltantes:
        st.info(f"El enlace no indicaba: {', '.join(faltantes)}. Se usan los valores predeterminados que ves "
                "en «Vista y filtros».")
    actual = st.query_params.to_dict()
    nuevo = {k: v for k, v in actual.items() if k not in PARAMETROS} | enlace  # conserva parámetros ajenos
    if nuevo != actual:
        st.query_params.from_dict(nuevo)


def descarga_csv(vista_url, tabla, nodos_csv, inicio, fin, resolucion, ayuda=None):
    """v0.6.2 · «Descargar CSV» y el enlace de la consulta, debajo de la tarjeta de cada vista.

    `tabla` sale de los DataFrames que la vista ya dibujó (exportar.tabla_*), así que el archivo trae los
    mismos valores sin consultas nuevas. El CSV se entrega ya armado (bytes): con `data` como función
    Streamlit Cloud respondía «Failed to generate file for download» (v0.6.2, 2026-11-13); armarlo cuesta
    milisegundos y pocos cientos de KB. La descarga no vuelve a ejecutar la página (`on_click="ignore"`):
    pestaña, filtros y URL no cambian.
    Solo se llama cuando la vista ya mostró resultados; una vista sin datos se detiene antes.
    """
    nombre = exportar.nombre_archivo(vista_url, nodos_csv, inicio, fin, resolucion)
    enlace = construir_enlace({clave: st.session_state.get(clave) for clave in PARAMETROS}
                              | {"vista": st.session_state.get("vista", VISTAS_URL["historico"])})
    with st.container(key="descarga", horizontal=True, vertical_alignment="center", gap="small"):
        st.download_button("Descargar CSV", data=exportar.a_csv(tabla), file_name=nombre,
                           mime="text/csv", on_click="ignore", icon=":material/download:", key=f"csv_{vista_url}",
                           help=ayuda or "Los datos de esta gráfica: fecha, hora (si es horaria), nodo y precios en MXN/MWh.")
        with st.popover("Enlace de esta consulta"):
            st.code(URL_APP + "?" + urlencode(enlace), language=None, wrap_lines=True)
            st.caption("Copia el enlace con el botón de la esquina. Abre esta misma vista con estos filtros.")
    st.caption(f"{nombre} · resolución {resolucion}, {len(tabla):,} filas · precios en MXN/MWh · coma como "
               "separador, punto decimal, UTF-8. Un periodo sin dato no tiene fila; una celda vacía no es cero.")


def flecha(cambio):
    return "sube" if cambio > 0 else "baja" if cambio < 0 else "igual"


def barra_rango(etiqueta, minimo, maximo, marca):
    """Barra mínimo–máximo con un punto en `marca` (como el «52 Week Range» de una ficha bursátil)."""
    pos = 50 if maximo == minimo else max(0, min(100, (marca - minimo) / (maximo - minimo) * 100))
    return (f'<div class="rango"><div class="et">{etiqueta}</div><div class="barra"><span style="left:{pos:.1f}%">'
            f'</span></div><div class="ext"><span>{mxn(minimo)}</span><span>{mxn(maximo)}</span></div></div>')


def cabecera(valor_del_dia, dia, limites, texto, porcentaje=True):
    """v0.5 · Número grande del último día con dato y su cambio contra el día anterior.

    `valor_del_dia(fecha)` devuelve el valor de ese día o None si no hay horas con dato. El día anterior puede
    quedar fuera del rango elegido; si no hay dato ese día, no se muestra cambio (nunca se compara contra cero).
    `porcentaje=False` para el spread: un % sobre una base cercana a cero no significa nada.
    """
    valor = valor_del_dia(dia)
    previo = valor_del_dia(dia - timedelta(days=1)) if dia - timedelta(days=1) >= limites["desde"] else None
    cambio_html = ""
    if valor is not None and previo is not None:
        cambio = valor - previo
        pct = f" ({cambio / abs(previo):+.2%})" if porcentaje and previo else ""
        cambio_html = f'<span class="cambio {flecha(cambio)}">{cambio:+,.2f}{pct}</span>'
    st.markdown(
        f'<div class="precio"><span class="valor">{mxn(valor)}</span><span class="unidad">MXN/MWh</span>'
        f'{cambio_html}<span class="fecha">{texto} del {dia} vs. día anterior</span></div>',
        unsafe_allow_html=True)
    return valor


def grafica_series(df, columnas, colores, resolucion, titulo_serie="Serie", nodo=None, cero=False):
    """Varias curvas con el mismo estilo que `grafica` (eje derecho, sin rejilla vertical, fechas en español).

    v0.5.1: el mismo recuadro pequeño al pasar el mouse (punto más cercano de cada curva).
    """
    largo = df.melt(id_vars=["periodo"], value_vars=columnas, var_name="serie", value_name="valor").dropna()
    largo["etiqueta"] = pd.to_datetime(largo["periodo"]).dt.strftime("%Y-%m" if resolucion == "mensual" else "%Y-%m-%d")
    largo = campos_recuadro(largo, resolucion, nodo or "")
    recuadro = ([alt.Tooltip("nodo_txt:N", title="Nodo")] if nodo else []) + [
        alt.Tooltip("serie:N", title=titulo_serie), alt.Tooltip("fecha_txt:N", title="Fecha")]
    if resolucion == "horaria":
        recuadro.append(alt.Tooltip("hora_txt:N", title="Hora"))
    recuadro.append(alt.Tooltip("valor:Q", title="MXN/MWh", format=",.2f"))
    base = alt.Chart(largo).encode(
        x=alt.X("periodo:T", title=None, axis=alt.Axis(grid=False, domain=False, tickColor=EJE)),
        y=alt.Y("valor:Q", title=None, scale=alt.Scale(zero=False),
                axis=alt.Axis(orient="right", domain=False, ticks=False, gridColor=REJILLA, tickCount=5)),
        color=alt.Color("serie:N", title=None, sort=columnas, scale=alt.Scale(domain=columnas, range=colores),
                        legend=alt.Legend(orient="top", direction="horizontal", title=None)),
        # v0.6.4 · No depender solo del color: la segunda curva va punteada (la leyenda muestra color y trazo).
        strokeDash=alt.StrokeDash("serie:N", title=None, sort=columnas,
                                  scale=alt.Scale(domain=columnas, range=[[1, 0], [6, 3], [2, 2]][:len(columnas)]),
                                  legend=alt.Legend(orient="top", direction="horizontal", title=None)),
    )
    cerca = alt.selection_point(on="pointerover", nearest=True, fields=["periodo", "serie"], empty=False,
                                clear="pointerout")
    puntos = (base.mark_point(size=70, filled=True, stroke=FONDO, strokeWidth=1.5)
              .encode(opacity=alt.condition(cerca, alt.value(1), alt.value(0)), tooltip=recuadro).add_params(cerca))
    capas = ([alt.Chart(largo).mark_rule(color=CERO, strokeWidth=1, strokeDash=[4, 3]).encode(y=alt.datum(0))]
             if cero else []) + [base.mark_line(strokeWidth=1.6), puntos]
    st.altair_chart(configurar(alt.layer(*capas).properties(background="transparent")), width="stretch")


def fila(etiqueta, valor):
    return f'<div class="fila"><span>{etiqueta}</span><span>{valor}</span></div>'


@st.cache_data(max_entries=2, show_spinner=False)
def cargar_ubicacion(nodos, firma):
    """v0.6.0 · Catálogo de referencia unido a la lista de nodos (left join: no se pierde ninguno).

    `firma` (tamaño y fecha del archivo) solo sirve para que la caché se renueve si cambia el catálogo.
    Devuelve {} si el catálogo falta o no pasa su validación: la app sigue funcionando solo con claves.
    """
    try:
        df, manifiesto = cat_nodos.cargar()
    except (cat_nodos.CatalogoInvalido, OSError, ValueError):
        return {}
    union = cat_nodos.unir(nodos, df)
    return {"union": union, "nombres": dict(zip(union["nodo"], union["nombre"])), "manifiesto": manifiesto}


def firma_catalogo():
    ruta = cat_nodos.REFERENCIA_DIR / cat_nodos.ARCHIVO
    return f"{ruta.stat().st_size}:{ruta.stat().st_mtime_ns}" if ruta.is_file() else ""


def limpiar_ubicacion(key):
    """Callback de «Limpiar ubicación»: vuelve Región, Estado y Zona a «Todas» sin tocar el nodo elegido."""
    for filtro in ("region", "estado", "zona"):
        st.session_state[f"{key}_{filtro}"] = TODAS


def _elegir(etiqueta, opciones, clave):
    """Selectbox de un filtro; si su valor anterior ya no existe con los otros filtros, vuelve a «Todas»."""
    opciones = [TODAS] + opciones
    if st.session_state.get(clave, TODAS) not in opciones:
        st.session_state[clave] = TODAS
    valor = st.selectbox(etiqueta, opciones, key=clave)
    return None if valor == TODAS else valor


def filtros_ubicacion(key, nodos, en_columnas):
    """v0.6.0 · Región de Control, Estado y Zona de carga (catálogo CENACE) antes del selector de nodo.

    Solo acotan la lista de opciones. Nunca cambian el nodo elegido: si queda fuera del filtro se
    conserva al inicio de la lista con un aviso (decisión aprobada 2026-11-12). No van en la URL.
    El estado es un filtro paralelo (fase 2, aprobado 2026-11-12): se aplica nodo por nodo, porque
    una zona de carga puede abarcar varios estados.
    """
    union = UBICACION["union"]
    c1, c2, c3 = st.columns(3) if en_columnas else (st.container(), st.container(), st.container())
    with c1:
        region = _elegir("Región de Control", cat_nodos.regiones(union), f"{key}_region")
    with c2:
        estado = _elegir("Estado", cat_nodos.estados(union, region), f"{key}_estado")
    with c3:
        zona = _elegir("Zona de carga", cat_nodos.zonas(union, region, estado), f"{key}_zona")
    if region is None and estado is None and zona is None:
        return nodos
    filtrados = cat_nodos.filtrar(union, region, zona, estado)
    actual = st.session_state[key]
    if actual not in filtrados:
        st.caption(f"{actual} está fuera de este filtro; se conserva hasta que elijas otro nodo.")
        filtrados = [actual] + filtrados
    st.button("Limpiar ubicación", key=f"{key}_limpiar", on_click=limpiar_ubicacion, args=(key,))
    return filtrados


def ubicacion_de(nodo):
    """Texto bajo el selector: región, zona y estado del nodo, o «sin clasificación verificada»."""
    fila = UBICACION["union"].set_index("nodo").loc[nodo]
    if not fila["clasificado"]:
        return f"{nodo}: {cat_nodos.SIN_CLASIFICACION.lower()} en el catálogo CENACE; disponible por su clave."
    texto = f"Región {fila['region_control'].title()} · Zona de carga {fila['zona_carga'].title()}"
    return texto + (f" · {fila['estado'].title()}" if isinstance(fila["estado"], str) else "")


def selector_nodo(nodos, etiqueta, key, defecto, en_columnas=True, al_cambiar=None):
    """Selector de NodoP: búsqueda directa por clave o nombre y, si hay catálogo, filtros de ubicación.

    El valor del widget es siempre la clave (la URL y los cálculos no cambian); el nombre solo se muestra.
    """
    # v0.5.1: el valor inicial va en session_state, como las fechas, porque un enlace compartido puede haberlo
    # escrito antes; con `index=` Streamlit avisaría de «valor por defecto y Session State a la vez».
    st.session_state.setdefault(key, defecto if defecto in nodos else nodos[0])
    if not UBICACION:
        return st.selectbox(etiqueta, nodos, key=key, placeholder="Clave, p. ej. 06ESC", help=AYUDA_SOLO_CLAVE,
                            on_change=al_cambiar)
    opciones = filtros_ubicacion(key, nodos, en_columnas)
    nombres = UBICACION["nombres"]
    nodo = st.selectbox(etiqueta, opciones, key=key, format_func=lambda n: cat_nodos.etiqueta(n, nombres),
                        placeholder="Clave o nombre, p. ej. 06ESC", help=AYUDA_NODO, on_change=al_cambiar)
    st.caption(ubicacion_de(nodo))
    return nodo


def congestion_pml(nodo, inicio, fin, resolucion, limites, version):
    """v0.8.0 · Congestión del nodo por periodo para las barras de SOLO: la misma consulta de la vista 3 (en caché).

    Sin componentes en el paquete (esquema v1) o si la consulta falla, no hay barras; la vista sigue igual.
    """
    if not limites.get("componentes"):
        return None
    try:
        comp = consultar_componentes(nodo, inicio, fin, resolucion, str(DATA_DIR), version)
    except (DatosNoDisponibles, duckdb.Error):
        return None
    return marcar_periodos(comp, inicio, fin, resolucion)[["periodo", "etiqueta", "congestion"]]


def vista_1(limites, nodos, fechas_nodo, version, panel):
    """Vista 1: PML histórico de un nodo."""
    with panel:
        st.caption(SIN_RESULTADOS)  # encima: la lista «No results» de Streamlit taparía un texto inferior
        nodo = selector_nodo(nodos, "Nodo · clave o nombre", "nodo", "01AAN-85")
        inicio, fin, resolucion = fechas_elegidas()  # v0.8.2: los selectores van en la barra superior
        primera, ultima = fechas_nodo.get(nodo, (None, None))
        if primera:
            st.caption(f"{nodo} tiene datos del {primera} al {ultima}.")
    actualizar_url(st.session_state["vista"])
    solista_pml(nodo)

    if inicio > fin:
        st.error("La fecha 'Desde' debe ser anterior a 'Hasta'.")
        st.stop()

    horario_completo = cobertura_horaria(inicio, fin)
    if not horario_completo and resolucion == "horaria":
        st.warning(f"La resolución horaria requiere que todo el rango esté entre {limites['horario_desde']} "
                   f"y {limites['horario_hasta']}. Ajusta las fechas o elige diaria o mensual.")
        st.stop()

    try:
        e = consultar_estadisticas(nodo, inicio, fin, str(DATA_DIR), version).iloc[0]
        df = consultar_serie(nodo, inicio, fin, resolucion, str(DATA_DIR), version)
    except (DatosNoDisponibles, duckdb.Error):
        st.error("No se puede consultar el rango con el paquete público recibido. Es necesario revisar sus particiones y esquema.")
        st.stop()

    if e["horas_con_dato"] == 0:
        detalle = (f" {nodo} tiene datos del {primera} al {ultima}; ninguna de esas fechas cae en el rango elegido."
                   if primera else "")
        st.warning(f"Sin observaciones para {nodo} entre {inicio} y {fin}.{detalle} "
                   "No se muestra ninguna cifra: la ausencia de datos no equivale a precio cero.")
        st.stop()

    st.subheader(f"{nodo}: {inicio} a {fin}")
    con_dato, del_rango = int(e["horas_con_dato"]), int(e["horas_del_rango"])
    desde_obs, hasta_obs = e["primera_fecha"].date(), e["ultima_fecha"].date()

    # v0.5 · Cabecera tipo ficha: el «precio» es el PML promedio del último día con dato del rango.
    def pml_del_dia(d):
        x = consultar_estadisticas(nodo, d, d, str(DATA_DIR), version).iloc[0]
        return None if x["horas_con_dato"] == 0 else x["promedio"]
    cabecera(pml_del_dia, hasta_obs, limites, "PML promedio")
    dia = consultar_estadisticas(nodo, hasta_obs, hasta_obs, str(DATA_DIR), version).iloc[0]
    st.markdown(f"MDA · SIN · CENACE | **Cobertura:** {e['cobertura_pct']}% ({con_dato:,} de {del_rango:,} horas "
                f"con dato) | **Rango con observaciones:** {desde_obs} a {hasta_obs}")
    if e["cobertura_pct"] < COBERTURA_ESCASA:
        motivo = (f" El nodo tiene datos desde {primera}." if primera and primera > inicio else "")
        st.warning(f"Cobertura escasa: los indicadores describen solo {con_dato:,} horas, entre {desde_obs} y "
                   f"{hasta_obs}, no todo el rango elegido.{motivo} Las horas sin dato no se tratan como cero.")
    elif e["cobertura_pct"] < 100:
        st.caption("Hay horas sin dato en el rango; los indicadores usan solo las horas con dato.")

    df = marcar_periodos(df, inicio, fin, resolucion)
    titulo = {"horaria": "PML horario", "diaria": "PML promedio diario",
              "mensual": "PML promedio mensual"}[resolucion]
    with st.container(key="tarjeta"):
        izq, der = st.columns([3.2, 1], gap="large")
        with izq:
            st.markdown(f"**{titulo} (MXN/MWh)**")
            grafica(df, "pml_promedio", "PML (MXN/MWh)", resolucion, nodo=nodo,
                    congestion=congestion_pml(nodo, inicio, fin, resolucion, limites, version))
        with der, st.container(key="ficha"):
            st.markdown(barra_rango("Rango horario del periodo", e["minimo"], e["maximo"], e["promedio"])
                        + (barra_rango(f"Rango del {hasta_obs}", dia["minimo"], dia["maximo"], dia["promedio"])
                           if dia["horas_con_dato"] else ""), unsafe_allow_html=True)
            st.metric("Promedio horario", mxn(e["promedio"]), help="Promedio simple de las horas con dato.")
            st.metric("Mediana horaria", mxn(e["mediana"]) if horario_completo else "—",
                      help=None if horario_completo else
                      f"Requiere datos horarios: disponible solo si todo el rango está entre "
                      f"{limites['horario_desde']} y {limites['horario_hasta']}.")
            st.metric("Mínimo horario", mxn(e["minimo"]), help="Menor PML de una hora en el rango.")
            st.metric("Máximo horario", mxn(e["maximo"]), help="Mayor PML de una hora en el rango.")
            st.metric("Horas con PML < 0", f"{int(e['horas_negativas']):,}")
            st.markdown(fila("Desv. estándar", mxn(e["desv_std"]))
                        + fila("Percentil 10", mxn(e["p10"]) if horario_completo else "—")
                        + fila("Percentil 90", mxn(e["p90"]) if horario_completo else "—")
                        + fila("Cobertura", f"{e['cobertura_pct']}%"), unsafe_allow_html=True)
    descarga_csv("historico", exportar.tabla_historico(df, nodo, resolucion), [nodo], inicio, fin, resolucion)
    st.caption(f"Indicadores calculados sobre las {con_dato:,} horas con dato, en MXN/MWh"
               + ("." if resolucion == "horaria" else f", aunque la gráfica sea {resolucion}."))
    if not horario_completo:
        st.caption("— Mediana, P10 y P90 requieren datos horarios: el rango excede la ventana horaria "
                   f"({limites['horario_desde']} a {limites['horario_hasta']}). No se estiman.")
    avisos_parciales(df, resolucion)

    with st.expander("Todas las estadísticas"):
        filas = [
            ("Horas con dato", f"{con_dato:,}", "h"),
            ("Horas del rango (24 × días)", f"{del_rango:,}", "h"),
            ("Cobertura", f"{e['cobertura_pct']}", "%"),
            ("Primera fecha con dato", str(desde_obs), ""),
            ("Última fecha con dato", str(hasta_obs), ""),
            ("Promedio horario", mxn(e["promedio"]), "MXN/MWh"),
            ("Desviación estándar muestral", mxn(e["desv_std"]), "MXN/MWh"),
            ("Mínimo horario", mxn(e["minimo"]), "MXN/MWh"),
            ("Percentil 10 horario", mxn(e["p10"]) if horario_completo else "Requiere datos horarios", "MXN/MWh"),
            ("Mediana horaria", mxn(e["mediana"]) if horario_completo else "Requiere datos horarios", "MXN/MWh"),
            ("Percentil 90 horario", mxn(e["p90"]) if horario_completo else "Requiere datos horarios", "MXN/MWh"),
            ("Máximo horario", mxn(e["maximo"]), "MXN/MWh"),
            ("Horas con PML < 0", f"{int(e['horas_negativas']):,}", "h"),
        ]
        st.dataframe(pd.DataFrame(filas, columns=["Indicador", "Valor", "Unidad"]),
                     hide_index=True, width="stretch")
        tabla = df[["etiqueta", "pml_promedio", "horas", "horas_posibles"]].rename(columns={
            "etiqueta": "Periodo", "pml_promedio": "PML promedio (MXN/MWh)",
            "horas": "Horas con dato", "horas_posibles": "Horas posibles en el rango"})
        st.dataframe(tabla, hide_index=True, width="stretch",
                     column_config={"PML promedio (MXN/MWh)": st.column_config.NumberColumn(format="%.2f")})


def vista_2(limites, nodos, fechas_nodo, version, panel):
    """Vista 2: spread A − B, solo en las horas en que los dos nodos tienen dato."""
    with panel:
        defecto_b = "01AGU-230" if "01AGU-230" in nodos else nodos[min(1, len(nodos) - 1)]
        st.caption(SIN_RESULTADOS)
        ca, cb = st.columns(2)
        with ca:
            nodo_a = selector_nodo(nodos, "Nodo A · clave o nombre", "nodo_a", "01AAN-85", en_columnas=False)
        with cb:
            nodo_b = selector_nodo(nodos, "Nodo B · clave o nombre", "nodo_b", defecto_b, en_columnas=False)
        inicio, fin, resolucion = fechas_elegidas()  # v0.8.2: los selectores van en la barra superior
        for n in (nodo_a, nodo_b):
            if n in fechas_nodo:
                st.caption(f"{n} tiene datos del {fechas_nodo[n][0]} al {fechas_nodo[n][1]}.")
    actualizar_url(st.session_state["vista"])
    solista_pml(nodo_a, nodo_b)

    st.markdown("**Spread = PML_A − PML_B** (MXN/MWh). Positivo: A más caro que B. "
                "Solo se comparan las horas en que los dos nodos tienen dato; después se agrega por día o mes.")
    if nodo_a == nodo_b:
        st.error("Elige dos nodos distintos.")
        st.stop()
    if inicio > fin:
        st.error("La fecha 'Desde' debe ser anterior a 'Hasta'.")
        st.stop()
    horario_completo = cobertura_horaria(inicio, fin)
    if not horario_completo and resolucion == "horaria":
        st.warning(f"La resolución horaria requiere que todo el rango esté entre {limites['horario_desde']} "
                   f"y {limites['horario_hasta']}. Ajusta las fechas o elige diaria o mensual.")
        st.stop()

    try:
        r = consultar_resumen(nodo_a, nodo_b, inicio, fin, str(DATA_DIR), version).iloc[0]
        d = consultar_diferencial(nodo_a, nodo_b, inicio, fin, resolucion, str(DATA_DIR), version)
        a = consultar_serie(nodo_a, inicio, fin, resolucion, str(DATA_DIR), version)
        b = consultar_serie(nodo_b, inicio, fin, resolucion, str(DATA_DIR), version)
    except (DatosNoDisponibles, duckdb.Error):
        st.error("No se puede consultar el rango con el paquete público recibido. Es necesario revisar sus particiones y esquema.")
        st.stop()

    if r["horas_coincidentes"] == 0:
        fechas = "; ".join(f"{n}: {fechas_nodo[n][0]} a {fechas_nodo[n][1]}" for n in (nodo_a, nodo_b) if n in fechas_nodo)
        st.warning(f"{nodo_a} y {nodo_b} no tienen horas con dato en común entre {inicio} y {fin}. "
                   f"Datos observados: {fechas}. No se calcula spread: la ausencia de datos no equivale a precio cero.")
        st.stop()

    st.subheader(f"{nodo_a} − {nodo_b}: {inicio} a {fin}")
    comunes, del_rango = int(r["horas_coincidentes"]), int(r["horas_del_rango"])
    desde_obs, hasta_obs = r["primera_fecha"].date(), r["ultima_fecha"].date()

    # v0.5 · Cabecera: spread promedio del último día común, cambio en MXN/MWh (sin %).
    def spread_del_dia(dia):
        x = consultar_resumen(nodo_a, nodo_b, dia, dia, str(DATA_DIR), version).iloc[0]
        return None if x["horas_coincidentes"] == 0 else x["promedio"]
    cabecera(spread_del_dia, hasta_obs, limites, "Spread A − B promedio", porcentaje=False)
    # v0.6.4 · Quién es más caro, en palabras: solo lee el signo del spread promedio ya calculado.
    if pd.notna(r["promedio"]) and r["promedio"] != 0:
        caro, barato = (nodo_a, nodo_b) if r["promedio"] > 0 else (nodo_b, nodo_a)
        st.markdown(f'<div class="linea-meta">En promedio del periodo, <b>{caro}</b> fue más caro que {barato} por '
                    f'<b>{mxn(abs(r["promedio"]))} MXN/MWh</b>.</div>', unsafe_allow_html=True)
    if UBICACION:
        nombres = UBICACION["nombres"]
        st.caption(f"A: {cat_nodos.etiqueta(nodo_a, nombres)} · B: {cat_nodos.etiqueta(nodo_b, nombres)}")
    st.markdown(f"Positivo: {nodo_a} más caro que {nodo_b} | **Cobertura común:** {r['cobertura_pct']}% ({comunes:,} de "
                f"{del_rango:,} horas con dato en los dos nodos) | **Rango común con observaciones:** {desde_obs} a {hasta_obs}")
    if r["cobertura_pct"] < COBERTURA_ESCASA:
        st.warning(f"Cobertura común escasa: el spread describe solo {comunes:,} horas, entre {desde_obs} y {hasta_obs}. "
                   "Las horas en que falta alguno de los dos nodos se excluyen, no se imputan.")
    if r["dias_no_comparables"]:
        st.warning(f"{int(r['dias_no_comparables']):,} días con horas incompletas en algún nodo se excluyeron: "
                   "fuera de la ventana horaria no se puede saber qué horas coinciden.")

    curvas = pd.merge(a[["periodo", "pml_promedio"]].rename(columns={"pml_promedio": nodo_a}),
                      b[["periodo", "pml_promedio"]].rename(columns={"pml_promedio": nodo_b}),
                      on="periodo", how="outer")
    d = marcar_periodos(d, inicio, fin, resolucion)
    with st.container(key="tarjeta"):
        izq, der = st.columns([3.2, 1], gap="large")
        with izq:
            st.markdown("**Spread A − B (MXN/MWh)** · solo horas coincidentes")
            grafica(d, "dif_promedio", "Spread A − B (MXN/MWh)", resolucion, nodo=f"{nodo_a} − {nodo_b}", cero=True)
        with der, st.container(key="ficha"):
            if pd.notna(r["minimo"]) and pd.notna(r["maximo"]):
                st.markdown(barra_rango("Rango horario del spread", r["minimo"], r["maximo"], r["promedio"]),
                            unsafe_allow_html=True)
            st.metric("Spread promedio", mxn(r["promedio"]),
                      help="Promedio horario simple de PML_A − PML_B en las horas coincidentes.")
            st.metric("Mediana horaria", mxn(r["mediana"]))
            st.metric("Mínimo horario", mxn(r["minimo"]))
            st.metric("Máximo horario", mxn(r["maximo"]))
            st.metric("Horas con A más caro", "—" if pd.isna(r["pct_a_mas_caro"]) else f"{r['pct_a_mas_caro']}%")
            st.markdown(fila("Horas coincidentes", f"{comunes:,}") + fila("Cobertura común", f"{r['cobertura_pct']}%")
                        + fila("Días excluidos", f"{int(r['dias_no_comparables'] or 0):,}"), unsafe_allow_html=True)
    # v0.6.4 · Las curvas de cada nodo pasan a una segunda tarjeta, debajo: en móvil ya no compiten con el spread
    # por la primera pantalla y la ficha del spread queda justo después de su gráfica.
    with st.container(key="tarjeta_curvas"):
        st.markdown("**PML de cada nodo (MXN/MWh)** · A continua, B punteada · cada curva con todas sus horas con dato")
        grafica_series(curvas, [nodo_a, nodo_b], [NARANJA, AZUL], resolucion, titulo_serie="Nodo")
    descarga_csv("comparacion", exportar.tabla_spread(d, nodo_a, nodo_b, resolucion), [nodo_a, nodo_b], inicio, fin,
                 resolucion)
    if not horario_completo:
        st.caption("Fuera de la ventana horaria el spread se calcula con los días en que ambos nodos tienen las 24 horas. "
                   f"Mediana, mínimo, máximo y % de horas con A más caro requieren el rango entre "
                   f"{limites['horario_desde']} y {limites['horario_hasta']}.")
    avisos_parciales(d, resolucion)

    with st.expander("Tabla del spread"):
        tabla = d[["etiqueta", "dif_promedio", "horas", "horas_posibles"]].rename(columns={
            "etiqueta": "Periodo", "dif_promedio": "Spread A − B (MXN/MWh)",
            "horas": "Horas coincidentes", "horas_posibles": "Horas posibles en el rango"})
        st.dataframe(tabla, hide_index=True, width="stretch",
                     column_config={"Spread A − B (MXN/MWh)": st.column_config.NumberColumn(format="%.2f")})


def vista_3(limites, nodos, fechas_nodo, version, panel):
    """Vista 3: PML descompuesto en energía, pérdidas y congestión, con su signo."""
    with panel:
        st.caption(SIN_RESULTADOS)  # encima: la lista «No results» de Streamlit taparía un texto inferior
        nodo = selector_nodo(nodos, "Nodo · clave o nombre", "nodo", "01AAN-85")
        inicio, fin, resolucion = fechas_elegidas()  # v0.8.2: los selectores van en la barra superior
        primera, ultima = fechas_nodo.get(nodo, (None, None))
        if primera:
            st.caption(f"{nodo} tiene datos del {primera} al {ultima}.")
    actualizar_url(st.session_state["vista"])
    solista_pml(nodo)

    st.markdown("**PML = energía + pérdidas + congestión** (MXN/MWh). La energía es igual en todos los nodos a la "
                "misma hora; pérdidas y congestión son lo propio del nodo y pueden ser negativas.")
    if not limites.get("componentes"):
        st.info("Los componentes del PML todavía no están en el paquete público. Esta vista se activa sola "
                "cuando el pipeline publique la versión 2 de los datos.")
        st.stop()
    if inicio > fin:
        st.error("La fecha 'Desde' debe ser anterior a 'Hasta'.")
        st.stop()
    horario_completo = cobertura_horaria(inicio, fin)
    if not horario_completo and resolucion == "horaria":
        st.warning(f"La resolución horaria requiere que todo el rango esté entre {limites['horario_desde']} "
                   f"y {limites['horario_hasta']}. Ajusta las fechas o elige diaria o mensual.")
        st.stop()

    try:
        r = consultar_resumen_componentes(nodo, inicio, fin, str(DATA_DIR), version).iloc[0]
        df = consultar_componentes(nodo, inicio, fin, resolucion, str(DATA_DIR), version)
    except (DatosNoDisponibles, duckdb.Error):
        st.error("No se puede consultar el rango con el paquete público recibido. Es necesario revisar sus particiones y esquema.")
        st.stop()

    if r["horas_con_dato"] == 0:
        detalle = f" {nodo} tiene datos del {primera} al {ultima}." if primera else ""
        st.warning(f"Sin observaciones para {nodo} entre {inicio} y {fin}.{detalle} "
                   "No se muestra ninguna cifra: la ausencia de datos no equivale a precio cero.")
        st.stop()

    st.subheader(f"{nodo}: componentes del PML, {inicio} a {fin}")
    con_dato = int(r["horas_con_dato"])
    hasta_obs = r["ultima_fecha"].date()

    # v0.5 · Cabecera: PML promedio del último día con dato, igual que en la vista 1.
    def pml_del_dia(dia):
        x = consultar_resumen_componentes(nodo, dia, dia, str(DATA_DIR), version).iloc[0]
        return None if x["horas_con_dato"] == 0 else x["pml"]
    cabecera(pml_del_dia, hasta_obs, limites, "PML promedio")
    st.markdown(f"MDA · SIN · CENACE | **Cobertura:** {r['cobertura_pct']}% ({con_dato:,} de "
                f"{int(r['horas_del_rango']):,} horas con dato) | **Rango con observaciones:** "
                f"{r['primera_fecha'].date()} a {hasta_obs}")
    if r["cobertura_pct"] < COBERTURA_ESCASA:
        st.warning(f"Cobertura escasa: los promedios describen solo {con_dato:,} horas. Las horas sin dato no se tratan como cero.")
    if r["horas_descuadre"] > 0:
        st.warning(f"{int(r['horas_descuadre']):,} horas con descuadre mayor a {UMBRAL_DESCUADRE} MXN/MWh.")

    df = marcar_periodos(df, inicio, fin, resolucion)
    nombres = {"energia": "Energía", "perdidas": "Pérdidas", "congestion": "Congestión"}
    colores = [NARANJA, AZUL, GRIS]
    largo = df.melt(id_vars=["periodo", "etiqueta"], value_vars=list(nombres), var_name="componente", value_name="valor")
    largo["componente"] = largo["componente"].map(nombres)
    with st.container(key="tarjeta"):
        izq, der = st.columns([3.2, 1], gap="large")
        with izq:
            st.markdown("**Componentes del PML (barras apiladas, MXN/MWh)** · los negativos quedan debajo del cero")
            st.altair_chart(configurar((alt.Chart(largo).mark_bar().encode(
                x=alt.X("periodo:T", title=None, axis=alt.Axis(grid=False, domain=False, tickColor=EJE)),
                y=alt.Y("valor:Q", title=None, stack="zero",
                        axis=alt.Axis(orient="right", domain=False, ticks=False, gridColor=REJILLA, tickCount=5)),
                color=alt.Color("componente:N", title=None, sort=list(nombres.values()),
                                scale=alt.Scale(domain=list(nombres.values()), range=colores),
                                legend=alt.Legend(orient="top", direction="horizontal", title=None)),
                tooltip=[alt.Tooltip("etiqueta:N", title="Periodo"), alt.Tooltip("componente:N", title="Componente"),
                         alt.Tooltip("valor:Q", title="MXN/MWh", format=",.2f")])
                + alt.Chart(largo).mark_rule(color=CERO, strokeWidth=1).encode(y=alt.datum(0)))
                .properties(background="transparent")),
                width="stretch")
            st.markdown("**Pérdidas y congestión (MXN/MWh)** · la parte propia del nodo, a su escala")
            grafica_series(df.rename(columns={"perdidas": "Pérdidas", "congestion": "Congestión"}),
                           ["Pérdidas", "Congestión"], colores[1:], resolucion, titulo_serie="Componente", nodo=nodo,
                           cero=True)
        with der, st.container(key="ficha"):
            st.metric("PML promedio", mxn(r["pml"]))
            st.metric("Energía", mxn(r["energia"]))
            st.metric("Pérdidas", mxn(r["perdidas"]))
            st.metric("Congestión", mxn(r["congestion"]))
            st.markdown(fila("Cobertura", f"{r['cobertura_pct']}%"), unsafe_allow_html=True)
            # v0.6.4 · Detalle técnico plegado: el resumen principal es PML + sus tres componentes. El aviso de
            # descuadre sobre el umbral sigue arriba, fuera de este bloque.
            with st.expander("Detalle técnico"):
                st.metric("Horas con congestión > 0", f"{int(r['horas_congestion_positiva']):,}")
                st.metric("Horas con congestión < 0", f"{int(r['horas_congestion_negativa']):,}")
                st.metric("Descuadre máximo", f"{r['descuadre_max']:,.4f}",
                          help="Máximo de |PML − (energía + pérdidas + congestión)| en una hora. Viene del redondeo de CENACE.")
    descarga_csv("componentes", exportar.tabla_componentes(df, nodo, resolucion), [nodo], inicio, fin, resolucion)
    st.caption(f"Promedios horarios simples sobre las mismas {con_dato:,} horas para el PML y cada componente."
               + ("" if r["horas_descuadre"] > 0 else f" Ninguna hora con descuadre mayor a {UMBRAL_DESCUADRE} MXN/MWh."))
    avisos_parciales(df, resolucion)

    with st.expander("Tabla de componentes y descuadre"):
        tabla = df[["etiqueta", "pml", "energia", "perdidas", "congestion", "descuadre", "horas"]].rename(columns={
            "etiqueta": "Periodo", "pml": "PML", "energia": "Energía", "perdidas": "Pérdidas",
            "congestion": "Congestión", "descuadre": "Descuadre promedio", "horas": "Horas con dato"})
        formato = {c: st.column_config.NumberColumn(format="%.2f") for c in ("PML", "Energía", "Pérdidas", "Congestión")}
        formato["Descuadre promedio"] = st.column_config.NumberColumn(format="%.4f")
        st.dataframe(tabla, hide_index=True, width="stretch", column_config=formato)


def selector_zona(zonas, al_cambiar=None):
    """v0.7.0 · Zona de carga con filtro opcional de Región de Control (decisión E: sin filtro de estado).

    Igual que con los nodos, el filtro solo acota la lista; nunca cambia la zona elegida.
    """
    st.session_state.setdefault("zona", ZONA_DEFECTO if ZONA_DEFECTO in zonas else zonas[0])
    opciones = zonas
    if PND["regiones"]:
        c1, c2 = st.columns([1, 2])
        with c1:
            region = _elegir("Región de Control", sorted(PND["regiones"]), "zona_region")
        if region is not None:
            opciones = [z for z in PND["regiones"][region] if z in zonas]
            if st.session_state["zona"] not in opciones:
                st.caption(f"{st.session_state['zona']} está fuera de esta región; se conserva hasta que elijas otra zona.")
                opciones = [st.session_state["zona"]] + opciones
        destino = c2
    else:
        destino = st.container()
    with destino:
        zona = st.selectbox("Zona de carga", opciones, key="zona", format_func=str.title, on_change=al_cambiar,
                            help="Zona de carga del SIN según CENACE. El PND es el precio de la zona, no de un nodo.")
    regiones = [r for r, zs in PND["regiones"].items() if zona in zs]
    if regiones:
        st.caption(f"Región de Control: {', '.join(r.title() for r in sorted(regiones))}")
    return zona


def vista_pnd(panel):
    """v0.7.0 · Precio de zona de carga (PND) histórico de una zona. Carril separado: no usa ningún dato PML."""
    limites, fechas_zona, version = PND["limites"], PND["zonas"], PND["version"]
    zonas = list(fechas_zona)
    with panel:
        zona = selector_zona(zonas)
        inicio, fin, resolucion = fechas_elegidas()  # v0.8.2: los selectores van en la barra superior
        primera, ultima = fechas_zona.get(zona, (None, None))
        if primera:
            st.caption(f"{zona.title()} tiene datos del {primera} al {ultima}.")
    actualizar_url(st.session_state.get("vista", VISTAS_URL["historico"]))
    solista_pnd(zona)

    if inicio > fin:
        st.error("La fecha 'Desde' debe ser anterior a 'Hasta'.")
        st.stop()
    if resolucion == "horaria" and (fin - inicio).days + 1 > PND_HORARIA_MAX_DIAS:
        st.warning(f"La resolución horaria admite hasta {PND_HORARIA_MAX_DIAS} días. "
                   "Acorta el rango o elige diaria o mensual.")
        st.stop()

    try:
        e = consultar_estadisticas_pnd(zona, inicio, fin, str(pnd_zonas.PND_DIR), version).iloc[0]
        df = consultar_serie_pnd(zona, inicio, fin, resolucion, str(pnd_zonas.PND_DIR), version)
    except (duckdb.Error, OSError):
        st.error("No se puede consultar el rango con el paquete público de PND. Es necesario revisar sus archivos.")
        st.stop()

    sin_dato = [d for d in limites["dias_sin_dato"] if inicio <= d <= fin]
    if e["horas_con_dato"] == 0:
        st.warning(f"Sin datos de PND para {zona.title()} entre {inicio} y {fin}. No se muestra ninguna "
                   "cifra: la ausencia de datos no equivale a precio cero."
                   + (" Ese periodo no tiene dato disponible en la consulta verificada al servicio de CENACE; "
                      "se reintenta en cada actualización." if sin_dato else ""))
        st.stop()

    st.subheader(f"{zona.title()}: precio de zona de carga (PND), {inicio} a {fin}")
    con_dato, del_rango = int(e["horas_con_dato"]), int(e["horas_del_rango"])
    desde_obs, hasta_obs = e["primera_fecha"].date(), e["ultima_fecha"].date()

    def pnd_del_dia(d):
        x = consultar_estadisticas_pnd(zona, d, d, str(pnd_zonas.PND_DIR), version).iloc[0]
        return None if x["horas_con_dato"] == 0 else x["promedio"]
    cabecera(pnd_del_dia, hasta_obs, limites, "PND promedio")
    st.markdown(f"Zona de carga · MDA · SIN · CENACE | **Cobertura:** {e['cobertura_pct']}% ({con_dato:,} de "
                f"{del_rango:,} horas con dato) | **Rango con observaciones:** {desde_obs} a {hasta_obs}")
    if sin_dato:
        evidencia = limites["evidencia_sin_dato"]
        detalle = "; ".join(f"{d} (consulta verificada {evidencia[d]['consultado_utc']})" for d in sin_dato)
        st.warning(f"Sin dato disponible en la consulta verificada al servicio de CENACE: {detalle}. Ese día no "
                   "tiene precio en el paquete (no es cero ni se rellena) y la cobertura lo cuenta como faltante; "
                   "se vuelve a consultar en cada actualización.")
    if e["cobertura_pct"] < COBERTURA_ESCASA:
        st.warning(f"Cobertura escasa: los indicadores describen solo {con_dato:,} horas, entre {desde_obs} y "
                   f"{hasta_obs}. Las horas sin dato no se tratan como cero.")
    corregidos = [d for d in limites["dias_corregidos"] if inicio <= d <= fin]
    if corregidos:
        st.caption(f"Días corregidos por CENACE después de su primera publicación: {', '.join(map(str, corregidos))}.")

    df = marcar_periodos(df, inicio, fin, resolucion)
    titulo = {"horaria": "PND horario", "diaria": "PND promedio diario", "mensual": "PND promedio mensual"}[resolucion]
    with st.container(key="tarjeta"):
        izq, der = st.columns([3.2, 1], gap="large")
        with izq:
            st.markdown(f"**{titulo} (MXN/MWh)**")
            # v0.8.0 · La congestión del PND es la del propio paquete PND (pz_cng), ya en esta serie: no se toma del PML.
            # v0.8.1 · PND en azul (PML en ámbar), igual que en el tablero ENSEMBLE.
            grafica(df, "pnd_promedio", "PND (MXN/MWh)", resolucion, color=AZUL, nodo=zona.title(), titulo_serie="Zona",
                    congestion=df[["periodo", "etiqueta", "congestion"]])
        with der, st.container(key="ficha"):
            st.markdown(barra_rango("Rango horario del periodo", e["minimo"], e["maximo"], e["promedio"]),
                        unsafe_allow_html=True)
            st.metric("Promedio horario", mxn(e["promedio"]), help="Promedio simple de las horas con dato.")
            st.metric("Mediana horaria", mxn(e["mediana"]))
            st.metric("Mínimo horario", mxn(e["minimo"]), help="Menor PND de una hora en el rango.")
            st.metric("Máximo horario", mxn(e["maximo"]), help="Mayor PND de una hora en el rango.")
            st.metric("Horas con PND < 0", f"{int(e['horas_negativas']):,}")
            st.markdown(fila("Energía", mxn(e["energia"])) + fila("Pérdidas", mxn(e["perdidas"]))
                        + fila("Congestión", mxn(e["congestion"])) + fila("Desv. estándar", mxn(e["desv_std"]))
                        + fila("Percentil 10", mxn(e["p10"])) + fila("Percentil 90", mxn(e["p90"]))
                        + fila("Cobertura", f"{e['cobertura_pct']}%"), unsafe_allow_html=True)
    descarga_csv("pnd", exportar.tabla_pnd(df, zona, resolucion), [zona], inicio, fin, resolucion,
                 ayuda="Los datos de esta gráfica: fecha, hora (si es horaria), zona de carga, PND y sus componentes "
                       "en MXN/MWh.")
    st.caption(f"Indicadores calculados sobre las {con_dato:,} horas con dato, en MXN/MWh"
               + ("." if resolucion == "horaria" else f", aunque la gráfica sea {resolucion}.")
               + " Energía, pérdidas y congestión: promedios sobre las mismas horas.")
    avisos_parciales(df, resolucion)

    with st.expander("Tabla del PND y sus componentes"):
        tabla = df[["etiqueta", "pnd_promedio", "energia", "perdidas", "congestion", "horas", "horas_posibles"]].rename(
            columns={"etiqueta": "Periodo", "pnd_promedio": "PND", "energia": "Energía", "perdidas": "Pérdidas",
                     "congestion": "Congestión", "horas": "Horas con dato", "horas_posibles": "Horas posibles en el rango"})
        st.dataframe(tabla, hide_index=True, width="stretch",
                     column_config={c: st.column_config.NumberColumn(format="%.2f")
                                    for c in ("PND", "Energía", "Pérdidas", "Congestión")})

# ---------------------------------------------------------------------------------------------------------------
# v0.8.0 · Graphite Trading | Ensemble & Solo. ENSEMBLE es el tablero compacto del mercado; SOLO son las vistas de
# v0.7.0 con el nodo o la zona como protagonista. Cambiar de escena es un callback: un solo rerun, sin animaciones,
# y las consultas ya hechas se reutilizan de la caché. Ver escena.py (URL) y ensemble.py (consultas).
# ---------------------------------------------------------------------------------------------------------------

def entrar_solo(modalidad, elemento):
    """Callback: pasa a SOLO con `elemento` (nodo PML o zona PND) como protagonista. Fechas y resolución se conservan.

    PML abre en la vista 1 y deja el nodo también como nodo A de «Comparar» (decisión D3); PND abre su histórico.
    """
    estado = st.session_state
    if PND:
        estado["modalidad"] = modalidad
        ajustar_fechas_modalidad()
    if modalidad == "pnd":
        estado["zona"] = elemento
    else:
        estado["nodo"] = estado["nodo_a"] = elemento
        estado["vista"] = VISTAS_URL["historico"]
    estado["escena"] = SOLO
    # v0.8.1 · El detalle aparece arriba: tras elegir desde el tablero (que puede estar más abajo), la página
    # lleva la vista al detalle una sola vez. `enfoque` cambia en cada elección para que el aviso se repita.
    estado["enfocar"] = True
    estado["enfoque"] = estado.get("enfoque", 0) + 1
    descartar_avisos()


def solista_actual():
    """v0.8.1 · (modalidad, elemento) del detalle abierto, o None si solo se ve el mercado."""
    estado = st.session_state
    if estado.get("escena") != SOLO:
        return None
    if PND and estado.get("modalidad") == "pnd":
        return "pnd", estado.get("zona")
    if estado.get("vista") == VISTAS_URL["comparacion"]:
        return "pml", estado.get("nodo_a")
    return "pml", estado.get("nodo")


def buscar_solista(modalidad, clave):
    """v0.8.1 · Callback de la búsqueda del tablero con el detalle abierto: cambia solo el protagonista de arriba.

    Es un selector aparte (no repite las claves `nodo`/`zona` del panel del detalle) y vuelve a quedar vacío.
    """
    elemento = st.session_state.get(clave)
    if elemento:
        entrar_solo(modalidad, elemento)
    st.session_state[clave] = None


def enfocar_detalle(hueco):
    """v0.8.1 · Lleva la vista al detalle recién elegido (sin animación si el sistema pide reducir movimiento).

    Se dibuja en un hueco fijo (`st.empty`): así el resto de la página no cambia de posición en el árbol de Streamlit
    y sus gráficas no se vuelven a montar en cada elección.
    """
    if not st.session_state.pop("enfocar", False):
        return
    hueco.html(f"""<script>/* enfoque {st.session_state.get("enfoque", 0)} */
(() => {{ let n = 0; const ir = () => {{
  const d = document.querySelector('[class*="st-key-detalle_"]');
  if (d) {{ const suave = !matchMedia('(prefers-reduced-motion: reduce)').matches;
           d.scrollIntoView({{behavior: suave ? 'smooth' : 'auto', block: 'start'}}); }}
  else if (n++ < 20) setTimeout(ir, 50); }}; setTimeout(ir, 30); }})();
</script>""", unsafe_allow_javascript=True)


def volver_al_mercado():
    """Callback de «Cerrar detalle»: solo el mercado, con las mismas fechas, resolución, modalidad y última selección."""
    st.session_state["escena"] = ENSEMBLE
    descartar_avisos()


def solista_pml(nodo, nodo_b=None):
    """Encabezado de SOLO PML: el nodo protagonista (o A − B en «Comparar») con su nombre oficial y ubicación."""
    nombres = UBICACION.get("nombres", {}) if UBICACION else {}
    if nodo_b:
        titulo, detalle = f"{nodo} <span class='vs'>vs</span> {nodo_b}", (
            f"{nombres.get(nodo) or nodo} · {nombres.get(nodo_b) or nodo_b}" if nombres else "")
    else:
        titulo = nodo
        detalle = (f"{nombres.get(nodo) or ''} · {ubicacion_de(nodo)}".lstrip(" ·") if UBICACION else "")
    st.markdown(f'<div class="solista pml"><span class="et">Solista al frente · PML · NodoP</span><span class="nombre">{titulo}'
                f'</span><span class="detalle">{detalle}</span></div>', unsafe_allow_html=True)


def solista_pnd(zona):
    """Encabezado de SOLO PND: la zona de carga protagonista y su Región de Control."""
    regiones = sorted(r.title() for r, zs in PND.get("regiones", {}).items() if zona in zs)
    detalle = f"Región de Control: {', '.join(regiones)}" if regiones else "Zona de carga del SIN"
    st.markdown(f'<div class="solista pnd"><span class="et">Solista al frente · PND · Zona de carga</span><span class="nombre">'
                f'{zona.title()}</span><span class="detalle">{detalle}</span></div>', unsafe_allow_html=True)


def actualizar_url_ensemble():
    """URL de ENSEMBLE: solo fechas y resolución. Un enlace con fechas inválidas avisa igual que en SOLO."""
    estado = st.session_state
    enlace = enlace_ensemble({clave: estado.get(clave) for clave in ("desde", "hasta", "resolucion")})
    problemas, _ = estado.get("enlace_avisos", ([], []))
    if problemas and enlace != estado.setdefault("enlace_inicial", enlace):
        problemas = []
        descartar_avisos()
    if problemas:
        st.error("Este enlace no se puede abrir tal cual:\n\n" + "\n".join(f"- {p}" for p in problemas)
                 + "\n\nNo se muestra ninguna cifra para no presentar un análisis distinto del compartido. "
                 "Corrige las fechas en el panel o continúa con la configuración que se ve ahí.")
        st.button("Continuar con la configuración mostrada", on_click=descartar_avisos)
        st.stop()
    actual = st.query_params.to_dict()
    nuevo = {k: v for k, v in actual.items() if k not in PARAMETROS} | enlace  # conserva parámetros ajenos
    if nuevo != actual:
        st.query_params.from_dict(nuevo)


TENSIONES = {"400 kV": 400.0, "230 kV": 230.0, "115 kV": 115.0, "Todas": None}
TENSION_INICIAL = "400 kV"
WATCHLIST_N = 6    # filas visibles de la lista del rail (v0.8.3: izquierdo); «Mostrar más» agrega WATCHLIST_MAS
WATCHLIST_MAS = 25


def reiniciar_lista():
    """Callback de los filtros de la lista: vuelve a mostrar las primeras filas."""
    st.session_state["wl_n"] = WATCHLIST_N


def mostrar_mas():
    st.session_state["wl_n"] = st.session_state.get("wl_n", WATCHLIST_N) + WATCHLIST_MAS


def tension_elegida():
    """kV del filtro de tensión, o None para «Todas». Sin selección (pastilla desmarcada) equivale a «Todas»."""
    return TENSIONES.get(st.session_state.get("nodo_tension") or "Todas")


def nodos_de_lista(nodos):
    """v0.8.0 · Nodos que cumplen tensión y ubicación. La tensión es la columna `tension_kv` del Catálogo de NodosP de
    CENACE (no se deduce del sufijo de la clave); un nodo sin tensión en el catálogo solo aparece con «Todas»."""
    if not UBICACION:
        return list(nodos)
    union = UBICACION["union"]
    kv = tension_elegida()
    filas = union if kv is None else union[union["tension_kv"] == kv]
    # v0.8.2 · Filtros propios de la lista (`lista_*`): la lista es permanente y no debe repetir las claves de los
    # filtros del selector de nodo del detalle.
    elegido = {f: (None if st.session_state.get(f"lista_{f}", TODAS) == TODAS else st.session_state[f"lista_{f}"])
               for f in ("region", "estado", "zona")}
    return cat_nodos.filtrar(filas, elegido["region"], elegido["zona"], elegido["estado"])


def md_literal(texto):
    """Escapa los signos de Markdown de un texto que va dentro de la etiqueta de un botón."""
    return "".join("\\" + c if c in "\\`*_[]~<>#|" else c for c in str(texto))


def etiqueta_fila(texto, precio, horas):
    """v0.8.3 · Etiqueta de dos líneas para el rail angosto: «*clave*» arriba (el CSS la recorta con «…») y
    «**precio**» abajo. Mismo valor que antes (`mxn`), mismo aviso de horas parciales."""
    parcial = f" · {horas} h" if horas and horas < 24 else ""
    return f"*{md_literal(texto)}* **{mxn(precio) if precio is not None else 'sin dato'}{parcial}**"


def fila_lista(clave_widget, elemento, texto, precio, horas, modalidad, ayuda):
    st.button(etiqueta_fila(texto, precio, horas), key=clave_widget,
              on_click=entrar_solo, args=(modalidad, elemento), width="stretch", help=ayuda,
              type="primary" if solista_actual() == (modalidad, elemento) else "secondary")


def lista_watchlist(filas, modalidad, clave, etiqueta, precios, titulo, nombre=None):
    """Lista del rail: muestra solo las primeras filas (no miles de botones) y «Mostrar más».

    v0.8.3 · `nombre(elemento)` da el nombre completo para la ayuda (la fila angosta puede recortarlo)."""
    st.session_state.setdefault("wl_n", WATCHLIST_N)
    n = st.session_state["wl_n"]
    st.markdown(f'<div class="lista-et">{titulo}</div>', unsafe_allow_html=True)
    with st.container(key=clave):
        for i, elemento in enumerate(filas[:n]):
            precio, horas = precios.get(elemento, (None, None))
            completo = nombre(elemento) if nombre else etiqueta(elemento)
            fila_lista(f"{clave}_{i}", elemento, etiqueta(elemento), precio, horas, modalidad,
                       f"Poner al frente {completo}. Precio: promedio del día de referencia, MXN/MWh.")
    if len(filas) > n:
        st.button(f"Mostrar {min(WATCHLIST_MAS, len(filas) - n)} más ({len(filas) - n})", key=f"mas_{clave}",
                  on_click=mostrar_mas, type="tertiary")


MODOS_RAIL = {"Nodos": "pml", "Zonas": "pnd"}  # v0.8.3 · pestañas del rail ↔ modalidad de precio de la cabecera


def cambiar_modo_rail():
    """v0.8.3 · Callback de «Nodos | Zonas» del rail: cambia la MISMA modalidad que el selector «Precio» de la
    cabecera (no hay un segundo estado de modalidad). Volver a tocar la pestaña activa no la desmarca."""
    elegido = st.session_state.get("rail_modo")
    if elegido is None:
        return
    st.session_state["modalidad"] = MODOS_RAIL[elegido]
    ajustar_fechas_modalidad()
    reiniciar_lista()


def atril(nodos, limites, version, con_detalle):
    """v0.8.2 · Panel permanente «Elige el solista» (watchlist): siempre visible junto al detalle y el tablero.

    v0.8.3 · Es un rail IZQUIERDO angosto con dos modos en el mismo panel: «Nodos» (PML/NodoP) y «Zonas» (PND/zona
    de carga). Las pestañas siguen a la modalidad de la cabecera y la cambian por callback: hay un solo estado
    (`modalidad`). Fechas y resolución siguen en la barra superior. Las claves son propias (`rail_modo`,
    `buscar_*`, `lista_*`): no repiten las del detalle.
    """
    estado = st.session_state
    modo_pnd = bool(PND) and estado.get("modalidad") == "pnd"
    hasta = estado["hasta"]
    with st.container(key="atril"):
        st.markdown('<div id="elige-solista" class="atril-et">' + ("Elige otro solista" if con_detalle
                    else "Elige el solista") + "</div>", unsafe_allow_html=True)
        if PND:
            # Se fija antes de dibujar el control: así sigue siempre a la modalidad (también si cambió en la cabecera).
            estado["rail_modo"] = "Zonas" if modo_pnd else "Nodos"
            st.segmented_control("Mostrar", list(MODOS_RAIL), key="rail_modo", on_change=cambiar_modo_rail,
                                 label_visibility="collapsed", width="stretch",
                                 help="Nodos: PML por NodoP. Zonas: PND por zona de carga. Cambia también el precio "
                                      "de la cabecera; PML y PND no se mezclan.")
        else:
            st.caption("PND por zona de carga no está en esta publicación: solo nodos PML.")
        if modo_pnd:
            zonas = list(PND["zonas"])
            with st.expander("Región"):
                region = (_elegir("Región de Control", sorted(PND["regiones"]), "lista_zona_region")
                          if PND["regiones"] else None)
            opciones = [z for z in PND["regiones"][region] if z in zonas] if region else zonas
            st.selectbox("Buscar zona", opciones, index=None, key="buscar_pnd", format_func=str.title,
                         placeholder="Nombre de la zona", on_change=buscar_solista, args=("pnd", "buscar_pnd"),
                         help="Zona de carga del SIN según CENACE. El PND es el precio de la zona, no de un nodo.")
            dia = ens.dia_pnd(hasta, PND["limites"], str(pnd_zonas.PND_DIR))
            precios = {}
            if dia is not None:
                r = consultar_ranking_pnd(dia, str(pnd_zonas.PND_DIR), PND["version"])
                precios = dict(zip(r["elemento"], zip(r["promedio"], r["horas"])))
            lista_watchlist(opciones, "pnd", "wl_pnd", str.title, precios,
                            f"{len(opciones):,} zonas · PND promedio<br>del {dia or '—'} · MXN/MWh")
        else:
            estado.setdefault("nodo_tension", TENSION_INICIAL)
            if UBICACION:
                st.segmented_control("Tensión (kV)", list(TENSIONES), key="nodo_tension", on_change=reiniciar_lista,
                                     format_func=lambda t: t.replace(" kV", ""), width="stretch",
                                     help="Tensión del NodoP según el Catálogo de NodosP de CENACE (no se deduce "
                                          "de la clave). «Todas» incluye también 69, 85, 138 kV y otras.")
            filtrados = nodos_de_lista(nodos)
            nombres = UBICACION.get("nombres", {}) if UBICACION else {}
            st.selectbox("Buscar nodo", filtrados, index=None, key="buscar_pml",
                         format_func=lambda n: cat_nodos.etiqueta(n, nombres),
                         placeholder="Clave o nombre", on_change=buscar_solista,
                         args=("pml", "buscar_pml"), help=AYUDA_NODO if UBICACION else AYUDA_SOLO_CLAVE)
            if UBICACION:
                with st.expander("Ubicación"):
                    union = UBICACION["union"]
                    region = _elegir("Región de Control", cat_nodos.regiones(union), "lista_region")
                    est = _elegir("Estado", cat_nodos.estados(union, region), "lista_estado")
                    _elegir("Zona de carga", cat_nodos.zonas(union, region, est), "lista_zona")
                    st.button("Limpiar ubicación", key="lista_limpiar", on_click=limpiar_ubicacion, args=("lista",))
            dia = ens.dia_pml(hasta, limites)
            try:
                r = consultar_ranking_pml(dia, str(DATA_DIR), version)
                precios = dict(zip(r["elemento"], zip(r["promedio"], r["horas"])))
            except (DatosNoDisponibles, duckdb.Error):
                precios = {}
            tension = estado.get("nodo_tension") or "Todas"
            lista_watchlist(filtrados, "pml", "wl_pml", str, precios,
                            f"{len(filtrados):,} nodos · {tension} · PML promedio<br>del {dia} · MXN/MWh",
                            nombre=lambda n: cat_nodos.etiqueta(n, nombres))


def kpis(celdas):
    """Indicadores compactos en rejilla (4 → 2 → 1 columnas según el ancho). `celdas`: [(etiqueta, valor, nota)]."""
    html = "".join(f'<div class="kpi"><div class="et">{e}</div><div class="v">{v}</div><div class="nota">{n}</div></div>'
                   for e, v, n in celdas)
    st.markdown(f'<div class="kpis">{html}</div>', unsafe_allow_html=True)


def distribucion(ranking, color, unidad):
    """Gráfica compacta de distribución: cuántos elementos tienen su promedio del día en cada intervalo.

    Solo agrupa los promedios del ranking para dibujarlos; no calcula ningún indicador nuevo.
    """
    df = ranking[["elemento", "promedio"]]
    intervalos = alt.Bin(maxbins=30)
    grafica_ = alt.Chart(df).mark_bar(color=color, opacity=.9, cornerRadiusTopLeft=1, cornerRadiusTopRight=1).encode(
        x=alt.X("promedio:Q", bin=intervalos, title=None,
                axis=alt.Axis(grid=False, domain=False, tickColor="#C9CBD0", format=",.0f", labelOverlap=True)),
        y=alt.Y("count():Q", title=None,
                axis=alt.Axis(orient="right", domain=False, ticks=False, gridColor="#DADCE0", tickCount=3)),
        tooltip=[alt.Tooltip("promedio:Q", bin=intervalos, title="Promedio del día (MXN/MWh)", format=",.2f"),
                 alt.Tooltip("count():Q", title=unidad)])
    st.altair_chart(configurar(grafica_.properties(height=ALTO_DISTRIBUCION, background="transparent"), oscuro=False),
                    width="stretch")


# v0.8.7 · Drill-down de la distribución PND (Issue #36). Tocar una barra (o elegir su rango en la lista) muestra
# debajo las zonas de esa barra con su promedio y horas con dato; tocar una zona la pone al frente. Las barras salen
# de ens.intervalos (réplica exacta del bin de Vega), así que el conteo de la barra y la lista son el mismo conjunto.
# El estado es (día, inicio del intervalo): si cambia el día de referencia PND, la selección se descarta.


def barra_pnd_elegida(dia, tabla):
    """Inicio del intervalo elegido para `dia`, o None si no hay selección vigente para ese día y esas barras."""
    elegido = st.session_state.get("pnd_barra")
    if not elegido or elegido[0] != dia:
        return None
    for ini in tabla["bin_ini"]:
        if abs(float(ini) - float(elegido[1])) < 1e-9:
            return float(ini)
    return None


def elegir_barra_pnd(clave):
    """Callback del clic en una barra (o en el fondo, que quita la selección)."""
    dia = st.session_state.get("pnd_barra_dia")
    evento = st.session_state.get(clave) or {}
    puntos = (evento.get("selection") or {}).get("barra_pnd") or []
    ini = puntos[0].get("bin_ini") if puntos else None
    st.session_state["pnd_barra"] = (dia, float(ini)) if ini is not None else None
    st.session_state[f"rango_pnd_{dia}"] = float(ini) if ini is not None else None


def elegir_rango_pnd(clave):
    """Callback de la lista «Ver zonas de un rango» (alternativa accesible al clic en la gráfica)."""
    dia = st.session_state.get("pnd_barra_dia")
    ini = st.session_state.get(clave)
    st.session_state["pnd_barra"] = (dia, float(ini)) if ini is not None else None
    st.session_state["pnd_barra_n"] = st.session_state.get("pnd_barra_n", 0) + 1  # la gráfica se redibuja limpia


def quitar_barra_pnd():
    dia = st.session_state.get("pnd_barra_dia")
    st.session_state["pnd_barra"] = None
    st.session_state[f"rango_pnd_{dia}"] = None
    st.session_state["pnd_barra_n"] = st.session_state.get("pnd_barra_n", 0) + 1


def rango_txt(ini, fin, paso):
    decimales = 0 if paso >= 1 else 2
    return f"{ini:,.{decimales}f}–{fin:,.{decimales}f}"


def distribucion_pnd(ranking, dia):
    """Distribución PND con selección de barra y la lista de zonas de la barra elegida."""
    zonas = ens.intervalos(ranking)
    tabla = ens.barras(zonas)
    if tabla.empty:
        return
    paso = float(tabla["bin_fin"].iloc[0] - tabla["bin_ini"].iloc[0])
    st.session_state["pnd_barra_dia"] = dia
    elegido = barra_pnd_elegida(dia, tabla)
    if elegido is None and st.session_state.get("pnd_barra"):
        st.session_state["pnd_barra"] = None  # de otro día o de barras que ya no existen: no se conserva
    tabla = tabla.assign(rango=[f"{rango_txt(a, b, paso)} MXN/MWh" for a, b in zip(tabla["bin_ini"], tabla["bin_fin"])],
                         elegida=tabla["bin_ini"] == elegido if elegido is not None else False)
    barra = alt.selection_point(name="barra_pnd", fields=["bin_ini"], on="click", empty=False)
    opacidad = (alt.condition("datum.elegida", alt.value(1), alt.value(.35)) if elegido is not None
                else alt.value(.9))
    # Sin cornerRadius: con x «binned» la versión de Vega-Lite de Streamlit dibuja las barras con ancho 0.
    grafica_ = alt.Chart(tabla).mark_bar(color=AZUL, cursor="pointer", binSpacing=1).encode(
        x=alt.X("bin_ini:Q", bin="binned", title=None,
                axis=alt.Axis(grid=False, domain=False, tickColor="#C9CBD0", format=",.0f", labelOverlap=True)),
        x2="bin_fin:Q",
        y=alt.Y("n:Q", title=None, axis=alt.Axis(orient="right", domain=False, ticks=False, gridColor="#DADCE0",
                                                 tickCount=3, tickMinStep=1)),
        opacity=opacidad,
        stroke=alt.condition("datum.elegida", alt.value("#1C1C1E"), alt.value(None)) if elegido is not None
        else alt.value(None),
        tooltip=[alt.Tooltip("rango:N", title="Promedio del día"), alt.Tooltip("n:Q", title="Zonas")],
    ).add_params(barra)
    clave = f"dist_pnd_{dia}_{st.session_state.get('pnd_barra_n', 0)}"
    st.altair_chart(configurar(grafica_.properties(height=ALTO_DISTRIBUCION, background="transparent")),
                    width="stretch", key=clave, on_select=lambda: elegir_barra_pnd(clave), selection_mode="barra_pnd")
    clave_rango = f"rango_pnd_{dia}"
    if st.session_state.get(clave_rango) not in [None, *tabla["bin_ini"]]:
        st.session_state[clave_rango] = None
    if elegido is not None:
        st.session_state[clave_rango] = elegido
    textos = {float(a): f"{r} · {n} zona{'s' if n != 1 else ''}"
              for a, r, n in zip(tabla["bin_ini"], tabla["rango"], tabla["n"])}
    with st.container(key="drill_pnd_ctl", horizontal=True, vertical_alignment="bottom", gap="small"):
        st.selectbox("Ver zonas de un rango", [None, *map(float, tabla["bin_ini"])], key=clave_rango,
                     format_func=lambda x: "Toca una barra o elige un rango" if x is None else textos[x],
                     on_change=elegir_rango_pnd, args=(clave_rango,), width=300,
                     help="Zonas de carga cuyo PND promedio del día cae en el intervalo [inicio, fin) de la barra; "
                          "la última barra incluye su límite superior. Mismos intervalos que la gráfica.")
        if elegido is not None:
            st.button("Quitar selección", key="quitar_barra_pnd", on_click=quitar_barra_pnd,
                      icon=":material/close:")
    if elegido is None:
        return
    fila = tabla[tabla["bin_ini"] == elegido].iloc[0]
    lista = ens.miembros(zonas, elegido)
    parciales = int((lista["horas"] < 24).sum())
    with st.container(key="drill_pnd"):
        st.markdown(f'<div class="drill-et"><b>{fila["rango"]} · {len(lista)} zona{"s" if len(lista) != 1 else ""} '
                    f'de carga</b><span>PND promedio del {dia} · zonas, no NodosP · de mayor a menor</span></div>',
                    unsafe_allow_html=True)
        with st.container(key="drill_lista", horizontal=True, gap="small"):
            for i, z in enumerate(lista.itertuples()):
                parcial = f" · {z.horas} h" if z.horas < 24 else ""
                st.button(f"{z.elemento.title()} · {mxn(z.promedio)}{parcial}", key=f"dz_pnd_{i}",
                          on_click=entrar_solo, args=("pnd", z.elemento),
                          type="primary" if solista_actual() == ("pnd", z.elemento) else "secondary",
                          help=f"Poner al frente {z.elemento}. Promedio de {z.horas} de 24 horas con dato, MXN/MWh.")
        if parciales:
            st.caption(f"{parciales} zona{'s' if parciales != 1 else ''} con menos de 24 horas con dato: su promedio "
                       "usa solo esas horas (sin dato no es cero).")


def lista_ranking(titulo, filas, modalidad, clave, etiqueta):
    """Filas del ranking como botones: tocar una abre SOLO de ese nodo o zona."""
    st.markdown(f'<div class="lista-et">{titulo}</div>', unsafe_allow_html=True)
    with st.container(key=clave):
        for i, fila_ in enumerate(filas.itertuples()):
            parcial = f" · {fila_.horas} h" if fila_.horas < 24 else ""
            st.button(f"{etiqueta(fila_.elemento)} · {mxn(fila_.promedio)}{parcial}", key=f"{clave}_{i}",
                      on_click=entrar_solo, args=(modalidad, fila_.elemento), width="stretch",
                      type="primary" if solista_actual() == (modalidad, fila_.elemento) else "secondary",
                      help=f"Poner al frente {fila_.elemento}. Promedio de {fila_.horas} horas con dato, MXN/MWh.")


def seccion_pml(dia, total, version):
    with st.container(key="seccion_pml"):
        st.markdown(f'<div class="seccion-et"><span class="marca pml"></span><b>PML · NodoP</b>'
                    f'<span>Precio Marginal Local por nodo · día {dia} · CENACE SW-PML, MDA, SIN</span></div>',
                    unsafe_allow_html=True)
        try:
            ranking = consultar_ranking_pml(dia, str(DATA_DIR), version)
        except (DatosNoDisponibles, duckdb.Error):
            st.error("No se puede consultar el día con el paquete público PML. Es necesario revisar sus particiones.")
            return
        if ranking.empty:
            st.warning(f"Ningún nodo tiene PML el {dia}. No se muestra ninguna cifra: sin dato no es precio cero.")
            return
        r = ens.resumen(ranking, total)
        kpis([("Nodos con dato", f"{r['con_dato']:,}", f"de {total:,} · {r['sin_dato']:,} sin dato"),
              ("Más caro", mxn(r["caro"]["promedio"]), r["caro"]["elemento"]),
              ("Más barato", mxn(r["barato"]["promedio"]), r["barato"]["elemento"]),
              ("Con alguna hora < 0", f"{r['con_negativos']:,}", "PML horario negativo ese día")])
        st.markdown('<div class="mini-et">Distribución del PML promedio del día entre nodos (MXN/MWh)</div>',
                    unsafe_allow_html=True)
        distribucion(ranking, NARANJA, "Nodos")
        caros, baratos = st.columns(2, gap="medium")
        with caros:
            lista_ranking("Más caros", ranking.head(RANKING_N), "pml", "rk_pml_caros", str)
        with baratos:
            lista_ranking("Más baratos", ranking.tail(RANKING_N).iloc[::-1], "pml", "rk_pml_baratos", str)
        st.caption("Promedio simple de las horas con dato de cada nodo ese día, el mismo valor que su detalle. "
                   + (f"{r['incompletos']:,} nodos tienen menos de 24 horas con dato. " if r["incompletos"] else "")
                   + "Un nodo sin horas con dato no entra al ranking ni se trata como cero.")


def seccion_pnd(hasta):
    lim = PND["limites"]
    carpeta = str(pnd_zonas.PND_DIR)
    dia = ens.dia_pnd(hasta, lim, carpeta)
    with st.container(key="seccion_pnd"):
        st.markdown(f'<div class="seccion-et"><span class="marca pnd"></span><b>PND · Zona de carga</b>'
                    f'<span>Precio de zona de carga · día {dia or "—"} · CENACE SW-PEND, MDA, SIN</span></div>',
                    unsafe_allow_html=True)
        if dia is None:
            st.warning(f"El paquete PND no tiene datos hasta el {hasta}. No se muestra ninguna cifra.")
            return
        if dia < min(hasta, lim["hasta"]):
            st.caption(f"El {min(hasta, lim['hasta'])} no tiene PND en el paquete (sin dato, no cero); "
                       f"se muestra el último día con dato, {dia}.")
        try:
            ranking = consultar_ranking_pnd(dia, carpeta, PND["version"])
        except (duckdb.Error, OSError):
            st.error("No se puede consultar el día con el paquete público de PND. Es necesario revisar sus archivos.")
            return
        total = len(PND["zonas"])
        r = ens.resumen(ranking, total)
        kpis([("Zonas con dato", f"{r['con_dato']:,}", f"de {total:,} · {r['sin_dato']:,} sin dato"),
              ("Más cara", mxn(r["caro"]["promedio"]), r["caro"]["elemento"].title()),
              ("Más barata", mxn(r["barato"]["promedio"]), r["barato"]["elemento"].title()),
              ("Con alguna hora < 0", f"{r['con_negativos']:,}", "PND horario negativo ese día")])
        st.markdown('<div class="mini-et">Distribución del PND promedio del día entre zonas de carga (MXN/MWh) · toca una barra para ver sus zonas</div>',
                    unsafe_allow_html=True)
        distribucion_pnd(ranking, dia)
        caras, baratas = st.columns(2, gap="medium")
        with caras:
            lista_ranking("Más caras", ranking.head(RANKING_N), "pnd", "rk_pnd_caras", str.title)
        with baratas:
            lista_ranking("Más baratas", ranking.tail(RANKING_N).iloc[::-1], "pnd", "rk_pnd_baratas", str.title)
        st.caption("PND publicado por CENACE para cada zona; promedio simple de sus horas con dato ese día, el mismo "
                   "valor que su detalle. No se compara con el PML de ningún nodo.")


def vista_ensemble(limites, nodos, version, con_detalle=False):
    """v0.8.0 · ENSEMBLE: el mercado del día de referencia, PML y PND en secciones separadas.

    v0.8.1 · Se dibuja siempre, debajo del detalle. v0.8.2 · El panel de elección es la columna derecha permanente
    (`atril`); aquí quedan solo las secciones. Con el detalle abierto, la URL es la del detalle.
    """
    rotulo = st.empty()  # siempre en el mismo lugar: el tablero no cambia de posición al abrir o cerrar el detalle
    rotulo.markdown('<div class="banda-et"><b>Mercado · ENSEMBLE</b><span>'
                    + ("la banda sigue aquí · " if con_detalle else "")
                    + "el día de referencia de todos los nodos y zonas de carga · toca uno para ponerlo al frente"
                      "</span></div>", unsafe_allow_html=True)
    with st.container(key="ensemble"):
        if not con_detalle:
            actualizar_url_ensemble()
        hasta = st.session_state["hasta"]
        seccion_pml(ens.dia_pml(hasta, limites), len(nodos), version)
        if PND:
            seccion_pnd(hasta)
        else:
            st.caption("PND por zona de carga no está en esta publicación; el tablero muestra solo PML.")


def metodologia_ensemble():
    with st.expander("Metodología · Ensemble"):
        st.markdown("""
- **Qué muestra:** el día de referencia («Hasta», acotado a cada paquete) de **todos** los nodos PML y, por separado, de **todas** las zonas de carga PND. PML y PND tienen su propio paquete y su propio día; nunca se combinan ni se comparan entre sí.
- **Promedio del día:** el mismo valor que la vista SOLO de ese nodo o zona para ese día: promedio simple de sus horas con dato (fuera de la ventana horaria PML, suma ÷ horas válidas del diario). El tablero solo **ordena** esos valores y **cuenta** elementos; no hay índices, promedios entre nodos ni ponderaciones nuevas.
- **Distribución:** cuántos nodos (o zonas) tienen su promedio del día en cada intervalo de precio. Agrupa los mismos promedios para dibujarlos; no es un indicador nuevo.
- **Faltantes:** un nodo o una zona sin horas con dato ese día no entra al ranking ni se trata como cero; se cuenta como «sin dato». Si un día PND no tiene dato, se usa el último día anterior con dato y se dice.
- **Solista al frente:** tocar un nodo o una zona muestra su detalle arriba (histórico, comparación, componentes o PND) con las fechas y la resolución del panel; el tablero sigue debajo en la misma página. Tocar otro cambia solo el protagonista. «Cerrar detalle» deja solo el mercado con los mismos filtros.
""")


ALTO_BARRA_JS = """<script>
/* v0.8.2 · Alto real de la barra superior en --alto-barra: la lista derecha fija y el enfoque del detalle se colocan
   justo debajo aunque la barra ocupe dos filas (tableta, móvil). Sin la variable, el CSS usa un valor por omisión. */
(() => { const b = document.querySelector('.st-key-barra'); if (!b || b.dataset.observado) return;
  b.dataset.observado = '1';
  const fijar = () => document.documentElement.style.setProperty('--alto-barra', b.getBoundingClientRect().height + 'px');
  new ResizeObserver(fijar).observe(b); fijar(); })();
</script>"""


def texto_solista(en_solo, modo_pnd):
    """v0.8.2 · Nombre corto del protagonista para la barra superior (o «Mercado» si no hay detalle abierto)."""
    if not en_solo:
        return "Mercado · ENSEMBLE"
    estado = st.session_state
    if modo_pnd:
        return f"PND · {str(estado.get('zona') or '—').title()}"
    if estado.get("vista") == VISTAS_URL["comparacion"]:
        a, b = estado.get("nodo_a"), estado.get("nodo_b")
        return f"PML · {a} vs {b}" if a and b else f"PML · spread {a or ''}".rstrip()
    return f"PML · {estado.get('nodo') or '—'}"


def barra_controles(limites_activos, en_solo, modo_pnd):
    """v0.8.2 · Segunda parte de la barra superior fija: precio, solista activo, rangos, fechas y estado del paquete.

    Los selectores de fechas y resolución viven solo aquí (en un popover): las vistas leen su valor.
    """
    with st.container(key="controles", horizontal=True, vertical_alignment="center", gap="small"):
        if PND:
            st.radio("Precio", list(MODALIDADES), key="modalidad", horizontal=True, format_func=MODALIDADES_CORTAS.get,
                     on_change=ajustar_fechas_modalidad, label_visibility="collapsed", width="content",
                     help="PML: precio de un nodo (NodoP). PND: precio de una zona de carga, con el que se liquida "
                          "la demanda. No se mezclan.")
        botones_rango(limites_activos)
        with st.popover("Fechas", icon=":material/calendar_month:", width="content"):
            controles_rango(limites_activos, en_columnas=False)
            st.caption("1D, 7D, Mes y YTD se anclan en el último día publicado del paquete de este precio, nunca "
                       "en el reloj. YTD: del 1 de enero de ese año a ese día.")
        estado = st.session_state
        st.markdown(f'<div class="estado-barra"><span class="activo">{texto_solista(en_solo, modo_pnd)}</span>'
                    f'<span>{estado["desde"]} → {estado["hasta"]} · {estado["resolucion"]}</span>'
                    f'<span>MDA · último día publicado {limites_activos["hasta"]}</span></div>', unsafe_allow_html=True)


TICKER_JS = """<script>
/* v0.8.5 · La cinta lleva dos copias para dar la vuelta sin salto. La segunda es solo visual: se oculta a lectores de
   pantalla y sale del orden del tabulador (el teclado recorre una sola vez cada zona). */
(() => { let n = 0; const marcar = () => {
  const b = document.querySelector('.st-key-tk_copia_b');
  if (!b) { if (n++ < 40) setTimeout(marcar, 100); return; }
  b.setAttribute('aria-hidden', 'true');
  b.querySelectorAll('button').forEach(x => x.setAttribute('tabindex', '-1'));
  new MutationObserver(() => b.querySelectorAll('button:not([tabindex])').forEach(x => x.setAttribute('tabindex', '-1')))
    .observe(b, {childList: true, subtree: true}); };
  marcar(); })();
</script>"""
CLASE_TICKER = {"sube": "sube", "baja": "baja", "igual": "igual"}


def cinta_pnd():
    """v0.8.5 · Ticker PND en la barra fija (Issue #34): zonas de `ticker.ZONAS_TICKER` con su promedio del último día
    publicado del paquete PND y el cambio contra el día calendario anterior. Rojo ▲ si subió, verde ▼ si bajó, gris
    si igual o no comparable. Tocar una zona abre su detalle PND (mismo callback que la lista). No cambia fechas,
    resolución ni el día de referencia de ENSEMBLE. Sin paquete PND o sin datos, la cinta no se dibuja."""
    if not PND:
        return
    lim = PND["limites"]
    try:
        datos = consultar_ticker(lim["desde"], lim["hasta"], tuple(sorted(PND["zonas"])), str(pnd_zonas.PND_DIR),
                                 PND["version"])
    except Exception:  # noqa: BLE001 — una falla de la cinta nunca afecta PML ni el resto de PND
        return
    if not datos or not datos["fichas"]:
        return
    dia, previo = datos["dia"], datos["dia_previo"]
    comparativo = (f"vs {previo}" if datos["previo_publicado"] else f"{previo} sin dato publicado")
    with st.container(key="ticker", horizontal=True, vertical_alignment="center", gap="small"):
        st.markdown(f'<div class="tk-et"><b>PND · Zonas de carga · promedio diario (MXN/MWh)</b>'
                    f'<span>{dia} {comparativo}<i class="tk-corto"> · CENACE · MDA · no tiempo real</i></span>'
                    f'<span class="tk-largo">Datos publicados por CENACE · MDA · no tiempo real</span></div>',
                    unsafe_allow_html=True)
        with st.container(key="cinta"), st.container(key="pista", horizontal=True, gap=None):
            for copia in ("a", "b"):
                with st.container(key=f"tk_copia_{copia}", horizontal=True, gap="small"):
                    for ficha in datos["fichas"]:
                        clase = CLASE_TICKER.get(ficha["direccion"], "neutro")
                        slug = "".join(c if c.isalnum() else "-" for c in ficha["zona"].lower())
                        precio = "sin dato" if ficha["precio"] is None else f"{ficha['precio']:,.2f}"
                        cambio = ticker.cambio(ficha)
                        etiqueta = f"*{ficha['zona']}* **{precio}**" + (f" `{cambio}`" if cambio else "")
                        st.button(etiqueta, key=f"tk{copia}_{clase}_{slug}", on_click=entrar_solo,
                                  args=("pnd", ficha["zona"]), help=ticker.descripcion(ficha, dia, previo))
    st.html(TICKER_JS, unsafe_allow_javascript=True)


def conservar_widgets():
    """v0.7.0 · Streamlit borra el estado de un widget que no se dibuja en una corrida. Al pasar a PND (o volver a
    PML) se ocultan pestañas y selectores de la otra modalidad; reescribir su valor lo conserva para el regreso."""
    claves = ["vista", "zona", "zona_region", "nodo_tension", "modalidad", "lista_region", "lista_estado",
              "lista_zona", "lista_zona_region"] + [f"{n}{s}" for n in ("nodo", "nodo_a", "nodo_b")
                                                for s in ("", "_region", "_estado", "_zona")]
    for clave in claves:
        if clave in st.session_state:
            st.session_state[clave] = st.session_state[clave]


st.set_page_config(page_title="PML Explorer", page_icon=str(ASSETS / "logo.svg"), layout="wide",
                   initial_sidebar_state="collapsed")
st.html(ESTILOS)
# H01: regreso explícito al sitio editorial, fuera de cualquier panel para que se vea en las tres vistas.
st.markdown(f"[← Mercados · edarji.net]({SITIO_MERCADOS})")
# v0.8.2 · Barra superior fija (sticky): marca compacta y, más abajo en el código (tras leer el paquete), precio,
# solista activo, rangos, fechas y estado del paquete. Ver CSS «Terminal persistente».
barra = st.container(key="barra", horizontal=True, vertical_alignment="center", gap="medium")
with barra, st.container(key="marca", horizontal=True, vertical_alignment="center", gap="small"):
    logo()
    with st.container(key="marca_texto"):
        st.title("PML Explorer")
        # v0.7.0 · El subtítulo depende de la modalidad (se conoce más abajo, tras leer el enlace): hueco reservado.
        subtitulo = st.empty()
        subtitulo.caption("Precio Marginal Local · Mercado del Día en Adelanto · SIN (CENACE) · MXN/MWh · "
                          "datos diarios publicados, no en tiempo real")
    # v0.8.2 · Tableta y móvil: la lista no queda fija al lado (taparía la gráfica); este botón lleva a ella.
    # v0.8.3 · El texto depende de la modalidad (se conoce más abajo): hueco reservado, «Cambiar zona» en PND.
    chip = st.empty()

if not (DATA_DIR / "metadata.json").is_file():
    st.info("Los derivados públicos de CENACE todavía no están disponibles en esta publicación.")
    st.stop()

try:
    # La versión de la app entra en la llave de la caché: al publicar una versión nueva, ningún resultado
    # guardado por el código anterior se reutiliza (v0.6.2: KeyError pml_a tras el despliegue).
    version = huella_paquete() + VERSION_APP
    limites, nodos, fechas_nodo = cargar_paquete(str(DATA_DIR), version)
except (DatosNoDisponibles, duckdb.Error):
    st.error("El paquete público está incompleto o su esquema no es compatible. La integración debe validarse antes de publicar cifras.")
    st.stop()

if not nodos:
    st.warning("El paquete público no contiene nodos con datos.")
    st.stop()
UBICACION.update(cargar_ubicacion(tuple(nodos), firma_catalogo()))
# v0.7.0 · PND: solo si la carpeta pública pnd/ existe y cumple su contrato. Si falla, PML sigue igual.
if (pnd_zonas.PND_DIR / "metadata.json").is_file():
    try:
        version_pnd = pnd_zonas.huella_pnd() + VERSION_APP
        limites_pnd, fechas_zona = cargar_pnd(str(pnd_zonas.PND_DIR), version_pnd)
        regiones_pnd = pnd_zonas.regiones_de_zonas(UBICACION["union"]) if UBICACION else {}
        PND.update(limites=limites_pnd, zonas=fechas_zona, version=version_pnd, limites_pml=limites,
                   regiones={r: [z for z in zs if z in fechas_zona] for r, zs in regiones_pnd.items()})
    except Exception:  # noqa: BLE001 — cualquier falla del paquete PND solo deshabilita PND; PML sigue igual
        PND.clear()


VISTAS = {VISTAS_URL["historico"]: vista_1, VISTAS_URL["comparacion"]: vista_2, VISTAS_URL["componentes"]: vista_3}
# v0.5.1: un enlace compartido elige vista y filtros antes de que se dibujen (ver enlaces.py).
leer_url(nodos, limites)
# H07: vista y filtros en un panel con texto visible dentro del contenido, cerrado al iniciar, en vez de la
# barra lateral (en móvil quedaba sobre los resultados o como un icono sin texto). Cerrarlo no borra la selección.
# v0.5: las vistas son una barra de pestañas visible arriba; nodo, fechas y resolución siguen en el panel.
conservar_widgets()
# v0.8.1 · Una sola página: sin selección, solo el mercado (ENSEMBLE). Con un nodo o una zona elegidos (o un enlace
# con nodo, zona, vista o modalidad), su detalle aparece ARRIBA y el mismo ENSEMBLE sigue debajo. Ver escena.py.
en_solo = st.session_state["escena"] == SOLO
modo_pnd = bool(PND) and st.session_state.get("modalidad") == "pnd"
if en_solo:
    subtitulo.caption(("Precio de zona de carga (PND) · " if modo_pnd else "Precio Marginal Local · ")
                      + "Mercado del Día en Adelanto · SIN (CENACE) · MXN/MWh · datos diarios publicados, no en tiempo real")
else:
    subtitulo.caption("Mercado del Día en Adelanto · SIN (CENACE) · MXN/MWh · PML por nodo y PND por zona de carga, "
                      "por separado · datos diarios publicados, no en tiempo real")
limites_activos = PND["limites"] if modo_pnd else limites
chip.markdown(f'<a class="chip-cambiar" href="#elige-solista">Cambiar {"zona" if modo_pnd else "nodo"}</a>',
              unsafe_allow_html=True)
st.html(ALTO_BARRA_JS, unsafe_allow_javascript=True)
with barra:
    barra_controles(limites_activos, en_solo, modo_pnd)
    cinta_pnd()
# v0.8.3 · «Elige el solista» es el rail IZQUIERDO angosto, fijo al desplazarse; detalle arriba y mercado debajo, en
# la columna principal (≤ 1024 px el rail pasa al final, ver CSS). El mercado y la lista se dibujan primero en el código: si el detalle se detiene con st.stop() (sin
# datos, fechas invertidas, enlace con problemas), el tablero, la lista, la metodología y el pie siguen visibles.
# Los huecos existen siempre, en el mismo orden: abrir, cambiar o cerrar el detalle no mueve el tablero de lugar
# y Streamlit no vuelve a montar sus gráficas.
enfocar_detalle(st.empty())
with st.container(key="shell"):
    rail, principal = st.columns([1, 5], gap="small")  # anchos reales en CSS: rail 172–200 px, principal el resto
with principal:
    detalle = st.container(key=f"detalle_{'pnd' if modo_pnd else 'pml'}") if en_solo else st.empty()
    mercado = st.container()
metodologia_ensemble()
metodologia()
if PND:
    metodologia_pnd()
if PND and not en_solo:
    lp = PND["limites"]
    st.caption(f"PML Explorer {VERSION_APP} · PML: esquema v{metadata()['version_esquema']}, {limites['desde']} a "
               f"{limites['hasta']}, actualización {actualizado_cdmx(limites['generado_utc'])} · PND: contrato v1, "
               f"{lp['desde']} a {lp['hasta']} ({lp['zonas']} zonas), actualización "
               f"{actualizado_cdmx(lp['generado_utc'])} · Ciudad de México.")
elif modo_pnd:
    lp = PND["limites"]
    st.caption(f"PML Explorer {VERSION_APP} · PND: contrato v1 · Fechas de operación disponibles: {lp['desde']} a "
               f"{lp['hasta']} ({lp['zonas']} zonas de carga) · Actualización del paquete PND: "
               f"{actualizado_cdmx(lp['generado_utc'])}, Ciudad de México · Fuente: CENACE SW-PEND, MDA, SIN.")
else:
    st.caption(f"PML Explorer {VERSION_APP} · Datos: esquema v{metadata()['version_esquema']} · "
               f"Fechas de operación disponibles: {limites['desde']} a {limites['hasta']} (diario); "
               f"{limites['horario_desde']} a {limites['horario_hasta']} (horario). "
               f"Actualización del paquete: {actualizado_cdmx(limites['generado_utc'])}, Ciudad de México."
               + (f" · Nombres y ubicación: Catálogo de NodosP de CENACE, versión "
                  f"{UBICACION['manifiesto']['version_catalogo']}." if UBICACION else ""))
with mercado:
    vista_ensemble(limites, nodos, version, con_detalle=en_solo)
with rail:
    atril(nodos, limites, version, con_detalle=en_solo)
if en_solo:
    with detalle:
        with st.container(key="cierre", horizontal=True, gap="medium", vertical_alignment="center"):
            st.button("Cerrar detalle", key="volver", icon=":material/close:", on_click=volver_al_mercado,
                      help="Deja solo el tablero ENSEMBLE, con las mismas fechas, resolución y selección.")
            with st.container(key="pestanas"):
                if modo_pnd:
                    st.markdown("**Precio de zona de carga (PND)** · histórico por zona")
                else:
                    vista = st.radio("Vista", list(VISTAS), key="vista", horizontal=True,
                                     label_visibility="collapsed", format_func=lambda v: v.split(". ", 1)[1])
        # Si el enlace trae problemas, el panel abre solo para corregirlos.
        panel = st.expander("Vista y filtros", expanded=st.session_state["panel_abierto"])
        if modo_pnd:
            vista_pnd(panel)
        else:
            VISTAS[vista](limites, nodos, fechas_nodo, version, panel)
