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

## 20. Conteúdo novo: um item à venda numa loja
O `sonic-mod` já editava tabelas e textos; faltava provar que um item **novo** (uma linha
que não existia em `Items.gda`) funciona no jogo. O teste: o item 288 "Chili Dog", com
dois textos novos e um `Item288.ITM` novo (`HealHP 321`), posto nas 5 lojas.

- **O problema: chegar a uma loja.** O save de teste está no capítulo 10, em Nocturne, e
  andar até uma loja com toques roteirizados seria longo e frágil. Procurei como o jogo
  abre uma loja. Nos dados, só a conversa `kron_store` tem uma ação com o código 40 e o
  dado 2, e a loja 2 é a "Kron Quartermaster". Os códigos de evento das conversas são os
  mesmos dos gatilhos das áreas (`EventID` de `Conversations.gda` também usa 23, por
  exemplo), então 40 parecia "abrir a loja N".
- **No código.** A troca de modos de jogo (`0x02030604`) é um `switch` (em `0x02030d18`)
  que cria um objeto por modo; o caso 11 cria o `GameModeStore`. Procurei quem pede o
  modo 11 a `0x020305a4` (a função que pede um modo): só uma função, `0x0207be48`. Ela
  grava o seu argumento `r3` em `GameModeStateStore+4` e pede o modo 11. É o tratador do
  evento 40, e o argumento é a linha de `stores.gda`.
- **Chamar uma função do jogo de fora.** Primeiro tentei mudar o PC do emulador dentro
  de um *callback* de execução: não funcionou: o tratador nunca rodou (provavelmente porque o
  DeSmuME já tinha buscado a próxima instrução). Funcionou trocar, por um quadro, o `bl` do laço principal por
  um `bl` para um trampolim de 24 bytes numa área livre da RAM, que chama o tratador e
  segue para a função original. **Erro nº 6:** no primeiro trampolim errei o
  deslocamento do `ldr r2, [pc, #...]` (no Thumb, o `pc` lido é o endereço da instrução
  + 4, arredondado para baixo a múltiplo de 4), o jogo pulou direto para a função
  original e a RAM virou lixo. Corrigido, a Overmart abriu.
- **O resultado.** O Chili Dog aparece na loja (no topo da lista, embora seja a última
  linha da tabela), com o nome, a descrição e o "HP +321" que o jogo monta a partir do
  `.ITM`. Comprado, custou 15 anéis e entrou no inventário (`288: 1` na RAM). Usado no
  Sonic pelo inventário, o HP foi de 100 para 421: **+321, exatamente**. O roteiro
  `analise/tools/testar_item_loja.py` refaz tudo e confere na RAM; com a ROM original
  (sem o item) ele falha, como deve: o primeiro da lista é o Med Emitter, que custa 20 e
  cura 250.
- Uma surpresa no caminho: aberta na tela de título (sem jogo carregado), a loja mostra o
  tutorial "Welcome to a store!" e um grupo vazio com tudo em 99.

## 21. Conteúdo novo: um golpe POW novo
Depois do item, um golpe: a linha 155 de `combo.gda`, "Sonic Boom", 3 PP, 300/350/400%
de dano, com nome, descrição e textos de dano novos, posta no `Combo7` do Sonic
(`creatures.gda`), que estava vazio.

- Na batalha, "Sonic Boom · 3 PP" aparece na lista de POW Moves do Sonic, abaixo dos
  seis golpes de sempre, e escolhê-lo gasta 3 PP (27 → 24): o custo veio da linha nova.
- Para provar que não é só a interface, pus um gancho em `Combat_PowDamage`
  (0x02010810): ele foi chamado **duas vezes com o terceiro argumento 155**. Duas
  chamadas batem com o "2x" do texto de dano, e 155 é a linha nova.
- **O que não consegui:** medir o dano. O dano de um POW depende do minijogo de toque, e
  o jogador automático de `analise/tools/testar_golpe.py` (acha o anel quando o jogo o
  pinta de verde e toca no centro) acerta 4 dos 5 anéis no melhor caso; com isso o jogo
  marca "Missed!" e o dano sai 0. Fica registrado como está: o golpe novo existe e é
  calculado pelo jogo, mas o dano ainda precisa de alguém jogando o minijogo à mão.
- **Pendente (projeto pausado em 2026-10-08):** medir o dano do Sonic Boom jogando o
  minijogo à mão (a seção 22 achou um jeito de pular o minijogo, o Chao 38); depois, os próximos conteúdos planejados, ainda não começados: uma
  variação de inimigo (`creatures.gda`/`squads.gda`) e um diálogo editado.

## 22. Conteúdo novo: animação e efeito visual para o Sonic Boom
O Sonic Boom da seção 21 era uma cópia do Axe Kick com outro nome. Agora ele tem uma
animação do Sonic que nenhum POW usava e uma onda de choque desenhada por nós.

