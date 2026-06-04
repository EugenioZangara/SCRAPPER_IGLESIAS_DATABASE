from django.db import migrations


def set_provincia_caba(apps, schema_editor):
    Parroquia = apps.get_model("iglesias", "Parroquia")
    Parroquia.objects.filter(
        provincia__isnull=True
    ).update(
        provincia="Ciudad Autónoma de Buenos Aires",
        ciudad="Buenos Aires",
        diocesis="Arquidiócesis de Buenos Aires",
    )


class Migration(migrations.Migration):
    dependencies = [
        ("iglesias", "0025_parroquia_provincia_ciudad_diocesis"),
    ]
    operations = [
        migrations.RunPython(set_provincia_caba, migrations.RunPython.noop),
    ]
