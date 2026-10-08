# Contexto para o Gemini (Antigravity)

Este arquivo é para você, o agente Gemini do Johans no Antigravity. O Antigravity e o
Gemini CLI carregam sozinhos um `GEMINI.md` na raiz da pasta aberta. Ele diz o que é o
projeto, onde você pode mexer, o que já sabemos sobre **personagens e seus assets** (a sua
frente: adicionar o **Silver**) e **os comandos exatos** para cada tarefa. Quando um
comando daqui servir, copie-o como está, em vez de inventar outro. Se algo aqui não bater
com o que você vê, pare e pergunte ao Johans.

Escrito em 08/10/2026. Os números de PR e o estado das frentes podem ter mudado desde
então: confira com `git fetch origin` e `git branch -r` (seção 4).

---

## 1. O projeto em 5 linhas

- Jogo: **Sonic Chronicles: The Dark Brotherhood**, Nintendo DS, versão dos EUA, código
  **YWSE**. Motor Aurora da BioWare, NitroSDK 4.2.
- Objetivos: decompilação completa, cheats para cartão R4, um painel de controle (mod
  menu) dentro do jogo e **criar conteúdo novo** (itens, golpes, inimigos, personagens).
- A sua frente: **adicionar o Silver**. Você já tem uma base da lógica; o que falta são
  assets fiéis ao jogo. A seção 5 diz o que o jogo usa para desenhar um personagem.
- Repositório: https://github.com/Johanshs/sonic-chronicles-decomp (GPL-3).
- Dono: **Johans** (GitHub `Johanshs`). Ele quer **aprender**: explique sempre o
  *porquê* do que fez, em português simples.
- Também trabalham aqui sessões do Claude, cada uma no seu branch. Você trabalha em
  paralelo com elas e **não mexe no trabalho delas** (seção 4).

## 2. Regras que não se negociam

1. **Nada do jogo no Git.** Nunca faça commit de ROM (`.nds`), save (`.sav`), savestate
   (`.dst`), imagens ou CSVs extraídos do jogo, assembly ou pseudo-C gerado. Isso fica em
   `work/`, `saida/`, `modproj/` (já estão no `.gitignore`). Pode entrar: código nosso,
   documentação, endereços, nomes de funções e descrições de formato.
   Antes de todo commit, rode `git status` e confira a lista de arquivos.
2. **Nada vale até ser conferido contra o jogo.** "Deve funcionar" não é resultado. Um mod
   só está pronto depois de aberto no emulador, com captura de tela ou leitura da RAM que
   prove o efeito. Se não deu para testar, escreva "não testado".
3. **Erros ficam registrados.** Hipótese errada, comando que falhou, causa achada: anote no
   seu diário (seção 8) com a evidência. Não apague o erro.
4. **Português** em documentação, comentários e mensagens de commit (verbo no imperativo:
   "Adiciona", "Corrige").
5. **Sempre numa cópia.** Nunca grave por cima da ROM original nem do save do Johans.
   Antes de sobrescrever qualquer arquivo dele, faça backup.

## 3. Mapa do repositório

```
engine/            Rust: sonic-formats (biblioteca), sonic-mod (modding), sonic-dump (extrator)
analise/tools/     Python: emulador sem janela (emu_run.py), leitores de formato, scripts de teste
decomp/            funções do jogo reescritas em C
docs/              documentação: leia MODDING.md, FERRAMENTAS.md, COMBATE.md, DIARIO.md
exemplos/          crate Rust mínima e didática
```

Documentos que valem a leitura antes de começar:

| Arquivo | O que tem |
|---|---|
| `docs/MODDING.md` | receitas: mudar atributos, renomear, item novo, golpe POW novo |
| `docs/COMBATE.md` | fórmulas de dano, golpes, status, itens, Chao |
| `docs/FERRAMENTAS.md` | cada ferramenta e como usá-la |
| `docs/FORMATOS.md` | os formatos de arquivo do jogo (HERF, GDA, TLK, NCGR...) |
| `docs/ESPIRITO.md` | por que o projeto trabalha assim |

## 4. Onde você trabalha (para não brigar com o Claude)

O fluxo do projeto: `main` é estável, `dev` é onde o trabalho entra, e cada assunto tem um
branch próprio que vira um PR para `dev`.

