import requests
from .config import LIST_URL, HEADERS
from .parser import extract_all_parishes


def run_crawler():
    print("Extrayendo página única...")

    response = requests.get(LIST_URL, headers=HEADERS)

    if response.status_code != 200:
        print("Error al acceder a la página.")
        return []

    data = extract_all_parishes(response.content)

    print(f"Total parroquias encontradas: {len(data)}")

    return data
