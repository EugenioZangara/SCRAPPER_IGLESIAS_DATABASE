import glob as _glob
import logging
import math
import os
from datetime import date, datetime, time as dtime, timedelta
from django.views.decorators.csrf import csrf_exempt, ensure_csrf_cookie
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth import authenticate, login as auth_login
from django.contrib.auth.decorators import login_required
from django.db.models import Case, Count, IntegerField, Q, Value, When
from django.http import HttpResponse, HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

logger = logging.getLogger(__name__)

from .models import Parroquia, RedSocial, PostParroquia, TipoEvento, Evento, CategoriaEvento, HorarioMisa, ScraperJob, ReporteHorario, ValidacionHorario, Banner, VotoHorario, ComentarioParroquia, PerfilUsuario, HorarioPropuestoAgregado

from django.conf import settings
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.text import slugify
from urllib.parse import urlparse
from django.views.decorators.http import require_POST
from django.urls import reverse
from django.contrib import messages
from django.utils import timezone


def _foto_url_local(parroquia):
    """Return URL for local photo from imagenes_parroquias/ if it exists, else None."""
    provincia_slug = slugify(parroquia.provincia or '')
    pattern = str(settings.BASE_DIR / 'imagenes_parroquias' / provincia_slug / f'{parroquia.pk}__*')
    matches = _glob.glob(pattern)
    if matches:
        filename = os.path.basename(matches[0])
        return f'/imagenes-parroquias/{provincia_slug}/{filename}'
    return None


_DIAS_SCHEMA = {0: 'Mo', 1: 'Tu', 2: 'We', 3: 'Th', 4: 'Fr', 5: 'Sa', 6: 'Su'}


def _generar_opening_hours(horarios_qs):
    resultado = []
    for hm in horarios_qs:
        dia_code = _DIAS_SCHEMA.get(hm.dia_semana, '')
        if not dia_code:
            continue
        horas = [h.strip() for h in (hm.horarios or '').replace('·', ',').split(',') if h.strip()]
        for hora in horas:
            try:
                partes = hora.split(':')
                h = int(partes[0])
                m = int(partes[1]) if len(partes) > 1 else 0
                h_fin = (h + 1) % 24
                resultado.append(f"{dia_code} {h:02d}:{m:02d}-{h_fin:02d}:{m:02d}")
            except (ValueError, IndexError):
                continue
    return resultado


def _armar_grupo_red(parroquia, tipo, etiqueta):
    redes = [
        red
        for red in parroquia.redes.all()
        if red.activo and red.tipo == tipo
    ]

    return {
        "tipo": tipo,
        "etiqueta": etiqueta,
        "redes": redes,
        "red_principal": next(
            (red for red in redes if red.verificado),
            redes[0] if redes else None,
        ),
        "red_pendiente": next(
            (red for red in redes if not red.verificado),
            None,
        ),
        "verificada": any(red.verificado for red in redes),
    }


def _estado_eventos(parroquia):
    hoy = date.today()
    todos = list(parroquia.eventos.all())

    eventos_futuros = [
        e for e in todos
        if e.activo and (e.fecha is None or e.fecha >= hoy)
    ][:5]

    eventos_pasados = [
        e for e in todos
        if e.activo and e.fecha and e.fecha < hoy
    ]

    if not eventos_futuros:
        resultado = {"estado": "sin_eventos", "etiqueta": "Sin eventos", "eventos": [], "completos": [], "incompletos": []}
    else:
        completos = [e for e in eventos_futuros if e.fecha and e.lugar]
        incompletos = [e for e in eventos_futuros if not e.fecha or not e.lugar]

        if incompletos and completos:
            estado = "requiere_verificacion"
            etiqueta = "Requiere verificación"
        elif incompletos and not completos:
            estado = "todos_incompletos"
            etiqueta = "Requiere verificación"
        else:
            estado = "validos"
            etiqueta = "Con eventos"

        resultado = {
            "estado": estado,
            "etiqueta": etiqueta,
            "eventos": eventos_futuros,
            "completos": completos,
            "incompletos": incompletos,
        }

    resultado["eventos_pasados"] = eventos_pasados
    return resultado

def _enriquecer_parroquias(parroquias):
    tipos_redes = RedSocial.TIPO_CHOICES

    for parroquia in parroquias:
        redes_activas = []
        for red in parroquia.redes.all():
            if not red.activo:
                continue
            redes_activas.append(red)

        parroquia.redes_resumen = [
            _armar_grupo_red(parroquia, tipo, etiqueta)
            for tipo, etiqueta in tipos_redes
        ]
        parroquia.redes_activas_resumen = redes_activas
        parroquia.eventos_estado = _estado_eventos(parroquia)

    return parroquias


