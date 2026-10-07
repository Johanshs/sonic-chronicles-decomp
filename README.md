# Sonic Chronicles: The Dark Brotherhood: início de decompilação

Base de engenharia reversa do Sonic Chronicles (DS, `YWSE`, BioWare 2008).
**Não é um port jogável.** É a fundação de que um port como o do Pokémon
Platinum precisa: o código mapeado e nomeado, os formatos de dados decifrados,
e as primeiras funções reescritas em C e Rust, com prova de que estão certas.

## Ferramentas prontas para usar

| Ferramenta | Para quê |
|---|---|
| **`sonic-mod`** | **modificar o jogo**: `unpack` cria um projeto com planilhas (itens, criaturas, lojas...) e textos; `pack` gera a ROM modificada. Testado no emulador. Guia: [`engine/crates/sonic-mod/PROJETO-LEIA-ME.md`](engine/crates/sonic-mod/PROJETO-LEIA-ME.md) |
| **`sonic-dump`** | extrair todos os assets (cenários, retratos, textos, tabelas) para PNG/CSV/JSON em ~7 s |

Binários para Windows e Linux na página de **Releases** (ou `cd engine && cargo build --release`).

## Documentação
- [`docs/PLANO-DECOMPILACAO.md`](docs/PLANO-DECOMPILACAO.md): **o plano da decompilação real**, fase por fase
- [`docs/ARQUITETURA.md`](docs/ARQUITETURA.md): como o jogo e este repositório estão organizados
- [`docs/FORMATOS.md`](docs/FORMATOS.md): referência de todos os formatos decifrados
- [`docs/hierarquia_classes.md`](docs/hierarquia_classes.md): as 290 classes C++ do jogo

> Nenhum código ou arquivo do jogo vem neste pacote. As ferramentas geram
> tudo a partir da **sua** ROM. O pseudo-C e os textos extraídos que
> acompanham esta entrega são para estudo pessoal: não publique.

---

## 1. O que foi descoberto

| Item | Resultado |
|---|---|
| Código ARM9 | 1,1 MB, **sem compressão e sem overlays**; NitroSDK 4.2 (`0x04027531`) |
| Funções encontradas | **6.820** (6.543 no código principal + 277 na ITCM) |
| Linguagem/compilador | C++ com exceções e RTTI → CodeWarrior (Metrowerks), ABI Itanium |
| Classes C++ recuperadas | **290**, com herança, e **351 vtables** |
| Funções com nome | 2.230 automáticas (1.720 métodos virtuais, 151 destrutores, 129 construtores, 382 que constroem objetos inline) + manuais |
| Pseudo-C (Ghidra) | todas as funções, agrupadas por classe |
| Pacote `test.herf` | 8.691 arquivos, **100% dos nomes** (8.690 pelo `erf.dict` oficial; 1 vazio) |
| Textos | ~7.570 textos × 5 idiomas; 101 diálogos (5.509 falas) com quem fala e emoção |
| Tabelas de jogo | 229 tabelas GDA + 431 tabelas 2DA → CSV (63% das colunas GDA com nome) |
| Cenários | **62 áreas** renderizadas em PNG, + mapa de profundidade |
| Gráficos | 3.444 imagens NCGR → PNG; 1.747 com paleta confirmada pelo jogo; 342 retratos/ícones montados |

### O motor é o Aurora da BioWare, adaptado para o DS
Os formatos GFF4, TLK e GDA são os mesmos do **Dragon Age: Origins**, com
adaptações para economizar memória: strings de 8 bits no TLK, números em ponto
fixo (`tipo 18`, 20.12) e strings ASCII inline (`tipo 20`).

### Arquitetura (ver `docs/hierarquia_classes.md`)
- `GameMode` é uma máquina de estados com 16 modos: `GameModeExplore`,
  `GameModeCombat`, `GameModeConversation`, `GameModeChaoGarden`,
  `GameModeWorldMap`...
- `CGameBaseComponent → CGameObject → CGameCreature / CGameSquad / Placeable`
- `Placeable → Puzzle`: uma classe por quebra-cabeça (`GreenHillBoat`,
  `KronBridgePuzzle`, `CentralCityCrane`...)
