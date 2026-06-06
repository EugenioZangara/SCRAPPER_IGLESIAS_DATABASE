"""
Procesa los ReporteHorario de usuarios y construye/actualiza
HorarioPropuestoAgregado para una parroquia dada.
"""
import logging
from collections import defaultdict
from .models import ReporteHorario, HorarioMisa, HorarioPropuestoAgregado

logger = logging.getLogger(__name__)

DIAS = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']
UMBRAL_CONFIANZA_ALTA = 1.5   # peso acumulado para pill violeta
UMBRAL_PROMOCION = 2.5        # peso acumulado para sugerir al admin


def calcular_peso_usuario(perfil):
    """
    Devuelve un peso entre 0.2 y 1.0 según historial del usuario.
    Sin perfil o sin historial → 0.5 (neutro).
    """
    if perfil is None:
        return 0.5
    enviados = perfil.reportes_enviados or 0
    if enviados == 0:
        return 0.5
    aprobados = perfil.reportes_aprobados or 0
    rechazados = perfil.reportes_rechazados or 0
    tasa = aprobados / (enviados + 1)
    penalizacion = rechazados / (enviados + 1) * 0.3
    peso = max(0.2, min(1.0, 0.5 + tasa - penalizacion))
    return round(peso, 3)


def extraer_horarios_de_propuesta(propuesta_ia):
    """
    propuesta_ia puede ser:
      - lista: [{'dia': 3, 'horario': '18:00'}, ...]   ← formato real del sistema
      - dict:  {'horarios': {'0': ['8:00'], '6': ['19:00']}}  ← formato alternativo
    Devuelve dict {dia_semana (int): [lista de horas "HH:MM"]}.
    """
    if not propuesta_ia:
        return {}

    resultado = {}

    # Formato lista: [{'dia': int, 'horario': 'HH:MM'}, ...]
    if isinstance(propuesta_ia, list):
        for item in propuesta_ia:
            if not isinstance(item, dict):
                continue
            dia = item.get('dia')
            horario = item.get('horario', '').strip()
            if dia is None or not horario:
                continue
            try:
                dia_int = int(dia)
            except (ValueError, TypeError):
                continue
            if dia_int not in resultado:
                resultado[dia_int] = []
            if horario not in resultado[dia_int]:
                resultado[dia_int].append(horario)
        return resultado

    # Formato dict: {'horarios': {'0': ['8:00'], ...}}
    if isinstance(propuesta_ia, dict):
        horarios = propuesta_ia.get('horarios', {})
        if isinstance(horarios, dict):
            for dia_str, horas in horarios.items():
                try:
                    dia_int = int(dia_str)
                except (ValueError, TypeError):
                    dia_int = next(
                        (i for i, d in enumerate(DIAS)
                         if d.lower().startswith(dia_str.lower()[:3])),
                        None
                    )
                if dia_int is not None and isinstance(horas, list):
                    resultado[dia_int] = [str(h).strip() for h in horas if h]

    return resultado


def reconstruir_propuestos(parroquia):
    """
    Recalcula HorarioPropuestoAgregado para una parroquia
    a partir de todos sus ReporteHorario aplicados o pendientes
    enviados por usuarios (no scraper).
    """
    reportes = ReporteHorario.objects.filter(
        parroquia=parroquia,
        fuente='usuario',
        estado__in=['pendiente', 'aplicado'],
    ).select_related('usuario__perfil')

    logger.warning(f"[propuestos] parroquia {parroquia.pk}: {reportes.count()} reportes encontrados")
    for r in reportes:
        logger.info(f"[propuestos]   reporte {r.pk} fuente={r.fuente} estado={r.estado} propuesta_ia={r.propuesta_ia}")

    votos_por_dia = defaultdict(lambda: defaultdict(float))
    total_por_dia = defaultdict(int)
    con_historial_dia = defaultdict(int)

    for reporte in reportes:
        perfil = None
        if reporte.usuario:
            try:
                perfil = reporte.usuario.perfil
            except Exception:
                pass
        peso = calcular_peso_usuario(perfil)
        tiene_historial = perfil and (perfil.reportes_enviados or 0) > 0

        horarios_propuestos = extraer_horarios_de_propuesta(reporte.propuesta_ia)
        logger.info(f"[propuestos]   reporte {reporte.pk} → horarios extraídos: {horarios_propuestos}")
        for dia_int, horas in horarios_propuestos.items():
            total_por_dia[dia_int] += 1
            if tiene_historial:
                con_historial_dia[dia_int] += 1
            for hora in horas:
                votos_por_dia[dia_int][hora] += peso

    oficiales_por_dia = {}
    for hm in HorarioMisa.objects.filter(parroquia=parroquia):
        horas_str = hm.horarios or ''
        horas_list = [h.strip() for h in horas_str.replace('·', ',').split(',') if h.strip()]
        oficiales_por_dia[hm.dia_semana] = set(horas_list)

    dias_involucrados = set(votos_por_dia.keys()) | set(oficiales_por_dia.keys())

    for dia in dias_involucrados:
        votos = votos_por_dia.get(dia, {})
        oficiales = oficiales_por_dia.get(dia, set())
        total = total_por_dia.get(dia, 0)
        con_hist = con_historial_dia.get(dia, 0)

        horarios_json = []
        for hora, peso_acumulado in sorted(votos.items()):
            estado = 'coincide' if hora in oficiales else 'nuevo'
            horarios_json.append({
                'hora': hora,
                'peso': round(peso_acumulado, 3),
                'estado': estado,
            })

        max_peso = max((h['peso'] for h in horarios_json), default=0)
        confianza = min(1.0, max_peso / UMBRAL_CONFIANZA_ALTA) if max_peso else 0.0

        HorarioPropuestoAgregado.objects.update_or_create(
            parroquia=parroquia,
            dia_semana=dia,
            defaults={
                'horarios_json': horarios_json,
                'confianza': round(confianza, 3),
                'total_aportes': total,
                'aportes_con_historial': con_hist,
            }
        )

    logger.info(f"[propuestos] dias_involucrados: {dias_involucrados}")
    logger.info(f"[propuestos] votos_por_dia: {dict(votos_por_dia)}")
    logger.info(f"[propuestos] {parroquia.pk} recalculado — {len(dias_involucrados)} días")
