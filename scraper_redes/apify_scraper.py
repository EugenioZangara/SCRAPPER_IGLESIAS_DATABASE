import os
import httpx
from datetime import datetime, timezone

APIFY_BASE = "https://api.apify.com/v2"


def normalizar_url_instagram(url: str) -> str:
    from urllib.parse import urlparse

    parsed = urlparse(url)
    path = parsed.path.rstrip("/")
    return f"https://www.instagram.com{path}/"


def scrapear_perfil_apify(url: str, limite: int = 5) -> list[dict]:
    token = os.environ.get("APIFY_API_TOKEN")
    if not token:
        raise ValueError("APIFY_API_TOKEN no está configurado.")

    url_limpia = normalizar_url_instagram(url)
    print(f"  [Apify] Scrapeando: {url_limpia}")

    headers = {"Authorization": f"Bearer {token}"}

    try:
        # Iniciar el run
        run_input = {
            "directUrls": [url_limpia],
            "resultsType": "posts",
            "resultsLimit": limite,
        }
        resp = httpx.post(
            f"{APIFY_BASE}/acts/apify~instagram-scraper/runs",
            json=run_input,
            headers=headers,
            timeout=30,
        )
        resp.raise_for_status()
        run_id = resp.json()["data"]["id"]
        dataset_id = resp.json()["data"]["defaultDatasetId"]

        # Esperar que termine
        import time

        for _ in range(60):  # máximo 5 minutos
            time.sleep(5)
            status_resp = httpx.get(
                f"{APIFY_BASE}/actor-runs/{run_id}",
                headers=headers,
                timeout=15,
            )
            status = status_resp.json()["data"]["status"]
            if status == "SUCCEEDED":
                break
            elif status in ("FAILED", "ABORTED", "TIMED-OUT"):
                print(f"  [Apify] Run terminó con estado: {status}")
                return []

        # Obtener resultados
        items_resp = httpx.get(
            f"{APIFY_BASE}/datasets/{dataset_id}/items",
            params={"format": "json", "limit": limite},
            headers=headers,
            timeout=30,
        )
        items_resp.raise_for_status()
        items = items_resp.json()

        print(f"  [Apify] {len(items)} posts obtenidos")

        resultados = []
        for item in items:
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
