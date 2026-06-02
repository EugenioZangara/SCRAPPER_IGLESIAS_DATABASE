import sys
import os
import time
import random
import argparse
from scraper_redes.config import SCRAPER_BACKEND

# Inicializar Django antes de importar modelos
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")

import django
django.setup()

# Cargar .env manualmente
env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
if os.path.exists(env_path):
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                os.environ.setdefault(key.strip(), value.strip())

from apps.iglesias.models import Parroquia, PostParroquia, Evento, RedSocial, TipoEvento, ReporteHorario
from django.utils import timezone
from scraper_redes.instagram import scrapear_perfil
from scraper_redes.procesador import procesar_post, procesar_post_facebook
from scraper_redes.config import INSTAGRAM_TEST_URL

# ID de la parroquia de prueba
PARROQUIA_TEST_ID = 559


def guardar_posts(parroquia, posts: list[dict]) -> tuple[int, int]:
    guardados = 0
    omitidos = 0

    for post in posts:
        _, creado = PostParroquia.objects.get_or_create(
            post_id=post["post_id"],
            defaults={
                "parroquia": parroquia,
                "red_social": "instagram",
                "imagen_url": post["imagen_url"],
                "fecha_publicacion": post["fecha"],
                "raw_data": post["raw_data"],
            }
        )
        if creado:
            guardados += 1
            print(f"  Guardado: {post['post_id']} ({post['fecha']})")
        else:
            omitidos += 1
            print(f"  Omitido (ya existe): {post['post_id']}")

    return guardados, omitidos


def procesar_posts_pendientes(parroquia):
    """Procesa con Gemini los posts que aún no fueron analizados."""
    pendientes = PostParroquia.objects.filter(
        parroquia=parroquia,
        procesado=False
    )

    print(f"\n=== Procesando {pendientes.count()} posts con Gemini ===")

    for post_obj in pendientes:
        post_dict = {
            "post_id": post_obj.post_id,
            "imagen_url": post_obj.imagen_url,
            "caption": post_obj.raw_data.get("caption", "") if post_obj.raw_data else "",
        }

        resultado = procesar_post(post_dict)

        # Actualizar el objeto en la DB
        post_obj.es_evento = resultado.get("es_evento")
        post_obj.procesado = True
        post_obj.raw_data = {
            **(post_obj.raw_data or {}),
            "gemini": resultado
        }
        post_obj.save()

        # Crear evento si fue clasificado como tal y NO es pasado
        if resultado.get("es_evento") and not resultado.get("es_pasado"):
            crear_evento_desde_post(post_obj, resultado)

        # Crear ReporteHorario si se detectaron horarios semanales
        if resultado.get("tiene_horarios") and resultado.get("horarios_detectados"):
            from datetime import timedelta
            hace_7_dias = timezone.now() - timedelta(days=7)
            if not ReporteHorario.objects.filter(
                parroquia=post_obj.parroquia,
                fuente="scraper",
                creado_en__gte=hace_7_dias,
            ).exists():
                _dias = ["Lunes","Martes","Miércoles","Jueves","Viernes","Sábado","Domingo"]
                lineas = [
                    f"{_dias[h['dia']]}: {h['horario']}"
                    for h in resultado["horarios_detectados"]
                    if 0 <= h.get("dia", -1) <= 6
                ]
                ReporteHorario.objects.create(
                    parroquia=post_obj.parroquia,
                    fuente="scraper",
                    texto_usuario="Horarios detectados desde imagen: " + ", ".join(lineas),
                    imagen_url=post_obj.imagen_url,
                    url_post=post_obj.raw_data.get("url_post", "") if post_obj.raw_data else "",
                    propuesta_ia=resultado["horarios_detectados"],
                    resumen_cambios="Detectado automáticamente desde imagen de la red social.",
                )
                print(f"     ReporteHorario scraper creado para {post_obj.parroquia.nombre}")

        time.sleep(4)  # 4 segundos entre requests

        es_evento_str = "✅ ES EVENTO" if resultado.get("es_evento") else "❌ no es evento"
        if resultado.get("es_evento") is None:
            es_evento_str = "⚠️  error al procesar"

        es_evento_str = "✅ ES EVENTO" if resultado.get("es_evento") else "❌ no es evento"
        if resultado.get("es_pasado"):
            es_evento_str = "📅 evento pasado"
        if resultado.get("es_evento") is None:
            es_evento_str = "⚠️  error al procesar"

        print(f"  {post_obj.post_id}: {es_evento_str}")
        if resultado.get("es_evento"):
            print(f"     Título : {resultado.get('titulo')}")
            print(f"     Fecha  : {resultado.get('fecha')}")
            print(f"     Tipo   : {resultado.get('tipo_evento')}")


def scrapear_con_backend(url: str) -> list[dict]:
    """Selecciona el backend de scraping según configuración."""
    if SCRAPER_BACKEND == "apify":
        from scraper_redes.apify_scraper import scrapear_perfil_apify
        from scraper_redes.config import POSTS_A_REVISAR

        return scrapear_perfil_apify(url, limite=POSTS_A_REVISAR)
    else:
        from scraper_redes.instagram import scrapear_perfil

        return scrapear_perfil(url)


