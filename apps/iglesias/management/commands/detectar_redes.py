from django.core.management.base import BaseCommand

from apps.iglesias.scraper.redes import detectar_redes


class Command(BaseCommand):
    help = "Detecta redes sociales oficiales desde los sitios web de parroquias"

    def add_arguments(self, parser):
        parser.add_argument(
            "--limit",
            type=int,
            default=None,
            help="Cantidad maxima de parroquias a procesar",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Reprocesa parroquias aunque ya tengan redes cargadas",
        )
        parser.add_argument(
            "--sleep",
            type=float,
            default=1,
            help="Segundos de pausa entre requests",
        )
        parser.add_argument(
            "--id-externo",
            type=int,
            default=None,
            help="Procesa solo la parroquia con este id_externo",
        )
        parser.add_argument(
            "--nombre",
            type=str,
            default=None,
            help="Procesa solo parroquias cuyo nombre contenga este texto",
        )

    def handle(self, *args, **options):
        self.stdout.write("Iniciando deteccion de redes sociales...\n")

        detectar_redes(
            limit=options["limit"],
            force=options["force"],
            sleep=options["sleep"],
            id_externo=options["id_externo"],
            nombre=options["nombre"],
        )

        self.stdout.write(self.style.SUCCESS("\nProceso finalizado"))
