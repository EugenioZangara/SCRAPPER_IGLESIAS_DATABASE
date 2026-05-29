import os, django, httpx, re
from bs4 import BeautifulSoup

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
with open(".env", encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ[k.strip()] = v.strip()
django.setup()

from apps.iglesias.models import Parroquia, ReporteHorario
from django.utils import timezone

DIAS_MAP = {
    "lunes": 0,
    "martes": 1,
    "miércoles": 2,
    "miercoles": 2,
    "jueves": 3,
    "viernes": 4,
    "sábado": 5,
    "sabado": 5,
    "domingo": 6,
}

# Matches manuales: (pk_parroquia, url_horariosmisa)
MATCHES = [
    (
        499,
        "https://horariosmisa.com.ar/ciudad-autonoma-de-buenos-aires/buenos-aires/parroquia-de-san-pedro-gonzalez-telmo/",
    ),
    (
        493,
        "https://horariosmisa.com.ar/ciudad-autonoma-de-buenos-aires/buenos-aires/parroquia-de-san-miguel-arcangel/",
    ),
    (
        535,
        "https://horariosmisa.com.ar/ciudad-autonoma-de-buenos-aires/buenos-aires/parroquia-santisima-trinidad/",
    ),
    (
        472,
        "https://horariosmisa.com.ar/ciudad-autonoma-de-buenos-aires/buenos-aires/parroquia-san-felipe-neri/",
    ),
    (
        461,
        "https://horariosmisa.com.ar/ciudad-autonoma-de-buenos-aires/buenos-aires/parroquia-y-santuario-san-antonio-de-padua/",
    ),
]


def scrapear_horarios(url):
    resp = httpx.get(url, timeout=15, headers={"User-Agent": "ParroGuia/1.0"})
    soup = BeautifulSoup(resp.text, "html.parser")
    horarios = {}
    tabla = soup.find("table")
    if tabla:
        for row in tabla.find_all("tr"):
            celdas = row.find_all(["td", "th"])
            if len(celdas) >= 2:
                dia_texto = celdas[0].get_text(strip=True).lower()
                horario_texto = celdas[1].get_text(strip=True)
                dia_num = DIAS_MAP.get(dia_texto)
                if dia_num is not None and horario_texto:
                    horas = [h.strip() for h in horario_texto.split(",")]
                    horarios[dia_num] = " · ".join(horas)
    return horarios


hace_30dias = timezone.now() - timezone.timedelta(days=30)

for pk, url in MATCHES:
    try:
        parroquia = Parroquia.objects.get(pk=pk)
        print(f"Procesando: {parroquia.nombre}")

        ya_existe = ReporteHorario.objects.filter(
            parroquia=parroquia, fuente="scraper_web", creado_en__gte=hace_30dias
        ).exists()  # cualquier estado — pendiente, aplicado o descartado

        if ya_existe:
            print(f"  → Ya tiene reporte pendiente")
            continue

        horarios = scrapear_horarios(url)
        if not horarios:
            print(f"  → Sin horarios encontrados")
            continue

        propuesta = [
            {"dia": dia, "horario": horario}
            for dia, horario in sorted(horarios.items())
        ]

        tiene_horarios = parroquia.horarios_misa.exists()
        resumen = (
            "Horarios encontrados en horariosmisa.com.ar — posible actualización"
            if tiene_horarios
            else "Horarios nuevos encontrados en horariosmisa.com.ar"
        )

        ReporteHorario.objects.create(
            parroquia=parroquia,
            texto_usuario=f"Match manual — extraído de horariosmisa.com.ar",
            propuesta_ia=propuesta,
            resumen_cambios=resumen,
            url_post=url,
            fuente="scraper_web",
            estado="pendiente",
        )
        print(f"  ✓ Reporte creado — {len(horarios)} días")

    except Parroquia.DoesNotExist:
        print(f"  ERROR: parroquia pk={pk} no existe")
    except Exception as e:
        print(f"  ERROR: {e}")

print("\nListo.")
