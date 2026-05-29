import httpx, os

with open(".env", encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ[k.strip()] = v.strip()

token = os.environ.get("SCRAPER_SECRET_TOKEN", "NO ENCONTRADO")
print(f"Token local: {token[:10]}...")

resp = httpx.post(
    "https://scrapper-iglesias-database.onrender.com/api/scraper/ejecutar/",
    headers={"X-Scraper-Token": token},
    timeout=30,
)
print(f"Status: {resp.status_code}")
print(f"Response: {resp.text[:200]}")
