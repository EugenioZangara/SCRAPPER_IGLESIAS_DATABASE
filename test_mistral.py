import os, httpx

with open(".env", encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ[key.strip()] = value.strip()

response = httpx.post(
    "https://api.mistral.ai/v1/chat/completions",
    headers={
        "Authorization": f'Bearer {os.environ["MISTRAL_API_KEY"]}',
        "Content-Type": "application/json",
    },
    json={
        "model": "mistral-small-latest",
        "messages": [{"role": "user", "content": "Di hola"}],
        "max_tokens": 50,
    },
    timeout=30,
)
print(f"Status: {response.status_code}")
print(response.json())
