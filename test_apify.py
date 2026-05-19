import os

with open(".env", encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip())

from apify_client import ApifyClient

client = ApifyClient(os.environ["APIFY_API_TOKEN"])

# Probar con una sola cuenta
run_input = {
    "directUrls": ["https://www.instagram.com/pquia.mariamadredelaesperanza/"],
    "resultsType": "posts",
    "resultsLimit": 5,
}

print("Iniciando scraping con Apify...")
run = client.actor("apify/instagram-scraper").call(run_input=run_input)

print(f"Run ID: {run['id']}")
print(f"Estado: {run['status']}")
print()

items = list(client.dataset(run["defaultDatasetId"]).iterate_items())
print(f"Posts obtenidos: {len(items)}")

for item in items[:3]:
    print(f"  - {item.get('shortCode', '?')} | {item.get('timestamp', '?')[:10]}")
    print(f"    {item.get('displayUrl', '')[:80]}")

import os, json

with open(".env", encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip())

import os, json

with open(".env", encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip())

from apify_client import ApifyClient

client = ApifyClient(os.environ["APIFY_API_TOKEN"])

run_input = {
    "directUrls": ["https://www.instagram.com/pquia.mariamadredelaesperanza/"],
    "resultsType": "posts",
    "resultsLimit": 1,
}

print("Obteniendo estructura de un post...")
run = client.actor("apify/instagram-scraper").call(run_input=run_input)
items = list(client.dataset(run["defaultDatasetId"]).iterate_items())

if items:
    print("\nCampos disponibles:")
    print(json.dumps(items[0], indent=2, ensure_ascii=False, default=str))
