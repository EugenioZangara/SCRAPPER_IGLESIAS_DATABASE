import instaloader
import json
import os
import sys

INSTAGRAM_USER = "pilotosprogramadores"
COOKIES_FILE = "instagram_cookies.json"


def main():
    if not os.path.exists(COOKIES_FILE):
        print(f"ERROR: No se encontró el archivo '{COOKIES_FILE}' en la raíz del proyecto.")
        sys.exit(1)

    with open(COOKIES_FILE, "r") as f:
        cookies = json.load(f)

    L = instaloader.Instaloader()

    # Carga las cookies en la sesión
    cookie_dict = {c["name"]: c["value"] for c in cookies}
    L.context._session.cookies.update(cookie_dict)
    L.context.username = INSTAGRAM_USER

    # Verifica que la sesión funcione
    try:
        profile = instaloader.Profile.from_username(L.context, INSTAGRAM_USER)
        print(f"Sesión verificada correctamente para: {profile.username}")
    except Exception as e:
        print(f"ERROR: La sesión no es válida. Revisá las cookies. Detalle: {e}")
        sys.exit(1)

    # Guarda la sesión para uso futuro
    L.save_session_to_file()
    print(f"Sesión guardada. Ya podés correr el scraper.")


if __name__ == "__main__":
    main()