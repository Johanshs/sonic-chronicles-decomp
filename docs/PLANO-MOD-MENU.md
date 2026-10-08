# Plano: mod menu dentro do jogo e cheats para R4

Branch: `mod-menu`. Status: **em andamento**. Vale só o que está marcado como "conferido"
ou descrito nas seções "Andamento".

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
Valores tirados de [COMBATE.md](COMBATE.md). Nenhum deles foi testado numa batalha ainda.

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
  | `0x022262F4` | anéis | heap |
  | `0x02226605`/`06` + 9×n | nível e posse dos Chao | laço do AR com passo 9 |
  | `0x021D10AC` (ponteiro) +0x114 | dinheiro | primeira cadeia de ponteiros conhecida |
  | `0x021D10EE`, `0x021D10F8` | EXP | perto do início do heap (`arenaLo` ~0x021B9500) |
  | `0x02160EB0` | anéis do tabuleiro | BSS: endereço estático |
  | `0x02017A20`, `0x0209451C` | patches de código (coletar de longe, pontos de habilidade) | trechos do ARM9 a estudar |

- **No cartão** (com autorização do dono): o `usrcheat.dat` de 55 MB foi trocado por um
  banco enxuto de 7,9 MB, gerado com `usrcheat.py`: as 248 entradas dos 27 jogos que estão
  no cartão (todas as regiões) e, na entrada do Sonic Chronicles, a pasta "Projeto
  sonic-chronicles-decomp" com os cheats de `cheats/YWSE.txt`. O banco completo é público
  ([DeadSkullzJr](https://gbatemp.net/threads/deadskullzjrs-nds-i-cheat-databases.488711/))
  e pode ser baixado de novo. Motivo da troca: o gravador do cartão aceita no máximo
  30 MB por arquivo, e o nome tem que ser `usrcheat.dat`.

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

### Andamento: fase B (08/10/2026)
O painel está em [`modmenu/`](../modmenu/README.md), versão 0.7, e **roda dentro do jogo
no emulador**, inclusive numa batalha. Falta o teste no DS.

- **B0, ambiente: feito, por outro caminho.** Em vez de devkitARM + NCPatcher, o painel é
  compilado com o **clang e o ld.lld** do LLVM, que já geram código para o ARM946E-S. Sem
  libnds nem NitroSDK: o código escreve direto nos registradores. O enxerto (o papel do
  NCPatcher) é `modmenu/ferramentas/enxertar.py`.
- **B1, gancho: feito no emulador.** `contar_funcoes.py` contou as execuções de cada uma
  das ~10 mil funções. O laço principal (`main`, 0x02000c8e) chama a leitura dos botões
  (`func_02002708`) uma vez por volta: 30 voltas por segundo na exploração, 60 no
  diálogo. O gancho troca essa chamada (0x02000d50). Conferido na exploração, no diálogo
  e na tela de perfil e, com o save do Capítulo 10, numa batalha (achada por um robô
  que anda ao acaso). Faltam os 30 minutos do critério.
- **B2, console: feito no emulador.** A tela volta idêntica byte a byte depois de 100
  aberturas na ROM de teste, e a tela de perfil do jogo volta perfeita.
- **B3: feito.** Todas as 74 regras (mapa de `analise/tools/mapa_regras.py`), com os 5
  formatos, e a dificuldade dinâmica. Falta ver uma regra mudar uma batalha.
- **B4: adiantada.** A carteira de anéis e os atributos de **todos** os personagens (a
  lista com nome e HP; 11 no Capítulo 10). Conferido: o painel mostra os mesmos números da
  tela de perfil e da tela de save; mudar o HP do Sonic numa batalha mudou o HP na tela
  da batalha. A v0.2 tinha dois erros que a sessão dos cheats achou: os anéis eram o
  contador do HUD (0x02160EB0), não a carteira, e o grupo tinha só 4 posições.
- **B5, itens: feito no emulador (v0.4 e v0.5).** O inventário é um `CGameObjectInventory`
  apontado pelo esquadrão (+0x40), com uma lista de `CGameItem`. O painel dá itens
  chamando a função do próprio jogo (0x0202dc6c, a das recompensas) e muda a
  quantidade de cada pilha. Conferido: o item dado aparece no Inventário do jogo
  ("POW Candy (2)"). Na v0.5 o painel mostra o nome de cada item, pedido ao próprio
  jogo (as funções da mensagem "você ganhou um item"). Critério cumprido no emulador: o item
  dado continuou no inventário depois de salvar pelo menu do jogo, reiniciar e carregar.
- **B6, combate: adiantada (v0.6 e v0.7).** Página dos inimigos da batalha (lista fixa
  em 0x02160AF8) e ações rápidas: curar o grupo, inimigos com HP 1 e **nocautear os
  inimigos**. Escrever HP 0 não nocauteia (o inimigo continua lutando); a v0.7 chama a
  função que todo golpe usa para mudar um atributo (0x02007e60), e o jogo faz o resto:
  os 4 inimigos caíram e a batalha terminou em vitória normal (VICTORY, XP, item,
  subida de nível). Conferido em 6 encontros, todos contra 4 Nocturne Decurion; falta
  um inimigo de outro tipo e um chefe. Faltam também forçar emboscada e ver o ajuste
  de dificuldade no inimigo.
- **B8: feito o enxerto e o `sonic-mod menu`; falta o teste no DS.** Novo bloco de
  autoload nos últimos 32 KB do heap (0x023D8000), fim do heap baixado para lá, ARM7
  mudado para o fim da ROM. O `sonic-mod menu rom.nds saida.nds` faz o enxerto sem
  Python; a saída é idêntica byte a byte à do `enxertar.py`. A release compila o painel
  e o põe no pacote, ao lado do `sonic-mod`; a CI compila o painel a cada push. Na
  v0.2 o painel ficava no começo do heap e deslocava todos os objetos do jogo, o que
  quebrava os cheats que usam endereços do heap; na v0.3 eles ficam nos mesmos
  endereços da ROM original (conferido num boot do zero).
- **Achado no caminho:** o jogo move tudo pelo tempo real entre voltas (objeto Time,
  0x02109b60). Sem cuidado, fechar o painel dava um salto no tempo; o gancho acerta o
  relógio ao fechar.

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
- O Pico Launcher abre pelo kernel do Gold Pro e lê o SD? (teste da fase A0)
- O formato exato do `usrcheat.dat` (cabeçalho, identificação do jogo por código + CRC) e
  quais tipos de código AR o Pico Launcher aceita: conferir na fase A3, no código-fonte
  do launcher.
- Menu em inglês ou português? (A fonte 8×8 nossa permite acentos.)

Referências: [Pico Loader](https://github.com/LNH-team/pico-loader),
[Pico Launcher: cheats](https://github.com/LNH-team/pico-launcher/blob/develop/docs/Cheats.md),
[NCPatcher](https://github.com/TheGameratorT/NCPatcher),
[EnHacklopedia: tipos de código do Action Replay DS](https://doc.kodewerx.org/hacking_nds.html).
