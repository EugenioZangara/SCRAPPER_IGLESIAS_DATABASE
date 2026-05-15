import sys, os

sys.path.insert(0, ".")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
import django

django.setup()

from apps.iglesias.models import RedSocial

verificar = [
    "parroquianjesus",
    "sagradaeucaristia",
    "iglesia.santacatalina",
    "parroquiasantaisabel",
    "santuariodefatimaoficial",
    "parroquiadelconsuelo",
    "donorionear",
    "medallamilagrosa2015",
    "parroquialoretopalermo",
    "lujanporteno",
    "ntra.sra.montserrat.ar",
    "elatriodelcarmen",
    "basilica.delpilar",
    "madreemigrantes",
    "sanbenitoparroquia",
    "sanca_liniers",
    "parroquia_sanenrique",
    "proyecto.sanignacio",
    "parroquia.sanisidrolabrador",
    "sanjosedeflores",
    "parroquia_santa_lucia",
    "porres.sanmartin",
    "parroquiasannicolasdebari",
    "parroquiasanroque_",
    "santaanaysanjoaquinvdp",
    "santalucia.barracas",
    "basilicasantarosadelima",
    "delsantisimoredentor",
    "santocristolugano",
    "parroquiademaria",
    "pquia.mariamadredelaesperanza",
    "parroquia.sanlucas",
]

count = 0
for username in verificar:
    updated = RedSocial.objects.filter(
        tipo="instagram", activo=True, verificado=False, url__icontains=username
    ).update(verificado=True)
    count += updated

total = RedSocial.objects.filter(tipo="instagram", activo=True, verificado=True).count()
print(f"Verificadas: {count} cuentas")
print(f"Total verificadas ahora: {total}")
