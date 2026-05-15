import json

with open("reconocimiento_web_resultados.json", encoding="utf-8") as f:
    data = json.load(f)

wp = [
    r
    for r in data
    if r.get("tecnologia") == "wordpress" and r.get("tiene_contenido_util")
]
wp_sorted = sorted(wp, key=lambda x: -len(x.get("keywords_encontradas", [])))

print("Top 5 WordPress con más contenido:")
for r in wp_sorted[:5]:
    kws = len(r["keywords_encontradas"])
    print(f"  {kws} kw — {r['nombre'][:40]:40} {r['url']}")
