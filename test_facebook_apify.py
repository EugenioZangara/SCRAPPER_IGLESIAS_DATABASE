import os, httpx, time, json

with open(".env", encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip())

token = os.environ["APIFY_API_TOKEN"]
headers = {"Authorization": f"Bearer {token}"}
BASE = "https://api.apify.com/v2"

# Probar con una página de Facebook conocida
run_input = {
    "startUrls": [{"url": "https://www.facebook.com/parroquianjesus"}],
    "resultsLimit": 3,
}

print("Iniciando scraping Facebook con Apify...")
resp = httpx.post(
    f"{BASE}/acts/apify~facebook-posts-scraper/runs",
    json=run_input,
    headers=headers,
    timeout=30,
)
print(f"Status: {resp.status_code}")
data = resp.json()

if resp.status_code != 201:
    print(f"ERROR: {data}")
else:
    run_id = data["data"]["id"]
    dataset_id = data["data"]["defaultDatasetId"]
    print(f"Run ID: {run_id}")

    # Esperar resultado
    for _ in range(24):
        time.sleep(5)
        status = httpx.get(
            f"{BASE}/actor-runs/{run_id}", headers=headers, timeout=15
        ).json()["data"]["status"]
        print(f"  Estado: {status}")
        if status == "SUCCEEDED":
            break
        elif status in ("FAILED", "ABORTED"):
            print("Falló")
            break

    items = httpx.get(
        f"{BASE}/datasets/{dataset_id}/items",
        params={"format": "json", "limit": 3},
        headers=headers,
        timeout=30,
    ).json()

    print(f"\nPosts obtenidos: {len(items)}")
    if items:
        print("\nEstructura del primer post:")
        print(json.dumps(items[0], indent=2, ensure_ascii=False, default=str)[:2000])
