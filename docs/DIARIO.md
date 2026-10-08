# Diário das descobertas

A história do projeto, em ordem, com as hipóteses que deram certo e as que deram errado.
Cada entrada diz **como** a coisa foi descoberta e **como** foi confirmada.

---

## 1. Abrindo a ROM
- Código do jogo `YWSE`, ARM9 de 1,1 MB **sem compressão e sem overlays** (raro: facilita
  muito), NitroSDK 4.2 (`0x04027531`, achado no bloco de parâmetros do módulo, assinatura
  `0xDEC00621`).
- 303 arquivos na raiz do NitroFS. As extensões `2DA`, `GFF`, `TLK` denunciaram o motor:
  **Aurora, da BioWare**, o mesmo de NWN/KotOR/Dragon Age, adaptado para o DS.
- O xoreos (reimplementação livre dos motores BioWare) já tinha estudado o jogo, mas só
  como visualizador.

## 2. Mapeando o código
- O `dsd` (ds-decomp) achou as funções seguindo as chamadas. Travou em `0x020ecc3c`: uma
  função **escrita à mão em assembly** que salva todos os registradores (estilo
  `setjmp`), logo após outra que termina num incomum `bx r2`. Solução: permitir
  chamadas para funções desconhecidas. Resultado: **6.820 funções**.
- Tentativa que não deu em nada: uma tabela com **98 tags de profiling**
  (`"Creat:UpdtGamepl"`, `"BG:SetFocusPoint"`...). Procurei a função `Begin` do profiler
  estatisticamente e não achei: o profiler foi **desligado** na versão final (a função de
  relatório, `0x020660c4`, não tem chamador). Ainda assim, os nomes revelam os subsistemas.

## 3. O RTTI: os nomes reais das classes
- Strings como `13CGameCreature` são nomes C++ "mangled", guardados para
  `dynamic_cast` e exceções. Seguindo `nome → typeinfo → vtable → funções`:
  **290 classes com herança, 351 vtables**.
- **Erro nº 1:** marquei como construtor toda função que lia o endereço de uma vtable.
  O assembly mostrou funções que só *registravam um singleton* (`static` local com o
  construtor inlinado). Correção: construtor é quem **grava** a vtable no offset 0, e
  quem faz isso dentro de outra tarefa vira `constructs_<Classe>`.
- **Erro nº 2:** supus o layout da ABI Itanium (destrutores nos slots 0 e 1 da vtable).
  O pseudo-C do Ghidra mostrou que os slots 0 e 1 eram métodos comuns. No CodeWarrior,
  o destrutor fica na ordem em que foi declarado. Correção: destrutor é **o método
  virtual que grava a vtable da própria classe em `this`**. 151 encontrados.

## 4. Uma função do começo ao fim: o hash dos nomes
O pacote `test.herf` guarda só hashes dos nomes. Testei candidatos (DJB2, CRC32, FNV) e
o DJB2 do nome em minúsculas bateu. Depois achei **a função do jogo** que calcula isso,
pela constante 5381 (`0x1505`):

```asm
ldr   r4, =0x1505          ; hash = 5381          <- assinatura do DJB2
bl    CExoString__CStr     ; s = name.CStr()
ldrsb r5, [r0, r1]         ; c = (signed char)*s   <- COM sinal!
ldrb  r5, [r0, r5]         ; se 0<=c<0x80: c = tabela_minusculas[c]
lsl   r7, r4, #5 ; add r4, r7 ; add r4, r5, r4      ; hash = hash*33 + c
```
Reescrita em C (`decomp/src/resource_hash.c`) e em Rust. Detalhe que só o assembly
revela: o caractere é lido **com sinal**. O teste em C recalcula todos os nomes do jogo.

**Erro nº 3:** o teste em C pegou **4 nomes falsos** que o ataque de dicionário tinha
aceitado: colisões de hash com "palavras" tiradas de bytes aleatórios.

