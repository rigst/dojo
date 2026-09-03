from django.shortcuts import render
from django.views.decorators.http import require_GET


@require_GET
def termos(request):
    return render(request, "legal/termos.html")


@require_GET
def privacidade(request):
    return render(request, "legal/privacidade.html")