**Como um POW chega à tela.** Seguindo números entre tabelas, e conferindo com ganchos
no emulador:
- `combo.gda`, coluna `col_9185ff28`, é a linha de `animations.gda` (Axe Kick = 21, cujo
  arquivo para o Sonic é `SON_CB_KD`; Whirlwind = 12, `SON_CB_AttackC`);
- `AnimationEvents.gda` diz o que acontece em cada quadro dessa animação. Pus um gancho
  em todas as funções do `VisualEffectManager` e só uma recebeu números que batiam com
  linhas de `VFX.gda`: **0x0202f47c, com r1 = linha do efeito**. No Sonic Boom ela foi
  chamada com 89 (`FX_Son_Shock`), que é o `EventData` do evento **46** da animação 21,
  esqueleto 0. Então o evento 46 = "crie o efeito N".

**Dois testes que derrubaram planos.**
- Efeitos 2D (`Type` 1: `.NCGR` + `.NCER` + `.NANR`, sprites "de verdade") seriam o
  natural para sprites novos. Troquei o efeito 89 pelo único efeito tipo 1 do jogo
  (`FX_ImpactFlash`): a função foi chamada, mas **nada apareceu**. Já um efeito tipo 3
  (modelo 3D + textura) no mesmo lugar apareceu. Conclusão: na batalha, só tipo 3.
- Uma linha **nova** em `animations.gda` (a 56) **travou a batalha** na vez do Sonic.
  A linha 13 (`SON_CB_PAttack02`) já existia, tinha arquivo para o Sonic e nenhum POW a
  usava: com ela e os eventos do Axe Kick copiados, o golpe rodou com outra animação.

**O efeito.** Um subagente desenhou 8 quadros de 32x32 (arte nossa, gerada por código em
`conteudo/sonic-boom/desenhar_sprites.py`, 7 cores). O jeito de pô-los no jogo sem fazer
um modelo 3D do zero: o `FX_SmokePuff` do jogo é um quadrado no chão que troca de
textura 8 vezes (um "flipbook"). `analise/tools/montar_vfx.py` copia o modelo e o
flipbook e troca só o desenho das 8 texturas pelos nossos quadros, no formato A3I5 do DS
(5 bits de cor numa paleta de 32 + 3 bits de transparência). Antes de usar, conferi a
conversão decodificando o arquivo gerado de volta para PNG.

**Erro nº 7: savestate não serve para testar tabelas.** Os primeiros testes partiam de um
savestate feito com a ROM anterior, e nenhuma mudança em `VFX.gda` aparecia. O jogo lê as
tabelas quando liga; o savestate guarda a RAM com as tabelas velhas. Passei a entrar na
batalha a partir do save, com a ROM nova (`testar_golpe.py` avisa disso no uso).

**Erro nº 8: arquivo novo que o jogo não acha.** Com tudo ligado, o efeito novo não
aparecia, mas o mesmo desenho gravado por cima do `FX_SmokePuff.nsbtx` aparecia. A
diferença: no pacote, os arquivos 3D estão como `FX_SmokePuff.nsbtx.small` (comprimidos
com LZ10), e o jogo procura os 3D só por esse nome. O `sonic-mod pack` guardava arquivos
novos sempre "soltos". Corrigido: um arquivo novo agora é guardado como os outros do mesmo
tipo (`.nsbmd`, `.nsbtx`, `.nsbtp` viram `.small` LZ10; `.ITM` continua solto).

**Resultado.** Com a ROM final (Chili Dog + Sonic Boom + efeito), entrando na batalha a
partir do save, `testar_golpe.py final.nds estado.dst 155 pasta 500 --vfx 467 --auto`
deu OK nas duas coisas: o jogo usou a linha 155 e pediu o efeito 467. A onda de choque
aparece no chão, em volta do Sonic, e se abre em anel. Na ROM anterior, o mesmo teste dá
FALHOU para o 467 (o jogo pede o 89), que é a prova negativa.

**O Chao 38.** O Johans lembrou que o Chao 38 faz o minijogo sozinho. No código, o
minijogo pergunta "o personagem tem a habilidade 0?" (0x0207b87a) e pula se não tiver
(0x0207b884). O `--auto` troca esse pulo por um "nop" na memória do emulador: todo
personagem age como se tivesse o Chao 38. Com isso os anéis do minijogo nem aparecem.

**Ainda em aberto.** O dano do Sonic Boom continua sem medida: nesta batalha os Nocturne
Decurions voltam a 340 de HP na tela e não achei onde ler o dano direto. A animação 13
ganhou eventos no esqueleto 0; se algum inimigo usar a animação 13 com esse esqueleto,
ele também mostrará o efeito (não vi nenhum, mas não provei que não existe).

## O que ainda não sabemos
Vídeos `.vx` (codec Actimagine), layout das telas `.gui`, paletas dos Chao, 311 nomes de
colunas GDA, onde quatro das cinco lojas ficam no jogo, os limites que o código impõe (número
máximo de itens, de personagens), a versão exata do compilador e as partes do combate listadas em
[COMBATE.md](COMBATE.md#16-o-que-ainda-não-sabemos). Os próximos passos estão no
[plano](PLANO-DECOMPILACAO.md).
