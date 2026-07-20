from urllib.parse import urlsplit

from django.conf import settings
from django.http import HttpResponsePermanentRedirect


class CanonicalDomainRedirectMiddleware:
    """Redirige (301) al dominio y esquema canónicos definidos en SITE_URL.

    Corrige host (no-www → www) y esquema (http → https) en un único hop,
    evitando cadenas de redirects (http://bare → https://bare → https://www)
    que Search Console puede marcar como exclusión de indexado.
    """

    def __init__(self, get_response):
        self.get_response = get_response
        parsed = urlsplit(settings.SITE_URL)
        self.canonical_scheme = parsed.scheme
        self.canonical_host = parsed.netloc
        self.bare_host = parsed.netloc[4:] if parsed.netloc.startswith("www.") else None

    def __call__(self, request):
        host = request.get_host()
        wrong_host = bool(self.bare_host) and host == self.bare_host
        wrong_scheme = self.canonical_scheme == "https" and not request.is_secure()
        if wrong_host or wrong_scheme:
            url = f"{self.canonical_scheme}://{self.canonical_host}{request.get_full_path()}"
            return HttpResponsePermanentRedirect(url)
        return self.get_response(request)
