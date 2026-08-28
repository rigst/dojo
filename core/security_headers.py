import secrets

from asgiref.sync import iscoroutinefunction, markcoroutinefunction
from django.conf import settings


class ContentSecurityPolicyMiddleware:
    """Sorteia o nonce da requisição e assina a resposta com a CSP.

    Precisa das duas metades. Síncrona e assíncrona. A view do chat é `async`
    e devolve um stream; se o middleware fosse só síncrono, o Django rodaria a
    view inteira dentro de `async_to_sync` numa thread, e o SSE só chegaria ao
    navegador depois de a resposta terminar, que é exatamente o contrário do
    que ele existe para fazer.
    """

    async_capable = True
    sync_capable = True

    def __init__(self, get_response):
        self.get_response = get_response
        self.async_mode = iscoroutinefunction(get_response)
        if self.async_mode:
            markcoroutinefunction(self)

    def __call__(self, request):
        if self.async_mode:
            return self.__acall__(request)
        nonce = self._marcar(request)
        return self._assinar(self.get_response(request), nonce)

    async def __acall__(self, request):
        nonce = self._marcar(request)
        return self._assinar(await self.get_response(request), nonce)

    def _marcar(self, request):
        nonce = secrets.token_urlsafe(16)
        request.csp_nonce = nonce
        return nonce

    def _assinar(self, response, nonce):
        if getattr(settings, "ENABLE_CSP", False) and "Content-Security-Policy" not in response:
            response["Content-Security-Policy"] = settings.CONTENT_SECURITY_POLICY.format(
                nonce=nonce
            )
        return response
