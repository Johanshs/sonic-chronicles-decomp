# Build "matching": reconstruir a ROM idêntica

Este é o resultado da **Fase 0** do [plano](PLANO-DECOMPILACAO.md): a ROM do jogo é
desmontada em pedaços, ligada de novo com o linker original da Metrowerks e sai
**idêntica byte a byte** à sua (mesmo SHA-1). A partir daí, cada função que for
decompilada para C++ entra no lugar do pedaço correspondente, e este mesmo build
prova que nada mudou.

```
decomp/tools/ferramentas.sh                  # uma vez: dsd, wibo e mwccarm em work/ferramentas/
decomp/tools/montar_rom.sh sua_copia.nds     # reconstrói e confere: "IDÊNTICA"
```

Requisitos: Linux x86-64 (ou WSL), `python3` com `pip install capstone pyelftools pillow`,
`curl`, `unzip`. O build leva uns 7 segundos. A ROM esperada (USA, `YWSE`) tem
SHA-1 `f4ff8291b38bf9a33ab280fb9f7625cf4d549473`.

> Nada disto vai para o Git: `work/` está no `.gitignore`. No repositório ficam só
> os scripts, o C++ decompilado (`src/`, `include/`) e a configuração (`config/`),
> que tem endereços, tamanhos e nomes, nenhum byte do jogo.

---

## O que cada passo faz e por quê

| Passo | Ferramenta | O que acontece |
|---|---|---|
| 1. extrair | `dsd rom extract` | separa a ROM em código (`arm9.bin`, ITCM, DTCM, `arm7.bin`), cabeçalho, banner e os 303 arquivos |
| 2. delink | `dsd delink` | corta o ARM9 em arquivos-objeto ELF (`.o`) |
| 2b. compilar | `mwccarm` | compila os arquivos de `src/` marcados como prontos |
| 3. lcf | `dsd lcf` | escreve o script do linker: a ordem de cada `.o` na memória |
| 4. link | `mwldarm` | o linker original junta tudo e resolve os endereços |
| 5. rom | `dsd rom config/build` | monta o `.nds` |
| 6. conferir | `dsd check` + SHA-1 | compara ARM9/ITCM/DTCM e a ROM inteira com a original |

### Delink: o contrário de ligar

Um compilador gera um `.o` por arquivo-fonte. Dentro dele, o código não sabe onde vai
morar: onde há um `bl CExoString::CStr`, o `.o` só guarda uma **relocação**, uma nota
dizendo "o linker põe aqui o endereço de `CStr`". O linker decide os endereços e
preenche as notas.

O `dsd delink` faz o caminho inverso. Ele pega o binário pronto e, usando as listas
`config/YWSE/arm9/symbols.txt` (onde começa cada função e cada dado) e `relocs.txt`
(cada lugar do código que aponta para outro endereço, 60 mil deles), recria arquivos
`.o` com as notas no lugar dos endereços. Se alguma relocação estiver errada ou
faltando, os endereços saem diferentes depois do link e o passo 6 acusa.

Por isso o build idêntico é a **rede de segurança**: ele prova que o mapa de símbolos
e relocações está certo, antes de qualquer linha de C++.

### Os arquivos de `config/YWSE/arm9/`

- `delinks.txt`: as seções do ARM9 (`.text` código, `.rodata` constantes, `.data`,
  `.bss`...) e, embaixo, os **arquivos-fonte** já identificados, com o pedaço de cada
  seção que pertence a eles. O que não está em nenhum arquivo vira um `_dsd_gap`
  (um "buraco" que continua sendo o código original). Um arquivo marcado `complete`
  já foi decompilado: o build usa o `.o` compilado de `src/` no lugar do cortado.
- `symbols.txt`: cada função e dado com endereço, tipo (ARM/Thumb) e tamanho. Os
  nomes vêm do RTTI e de `analise/symbols_manual.txt`. Uma função decompilada usa o
  nome "mangled" que o compilador gera (`_ZNK10CExoString4CStrEv`), para que o resto
  do código, que chama esse nome, a encontre.
- `relocs.txt`: as relocações.

`decomp/tools/gerar_config.sh rom.nds` gera tudo isso do zero (`dsd init` + nomes).
Ele **apaga** as edições à mão: depois da primeira vez, `config/` é editado e
versionado.

### Dois detalhes fora do código

A primeira reconstrução saiu com **20 bytes diferentes**, nenhum deles de código:

