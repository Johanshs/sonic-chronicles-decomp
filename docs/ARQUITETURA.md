# Arquitetura

## O jogo

Sonic Chronicles roda no motor **Aurora da BioWare** (o mesmo família de NWN, KotOR,
Dragon Age), adaptado para o DS e escrito em C++ (CodeWarrior, com RTTI e exceções).

```
 ┌────────────────────────── ARM9 (1,1 MB de código) ───────────────────────────┐
 │ Jogo:  GameMode (16 modos) · GuiManager · CGameObject e derivados · Puzzles   │
 │ Motor Aurora: CExoString · CDSFileSystem/CErfMan · CTlkTable · CRules · GFF4 │
 │ NitroSystem (NNS: G3D, G2D, som) · MSL C++ (Metrowerks) · NitroSDK 4.2       │
 └───────────────────────────────────────────────────────────────────────────────┘
 Dados (NitroFS):  test.herf (8.691 recursos) · test_[efgis].herf (por idioma)
                   strings*.tlk (textos) · <área>.cbgt/.pal/.2da/.cdpth (cenários)
                   *.vx (vídeos) · sound_data.sdat (som)
```

O jogo é **guiado por dados**: itens, criaturas, lojas, capítulos, diálogos,
áreas e telas são tabelas e arquivos GFF4 dentro do `test.herf`. É isso que torna
o modding por dados (`sonic-mod`) possível antes da decompilação estar pronta.

Fluxo de um recurso: o código pede um nome (ex.: `"Items.GDA"`); `CErfMan` calcula
`HashResourceName` (DJB2), procura `nome.small` e depois `nome` no índice ordenado
do HERF (busca binária), descomprime o `.small` (LZ10) se preciso, e o leitor do
formato (GFF4/GDA/TLK) interpreta.

## Este repositório

```
engine/                       Rust (workspace)
  crates/sonic-formats/       biblioteca: todos os formatos, leitura E escrita
  crates/sonic-dump/          CLI: extrai assets para PNG/CSV/JSON
  crates/sonic-mod/           CLI: unpack (projeto editável) / pack (ROM modificada)
tools/                        Python: análise (RTTI, xref, HERF, GFF4, emulador)
ghidra_scripts/               preparação do Ghidra + decompilação em massa
src/ include/ tests/          funções do jogo reescritas em C + testes contra o jogo
rust/                         versão didática mínima (HERF + LZ10)
docs/                         esta documentação
run_all.sh                    pipeline de análise completo
```

### Princípios
1. **Nada do jogo no repositório.** Tudo é gerado a partir da ROM do usuário.
2. **Toda escrita é provada por ida e volta.** Ler e escrever sem mudar nada tem
   que dar o arquivo original byte a byte (`engine/crates/sonic-formats/tests`).
3. **Toda descoberta é validada contra o jogo**, nunca só contra a hipótese:
   hashes recalculados, cenários medidos pelas bordas, mods testados no emulador.
4. **A biblioteca não sabe de disco nem de CLI.** Assim um futuro executável
   (visualizador, port) reaproveita os mesmos leitores.

### Testes
```
cd engine && cargo test --release                                 # unitários
SONIC_ROM=rom.nds cargo test --release -- --nocapture             # ida e volta com a ROM real
make test MANIFEST=saida/herf/_manifesto.json                     # funções em C contra o jogo
SDL_VIDEODRIVER=dummy python3 tools/emu_run.py rom.nds out "w 600; s tela"   # no emulador
```
