"""
descarga_establecimientos.py
=============================
Descarga los establecimientos educativos con NIVEL ESCOLAR = DIVERSIFICADO
del portal del MINEDUC (Guatemala) y guarda los datos CRUDOS en .csv.

USO
---
    python descarga_establecimientos.py

Salidas:
    data/raw/diversificado_<DEPARTAMENTO>.csv   (un archivo por departamento)
    data/diversificado_consolidado.csv      (todo el país, crudo)

"""

from __future__ import annotations
import os
import re
import time
from pathlib import Path

import pandas as pd
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

# ----------------------------------------------------------------------------
BASE_URL = "http://www.mineduc.gob.gt/BUSCAESTABLECIMIENTO_GE/"
# Rutas relativas al directorio desde donde se ejecuta el script
DATA_DIR = Path.cwd() / "data"
OUT_DIR = DATA_DIR / "raw"                    # .xls y CSV por departamento
OUT_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR.mkdir(parents=True, exist_ok=True)

NIVEL_OBJETIVO = "DIVERSIFICADO"
HEADLESS = os.environ.get("HEADLESS", "1") != "0"   # HEADLESS=0 para ver el navegador
TIMEOUT_MS = 60_000

# Palabras que identifican la tabla de RESULTADOS
ENCABEZADOS_ESPERADOS = {
    "codigo", "establecimiento", "departamento", "municipio", "direccion",
    "nivel", "sector", "distrito", "director", "telefono", "jornada", "plan",
    "area", "status", "modalidad", "supervisor", "nombre",
}


# ----------------------------------------------------------------------------
# Extracción de la tabla de resultados
# ----------------------------------------------------------------------------
def _norm(s: str) -> str:
    s = re.sub(r"\s+", " ", str(s)).strip().lower()
    return "".join(c for c in s if c.isalnum() or c == " ")


def parse_results_table(html: str) -> pd.DataFrame:
    """Devuelve la tabla cuyo encabezado coincide con columnas de establecimientos."""
    soup = BeautifulSoup(html, "html.parser")
    mejor, mejor_score = None, 0
    for t in soup.find_all("table"):
        filas = t.find_all("tr")
        if len(filas) < 2:
            continue
        cabeza = filas[0].find_all(["th", "td"])
        textos = {_norm(c.get_text()) for c in cabeza}
        score = sum(any(k in tx for k in ENCABEZADOS_ESPERADOS) for tx in textos)
        if score >= 2 and (score > mejor_score or
                            (mejor is not None and len(filas) > len(mejor.find_all("tr")))):
            mejor, mejor_score = t, score
    if mejor is None:
        return pd.DataFrame()

    filas = []
    for tr in mejor.find_all("tr"):
        celdas = [re.sub(r"\s+", " ", td.get_text(" ", strip=True))
                  for td in tr.find_all(["td", "th"])]
        if celdas:
            filas.append(celdas)
    enc = filas[0]
    ancho = len(enc)
    cuerpo = [f for f in filas[1:] if len(f) == ancho]
    return pd.DataFrame(cuerpo, columns=enc)


# ----------------------------------------------------------------------------
# Descubrimiento de controles del formulario por su contenido
# ----------------------------------------------------------------------------
def encontrar_select(page, palabras_clave: list[str]):
    """Devuelve el ElementHandle del <select> cuyas opciones contienen las palabras."""
    claves = [k.upper() for k in palabras_clave]
    for sel in page.query_selector_all("select"):
        textos = [(o.inner_text() or "").upper() for o in sel.query_selector_all("option")]
        if all(any(k in t for t in textos) for k in claves):
            return sel
    raise RuntimeError(f"No encontré un <select> con opciones {palabras_clave}")


def opciones_de(sel) -> list[str]:
    return [(o.inner_text() or "").strip() for o in sel.query_selector_all("option")]


