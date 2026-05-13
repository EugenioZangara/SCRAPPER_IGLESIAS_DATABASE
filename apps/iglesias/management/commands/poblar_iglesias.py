from django.core.management.base import BaseCommand
from apps.iglesias.models import Parroquia
from apps.iglesias.scraper.crawler import run_crawler


class Command(BaseCommand):
    help = "Extrae la lista completa de parroquias"

    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING("Iniciando crawler..."))

        iglesias_encontradas = run_crawler()

        for data in iglesias_encontradas:
            Parroquia.objects.update_or_create(
                id_externo=data["id_externo"],
                defaults=data,
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"Se actualizaron {len(iglesias_encontradas)} parroquias."
            )
        )
