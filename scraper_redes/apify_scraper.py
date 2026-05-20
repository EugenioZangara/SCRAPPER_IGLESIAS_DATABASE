import os
from datetime import datetime, timezone


def get_client():
    from apify_client import ApifyClient

    token = os.environ.get("APIFY_API_TOKEN")
    if not token:
        raise ValueError("APIFY_API_TOKEN no está configurado.")
    return ApifyClient(token)


def normalizar_url_instagram(url: str) -> str:
    """
    Normaliza una URL de Instagram para que sea válida para Apify.
    - Asegura https://www.instagram.com/
    - Elimina parámetros (?hl=es, etc.)
    - Elimina trailing slashes extras
    """
    from urllib.parse import urlparse

    parsed = urlparse(url)
    # Extraer solo el path limpio
    path = parsed.path.rstrip("/")
    # Reconstruir URL limpia
    return f"https://www.instagram.com{path}/"


def scrapear_perfil_apify(url: str, limite: int = 5) -> list[dict]:
    """
    Scrapea un perfil de Instagram usando Apify.
    Retorna lista de dicts compatible con el formato de instagram.py.
    """
    print(f"  [Apify] Scrapeando: {url}")
    client = get_client()
    url_limpia = normalizar_url_instagram(url)
    print(f"  [Apify] Scrapeando: {url_limpia}")
    run_input = {
    "directUrls": [url_limpia],
        
        "resultsType": "posts",
        "resultsLimit": limite,
    }

    try:
        run = client.actor("apify/instagram-scraper").call(run_input=run_input)

        if run["status"] != "SUCCEEDED":
            print(f"  [Apify] ERROR: run status = {run['status']}")
            return []

        items = list(client.dataset(run["defaultDatasetId"]).iterate_items())
        print(f"  [Apify] {len(items)} posts obtenidos")

        resultados = []
        for item in items:
            # Parsear timestamp
            ts_str = item.get("timestamp", "")
            try:
                fecha = datetime.fromisoformat(
                    ts_str.replace("Z", "+00:00")
                ).astimezone(timezone.utc)
            except Exception:
                fecha = datetime.now(timezone.utc)

            resultados.append(
                {
                    "post_id": item.get("shortCode", ""),
                    "imagen_url": item.get("displayUrl", ""),
                    "caption": (item.get("caption") or "")[:200],
                    "fecha": fecha,
                    "raw_data": {
                        "shortcode": item.get("shortCode", ""),
                        "likes": item.get("likesCount", 0),
                        "fecha": ts_str,
                        "caption": item.get("caption", ""),
                        "tipo": item.get("type", ""),
                        "location": item.get("locationName", ""),
                    },
                }
            )

        return resultados

    except Exception as e:
        print(f"  [Apify] ERROR inesperado: {e}")
        return []
