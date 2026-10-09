# Sonic Boom: animação e efeito visual novos

Conteúdo **nosso** para o golpe POW 155 "Sonic Boom" (a receita do golpe está em
[docs/MODDING.md](../../docs/MODDING.md#adicionar-um-golpe-pow-novo)). Nada aqui veio do
jogo: os quadros são desenhados por código.

| Arquivo | O que é |
|---|---|
| `desenhar_sprites.py` | desenha os 8 quadros da onda de choque (32x32, 7 cores, alfa em 8 níveis) |
| `sprites/boom_f1.png` … `boom_f8.png` | os quadros gerados |
| `aplicar.py` | põe o efeito num projeto do `sonic-mod` (tabelas + arquivos do efeito) |

Para usar (depois de criar o golpe 155 no projeto):

```
sonic-dump rom_original.nds dump                       # uma vez, para ter os moldes
python3 conteudo/sonic-boom/aplicar.py projeto dump/herf/test
sonic-mod pack rom_original.nds projeto rom_modificada.nds
```

O `aplicar.py` gera `FX_SonicBoom.nsbmd/.nsbtx/.nsbtp` dentro do projeto. Esses três
arquivos usam o modelo da fumaça do jogo como molde, então **não vão para o Git**.
Como tudo foi descoberto e testado: [docs/DIARIO.md, seção 22](../../docs/DIARIO.md#22-conteúdo-novo-animação-e-efeito-visual-para-o-sonic-boom).
