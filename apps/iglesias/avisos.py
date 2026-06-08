import logging
import resend
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from django.conf import settings

from .models import SuscripcionAvisoMisa, HorarioMisa

logger = logging.getLogger(__name__)

ARGENTINA_TZ = ZoneInfo('America/Argentina/Buenos_Aires')

DIAS_NOMBRES = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']


def enviar_avisos_misa():
    """
    Busca misas que ocurren en aproximadamente 1 hora desde ahora
    y envía avisos por email a los suscriptores activos.
    Retorna dict con estadísticas.
    """
    resend.api_key = settings.RESEND_API_KEY
    if not resend.api_key:
        logger.error("RESEND_API_KEY no configurada")
        return {'enviados': 0, 'errores': 0, 'error': 'Sin API key'}

    ahora = datetime.now(ARGENTINA_TZ)
    hora_objetivo = ahora + timedelta(hours=1)
    dia_semana_hoy = ahora.weekday()  # 0=Lunes, 6=Domingo

    horarios_hoy = HorarioMisa.objects.filter(
        dia_semana=dia_semana_hoy
    ).select_related('parroquia')

    enviados = 0
    errores = 0
    ya_notificados = set()  # evitar duplicados usuario+parroquia

    for horario in horarios_hoy:
        horas_misa = [h.strip() for h in horario.horarios.replace('·', '|').split('|')]

        for hora_misa in horas_misa:
            try:
                partes = hora_misa.strip().split(':')
                if len(partes) != 2:
                    continue
                h, m = int(partes[0]), int(partes[1])
                hora_misa_dt = ahora.replace(hour=h, minute=m, second=0, microsecond=0)

                diff = abs((hora_misa_dt - hora_objetivo).total_seconds())
                if diff > 600:
                    continue

                suscripciones = SuscripcionAvisoMisa.objects.filter(
                    parroquia=horario.parroquia,
                    activa=True
                ).select_related('usuario')

                for suscripcion in suscripciones:
                    if suscripcion.dias_semana and dia_semana_hoy not in suscripcion.dias_semana:
                        continue

                    clave = f"{suscripcion.usuario.id}_{horario.parroquia.id}"
                    if clave in ya_notificados:
                        continue
                    ya_notificados.add(clave)

                    try:
                        _enviar_email_aviso(
                            suscripcion.usuario,
                            horario.parroquia,
                            hora_misa.strip(),
                            ahora
                        )
                        enviados += 1
                    except Exception as e:
                        logger.error(f"Error enviando aviso a {suscripcion.usuario.email}: {e}")
                        errores += 1

            except (ValueError, AttributeError) as e:
                logger.warning(f"Error parseando horario '{hora_misa}': {e}")
                continue

    logger.info(f"Avisos enviados: {enviados}, errores: {errores}")
    return {'enviados': enviados, 'errores': errores}


def _enviar_email_aviso(usuario, parroquia, hora_misa, ahora):
    """Envía el email de aviso a un usuario para una parroquia y hora específica."""
    nombre_usuario = usuario.first_name or usuario.email.split('@')[0]
    dia_nombre = DIAS_NOMBRES[ahora.weekday()]

    site_url = settings.SITE_URL
    url_parroquia = f"{site_url}/publico/{parroquia.pk}/"
    url_perfil = f"{site_url}/publico/perfil/"

    direccion = parroquia.direccion or ''
    if parroquia.barrio:
        direccion += f", {parroquia.barrio}"
    if parroquia.ciudad:
        direccion += f", {parroquia.ciudad}"

    html_content = f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Aviso de Misa — {parroquia.nombre}</title>
</head>
<body style="margin:0;padding:0;background-color:#faf9f5;font-family:Georgia,serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background-color:#faf9f5;padding:32px 16px;">
    <tr>
      <td align="center">
        <table width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%;background:#ffffff;border-radius:12px;overflow:hidden;box-shadow:0 2px 12px rgba(0,0,0,0.08);">
          <tr>
            <td style="background-color:#14315E;padding:28px 32px;text-align:center;">
              <h1 style="margin:0;color:#F2A007;font-size:24px;font-family:Georgia,serif;letter-spacing:1px;">
                🔔 Aviso de Misa
              </h1>
              <p style="margin:8px 0 0;color:#ffffff;font-size:14px;opacity:0.85;">
                Parroguía — Tu guía de parroquias
              </p>
            </td>
          </tr>
          <tr>
            <td style="padding:32px;">
              <p style="margin:0 0 16px;color:#333;font-size:16px;">
                Hola {nombre_usuario},
              </p>
              <p style="margin:0 0 24px;color:#555;font-size:15px;line-height:1.6;">
                En <strong>1 hora</strong> comienza la misa en tu parroquia favorita:
              </p>
              <table width="100%" cellpadding="0" cellspacing="0" style="background:#f0f4ff;border-left:4px solid #14315E;border-radius:8px;margin-bottom:24px;">
                <tr>
                  <td style="padding:20px 24px;">
                    <h2 style="margin:0 0 8px;color:#14315E;font-size:18px;">{parroquia.nombre}</h2>
                    <p style="margin:0 0 12px;color:#666;font-size:14px;">📍 {direccion}</p>
                    <p style="margin:0;font-size:28px;font-weight:bold;color:#F2A007;">
                      🕐 {hora_misa} hs
                    </p>
                    <p style="margin:4px 0 0;color:#888;font-size:13px;">{dia_nombre}</p>
                  </td>
                </tr>
              </table>
              <table width="100%" cellpadding="0" cellspacing="0">
                <tr>
                  <td align="center" style="padding-bottom:24px;">
                    <a href="{url_parroquia}"
                       style="display:inline-block;background-color:#F2A007;color:#14315E;text-decoration:none;font-weight:bold;font-size:15px;padding:14px 32px;border-radius:8px;font-family:Arial,sans-serif;">
                      Ver parroquia →
                    </a>
                  </td>
                </tr>
              </table>
              <hr style="border:none;border-top:1px solid #eee;margin:8px 0 24px;">
              <p style="margin:0;color:#999;font-size:12px;text-align:center;line-height:1.6;">
                Recibís este aviso porque activaste las notificaciones en
                <a href="{url_perfil}" style="color:#14315E;">tu perfil de Parroguía</a>.<br>
                Para desactivarlos, ingresá a tu perfil y desactivá los avisos.
              </p>
            </td>
          </tr>
          <tr>
            <td style="background-color:#14315E;padding:16px 32px;text-align:center;">
              <p style="margin:0;color:#ffffff;font-size:12px;opacity:0.7;">
                © 2025 Parroguía ·
                <a href="{site_url}/privacidad/" style="color:#F2A007;">Privacidad</a> ·
                <a href="{site_url}/terminos/" style="color:#F2A007;">Términos</a>
              </p>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""

    resend.Emails.send({
        "from": "Parroguía <noreply@parroguia.com>",
        "to": [usuario.email],
        "subject": f"🔔 Misa en {parroquia.nombre} en 1 hora — {hora_misa} hs",
        "html": html_content,
    })