- `CExoString`, `CTlkTable`, `CErfMan`, `CDSFileSystem`: infraestrutura Aurora.

Pistas extras: uma tabela com 98 tags de profiling (`"Creat:UpdtGamepl"`,
`"BG:SetFocusPoint"`) mostra os subsistemas medidos pelos desenvolvedores. O
profiler foi desligado na versão final: a função de relatório
(`Profiler_PrintReport`, 0x020660c4) não tem nenhum chamador.

---

## 2. O pipeline, passo a passo

`./run_all.sh rom.nds` executa tudo. Cada etapa ensina uma técnica:

1. **Extrair a ROM** (`tools/extract_rom.py`): um `.nds` é um contêiner com
   cabeçalho, ARM9, ARM7 e um sistema de arquivos (NitroFS).
2. **Achar as funções** (`dsd init`): o `dsd` segue as chamadas a partir do
   ponto de entrada e descobre onde cada função começa e termina, e se ela é
   ARM (32 bits) ou Thumb (16 bits). Ele travou em 2 funções escritas à mão
   em assembly (salvam todos os registradores, estilo `setjmp`), por isso o
   `--allow-unknown-function-calls`.
3. **RTTI → nomes** (`tools/rtti.py`): o C++ guarda o nome de cada classe
   polimórfica para `dynamic_cast` e exceções. Seguindo
   `nome → typeinfo → vtable → funções`, cada método virtual ganha nome de
   classe. Construtores são as funções que **gravam** a vtable no offset 0 de
   um objeto. Quem só a inicializa inline (um singleton `static`, por
   exemplo) vira `constructs_<Classe>`, para não mentir. O **destrutor** é o
   método *virtual* que grava a vtable da própria classe em `this`
   (construtores nunca são virtuais). Lição aprendida aqui: eu supus o layout
   da ABI Itanium (destrutores nos slots 0 e 1), o pseudo-C mostrou que estava
   errado, e o CodeWarrior põe o destrutor na ordem em que foi declarado.
4. **Assembly** (`dsd dis`): um `.s` legível com os nomes aplicados.
5. **HERF** (`tools/herf.py`): o pacote guarda só hashes dos nomes. Primeiro
   tentei um **ataque de dicionário** (strings do código + nomes achados dentro
   dos próprios arquivos), que recuperou 91%. Depois descobri que o próprio
   pacote traz um **`erf.dict`** com todos os nomes oficiais: 100%. Comparando
   os dois, o dicionário oficial revelou **12 nomes falsos** (colisões de hash)
   que o ataque tinha aceitado, por exemplo `1_c.emit`, que na verdade é
   `BTN_PUZZ_ON.NCGR`. Os arquivos `.small` têm cabeçalho
   `tipo | tamanho << 8`: tipo 0x10 = LZ10, tipo 0x00 = sem compressão.
6. **Dados legíveis** (`gff4.py`, `dump_dialogs.py`, `gda.py`).
7. **Validação em C** (`make test`): a função de hash decompilada recalcula
   os 8.690 nomes oficiais e bate com 100% deles. Na versão anterior, esse teste
   também **descobriu 4 nomes falsos** que o ataque de dicionário tinha aceitado.
8. **Rust** (`rust/`): a mesma lógica escrita do jeito idiomático, com testes.
9. **Pseudo-C** (Ghidra headless): rascunho automático de todas as funções.

---

## 3. Uma função do começo ao fim

A melhor forma de entender o processo é seguir uma função pelas quatro etapas.

**Assembly original** (`func_02009b78`, Thumb):
```asm
ldr   r4, =0x1505          ; hash = 5381          <- assinatura do DJB2
bl    CExoString__CStr     ; s = name.CStr()
ldrsb r5, [r0, r1]         ; c = (signed char)*s   <- COM sinal!
...
ldrb  r5, [r0, r5]         ; se 0<=c<0x80: c = tabela_minusculas[c]
lsl   r7, r4, #5           ; hash*32
add   r4, r7               ; hash*33
add   r4, r5, r4           ; hash*33 + c
```

**Ghidra cru** (automático, antes dos nomes):
```c
iVar4 = DAT_02009bb4;                 // não sabe que é 5381
pcVar3 = (char *)func_020052f0();
...
iVar4 = uVar5 + iVar4 * 0x21;
```