def dump_controles(page):
    """Imprime todos los controles clicables (para identificar el botón Buscar)."""
    print("\n  --- CONTROLES ENCONTRADOS EN LA PÁGINA ---")
    for inp in page.query_selector_all("input"):
        tipo = (inp.get_attribute("type") or "text")
        if tipo.lower() in ("submit", "image", "button"):
            print(f"  <input type={tipo!r} "
                  f"id={inp.get_attribute('id')!r} name={inp.get_attribute('name')!r} "
                  f"value={inp.get_attribute('value')!r} alt={inp.get_attribute('alt')!r} "
                  f"src={inp.get_attribute('src')!r} visible={inp.is_visible()}>")
    for b in page.query_selector_all("button"):
        print(f"  <button id={b.get_attribute('id')!r} name={b.get_attribute('name')!r} "
              f"text={(b.inner_text() or '').strip()!r} visible={b.is_visible()}>")
    for a in page.query_selector_all("a[href*='doPostBack']"):
        print(f"  <a text={(a.inner_text() or '').strip()!r} "
              f"href={(a.get_attribute('href') or '')[:70]!r}>")
    print("  --- FIN ---\n")


def clic_buscar(page, diagnosticar=True):
    """Presiona el botón Buscar probando varias estrategias (incluye botón de imagen)."""
    estrategias = [
        # Botón real del portal (identificado): imagen 'seleccionar_estab.gif', id ...IbtnConsultar
        "input[type=image][id*='IbtnConsultar']",
        "input[type=image][id*='Consultar' i]",
        "input[type=image][src*='seleccionar_estab' i]",
        "input[name*='IbtnConsultar']",
        # respaldos genéricos
        "input[type=submit][value*='Buscar' i]",
        "input[type=image][alt*='Buscar' i]",
        "input[type=image][src*='busc' i]",
        "button:has-text('Buscar')",
        "a[href*='doPostBack']:has-text('Buscar')",
    ]
    for sel in estrategias:
        try:
            loc = page.locator(sel).first
            if loc.count() and loc.is_visible():
                loc.click(timeout=6000)
                return True
        except Exception:
            continue
    # Fallback: botón de acción visible que NO sea limpiar/cerrar.
    def _es_accion(el):
        meta = " ".join(str(el.get_attribute(a) or "") for a in ("id", "name", "src", "value")).lower()
        return not any(x in meta for x in ("limpiar", "cerrar", "clear"))
    candidatos = [c for c in page.query_selector_all(
        "input[type=submit], input[type=image], button")
        if c.is_visible() and _es_accion(c)]
    if len(candidatos) == 1:
        try:
            candidatos[0].click(timeout=6000)
            return True
        except Exception:
            pass
    if diagnosticar:
        dump_controles(page)   # muestra qué botón usar
    return False


def esperar_resultados(page):
    """Espera a que termine el postback y aparezca contenido de resultados."""
    try:
        page.wait_for_load_state("networkidle", timeout=TIMEOUT_MS)
    except PWTimeout:
        pass
    page.wait_for_timeout(1200)


# ----------------------------------------------------------------------------
# Paginación (GridView de ASP.NET)
# ----------------------------------------------------------------------------
def ir_a_siguiente_pagina(page, pagina_actual: int) -> bool:
    """Hace clic en el enlace de la página siguiente si existe. Devuelve True si avanzó."""
    objetivo = str(pagina_actual + 1)
    # 1) enlace cuyo texto es exactamente el número siguiente
    for a in page.query_selector_all("a"):
        txt = (a.inner_text() or "").strip()
        if txt == objetivo and "doPostBack" in (a.get_attribute("href") or ""):
            try:
                a.click(); esperar_resultados(page); return True
            except Exception:
                pass
    # 2) enlace ">" o "Siguiente" (cuando hay más de 10 páginas)
    for a in page.query_selector_all("a"):
        txt = (a.inner_text() or "").strip().lower()
        if txt in (">", "»", "siguiente", "...") and "doPostBack" in (a.get_attribute("href") or ""):
            try:
                a.click(); esperar_resultados(page); return True
            except Exception:
                pass
    return False


