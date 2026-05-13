import httpx
import json
import os
import base64


def cargar_env():
    env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ.setdefault(key.strip(), value.strip())


def descargar_imagen(url: str) -> bytes:
    """Descarga la imagen en memoria, sin guardar en disco."""
    response = httpx.get(url, timeout=15, follow_redirects=True)
    response.raise_for_status()
    return response.content


PROMPT_FLYER = """Analizá esta imagen y su pie de foto que provienen de la red social de una parroquia católica.

Tu objetivo es detectar ÚNICAMENTE publicaciones que inviten a la comunidad a participar 
de un evento FUTURO o PRÓXIMO.

CLASIFICAR COMO EVENTO (es_evento: true):
- Flyers o anuncios con convocatoria explícita: misa especial, retiro, charla, peregrinación,
  bautismo, confirmación, actividad juvenil, talleres, novenas, procesiones
- Celebraciones abiertas a la comunidad con fecha/hora (ej: cumpleaños del párroco 
  con misa o festejo abierto)
- Frases como: "los esperamos", "te invitamos", "participá", "unite", "acompañanos",
  "no te lo pierdas", "este sábado", "próximo domingo"

NO CLASIFICAR COMO EVENTO (es_evento: false):
- Saludos o felicitaciones sin convocatoria (ej: "Feliz cumpleaños Padre X" sin invitación)
- Fotos o crónicas de eventos ya realizados ("gracias por venir", "fue una hermosa jornada")
- Contenido devocional, reflexiones, frases bíblicas o religiosas sin convocatoria
- Avisos institucionales sin actividad específica
- Transmisiones en vivo ya finalizadas

{caption_line}

Respondé ÚNICAMENTE con un JSON válido, sin texto adicional, sin markdown, sin backticks.
El JSON debe tener exactamente estos campos:
{{
  "es_evento": true si es invitación a participar en evento futuro, false en cualquier otro caso,
  "es_pasado": true si el contenido muestra un evento ya realizado,
  "titulo": "título del evento o null",
  "fecha": "DD/MM/YYYY o null",
  "hora": "HH:MM o null",
  "lugar": "lugar del evento o null",
  "descripcion": "descripción breve en 1-2 oraciones o null",
  "tipo_evento": "misa/retiro/charla/bautismo/confirmacion/peregrinacion/juventud/otro o null"
}}"""
def analizar_con_openrouter(imagen_bytes: bytes, caption: str = "") -> dict:
    """Analiza la imagen usando OpenRouter con modelo de visión gratuito."""
    from openai import OpenAI

    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise ValueError("OPENROUTER_API_KEY no está definida en el .env")

    client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=api_key,
    )

    imagen_b64 = base64.b64encode(imagen_bytes).decode("utf-8")
    caption_line = f"El pie de foto dice: {caption}" if caption else ""
    prompt = PROMPT_FLYER.format(caption_line=caption_line)

    response = client.chat.completions.create(
       model="nvidia/nemotron-nano-12b-v2-vl:free",
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{imagen_b64}"
                        }
                    },
                    {
                        "type": "text",
                        "text": prompt
                    }
                ]
            }
        ],
        max_tokens=500,
    )

    texto = response.choices[0].message.content.strip()
    texto = texto.replace("```json", "").replace("```", "").strip()
    return json.loads(texto)


def analizar_con_gemini(imagen_bytes: bytes, caption: str = "") -> dict:
    """Analiza la imagen usando Gemini."""
    from google import genai
    from google.genai import types

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY no está definida en el .env")

    client = genai.Client(api_key=api_key)
    caption_line = f"El pie de foto dice: {caption}" if caption else ""
    prompt = PROMPT_FLYER.format(caption_line=caption_line)

    response = client.models.generate_content(
       model="gemini-3-flash-preview",
        contents=[
            types.Part.from_bytes(data=imagen_bytes, mime_type="image/jpeg"),
            types.Part.from_text(text=prompt),
        ]
    )
    texto = response.text.strip()
    texto = texto.replace("```json", "").replace("```", "").strip()
    return json.loads(texto)


def analizar_flyer(imagen_bytes: bytes, caption: str = "") -> dict:
    try:
        return analizar_con_gemini(imagen_bytes, caption)
    except Exception as e:
        error_str = str(e)
        if any(code in error_str for code in ["429", "503", "RESOURCE_EXHAUSTED", "UNAVAILABLE", "quota"]):
            print("  Gemini no disponible, usando OpenRouter...")
            try:
                return analizar_con_openrouter(imagen_bytes, caption)
            except json.JSONDecodeError as e2:
                print(f"  ERROR: OpenRouter no devolvió JSON válido: {e2}")
                return {"es_evento": None, "error": "json_invalido"}
            except Exception as e2:
                print(f"  ERROR inesperado con OpenRouter: {e2}")
                return {"es_evento": None, "error": str(e2)}
        print(f"  ERROR inesperado con Gemini: {e}")
        return {"es_evento": None, "error": str(e)}

def procesar_post(post: dict) -> dict:
    """
    Recibe un dict de post (con imagen_url y caption) y devuelve
    el resultado del análisis.
    """
    cargar_env()
    print(f"  Procesando: {post['post_id']}...")

    try:
        imagen_bytes = descargar_imagen(post["imagen_url"])
    except Exception as e:
        print(f"  ERROR al descargar imagen: {e}")
        return {"es_evento": None, "error": "descarga_fallida"}

    resultado = analizar_flyer(imagen_bytes, post.get("caption", ""))
    return resultado