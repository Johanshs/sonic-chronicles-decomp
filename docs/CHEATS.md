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

Confiança:
- **[DS]**: testado no DS real em 08/10/2026, a olho (ligou, o jogo rodou e o efeito foi o
  esperado).
- **[alta]**: o endereço já foi testado no DS; só o valor é novo. A conta vem do
  [COMBATE.md](COMBATE.md), onde as fórmulas têm confiança alta.
- **[média]**: o endereço foi conferido só no emulador, pelo valor dele depois do boot.

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

## Protocolo de teste no DS

1. **Backup do save antes de tudo**: copie o `.sav` do Sonic Chronicles (na pasta da ROM,
   `D:\ROMs\DS`) para outra pasta. Os cheats desta bateria não escrevem no save, mas um
   cheat errado pode travar o jogo durante um salvamento.
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

**Coletar itens de longe:** `52017A20 D14F2803`, depois `02017A20 46C02803`. Em 0x02017A20
há `2803` (`cmp r0, #3`) e em 0x02017A22 há `D14F` (`bne`: "se não for 3, pule"). O cheat
troca o `bne` por `46C0` (`mov r8, r8`, uma instrução que não faz nada). Sem o desvio, o
jogo segue como se o teste tivesse passado. O mesmo truque é feito em 0x02017A56 e
0x02017A88. O que exatamente cada teste confere, vamos ler no assembly com a ROM.

**Dinheiro (ponteiro):**
```
621D10AC 00000000    se a palavra em 0x021D10AC for diferente de 0 (ponteiro válido)...
B21D10AC 00000000    offset = o valor guardado em 0x021D10AC (o endereço de um objeto)
00000114 0001869F    escreve 99999 em offset + 0x114
D2000000 00000000    fim (zera o offset)
```
O dinheiro mora num objeto no heap, que muda de lugar. Mas uma global fixa
(0x021D10AC) guarda **onde** o objeto está. O cheat segue esse ponteiro a cada quadro.
É exatamente o que a fase A2 vai fazer para HP, PP e itens.

**Anéis (`022262F4 000F432F`):** escreve direto num endereço do heap, sem ponteiro. A
SuperCheats avisa que, com ele ligado, o Sonic erra todos os ataques. A explicação mais
provável: naquele momento o objeto dos anéis estava em outro lugar e o cheat escreveu em
cima de outra coisa. É por isso que, para dados do heap, a A2 exige um ponteiro que
sobreviva a trocar de área e recarregar o save.

## O que vem depois (precisa da ROM)

Tudo acima usa endereços fixos que já conhecíamos. O resto do "modificar qualquer coisa"
mora no heap ou em código que ainda não lemos:

| Categoria | Cheats previstos | O que falta |
|---|---|---|
| Regras de combate | uma entrada para cada uma das 74 regras (iniciativa, emboscada, minijogo POW...) | ler `CRules_LoadCombatRules` para saber o endereço de cada regra |
| Grupo | HP/PP infinitos, atributos, nível, XP ×N | busca na RAM (A2) e a cadeia de ponteiros |
| Inventário | anéis, dinheiro, qualquer item, Chao | A2; conferir o ponteiro público 0x021D10AC |
| Combate | vencer a batalha, nocautear inimigos, sem encontros | A2 e leitura do `GameModeCombat` |
| Mundo | flags de história, teletransporte | leitura das funções de plot |

A ferramenta para isso já existe: `analise/tools/emu_run.py` liga cheats no emulador
(ação `cheat cheats/YWSE.txt TEXTO`) e lê endereços (`ler 020F64C0`). A busca na RAM
(`ram_busca.py`) é o próximo passo da A2.
