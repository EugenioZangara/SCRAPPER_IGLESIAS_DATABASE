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
- `/parroquias/<pk>/editar/contacto/` → GET (form inline) / POST (guarda) — edición HTMX sección Contacto
- `/parroquias/<pk>/editar/ubicacion/` → GET / POST — edición HTMX sección Ubicación
- `/parroquias/<pk>/editar/clero/` → GET / POST — edición HTMX sección Clero e historia
- `/parroquias/<pk>/editar/bai/` → GET / POST — edición HTMX sección BAIglesias
- `/eventos/<pk>/aprobar/` → POST — aprueba evento
- `/eventos/<pk>/rechazar/` → POST — rechaza evento
- `/eventos/<pk>/editar/` → GET/POST — editar y aprobar evento
- `/eventos/<pk>/aprobar-extendido/` → GET/POST (staff only) — formulario extendido de aprobación con campos de categoría, audiencia, ubicación, logística y datos del scraper en panel lateral
- `/redes/<pk>/verificar/` → POST — verifica red social
- `/redes/<pk>/eliminar/` → POST — elimina red social
- `/parroquias/<pk>/scrapear/` → POST (staff only) — lanza scraping Instagram de esa parroquia y devuelve partial HTMX con resultado
- `/eventos/moderacion/` → GET (staff only) — lista de moderación de eventos con tabs y acciones HTMX inline (solo futuros o sin fecha)
- `/eventos/moderacion/pasados/` → GET (staff only) — lista de eventos pasados (fecha < hoy); acciones Editar, Rechazar/Restaurar

### Lógica de estado de eventos en el listado
Calculado en `_estado_eventos()` en `views.py`:
- `validos`: todos los eventos futuros tienen fecha y lugar
- `requiere_verificacion`: algunos eventos futuros tienen fecha y lugar, otros no
- `todos_incompletos`: ningún evento futuro tiene fecha y lugar completos
- `sin_eventos`: no hay eventos futuros activos

### Detalle de parroquia
- Columna izquierda: datos de identificación, ubicación, contacto, clero, BAIglesias
- Columna derecha: estado de información, redes sociales, eventos próximos (máx 5)
- Acordeón debajo de eventos próximos: eventos pasados colapsados
- Navegación anterior/siguiente por nombre en el page-title

### Scraping Instagram desde el panel (botón por parroquia)
- Visible en el aside del detalle solo si `request.user.is_staff` y la parroquia tiene
  una red de Instagram `activo=True, verificado=True` (`ig_verificada` en el contexto)
- HTMX POST a `/parroquias/<pk>/scrapear/` con indicador de carga (`#scraping-loader`)
- La vista `scrapear_parroquia` en `views.py`: obtiene la red verificada, llama a
  `scraper_redes.instagram.scrapear_perfil` y `scraper_redes.procesador.procesar_post`
- Guarda posts nuevos con `get_or_create` por `post_id`, crea `Evento` para los nuevos
- Retorna el partial `iglesias/partials/scraping_resultado.html` con stats o error
- **No importar `scraper_redes.run`** — tiene código de nivel módulo (`argparse`) que
  ejecuta `main()` al importar. La lógica de `_crear_evento_desde_post` está replicada
  inline en `views.py`

### Vista aprobar_extendido (solo staff)
- URL: `/eventos/<pk>/aprobar-extendido/` → vista `aprobar_extendido`
- Layout dos columnas: formulario a la izquierda, paneles informativos sticky a la derecha
- Columna derecha muestra datos detectados por IA (`evento.post.raw_data["gemini"]`), link IG y datos de parroquia
- Preselecciona `ubicacion_lugar` desde `evento.lugar` si está vacío
- `gratuito` preselecciona "sí" cuando el campo es `True` o `None` (no establecido)
- Los botones "✓ Aprobar" en `moderacion_eventos` y `detalle_parroquia` redirigen aquí (no hacen POST directo)
- El parámetro `next` lleva de vuelta a la tab activa de moderación codificando `?` como `%3F`

### Moderación de eventos (solo staff)
- URL: `/eventos/moderacion/` → vista `moderacion_eventos`
- Solo muestra eventos futuros o sin fecha (`fecha >= hoy` o `fecha=None`)
- Enlace "Ver N eventos pasados →" hacia `/eventos/moderacion/pasados/` si hay alguno
- Tabs por estado: `pendiente` (default) / `aprobado` / `rechazado` / `todos`
- Cada fila tiene `id="evento-{{ evento.pk }}"` como target de HTMX
- Acciones Aprobar/Rechazar/Restaurar usan `hx-post` + `hx-swap="outerHTML"` sobre la fila
- `aprobar_evento` y `rechazar_evento` detectan `HX-Request` y devuelven el partial
  `iglesias/partials/evento_fila.html` en lugar de redirigir
- El partial `evento_fila.html` determina los botones a mostrar por el estado del objeto
  (no por el filtro activo), usando `evento.activo` y `evento.verificado`
- Link "IG" visible solo si el evento tiene `post` asociado

