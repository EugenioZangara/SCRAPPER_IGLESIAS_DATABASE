from django.core.management.base import BaseCommand

from apps.iglesias.models import RedSocial


class Command(BaseCommand):
    help = "Marca redes sociales existentes como sin verificar"

    def add_arguments(self, parser):
        parser.add_argument(
            "--confirm",
            action="store_true",
            help="Aplica el cambio. Sin esto solo muestra cuantas redes se actualizarian.",
        )
        parser.add_argument(
            "--include-inactive",
            action="store_true",
            help="Incluye redes inactivas. Por defecto solo afecta redes activas.",
        )

    def handle(self, *args, **options):
        confirm = options["confirm"]
        include_inactive = options["include_inactive"]

        redes = RedSocial.objects.filter(verificado=True)

        if not include_inactive:
            redes = redes.filter(activo=True)

        total = redes.count()
        alcance = "activas e inactivas" if include_inactive else "activas"

        self.stdout.write(f"Redes verificadas {alcance} encontradas: {total}")

        if not confirm:
            self.stdout.write(
                self.style.WARNING(
                    "No se modifico nada. Ejecuta con --confirm para marcarlas como sin verificar."
                )
            )
            return

        actualizadas = redes.update(verificado=False)
        self.stdout.write(
            self.style.SUCCESS(
                f"Redes marcadas como sin verificar: {actualizadas}"
            )
        )