**Seu branch:** crie sempre a partir de `dev`, com o prefixo `gemini/`:

```bash
git fetch origin
git switch -c gemini/NOME-DO-ASSUNTO origin/dev     # ex.: gemini/silver
```

**Não toque nestes branches** (são do Claude ou já têm PR aberto). Não faça commit, merge,
rebase nem push neles:

| Branch | Frente | PR |
|---|---|---|
| `mod-menu`, `claude/registrar-teste-cheats-*` | cheats originais do R4 | #35 |
| `claude/bateria-cheats-*` | bateria de 35 cheats (pausada) | #36 |
| `claude/painel-controle-*` | painel de controle dentro do jogo | #37 |
| `claude/decomp-fase-0-*` | decompilação matching (pausada) | #38 |
| `claude/conteudo-novo-*` | conteúdo novo: item, golpe POW, POW com animação | #39 |

Para ver o estado atual: `git fetch origin && git branch -r`.

**Arquivos que vários branches estão mudando ao mesmo tempo.** Se você editar estes, o PR
vai ter conflito. Evite; se precisar, mude o mínimo e avise o Johans:
`docs/DIARIO.md`, `docs/MODDING.md`, `docs/FERRAMENTAS.md`, `README.md`,
`cheats/YWSE.txt`, `docs/PLANO-MOD-MENU.md`.
Arquivos **novos** seus não dão conflito: prefira criá-los.

## 5. A frente do Silver: como o jogo define e desenha um personagem

Tudo o que está aqui foi lido das tabelas e dos arquivos do jogo em 08/10/2026. O que foi
**conferido no emulador** está marcado; o resto é leitura ou inferência e precisa de prova.

### 5.1 O personagem nas tabelas (projeto do `sonic-mod unpack`, pasta `tabelas/test/`)

| Tabela | O que define | Shadow (exemplo) |
|---|---|---|
| `creatures.csv` | uma linha por criatura; linhas 0 a 9 são os jogáveis | `ID` 4 |
| ↳ `NameStrRef` | id do nome em `textos/en.csv` | 21782 ("Shadow") |
| ↳ `HitPoints`, `Speed`, `Attack`, `Defense`, `Power`, `Grit`, `Luck`, `NumActions` | atributos | 30, 7, 8, 18, 11, 3, 1, 3 |
| ↳ `Combo1`...`Combo10` | golpes POW (linhas de `combo.csv`) | 12 a 17 |
| ↳ `Advancement` | curva de nível (`Adv_Shadow.csv`) | `Adv_Shadow` |
| ↳ `Appearance` | linha de `appearances.csv` (o modelo 3D) | 4 |
| ↳ `ConversationPortrait`, `PortraitPalette` | retratos de diálogo e a paleta deles | `PRTL_SDW`, `PRTL_Shadow.nclr` |
| ↳ `MicroPortrait`, `Portrait`, `ExploreMicroPortrait` | retratos pequenos das telas | `PRT_TP_SDW.ncgr`, `PRT_SP_SDW.ncgr`, `PRT_TP_E_SDW.ncgr` |
| ↳ `ProfilePortraitPrefix`, `ProfilePortraitPalette` | tela de perfil | `CharPro_SDW`, `CharPro_SDW.nclr` |
| ↳ `PlayerID`, `Class` | qual jogável é | 4, 4 |
| `appearances.csv` | `Scale`, nome do modelo (coluna `col_7e7d1786`), `Skeleton` | linha 4: `Type` 4, modelo vazio, `Skeleton` 4 |
| `animations.csv` | uma linha por ação (`EX_IDLE`, `EX_WALK`, `CB_ATTACK`...); uma coluna por esqueleto; a linha 0 dá o prefixo dos arquivos | coluna do Shadow: prefixo `SHA_` |
| `party.csv` | os membros do grupo (`MemberName`, `CreatureID`) | |

Atenção: o Sonic e o Shadow jogáveis têm `Type` 4 e o nome do modelo **vazio** em
`appearances.csv`. Mesmo assim o jogo usa as texturas `GenSonN_AA.nsbtx` no Sonic (provado
no emulador, 5.3). Como o jogo escolhe o modelo do `Type` 4 ainda não sabemos. Também não
sabemos quantos personagens jogáveis o código aceita: isso está no código, não nas tabelas.

