import os, httpx

with open(".env", encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ[k.strip()] = v.strip()

resp = httpx.get(
    "https://api.apify.com/v2/users/me",
    headers={"Authorization": f'Bearer {os.environ["APIFY_API_TOKEN"]}'},
    timeout=10,
)
print(f"Status: {resp.status_code}")
data = resp.json().get("data", {})
print(f'Plan: {data.get("plan", {}).get("id", "?")}')
print(f'Usage: {data.get("plan", {}).get("monthlyUsage", {})}')
