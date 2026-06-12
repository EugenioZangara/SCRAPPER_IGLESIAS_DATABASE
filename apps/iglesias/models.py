from django.db import models
from django.conf import settings
from django.contrib.auth.models import User


class Parroquia(models.Model):
    # Identificador y enlaces
    id_externo = models.IntegerField(unique=True, help_text="ID de la URL oficial")
    nombre = models.CharField(max_length=255)
    url_detalle = models.CharField(max_length=255)

    # Ubicación y Contacto
    direccion = models.CharField(max_length=255, blank=True, null=True)
    codigo_postal = models.CharField(max_length=100, blank=True, null=True)
    telefonos = models.CharField(max_length=255, blank=True, null=True)
    mail_1 = models.EmailField(max_length=255, blank=True, null=True)
    mail_2 = models.EmailField(max_length=255, blank=True, null=True)
    sitio_web = models.URLField(max_length=500, blank=True, null=True)
    imagen_url = models.URLField(
        max_length=2000,
        blank=True,
        default='',
        help_text='URL de imagen de la fachada o interior. Obtenida por scraping.'
    )

    # Organización Eclesiástica
    vicaria = models.CharField(max_length=100, blank=True, null=True)
    decanato = models.CharField(max_length=100, blank=True, null=True)
    barrio = models.CharField(max_length=100, blank=True, null=True)
    provincia = models.CharField(
        max_length=100, blank=True, null=True,
        default="Ciudad Autónoma de Buenos Aires",
        help_text="Provincia donde se encuentra la parroquia"
    )
    ciudad = models.CharField(
        max_length=100, blank=True, null=True,
        help_text="Ciudad o localidad"
    )
    diocesis = models.CharField(
        max_length=150, blank=True, null=True,
        help_text="Diócesis o Arquidiócesis"
    )
    clero_cargo = models.CharField(max_length=255, blank=True, null=True)
    parroco = models.CharField(max_length=255, blank=True, null=True)

    # Historia y Límites
    fecha_ereccion_canonica = models.CharField(max_length=100, blank=True, null=True)
    comenzo_a_funcionar = models.CharField(max_length=100, blank=True, null=True)
    limite_parroquial = models.TextField(blank=True, null=True)

    # Control de Scraper
    detalles_completos = models.BooleanField(default=False)
    actualizado_el = models.DateTimeField(auto_now=True)
    tiene_redes = models.BooleanField(default=False)
    web_verificada = models.BooleanField(
        default=False,
        help_text="Si True, el scraper no sobreescribe sitio_web"
    )
    redes_verificadas = models.BooleanField(
        default=False,
        help_text="Si True, el scraper no agrega ni modifica redes sociales"
    )
    horarios_verificados = models.BooleanField(
        default=False,
        help_text="Si True, el scraper no sobreescribe horarios de misa"
    )
    latitud = models.FloatField(null=True, blank=True)
    longitud = models.FloatField(null=True, blank=True)

    class Meta:
        verbose_name = "Parroquia"
        verbose_name_plural = "Parroquias"

    def __str__(self):
        return self.nombre


class RedSocial(models.Model):
    TIPO_CHOICES = [
        ("facebook", "Facebook"),
        ("instagram", "Instagram"),
        ("youtube", "YouTube"),
        ("tiktok", "TikTok"),
        ("otro", "Otro"),
    ]

    parroquia = models.ForeignKey(
        "Parroquia", on_delete=models.CASCADE, related_name="redes"
    )
    username = models.CharField(max_length=255, null=True, blank=True)
    tipo = models.CharField(max_length=50, choices=TIPO_CHOICES)
    url = models.URLField(max_length=500)

    activo = models.BooleanField(default=True)
    verificado = models.BooleanField(default=False)

    creado_el = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("parroquia", "url")

    def __str__(self):
        return f"{self.tipo} - {self.parroquia.nombre}"