### 5.2 Os assets de um personagem

Os personagens **não são sprites**: são **modelos 3D** do NitroSystem. Os arquivos do
Shadow, como o `sonic-dump` os extrai em `saida/herf/test/`:

| O quê | Arquivos do Shadow | Formato | Temos ferramenta? |
|---|---|---|---|
| modelo (forma e esqueleto) | `GenSha_AA.nsbmd` | `BMD0` | **não** |
| texturas | `GenSha_AA.nsbtx` | 3 texturas de 256 cores (64×64, 32×32, 32×32) + 3 paletas | **sim**: `analise/tools/nsbtx.py` |
| animações de batalha | `SHA_CB_*.nsbca`, `Sha_CB_Block*.nsbca` | `BCA0` | **não** |
| animações de exploração | `SHA_EX_*.nsbca` (Idle, Walk, Run, Jump, Fall...) | `BCA0` | **não** |
| retratos de diálogo | `PRTL_SDW<emoção>_0`...`_3.NCGR` (`def`, `gen`, `mad`, `smg`) + `PRTL_Shadow.NCLR` | 4 peças de 64×64 a 256 cores (montadas em 2×2) | ler: sim (`sonic-dump` gera PNG); **gravar: não** |
| retratos pequenos | `PRT_TP_SDW`, `PRT_SP_SDW`, `PRT_MP_SDW`, `PRT_TP_E_SDW`, `PRT_TP_M_SDW` (`.NCGR`) | NCGR | ler: sim; gravar: não |
| tela de perfil | `CharPro_SDW0`...`5.NCGR` + `CharPro_SDW.NCLR` | NCGR/NCLR | ler: sim; gravar: não |
| efeitos dos golpes | `FX_SHASON_Atom.*`, `FX_SHASON_Nuke.*`, `FX_ShadBeam.nsbmd`, `FX_ShadTele.nsbmd` | modelos 3D de efeito | é a frente do Claude (5.5) |

Para ver as texturas: `python3 analise/tools/nsbtx.py png saida/herf/test/GenSha_AA.nsbtx work/tex_shadow`.
A de 64×64 tem o rosto e as penas; as de 32×32, as luvas e os sapatos.

### 5.3 O que já foi provado no emulador

Trocando **só as paletas** de `GenSonN_AA.nsbtx` (azul → verde) com o `nsbtx.py`, e
gerando a ROM com o `sonic-mod pack`, o Sonic aparece **verde** na exploração (save do
Capítulo 10). Captura antes e depois: `textura-recolorida-sonic.png` (o Johans tem o
arquivo). Ou seja: o caminho "exportar a paleta → editar → importar → `pack`" funciona e o
jogo usa a textura nova.

### 5.4 Caminho recomendado para o Silver, do mais seguro ao mais difícil

**Etapa 1: Silver no lugar do Shadow (só dados; tudo já dá para fazer e conferir).**
O Shadow é o personagem com o corpo mais parecido. Nesta etapa o Silver substitui o
Shadow em todo o jogo, inclusive nas cenas da história; é um primeiro passo, não o fim.
1. Recolorir as 3 paletas de `GenSha_AA.nsbtx`: preto → branco/cinza claro, listras
   vermelhas → turquesa (comandos na seção 6.6).
2. Nome: em `textos/en.csv`, troque `21782,Shadow` por `21782,Silver` (e em `fr`, `de`, `es`,
   `it`). Esse é o nome do personagem; as falas dos diálogos citam "Shadow" em outros textos.
3. Atributos e golpes: a linha `ID` 4 de `creatures.csv`.
4. Limite: a **forma** das penas continua a do Shadow, porque ela está no `.nsbmd`.

**Etapa 2: as ferramentas que faltam (bom trabalho para você).** Cada uma precisa de prova
de ida e volta: converter um arquivo original e voltar tem que dar **os mesmos bytes**.
- PNG → textura do `.nsbtx` (mesmo tamanho, 256 cores), para **redesenhar** e não só
  recolorir. Prova: `nsbtx.py png` de uma textura original, converter de volta, comparar.
