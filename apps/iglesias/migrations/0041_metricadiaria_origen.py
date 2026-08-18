from django.db import migrations, models


class Migration(migrations.Migration):
    """Etiqueta cada métrica según quién la generó.

    Las filas que ya existían quedan como 'desconocido': no se pueden
    reclasificar hacia atrás porque nunca se guardó el user-agent. Es
    información honesta, no un dato faltante.
    """

    dependencies = [
        ("iglesias", "0040_metricadiaria"),
    ]

    operations = [
        migrations.AddField(
            model_name="metricadiaria",
            name="origen",
            field=models.CharField(
                choices=[
                    ("humano", "Persona"),
                    ("bot", "Rastreador automático"),
                    ("desconocido", "Sin clasificar"),
                ],
                db_index=True,
                default="desconocido",
                help_text=(
                    "Quién generó el evento. 'desconocido' son los datos "
                    "previos a que empezáramos a clasificar."
                ),
                max_length=12,
            ),
        ),
        migrations.AddIndex(
            model_name="metricadiaria",
            index=models.Index(
                fields=["fecha", "tipo", "origen"],
                name="metrica_fecha_tipo_origen",
            ),
        ),
    ]