class PostParroquia(models.Model):
    RED_SOCIAL_CHOICES = [
        ("facebook", "Facebook"),
        ("instagram", "Instagram"),
    ]

    parroquia = models.ForeignKey(
        "Parroquia", on_delete=models.CASCADE, related_name="posts_redes"
    )
    post_id = models.CharField(max_length=100, unique=True, help_text="ID nativo de Meta")
    red_social = models.CharField(max_length=20, choices=RED_SOCIAL_CHOICES)
    imagen_url = models.URLField(max_length=1000, help_text="Puede caducar en Instagram")
    fecha_publicacion = models.DateTimeField(null=True, blank=True, help_text="Fecha de publicación en la red social")
    procesado = models.BooleanField(default=False)
    es_evento = models.BooleanField(null=True, help_text="null = sin procesar")
    creado_en = models.DateTimeField(auto_now_add=True)
    raw_data = models.JSONField(blank=True, null=True, help_text="Respuesta cruda de la API")

    class Meta:
        ordering = ["-creado_en"]
        verbose_name = "Post de Parroquia"
        verbose_name_plural = "Posts de Parroquias"

    def __str__(self):
        return f"{self.red_social.capitalize()} post ({self.post_id}) - {self.parroquia.nombre}"

class TipoEvento(models.Model):
    nombre = models.CharField(max_length=100, unique=True)
    activo = models.BooleanField(default=True)

    class Meta:
        ordering = ["nombre"]
        verbose_name = "Tipo de Evento"
        verbose_name_plural = "Tipos de Evento"

    def __str__(self):
        return self.nombre


class CategoriaEvento(models.Model):
    nombre = models.CharField(max_length=100, unique=True)
    activo = models.BooleanField(default=True)

    class Meta:
        ordering = ["nombre"]
        verbose_name = "Categoría de Evento"
        verbose_name_plural = "Categorías de Evento"

    def __str__(self):
        return self.nombre


class Evento(models.Model):
    parroquia = models.ForeignKey(
        "Parroquia", on_delete=models.CASCADE, related_name="eventos"
    )
    post = models.OneToOneField(
        "PostParroquia", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="evento"
    )

    titulo = models.CharField(max_length=255)
    tipo = models.ForeignKey(
        "TipoEvento", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="eventos"
    )
    fecha = models.DateField(null=True, blank=True)
    hora = models.TimeField(null=True, blank=True)
    lugar = models.CharField(max_length=255, blank=True, null=True)
    descripcion = models.TextField(blank=True, null=True)
    categoria = models.ForeignKey(
        "CategoriaEvento", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="eventos"
    )
    fecha_fin = models.DateTimeField(null=True, blank=True)
    url_externa = models.URLField(max_length=500, blank=True, null=True,
        help_text="Link de contacto o inscripción (WhatsApp, formulario, etc.)")
    AUDIENCIA_CHOICES = [
        ("ambos", "Hombres y Mujeres"),
        ("hombres", "Hombres"),
        ("mujeres", "Mujeres"),
    ]
    audiencia = models.CharField(max_length=20, choices=AUDIENCIA_CHOICES,
        blank=True, null=True)
    edad_desde = models.PositiveIntegerField(null=True, blank=True, default=0)
    edad_hasta = models.PositiveIntegerField(null=True, blank=True, default=100)
    gratuito = models.BooleanField(null=True, blank=True)
    capacidad = models.PositiveIntegerField(null=True, blank=True)
    ubicacion_lugar = models.CharField(max_length=255, blank=True, null=True)
    ubicacion_direccion = models.CharField(max_length=255, blank=True, null=True)
    ubicacion_ciudad = models.CharField(max_length=100, blank=True, null=True,
        default="Buenos Aires")
    ubicacion_cp = models.CharField(max_length=20, blank=True, null=True)
    ubicacion_provincia = models.CharField(max_length=100, blank=True, null=True,
        default="Buenos Aires")
    exportado_sheets = models.BooleanField(default=False,
        help_text="True si fue exportado a Google Sheets")
    imagen_url = models.URLField(max_length=1000, blank=True, null=True)

    activo = models.BooleanField(default=True)
    verificado = models.BooleanField(default=False, help_text="Confirmado manualmente por un administrador")
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["fecha", "hora"]
        verbose_name = "Evento"
        verbose_name_plural = "Eventos"

    def __str__(self):
        fecha_str = self.fecha.strftime("%d/%m/%Y") if self.fecha else "Sin fecha"
        return f"{self.titulo} - {self.parroquia.nombre} ({fecha_str})"


class InfoBaiglesias(models.Model):
    parroquia = models.OneToOneField(
        "Parroquia", on_delete=models.CASCADE, related_name="info_bai"
    )
    direccion_completa = models.TextField(blank=True, null=True)
    como_llegar = models.TextField(blank=True, null=True)
    url_scrapeada = models.URLField(max_length=500)
    scrapeado_el = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Info BAIglesias"
        verbose_name_plural = "Infos BAIglesias"

    def __str__(self):
        return f"Info BAI — {self.parroquia.nombre}"