- PNG → NCGR + NCLR, para os retratos do Silver. O leitor já existe em Rust
  (`engine/crates/sonic-formats/src/nitro.rs`); falta o escritor. Prova: `sonic-dump` de um
  retrato original, converter o PNG de volta, comparar com o original.

**Etapa 3: o Silver como personagem a mais (sem tirar o Shadow). Ninguém testou ainda.**
Ideia a provar: copiar `GenSha_AA.nsbmd` e o `.nsbtx` recolorido com nomes novos
(ex.: `GenSil_AA.nsbmd`, `GenSil_AA.nsbtx`) em `arquivos/test/` (o `pack` **adiciona**
arquivos de nome novo), criar uma linha em `appearances.csv` com esse modelo e o mesmo
`Skeleton` de uma aparência que já usa `GenSha_AA` (a linha 68 usa o esqueleto 58, cujo
prefixo de animação também é `SHA_`), e uma linha nova em `creatures.csv`. Riscos: os nomes
das texturas **dentro** do `.nsbtx` (`GENSha_AA_1`...) talvez precisem bater com o `.nsbmd`;
e o código pode limitar o número de jogáveis. Teste um passo de cada vez.

**Etapa 4: forma e animações próprias.** Penas do Silver e a pose da psicocinese exigem
editar o `.nsbmd` e criar `.nsbca`. Não temos leitor nem escritor desses formatos. Converse
com o Johans antes de começar; é um projeto grande por si só.

### 5.5 A outra frente de conteúdo novo (do Claude): não refaça, não mexa

