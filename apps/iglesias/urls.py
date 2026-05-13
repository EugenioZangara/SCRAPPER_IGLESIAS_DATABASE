from django.urls import path
from django.views.generic import RedirectView

from . import views

app_name = "iglesias"

urlpatterns = [
    path("", RedirectView.as_view(pattern_name="iglesias:lista_parroquias", permanent=False), name="inicio"),
    path("parroquias/", views.lista_parroquias, name="lista_parroquias"),
    path("parroquias/<int:pk>/", views.detalle_parroquia, name="detalle_parroquia"),
    path("redes/<int:pk>/verificar/", views.verificar_red_social, name="verificar_red_social"),
    path("redes/<int:pk>/eliminar/", views.eliminar_red_social, name="eliminar_red_social"),
    path("eventos/<int:pk>/aprobar/", views.aprobar_evento, name="aprobar_evento"),
    path("eventos/<int:pk>/rechazar/", views.rechazar_evento, name="rechazar_evento"),
    path("eventos/<int:pk>/editar/", views.editar_evento, name="editar_evento"),
]
