from django.core.management.base import BaseCommand

from apps.iglesias.models import Parroquia, RedSocial
from apps.iglesias.scraper.redes import (
    es_red_probablemente_oficial,
    texto_tiene_indicios_extranjeros,
    url_tiene_dominio_extranjero_riesgoso,
    url_tiene_indicios_argentina,
)


class Command(BaseCommand):
    help = "Borra redes sociales que no pasan los filtros actuales de confiabilidad"

    def add_arguments(self, parser):
        parser.add_argument(
            "--confirm",
            action="store_true",
            help="Borra efectivamente las redes detectadas. Sin esto solo muestra el reporte.",
        )
        parser.add_argument(
            "--include-inactive",
            action="store_true",
            help="Incluye redes ya marcadas como inactivas en la limpieza.",
        )

    def handle(self, *args, **options):
        confirm = options["confirm"]
        include_inactive = options["include_inactive"]

        redes = RedSocial.objects.select_related("parroquia").order_by(
            "parroquia__nombre",
            "tipo",
            "url",
        )

        if not include_inactive:
            redes = redes.filter(activo=True)

        candidatas = []

        for red in redes:
            motivos = []

            red_data = {
                "tipo": red.tipo,
                "url": red.url,
                "username": red.username,
            }

            if not es_red_probablemente_oficial(red.parroquia, red_data):
                motivos.append("no parece oficial para la parroquia")

            if url_tiene_dominio_extranjero_riesgoso(red.url) and not url_tiene_indicios_argentina(red.url):
                motivos.append("dominio extranjero sin indicios de Argentina")

            if texto_tiene_indicios_extranjeros(f"{red.username or ''} {red.url}"):
                motivos.append("texto/url con indicios de otro pais")

            if motivos:
                candidatas.append((red, motivos))

        self.stdout.write(f"Redes revisadas: {redes.count()}")
        self.stdout.write(f"Redes no confiables detectadas: {len(candidatas)}")

        for red, motivos in candidatas:
            self.stdout.write(
                "- "
                f"{red.parroquia.nombre} | {red.tipo} | {red.url} | "
                + "; ".join(motivos)
            )

        if not candidatas:
            self.stdout.write(self.style.SUCCESS("No hay redes para borrar."))
            return

        if not confirm:
            self.stdout.write(
                self.style.WARNING(
                    "\nNo se borro nada. Ejecuta nuevamente con --confirm para borrar estas redes."
                )
            )
            return

        ids = [red.id for red, _ in candidatas]
        parroquias_afectadas = {red.parroquia_id for red, _ in candidatas}
        borradas, detalle = RedSocial.objects.filter(id__in=ids).delete()

        parroquias_sin_redes = 0
        for parroquia_id in parroquias_afectadas:
            if not RedSocial.objects.filter(parroquia_id=parroquia_id, activo=True).exists():
                Parroquia.objects.filter(id=parroquia_id).update(tiene_redes=False)
                parroquias_sin_redes += 1

        self.stdout.write(self.style.SUCCESS(f"\nRedes borradas: {borradas}"))
        for modelo, cantidad in detalle.items():
            self.stdout.write(f"{modelo}: {cantidad}")
        self.stdout.write(f"Parroquias marcadas sin redes: {parroquias_sin_redes}")
