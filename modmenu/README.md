# Painel de controle (mod menu)

Código C nosso que roda **dentro** do Sonic Chronicles (EUA, YWSE): aperta-se
L + R + SELECT, o jogo pausa e uma das telas vira um painel para ler e mudar valores do
jogo ao vivo. O plano completo está em [`docs/PLANO-MOD-MENU.md`](../docs/PLANO-MOD-MENU.md)
(caminho B).

**Situação (08/10/2026), versão 0.2:**
- **Funciona dentro do jogo, no emulador**: conferido na exploração, num diálogo e na
  tela de perfil (ver "Como foi testado").
- **Ainda não testado num DS de verdade nem numa batalha.**
- Páginas: as **74 regras de combate**, a dificuldade dinâmica, os anéis e os
  atributos dos **4 membros do grupo** (HP, PP, Speed, Attack, Defense, Power, Grit, Luck).

Nada aqui vem do jogo: o repositório só tem o nosso código e os endereços. O painel é
posto na **sua cópia** da ROM por `ferramentas/enxertar.py`.

```
include/ds.h                    registradores do DS que usamos (sem libnds, sem NitroSDK)
src/menu.c                      o painel: páginas, campos, teclado, pausa
src/console.c                   texto na tela, salvando e restaurando tudo o que toca
src/fonte.c                     fonte 8x8 de domínio público (font8x8, de Daniel Hepper)
jogo/gancho.s                   a ponte entre o laço principal do jogo e o painel
jogo/painel.ld                  onde o painel mora na memória do jogo (0x021B9500)
teste/                          a ROM de teste: um "jogo de mentira" que chama o painel
ferramentas/enxertar.py         põe o painel numa cópia da ROM
ferramentas/testar.py           testa o painel na ROM de teste (14 checagens)
ferramentas/testar_no_jogo.py   testa o painel dentro do jogo enxertado (7 checagens)
ferramentas/contar_funcoes.py   conta quantas vezes cada função roda (como o gancho foi achado)
ferramentas/mknds.py            monta o .nds da ROM de teste
```

## Usar

Precisa de `clang` e `ld.lld` (LLVM 14 ou mais novo) e `python3`. Para os testes,
`pip install py-desmume`. Não precisa de devkitARM: o clang já gera código para o ARM9.

```bash
cd modmenu
make enxertar ROM="Sonic Chronicles.nds" SAIDA=sonic_painel.nds   # a original não muda
```

No jogo: segure **L + R + SELECT**. CIMA/BAIXO escolhem, A entra, B volta, ESQUERDA/DIREITA
mudam o valor em 1, L/R em 10, START fecha. Segure o combo por meio segundo: durante um
carregamento o jogo não passa pelo gancho e o painel só abre quando o carregamento acaba.

**O painel aparece na tela do "motor B"** (um dos dois processadores de vídeo do DS). Na
exploração e no perfil, o jogo usa o motor B na tela de **cima**, então o painel aparece
em cima. Ele não escolhe a tela: usa a que o jogo deu ao motor B.

**Cuidados:** faça backup do `.sav` antes. As regras e a dificuldade não vão para o save
(o jogo recarrega as regras a cada boot), mas anéis e atributos do grupo provavelmente
vão, se você salvar depois de mudá-los.

## Testar

```bash
make testar                        # ROM de teste, sem precisar do jogo (14 checagens)
make testar-jogo ROM=rom.nds       # enxerta e testa dentro do jogo (7 checagens)
```

## Como funciona

1. **Onde o código mora.** O painel ocupa ~6 KB de código e ~5,5 KB de variáveis. Ele
   vira um bloco novo de *autoload*: a lista que o início do programa (crt0 do NitroSDK)
   percorre para copiar blocos do ARM9 para a memória (o jogo já a usa para o ITCM e o
   DTCM). O bloco vai para 0x021B9500, onde o heap do jogo começaria, e o começo do heap
   (`OS_GetInitArenaLo`, literal em 0x020d8d10) é empurrado para depois do painel. Assim
   o jogo nunca usa a nossa memória. É a técnica do NCPatcher, feita à mão em Python.
2. **O gancho.** O laço principal do jogo (`main`, 0x02000c8e) chama a leitura dos
   botões (`func_02002708`, do objeto Input) uma vez por volta. Trocamos essa chamada
   (0x02000d50) por uma chamada ao `gancho`, que chama o painel e depois a função
   original. Como o painel roda antes da leitura dos botões, o jogo não vê as teclas
   usadas no painel.