1. **O ícone do banner (16 bytes + CRC).** O `dsd` salva o ícone como PNG colorido e,
   na volta, cada pixel é convertido para o **primeiro** índice da paleta com aquela
   cor. A paleta do jogo tem duas entradas iguais (2 e 4 = `0x2083`), então todo pixel
   de índice 4 voltava como 2. `decomp/tools/banner_sem_perda.py` regrava os PNGs
   usando os 3 bits baixos de cada canal, que o DS ignora (a cor do DS tem 5 bits, o
   PNG tem 8), para que cada índice tenha uma cor PNG única.
2. **O CRC da área segura (2 bytes + CRC do cabeçalho).** Os primeiros 16 KB do ARM9
   ficam criptografados no cartucho, e o cabeçalho guarda o CRC dessa versão
   criptografada. A chave está na BIOS do ARM7, que não temos (nem podemos
   distribuir), e sem ela o `dsd` grava 0. `decomp/tools/crc_area_segura.py` confere
   que os 16 KB reconstruídos são idênticos aos da original e só então copia o CRC.
   Se alguém mudar o começo do ARM9, ele recusa; aí é preciso a BIOS
   (`dsd rom build --arm7-bios bios7.bin`).

### Quando o build falha

```
DIFERENTE. Primeiros bytes que mudaram:
   offset 0xdba6 (ARM9 0x02009ba6): 2c -> 64
```

O endereço do ARM9 aponta para a função (procure em `symbols.txt` a que contém o
endereço). Compile o arquivo e compare só aquela função:

```
decomp/tools/compilar.sh src/Aurora/ResourceHash.cpp /tmp/x.o
python3 decomp/tools/comparar.py /tmp/x.o --listar
python3 decomp/tools/comparar.py /tmp/x.o _Z16HashResourceNameRK10CExoString 0x02009b78
```

O `comparar.py` mostra o assembly do jogo e o seu lado a lado, com `!!` nas
instruções diferentes e `R` nos bytes que o linker ainda vai preencher.

---

## As bibliotecas da Nintendo, ligadas do fonte

