from django.contrib import admin

from .models import (
    Parroquia,
    RedSocial,
    PostParroquia,
    TipoEvento,
    CategoriaEvento,
    Evento,
    InfoBaiglesias,
    HorarioMisa,
    ReporteHorario,
    PerfilUsuario,
    Banner,
    PerfilGestorParroquia,
)


class HorarioMisaInline(admin.TabularInline):
    model = HorarioMisa
    extra = 0
    fields = ("dia_semana", "horarios", "nota", "fuente")


@admin.register(Parroquia)
class ParroquiaAdmin(admin.ModelAdmin):
    list_display = (
        "nombre",
        "direccion",
        "barrio",
        "tiene_redes",
        "detalles_completos",
    )
    search_fields = ("nombre", "barrio", "decanato", "provincia", "ciudad", "diocesis")
    list_filter = ("tiene_redes", "detalles_completos", "vicaria", "provincia",
                   "web_verificada", "redes_verificadas", "horarios_verificados")
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


@admin.register(TipoEvento)
class TipoEventoAdmin(admin.ModelAdmin):
    list_display = ("nombre", "activo")
    search_fields = ("nombre",)
    list_filter = ("activo",)


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
    list_display = ("parroquia", "dia_semana", "horarios", "fuente")
    search_fields = ("parroquia__nombre",)
    list_filter = ("dia_semana", "fuente")


@admin.register(ReporteHorario)
class ReporteHorarioAdmin(admin.ModelAdmin):
    list_display = ("parroquia", "usuario", "estado", "creado_en", "revisado_por")
    list_filter = ("estado",)
    search_fields = ("parroquia__nombre",)
    readonly_fields = ("creado_en", "revisado_en", "revisado_por",
                       "propuesta_ia", "resumen_cambios")


@admin.register(PerfilUsuario)
class PerfilUsuarioAdmin(admin.ModelAdmin):
    list_display = ("user", "score", "nivel", "reportes_enviados",
                    "reportes_aprobados", "reportes_rechazados",
                    "validaciones_enviadas", "proveedor", "creado_en")
    list_filter = ("proveedor",)
    search_fields = ("user__username", "user__email")
    ordering = ("-score",)
    readonly_fields = ("score", "reportes_enviados", "reportes_aprobados",
                       "reportes_rechazados", "validaciones_enviadas",
                       "creado_en", "actualizado_en")


@admin.register(InfoBaiglesias)
class InfoBaiglesiasAdmin(admin.ModelAdmin):
    list_display = ("parroquia", "url_scrapeada", "scrapeado_el")
    search_fields = ("parroquia__nombre",)
    readonly_fields = ("scrapeado_el",)


@admin.register(Banner)
class BannerAdmin(admin.ModelAdmin):
    list_display = ("titulo", "posicion", "activo", "orden", "creado_en")
    list_filter = ("posicion", "activo")
    list_editable = ("activo", "orden")


@admin.register(PerfilGestorParroquia)
class PerfilGestorParroquiaAdmin(admin.ModelAdmin):
    list_display = ("user", "parroquia", "activo", "creado")
    list_filter = ("activo",)
    search_fields = ("user__username", "user__email", "parroquia__nombre")
    raw_id_fields = ("user", "parroquia")
    readonly_fields = ("creado",)
