import os
import httpx
import time
from datetime import datetime, timezone

APIFY_BASE = "https://api.apify.com/v2"


def normalizar_url_instagram(url: str) -> str:
    from urllib.parse import urlparse

    parsed = urlparse(url)
    path = parsed.path.rstrip("/")
    return f"https://www.instagram.com{path}/"


def _get_apify_tokens() -> list:
    tokens = []
    t1 = os.environ.get("APIFY_API_TOKEN")
    t2 = os.environ.get("APIFY_API_TOKEN_2")
    if t1:
        tokens.append(t1)
    if t2:
        tokens.append(t2)
    return tokens


def scrapear_perfil_apify(url: str, limite: int = 5) -> list[dict]:
    """
    Scrapea posts de un perfil de Instagram usando Apify.
    Intenta con APIFY_API_TOKEN y si da 403 reintenta con APIFY_API_TOKEN_2.
    """
    tokens = _get_apify_tokens()
    if not tokens:
        raise ValueError("APIFY_API_TOKEN no está configurado.")

    url_limpia = normalizar_url_instagram(url)
    print(f"  [Apify] Scrapeando: {url_limpia}")

    run_input = {
        "directUrls": [url_limpia],
        "resultsType": "posts",
        "resultsLimit": limite,
    }

    token_usado = None
    run_id = None
    dataset_id = None
    last_error = None

    for token in tokens:
        headers = {"Authorization": f"Bearer {token}"}
        try:
            resp = httpx.post(
                f"{APIFY_BASE}/acts/apify~instagram-scraper/runs",
                json=run_input,
                headers=headers,
                timeout=30,
            )
            if resp.status_code == 403:
                print(f"  [Apify] Token agotado, intentando siguiente...")
                last_error = "403 Forbidden"
                continue
            resp.raise_for_status()
            run_id = resp.json()["data"]["id"]
            dataset_id = resp.json()["data"]["defaultDatasetId"]
            token_usado = token
            break
        except Exception as e:
            last_error = str(e)
            if "403" in str(e):
                print(f"  [Apify] Token agotado, intentando siguiente...")
                continue
            raise

    if not token_usado:
        print(f"  [Apify] Todos los tokens fallaron: {last_error}")
        return []

    try:
        headers = {"Authorization": f"Bearer {token_usado}"}

        # Esperar que termine
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
                        "url_post": f"https://www.instagram.com/p/{item.get('shortCode', '')}/",
                    },
                }
            )

        return resultados

    except Exception as e:
        print(f"  [Apify] ERROR inesperado: {e}")
        return []
