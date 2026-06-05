from django.conf import settings


def seo_context(request):
    return {
        "FACEBOOK_APP_ID": getattr(settings, "FACEBOOK_APP_ID", ""),
    }
