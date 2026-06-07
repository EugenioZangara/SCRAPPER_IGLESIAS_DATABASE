"""
Moderación híbrida de comentarios:
  1. Filtro local rápido (lista de palabras)
  2. Si pasa, IA modera en background
"""
import json
import logging
import threading

from .models import ComentarioParroquia

logger = logging.getLogger(__name__)

PALABRAS_BLOQUEADAS = [
    'pelotudo', 'boludo', 'hijo de puta', 'hdp', 'concha', 'puto', 'puta',
    'forro', 'cagón', 'idiota', 'imbécil', 'estúpido', 'tarado', 'mogólico',
    'retrasado', 'garca', 'chanta', 'mierda', 'carajo', 'pijo', 'verga',
    'negro de mierda', 'villero', 'sudaca', 'paragua', 'bolita',
    'te voy a matar', 'te voy a cagar', 'muerte a',
    'click aquí', 'ganá dinero', 'gana dinero', 'oferta imperdible',
]

PROMPT_MODERACION = """Eres un moderador de contenido para Parroguía, una web de horarios de misas en Argentina.
Tu tarea es evaluar si el siguiente comentario de usuario es apropiado para publicar.

Rechazá el comentario si contiene:
- Insultos, agresiones o lenguaje violento
- Discriminación racial, religiosa, de género o sexual
- Spam, publicidad o contenido irrelevante
- Contenido sexual o inapropiado
- Amenazas o incitación al odio
- Información personal de terceros

Aprobá el comentario si es:
- Una experiencia personal con la parroquia
- Una corrección o consulta sobre horarios
- Un comentario neutro o positivo sobre la comunidad
- Crítica constructiva y respetuosa

Respondé SOLO con un JSON válido, sin texto adicional:
{"decision": "aprobado", "razon": ""}
o
{"decision": "rechazado", "razon": "breve explicación en español"}

Comentario a evaluar:
"""


def filtro_local(texto):
    texto_lower = texto.lower()
    for palabra in PALABRAS_BLOQUEADAS:
        if palabra in texto_lower:
            return True, "Contenido inapropiado detectado"
    return False, ''


def moderar_con_ia(comentario_pk):
    try:
        comentario = ComentarioParroquia.objects.get(pk=comentario_pk)
    except ComentarioParroquia.DoesNotExist:
        return

    texto = comentario.texto
    decision = None
    razon = ''

    # 1. Gemini
    try:
        import os
        from google import genai
        from google.genai import types
        client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
        response = client.models.generate_content(
            model='gemini-2.0-flash',
            contents=PROMPT_MODERACION + texto,
            config=types.GenerateContentConfig(
                max_output_tokens=150,
                temperature=0.1,
            )
        )
        raw = response.text.strip().replace('```json', '').replace('```', '').strip()
        data = json.loads(raw)
        decision = data.get('decision')
        razon = data.get('razon', '')
        logger.info(f"[moderacion] Gemini → comentario {comentario_pk}: {decision}")
    except Exception as e:
        logger.warning(f"[moderacion] Gemini falló: {e}")

    # 2. Mistral
    if not decision:
        try:
            import os
            import requests
            resp = requests.post(
                'https://api.mistral.ai/v1/chat/completions',
                headers={'Authorization': f'Bearer {os.environ.get("MISTRAL_API_KEY")}',
                         'Content-Type': 'application/json'},
                json={
                    'model': 'mistral-small-latest',
                    'messages': [{'role': 'user', 'content': PROMPT_MODERACION + texto}],
                    'max_tokens': 100,
                    'temperature': 0.1,
                },
                timeout=15,
            )
            data = json.loads(resp.json()['choices'][0]['message']['content'].strip())
            decision = data.get('decision')
            razon = data.get('razon', '')
            logger.info(f"[moderacion] Mistral → comentario {comentario_pk}: {decision}")
        except Exception as e:
            logger.warning(f"[moderacion] Mistral falló: {e}")

    # 3. Groq
    if not decision:
        try:
            import os
            import requests
            resp = requests.post(
                'https://api.groq.com/openai/v1/chat/completions',
                headers={'Authorization': f'Bearer {os.environ.get("GROQ_API_KEY")}',
                         'Content-Type': 'application/json'},
                json={
                    'model': 'llama-3.3-70b-versatile',
                    'messages': [{'role': 'user', 'content': PROMPT_MODERACION + texto}],
                    'max_tokens': 100,
                    'temperature': 0.1,
                },
                timeout=15,
            )
            raw = resp.json()['choices'][0]['message']['content'].strip()
            raw = raw.replace('```json', '').replace('```', '').strip()
            data = json.loads(raw)
            decision = data.get('decision')
            razon = data.get('razon', '')
            logger.info(f"[moderacion] Groq → comentario {comentario_pk}: {decision}")
        except Exception as e:
            logger.warning(f"[moderacion] Groq falló: {e}")

    # 4. Fallback: aprobar por defecto
    if not decision:
        decision = 'aprobado'
        razon = ''
        logger.warning(f"[moderacion] Todos los fallbacks fallaron → aprobando por defecto comentario {comentario_pk}")

    if decision == 'rechazado':
        ComentarioParroquia.objects.filter(pk=comentario_pk).update(
            estado_moderacion='rechazado',
            razon_rechazo=razon,
            moderado_por_ia=True,
            oculto=True,
        )
        logger.info(f"[moderacion] Comentario {comentario_pk} RECHAZADO por IA: {razon}")
    else:
        ComentarioParroquia.objects.filter(pk=comentario_pk).update(
            estado_moderacion='aprobado',
            moderado_por_ia=True,
            oculto=False,
        )
        logger.info(f"[moderacion] Comentario {comentario_pk} APROBADO por IA")


def moderar_comentario(comentario):
    """
    Punto de entrada. Llamar después de guardar un ComentarioParroquia.
    Filtro local inmediato → si pasa, IA en background thread.
    """
    bloqueado, razon = filtro_local(comentario.texto)
    if bloqueado:
        ComentarioParroquia.objects.filter(pk=comentario.pk).update(
            estado_moderacion='rechazado',
            razon_rechazo=razon,
            moderado_por_ia=False,
            oculto=True,
        )
        logger.info(f"[moderacion] Comentario {comentario.pk} bloqueado por filtro local: {razon}")
        return

    threading.Thread(target=moderar_con_ia, args=(comentario.pk,), daemon=True).start()
    logger.info(f"[moderacion] Comentario {comentario.pk} enviado a moderación IA (background)")
