import os
import json
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime


SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
]


def get_sheets_client():
    """
    Retorna un cliente autenticado de gspread.
    Soporta credenciales desde archivo (local) o
    variable de entorno GOOGLE_CREDENTIALS_JSON (producción).
    """
    creds_json = os.environ.get("GOOGLE_CREDENTIALS_JSON")
    creds_file = os.environ.get("GOOGLE_CREDENTIALS_FILE", "google_credentials.json")

    if creds_json:
        creds_dict = json.loads(creds_json)
        creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
    elif os.path.exists(creds_file):
        creds = Credentials.from_service_account_file(creds_file, scopes=SCOPES)
    else:
        raise ValueError(
            "No se encontraron credenciales de Google. "
            "Configurar GOOGLE_CREDENTIALS_JSON o GOOGLE_CREDENTIALS_FILE."
        )

    return gspread.authorize(creds)


def formatear_fecha(dt):
    """Formatea datetime o date a string para el Sheet."""
    if not dt:
        return ""
    if hasattr(dt, "strftime"):
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    return str(dt)


def formatear_edad(edad_desde, edad_hasta):
    """Formatea rango de edad para el Sheet."""
    if edad_desde == 0 and edad_hasta == 100:
        return "Todo público"
    desde = edad_desde if edad_desde is not None else 0
    hasta = edad_hasta if edad_hasta is not None else 100
    return f"{desde} a {hasta}"


def formatear_audiencia(audiencia):
    """Formatea audiencia para el Sheet con punto y coma."""
    if not audiencia:
        return ""
    mapping = {
        "ambos": "Hombres;Mujeres",
        "hombres": "Hombres",
        "mujeres": "Mujeres",
    }
    return mapping.get(audiencia, audiencia)


def exportar_evento_a_sheets(evento) -> bool:
    """
    Exporta un evento aprobado al Google Sheet.
    Retorna True si fue exitoso, False si falló.
    """
    sheets_id = os.environ.get("GOOGLE_SHEETS_ID")
    if not sheets_id:
        raise ValueError("GOOGLE_SHEETS_ID no está configurado.")

    try:
        client = get_sheets_client()
        sheet = client.open_by_key(sheets_id).sheet1

        fecha_inicio = ""
        if evento.fecha:
            fecha_inicio = evento.fecha.strftime("%Y-%m-%d")
            if evento.hora:
                fecha_inicio += f" {evento.hora.strftime('%H:%M:%S')}"
            else:
                fecha_inicio += " 00:00:00"

        fila = [
            evento.titulo or "",
            evento.tipo.nombre if evento.tipo else "",
            evento.url_externa or "",
            evento.categoria.nombre if evento.categoria else "",
            evento.descripcion or "",
            fecha_inicio,
            formatear_fecha(evento.fecha_fin),
            evento.ubicacion_lugar or evento.lugar or "",
            evento.ubicacion_direccion or "",
            evento.ubicacion_ciudad or "Buenos Aires",
            evento.ubicacion_cp or "",
            evento.ubicacion_provincia or "Buenos Aires",
            "Borrador",
            formatear_audiencia(evento.audiencia),
            formatear_edad(evento.edad_desde, evento.edad_hasta),
            "Sí" if evento.gratuito else "No",
            str(evento.capacidad) if evento.capacidad else "",
        ]

        sheet.append_row(fila, value_input_option="USER_ENTERED")
        return True

    except Exception as e:
        print(f"ERROR exportando a Google Sheets: {e}")
        return False
