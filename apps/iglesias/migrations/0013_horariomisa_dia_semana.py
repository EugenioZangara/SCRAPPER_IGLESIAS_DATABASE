from django.db import migrations, models


DIAS_MAP = {
    "lunes": [0],
    "martes": [1],
    "miércoles": [2], "miercoles": [2],
    "jueves": [3],
    "viernes": [4],
    "sábado": [5], "sabado": [5], "sábados": [5], "sabados": [5],
    "domingo": [6], "domingos": [6],
    "lunes a viernes": [0, 1, 2, 3, 4],
    "lunes a jueves": [0, 1, 2, 3],
    "lunes a sábados": [0, 1, 2, 3, 4, 5],
    "lunes a sábado": [0, 1, 2, 3, 4, 5],
    "martes a viernes": [1, 2, 3, 4],
    "martes a sábado": [1, 2, 3, 4, 5],
    "miércoles a viernes": [2, 3, 4],
    "miercoles a viernes": [2, 3, 4],
    "jueves a viernes": [3, 4],
    "sábados y domingos": [5, 6],
    "sabados y domingos": [5, 6],
    "fines de semana": [5, 6],
    "todos los días": [0, 1, 2, 3, 4, 5, 6],
    "todos los dias": [0, 1, 2, 3, 4, 5, 6],
    "diariamente": [0, 1, 2, 3, 4, 5, 6],
}


def migrar_horarios(apps, schema_editor):
    HorarioMisa = apps.get_model("iglesias", "HorarioMisa")
    registros_a_crear = []
    registros_a_eliminar = []

    for h in HorarioMisa.objects.all():
        dias_texto = (h.dias or "").strip().lower()
        dias_numeros = DIAS_MAP.get(dias_texto)

        if dias_numeros is None:
            for key, nums in DIAS_MAP.items():
                if key in dias_texto:
                    dias_numeros = nums
                    break

        if dias_numeros:
            registros_a_eliminar.append(h.pk)
            for dia_num in dias_numeros:
                existe = HorarioMisa.objects.filter(
                    parroquia_id=h.parroquia_id,
                    dia_semana=dia_num
                ).exists()
                if not existe:
                    registros_a_crear.append(
                        HorarioMisa(
                            parroquia_id=h.parroquia_id,
                            dia_semana=dia_num,
                            horarios=h.horarios,
                            nota=h.nota or "",
                            dias="",  # campo aún existe, NOT NULL — vaciar
                        )
                    )
        else:
            print(f"  No se pudo convertir: '{h.dias}' para {h.parroquia_id}")
            h.dia_semana = 0
            h.save()

    HorarioMisa.objects.filter(pk__in=registros_a_eliminar).delete()
    HorarioMisa.objects.bulk_create(registros_a_crear)


def revertir_horarios(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    atomic = False  # necesario para mezclar DML y DDL en PostgreSQL

    dependencies = [
        ('iglesias', '0012_reportehorario'),
    ]

    operations = [
        # 1. Agregar dia_semana nullable con default
        migrations.AddField(
            model_name='horariomisa',
            name='dia_semana',
            field=models.IntegerField(
                choices=[
                    (0, 'Lunes'), (1, 'Martes'), (2, 'Miércoles'),
                    (3, 'Jueves'), (4, 'Viernes'), (5, 'Sábado'), (6, 'Domingo'),
                ],
                default=0,
                null=True,
            ),
        ),
        # 2. Agregar campo fuente
        migrations.AddField(
            model_name='horariomisa',
            name='fuente',
            field=models.CharField(
                choices=[
                    ('baiglesias', 'BAIglesias'),
                    ('web_propia', 'Web propia'),
                    ('usuario', 'Reporte de usuario'),
                ],
                default='baiglesias',
                max_length=20,
            ),
        ),
        # 3. Ampliar max_length de horarios
        migrations.AlterField(
            model_name='horariomisa',
            name='horarios',
            field=models.CharField(
                max_length=200,
                help_text='Ej: 8:00 · 19:00',
            ),
        ),
        # 4. Migrar datos existentes
        migrations.RunPython(migrar_horarios, revertir_horarios),
        # 5. Eliminar campo dias
        migrations.RemoveField(
            model_name='horariomisa',
            name='dias',
        ),
        # 6. dia_semana NOT NULL
        migrations.AlterField(
            model_name='horariomisa',
            name='dia_semana',
            field=models.IntegerField(
                choices=[
                    (0, 'Lunes'), (1, 'Martes'), (2, 'Miércoles'),
                    (3, 'Jueves'), (4, 'Viernes'), (5, 'Sábado'), (6, 'Domingo'),
                ],
            ),
        ),
        # 7. Cambiar ordering
        migrations.AlterModelOptions(
            name='horariomisa',
            options={
                'ordering': ['dia_semana'],
                'verbose_name': 'Horario de Misa',
                'verbose_name_plural': 'Horarios de Misa',
            },
        ),
        # 8. unique_together
        migrations.AlterUniqueTogether(
            name='horariomisa',
            unique_together={('parroquia', 'dia_semana')},
        ),
    ]