### Edición inline (solo staff)
- Las secciones Contacto, Ubicación, Clero e historia y BAIglesias tienen botón "Editar"
  visible solo si `request.user.is_staff`
- Al hacer clic, HTMX reemplaza la sección con un formulario inline (sin redirección)
- Al guardar, HTMX reemplaza de vuelta con la vista actualizada
- Cancelar rehace GET `?cancelar=1` que devuelve la vista sin guardar
- Acceso directo a las URLs de edición sin ser staff devuelve 403
- Los partials de sección están en `apps/iglesias/templates/iglesias/partials/`:
  `seccion_contacto.html`, `seccion_ubicacion.html`, `seccion_clero.html`, `seccion_bai.html`
- Cada partial maneja ambos modos (view/edit) según la variable `editing`
- La sección BAIglesias permite editar/crear/eliminar horarios de misa con JS nativo

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

---

## Scraper BAIglesias

- Se agregaron dos modelos nuevos: `InfoBaiglesias` (OneToOne con Parroquia) y
  `HorarioMisa` (FK a Parroquia). Ambos en `apps/iglesias/models.py`.

- El scraper se encuentra en `scraper_redes/baiglesias.py` y el orquestador
  en `scraper_redes/run_baiglesias.py`.

- Para correrlo: `python -m scraper_redes.run_baiglesias`
  Procesa únicamente parroquias cuyo `sitio_web` contiene `"baiglesias.com"` (30 parroquias).

- Los datos scrapeados son: dirección completa, cómo llegar y horarios de misas
  por día. La historia no se guarda.

- El scraper usa `httpx` + `BeautifulSoup4` para parsear el HTML estático del sitio.

- La información se muestra en el detalle de la parroquia en el panel Django,
  en una sección llamada "Información BAIglesias", solo si la parroquia tiene
  datos scrapeados.

- La dependencia `beautifulsoup4` fue agregada a `scraper_redes/requirements.txt`.

---

## Sistema de diseño

### Dirección estética
Editorial / archivo — apropiado para contenido eclesiástico.
Tipografía serif para display, sans neutra para cuerpo, mono para metadatos.
Paleta cálida en papel crema con tinta profunda y acento litúrgico burdeos.
Sin gradientes, sin emojis, datos tratados como tipografía editorial.

### Fuentes (Google Fonts)
- Newsreader — serif display (títulos, valores grandes, dd en fields)
- Geist — sans neutra (cuerpo, nav, botones)
- JetBrains Mono — mono (labels, metadatos, IDs, fechas, URLs)

### Variables CSS principales
```
--paper: oklch(0.975 0.008 80)        ← fondo principal
--paper-2: oklch(0.96 0.009 80)       ← fondo alternativo
--ink: oklch(0.20 0.015 60)           ← texto principal
--ink-2: oklch(0.36 0.015 60)         ← texto secundario
--muted: oklch(0.55 0.012 60)         ← texto atenuado
--faint: oklch(0.72 0.010 60)         ← texto muy atenuado
--rule: oklch(0.86 0.012 60)          ← bordes principales
--rule-2: oklch(0.91 0.010 80)        ← bordes suaves
--accent: #7A1F2B                     ← burdeos litúrgico
--accent-soft: #7A1F2B14              ← acento suave
--ok: oklch(0.48 0.08 150)            ← verde confirmación
--serif: "Newsreader", Georgia, serif
--sans: "Geist", system-ui, sans-serif
--mono: "JetBrains Mono", monospace
```

### Componentes clave
- `.masthead`: header con brand-mark (serif + em italic accent) y nav mono uppercase
- `.fiche-head`: grid 1fr/auto con título serif grande + número de registro
- `.meta-strip`: grid 4 columnas con `.meta-cell` (lbl mono + val serif grande + foot)
- `.block` + `.block-head`: secciones con h2 serif y numeración romana en `.num`
- `dl.fields > div`: grid 180px/1fr con dt mono uppercase y dd serif 19px
- `.social-card`: tarjeta de red social con sc-head/sc-handle/sc-url/sc-open
- `.actions`: lista de acciones con `.action` (primary = fondo ink)
- `.events .ev-row`: grid 80px/1fr/auto para timeline de eventos
- `.empty`: estado vacío con SVG + texto italic serif
- `.badge`: pill mono uppercase con punto de color antes del texto
  - `.ok` → punto acento, borde ink
  - `.warn` → punto hueco, color faint
  - `.missing` → variante rojo

### Archivos de referencia
- Diseño estático original: `Parroquia-detalle.html` (en raíz del proyecto)
- Template Django implementado: `apps/iglesias/templates/iglesias/detalle_parroquia.html`
- Estilos base compartidos: `apps/iglesias/templates/iglesias/base.html`

### Notas de implementación
- Los nombres de parroquias usan la última palabra en `<em>` italic accent
- IDs y URLs van en `<span class="mono">`
- Valores secundarios van en `<span class="secondary">`
- Links con `border-bottom: 1px solid var(--accent)`, sin text-decoration
- El aside es sticky (`top: 24px`) en desktop, static en mobile
- `body::before` tiene textura de puntos con radial-gradient (`mix-blend-mode: multiply`)

