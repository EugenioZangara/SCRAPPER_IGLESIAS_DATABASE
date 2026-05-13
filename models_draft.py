from django.db import models
from apps.iglesias.models import Parroquia

class PostParroquia(models.Model):
    RED_SOCIAL_CHOICES = [
        ('facebook', 'Facebook'),
        ('instagram', 'Instagram'),
    ]

    parroquia = models.ForeignKey(Parroquia, on_delete=models.CASCADE, related_name='posts_redes')
    post_id = models.CharField(max_length=100, unique=True, help_text="ID nativo de Meta")
    red_social = models.CharField(max_length=20, choices=RED_SOCIAL_CHOICES)
    imagen_url = models.URLField(max_length=1000, help_text="Puede caducar en Instagram")
    procesado = models.BooleanField(default=False)
    es_evento = models.BooleanField(null=True, help_text="null significa sin procesar")
    creado_en = models.DateTimeField(auto_now_add=True)
    raw_data = models.JSONField(blank=True, null=True, help_text="Respuesta cruda de la API")

    class Meta:
        ordering = ['-creado_en']
        verbose_name = "Post de Parroquia"
        verbose_name_plural = "Posts de Parroquias"

    def __str__(self):
        return f"{self.red_social.capitalize()} post ({self.post_id}) - {self.parroquia.nombre}"
