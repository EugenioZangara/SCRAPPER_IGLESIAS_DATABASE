from django.core.management.base import BaseCommand
from apps.iglesias.scraper.detalle import completar_detalles


class Command(BaseCommand):
    help = "Completa detalles de parroquias"

    def handle(self, *args, **kwargs):
        self.stdout.write("Iniciando scraping de detalles...")
        completar_detalles()
        self.stdout.write(self.style.SUCCESS("Proceso finalizado"))