## 5. Os formatos de dados
- **`.small`**: primeiro achei só LZ10 (byte `0x10`). Sobravam 185 arquivos começando com
  `00 28 02 00`. O cabeçalho é `tipo | tamanho << 8`, e o **tipo 0 é sem compressão**.
- **GFF4**: o mesmo do Dragon Age, mas o TLK usa texto de **8 bits** (no PC é UTF-16),
  enquanto os diálogos usam UTF-16. Há dois tipos de campo só do Sonic: 18 (ponto fixo
  20.12 do DS) e 20 (ASCII inline).
- **GDA**: os nomes de coluna são `CRC32(nome.lower() em UTF-16)`. 534 de 845 são
  conhecidos (os mesmos 63% do xoreos).
- **Diálogos**: o campo "quem fala" vale sempre `PLAYER`. Quem fala de verdade, e com
  que **emoção**, está no nome do retrato: `tailssca` = Tails assustado.

## 6. Os cenários (formato que ninguém tinha decifrado)
1. `.pal` com 136.192 bytes = 1.064 × 128? Primeira hipótese: paleta de 64 cores por
   tile. Os índices chegavam a 215, então estava errada.
2. Os tiles são LZ10 de 4.096 bytes (64×64). Desenhados linha a linha, saíam listrados;
   em **blocos de 8×8**, apareceram folhas e pedras.
3. Ainda havia ruído: 136.192 = 266 × 512 = **266 paletas de 256 cores**, e
   38 × 28 tiles / 4 = 266. Ou seja, uma paleta por bloco de 2×2 tiles.
4. A posição dos tiles ainda estava errada. Em vez de chutar, **medi** a diferença de
   cor nas bordas entre vizinhos para cada hipótese de ordem. A melhor deu 35, ainda
   ruim. O `.2da` da área era um **mapa de paletas** (paletas numeradas coluna a coluna).
   Com ele: **4,8**. Green Hill apareceu inteira.
5. Profundidade (`.cdpth`): mesmo índice, mas valores de 16 bits em ordem **linear**
   (diferente da cor!), com `0x7FFF` = vazio. Ela mostra os pilares e as estátuas que
   ficam na frente dos personagens.

## 7. O dicionário oficial
Dentro do próprio pacote havia um `erf.dict` com **todos os nomes** dos recursos. Ele
levou a recuperação a 100% e revelou mais **12 nomes falsos** do ataque de dicionário
(ex.: `1_c.emit`, que na verdade é `BTN_PUZZ_ON.NCGR`). Lição: um método esperto que
acerta 91% ainda erra; a fonte oficial, quando existe, vale mais.

## 8. Paletas dos sprites
**Erro nº 4:** a regra "paleta mais comum do mesmo prefixo" pintou **555 retratos com a
paleta do Tails**. Correção: as tabelas dizem a paleta de cada personagem
(`creatures.gda`: `PRTL_TAILS` → `PRTL_Tal.nclr`), e as telas `.gui` dizem a de cada
elemento. 1.747 imagens passaram a ter a paleta confirmada pelo jogo.

## 9. Escrevendo de volta: o caminho do modding
Para modificar, é preciso **escrever** os formatos. O critério foi ler e reescrever sem
mudanças e obter o arquivo original byte a byte:
- GDA: 137 de 229 na primeira tentativa. O preenchimento entre textos é `0xFF`, não
  zero. Depois disso, 229 de 229.
- HERF: faltava alinhar também o fim do arquivo. Depois, 6 de 6 (incluindo o de 49 MB).
- **TLK: é uma tabela hash.** Das 18.845 entradas, 4.711 estavam vazias (id
  `0xFFFFFFFF`) e os ids não tinham ordem. Hashes comuns não explicavam as posições.
  Fui ao **código do jogo**: a função `0x020989fc` (a busca de textos) mostrou a fórmula,
  uma variante do hash de inteiros de Thomas Wang, com sondagem linear. Conferida:
  14.134 de 14.134 posições corretas. Sem isso, um texto novo ficaria numa posição
  onde o jogo nunca o procuraria.
- Compressor LZ10 **sem referências de distância 1**: a rotina da BIOS que escreve na
  VRAM grava 16 bits por vez e quebraria com elas.