def scrapear_facebook_con_backend(url: str) -> list[dict]:
    """Scrapea Facebook usando Apify."""
    from scraper_redes.facebook_apify import scrapear_perfil_facebook
    from scraper_redes.config import POSTS_A_REVISAR

    return scrapear_perfil_facebook(url, limite=POSTS_A_REVISAR)


def main():
    print(f"=== Scraper de redes sociales ===")
    print(f"URL de prueba: {INSTAGRAM_TEST_URL}\n")

    try:
        parroquia = Parroquia.objects.get(id=PARROQUIA_TEST_ID)
        print(f"Parroquia: {parroquia.nombre}\n")
    except Parroquia.DoesNotExist:
        print(f"ERROR: No existe parroquia con ID {PARROQUIA_TEST_ID}")
        return

    # 1. Scrapear posts nuevos
    posts = scrapear_con_backend(INSTAGRAM_TEST_URL)

    if not posts:
        print("No se obtuvieron posts.")
        return

    print(f"\n=== Guardando {len(posts)} posts en la DB ===")
    guardados, omitidos = guardar_posts(parroquia, posts)
    print(f"Resumen: {guardados} guardados, {omitidos} omitidos.")

    # 2. Procesar con Gemini los pendientes
    procesar_posts_pendientes(parroquia)

    print(f"\n=== Finalizado ===")
    total = PostParroquia.objects.filter(parroquia=parroquia).count()
    eventos = PostParroquia.objects.filter(parroquia=parroquia, es_evento=True).count()
    print(f"Total posts en DB : {total}")
    print(f"Eventos detectados: {eventos}")

def main_produccion():
    redes = RedSocial.objects.filter(
        tipo="instagram", activo=True, verificado=True
    ).select_related("parroquia").order_by("parroquia__nombre")

    total = redes.count()
    print(f"=== Modo producción: {total} perfiles de Instagram verificados ===\n")

    resumen = {"procesadas": 0, "posts_nuevos": 0, "eventos_detectados": 0, "errores": 0}

    for i, red in enumerate(redes, 1):
        parroquia = red.parroquia
        print(f"\n--- [{i}/{total}] {parroquia.nombre} ---")
        print(f"URL: {red.url}")

        if red.parroquia.redes_verificadas:
            print(f"  Saltando {red.parroquia.nombre} — redes verificadas")
            resumen["procesadas"] += 1
            continue

        try:
            posts = scrapear_con_backend(red.url)

            if not posts:
                print("  No se obtuvieron posts.")
                resumen["procesadas"] += 1
            else:
                print(f"  Guardando {len(posts)} posts...")
                guardados, omitidos = guardar_posts(parroquia, posts)
                resumen["posts_nuevos"] += guardados
                print(f"  {guardados} guardados, {omitidos} omitidos.")

                eventos_antes = Evento.objects.filter(parroquia=parroquia).count()
                procesar_posts_pendientes(parroquia)
                resumen["eventos_detectados"] += Evento.objects.filter(parroquia=parroquia).count() - eventos_antes

                resumen["procesadas"] += 1

        except Exception as e:
            print(f"  ERROR: {e}")
            resumen["errores"] += 1

        if i < total:
            delay = random.randint(10, 20)
            print(f"  Esperando {delay}s antes de la siguiente parroquia...")
            time.sleep(delay)

    print(f"\n=== RESUMEN FINAL ===")
    print(f"Parroquias procesadas : {resumen['procesadas']}/{total}")
    print(f"Posts nuevos guardados: {resumen['posts_nuevos']}")
    print(f"Eventos detectados    : {resumen['eventos_detectados']}")
    print(f"Errores               : {resumen['errores']}")


