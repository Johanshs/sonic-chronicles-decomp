# Cheats do projeto (bateria)

Os códigos ficam em [`cheats/YWSE.txt`](../cheats/YWSE.txt). Este documento diz, para
cada um, **o que faz, por que funciona, quanto confiamos nele e como testar**. O plano
geral (fases A0–A3 e o mod menu) está em [PLANO-MOD-MENU.md](PLANO-MOD-MENU.md).

## Como usar

```
# 1. conferir a forma dos códigos (tipos conhecidos, endereços na RAM, condições fechadas)
python3 analise/tools/ar_codes.py validar cheats/YWSE.txt

# 2. ver o que cada cheat escreveria, com e sem botões apertados
python3 analise/tools/ar_codes.py simular cheats/YWSE.txt
python3 analise/tools/ar_codes.py simular cheats/YWSE.txt L,UP

# 3. gravar no banco do cartão (faça uma cópia do usrcheat.dat antes!)
python3 analise/tools/usrcheat.py inserir usrcheat.dat cheats/YWSE.txt saida.dat
```

O `inserir` **troca** as pastas que começam por "Projeto" (inclusive a antiga "Projeto
sonic-chronicles-decomp") pelas novas e mantém o resto do banco igual. Por isso dá para
rodar sobre o `usrcheat.dat` que já está no cartão. Depois, renomeie `saida.dat` para
`usrcheat.dat` e copie para `SD:/_pico/`.

No cartão, cada pasta "Projeto: ..." aparece dentro do Sonic Chronicles. As pastas
marcadas com `@escolha` no texto só deixam **um** cheat ligado por vez, porque todos os
cheats dela escrevem no mesmo endereço e brigariam entre si. (O Pico Launcher lê essa
marca do formato, `isMaxOneCheatActive`; ainda não vimos isso funcionando no DS.)

## Por que estes cheats funcionam

1. **As regras de combate moram em endereços fixos.** No boot, `CRules_LoadCombatRules`
   (0x0201f270) copia as 74 linhas de `combatrules.gda` para variáveis globais. O ARM9
   deste jogo não tem overlays, então essas variáveis estão sempre no mesmo lugar, no DS
   e no emulador.
2. **O jogo lê a regra na hora da conta.** A fórmula do dano busca a global toda vez que
   alguém ataca. O teste de 08/10/2026 no DS provou isso: se o jogo guardasse uma cópia,
   mudar a global não mudaria o dano.
3. **O motor de cheats escreve a cada quadro.** Um cheat sem condição fica reescrevendo
   o valor 60 vezes por segundo, então ele vale o tempo todo.
4. **Uma escrita só já basta para as regras.** Como o jogo só carrega a tabela no boot,
   ninguém volta a mexer na global. É por isso que os cheats "por botão" funcionam como
   um interruptor: apertou, o valor muda e fica; apertou o outro, volta ao original.
5. **Reiniciar o jogo desfaz tudo.** Desligou o cheat no launcher e abriu o jogo de novo:
   o boot recarrega a tabela original. Nada disso toca no save.

### Como ler um código de botão

`94000130 FCBF0100` quer dizer: "leia 16 bits em `0x04000130` (o registrador das
teclas), apague os bits que estão ligados em `FCBF` e compare com `0100`".

- Em `0x04000130`, cada tecla é um bit, e **0 = apertada**: A = bit 0, B = 1,
  Select = 2, Start = 3, Direita = 4, Esquerda = 5, Cima = 6, Baixo = 7, R = 8, L = 9.
- `FCBF` é a máscara invertida: `~FCBF = 0340` = bits 9 (L), 8 (R) e 6 (Cima). Só essas
  três teclas importam; as outras são ignoradas.
- `0100` é o valor esperado nesses bits: L = 0 (apertado), Cima = 0 (apertado) e
  **R = 1 (solto)**.

Exigir o R solto é de propósito: o cheat de dificuldade usa L+R (`94000130 FCFF0000`).
Sem isso, apertar L+R+Cima dispararia os dois. O `ar_codes.py simular` mostra isso:
com `L,UP` o cheat de dano liga; com `L,R,UP`, não.

## A bateria

**ROM original ou ROM do painel?** Os cheats foram feitos para a ROM original. Todos
partem de endereços fixos do programa (as regras, a dificuldade, a lista do grupo, o
`0x02160C18` do esquadrão) ou de trechos de código, nunca de um endereço fixo dentro do
heap. Por isso eles também devem funcionar com a ROM do painel de controle, que muda a
arrumação do heap na v0.2 (na v0.3 o painel vai para o fim do heap e os endereços voltam
a bater com a ROM original). Cheats públicos que escrevem direto no heap, como o de anéis
`022262F4`, não têm essa garantia. **Conferido no emulador com a ROM do painel v0.3** e o seu save
(Capítulo 10): com os cheats de anéis, itens, XP, Chao e grupo ligados, todos escreveram
nos lugares certos (carteira 999999, XP 2700000, patch dos itens, Chao 44, os 11
personagens com Defense e PP 99).

Confiança:
- **[DS]**: testado no DS real em 08/10/2026, a olho (ligou, o jogo rodou e o efeito foi o
  esperado).
- **[alta]**: o endereço já foi testado no DS; só o valor é novo. A conta vem do
  [COMBATE.md](COMBATE.md), onde as fórmulas têm confiança alta.
- **[média]**: o endereço e o efeito na memória foram conferidos só no emulador.
- **[baixa]**: deduzido, sem confirmação direta nem no emulador.

