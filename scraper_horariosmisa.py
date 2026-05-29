import os, django, httpx, time, re
from bs4 import BeautifulSoup
from difflib import SequenceMatcher

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')

with open('.env', encoding='utf-8') as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith('#') and '=' in line:
            k, v = line.split('=', 1)
            os.environ[k.strip()] = v.strip()

django.setup()

from apps.iglesias.models import Parroquia, ReporteHorario

BASE_URL = "https://horariosmisa.com.ar/ciudad-autonoma-de-buenos-aires/buenos-aires/"

DIAS_MAP = {
    "lunes": 0, "martes": 1, "miércoles": 2, "miercoles": 2,
    "jueves": 3, "viernes": 4, "sábado": 5, "sabado": 5, "domingo": 6
}

def similaridad(a, b):
    a = re.sub(r'[^\w\s]', '', a.lower())
    b = re.sub(r'[^\w\s]', '', b.lower())
    return SequenceMatcher(None, a, b).ratio()

def buscar_parroquia_match(nombre_externo, parroquias):
    """Busca la parroquia más similar en nuestra DB."""
    mejor = None
    mejor_score = 0
    for p in parroquias:
        score = similaridad(nombre_externo, p.nombre)
        if score > mejor_score:
            mejor_score = score
            mejor = p
    return mejor, mejor_score

def obtener_urls_parroquias():
    """Obtiene todas las URLs de parroquias del listado."""
    print("Obteniendo listado de parroquias...")
    resp = httpx.get(BASE_URL, timeout=15,
                     headers={"User-Agent": "ParroGuia/1.0"})
    soup = BeautifulSoup(resp.text, 'html.parser')
    urls = set()
    for a in soup.find_all('a', href=True):
        href = a['href']
        if href.startswith(BASE_URL) and href != BASE_URL:
            urls.add(href.rstrip('/') + '/')
    print(f"  {len(urls)} parroquias encontradas")
    return list(urls)

def scrapear_horarios(url):
    """Scrapea los horarios de una parroquia."""
    resp = httpx.get(url, timeout=15,
                     headers={"User-Agent": "ParroGuia/1.0"})
    soup = BeautifulSoup(resp.text, 'html.parser')

    # Nombre de la parroquia
    h1 = soup.find('h1')
    nombre = h1.get_text(strip=True) if h1 else ""
    # Limpiar sufijo " - Buenos Aires..."
    nombre = re.sub(r'\s*-\s*Buenos Aires.*$', '', nombre, flags=re.IGNORECASE)

    # Buscar tabla de horarios
    horarios = {}
    tabla = soup.find('table')
    if tabla:
        for row in tabla.find_all('tr'):
            celdas = row.find_all(['td', 'th'])
            if len(celdas) >= 2:
                dia_texto = celdas[0].get_text(strip=True).lower()
                horario_texto = celdas[1].get_text(strip=True)
                dia_num = DIAS_MAP.get(dia_texto)
                if dia_num is not None and horario_texto:
                    # Convertir "08:00, 12:00, 19:00" → "8:00 · 12:00 · 19:00"
                    horas = [h.strip() for h in horario_texto.split(',')]
                    horario_formateado = ' · '.join(horas)
                    horarios[dia_num] = horario_formateado

    return nombre, horarios

def main():
    parroquias_db = list(Parroquia.objects.all())
    print(f"Parroquias en DB: {len(parroquias_db)}")

    urls = obtener_urls_parroquias()
    print(f"\nProcesando {len(urls)} parroquias de horariosmisa.com.ar...\n")

    matches_buenos = 0
    matches_dudosos = 0
    sin_match = 0
    reportes_creados = 0

    for i, url in enumerate(urls, 1):
        try:
            nombre_externo, horarios = scrapear_horarios(url)
            if not nombre_externo or not horarios:
                continue

            parroquia, score = buscar_parroquia_match(
                nombre_externo, parroquias_db
            )

            print(f"[{i}/{len(urls)}] {nombre_externo[:45]}")
            print(f"  → {parroquia.nombre[:45]} (score: {score:.2f})")

            if score < 0.4:
                print(f"  ✗ Sin match suficiente")
                sin_match += 1
                time.sleep(0.5)
                continue

            if score < 0.65:
                print(f"  ⚠ Match dudoso — omitiendo")
                matches_dudosos += 1
                time.sleep(0.5)
                continue

            matches_buenos += 1

            # Verificar si ya hay reporte pendiente de esta fuente
            from django.utils import timezone
            hace_30dias = timezone.now() - timezone.timedelta(days=30)
            ya_existe = ReporteHorario.objects.filter(
                parroquia=parroquia,
                fuente="scraper_web",
                estado="pendiente",
                creado_en__gte=hace_30dias
            ).exists()

            if ya_existe:
                print(f"  → Ya tiene reporte pendiente reciente")
                time.sleep(0.5)
                continue

            # Construir propuesta en formato dia/horario
            propuesta = [
                {"dia": dia, "horario": horario}
                for dia, horario in sorted(horarios.items())
            ]

            # Determinar si es nuevo o actualización
            tiene_horarios = parroquia.horarios_misa.exists()
            if tiene_horarios:
                resumen = f"Horarios encontrados en horariosmisa.com.ar — posible actualización"
            else:
                resumen = f"Horarios nuevos encontrados en horariosmisa.com.ar"

            ReporteHorario.objects.create(
                parroquia=parroquia,
                texto_usuario=f"Extraído de horariosmisa.com.ar — {url}",
                propuesta_ia=propuesta,
                resumen_cambios=resumen,
                url_post=url,
                fuente="scraper_web",
                estado="pendiente",
            )
            reportes_creados += 1
            print(f"  ✓ Reporte creado — {len(horarios)} días")

            time.sleep(0.8)  # respetar el servidor

        except Exception as e:
            print(f"  ERROR: {e}")
            time.sleep(1)

    print(f"\n=== RESUMEN ===")
    print(f"Procesadas    : {len(urls)}")
    print(f"Matches buenos: {matches_buenos}")
    print(f"Dudosos       : {matches_dudosos}")
    print(f"Sin match     : {sin_match}")
    print(f"Reportes      : {reportes_creados}")

if __name__ == "__main__":
    main()
    