# CLAUDE.md — Scrapper Iglesias Database

## Descripción del proyecto

Sistema Django para centralizar, gestionar y enriquecer información sobre parroquias
católicas de Buenos Aires. Incluye scraping de datos oficiales, detección de redes
sociales, scraping de posts de Instagram, análisis de imágenes con IA para detectar
eventos parroquiales, y un panel de administración web.

El objetivo final es promocionar eventos parroquiales obtenidos automáticamente
desde las redes sociales de las parroquias, con validación manual antes de publicar.

---

## Stack tecnológico

- **Backend**: Django 6.x, Python 3.13
- **Base de datos**: PostgreSQL (local y Render)
- **Frontend**: HTML/CSS vanilla + HTMX 1.9.12
- **Scraping Instagram**: `instaloader` con sesión por cookies
- **IA para análisis de imágenes**: Gemini (principal) → OpenRouter (fallback)
- **HTTP client**: `httpx`
- **Entorno virtual**: `entorno_SID`

---

## Estructura del proyecto

```
scrapper_iglesias_database/
│
├── core/                          ← configuración Django
│   ├── settings.py
│   └── urls.py
│
├── apps/
│   └── iglesias/                  ← app principal
│       ├── models.py              ← Parroquia, RedSocial, PostParroquia, Evento
│       ├── views.py
│       ├── urls.py
│       ├── admin.py
│       └── templates/
│           └── iglesias/
│               ├── base.html
│               ├── lista_parroquias.html
│               ├── detalle_parroquia.html
│               ├── editar_evento.html
│               └── partials/
│                   └── red_status.html
│
├── scraper_redes/                 ← módulo de scraping (standalone)
│   ├── __init__.py
│   ├── config.py                  ← URL hardcodeada y parámetros
│   ├── instagram.py               ← scraping con instaloader
│   ├── procesador.py              ← análisis de imágenes con Gemini/OpenRouter
│   ├── run.py                     ← orquestador principal
│   └── requirements.txt
│
├── check_resultados.py            ← script de verificación manual
├── check_models.py                ← script para listar modelos IA disponibles
├── instagram_login.py             ← script de login con cookies (correr 1 vez)
├── instagram_cookies.json         ← cookies exportadas desde el navegador (NO subir a git)
├── manage.py
├── requirements.txt
└── .env                           ← variables de entorno (NO subir a git)
```

---

## Modelos principales

### Parroquia
Información estructural de cada parroquia: nombre, dirección, contacto, organización
eclesiástica, flags de control (`tiene_redes`, `detalles_completos`).

### RedSocial
Vincula parroquias con sus perfiles digitales. Tipos: facebook, instagram, youtube,
tiktok, otro. Campos: `url`, `username`, `activo`, `verificado`.

### PostParroquia
Posts scrapeados de redes sociales. Campos clave:
- `post_id`: ID nativo de Instagram (shortcode)
- `red_social`: "instagram" o "facebook"
- `imagen_url`: URL de la imagen (puede caducar en Instagram)
- `fecha_publicacion`: datetime con timezone UTC
- `procesado`: bool — False si aún no fue analizado por IA
- `es_evento`: bool nullable — null=sin procesar, True=evento, False=no evento
- `raw_data`: JSON con respuesta cruda de la API de IA

### Evento
Eventos detectados por IA y validados manualmente. Campos clave:
- `parroquia`: FK a Parroquia
- `post`: OneToOne a PostParroquia (puede ser null)
- `titulo`, `tipo`, `fecha`, `hora`, `lugar`, `descripcion`
- `imagen_url`: URL del flyer
- `activo`: bool — False si fue rechazado manualmente
- `verificado`: bool — True si fue aprobado manualmente
- Ordering: `["fecha", "hora"]`

---

## Variables de entorno (.env)

```
META_ACCESS_TOKEN=...           # Graph API de Facebook (opcional por ahora)
GEMINI_API_KEY=...              # Google AI Studio — modelo principal
OPENROUTER_API_KEY=...          # OpenRouter — fallback cuando Gemini falla
INSTAGRAM_SESSION_USER=pilotosprogramadores
```

---

## Scraper de redes sociales

### Cómo correr el scraper
```bash
# Modo prueba: usa la URL hardcodeada en config.py (parroquia TEST)
python -m scraper_redes.run

# Modo producción: itera sobre todas las RedSocial tipo instagram, activo=True, verificado=True
python -m scraper_redes.run --produccion
```

