# Plano: mod menu dentro do jogo e cheats para R4

Branch: `mod-menu`. Status: **plano**. Nada aqui foi construído ainda, exceto onde está
escrito "conferido".

O objetivo é ter um **painel de administração dentro do jogo**: aperta-se uma
combinação de botões, o jogo pausa, aparece um menu na tela de baixo e dá para mudar
regras de combate, atributos, itens, dificuldade, e testar o que quisermos. Ele deve
rodar num DS de verdade a partir de um cartão R4 e também em emulador.

Há dois caminhos, e o plano faz os dois, nesta ordem:

| | **A. Cheats (Action Replay)** | **B. Mod menu (código injetado)** |
|---|---|---|
| O que é | códigos que o motor de cheats do cartão aplica a cada quadro | código C nosso, compilado e embutido na ROM |
| Onde roda | só com um motor de cheats (Pico Loader, kernel do R4, emulador) | em qualquer lugar: a ROM modificada já tem o menu |
| Pode | escrever valores na RAM, com condições e botões | qualquer coisa: menus, chamar funções do jogo, mostrar texto |
| Esforço | dias | semanas |
| Serve para | provar os endereços e ter os primeiros "botões de admin" | o painel completo |

O caminho A vem primeiro porque **descobre e valida os endereços** que o B vai usar.

---

## 1. O que já sabemos (base técnica)

- **O ARM9 não tem overlays nem compressão**: todo o código fica na RAM o tempo todo, em
  endereços fixos. Para quem faz cheats e patches, isso é o melhor caso possível.
- **Mapa da memória** (cabeçalho e parâmetros do NitroSDK, conferido):

  | Região | Endereço | Observação |
  |---|---|---|
  | código e dados do ARM9 | 0x02000000–0x021090E0 | carregado da ROM |
  | BSS (variáveis zeradas) | 0x021090E0–0x021B9500 | as globais do combate estão aqui ou em `.data` |
  | heap do jogo (arena) | a partir de ~0x021B9500 | objetos criados em tempo de execução |
  | ITCM | 0x01FF8000, 0x6DE0 usados de 0x8000 | ~4,6 KB livres (código rápido) |
  | DTCM | 0x027E0000, 0x1060 usados | também guarda a pilha |

- **Variáveis de combate em endereço fixo**, lidas da tabela `CombatRules` na
  inicialização ([COMBATE.md](COMBATE.md), seção 15). **Conferido no emulador**: depois do
  boot, `0x020F64C0` = 110 (regra 44), `0x020F64BC` = 60 (regra 45), `0x020F6470` = 7
  (regra 7, que vale 2 no binário: a prova de que a tabela foi carregada por cima).
- **Dificuldade dinâmica**: nível em `0x02160E54` (byte com sinal) e chave em `0x02160E58`.
- **Ponteiros para objetos** (grupo, inventário, criaturas na batalha) ainda **não** são
  conhecidos: ficam no heap e mudam de lugar. O jogo os acha por um armazém de objetos
  (`CGameObjectStorage`, consultado em `0x0200B1E0`/`0x0200B1A0` sobre `0x02160AAC`). A
  fase A2 vai seguir essa cadeia.

## 2. O cartão: R4 SDHC + Pico Loader

