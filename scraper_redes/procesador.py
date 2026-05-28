import httpx
import json
import os
import base64


def cargar_env():
    env_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"
    )
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    os.environ.setdefault(key.strip(), value.strip())


def descargar_imagen(url: str) -> bytes:
    response = httpx.get(url, timeout=15, follow_redirects=True)
    response.raise_for_status()
    return response.content


PROMPT_FLYER = """Analizá esta imagen y su pie de foto que provienen de la red social de una parroquia católica.

Tenés DOS tareas:

TAREA 1 — Detectar si es un EVENTO
Clasificá si la publicación invita a participar de un evento FUTURO o PRÓXIMO.

CLASIFICAR COMO EVENTO (es_evento: true):
- Flyers o anuncios con convocatoria explícita: misa especial, retiro, charla, peregrinación,
  bautismo, confirmación, actividad juvenil, talleres, novenas, procesiones
- Celebraciones abiertas a la comunidad con fecha/hora
- Frases como: "los esperamos", "te invitamos", "participá", "unite", "acompañanos",
  "no te lo pierdas", "este sábado", "próximo domingo"

NO CLASIFICAR COMO EVENTO (es_evento: false):
- Saludos o felicitaciones sin convocatoria
- Fotos o crónicas de eventos ya realizados
- Contenido devocional, reflexiones, frases bíblicas sin convocatoria
- Avisos institucionales sin actividad específica
- Transmisiones en vivo ya finalizadas

TAREA 2 — Detectar si hay HORARIOS DE MISA SEMANALES
Detectá si la imagen o el pie de foto muestran el horario semanal regular de misas.

CLASIFICAR COMO HORARIOS (tiene_horarios: true) SOLO SI:
- Se ve un cuadro, tabla o lista con días y horarios de misa semanales regulares
- El texto indica claramente los días y horas de celebración semanal
- Ej: "Misas: Lunes 19hs, Miércoles 9hs, Domingo 10hs y 19hs"

NO CLASIFICAR COMO HORARIOS (tiene_horarios: false) SI:
- Solo hay una misa especial o fecha puntual (eso es evento, no horario regular)
- No hay días o horas específicas visibles
- Es solo el anuncio de un evento único

Si tiene_horarios es true, extraé los horarios en horarios_detectados:
- dia: número entero 0=Lunes, 1=Martes, 2=Miércoles, 3=Jueves, 4=Viernes, 5=Sábado, 6=Domingo
- horario: string con los horarios del día separados por " · " (ej: "9:00 · 19:00")
- Omití los días sin misa

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
  "tipo_evento": "misa/retiro/charla/bautismo/confirmacion/peregrinacion/juventud/otro o null",
  "tiene_horarios": true si hay horario semanal regular de misas visible, false en cualquier otro caso,
  "horarios_detectados": lista de objetos con dia (int 0-6) y horario (string) si tiene_horarios es true, si no lista vacía []
}}"""


def analizar_con_gemini(imagen_bytes: bytes, caption: str = "") -> dict:
    from google import genai
    from google.genai import types

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY no configurada")

    client = genai.Client(api_key=api_key)
    caption_line = f"El pie de foto dice: {caption}" if caption else ""
    prompt = PROMPT_FLYER.format(caption_line=caption_line)

    response = client.models.generate_content(
        model="gemini-2.0-flash",
        contents=[
            types.Part.from_bytes(data=imagen_bytes, mime_type="image/jpeg"),
            types.Part.from_text(text=prompt),
        ],
    )
    texto = response.text.strip().replace("```json", "").replace("```", "").strip()
    return json.loads(texto)


def analizar_con_openrouter(
    imagen_bytes: bytes,
    caption: str = "",
    modelo: str = "meta-llama/llama-4-maverick:free",
) -> dict:
    from openai import OpenAI

    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise ValueError("OPENROUTER_API_KEY no configurada")

    client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=api_key,
    )

    imagen_b64 = base64.b64encode(imagen_bytes).decode("utf-8")
    caption_line = f"El pie de foto dice: {caption}" if caption else ""
    prompt = PROMPT_FLYER.format(caption_line=caption_line)

    response = client.chat.completions.create(
        model=modelo,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{imagen_b64}"},
                    },
                    {"type": "text", "text": prompt},
                ],
            }
        ],
        max_tokens=500,
    )

    texto = response.choices[0].message.content.strip()
    texto = texto.replace("```json", "").replace("```", "").strip()
    return json.loads(texto)


def analizar_flyer(imagen_bytes: bytes, caption: str = "") -> dict:
    """
    Fallback de tres niveles — todos gratuitos:
    1. Gemini 2.0 Flash directo (~1000 req/día)
    2. Llama 4 Maverick via OpenRouter (multimodal, gratuito)
    3. Nvidia Nemotron via OpenRouter (gratuito)
    """
    FALLBACKS = [
        ("gemini", None),
        ("openrouter", "meta-llama/llama-4-maverick:free"),
        ("openrouter", "nvidia/nemotron-nano-12b-v2-vl:free"),
    ]

    for proveedor, modelo in FALLBACKS:
        try:
            if proveedor == "gemini":
                print("  Usando Gemini 2.0 Flash...")
                return analizar_con_gemini(imagen_bytes, caption)
            else:
                print(f"  Usando OpenRouter {modelo}...")
                return analizar_con_openrouter(imagen_bytes, caption, modelo)
        except json.JSONDecodeError as e:
            print(f"  ERROR JSON ({proveedor} {modelo}): {e}")
            continue
        except Exception as e:
            print(f"  ERROR ({proveedor} {modelo}): {str(e)[:120]}")
            continue

    print("  Todos los modelos fallaron.")
    return {"es_evento": None, "error": "todos_los_modelos_fallaron"}


def procesar_post(post: dict) -> dict:
    cargar_env()
    print(f"  Procesando: {post['post_id']}...")

    try:
        imagen_bytes = descargar_imagen(post["imagen_url"])
    except Exception as e:
        print(f"  ERROR al descargar imagen: {e}")
        return {"es_evento": None, "error": "descarga_fallida"}

    return analizar_flyer(imagen_bytes, post.get("caption", ""))
