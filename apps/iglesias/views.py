from datetime import date

from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .models import Parroquia, RedSocial, Evento


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
        Parroquia.objects.prefetch_related("redes", "eventos"),
        pk=pk,
    )
    eventos_estado = _estado_eventos(parroquia)

    return render(
        request,
        "iglesias/detalle_parroquia.html",
        {
            "parroquia": parroquia,
            "eventos_estado": eventos_estado,
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

    return redirect(request.POST.get("next") or "iglesias:lista_parroquias")


@require_POST
def rechazar_evento(request, pk):
    evento = get_object_or_404(Evento, pk=pk)
    evento.activo = False
    evento.verificado = False
    evento.save(update_fields=["activo", "verificado"])

    return redirect(request.POST.get("next") or "iglesias:lista_parroquias")


def editar_evento(request, pk):
    evento = get_object_or_404(Evento, pk=pk)
    parroquia = evento.parroquia

    if request.method == "POST":
        evento.titulo = request.POST.get("titulo", evento.titulo).strip()
        evento.tipo = request.POST.get("tipo", evento.tipo)
        evento.lugar = request.POST.get("lugar", "").strip() or None
        evento.descripcion = request.POST.get("descripcion", "").strip() or None

        fecha_str = request.POST.get("fecha", "").strip()
        if fecha_str:
            try:
                from datetime import datetime
                evento.fecha = datetime.strptime(fecha_str, "%Y-%m-%d").date()
            except ValueError:
                pass
        else:
            evento.fecha = None

        hora_str = request.POST.get("hora", "").strip()
        if hora_str:
            try:
                from datetime import datetime
                evento.hora = datetime.strptime(hora_str, "%H:%M").time()
            except ValueError:
                pass
        else:
            evento.hora = None

        evento.verificado = True
        evento.activo = True
        evento.save()

        return redirect("iglesias:detalle_parroquia", pk=parroquia.pk)

    return render(
        request,
        "iglesias/editar_evento.html",
        {
            "evento": evento,
            "parroquia": parroquia,
            "tipo_choices": Evento.TIPO_CHOICES,
        },
    )