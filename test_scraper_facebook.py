import os
import requests
import sys
from urllib.parse import urlparse

# URL de la página de Facebook a consultar
PAGE_URL = "https://www.facebook.com/people/Parroquia-Cristo-Maestro/100082483506442/"

def get_facebook_handle(url):
    """
    Maneja tres formatos de URL de Facebook:
    - facebook.com/parroquiasanpedro              → handle: parroquiasanpedro
    - facebook.com/people/Nombre/100082483506442  → handle: 100082483506442
    - facebook.com/profile.php?id=100082483506442 → handle: 100082483506442
    """
    parsed = urlparse(url)
    
    # Caso profile.php?id=XXXXXXX
    if 'profile.php' in parsed.path:
        from urllib.parse import parse_qs
        params = parse_qs(parsed.query)
        if 'id' in params:
            return params['id'][0]
        return None
    
    parts = parsed.path.strip('/').split('/')
    
    # Caso /people/Nombre/ID_NUMERICO
    if parts[0] == 'people' and len(parts) >= 3:
        return parts[2]
    
    # Caso /handle_directo
    if parts[0] and parts[0] not in ('groups', 'people', 'pages'):
        return parts[0]
    
    return None

def load_env():
    """
    Carga variables desde el archivo .env si existe, sin usar librerías externas.
    """
    env_path = os.path.join(os.path.dirname(__file__), '.env')
    if os.path.exists(env_path):
        with open(env_path, 'r') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                if '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key.strip()] = value.strip()

def main():
    # Cargar variables del .env
    load_env()

    # 1. Obtener access token
    access_token = os.environ.get("META_ACCESS_TOKEN")
    if not access_token:
        print("ERROR: La variable de entorno META_ACCESS_TOKEN no está definida en el sistema ni en el archivo .env.")
        sys.exit(1)

    handle = get_facebook_handle(PAGE_URL)
    if not handle:
        print(f"ERROR: No se pudo extraer un handle válido de la URL: {PAGE_URL}")
        sys.exit(1)

    print(f"--- Iniciando scraping para: {PAGE_URL} (Handle: {handle}) ---")

    # 2. Resolver page_id
    # Endpoint: https://graph.facebook.com/v20.0/{handle}?access_token={token}
    try:
        url_id = f"https://graph.facebook.com/v20.0/{handle}"
        params_id = {'access_token': access_token, 'fields': 'id,name'}
        response_id = requests.get(url_id, params=params_id)
        
        if response_id.status_code != 200:
            print(f"ERROR al resolver ID de página: {response_id.json().get('error', {}).get('message', 'Error desconocido')}")
            sys.exit(1)
        
        page_data = response_id.json()
        page_id = page_data.get('id')
        page_name = page_data.get('name')
        print(f"Page ID encontrado: {page_id} (Nombre: {page_name})")

    except Exception as e:
        print(f"ERROR inesperado al conectar con Meta API: {e}")
        sys.exit(1)

    # 3. Obtener posts
    # Endpoint: https://graph.facebook.com/v20.0/{page_id}/posts?fields=full_picture,id,message,created_time
    try:
        url_posts = f"https://graph.facebook.com/v20.0/{page_id}/posts"
        params_posts = {
            'access_token': access_token,
            'fields': 'id,full_picture,message,created_time',
            'limit': 10  # Obtenemos los últimos 10 para buscar uno con imagen
        }
        response_posts = requests.get(url_posts, params=params_posts)
        
        if response_posts.status_code != 200:
            print(f"ERROR al obtener posts: {response_posts.json().get('error', {}).get('message', 'Error desconocido')}")
            sys.exit(1)

        posts_data = response_posts.json().get('data', [])
        print(f"Cantidad de posts obtenidos: {len(posts_data)}")

        if not posts_data:
            print("No se encontraron posts en esta página.")
            sys.exit(0)

        # 4. Extraer URL de la imagen del último post con imagen
        latest_image_url = None
        for post in posts_data:
            if 'full_picture' in post:
                latest_image_url = post['full_picture']
                break
        
        if latest_image_url:
            print(f"URL de la imagen del último post con imagen: {latest_image_url}")
        else:
            print("No se encontraron posts con imagen entre los obtenidos.")

    except Exception as e:
        print(f"ERROR inesperado al obtener posts: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
