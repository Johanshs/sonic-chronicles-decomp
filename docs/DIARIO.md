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

## 14. A ROM reconstruída (Fase 0)
O guia está em [`BUILD.md`](BUILD.md). O caminho:

- **Ferramentas sem Windows.** Os compiladores da Metrowerks são `.exe` de 32 bits. O
  `wibo`, um carregador mínimo feito pela comunidade de decompilação, roda eles no
  Linux sem Wine. O pacote de compiladores é o mesmo que o decomp.me usa.
- **Desmontar e montar de novo.** `dsd delink` corta o ARM9 em `.o` com as
  relocações no lugar dos endereços; o `mwldarm` (o linker original) junta tudo. O
  ARM9, o ITCM e o DTCM saíram idênticos na primeira tentativa: as 60 mil relocações
  achadas pelo `dsd init` estão certas.
- **Os 20 bytes teimosos.** A ROM inteira ainda tinha 20 bytes diferentes, nenhum de
  código. 16 eram do ícone: a paleta tem duas cores iguais e o PNG intermediário do
  `dsd` não guarda qual índice era qual. Os outros eram o CRC da área segura, que
  depende da chave da BIOS do ARM7. Os dois foram resolvidos sem a BIOS, e o SHA-1
  bateu: `f4ff8291...`.
- **Erro nº 7:** primeiro li as diferenças do ícone como "índice 8 virou 6" (olhando
  os bytes em octal do `cmp`). Comparando nibble a nibble, todas eram 4 → 2: as duas
  entradas com a mesma cor. A causa certa só apareceu quando li o código do `ds-rom`
  que converte o PNG.
- **Uma falha da ferramenta.** Compilado do código mais novo, o `dsd` recusava
  qualquer divisão do ARM9 em arquivos ("nome duplicado" nos buracos sem fonte). O
  binário da release 0.12.1 não tem o problema; ficamos com ele.

## 15. O compilador (Fase 1)
O resultado está em [`COMPILADOR.md`](COMPILADOR.md): **mwccarm 2.0, `-O4,p`, Thumb**.

- **Comparar sem o linker.** `decomp/tools/comparar.py` põe lado a lado a função do
  jogo e a do `.o`, ignorando os bytes que só o linker preenche (o destino de um
  `bl`, os ponteiros do pool de constantes).
- **CExoString::CStr** bateu de primeira em todas as versões 2.0: é pequena demais para
  dizer qual. **HashResourceName** precisou de 3 rodadas: o `tolower` inline com `||`
  explicou o registrador-bandeira, e uma variável temporária acertou a ordem dos
  operandos da última soma.
- **Procurando uma função que separe as versões.** Compilei ~30 construções de C++
  com todas as versões: só três famílias geram código diferente (1.2, 2.0 e DSi).
  Uma diferença da DSi é alocar `r4-r7` onde a 2.0 usa `r3-r6`; procurando funções do
  jogo com esse padrão, a remoção de item de uma lista (`0x0202d428`) bateu com toda a
  2.0 e com nenhuma DSi.
- **Exceções desligadas.** Com exceções ligadas o hash ganhava uma entrada no
  `.exceptix`; as do jogo são todas da biblioteca MSL. O jogo foi compilado sem.
- **Erro nº 8:** o `comparar.py` media as relocações pela primeira seção `.text` do
  `.o`. Com uma função de template (que o compilador põe numa seção própria), as
  relocações erradas eram mascaradas e uma função idêntica aparecia como diferente. A
  seção certa é a que o campo `sh_info` da seção de relocações aponta.
- **O service pack pelas bibliotecas.** O código do jogo não separava as versões 2.0,
  mas o MSL que vem pronto com cada CodeWarrior sim. Procurando no jogo as funções das
  bibliotecas de 7 versões, só a 2.0 sp2 achou todas as 283 (as outras, de 274 a 280).
  De quebra, 171 funções do MSL ganharam o nome verdadeiro (`memcpy`, `fwrite`...).
- **Do teste para o jogo.** CStr e o hash viraram `src/Aurora/*.cpp`, marcados
  `complete` no `delinks.txt`. O build passou a usar o nosso `.o` no lugar do código
  original, e o SHA-1 continuou o mesmo. Para provar que a verificação funciona,
  desfiz a variável temporária do hash: o build falhou apontando o byte
  `0x02009ba6`, a soma com os operandos trocados.

## 16. O NitroSDK pelo fonte (começo da Fase 2)
- **A mesma versão, decompilada.** O SDK do jogo é o 4.2.30001, o mesmo que a
  comunidade decompilou para o Pokémon Platinum. Compilando aquele fonte, cada função
  do SDK deveria aparecer no jogo com os mesmos bytes.
- **Erro nº 9:** compilei em ARM, como o Platinum faz, e nada bateu. O assembly do
  `OS_GetOwnerInfo` no jogo é Thumb: a BioWare usou a versão Thumb das bibliotecas.
  Recompilado com `-thumb -DSDK_CODE_THUMB`, 562 funções ganharam nome.
- **Como saber que não é coincidência.** Duas funções pequenas podem ter os mesmos
  bytes. Por isso os nomes foram conferidos pelas chamadas: se `X` chama `Y` no fonte,
  o `bl` da função `X` no jogo tem que cair na função `Y`. As 1.140 referências
  bateram. A única que parecia errada era um ponteiro para *dentro* da própria função
  (o endereço de retorno de `OSi_DisplayExContext`), e o erro era do conferidor, que
  ignorava o deslocamento da relocação.
- **O SDK não foi compilado com o compilador do jogo.** As bibliotecas da Nintendo
  batem melhor com a 2.0 sp1 (652 funções) do que com a sp2 (649) que compilou o jogo:
  a Nintendo entrega o SDK já compilado.

## O que ainda não sabemos
Vídeos `.vx` (codec Actimagine), layout das telas `.gui`, paletas dos Chao, 311 nomes de
colunas GDA, se um item novo numa loja funciona, os limites que o código impõe (número de
itens, de personagens), o service pack exato do compilador (2.0 base ou sp1+) e as partes do combate listadas em
[COMBATE.md](COMBATE.md#16-o-que-ainda-não-sabemos). Os próximos passos estão no
[plano](PLANO-DECOMPILACAO.md).
