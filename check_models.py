import os
import httpx

env_path = '.env'
with open(env_path) as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith('#') and '=' in line:
            key, value = line.split('=', 1)
            os.environ[key.strip()] = value.strip()

headers = {'Authorization': f'Bearer {os.environ["OPENROUTER_API_KEY"]}'}
r = httpx.get('https://openrouter.ai/api/v1/models', headers=headers)
models = r.json()['data']

free = [m for m in models if ':free' in m['id']]

print(f"Modelos gratuitos totales: {len(free)}\n")
for m in free:
    arch = m.get('architecture', {})
    modalities = arch.get('input_modalities', arch.get('modality', ''))
    print(f"{m['id']} — input: {modalities}")