- **Pronto (PR #39):** item 288 "Chili Dog" nas lojas e golpe POW 155 "Sonic Boom" no Sonic.
  Textos novos com ids `990100` em diante.
- **Em andamento agora:** um POW novo com animação, efeito visual (VFX) e sprites novos. A
  ligação já achada: `combo.csv` → `animations.csv` → `AnimationEvents.csv` → `VFX.csv`; a
  função que cria cada efeito está em `0x0202f47c`. Quando esse PR sair, ele vai dizer como
  fazer o efeito de um golpe; use isso para os golpes do Silver em vez de descobrir de novo.
- **Para não colidir:** use ids de texto de **995000 a 995999** (o Claude usa 990xxx). Numa
  linha nova de tabela, use o próximo número livre e anote no PR qual número usou.

## 6. Comandos prontos

Nos exemplos, `ROM` é o caminho da ROM original do Johans. **Pergunte a ele onde está**;
não procure pelo disco inteiro. Os comandos são para bash (Linux, WSL ou Git Bash). No
PowerShell, as diferenças estão no fim de cada bloco.

### 6.1 Uma vez: preparar

```bash
# Rust 1.80+ (https://rustup.rs) e Python 3.10+
pip install ndspy capstone pillow py-desmume      # pillow também serve ao nsbtx.py
cd engine && cargo build --release && cd ..
# os programas ficam em engine/target/release/sonic-mod e engine/target/release/sonic-dump
```

Sem compilar: baixe `sonic-tools-windows.zip` em
https://github.com/Johanshs/sonic-chronicles-decomp/releases e use `sonic-mod.exe`.

### 6.2 Fazer um mod (o ciclo inteiro)

```bash
ROM="/caminho/para/Sonic Chronicles.nds"          # pergunte ao Johans
SM=engine/target/release/sonic-mod

$SM unpack "$ROM" modproj/meu_mod                  # cria as planilhas (fica fora do Git)
# edite modproj/meu_mod/tabelas/test/*.csv e modproj/meu_mod/textos/en.csv
$SM pack "$ROM" modproj/meu_mod work/meu_mod.nds   # gera a ROM modificada
```

O `pack` mostra o que mudou (ex.: `textos en: 1 alterados, 0 novos`). Se disser
`nada mudou em relação à ROM original`, a sua edição não foi salva no CSV.

Conferido em 08/10/2026: `unpack` cria 229 planilhas, 370 arquivos de texto e 5 idiomas
em ~4 s; trocar `15877,Health Seed` em `textos/en.csv` e rodar `pack` regrava só o
`strings.tlk`.

PowerShell: `$ROM = "C:\caminho\Sonic Chronicles.nds"` e
`.\sonic-mod.exe unpack $ROM modproj\meu_mod`.

### 6.3 Onde fica cada coisa nas planilhas

| Quero mudar | Arquivo em `modproj/meu_mod/` |
|---|---|
| itens | `tabelas/test/Items.csv` + efeitos em `arquivos/test/ItemN.ITM` |
| lojas | `tabelas/test/Store1.csv` ... `Store5.csv` (colunas: ID do item, compra, venda) |
| golpes POW | `tabelas/test/combo.csv` (`Cost`, `Damage1..3`, `NameStrRef`...) |
| personagens e inimigos | `tabelas/test/creatures.csv` (linhas 0 a 9 = jogáveis; 0 é o Sonic) |
| grupos de inimigos | `tabelas/test/squads.csv` |
| aparência (modelo 3D) | `tabelas/test/appearances.csv` |
| animações e efeitos | `animations.csv`, `AnimationEvents.csv`, `VFX.csv` (efeitos: frente do Claude, 5.5) |
| grupo | `tabelas/test/party.csv` |
| textos | `textos/en.csv` (`id,texto`), e `fr`, `de`, `es`, `it` |

Comandos úteis para olhar uma planilha sem abrir editor:

```bash
head -1 modproj/meu_mod/tabelas/test/combo.csv | tr ',' '\n' | cat -n   # nomes das colunas
tail -1 modproj/meu_mod/tabelas/test/Items.csv | cut -d, -f1           # último ID usado
grep -n '^15877,' modproj/meu_mod/textos/en.csv                        # achar um texto pelo id
```

Colunas chamadas `col_xxxxxxxx` ainda não têm nome conhecido. Não chute o significado:
descubra mudando o valor e olhando no emulador, e anote o que achou.

### 6.4 Testar no emulador (sem janela)

```bash
SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy python3 analise/tools/emu_run.py \
  work/meu_mod.nds work/capturas "w 600; s inicio; p START; w 120; t 128 96; w 60; s depois"
```

O roteiro são ações separadas por `;`: `w N` espera N quadros (60 = 1 s), `p TECLA`
aperta (A B X Y L R START SELECT UP DOWN LEFT RIGHT), `t X Y` toca a tela de baixo,
`s NOME` salva a captura das duas telas, `save ARQ`/`load ARQ` guardam e carregam o estado.
**Abra as capturas** em `work/capturas/` e olhe se o efeito aparece.

PowerShell: `$env:SDL_VIDEODRIVER="dummy"; $env:SDL_AUDIODRIVER="dummy"` antes do `python`.

Para jogar com as mãos: abra `work/meu_mod.nds` no melonDS ou no DeSmuME. Use um save
novo, ou uma cópia do save do Johans.

**O save do Johans:** o arquivo `.sav` tem 512 KB, mas o jogo só usa os primeiros 64 KB.
Para o DeSmuME carregar, corte uma **cópia** em 65536 bytes:
`head -c 65536 Sonic_Chronicles_USA.sav > work/save64k.sav`.

Scripts de prova que já existem no branch `claude/conteudo-novo-*` (leia, não altere):
`analise/tools/testar_item_loja.py` (compra e usa um item novo, conferindo a RAM) e
`analise/tools/testar_golpe.py` (mostra qual linha de `combo.gda` o jogo usou num POW).
Para ler um deles sem trocar de branch:
`git show origin/claude/conteudo-novo-uea5jk:analise/tools/testar_golpe.py`.

Dica do Johans para testar golpes POW: existe um **Chao que joga o minijogo de toque
sozinho**. Equipado no personagem, ele evita depender de acertar os anéis.

### 6.5 Extrair os assets (para olhar e para copiar)

```bash
engine/target/release/sonic-dump "$ROM" saida      # ~8 s; tudo fica em saida/ (fora do Git)
ls saida/herf/test | grep -i -E 'GenSha|^SHA_|SDW'  # os arquivos do Shadow
```

`saida/herf/test/` tem cada arquivo do pacote principal já descomprimido e com nome;
`saida/imagens/montadas/test/PRTL_SDWgen.png` é um retrato inteiro do Shadow (as 4 peças
juntas) e `saida/imagens/sprites/test/` tem cada peça e os retratos pequenos em PNG. Para trocar um arquivo do jogo, copie a
versão editada para `modproj/meu_mod/arquivos/test/` **com o mesmo nome** e rode o `pack`:
ele mostra `arquivo test/NOME (substituído)`. Um nome que não existe é **adicionado**.

### 6.6 Recolorir um personagem (a receita provada na seção 5.3)

```bash
T=analise/tools/nsbtx.py
python3 $T info     saida/herf/test/GenSha_AA.nsbtx                  # texturas e paletas
python3 $T png      saida/herf/test/GenSha_AA.nsbtx work/tex_shadow  # ver as texturas
python3 $T exportar saida/herf/test/GenSha_AA.nsbtx work/shadow.csv  # paleta,indice,r,g,b
# edite work/shadow.csv (cores de 0 a 255) e salve como work/silver.csv
python3 $T importar saida/herf/test/GenSha_AA.nsbtx work/silver.csv modproj/meu_mod/arquivos/test/GenSha_AA.nsbtx
python3 $T png      modproj/meu_mod/arquivos/test/GenSha_AA.nsbtx work/tex_silver   # confira antes do pack
engine/target/release/sonic-mod pack "$ROM" modproj/meu_mod work/silver.nds
```

Não mude as cores magenta (255, 0, 255): aparecem nas texturas como área transparente
(em `GENSha_AA_1_pl` é o índice 0). O DS guarda 32
níveis por canal, então cores muito próximas podem virar a mesma. Para ver o Shadow no
jogo, ele precisa estar no grupo. No save do Capítulo 10 do Johans o grupo é Sonic, Tails,
Omega e Rouge, e na exploração só o líder (Sonic) aparece na tela.

### 6.7 Antes de abrir o PR

```bash
cd engine && cargo fmt && cargo clippy --release && cargo test --release && cd ..
SONIC_ROM="$ROM" cargo test --release --manifest-path engine/Cargo.toml   # só se mexeu no Rust
git status            # confira: nenhum .nds, .sav, .dst, .png do jogo, nada de work/ ou modproj/
```

## 7. Commit e PR

Os commits saem com o nome do Johans, e uma linha no fim diz que foi você:

```bash
git add CAMINHO/DO/ARQUIVO                   # um por um; nunca "git add ." sem olhar o status
git -c user.name="Johanshs" -c user.email="aluno.johan@gmail.com" commit -m "Adiciona as paletas do Silver

Feito com o Gemini."
git push -u origin gemini/NOME-DO-ASSUNTO
```

Abra o PR **para `dev`** (nunca para `main`). Na descrição, em português:
- **Antes:** o que acontecia no jogo.
- **Depois:** o que acontece agora.
- **Como conferi:** o comando que rodou, a captura ou o valor lido na RAM. Se algo não foi
  testado, escreva "não testado".

## 8. Seu diário

Escreva as descobertas e os erros em **`docs/DIARIO-GEMINI.md`** (arquivo só seu, para não
dar conflito com o `docs/DIARIO.md`, que outros branches estão mudando). Cada entrada: o
que você tentou, o que aconteceu, a evidência e, se errou, por que errou. Quando o PR for
aceito, o Johans decide se as entradas passam para o `DIARIO.md`.

## 9. Não faça

- Não faça commit de nada do jogo (regra 1). Se fez sem querer, **não** dê push: avise.
- Não mexa nos branches da seção 4, não force push (`--force`) e não reescreva o histórico.
- Não grave por cima da ROM original nem do save do Johans.
- Não diga que funciona sem ter testado no emulador.
- Não invente endereço de memória, nome de coluna ou formato. Se não sabe, escreva que não
  sabe e mostre como descobriu o que sabe.
- Não instale programas além dos da seção 6.1 sem perguntar ao Johans.
- Não apague linhas de `Items.csv` ou `combo.csv`: outras tabelas apontam para elas pelo
  número. Para tirar algo do jogo, tire das lojas, recompensas ou do personagem.

## 10. Quando travar

Pare e pergunte ao Johans se: um comando falhar duas vezes do mesmo jeito; o `pack` der
erro que você não entende; o jogo travar no emulador; ou você precisar mexer num arquivo
da lista da seção 4. Mostre a ele o comando, a saída do erro e o que você já tentou.
Quando o jogo travar com um mod, volte metade da mudança e teste de novo, até achar a
linha que causa o problema.