# ----------------------------------------------------------------------------
# Botón de exportar a Excel (el portal ofrece descargar los resultados)
# ----------------------------------------------------------------------------
EXPORT_KEYS = ("excel", "xls", "export", "exportar", "descargar", "descarga")

def encontrar_export(page):
    """Ubica el control que descarga el Excel de resultados (evita limpiar/cerrar)."""
    sels = "input[type=image], input[type=submit], input[type=button], button, a"
    for el in page.query_selector_all(sels):
        if not el.is_visible():
            continue
        meta = " ".join(str(el.get_attribute(a) or "")
                        for a in ("id", "name", "src", "value", "alt", "href", "title"))
        blob = (meta + " " + (el.inner_text() or "")).lower()
        if any(k in blob for k in EXPORT_KEYS) and not any(
                x in blob for x in ("limpiar", "cerrar", "clear")):
            return el
    return None


CANON = ["CODIGO", "DISTRITO", "DEPARTAMENTO", "MUNICIPIO", "ESTABLECIMIENTO",
         "DIRECCION", "TELEFONO", "SUPERVISOR", "DIRECTOR", "NIVEL", "SECTOR",
         "AREA", "STATUS", "MODALIDAD", "JORNADA", "PLAN", "DEPARTAMENTAL"]


def leer_tabla_archivo(path: Path) -> pd.DataFrame:
    """
    Lee el Excel/HTML descargado. El portal entrega un .xls que en realidad es una
    tabla HTML con basura arriba (título/formulario) y abajo ('N encontrados' + fila
    vacía). Detectamos la fila de encabezados reales y nos quedamos solo con las filas
    cuyo CODIGO tiene formato ##-##-####-##.
    """
    html = Path(path).read_text("latin-1", errors="replace")
    soup = BeautifulSoup(html, "html.parser")
    filas = []
    for tr in soup.find_all("tr"):
        celdas = [re.sub(r"\s+", " ", td.get_text(" ", strip=True))
                  for td in tr.find_all(["td", "th"])]
        if len(celdas) == len(CANON):        # filas reales (encabezado + datos)
            filas.append(celdas)
    if not filas:
        return pd.DataFrame()
    hi = next((i for i, f in enumerate(filas)
               if "CODIGO" in [c.upper() for c in f]
               and "ESTABLECIMIENTO" in [c.upper() for c in f]), None)
    if hi is not None:
        cols, datos = [c.upper() for c in filas[hi]], filas[hi + 1:]
    else:
        cols, datos = CANON, filas
    df = pd.DataFrame(datos, columns=cols)
    codcol = df.columns[0]
    df = df[df[codcol].str.match(r"^\d{2}-\d{2}-\d{4}-\d{2}$", na=False)].reset_index(drop=True)
    return df


