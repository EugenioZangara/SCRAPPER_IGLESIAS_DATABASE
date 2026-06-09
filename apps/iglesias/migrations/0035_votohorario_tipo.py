from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('iglesias', '0034_backfill_banner_static_image'),
    ]

    operations = [
        migrations.AddField(
            model_name='votohorario',
            name='tipo',
            field=models.CharField(
                choices=[('oficial', 'Oficial'), ('propuesto', 'Propuesto')],
                default='oficial',
                max_length=10,
            ),
        ),
        migrations.RemoveConstraint(
            model_name='votohorario',
            name='unique_voto_usuario',
        ),
        migrations.RemoveConstraint(
            model_name='votohorario',
            name='unique_voto_sesion',
        ),
        migrations.AddConstraint(
            model_name='votohorario',
            constraint=models.UniqueConstraint(
                condition=models.Q(usuario__isnull=False),
                fields=['parroquia', 'tipo', 'usuario'],
                name='unique_voto_usuario',
            ),
        ),
        migrations.AddConstraint(
            model_name='votohorario',
            constraint=models.UniqueConstraint(
                condition=models.Q(usuario__isnull=True),
                fields=['parroquia', 'tipo', 'session_key'],
                name='unique_voto_sesion',
            ),
        ),
    ]