As contas abaixo usam P = Power do atacante, A = Grit do alvo, e a média de `3dP/3`,
que é ≈ (P + 1)/2 ([COMBATE.md, seção 5.2](COMBATE.md#52-dano)).

### Pasta "Projeto: dano do grupo (regra 44)", escolha 1

A regra 44 é o `k` do grupo: `dano = 0,9 P + k/100 × (3dP/3) − A`; crítico
`P × (90 + k)/100 − A`; POW `P × Dano% × (90 + k/2)/100 × (1 + desempenho) − A`.

| Cheat | Código | Efeito (antes do Grit) | Confiança |
|---|---|---|---|
| Dano do grupo muito maior | `020F64C0 000003E8` (k = 1000) | básico médio 1,45 P → 5,9 P (≈ 4×); crítico 2 P → 10,9 P; POW 1,45 → 5,9 | [DS] |
| Dano do grupo sem sorte | `020F64C0 00000000` (k = 0) | básico **sempre** 0,9 P; crítico também 0,9 P (deixa de valer a pena); POW 0,9 | [alta] |
| Dano do grupo x4 por botão | L+Cima grava 1000; L+Baixo grava 110 | igual ao primeiro, ligável no meio do jogo | [alta] |

**Para que serve o "sem sorte":** com k = 0 o dano básico deixa de ter parte aleatória.
Dois ataques do mesmo personagem no mesmo inimigo têm que dar **o mesmo número**. É o
jeito mais fácil de conferir a fórmula a olho no DS, com a tela de status aberta: dano =
0,9 × Power − Grit do inimigo (se o resultado for menor que P/2, o jogo soma P/4).

**Como testar:** numa batalha, ataque o mesmo tipo de inimigo 3 vezes com o mesmo
personagem e anote os números. Com "sem sorte", os 3 são iguais (salvo um crítico, que
agora dá o mesmo valor). Com o "por botão": anote um dano, aperte **L+Cima**, ataque de
novo (deve ser ≈ 4× maior), aperte **L+Baixo** e confira que voltou ao normal. Anote também
se L+direcional faz alguma outra coisa no jogo, para trocarmos o atalho se fizer.

### Pasta "Projeto: dano dos inimigos (regra 45)", escolha 1

A regra 45 é o `k` dos inimigos, nas mesmas fórmulas (POW com `1 − desempenho`).

| Cheat | Código | Efeito (antes do Grit) | Confiança |
|---|---|---|---|
| Inimigos sem dano aleatório | `020F64BC 00000000` (k = 0) | básico sempre 0,9 P | [DS] |
| Inimigos batem 2x mais | `020F64BC 0000012C` (k = 300) | básico médio 1,2 P → 2,4 P (2×); crítico 1,5 P → 3,9 P; POW 1,2 → 2,4 | [alta] |
| Inimigos 2x por botão | L+Direita grava 300; L+Esquerda grava 60 | igual ao anterior, ligável | [alta] |

**Como testar:** escolha uma batalha fácil e anote o dano que um inimigo causa em 2 ou
3 ataques. Com "2x mais", o mesmo inimigo deve tirar cerca do dobro (um pouco mais do
dobro quando o Grit do seu personagem é alto, porque o Grit é subtraído depois). Use o
"por botão" para comparar na mesma batalha.

### Pasta "Projeto: defender"

As regras 7 e 8 só aparecem no comando Defender (0x02073590):
`Defense += Defense × R7/10` e `Grit += Grit × R8/10`. Defense é a esquiva (o inimigo
acerta se `Defense ≤ Attack + 1d20`); Grit é a armadura (subtraída do dano).

| Cheat | Código | Efeito | Confiança |
|---|---|---|---|
| Defender mais forte | `020F64FC 00000064` (R8 = 100) | Grit ×3 → ×11 ao defender | [DS] |
| Defender: esquiva x3 | `020F6470 00000014` (R7 = 20) | Defense ×1,7 → ×3 ao defender | [média] |

**Por que [média]:** o endereço `0x020F6470` foi identificado no emulador porque guarda 7
depois do boot (no binário vale 2, prova de que a tabela foi carregada por cima). Ainda
não foi testado no DS nem lido na função do Defender instrução por instrução.

**Como testar:** defenda com um personagem e conte quantos ataques erram nele naquela
rodada, em 3 ou 4 batalhas, com e sem o cheat. É o efeito mais difícil de ver a olho:
o número de erros depende do 1d20. Se não der para perceber, ele fica para a medição
no emulador (fase A1).

### Pasta "Projeto: dificuldade dinâmica", escolha 1

O nível fica em `0x02160E54` (byte com sinal, de −4 a +6); `0x02160E58` é a chave que
liga o ajuste. Cada atributo de inimigo recebe `regra × (nível ÷ 2)`, com divisão
inteira ([COMBATE.md, seção 14](COMBATE.md#14-dificuldade-dinâmica)). Cada inimigo copia
o nível no começo da batalha, por isso a mudança vale **a partir da próxima** batalha.

| Cheat | Código | Inimigos | Confiança |
|---|---|---|---|
| Dificuldade mínima (L+R) | segure L+R: chave 1, nível −4 | Power −10, Attack −4, Defense −4, Grit −10 | [DS] |
| Travada no mínimo (−4) | chave 1, nível −4, sempre | igual ao anterior, sem botão | [alta] |
| Travada no neutro (0) | nível 0, sempre | sem ajuste: os atributos da tabela | [alta] |
| Travada no máximo (+6) | chave 1, nível +6, sempre | Power +9, Attack +3, HP máximo +60 | [alta] |

O cheat escreve a cada quadro, então ele também apaga o ajuste que o jogo faz no fim de
cada batalha (−1 se a batalha foi longa, +1 se foi curta).

**Como testar:** escolha um encontro que dá para repetir (o mesmo esquadrão) e anote
quantos ataques leva para derrubar um inimigo. Com "+6", o inimigo tem 60 de HP a mais e
bate mais forte; com "−4", cai mais rápido e erra mais. O "neutro" serve de referência.

### Pasta "Projeto: anéis e itens"

| Cheat | Código | Efeito | Confiança |
|---|---|---|---|
| Anéis sempre 999999 | ponteiro `0x02160C18` → objeto → esquadrão, `+0x114` (abaixo) | a carteira (a do inventário e da tela de save) fica em 999999 | [média] |
| Itens não acabam | patch de código em `0x0202DB4C` | usar um item não gasta | [média] |
| Pegar todos os anéis da área (de longe) | patch de código em `0x02017A56` e `0x02017A88` | todo anel da área é pego na hora | [média] |

Os anéis que você gasta moram no objeto `CGamePlayerSquad` (o "esquadrão"), no heap. A
global `0x02160C18` (na área de variáveis fixas do programa, a BSS) aponta para um objeto
cujo primeiro campo é o esquadrão, e a carteira fica em `+0x114`:

```
32160C18 02400000   se o ponteiro em 0x02160C18 é menor que o fim da RAM...
42160C18 01FFFFFF   ...e maior que o começo (trava)
B2160C18 00000000   offset = o objeto
30000000 02400000   se o primeiro campo dele também aponta para a RAM...
40000000 01FFFFFF
B0000000 00000000   offset = o esquadrão
50000000 020F9C08   se o primeiro campo é a vtable de CGamePlayerSquad (trava)
00000114 000F423F   carteira = 999999
D2000000 00000000   fim
```

**Por que não `0x021D10AC`:** o cheat público de dinheiro (e a primeira versão deste) parte
de `0x021D10AC`, que também aponta para o esquadrão. Mas esse endereço fica **dentro do
heap** (que começa em `0x021B9500`): ele só é sempre o mesmo porque o jogo aloca as coisas
na mesma ordem a cada boot. Se algo mudar a arrumação do heap, ele vira outra coisa. A
ROM do painel de controle (v0.2) fez exatamente isso: empurrou o heap `0x2EA0` bytes. O
`0x02160C18` foi achado pela conversa do painel e conferido aqui em 6 estados (título,
seleção de save, Green Hill, Nocturne, batalha e depois dela).

**Como foi achado (e o erro da primeira versão):** pegando um anel (8 → 9), dois
contadores somaram 1: `0x02160EB0` (endereço fixo) e o `0x022262F4` do cheat público. A
primeira versão deste cheat escrevia em `0x02160EB0`, porque no Green Hill ele mudava o
número do HUD. Estava errado: abrindo o **Inventário**, quem aparece é o outro. Escrevi
500 em `0x02160EB0` e o inventário continuou em 9; escrevi 777 na carteira e o inventário
mostrou 777. No save do Capítulo 10 a diferença fica clara: carteira 986967 (o número da
tela de save), `0x02160EB0` = 54 e o HUD mostrando "93/124". O `0x022262F4` é a carteira
naquele momento (esquadrão em `0x022261E0` + `0x114`); o cheat usa o ponteiro para não
depender disso.

O `0x02160EB0` soma 1 por anel pego, mas não é o que você gasta. No Green Hill ele bate com
o HUD ("x/185", anéis da área); no Nocturne não bate (55 contra 94). Ainda não sabemos
exatamente o que é, então não há cheat para ele.

**Por que 999999:** é o maior número que cabe na tela. Com 1000000 o inventário mostra
"1000000" passando da moldura.

**Cuidado:** se você salvar com o cheat ligado, os 999999 anéis ficam no save.

**Itens não acabam.** Cada item da mochila é um objeto `CGameItem` com o número do item em
`+0xB8` e a quantidade em `+0xBB` (um byte; o jogo recusa mais de 99, em `0x02019F20`). A
mochila (`CGameObjectInventory`) tem um vetor de ponteiros para eles. Gastar um item passa
pela função que tira itens da mochila; o trecho que importa é este:

| Endereço | Original | Quer dizer | Com o cheat |
|---|---|---|---|
| 0x0202DB4C | `DD07` | `ble`: se a quantidade é 1 (ou menos), vá apagar o item | `46C0` (não faz nada) |
| 0x0202DB4E | `1E49` | `subs r1, r1, #1`: quantidade − 1 | `46C0` (não faz nada) |

Sem as duas instruções, o jogo grava a mesma quantidade de volta e nunca apaga o item. O
código é `5202DB4C 1E49DD07` (só age se as instruções originais estiverem lá) e
`0202DB4C 46C046C0`. **Conferido no emulador:** no menu, usar o Med Emitter duas vezes
levou de 87 para 85 sem o cheat e deixou em 87 com ele; com a quantidade em 1, o item
continuou lá. Numa batalha, usar o Med Emitter e vencer: 86 sem o cheat, 87 com ele.

**Efeito colateral provável:** a mesma função deve ser usada para vender e para passar um
equipamento da mochila para um personagem. Com o cheat ligado, vender pode dar anéis sem
perder o item, e equipar pode duplicar o equipamento. Ainda não conferimos; desligue o
cheat antes de ir à loja se não quiser isso. A função tem só dois chamadores diretos no
ARM9: um que tira um item depois de conferir seu número (`0x0202E09C`) e um do jardim dos
Chao (`0x0203939E`), que tira um item e soma uma cópia a um Chao. No emulador, abrir o
jardim com o cheat ligado chocou os ovos normalmente e o jogo não travou.

**Pegar todos os anéis da área.** A cada quadro, uma função (a partir de `0x02017A00`)
passa pela lista de coletáveis da área. Para cada um ela confere o tipo (1 = anel, 3 = o
outro coletável do HUD, o ícone azul "x/11"), depois a distância até o Sonic em X e em Y.
Só se as duas forem menores que `5 << 14` (5 unidades do mapa, em ponto fixo) ela chama a
função que pega o anel (`0x0201762C`). O cheat troca os dois desvios "longe demais, pule"
por "não faz nada":

| Endereço | Original | Quer dizer | Com o cheat |
|---|---|---|---|
| 0x02017A56 | `D035` | `beq`: X longe demais, pule este | `46C0` (não faz nada) |
| 0x02017A88 | `D01C` | `beq`: Y longe demais, pule este | `46C0` (não faz nada) |

Sem os dois testes, todo coletável válido da área é pego no primeiro quadro.
**Conferido no emulador:** no Green Hill a carteira foi de 8 para 183 e o HUD de "8/185"
para "183/185" (o outro contador, de 0/11 para 10/11); no Nocturne, mais 24 anéis. Os que
sobram ficam fora da lista dessa área (atrás de uma porta ou de um evento, por exemplo).

### Pasta "Projeto: multiplicador de anéis", escolha 1

| Cheat | Código | Efeito | Confiança |
|---|---|---|---|
| Anéis x2 na carteira | `02017648 F01F3102` | cada anel pego vale 2 | [média] |
| Anéis x5 na carteira | `02017648 F01F3105` | cada anel pego vale 5 | [média] |
| Anéis x10 na carteira | `02017648 F01F310A` | cada anel pego vale 10 | [média] |

A função que pega um anel (`0x0201762C`) soma 1 em **dois** lugares: primeiro no contador
da área (o "x/185" do HUD, em `0x02160EB0`), depois na carteira (esquadrão `+0x114`):

| Endereço | Original | Quer dizer |
|---|---|---|
| 0x0201763A | `1C52` | `adds r2, r2, #1`: contador da área + 1 |
| 0x02017648 | `1C49` | `adds r1, r1, #1`: carteira + 1 |

O cheat público "×2" troca o primeiro, então ele **só dobra o contador do HUD**: a carteira
continua subindo de 1 em 1. Os nossos trocam o segundo por `adds r1, #N` (`3102`, `3105`,
`310A`). Como a palavra de 4 bytes em `0x02017648` tem a instrução seguinte junto, o código
confere e escreve as duas (`F01F` é a primeira metade de um `bl`, que fica igual).
**Conferido no emulador**, pegando o mesmo anel no Green Hill:

| Cheat | Carteira | Contador da área |
|---|---|---|
| nenhum | 8 → 9 | 8 → 9 |
| público ×2 (`0201763A`) | 8 → 9 | 8 → 10 |
| Anéis x2 | 8 → 10 | 8 → 9 |
| Anéis x5 | 8 → 13 | 8 → 9 |
| Anéis x10 | 8 → 18 | 8 → 9 |

Eles ficam numa pasta de escolha porque escrevem no mesmo endereço. Combinam com o "Pegar
todos os anéis da área": no Green Hill, com o x10, são 1750 anéis de uma vez.

### Pasta "Projeto: POW"

| Cheat | Escreve | Efeito | Confiança |
|---|---|---|---|
| POW: compra sem gastar pontos | patch de código em `0x0209451C` e `0x02094578` | comprar um nível de golpe não exige nem gasta pontos | [média] |
| POW: 99 pontos para o grupo | atributo 75 = 99 | 99 pontos de POW para todos | [média] |
| POW: todos os golpes no nível III | atributos 69 a 74 = 3 | os 6 golpes de todos no nível III | [média] |

Na tela de perfil, o botão "POW Moves" abre a loja de golpes: cada personagem tem 6, com
níveis I, II e III, e cada nível custa pontos ("Points") que vêm com os níveis de
experiência. Esses números moram no **mesmo vetor de atributos** dos cheats do grupo (o
vetor tem 115 posições, não 47 como eu tinha visto):

| Posição | Atributo | Conferido |
|---|---|---|
| 68 (`+0x110`) | nível do personagem | perfil (Sonic: 16) |
| 69 a 74 (`+0x114` a `+0x128`) | nível de cada um dos 6 golpes (0 a 3) | a tela de POW, golpe por golpe |
| 75 (`+0x12C`) | pontos de POW | "Points: 5" na tela; escrevi 77 e ela mostrou 77 |

Para achar o 75, pus um vigia de leitura no campo que mudava a tela: quem lia era a função
genérica de atributos (`0x02007AC0`), com o índice 0x4B = 75 no registrador.

**Compra sem gastar pontos.** A função que diz se dá para comprar (`0x020944EC`) confere
que o golpe tem nível menor que 3 e que o custo não passa dos pontos; a que compra
(`0x02094548`) tira o custo dos pontos e sobe o nível:

| Endereço | Original | Quer dizer | Com o cheat |
|---|---|---|---|
| 0x0209451C | `DC11` | `bgt`: custo maior que os pontos, não pode | `46C0` (não faz nada) |
| 0x0209457A | `1B01` | `subs r1, r0, r4`: pontos − custo | `1C01` = `adds r1, r0, #0`: pontos iguais |

O cheat público só faz a primeira troca. **Conferido no emulador** (Sonic com 5 pontos,
comprando o Whirlwind II, que custa 10): sem cheat, nada acontece; com o público, a compra
sai e os pontos ficam em **−5**; com o nosso, a compra sai e os pontos ficam em 5. Saindo e
voltando à tela, o Whirlwind continua no II. Os pontos da tela só são gravados no
personagem quando você aperta "Exit".

**Cuidados:** pontos negativos (o cheat público) não travaram nada no teste, mas os
próximos níveis vão gastar pontos para "pagar a dívida". E "todos no nível III" também liga
golpes que o personagem ainda tinha em 0; nas telas de POW eles aparecem normais (testado
no Sonic e no Tails), mas ainda não usamos um golpe assim numa batalha. Salvar com estes
cheats grava os níveis no save.

### Pasta "Projeto: XP"

| Cheat | Código | Efeito | Confiança |
|---|---|---|---|
| XP no máximo | esquadrão `+0x48` → objeto, `+0x50` = 2700000 | todos sobem ao nível 30 na próxima vitória | [média] |

O XP é **um só para o grupo todo** (cada personagem converte esse número em nível pela sua
curva, `Adv_<personagem>.gda`). Ele mora num objeto apontado pelo esquadrão em `+0x48`, no
campo `+0x50`. O nível 30 pede de 952810 (Rouge) a 2643707 (Eggman) de XP; 2700000 passa
de todos. **Conferido no emulador:** com o cheat, uma vitória levou o Sonic do nível 16 ao
30 (HP 570, o valor da tabela no nível 30) e a tela "Level Up!" deu os pontos de bônus.

**Cuidado:** subir de nível não tem volta. Se salvar depois, os níveis ficam no save.
Faça backup do `.sav` antes.

### Pasta "Projeto: Chao"

| Cheat | Escreve | Efeito | Confiança |
|---|---|---|---|
| Chao: todos no nível Max | nível 3 nos 45 Chao | os Chao que você tem ficam no nível máximo | [média] |
| Chao: os 5 de troca sem fio | Chao 40 a 44: nível 3 e 1 cópia | aparecem os 5 que só vinham por troca | [média] |

O jogo tem 45 Chao (`Chaos.gda`). Os 5 últimos (40 a 44, como o Pooki e o Farfinkle) têm
`Hatchable = 0` e `Viral = 1`: não nascem no jardim, só chegam por troca sem fio com outro
DS. Por isso a tela de save mostra "40/40" mesmo com a coleção "completa".

Cada Chao ocupa 10 bytes a partir de esquadrão `+0x424`, na ordem do número:

| Byte | O que é | Como foi conferido |
|---|---|---|
| 0 | número do Chao (0 a 44) | igual à posição, nos dois saves |
| 1 | nível: 0 = não tem, 3 = Max | todos os 40 do Capítulo 10 estão em 3 e aparecem como "Max!" |
| 2 | cópias | o Seeri foi de 6 para 7 quando um ovo chocou, e a tela mostrou "Copies: 7" |

A pista pública dizia "passo de 9 a partir de `0x02226605`"; o passo é 10, e
`0x02226605` é o nível do Chao 0 (esquadrão `0x022261E0` + `0x425`).

**Conferido no emulador:** no save do Green Hill (nenhum Chao), só o nível não basta: o
jardim mostrou "0/40", porque ele conta quem tem cópias. Com nível 3 e 1 cópia, mostrou
"45/45, Maxed: 45". No save do Capítulo 10, com os dois cheats, o jardim mostrou
"45/45, Maxed: 45" e os Chao continuaram com as cópias que tinham.

**Cuidado:** os Chao ficam no save se salvar. O efeito dos 5 de troca na batalha ainda não
foi testado.

### Pasta "Projeto: grupo"

Cada personagem é um objeto `CGamePlayerCreature` no heap. O endereço muda, mas o jogo
guarda uma **lista dos personagens** num lugar fixo: `0x02160B28` aponta para um vetor em
que a posição 1 é o primeiro personagem, a 2 o segundo, e assim por diante. A lista tem
**todos** os personagens que já entraram no grupo, não só os 4 da batalha: no save do
Capítulo 10 são 11, e o Omega, que está no time de batalha, é o 10º. Dentro da criatura,
`+0x1C` aponta para o vetor de atributos (4 bytes cada):

| Posição no vetor | Atributo | Conferido |
|---|---|---|
| 0 (`+0x00`) | HP atual | barra vermelha do retrato |
| 37 (`+0x94`) | Speed | tela de perfil (Spd) |
| 38 (`+0x98`) | Attack (acerto) | tela de perfil (Atk) |
| 39 (`+0x9C`) | Defense (esquiva) | tela de perfil (Def) |
| 40 (`+0xA0`) | HP máximo | barra vermelha e perfil |
| 41 (`+0xA4`) | Power (dano) | medido numa batalha: é o P da fórmula (veja as medições) |
| 42 (`+0xA8`) | Grit (armadura) | deduzido pela ordem |
| 43 (`+0xAC`) | Luck | tela de perfil (Lck) |
| 44 (`+0xB0`) | PP atual, ×4096 (ponto fixo) | barra azul |
| 46 (`+0xB8`) | PP máximo | perfil (PP 9/9 da Amy) |

Cada cheat repete este bloco para as posições 0 a 11 (aqui, a posição 1; a posição 0 não tem
a linha `DC`):

```
62160B28 00000000   se a lista existe...
B2160B28 00000000   offset = endereço da lista
DC000000 00000004   offset += 4 (posição 1; a posição 2 usa 8, ..., a 11 usa 2C)
30000000 02400000   se o ponteiro é menor que o fim da RAM...
40000000 01FFFFFF   ...e maior que o começo (trava: posição vazia ou lixo)
B0000000 00000000   offset = a criatura
50000000 020F9200   se o primeiro campo é a vtable de CGamePlayerCreature (trava)
B000001C 00000000   offset = o vetor de atributos
D9000000 000000A0   dado = HP máximo (posição 40)
D6000000 00000000   HP atual (posição 0) = dado
D2000000 00000000   fim
```

As duas travas são o que deixa o cheat seguro: se o heap estiver diferente no DS, ou a
posição estiver vazia, as condições falham e nada é escrito. Elas são necessárias: no
começo do jogo, com só Sonic e Amy, a posição 3 da lista tem lixo (pedaço de um nome de
arquivo, `0x6C616D69`) e a 8 tem um endereço válido que não é uma criatura. As travas
pulam as duas. A vtable é o
"RG" da classe: todo objeto `CGamePlayerCreature` começa com `0x020F9200`.

| Cheat | Escreve | Efeito | Confiança |
|---|---|---|---|
| HP do grupo sempre cheio | HP atual = HP máximo | ninguém do grupo morre | [média] |
| Grupo: Defense 99 | posição 39 = 99 | inimigo só acerta se `99 ≤ Attack + 1d20`: quase nunca | [média] |
| Grupo: Luck 99 | posição 43 = 99 | crítico se `1d100 < 99`: quase sempre | [média] |
| Grupo: Speed 60 | posição 37 = 60 | 1ª ação em `max(0, 60 − 60) + 1d2`: o grupo age primeiro | [média] |
| Grupo: Power 99 | posição 41 = 99 | dano bem maior | [média] |
| Grupo: PP 99 | posição 46 = 99 e posição 44 = `0x63000` | PP cheio sempre: POW à vontade | [média] |

[média] aqui quer dizer: no emulador, com o seu save, os valores mudaram, a tela de perfil
mostrou os números novos e, menos o Speed e o PP, o efeito foi medido numa batalha (veja
as medições abaixo). Ainda não foram testados no DS.

**Por que o PP usa dois números:** o PP atual é guardado em ponto fixo (valor × 4096) e o
PP máximo é inteiro. O Action Replay não sabe multiplicar, então não dá para copiar um no
outro como no HP. A saída é escrever valores prontos: máximo 99 e atual
99 × 4096 = `0x63000`. Na batalha, os 4 retratos mostraram "99 PP".

**Correção (v3):** a primeira versão só cobria as posições 1 a 4, achando que eram os 4
da batalha. Na batalha do Capítulo 10 o Omega (posição 10) tomou 164 de dano com o "HP
sempre cheio" ligado. Agora são as posições 0 a 11, e o mesmo teste deixou todos cheios.
A posição 0 entrou porque, segundo a conversa do painel, num jogo novo o Sonic fica nela;
nos saves que testamos ela estava vazia. Ordem no Capítulo 10: 1 Sonic, 2 Amy, 3 Tails,
4 Rouge, 5 Big, 6 Knuckles, 7 Cream, 8 Eggman, 9 Shadow, 10 Omega, 11 Shade (o nome está
num ponteiro em `+0x98` da criatura).

**Tamanho:** repetir o bloco 11 vezes deixa cada cheat com cerca de 1 KB. O Pico Loader
copia os cheats ligados para a RAM principal, no espaço livre logo depois do código do
ARM7, sem um limite fixo (`arm9/source/Arm7Patcher.cpp` do Pico Loader). Um laço do AR
(`C0`) seria menor, mas laço com condições dentro é o caso mais sujeito a diferenças entre
motores de cheat; o bloco repetido usa só códigos que já têm teste no nosso interpretador.

**Cuidado:** estes atributos podem ser gravados no save. Não salve com eles ligados se
quiser voltar ao normal depois (e faça backup do `.sav` antes de testar).

## Medições no emulador (fase A1)

Feitas em 08/10/2026 no py-desmume com o seu save, slot do Capítulo 10 (Nocturne), numa
batalha contra 4 Nocturne Decurion (340 HP). A técnica: um *savestate* logo antes do
golpe. Como o emulador é determinístico, carregar o mesmo estado e repetir os mesmos
toques dá **os mesmos dados sorteados**; a única coisa que muda entre uma rodada e outra é
o valor que o cheat escreve. Assim, a diferença no dano é efeito só do cheat.

**Regra 44 (k do grupo).** O golpe do Sonic na emboscada que abre a batalha (Sonic:
Power 39):

| k | 0 | 50 | 100 | 110 (normal) | 200 | 300 | 500 | 1000 | 2000 |
|---|---|---|---|---|---|---|---|---|---|
| dano | 26 | 22 | 27 | 28 | 37 | 47 | 67 | 117 | 217 |

De k = 50 em diante, dano = 17 + k/10, uma reta. Pela fórmula,
`0,9 × 39 + k/100 × (3dP/3) − A`: o dado deu 10 e o Grit do Decurion é 18
(35 − 18 = 17). O ponto fora da reta, k = 0, é o **piso** da fórmula: 17 é menor que
P/2 = 19,5, então o jogo soma P/4 = 9 e dá 26. Com k = 50 o dano (22) já passa de
19,5 e o piso não entra. Tudo bate com o [COMBATE.md](COMBATE.md#52-dano), inclusive
que o P é o atributo da posição 41: com o Attack (44) as contas não fecham.

**Regra 45 (k dos inimigos).** Primeiro golpe de um Decurion na Rouge:

| k | 0 | 60 (normal) | 300 |
|---|---|---|---|
| dano | 24 | 47 | 138 |

A mesma reta: 24 + k/100 × 38 (o dado deu 38). Com k = 300 a Rouge ficou com HP
negativo (−25): o jogo guarda o HP com sinal e a deixa nocauteada.

**Atributos do grupo,** no mesmo golpe da emboscada:

| Cheat | Dano do Sonic | Por quê |
|---|---|---|
| nenhum | 28 | |
| Power 99 | 101 | P = 99 (com 99 faces, o dado sorteia outro número) |
| Luck 99 | 60 | crítico: `39 × (90 + 110)/100 − 18 = 60`, exato |

**Defense 99:** em 24 rodadas de batalha, os inimigos acertaram 5 golpes sem o cheat e 1
com ele. Esse 1 pode ter sido um ataque que não se esquiva (Inescapable); ainda não
conferimos.

**HP sempre cheio:** com k dos inimigos em 300, sem o cheat a Rouge e o Omega caíram;
com ele, os 11 personagens terminaram com HP cheio.

Para repetir: com `emu_run.py`, carregue o save (`sav`), ande até uma batalha, grave um
*savestate* (`save`) e, a partir dele, compare rodadas com e sem `cheat`, lendo o HP do
inimigo com `ler`. Os *savestates* têm a RAM do jogo, por isso ficam fora do Git.

## Mapa das 74 regras de combate

Todas as regras de `combatrules.gda` moram em endereço fixo. O mapa saiu de
`analise/tools/mapa_regras.py`, que executa no Unicorn a função que as carrega
(0x0201f270) e anota onde cada linha é gravada. Os valores foram lidos no emulador logo
depois do boot e batem com o [COMBATE.md](COMBATE.md).

Formatos: **int** = número inteiro; **fx** = ponto fixo do DS (valor × 4096); **bool** = 0
ou 1; **fx/100** e **fx/1000** = o valor da tabela dividido por 100 ou 1000, em ponto fixo.
Para não errar a conversão, use:

```
python3 analise/tools/ar_codes.py regra 47 30     →  020F64B4 0000001E
python3 analise/tools/ar_codes.py regra 71 50     →  021A57C0 00000800
```

| Regra | Endereço | Formato | Valor (boot) | Uso |
|---|---|---|---|---|
| 0 | `0x020F6480` | int | 90 | não usada no código |
| 1 | `0x020F6474` | int | 60 | iniciativa: base (60) |
| 2 | `0x020F6484` | int | 2 | iniciativa: dado 1dN |
| 3 | `0x021A57B4` | fx | 1 | iniciativa: multiplicador do Speed |
| 4 | `0x020F6478` | bool | 1 | 0x020451c4 (não analisada) |
| 5 | `0x020F64E0` | int | 24 | minijogo de toque e câmera dos POW |
| 6 | `0x020F64DC` | int | 24 | minijogo de toque e câmera dos POW |
| 7 | `0x020F6470` | int | 7 | Defender: +Defense ×R/10 |
| 8 | `0x020F64FC` | int | 20 | Defender: +Grit ×R/10 |
| 9 | `0x020F64D8` | int | 1000 |  |
| 10 | `0x020F64F4` | int | 1 | 0x02043ea8 (não analisada) |
| 11 | `0x020F64F0` | int | 1 | Defender: recupera PP (liga/desliga) |
| 12 | `0x020F64EC` | int | 1 | 0x020436e4 (não analisada) |
| 13 | `0x020F64E8` | int | 1 | 0x020441cc (não analisada) |
| 14 | `0x020F64E4` | int | 0 | 0x02042034 (não analisada) |
| 15 | `0x021AC29C` | fx | 100 | minijogo de toque e câmera dos POW |
| 16 | `0x021AC2A0` | fx | 135 | minijogo de toque e câmera dos POW |
| 17 | `0x021AC2A4` | fx | 250 | minijogo de toque e câmera dos POW |
| 18 | `0x021AC2D8` | fx | -20 | minijogo de toque e câmera dos POW |
| 19 | `0x021AC2DC` | fx | 15 | minijogo de toque e câmera dos POW |
| 20 | `0x021AC2E0` | fx | -50 | minijogo de toque e câmera dos POW |
| 21 | `0x021AC2A8` | fx | 0 | minijogo de toque e câmera dos POW |
| 22 | `0x021AC2AC` | fx | 100 | minijogo de toque e câmera dos POW |
| 23 | `0x021AC2B0` | fx | 230 | minijogo de toque e câmera dos POW |
| 24 | `0x021AC2B4` | fx | 0 | minijogo de toque e câmera dos POW |
| 25 | `0x021AC2B8` | fx | 85 | minijogo de toque e câmera dos POW |
| 26 | `0x021AC2BC` | fx | 200 | minijogo de toque e câmera dos POW |
| 27 | `0x021AC2C0` | fx | 100 | minijogo de toque e câmera dos POW |
| 28 | `0x021AC2C4` | fx | 100 | minijogo de toque e câmera dos POW |
| 29 | `0x021AC2C8` | fx | 250 | minijogo de toque e câmera dos POW |
| 30 | `0x021AC2FC` | fx | -20 | minijogo de toque e câmera dos POW |
| 31 | `0x021AC300` | fx | -10 | minijogo de toque e câmera dos POW |
| 32 | `0x021AC304` | fx | -50 | minijogo de toque e câmera dos POW |
| 33 | `0x020F64F8` | int | 4 | iniciativa: divisor |
| 34 | `0x021A57F0` | bool | 0 | exploração: início do combate |
| 35 | `0x021A57E8` | fx/1000 | ≈ 833 | interface do combate em tempo real |
| 36 | `0x021AC288` | int | 11 | 0x02069d88 (não analisada) |
| 37 | `0x021AC28C` | int | 54 | 0x02069d88 (não analisada) |
| 38 | `0x020F944C` | int | 16 | interface do combate em tempo real |
| 39 | `0x020F64D4` | int | 100 | dano básico (100) |
| 40 | `0x020F64D0` | int | 5 | desempenho do minijogo POW |
| 41 | `0x020F64CC` | int | 30 | desempenho do minijogo POW |
| 42 | `0x020F64C8` | int | 1000 | desempenho do minijogo POW |
| 43 | `0x020F64C4` | int | 90 | dano: parte fixa (90 = 0,9 P) |
| 44 | `0x020F64C0` | int | 110 | dano: k do grupo |
| 45 | `0x020F64BC` | int | 60 | dano: k dos inimigos |
| 46 | `0x020F64B8` | int | 150 | (não analisada) |
| 47 | `0x020F64B4` | int | 10 | emboscada: dado |
| 48 | `0x021AC2CC` | fx | 150 | minijogo de toque e câmera dos POW |
| 49 | `0x021AC2D0` | fx | 200 | minijogo de toque e câmera dos POW |
| 50 | `0x021AC2D4` | fx | 250 | minijogo de toque e câmera dos POW |
| 51 | `0x021A57E0` | fx/100 | ≈ 7369 | (não analisada) |
| 52 | `0x021A57DC` | fx/100 | ≈ 120 | (não analisada) |
| 53 | `0x021A57EC` | fx/1000 | ≈ 100 | exploração: início do combate |
| 54 | `0x021A57D8` | fx/100 | ≈ 50 | (não analisada) |
| 55 | `0x020F64B0` | int | 2 | 0x0203d274 (não analisada) |
| 56 | `0x020F64AC` | int | 6 | 0x0203d274 (não analisada) |
| 57 | `0x021A57D4` | int | 0 | dificuldade: Defense (+) |
| 58 | `0x020F64A8` | int | 3 | dificuldade: Power (+) |
| 59 | `0x020F64A4` | int | 1 | dificuldade: Attack (+) |
| 60 | `0x021A57D0` | int | 0 | dificuldade: Grit (+) |
| 61 | `0x020F64A0` | int | 20 | dificuldade: HP máximo (+) |
| 62 | `0x020F649C` | int | 2 | dificuldade: divisor (+) |
| 63 | `0x020F6498` | int | 6 | dificuldade: nível máximo |
| 64 | `0x021A57CC` | int | -4 | dificuldade: nível mínimo |
| 65 | `0x020F6494` | int | 2 | dificuldade: divisor (−) |
| 66 | `0x021A57C8` | int | 2 | dificuldade: Defense (−) |
| 67 | `0x020F6490` | int | 5 | dificuldade: Power (−) |
| 68 | `0x020F648C` | int | 2 | dificuldade: Attack (−) |
| 69 | `0x020F6488` | int | 5 | dificuldade: Grit (−) |
| 70 | `0x021A57C4` | int | 0 | dificuldade: HP máximo (−) |
| 71 | `0x021A57C0` | fx/100 | ≈ 90 | minijogo: escala do golpe nível 1 |
| 72 | `0x021A57BC` | fx/100 | ≈ 95 | minijogo: escala do golpe nível 2 |
| 73 | `0x021A57B8` | fx/100 | ≈ 100 | minijogo: escala do golpe nível 3 |

As regras 35 e 51 têm valores grandes cujo sentido ainda não conhecemos. Não mexa nelas
antes de ler quem as usa.

## Protocolo de teste no DS

1. **Backup do save antes de tudo**: copie o `.sav` do Sonic Chronicles (na pasta da ROM,
   `D:\ROMs\DS`) para outra pasta. Os cheats de regras e dificuldade não ficam no save,
   mas os de anéis e de atributos do grupo provavelmente ficam, e um cheat errado pode
   travar o jogo durante um salvamento.
2. **Um cheat por vez.** Ligue só um, teste, desligue, reabra o jogo. Assim, se algo der
   errado, sabemos qual foi.
3. **Anote** o cheat, a batalha e os números (ou só "funcionou / não percebi / travou").
   Com isso eu atualizo a confiança no `YWSE.txt` e registro no [diário](DIARIO.md).

## Aula: lendo os cheats públicos

O banco público (DeadSkullzJr) já traz 13 cheats do Sonic Chronicles, que estão no seu
cartão na pasta "Miscellaneous Codes". Eles não são nossos e ainda não foram conferidos
pelo projeto, mas mostram técnicas que vamos usar. Os códigos abaixo são os publicados em
[Almar's Guides](https://almarsguides.com/retro/walkthroughs/NDS/Games/SonicChroniclesTheDarkBrotherhood/ActionReplay/)
e da [SuperCheats](https://www.supercheats.com/nintendods/sonic-chronicles-the-dark-brotherhood/3988/ar-codes/us-action-replay-codes/).
Antes de usar, compare com a sua cópia: `usrcheat.py listar usrcheat.dat YWSE`.

**Multiplicador de anéis (×2):**
```
52017638 1C525842    se a palavra em 0x02017638 for 1C525842 (o código original)...
02017638 32025842    ...troca por 32025842
D2000000 00000000    fim
```
Isto é um **patch de código**, não de dado. Em 0x02017638 há duas instruções Thumb de 16
bits (a memória guarda o byte baixo primeiro, então `5842` vem antes de `1C52`):

| Endereço | Original | Quer dizer | Depois do cheat |
|---|---|---|---|
| 0x02017638 | `5842` | `ldr r2, [r0, r1]`: lê o contador de anéis | igual |
| 0x0201763A | `1C52` | `adds r2, r2, #1`: soma **1** anel | `3202` = `adds r2, #2`: soma **2** |

As versões ×4, ×8 e ×16 só trocam o número (`3204`, `3208`, `3210`). A primeira linha
(tipo 5, "se igual") é uma trava de segurança: o cheat só escreve se o código original
estiver lá. Se o jogo fosse outra versão, ele não faria nada em vez de quebrar.
**Conferido no emulador:** esse `adds` é o do contador da área (o "x/185" do HUD), não o da
carteira. Com o ×2 público, o HUD sobe de 2 em 2 e a carteira de 1 em 1. Os nossos
multiplicadores trocam o `adds` da carteira, 14 bytes depois (pasta "multiplicador de
anéis").

**Coletar itens de longe:** `52017A20 D14F2803`, depois `02017A20 46C02803`. Em 0x02017A20
há `2803` (`cmp r0, #3`) e em 0x02017A22 há `D14F` (`bne`: "se não for 3, pule"). O cheat
troca o `bne` por `46C0` (`mov r8, r8`, uma instrução que não faz nada). Sem o desvio, o
jogo segue como se o teste tivesse passado. O mesmo truque é feito em 0x02017A56 e
0x02017A88. **Lido no assembly e conferido no emulador:** o `bne` de 0x02017A22 é o teste
do tipo (anel ou o outro coletável) e não precisava ser trocado, porque o jogo repete esse
teste em 0x02017A8A antes de pegar; os que fazem o trabalho são os de 0x02017A56 e
0x02017A88 (distância em X e em Y). O nosso "Pegar todos os anéis da área" troca só esses
dois.

**Pontos de habilidade:** `5209451C 1C28DC11`, depois `0209451C 1C2846C0`. É a compra de
níveis de POW: troca o teste "custo maior que os pontos" por "não faz nada". **Conferido
no emulador:** a compra sai, mas o custo continua sendo descontado e os pontos ficam
negativos (5 − 10 = −5). O nosso "POW: compra sem gastar pontos" troca também a conta.

**Dinheiro (ponteiro):**
```
621D10AC 00000000    se a palavra em 0x021D10AC for diferente de 0 (ponteiro válido)...
B21D10AC 00000000    offset = o valor guardado em 0x021D10AC (o endereço de um objeto)
00000114 0001869F    escreve 99999 em offset + 0x114
D2000000 00000000    fim (zera o offset)
```
O dinheiro mora num objeto no heap. Um ponteiro guarda **onde** ele está, e o cheat segue
esse ponteiro a cada quadro. A ideia é boa, mas o ponteiro escolhido, `0x021D10AC`, também
está no heap: ele só funciona enquanto o heap tiver a arrumação de sempre. O nosso cheat
de anéis parte de `0x02160C18`, que está na BSS e não depende disso.

**Anéis (`022262F4 000F432F`):** escreve direto num endereço do heap, sem ponteiro. Hoje
sabemos que `0x022262F4` é a carteira (esquadrão em `0x022261E0` + `0x114`). Nos estados que
vimos (tela de título, Green Hill, Nocturne) o esquadrão estava sempre em `0x022261E0`,
porque ele é criado cedo e não muda de lugar. Então o código público provavelmente
funciona nesta versão. A SuperCheats avisa que, com ele ligado, o Sonic erra todos os
ataques; isso não apareceu no emulador. Dois detalhes: `000F432F` é 1000239, mais do que
cabe na tela (o máximo que aparece inteiro é 999999), e um endereço fixo no heap é uma
aposta: com a ROM do painel v0.2, que empurra o heap, ele escreveria em cima de outra
coisa. O nosso usa o ponteiro, que continua certo mesmo se o objeto mudar de lugar.

## O que vem depois

| Categoria | Falta | Como |
|---|---|---|
| Medir no DS | os cheats [média] e [alta] | protocolo acima, um por vez |
| Inventário | conferir a loja com "Itens não acabam"; cheat para ganhar itens novos | teste na loja; ler a função que cria itens |
| Loja | compra de graça: a compra (`0x020B3AB0`) confere `carteira >= preço` e faz `carteira − preço` em `0x020B3AD0` | achar uma loja num estado do emulador para conferir |
| POW | usar numa batalha um golpe que estava em 0 e foi para III | batalha com "todos no nível III" |
| Combate | vencer a batalha, nocautear inimigos, sem encontros | ler o `GameModeCombat` |
| Mundo | flags de história, teletransporte | ler as funções de plot |

A ferramenta já existe: `analise/tools/emu_run.py` carrega o seu save (`sav`), liga
cheats (`cheat`), lê a RAM (`ler`) e grava/carrega *savestates* (`save`/`load`), que é o
que as medições acima usaram.
