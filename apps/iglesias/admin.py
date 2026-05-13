from django.contrib import admin
from .models import Parroquia, RedSocial, PostParroquia, Evento

@admin.register(Parroquia)
class ParroquiaAdmin(admin.ModelAdmin):
    list_display = ("nombre", "direccion", "barrio", "tiene_redes", "detalles_completos")
    search_fields = ("nombre", "barrio", "decanato")
    list_filter = ("tiene_redes", "detalles_completos", "vicaria")


@admin.register(RedSocial)
class RedSocialAdmin(admin.ModelAdmin):
    list_display = ("parroquia", "tipo", "url", "activo", "verificado")
    search_fields = ("parroquia__nombre", "url")
    list_filter = ("tipo", "activo", "verificado")


@admin.register(PostParroquia)
class PostParroquiaAdmin(admin.ModelAdmin):
    list_display = ("parroquia", "red_social", "post_id", "procesado", "es_evento", "creado_en")
    search_fields = ("parroquia__nombre", "post_id")
    list_filter = ("red_social", "procesado", "es_evento")
    readonly_fields = ("creado_en", "raw_data")

@admin.register(Evento)
class EventoAdmin(admin.ModelAdmin):
    list_display = ("titulo", "parroquia", "tipo", "fecha", "hora", "lugar", "activo", "creado_en")
    search_fields = ("titulo", "parroquia__nombre", "lugar")
    list_filter = ("tipo", "activo", "fecha")
    readonly_fields = ("creado_en",)