---

## Exportación a Google Sheets

### Modelo CategoriaEvento
Tabla de categorías para clasificar eventos antes de exportar a Sheets.
- `nombre`: CharField(100), unique
- `activo`: BooleanField, default=True
- Ordering: `["nombre"]`
- Fixture inicial: `apps/iglesias/fixtures/categorias_evento.json` (10 categorías)

### Campos nuevos en modelo Evento
Agregados después de `descripcion`, antes de `imagen_url`:

| Campo | Tipo | Notas |
|---|---|---|
| `categoria` | FK → CategoriaEvento | null/blank, SET_NULL |
| `fecha_fin` | DateTimeField | null/blank — fin del evento |
| `url_externa` | URLField(500) | WhatsApp, formulario, etc. |
| `audiencia` | CharField(20) | choices: ambos/hombres/mujeres |
| `edad_desde` | PositiveIntegerField | default 0 |
| `edad_hasta` | PositiveIntegerField | default 100 |
| `gratuito` | BooleanField | null/blank |
| `capacidad` | PositiveIntegerField | null/blank |
| `ubicacion_lugar` | CharField(255) | null/blank |
| `ubicacion_direccion` | CharField(255) | null/blank |
| `ubicacion_ciudad` | CharField(100) | default "Buenos Aires" |
| `ubicacion_cp` | CharField(20) | null/blank |
| `ubicacion_provincia` | CharField(100) | default "Buenos Aires" |
| `exportado_sheets` | BooleanField | default False |

### Fixture inicial de categorías
```bash
python manage.py loaddata apps/iglesias/fixtures/categorias_evento.json
```
10 categorías: Retiros espirituales, Misas especiales, Charlas y conferencias,
Peregrinaciones, Actividades juveniles, Sacramentos, Catequesis,
Festividades patronales, Actividades solidarias, Formación y talleres.

### Integración Google Sheets
- Archivo: `apps/iglesias/sheets.py`
- Función principal: `exportar_evento_a_sheets(evento)` — agrega una fila al sheet y retorna `True/False`
- Credenciales locales: archivo `google_credentials.json` (en `.gitignore`)
- Credenciales producción: variable `GOOGLE_CREDENTIALS_JSON` (contenido del JSON)
- `GOOGLE_SHEETS_ID`: ID del spreadsheet destino
- La exportación ocurre automáticamente en `aprobar_extendido` POST; si falla, **no bloquea** la aprobación (captura excepción con print)
- El campo `exportado_sheets` en `Evento` queda en `True` cuando la exportación fue exitosa
- Columnas exportadas: título, tipo, url_externa, categoría, descripción, fecha_inicio, fecha_fin, lugar, dirección, ciudad, CP, provincia, estado ("Borrador"), audiencia, rango edad, gratuito, capacidad

---

## Deploy en Render

### Archivos de configuración
- `render.yaml` — Blueprint con web service, cron job y base de datos
- `build.sh` — Script de build: `pip install`, `collectstatic`, `migrate`

### Servicios en Render
| Servicio | Tipo | Descripción |
|---|---|---|
| `scraper-catolico` | Web | App Django con gunicorn |
| `scraper-instagram` | Cron | Scraper semanal, lunes 06:00 UTC |
| `scraper-catolico-db` | PostgreSQL | Plan free |

### Variables de entorno (configurar manualmente en Render)
Las siguientes variables tienen `sync: false` y deben setearse a mano en el dashboard:
- `GEMINI_API_KEY`
- `OPENROUTER_API_KEY`
- `META_ACCESS_TOKEN`
- `INSTAGRAM_SESSION_USER`

Las siguientes se generan o setean automáticamente via `render.yaml`:
- `DATABASE_URL` — inyectada desde la base de datos
- `SECRET_KEY` — generada automáticamente por Render
- `ALLOWED_HOSTS` — dominio de Render
- `CSRF_TRUSTED_ORIGINS` — origen HTTPS de Render
- `DEBUG` — false

### Settings relevantes en core/settings.py
- `ALLOWED_HOSTS` y `CSRF_TRUSTED_ORIGINS` se leen con `env.list()`
- `STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"`
- `STATIC_ROOT = BASE_DIR / "staticfiles"` — directorio generado por `collectstatic`
- WhiteNoise va inmediatamente después de `SecurityMiddleware` en `MIDDLEWARE`

### Dependencias de producción (en requirements.txt)
- `gunicorn` — servidor WSGI
- `whitenoise` — sirve archivos estáticos sin Nginx
- `psycopg2-binary` — driver PostgreSQL

### Notas
- El cron job del scraper necesita las cookies de Instagram en la sesión de Render;
  por ahora corre solo si la sesión está activa en el entorno.
- `staticfiles/` está en `.gitignore` — se genera en cada build.
- Para deploy manual: push a la rama conectada en Render o usar `render deploy`.