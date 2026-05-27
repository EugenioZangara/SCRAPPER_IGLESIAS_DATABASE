from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('iglesias', '0013_horariomisa_dia_semana'),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name='horariomisa',
            unique_together={('parroquia', 'dia_semana')},
        ),
    ]
