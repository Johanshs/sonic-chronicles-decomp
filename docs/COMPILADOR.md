# O compilador do jogo

Resultado da **Fase 1** do [plano](PLANO-DECOMPILACAO.md). Sem o compilador e as
flags certas, nenhum C++ sai igual ao original; com eles, uma função reescrita pode
ser provada certa byte a byte.

## Resposta curta

| | Valor | Como sabemos |
|---|---|---|
| Compilador | **Metrowerks CodeWarrior para DS, mwccarm 2.0** | 3 funções com 100% de match; 1.2 e "DSi" (4.0) erram |
| Service pack | **2.0 sp2** (as bibliotecas com certeza; o compilador, quase) | o MSL e o Runtime ligados no jogo são os da sp2: [abaixo](#o-service-pack-pelas-bibliotecas) |
| Otimização | `-O4,p` | `-O4,s` (tamanho) erra 2 das 3; `-O3,p` também acerta |
| Modo | `-thumb -interworking` | o código do jogo é Thumb (e as bibliotecas da Nintendo também, veja abaixo) |
| C++ | `-lang=c++ -Cpp_exceptions off -RTTI on` | abaixo |
| Outras | `-proc arm946e -enum int -char signed` | padrão dos jogos de DS; ainda não testadas uma a uma |

As flags estão num lugar só: [`decomp/tools/compilar.sh`](../decomp/tools/compilar.sh).

## As três funções

| Função | Endereço | Tamanho | Arquivo |
|---|---|---|---|
| `CExoString::CStr` | `0x020052f0` | 0x10 | [`src/Aurora/CExoString.cpp`](../src/Aurora/CExoString.cpp) |
| `HashResourceName` | `0x02009b78` | 0x44 | [`src/Aurora/ResourceHash.cpp`](../src/Aurora/ResourceHash.cpp) |
| lista: remover item | `0x0202d428` | 0x2c | [`decomp/compilador/lista.cpp`](../decomp/compilador/lista.cpp) |

As duas primeiras já são arquivos do jogo de verdade: o build da
[Fase 0](BUILD.md) usa o `.o` compilado delas no lugar do código original, e a ROM
continua com o mesmo SHA-1.

A matriz abaixo é a saída de `decomp/tools/testar_compilador.sh`: quantas das 3
funções saem idênticas em cada versão e otimização.

```
versão     -O4,p   -O4,s   -O3,p   -O2
1.2/base    1/3     1/3     1/3     1/3      (1.2/sp2, sp2p3, sp3, sp4: igual)
2.0/base    3/3     1/3     3/3     1/3      (2.0/sp1 ... sp2p4: igual)
dsi/1.1     2/3     1/3     2/3     1/3      (todas as dsi/: igual)
```

- **1.2** gera `mul` para `hash * 33` e salva os registradores com outra convenção
  (`push {r4, r5, lr}` + `sub sp, #4` em vez de `push {r3, r4, r5, lr}`).
- **DSi (4.0)** acerta CStr e o hash, mas na remoção de item aloca os registradores
  de outro jeito (16 instruções diferentes).
- **`-O4,s`** monta o laço do hash de outro jeito; só a função trivial sobrevive.

## Por que exceções desligadas e RTTI ligado

- **RTTI ligado:** o jogo tem typeinfo para 290 classes do próprio jogo
  (`13CGameCreature`...). É assim que os nomes das classes foram recuperados.
- **Exceções desligadas:** com `-Cpp_exceptions on`, o compilador cria uma entrada
  de 12 bytes na seção `.exceptix` para cada função que chama outra (como o hash, que
  chama `CStr`). As 206 entradas do `.exceptix` do jogo são todas de endereços acima
  de `0x020e09d1`, a região da biblioteca C++ (MSL). Ou seja: a Metrowerks compilou a
  biblioteca com exceções, a BioWare compilou o jogo sem.

## O que aprendemos igualando funções

Igualar uma função é ajustar o C++ até o compilador escolher as mesmas instruções.
Algumas lições destas três, que devem valer para o resto do jogo:

- **`||` dentro de `?:` vira um valor guardado.** O padrão estranho
  `r7 = 1; se 0 <= c < 0x80 então r7 = 0; se r7 == 0 então c = tabela[c]` é um
  `tolower` inline escrito como `(c < 0 || c >= 0x80) ? c : tabela[c]`.
- **Variáveis temporárias mudam a ordem dos registradores.** Com
  `hash = (hash << 5) + hash + tolower(c)` a última soma sai `add r4, r4, r5`; com o
  `tolower` numa variável própria sai `add r4, r5, r4`, como no jogo. O valor é o
  mesmo, a instrução não.
- **O compilador relê da memória o que pode ter mudado.** Na remoção de item, `data`
  e `count` são relidos a cada volta: gravar em `data[i]` poderia, para o compilador,
  mudar o próprio objeto. Reproduzir isso pede ler os campos pelo objeto, e não
  copiá-los para variáveis locais.
- **`ldrsb r5, [r3, r6]` com `r6 = 0`** é só um `*p`: em Thumb, o `ldrsb` (byte com
  sinal) não tem a forma com deslocamento fixo, então o compilador usa um registrador
  zerado.

## O service pack pelas bibliotecas

O código do próprio jogo não separa as versões 2.0 entre si. Mas o jogo também traz,
no fim do ARM9 (a partir de `0x020e09d0`), a biblioteca C/C++ da Metrowerks (MSL) e
o Runtime (divisão, ponto flutuante, `new`/`delete`...). Essas bibliotecas vêm
**prontas** com cada versão do CodeWarrior, e mudam um pouco de uma versão para outra.

`decomp/tools/achar_funcoes.py` procura cada função de uma biblioteca no jogo
(mesmo tamanho, mesmos bytes fora das relocações). `decomp/tools/versao_msl.sh` faz
isso com as bibliotecas de cada versão (pacote do [metroskrew](https://github.com/mid-kid/metroskrew)):

```
versão  endereços achados (de 283 que alguma versão acha)
base     274
p2       274
p4       276
sp1      276
sp1p2    280
sp2      283      <- a única que acha todos
sp2p3    275
```

Das 15 funções que mudam entre versões, a sp2 acerta as 15; cada outra versão erra
pelo menos 3. Então o jogo foi ligado com o CodeWarrior 2.0 **sp2**. O compilador quase
certamente é o da mesma instalação: `2.0/sp2`, ou um patch dela que não tenha trazido
bibliotecas novas (o pacote não tem bibliotecas próprias da `sp2p2`; isto é dedução).
É o que `compilar.sh` usa.

Para comparação: no decomp do Pokémon Platinum, o NitroSDK 4.2.30001 (a mesma versão
deste jogo) foi compilado pela Nintendo com a `2.0/sp1p2`, e a NitroSystem com a `2.0/sp2`.

**Bônus:** as funções achadas sem ambiguidade ganharam o nome verdadeiro em
`symbols.txt` (171 nomes: `memcpy`, `fwrite`, `__flush_buffer`, `abort`...). Funções que
são idênticas entre si (`abs` e `labs`, os destrutores vazios) ficaram com o nome
antigo, porque não dá para saber qual é qual. O comando:

```
L=work/ferramentas/metroskrew/lib/metroskrew/sdk/ds/2.0/sp2
python3 decomp/tools/achar_funcoes.py --de 0x020e09d0 --aplicar \
    $L/msl/MSL_C/MSL_ARM/Lib/MSL_C_NITRO_{T,Ai}_LE.a \
    $L/msl/MSL_C++/MSL_ARM/Lib/MSL_CPP_NITRO_{T,Ai}_LE.a \
    $L/Runtime/Runtime_ARM/Runtime_NITRO/Lib/NITRO_Runtime_{T,Ai}_LE.a
```

## O NitroSDK: compilado pela Nintendo, em Thumb

O jogo usa o NitroSDK **4.2.30001** (o número `0x04027531` no ARM9). Essa exata versão
foi decompilada pela comunidade ([ntrtwl/NitroSDK](https://github.com/ntrtwl/NitroSDK),
a mesma base do decomp do Pokémon Platinum). `decomp/tools/nitrosdk.sh` baixa esse
fonte, compila os 169 arquivos do ARM9 e procura cada função no jogo.

- **Thumb, não ARM.** A primeira tentativa, em ARM (como o Platinum), achou 0 de 4
  funções do `os_ownerInfo.c`. O `OS_GetOwnerInfo` do jogo começa com `push {r4, lr}`
  em Thumb: a BioWare ligou a versão Thumb das bibliotecas do SDK
  (`-thumb -DSDK_CODE_THUMB`). Com isso, 3 de 4 bateram de cara.
- **Versão do compilador do SDK.** Funções achadas na região do SDK
  (`0x020d4000`-`0x020e09d0`) com cada versão: `2.0/base` 627, `sp1`/`sp1p2`/`sp1p5`
  652, `sp2` 649. O SDK foi compilado pela Nintendo com uma 2.0 sp1 (o Platinum usa a
  `sp1p2`, a que adotamos aqui), não com a sp2 do jogo. Faz sentido: a Nintendo
  entrega o SDK já compilado.
- **562 funções ganharam o nome verdadeiro** (`OS_IrqHandler`, `MTX_Concat43`,
  `FS_ReadFile`...), contando ITCM e o `crt0` (`_start`, `do_autoload`). Só entram as
  sem ambiguidade.
- **Prova independente:** `decomp/tools/conferir_chamadas.py` segue todas as chamadas
  e ponteiros das funções nomeadas: das 1.140 referências, as 1.140 apontam para a
  função com o nome que o fonte diz. Um nome errado por coincidência de bytes quebraria
  essa conta.

Com o MSL (171) e o SDK (562), as funções com nome automático (`func_...`) caíram de
5.685 para 4.973 no ARM9 (e para 4.611 com a NitroSystem, abaixo).

## A NitroSystem: 100% da região reconhecida

A NitroSystem é a outra biblioteca da Nintendo: 3D (`NNS_G3d*`, que desenha os
modelos), 2D (`NNS_G2d*`), som (`NNS_Snd*`), memória (`NNS_Fnd*`) e VRAM (`NNS_Gfd*`).
Ela também tem decompilação pública ([ntrtwl/NitroSystem](https://github.com/ntrtwl/NitroSystem),
versão 071126). `decomp/tools/nitrosystem.sh` compila os 96 arquivos dela e procura cada
função no jogo, como `nitrosdk.sh` faz com o SDK.

- **Onde está:** de `0x020c8278` a `0x020d4394`, logo antes do NitroSDK (o SDK começa
  em `MTX_Identity22_`, não em `0x020d4000` como eu achava).
- **Thumb de novo:** em Thumb, 519 funções da biblioteca batem. Em ARM, só batem as dos
  arquivos que o próprio fonte já força para ARM (`#include <nitro/code32.h>`, como os
  cálculos de animação e de textura do 3D), que saem iguais nos dois modos.
- **Compilador:** `2.0/sp2` e `sp2p2` acham 519, `sp1p2` 517, `sp2p3` 513, `2.0/base` 494.
  As duas funções que só a sp2 acerta são `NNSi_G3dFuncSbc_MAT_InternalDefault` e
  `NNSi_G3dFuncSbc_NODEDESC`. Igual ao Platinum: a NitroSystem foi compilada com a sp2,
  e o SDK com a sp1.
- **A versão é a mesma:** das 464 funções da região, **todas** batem com alguma função da
  NitroSystem 071126. Nenhuma sobra: o jogo usa exatamente esta versão.
- **360 nomes novos** (`NNS_G3dDraw`, `NNS_SndArcInit`, `NNS_FndAllocFromExpHeapEx`...).
  As outras ~100 funções são ambíguas: funções `static` com o mesmo nome em vários
  arquivos (`texmtxCalc_flagTRS_` existe nos arquivos do Maya, do 3ds Max e do XSI) ou
  funções idênticas entre si.
- **Conferido pelas chamadas:** 708 de 708 referências certas (1.848 de 1.848 com o SDK).

Com o MSL, o SDK e a NitroSystem, as funções com nome automático no ARM9 caíram de
5.685 para 4.611. Na região do SDK, 628 das 631 funções batem com o fonte; as 3 que
sobram (`0x020d6930`, `0x020e067c`, `0x020e096c`) ainda não sabemos de onde vêm.

## O que não sabemos (ainda)

- **O service pack do compilador com prova direta.** As bibliotecas são da sp2, mas
  em cerca de 30 construções de C++ as versões `2.0/sp1` a `2.0/sp2p4` geraram código
  idêntico; a única diferença achada foi `while (n--)` entre a `2.0/base` e as outras.
  Se uma função futura só bater com outra versão, troca-se em `compilar.sh`.
- **As outras bibliotecas** (o vídeo VX da Actimagine, a de backup): ainda não
  procuradas, e sem decompilação pública conhecida.
- `-enum int`, `-char signed`, `-inline`, `-str`, `-ipa`: ainda sem uma função que
  dependa delas.

## Como repetir

```
decomp/tools/ferramentas.sh
decomp/tools/montar_rom.sh sua_copia.nds      # extrai o ARM9 em work/extract
decomp/tools/testar_compilador.sh             # a matriz acima (~50 s)
```

Para tentar uma função nova: escreva o C++, compile com `compilar.sh` e compare com
`comparar.py` (exemplos em [BUILD.md](BUILD.md#quando-o-build-falha)). Quando bater,
acrescente a linha em `decomp/compilador/casos.txt` e regrave `esperado.txt` com
`conferir_sem_rom.py --gerar` (veja [BUILD.md](BUILD.md#o-que-falta-da-fase-0)): ela passa a
fazer parte do teste e do CI.
