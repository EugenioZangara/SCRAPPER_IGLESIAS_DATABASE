from urllib.parse import urlsplit

from django.conf import settings
from django.http import HttpResponsePermanentRedirect


class CanonicalDomainRedirectMiddleware:
    """Redirige (301) el host no-www al dominio canónico definido en SITE_URL.

    Defensa en profundidad a nivel Django: aunque Render/DNS deban tener
    configurado el mismo redirect, esto garantiza una única versión
    indexable incluso si esa config se pierde o cambia.
    """

    def __init__(self, get_response):
        self.get_response = get_response
        parsed = urlsplit(settings.SITE_URL)
        self.canonical_scheme = parsed.scheme
        self.canonical_host = parsed.netloc
        self.bare_host = parsed.netloc[4:] if parsed.netloc.startswith("www.") else None

    def __call__(self, request):
        host = request.get_host()
        if self.bare_host and host == self.bare_host:
            url = f"{self.canonical_scheme}://{self.canonical_host}{request.get_full_path()}"
            return HttpResponsePermanentRedirect(url)
        return self.get_response(request)