**C reescrito à mão** (`src/resource_hash.c`):
```c
u32 HashResourceName(const CExoString *name) {
    u32 hash = 5381;
    const s8 *s = (const s8 *)CExoString_CStr(name);
    for (s32 c = *s++; c != 0; c = *s++) {
        if (c >= 0 && c < 0x80) c = s_toLower[c];
        hash = hash * 33 + (u32)c;
    }
    return hash;
}
```

**Rust** (`rust/src/lib.rs`): `hash_resource_name()`, com o mesmo cuidado com o sinal.

Prova: `make test` recalcula 8.690 hashes do jogo e todos batem (com `MANIFEST=saida/herf/_manifesto.json`, valida a saída do `sonic-dump`).

---

## 4. Estrutura

```
run_all.sh              pipeline completo
symbols_manual.txt      nomes identificados à mão (com a evidência)
tools/                  extratores e analisadores (Python)
ghidra_scripts/         SetupSonic.java (prepara) + DecompileAll.java (pseudo-C)
src/ include/ tests/    decompilação manual em C + testes contra o jogo
rust/                   crate Rust mínima: HERF, hash, LZ10 (+ CLI `herf`) — versão didática
engine/                 workspace Rust: biblioteca sonic-formats + ferramentas sonic-dump e sonic-mod
docs/                   hierarquia de classes, notas de formato
```

Requisitos: Python 3 (`pip install ndspy capstone`), Rust/cargo, um
compilador C, e opcionalmente o Ghidra 11.x (`GHIDRA_HOME`). No Windows,
use WSL.

---

## 5. Até onde isto vai e o que falta

O plano detalhado, fase por fase, está em [`docs/PLANO-DECOMPILACAO.md`](docs/PLANO-DECOMPILACAO.md).

Esta é uma decompilação **"non-matching"**: o C reescrito faz a mesma coisa,
mas não gera os mesmos bytes. Para chegar ao nível do projeto do Platinum:

1. **Descobrir a versão exata do compilador** (mwccarm) e as flags. É o que
   permite compilar o C e comparar byte a byte com o original.
2. **Montar a ROM de volta** com `dsd delink` + `dsd lcf` + linker. Quando o
   `.nds` reconstruído for idêntico ao original, cada função pode ser trocada
   de assembly para C, uma por vez, e conferida com o `objdiff`.
3. **Reescrever função por função.** São 6.820. O pseudo-C do Ghidra é o
   rascunho; os nomes de classe já dizem a qual sistema cada função pertence.
4. **Para um port de PC**, a camada de hardware (NitroSDK: gráficos 2D/3D,
   som, entrada) precisa ser substituída, como a `libntr` fez para o Platinum.

