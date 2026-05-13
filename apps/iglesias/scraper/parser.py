import re
from bs4 import BeautifulSoup


def extract_all_parishes(html_content):
    soup = BeautifulSoup(html_content, "html.parser")
    results = []

    table = soup.find("table", id="tablaparr") or soup.find("table")
    if not table:
        return []

    rows = table.find_all("tr")

    for row in rows:
        # Extraemos TODO el texto de la fila para procesarlo
        full_text = row.get_text(" ", strip=True)

        # 1. Extraer el ID del formulario (esto suele estar intacto en el HTML)
        input_id = row.find("input", {"name": "codigo"})
        if not input_id:
            continue
        parish_id = int(input_id["value"])

        # 2. Extraer Mails con Regex
        # Buscamos patrones de correos electrónicos dentro del texto de la fila
        mails = re.findall(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", full_text)

        mail_1 = mails[0].lower() if len(mails) > 0 else None
        mail_2 = mails[1].lower() if len(mails) > 1 else None

        # 3. Limpiar el Nombre
        # El texto suele empezar con el ID, luego el Nombre y luego los mails.
        # Quitamos el ID del principio y cortamos antes de que aparezca el primer mail.
        nombre_sucio = full_text.replace(str(parish_id), "", 1).strip()

        if mail_1:
            # Cortamos el string justo donde empieza el primer mail para quedarnos solo con el nombre
            # eliminar mails del texto directamente
            for mail in mails:
                nombre_sucio = nombre_sucio.replace(mail, "")

            nombre = nombre_sucio.replace("Ver", "").strip()
        else:
            # Si no hay mail, buscamos la palabra "Ver" que suele estar al final
            nombre = nombre_sucio.split("Ver")[0].strip()

        # 4. Extraer Sitio Web
        web_tag = row.find("a", href=re.compile(r"http"))
        # Evitamos capturar el mailto como web
        sitio = None
        if web_tag and "mailto" not in web_tag["href"]:
            sitio = web_tag["href"]

        print(
            f"LOG -> ID: {parish_id} | Nombre: {nombre} | M1: {mail_1} | M2: {mail_2}"
        )

        results.append(
            {
                "id_externo": parish_id,
                "nombre": nombre,
                "mail_1": mail_1,
                "mail_2": mail_2,
                "sitio_web": sitio,
                "url_detalle": f"listparrdetalle.php?codigo={parish_id}",
            }
        )

    return results
