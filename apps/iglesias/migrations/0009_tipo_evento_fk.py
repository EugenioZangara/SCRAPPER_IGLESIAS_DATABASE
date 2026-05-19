import django.db.models.deletion
from django.db import migrations, models


TIPOS_EVENTO = [
    ("misa", "Misa"),
    ("retiro", "Retiro"),
    ("charla", "Charla"),
    ("bautismo", "Bautismo"),
    ("confirmacion", "Confirmación"),
    ("peregrinacion", "Peregrinación"),
    ("juventud", "Juventud"),
    ("otro", "Otro"),
]


def insertar_tipos_evento(apps, schema_editor):
    TipoEvento = apps.get_model("iglesias", "TipoEvento")
    for _, nombre in TIPOS_EVENTO:
        TipoEvento.objects.get_or_create(nombre=nombre, defaults={"activo": True})


def migrar_tipos_evento(apps, schema_editor):
    conn = schema_editor.connection
    with conn.cursor() as cursor:
        for slug, nombre in TIPOS_EVENTO:
            cursor.execute(
                """
                UPDATE iglesias_evento
                SET tipo_id = (SELECT id FROM iglesias_tipoevento WHERE nombre = %s LIMIT 1)
                WHERE tipo = %s
                """,
                [nombre, slug],
            )


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('iglesias', '0008_categoriaevento_evento_audiencia_evento_capacidad_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='TipoEvento',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nombre', models.CharField(max_length=100, unique=True)),
                ('activo', models.BooleanField(default=True)),
            ],
            options={
                'verbose_name': 'Tipo de Evento',
                'verbose_name_plural': 'Tipos de Evento',
                'ordering': ['nombre'],
            },
        ),
        migrations.RunPython(insertar_tipos_evento, noop),
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    sql="ALTER TABLE iglesias_evento ADD COLUMN tipo_id BIGINT NULL REFERENCES iglesias_tipoevento(id)",
                    reverse_sql="ALTER TABLE iglesias_evento DROP COLUMN tipo_id",
                ),
            ],
            state_operations=[
                migrations.RemoveField(model_name='evento', name='tipo'),
                migrations.AddField(
                    model_name='evento',
                    name='tipo',
                    field=models.ForeignKey(
                        blank=True, null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='eventos',
                        to='iglesias.tipoevento',
                    ),
                ),
            ],
        ),
        migrations.RunPython(migrar_tipos_evento, noop),
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    sql="ALTER TABLE iglesias_evento DROP COLUMN tipo",
                    reverse_sql="ALTER TABLE iglesias_evento ADD COLUMN tipo VARCHAR(50) NULL",
                ),
            ],
            state_operations=[],
        ),
    ]