O [Pico Loader](https://github.com/LNH-team/pico-loader) (LNH team, licença zlib) carrega
jogos de DS e homebrew. Ele foi feito para o DSpico, mas também funciona em vários
cartões. A lista inclui o R4DS original e várias versões do **R4i-SDHC**:
`r4isdhc.com.cn`, `r4isdhc.hk` (2020+), `r4isdhc.com` (2014+), `r4i-sdhc.com`, `r4idsn.com`
e `r4rts.com`. O [Pico Launcher](https://github.com/LNH-team/pico-launcher) é o menu que
roda por cima dele e tem **suporte a cheats**: lê `/_pico/usrcheat.dat` (o mesmo formato
de banco de cheats dos kernels de R4/Wood). Os cheats são abertos com **Y** sobre o jogo,
e liga-se cada código com **A**.

### O cartão do projeto: R4i-SDHC Gold Pro (r4isdhc.com)
O Pico Loader é compilado **por plataforma**, e muitos clones de R4 se comportam como
outro cartão mais antigo. Na tabela de plataformas do Pico Loader, os cartões **`r4isdhc.com` de
2014 em diante** usam a plataforma **`DSTT`**, a mesma do DSTT e do SuperCard DSONE
SDHC (ou seja, o loader fala com eles do mesmo jeito), **com** suporte a leitura por DMA. Sem DMA, alguns jogos têm problemas de
cache; não é o nosso caso. O Gold Pro é dessa família, então:

- **Pico Loader**: baixar `Pico_Loader_DSTT.zip` da
  [última release](https://github.com/LNH-team/pico-loader/releases) (v1.7.1, de
  28/06/2026, quando este plano foi escrito).
- **Pico Launcher**: `LAUNCHER.nds` da
  [release dele](https://github.com/LNH-team/pico-launcher/releases).

**O que ainda não está confirmado:** a documentação do Pico Launcher só descreve a
instalação no DSpico. Num R4, quem abre o `LAUNCHER.nds` é o kernel do cartão, e o
launcher precisa ler o SD. Kernels de R4i costumam aplicar o patch DLDI automaticamente
ao abrir homebrew, o que resolveria isso, mas só um teste no aparelho confirma. Por isso a
fase A0 tem um plano B.

Instalação a testar:
```
SD:/_pico/picoLoader7.bin      ← do Pico_Loader_DSTT.zip
SD:/_pico/picoLoader9.bin      ← do Pico_Loader_DSTT.zip (a versão DSTT)
SD:/_pico/aplist.bin, savelist.bin, patchlist.bin
SD:/_pico/usrcheat.dat         ← cheats (gerado pela fase A3)
SD:/LAUNCHER.nds               ← aberto pelo menu do kernel do R4
```
(Os arquivos do kernel original do cartão continuam no SD; o Pico só se soma a eles.)

**Plano B, se o Pico Launcher não abrir pelo kernel:** o próprio kernel do R4i-SDHC tem
um motor de cheats que também lê `usrcheat.dat` (a pasta depende da versão do kernel).
Outra opção conhecida para esses cartões é o TWiLight Menu++ com o nds-bootstrap, que
também lê `usrcheat.dat`. Os códigos Action Replay são os mesmos em qualquer um deles, e o
caminho B (o menu) não depende de cartão.

## 3. Caminho A: cheats Action Replay

### Como um código AR funciona (para entender o que vamos escrever)
Cada linha tem 2 palavras de 32 bits. O motor executa a lista **a cada quadro**:

| Código | Faz |
|---|---|
| `0XXXXXXX YYYYYYYY` | escreve 32 bits YYYYYYYY no endereço XXXXXXX |
| `1XXXXXXX 0000YYYY` | escreve 16 bits |
| `2XXXXXXX 000000YY` | escreve 8 bits |
| `9XXXXXXX ZZZZYYYY` | só continua se `(valor de 16 bits & ~ZZZZ) == YYYY` (usado com botões) |
| `BXXXXXXX 00000000` | lê um **ponteiro** em XXXXXXX e passa a escrever relativo a ele |
| `D0000000 00000000` | fim do bloco condicional |

Os botões ficam em `0x04000130` (bit em 0 = apertado): A = bit 0, B = 1, Select = 2,
Start = 3, R = 8, L = 9. Assim, "L + R apertados" é `94000130 FCFF0000`.

### Primeiros cheats (rascunho, a validar na fase A1)
Valores tirados de [COMBATE.md](COMBATE.md). **Testados no DS real em 08/10/2026**: os 4
ligaram e o efeito visto em batalha foi o esperado (ver "Andamento" abaixo). Falta a
medição da fase A1: conferir os números contra as fórmulas.

```
[Dano do grupo bem maior (k 110 → 1000: o termo aleatório pesa 9× mais)]
020F64C0 000003E8

[Inimigos sem a parte aleatória do dano (k 60 → 0)]
020F64BC 00000000

[Defender: Grit ×11 em vez de ×3 (regra 8: 20 → 100)]
020F64FC 00000064

[Dificuldade dinâmica no mínimo (−4) enquanto L+R estiverem apertados]
; a confirmar: cada inimigo guarda uma cópia do nível no começo da batalha (+0x1d8)
94000130 FCFF0000
22160E58 00000001
22160E54 000000FC
D0000000 00000000
```

Por que funcionam: o jogo carrega as regras **uma vez**, no boot, e lê as globais na hora
de cada conta. O cheat reescreve a global a cada quadro, então a nova regra vale em toda
batalha. É o mesmo efeito de mudar `CombatRules.csv` com o `sonic-mod`, só que ligável e
desligável sem gerar outra ROM.

### Fases

| Fase | O que | Pronto quando | Dias |
|---|---|---|---|
| **A0** | montar o SD com o Pico Loader DSTT + Pico Launcher (seção 2); abrir o `LAUNCHER.nds` pelo kernel; abrir o jogo original por ele; ligar um cheat trivial do banco público para provar o motor. Se falhar: plano B | o jogo roda no DS pelo cartão e um cheat conhecido funciona | 1 |
| **A1** | `analise/tools/ar_codes.py`: aplica uma lista de códigos AR no py-desmume a cada quadro (as escritas e condições básicas); validar os 4 cheats acima numa batalha real | dano muda como a fórmula prevê, com captura de tela | 2–3 |
| **A2** | `analise/tools/ram_busca.py`: busca de valores na RAM no estilo Cheat Engine (valor exato → mudou → não mudou), com estados salvos; achar HP/PP/atributos do grupo, anéis e inventário, e a **cadeia de ponteiros** a partir de uma global fixa | cada endereço confirmado em 2 momentos diferentes do jogo (o ponteiro tem que sobreviver a trocar de área e recarregar o save) | 3–5 |
| **A3** | `cheats/YWSE.txt` (texto, no repositório: só endereços e valores, nada do jogo) e um gerador de `usrcheat.dat` (ou instruções para o editor R4CCE) | o Pico Launcher lista os cheats e eles funcionam no DS | 2 |

Cheats previstos depois da A2: HP/PP infinitos, anéis, todos os itens, XP ×N, vencer a
batalha, sem encontros, nível dos POW no máximo.

### Andamento: fase A0 (08/10/2026)
- **Cartão conferido**: o SD já tinha o Pico Launcher instalado (`r4.dat` abre
  `/_picoboot.nds`). O `picoLoader9.bin` é idêntico, byte a byte, ao da release
  **v1.6.0, plataforma DSTT**: a plataforma certa para o R4i-SDHC Gold Pro. A v1.7.1 é
  opcional; a v1.6.0 já roda os jogos.
- **Banco de cheats**: o `usrcheat.dat` do cartão é o de DeadSkullzJr (12/08/2025, 4.263
  jogos). Ele **já tem o Sonic Chronicles** (entrada `YWSE`, CRC `ACB0DF12`, que confere
  com a nossa ROM: `~crc32` do cabeçalho de 0x200 bytes).
- **Ferramenta**: `analise/tools/usrcheat.py` lê, extrai e grava esse formato. A ida e
  volta do banco inteiro (55 MB) sai idêntica byte a byte.
- **Pistas para a fase A2**, tiradas dos cheats públicos (endereços de terceiros, a
  conferir no emulador):

  | Endereço | O que o cheat diz | Observação |
  |---|---|---|
  | `0x022604A0` | HP (escreve 9999) | heap, mas em posição fixa |
  | `0x022262F4` | anéis | heap: é a carteira, esquadrão `0x022261E0` + `0x114` (conferido) |
  | `0x02226605`/`06` + 9×n | nível e posse dos Chao | o passo é 10: nível e cópias em esquadrão `+0x425`/`+0x426` (conferido) |
  | `0x021D10AC` (ponteiro) +0x114 | dinheiro | aponta para o esquadrão, mas fica no heap; o caminho fixo é `0x02160C18` (conferido) |
  | `0x021D10EE`, `0x021D10F8` | EXP | `0x021D10F8` é o XP do grupo (esquadrão `+0x48` → `+0x50`, conferido) |
  | `0x02160EB0` | anéis do tabuleiro | BSS: soma 1 por anel, mas não é a carteira (conferido) |
  | `0x0201763A` | patch de código (anéis ×2) | só dobra o contador da área; a carteira é `0x02017648` (conferido) |
  | `0x02017A20` | patch de código (coletar de longe) | funciona; os testes que importam são `0x02017A56`/`88` (conferido) |
  | `0x0209451C` | patch de código (pontos de habilidade) | compra de POW sai, mas os pontos ficam negativos (conferido) |

- **No cartão** (com autorização do dono): o `usrcheat.dat` de 55 MB foi trocado por um
  banco enxuto de 7,9 MB, gerado com `usrcheat.py`: as 248 entradas dos 27 jogos que estão
  no cartão (todas as regiões) e, na entrada do Sonic Chronicles, a pasta "Projeto
  sonic-chronicles-decomp" com os cheats de `cheats/YWSE.txt`. O banco completo é público
  ([DeadSkullzJr](https://gbatemp.net/threads/deadskullzjrs-nds-i-cheat-databases.488711/))
  e pode ser baixado de novo. Motivo da troca: o gravador do cartão aceita no máximo
  30 MB por arquivo, e o nome tem que ser `usrcheat.dat`.
- **Teste no DS (08/10/2026)**: com esse banco no cartão, os 4 cheats de
  `cheats/YWSE.txt` foram ligados pelo Pico Launcher. O jogo rodou sem erro e o efeito
  de cada um foi o esperado. Com isso:
  - a **A0 está concluída**: o jogo roda pelo cartão e o motor de cheats funciona (com
    cheats nossos, o que prova mais do que um cheat do banco público);
  - o critério da **A3** ("o Pico Launcher lista os cheats e eles funcionam no DS") foi
    atingido para estes 4 cheats; a A3 continua valendo para os cheats que a A2 trouxer;
  - o Pico Launcher aceitou os tipos de código `0` (escrita de 32 bits), `2` (8 bits),
    `9` (condição de 16 bits, os botões) e `D0` (fim do bloco);
  - a **A1 continua aberta**: o teste foi a olho, sem medir o dano. A A1 vai dizer se os
    números batem com as fórmulas do [COMBATE.md](COMBATE.md). O efeito da dificuldade
    dinâmica é o mais difícil de ver a olho, e a dúvida sobre a cópia do nível em cada
    inimigo (`+0x1d8`) também fica para a A1.

### Andamento: bateria de cheats (08/10/2026)
- **Bateria v1** em `cheats/YWSE.txt`, explicada em [CHEATS.md](CHEATS.md): 12 cheats em
  4 pastas (dano do grupo, dano dos inimigos, defender, dificuldade), 8 deles novos. Os
  novos usam os endereços já testados no DS com outros valores, mais a regra 7
  (`0x020F6470`, conferida só no emulador). Há cheats "por botão" (L+direcional) que
  funcionam como interruptor, porque o jogo não regrava as regras depois do boot.
- **Pastas "escolha 1"**: o `usrcheat.py` agora grava várias pastas e a marca "um só
  ativo" do formato, e troca as pastas "Projeto..." de uma versão anterior.
- **Tipos de código**: o Pico Loader usa o motor de cheats do NitroHax (o
  `CheatPreprocessor.cpp` dele diz isso e adapta os códigos D4/DB/E para esse motor), que
  implementa o conjunto completo do Action Replay DS. Os tipos 5, 6, B e D2 dos cheats
  públicos devem funcionar; no DS, só `0`, `2`, `9` e `D0` foram vistos rodando.
- **A1, parte da ferramenta**: `analise/tools/ar_codes.py` interpreta os códigos AR
  (com testes), e o `emu_run.py` liga cheats e lê a RAM no emulador. Falta rodar com a ROM
  e medir o dano numa batalha.
- **A2, primeira rodada (com a ROM e o save)**: as 74 regras têm endereço e formato
  conhecidos (`mapa_regras.py`); anéis do HUD em `0x02160EB0`; lista do grupo em
  `0x02160B28`, com HP, PP e atributos de cada membro. Os cheats de anéis e do grupo
  foram conferidos no emulador (valores na memória e na tela de perfil). Faltam: o
  critério "sobrevive a trocar de área e recarregar o save", a batalha, XP, itens e Chao.
- **A1 e A2, segunda rodada**: medido numa batalha do Capítulo 10 no emulador. As regras
  44 e 45 seguem a fórmula do COMBATE.md à risca; Power, Luck e Defense 99 têm o efeito
  previsto. Duas correções: o cheat de anéis agora usa a carteira (`0x02160C18` →
  esquadrão `+0x114`, conferida no Inventário), e os do grupo cobrem as posições 0 a 11
  da lista de personagens. Novos: XP no máximo e "Itens não acabam" (patch de código).
  Chao: nível Max e os 5 de troca sem fio. As cadeias valem nos dois saves testados
  (Green Hill e Nocturne). Falta: testar no DS.
- **A2, terceira rodada**: as três pistas públicas de código foram lidas no assembly e
  rodadas no emulador (tabela acima). Novos, todos conferidos pelo interpretador AR no
  emulador: multiplicador de anéis na carteira (×2, ×5, ×10), pegar todos os anéis da
  área, e a pasta POW (compra sem gastar pontos, 99 pontos, todos os golpes no nível III).
  Os pontos e níveis de POW são os atributos 75 e 69 a 74 do personagem. Depois:
  "5 ações por rodada" e "imune aos 6 elementos" (conferidos numa batalha) e "Loja:
  comprar sem gastar anéis" ([baixa]: falta uma loja no emulador).
- **A2, quarta rodada**: a loja foi aberta no emulador (teletransporte e troca de destino,
  DIARIO seção 17) e o cheat dela passou a [média], com a conferência do botão que faltava.
  Novos: andar 2x e 4x mais rápido no mapa. Confirmado: "Itens não acabam" deixa vender sem
  perder o item.

## 4. Caminho B: o mod menu

### 4.1 Como o código entra no jogo
O jogo é um programa NitroSDK. Para pôr código novo:

1. **Espaço**: o código novo fica no começo do heap (`arenaLo`, ~0x021B9500). Para isso,
   acrescentamos um bloco de **autoload** (a lista que o próprio crt0 do NitroSDK já usa
   para copiar o código do ITCM e do DTCM) e subimos o `arenaLo` pelo tamanho do bloco.
   Assim, o heap do jogo começa depois do nosso código e nada se sobrepõe. É a técnica do
   [NCPatcher](https://github.com/TheGameratorT/NCPatcher) (GPL-3, a mesma licença deste
   projeto), feito para jogos NitroSDK.
2. **Gancho**: troca-se uma instrução de uma função chamada **uma vez por quadro** por um
   desvio (`bl`) para o nosso código, que executa a instrução original e volta.
3. **Ferramenta**: primeiro, usar o NCPatcher como prova de conceito. Depois, decidir se
   vale escrever um `sonic-patch` em Rust dentro de `engine/` para manter a regra do
   projeto ("ROM sem mudanças → idêntica byte a byte"). O `sonic-formats` já regrava a
   ROM e o CRC do cabeçalho; falta regravar o ARM9, a tabela de autoload e os parâmetros
   do módulo.

### 4.2 Como o menu funciona
- **Abrir**: L + R + Select (a combinação final será escolhida para não colidir com o jogo).
- **Pausa total**: enquanto o menu está aberto, o gancho não devolve o controle ao jogo.
  Ele fica num laço próprio: lê os botões e a tela de toque, espera o VBlank e desenha.
  O ARM7 (som) segue sozinho.
- **Tela**: usamos uma camada de fundo da tela de baixo. **Antes** de desenhar, salvamos
  os registradores dela e o trecho de VRAM e paleta que vamos usar; **ao fechar**,
  restauramos. O jogo não percebe nada. A fonte é um bitmap 8×8 nosso.
- **Ações**: o menu lê e escreve a RAM (os endereços das fases A1 e A2) e, quando der,
  **chama funções do próprio jogo** em vez de mexer na memória (por exemplo, a função que
  põe um item no inventário), porque assim o jogo mantém os dados coerentes.

### 4.3 Fases

| Fase | O que | Pronto quando | Dias |
|---|---|---|---|
| **B0** | ambiente: devkitARM ou BlocksDS + NCPatcher; um "olá" que só pinta a cor de fundo ao apertar uma tecla | a cor muda no emulador e no DS | 2–3 |
| **B1** | achar a função por quadro: no py-desmume, contar as execuções de candidatas (o laço do `ModeSwitcher`, as atualizações dos `GameMode*`, o relógio `Time`) e escolher uma que rode exatamente 1×/quadro em todos os modos (exploração, combate, menus, diálogo) | gancho estável por 30 min de jogo nos 4 modos | 2–3 |
| **B2** | console de texto na tela de baixo com salvar e restaurar a VRAM; navegação com o direcional, A e B | abrir e fechar 100× sem corromper a tela do jogo | 3–4 |
| **B3** | **página "Regras"**: as 74 `CombatRules` com nome e valor, editáveis ao vivo; **"Dificuldade"**: ver e fixar o nível | mudar a regra 44 no menu muda o dano na próxima batalha | 2 |
| **B4** | **página "Grupo"**: HP, PP, atributos, nível, XP de cada personagem (endereços da A2) | editar e ver o efeito na tela de status do jogo | 3–5 |
| **B5** | **"Itens" e "Anéis"**: dar qualquer item, chamando a função do jogo | o item aparece no inventário e sobrevive a salvar e carregar | 3–5 |
| **B6** | **"Combate"**: curar o grupo, nocautear os inimigos, vencer, forçar emboscada, ver os atributos do inimigo (inclusive o ajuste de dificuldade) | cada ação testada em 3 batalhas diferentes | 3–5 |
| **B7** | **"Mundo"**: flags de história (plots), teletransporte (`GameAction_ExploreTeleport` existe), encontros ligados/desligados | | 5+ |
| **B8** | distribuição: `sonic-mod menu rom.nds saida.nds` aplica o patch à cópia do usuário; teste no R4 | roda no DS pelo cartão, com o save preservado | 2 |

Ordem e dependências: B0 → B1 → B2 → B3 (só endereços que já temos) → B4/B5/B6 (precisam
da A2) → B7.

## 5. Riscos e cuidados

| Risco | Como lidar |
|---|---|
| Gancho numa função que não roda em algum modo (ex.: vídeos) | testar nos 4 modos (B1); o menu simplesmente não abre ali |
| VRAM ou paleta corrompida ao fechar o menu | salvar e restaurar tudo o que tocamos; teste de 100 ciclos (B2) |
| Pouco espaço no heap: o jogo pode precisar de toda a RAM | medir o pico de uso do heap no emulador antes; manter o menu pequeno (meta: < 32 KB) |
| Escrever na RAM deixa dados incoerentes (HP > HP máx, item sem registro) | usar funções do jogo sempre que possível; limites nos campos do menu |
| **Save corrompido** | testar com cópia; o menu nunca grava o save sozinho; avisar no README |
| Cartão R4 sem suporte no Pico Loader | usar o motor de cheats do kernel; o caminho B não depende do cartão |
| Diferença entre emulador e DS (tempo, cache) | todo marco "pronto" inclui um teste no DS real |

## 6. O que vai para o Git

Igual ao resto do projeto: **nada do jogo**. Entram o código C do menu, os patches
(endereços e instruções nossas), as ferramentas e os códigos AR em texto (endereços e
valores). O usuário aplica tudo na **própria cópia**. Nunca distribuímos uma ROM, nem
mesmo modificada.

## 7. Perguntas em aberto

- ~~Qual é o modelo do R4?~~ R4i-SDHC Gold Pro (r4isdhc.com) → plataforma DSTT.
- ~~O Pico Launcher abre pelo kernel do Gold Pro e lê o SD?~~ Sim: o jogo e os cheats
  rodaram por ele no DS (08/10/2026).
- ~~O formato exato do `usrcheat.dat` e quais tipos de código AR o Pico Launcher
  aceita~~ O formato está em `usrcheat.py` (ida e volta idêntica); o motor é o do
  NitroHax, com todos os tipos do Action Replay DS (ver o andamento da bateria, acima).
- Menu em inglês ou português? (A fonte 8×8 nossa permite acentos.)

Referências: [Pico Loader](https://github.com/LNH-team/pico-loader),
[Pico Launcher: cheats](https://github.com/LNH-team/pico-launcher/blob/develop/docs/Cheats.md),
[NCPatcher](https://github.com/TheGameratorT/NCPatcher),
[EnHacklopedia: tipos de código do Action Replay DS](https://doc.kodewerx.org/hacking_nds.html).
