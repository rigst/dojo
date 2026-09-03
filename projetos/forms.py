from typing import cast

from django import forms

from projetos.models import Etapa, Passo, Projeto, Stack


class ProjetoForm(forms.ModelForm):
    """Serve a criação e a edição.

    Título e subtítulo só aparecem no formulário quando o projeto já existe
    (`instance.pk`): na criação, ninguém digita título, o mentor escolhe um ao
    gerar o plano. Na edição, ficam como correção manual, para quando o mentor
    escolhe mal — mas replanejar escolhe de novo e apaga a correção.
    """

    class Meta:
        model = Projeto
        # Sem `horas_por_semana` nem `preferencia_didatica`: perguntar os dois
        # só adiava a tela seguinte por dado que raramente mudava a resposta.
        # O estilo é sempre socrático agora (ver `Projeto.preferencia_didatica`
        # e `ia/prompts.py:DIDATICA`), e o tempo disponível fica no padrão do
        # campo do modelo.
        fields = ("titulo", "subtitulo", "objetivo", "stacks", "nivel")
        widgets = {
            "objetivo": forms.Textarea(attrs={"rows": 5, "placeholder": "Ex.: um app de lista de tarefas com login, para eu usar de verdade no dia a dia."}),
            "nivel": forms.RadioSelect,
            "stacks": forms.CheckboxSelectMultiple,
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # self.fields[...] é tipado como Field genérico, que não tem
        # `queryset`. O cast diz ao mypy o que a Meta.widgets já garante.
        campo = cast(forms.ModelMultipleChoiceField, self.fields["stacks"])
        campo.queryset = Stack.objects.all()
        # Sem instância ainda (criação): o campo nem aparece no template, e
        # marcá-lo obrigatório travaria o envio de um formulário que não pode
        # preenchê-lo. Com instância (edição), continua exigindo texto: um
        # título em branco quebraria toda tela que mostra o nome do projeto.
        if not self.instance.pk:
            self.fields["titulo"].required = False
        self.fields["subtitulo"].required = False

    def stacks_por_categoria(self):
        """As opções de stack agrupadas, na ordem das categorias.

        Uma lista corrida de 26 caixas não ajuda ninguém a escolher; agrupada,
        a pessoa varre só a seção que interessa. O agrupamento é feito aqui e
        não no template porque envolve casar cada opção do formulário com o
        objeto Stack. Lógica que em template vira sopa de `for` aninhado.
        """
        # Uma consulta só: as opções carregam a pk, e o mapa evita ir ao banco
        # uma vez por caixa de seleção.
        campo = cast(forms.ModelMultipleChoiceField, self.fields["stacks"])
        # `queryset` é Optional nos stubs; aqui o __init__ já o definiu, mas
        # o `or ()` deixa isso explícito em vez de depender da ordem.
        por_pk = {s.pk: s for s in (campo.queryset or ())}
        grupos: dict[str, list] = {}
        for opcao in self["stacks"]:
            stack = por_pk.get(opcao.data["value"].value)
            if stack is None:
                continue
            grupos.setdefault(stack.categoria, []).append(opcao)

        return [
            {
                "slug": categoria,
                "nome": rotulo,
                "opcoes": grupos[categoria],
            }
            for categoria, rotulo in Stack.Categoria.choices
            if categoria in grupos
        ]


class PassoForm(forms.ModelForm):
    """Edição manual de um passo.

    Critérios e armadilhas são listas no banco e texto na tela: uma linha por
    item. Pedir JSON a quem está corrigindo o próprio plano seria transferir a
    forma de armazenamento para a pessoa.
    """

    criterios_aceite = forms.CharField(
        label="Critérios de aceite",
        required=False,
        widget=forms.Textarea(attrs={"rows": 4, "placeholder": "Um por linha."}),
        help_text="Um por linha. Verificáveis: “o endpoint devolve 404 para id inexistente”, não “o código está bom”.",
    )
    armadilhas = forms.CharField(
        label="Onde costuma dar errado",
        required=False,
        widget=forms.Textarea(attrs={"rows": 3, "placeholder": "Uma por linha."}),
    )

    class Meta:
        model = Passo
        fields = ("titulo", "o_que_fazer", "como_fazer", "teoria", "o_que_enviar", "estimativa_min")
        widgets = {
            "o_que_fazer": forms.Textarea(attrs={"rows": 3}),
            "como_fazer": forms.Textarea(attrs={"rows": 4}),
            "teoria": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["estimativa_min"].label = "Estimativa (minutos)"
        self.fields["o_que_enviar"].label = "O que mandar para a revisão"
        self.fields["o_que_enviar"].help_text = "Uma frase: qual arquivo, função ou trecho."
        if self.instance and self.instance.pk:
            self.fields["criterios_aceite"].initial = "\n".join(self.instance.criterios_aceite or [])
            self.fields["armadilhas"].initial = "\n".join(self.instance.armadilhas or [])

    @staticmethod
    def _linhas(texto):
        return [linha.strip() for linha in (texto or "").splitlines() if linha.strip()]

    def save(self, commit=True):
        passo = super().save(commit=False)
        passo.criterios_aceite = self._linhas(self.cleaned_data.get("criterios_aceite"))
        passo.armadilhas = self._linhas(self.cleaned_data.get("armadilhas"))
        if commit:
            passo.save()
        return passo


class EtapaForm(forms.ModelForm):
    class Meta:
        model = Etapa
        fields = ("titulo", "objetivo")
        widgets = {"objetivo": forms.TextInput()}