### Login de Instagram (solo la primera vez o cuando caduca la sesión)
```bash
# 1. Exportar cookies desde el navegador con la extensión Cookie-Editor
#    Guardar como instagram_cookies.json en la raíz del proyecto
# 2. Correr el script de login
python instagram_login.py
```

### Flujo del scraper
1. Lee `INSTAGRAM_TEST_URL` de `config.py` (URL hardcodeada por ahora)
2. Carga sesión de Instagram desde archivo
3. Obtiene los últimos `POSTS_A_REVISAR` posts del perfil
4. Guarda posts nuevos en `PostParroquia` con deduplicación por `post_id`
5. Procesa posts pendientes con Gemini → si falla usa OpenRouter como fallback
6. Si detecta evento futuro (`es_evento=True` y `es_pasado=False`), crea un `Evento`

### Parámetros en config.py
```python
INSTAGRAM_TEST_URL = "https://www.instagram.com/nombre_cuenta/"
INSTAGRAM_SESSION_USER = "pilotosprogramadores"
POSTS_A_REVISAR = 5
```

---

## Lógica de detección de eventos

El prompt de IA distingue entre:
- ✅ **Evento futuro**: flyer con convocatoria explícita, palabras como "los esperamos",
  "te invitamos", "este sábado", con fecha/hora futura
- 📅 **Evento pasado**: crónica de algo ya realizado ("gracias por venir", "se festejó")
- ❌ **No es evento**: contenido devocional, reflexiones, saludos sin convocatoria

El JSON que devuelve la IA tiene estos campos:
```json
{
  "es_evento": true/false,
  "es_pasado": true/false,
  "titulo": "...",
  "fecha": "DD/MM/YYYY",
  "hora": "HH:MM",
  "lugar": "...",
  "descripcion": "...",
  "tipo_evento": "misa/retiro/charla/bautismo/confirmacion/peregrinacion/juventud/otro"
}
```

---

## Panel web

### URLs principales
- `/` → redirige a lista de parroquias
- `/parroquias/` → lista con filtros y stats
- `/parroquias/<pk>/` → detalle con eventos y redes
- `/eventos/<pk>/aprobar/` → POST — aprueba evento
- `/eventos/<pk>/rechazar/` → POST — rechaza evento
- `/eventos/<pk>/editar/` → GET/POST — editar y aprobar evento
- `/redes/<pk>/verificar/` → POST — verifica red social
- `/redes/<pk>/eliminar/` → POST — elimina red social

### Lógica de estado de eventos en el listado
Calculado en `_estado_eventos()` en `views.py`:
- `validos`: todos los eventos futuros tienen fecha y lugar
- `requiere_verificacion`: algunos eventos futuros tienen fecha y lugar, otros no
- `todos_incompletos`: ningún evento futuro tiene fecha y lugar completos
- `sin_eventos`: no hay eventos futuros activos

### Detalle de parroquia
- Columna izquierda: datos de identificación, ubicación, contacto, clero
- Columna derecha: estado de información, redes sociales, eventos próximos (máx 5)
- Acordeón debajo de eventos próximos: eventos pasados colapsados

---

## Próximos pasos pendientes

1. **Escalar a las 186 parroquias**: reemplazar URL hardcodeada en `config.py` por
   un loop sobre `RedSocial.objects.filter(tipo="instagram", activo=True)`
2. **Scheduler semanal**: implementar con Celery Beat o Render Cron Job
3. **Migración a producción**: cuando esté en Render, el scraper llama a un endpoint
   REST de la app Django en lugar de escribir directo a la DB
4. **Modelos de IA en producción**: reemplazar Gemini free tier por modelo pago
   (Gemini Pro o Claude API) para mayor precisión y sin límites de cuota

---

## Notas importantes

- **No subir a git**: `.env`, `instagram_cookies.json`, `instagram_login.py`
- **Sesión de Instagram**: caduca periódicamente. Renovar exportando cookies nuevas
  desde el navegador y corriendo `instagram_login.py`
- **OpenRouter como fallback**: menos preciso que Gemini. En producción usar solo
  modelos pagos. Los errores de OpenRouter son aceptables en fase de pruebas
- **Parroquia de prueba**: id=559, id_externo=9999, nombre="Parroquia Cristo Obrero (TEST)"
- **DJANGO_SETTINGS_MODULE**: `core.settings`
- **Comando para correr el scraper**: siempre desde la raíz del proyecto con
  `python -m scraper_redes.run`