Ainda não decifrados: os vídeos `.vx` (Actimagine), a montagem das telas `.gui`
(as peças são esticadas/repetidas por regras de layout ainda desconhecidas), as
paletas dos Chao (escolhidas em tempo de execução) e os 37% de nomes de coluna
GDA que faltam. Modelos 3D (`.nsbmd`) e áudio (`.sdat`) são formatos padrão da
Nintendo: o [apicula](https://github.com/scurest/apicula) e o VGMTrans já os convertem.

---

## 6. `sonic-mod`: modding

```
sonic-mod unpack rom.nds meu_mod/          # cria planilhas, textos e arquivos editáveis
# ... edite meu_mod/tabelas/test/Items.csv, meu_mod/textos/en.csv ...
sonic-mod pack rom.nds meu_mod/ rom_modificada.nds
```

Como funciona: os escritores de GDA, TLK, HERF e LZ10 reproduzem os arquivos
originais **byte a byte**, então o `pack` detecta exatamente o que você mudou e só
regrava isso. Os arquivos alterados vão para o lugar original, se couberem, ou para
o fim do cartucho; a FAT e o CRC do cabeçalho são atualizados.

Descobertas que tornaram isso possível:
- o TLK é uma **tabela hash** (função `0x020989fc` do jogo), então inserir um texto
  novo exige calcular a posição certa. Sem isso, o jogo não acharia o texto;
- o índice do HERF é **ordenado por hash** (o jogo faz busca binária).

Teste no emulador (DeSmuME sem janela, `tools/emu_run.py`): editar a tabela
`Chapter0` para apontar para um texto novo (id 990001) fez a tela de abertura
mostrar o texto criado.

## 7. `sonic-dump`: extrator de assets (e base do futuro executável)

```
sonic-dump rom.nds saida/          # Windows: sonic-dump.exe rom.nds saida
  --sem-imagens --sem-cenarios --sem-json --sem-bruto
```

O código fica em `engine/`, dividido em partes de propósito:

- **`sonic-formats`** (biblioteca): todos os formatos do jogo (ROM/NitroFS, HERF +
  `erf.dict`, LZ10/`.small`, GFF4, TLK, GDA, 2DA, NCLR/NCGR, cenários). Não grava
  nada em disco e não sabe que existe linha de comando. Um futuro executável que
  carregue os assets originais (um visualizador de áreas, um port) usa esta mesma
  biblioteca. Por exemplo, `background::render()` já devolve o cenário pronto
  para virar textura.
- **`sonic-dump`** (ferramenta): usa a biblioteca e grava tudo em formatos
  abertos, em paralelo (`rayon`).

O que sai: `bruto/` (arquivos originais), `herf/` (8.901 arquivos nomeados e
descomprimidos), `textos/` (CSV com 5 idiomas + roteiro por idioma), `tabelas/`
(CSV), `json/` (todo GFF4 em JSON), `imagens/sprites|montadas|cenarios`.

### Cenários: como o formato foi decifrado
1. `.pal` tem 136.192 bytes = 266 × 512, e a área tem 19 × 14 = 266 blocos 2×2:
   **uma paleta de 256 cores por bloco de 2×2 tiles**.
2. Os tiles do `.cbgt` começam com `0x10` (LZ10) e descomprimem para 4.096 bytes
   = 64×64 pixels a 8 bpp, organizados em **blocos 8×8** (a desordem visível no
   primeiro teste denunciou isso).
3. A ordem dos tiles foi escolhida **medindo**: a diferença de cor entre bordas
   vizinhas foi 4,8 para "linha a linha com o mapa de paletas do `.2da`" e de 35
   a 56 nas outras hipóteses.
4. O `.cdpth` usa o mesmo índice, mas com valores de 16 bits em ordem **linear**
   (`0x7FFF` = vazio). É o que diz ao jogo quais pilares e estátuas ficam na frente
   dos personagens.

### Paletas dos sprites
Há 3.444 imagens para só ~210 paletas. Em ordem de confiança: `gui` (a tela diz,
no struct `IMG`, campo 60004 = imagem e 60015 = paleta), `tabela` (uma linha de
GDA cita a paleta, ex.: `PRTL_TAILS` → `PRTL_Tal.nclr`), `mesmo_nome`, `prefixo`
(palpite) e `cinza` (desconhecida). `imagens/_paletas.json` registra o método de
cada imagem.

### Compilar
```
cd engine && cargo build --release                    # Linux/macOS/Windows nativo
# Windows a partir do Linux (como os binários de bin/ foram feitos):
pip install ziglang cargo-zigbuild
rustup target add x86_64-pc-windows-gnu
cargo zigbuild --release --target x86_64-pc-windows-gnu -p sonic-dump
```
Licença: GPL-3.0 (a tabela de colunas GDA embutida vem do xoreos).

---

Sonic Chronicles: The Dark Brotherhood © SEGA / BioWare. Projeto de fãs, sem
afiliação. Nenhum código, binário ou asset do jogo é distribuído aqui: tudo é
gerado a partir de uma cópia do jogo que você possui.

## Créditos
- [ds-decomp (`dsd`)](https://github.com/AetiasHax/ds-decomp): análise e disassembly
- [xoreos](https://github.com/xoreos/xoreos): documentação dos formatos Aurora e
  a tabela de nomes de coluna GDA (`tools/gda_columns_xoreos.json`, GPLv3)
- [ndspy](https://github.com/RoadrunnerWMC/ndspy), [Capstone](https://www.capstone-engine.org/), [Ghidra](https://ghidra-sre.org/)
