import json

with open("reconocimiento_web_resultados.json", encoding="utf-8") as f:
    data = json.load(f)

KEYWORDS_EVENTOS = [
    "evento",
    "eventos",
    "agenda",
    "actividad",
    "actividades",
    "retiro",
    "peregrinacion",
    "peregrinación",
    "charla",
    "taller",
    "encuentro",
    "jornada",
    "fiesta",
    "celebracion",
    "celebración",
    "novena",
    "procesion",
    "procesión",
    "mision",
    "misión",
]

print("Sitios con keywords de eventos:")
print(f"{'PARROQUIA':45} {'TECNOLOGIA':12} KEYWORDS EVENTOS")
print("-" * 90)

con_eventos = []
for r in data:
    if r.get("error") or r.get("status") != 200:
        continue
    kws_encontradas = [
        kw for kw in KEYWORDS_EVENTOS if kw in str(r.get("keywords_encontradas", []))
    ]
    # También buscar en el título
    titulo = r.get("titulo_pagina", "") or ""
    kws_titulo = [kw for kw in KEYWORDS_EVENTOS if kw in titulo.lower()]
    todas = list(set(kws_encontradas + kws_titulo))
    if todas:
        con_eventos.append((r, todas))

con_eventos.sort(key=lambda x: -len(x[1]))

for r, kws in con_eventos:
    print(f"  {r['nombre'][:43]:45} {r.get('tecnologia','?'):12} {', '.join(kws[:4])}")

print(f"\nTotal con keywords de eventos: {len(con_eventos)}/{len(data)}")
