from django.shortcuts import render


def termos(request):
    return render(request, "legal/termos.html")


def privacidade(request):
    return render(request, "legal/privacidade.html")
