import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('projetos', '0006_passo_o_que_enviar'),
        ('mentoria', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='conversa',
            name='projeto',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='conversas', to='projetos.projeto'),
        ),
        migrations.AddField(
            model_name='conversa',
            name='passo',
            field=models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='conversa', to='projetos.passo'),
        ),
        migrations.AddConstraint(
            model_name='conversa',
            constraint=models.UniqueConstraint(condition=models.Q(('passo__isnull', True)), fields=('projeto',), name='uma_conversa_geral_por_projeto'),
        ),
    ]
