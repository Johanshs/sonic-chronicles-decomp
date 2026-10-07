# Ferramentas

As ferramentas estão em três grupos:

- **`engine/`** (Rust): o que se usa no dia a dia. Rápido e testado, com binários para Windows e Linux.
- **`analise/`** (Python, Java/Ghidra, shell): o pipeline de engenharia reversa.
  É onde as descobertas foram feitas.
- **`decomp/`** (C): funções do jogo reescritas e os testes que as validam.

Requisitos gerais: Rust 1.80+ (`cargo`), Python 3.10+ (`pip install ndspy capstone pillow`),
um compilador C. Opcionais: Ghidra 11.x (`GHIDRA_HOME`), `py-desmume` (emulador).

---

## `sonic-mod`: modding

```
sonic-mod unpack <rom.nds> <projeto>
sonic-mod pack   <rom.nds> <projeto> <saida.nds>
```

**unpack** cria um projeto editável:

| Saída | Origem |
|---|---|
| `tabelas/<pacote>/<Tabela>.csv` | cada GDA dos pacotes HERF (229), com nomes de coluna |
| `textos/<idioma>.csv` (`id,texto`) | os 5 TLK (`en`, `fr`, `de`, `es`, `it`) |
| `arquivos/<pacote>/*` | tabelas em texto 2DA (`.ITM` efeitos de itens, `.SPL` golpes...) |
| `LEIA-ME.md` | o [guia de modding](MODDING.md) |

**pack**, por dentro, em ordem:
1. Lê a ROM original e recupera os nomes dos recursos (`erf.dict`).
2. Para cada planilha: lê a tabela original para saber o **tipo de cada coluna**,
   converte as células (com erro claro de arquivo/linha/coluna), gera o GDA e compara
   com o original. Os escritores são exatos, então "igual" quer dizer que você não mexeu.
3. Arquivos em `arquivos/`: o mesmo nome substitui o original; um nome novo **adiciona**
   o recurso ao pacote (com o hash certo, na posição certa do índice ordenado, e no `erf.dict`).
4. Textos: altera os ids existentes e **insere ids novos na tabela hash** do TLK, com a
   mesma função de hash do jogo.
5. Reempacota os HERF alterados, recomprimindo em LZ10 o que era `.small`.
6. Grava os arquivos na ROM: no lugar original se couberem, senão no fim do cartucho;
   atualiza a FAT, o tamanho usado e o CRC16 do cabeçalho.
7. **Reabre a ROM gerada** e confere que cada arquivo gravado volta idêntico.

Sem mudanças, `pack` diz "nada mudou" e não gera nada. Esse também é o teste de que o
`unpack` não perde nenhuma informação.

## `sonic-dump`: extrator de assets

```
sonic-dump <rom.nds> <saida> [--sem-imagens] [--sem-cenarios] [--sem-json] [--sem-bruto]
```

| Saída | Conteúdo |
|---|---|
| `bruto/` | arquivos originais do NitroFS + `arm9.bin`, `arm7.bin` |
| `herf/<pacote>/` | 8.901 recursos descomprimidos e com nome + `_manifesto.json` |
| `textos/` | `textos_5_idiomas.csv` e `roteiro_<idioma>.txt` (diálogos, com personagem e emoção) |
| `tabelas/gda/`, `tabelas/2da/` | 229 tabelas binárias e 431 em texto, em CSV |
| `json/` | todo GFF4 (diálogos, áreas, telas, plots) em JSON |
| `imagens/sprites/` | 3.444 NCGR em PNG; `imagens/_paletas.json` diz a paleta e o método usado |
| `imagens/montadas/` | 342 retratos/ícones (4 peças 64×64 montadas em 128×128) |
| `imagens/cenarios/` | 62 áreas completas + `_profundidade.png` |

Paleta de cada sprite, em ordem de confiança: `gui` (as telas dizem), `tabela` (uma
linha de GDA cita), `mesmo_nome`, `prefixo` (palpite), `cinza` (desconhecida).
Roda em paralelo (`rayon`): cerca de 7 segundos para tudo.

## `sonic-formats`: a biblioteca

A base das duas ferramentas acima e de um futuro executável. Não faz E/S de disco.

| Módulo | Ler | Escrever | Destaque |
|---|---|---|---|
| `nds` | `Rom::parse`, NitroFS | `replace_file`, `header_crc16` | troca arquivos com o mínimo de mudanças |
| `herf` | `Herf`, `parse_name_dict`, `recover_names` | `write`, `write_name_dict` | ataque de dicionário + `erf.dict` |
| `compression` | `lz10_decompress`, `open_small` | `lz10_compress`, `make_small` | sem distância 1 (seguro p/ VRAM) |
| `gff4` | `Gff4::root()` → JSON | (planejado) | tipos 18 e 20, exclusivos do Sonic |
| `tlk` | `Tlk::parse`, `get`, `texts` | `set`, `remove`, `to_bytes` | tabela hash do jogo (`slot_hash`) |
| `gda` | `Gda::parse`, `cell_to_text` | `to_bytes`, `cell_from_text` | tipado por coluna |
| `twoda` | `read` | (texto puro) | |
| `nitro` | `Palette`, `Tiles::render` | | NCLR/NCGR |
| `background` | `render`, `render_depth` | | cenários `.cbgt` |
| `image`, `csv` | utilitários | | PNG, CSV com `,` ou `;` |