def lista_parroquias(request):
    parroquias = (
        Parroquia.objects.annotate(total_redes=Count("redes", distinct=True))
        .prefetch_related("redes", "eventos")
        .all()
        .order_by("nombre")
    )

    query = request.GET.get("q", "").strip()
    estado_web = request.GET.get("web", "").strip()
    estado_redes = request.GET.get("redes", "").strip()
    estado_detalles = request.GET.get("detalles", "").strip()

    if query:
        parroquias = parroquias.filter(
            Q(nombre__icontains=query)
            | Q(barrio__icontains=query)
            | Q(vicaria__icontains=query)
            | Q(decanato__icontains=query)
            | Q(direccion__icontains=query)
        )

    if estado_web == "con":
        parroquias = parroquias.exclude(sitio_web__isnull=True).exclude(sitio_web="")
    elif estado_web == "sin":
        parroquias = parroquias.filter(Q(sitio_web__isnull=True) | Q(sitio_web=""))

    if estado_redes == "con":
        parroquias = parroquias.filter(redes__activo=True).distinct()
    elif estado_redes == "sin":
        parroquias = parroquias.exclude(redes__activo=True)

    if estado_detalles == "completos":
        parroquias = parroquias.filter(detalles_completos=True)
    elif estado_detalles == "pendientes":
        parroquias = parroquias.filter(detalles_completos=False)

    parroquias = _enriquecer_parroquias(list(parroquias))

    stats_base = Parroquia.objects.all()
    stats = stats_base.aggregate(
        total=Count("id", distinct=True),
        con_web=Count(
            "id",
            filter=Q(sitio_web__isnull=False) & ~Q(sitio_web=""),
            distinct=True,
        ),
        con_redes=Count("id", filter=Q(redes__activo=True), distinct=True),
        detalles_completos=Count("id", filter=Q(detalles_completos=True), distinct=True),
        **{
            f"con_{tipo}": Count(
                "id",
                filter=Q(redes__tipo=tipo, redes__activo=True),
                distinct=True,
            )
            for tipo, _ in RedSocial.TIPO_CHOICES
        },
    )
    stats_redes = [
        {
            "tipo": tipo,
            "etiqueta": etiqueta,
            "cantidad": stats.get(f"con_{tipo}", 0),
        }
        for tipo, etiqueta in RedSocial.TIPO_CHOICES
    ]

    ultimo_job = ScraperJob.objects.filter(
        estado="completado"
    ).order_by("-iniciado_en").first()

    duracion = None
    if ultimo_job and ultimo_job.actualizado_en and ultimo_job.iniciado_en:
        delta = ultimo_job.actualizado_en - ultimo_job.iniciado_en
        minutos = int(delta.total_seconds() // 60)
        duracion = f"{minutos} min" if minutos > 0 else "< 1 min"

    return render(
        request,
        "iglesias/lista_parroquias.html",
        {
            "parroquias": parroquias,
            "stats": stats,
            "stats_redes": stats_redes,
            "tipos_redes": RedSocial.TIPO_CHOICES,
            "filtros": {
                "q": query,
                "web": estado_web,
                "redes": estado_redes,
                "detalles": estado_detalles,
            },
            "ultimo_job": ultimo_job,
            "ultimo_job_duracion": duracion,
        },
    )


def detalle_parroquia(request, pk):
    parroquia = get_object_or_404(
        Parroquia.objects.prefetch_related(
            "redes", "eventos", "horarios_misa"
        ).select_related("info_bai"),
        pk=pk,
    )
    eventos_estado = _estado_eventos(parroquia)

    anterior = Parroquia.objects.filter(nombre__lt=parroquia.nombre).order_by("-nombre").first()
    siguiente = Parroquia.objects.filter(nombre__gt=parroquia.nombre).order_by("nombre").first()
    ig_verificada = any(
        r.tipo == "instagram" and r.activo and r.verificado
        for r in parroquia.redes.all()
    )

    return render(
        request,
        "iglesias/detalle_parroquia.html",
        {
            "parroquia": parroquia,
            "eventos_estado": eventos_estado,
            "anterior": anterior,
            "siguiente": siguiente,
            "ig_verificada": ig_verificada,
        },
    )


@staff_member_required
@require_POST
def verificar_red_social(request, pk):
    try:
        red = RedSocial.objects.get(pk=pk)
    except RedSocial.DoesNotExist:
        messages.warning(request, "La red social ya no existe.")
        next_url = request.POST.get("next", "").strip()
        if next_url and next_url.startswith("/"):
            return redirect(next_url)
        return redirect("iglesias:lista_parroquias")

    red.verificado = True
    red.activo = True
    red.save(update_fields=["verificado", "activo"])

    if request.headers.get("HX-Request"):
        grupo = _armar_grupo_red(red.parroquia, red.tipo, red.get_tipo_display())
        return render(
            request,
            "iglesias/partials/red_status.html",
            {"grupo": grupo},
        )

    return redirect(request.POST.get("next") or "iglesias:lista_parroquias")


@require_POST
def eliminar_parroquia(request, pk):
    if not request.user.is_staff:
        return HttpResponse("Forbidden", status=403)

    parroquia = get_object_or_404(Parroquia, pk=pk)
    nombre = parroquia.nombre

    confirmacion = request.POST.get("confirmar", "").strip()
    if confirmacion != "ELIMINAR":
        messages.error(
            request,
            "Para eliminar escribí ELIMINAR en el campo de confirmación."
        )
        return redirect("iglesias:detalle_parroquia", pk=pk)

    parroquia.delete()
    messages.success(request, f"Parroquia '{nombre}' eliminada correctamente.")
    return redirect("iglesias:lista_parroquias")


@staff_member_required
@require_POST
def eliminar_red_social(request, pk):
    red = get_object_or_404(RedSocial, pk=pk)
    parroquia = red.parroquia
    tipo = red.tipo
    etiqueta = red.get_tipo_display()
    red.delete()

    if not parroquia.redes.filter(activo=True).exists():
        parroquia.tiene_redes = False
        parroquia.save(update_fields=["tiene_redes", "actualizado_el"])

    if request.headers.get("HX-Request"):
        grupo = _armar_grupo_red(parroquia, tipo, etiqueta)
        return render(
            request,
            "iglesias/partials/red_status.html",
            {"grupo": grupo},
        )

    return redirect(request.POST.get("next") or "iglesias:lista_parroquias")

@require_POST
def aprobar_evento(request, pk):
    if not request.user.is_staff:
        return HttpResponse("Forbidden", status=403)
    evento = get_object_or_404(Evento, pk=pk)
    evento.verificado = True
    evento.activo = True
    evento.save(update_fields=["verificado", "activo"])

    if request.headers.get("HX-Request"):
        return render(request, "iglesias/partials/evento_fila.html", {"evento": evento})

    return redirect(request.POST.get("next") or "iglesias:lista_parroquias")


@require_POST
def rechazar_evento(request, pk):
    if not request.user.is_staff:
        return HttpResponse("Forbidden", status=403)
    evento = get_object_or_404(Evento, pk=pk)
    evento.activo = False
    evento.verificado = False
    evento.save(update_fields=["activo", "verificado"])

    if request.headers.get("HX-Request"):
        return render(request, "iglesias/partials/evento_fila.html", {"evento": evento})

    return redirect(request.POST.get("next") or "iglesias:lista_parroquias")


@ensure_csrf_cookie
def moderacion_eventos(request):
    if not request.user.is_staff:
        from django.http import HttpResponse
        return HttpResponse("Forbidden", status=403)

    hoy = date.today()

    def es_futuro(qs):
        return qs.filter(Q(fecha__isnull=True) | Q(fecha__gte=hoy))

    estado = request.GET.get("estado", "pendiente")

    if estado == "pendiente":
        eventos = es_futuro(Evento.objects.filter(verificado=False, activo=True))
    elif estado == "aprobado":
        eventos = es_futuro(Evento.objects.filter(verificado=True, activo=True))
    elif estado == "rechazado":
        eventos = es_futuro(Evento.objects.filter(activo=False))
    else:
        eventos = es_futuro(Evento.objects.all())

    eventos = eventos.select_related("parroquia", "tipo", "post").order_by("fecha", "creado_en")

    counts = {
        "pendiente": es_futuro(Evento.objects.filter(verificado=False, activo=True)).count(),
        "aprobado": es_futuro(Evento.objects.filter(verificado=True, activo=True)).count(),
        "rechazado": es_futuro(Evento.objects.filter(activo=False)).count(),
        "total": es_futuro(Evento.objects.all()).count(),
    }

    ultimo_job = ScraperJob.objects.filter(
        estado="completado"
    ).order_by("-actualizado_en").first()

    jobs_recientes = ScraperJob.objects.filter(
        estado="completado"
    ).order_by("-iniciado_en")[:5]

    return render(request, "iglesias/moderacion_eventos.html", {
        "eventos": eventos,
        "estado": estado,
        "counts": counts,
        "total_pasados": Evento.objects.filter(
            fecha__lt=hoy, fecha__isnull=False
        ).count(),
        "total_cuentas_ig": RedSocial.objects.filter(
            tipo="instagram", activo=True, verificado=True
        ).count(),
        "total_cuentas_fb": RedSocial.objects.filter(
            tipo="facebook", activo=True, verificado=True
        ).count(),
        "ultimo_job": ultimo_job,
        "jobs_recientes": jobs_recientes,
    })


def moderacion_eventos_pasados(request):
    if not request.user.is_staff:
        from django.http import HttpResponse
        return HttpResponse("Forbidden", status=403)

    hoy = date.today()
    eventos = (
        Evento.objects.filter(fecha__lt=hoy, fecha__isnull=False)
        .select_related("parroquia", "post")
        .order_by("-fecha")
    )

    return render(request, "iglesias/moderacion_eventos_pasados.html", {
        "eventos": eventos,
        "total": eventos.count(),
    })


def scraper_estado(request):
    if not request.user.is_staff:
        return JsonResponse({"activo": False})
    from datetime import timedelta
    from django.utils import timezone as tz

    # Marcar como completados jobs que llevan más de 60 min corriendo
    hace_60min = tz.now() - timedelta(minutes=60)
    ScraperJob.objects.filter(
        estado="corriendo",
        iniciado_en__lt=hace_60min
    ).update(estado="completado", mensaje_final="Tiempo límite alcanzado")

    job = ScraperJob.objects.filter(estado="corriendo").first()
    if not job:
        return JsonResponse({"activo": False})
    ...

    return JsonResponse({
        "activo": True,
        "estado": job.estado,
        "total": job.total,
        "procesados": job.procesados,
        "posts_nuevos": job.posts_nuevos,
        "eventos_nuevos": job.eventos_nuevos,
        "errores": job.errores,
        "parroquia_actual": job.parroquia_actual,
        "mensaje_final": job.mensaje_final,
        "pk": job.pk,
    })


def scraper_estado_resultado(request):
    if not request.user.is_staff:
        return JsonResponse({"hay_resultado": False})
    from datetime import timedelta
    from django.utils import timezone as tz

    hace_10min = tz.now() - timedelta(minutes=10)

    job = ScraperJob.objects.filter(
        estado="completado",
        actualizado_en__gte=hace_10min
    ).order_by("-actualizado_en").first()

    if not job:
        return JsonResponse({"hay_resultado": False})

    return JsonResponse({
        "hay_resultado": True,
        "mensaje_final": job.mensaje_final,
        "posts_nuevos": job.posts_nuevos,
        "eventos_nuevos": job.eventos_nuevos,
        "errores": job.errores,
    })


@require_POST
def ejecutar_scraper_completo(request):
    if not request.user.is_staff:
        return HttpResponse("Forbidden", status=403)

    import threading

    redes_ig = list(RedSocial.objects.filter(
        tipo="instagram", activo=True, verificado=True
    ).select_related("parroquia"))

    redes_fb = list(RedSocial.objects.filter(
        tipo="facebook", activo=True, verificado=True
    ).select_related("parroquia"))

    job = ScraperJob.objects.create(
        total=len(redes_ig) + len(redes_fb),
        procesados=0,
        origen="manual",
    )

    def correr_scraper():
        from scraper_redes.run import scrapear_con_backend, scrapear_facebook_con_backend, crear_evento_desde_post
        from scraper_redes.procesador import procesar_post, procesar_post_facebook
        from apps.iglesias.models import PostParroquia
        import time, random

        for i, red in enumerate(redes_ig):
            if red.parroquia.redes_verificadas:
                job.procesados += 1
                job.save(update_fields=["procesados", "actualizado_en"])
                continue
            job.parroquia_actual = red.parroquia.nombre
            job.procesados = i
            job.save(update_fields=["parroquia_actual", "procesados", "actualizado_en"])
            try:
                posts = scrapear_con_backend(red.url)
                guardados_parroquia = 0
                for post in posts:
                    _, creado = PostParroquia.objects.get_or_create(
                        post_id=post["post_id"],
                        defaults={
                            "parroquia": red.parroquia,
                            "red_social": "instagram",
                            "imagen_url": post["imagen_url"],
                            "fecha_publicacion": post["fecha"],
                            "raw_data": post["raw_data"],
                        }
                    )
                    if creado:
                        guardados_parroquia += 1

                eventos_parroquia = 0
                pendientes = PostParroquia.objects.filter(
                    parroquia=red.parroquia, procesado=False
                )
                for post_obj in pendientes:
                    post_dict = {
                        "post_id": post_obj.post_id,
                        "imagen_url": post_obj.imagen_url,
                        "caption": post_obj.raw_data.get("caption", "") if post_obj.raw_data else "",
                    }
                    resultado = procesar_post(post_dict)
                    post_obj.es_evento = resultado.get("es_evento")
                    post_obj.procesado = resultado.get("es_evento") is not None
                    post_obj.raw_data = {**(post_obj.raw_data or {}), "gemini": resultado}
                    post_obj.save()

                    if resultado.get("es_evento") and not resultado.get("es_pasado"):
                        if not hasattr(post_obj, "evento"):
                            crear_evento_desde_post(post_obj, resultado)
                            eventos_parroquia += 1

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

                job.posts_nuevos += guardados_parroquia
                job.eventos_nuevos += eventos_parroquia
                job.save(update_fields=["posts_nuevos", "eventos_nuevos", "actualizado_en"])

                time.sleep(random.uniform(2, 4))

            except Exception as e:
                job.errores += 1
                job.save(update_fields=["errores", "actualizado_en"])
                print(f"ERROR scrapeando {red.parroquia.nombre}: {e}")

        job.procesados = len(redes_ig)
        job.save(update_fields=["procesados", "actualizado_en"])

        for red in redes_fb:
            if red.parroquia.redes_verificadas:
                job.procesados += 1
                job.save(update_fields=["procesados", "actualizado_en"])
                continue
            job.parroquia_actual = f"[FB] {red.parroquia.nombre}"
            job.procesados += 1
            job.save(update_fields=["parroquia_actual", "procesados", "actualizado_en"])
            try:
                posts = scrapear_facebook_con_backend(red.url)
                guardados_fb = 0
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
                        guardados_fb += 1

                eventos_fb = 0
                pendientes_fb = PostParroquia.objects.filter(
                    parroquia=red.parroquia,
                    procesado=False,
                    red_social="facebook"
                )
                for post_obj in pendientes_fb:
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
                            eventos_fb += 1

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

                job.posts_nuevos += guardados_fb
                job.eventos_nuevos += eventos_fb
                job.save(update_fields=["posts_nuevos", "eventos_nuevos", "actualizado_en"])

                time.sleep(random.uniform(2, 4))

            except Exception as e:
                job.errores += 1
                job.save(update_fields=["errores", "actualizado_en"])
                print(f"ERROR scrapeando Facebook {red.parroquia.nombre}: {e}")

        job.parroquia_actual = ""
        job.estado = "completado"
        job.mensaje_final = (
            f"{job.total} parroquias · "
            f"{job.posts_nuevos} posts nuevos · "
            f"{job.eventos_nuevos} eventos detectados · "
            f"{job.errores} errores"
        )
        job.save()

    thread = threading.Thread(target=correr_scraper, daemon=True)
    thread.start()

    messages.success(
        request,
        f"Scraping iniciado — {len(redes_ig)} Instagram + {len(redes_fb)} Facebook."
    )

    next_url = request.POST.get("next", "").strip()
    if next_url and next_url.startswith("/"):
        return redirect(next_url)
    return redirect("iglesias:moderacion_eventos")


@csrf_exempt
@require_POST
def detener_scraper(request):
    if not request.user.is_staff:
        return HttpResponse("Forbidden", status=403)
    jobs = ScraperJob.objects.filter(estado="corriendo")
    count = jobs.update(
        estado="completado",
        mensaje_final="Detenido manualmente por el usuario"
    )
    messages.warning(request, f"Scraper detenido ({count} job/s cancelado/s).")
    next_url = request.POST.get("next", "").strip()
    if next_url and next_url.startswith("/"):
        return redirect(next_url)
    return redirect("iglesias:moderacion_eventos")


def editar_evento(request, pk):
    if not request.user.is_staff:
        return HttpResponse("Forbidden", status=403)
    evento = get_object_or_404(Evento, pk=pk)
    parroquia = evento.parroquia
    categorias = CategoriaEvento.objects.filter(activo=True)

    if request.method == "POST":
        from datetime import datetime as dt

        evento.titulo = request.POST.get("titulo", evento.titulo).strip()
        tipo_id = request.POST.get("tipo", "").strip()
        evento.tipo_id = int(tipo_id) if tipo_id else None
        evento.descripcion = request.POST.get("descripcion", "").strip() or None

        fecha_str = request.POST.get("fecha", "").strip()
        if fecha_str:
            try:
                evento.fecha = dt.strptime(fecha_str, "%Y-%m-%d").date()
            except ValueError:
                pass
        else:
            evento.fecha = None

        hora_str = request.POST.get("hora", "").strip()
        if hora_str:
            try:
                evento.hora = dt.strptime(hora_str, "%H:%M").time()
            except ValueError:
                pass
        else:
            evento.hora = None

        fecha_fin_str = request.POST.get("fecha_fin", "").strip()
        hora_fin_str = request.POST.get("hora_fin", "").strip()
        if fecha_fin_str:
            try:
                fecha_fin = dt.strptime(fecha_fin_str, "%Y-%m-%d")
                if hora_fin_str:
                    hora_fin = dt.strptime(hora_fin_str, "%H:%M")
                    fecha_fin = fecha_fin.replace(hour=hora_fin.hour, minute=hora_fin.minute)
                evento.fecha_fin = fecha_fin
            except ValueError:
                pass
        else:
            evento.fecha_fin = None

        categoria_id = request.POST.get("categoria", "").strip()
        evento.categoria_id = int(categoria_id) if categoria_id else None
        evento.url_externa = request.POST.get("url_externa", "").strip() or None
        evento.audiencia = request.POST.get("audiencia", "").strip() or None
        evento.lugar = request.POST.get("lugar", "").strip() or None

        edad_desde = request.POST.get("edad_desde", "").strip()
        edad_hasta = request.POST.get("edad_hasta", "").strip()
        evento.edad_desde = max(0, min(120, int(edad_desde))) if edad_desde and edad_desde.isdigit() else 0
        evento.edad_hasta = max(0, min(120, int(edad_hasta))) if edad_hasta and edad_hasta.isdigit() else 100

        evento.gratuito = request.POST.get("gratuito") == "si"
        capacidad_str = request.POST.get("capacidad", "").strip()
        evento.capacidad = int(capacidad_str) if capacidad_str else None

        evento.ubicacion_lugar = request.POST.get("ubicacion_lugar", "").strip() or None
        evento.ubicacion_direccion = request.POST.get("ubicacion_direccion", "").strip() or None
        evento.ubicacion_ciudad = request.POST.get("ubicacion_ciudad", "Buenos Aires").strip()
        evento.ubicacion_cp = request.POST.get("ubicacion_cp", "").strip() or None
        evento.ubicacion_provincia = request.POST.get("ubicacion_provincia", "Buenos Aires").strip()

        evento.save()

        next_url = request.POST.get("next", "").strip()
        if next_url and next_url.startswith("/"):
            return redirect(next_url)
        return redirect("iglesias:detalle_parroquia", pk=parroquia.pk)

    gemini_data = {}
    if evento.post and evento.post.raw_data and "gemini" in evento.post.raw_data:
        gemini_data = evento.post.raw_data["gemini"]

    if not evento.ubicacion_lugar and evento.lugar:
        evento.ubicacion_lugar = evento.lugar

    hora_fin_str = evento.fecha_fin.strftime("%H:%M") if evento.fecha_fin else ""

    return render(request, "iglesias/editar_evento.html", {
        "evento": evento,
        "parroquia": parroquia,
        "categorias": categorias,
        "tipos": TipoEvento.objects.filter(activo=True),
        "audiencia_choices": Evento.AUDIENCIA_CHOICES,
        "gemini_data": gemini_data,
        "hora_fin_str": hora_fin_str,
        "next": request.GET.get("next", ""),
    })


def aprobar_extendido(request, pk):
    if not request.user.is_staff:
        from django.http import HttpResponse
        return HttpResponse("Forbidden", status=403)

    evento = get_object_or_404(
        Evento.objects.select_related("post", "parroquia", "categoria"),
        pk=pk,
    )
    categorias = CategoriaEvento.objects.filter(activo=True)

    if request.method == "POST":
        from datetime import datetime as dt

        evento.titulo = request.POST.get("titulo", evento.titulo).strip()
        tipo_id = request.POST.get("tipo", "").strip()
        evento.tipo_id = int(tipo_id) if tipo_id else None
        evento.descripcion = request.POST.get("descripcion", "").strip() or None

        fecha_str = request.POST.get("fecha", "").strip()
        if fecha_str:
            try:
                evento.fecha = dt.strptime(fecha_str, "%Y-%m-%d").date()
            except ValueError:
                pass
        else:
            evento.fecha = None

        hora_str = request.POST.get("hora", "").strip()
        if hora_str:
            try:
                evento.hora = dt.strptime(hora_str, "%H:%M").time()
            except ValueError:
                pass
        else:
            evento.hora = None

        fecha_fin_str = request.POST.get("fecha_fin", "").strip()
        hora_fin_str = request.POST.get("hora_fin", "").strip()
        if fecha_fin_str:
            try:
                fecha_fin = dt.strptime(fecha_fin_str, "%Y-%m-%d")
                if hora_fin_str:
                    hora_fin = dt.strptime(hora_fin_str, "%H:%M")
                    fecha_fin = fecha_fin.replace(hour=hora_fin.hour, minute=hora_fin.minute)
                evento.fecha_fin = fecha_fin
            except ValueError:
                pass
        else:
            evento.fecha_fin = None

        categoria_id = request.POST.get("categoria", "").strip()
        evento.categoria_id = int(categoria_id) if categoria_id else None
        evento.url_externa = request.POST.get("url_externa", "").strip() or None
        evento.audiencia = request.POST.get("audiencia", "").strip() or None
        evento.lugar = request.POST.get("lugar", "").strip() or None

        edad_desde = request.POST.get("edad_desde", "").strip()
        edad_hasta = request.POST.get("edad_hasta", "").strip()
        evento.edad_desde = max(0, min(120, int(edad_desde))) if edad_desde and edad_desde.isdigit() else 0
        evento.edad_hasta = max(0, min(120, int(edad_hasta))) if edad_hasta and edad_hasta.isdigit() else 100

        evento.gratuito = request.POST.get("gratuito") == "si"
        capacidad_str = request.POST.get("capacidad", "").strip()
        evento.capacidad = int(capacidad_str) if capacidad_str else None

        evento.ubicacion_lugar = request.POST.get("ubicacion_lugar", "").strip() or None
        evento.ubicacion_direccion = request.POST.get("ubicacion_direccion", "").strip() or None
        evento.ubicacion_ciudad = request.POST.get("ubicacion_ciudad", "Buenos Aires").strip()
        evento.ubicacion_cp = request.POST.get("ubicacion_cp", "").strip() or None
        evento.ubicacion_provincia = request.POST.get("ubicacion_provincia", "Buenos Aires").strip()

        evento.verificado = True
        evento.activo = True
        evento.save()

        try:
            from .sheets import exportar_evento_a_sheets
            exportado = exportar_evento_a_sheets(evento)
            if exportado:
                evento.exportado_sheets = True
                evento.save(update_fields=["exportado_sheets"])
                messages.success(
                    request,
                    f'Evento "{evento.titulo}" aprobado y exportado a Google Sheets.'
                )
            else:
                messages.warning(
                    request,
                    f'Evento "{evento.titulo}" aprobado, pero no se pudo exportar a Google Sheets.'
                )
        except Exception as e:
            messages.warning(
                request,
                f'Evento "{evento.titulo}" aprobado, pero falló la exportación a Sheets: {str(e)[:100]}'
            )

        next_url = request.POST.get("next", "").strip()
        if next_url and next_url.startswith("/"):
            return redirect(next_url)
        return redirect("iglesias:moderacion_eventos")

    gemini_data = {}
    if evento.post and evento.post.raw_data and "gemini" in evento.post.raw_data:
        gemini_data = evento.post.raw_data["gemini"]

    if not evento.ubicacion_lugar and evento.lugar:
        evento.ubicacion_lugar = evento.lugar

    hora_fin_str = evento.fecha_fin.strftime("%H:%M") if evento.fecha_fin else ""

    return render(request, "iglesias/aprobar_extendido.html", {
        "evento": evento,
        "categorias": categorias,
        "tipos": TipoEvento.objects.filter(activo=True),
        "audiencia_choices": Evento.AUDIENCIA_CHOICES,
        "gemini_data": gemini_data,
        "hora_fin_str": hora_fin_str,
        "next": request.GET.get("next", ""),
    })


@require_POST
def editar_nombre_parroquia(request, pk):
    if not request.user.is_staff:
        return HttpResponse("Forbidden", status=403)
    parroquia = get_object_or_404(Parroquia, pk=pk)
    nombre = request.POST.get("nombre", "").strip()
    if nombre and len(nombre) >= 3:
        parroquia.nombre = nombre.upper()
        parroquia.save(update_fields=["nombre"])
    return redirect("iglesias:detalle_parroquia", pk=pk)


@require_POST
def agregar_red_social(request, pk):
    if not request.user.is_staff:
        return HttpResponse("Forbidden", status=403)
    parroquia = get_object_or_404(Parroquia, pk=pk)
    tipo = request.POST.get("tipo", "").strip()
    url = request.POST.get("url", "").strip()
    username = request.POST.get("username", "").strip()

    TIPOS_VALIDOS = ["facebook", "instagram", "youtube", "tiktok", "otro"]
    if tipo not in TIPOS_VALIDOS:
        messages.error(request, "Tipo de red social inválido.")
        return redirect("iglesias:detalle_parroquia", pk=pk)

    parsed = urlparse(url if url.startswith("http") else "https://" + url)
    if parsed.scheme not in ('http', 'https'):
        messages.error(request, "URL inválida.")
        return redirect(request.META.get('HTTP_REFERER') or 'iglesias:lista_parroquias')
    url = parsed.geturl()

    from .models import RedSocial
    _, creada = RedSocial.objects.get_or_create(
        parroquia=parroquia,
        url=url,
        defaults={
            "tipo": tipo,
            "username": username or None,
            "activo": True,
            "verificado": True,
        }
    )
    if creada:
        parroquia.tiene_redes = True
        parroquia.save(update_fields=["tiene_redes", "actualizado_el"])
        messages.success(request, f"Red social {tipo} agregada correctamente.")
    else:
        messages.warning(request, "Esa URL ya estaba registrada.")

    return redirect("iglesias:detalle_parroquia", pk=pk)


def editar_seccion_contacto(request, pk):
    if not request.user.is_staff:
        return HttpResponseForbidden("No autorizado")
    parroquia = get_object_or_404(Parroquia, pk=pk)

    if request.method == "POST":
        parroquia.telefonos = request.POST.get("telefonos", "").strip() or None
        parroquia.mail_1 = request.POST.get("mail_1", "").strip() or None
        parroquia.mail_2 = request.POST.get("mail_2", "").strip() or None
        parroquia.sitio_web = request.POST.get("sitio_web", "").strip() or None
        parroquia.save(update_fields=["telefonos", "mail_1", "mail_2", "sitio_web"])
        editing = False
    else:
        editing = request.GET.get("cancelar") != "1"

    return render(request, "iglesias/partials/seccion_contacto.html", {
        "parroquia": parroquia,
        "editing": editing,
    })


def editar_seccion_ubicacion(request, pk):
    if not request.user.is_staff:
        return HttpResponseForbidden("No autorizado")
    parroquia = get_object_or_404(Parroquia, pk=pk)

    if request.method == "POST":
        parroquia.direccion = request.POST.get("direccion", "").strip() or None
        parroquia.codigo_postal = request.POST.get("codigo_postal", "").strip() or None
        parroquia.barrio = request.POST.get("barrio", "").strip() or None
        parroquia.vicaria = request.POST.get("vicaria", "").strip() or None
        parroquia.decanato = request.POST.get("decanato", "").strip() or None
        parroquia.save(update_fields=["direccion", "codigo_postal", "barrio", "vicaria", "decanato"])
        editing = False
    else:
        editing = request.GET.get("cancelar") != "1"

    return render(request, "iglesias/partials/seccion_ubicacion.html", {
        "parroquia": parroquia,
        "editing": editing,
    })


def editar_seccion_clero(request, pk):
    if not request.user.is_staff:
        return HttpResponseForbidden("No autorizado")
    parroquia = get_object_or_404(Parroquia, pk=pk)

    if request.method == "POST":
        parroquia.clero_cargo = request.POST.get("clero_cargo", "").strip() or None
        parroquia.parroco = request.POST.get("parroco", "").strip() or None
        parroquia.fecha_ereccion_canonica = request.POST.get("fecha_ereccion_canonica", "").strip() or None
        parroquia.comenzo_a_funcionar = request.POST.get("comenzo_a_funcionar", "").strip() or None
        parroquia.limite_parroquial = request.POST.get("limite_parroquial", "").strip() or None
        parroquia.save(update_fields=["clero_cargo", "parroco", "fecha_ereccion_canonica", "comenzo_a_funcionar", "limite_parroquial"])
        editing = False
    else:
        editing = request.GET.get("cancelar") != "1"

    return render(request, "iglesias/partials/seccion_clero.html", {
        "parroquia": parroquia,
        "editing": editing,
    })


@require_POST
def scrapear_parroquia(request, pk):
    if not request.user.is_staff:
        return HttpResponse("Forbidden", status=403)

    parroquia = get_object_or_404(Parroquia, pk=pk)
    red = parroquia.redes.filter(
        tipo="instagram", activo=True, verificado=True
    ).first()

    if not red:
        messages.error(
            request,
            f'No hay cuenta de Instagram verificada para {parroquia.nombre}.'
        )
        return redirect("iglesias:detalle_parroquia", pk=pk)

    import threading

    def correr_scraper_parroquia():
        from scraper_redes.run import scrapear_con_backend, crear_evento_desde_post
        from scraper_redes.procesador import procesar_post
        from apps.iglesias.models import PostParroquia, ScraperJob

        job = ScraperJob.objects.create(
            total=1,
            procesados=0,
            parroquia_actual=parroquia.nombre,
        )
        try:
            posts = scrapear_con_backend(red.url)
            guardados = 0
            eventos_nuevos = 0

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

            pendientes = PostParroquia.objects.filter(
                parroquia=parroquia, procesado=False
            )

            for post_obj in pendientes:
                post_dict = {
                    "post_id": post_obj.post_id,
                    "imagen_url": post_obj.imagen_url,
                    "caption": post_obj.raw_data.get("caption", "") if post_obj.raw_data else "",
                }
                resultado = procesar_post(post_dict)
                post_obj.es_evento = resultado.get("es_evento")
                post_obj.procesado = resultado.get("es_evento") is not None
                post_obj.raw_data = {**(post_obj.raw_data or {}), "gemini": resultado}
                post_obj.save()

                if resultado.get("es_evento") and not resultado.get("es_pasado"):
                    if not hasattr(post_obj, "evento"):
                        crear_evento_desde_post(post_obj, resultado)
                        eventos_nuevos += 1

                if resultado.get("tiene_horarios") and resultado.get("horarios_detectados"):
                    from datetime import timedelta
                    hace_7_dias = timezone.now() - timedelta(days=7)
                    if not ReporteHorario.objects.filter(
                        parroquia=parroquia,
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
                            parroquia=parroquia,
                            fuente="scraper",
                            texto_usuario="Horarios detectados desde imagen: " + ", ".join(lineas),
                            imagen_url=post_obj.imagen_url,
                            url_post=post_obj.raw_data.get("url_post", "") if post_obj.raw_data else "",
                            propuesta_ia=resultado["horarios_detectados"],
                            resumen_cambios="Detectado automáticamente desde imagen de la red social.",
                        )

            job.posts_nuevos = guardados
            job.eventos_nuevos = eventos_nuevos
            job.procesados = 1
            job.estado = "completado"
            job.parroquia_actual = ""
            job.mensaje_final = (
                f"{guardados} posts nuevos · "
                f"{eventos_nuevos} eventos detectados"
            )
            job.save()

        except Exception as e:
            job.estado = "error"
            job.mensaje_final = str(e)[:200]
            job.save()
            print(f"ERROR scraper {parroquia.nombre}: {e}")

    thread = threading.Thread(target=correr_scraper_parroquia, daemon=True)
    thread.start()

    messages.success(request, f"Scraping de {parroquia.nombre[:30]} iniciado.")
    return redirect("iglesias:detalle_parroquia", pk=pk)


_TIPO_SLUG_MAP = {
    "misa": "Misa",
    "retiro": "Retiro",
    "charla": "Charla",
    "bautismo": "Bautismo",
    "confirmacion": "Confirmación",
    "peregrinacion": "Peregrinación",
    "juventud": "Juventud",
    "otro": "Otro",
}


def _crear_evento_desde_post(post_obj, resultado: dict):
    from datetime import datetime as dt
    if hasattr(post_obj, "evento"):
        return None
    fecha = None
    if fecha_str := resultado.get("fecha"):
        try:
            fecha = dt.strptime(fecha_str, "%d/%m/%Y").date()
        except ValueError:
            pass
    hora = None
    if hora_str := resultado.get("hora"):
        try:
            hora = dt.strptime(hora_str, "%H:%M").time()
        except ValueError:
            pass
    tipo_slug = resultado.get("tipo_evento") or "otro"
    tipo_nombre = _TIPO_SLUG_MAP.get(tipo_slug, "Otro")
    tipo_obj = TipoEvento.objects.filter(nombre__iexact=tipo_nombre).first()
    return Evento.objects.create(
        parroquia=post_obj.parroquia,
        post=post_obj,
        titulo=resultado.get("titulo") or "Sin título",
        tipo=tipo_obj,
        fecha=fecha,
        hora=hora,
        lugar=resultado.get("lugar"),
        descripcion=resultado.get("descripcion"),
        imagen_url=post_obj.imagen_url,
    )


@require_POST
def crear_tipo_evento(request):
    if not request.user.is_staff:
        from django.http import JsonResponse
        return JsonResponse({"error": "Forbidden"}, status=403)
    nombre = request.POST.get("nombre", "").strip()
    if not nombre:
        from django.http import JsonResponse
        return JsonResponse({"error": "Nombre requerido"}, status=400)
    tipo, _ = TipoEvento.objects.get_or_create(nombre=nombre, defaults={"activo": True})
    tipos = list(TipoEvento.objects.filter(activo=True).values("pk", "nombre"))
    from django.http import JsonResponse
    return JsonResponse({"pk": tipo.pk, "nombre": tipo.nombre, "tipos": tipos})


_NIVELES_NUEVO = [
    (0,   "Explorador", "#76859C"),
    (50,  "Vecino",     "#D98A00"),
    (150, "Sacristán",  "#1F8A5B"),
    (300, "Catequista", "#14315E"),
    (600, "Párroco",    "#F2A007"),
]

def _nivel_nuevo(score):
    tier = _NIVELES_NUEVO[0]
    for t in _NIVELES_NUEVO:
        if score >= t[0]:
            tier = t
    idx = _NIVELES_NUEVO.index(tier)
    if idx < len(_NIVELES_NUEVO) - 1:
        next_t = _NIVELES_NUEVO[idx + 1]
        to_next = next_t[0] - score
        pct = max(0, min(100, int((score - tier[0]) / (next_t[0] - tier[0]) * 100)))
        next_name = next_t[1]
    else:
        to_next = 0
        pct = 100
        next_name = None
    return {"nivel": tier[1], "color": tier[2], "pct": pct,
            "to_next": to_next, "next_nivel": next_name}


def _insignias(perfil, ranking_pos):
    INSIGNIAS = [
        ("Verificador",  "25 datos confirmados",   perfil.validaciones_enviadas >= 25),
        ("Constante",    "Racha de 5 semanas",      False),
        ("Primer aporte","Tu primera colaboración", (perfil.reportes_enviados + perfil.validaciones_enviadas) >= 1),
        ("Vecino fiel",  "50 confirmaciones",       perfil.validaciones_enviadas >= 50),
        ("Pilar",        "Top 10 del mes",          1 <= ranking_pos <= 10 if ranking_pos else False),
        ("Misionero",    "5 parroquias nuevas",     False),
    ]
    return [{"nombre": n, "desc": d, "desbloqueada": ok} for n, d, ok in INSIGNIAS]


def _gradiente_parroquia(pk):
    colores = [
        ("#2d7d6e", "#1a5c52"),
        ("#4a7c59", "#2d5e3a"),
        ("#8b5e52", "#6b3d33"),
        ("#4a5568", "#2d3748"),
        ("#7b6b3d", "#5c4f2a"),
        ("#5b4a7a", "#3d3057"),
    ]
    return colores[pk % len(colores)]


def _proxima_misa(p_horarios):
    """Return {hora, dia_label, mins_until} for the next upcoming mass, or None."""
    if not p_horarios:
        return None
    schedule = {}
    for h in p_horarios:
        times = []
        for t_str in h.horarios.split('·'):
            t_str = t_str.strip()
            try:
                parts = t_str.split(':')
                times.append(dtime(int(parts[0]), int(parts[1]) if len(parts) > 1 else 0))
            except (ValueError, IndexError):
                pass
        if times:
            schedule[h.dia_semana] = sorted(times)
    if not schedule:
        return None
    now = datetime.now()
    hoy = now.date()
    DIAS = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
    for offset in range(8):
        target = hoy + timedelta(days=offset)
        dia = target.weekday()
        if dia not in schedule:
            continue
        for t in schedule[dia]:
            target_dt = datetime.combine(target, t)
            if target_dt > now:
                mins = int((target_dt - now).total_seconds() / 60)
                if offset == 0:
                    label = "Hoy"
                elif offset == 1:
                    label = "Mañana"
                else:
                    label = DIAS[dia]
                h_restantes = mins // 60
                m_restantes = mins % 60
                if h_restantes > 0:
                    countdown = f"en {h_restantes} h {m_restantes:02d} min"
                else:
                    countdown = f"en {m_restantes} min"
                return {"hora": t.strftime("%H:%M"), "dia_label": label, "countdown": countdown}
    return None


def publico_inicio(request):
    from .models import PerfilUsuario
    hoy = date.today()

    mi_parroquia = None
    if request.user.is_authenticated:
        try:
            perfil = request.user.perfil
            p = perfil.parroquias_favoritas.first()
            if p:
                p_redes = list(p.redes.all())
                p_eventos = list(p.eventos.all())
                p_horarios = list(p.horarios_misa.all())
                redes_v = [r for r in p_redes if r.activo and r.verificado]
                eventos_p = [e for e in p_eventos
                             if e.activo and e.verificado
                             and e.fecha and e.fecha >= hoy]
                mi_parroquia = {
                    "pk": p.pk,
                    "nombre": p.nombre,
                    "barrio": p.barrio or "",
                    "tiene_horarios": bool(p_horarios),
                    "tiene_ig": any(r.tipo == "instagram" for r in redes_v),
                    "tiene_fb": any(r.tipo == "facebook" for r in redes_v),
                    "eventos_count": len(eventos_p),
                    "proxima_misa": _proxima_misa(p_horarios),
                }
        except Exception:
            pass

    mis_favoritas = []
    if request.user.is_authenticated:
        try:
            from .models import SuscripcionAvisoMisa as _SuscAviso
            perfil = request.user.perfil
            subs_pks = set(
                _SuscAviso.objects.filter(usuario=request.user, activa=True)
                .values_list('parroquia_id', flat=True)
            )
            for p in perfil.parroquias_favoritas.prefetch_related('horarios_misa').all():
                if mi_parroquia and p.pk == mi_parroquia['pk']:
                    continue
                p_horarios = list(p.horarios_misa.all())
                p.proxima_misa = _proxima_misa(p_horarios)
                p.tiene_horarios = bool(p_horarios)
                p.suscripcion_activa = p.pk in subs_pks
                mis_favoritas.append(p)
        except Exception:
            pass

    provincias = (
        Parroquia.objects
        .exclude(provincia__isnull=True)
        .values("provincia")
        .annotate(total=Count("pk"))
        .order_by("-total")
    )

    nivel_info = None
    suscripcion_activa_inicio = False
    if request.user.is_authenticated:
        try:
            nivel_info = _nivel_nuevo(request.user.perfil.score)
        except Exception:
            pass
        if mi_parroquia:
            from .models import SuscripcionAvisoMisa
            suscripcion_activa_inicio = SuscripcionAvisoMisa.objects.filter(
                usuario=request.user,
                parroquia_id=mi_parroquia['pk'],
                activa=True
            ).exists()

    return render(request, "iglesias/publico/inicio.html", {
        "total": Parroquia.objects.count(),
        "con_eventos": Parroquia.objects.filter(
            eventos__activo=True,
            eventos__verificado=True,
            eventos__fecha__gte=hoy
        ).distinct().count(),
        "todas_parroquias": Parroquia.objects.all().order_by("nombre"),
        "mi_parroquia": mi_parroquia,
        "mis_favoritas": mis_favoritas,
        "provincias": provincias,
        "total_provincias": provincias.count(),
        "nivel_info": nivel_info,
        "suscripcion_activa": suscripcion_activa_inicio,
    })


def publico_favoritas(request):
    if not request.user.is_authenticated:
        return render(request, "iglesias/publico/favoritas.html", {"login_required": True})

    perfil = getattr(request.user, 'perfil', None)
    favoritas = perfil.parroquias_favoritas.all() if perfil else Parroquia.objects.none()

    # Enriquecer cada favorita con próxima misa y estado de suscripción
    from .models import SuscripcionAvisoMisa
    subs_activas = set(
        SuscripcionAvisoMisa.objects.filter(
            usuario=request.user, activa=True
        ).values_list('parroquia_id', flat=True)
    ) if request.user.is_authenticated else set()

    favoritas_data = []
    for p in favoritas:
        horarios = list(p.horarios_misa.all().order_by("dia_semana"))
        pm_raw = _proxima_misa(horarios)
        proxima_misa = None
        if pm_raw:
            proxima_misa = {
                "dia": pm_raw["dia_label"],
                "hora": pm_raw["hora"],
                "es_hoy": pm_raw["dia_label"] == "Hoy",
            }
        favoritas_data.append({
            "parroquia": p,
            "proxima_misa": proxima_misa,
            "suscripcion_activa": p.pk in subs_activas,
        })

    return render(request, "iglesias/publico/favoritas.html", {
        "favoritas": favoritas_data,
    })


def publico_mis_aportes(request):
    from .models import PerfilUsuario
    if not request.user.is_authenticated:
        return render(request, "iglesias/publico/mis_aportes.html", {"login_required": True})

    perfil, _ = PerfilUsuario.objects.get_or_create(user=request.user)
    reportes = list(
        ReporteHorario.objects.filter(usuario=request.user)
        .select_related("parroquia").order_by("-creado_en")[:20]
    )
    validaciones = list(
        ValidacionHorario.objects.filter(usuario=request.user)
        .select_related("parroquia").order_by("-creado_en")[:20]
    )
    from itertools import chain
    from operator import attrgetter
    actividad = sorted(
        chain(reportes, validaciones),
        key=attrgetter("creado_en"),
        reverse=True,
    )[:30]

    comentarios_aprobados = ComentarioParroquia.objects.filter(
        usuario=request.user,
        estado_moderacion='aprobado',
    ).select_related('parroquia').order_by('-fecha')

    comentarios_rechazados = ComentarioParroquia.objects.filter(
        usuario=request.user,
        estado_moderacion='rechazado',
    ).select_related('parroquia').order_by('-fecha')

    comentarios_pendientes = ComentarioParroquia.objects.filter(
        usuario=request.user,
        estado_moderacion='pendiente',
    ).select_related('parroquia').order_by('-fecha')

    return render(request, "iglesias/publico/mis_aportes.html", {
        "perfil": perfil,
        "actividad": actividad,
        "total_aportes": perfil.reportes_enviados + perfil.validaciones_enviadas,
        "nivel_info": _nivel_nuevo(perfil.score),
        "comentarios_aprobados": comentarios_aprobados,
        "comentarios_rechazados": comentarios_rechazados,
        "comentarios_pendientes": comentarios_pendientes,
    })


def publico_perfil(request):
    from .models import PerfilUsuario
    if not request.user.is_authenticated:
        from django.contrib.auth.views import redirect_to_login
        return redirect_to_login(request.get_full_path())

    perfil, _ = PerfilUsuario.objects.get_or_create(user=request.user)
    nivel_info = _nivel_nuevo(perfil.score)

    ranking = list(
        PerfilUsuario.objects.select_related("user").order_by("-score")[:10]
    )
    ranking_pos = next(
        (i + 1 for i, p in enumerate(ranking) if p.user_id == request.user.pk), None
    )
    if ranking_pos is None:
        pos_total = PerfilUsuario.objects.filter(score__gt=perfil.score).count() + 1
        ranking_pos = pos_total

    insignias = _insignias(perfil, ranking_pos)

    actividad = list(
        ReporteHorario.objects.filter(usuario=request.user)
        .select_related("parroquia").order_by("-creado_en")[:10]
    )

    from .models import SuscripcionAvisoMisa
    primera_favorita = perfil.parroquias_favoritas.first()
    suscripcion_activa = False
    if primera_favorita:
        suscripcion_activa = SuscripcionAvisoMisa.objects.filter(
            usuario=request.user,
            parroquia=primera_favorita,
            activa=True
        ).exists()

    return render(request, "iglesias/publico/perfil.html", {
        "perfil": perfil,
        "primera_favorita": primera_favorita,
        "nivel_info": nivel_info,
        "ranking": ranking,
        "ranking_pos": ranking_pos,
        "insignias": insignias,
        "actividad": actividad,
        "suscripcion_activa": suscripcion_activa,
    })


@require_POST
def upload_avatar(request):
    import logging
    from django.http import JsonResponse
    from imagekitio import ImageKit

    if not request.user.is_authenticated:
        return JsonResponse({"ok": False}, status=403)

    if not settings.IMAGEKIT_PRIVATE_KEY:
        logging.getLogger(__name__).error("[upload_avatar] IMAGEKIT_PRIVA_KEY no configurada")
        return JsonResponse({"ok": False, "error": "Servicio de imágenes no configurado"}, status=500)

    f = request.FILES.get("avatar")
    if not f:
        return JsonResponse({"ok": False, "error": "Sin archivo"}, status=400)
    if f.size > 2 * 1024 * 1024:
        return JsonResponse({"ok": False, "error": "Imagen demasiado grande (máx 2 MB)"}, status=400)

    try:
        imagekit = ImageKit(private_key=settings.IMAGEKIT_PRIVATE_KEY)
        file_name = f"avatar_{request.user.pk}_{f.name}"
        result = imagekit.files.upload(
            file=f.read(),
            file_name=file_name,
            folder="/avatars/",
        )
        url = f"{settings.IMAGEKIT_URL_ENDPOINT}/{result.file_path}"
        perfil, _ = PerfilUsuario.objects.get_or_create(user=request.user)
        perfil.avatar_url = url
        perfil.save(update_fields=["avatar_url"])
        return JsonResponse({"ok": True, "url": url})
    except Exception as e:
        logging.getLogger(__name__).error(f"[upload_avatar] Error ImageKit: {e}")
        return JsonResponse({"ok": False, "error": "Error al subir la imagen"}, status=500)


@require_POST
def delete_avatar(request):
    from django.http import JsonResponse
    if not request.user.is_authenticated:
        return JsonResponse({"ok": False}, status=403)
    try:
        perfil = request.user.perfil
    except Exception:
        return JsonResponse({"ok": False}, status=404)
    perfil.avatar_url = ""
    perfil.save(update_fields=["avatar_url"])
    return JsonResponse({"ok": True})


@csrf_exempt
@require_POST
def set_parroquia_favorita(request, pk):
    if not request.user.is_authenticated:
        return JsonResponse({"ok": False, "login_required": True})

    parroquia = get_object_or_404(Parroquia, pk=pk)
    perfil, _ = PerfilUsuario.objects.get_or_create(user=request.user)

    if perfil.parroquias_favoritas.filter(pk=pk).exists():
        perfil.parroquias_favoritas.remove(parroquia)
        return JsonResponse({"ok": True, "favorita": False})
    else:
        perfil.parroquias_favoritas.add(parroquia)
        horarios = list(parroquia.horarios_misa.all().order_by("dia_semana"))
        pm = _proxima_misa(horarios)
        return JsonResponse({
            "ok": True,
            "favorita": True,
            "parroquia": {
                "pk": parroquia.pk,
                "nombre": parroquia.nombre,
                "barrio": parroquia.barrio or "",
                "tiene_horarios": bool(horarios),
                "proxima_misa": pm,
            },
        })


def parroquias_geo_json(request):
    from django.http import JsonResponse
    from datetime import date
    hoy = date.today()

    parroquias = Parroquia.objects.filter(
        latitud__isnull=False,
        longitud__isnull=False
    ).prefetch_related("redes", "eventos", "horarios_misa")

    resultado = []
    for p in parroquias:
        redes_v = [r for r in p.redes.all() if r.activo and r.verificado]
        eventos_p = [e for e in p.eventos.all()
                     if e.activo and e.verificado and e.fecha and e.fecha >= hoy]
        resultado.append({
            "pk": p.pk,
            "nombre": p.nombre,
            "barrio": p.barrio or "",
            "provincia": p.provincia or "",
            "diocesis": p.diocesis or "",
            "lat": p.latitud,
            "lng": p.longitud,
            "imagen_url": p.imagen_url or "",
            "tiene_horarios": p.horarios_misa.exists(),
            "tiene_ig": any(r.tipo == "instagram" for r in redes_v),
            "tiene_fb": any(r.tipo == "facebook" for r in redes_v),
            "eventos_count": len(eventos_p),
        })

    return JsonResponse({"parroquias": resultado})


def _haversine(lat1, lon1, lat2, lon2):
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _fmt_dist(km):
    if km is None:
        return None
    if km < 1:
        return f"{round(km * 1000)}m"
    return f"{km:.1f}km"


def publico_buscar(request):
    q = request.GET.get("q", "").strip()
    barrio = request.GET.get("barrio", "").strip()
    filtro = request.GET.get("filtro", "todas").strip()
    provincia = request.GET.get("provincia", "").strip()
    user_lat = user_lng = None
    try:
        lat_s = request.GET.get("lat", "").strip()
        lng_s = request.GET.get("lng", "").strip()
        if lat_s and lng_s:
            _lt, _lg = float(lat_s), float(lng_s)
            if -90 <= _lt <= 90 and -180 <= _lg <= 180:
                user_lat, user_lng = _lt, _lg
    except ValueError:
        pass

    parroquias = Parroquia.objects.all()

    if provincia:
        parroquias = parroquias.filter(provincia__icontains=provincia)

    if q:
        parroquias = parroquias.filter(
            Q(nombre__icontains=q)
            | Q(barrio__icontains=q)
            | Q(ciudad__icontains=q)
            | Q(parroco__icontains=q)
            | Q(direccion__icontains=q)
        ).annotate(
            relevancia=Case(
                When(nombre__istartswith=q, then=Value(0)),
                When(nombre__icontains=q, then=Value(1)),
                When(barrio__icontains=q, then=Value(2)),
                When(ciudad__icontains=q, then=Value(3)),
                default=Value(4),
                output_field=IntegerField(),
            )
        )

    if barrio:
        parroquias = parroquias.filter(barrio__icontains=barrio)

    if filtro == "eventos":
        parroquias = parroquias.filter(
            eventos__activo=True,
            eventos__verificado=True,
            eventos__fecha__gte=date.today(),
        ).distinct()
    elif filtro == "horarios":
        parroquias = parroquias.filter(horarios_misa__isnull=False).distinct()
    elif filtro == "redes":
        parroquias = parroquias.filter(
            redes__activo=True,
            redes__verificado=True,
        ).distinct()

    limit = 200 if user_lat is not None else 80
    if q:
        parroquias = parroquias.prefetch_related(
            "redes", "eventos", "horarios_misa"
        ).order_by("relevancia", "nombre")[:limit]
    else:
        parroquias = parroquias.prefetch_related(
            "redes", "eventos", "horarios_misa"
        ).order_by("nombre")[:limit]

    favoritas_pks = set()
    if request.user.is_authenticated:
        try:
            favoritas_pks = set(
                request.user.perfil.parroquias_favoritas.values_list('pk', flat=True)
            )
        except Exception:
            pass

    hoy = date.today()

    resultados = []
    for p in parroquias:
        redes_verificadas = [r for r in p.redes.all() if r.activo and r.verificado]
        eventos_proximos = [
            e for e in p.eventos.all()
            if e.activo and e.verificado and e.fecha and e.fecha >= hoy
        ]
        tiene_horarios = p.horarios_misa.exists()
        dist = None
        if user_lat is not None and p.latitud and p.longitud:
            dist = _haversine(user_lat, user_lng, p.latitud, p.longitud)
        resultados.append({
            "parroquia": p,
            "redes": redes_verificadas,
            "eventos_count": len(eventos_proximos),
            "tiene_horarios": tiene_horarios,
            "tiene_ig": any(r.tipo == "instagram" for r in redes_verificadas),
            "tiene_fb": any(r.tipo == "facebook" for r in redes_verificadas),
            "distancia": dist,
            "distancia_fmt": _fmt_dist(dist),
            "es_favorita": p.pk in favoritas_pks,
        })

    if user_lat is not None:
        resultados.sort(key=lambda x: x["distancia"] if x["distancia"] is not None else float("inf"))
        resultados = resultados[:40]

    banners = list(Banner.objects.filter(posicion="resultados", activo=True))

    return render(request, "iglesias/publico/partials/resultados.html", {
        "resultados": resultados,
        "total": len(resultados),
        "query": q,
        "banners": banners,
    })


def publico_detalle(request, pk):
    parroquia = get_object_or_404(Parroquia, pk=pk)
    hoy = date.today()

    redes_verificadas = parroquia.redes.filter(
        activo=True, verificado=True
    ).order_by("tipo")

    eventos_proximos = parroquia.eventos.filter(
        activo=True, verificado=True,
        fecha__gte=hoy,
    ).order_by("fecha")[:5]

    horarios = parroquia.horarios_misa.filter(
        horarios__gt=""
    ).order_by("dia_semana")

    ya_valido = bool(request.COOKIES.get(f"validado_{pk}"))
    ya_reporto = bool(request.COOKIES.get(f"reportado_{pk}"))
    contacto_ya_enviado = bool(request.COOKIES.get(f"contacto_parroquia_{pk}"))

    es_favorita = False
    if request.user.is_authenticated:
        try:
            perfil = request.user.perfil
            es_favorita = perfil.parroquias_favoritas.filter(pk=parroquia.pk).exists()
        except Exception:
            pass

    banner_detalle = Banner.objects.filter(posicion="detalle", activo=True).first()

    comentarios = ComentarioParroquia.objects.filter(
        parroquia=parroquia,
        oculto=False,
        estado_moderacion='aprobado',
    ).select_related('usuario', 'usuario__perfil')[:30]

    votos = VotoHorario.objects.filter(parroquia=parroquia, tipo='oficial')
    votos_up = votos.filter(valor=1).count()
    votos_down = votos.filter(valor=-1).count()
    votos_total = votos_up + votos_down
    pct_up = round(votos_up / votos_total * 100) if votos_total else 0

    voto_usuario = None
    if request.user.is_authenticated:
        v = votos.filter(usuario=request.user).first()
        voto_usuario = v.valor if v else None
    elif request.session.session_key:
        v = votos.filter(session_key=request.session.session_key, usuario__isnull=True).first()
        voto_usuario = v.valor if v else None

    votos_prop = VotoHorario.objects.filter(parroquia=parroquia, tipo='propuesto')
    votos_up_prop = votos_prop.filter(valor=1).count()
    votos_down_prop = votos_prop.filter(valor=-1).count()
    votos_total_prop = votos_up_prop + votos_down_prop
    pct_up_prop = round(votos_up_prop / votos_total_prop * 100) if votos_total_prop else 0

    voto_usuario_prop = None
    if request.user.is_authenticated:
        v = votos_prop.filter(usuario=request.user).first()
        voto_usuario_prop = v.valor if v else None
    elif request.session.session_key:
        v = votos_prop.filter(session_key=request.session.session_key, usuario__isnull=True).first()
        voto_usuario_prop = v.valor if v else None

    horarios_propuestos = HorarioPropuestoAgregado.objects.filter(
        parroquia=parroquia
    ).order_by('dia_semana')

    import logging as _logging
    _logging.getLogger(__name__).info(
        f"[detalle] parroquia {parroquia.pk}: horarios_propuestos count={horarios_propuestos.count()}"
    )

    foto_url = _foto_url_local(parroquia)

    from .models import SuscripcionAvisoMisa
    suscripcion_activa = False
    if request.user.is_authenticated and es_favorita:
        suscripcion_activa = SuscripcionAvisoMisa.objects.filter(
            usuario=request.user,
            parroquia=parroquia,
            activa=True
        ).exists()

    return render(request, "iglesias/publico/detalle.html", {
        "parroquia": parroquia,
        "foto_url": foto_url,
        "redes": redes_verificadas,
        "eventos": eventos_proximos,
        "horarios": horarios,
        "ya_valido": ya_valido,
        "ya_reporto": ya_reporto,
        "es_favorita": es_favorita,
        "suscripcion_activa": suscripcion_activa,
        "banner_detalle": banner_detalle,
        "comentarios": comentarios,
        "votos_up": votos_up,
        "votos_down": votos_down,
        "votos_total": votos_total,
        "pct_up": pct_up,
        "voto_usuario": voto_usuario,
        "votos_up_prop": votos_up_prop,
        "votos_down_prop": votos_down_prop,
        "votos_total_prop": votos_total_prop,
        "pct_up_prop": pct_up_prop,
        "voto_usuario_prop": voto_usuario_prop,
        "hoy_dia": date.today().weekday(),
        "horarios_propuestos": horarios_propuestos,
        "UMBRAL_CONFIANZA_ALTA": 1.5,
        "opening_hours_schema": _generar_opening_hours(horarios),
        "contacto_ya_enviado": contacto_ya_enviado,
    })


_RESEND_API_URL = "https://api.resend.com/emails"


def _enviar_email_resend(to, subject, html_body, reply_to=None):
    import requests as _requests
    headers = {
        "Authorization": f"Bearer {settings.RESEND_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "from": settings.DEFAULT_FROM_EMAIL,
        "to": [to],
        "subject": subject,
        "html": html_body,
    }
    if reply_to:
        payload["reply_to"] = reply_to
    response = _requests.post(_RESEND_API_URL, json=payload, headers=headers, timeout=10)
    response.raise_for_status()
    return response


def contacto_parroquia(request, pk):
    import logging
    from .forms import ContactoParroquiaForm

    parroquia = get_object_or_404(Parroquia, pk=pk)
    cookie_key = f"contacto_parroquia_{pk}"

    if request.method == "GET":
        form = ContactoParroquiaForm()
        return render(request, "iglesias/publico/partials/contacto_parroquia_form.html", {
            "form": form,
            "parroquia": parroquia,
        })

    # POST
    if request.COOKIES.get(cookie_key):
        return render(request, "iglesias/publico/partials/contacto_parroquia_exito.html", {
            "ya_enviado": True,
            "parroquia": parroquia,
        })

    form = ContactoParroquiaForm(request.POST)
    if not form.is_valid():
        return render(request, "iglesias/publico/partials/contacto_parroquia_form.html", {
            "form": form,
            "parroquia": parroquia,
        })

    nombre = form.cleaned_data["nombre"]
    email = form.cleaned_data["email"]
    rol_key = form.cleaned_data["rol"]
    rol_label = dict(form.fields["rol"].choices).get(rol_key, rol_key)
    mensaje = form.cleaned_data["mensaje"]

    admin_url = request.build_absolute_uri(
        reverse("iglesias:detalle_parroquia", args=[pk])
    )
    ciudad = parroquia.ciudad or parroquia.barrio or "—"

    html_equipo = (
        f"<p><strong>Nueva consulta de contacto desde ParroGuía</strong></p>"
        f"<p>Parroquia: {parroquia.nombre}<br>"
        f"Ciudad: {ciudad}<br>"
        f"Panel admin: <a href='{admin_url}'>{admin_url}</a></p>"
        f"<p>Nombre: {nombre}<br>"
        f"Email: {email}<br>"
        f"Rol: {rol_label}</p>"
        f"<p>Mensaje:<br>{mensaje}</p>"
    )
    html_confirmacion = (
        f"<p>Hola {nombre},</p>"
        f"<p>Recibimos tu mensaje sobre <strong>{parroquia.nombre}</strong>. "
        f"Te contactaremos a la brevedad a este email.</p>"
        f"<p>— El equipo de ParroGuía</p>"
    )
    try:
        _enviar_email_resend(
            to=settings.CONTACTO_EMAIL,
            subject=f"[Contacto parroquia] {parroquia.nombre}",
            html_body=html_equipo,
            reply_to=email,
        )
        _enviar_email_resend(
            to=email,
            subject="Recibimos tu mensaje — Parroguía",
            html_body=html_confirmacion,
        )
    except Exception as exc:
        logging.getLogger(__name__).error(f"[contacto_parroquia] Error al enviar email pk={pk}: {exc}")

    response = render(request, "iglesias/publico/partials/contacto_parroquia_exito.html", {
        "email": email,
        "parroquia": parroquia,
    })
    response.set_cookie(cookie_key, "1", max_age=30 * 24 * 3600, samesite="Lax", httponly=True)
    return response


@require_POST
@csrf_exempt
def votar_horario(request, pk):
    from django.db import models as db_models
    parroquia = get_object_or_404(Parroquia, pk=pk)
    valor = request.POST.get('valor')
    if valor not in ('1', '-1'):
        return JsonResponse({'error': 'Valor inválido'}, status=400)
    valor = int(valor)

    tipo = request.POST.get('tipo', 'oficial')
    if tipo not in ('oficial', 'propuesto'):
        tipo = 'oficial'

    if tipo == 'oficial' and not parroquia.horarios_misa.filter(horarios__gt="").exists():
        return JsonResponse({'error': 'Sin horarios'}, status=400)
    if tipo == 'propuesto' and not HorarioPropuestoAgregado.objects.filter(parroquia=parroquia).exists():
        return JsonResponse({'error': 'Sin horarios propuestos'}, status=400)

    if not request.session.session_key:
        request.session.create()

    usuario = request.user if request.user.is_authenticated else None
    session_key = '' if usuario else request.session.session_key

    filtro = {'parroquia': parroquia, 'tipo': tipo}
    if usuario:
        filtro['usuario'] = usuario
    else:
        filtro['session_key'] = session_key
        filtro['usuario__isnull'] = True

    voto_existente = VotoHorario.objects.filter(**filtro).first()

    if voto_existente:
        if voto_existente.valor == valor:
            voto_existente.delete()
            voto_actual = None
        else:
            voto_existente.valor = valor
            voto_existente.save(update_fields=['valor'])
            voto_actual = valor
    else:
        VotoHorario.objects.create(parroquia=parroquia, tipo=tipo, usuario=usuario, session_key=session_key, valor=valor)
        voto_actual = valor
        if usuario:
            PerfilUsuario.objects.filter(user=usuario).update(score=db_models.F('score') + 1)

    votos = VotoHorario.objects.filter(parroquia=parroquia, tipo=tipo)
    up = votos.filter(valor=1).count()
    down = votos.filter(valor=-1).count()
    total = up + down
    pct = round(up / total * 100) if total else 0

    return JsonResponse({'up': up, 'down': down, 'total': total, 'pct': pct, 'voto_actual': voto_actual})


@require_POST
def agregar_comentario(request, pk):
    import threading
    from django.db import models as db_models
    parroquia = get_object_or_404(Parroquia, pk=pk)
    texto = request.POST.get('texto', '').strip()

    if len(texto) < 3:
        return JsonResponse({'ok': False, 'error': 'El comentario es demasiado corto.'}, status=400)
    if len(texto) > 500:
        return JsonResponse({'ok': False, 'error': 'El comentario no puede superar los 500 caracteres.'}, status=400)

    if not request.session.session_key:
        request.session.create()

    usuario = request.user if request.user.is_authenticated else None

    comentario = ComentarioParroquia.objects.create(
        parroquia=parroquia,
        usuario=usuario,
        texto=texto,
        oculto=True,
        estado_moderacion='pendiente',
    )

    from .moderacion_comentarios import moderar_comentario
    moderar_comentario(comentario)

    def generar_reporte_silencioso():
        try:
            from apps.iglesias.ia_horarios import procesar_reporte_horario
            resultado = procesar_reporte_horario(parroquia, texto)
            if resultado and resultado.get('propuesta_ia'):
                reporte = ReporteHorario.objects.create(
                    parroquia=parroquia,
                    texto_usuario=texto,
                    propuesta_ia=resultado['propuesta_ia'],
                    resumen_cambios=resultado.get('resumen_cambios', ''),
                    estado='pendiente',
                    fuente='usuario',
                    usuario=usuario,
                )
                ComentarioParroquia.objects.filter(pk=comentario.pk).update(reporte=reporte)
                import logging as _log
                _log.getLogger(__name__).info(
                    f"[comentar] reporte creado pk={reporte.pk} fuente={reporte.fuente} propuesta_ia={reporte.propuesta_ia}"
                )
                if usuario:
                    PerfilUsuario.objects.filter(user=usuario).update(
                        score=db_models.F('score') + 5,
                        reportes_enviados=db_models.F('reportes_enviados') + 1
                    )
        except Exception as e:
            print(f"Error IA comentario {comentario.pk}: {e}")

    threading.Thread(target=generar_reporte_silencioso, daemon=True).start()

    nivel_slug = 'explorador'
    nivel_label = 'Explorador'
    initials = 'AN'
    nombre = 'Anónimo'
    if usuario:
        try:
            perfil = usuario.perfil
            nivel_slug = perfil.nivel_slug
            nivel_label = perfil.get_nivel_display()
        except Exception:
            pass
        initials = ((usuario.first_name[:1] + usuario.last_name[:1]).upper() or 'U')
        nombre = usuario.get_full_name() or usuario.username

    return JsonResponse({
        'ok': True,
        'comentario': {
            'pk': comentario.pk,
            'texto': comentario.texto,
            'nombre': nombre,
            'initials': initials,
            'nivel': nivel_label,
            'nivel_slug': nivel_slug,
            'fecha': 'ahora mismo',
        }
    })


@require_POST
def crear_categoria_evento(request):
    if not request.user.is_staff:
        from django.http import JsonResponse
        return JsonResponse({"error": "Forbidden"}, status=403)
    nombre = request.POST.get("nombre", "").strip()
    if not nombre:
        from django.http import JsonResponse
        return JsonResponse({"error": "Nombre requerido"}, status=400)
    cat, _ = CategoriaEvento.objects.get_or_create(nombre=nombre, defaults={"activo": True})
    categorias = list(CategoriaEvento.objects.filter(activo=True).values("pk", "nombre"))
    from django.http import JsonResponse
    return JsonResponse({"pk": cat.pk, "nombre": cat.nombre, "categorias": categorias})


def editar_seccion_bai(request, pk):
    if not request.user.is_staff:
        return HttpResponseForbidden("No autorizado")

    parroquia = get_object_or_404(
        Parroquia.objects.prefetch_related("horarios_misa").select_related("info_bai"),
        pk=pk,
    )

    if request.method == "POST":
        if hasattr(parroquia, "info_bai") and parroquia.info_bai:
            info_bai = parroquia.info_bai
            info_bai.direccion_completa = request.POST.get("direccion_completa", "").strip() or None
            info_bai.como_llegar = request.POST.get("como_llegar", "").strip() or None
            info_bai.save(update_fields=["direccion_completa", "como_llegar"])

        for num, _ in HorarioMisa.DIA_CHOICES:
            horarios_val = request.POST.get(f"horarios_{num}", "").strip()
            nota = request.POST.get(f"nota_{num}", "").strip() or None
            if horarios_val:
                HorarioMisa.objects.update_or_create(
                    parroquia=parroquia,
                    dia_semana=num,
                    defaults={"horarios": horarios_val, "nota": nota, "fuente": "web_propia"},
                )
            else:
                HorarioMisa.objects.filter(parroquia=parroquia, dia_semana=num).delete()

        parroquia = get_object_or_404(
            Parroquia.objects.prefetch_related("horarios_misa").select_related("info_bai"),
            pk=pk,
        )
        editing = False
    else:
        editing = request.GET.get("cancelar") != "1"

    horarios_por_dia = {h.dia_semana: h for h in parroquia.horarios_misa.all()}
    horarios_form = [
        {
            "num": num,
            "nombre": nombre,
            "horarios": horarios_por_dia[num].horarios if num in horarios_por_dia else "",
            "nota": horarios_por_dia[num].nota or "" if num in horarios_por_dia else "",
        }
        for num, nombre in HorarioMisa.DIA_CHOICES
    ]

    return render(request, "iglesias/partials/seccion_bai.html", {
        "parroquia": parroquia,
        "editing": editing,
        "horarios_form": horarios_form,
    })


def reportar_horario(request, pk):
    from django.http import JsonResponse
    parroquia = get_object_or_404(Parroquia, pk=pk)

    if request.method != "POST":
        return JsonResponse({"ok": False, "error": "Método no permitido"})

    cookie_key = f"reportado_{pk}"
    if request.COOKIES.get(cookie_key):
        return JsonResponse({"ok": False, "error": "Ya enviaste un reporte para esta parroquia recientemente."})

    texto = request.POST.get("texto", "").strip()
    if not texto or len(texto) < 10:
        return JsonResponse({"ok": False, "error": "Texto muy corto"})

    reporte = ReporteHorario.objects.create(
        parroquia=parroquia,
        texto_usuario=texto,
        usuario=request.user if request.user.is_authenticated else None,
    )

    from apps.iglesias.signals import actualizar_score_reporte_enviado
    actualizar_score_reporte_enviado(reporte)

    import threading
    def procesar():
        from apps.iglesias.ia_horarios import procesar_reporte_horario
        resultado = procesar_reporte_horario(parroquia, texto)
        reporte.propuesta_ia = resultado["propuesta_ia"]
        reporte.resumen_cambios = resultado["resumen_cambios"]
        reporte.save(update_fields=["propuesta_ia", "resumen_cambios"])

    threading.Thread(target=procesar, daemon=True).start()

    response = JsonResponse({"ok": True})
    response.set_cookie(
        cookie_key,
        "1",
        max_age=60 * 60 * 24 * 30,
        httponly=True,
        samesite="Lax",
    )
    return response


def revision_reportes(request):
    if not request.user.is_staff:
        return HttpResponse("Forbidden", status=403)

    fuente = request.GET.get("fuente", "")

    pendientes_qs = ReporteHorario.objects.filter(
        estado="pendiente"
    ).select_related("parroquia").prefetch_related("parroquia__horarios_misa")

    if fuente in ("usuario", "scraper", "scraper_web"):
        pendientes_qs = pendientes_qs.filter(fuente=fuente)

    revisados = ReporteHorario.objects.exclude(
        estado="pendiente"
    ).select_related("parroquia", "revisado_por")[:20]

    total_pendientes = ReporteHorario.objects.filter(estado="pendiente").count()

    return render(request, "iglesias/revision_reportes.html", {
        "pendientes": pendientes_qs,
        "revisados": revisados,
        "total_pendientes": total_pendientes,
        "fuente_activa": fuente,
        "total_usuario": ReporteHorario.objects.filter(estado="pendiente", fuente="usuario").count(),
        "total_scraper": ReporteHorario.objects.filter(estado="pendiente", fuente="scraper").count(),
        "total_web": ReporteHorario.objects.filter(estado="pendiente", fuente="scraper_web").count(),
    })


@require_POST
def aplicar_reporte(request, pk):
    if not request.user.is_staff:
        return HttpResponse("Forbidden", status=403)

    reporte = get_object_or_404(ReporteHorario, pk=pk)
    parroquia = reporte.parroquia

    cambios = []
    for i in range(7):
        dia_str = request.POST.get(f"dia_{i}", "").strip()
        horario_val = request.POST.get(f"horario_{i}", "").strip()
        if dia_str.isdigit() and 0 <= int(dia_str) <= 6:
            cambios.append({"dia": int(dia_str), "horario": horario_val})
    if not cambios:
        cambios = reporte.propuesta_ia or []

    for cambio in cambios:
        dia = cambio.get("dia")
        horario = (cambio.get("horario") or "").strip()
        if dia is None:
            continue
        if horario:
            HorarioMisa.objects.update_or_create(
                parroquia=parroquia,
                dia_semana=dia,
                defaults={"horarios": horario, "fuente": "usuario"},
            )
        else:
            HorarioMisa.objects.filter(parroquia=parroquia, dia_semana=dia).delete()

    ValidacionHorario.objects.filter(parroquia=parroquia).delete()

    reporte.estado = "aplicado"
    reporte.revisado_en = timezone.now()
    reporte.revisado_por = request.user
    reporte.save()

    from apps.iglesias.signals import actualizar_score_aprobacion
    actualizar_score_aprobacion(reporte)

    messages.success(
        request,
        f"Horarios de {parroquia.nombre} actualizados correctamente."
    )
    return redirect("iglesias:revision_reportes")


@require_POST
def descartar_reporte(request, pk):
    if not request.user.is_staff:
        return HttpResponse("Forbidden", status=403)

    reporte = get_object_or_404(ReporteHorario, pk=pk)
    reporte.estado = "descartado"
    reporte.revisado_en = timezone.now()
    reporte.revisado_por = request.user
    reporte.save()

    from apps.iglesias.signals import actualizar_score_rechazo
    actualizar_score_rechazo(reporte)

    messages.warning(
        request,
        f"Reporte de {reporte.parroquia.nombre} descartado."
    )
    return redirect("iglesias:revision_reportes")


def reportes_count(request):
    if not request.user.is_staff:
        from django.http import JsonResponse
        return JsonResponse({"count": 0})
    count = ReporteHorario.objects.filter(estado="pendiente").count()
    from django.http import JsonResponse
    return JsonResponse({"count": count})


def validar_horario(request, pk):
    from django.http import JsonResponse
    parroquia = get_object_or_404(Parroquia, pk=pk)

    if request.method != "POST":
        return JsonResponse({"ok": False, "error": "Método no permitido"})

    cookie_key = f"validado_{pk}"
    if request.COOKIES.get(cookie_key):
        total = parroquia.validaciones_horario.count()
        return JsonResponse({"ok": True, "total": total, "ya_validado": True})

    validacion = ValidacionHorario.objects.create(
        parroquia=parroquia,
        usuario=request.user if request.user.is_authenticated else None,
    )
    total = ValidacionHorario.objects.filter(parroquia=parroquia).count()

    from apps.iglesias.signals import actualizar_score_validacion
    actualizar_score_validacion(validacion)

    response = JsonResponse({"ok": True, "total": total, "ya_validado": False})
    response.set_cookie(
        cookie_key,
        "1",
        max_age=60 * 60 * 24 * 30,
        httponly=True,
        samesite="Lax",
    )
    return response


def reporte_card(request, pk):
    if not request.user.is_staff:
        return HttpResponse("Forbidden", status=403)
    reporte = get_object_or_404(ReporteHorario, pk=pk)
    return render(request, "iglesias/partials/reporte_card.html", {
        "reporte": reporte,
    })


def sitemap(request):
    from datetime import date as _date
    parroquias = Parroquia.objects.all().order_by("id")
    base_url = f"{request.scheme}://{request.get_host()}"
    return render(request, "iglesias/publico/sitemap.xml",
                  {"parroquias": parroquias, "base_url": base_url,
                   "today": _date.today().isoformat()},
                  content_type="application/xml")


def robots_txt(request):
    content = (
        "User-agent: *\n"
        "Allow: /publico/\n"
        "Allow: /sitemap.xml\n"
        "\n"
        "Disallow: /admin/\n"
        "Disallow: /admin-login/\n"
        "Disallow: /admin-logout/\n"
        "Disallow: /accounts/\n"
        "Disallow: /parroquias/\n"
        "Disallow: /eventos/\n"
        "Disallow: /horarios/\n"
        "Disallow: /scraper/\n"
        "Disallow: /posts/\n"
        "Disallow: /debug/\n"
        "Disallow: /api/\n"
        "\n"
        "Sitemap: https://parroguia.com/sitemap.xml\n"
    )
    from django.http import HttpResponse
    return HttpResponse(content, content_type="text/plain")


def publico_ranking(request):
    from .models import PerfilUsuario
    perfiles = PerfilUsuario.objects.filter(
        score__gt=0
    ).select_related("user").order_by("-score")[:20]

    mi_perfil = None
    if request.user.is_authenticated:
        mi_perfil, _ = PerfilUsuario.objects.get_or_create(user=request.user)

    return render(request, "iglesias/publico/ranking.html", {
        "perfiles": perfiles,
        "mi_perfil": mi_perfil,
    })


def admin_login(request):
    if request.user.is_authenticated and request.user.is_staff:
        return redirect("iglesias:lista_parroquias")

    error = None
    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "")
        user = authenticate(request, username=username, password=password)
        if user and user.is_staff:
            auth_login(request, user)
            next_url = request.POST.get("next", "").strip()
            if next_url and next_url.startswith("/"):
                return redirect(next_url)
            return redirect("iglesias:lista_parroquias")
        elif user and not user.is_staff:
            error = "Esta cuenta no tiene acceso al panel de administración."
        else:
            error = "Usuario o contraseña incorrectos."

    return render(request, "iglesias/admin_login.html", {
        "error": error,
        "next": request.GET.get("next", ""),
    })


