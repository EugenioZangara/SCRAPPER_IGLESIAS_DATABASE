import os

# Instagram
INSTAGRAM_TEST_URL = "https://www.instagram.com/pquia.mariamadredelaesperanza/"
INSTAGRAM_SESSION_USER = "pilotosprogramadores"

# Facebook
FACEBOOK_TEST_URL = "https://www.facebook.com/parroquianjesus"

# Cuántos posts recientes revisar por perfil
POSTS_A_REVISAR = 5

# Backend de scraping: "instaloader" o "apify"
# Cambiar a "instaloader" cuando se actualice la librería
SCRAPER_BACKEND = os.environ.get("SCRAPER_BACKEND", "apify")
