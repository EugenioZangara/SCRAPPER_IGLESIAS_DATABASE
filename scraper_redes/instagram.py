import instaloader
import base64
import os
from .config import INSTAGRAM_SESSION_USER, POSTS_A_REVISAR
from datetime import timezone

def get_loader():
    """Inicializa Instaloader con la sesión guardada."""
    L = instaloader.Instaloader()

    # Opción A: sesión desde variable de entorno (producción)
    # Opción A: sesión desde variable de entorno (producción)
    session_b64 = os.environ.get("INSTAGRAM_SESSION_B64")
    if session_b64:
        try:
            session_data = base64.b64decode(session_b64)
            # En Windows: AppData\Local\Instaloader\
            # En Linux: ~/.config/instaloader/
            if os.name == "nt":
                session_dir = os.path.join(
                    os.environ.get("LOCALAPPDATA", os.path.expanduser("~")),
                    "Instaloader",
                )
            else:
                session_dir = os.path.join(
                    os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config")),
                    "instaloader",
                )
            os.makedirs(session_dir, exist_ok=True)
            session_path = os.path.join(
                session_dir, f"session-{INSTAGRAM_SESSION_USER}"
            )
            with open(session_path, "wb") as f:
                f.write(session_data)
            L.load_session_from_file(username=INSTAGRAM_SESSION_USER)
            print(
                f"Sesión cargada desde variable de entorno para: {INSTAGRAM_SESSION_USER}"
            )
            return L
        except Exception as e:
            print(f"ERROR cargando sesión desde variable de entorno: {e}")
            return None

    # Opción B: sesión desde archivo local (desarrollo)
    try:
        L.load_session_from_file(username=INSTAGRAM_SESSION_USER)
        print(f"Sesión cargada desde archivo para: {INSTAGRAM_SESSION_USER}")
        return L
    except FileNotFoundError:
        print("ERROR: No encontró el archivo de sesión.")
        print("Corré primero instagram_login.py o configurá INSTAGRAM_SESSION_B64.")
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