@csrf_exempt
def scraper_automatico(request):
    if request.method != "POST":
        from django.http import HttpResponseNotAllowed
        return HttpResponseNotAllowed(["POST"])

    token = request.headers.get("X-Scraper-Token", "")
    token_esperado = os.environ.get("SCRAPER_SECRET_TOKEN", "")
    if not token_esperado or token != token_esperado:
        return JsonResponse({"ok": False, "error": "Token inválido"}, status=403)

    if ScraperJob.objects.filter(estado="corriendo").exists():
        return JsonResponse({"ok": False, "error": "Ya hay un scraper corriendo"})

    import threading
    from datetime import timedelta

    redes_ig = list(RedSocial.objects.filter(
        tipo="instagram", activo=True, verificado=True
    ).select_related("parroquia"))

    redes_fb = list(RedSocial.objects.filter(
        tipo="facebook", activo=True, verificado=True
    ).select_related("parroquia"))

    job = ScraperJob.objects.create(
        total=len(redes_ig) + len(redes_fb),
        procesados=0,
        origen="automatico",
    )

    def correr():
        from scraper_redes.run import (
            scrapear_con_backend,
            scrapear_facebook_con_backend,
            crear_evento_desde_post,
        )
        from scraper_redes.procesador import procesar_post, procesar_post_facebook
        import time, random

        try:
            # Instagram
            for red in redes_ig:
                if ScraperJob.objects.filter(pk=job.pk, estado="completado").exists():
                    break
                if red.parroquia.redes_verificadas:
                    job.procesados += 1
                    job.save(update_fields=["procesados", "actualizado_en"])
                    continue
                job.parroquia_actual = red.parroquia.nombre
                job.procesados += 1
                job.save(update_fields=["parroquia_actual", "procesados", "actualizado_en"])
                try:
                    posts = scrapear_con_backend(red.url)
                    guardados = 0
                    for post in posts:
                        _, creado = PostParroquia.objects.get_or_create(
                            post_id=post["post_id"],
                            defaults={
                                "parroquia": red.parroquia,
                                "red_social": "instagram",
                                "imagen_url": post["imagen_url"],
                                "fecha_publicacion": post["fecha"],
                                "raw_data": post["raw_data"],
                            }
                        )
                        if creado:
                            guardados += 1
                    pendientes = PostParroquia.objects.filter(
                        parroquia=red.parroquia,
                        procesado=False,
                    )
                    for post_obj in pendientes:
                        post_dict = {
                            "post_id": post_obj.post_id,
                            "imagen_url": post_obj.imagen_url,
                            "caption": post_obj.raw_data.get("caption", "") if post_obj.raw_data else "",
                        }
                        resultado = procesar_post(post_dict)
                        post_obj.es_evento = resultado.get("es_evento")
                        post_obj.procesado = resultado.get("es_evento") is not None
                        post_obj.raw_data = {**(post_obj.raw_data or {}), "gemini": resultado}
                        post_obj.save()
                        if resultado.get("es_evento") and not resultado.get("es_pasado"):
                            if not hasattr(post_obj, "evento"):
                                crear_evento_desde_post(post_obj, resultado)
                                job.eventos_nuevos += 1
                        if resultado.get("tiene_horarios") and resultado.get("horarios_detectados"):
                            hace_7dias = timezone.now() - timedelta(days=7)
                            if not ReporteHorario.objects.filter(
                                parroquia=red.parroquia, fuente="scraper",
                                estado="pendiente", creado_en__gte=hace_7dias
                            ).exists():
                                ReporteHorario.objects.create(
                                    parroquia=red.parroquia,
                                    fuente="scraper",
                                    texto_usuario=f"Scraper Instagram @{red.url}",
                                    propuesta_ia=resultado["horarios_detectados"],
                                    resumen_cambios="Detectado automáticamente",
                                    imagen_url=post_obj.imagen_url,
                                    url_post=post_obj.raw_data.get("url_post", "") if post_obj.raw_data else "",
                                )
                    job.posts_nuevos += guardados
                    job.save(update_fields=["posts_nuevos", "eventos_nuevos", "actualizado_en"])
                    time.sleep(random.uniform(2, 4))
                except Exception as e:
                    job.errores += 1
                    job.save(update_fields=["errores", "actualizado_en"])
                    print(f"ERROR IG {red.parroquia.nombre}: {e}")

            # Facebook
            for red in redes_fb:
                if ScraperJob.objects.filter(pk=job.pk, estado="completado").exists():
                    break
                if red.parroquia.redes_verificadas:
                    job.procesados += 1
                    job.save(update_fields=["procesados", "actualizado_en"])
                    continue
                job.parroquia_actual = f"[FB] {red.parroquia.nombre}"
                job.procesados += 1
                job.save(update_fields=["parroquia_actual", "procesados", "actualizado_en"])
                try:
                    posts = scrapear_facebook_con_backend(red.url)
                    guardados_fb = 0
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
                            guardados_fb += 1
                    pendientes_fb = PostParroquia.objects.filter(
                        parroquia=red.parroquia,
                        procesado=False,
                        red_social="facebook",
                    )
                    for post_obj in pendientes_fb:
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
                                job.eventos_nuevos += 1
                        if resultado.get("tiene_horarios") and resultado.get("horarios_detectados"):
                            hace_7dias = timezone.now() - timedelta(days=7)
                            if not ReporteHorario.objects.filter(
                                parroquia=red.parroquia, fuente="scraper",
                                estado="pendiente", creado_en__gte=hace_7dias
                            ).exists():
                                ReporteHorario.objects.create(
                                    parroquia=red.parroquia,
                                    fuente="scraper",
                                    texto_usuario=f"Scraper Facebook {red.url}",
                                    propuesta_ia=resultado["horarios_detectados"],
                                    resumen_cambios="Detectado automáticamente",
                                    imagen_url=post_obj.imagen_url,
                                    url_post=post_obj.raw_data.get("url_post", "") if post_obj.raw_data else "",
                                )
                    job.posts_nuevos += guardados_fb
                    job.save(update_fields=["posts_nuevos", "eventos_nuevos", "actualizado_en"])
                    time.sleep(random.uniform(5, 10))
                except Exception as e:
                    job.errores += 1
                    job.save(update_fields=["errores", "actualizado_en"])
                    print(f"ERROR FB {red.parroquia.nombre}: {e}")

        finally:
            job.estado = "completado"
            job.parroquia_actual = ""
            job.mensaje_final = (
                f"{job.total} fuentes · {job.posts_nuevos} posts · "
                f"{job.eventos_nuevos} eventos · {job.errores} errores"
            )
            job.save()

    threading.Thread(target=correr, daemon=True).start()

    return JsonResponse({
        "ok": True,
        "job_id": job.pk,
        "total": job.total,
        "mensaje": f"Scraper iniciado — {len(redes_ig)} IG + {len(redes_fb)} FB",
    })


