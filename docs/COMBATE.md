# O combate por dentro

Como o Sonic Chronicles decide quem age primeiro, quem acerta, quanto dano sai, como os
golpes POW, os status, os itens e os Chao entram na conta. Tudo aqui saiu de duas fontes:

- **o código do ARM9** (pseudo-C do Ghidra; funções pequenas executadas isoladas no
  [Unicorn](https://www.unicorn-engine.org/) para conferir o que fazem);
- **as tabelas do jogo** (GDA e os arquivos de efeito `.ITM`/`.SPL`), lidas com o
  `sonic-mod unpack`.

> **Sem dados do jogo aqui além do necessário para explicar.** As tabelas completas
> (todos os golpes, efeitos, itens e criaturas) são geradas a partir da sua cópia:
> ```
> sonic-mod unpack rom.nds meu_mod
> python3 analise/tools/combate_tabelas.py meu_mod      # gera meu_mod/combate/*.md
> ```

## Como ler este documento

Cada afirmação tem um nível de confiança:

| Nível | Quer dizer |
|---|---|
| **Alta** | li o código e ele bate com os dados (e, quando dava, executei a função no Unicorn) |
| **Média** | li o código, mas um passo da interpretação é dedução (o nome de um campo, a unidade de um valor) |
| **Baixa** | dedução a partir dos dados, dos nomes ou dos textos do jogo; o código ainda não foi lido |

Endereços são do ARM9 da versão americana (`YWSE`). "Regra N" é a linha N da tabela
`CombatRules` (seção 14). `1dN` é um dado de N faces (`Rules_RollDice`, 0x02008550).
Os nomes das funções estão em [`analise/symbols_manual.txt`](../analise/symbols_manual.txt).

## Sumário
1. [Uma batalha, do começo ao fim](#1-uma-batalha-do-começo-ao-fim)
2. [Atributos](#2-atributos)
3. [Ordem de ação (iniciativa)](#3-ordem-de-ação-iniciativa)
4. [Emboscada](#4-emboscada)
5. [Ataque básico](#5-ataque-básico)
6. [Aplicação do dano, elementos e resistências](#6-aplicação-do-dano-elementos-e-resistências)
7. [Defender](#7-defender)
8. [Golpes POW](#8-golpes-pow)
9. [O sistema de efeitos (.SPL e .ITM)](#9-o-sistema-de-efeitos-spl-e-itm)
10. [Status (buffs e debuffs)](#10-status-buffs-e-debuffs)
11. [Habilidades especiais](#11-habilidades-especiais)
12. [Itens](#12-itens)
13. [Inimigos](#13-inimigos)
14. [Dificuldade dinâmica](#14-dificuldade-dinâmica)
15. [CombatRules: as 74 regras](#15-combatrules-as-74-regras)
16. [O que ainda não sabemos](#16-o-que-ainda-não-sabemos)
17. [Como conferir](#17-como-conferir)

---

## 1. Uma batalha, do começo ao fim

```
encontro (exploração) ─► GameModeCombat vfunc02 (0x02039af4)
   ├─ ajusta o nível de dificuldade dinâmica ............ seção 14
   ├─ decide a emboscada (AmbushValue, Chao) ............. seção 4
   └─ loop de rodadas
        ├─ Combat_BuildTurnQueue (0x020448c0): fila por iniciativa ... seção 3
        ├─ cada ação: Atacar / Defender / POW / Item / Fugir
        │     ├─ Combat_ResolveAttack (0x0200f804) → acerto ......... seção 5
        │     ├─ Combat_BasicAttackDamage / Combat_PowDamage ....... seções 5 e 8
        │     └─ Combat_ApplyDamage (0x02011ac4) + resistências .... seção 6
        └─ efeitos por rodada (veneno, regeneração, PP) ............. seções 9–11
fim: XP e itens (squads, rewards, RandItems); ajuste da dificuldade
```

## 2. Atributos

Os atributos são números de uma tabela por criatura. O código não usa a coluna
diretamente: chama `StatsRedirect_Map` (0x020083d0), que converte o **atributo
lógico** *n* na coluna *n + 1* de `StatRedirect.gda`, e depois `Stats_GetInt`
(0x02007ab0), cujo terceiro argumento escolhe o valor **base** (1) ou o **atual**, com
bônus (0). **Confiança: alta.**

| Nº | Atributo | Para que serve |
|---|---|---|
| 0 | HP | vida atual |
| 21 | Speed | iniciativa (seção 3), fuga e perseguição |
| 22 | Attack | chance de acertar |
| 23 | Defense | chance de ser errado |
| 24 | HP máximo | |
| 25 | Power | dano ("damage rating"; o jogo não mostra) |
| 26 | Grit | armadura: subtraída do dano (o jogo não mostra) |
| 27 | Luck | crítico, emboscada |
| 28 | PP | "Fatigue" nas tabelas: os pontos para golpes POW |
| 36 | PP máximo | |
| 39–54 | marcas de status | atributo 39 + ID do status (seção 10) |
| 70 | Classe | 0 e 4 = Power, 1 e 3 = Support, 2 = Shifter (`classes.gda`) |
| 75–80 | resistência a Fogo, Água, Terra, Vento, Raio, Gelo | em %, seção 6 |
| 90–121 | dano elemental | > 0 liga o elemento no ataque; 107–112 = os 6 elementos |
| 122 | desconto no custo dos POW | item Economizer |
| 123 | ações por rodada | `NumActions` de `creatures.gda` |

Os valores iniciais estão em `creatures.gda` (colunas `HitPoints`, `Speed`, `Attack`,
`Defense`, `Health`, `Power`, `Grit`, `Luck`, `Fatigue`, `MaxFatigue`, `NumActions`) e
crescem pelas curvas `Adv_<personagem>.gda` (30 linhas, uma por nível: `XP` acumulado
para chegar ao nível, e os atributos). Exemplo, Sonic: nível 1 tem Speed 7, Attack 8,
Defense 14, HP 33, Power 8, Grit 2, Luck 3, PP 7; nível 30 tem 65, 64, 57, 570, 57, 31, 38, 22.
As colunas `PlayerChoice` e `Combat` das curvas ainda não têm significado confirmado
(**baixa**: parecem pontos a distribuir e pontos de POW).

## 3. Ordem de ação (iniciativa)

`Combat_BuildTurnQueue` (0x020448c0). **Confiança: alta.**

No começo de cada rodada, cada combatente vivo (até 4 por lado) recebe **uma entrada na
fila por ação** que tem (atributo 123, ações por rodada). O "tempo" de cada entrada é:

```
1ª ação:  t₁ = max(0, R1 − Speed × R3) + 1dR2
ação n+1: tₙ₊₁ = tₙ + max(R1 / R33, R1 − Speed × R3) + 1dR2
          R1 = regra 1 = 60   R2 = regra 2 = 2   R3 = regra 3 = 1   R33 = regra 33 = 4
```

A fila é ordenada pelo tempo, do menor para o maior (`ActionQueue_InsertByTime`,
0x0204516c). Como o grupo do jogador é inserido primeiro e um empate entra **depois** dos
iguais, **o grupo vence os empates**.

O que isso significa na prática:

- Speed baixa espaça as ações: Sonic no nível 1 (Speed 7, 3 ações) age em ~54, ~107, ~160.
- O espaço entre ações nunca é menor que 60/4 = 15: com Speed ≥ 45 todas as ações
  ficam a 15 de distância, e um personagem rápido com várias ações age várias vezes
  antes de um lento.
- Na rodada de emboscada (seção 4), só o lado que emboscou age, e com **no máximo 1 ação**.

## 4. Emboscada

Em `GameModeCombat` vfunc02 (0x02039af4). **Confiança: média** (a fórmula é alta; a
origem do valor do grupo do jogador ainda não foi achada).

Cada esquadrão tem um valor de emboscada (`vfunc 0x12c`). Para os inimigos ele vem da
coluna `AmbushValue` de `squads.gda`, que também força o resultado:

| AmbushValue | Resultado |
|---|---|
| −1 | ninguém embosca (6 esquadrões) |
| −2 | o jogador embosca |
| −3 | os inimigos emboscam (3 esquadrões) |
| outro | sorteio abaixo |

O sorteio: o lado com o valor maior (*a*) tem chance de emboscar o outro (*b*):

```
a' = a × (100 + bônus de emboscada do lado a) / 100 × (100 − proteção do lado b) / 100
embosca se  rand(0..R47) ≤ a' − b        R47 = regra 47 = 10
```

O bônus e a proteção são as habilidades especiais 21 e 22 (seção 11), somadas entre os
membros do esquadrão (`Squad_SumAbility`, 0x02033df4); vêm dos Chao "Ambush". O diário
do jogo diz que Luck também influencia a emboscada; isso deve estar no valor *a* do grupo,
que ainda não rastreei.

## 5. Ataque básico

### 5.1 Acerto
`Combat_ResolveAttack` (0x0200f804) e `Combat_RollToHit` (0x02013740). **Alta.**

```
acerta se  Defense_alvo ≤ Attack_atacante + 1d20
```
(sem alvo definido, usa Defense = Attack + 10.) Antes da rolagem, o ataque **erra
sempre** se o alvo tem:

- **Phased** (habilidade 25): nem ataques "Can't miss" acertam;
- **Agile** (habilidade 26), a menos que o ataque seja **Inescapable** ("Can't miss").

Um ataque Inescapable também ignora uma rolagem de acerto que falhou. Quando o ataque
erra e o alvo tem a habilidade **contra-ataque** (2), ele revida (texto "Counter").

### 5.2 Dano
`Combat_BasicAttackDamage` (0x0200fcdc). **Alta.**

```
P = Power do atacante       A = Grit do alvo
k = 110 (regra 44) para o grupo do jogador, 60 (regra 45) para inimigos

normal:   dano = 0,9 × P  +  k/100 × (3dP / 3)  −  A
crítico:  dano = P × (90 + k) / 100  −  A          se 1d100 < Luck do atacante
```

- O termo `3dP / 3` é a média de três dados de *P* faces: varia entre 1 e *P*, com
  média ≈ (P + 1)/2. Na média, um ataque do grupo dá ≈ **1,45 P − A** e o de um
  inimigo ≈ **1,2 P − A**. O crítico usa o valor máximo: **2 P − A** para o grupo,
  **1,5 P − A** para inimigos.
- **Armor Piercing** (perfura-armadura): se A < 500, A = 0.
- Só nos ataques do grupo: se 0 < dano < P/2, soma P/4 (um piso para ataques fracos).
- **Dano mínimo 1.**
- **KO instantâneo**: se a soma da habilidade 1 do atacante ≥ 1d100, o dano vira o HP
  inteiro do alvo (texto "KO"). Vem dos Chao "instant KO" (5%, 7%, 10%).
- **Blast**: os vizinhos do alvo levam `(dano − (A_vizinho − A_alvo)) / 2`, mínimo 1.
- **Leech**: o atacante recupera vida (seção 6.1).
- **Status ao acertar** (habilidade 13): até 4 efeitos guardados no valor (um por byte);
  um é sorteado e aplicado.

Inimigos ainda recebem os ajustes da dificuldade dinâmica em Attack, Defense, Power e
Grit (seção 14).

## 6. Aplicação do dano, elementos e resistências

### 6.1 Depois da fórmula
`Combat_ApplyDamage` (0x02011ac4). **Alta**, salvo onde indicado.

1. **Redução do alvo** (habilidade 14, soma em %): `dano × (1 − soma/100)`, arredondado.
   Se o alvo tiver essa habilidade e aliados vivos, o dano que sobra é **dividido em
   partes iguais** entre ele e os aliados (cada aliado leva `dano / (aliados + 1)`; o
   alvo leva o resto). Confere com a descrição da habilidade: "takes less damage ... and
   spreads the remaining damage evenly among other team members".
2. **Leech**: o atacante recupera `% × HP máximo do atacante` (é o que o código faz:
   a base é o HP máximo, não o dano causado).
3. **Drena PP** (habilidade 28 do alvo): se o atacante é do grupo do jogador, ele perde
   `soma% × seu PP máximo` (no mínimo 1).
4. O dano vira um **efeito** "HP − dano" (EffectId 1, seção 9) com a máscara de elementos
   do ataque. A resistência é aplicada nesse efeito.

### 6.2 Elementos
Os seis elementos são Fogo, Água, Terra, Vento, Raio e Gelo. **Alta.**

- **Ataque**: o código monta uma máscara de 32 bits com os atributos 90–121 maiores que
  zero (bit *i* = atributo 90 + *i*). Os seis elementos usam os bits 17–22 (atributos
  107–112). Um personagem ganha um elemento equipando um anel ou um Chao (+1 no
  atributo); um POW o traz na coluna `ElementalDamage` (ex.: `1048576` = bit 20 = Vento).
- **Defesa** (`Effect_ElementResistance`, 0x0200e4d0): para cada bit da máscara, lê a
  resistência correspondente (bits 0–15 → atributos 3–18; bits 16–31 → atributos 74–89;
  os elementos caem em 75–80) e calcula a **média** das resistências envolvidas:

```
R = média(resistências) / 100
dano final = dano × (1 − R)        (EffectFn_ModifyAttributeResist, 0x020065bc)
```

Resistência **negativa é fraqueza**: −75 multiplica o dano por 1,75; +25 por 0,75. A
interface marca o golpe como fraco/resistido pelo sinal (campo `+0x159`: 1, 2 ou 3).
Para outros tipos de efeito, há um modo em que R é a **chance de resistir por inteiro**
(`Effect_ApplyResistance`, 0x0200e640).

### 6.3 Tipos de inimigo
As resistências dos inimigos vêm dos efeitos permanentes `Spell_Int_*` (spells 121–129,
148–149). Os valores, em %:

| Tipo | Fogo | Água | Terra | Vento | Raio | Gelo |
|---|---|---|---|---|---|---|
| Robô voador | +25 | **−75** | +10 | −25 | +10 | +25 |
| Robô terrestre | +25 | **−75** | −25 | +10 | +10 | +25 |
| Animal voador | −25 | +50 | +25 | −10 | −10 | −10 |
| Animal terrestre | −25 | +50 | −10 | +25 | −10 | −10 |
| Kron | +25 | −25 | **+75** | −25 | −10 | −10 |
| N'rrgal | −25 | +50 | −10 | −10 | +50 | −25 |
| Zoah | −10 | −10 | −25 | +25 | +50 | +10 |
| Voxai | −25 | +10 | −25 | +50 | −10 | +25 |

(A tabela do jogo diz que "Wind attacks are more deadly to flying enemies"; nos dados,
Vento é −25 contra robôs voadores e −10 contra animais voadores, mas +10/+25 contra os
terrestres.)

## 7. Defender

`GameAction_Defend` vfunc04 (0x02073590). **Alta** para as contas; **média** para a
duração (o código guarda o quanto somou, para desfazer depois, mas não li onde desfaz).

```
Defense += Defense × R7 / 10      R7 = regra 7 = 7   → +70%
Grit    += Grit × R8 / 10         R8 = regra 8 = 20  → +200% (Grit triplica)
se regra 11 > 0 e PP < PP máximo:  recupera PP
```

Quanto PP volta depende da **classe** (atributo 70), para personagens do grupo:

| Classe | Personagens | PP por Defender |
|---|---|---|
| 1 e 3 (Support) | Tails, Big, Cream | 3 |
| 2 (Shifter) | Amy, Rouge, Eggman | 2 |
| 0 e 4 (Power) e inimigos | Sonic, Knuckles, Omega, Shadow | 1 |

O diário do jogo confirma: "You can regain PP by defending".

## 8. Golpes POW

Os golpes ficam em `combo.gda` (155 linhas; as 60 primeiras são do grupo do jogador). A
ligação de cada personagem aos golpes fica em `creatures.gda` (`Combo1`…`Combo10`).
O dono e os parceiros são IDs de criatura; a criatura 10 é um espaço vazio que os golpes
usam para a **Shade** (membro 10 de `party.gda`, cuja criatura de verdade é a 27).

### 8.1 Colunas de `combo.gda`
Várias colunas não têm o nome original (só o CRC32); o significado abaixo vem do código
(`Combat_PowDamage`, 0x02010810, que lê as colunas por posição) e dos dados.

| Posição | Coluna | Significado | Confiança |
|---|---|---|---|
| 1 | `col_a66f4be0` | número de participantes (1–4) | média |
| 2 | `col_64834397` | dono (ID de criatura; 10 = Shade) | alta (bate com os nomes) |
| 3–5 | `col_4fae1054`, `col_56b52115`, `col_19f4b7d2` | parceiros do golpe em equipe | alta |
| 11 | `Cost` | custo em PP | alta |
| 12–14 | `Damage1`…`Damage3` | dano em % por nível do golpe | alta |
| 24–26 | `RewardItem1`…`3` | itens roubados (Plunder), dois IDs por valor | alta |
| 27–29 | `Spell1`…`Spell3` | efeito aplicado por nível (linha de `spells.gda`) | alta |
| 30–32 | `col_a9e4c4fc`, `GUITypeAggressive`, `col_9bd2a67e` | chance do efeito por nível (0,3 = 30%) | alta |
| 45 | `ArmorPiercing` | ignora o Grit | alta |
| 46 | `col_8b96e6f9` | chance de KO instantâneo (0,5 = 50%) | alta |
| 47 | `Inescapable` | "Can't miss" | alta |
| 48 | `Blast` | atinge os vizinhos | alta |
| 49 | `Scatter` | "Full Auto": muitos golpes pequenos | média |
| 50 | `Leech` | % de vida devolvida | alta |
| 51 | `ElementalDamage` | máscara de elementos (seção 6.2) | alta |
| 52 | `col_46eddb98` | atinge todos do lado | alta |
| 54 | `col_6f47ed9a` | gravado em `GameModeCombat+0x7c8` (provavelmente nº de alvos do minijogo) | baixa |
| 55 | `EarlyFailure` | o minijogo pode falhar no começo | baixa |

`GUITypeAggressive` é o nome que o dicionário do xoreos dá para esse CRC32, mas o
conteúdo (0,5 nas chances do nível 2) mostra que é a chance do status: o nome é uma
colisão ou foi reaproveitado.

### 8.2 Dano de um POW
`Combat_PowDamage` (0x02010810). **Alta.**

```
dano = P × Damage%/100 × (90 + k/2)/100 × (1 ± desempenho) − A
       k = 110 (grupo) ou 60 (inimigo)   →   fator 1,45 (grupo) ou 1,2 (inimigo)
```

- **Desempenho** é o resultado do minijogo de toque (0 a 1). Em golpe do jogador ele
  **soma** (`1 + desempenho`); em golpe inimigo, o desempenho é a defesa do jogador e
  **subtrai** (`1 − desempenho`).
- Golpe inimigo com defesa perfeita (desempenho 1,0) **erra**, salvo se for Inescapable.
- Dano mínimo 1 (0 se `Damage%` for 0, como nos golpes de suporte).
- Comparando com a seção 5: um POW com `Damage%` = 100 dá o mesmo que um ataque básico
  médio, antes do bônus do minijogo.

**O nível do golpe** (1, 2 ou 3) escolhe a coluna de dano, o efeito e a chance. A
`GameAction_Combo` vfunc04 (0x020702d8) também escolhe as regras 71/72/73
(0,90 / 0,95 / 1,00) pelo nível e as passa ao relógio do minijogo (**média**: parece a
escala de tempo do minijogo; o nível 1 seria mais lento).

**Status de um POW**: golpe do jogador só aplica o efeito com **minijogo perfeito e**
`rolagem < chance`; golpe inimigo aplica se a defesa **não** foi perfeita. **Alta.**
Uma chance negativa (−1) nunca é atingida: o Echidna Rush tem efeitos cadastrados que
nunca são aplicados.

**Custo**: o atributo 122 (Economizer) reduz o custo (**média**: li o uso, não a conta).

### 8.3 Os golpes do grupo
Dano em % por nível; "efeito" = status (nível) e chance por nível do golpe.

| Golpe | Dono | Parceiros | PP | Dano % | Efeito | Marcas |
|---|---|---|---|---|---|---|
| Axe Kick | Sonic | | 4 | 75/88/100 | | |
| Whirlwind | Sonic | | 6 | 50/55/63 | | Inescapable, todos, Vento |
| Blue Bomber | Sonic | Tails | 4 | 100/113/125 | Weakened 1/2/3 (30/50/80%) | |
| Fastball | Sonic | Amy | 5 | 88/100/113 | Sluggish 1/2/3 (30/50/80%) | |
| Triple Tornado | Sonic | Knuckles, Tails | 5 | 75/88/113 | Sluggish 1/2/3 (30/50/80%) | Inescapable, todos, Vento |
| Hail Storm | Sonic | Knuckles, Tails, Amy | 6 | 88/100/113 | Stunned (20/30/40%) | |
| Uppercut | Knuckles | | 4 | 68/75/88 | | Armor Piercing |
| Quake Punch | Knuckles | | 6 | 33/40/50 | Stunned (30/40/50%) | Inescapable, todos, Terra |
| Revolver Slam | Knuckles | Sonic | 4 | 100/113/125 | Vulnerable 1/2/3 (30/50/80%) | Armor Piercing |
| Knuckles Express | Knuckles | Shadow | 5 | 75/113/125 | Distracted 1/2/3 (20/30/40%) | todos |
| Knuckles Sandwich | Knuckles | Sonic, Amy | 5 | 63/75/88 | Stunned (30/50/80%) | |
| Hard Line | Knuckles | Shadow, Shade | 5 | 150/163/175 | Distracted 1/2/3 (50/60/70%) | |
| Chaos Spear | Shadow | | 4 | 50/63/75 | | Armor Piercing, Scatter |
| Chaos Rift | Shadow | | 8 | 0 | Distracted 1 (40/50/60%) | KO 50% |
| Chaos Blast | Shadow | | 6 | 75/80/85 | Weakened 1 (20/30/40%) | Blast |
| Atomic Strike | Shadow | Sonic | 4 | 100/113/125 | | Inescapable, todos, Raio |
| Focus Field | Shadow | Omega | 4 | 113/125/138 | Vulnerable 1 (30/40/50%) | |
| Metal Storm | Shadow | Rouge, Omega | 5 | 150/163/175 | Stunned (20/30/40%) | |
| Scan | Tails | | 4 | 0 | Grit −25/−50/−75% (sempre) | |
| Tinker | Tails | | 4 | 0 | Tinkered 1/2/3 (sempre) | |
| Medi Bot | Tails | | 5 | 0 | cura por 3 rodadas (sempre) | |
| Shield Bot | Tails | | 5 | 0 | Fortified 1/2/3 (sempre) | |
| Flash Bang | Tails | | 5 | 0 | Sluggish + Cursed 1/2/3 (sempre) | |
| Adrenaline Rush | Tails | | 5 | 0 | Hyper 1/2/3 e +1 ação (sempre) | |
| Refresh | Cream | | 8 | 0 | PP +5/+10/+15 em todos | |
| Demoralize | Cream | | 5 | 0 | Distracted 1/2/3 em todos os inimigos | |
| Cure | Cream | | 4 | 0 | remove debuffs de todos | |
| Revive | Cream | | 5 | 0 | revive com 1 HP / 50% / 100% | |
| Heal | Cream | | 6 | 0 | HP +50/+100/+150 em todos | |
| Tough | Cream | | 5 | 0 | Fortified 1/2/3 | |
| Lure Whip | Big | | 4 | 25/38/50 | Stunned (60/70/80%) | |
| Battering Ram | Big | | 5 | 70/80/90 | Distracted 1 (30/50/80%) | |
| Taunt | Big | | 6 | 0 | atrai os ataques + Fortified 1/2/3 | |
| Froggy Poison | Big | | 5 | 25/38/50 | Poisoned (sempre) | |
| Feel No Pain | Big | | 5 | 0 | regenera 30/40/50% do HP por rodada | |
| Froggy Rain | Big | | 6 | 60/70/80 | | Inescapable, todos |
| Flamethrower | Omega | | 4 | 50/65/75 | | todos, Fogo |
| Beam Cannon | Omega | | 5 | 125/138/150 | Vulnerable 1 (50/70/100%) | Armor Piercing |
| Blazing Tornado | Omega | Rouge | 4 | 100/113/125 | | Blast, Fogo |
| Wrecking Ball | Omega | Big | 5 | 100/113/125 | Distracted 1 (30/50/80%) | Blast |
| Temporal Field | Omega | | 5 | 0 | Hyper + Phased por 2/3/4 rodadas | |
| Machine Gunner | Omega | | 6 | 13/25/38 | | Scatter |
| Tornado Kick | Rouge | | 4 | 63/68/73 | | Vento |
| Jewel Storm | Rouge | | 5 | 38/50/63 | | Armor Piercing, todos |
| Rising Knuckle | Rouge | Knuckles | 5 | 88/100/113 | Stunned (20/30/50%) | |
| Plunder | Rouge | | 4 | 0 | rouba itens (seção 12.5) | |
| Distract | Rouge | | 4 | 0 | Distracted 1/2/3 | |
| Shriek | Rouge | | 4 | 0 | Sluggish 1/2/3 | |
| Low Blow | Amy | | 4 | 63/75/88 | Vulnerable 1 (30/50/80%) | |
| Spin Cycle | Amy | Cream | 4 | 75/88/100 | | Inescapable, Blast |
| Tantrum | Amy | | 5 | 50/63/75 | Sluggish 1 (20/30/40%) | |
| Blow Kiss | Amy | | 4 | 0 | Empowered 1/2/3 num aliado | |
| Tarot Draw | Amy | | 4 | 0 | Cursed 1/2/3 | |
| Flower Power | Amy | Big, Cream | 5 | 150/163/175 | Stunned (40/50/60%) | |
| Cloak | Shade | | 4 | 0 | Hyper 1/2/3 em si mesma | |
| Blade Rush | Shade | | 5 | 75/88/100 | | Leech 10% |
| Echidna Rush | Shade | Knuckles | 5 | 100/113/125 | Distracted (chance −1: nunca) | Armor Piercing |
| Blade Drop | Shade | Sonic | 5 | 100/113/125 | | Armor Piercing, Leech 15% |
| Bombardment | Eggman | | 5 | 100/113/125 | Sluggish 1 (50%) | Inescapable, todos |
| Sabotage | Eggman | Tails | 6 | 0 | HP −100% (80/90/100%) | |

Nos golpes de suporte (dano 0), o efeito é aplicado sempre (chance 1,0). Os golpes 60
em diante são dos inimigos: um só nível, custo 0, dano de até 400%.

## 9. O sistema de efeitos (.SPL e .ITM)

Golpes, itens, status e habilidades usam o mesmo mecanismo: um **arquivo de efeito** em
texto 2DA (`.SPL` para os de `spells.gda`, `.ITM` para os de `Items.gda`, coluna
`BaseItem1`). Cada linha tem `rótulo, ID, EffectId, Data, SData1, SData2, SData3, Pulse`.

### 9.1 Cabeçalho
- **`SpellData`**: o `EffectId` dessa linha é o **alvo**. **Alta** (bate com todos os itens).

  | Valor | Alvo |
  |---|---|
  | 0 | um inimigo |
  | 1 | um aliado |
  | 2 | todos os inimigos |
  | 3 | todos os aliados |
  | 5 | o próprio usuário |
  | 6 | um aliado nocauteado |

- **`CollectionData`** (nos itens, `CollectionData_Equip` e `CollectionData_Use`):
  `Data` = **duração**, `SData1` = **categoria**, `SData2` = tempo.

  | Data | Duração | Confiança |
  |---|---|---|
  | 0 | instantâneo | alta |
  | 1 | permanente | alta |
  | 2 | enquanto equipado | média |
  | 3 | temporário, `SData2` milésimos de rodada (3000 = 3 rodadas) | média |

  A **categoria** é uma máscara: bit *n* = status *n* − 1 para os debuffs (Poisoned = 8,
  Weakened = 16, Vulnerable = 32, Distracted = 64, Sluggish = 128, Cursed = 256,
  Stunned = 512, Tinkered = 4) e bit = status para os buffs (Empowered = 1024,
  Fortified = 2048, Focused = 4096, Hyper = 8192, Lucky = 16384). É ela que o
  "remover status" procura. **Alta** (Iron Tonic remove 32 = Vulnerable, Rock Salt 16 =
  Weakened, Prune Juice 64 = Distracted, Psychic Water 128 = Sluggish, os pares do diário
  do jogo).

### 9.2 Tipos de efeito (EffectId)
O código tem uma tabela com 11 tipos (`CGameEffectFunctions`, 0x02005cec), cada um com
funções de aplicar, remover, repetir e resistir.

| EffectId | O que faz | Campos | Confiança |
|---|---|---|---|
| 0 | dados da coleção (cabeçalho) | | alta |
| 1 | muda um atributo | `Data` = quantidade, `SData1` = atributo, `SData2` = flags, `Pulse` 1000 = repete a cada rodada | alta |
| 5 | efeito visual | `Data` = VFX | alta |
| 6 | revive | | alta |
| 7 | remove status | `Data` = máscara de categorias (1022 = todos os debuffs; 131070 = todos) | alta |
| 8 | atrai os ataques (Taunt) | | média |
| 9 | aplica outro efeito | `Data` = linha de `spells.gda` | alta |
| 10 | concede uma habilidade especial | `Data` = código (seção 11) | média |

### 9.3 As flags do EffectId 1
`EffectFn_ModifyAttribute` (0x02005fcc). **Alta.**

```
bit 0      : 0 = soma ao valor atual;  1 = define (substitui)
bits 1–2   : base da quantidade
             0 = valor absoluto
             1 = % do valor BASE do próprio atributo
             2 = % do HP máximo
             3 = % do PP máximo
```

| SData2 | Lê-se | Exemplo |
|---|---|---|
| 0 | soma absoluta | Weakened: Power −10 |
| 2 | soma % do valor base | Scan: Grit −25% |
| 3 | define em % do valor base | Heal1: Attack, Defense, Power, Grit, Luck = 100% da base (desfaz debuffs) |
| 4 | soma % do HP máximo | Poisoned: HP −10% do máximo por rodada |
| 5 | define em % do HP máximo | Revival Ring: HP = 10% do máximo |

## 10. Status (buffs e debuffs)

`Statuses.gda` tem 16 status. A coluna `CanAct` = 0 impede de agir; `Priority` ordena os
ícones. Um status ativo é o atributo `39 + ID` > 0, e os efeitos que o causam somam +1
nele. Os nomes internos (`ATKdown`…) diferem dos nomes do diário do jogo; os valores são
de `Spell_<Status>.spl`, `_2` e `_3`. **Alta.**

| ID | Interno | Nome no jogo | Efeito (nível 1 / 2 / 3) | Duração | Cura |
|---|---|---|---|---|---|
| 0 | Dead | K.O. | não age | | Revival Ring, Ring of Life, Revive |
| 1 | Tinkered | (Tinker) | Power e Defense −5 / −10 / −15 | 3 | Antidote |
| 2 | Poisoned | Poisoned | HP −10% do máximo por rodada | 3 | Antidote |
| 3 | ATKdown | Weakened | Power −10 / −15 / −20 | 3 | Rock Salt, Antidote |
| 4 | DEFdown | Vulnerable | Grit −5 / −10 / −15 | 3 | Iron Tonic, Antidote |
| 5 | ACCdown | Distracted | Attack −10 / −15 / −20 | 3 | Prune Juice, Antidote |
| 6 | EVAdown | Sluggish | Defense −10 / −15 / −20 | 3 | Psychic Water, Antidote |
| 7 | LCKdown | Cursed | Luck e Attack −10 / −15 / −20 | 3 | Antidote (o diário cita Clover Juice) |
| 8 | Paralyzed | Stunned | **não age**; Defense −20 | 2 | Antidote |
| 9 | (sem nome) | ? | dado pelo item Crazy Beans | | |
| 10 | ATKup | Empowered | Power +10 / +15 / +20 | 3 | |
| 11 | DEFup | Fortified | Grit +10 / +15 / +20 | 3 | |
| 12 | ACCup | Focused | Attack +10 / +15 | 3 | |
| 13 | EVAup | Hyper | Speed e Defense +10 / +15 / +20 | 3 | |
| 14 | LCKup | Lucky | Luck +10 / +15 / +20 | 3 | |
| 15 | (sem nome) | Bug Spray | Grit −10, Defense −10, Speed −6, Power −3 | | |

Os números são absolutos (não %): no nível 1 um personagem tem Power ~10 e no 30 ~60,
então o mesmo Weakened pesa muito mais no começo do jogo. Detalhe: os nomes internos
estão "trocados" em relação ao que o jogo mostra porque, no código, **Attack** é a
precisão (o "ACC") e **Power** é o dano (o "ATK").

## 11. Habilidades especiais

Efeitos que não são números num atributo: o código pergunta "quanto desta habilidade a
criatura tem?" (`vfunc 0xbc`, somando todos os efeitos ativos do tipo). Elas vêm de duas
colunas de `Items.gda` (`col_ab33ab1a` = código, `col_dee49bb0` = valor; e
`col_801ef8d9`/`col_f5c9c873` para uma segunda) e do EffectId 10. Os significados vêm das
descrições dos itens (Chao e equipamentos) e, quando marcado, do código. **Média**, salvo
indicação.

| Código | Habilidade | Valor | No código |
|---|---|---|---|
| 0 | POW sempre perfeito (Chao 38) | | |
| 1 | KO instantâneo no ataque básico (Chao 40) | % | **alta**: soma ≥ 1d100 |
| 2 | contra-ataque (Chao 213) | | **alta**: revida quando é errado |
| 3 | revive 1× por batalha (Angel Amulet, Chao 39) | % do HP | |
| 4 | evitado pelos inimigos, salvo se for o último (Chao 214) | | |
| 5 | atrai um inimigo (Chao 35) | nº de inimigos | |
| 6 | esquiva alguns ataques básicos por rodada (Chao 215) | | |
| 7 | regenera HP do time no começo da rodada (Chao 21) | % | |
| 9 | regenera HP (Replenisher, Chao 1) | % | |
| 10 | recupera PP no fim da rodada (Refresher) | | |
| 11 | sorte do time (Cheese) | | |
| 12 | XP extra (Chao 37) | % | |
| 13 | status aleatório ao acertar | até 4 efeitos, 1 por byte | **alta** |
| 14 | reduz o dano recebido e divide com o time | % | **alta** (seção 6.1) |
| 15 | fuga/perseguição (Nrrgal Module, Chao 33) | | |
| 18 | inimigos fogem mais (Spooky Charm, Chao 29) | | |
| 19 | Chao raros nos ovos (Chao 34) | | |
| 21 | chance de emboscar (Chao 30) | % | **alta** (seção 4) |
| 22 | reduz chance de ser emboscado (Chao 31) | % | **alta** (seção 4) |
| 23 | item extra na recompensa (Chao 32) | 2 IDs de item | |
| 25 | **Phased**: imune a dano | | **alta** (seção 5.1) |
| 26 | **Agile** ("Evading") | | **alta** (seção 5.1) |
| 27 | auto-reparo (inimigos) | % | |
| 28 | drena PP de quem ataca (inimigos) | % | **alta** (seção 6.1) |
| 29 | regenera PP do time (Chao 22) | | |
| 30 | regenera PP (Chao 2) | | |
| 31 | imunidade (inimigos) | | |

Os itens 211–230 e 277–285 não aparecem no inventário: são as habilidades dos inimigos,
equipadas neles.

## 12. Itens

`Items.gda` (288 linhas) + um `.ITM` por item. **Alta**, salvo indicação.

### 12.1 Tipos e slots

| Type | Tipo | EquipSlot |
|---|---|---|
| 0 | consumível (`SubType` 0 HP, 1 PP, 2 reviver, 3 curar status, 4 especial) | −1 |
| 1 | equipamento | 0 = pés, 1 = mãos, 2 = acessório |
| 2 | item de história (esmeraldas, objetos de missão) | −1 |
| 3 | Chao | 4 |

**Quem pode equipar** é a máscara `AllowEquip`: bit *i* = personagem *i* de
`creatures.gda` (0 Sonic, 1 Knuckles, 2 Tails, 3 Amy, 4 Shadow, 5 Rouge, 6 Big, 7 Cream,
8 Omega, 9 Eggman). Exemplos: `21` (bits 0, 2, 4) = tênis do Sonic, Tails e Shadow; `200`
= sapatilhas de Amy, Big e Cream; `256` = só Omega (hidráulicos e garras); `136` = vestidos
de Amy e Cream. O bit 27, presente em vários valores, ainda não tem significado (**baixa**).

### 12.2 Consumíveis

| Item | Alvo | Efeito |
|---|---|---|
| Health Seed / Leaf / Root | aliado | HP +50 / +100 / +250 |
| Med Emitter | todos aliados | HP +250 |
| POW Candy / Gum / Drink | aliado | PP +5 / +10 / +50 |
| Refresher Wave | todos aliados | PP +50 |
| Revival Ring / Ring of Life | nocauteado | revive com 10% / 100% do HP e limpa os status |
| Antidote / Cure All Spray / Immunity Booster | aliado / todos | remove os debuffs (máscara 1022) |
| Iron Tonic, Rock Salt, Prune Juice, Psychic Water | aliado | buff +10 e remove o debuff oposto |
| Clover Juice | aliado | Lucky (+10 Luck); o diário diz que cura Cursed, mas o `.ITM` não tem a linha de remoção |
| Speed Bar | aliado | Speed +10 |
| Bug Spray | todos inimigos | status 15: Grit −10, Defense −10, Speed −6, Power −3 |

### 12.3 Equipamentos
Os bônus são pequenos e absolutos (+1 a +6), sempre "enquanto equipado":

- **Pés** (sapatilhas, tênis, botas, hidráulicos): Defense e Grit, às vezes Speed ou Power.
- **Mãos** (luvas, garras): Attack e Power. As "Cursed" dão Power +6 com Attack e
  Defense −2.
- **Acessórios**: anéis elementais (+1 no dano elemental, seção 6.2), Economizer (atributo
  122), Kron Hammer (Power +5), Zoah Shield (Grit +4), Nocturne Blade (Attack +4), Voxai
  Teleporter (Defense +4), e os de habilidade (Refresher, Replenisher, Nrrgal Module,
  Angel Amulet, Spooky Charm, Immunity Idol).
- O item 82 (sem nome) dá +999 em tudo: um item de teste que ficou no jogo.

### 12.4 Chao
Equipados no slot 4. Os de 1 a 20 dão atributos (HP máx +10%, PP máx +2, +1 em Attack,
Defense, Power, Grit ou Luck, um elemento no ataque, ou resistência +50 a um elemento);
os de 21 em diante dão habilidades especiais (seção 11). O mesmo Chao aparece em três
graus (IDs 91–130, 131–170, 171–210) com valores maiores: por exemplo, o Chao 39 revive
com 10%, 50% e 100% do HP.

### 12.5 Itens aleatórios, roubo e lojas
- **Itens aleatórios**: a coluna `Random` > 0 transforma o item num sorteio na linha
  correspondente de `RandItems.gda` (até 8 pares peso/item). Os itens 258–276 e 287 são
  esses "envelopes"; um sorteio pode cair noutro envelope (o item 275 aparece na linha 2).
  `Random` = −2 em alguns itens comuns (Health Root, Speed Bar, ...): significado
  desconhecido (**baixa**).
- **Plunder** (Rouge): `RewardItem1..3` guarda dois IDs por valor (16 bits cada):
  nível 1 = `3` (POW Candy ou Health Seed), nível 2 = `0x40007` (POW Gum ou Health Leaf),
  nível 3 = `0x50008` (Health Root ou POW Drink). Bate com o diário do jogo. O mesmo
  formato aparece no Chao "item extra" (código 23).
- **Lojas**: `stores.gda` aponta as 5 tabelas `Store1`…`Store5` (0 Central City,
  1 Station Square, 2 Kron Quartermaster, 3 Civilian Supply Depot, 4 The Overmart), com 3
  colunas sem nome: item, preço de compra e preço de venda (**alta**: um item novo posto
  com preço 15 custou 15 anéis no jogo; Health Seed custa 6 e vende por 3).
  **Como o jogo abre uma loja** (**alta**, conferido no emulador): o evento 40 (o mesmo
  código de evento dos gatilhos de área e das respostas de conversa; a conversa
  `kron_store` usa evento 40 com dado 2) cai no tratador `0x0207be48`, que grava o dado
  (a linha de `stores.gda`) em `GameModeStateStore+4` e pede o **modo 11** ao
  `ModeSwitcher` (global `0x02109ba0`; `0x020305a4` pede um modo, `0x02030604` faz a
  troca, e o `switch` em `0x02030d18` cria o `GameModeStore` no caso 11). Chamar esse
  tratador com outro índice abre qualquer loja em qualquer lugar.
- **Recompensas**: `rewards.gda` (70 linhas: missões) dá `XP` e até 6 itens; as colunas
  `Copper`, `Silver`, `Gold` ainda não foram ligadas ao código (**baixa**).

## 13. Inimigos

- **`creatures.gda`** (128 linhas; 0–9 são o grupo): atributos base, `Type`, `Level`,
  `Combo1..10`, `FleeProbability` (0,05 para quase todos), e as marcas do ataque básico
  (`AttackArmorPiercing`, `AttackInescapable`, `AttackBlast`, `AttackScatter`,
  `AttackLeech`), que entram nas mesmas fórmulas da seção 5.
- **`squads.gda`** (332 esquadrões): até 4 membros (`Member1..4`), `XPValue`, `Level`,
  `RewardItem`, `AmbushValue` (seção 4), `CanFlee` (89 podem fugir), `FleeTable`/
  `ChaseTable` (minijogos de fuga e perseguição), `CombatRoundLimit` (2 batalhas com
  limite de rodadas), `NoticeDistance`.
- **`CombatAI.gda`** (14 perfis): pesos, que somam 100, para Atacar, Defender e
  `Combo1..10`. Ex.: perfil 6 = 85% ataque e 15% defesa; perfil 11 = só defende. **Média**:
  a ligação do perfil a cada criatura ainda não foi rastreada.
- **Fraquezas**: seção 6.3.

## 14. Dificuldade dinâmica

O jogo ajusta os inimigos conforme o jogador vai bem ou mal. **Média**: as contas são
alta; o que exatamente conta como "ir bem" é dedução.

- O nível de ajuste fica em `DAT_02160e54` e vai de **−4 a +6** (regras 64 e 63). Ele só
  liga em certas condições (plot 0x1cc == 1 e um contador do esquadrão ≥ 4).
- No fim da batalha (`GameModeCombat+0x13c0`, o contador de rodadas): batalha com
  6 rodadas ou mais → nível −1; batalha curta (3 a 5 rodadas) → nível +1.
- Cada atributo de inimigo recebe `regra × (nível ÷ divisor)`, com divisão inteira
  (níveis ±1 não mudam nada) e piso 0:

| Atributo | Função | Nível > 0 (÷ regra 62 = 2) | Nível < 0 (÷ regra 65 = 2) |
|---|---|---|---|
| Power | 0x02019414 | +3 (regra 58) | +5 (regra 67) |
| Defense | 0x02019468 | +0 (regra 57) | +2 (regra 66) |
| Attack | 0x020194bc | +1 (regra 59) | +2 (regra 68) |
| Grit | 0x02019510 | +0 (regra 60) | +5 (regra 69) |
| HP máximo | 0x02019564 | +20 (regra 61) | +0 (regra 70) |

  No nível +6: Power +9, Attack +3, HP máximo +60. No nível −4: Power −10, Defense −4,
  Attack −4, Grit −10.

## 15. CombatRules: as 74 regras

`CRules_LoadCombatRules` (0x0201f270) copia cada linha para uma variável global. A lista
completa, com valores, sai de `combate_tabelas.py` (`regras.md`). As conhecidas:

| Regras | Uso | Onde |
|---|---|---|
| 0 | não usada no código (90) | |
| 1, 2, 3, 33 | iniciativa (60, 1d2, ×1, ÷4) | 0x020448c0 |
| 4 | 0x020451c4 (não analisada) | |
| 5, 6, 15–32, 48–50 | minijogo de toque e câmera dos POW | 0x02047a14, 0x02047f70, 0x02039af4 |
| 7, 8, 11 | Defender (+70% Defense, +200% Grit, PP) | 0x02073590 |
| 10, 12, 13, 14 | 0x02043ea8, 0x020436e4, 0x020441cc, 0x02042034 (não analisadas) | |
| 34, 53 | exploração (início do combate a partir do mapa) | GameModeExplore |
| 35, 38 | interface do combate em tempo real | CombatRealTimeGui |
| 36, 37 | 0x02069d88 (não analisada) | |
| 39 | dano básico (100) | 0x0200fcdc |
| 40–42 | desempenho do minijogo POW | 0x02070928 |
| 43, 44, 45 | dano: 90 fixo, k = 110 (grupo), k = 60 (inimigo) | 0x0200fcdc, 0x02010810 |
| 47 | dado da emboscada (10) | 0x02039af4 |
| 55, 56 | 0x0203d274 (não analisada) | |
| 57–70 | dificuldade dinâmica | seção 14 |
| 71–73 | escala do minijogo por nível do golpe (0,90 / 0,95 / 1,00) | 0x020702d8 |

## 16. O que ainda não sabemos

- **Fuga e perseguição**: a fórmula que usa `FleeProbability`, Speed e as habilidades 15
  e 18; os minijogos `Flee*`/`Chase*`.
- **De onde vem o valor de emboscada do grupo** (e onde entra a Luck).
- **XP**: como `XPValue` é dividido e onde entra o bônus do Chao 37.
- **O minijogo de toque**: o significado exato das regras 15–32 e 48–50 e da tabela
  `realtime.gda` (65 elementos de toque), e como o desempenho (0 a 1) é calculado.
- **Quando os efeitos do Defender são desfeitos** e a ordem em que os efeitos por rodada
  (veneno, regeneração) são aplicados.
- A ligação de `CombatAI.gda` às criaturas; o status 9; o bit 27 de `AllowEquip`;
  `Random` = −2.
- **Onde as lojas ficam no jogo**: só a do Kron (conversa `kron_store`, evento 40, dado 2)
  foi achada; nenhum gatilho de área usa o evento 40. As outras quatro devem ser abertas
  por outro caminho (talvez o mapa-múndi). Também falta a regra de ordem da lista da loja.

## 17. Como conferir

| Para conferir | Faça |
|---|---|
| uma fórmula | leia a função no pseudo-C (`analise/run_all.sh` gera em `work/`) pelo endereço citado |
| uma função auxiliar | execute-a isolada com o Unicorn: carregue `arm9.bin` em 0x02000000, ponha os argumentos em r0–r3 e um endereço de retorno em lr (funções Thumb: endereço \| 1) |
| um valor de tabela | `sonic-mod unpack` e abra a planilha; `combate_tabelas.py` decodifica os `.SPL`/`.ITM` |
| no jogo | mude um valor (ex.: regra 44, o k do grupo) com o `sonic-mod pack` e compare o dano no emulador |
| um item novo numa loja | `analise/tools/testar_item_loja.py rom_mod.nds save.sav ITEM LOJA PRECO CURA pasta` abre a loja pelo tratador do jogo, compra e usa o item, e confere anéis, inventário e HP na RAM |
| um golpe novo e o efeito dele | `analise/tools/testar_golpe.py rom_mod.nds estado.dst 155 pasta 500 --vfx 467 --auto` mostra a linha de `combo.gda` usada e os efeitos (`VFX.gda`) pedidos |

A história de como cada parte foi descoberta está no [diário](DIARIO.md#11-o-combate).