class HorarioMisa(models.Model):
    DIA_CHOICES = [
        (0, "Lunes"),
        (1, "Martes"),
        (2, "Miércoles"),
        (3, "Jueves"),
        (4, "Viernes"),
        (5, "Sábado"),
        (6, "Domingo"),
    ]
    parroquia = models.ForeignKey(
        "Parroquia", on_delete=models.CASCADE, related_name="horarios_misa"
    )
    dia_semana = models.IntegerField(choices=DIA_CHOICES)
    horarios = models.CharField(
        max_length=200,
        help_text="Ej: 8:00 · 19:00"
    )
    nota = models.TextField(blank=True, null=True)
    fuente = models.CharField(
        max_length=20,
        choices=[("baiglesias", "BAIglesias"), ("web_propia", "Web propia"),
                 ("usuario", "Reporte de usuario")],
        default="baiglesias"
    )
    creado_en = models.DateTimeField(auto_now_add=True, null=True)
    actualizado_en = models.DateTimeField(auto_now=True, null=True)

    class Meta:
        verbose_name = "Horario de Misa"
        verbose_name_plural = "Horarios de Misa"
        ordering = ["dia_semana"]
        unique_together = ("parroquia", "dia_semana")

    _SCHEMA_DAYS = ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"]

    @property
    def schema_opening_hours(self):
        day = self._SCHEMA_DAYS[self.dia_semana]
        times = [t.strip() for t in self.horarios.split("·") if t.strip()]
        return [f"{day} {t}-{t}" for t in times]

    def __str__(self):
        return f"{self.get_dia_semana_display()}: {self.horarios} — {self.parroquia.nombre}"


class ValidacionHorario(models.Model):
    parroquia = models.ForeignKey(
        "Parroquia", on_delete=models.CASCADE,
        related_name="validaciones_horario"
    )
    usuario = models.ForeignKey(
        User, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="validaciones_horario_usuario"
    )
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-creado_en"]
        verbose_name = "Validación de Horario"
        verbose_name_plural = "Validaciones de Horario"

    def __str__(self):
        return f"Validación {self.pk} — {self.parroquia.nombre}"


class PerfilUsuario(models.Model):
    user = models.OneToOneField(
        User, on_delete=models.CASCADE,
        related_name="perfil"
    )
    avatar_url = models.URLField(max_length=500, blank=True, null=True)
    proveedor = models.CharField(
        max_length=20, blank=True, null=True,
        help_text="google, facebook, etc."
    )
    score = models.IntegerField(default=0)
    reportes_enviados = models.IntegerField(default=0)
    reportes_aprobados = models.IntegerField(default=0)
    reportes_rechazados = models.IntegerField(default=0)
    validaciones_enviadas = models.IntegerField(default=0)
    parroquias_favoritas = models.ManyToManyField(
        "Parroquia",
        blank=True,
        related_name="usuarios_favoritos"
    )
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-score"]
        verbose_name = "Perfil de Usuario"
        verbose_name_plural = "Perfiles de Usuario"

    def __str__(self):
        return f"{self.user.username} — score: {self.score}"

    @property
    def nivel(self):
        if self.score >= 100:
            return "Verificado"
        elif self.score >= 51:
            return "Experto"
        elif self.score >= 11:
            return "Confiable"
        return "Nuevo"

    @property
    def nivel_color(self):
        colores = {
            "Verificado": "#4f46e5",
            "Experto": "#0f6e56",
            "Confiable": "#d97706",
            "Nuevo": "#6b7280",
        }
        return colores.get(self.nivel, "#6b7280")

    @property
    def get_avatar(self):
        return self.avatar_url or None

    NIVEL_COLORES = {
        'explorador': ('#dbeafe', '#1e40af'),
        'vecino':     ('#dcfce7', '#166534'),
        'sacristan':  ('#fef9c3', '#854d0e'),
        'catequista': ('#ede9fe', '#5b21b6'),
        'parroco':    ('#fee2e2', '#991b1b'),
    }

    @property
    def nivel_slug(self):
        if self.score >= 600: return 'parroco'
        if self.score >= 300: return 'catequista'
        if self.score >= 150: return 'sacristan'
        if self.score >= 50:  return 'vecino'
        return 'explorador'

    @property
    def color_avatar(self):
        return self.NIVEL_COLORES[self.nivel_slug][0]

    @property
    def color_avatar_texto(self):
        return self.NIVEL_COLORES[self.nivel_slug][1]

    def get_nivel_display(self):
        return self.nivel_slug.capitalize()


