from datetime import date

from django.db.models import Count, Q
from django.http import HttpResponse, HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .models import Parroquia, RedSocial, PostParroquia, TipoEvento, Evento, CategoriaEvento, HorarioMisa, ScraperJob

from django.views.decorators.http import require_POST
from django.urls import reverse
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test

# --- Eliminar RedSocial ---
@require_POST
@login_required
@user_passes_test(lambda u: u.is_staff)
def eliminar_red_social(request, pk):
    red = get_object_or_404(RedSocial, pk=pk)
    parroquia_id = red.parroquia_id
    red.delete()
    next_url = request.POST.get("next") or reverse("iglesias:detalle_parroquia", args=[parroquia_id])
    return redirect(next_url)


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


@require_POST
def verificar_red_social(request, pk):
    red = get_object_or_404(RedSocial, pk=pk, activo=True, verificado=False)
    red.verificado = True
    red.save(update_fields=["verificado"])

    if request.headers.get("HX-Request"):
        grupo = _armar_grupo_red(red.parroquia, red.tipo, red.get_tipo_display())
        return render(
            request,
            "iglesias/partials/red_status.html",
            {"grupo": grupo},
        )

    return redirect(request.POST.get("next") or "iglesias:lista_parroquias")


@require_POST
def eliminar_red_social(request, pk):
    red = get_object_or_404(RedSocial, pk=pk, activo=True, verificado=False)
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
    evento = get_object_or_404(Evento, pk=pk)
    evento.verificado = True
    evento.activo = True
    evento.save(update_fields=["verificado", "activo"])

    if request.headers.get("HX-Request"):
        return render(request, "iglesias/partials/evento_fila.html", {"evento": evento})

    return redirect(request.POST.get("next") or "iglesias:lista_parroquias")


@require_POST
def rechazar_evento(request, pk):
    evento = get_object_or_404(Evento, pk=pk)
    evento.activo = False
    evento.verificado = False
    evento.save(update_fields=["activo", "verificado"])

    if request.headers.get("HX-Request"):
        return render(request, "iglesias/partials/evento_fila.html", {"evento": evento})

    return redirect(request.POST.get("next") or "iglesias:lista_parroquias")


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

    eventos = eventos.select_related("parroquia", "post").order_by("fecha", "-creado_en")

    counts = {
        "pendiente": es_futuro(Evento.objects.filter(verificado=False, activo=True)).count(),
        "aprobado": es_futuro(Evento.objects.filter(verificado=True, activo=True)).count(),
        "rechazado": es_futuro(Evento.objects.filter(activo=False)).count(),
        "total": es_futuro(Evento.objects.all()).count(),
    }

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
    """Endpoint separado para obtener el resultado del último job."""
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
    )

    def correr_scraper():
        from scraper_redes.run import scrapear_con_backend, scrapear_facebook_con_backend, crear_evento_desde_post
        from scraper_redes.procesador import procesar_post
        from apps.iglesias.models import PostParroquia
        import time, random

        for i, red in enumerate(redes_ig):
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
                    resultado = procesar_post(post_dict)
                    post_obj.es_evento = resultado.get("es_evento")
                    post_obj.procesado = resultado.get("es_evento") is not None
                    post_obj.raw_data = {**(post_obj.raw_data or {}), "gemini": resultado}
                    post_obj.save()

                    if resultado.get("es_evento") and not resultado.get("es_pasado"):
                        if not hasattr(post_obj, "evento"):
                            crear_evento_desde_post(post_obj, resultado)
                            eventos_fb += 1

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
        evento.edad_desde = int(edad_desde) if edad_desde else 0
        evento.edad_hasta = int(edad_hasta) if edad_hasta else 100

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
        evento.edad_desde = int(edad_desde) if edad_desde else 0
        evento.edad_hasta = int(edad_hasta) if edad_hasta else 100

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

        for horario in list(parroquia.horarios_misa.all()):
            if request.POST.get(f"delete_{horario.pk}"):
                horario.delete()
            else:
                dias = request.POST.get(f"dias_{horario.pk}", "").strip()
                horarios_val = request.POST.get(f"horarios_{horario.pk}", "").strip()
                nota = request.POST.get(f"nota_{horario.pk}", "").strip() or None
                if dias and horarios_val:
                    horario.dias = dias
                    horario.horarios = horarios_val
                    horario.nota = nota
                    horario.save(update_fields=["dias", "horarios", "nota"])

        new_dias_list = request.POST.getlist("new_dias")
        new_horarios_list = request.POST.getlist("new_horarios")
        new_nota_list = request.POST.getlist("new_nota")
        for dias, horarios_val, nota in zip(new_dias_list, new_horarios_list, new_nota_list):
            dias = dias.strip()
            horarios_val = horarios_val.strip()
            nota = nota.strip() or None
            if dias and horarios_val:
                HorarioMisa.objects.create(
                    parroquia=parroquia,
                    dias=dias,
                    horarios=horarios_val,
                    nota=nota,
                )

        parroquia = get_object_or_404(
            Parroquia.objects.prefetch_related("horarios_misa").select_related("info_bai"),
            pk=pk,
        )
        editing = False
    else:
        editing = request.GET.get("cancelar") != "1"

    return render(request, "iglesias/partials/seccion_bai.html", {
        "parroquia": parroquia,
        "editing": editing,
    })
