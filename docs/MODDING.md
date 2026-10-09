# Projeto de mod do Sonic Chronicles

Esta pasta foi criada por `sonic-mod unpack`. Edite o que quiser e gere a ROM:

```
sonic-mod pack rom_original.nds esta_pasta rom_modificada.nds
```

O `pack` compara tudo com a ROM original e **só regrava o que mudou**. Ele mostra
um relatório do que foi alterado e confere a ROM gerada antes de salvar. Jogue a
ROM modificada num emulador (melonDS ou DeSmuME). Faça um save novo, porque
saves antigos podem não combinar com tabelas alteradas.

> Uso pessoal. Esta pasta contém dados do jogo (SEGA/BioWare): não publique.
> Para compartilhar um mod, compartilhe só os arquivos que você mudou.

## O que tem aqui

| Pasta | Conteúdo | Como editar |
|---|---|---|
| `tabelas/test/` | 229 tabelas do jogo (itens, criaturas, lojas, áreas...) | LibreOffice Calc ou VS Code |
| `textos/` | todos os textos, um arquivo por idioma (`en`, `fr`, `de`, `es`, `it`) | idem |
| `arquivos/test/` | tabelas em texto: efeitos de itens (`.ITM`), golpes (`.SPL`)... | qualquer editor de texto |

**Planilhas:** salve como CSV em UTF-8, separado por vírgula. Evite o Excel: ele
converte números como `1.5` em datas e corta casas decimais. Prefira o LibreOffice
(ao abrir, escolha UTF-8 e vírgula) ou o VS Code. O `pack` também aceita `;`.

**Tipos das colunas:** o `pack` sabe o tipo de cada coluna pela tabela original e
avisa com arquivo, linha e coluna se algo não encaixar:
- números inteiros: `ID`, `Name` (que é um **id de texto**), `HitPoints`...
- números com casas (ponto fixo do DS): `MoveSpeed`, `ScaleModifier`... (ex.: `150.0`)
- textos/nomes de arquivo: só ASCII, sem acentos (ex.: `ITM_ACE_seed_`); célula vazia = nenhum
- colunas `col_xxxxxxxx`: o nome original ainda é desconhecido (só temos o hash)

**Textos:** `textos/en.csv` tem `id,texto`. Os textos aceitam acentos do português
(o jogo usa cp1252). Caracteres fora dele, como emojis, viram `?` e o `pack` avisa.
Ids que você criar devem ser números novos e altos (ex.: a partir de `990000`),
para não colidir com os do jogo.

## Receitas

### Mudar atributos de um personagem
`tabelas/test/creatures.csv`. As linhas 0 a 9 são os jogáveis (0 Sonic, 1 Knuckles,
2 Tails, 3 Amy, 4 Shadow, 5 Rouge, 6 Big, 7 Cream, 8 Omega, 9 Eggman); as
seguintes são inimigos. Colunas: `HitPoints`, `Attack`, `Defense`, `Speed`,
`Health`, `Power`, `Grit`, `Luck`, `MoveSpeed`... A curva de evolução fica em
`tabelas/test/Adv_<Personagem>.csv`.

### Renomear qualquer coisa
Ache o texto em `textos/en.csv` (ex.: `15877,Health Seed`) e troque. Para o nome de
um personagem, veja a coluna `NameStrRef` de `creatures.csv`. Para um item, veja a
coluna `Name` de `Items.csv`.

### Mudar um item
`tabelas/test/Items.csv`: `Name` e `Description` (ids de texto), `Type`/`SubType`,
`BaseItem1` (arquivo de efeitos), ícones, `MinimumCost` (preço). Os efeitos ficam em
`arquivos/test/ItemN.ITM`. Por exemplo, `Item1.ITM` (Health Seed) tem
`HealHP ... 50`, e trocar o 50 muda quanto o item cura.

### Adicionar um item novo
1. Em `Items.csv`, copie a linha de um item parecido para o fim e dê um `ID` novo
   (o próximo número livre: o jogo original vai até 287).
2. Crie dois textos novos em `textos/en.csv`, por exemplo `990100,Chili Dog` e
   `990101,Restores 321 HP.`, e ponha `990100` em `Name` e `990101` em `Description`.
3. Copie `arquivos/test/Item1.ITM` para `arquivos/test/Item288.ITM`, edite os
   efeitos (ex.: `HealHP ... 321`) e ponha `Item288.ITM` em `BaseItem1`. Arquivos
   com nome novo são **adicionados** ao pacote.
4. Para o item aparecer no jogo, coloque-o numa loja: em `Store1.csv`... `Store5.csv`
   acrescente uma linha `N,288,15,7` (as colunas ainda não têm nome; são o **ID do
   item**, o **preço de compra** e o **preço de venda**). Ou numa recompensa
   (`rewards.csv`).

Testado no emulador com o item 288 "Chili Dog" (cura 321 HP) nas 5 lojas: ele aparece
na lista da loja (no topo; a regra de ordem da lista ainda não é conhecida), a
descrição e o "HP +321" saem do texto novo e do `.ITM`, a compra tira 15 anéis, o item
entra no inventário em "Consumables" e, usado no Sonic, o HP sobe exatamente 321.
O roteiro que prova isso é `analise/tools/testar_item_loja.py` no repositório.
Ainda não testado: o texto só existe em inglês (se o DS estiver em outro idioma, crie
também em `fr.csv`, `de.csv`...), e itens de equipamento ou Chao novos.

