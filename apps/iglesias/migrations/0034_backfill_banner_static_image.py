from django.db import migrations


def backfill_banner_static_image(apps, schema_editor):
    Banner = apps.get_model("iglesias", "Banner")
    Banner.objects.filter(
        imagen_static__isnull=True,
        imagen="banners/ad_gaudium1.jpeg",
    ).update(imagen_static="iglesias/img/ad_gaudium1.jpeg")
    Banner.objects.filter(
        imagen_static="",
        imagen="banners/ad_gaudium1.jpeg",
    ).update(imagen_static="iglesias/img/ad_gaudium1.jpeg")


def clear_banner_static_image(apps, schema_editor):
    Banner = apps.get_model("iglesias", "Banner")
    Banner.objects.filter(
        imagen_static="iglesias/img/ad_gaudium1.jpeg",
        imagen="banners/ad_gaudium1.jpeg",
    ).update(imagen_static=None)


class Migration(migrations.Migration):

    dependencies = [
        ("iglesias", "0033_suscripcion_aviso_misa"),
    ]

    operations = [
        migrations.RunPython(backfill_banner_static_image, clear_banner_static_image),
    ]
