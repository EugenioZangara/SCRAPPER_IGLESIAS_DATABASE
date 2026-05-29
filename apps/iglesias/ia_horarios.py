import os
import json


def _llamar_gemini_directo(prompt: str) -> str:
    from google import genai
    client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
    response = client.models.generate_content(
        model="gemini-2.0-flash",
        contents=prompt,
    )
    return response.text


def _llamar_mistral(prompt: str) -> str:
    import httpx
    response = httpx.post(
        "https://api.mistral.ai/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {os.environ.get('MISTRAL_API_KEY')}",
            "Content-Type": "application/json",
        },
        json={
            "model": "mistral-small-latest",
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 1000,
        },
        timeout=30,
    )
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"]


def _llamar_openrouter(prompt: str, modelo: str) -> str:
    from openai import OpenAI
    client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=os.environ.get("OPENROUTER_API_KEY"),
    )
    response = client.chat.completions.create(
        model=modelo,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=1000,
    )
    return response.choices[0].message.content


def _parsear_respuesta(text: str) -> dict:
    text = text.strip()
    if "```" in text:
        parts = text.split("```")
        for part in parts:
            if part.strip().startswith("json"):
                text = part.strip()[4:]
                break
            elif part.strip().startswith("{"):
                text = part.strip()
                break
    return json.loads(text.strip())


def _cargar_env():
    env_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__)
        ))),
        ".env",
    )
    if os.path.exists(env_path):
        with open(env_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    os.environ[key.strip()] = value.strip()


def procesar_reporte_horario(parroquia, texto_usuario: str) -> dict:
    _cargar_env()

    DIAS = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]

    horarios_dict = {}
    for h in parroquia.horarios_misa.all():
        horarios_dict[h.dia_semana] = h.horarios

    tabla_actual = "\n".join([
        f"  {DIAS[i]}: {horarios_dict.get(i, 'sin misa')}"
        for i in range(7)
    ])

    ejemplo = '{"cambios": [{"dia": 0, "horario": "19:00"}, {"dia": 5, "horario": "19:00"}], "resumen_cambios": "Se agregaron misas de lunes a sábado a las 19:00"}'

    prompt = (
        f"Sos un asistente que actualiza horarios de misas.\n\n"
        f"HORARIOS ACTUALES de {parroquia.nombre}:\n"
        f"{tabla_actual}\n\n"
        f"REPORTE DEL USUARIO:\n"
        f'"{texto_usuario}"\n\n'
        f"Tu tarea:\n"
        f"Devolvé ÚNICAMENTE los días que el usuario mencionó "
        f"explícitamente con sus nuevos horarios.\n"
        f"NO incluyas días que el usuario no mencionó.\n"
        f"NO elimines días que no fueron mencionados.\n\n"
        f"EJEMPLOS:\n"
        f"- Usuario dice 'los domingos a las 10' → solo devolvés dia:6\n"
        f"- Usuario dice 'lunes a viernes 19hs' → devolvés dias 0,1,2,3,4\n"
        f"- Usuario dice 'sábados ya no hay misa' → devolvés dia:5 horario:''\n\n"
        f"dia: 0=Lunes, 1=Martes, 2=Miércoles, 3=Jueves, "
        f"4=Viernes, 5=Sábado, 6=Domingo\n"
        f"Si un día deja de tener misa, horario debe ser '' (vacío).\n\n"
        f"Respondé SOLO con JSON válido sin backticks:\n"
        + ejemplo
    )

    MODELOS_FALLBACK = [
        ("gemini_directo", None),
        ("mistral", None),
        ("openrouter", "meta-llama/llama-3.3-70b-instruct:free"),
        ("openrouter", "deepseek/deepseek-chat-v3-0324:free"),
    ]

    for proveedor, modelo in MODELOS_FALLBACK:
        try:
            if proveedor == "gemini_directo":
                text = _llamar_gemini_directo(prompt)
                print(f"  ia_horarios: usando Gemini directo")
            elif proveedor == "mistral":
                text = _llamar_mistral(prompt)
                print(f"  ia_horarios: usando Mistral")
            else:
                text = _llamar_openrouter(prompt, modelo)
                print(f"  ia_horarios: usando OpenRouter {modelo}")

            result = _parsear_respuesta(text)
            return {
                "propuesta_ia": result.get("cambios", []),
                "resumen_cambios": result.get("resumen_cambios", ""),
            }
        except Exception as e:
            print(f"  ia_horarios ERROR ({proveedor} {modelo}): {e}")
            continue

    return {
        "propuesta_ia": [],
        "resumen_cambios": "No se pudo procesar con ningún modelo disponible.",
    }
