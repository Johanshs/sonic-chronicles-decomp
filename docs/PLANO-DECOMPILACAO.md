# Plano da decompilação real

O objetivo é ter o código do jogo em C/C++ que, compilado, gere **a mesma ROM byte a
byte** (decompilação "matching"). Esse é o caminho que tornou possível o port do
Pokémon Platinum. Com isso pronto, um executável nativo de PC deixa de ser um
sonho: basta trocar a camada do hardware do DS (veja a Fase 7).

Este plano está dividido em **fases**, cada uma com **partes** de 1 a 5 dias e um
critério de "pronto" verificável. As fases 0 a 2 têm ordem obrigatória. Da 3 em
diante, as partes podem ser feitas em paralelo, e de forma incremental para sempre.

---

## Ponto de partida (o que já existe neste repositório)

| Ativo | Situação |
|---|---|
| Funções do ARM9 | 6.820 delimitadas pelo `dsd` (`work/config/` gerado por `analise/run_all.sh`) |
| Nomes | ~2.230 por RTTI (classes, métodos virtuais, construtores, destrutores) + manuais em `analise/symbols_manual.txt` |
| Classes | 290, com herança (`docs/hierarquia_classes.md`) |
| Pseudo-C | Ghidra headless (`analise/ghidra_scripts/`) para todas as funções |
| Funções já reescritas | `HashResourceName`, `CExoString::CStr`, escolha do TLK por idioma (`src/`), validadas contra o jogo |
| Formatos de dados | todos os principais lidos **e escritos** byte a byte (`engine/`) |
| Bibliotecas embutidas | NitroSDK 4.2 (`0x04027531`), NitroSystem (`NNS_Tga`, `G3D`), MSL C++ da Metrowerks (iostreams) |
| Compilador | CodeWarrior para DS, **mwccarm 2.0 sp2, `-O4,p`, Thumb, RTTI ligado, exceções desligadas** ([COMPILADOR.md](COMPILADOR.md)) |
| Build matching | ✅ ROM reconstruída idêntica (SHA-1) a partir do assembly e do C++ de `src/` ([BUILD.md](BUILD.md)) |

---

## Fase 0: build "matching" a partir do assembly (semana 1) ✅ 0.1 a 0.3

Antes de escrever qualquer C, a ROM precisa ser **reconstruída a partir das partes
desmontadas** e sair idêntica. É a rede de segurança de todo o resto.

- **0.1 Ferramentas.** Instalar `dsd`, `objdiff`, o linker `mwldarm` e um
  executor para os binários Windows da Metrowerks no Linux (`wibo` ou Wine). Os
  compiladores mwccarm não são distribuídos livremente; use os pacotes que a
  comunidade de decompilação de DS usa (o decomp.me tem os mesmos).
  **Pronto quando:** `mwccarm -version` roda. ✅ `decomp/tools/ferramentas.sh` (dsd 0.12.1,
  wibo 0.6.16, mwccarm do decomp.me); o `objdiff` foi trocado por `decomp/tools/comparar.py` por enquanto.
- **0.2 Delink.** `dsd delink` corta o ARM9 em arquivos-objeto (`.o`) por seção.
  No começo, um arquivo por região grande. **Pronto quando:** os `.o` são gerados
  sem erro. ✅
