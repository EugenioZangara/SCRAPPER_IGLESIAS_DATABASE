from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from allauth.socialaccount.signals import social_account_added


@receiver(post_save, sender=User)
def crear_perfil_usuario(sender, instance, created, **kwargs):
    if created:
        from .models import PerfilUsuario
        PerfilUsuario.objects.get_or_create(
            user=instance,
            defaults={"proveedor": "email"},
        )


@receiver(social_account_added)
def actualizar_proveedor_social(sender, request, sociallogin, **kwargs):
    try:
        perfil = sociallogin.user.perfil
        perfil.proveedor = sociallogin.account.provider
        perfil.save(update_fields=["proveedor"])
    except Exception:
        pass


def actualizar_score_aprobacion(reporte):
    """Llamar cuando un reporte es aprobado."""
    if not reporte.usuario:
        return
    try:
        perfil = reporte.usuario.perfil
        perfil.reportes_aprobados += 1
        perfil.score += 10
        if perfil.reportes_aprobados % 5 == 0:
            perfil.score += 20
        perfil.save()
    except Exception:
        pass


def actualizar_score_rechazo(reporte):
    """Llamar cuando un reporte es rechazado."""
    if not reporte.usuario:
        return
    try:
        perfil = reporte.usuario.perfil
        perfil.reportes_rechazados += 1
        perfil.score = max(0, perfil.score - 2)
        perfil.save()
    except Exception:
        pass


def actualizar_score_reporte_enviado(reporte):
    """Llamar cuando se crea un reporte."""
    if not reporte.usuario:
        return
    try:
        perfil = reporte.usuario.perfil
        perfil.reportes_enviados += 1
        if perfil.reportes_enviados == 1:
            perfil.score += 5
        perfil.save()
    except Exception:
        pass


def actualizar_score_validacion(validacion):
    """Llamar cuando se crea una validación."""
    if not validacion.usuario:
        return
    try:
        perfil = validacion.usuario.perfil
        perfil.validaciones_enviadas += 1
        perfil.score += 1
        perfil.save()
    except Exception:
        pass


@receiver(post_save, sender='iglesias.ReporteHorario')
def actualizar_propuestos_on_reporte(sender, instance, **kwargs):
    import logging
    import threading
    logging.getLogger(__name__).info(
        f"[signal] ReporteHorario {instance.pk} saved — fuente={instance.fuente} parroquia={instance.parroquia_id}"
    )
    if instance.fuente == 'usuario' and instance.parroquia_id:
        def _reconstruir():
            try:
                from .ia_propuestas import reconstruir_propuestos
                reconstruir_propuestos(instance.parroquia)
            except Exception as e:
                import logging
                logging.getLogger(__name__).error(
                    f"[signal] Error reconstruyendo propuestos: {e}"
                )
        t = threading.Thread(target=_reconstruir, daemon=True)
        t.start()