# ----------------------------------------------------------------------------
# Descarga de un departamento (vía botón Excel)
# ----------------------------------------------------------------------------
def descargar_departamento(page, dep_texto, sel_dep, nivel_label) -> pd.DataFrame:
    # 1) seleccionar departamento (dispara postback que recarga municipios)
    sel_dep.select_option(label=dep_texto)
    esperar_resultados(page)

    # 2) re-ubicar el select de nivel (el postback pudo regenerar el DOM) y elegir DIVERSIFICADO
    sel_nivel = encontrar_select(page, ["DIVERSIFICADO", "BASICO"])
    sel_nivel.select_option(label=nivel_label)

    # 3) buscar
    if not clic_buscar(page):
        raise RuntimeError("No pude presionar el botón Buscar")
    esperar_resultados(page)

    safe = re.sub(r"[^A-Za-z0-9]+", "_", dep_texto).strip("_").upper()

    # 4a) camino preferido: botón de descargar Excel
    export = encontrar_export(page)
    if export is not None:
        try:
            with page.expect_download(timeout=TIMEOUT_MS) as di:
                export.click()
            descarga = di.value
            ext = Path(descarga.suggested_filename).suffix or ".xls"
            crudo = OUT_DIR / f"diversificado_{safe}{ext}"      # archivo tal cual lo da el portal
            descarga.save_as(str(crudo))
            df = leer_tabla_archivo(crudo)
            return df
        except Exception as e:
            print(f"   (falló la descarga de Excel: {e}; intento leer la tabla HTML)")

    # 4b) respaldo: parsear la tabla HTML (con paginación) si no hubo Excel
    paginas, pagina, vistas = [], 1, set()
    while True:
        d = parse_results_table(page.content())
        if not d.empty:
            paginas.append(d)
        if pagina in vistas or pagina > 500:
            break
        vistas.add(pagina)
        if not ir_a_siguiente_pagina(page, pagina):
            break
        pagina += 1
    if not paginas:
        dump_controles(page)   # para ver qué botón de descarga hay
        return pd.DataFrame()
    out = pd.concat(paginas, ignore_index=True).drop_duplicates()
    return out


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=HEADLESS)
        page = browser.new_page()
        page.set_default_timeout(TIMEOUT_MS)
        print("→ Abriendo el portal…")
        page.goto(BASE_URL, wait_until="domcontentloaded")
        page.wait_for_timeout(1500)

        sel_dep = encontrar_select(page, ["GUATEMALA", "ZACAPA", "PETEN"])
        sel_nivel = encontrar_select(page, ["DIVERSIFICADO", "BASICO"])

        # etiqueta exacta de la opción DIVERSIFICADO tal como aparece en el <select>
        nivel_label = next(o for o in opciones_de(sel_nivel) if NIVEL_OBJETIVO in o.upper())

        departamentos = [d for d in opciones_de(sel_dep)
                         if d and "SELECCIONE" not in d.upper() and d.upper() != "TODOS"]
        print(f"  Departamentos a recorrer: {len(departamentos)}")
        print(f"  Nivel objetivo: '{nivel_label}'\n")

        consolidado = []
        for dep in departamentos:
            print(f"→ {dep} …", end=" ", flush=True)
            try:
                df = descargar_departamento(page, dep, sel_dep, nivel_label)
            except Exception as e:
                print(f"ERROR: {e}")
                try:
                    page.screenshot(path=str(OUT_DIR / f"_error_{re.sub(r'[^A-Za-z]+','_',dep)}.png"))
                except Exception:
                    pass
                # recargamos para el siguiente departamento
                page.goto(BASE_URL, wait_until="domcontentloaded"); page.wait_for_timeout(1200)
                sel_dep = encontrar_select(page, ["GUATEMALA", "ZACAPA", "PETEN"])
                continue

            if df.empty:
                print("0 filas")
            else:
                print(f"{len(df)} filas")
                safe = re.sub(r"[^A-Za-z0-9]+", "_", dep).strip("_").upper()
                df.to_csv(OUT_DIR / f"diversificado_{safe}.csv", index=False, encoding="utf-8-sig")
                consolidado.append(df)

            # volver al formulario limpio para el siguiente departamento
            page.goto(BASE_URL, wait_until="domcontentloaded"); page.wait_for_timeout(1000)
            sel_dep = encontrar_select(page, ["GUATEMALA", "ZACAPA", "PETEN"])

        browser.close()

    if consolidado:
        full = pd.concat(consolidado, ignore_index=True)
        full.to_csv(DATA_DIR / "diversificado_consolidado.csv", index=False, encoding="utf-8-sig")
        print(f"\n Consolidado: {len(full)} filas, {full.shape[1]} columnas")
        print(f"   {DATA_DIR / 'diversificado_consolidado.csv'}")
    else:
        print("\n  No se obtuvieron datos. Probá con  HEADLESS=0  para ver qué pasa,")
        print("    o usá el FALLBACK manual (ver final del archivo).")


if __name__ == "__main__":
    main()
