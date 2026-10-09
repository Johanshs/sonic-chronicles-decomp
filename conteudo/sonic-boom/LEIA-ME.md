# Sonic Boom: golpe POW novo com efeito visual próprio

Conteúdo **nosso** para o golpe POW 155 "Sonic Boom". Nada aqui veio do jogo: os quadros
são desenhados por código, e o `aplicar.py` só muda tabelas do seu projeto.

| Arquivo | O que é |
|---|---|
| `desenhar_sprites.py` | desenha os 8 quadros da onda de choque (32x32, 7 cores, alfa em 8 níveis) |
| `sprites/boom_f1.png` … `boom_f8.png` | os quadros gerados |
| `aplicar.py` | põe o golpe e o efeito num projeto do `sonic-mod` (tabelas, textos e arquivos do efeito) |

Para usar:

```
sonic-dump rom_original.nds dump                       # uma vez, para ter os moldes
python3 conteudo/sonic-boom/aplicar.py projeto dump/herf/test
sonic-mod pack rom_original.nds projeto rom_modificada.nds
```

**O Sonic Boom entra no lugar do Axe Kick.** Um herói tem no máximo 6 golpes POW, cada um
numa vaga com coreografia própria; um 7º golpe trava a tela "POW Moves" do perfil. O
golpe usa a coreografia do Axe Kick com a onda de choque nova no lugar do efeito dele, 3
PP e dano maior. Para tirar o Whirlwind em vez do Axe Kick:
`aplicar.py projeto dump/herf/test --no-lugar-do whirlwind` (essa variante ainda não foi
testada na batalha).

O `aplicar.py` gera `FX_SonicBoom.nsbmd/.nsbtx/.nsbtp` dentro do projeto. Esses três
arquivos usam o modelo da fumaça do jogo como molde, então **não vão para o Git**.
Como tudo foi descoberto e testado: [docs/DIARIO.md, seções 22 e 23](../../docs/DIARIO.md#23-como-um-pow-funciona-de-verdade-e-o-sonic-boom-consertado).