Testes: `cargo test` (unitários) e `SONIC_ROM=rom.nds cargo test` (ida e volta com a ROM
real: 5 TLK, 6 HERF, 229 GDA idênticos; 400 arquivos recomprimidos em LZ10 sem perda).
Documentação da API: `cd engine && cargo doc --open`.

---

## `analise/`: pipeline de engenharia reversa

`./analise/run_all.sh rom.nds [--sem-ghidra]` faz tudo em sequência dentro de `work/`.

| Passo | Ferramenta | O que faz |
|---|---|---|
| 1 | `tools/extract_rom.py` | extrai ARM9, ARM7 e o NitroFS (`ndspy`) |
| 2 | `dsd init` | acha as 6.820 funções e o modo ARM/Thumb de cada uma |
| 3 | `tools/rtti.py` | lê o RTTI do C++: 290 classes, 351 vtables; nomeia métodos virtuais, construtores e destrutores pelo **comportamento** (quem grava a vtable em `this`) |
| 3b | `tools/apply_names.py` | aplica `symbols_manual.txt` (nomes dados à mão, com a evidência) |
| 4 | `dsd dis` | assembly completo com os nomes |
| 5 | `tools/herf.py` | extrai pacotes HERF (`erf.dict` + ataque de dicionário) |
| 6 | `tools/dump_dialogs.py`, `tools/gda.py` | roteiro e tabelas legíveis |
| 7 | `make -C decomp test` | valida as funções em C contra o jogo |
| 8 | `cargo test` (engine) | testes da biblioteca |
| 9 | Ghidra headless | `ghidra_scripts/SetupSonic.java` cria ITCM/DTCM, marca código como somente leitura (para o decompilador mostrar constantes) e cria as funções; `DecompileAll.java` gera um `.c` por classe |

Outras ferramentas:

| Ferramenta | Uso |
|---|---|
| `tools/xref.py arm9.bin symbols.txt relocs.txt saida.json` | quais funções usam quais strings (pelas relocações do literal pool) |
| `tools/gff4.py arquivo [saida.json]` | qualquer GFF4 → JSON (referência em Python do leitor Rust) |
| `tools/emu_run.py rom.nds pasta "roteiro"` | roda a ROM no DeSmuME sem janela e executa ações: `w N` espera, `p TECLA` aperta, `t X Y` toca a tela, `s nome` captura, `save`/`load` estado. Precisa de `SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy` |
| `tools/ghidra_symbols.py` | converte os símbolos do dsd para o Ghidra |
| `tools/manifest_pairs.py` | lista hash/nome de um manifesto (para os testes em C) |

Exemplo de teste de mod no emulador (chega à tela da citação de abertura):
```
SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy python3 analise/tools/emu_run.py rom_mod.nds shots \
  "w 400; t 128 96; w 200; t 128 96; w 200; t 128 96; w 240; t 128 96; w 240; t 128 140; w 240; t 128 96; w 300; s citacao"
```

## `decomp/`: funções reescritas em C

| Arquivo | Função do jogo | Validação |
|---|---|---|
| `src/resource_hash.c` | `HashResourceName` (0x02009b78) | recalcula os 8.690 nomes do `erf.dict`: 100% |
| `src/exo_string.c` | `CExoString::CStr` (0x020052f0) | usada pela anterior |
| `src/language.c` | escolha do TLK por idioma (trecho de 0x020148c8) | os 7 casos do `switch` |

```
make -C decomp test HERF_DIR=$PWD/work/herf/test          # saída do run_all.sh
make -C decomp test MANIFEST=$PWD/saida/herf/_manifesto.json   # saída do sonic-dump
```
Estas são decompilações *non-matching* (mesmo comportamento, não os mesmos bytes). O
caminho para o matching está no [plano](PLANO-DECOMPILACAO.md).

## `exemplos/rust-minimo/`

Uma crate de ~150 linhas com o essencial (hash, HERF, LZ10) e uma CLI `herf list/get`.
É o melhor ponto de partida para quem está aprendendo Rust e quer ver o formato inteiro
de uma vez, sem a estrutura da biblioteca completa.

## Publicar uma versão

```
git tag v0.3.0 && git push origin v0.3.0
```
ou, sem linha de comando: aba **Actions → release → Run workflow**, informando a versão.
O workflow `.github/workflows/release.yml` compila no Windows e no Linux (máquinas do
GitHub), roda os testes e publica a release com `sonic-tools-windows.zip` e
`sonic-tools-linux.tar.gz`. A CI normal (`ci.yml`) roda em todo push.

## Compilar para Windows a partir do Linux

```
pip install ziglang cargo-zigbuild
rustup target add x86_64-pc-windows-gnu
cd engine && cargo zigbuild --release --target x86_64-pc-windows-gnu -p sonic-mod -p sonic-dump
```
Os `.exe` dependem só de DLLs do sistema (Windows 10/11).
