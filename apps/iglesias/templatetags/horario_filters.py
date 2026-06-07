import json as _json
from django import template

register = template.Library()


@register.filter
def safe_json(value):
    return _json.dumps(value, ensure_ascii=False)


@register.filter
def split_horarios(value):
    """Divide '8:00 · 10:00' en lista de horas."""
    if not value:
        return []
    return [h.strip() for h in value.replace('·', ',').split(',') if h.strip()]


@register.filter
def confianza_promedio(horarios_propuestos):
    items = list(horarios_propuestos)
    if not items:
        return 0
    total = sum(hp.confianza for hp in items)
    return round((total / len(items)) * 100)


@register.filter
def total_aportes(horarios_propuestos):
    items = list(horarios_propuestos)
    if not items:
        return 0
    return max(hp.total_aportes for hp in items)


@register.filter
def aportes_historial(horarios_propuestos):
    items = list(horarios_propuestos)
    if not items:
        return 0
    return max(hp.aportes_con_historial for hp in items)