def pagina_privacidad(request):
    return render(request, "iglesias/publico/privacidad.html")


@require_POST
def toggle_verificacion(request, pk):
    if not request.user.is_staff:
        return HttpResponse("Forbidden", status=403)

    parroquia = get_object_or_404(Parroquia, pk=pk)
    campo = request.POST.get("campo", "")

    CAMPOS_VALIDOS = ["web_verificada", "redes_verificadas", "horarios_verificados"]
    if campo not in CAMPOS_VALIDOS:
        messages.error(request, "Campo inválido.")
        return redirect("iglesias:detalle_parroquia", pk=pk)

    valor_actual = getattr(parroquia, campo)
    setattr(parroquia, campo, not valor_actual)
    parroquia.save(update_fields=[campo])

    estado = "activada" if not valor_actual else "desactivada"
    messages.success(request, f"Protección '{campo}' {estado}.")
    return redirect("iglesias:detalle_parroquia", pk=pk)


def pagina_terminos(request):
    return render(request, "iglesias/publico/terminos.html")


def como_funciona(request):
    canonical = f"{request.scheme}://{request.get_host()}/publico/como-funciona/"
    niveles = [
        {"emoji": "🗺️", "nombre": "Explorador", "rango": "0 – 49 pts"},
        {"emoji": "🏘️", "nombre": "Vecino", "rango": "50 – 149 pts"},
        {"emoji": "⛪", "nombre": "Sacristán", "rango": "150 – 299 pts"},
        {"emoji": "📖", "nombre": "Catequista", "rango": "300 – 599 pts"},
        {"emoji": "✝️", "nombre": "Párroco", "rango": "600+ pts"},
    ]
    return render(request, "iglesias/publico/como_funciona.html", {
        "titulo_seo": "Cómo funciona ParroGuía — Directorio de parroquias de Buenos Aires",
        "descripcion_seo": "Descubrí cómo usar ParroGuía para encontrar parroquias, ver horarios de misas, reportar cambios y ganar puntos colaborando con la comunidad.",
        "canonical": canonical,
        "niveles": niveles,
    })


