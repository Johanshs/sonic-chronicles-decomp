# Sonic Chronicles: The Dark Brotherhood: decomp e modding

Engenharia reversa do **Sonic Chronicles: The Dark Brotherhood** (Nintendo DS, BioWare, 2008).
O objetivo é entender o jogo por dentro, poder **modificá-lo** e, no fim, ter o código
inteiro decompilado, a base para um executável nativo de PC.

> **Nada do jogo está neste repositório.** Nem ROM, nem assets, nem código do jogo.
> Todas as ferramentas trabalham a partir de uma cópia que você possui.

## O espírito do projeto

Este é um projeto para **aprender fazendo**, com uma regra acima de todas: *nenhuma
descoberta vale até ser conferida contra o jogo de verdade*. Cada formato decifrado é
reescrito e comparado byte a byte com o original; cada função reescrita é testada
contra milhares de dados reais; cada mod é aberto no emulador. Quando uma hipótese
estava errada, e várias estavam, o erro e a correção ficam registrados, porque é
assim que se aprende. Leia [`docs/ESPIRITO.md`](docs/ESPIRITO.md) e o diário das
descobertas em [`docs/DIARIO.md`](docs/DIARIO.md).

## Onde estamos

| Frente | Situação |
|---|---|
| **Modding** | ✅ `sonic-mod`: edite itens, criaturas, lojas e textos em planilhas e gere a ROM. Testado no emulador. |
| **Assets** | ✅ `sonic-dump`: 62 cenários, 3.444 sprites, 342 retratos, textos em 5 idiomas, 660 tabelas, em ~7 s |
| **Formatos** | ✅ ROM, HERF, LZ10, GFF4, TLK, GDA, 2DA, NCGR/NCLR e cenários: lidos **e escritos** byte a byte |
| **Código** | 🟡 6.820 funções mapeadas, 290 classes C++ recuperadas, ~2.230 funções nomeadas, pseudo-C de tudo |
| **Decompilação matching** | ⏳ planejada: [`docs/PLANO-DECOMPILACAO.md`](docs/PLANO-DECOMPILACAO.md) (7 fases, backlog nas *issues*) |
| **Port para PC** | ⏳ Fase 7 do plano; hoje o jogo (modificado) roda no PC via emulador |

## Começando

**Só quero modificar o jogo (Windows):** baixe `sonic-tools-windows.zip` nas
[Releases](../../releases), e então:
```powershell
.\sonic-mod.exe unpack "Sonic Chronicles.nds" meu_mod
# edite meu_mod\tabelas\test\Items.csv, meu_mod\textos\en.csv ...
.\sonic-mod.exe pack "Sonic Chronicles.nds" meu_mod rom_modificada.nds
```
Guia completo: [`docs/MODDING.md`](docs/MODDING.md). Para jogar, use o melonDS ou o DeSmuME.

**Quero os assets:** `sonic-dump "Sonic Chronicles.nds" saida`

**Quero compilar e estudar:**
```bash
cd engine && cargo build --release && cargo test --release
SONIC_ROM=/caminho/rom.nds cargo test --release        # prova de ida e volta com a ROM real
./analise/run_all.sh /caminho/rom.nds                  # pipeline completo de engenharia reversa
```

## Mapa do repositório

```
engine/              Rust: sonic-formats (biblioteca), sonic-mod, sonic-dump
analise/             pipeline de engenharia reversa (Python, Ghidra, emulador)
decomp/              funções do jogo reescritas em C, testadas contra o jogo
exemplos/            crate Rust mínima e didática (HERF + LZ10)
docs/                toda a documentação (abaixo)
```

## Documentação

| Documento | Para quê |
|---|---|
| [`docs/ESPIRITO.md`](docs/ESPIRITO.md) | os princípios: como e por que trabalhamos assim |
| [`docs/FERRAMENTAS.md`](docs/FERRAMENTAS.md) | **cada ferramenta**: o que faz, como usar, como funciona por dentro |
| [`docs/MODDING.md`](docs/MODDING.md) | guia de modding com receitas (vai junto em cada projeto do `sonic-mod`) |
| [`docs/ARQUITETURA.md`](docs/ARQUITETURA.md) | como o jogo e este repositório estão organizados |
| [`docs/FORMATOS.md`](docs/FORMATOS.md) | referência de todos os formatos decifrados |
| [`docs/DIARIO.md`](docs/DIARIO.md) | a história das descobertas, incluindo os erros e as correções |
| [`docs/PLANO-DECOMPILACAO.md`](docs/PLANO-DECOMPILACAO.md) | o plano da decompilação real, fase por fase |
| [`docs/hierarquia_classes.md`](docs/hierarquia_classes.md) | as 290 classes C++ do jogo |
| [`CONTRIBUTING.md`](CONTRIBUTING.md) | regras para contribuir |

## Créditos

- [ds-decomp (`dsd`)](https://github.com/AetiasHax/ds-decomp): análise de funções e disassembly
- [xoreos](https://github.com/xoreos/xoreos): documentação dos formatos Aurora e a tabela de nomes de
  coluna GDA (`engine/crates/sonic-formats/data/gda_columns_xoreos.json`, GPLv3)
- [ndspy](https://github.com/RoadrunnerWMC/ndspy), [Capstone](https://www.capstone-engine.org/),
  [Ghidra](https://ghidra-sre.org/), [py-desmume](https://github.com/SkyTemple/py-desmume)
- Inspiração: [pret/pokeplatinum](https://github.com/pret/pokeplatinum) e o
  [port de PC](https://github.com/cybervisi0n/pokeplatinum)

## Licença e aviso legal

Código sob **GPL-3.0** ([`LICENSE`](LICENSE)). Sonic Chronicles: The Dark Brotherhood é ©
SEGA / BioWare. Este é um projeto de fãs, sem afiliação com eles e sem fins comerciais. Use
apenas com uma cópia que você possua, e não distribua ROMs, assets nem material extraído.