3. **Pausar** é não devolver o controle: com o painel aberto, `modmenu_quadro()` fica no
   próprio laço (espera o quadro, lê botões, desenha) e o laço do jogo espera por ele.
4. **O relógio.** O objeto Time (0x02109b60) mede o tempo real entre duas voltas do laço
   e o jogo move tudo por esse tempo. Depois de um minuto com o painel aberto, o jogo
   acharia que passou um minuto e daria um salto. O gancho grava o tick atual no Time
   quando o painel fecha, então a volta seguinte mede só uma volta normal.
5. **A tela é emprestada.** Antes de desenhar, o console guarda os registradores, a
   paleta e os 5 KB de VRAM que vai usar; ao fechar, devolve tudo.
6. **Os campos.** Cada campo é um endereço e um formato. As regras têm 5 formatos
   (inteiro, 0/1, ponto fixo ×4096 e ponto fixo dividido por 100 ou 1000); o painel
   mostra e edita o valor como está na tabela do jogo e converte ao gravar. Os membros
   do grupo são achados pela lista em 0x02160B28, conferindo cada ponteiro e a "vtable"
   (o primeiro campo de todo `CGamePlayerCreature` é 0x020F9200) antes de escrever.

## Como foi testado

- **ROM de teste** (`make testar`): abre, pausa, edita regras de vários formatos, a
  dificuldade, os anéis e um membro de um grupo de mentira; recusa escrever num membro
  vazio; e a tela volta idêntica, byte a byte, depois de 100 aberturas. Para provar que
  o teste pega erro, a restauração da paleta foi desligada de propósito uma vez: o teste
  falhou, como devia.
- **Dentro do jogo, no DeSmuME** (`make testar-jogo`): heap empurrado, gancho rodando
  uma vez por volta, painel abrindo, Sonic achado com HP 33/33 e Luck 3, Luck mudado
  para 13, relógio sem salto depois de 5 s aberto, tela devolvida ao fechar.
- **À mão, no DeSmuME:** a tela do perfil (modo bitmap, paletas estendidas) volta
  perfeita depois de fechar; os atributos do Sonic no painel batem com os do perfil
  (Spd 7, Atk 8, Def 14, Lck 3).

## Descobertas e erros pelo caminho

- **O jogo roda a 30 voltas por segundo na exploração e a 60 no diálogo.** A contagem
  de funções (`contar_funcoes.py`) mostrou isso: a leitura dos botões rodou 60 vezes em
  120 quadros num caso e 120 no outro. O gancho está no laço, então acompanha os dois.
- **O salto no tempo** foi visto antes de ser corrigido: sem o acerto do relógio, a
  primeira volta depois de 5 s de pausa mediu 0x1480 em vez de ~0x21 (160 vezes mais).
  Com o acerto, 0x20 a 0x24.
- **Um teste meu estava errado:** para comparar "com e sem o acerto do relógio",
  carreguei o mesmo savestate nas duas ROMs. O savestate guarda a RAM inteira, inclusive
  o código do painel, então as duas rodaram o mesmo código. Só ligando cada ROM do zero
  a diferença apareceu.
- **A lista do grupo muda de forma:** no começo de um jogo novo o Sonic está na posição
  0 da lista; com o save do projeto, o primeiro membro estava na posição 1. O painel
  conta os ponteiros válidos em vez de confiar na posição.
- **No perfil, um combo de 4 quadros não abriu o painel**: o jogo estava carregando e
  não passou pelo gancho nesses quadros. Com o combo segurado por mais tempo, abre.

## Limites conhecidos

- **Batalha e DS real ainda não testados.** O gancho está no laço principal, que é o
  mesmo em todos os modos, mas só um teste vai dizer.
- A ROM enxertada muda 12 bytes do ARM9 dentro da "área segura" (0x4000 a 0x7FFF da
  ROM: o gancho e a posição da lista de autoload). Emuladores e cartões com ROMs
  decifradas não conferem essa área; um cartão original conferiria.
- A rolagem da camada BG0 do motor B é só de escrita: ao fechar, volta a 0.
- X e Y não são usados: no DS só o ARM7 lê esses dois botões.
- Textos sem acento (a fonte só tem ASCII).
- Só para a versão YWSE (EUA). O `enxertar.py` confere a versão e os bytes que muda e
  recusa qualquer outra ROM.
