# Imagens

Ambas em domínio público, reproduzidas de museus que liberam as obras do acervo
em alta resolução. Convertidas para tons de cinza e recomprimidas para web; o
enquadramento é o original.

| Arquivo | Obra | Autor | Acervo | Situação |
|---|---|---|---|---|
| `bambu.jpg` | *Bamboo* | Katsushika Hokusai (1760–1849) | The Metropolitan Museum of Art, 56.121.1 | Domínio público |
| `paisagem.jpg` | *Haboku-sansui* (paisagem em tinta esparramada) | Sesshū Tōyō (1420–1506) | via Wikimedia Commons | Domínio público |

Nanquim sobre papel dos dois lados: é a mesma família de gesto do ensō da marca,
e é o motivo de a escolha não ter caído em foto de banco de imagens.

## Preparo

`paisagem-tinta.png` é a obra de Sesshū com o papel removido: a luminância
invertida vira o canal alfa, então sobra só a tinta sobre transparência. É o que
permite a arte aparecer sobre o fundo dos dois temas sem virar um retângulo
colado na tela. No escuro basta inverter a cor, e o recorte continua valendo.

```
# 1. corta a moldura do scan, tira a cor
magick sesshu.jpg -gravity center -crop 92%x94%+0+0 +repage \
       -colorspace Gray -resize 640x base.png

# 2. alfa = negativo da luminância. O papel mede ~31% no negativo e a montanha
#    ao fundo, ~30%: o ponto de preto em 34% zera o papel e leva junto o mais
#    claro da montanha, que no original também é quase nada. O black-threshold
#    mata o respingo de digitalização. Alfa de até 8% espalhado, invisível no
#    tema claro e um véu branco no escuro.
magick base.png -negate -level 34%,90% -black-threshold 12% alpha.png

# 3. tinta preta chapada + esse alfa. Manter a luminância original junto
#    deixaria a tinta cinzenta e lavada sobre o papel do tema.
magick -size 640x1011 xc:black alpha.png -alpha off \
       -compose CopyOpacity -composite -strip paisagem-tinta.png
```

`bambu.jpg` continua sendo foto com o papel: ali a imagem preenche o painel
inteiro do login, e a textura do papel é parte do que se quer ver.
