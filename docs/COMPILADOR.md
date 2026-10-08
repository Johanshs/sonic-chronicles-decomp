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
| Modo | `-thumb -interworking` | o código do jogo é Thumb; o NitroSDK é ARM |
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

## O que não sabemos (ainda)

- **O service pack do compilador com prova direta.** As bibliotecas são da sp2, mas
  em cerca de 30 construções de C++ as versões `2.0/sp1` a `2.0/sp2p4` geraram código
  idêntico; a única diferença achada foi `while (n--)` entre a `2.0/base` e as outras.
  Se uma função futura só bater com outra versão, troca-se em `compilar.sh`.
- **As flags do NitroSDK, da NitroSystem e do MSL** (Fase 1.3). São bibliotecas que a
  Nintendo e a Metrowerks compilaram, em ARM, provavelmente com outras flags. Elas
  serão testadas quando a Fase 2 as separar.
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