## 10. No emulador
- O DeSmuME roda sem janela (`py-desmume` com `SDL_VIDEODRIVER=dummy`) a ~110 fps. Um
  roteiro de toques chega à tela de título e à citação de abertura.
- Teste 1: trocar o texto da citação (TLK). Funcionou.
- Teste 2, pelo `sonic-mod`: editar a tabela `Chapter0` para apontar para um **texto novo**
  (id 990001) que não existia. A tela mostrou o texto novo. Isso prova a edição de
  tabela, a inserção na tabela hash do TLK e a gravação de arquivo maior no fim do
  cartucho, tudo ao mesmo tempo.

## 11. O combate
O resultado está em [`COMBATE.md`](COMBATE.md). O caminho:

- **Das regras para o código.** `combatrules.gda` tem 74 números sem nome. A função que
  a carrega (0x0201f270) copia cada linha para uma variável global; cruzando cada global
  com as funções que a leem, cada regra ganhou um "dono" (ex.: as regras 7, 8 e 11 só
  aparecem no `Defend`). Foi assim que as fórmulas foram achadas: pelos números que elas
  usam, não pelos nomes.
- **Funções pequenas executadas de verdade.** O dano usa ponto flutuante por software
  (`0x020ea840`, `0x020ea8d0`...). Em vez de adivinhar pelo nome, cada uma foi executada
  no Unicorn com entradas conhecidas (`3 → 3.0`, `6.0 / 4.0 → 1.5`). O mesmo para o
  `RollDice` (0x02008550).
- **Erro nº 5:** o Ghidra mostrou `func_020d5cfc(x)` com **um** argumento e eu a tratei
  como uma função de uma entrada (raiz? inverso?). No Unicorn ela travava. O assembly
  mostrou que é o **divisor de hardware** do DS (registradores 0x4000280) e que o segundo
  argumento (`r1 = 0x64000`, ou 100,0 em ponto fixo) existe, só o Ghidra o perdeu. Lição:
  quando o pseudo-C parece estranho, o assembly decide.
- **Os nomes das colunas mentem às vezes.** A coluna `GUITypeAggressive` de `combo.gda`
  (nome vindo do dicionário do xoreos) guarda 0,3/0,5/0,8: a chance do status por nível.
