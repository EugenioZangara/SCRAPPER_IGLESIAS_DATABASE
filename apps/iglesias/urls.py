from django.urls import path
from django.views.generic import RedirectView

from . import views

app_name = "iglesias"

urlpatterns = [
    path("publico/", views.publico_inicio, name="publico_inicio"),
    path("publico/buscar/", views.publico_buscar, name="publico_buscar"),
    path("publico/geo/", views.parroquias_geo_json, name="parroquias_geo"),
    path("publico/favoritas/", views.publico_favoritas, name="publico_favoritas"),
    path("publico/<int:pk>/", views.publico_detalle, name="publico_detalle"),
    path(
        "",
        RedirectView.as_view(pattern_name="iglesias:publico_inicio", permanent=False),
        name="inicio",
    ),
    path("parroquias/", views.lista_parroquias, name="lista_parroquias"),
    path("parroquias/<int:pk>/", views.detalle_parroquia, name="detalle_parroquia"),
    path(
        "parroquias/<int:pk>/editar/contacto/",
        views.editar_seccion_contacto,
        name="editar_seccion_contacto",
    ),
    path(
        "parroquias/<int:pk>/editar/ubicacion/",
        views.editar_seccion_ubicacion,
        name="editar_seccion_ubicacion",
    ),
    path(
        "parroquias/<int:pk>/editar/clero/",
        views.editar_seccion_clero,
        name="editar_seccion_clero",
    ),
    path(
        "parroquias/<int:pk>/editar/bai/",
        views.editar_seccion_bai,
        name="editar_seccion_bai",
    ),
    path(
        "parroquias/<int:pk>/editar/nombre/",
        views.editar_nombre_parroquia,
        name="editar_nombre_parroquia",
    ),
    path(
        "parroquias/<int:pk>/agregar-red/",
        views.agregar_red_social,
        name="agregar_red_social",
    ),
    path(
        "redes/<int:pk>/verificar/",
        views.verificar_red_social,
        name="verificar_red_social",
    ),
    path("redes/<int:pk>/eliminar/", views.eliminar_red_social, name="eliminar_red"),
    path("eventos/<int:pk>/aprobar/", views.aprobar_evento, name="aprobar_evento"),
    path("eventos/<int:pk>/rechazar/", views.rechazar_evento, name="rechazar_evento"),
    path("eventos/moderacion/", views.moderacion_eventos, name="moderacion_eventos"),
    path("comentarios/moderacion/", views.moderacion_comentarios, name="moderacion_comentarios"),
    path("comentarios/<int:pk>/aprobar/", views.aprobar_comentario, name="aprobar_comentario"),
    path("comentarios/<int:pk>/rechazar/", views.rechazar_comentario, name="rechazar_comentario"),
    path("comentarios/<int:pk>/apelar/", views.apelar_comentario, name="apelar_comentario"),
    path(
        "eventos/moderacion/pasados/",
        views.moderacion_eventos_pasados,
        name="moderacion_eventos_pasados",
    ),
    path("eventos/<int:pk>/editar/", views.editar_evento, name="editar_evento"),
    path(
        "eventos/<int:pk>/aprobar-extendido/",
        views.aprobar_extendido,
        name="aprobar_extendido",
    ),
    path(
        "parroquias/<int:pk>/eliminar/",
        views.eliminar_parroquia,
        name="eliminar_parroquia",
    ),
    path(
        "parroquias/<int:pk>/scrapear/",
        views.scrapear_parroquia,
        name="scrapear_parroquia",
    ),
    path("eventos/tipos/crear/", views.crear_tipo_evento, name="crear_tipo_evento"),
    path(
        "eventos/categorias/crear/",
        views.crear_categoria_evento,
        name="crear_categoria_evento",
    ),
    path(
        "scraper/ejecutar/",
        views.ejecutar_scraper_completo,
        name="ejecutar_scraper_completo",
    ),
    path("scraper/estado/", views.scraper_estado, name="scraper_estado"),
    path(
        "scraper/resultado/", views.scraper_estado_resultado, name="scraper_resultado"
    ),
    path("scraper/detener/", views.detener_scraper, name="detener_scraper"),
    path(
        "publico/<int:pk>/reportar-horario/",
        views.reportar_horario,
        name="reportar_horario",
    ),
    path("horarios/reportes/", views.revision_reportes, name="revision_reportes"),
    path(
        "horarios/reportes/<int:pk>/aplicar/",
        views.aplicar_reporte,
        name="aplicar_reporte",
    ),
    path(
        "horarios/reportes/<int:pk>/descartar/",
        views.descartar_reporte,
        name="descartar_reporte",
    ),
    path("horarios/reportes/count/", views.reportes_count, name="reportes_count"),
    path("horarios/reportes/<int:pk>/card/", views.reporte_card, name="reporte_card"),
    path(
        "publico/<int:pk>/validar-horario/",
        views.validar_horario,
        name="validar_horario",
    ),
    path("publico/ranking/", views.publico_ranking, name="publico_ranking"),
    path("admin-login/", views.admin_login, name="admin_login"),
    path("publico/<int:pk>/favorita/", views.set_parroquia_favorita, name="set_parroquia_favorita"),
    path("api/scraper/ejecutar/", views.scraper_automatico, name="scraper_automatico"),
    path("publico/mis-aportes/", views.publico_mis_aportes, name="publico_mis_aportes"),
    path("publico/perfil/", views.publico_perfil, name="publico_perfil"),
    path("publico/privacidad/", views.pagina_privacidad, name="privacidad"),
    path("publico/terminos/", views.pagina_terminos, name="terminos"),
    path("publico/como-funciona/", views.como_funciona, name="como_funciona"),
    path("publico/<int:pk>/votar-horario/", views.votar_horario, name="votar_horario"),
    path("publico/<int:pk>/comentar/", views.agregar_comentario, name="agregar_comentario"),
    path(
        "parroquias/<int:pk>/toggle-verificacion/",
        views.toggle_verificacion,
        name="toggle_verificacion",
    ),
]