def main_produccion_facebook():
    """Scrapea todas las RedSocial de Facebook verificadas."""
    redes = RedSocial.objects.filter(
        tipo="facebook", activo=True, verificado=True
    ).select_related("parroquia")

    total = redes.count()
    print(f"=== Scraper Facebook — {total} páginas verificadas ===\n")

    guardados_total = 0
    eventos_total = 0
    errores = 0

    for i, red in enumerate(redes, 1):
        print(f"--- [{i}/{total}] {red.parroquia.nombre} ---")
        print(f"URL: {red.url}")

        if red.parroquia.redes_verificadas:
            print(f"  Saltando {red.parroquia.nombre} — redes verificadas")
            continue

        try:
            posts = scrapear_facebook_con_backend(red.url)
            guardados = 0

            for post in posts:
                _, creado = PostParroquia.objects.get_or_create(
                    post_id=post["post_id"],
                    defaults={
                        "parroquia": red.parroquia,
                        "red_social": "facebook",
                        "imagen_url": post["imagen_url"],
                        "fecha_publicacion": post["fecha"],
                        "raw_data": post["raw_data"],
                    }
                )
                if creado:
                    guardados += 1
                    guardados_total += 1

            pendientes = PostParroquia.objects.filter(
                parroquia=red.parroquia,
                procesado=False,
                red_social="facebook"
            )

            for post_obj in pendientes:
                post_dict = {
                    "post_id": post_obj.post_id,
                    "imagen_url": post_obj.imagen_url,
                    "caption": post_obj.raw_data.get("caption", "") if post_obj.raw_data else "",
                }
                resultado = procesar_post_facebook(post_dict)
                post_obj.es_evento = resultado.get("es_evento")
                post_obj.procesado = resultado.get("es_evento") is not None
                post_obj.raw_data = {**(post_obj.raw_data or {}), "gemini": resultado}
                post_obj.save()

                if resultado.get("es_evento") and not resultado.get("es_pasado"):
                    if not hasattr(post_obj, "evento"):
                        crear_evento_desde_post(post_obj, resultado)
                        eventos_total += 1

                if resultado.get("tiene_horarios") and resultado.get("horarios_detectados"):
                    from datetime import timedelta
                    hace_7_dias = timezone.now() - timedelta(days=7)
                    if not ReporteHorario.objects.filter(
                        parroquia=post_obj.parroquia,
                        fuente="scraper",
                        creado_en__gte=hace_7_dias,
                    ).exists():
                        _dias = ["Lunes","Martes","Miércoles","Jueves","Viernes","Sábado","Domingo"]
                        lineas = [
                            f"{_dias[h['dia']]}: {h['horario']}"
                            for h in resultado["horarios_detectados"]
                            if 0 <= h.get("dia", -1) <= 6
                        ]
                        ReporteHorario.objects.create(
                            parroquia=post_obj.parroquia,
                            fuente="scraper",
                            texto_usuario="Horarios detectados desde imagen: " + ", ".join(lineas),
                            imagen_url=post_obj.imagen_url,
                            url_post=post_obj.raw_data.get("url_post", "") if post_obj.raw_data else "",
                            propuesta_ia=resultado["horarios_detectados"],
                            resumen_cambios="Detectado automáticamente desde imagen de la red social.",
                        )

            print(f"  {guardados} guardados")

        except Exception as e:
            errores += 1
            print(f"  ERROR: {e}")

        if i < total:
            espera = random.randint(5, 10)
            print(f"  Esperando {espera}s...")
            time.sleep(espera)

    print(f"\n=== RESUMEN FACEBOOK ===")
    print(f"Páginas procesadas : {total}")
    print(f"Posts nuevos       : {guardados_total}")
    print(f"Eventos detectados : {eventos_total}")
    print(f"Errores            : {errores}")


_SLUG_MAP = {
    "misa": "Misa",
    "retiro": "Retiro",
    "charla": "Charla",
    "bautismo": "Bautismo",
    "confirmacion": "Confirmación",
    "peregrinacion": "Peregrinación",
    "juventud": "Juventud",
    "otro": "Otro",
}


def _resolver_tipo_evento(slug):
    nombre = _SLUG_MAP.get(slug or "otro", "Otro")
    tipo, _ = TipoEvento.objects.get_or_create(
        nombre__iexact=nombre,
        defaults={"nombre": nombre, "activo": True},
    )
    return tipo


def crear_evento_desde_post(post_obj, resultado: dict):
    """Crea un Evento a partir de un PostParroquia clasificado como evento futuro."""

    # Si ya tiene un evento asociado, no crear otro
    if hasattr(post_obj, 'evento'):
        return None

    # Parsear fecha si viene como string DD/MM/YYYY
    fecha = None
    fecha_str = resultado.get("fecha")
    if fecha_str:
        try:
            from datetime import datetime
            fecha = datetime.strptime(fecha_str, "%d/%m/%Y").date()
        except ValueError:
            pass

    # Parsear hora si viene como string HH:MM
    hora = None
    hora_str = resultado.get("hora")
    if hora_str:
        try:
            from datetime import datetime
            hora = datetime.strptime(hora_str, "%H:%M").time()
        except ValueError:
            pass

    evento = Evento.objects.create(
        parroquia=post_obj.parroquia,
        post=post_obj,
        titulo=resultado.get("titulo") or "Sin título",
        tipo=_resolver_tipo_evento(resultado.get("tipo_evento")),
        fecha=fecha,
        hora=hora,
        lugar=resultado.get("lugar"),
        descripcion=resultado.get("descripcion"),
        imagen_url=post_obj.imagen_url,
    )

    print(f"     Evento creado: {evento}")
    return evento


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Scraper de redes sociales")
    parser.add_argument("--produccion", action="store_true", help="Procesar todas las parroquias de Instagram verificadas")
    parser.add_argument("--facebook", action="store_true", help="Procesar todas las páginas de Facebook verificadas")
    args = parser.parse_args()

    if args.facebook:
        main_produccion_facebook()
    elif args.produccion:
        main_produccion()
    else:
        main()
