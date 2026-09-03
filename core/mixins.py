from typing import TYPE_CHECKING

from django.shortcuts import get_object_or_404

if TYPE_CHECKING:
    from django.http import HttpRequest
    from django.views.generic.detail import SingleObjectMixin

    # Só para o verificador: dá ao mixin uma base que tem `get_queryset`, que é
    # de onde o `super()` abaixo vem na prática. Em tempo de execução a base é
    # `object`, e quem herda traz a view genérica de verdade.
    _Base = SingleObjectMixin
else:
    _Base = object


class DonoObrigatorioMixin(_Base):
    """Restringe a view aos objetos do usuário autenticado.

    Existe para que nenhuma view precise lembrar de filtrar por dono: a regra
    fica num lugar só, e esquecer dela quebra o teste de isolamento em vez de
    vazar o projeto de outra pessoa.

    A subclasse define `model` (ou `queryset`) e, quando o dono não é um campo
    direto, `caminho_do_dono` com o lookup até ele.
    """

    caminho_do_dono = "usuario"

    if TYPE_CHECKING:
        # `request` vem da View concreta que a subclasse também herda. Sem
        # declarar aqui, o mypy não tem como saber — e a alternativa seria um
        # `# type: ignore`, que este projeto não usa.
        request: "HttpRequest"

    def get_queryset(self):
        queryset = super().get_queryset()
        return queryset.filter(**{self.caminho_do_dono: self.request.user})


def obter_do_usuario(model, usuario, *, caminho_do_dono="usuario", **filtros):
    """Versão funcional do mixin, para views baseadas em função.

    Devolve 404, e não 403, quando o objeto é de outra pessoa: quem não pode
    ver também não deveria descobrir que ele existe.
    """
    return get_object_or_404(model, **{caminho_do_dono: usuario}, **filtros)