@staff_member_required
def moderacion_comentarios(request):
    estado = request.GET.get('estado', 'pendiente')
    estados_validos = ('pendiente', 'aprobado', 'rechazado')
    if estado not in estados_validos:
        estado = 'pendiente'
    comentarios = ComentarioParroquia.objects.filter(
        estado_moderacion=estado
    ).select_related('parroquia', 'usuario').order_by('-fecha')
    counts = {
        e: ComentarioParroquia.objects.filter(estado_moderacion=e).count()
        for e in estados_validos
    }
    return render(request, 'iglesias/moderacion_comentarios.html', {
        'comentarios': comentarios,
        'estado_activo': estado,
        'counts': counts,
    })


@staff_member_required
@require_POST
def aprobar_comentario(request, pk):
    comentario = get_object_or_404(ComentarioParroquia, pk=pk)
    comentario.estado_moderacion = 'aprobado'
    comentario.oculto = False
    comentario.save(update_fields=['estado_moderacion', 'oculto'])
    messages.success(request, 'Comentario aprobado.')
    referer = request.META.get('HTTP_REFERER', '')
    if url_has_allowed_host_and_scheme(referer, allowed_hosts={request.get_host()}):
        return redirect(referer)
    return redirect('iglesias:moderacion_comentarios')


@staff_member_required
@require_POST
def rechazar_comentario(request, pk):
    comentario = get_object_or_404(ComentarioParroquia, pk=pk)
    comentario.estado_moderacion = 'rechazado'
    comentario.oculto = True
    comentario.razon_rechazo = request.POST.get('razon', 'Rechazado manualmente')
    comentario.save(update_fields=['estado_moderacion', 'oculto', 'razon_rechazo'])
    messages.success(request, 'Comentario rechazado.')
    referer = request.META.get('HTTP_REFERER', '')
    if url_has_allowed_host_and_scheme(referer, allowed_hosts={request.get_host()}):
        return redirect(referer)
    return redirect('iglesias:moderacion_comentarios')


