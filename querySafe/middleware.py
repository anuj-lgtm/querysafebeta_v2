from django.http import HttpResponsePermanentRedirect


class DomainRedirectMiddleware:
    """Redirect .querysafe.in domains to their .querysafe.ai equivalents."""

    REDIRECT_MAP = {
        'console.querysafe.in': 'https://console.querysafe.ai',
        'querysafe.in': 'https://querysafe.ai',
        'www.querysafe.in': 'https://querysafe.ai',
    }

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        host = request.get_host().split(':')[0].lower()

        if host in self.REDIRECT_MAP:
            target = self.REDIRECT_MAP[host]
            return HttpResponsePermanentRedirect(target + request.get_full_path())

        return self.get_response(request)
