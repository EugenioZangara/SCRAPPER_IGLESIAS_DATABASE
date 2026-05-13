# Headers para evitar ser bloqueados
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36'
}
BASE_URL = "https://www.arzbaires.org.ar/inicio/"
LIST_URL = f"{BASE_URL}listparrweb.php"

import requests


def validar_web(url):
    try:
        if not url:
            return False

        # normalizar (por si falta http)
        if not url.startswith("http"):
            url = "http://" + url

        response = requests.get(url, headers=HEADERS, timeout=5, allow_redirects=True)

        # validamos que sea una web real
        if response.status_code == 200 and len(response.text) > 500:
            return True

        return False

    except Exception:
        return False
