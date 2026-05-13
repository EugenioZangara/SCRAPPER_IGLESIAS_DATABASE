import sys, os
sys.path.insert(0, '.')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')

import django
django.setup()

from apps.iglesias.models import PostParroquia

posts = PostParroquia.objects.filter(parroquia_id=559).order_by('-creado_en')

print(f"=== Posts procesados: {posts.count()} ===\n")

for post in posts:
    gemini = post.raw_data.get('gemini', {}) if post.raw_data else {}
    es_evento = "✅ EVENTO" if post.es_evento else "❌ no evento"

    print(f"{'='*60}")
    print(f"Post ID  : {post.post_id}")
    print(f"Resultado: {es_evento}")
    print(f"Título   : {gemini.get('titulo')}")
    print(f"Fecha    : {gemini.get('fecha')}")
    print(f"Hora     : {gemini.get('hora')}")
    print(f"Lugar    : {gemini.get('lugar')}")
    print(f"Tipo     : {gemini.get('tipo_evento')}")
    print(f"Desc     : {gemini.get('descripcion')}")
    caption = post.raw_data.get('caption') if post.raw_data else ''
    print(f"Caption  : {(caption or '')[:80]}")
    print(f"Imagen   : {post.imagen_url}")
    print(f"Ver post : https://www.instagram.com/p/{post.post_id}/")
    print()