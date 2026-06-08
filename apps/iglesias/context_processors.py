from django.conf import settings


def seo_context(request):
    return {
        "FACEBOOK_APP_ID": getattr(settings, "FACEBOOK_APP_ID", ""),
        "SITE_URL": getattr(settings, "SITE_URL", "https://parroguia.com"),
        "IMAGEKIT_URL_ENDPOINT": getattr(settings, "IMAGEKIT_URL_ENDPOINT", ""),
    }