A NitroSystem inteira (de `0x020c8278` a `0x020d4394`, 59 arquivos) e 84 dos 87
arquivos do NitroSDK que o jogo usa não vêm mais do assembly cortado: o build compila
os `.c` do fonte público (veja [COMPILADOR.md](COMPILADOR.md#a-nitrosystem-100-da-região-reconhecida))
e liga os `.o`, e a ROM continua idêntica. São 95 KB, **9,8% do código do ARM9** (com o ITCM). Na
primeira vez, `montar_rom.sh` baixa e compila as bibliotecas sozinho (`nitrosdk.sh` e
`nitrosystem.sh`, para `work/bibliotecas/`).

Os 3 arquivos do SDK que ainda vêm do assembly, e por quê:

| Motivo | Arquivos |
|---|---|
| uma função no meio não bate com o fonte | `card_backup.c`, `gx_vramcnt.c` |
| têm a seção `.version`, que o linker da Nintendo punha num lugar próprio | `os_china.c` |

Quatro coisas no link que só apareceram com o SDK:

- **Funções que ninguém chama.** O jogo tem `OS_DisableProtectionUnit`, que nada chama.
  O linker original a manteve; o nosso, com `-dead`, joga fora. `montar_rom.sh` põe um
  bloco `FORCE_ACTIVE` no `.lcf` com as funções globais dos arquivos ligados. (A opção
  `-force_active` da linha de comando aborta, sem mensagem, quando a lista passa de
  ~256 caracteres.)
- **Funções "weak".** `OS_Terminate` e `OS_Halt` são declaradas fracas no SDK (o jogo
  poderia ter a sua própria versão). O `mwcc` grava isso com um código próprio (14), e
  `symbols.txt` precisa dizer `weak`.
- **Símbolos que o linker calculava.** `os_arena.c`, `os_thread.c` e outros usam
  `SDK_SYS_STACKSIZE`, `SDK_MAIN_ARENA_LO`, `SDK_AUTOLOAD_DTCM_START`... Eles não estão
  em nenhum `.c`: o `.lcf` da Nintendo os definia. Estão em
  `config/YWSE/arm9/simbolos_linker.lcf`, que `montar_rom.sh` cola no `.lcf` gerado
  pelo `dsd`, com valores conferidos contra os que o jogo tem gravados no código.
- **Um arquivo em três módulos.** `os_irqHandler.c` tem `OS_WaitIrq` no ARM9,
  `OS_IrqHandler` no ITCM (a memória rápida, para a interrupção) e uma variável no
  DTCM. É um `.o` só, mas o `dsd` corta cada módulo à parte e não aceita o mesmo nome
  em dois. Então a parte do ITCM aparece em `itcm/delinks.txt` como
  `os_irqHandler.itcm.c` (e a do DTCM como `.dtcm.c`), e `montar_rom.sh` troca no
  `.lcf` `os_irqHandler.itcm.o(.text)` por `os_irqHandler.o(.itcm)`. Os `static` que uma
  parte usa da outra (`OSi_DoResetSystem`) ficam globais em `symbols.txt`, senão o
  `dsd` recusa; o `dsd check symbols` aponta essa diferença e `montar_rom.sh` deixa
  passar só ela.

Quem escreve essas entradas em `delinks.txt` é `decomp/tools/ligar_bibliotecas.py`:

1. **Qual arquivo é cada função.** O linker põe as funções de um arquivo juntas e na
   ordem do `.o`. O script percorre a região e corta onde muda o arquivo de origem.
   Quando duas funções têm o mesmo código (os `NNS_G3dFree*`, que só chamam
   `NNS_FndFreeToAllocator`), desempatam o destino das chamadas e a ordem no `.o`.
2. **Onde estão os dados de cada arquivo.** Se a função X do `.o` lê `.bss+8` e no
   jogo o ponteiro vale `0x021b0d68`, a `.bss` daquele arquivo começa em `0x021b0d60`.
   Os bytes de `.data`/`.rodata` são conferidos, ponteiros incluídos.
3. **Os nomes que o `.o` espera.** O `.o` chama `_s32_div_f`, `FS_ReadFile`... O endereço
   de cada um sai da instrução do jogo, e o nome entra em `symbols.txt`. As funções
   `static` ficam `local`, e os dados ganham o tamanho que têm no `.o`.
4. **Quem aponta para o meio de um arquivo.** O jogo usa `NNS_G3dGlb + 0x80` (um campo
   da estrutura). O `.o` só tem o símbolo `NNS_G3dGlb`, então a relocação vira
   `to:NNS_G3dGlb add:0x80`.

```
python3 decomp/tools/ligar_bibliotecas.py NitroSystem work/NitroSystem \
    work/bibliotecas/nitrosystem 0x020c8278 0x020d4394            # só mostra
python3 decomp/tools/ligar_bibliotecas.py ... --aplicar           # grava
```

## As ferramentas e as versões

| Ferramenta | Versão | De onde |
|---|---|---|
| `dsd` | 0.12.1 (binário da release) | [ds-decomp](https://github.com/AetiasHax/ds-decomp/releases/tag/v0.12.1) |
| `wibo` | 0.6.16 | [decompals/wibo](https://github.com/decompals/wibo): roda os `.exe` de 32 bits da Metrowerks no Linux, bem menor que o Wine |
| `mwccarm`, `mwldarm` | 2.0/sp2 (veja [COMPILADOR.md](COMPILADOR.md)) | pacote `mwccarm.zip` do [decomp.me](https://github.com/decompme/compilers) |

Todas são baixadas com SHA-256 conferido. Por que a release do `dsd` e não o código
do `main`: compilado do `main` (commit `c408063`), o `dsd lcf` acusa "nome de arquivo
duplicado" em todo `_dsd_gap` assim que o ARM9 é dividido em mais de um arquivo. O
binário da release 0.12.1 não tem o problema.

## O que falta da Fase 0

**0.4, o CI com a ROM.** O build completo precisa da ROM, e ela não pode ir para o
GitHub (nem como segredo: o limite de um segredo é 48 KB). Rode `montar_rom.sh`
antes de cada PR que mexa em `src/` ou `config/`.

Enquanto isso, o CI já confere a parte que mais quebra, **sem a ROM**: o job
`decomp-matching` compila cada função de `decomp/compilador/casos.txt` e compara o
SHA-1 dos bytes (com as relocações zeradas) com `decomp/compilador/esperado.txt`.
Só o hash fica no repositório. Se o C++ de uma função deixar de bater, o PR fica
vermelho. Ao igualar uma função nova, acrescente-a em `casos.txt` e rode
`python3 decomp/tools/conferir_sem_rom.py --gerar work/extract/arm9/arm9.bin`.