class ReporteHorario(models.Model):
    ESTADO_CHOICES = [
        ("pendiente", "Pendiente"),
        ("aplicado", "Aplicado"),
        ("descartado", "Descartado"),
    ]
    parroquia = models.ForeignKey(
        "Parroquia", on_delete=models.CASCADE,
        related_name="reportes_horario"
    )
    usuario = models.ForeignKey(
        User, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="reportes_horario"
    )
    texto_usuario = models.TextField(
        help_text="Texto libre ingresado por el usuario"
    )
    propuesta_ia = models.JSONField(
        null=True, blank=True,
        help_text="Lista de dicts con dias/horarios propuestos por la IA"
    )
    resumen_cambios = models.TextField(
        blank=True, null=True,
        help_text="Descripción de los cambios detectados por la IA"
    )
    estado = models.CharField(
        max_length=20, choices=ESTADO_CHOICES, default="pendiente"
    )
    imagen_url = models.URLField(
        max_length=1000, blank=True, null=True,
        help_text="URL de la imagen del post scrapeado"
    )
    url_post = models.URLField(
        max_length=1000, blank=True, null=True,
        help_text="URL del post original en la red social"
    )
    fuente = models.CharField(
        max_length=20,
        choices=[
            ("usuario", "Reporte de usuario"),
            ("scraper", "Scraper automático"),
        ],
        default="usuario"
    )
    creado_en = models.DateTimeField(auto_now_add=True)
    revisado_en = models.DateTimeField(null=True, blank=True)
    revisado_por = models.ForeignKey(
        "auth.User", on_delete=models.SET_NULL,
        null=True, blank=True
    )

    class Meta:
        ordering = ["-creado_en"]
        verbose_name = "Reporte de Horario"
        verbose_name_plural = "Reportes de Horario"

    def __str__(self):
        return f"Reporte {self.pk} — {self.parroquia.nombre} ({self.estado})"


class ScraperJob(models.Model):
    ESTADO_CHOICES = [
        ("corriendo", "Corriendo"),
        ("completado", "Completado"),
        ("error", "Error"),
    ]
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES,
                              default="corriendo")
    origen = models.CharField(
        max_length=20,
        choices=[
            ("manual", "Manual"),
            ("automatico", "Automático"),
        ],
        default="manual"
    )
    total = models.IntegerField(default=0)
    procesados = models.IntegerField(default=0)
    posts_nuevos = models.IntegerField(default=0)
    eventos_nuevos = models.IntegerField(default=0)
    errores = models.IntegerField(default=0)
    parroquia_actual = models.CharField(max_length=255, blank=True)
    iniciado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)
    mensaje_final = models.TextField(blank=True)

    class Meta:
        ordering = ["-iniciado_en"]
        verbose_name = "Scraper Job"

    def __str__(self):
        return f"ScraperJob {self.pk} — {self.estado}"


class Banner(models.Model):
    POSICION_CHOICES = [
        ("resultados", "Entre resultados del buscador"),
        ("detalle", "Página de detalle de parroquia"),
    ]
    titulo = models.CharField(max_length=100)
    imagen = models.ImageField(
        upload_to="banners/",
        null=True, blank=True,
        help_text="Imagen del banner (recomendado: 728x90px)"
    )
    imagen_static = models.CharField(
        max_length=200, blank=True, null=True,
        help_text="Ruta estática ej: iglesias/img/ad_gaudium1.jpeg"
    )
    url_destino = models.URLField(
        max_length=500, blank=True, null=True,
        help_text="URL a la que redirige el banner"
    )
    texto_alternativo = models.CharField(
        max_length=200, blank=True,
        help_text="Texto alternativo para SEO y accesibilidad"
    )
    posicion = models.CharField(
        max_length=20, choices=POSICION_CHOICES,
        default="resultados"
    )
    activo = models.BooleanField(default=True)
    orden = models.IntegerField(default=0)
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["orden", "-creado_en"]
        verbose_name = "Banner publicitario"
        verbose_name_plural = "Banners publicitarios"

    def __str__(self):
        return f"{self.titulo} ({self.posicion})"