@login_required
@require_POST
def apelar_comentario(request, pk):
    comentario = get_object_or_404(
        ComentarioParroquia,
        pk=pk,
        usuario=request.user,
        estado_moderacion='rechazado',
    )
    if comentario.apelado:
        return JsonResponse({'ok': False, 'error': 'Ya apelaste este rechazo.'}, status=400)

    comentario.apelado = True
    comentario.apelado_en = timezone.now()
    comentario.estado_moderacion = 'pendiente'
    comentario.oculto = True
    comentario.save(update_fields=['apelado', 'apelado_en', 'estado_moderacion', 'oculto'])

    return JsonResponse({'ok': True, 'mensaje': 'Tu apelación fue enviada. La revisaremos pronto.'})


@csrf_exempt
def enviar_avisos_view(request):
    """Endpoint llamado por GitHub Actions cada hora para enviar avisos de misa."""
    logger.info("enviar_avisos_view alcanzado")
    if request.method != 'POST':
        return JsonResponse({'error': 'Método no permitido'}, status=405)

    token = request.headers.get('X-Scraper-Token', '')
    if token != settings.SCRAPER_SECRET_TOKEN:
        return JsonResponse({'error': 'No autorizado'}, status=403)

    from .avisos import enviar_avisos_misa
    resultado = enviar_avisos_misa()
    return JsonResponse(resultado)


