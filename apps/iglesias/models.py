from django.db import models


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

    # Organización Eclesiástica
    vicaria = models.CharField(max_length=100, blank=True, null=True)
    decanato = models.CharField(max_length=100, blank=True, null=True)
    barrio = models.CharField(max_length=100, blank=True, null=True)
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

class Evento(models.Model):
    TIPO_CHOICES = [
        ("misa", "Misa"),
        ("retiro", "Retiro"),
        ("charla", "Charla"),
        ("bautismo", "Bautismo"),
        ("confirmacion", "Confirmación"),
        ("peregrinacion", "Peregrinación"),
        ("juventud", "Juventud"),
        ("otro", "Otro"),
    ]

    parroquia = models.ForeignKey(
        "Parroquia", on_delete=models.CASCADE, related_name="eventos"
    )
    post = models.OneToOneField(
        "PostParroquia", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="evento"
    )

    titulo = models.CharField(max_length=255)
    tipo = models.CharField(max_length=50, choices=TIPO_CHOICES, default="otro")
    fecha = models.DateField(null=True, blank=True)
    hora = models.TimeField(null=True, blank=True)
    lugar = models.CharField(max_length=255, blank=True, null=True)
    descripcion = models.TextField(blank=True, null=True)
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
    parroquia = models.ForeignKey(
        "Parroquia", on_delete=models.CASCADE, related_name="horarios_misa"
    )
    dias = models.CharField(max_length=100)
    horarios = models.CharField(max_length=100)
    nota = models.TextField(blank=True, null=True)

    class Meta:
        verbose_name = "Horario de Misa"
        verbose_name_plural = "Horarios de Misa"
        ordering = ["id"]

    def __str__(self):
        return f"{self.dias}: {self.horarios} — {self.parroquia.nombre}"
