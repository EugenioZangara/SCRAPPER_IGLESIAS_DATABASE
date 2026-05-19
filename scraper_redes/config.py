# URL hardcodeada para pruebas — reemplazá con la cuenta real
import os


INSTAGRAM_TEST_URL = "https://www.instagram.com/pquia.mariamadredelaesperanza/"
# Usuario de Instagram con el que vas a autenticarte
INSTAGRAM_SESSION_USER = "pilotosprogramadores"

# Cuántos posts recientes revisar por perfil
POSTS_A_REVISAR = 5

# URL hardcodeada para pruebas — reemplazá con la cuenta real
INSTAGRAM_TEST_URL = "https://www.instagram.com/pquia.mariamadredelaesperanza/"

# Usuario de Instagram con el que vas a autenticarte
INSTAGRAM_SESSION_USER = "pilotosprogramadores"

# Cuántos posts recientes revisar por perfil
POSTS_A_REVISAR = 5

# Backend de scraping: "instaloader" o "apify"
# Cambiar a "instaloader" cuando se actualice la librería
SCRAPER_BACKEND = os.environ.get("SCRAPER_BACKEND", "apify")