- **O texto do próprio jogo como prova.** As habilidades especiais têm só um código
  numérico. As descrições dos Chao e dos acessórios ("Increases the team's chances of
  Ambushing...") deram o significado de cada código, e o código da emboscada confirmou
  os de número 21 e 22. O diário de regras do jogo (`journalrules.gda`) confirmou a
  ligação entre Armor/Grit, Power/dano e os pares de status e curas.
- **Uma descoberta que contradiz o texto.** O diário do jogo diz que o Clover Juice cura
  Cursed; o `.ITM` dele não tem a linha de remoção. Ficou registrado como está.
- O gerador `analise/tools/combate_tabelas.py` transforma as tabelas e os arquivos de
  efeito em Markdown legível, para conferir tudo isto na sua cópia.

## 12. Os cheats no DS de verdade
O primeiro teste fora do emulador. O resultado está em
[PLANO-MOD-MENU.md](PLANO-MOD-MENU.md#andamento-fase-a0-08102026).

- **O caminho até o cartão.** O R4i-SDHC Gold Pro roda o Pico Loader v1.6.0, plataforma
  DSTT (o arquivo do cartão é idêntico, byte a byte, ao da release oficial). O banco de
  cheats público de 55 MB passava do limite de 30 MB do gravador do cartão; o
  `usrcheat.py` gerou um banco enxuto com os jogos do cartão e uma pasta "Projeto
  sonic-chronicles-decomp" com os 4 cheats de `cheats/YWSE.txt`.
- **O teste (08/10/2026).** Os 4 cheats foram ligados pelo Pico Launcher, no DS. O jogo
  rodou sem erro e o efeito de cada um foi o esperado: dano do grupo bem maior, dano inimigo sem a parte aleatória, defesa mais forte e a dificuldade dinâmica
  baixando com L+R.
- **O que isto prova.** Que os endereços das regras de combate (`0x020F64BC`,
  `0x020F64C0`, `0x020F64FC`) e da dificuldade (`0x02160E54`/`58`) são os mesmos no DS e
  no emulador, como se esperava de um ARM9 sem overlays; que o jogo lê as regras na hora
  de cada conta (se as copiasse no boot, reescrever a global não mudaria nada); e que o
  Pico Launcher aceita os tipos de código `0`, `2`, `9` e `D0`.
- **O que isto não prova.** O teste foi a olho, sem medir. Ainda não sabemos se o dano
  bate com as fórmulas do [COMBATE.md](COMBATE.md) número por número: isso é a fase A1, no
  emulador, com captura de tela. A dificuldade dinâmica é o efeito mais difícil de ver
  sem medir, então é o que mais precisa da A1.

## 13. A bateria de cheats
O resultado está em [CHEATS.md](CHEATS.md).

- **Quais códigos o cartão entende.** Em vez de testar tipo por tipo no DS, fui ao
  código do Pico Loader: o `CheatPreprocessor.cpp` diz que ele usa o motor do NitroHax
  e adapta alguns códigos (D4, DB, E) para ele. O NitroHax implementa o Action Replay DS
  completo. Fica como **dedução** até um cheat com tipo 5 ou B rodar no DS.
- **Um interruptor sem "senão".** O Action Replay não tem "se apertou, liga; senão,
  desliga" num código só. Mas as regras de combate só são carregadas no boot, então uma
  escrita única permanece: dois blocos (um por atalho) bastam para ligar e desligar.
- **Atalhos que não se cruzam.** O atalho da dificuldade é L+R. Os novos usam
  L+direcional e exigem o **R solto** (o bit do R entra na máscara com valor 1); sem isso,
  L+R+Cima dispararia dois cheats ao mesmo tempo. O `ar_codes.py simular` confere.
- **Erro nº 6** (pego pelo teste antes de ir para o Git): no interpretador, o `D2`
  zerava o offset **antes** de voltar ao começo do laço `C0`, então só a primeira
  repetição escrevia no lugar certo. Na especificação, o `D2` repete o bloco e só zera
  tudo quando o laço acaba. Lição: o teste do laço tinha a resposta esperada escrita à
  mão, e foi isso que pegou o erro.

## 14. A RAM do jogo, com o save de verdade
Com a ROM e o save do cartão no emulador. O resultado está em [CHEATS.md](CHEATS.md).

- **O save "sumido".** O jogo ignorava o `.sav` e começava do zero. O arquivo do Pico
  Loader tem 512 KB, mas só os primeiros 64 KB têm dados: o jogo usa uma memória de
  512 Kbit. Com o arquivo inteiro, o DeSmuME deduz 4 Mbit e o jogo não reconhece nada.
  Cortado em 64 KB, apareceu "Green Hill Zone, Chapter 1, 8 anéis". O `emu_run.py` ganhou
  `sav ARQ 65536`.
- **As 74 regras de uma vez.** Em vez de ler 74 chamadas no assembly, executei a função
  que carrega a tabela no Unicorn, trocando a leitura do arquivo por uma função que
  devolve um valor de teste. Cada escrita na memória disse onde a regra mora. Rodando com
  dois valores de teste diferentes, apareceu também a conversão (inteiro, ×4096, 0/1,
  ÷100). Os 4 endereços que já conhecíamos bateram, e os valores lidos no boot também.
- **Anéis: dois contadores.** A busca "era 8, virou 9" deu dois endereços. Escrever em
  cada um, separadamente, mostrou qual é o do HUD (`0x02160EB0`, fixo).
- **O grupo.** Pendurei uma função Python na `Stats_GetInt` (0x02007ab0) do emulador
  para anotar quem lê atributos. Dois objetos de 115 atributos apareciam o tempo todo:
  Sonic e Amy. Escrever no atributo 0 mudou a barra vermelha (HP), e escrever na tela de
  perfil confirmou Speed, Attack, Defense e Luck.
- **Erro nº 7** (pego antes de virar cheat): a primeira cadeia de ponteiros que a busca
  achou para o HP do Sonic partia de `0x021A4C70` e funcionava. Mas o primeiro campo do
  objeto apontado era `0x10000001`, sem vtable: era um bloco do heap, não um objeto do
  jogo, e a cadeia da Amy pelo mesmo caminho tinha deslocamentos diferentes, ou seja,
  coincidência. Procurei quem aponta para as duas criaturas e achei a lista do grupo em
  `0x02160B28`, com Sonic e Amy lado a lado. Lição: uma cadeia de ponteiros só vale se
  cada passo for um objeto que faz sentido (a vtable diz qual classe é); "funcionou
  agora" não basta, porque o heap muda de uma sessão para outra.
- **Erro nº 8** (meu, no commit anterior): ao acrescentar a seção 13, troquei sem querer
  o título "O que ainda não sabemos" pelo texto novo, e a seção perdeu o título. Ele
  voltou abaixo.

## 15. A primeira batalha medida
Com o save do Capítulo 10 (o slot Nocturne do seu cartão), um passeio aleatório no mapa
achou uma batalha contra 4 Nocturne Decurion. O truque da medição: um *savestate* logo
antes do golpe. O emulador é determinístico, então carregar o mesmo estado e repetir os
mesmos toques sorteia os mesmos dados; só o valor do cheat muda. Resultados em
[CHEATS.md](CHEATS.md#medições-no-emulador-fase-a1).

- **A fórmula do dano bateu.** Nove valores da regra 44 deram uma reta exata
  (dano = 17 + k/10), mais o piso da fórmula aparecendo em k = 0. A regra 45 deu a mesma
  reta para os inimigos, e o Luck 99 deu o crítico previsto, 60, até o último ponto. O P
  da fórmula é o atributo 41, que estava como "deduzido".
- **Erro nº 9: o cheat de anéis mexia no contador errado.** Ele escrevia em
  `0x02160EB0` porque, no Green Hill, esse número aparecia no HUD. Abrindo o Inventário,
  o número era outro: a carteira está no esquadrão (`+0x114`). No save do
  Capítulo 10 a diferença salta: carteira 986967, `0x02160EB0` = 54, HUD "93/124".
  Lição: conferir um valor numa tela só prova o que aquela tela mostra. Para dinheiro, a
  tela que importa é onde ele é gasto.
- **Erro nº 10: os cheats do grupo só cobriam 4 personagens.** A lista em `0x02160B28`
  não é o time da batalha, é todo mundo que já entrou no grupo: 11 no Capítulo 10, e o
  Omega, que estava lutando, é o 10º. Com o "HP sempre cheio" ligado ele tomou 164 de
  dano. Agora os cheats percorrem as posições 0 a 11, e o mesmo teste deixou todos cheios.
  Lição: o save do começo do jogo (2 personagens) escondia o problema; testar no save
  mais avançado achou.
- **As travas provaram que eram necessárias.** No começo do jogo, a posição 3 da lista
  tem lixo (`0x6C616D69`, pedaço de um nome de arquivo) e a 8 aponta para algo que não é
  uma criatura. Com todos os cheats ligados, nada fora das criaturas foi escrito.

- **XP e itens.** O XP é um número só para o grupo todo, num objeto que o esquadrão aponta
  (`+0x48`, campo `+0x50`); uma vitória somou 8000 nele. Com o cheat de XP no máximo, a
  vitória seguinte levou o Sonic do nível 16 ao 30. Os itens: a mochila tem um vetor de
  `CGameItem`, com a quantidade no byte `+0xBB`. Para achar quem gasta, pus um "vigia" de
  escrita do emulador nesse byte e usei um item: ele apontou a função que tira itens da
  mochila. Duas instruções trocadas por "não faz nada" e o item deixou de acabar.
- **Chao.** A pista pública falava em passo de 9 bytes; olhando a memória lado a lado
  (save novo e save do Capítulo 10) o passo é 10: número, nível (3 = Max) e cópias. Um
  ovo que chocou ao abrir o jardim confirmou o byte das cópias (6 → 7 na tela).
- **Erro nº 11: `0x021D10AC` não é uma global fixa.** Eu tinha escrito que era, porque o
  endereço era sempre o mesmo. Ele fica dentro do heap; só se repete porque o jogo aloca
  tudo na mesma ordem a cada boot. Quem achou foi a conversa do painel de controle, cuja
  ROM empurra o heap. O caminho certo parte de `0x02160C18`, na BSS. Lição: "o endereço é
  sempre o mesmo" não diz se ele é fixo; é preciso ver em que região da memória ele está.
- **Erro nº 12: Eggman ou Omega.** Chamei de Eggman o robô vermelho e preto da batalha. É
  o Omega. Eu tinha identificado o personagem pelo desenho; o nome certo está num ponteiro
  dentro da criatura (`+0x98`), e a conversa do painel o leu. O Eggman é o 8º da lista.

## 16. Os cheats públicos de código, lidos de verdade
Os três cheats públicos que trocam instruções do jogo (e não dados) foram lidos no
assembly e rodados no emulador. Nenhum deles faz exatamente o que o nome diz.

- **O "anéis ×2" não dobra o que você gasta.** A função que pega um anel soma 1 em dois
  lugares: no contador da área (o "x/185" do HUD) e na carteira. O cheat público troca a
  primeira soma. Com ele, o HUD sobe de 2 em 2 e a carteira de 1 em 1. É o mesmo engano do
  erro nº 9, só que de outra pessoa: o efeito foi conferido na tela do HUD, não na tela
  onde o dinheiro é gasto. O nosso multiplicador troca a segunda soma, 14 bytes depois.
- **O "coletar de longe" funciona, mas troca um teste à toa.** A função confere o tipo do
  coletável, a distância em X e a distância em Y. O cheat desliga os três; o do tipo é
  repetido logo depois, então desligá-lo não muda nada. O nosso desliga só as distâncias.
- **O "pontos de habilidade" deixa os pontos negativos.** Ele libera a compra de golpes POW
  mesmo sem pontos, mas a compra continua descontando o custo: 5 pontos, golpe de 10,
  sobra −5. O nosso também troca a conta (`pontos − custo` vira `pontos + 0`).
- **O vetor de atributos é maior do que eu achava.** Eu só tinha olhado 47 posições; são
  115. Os pontos de POW apareceram com um vigia de *leitura*: escrevi 77 num candidato,
  a tela mostrou 77, e o vigia mostrou quem lia: a função genérica de atributos, com o
  índice 75. Lição: quando um valor está "em lugares diferentes" em cada personagem (aqui,
  `+0x3CC` no Sonic e um ponteiro no Eggman), o mais provável é que ele esteja numa
  estrutura alocada à parte, e o caminho certo é o ponteiro para ela.
- **Testar uma defesa sem o ataque certo.** Os inimigos da batalha de teste batem sem
  elemento, então a resistência do grupo nunca entrava na conta. A saída foi mudar o
  inimigo: um 1 no dano elemental dele (um elemento por vez) e a mesma batalha de novo.
  Sem o cheat, os números bateram com as resistências da Rouge (Fogo −25%: 47 virou 59);
  com ele, os golpes com elemento continuaram vindo e deram 0. Lição: quando o jogo não
  oferece o caso de teste, dá para montá-lo, desde que a mudança seja só no lado que não
  está sendo testado.

## O que ainda não sabemos
Vídeos `.vx` (codec Actimagine), layout das telas `.gui`, paletas dos Chao, 311 nomes de
colunas GDA, se um item novo numa loja funciona, os limites que o código impõe (número de
itens, de personagens), a versão exata do compilador e as partes do combate listadas em
[COMBATE.md](COMBATE.md#16-o-que-ainda-não-sabemos). Os próximos passos estão no
[plano](PLANO-DECOMPILACAO.md).
