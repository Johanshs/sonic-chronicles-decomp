# Contexto para o Gemini

Este arquivo é para você, Gemini. O Gemini CLI o carrega sozinho quando você é aberto
dentro desta pasta. Ele diz o que é o projeto, onde você pode mexer, o que já está pronto
e **os comandos exatos** para cada tarefa. Quando um comando daqui servir, copie-o como
está, em vez de inventar outro. Se algo aqui não bater com o que você vê, pare e pergunte
ao Johans.

Escrito em 08/10/2026. Os números de PR e o estado das frentes podem ter mudado desde
então: confira com `git fetch origin` e `git branch -r` (seção 4).

---

## 1. O projeto em 5 linhas

- Jogo: **Sonic Chronicles: The Dark Brotherhood**, Nintendo DS, versão dos EUA, código
  **YWSE**. Motor Aurora da BioWare, NitroSDK 4.2.
- Objetivos: decompilação completa, cheats para cartão R4, um painel de controle (mod
  menu) dentro do jogo e **criar conteúdo novo** (itens, golpes, inimigos, textos).
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
git switch -c gemini/NOME-DO-ASSUNTO origin/dev     # ex.: gemini/inimigo-variante
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

## 5. Conteúdo novo: o que já existe e o que está em andamento

Esta é a frente mais parecida com a sua. Leia antes de começar para não refazer nada.

**Pronto e provado no emulador (PR #39, branch `claude/conteudo-novo-*`):**
- **Item novo:** linha 288 de `Items.csv`, "Chili Dog", cura 321 HP (`Item288.ITM`), à
  venda nas 5 lojas (`Store1.csv`...`Store5.csv`). Compra e cura conferidas na RAM.
- **Golpe POW novo:** linha 155 de `combo.csv`, "Sonic Boom", 3 PP, posto no `Combo7` do
  Sonic em `creatures.csv`. Aparece na lista, gasta 3 PP e o jogo calcula o dano pela linha
  155. O dano ainda não foi medido.
- Textos novos com ids `990100` em diante.

**Em andamento agora, pelo Claude (não comece o mesmo):**
- Um POW novo **com animação e efeito visual (VFX)** e **sprites novos**. A ligação
  descoberta até aqui: `combo.csv` → `animations.csv` → `AnimationEvents.csv` → `VFX.csv`.
  A função do jogo que cria cada efeito visual está em `0x0202f47c`.

**Planejado e ainda livre** (combine com o Johans qual você pega):
- uma variação de inimigo (`creatures.csv` e `squads.csv`);
- um diálogo editado;
- itens de equipamento ou Chao novos (só itens consumíveis foram testados).

**Para os seus conteúdos não colidirem com os do Claude:**
- ids de texto: use **995000 a 995999** (o Claude usa 990xxx);
- numa linha nova de tabela, use o próximo número livre do seu projeto de mod e anote no
  PR qual número usou. Se um dia os mods forem juntados, um dos dois renumera.

## 6. Comandos prontos

Nos exemplos, `ROM` é o caminho da ROM original do Johans. **Pergunte a ele onde está**;
não procure pelo disco inteiro. Os comandos são para bash (Linux, WSL ou Git Bash). No
PowerShell, as diferenças estão no fim de cada bloco.

### 6.1 Uma vez: preparar

```bash
# Rust 1.80+ (https://rustup.rs) e Python 3.10+
pip install ndspy capstone pillow py-desmume
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
| animações e efeitos | `animations.csv`, `AnimationEvents.csv`, `VFX.csv` (frente do Claude, seção 5) |
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

### 6.5 Antes de abrir o PR

```bash
cd engine && cargo fmt && cargo clippy --release && cargo test --release && cd ..
SONIC_ROM="$ROM" cargo test --release --manifest-path engine/Cargo.toml   # só se mexeu no Rust
git status            # confira: nenhum .nds, .sav, .dst, .png do jogo, nada de work/ ou modproj/
```

## 7. Commit e PR

Os commits saem com o nome do Johans, e uma linha no fim diz que foi você:

```bash
git add CAMINHO/DO/ARQUIVO                   # um por um; nunca "git add ." sem olhar o status
git -c user.name="Johanshs" -c user.email="aluno.johan@gmail.com" commit -m "Adiciona variação do inimigo X

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
