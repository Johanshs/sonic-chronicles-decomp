# Guia do painel de controle (v0.9)

Este é o "wiki" do painel: o que cada página, campo, ação e truque faz, como faz e o que
pode dar errado. O código está em [`modmenu/`](../modmenu/) e a história de como cada
coisa foi achada está no [`modmenu/README.md`](../modmenu/README.md) e no
[`docs/CHEATS.md`](CHEATS.md) (bateria de cheats; ele chega com o PR #36, então até lá o
link só funciona no branch daquele PR).

**Sumário**

1. [Abrir e usar](#1-abrir-e-usar)
2. [Mapa das páginas](#2-mapa-das-páginas)
3. [Receitas rápidas](#3-receitas-rápidas)
4. [Regras de combate](#4-regras-de-combate)
5. [Dificuldade dinâmica](#5-dificuldade-dinâmica)
6. [Anéis e XP](#6-anéis-e-xp)
7. [Grupo (personagens)](#7-grupo-personagens)
8. [Inimigos (batalha)](#8-inimigos-batalha)
9. [Ações rápidas](#9-ações-rápidas)
10. [Itens (inventário)](#10-itens-inventário)
11. [Truques (liga/desliga)](#11-truques-ligadesliga)
12. [O que fica no save e o que volta sozinho](#12-o-que-fica-no-save-e-o-que-volta-sozinho)
13. [Cheats do cartão e o painel](#13-cheats-do-cartão-e-o-painel)
14. [Palavras que aparecem aqui](#14-palavras-que-aparecem-aqui)

---

## 1. Abrir e usar

- **Abrir:** segure **L + R + SELECT** por meio segundo. O jogo pausa e a tela do
  "motor B" vira o painel. Na exploração ela é a tela de **cima**. Durante um
  carregamento o painel espera o carregamento acabar.
- **Teclas:**

| Tecla | O que faz |
|---|---|
| CIMA / BAIXO | escolhe a linha (a lista dá a volta) |
| A | entra na página, escolhe o personagem, faz a ação, dá ou tira o item |
| ESQUERDA / DIREITA | muda o valor em 1 (em 1000 nos números grandes: anéis e XP) |
| L / R | muda o valor em 10 (em 100000 nos números grandes) |
| B | volta uma tela |
| START | fecha o painel e o jogo continua de onde parou |

- **As colunas** das páginas de valores: o nome do campo, o valor atual e uma marca:
  - **emu**: conferido no emulador (escrevemos e vimos o jogo mudar);
  - **est**: só pela análise do código (estático). O valor é lido do lugar certo, mas
    ainda não vimos o efeito de mudá-lo no jogo.
- **Limites:** cada campo tem um mínimo e um máximo. O painel não deixa passar deles. Os
  limites protegem a tela do jogo (999999 é o maior número de anéis que cabe nela, por
  exemplo).
- **Por que o relógio não pula:** o jogo mede o tempo real entre duas voltas do laço
  principal. O painel avisa o relógio quando fecha, então o jogo não acha que passou um
  minuto de uma vez.

> **Antes de tudo:** faça backup do `.sav`. Tudo o que é do personagem, do grupo e da
> mochila vai para o save se você salvar depois de mexer.

## 2. Mapa das páginas

| Página | Serve para | Vai para o save? |
|---|---|---|
| Regras de combate (74) | os números que o combate usa nas contas | não (o jogo recarrega a cada boot) |
| Dificuldade dinâmica | o ajuste automático dos inimigos | não (só dura a sessão) |
| Anéis e XP | dinheiro e experiência do grupo | sim, se salvar |
| Grupo (personagens) | HP, PP, **pontos de POW**, golpes, atributos, resistências | sim, se salvar |
| Inimigos (batalha) | os atributos dos inimigos da luta atual | não (somem com a luta) |
| Ações rápidas | curar, nocautear, Chao | curar e Chao sim; a luta não |
| Itens (inventário) | dar e tirar qualquer item, mudar quantidades | sim, se salvar |
| Truques (liga/desliga) | os cheats de código: itens infinitos, loja grátis... | não (volta ao religar o DS) |

## 3. Receitas rápidas

**Mais pontos de POW (o pedido principal desta versão).**
1. Feche a tela de POW do jogo, se estiver nela (veja o cuidado abaixo).
2. L + R + SELECT → **Grupo** → escolha o personagem → **Pontos de POW**.
3. R soma 10, DIREITA soma 1. Vai até 999.
4. START. No menu do jogo: perfil do personagem → botão **POW Moves**. Os pontos
   aparecem em "Points" e servem para comprar níveis normalmente.

Conferido no emulador (save do Capítulo 10): o Sonic tinha 5 pontos; o painel subiu
para 55, a tela "POW Moves" mostrou **Points: 55**, comprar o **Axe Kick III** (custo 15)
deixou 40 pontos e o golpe no nível 3. Com 999 a tela também mostrou "999" sem problema.

> **Cuidado:** a tela "POW Moves" copia os pontos quando abre e só os grava de volta no
> personagem quando você aperta **Exit**. Se você abrir o painel por cima dela e mudar os
> pontos, o Exit grava o número antigo por cima do seu. (Isto é deduzido do que o cheat
> de POW mostrou; o painel em si foi testado com a tela fechada.)

**Outros caminhos para o POW:**
- **Subir o golpe direto:** na mesma página, "Golpe POW 1" a "Golpe POW 6" são os níveis
  (0 a 3) dos seis golpes, na ordem da tela do jogo (no Sonic: Axe Kick, Whirlwind,
  Blue Bomber, Fastball, Triple Tornado, Hail Storm). Escrever 3 = nível III sem gastar
  pontos.
- **Comprar sem gastar:** página **Truques** → "POW sem gastar pontos". Com ele ligado, a
  loja de golpes compra mesmo sem pontos e não desconta nada.

**Dinheiro:** Anéis e XP → "Aneis (carteira)" → R (soma 100000) até 999999.

**Todo mundo no nível 30:** Anéis e XP → "XP do grupo" → R até 2700000, depois vença
uma batalha. Não tem volta (veja a seção 6).

**Batalha difícil:** Ações rápidas → "Nocautear inimigos (pelo jogo)". A luta termina em
vitória normal, com XP e itens.

**Loja de graça:** Truques → "Loja de graca" → A.

**Todos os Chao:** Ações rápidas → "Chao: ganhar os 45 (nivel Max)".

## 4. Regras de combate

O jogo lê uma tabela de 74 números (`combatrules.gda`) no boot e copia cada um para uma
variável fixa. O combate usa essas variáveis nas contas. O painel mostra cada regra com
o número dela e um apelido. "?" quer dizer que ainda não sabemos o que ela faz.

**Formatos.** A maioria é um inteiro. Algumas guardam um número quebrado: o painel mostra
o valor como ele aparece na tabela do jogo (por exemplo, 0,90 aparece como 90 na regra
71) e converte ao gravar.

| Regras | Apelido no painel | O que fazem (valor original) |
|---|---|---|
| 1, 2, 3, 33 | inic: base, dado 1dN, x Speed, divisor | quem age primeiro na rodada (60, 1d2, ×1, ÷4) |
| 7, 8, 11 | Defender: Def, Grit, PP | o bônus de quem escolhe Defender (+70% Defense, +200% Grit, PP) |
| 39 | dano basico | o dano do ataque básico (100) |
| 43, 44, 45 | dano: fixo, k grupo, k inimigo | a parte fixa (90) e a parte da sorte do dano do grupo (110) e dos inimigos (60) |
| 47 | emboscada: dado | o dado da emboscada (10) |
| 57 a 70 | dific+/dific- | quanto cada nível da dificuldade dinâmica muda os inimigos (seção 5) |
| 71, 72, 73 | POW escala nv1/2/3 | multiplicador do minijogo de toque por nível do golpe (0,90 / 0,95 / 1,00) |
| 5, 6, 15 a 32, 48 a 50 | minijogo POW | o minijogo de toque e a câmera dos golpes POW |
| 40, 41, 42 | desempenho POW | como o desempenho no minijogo vira dano |
| 34, 53 | explor: combate | como o combate começa a partir do mapa |
| 35, 38 | GUI tempo real | a interface do combate em tempo real |
| 0 | nao usada | não aparece no código |

Exemplos testados pela bateria de cheats:
- **Regra 44 = 1000:** o dano do grupo fica cerca de 4 vezes maior. **0:** o dano perde a
  parte da sorte (sempre 0,9 × Power, e o crítico deixa de valer a pena).
- **Regra 45 = 300:** os inimigos batem 2 vezes mais. **0:** batem sempre o mínimo.
- **Regra 8 = 100:** quem defende fica com Grit ×11 em vez de ×3.

Detalhes e fórmulas: [`docs/COMBATE.md`](COMBATE.md), seções 3 a 8 e 15.

> **Cuidado:** não vão para o save; ao religar o DS tudo volta. Mesmo assim, valores
> absurdos (negativos, gigantes) podem fazer contas estranharem. Mude um de cada vez e
> anote o original (ele aparece no painel antes de você mexer).

## 5. Dificuldade dinâmica

O jogo ajusta os inimigos conforme você vai: depois de uma batalha longa (6 rodadas ou
mais) o nível desce 1; depois de uma curta (3 a 5), sobe 1.

| Campo | O que é |
|---|---|
| Nivel (-4 a +6) | o nível de ajuste atual. +6: inimigos com Power +9, Attack +3, HP máximo +60. −4: Power −10, Defense −4, Attack −4, Grit −10. Os níveis ±1 não mudam nada (a conta usa divisão inteira por 2). |
| Chave (0/1) | liga o ajuste. O jogo só liga depois de certo ponto da história. Marcada **est**. |

O nível muda sozinho no fim de cada batalha, então um valor posto pelo painel não fica
"travado" (para travar, use o cheat do cartão da pasta "dificuldade dinâmica").
Detalhes: [`docs/COMBATE.md`](COMBATE.md), seção 14.

## 6. Anéis e XP

| Campo | O que é | Passos |
|---|---|---|
| Aneis (carteira) | os anéis que você gasta (os da tela de Inventário e de save), de 0 a 999999 | ◀▶ 1000, L/R 100000 |
| XP do grupo | a experiência, uma só para o grupo todo, de 0 a 2700000 | ◀▶ 1000, L/R 100000 |

- **A carteira não é o contador do HUD.** O "x/185" do canto da tela é outro número, o
  dos anéis da área. O painel mexe no que você gasta.
- **Como o XP vira nível:** cada personagem converte o mesmo XP em nível pela sua própria
  tabela. O nível 30 pede de 952810 (Rouge) a 2643707 (Eggman); 2700000 passa de todos.
- **Quando sobe:** só no fim da próxima batalha vencida (a tela "Level Up!" aparece e dá
  os pontos de bônus). Baixar o XP depois **não** desce o nível.

> **Cuidado:** subir de nível não tem volta. Se salvar depois, fica no save.

## 7. Grupo (personagens)

A primeira tela lista todos os personagens que já entraram no grupo (11 no fim do jogo),
com o HP. Escolha um com A. A tela seguinte tem os atributos dele:

| Campo | O que faz no jogo | Limites |
|---|---|---|
| HP | vida atual. 0 = nocauteado (mas veja a nota abaixo) | 0 a 9999 |
| HP maximo | vida máxima | 1 a 9999 |
| PP | pontos para usar golpes POW | 0 a 999 |
| PP maximo | o máximo de PP | 0 a 999 |
| **Pontos de POW** | os pontos que a tela "POW Moves" gasta para subir golpes. Vêm com os níveis. | 0 a 999 |
| Golpe POW 1 a 6 (0-3) | o nível de cada um dos 6 golpes, na ordem da tela. 0 = ainda não tem; 3 = nível III | 0 a 3 |
| Speed | quem age primeiro: a 1ª ação sai em `max(0, 60 − Speed) + 1d2` | 0 a 999 |
| Attack (acerto) | a chance de acertar: o golpe acerta se `Defense do alvo ≤ Attack + 1d20` | 0 a 999 |
| Defense (esquiva) | o outro lado da mesma conta: quanto maior, mais o inimigo erra | 0 a 999 |
| Power (dano) | a base do dano | 0 a 999 |
| Grit (armadura) | armadura: é subtraída do dano recebido | 0 a 999 |
| Luck | a chance de crítico: crítico se `1d100 < Luck` | 0 a 999 |
| Acoes por rodada | quantas vezes ele age por rodada (no Capítulo 10: Sonic 3, Tails e Rouge 2, Omega 1) | 1 a 9 |
| Resist. Fogo/Agua/Terra/Vento/Raio/Gelo % | resistência a cada elemento. 100 = imune, 0 = normal, negativo = fraqueza. O dano daquele elemento é multiplicado por `1 − R/100` | −100 a 100 |

Notas:
- **Power e Grit estão marcados "est"** porque o jogo não mostra esses dois em nenhuma
  tela: o lugar foi achado pelo código e pela tabela de atributos, mas não deu para ver o
  número mudar na tela como nos outros. O efeito vem pelo dano (ver `docs/COMBATE.md`).
- **HP e nocaute:** pôr o HP de alguém em 0 escrevendo o número **não** nocauteia (o jogo
  só nocauteia pela função dele; foi assim que descobrimos o "Nocautear" da seção 9).
- **Golpe no nível 0 posto em 3:** ele aparece normal nas telas de POW (testado no Sonic e
  no Tails), mas ainda não usamos um golpe assim numa batalha.
- Os golpes e os pontos ficam no save se você salvar.

## 8. Inimigos (batalha)

Só tem gente dentro de uma batalha: a lista mostra os inimigos da luta atual, com nome e
HP. Escolhendo um, os campos são os **mesmos** da página do grupo (o jogo guarda inimigos
e personagens no mesmo formato). Para inimigos, mexer em HP, Speed, Attack, Defense, Power,
Grit, Luck, ações por rodada e resistências faz sentido; os campos de POW existem no vetor
mas os inimigos não os usam.

Fora da batalha a lista fica vazia. Nada daqui vai para o save: os inimigos somem quando a
luta acaba.

## 9. Ações rápidas

| Ação | O que faz | Como |
|---|---|---|
| Curar o grupo (HP e PP cheios) | todo o grupo com HP = HP máximo e PP = PP máximo, de uma vez | escreve os números. Quem está nocauteado não é mexido (use um item de reviver) |
| Inimigos com HP 1 | os inimigos da luta ficam com 1 de HP: qualquer golpe derruba | escreve o número |
| Nocautear inimigos (pelo jogo) | derruba todos os inimigos e a luta acaba em **vitória** normal (tela VICTORY, XP, item, subida de nível) | chama a função que todo golpe do jogo usa para mudar um atributo, pedindo HP 0. É ela que avisa a criatura e faz o nocaute de verdade |
| Chao: os seus no nivel Max | os Chao que você já tem vão para o nível Max | nível 3 em quem tem cópias |
| Chao: ganhar os 45 (nivel Max) | todos os 45 Chao, inclusive os 5 que só vinham por troca sem fio (40 a 44, como o Pooki e o Farfinkle) | nível 3 e pelo menos 1 cópia em cada um |

**Chao, por dentro:** cada Chao ocupa 10 bytes no esquadrão (a partir de `+0x424`):
número (0 a 44), nível (0 = não tem, 3 = Max) e cópias. O jardim conta quem tem cópias, por
isso "ganhar os 45" também põe 1 cópia em quem tinha 0. Antes de escrever, o painel confere
que a tabela está no formato esperado (o número de cada registro igual à posição); se não
estiver, ele recusa. Conferido no save do Capítulo 10: os 40 que você tinha ficaram como
estavam (já eram Max) e os 5 de troca entraram com nível 3 e 1 cópia. A bateria de cheats
viu o jardim mostrar "45/45, Maxed: 45" com esses mesmos bytes.

> **Cuidado:** Chao e curas vão para o save se salvar. O efeito dos 5 Chao de troca na
> batalha ainda não foi testado.

## 10. Itens (inventário)

A primeira linha é **dar**: ◀▶ e L/R escolhem o número do item (0 a 287, as linhas da
tabela `Items.gda`); o nome aparece embaixo, lido do texto do próprio jogo. A dá 1 unidade.

As linhas seguintes são as pilhas da mochila (nome e quantidade):
- **◀▶ / L/R** mudam a quantidade (1 a 99; o jogo recusa mais de 99);
- **A tira 1 unidade.** Na última, a pilha some.

Dar e tirar usam as **funções do próprio jogo** (as mesmas das recompensas e do combate),
então o item fica montado do jeito que o jogo espera. Antes de chamar, o painel confere os
primeiros bytes da função; se não baterem, recusa ("recusou").

> **Cuidados:**
> - **Não tire itens de história** (chaves, objetos de missão). Ao tirar a última unidade,
>   o jogo desliga a marca que diz que o grupo tem aquele item, e a história pode travar.
> - Itens vão para o save se salvar.

## 11. Truques (liga/desliga)

Estes são os **cheats de código** da bateria: em vez de mudar um número, eles trocam
instruções do programa do jogo na memória. A (ou ◀▶) passa para o próximo estado. Ao
religar o DS, tudo volta ao normal.

| Truque | Estados | O que faz | Trocas (endereço: original → novo) |
|---|---|---|---|
| Itens nao acabam | desligado / LIGADO | usar um item não gasta | `0202DB4C`: `DD07`→`46C0`, `0202DB4E`: `1E49`→`46C0` |
| Pegar aneis da area | desligado / LIGADO | todo anel da área é pego na hora, de longe | `02017A56`: `D035`→`46C0`, `02017A88`: `D01C`→`46C0` |
| Loja de graca | desligado / LIGADO | o botão "Buy Item" fica sempre aceso e comprar não gasta anéis | `020B2EC0`: `DC00`→`46C0`, `020B3AD0`: `DB15`→`46C0`, `020B3AD2`: `1A51`→`1C11` |
| POW sem gastar pontos | desligado / LIGADO | a loja de golpes compra sem conferir nem gastar pontos | `0209451C`: `DC11`→`46C0`, `0209457A`: `1B01`→`1C01` |
| Aneis por anel | x1 / x2 / x5 / x10 | cada anel pego soma 2, 5 ou 10 na carteira | `02017648`: `1C49`→`3102`/`3105`/`310A` |
| Andar mais rapido | x1 / x2 / x4 | o grupo anda no mapa 2 ou 4 vezes mais rápido (a colisão continua) | `02034B92`: `0320`→`0360`/`03A0` |

**Como funcionam (exemplo do "Itens nao acabam"):** a função do jogo que tira um item faz
"se a quantidade é 1, apague o item" (`DD07`) e "quantidade − 1" (`1E49`). O truque troca
as duas por `46C0`, uma instrução que não faz nada. Sem elas, o jogo grava a mesma
quantidade de volta. Os efeitos de cada truque foram medidos pela bateria de cheats
(tabelas antes/depois em [`docs/CHEATS.md`](CHEATS.md)); o painel escreve os mesmos bytes,
conferido no emulador.

**Por que o painel limpa o cache:** o processador do DS guarda pedaços do programa num
cache de instruções. Se ele já tiver a instrução antiga guardada, trocar a memória não
basta: ele continuaria rodando a velha. Depois de cada troca, o painel manda o
processador gravar o que mudou e esquecer as instruções guardadas. (O emulador não
simula esse cache, então esta parte só se prova no DS de verdade.)

**"?" no estado:** o painel só mexe se encontrar exatamente o original ou um dos estados
dele. Se outro cheat trocou aquelas instruções por outra coisa (o cheat público de POW,
por exemplo, só faz a primeira troca), ele mostra "?" e avisa "mexido por outro cheat:
nao mexo".

> **Cuidados:**
> - **Itens não acabam + loja:** a mesma função serve para vender. Com o truque ligado,
>   vender um item dá os anéis e o item continua lá. Desligue antes de ir à loja se não
>   quiser dinheiro infinito.
> - **Itens não acabam + tirar pelo painel:** funciona. O painel desliga o truque por um
>   instante, tira o item e liga de novo (conferido no emulador).
> - **Não use junto com o mesmo cheat ligado no cartão:** o cheat do cartão regrava as
>   instruções a cada quadro, então desligar pelo painel não adiantaria.

## 12. O que fica no save e o que volta sozinho

| Volta sozinho ao religar o DS | Fica no save se você salvar |
|---|---|
| regras de combate, dificuldade, truques | anéis, XP (e os níveis que ele der), atributos do grupo, pontos e níveis de POW, itens, Chao |

Faça backup do `.sav` antes de salvar depois de mexer. No R4, o save fica ao lado da ROM
no cartão SD (mesmo nome, `.sav`).

## 13. Cheats do cartão e o painel

O que cada pasta da bateria de cheats ([`docs/CHEATS.md`](CHEATS.md)) tem no painel. A
diferença geral: o cheat do cartão regrava o valor **a cada quadro** (fica "travado"); o
painel grava **uma vez** e o jogo segue dali.

| Pasta de cheats | No painel |
|---|---|
| dano do grupo (regra 44) | Regras → R44 |
| dano dos inimigos (regra 45) | Regras → R45 |
| defender | Regras → R7, R8 |
| dificuldade dinâmica | Dificuldade (sem travar: o jogo muda o nível a cada luta) |
| anéis e itens: anéis 999999 | Anéis e XP → carteira |
| anéis e itens: itens não acabam, pegar anéis, loja | Truques |
| multiplicador de anéis | Truques → Aneis por anel |
| velocidade de andar | Truques → Andar mais rapido |
| POW: compra sem gastar pontos | Truques → POW sem gastar pontos |
| POW: 99 pontos / golpes no III | Grupo → personagem → Pontos de POW, Golpe POW 1 a 6 |
| XP | Anéis e XP → XP do grupo |
| Chao | Ações rápidas → Chao |
| grupo: HP cheio | Ações rápidas → Curar o grupo (uma vez, não sempre) |
| grupo: Defense, Luck, Speed, Power, PP, ações, elementos | Grupo → personagem → o campo |

## 14. Palavras que aparecem aqui

- **Ponto fixo:** o jogo guarda alguns números quebrados como inteiros multiplicados por
  4096 (o PP e as resistências, por exemplo). O painel mostra o número normal e faz a
  conta ao gravar.
- **Heap:** a área de memória onde o jogo cria os objetos (personagens, mochila). Os
  endereços mudam conforme o jogo, por isso o painel os acha seguindo ponteiros a partir
  de endereços fixos.
- **vtable:** o primeiro campo de todo objeto C++ do jogo; diz de que tipo ele é. O
  painel confere a vtable antes de escrever, para não mexer em algo que não é o que ele
  pensa.
- **Patch de código:** trocar instruções do programa (como os truques). As instruções
  aqui são Thumb, de 2 bytes cada, escritas em hexadecimal.
- **Esquadrão:** o objeto do jogo que guarda o grupo do jogador: carteira, mochila, XP,
  Chao.
