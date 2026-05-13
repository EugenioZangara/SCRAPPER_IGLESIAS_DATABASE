import requests
from bs4 import BeautifulSoup
from .config import BASE_URL, HEADERS

DETAIL_URL = BASE_URL + "listparrdetalle.php"


def fetch_detalle(parroquia_id):
    response = requests.post(DETAIL_URL, data={"codigo": parroquia_id}, headers=HEADERS)
    response.raise_for_status()
    return response.text


def parse_detalle(html):
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    data = {}

    bloques = soup.select("ul.list-inline")

    for ul in bloques:
        items = ul.find_all("li")

        if len(items) < 2:
            continue

        label = items[0].get_text(strip=True)
        value = items[1].get_text(strip=True)

        if "Dirección" in label:
            data["direccion"] = value

        elif "Código Postal" in label:
            data["codigo_postal"] = value

        elif "Teléfonos" in label:
            data["telefonos"] = value

        elif "Vicaria" in label:
            # este bloque tiene múltiples valores
            textos = [li.get_text(strip=True) for li in items]

            try:
                data["vicaria"] = textos[1]
                data["decanato"] = textos[3]
                data["barrio"] = textos[5]
            except:
                pass

    # mails
    mails = soup.select("a[href^=mailto]")
    if len(mails) > 0:
        data["mail_1"] = mails[0].text.strip()
    if len(mails) > 1:
        data["mail_2"] = mails[1].text.strip()

    # parroco (BOTÓN, no <a>)
    parroco = soup.find(string=lambda x: x and "PARROCO:" in x)
    if parroco:
        btn = parroco.find_next("button")
        if btn:
            data["parroco"] = btn.text.strip()

    # límite parroquial
    limite = soup.find(string=lambda x: x and "LIMITE PARROQUIAL" in x)
    if limite:
        p = limite.find_next("p")
        if p:
            data["limite_parroquial"] = p.text.strip()

    return data


from apps.iglesias.models import Parroquia
import time


def completar_detalles():
    parroquias = Parroquia.objects.filter(detalles_completos=False)

    for p in parroquias:
        try:
            print(f"Procesando {p.nombre}")

            html = fetch_detalle(p.id_externo)
            data = parse_detalle(html)

            for key, value in data.items():
                setattr(p, key, value)

            p.detalles_completos = True
            p.save()

            time.sleep(0.5)

        except Exception as e:
            print(f"Error en {p.nombre}: {e}")
