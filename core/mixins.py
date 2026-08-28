from django.shortcuts import get_object_or_404


class DonoObrigatorioMixin:
    """Restringe a view aos objetos do usuário autenticado.

    Existe para que nenhuma view precise lembrar de filtrar por dono: a regra
    fica num lugar só, e esquecer dela quebra o teste de isolamento em vez de
    vazar o projeto de outra pessoa.

    A subclasse define `model` (ou `queryset`) e, quando o dono não é um campo
    direto, `caminho_do_dono` com o lookup até ele.
    """

    caminho_do_dono = "usuario"

    def get_queryset(self):
        queryset = super().get_queryset()
        return queryset.filter(**{self.caminho_do_dono: self.request.user})


def obter_do_usuario(model, usuario, *, caminho_do_dono="usuario", **filtros):
    """Versão funcional do mixin, para views baseadas em função.

    Devolve 404, e não 403, quando o objeto é de outra pessoa: quem não pode
    ver também não deveria descobrir que ele existe.
    """
    return get_object_or_404(model, **{caminho_do_dono: usuario}, **filtros)
