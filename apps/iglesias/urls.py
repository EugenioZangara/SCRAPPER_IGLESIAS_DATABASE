from django.urls import path
from django.views.generic import RedirectView

from . import views

app_name = "iglesias"

urlpatterns = [
    path("", RedirectView.as_view(pattern_name="iglesias:lista_parroquias", permanent=False), name="inicio"),
    path("parroquias/", views.lista_parroquias, name="lista_parroquias"),
    path("parroquias/<int:pk>/", views.detalle_parroquia, name="detalle_parroquia"),
    path("parroquias/<int:pk>/editar/contacto/", views.editar_seccion_contacto, name="editar_seccion_contacto"),
    path("parroquias/<int:pk>/editar/ubicacion/", views.editar_seccion_ubicacion, name="editar_seccion_ubicacion"),
    path("parroquias/<int:pk>/editar/clero/", views.editar_seccion_clero, name="editar_seccion_clero"),
    path("parroquias/<int:pk>/editar/bai/", views.editar_seccion_bai, name="editar_seccion_bai"),
    path("redes/<int:pk>/verificar/", views.verificar_red_social, name="verificar_red_social"),
    path("redes/<int:pk>/eliminar/", views.eliminar_red_social, name="eliminar_red"),
    path("eventos/<int:pk>/aprobar/", views.aprobar_evento, name="aprobar_evento"),
    path("eventos/<int:pk>/rechazar/", views.rechazar_evento, name="rechazar_evento"),
    path("eventos/<int:pk>/editar/", views.editar_evento, name="editar_evento"),
    path("parroquias/<int:pk>/scrapear/", views.scrapear_parroquia, name="scrapear_parroquia"),
]