### Dar a um herói uma habilidade de inimigo
A habilidade de um equipamento vem de duas colunas de `Items.csv`: `col_ab33ab1a` (o
código) e `col_dee49bb0` (o valor). Os inimigos ganham Phased e afins "equipando" itens
escondidos com esses códigos: 25 Phased (todo ataque erra), 26 Evading (erra o que não
for "Can't miss"), 27 auto-reparo, 31 imunidade. Para um herói, crie um acessório como
em "Adicionar um item novo" copiando a linha de um acessório (ex.: 63, Refresher) e
ponha o código e o valor nessas colunas. `conteudo/itens-de-inimigo/aplicar.py` faz isso
para os quatro. Testado no emulador: compra, equipa, o jogo passa a dizer que o herói tem
a habilidade, e a Evasion Band fez um ataque inimigo errar a Tails.

### Adicionar um golpe POW novo
Um herói tem **no máximo 6 golpes POW**, e cada um ocupa uma **vaga** com coreografia
própria. Por isso um golpe novo entra **no lugar** de um golpe do personagem.

| Vaga (`creatures.csv`) | `Combo1` | `Combo2` | `Combo3` | `Combo4` | `Combo5` | `Combo6` |
|---|---|---|---|---|---|---|
| Coreografia (linha de `animations.csv`) | 21 | 12 | 23 | 24 | 25 | 26 |

1. Em `tabelas/test/combo.csv`, copie a linha do golpe que vai sair para o fim e dê um
   `ID` novo (o jogo original vai até 154). Ajuste `Cost` (PP), `Damage1..3` (dano em %
   por acerto, por nível) e as marcas (`Inescapable`, `ElementalDamage`,
   `ArmorPiercing`...). Mantenha a coluna `col_9185ff28` (a coreografia da vaga).
2. Textos novos em `textos/en.csv` para `NameStrRef`, `DescriptionStrRef` e os
   `DamageStrRef1..3` (o que aparece na tela do golpe); `EffectStrRef1..3` pode
   reaproveitar um texto do jogo.
3. Em `creatures.csv`, troque o ID do golpe antigo pelo do novo na mesma vaga
   (`Combo1`…`Combo6`). **Não use `Combo7` a `Combo10`**: testamos, e a tela "POW Moves"
   do perfil (onde se gastam os pontos de POW) trava.

O golpe novo herda o nível que o save tinha naquela vaga. O roteiro pronto do "Sonic
Boom" (no lugar do Axe Kick) é `conteudo/sonic-boom/aplicar.py`. Testado no emulador:
aparece na lista da batalha e na tela "POW Moves", gasta 3 PP, dá os 2 acertos e a
batalha segue. Confira um golpe seu com `analise/tools/testar_golpe.py ... 1500
--acertos 2 --auto`.

### Dar um efeito visual próprio a um golpe
| Tabela | O que diz |
|---|---|
| `combo.csv`, coluna `col_9185ff28` | a **coreografia** do golpe: a linha de `animations.csv` da vaga (tabela acima) |
| `animations.csv` | o arquivo de animação 3D de cada personagem (`?` = prefixo + nome da linha; ex.: linha 21 do Sonic = `SON_CB_KD`, o Axe Kick) |
| `AnimationEvents.csv` | o roteiro, quadro a quadro, para cada personagem (`Skeleton` 0 = Sonic): 10003/10004 abrem e fecham o minijogo, 10001 é um acerto, 10006 termina o golpe, 2 é som, 12 é câmera, **46 cria o efeito visual** da linha `EventData` de `VFX.csv` |
| `VFX.csv` | o efeito: `Type` 3 = modelo 3D (`.nsbmd`) + textura (`.nsbtx`) + troca de textura (`.nsbtp`), com `LifeTime`, `Target`, `Scale`... |

Receita (é o que `conteudo/sonic-boom/aplicar.py` faz):
1. Em `VFX.csv`, uma linha nova no fim (o jogo vai até 466) com os seus arquivos.
2. Os arquivos do efeito vão em `arquivos/test/`. Para desenhar a textura com quadros
   PNG seus, use `analise/tools/montar_vfx.py` (8 quadros de 32x32, até 32 cores; ele usa
   a fumaça do jogo como molde e troca só o desenho).
3. Em `AnimationEvents.csv`, no roteiro da vaga do golpe e do personagem (`Animation` =
   a coreografia, `Skeleton` = o personagem), troque o `EventData` do evento 46 pelo seu
   efeito. Esse roteiro é do personagem naquela vaga: o golpe que saiu da vaga não o usa
   mais.

O que **não** funciona (testado): criar linhas novas em `animations.csv` (a batalha trava),
usar uma linha que não é vaga, como a 13 (o golpe se repete sem parar ou o personagem fica
parado), e efeitos 2D (`Type` 1, `.NCGR`/`.NCER`/`.NANR`), que não aparecem na batalha.
Para testar sem jogar o minijogo: `testar_golpe.py ... --vfx N --auto --acertos 2` (o
`--auto` faz como o Chao 38, que acerta o minijogo sozinho). O savestate tem de ser da
mesma ROM: o jogo lê as tabelas ao ligar.

### Remover um item
Prefira **tirar o item das lojas e recompensas** a apagar a linha de `Items.csv`.
Outras tabelas se referem aos itens pelo ID, e apagar a linha pode deixar
referências quebradas.

### Personagens novos
Um personagem novo **jogável** precisa de modelo 3D, animações, golpes e
retratos, e o código do jogo pode limitar o número de personagens. Isso depende
da decompilação (veja `docs/PLANO-DECOMPILACAO.md` no repositório
https://github.com/Johanshs/sonic-chronicles-decomp). O que já dá
para fazer é uma **variação**: mudar nome, atributos, golpes e retratos de um
personagem existente ou de um inimigo em `creatures.csv`.

## Problemas?
- `a linha tem N colunas`: o editor juntou ou separou colunas. Confira as aspas.
- O jogo trava: volte a mudança e aplique metade dela de cada vez, para descobrir
  qual linha causa o problema. Guarde sempre a ROM original intacta.
