import instaloader
from .config import INSTAGRAM_SESSION_USER, POSTS_A_REVISAR
from datetime import timezone

def get_loader():
    """Inicializa Instaloader con la sesión guardada."""
    L = instaloader.Instaloader()
    try:
        L.load_session_from_file(username=INSTAGRAM_SESSION_USER)
        print(f"Sesión cargada para: {INSTAGRAM_SESSION_USER}")
        return L
    except FileNotFoundError:
        print("ERROR: No encontró el archivo de sesión.")
        print("Corré primero instagram_login.py en la raíz del proyecto.")
        return None


def obtener_username_de_url(url: str) -> str:
    """Extrae el username de una URL de Instagram."""
    # Limpia la URL y extrae solo el username
    url = url.rstrip("/")
    return url.split("/")[-1].split("?")[0]


def scrapear_perfil(url: str) -> list[dict]:
    """
    Dado una URL de perfil de Instagram, devuelve los últimos posts con imagen.
    Retorna una lista de dicts con post_id, imagen_url y raw_data.
    """
    L = get_loader()
    if not L:
        return []

    username = obtener_username_de_url(url)
    print(f"Scrapeando perfil: {username}")

    resultados = []

    try:
        profile = instaloader.Profile.from_username(L.context, username)
        print(f"Perfil encontrado: {profile.full_name} ({profile.followers} seguidores)")

        for post in profile.get_posts():
            if len(resultados) >= POSTS_A_REVISAR:
                break
            if post.is_video:
                continue

            resultados.append({
                "post_id": post.shortcode,
                "imagen_url": post.url,
                "caption": post.caption[:200] if post.caption else "",
                "fecha": post.date.replace(tzinfo=timezone.utc),
                "raw_data": {
                    "shortcode": post.shortcode,
                    "likes": post.likes,
                    "fecha": post.date.isoformat(),
                    "caption": post.caption,
                }
            })
            print(f"  Post encontrado: {post.shortcode} ({post.date.strftime('%d/%m/%Y')})")

    except instaloader.exceptions.ProfileNotExistsException:
        print(f"ERROR: El perfil '{username}' no existe.")
    except Exception as e:
        print(f"ERROR inesperado scrapeando {username}: {e}")

    return resultados