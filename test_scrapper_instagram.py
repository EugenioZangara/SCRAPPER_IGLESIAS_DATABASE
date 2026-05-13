import instaloader

L = instaloader.Instaloader()
L.load_session_from_file("pilotosprogramadores@gmail.com")  # carga sesión guardada

# Solo el nombre de usuario, sin URL ni parámetros
profile = instaloader.Profile.from_username(L.context, "parroquia_cristo_obrero")

for post in profile.get_posts():
    if not post.is_video:
        print(f"URL imagen: {post.url}")
        print(f"Fecha: {post.date}")
        print(f"Caption: {post.caption[:100] if post.caption else 'Sin texto'}")
        break