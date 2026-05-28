import os
import httpx
import time
from datetime import datetime, timezone
from urllib.parse import urlparse

APIFY_BASE = "https://api.apify.com/v2"


def normalizar_url_facebook(url: str) -> str:
    """Normaliza URLs de Facebook eliminando parámetros y locale."""
    parsed = urlparse(url)
    netloc = "www.facebook.com"
    path = parsed.path.rstrip("/")
    return f"https://{netloc}{path}"


def _get_apify_tokens() -> list:
    tokens = []
    t1 = os.environ.get("APIFY_API_TOKEN")
    t2 = os.environ.get("APIFY_API_TOKEN_2")
    if t1:
        tokens.append(t1)
    if t2:
        tokens.append(t2)
    return tokens


def scrapear_perfil_facebook(url: str, limite: int = 5) -> list[dict]:
    """
    Scrapea posts de una página de Facebook usando Apify.
    Retorna lista de dicts compatible con el formato del pipeline.
    Intenta con APIFY_API_TOKEN y si da 403 reintenta con APIFY_API_TOKEN_2.
    """
    tokens = _get_apify_tokens()
    if not tokens:
        raise ValueError("No hay APIFY_API_TOKEN configurado.")

    url_limpia = normalizar_url_facebook(url)
    print(f"  [Apify FB] Scrapeando: {url_limpia}")

    run_input = {
        "startUrls": [{"url": url_limpia}],
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
                f"{APIFY_BASE}/acts/apify~facebook-posts-scraper/runs",
                json=run_input,
                headers=headers,
                timeout=30,
            )
            if resp.status_code == 403:
                print(f"  [Apify FB] Token agotado, intentando siguiente...")
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
                print(f"  [Apify FB] Token agotado, intentando siguiente...")
                continue
            raise

    if not token_usado:
        print(f"  [Apify FB] Todos los tokens fallaron: {last_error}")
        return []

    try:
        headers = {"Authorization": f"Bearer {token_usado}"}

        # Esperar que termine
        for _ in range(60):
            time.sleep(5)
            status = httpx.get(
                f"{APIFY_BASE}/actor-runs/{run_id}",
                headers=headers,
                timeout=15,
            ).json()["data"]["status"]
            if status == "SUCCEEDED":
                break
            elif status in ("FAILED", "ABORTED", "TIMED-OUT"):
                print(f"  [Apify FB] Run terminó con estado: {status}")
                return []

        items_resp = httpx.get(
            f"{APIFY_BASE}/datasets/{dataset_id}/items",
            params={"format": "json", "limit": limite},
            headers=headers,
            timeout=30,
        )
        items_resp.raise_for_status()
        items = items_resp.json()

        # Filtrar errores
        items = [i for i in items if not i.get("error")]
        print(f"  [Apify FB] {len(items)} posts obtenidos")

        resultados = []
        for item in items:
            # Extraer imagen
            imagen_url = ""
            media = item.get("media", [])
            if media:
                imagen_url = media[0].get("photo_image", {}).get("uri", "") or media[
                    0
                ].get("thumbnail", "")

            # Parsear fecha
            ts_str = item.get("time", "")
            try:
                fecha = datetime.fromisoformat(
                    ts_str.replace("Z", "+00:00")
                ).astimezone(timezone.utc)
            except Exception:
                fecha = datetime.now(timezone.utc)

            # Solo incluir posts con imagen o texto
            caption = item.get("text", "") or ""
            if not imagen_url and not caption:
                continue

            resultados.append(
                {
                    "post_id": item.get("postId", ""),
                    "imagen_url": imagen_url,
                    "caption": caption[:200],
                    "fecha": fecha,
                    "raw_data": {
                        "shortcode": item.get("postId", ""),
                        "likes": item.get("likes", 0),
                        "fecha": ts_str,
                        "caption": caption,
                        "url_post": item.get("url", ""),
                        "red_social": "facebook",
                    },
                }
            )

        return resultados

    except Exception as e:
        print(f"  [Apify FB] ERROR inesperado: {e}")
        return []
