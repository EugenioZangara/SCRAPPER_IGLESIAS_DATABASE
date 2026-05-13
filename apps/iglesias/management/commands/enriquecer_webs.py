from django.core.management.base import BaseCommand
from apps.iglesias.scraper.redes import enriquecer_webs


class Command(BaseCommand):
    help = "Valida y corrige sitios web de parroquias"

    def handle(self, *args, **kwargs):
        self.stdout.write("Iniciando enriquecimiento de webs...\n")

        enriquecer_webs()

        self.stdout.write(self.style.SUCCESS("\nProceso finalizado"))
