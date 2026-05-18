from django.contrib import admin

from .models import (
    Parroquia,
    RedSocial,
    PostParroquia,
    CategoriaEvento,
    Evento,
    InfoBaiglesias,
    HorarioMisa,
)


class HorarioMisaInline(admin.TabularInline):
    model = HorarioMisa
    extra = 0


@admin.register(Parroquia)
class ParroquiaAdmin(admin.ModelAdmin):
    list_display = (
        "nombre",
        "direccion",
        "barrio",
        "tiene_redes",
        "detalles_completos",
    )
    search_fields = ("nombre", "barrio", "decanato")
    list_filter = ("tiene_redes", "detalles_completos", "vicaria")
    inlines = [HorarioMisaInline]


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


@admin.register(CategoriaEvento)
class CategoriaEventoAdmin(admin.ModelAdmin):
    list_display = ("nombre", "activo")
    search_fields = ("nombre",)
    list_filter = ("activo",)


@admin.register(Evento)
class EventoAdmin(admin.ModelAdmin):
    list_display = ("titulo", "parroquia", "tipo", "categoria", "fecha",
                    "hora", "lugar", "activo", "verificado",
                    "exportado_sheets", "creado_en")
    search_fields = ("titulo", "parroquia__nombre", "lugar")
    list_filter = ("tipo", "activo", "fecha")
    readonly_fields = ("creado_en",)


@admin.register(HorarioMisa)
class HorarioMisaAdmin(admin.ModelAdmin):
    list_display = ("parroquia", "dias", "horarios")
    search_fields = ("parroquia__nombre",)


@admin.register(InfoBaiglesias)
class InfoBaiglesiasAdmin(admin.ModelAdmin):
    list_display = ("parroquia", "url_scrapeada", "scrapeado_el")
    search_fields = ("parroquia__nombre",)
    readonly_fields = ("scrapeado_el",)
