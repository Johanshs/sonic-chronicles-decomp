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

### Adicionar um golpe POW novo
1. Em `tabelas/test/combo.csv`, copie a linha de um golpe parecido para o fim e dê um
   `ID` novo (o jogo original vai até 154). Ajuste `Cost` (PP), `Damage1..3` (dano em %
   por nível) e as marcas (`Inescapable`, `ElementalDamage`, `ArmorPiercing`...).
2. Textos novos em `textos/en.csv` para `NameStrRef`, `DescriptionStrRef` e os
   `DamageStrRef1..3` (o que aparece na tela do golpe); `EffectStrRef1..3` pode
   reaproveitar um texto do jogo.
3. Dê o golpe a alguém: em `creatures.csv`, ponha o ID do golpe numa coluna
   `Combo1`…`Combo10` livre do personagem (o Sonic usa de `Combo1` a `Combo6`).

Testado no emulador com o golpe 155 "Sonic Boom" (3 PP) no `Combo7` do Sonic: ele
aparece na lista de POW Moves com o nome, o custo e a descrição novos, gasta exatamente
3 PP e, ao ser usado, o jogo calcula o dano pela linha 155 (duas vezes, o "2x" do golpe).
Confira com `analise/tools/testar_golpe.py`. O dano em si depende do minijogo de toque,
que ainda não sabemos jogar bem de forma automática.

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
