from django import forms

from projetos.models import Etapa, Passo, Projeto, Stack


class ProjetoForm(forms.ModelForm):
    class Meta:
        model = Projeto
        fields = ("titulo", "objetivo", "stacks", "nivel", "horas_por_semana", "preferencia_didatica")
        widgets = {
            "objetivo": forms.Textarea(attrs={"rows": 5, "placeholder": "Ex.: um app de lista de tarefas com login, para eu usar de verdade no dia a dia."}),
            "nivel": forms.RadioSelect,
            "preferencia_didatica": forms.RadioSelect,
            "stacks": forms.CheckboxSelectMultiple,
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["stacks"].queryset = Stack.objects.all()
        self.fields["horas_por_semana"].help_text = "Serve para dimensionar os passos, não para cobrar ritmo."

    def stacks_por_categoria(self):
        """As opções de stack agrupadas, na ordem das categorias.

        Uma lista corrida de 26 caixas não ajuda ninguém a escolher; agrupada,
        a pessoa varre só a seção que interessa. O agrupamento é feito aqui e
        não no template porque envolve casar cada opção do formulário com o
        objeto Stack. Lógica que em template vira sopa de `for` aninhado.
        """
        # Uma consulta só: as opções carregam a pk, e o mapa evita ir ao banco
        # uma vez por caixa de seleção.
        por_pk = {s.pk: s for s in self.fields["stacks"].queryset}
        grupos = {}
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
        fields = ("titulo", "o_que_fazer", "como_fazer", "teoria", "estimativa_min")
        widgets = {
            "o_que_fazer": forms.Textarea(attrs={"rows": 3}),
            "como_fazer": forms.Textarea(attrs={"rows": 4}),
            "teoria": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["estimativa_min"].label = "Estimativa (minutos)"
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