class VotoHorario(models.Model):
    TIPO_CHOICES = [('oficial', 'Oficial'), ('propuesto', 'Propuesto')]

    parroquia = models.ForeignKey('Parroquia', on_delete=models.CASCADE, related_name='votos_horario')
    tipo = models.CharField(max_length=10, choices=TIPO_CHOICES, default='oficial')
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    session_key = models.CharField(max_length=40, blank=True)
    valor = models.SmallIntegerField()  # +1 correcto, -1 incorrecto
    fecha = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['parroquia', 'tipo', 'usuario'], condition=models.Q(usuario__isnull=False), name='unique_voto_usuario'),
            models.UniqueConstraint(fields=['parroquia', 'tipo', 'session_key'], condition=models.Q(usuario__isnull=True), name='unique_voto_sesion'),
        ]

    def __str__(self):
        return f"Voto {self.valor:+d} ({self.tipo}) — {self.parroquia}"


class ComentarioParroquia(models.Model):
    ESTADO_MODERACION_CHOICES = [
        ('pendiente', 'Pendiente'),
        ('aprobado', 'Aprobado'),
        ('rechazado', 'Rechazado'),
    ]

    parroquia = models.ForeignKey('Parroquia', on_delete=models.CASCADE, related_name='comentarios')
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='comentarios')
    texto = models.TextField(max_length=500)
    fecha = models.DateTimeField(auto_now_add=True)
    reporte = models.OneToOneField('ReporteHorario', on_delete=models.SET_NULL, null=True, blank=True, related_name='comentario')
    estado_moderacion = models.CharField(
        max_length=20,
        choices=ESTADO_MODERACION_CHOICES,
        default='pendiente',
        db_index=True,
    )
    razon_rechazo = models.CharField(
        max_length=255, blank=True, null=True,
        help_text="Razón del rechazo (filtro local o IA)",
    )
    moderado_por_ia = models.BooleanField(
        default=False,
        help_text="True si la IA ya procesó este comentario",
    )
    oculto = models.BooleanField(default=False)
    apelado = models.BooleanField(
        default=False,
        help_text="El usuario marcó este rechazo como error",
    )
    apelado_en = models.DateTimeField(
        null=True, blank=True,
        help_text="Fecha en que el usuario apeló",
    )

    class Meta:
        ordering = ['-fecha']

    def __str__(self):
        return f"{self.usuario or 'Anónimo'} → {self.parroquia} ({self.fecha:%d/%m/%Y})"


class HorarioPropuestoAgregado(models.Model):
    parroquia = models.ForeignKey(
        'Parroquia', on_delete=models.CASCADE,
        related_name='horarios_propuestos'
    )
    dia_semana = models.IntegerField(
        choices=[(i, d) for i, d in enumerate(
            ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']
        )]
    )
    # JSON: [{"hora": "18:30", "peso": 1.4, "estado": "nuevo"}, ...]
    # estado: "coincide" | "nuevo" | "eliminado"
    horarios_json = models.JSONField(default=list)
    confianza = models.FloatField(default=0.0)  # 0.0 a 1.0
    total_aportes = models.IntegerField(default=0)
    aportes_con_historial = models.IntegerField(default=0)
    ultima_actualizacion = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('parroquia', 'dia_semana')
        ordering = ['dia_semana']
        verbose_name = 'Horario propuesto agregado'
        verbose_name_plural = 'Horarios propuestos agregados'

    def __str__(self):
        dia = ['Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb', 'Dom'][self.dia_semana]
        return f"{self.parroquia} — {dia}"


class SuscripcionAvisoMisa(models.Model):
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='suscripciones_avisos'
    )
    parroquia = models.ForeignKey(
        'Parroquia',
        on_delete=models.CASCADE,
        related_name='suscripciones_avisos'
    )
    dias_semana = models.JSONField(
        default=list,
        help_text='Lista de días [0-6] donde 0=Lunes. Vacío = todos los días.'
    )
    activa = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('usuario', 'parroquia')
        verbose_name = 'Suscripción aviso misa'
        verbose_name_plural = 'Suscripciones avisos misa'

    def __str__(self):
        return f"{self.usuario.email} → {self.parroquia.nombre}"
