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

### Pasta "Projeto: anéis"

| Cheat | Código | Efeito | Confiança |
|---|---|---|---|
| Anéis sempre 9999 | `02160EB0 0000270F` | o contador de anéis do HUD fica em 9999 | [média] |

**Como foi achado:** no emulador, com o seu save, peguei um anel (8 → 9) e procurei na RAM
os valores que eram 8 e passaram a 9. Sobraram dois: `0x02160EB0` (BSS, endereço fixo) e
`0x022262F4` (heap, o do cheat público). Escrevi 500 em cada um, um por vez: só o
`0x02160EB0` mudou o número do HUD, e ao pegar outro anel ele foi para 501. O outro
contador também soma 1 por anel, mas não aparece na tela; ainda não sabemos para que
serve (talvez o total da área). Ainda não conferimos se a loja usa o mesmo contador.

**Cuidado:** se você salvar com o cheat ligado, os 9999 anéis provavelmente ficam no save.

### Pasta "Projeto: grupo"

Cada membro do grupo é um objeto `CGamePlayerCreature` no heap. O endereço muda, mas o
jogo guarda uma **lista do grupo** num lugar fixo: `0x02160B28` aponta para um vetor em que
a posição 1 é o primeiro membro, a 2 o segundo, e assim por diante. Dentro da criatura,
`+0x1C` aponta para o vetor de atributos (4 bytes cada):

| Posição no vetor | Atributo | Conferido |
|---|---|---|
| 0 (`+0x00`) | HP atual | barra vermelha do retrato |
| 37 (`+0x94`) | Speed | tela de perfil (Spd) |
| 38 (`+0x98`) | Attack (acerto) | tela de perfil (Atk) |
| 39 (`+0x9C`) | Defense (esquiva) | tela de perfil (Def) |
| 40 (`+0xA0`) | HP máximo | barra vermelha e perfil |
| 41 (`+0xA4`) | Power (dano) | deduzido pela ordem; não aparece no perfil |
| 42 (`+0xA8`) | Grit (armadura) | deduzido pela ordem |
| 43 (`+0xAC`) | Luck | tela de perfil (Lck) |
| 44 (`+0xB0`) | PP atual, ×4096 (ponto fixo) | barra azul |
| 46 (`+0xB8`) | PP máximo | perfil (PP 9/9 da Amy) |

Cada cheat repete este bloco para os membros 1 a 4 (aqui, o membro 1):

```
62160B28 00000000   se a lista existe...
B2160B28 00000000   offset = endereço da lista
DC000000 00000004   offset += 4 (posição 1; o membro 2 usa 8, e assim por diante)
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
posição do grupo estiver vazia, as condições falham e nada é escrito. A vtable é o
"RG" da classe: todo objeto `CGamePlayerCreature` começa com `0x020F9200`.

| Cheat | Escreve | Efeito | Confiança |
|---|---|---|---|
| HP do grupo sempre cheio | HP atual = HP máximo | ninguém do grupo morre | [média] |
| Grupo: Defense 99 | posição 39 = 99 | inimigo só acerta se `99 ≤ Attack + 1d20`: quase nunca | [média] |
| Grupo: Luck 99 | posição 43 = 99 | crítico se `1d100 < 99`: quase sempre | [média] |
| Grupo: Speed 60 | posição 37 = 60 | 1ª ação em `max(0, 60 − 60) + 1d2`: o grupo age primeiro | [média] |
| Grupo: Power 99 | posição 41 = 99 | dano bem maior | [baixa] |

[média] aqui quer dizer: no emulador, com o seu save, os valores mudaram e a tela de perfil
mostrou os números novos. Ainda não vimos o efeito numa batalha.

**Cuidado:** estes atributos podem ser gravados no save. Não salve com eles ligados se
quiser voltar ao normal depois (e faça backup do `.sav` antes de testar).

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

## O que vem depois

| Categoria | Falta | Como |
|---|---|---|
| Medir o dano (A1) | entrar numa batalha no emulador e comparar com as fórmulas | achar um inimigo no mapa com o seu save |
| Grupo | PP cheio (o PP atual é ponto fixo e o máximo é inteiro: o AR não converte), XP, nível | XP: ainda não está no vetor de atributos |
| Inventário | itens, Chao, conferir se a loja usa o contador de anéis | busca na RAM ao comprar algo |
| Combate | vencer a batalha, nocautear inimigos, sem encontros | ler o `GameModeCombat` |
| Mundo | flags de história, teletransporte | ler as funções de plot |

A ferramenta já existe: `analise/tools/emu_run.py` carrega o seu save (`sav`), liga
cheats (`cheat`) e lê a RAM (`ler`).
