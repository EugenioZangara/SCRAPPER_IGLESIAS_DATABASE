import httpx
from bs4 import BeautifulSoup
import re


def fetch_pagina(url: str) -> BeautifulSoup | None:
    """Descarga y parsea la página de baiglesias."""
    try:
        response = httpx.get(url, timeout=15, follow_redirects=True)
        response.raise_for_status()
        return BeautifulSoup(response.text, "html.parser")
    except Exception as e:
        print(f"  ERROR al descargar {url}: {e}")
        return None


def _detectar_heading_horarios(content):
    """
    Devuelve el tag h2/h3 cuyo texto es exactamente 'Horarios' (Estructura B),
    o None si no existe (Estructura A).
    La comparación es estricta para no matchear 'Información de Contacto y Horarios'.
    """
    for tag in content.find_all(["h2", "h3"]):
        if tag.get_text().strip().lower() == "horarios":
            return tag
    return None


def _extraer_horarios_estructura_a(content) -> tuple[list, str | None]:
    """
    Estructura A: lista plana con un item 'Misas:' seguido de sub-items por día.
    Ejemplo: parroquia-asuncion-de-la-santisima-virgen
    """
    nota_misas = None
    horarios = []
    en_misas = False

    for li in content.find_all("li"):
        texto = li.get_text(separator=" ").strip()
        texto_lower = texto.lower()

        if texto_lower.startswith("dirección:") or texto_lower.startswith("direccion:"):
            en_misas = False

        elif "cómo llegar" in texto_lower or "como llegar" in texto_lower:
            en_misas = False

        elif texto_lower.startswith("misas:"):
            contenido_misas = texto.split(":", 1)[1].strip()
            lineas = contenido_misas.split("\n")
            nota_lineas = []
            for linea in lineas:
                linea = linea.strip()
                if linea and ":" not in linea:
                    nota_lineas.append(linea)
                elif linea and not re.search(r"\d{1,2}:\d{2}", linea):
                    nota_lineas.append(linea)
            nota_misas = " ".join(nota_lineas).strip() or None
            en_misas = True

        elif (
            en_misas
            and ":" in texto
            and not texto_lower.startswith("tel")
            and not texto_lower.startswith("mail")
        ):
            partes = texto.split(":", 1)
            if len(partes) == 2:
                dias = partes[0].strip()
                horario = partes[1].strip()
                if horario and len(dias) < 60:
                    horarios.append({"dias": dias, "horarios": horario, "nota": nota_misas})
                    nota_misas = None

        else:
            en_misas = False

    return horarios, nota_misas


def _extraer_horarios_estructura_b(heading_horarios) -> list:
    """
    Estructura B: heading 'Horarios' seguido de un ul con sub-items como
    Apertura, Secretaría, Confesiones, Misa. Solo se captura el sub-item 'Misa'.
    Ejemplo: parroquia-del-buen-pastor
    """
    horarios = []

    # Buscar el primer ul hermano del heading (antes del próximo heading)
    sibling = heading_horarios.next_sibling
    ul_horarios = None
    while sibling:
        if hasattr(sibling, "name"):
            if sibling.name == "ul":
                ul_horarios = sibling
                break
            elif sibling.name in ["h1", "h2", "h3", "h4"]:
                break
        sibling = sibling.next_sibling

    if not ul_horarios:
        return horarios

    # Buscar el li directo que empiece con "misa" (ignorar Apertura, Secretaría, etc.)
    for li in ul_horarios.find_all("li", recursive=False):
        if li.get_text(separator=" ").strip().lower().startswith("misa"):
            sub_ul = li.find("ul")
            if sub_ul:
                for sub_li in sub_ul.find_all("li"):
                    texto = sub_li.get_text(separator=" ").strip()
                    if ":" in texto:
                        partes = texto.split(":", 1)
                        dias = partes[0].strip()
                        horario = partes[1].strip()
                        if horario and len(dias) < 60:
                            horarios.append({"dias": dias, "horarios": horario, "nota": None})
            break

    return horarios


def extraer_info(soup: BeautifulSoup, url: str) -> dict:
    """
    Extrae información de contacto, horarios y cómo llegar
    de una página de baiglesias.com. Maneja dos estructuras:
    - Estructura A: lista plana con 'Misas:' (sin heading 'Horarios' exacto)
    - Estructura B: heading 'Horarios' con sub-items Apertura/Misa/etc.
    """
    resultado = {
        "url": url,
        "direccion_completa": None,
        "como_llegar": None,
        "horarios": [],
        "nota_misas": None,
    }

    content = soup.find("div", class_="entry-content") or soup.find("article")
    if not content:
        print("  ERROR: No se encontró el contenido principal")
        return resultado

    # Extraer dirección y cómo llegar (igual en ambas estructuras)
    for li in content.find_all("li"):
        texto = li.get_text(separator=" ").strip()
        texto_lower = texto.lower()

        if texto_lower.startswith("dirección:") or texto_lower.startswith("direccion:"):
            resultado["direccion_completa"] = texto.split(":", 1)[1].strip()

        elif "cómo llegar" in texto_lower or "como llegar" in texto_lower:
            resultado["como_llegar"] = (
                texto.split(":", 1)[1].strip() if ":" in texto else texto
            )

    # Detectar estructura y extraer horarios
    heading_horarios = _detectar_heading_horarios(content)

    if heading_horarios:
        resultado["horarios"] = _extraer_horarios_estructura_b(heading_horarios)
    else:
        resultado["horarios"], resultado["nota_misas"] = _extraer_horarios_estructura_a(content)

    return resultado


def scrapear_baiglesias(url: str) -> dict | None:
    """
    Función principal: descarga y extrae info de una URL de baiglesias.com.
    """
    print(f"  Scrapeando: {url}")
    soup = fetch_pagina(url)
    if not soup:
        return None
    return extraer_info(soup, url)