- **0.3 Linker script.** `dsd lcf` gera o `.lcf` para o `mwldarm`; ligar tudo e
  montar com `dsd rom build`. **Pronto quando:** `sha1(rom_reconstruida) == sha1(rom_original)`.
  ✅ `decomp/tools/montar_rom.sh` (o ícone do banner e o CRC da área segura precisaram de
  correção; veja [BUILD.md](BUILD.md#dois-detalhes-fora-do-código)).
- **0.4 CI.** Uma GitHub Action que roda o build, compara o SHA-1 e publica o
  progresso. A ROM não pode ir para o repositório: o CI só roda com a ROM num
  segredo, ou em uma máquina própria. **Pronto quando:** o build quebrado deixa o PR vermelho.
  🟡 parcial: sem a ROM, o CI confere o SHA-1 de cada função decompilada
  (`conferir_sem_rom.py`). O build completo no CI segue em aberto: um segredo do GitHub
  tem no máximo 48 KB e a ROM tem 128 MB.

## Fase 1: identificar o compilador e as flags (semana 2) ✅ 1.1 e 1.2

Sem o compilador certo, nenhum C sai igual ao original.

- **1.1 Candidatos.** Pelo SDK (NitroSDK 4.2, 2008), os candidatos são as versões
  mwccarm 2.0 (service packs sp1 a sp2) e 1.2. Verificar quais o decomp.me oferece
  para `nds_arm9`.
- **1.2 Teste com funções conhecidas.** Compilar `decomp/src/resource_hash.c` (função
  `0x02009b78`, 64 bytes) com cada candidato e combinação de flags (`-O4,p`/`-O4,s`,
  `-proc arm946e`, `-thumb`, `-interworking`, `-enum int`, `-char signed`...).
  Comparar com o `objdiff`. A função é Thumb, então `-thumb` deve estar ativo.
  **Pronto quando:** pelo menos 3 funções diferentes dão 100% de match com a mesma configuração.
  ✅ `CExoString::CStr`, `HashResourceName` e a remoção de item de lista (`0x0202d428`):
  todas as 2.0, `-O4,p`. Matriz completa: `decomp/tools/testar_compilador.sh`.
- **1.3 Configurações por biblioteca.** O SDK e a NitroSystem costumam ter sido
  compilados com versão e flags diferentes das do jogo. Repetir 1.2 com uma função
  de cada biblioteca. Documentar em `docs/COMPILADOR.md`.

## Fase 2: separar as bibliotecas (semanas 3 e 4)

Boa parte do ARM9 é código de biblioteca, que tem decompilações públicas e não
precisa ser reescrito do zero.

- **2.1 NitroSDK.** Usar as decompilações públicas do NitroSDK, a mesma base da
  `libntr` do port do Platinum, para identificar e nomear as funções `OS_`, `FS_`,
  `GX_`, `G3_`, `SND_`, `MI_`, `FX_`... Gerar assinaturas e aplicar com
  `dsd sig apply`. **Pronto quando:** as funções do SDK estão nomeadas e os
  arquivos `.c` delas ligam com match.
  🟡 562 funções nomeadas (`decomp/tools/nitrosdk.sh`, com o fonte de ntrtwl/NitroSDK
  4.2.30001, compilado em Thumb com a 2.0/sp1p2); 73 dos 87 arquivos já ligam a partir
  do fonte com a ROM idêntica. Faltam 14 (ITCM/DTCM, símbolos do linker, 2 que não
  batem): lista em [BUILD.md](BUILD.md#as-bibliotecas-da-nintendo-ligadas-do-fonte).
- **2.2 NitroSystem** (`NNS_G3d*`, `NNS_G2d*`, `NNS_Snd*`). Mesma abordagem.
  ✅ a região `0x020c8278`-`0x020d4394` é 100% NitroSystem 071126 (Thumb, 2.0/sp2), e os
  59 arquivos dela são ligados a partir do fonte compilado com a ROM idêntica
  (`decomp/tools/nitrosystem.sh` + `decomp/tools/ligar_bibliotecas.py`).
- **2.3 Runtime C/C++ (MSL).** `memcpy`, `__register_global_object`, exceções,
  iostreams. Em geral, ligar o `.a` original do CodeWarrior já resolve.
  🟡 as bibliotecas são as do CodeWarrior 2.0 sp2; 171 funções já têm o nome verdadeiro
  (`decomp/tools/achar_funcoes.py`). Falta ligar o `.a` no lugar do código cortado.
- **2.4 Mapa de arquivos.** Definir em `delinks.txt` os limites de cada "arquivo
  fonte" (*translation unit*). O jogo foi compilado arquivo por arquivo, e as
  classes ajudam a adivinhar a divisão (ex.: tudo de `CTlkTable` num `TlkTable.cpp`).
  **Pronto quando:** o build continua idêntico com o ARM9 dividido em TUs.

**Métrica a partir daqui:** % de bytes de código em C com match (relatório do `objdiff`).

## Fase 3: núcleo do motor Aurora (semanas 5 a 8)

A base sobre a qual todo o jogo foi construído. Começar por ela traz o máximo de
retorno, porque essas funções são chamadas em todo lugar.

| Parte | Classes / funções | Por que primeiro |
|---|---|---|
| 3.1 Strings | `CExoString` (já começado), `CResRef` | usadas em todo lugar |
| 3.2 Memória e singletons | alocador (`func_020033e8`/`func_02003438`), `Singleton<T>`, `ResourcePool<T>` | padrão repetido em centenas de funções |
| 3.3 Arquivos | `CDSFileSystem`, `CErfMan`, `CErfTable`, `FileReference`, leitura de `.small` | o formato já está 100% documentado |
| 3.4 Dados | leitores GFF4, GDA, 2DA, `CTlkTable` (o hash já foi descoberto) | já temos as especificações e os escritores |
| 3.5 Regras | `CRules`, `StatInfos`, `StatRedirect` | ponte para o modding avançado |

**Pronto quando:** cada parte compila com match e tem um teste que lê dados reais.

## Fase 4: objetos de jogo (semanas 9 a 14)

`CGameBaseComponent → CGameObject → CGameCreature / CGameItem / CGameSquad /
CGameTrigger / Placeable`, `ActionQueue`, `CGameEffect`, `InventoryData`,
`CPlotManager`. As vtables já estão mapeadas: cada slot é um método a escrever.
Ordem sugerida: `CGameObject` (base de 51 métodos) → `CGameItem` (itens, o maior
interesse para mods) → `CGameCreature` → `Placeable` / `Puzzle`.

**Destrava para modding:** entender os limites que o código impõe (quantos itens,
personagens no grupo, slots), e assim adicionar personagens jogáveis de verdade.

## Fase 5: modos de jogo e interface (semanas 15 a 22)

`GameMode` e os 16 modos (`GameModeExplore`, `GameModeCombat`,
`GameModeConversation`, `GameModeChaoGarden`, `GameModeWorldMap`...), o
`GuiManager` e o sistema de telas `.gui`. Combate é o maior e o mais interessante.
Deixá-lo para depois do Explore, que é menor.

## Fase 6: gráficos, som e o resto (semanas 23 em diante)

Renderização de cenários (o formato `.cbgt` já está decifrado), `ModelManager`
(modelos `.nsbmd`), `VisualEffect`, `CMoviePlayer` (vídeos VX), som. Termina quando
o `objdiff` marcar 100%.

## Fase 7: port para PC (em paralelo, a partir da Fase 4)

Seguindo o modelo do Platinum: o jogo continua chamando as funções do NitroSDK,
e uma camada nova as implementa no PC.

- **7.1** Compilar o C decompilado para x86-64 com Clang/GCC, com o SDK
  substituído por *stubs*. **Pronto quando:** liga, mesmo que não rode.
- **7.2** Camada de plataforma: avaliar usar a `libntr` (já traduz o 3D do DS para
  OpenGL e simula o 2D) ou escrever uma própria em Rust. A `sonic-formats` deste
  repositório já lê todos os assets e pode alimentar essa camada.
- **7.3** Entrada (mouse = tela de toque), áudio, saves.
- **Pronto quando:** `sonic-chronicles.exe` chega à tela de título.

---

## Como trabalhar numa função (o ciclo diário)

1. Escolher uma função no relatório do `objdiff` (comece pelas pequenas, com classe conhecida).
2. Ler o assembly (`work/asm/`) e o pseudo-C do Ghidra lado a lado.
3. Escrever o C/C++ no arquivo da TU certa, com nomes e tipos de verdade.
4. Compilar e comparar no `objdiff` até dar 100%. Se travar, criar um *scratch* no
   decomp.me (o `dsd objdiff --scratch` gera os links) e pedir ajuda à comunidade.
5. Atualizar `symbols.txt` e os headers (`include/`) com o que aprendeu.
6. Commit pequeno: uma função ou um grupo de funções relacionadas por PR.

## Riscos conhecidos

- **Compilador indisponível ou versão errada.** Isso bloqueia tudo a partir da
  Fase 1. Mitigação: confirmar cedo com o decomp.me; a comunidade de DS mantém
  os compiladores.
- **Código C++ com templates e exceções** é mais difícil de igualar do que C.
  Mitigação: começar pelas funções C-like do motor.
- **Questão legal.** O repositório nunca contém a ROM, os assets nem o binário. O
  build exige a ROM do próprio usuário (como no pret/pokeplatinum).

## Referências

- [ds-decomp (`dsd`)](https://github.com/AetiasHax/ds-decomp): delink, lcf, objdiff, build da ROM
- [objdiff](https://github.com/encounter/objdiff): comparação função a função e relatório de progresso
- [decomp.me](https://decomp.me): compiladores na nuvem e *scratches* compartilháveis
- [pret/pokeplatinum](https://github.com/pret/pokeplatinum) e o [port de PC](https://github.com/cybervisi0n/pokeplatinum) com a [libntr](https://github.com/cybervisi0n/libntr): o modelo seguido aqui
- [xoreos](https://github.com/xoreos/xoreos): formatos Aurora/BioWare