@csrf_exempt
@login_required
@require_POST
def toggle_avisos_view(request):
    """Toggle avisos para la parroquia favorita. Acepta parroquia_pk en POST para multi-favoritas."""
    import logging
    logger = logging.getLogger(__name__)
    from .models import SuscripcionAvisoMisa, PerfilUsuario

    perfil, _ = PerfilUsuario.objects.get_or_create(user=request.user)

    parroquia_pk = request.POST.get('parroquia_pk')
    if parroquia_pk:
        try:
            parroquia_favorita = perfil.parroquias_favoritas.get(pk=int(parroquia_pk))
        except Exception:
            logger.warning(f"toggle_avisos: parroquia_pk={parroquia_pk} no válida para user={request.user}")
            return JsonResponse({'error': 'Parroquia no válida'}, status=400)
    else:
        parroquia_favorita = perfil.parroquias_favoritas.first()

    if not parroquia_favorita:
        logger.warning(f"toggle_avisos: user={request.user} no tiene favoritas")
        return JsonResponse({'error': 'No tenés parroquia favorita seleccionada'}, status=400)

    suscripcion, created = SuscripcionAvisoMisa.objects.get_or_create(
        usuario=request.user,
        parroquia=parroquia_favorita,
        defaults={'activa': True, 'dias_semana': []}
    )

    if not created:
        suscripcion.activa = not suscripcion.activa
        suscripcion.save(update_fields=['activa'])

    return JsonResponse({
        'activa': suscripcion.activa,
        'mensaje': 'Avisos activados' if suscripcion.activa else 'Avisos desactivados'
    })


def error_403(request, exception=None):
    return render(request, 'iglesias/403.html', status=403)


def error_404(request, exception=None):
    return render(request, 'iglesias/404.html', status=404)


def error_500(request):
    return render(request, 'iglesias/500.html', status=500)
