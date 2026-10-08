# Painel de controle (mod menu)

Código C nosso que roda **dentro** do Sonic Chronicles (EUA, YWSE): aperta-se
L + R + SELECT, o jogo pausa e uma das telas vira um painel para ler e mudar valores do
jogo ao vivo. O plano completo está em [`docs/PLANO-MOD-MENU.md`](../docs/PLANO-MOD-MENU.md)
(caminho B).

**Situação (08/10/2026), versão 0.4:**
- **Funciona dentro do jogo, no emulador**: conferido na exploração (num jogo novo e no
  save do Capítulo 10), num diálogo, na tela de perfil e **numa batalha** (ver "Como foi
  testado").
- **Ainda não testado num DS de verdade.**
- Páginas: as **74 regras de combate**, a dificuldade dinâmica, os **anéis da carteira**
  e o **grupo inteiro**: a lista de todos os personagens que já entraram (11 no fim do
  jogo), com nome e HP; escolhendo um, os atributos dele (HP, PP, Speed, Attack, Defense,
  Power, Grit, Luck).
- **Itens**: dar qualquer item pelo número (a linha de `Items.gda`), usando a função do
  próprio jogo, e mudar a quantidade de cada pilha do inventário.
- **Compatível com os cheats**: o painel mora no fim do heap do jogo, então os objetos
  do jogo ficam nos mesmos endereços da ROM original (a v0.2 os deslocava).

Nada aqui vem do jogo: o repositório só tem o nosso código e os endereços. O painel é
posto na **sua cópia** da ROM por `ferramentas/enxertar.py`.

```
include/ds.h                    registradores do DS que usamos (sem libnds, sem NitroSDK)
src/menu.c                      o painel: páginas, campos, teclado, pausa
src/console.c                   texto na tela, salvando e restaurando tudo o que toca
src/fonte.c                     fonte 8x8 de domínio público (font8x8, de Daniel Hepper)
jogo/gancho.s                   a ponte entre o laço principal do jogo e o painel
jogo/painel.ld                  onde o painel mora na memória do jogo (0x023DC000)
teste/                          a ROM de teste: um "jogo de mentira" que chama o painel
ferramentas/enxertar.py         põe o painel numa cópia da ROM
ferramentas/testar.py           testa o painel na ROM de teste (21 checagens)
ferramentas/testar_no_jogo.py   testa o painel dentro do jogo enxertado (11 checagens)
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

**Com cheats:** a partir da v0.3 os cheats do projeto e os públicos funcionam na ROM com
o painel, porque o heap fica igual ao do jogo original. **Não use a ROM da v0.2 com
cheats que escrevem em endereços do heap** (os de anéis): nela o heap estava deslocado e
um cheat de endereço fixo, como o público `022262F4`, escreveria no lugar errado.

## Testar

```bash
make testar                        # ROM de teste, sem precisar do jogo (21 checagens)
make testar-jogo ROM=rom.nds       # enxerta e testa dentro do jogo (11 checagens)
```

## Como funciona

1. **Onde o código mora.** O painel ocupa ~7 KB de código e ~5,5 KB de variáveis. Ele
   vira um bloco novo de *autoload*: a lista que o início do programa (crt0 do NitroSDK)
   percorre para copiar blocos do ARM9 para a memória (o jogo já a usa para o ITCM e o
   DTCM). O heap do jogo vai de 0x021B9500 a 0x023E0000. O bloco vai para os últimos
   16 KB (0x023DC000), e o fim do heap (`OS_GetInitArenaHi`, literal em 0x020d8c9c)
   baixa para 0x023DC000. Assim o jogo nunca usa a nossa memória. É a técnica do
   NCPatcher, feita à mão em Python.

   **Por que no fim do heap.** O jogo aloca os objetos a partir do começo do heap, um
   atrás do outro. A v0.2 punha o painel no começo e empurrava o heap 0x2EA0 bytes para
   a frente: todos os objetos mudavam de endereço, e os cheats que usam endereços do
   heap (o esquadrão em 0x022261E0, por exemplo) deixavam de valer. Tirando o espaço do
   fim, o começo fica igual e os endereços também. Conferido: num boot do zero, o
   esquadrão, a lista do grupo e o Sonic caem nos mesmos endereços da ROM original.
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
   mostra e edita o valor como está na tabela do jogo e converte ao gravar.
7. **Objetos do heap.** Os anéis e os personagens moram no heap, em endereços que
   mudam. O painel os acha por caminhos fixos e confere a "vtable" (o primeiro campo de
   todo objeto C++ do jogo diz a classe dele) antes de escrever:
   - **carteira**: a global `0x02160C18` aponta para um objeto cujo primeiro campo é o
     esquadrão (`CGamePlayerSquad`, vtable `0x020F9C08`); os anéis ficam em `+0x114`;
   - **grupo**: `0x02160B28` aponta para a lista de todos os personagens que já
     entraram (vtable `0x020F9200`); cada um tem os atributos em `+0x1C` e o nome em
     `+0x98`. As posições variam (num jogo novo o Sonic é a 0; num save carregado, a 1),
     e depois do último vem lixo, então o painel percorre 16 posições e fica só com as
     que passam na conferência;
   - **inventário**: esquadrão `+0x40` aponta para o `CGameObjectInventory` (vtable
     `0x020F93DC`); ele tem a lista de pilhas (quantas em `+0x2C`, o vetor em `+0x34`), e
     cada pilha é um `CGameItem` (vtable `0x020F6120`) com o número do item em `+0xB8`
     e a quantidade em `+0xBB`.
8. **Dar um item chamando o jogo.** Escrever bytes não basta para criar um item: o jogo
   precisa de um objeto `CGameItem` montado do jeito dele. Então o painel chama a
   **função do próprio jogo** que dá itens (`0x0202dc6c`), a mesma que as recompensas e
   o roubo da Rouge usam: ela soma 1 numa pilha do mesmo item ou cria uma nova. Os
   argumentos foram lidos no assembly de quem já a chama: (inventário, número do item,
   um vetor onde ela anota o que mexeu, marcar como novo, 1). Antes de chamar, o painel
   confere os primeiros bytes da função; se não baterem (outra versão), ele recusa.

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
- **Com o save do Capítulo 10** (o `.sav` cortado em 64 KB, como no `emu_run.py`): a
  carteira mostra 986967, o mesmo número da tela de save, e o grupo lista os 11
  personagens com os nomes certos.
- **Numa batalha** (Capítulo 10, contra 4 Nocturne Decurion, achada por um robô que anda
  ao acaso pelo mapa): o gancho roda 30 vezes por segundo também na batalha; o painel
  abre na tela de cima; baixar o HP do Sonic de 311 para 301 no painel mudou o número
  na tela da batalha; ao fechar, a batalha seguiu para o menu de ações.
- **Itens** (Capítulo 10): dar o item 3 duas vezes criou uma pilha nova e depois somou 1
  nela; o Inventário do jogo, em "Consumables", mostrou **POW Candy (2)**. As outras
  quantidades do painel batem com as da tela (Med Emitter 87, Health Root 4, Refresher
  Wave 90). Num jogo novo, com o inventário vazio, também funciona (teste automático).

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
- **Dois erros da v0.2, achados pela sessão dos cheats:** a página "Aneis" mexia em
  `0x02160EB0`, que é o contador do HUD, não a carteira; e o grupo tinha só 4 páginas,
  achando que a lista era o time da batalha, mas ela tem todos os personagens (11 no
  Capítulo 10). Lição: o jogo novo (2 personagens, carteira 0) escondia os dois; o save
  avançado mostrou.
- **A v0.2 deslocava o heap.** Ao seguir o ponteiro do cheat de anéis (`0x021D10AC`) na
  ROM com o painel, li lixo. O motivo: `0x021D10AC` não é uma global, é um endereço do
  heap, e a v0.2 empurrava o heap 0x2EA0 bytes. Daí a mudança do painel para o fim do
  heap e a busca de um caminho que não dependa do heap (`0x02160C18`).

## Limites conhecidos

- **DS real ainda não testado.**
- **Itens: só o número, sem o nome** (o nome está no texto do jogo; a lista de números
  e nomes está no [COMBATE.md](../docs/COMBATE.md#12-itens) e no `Items.gda` da sua
  cópia). Prefira consumíveis, equipamentos e Chao: dar itens de história (esmeraldas,
  objetos de missão) ou os "envelopes" de itens aleatórios (258–276, 287) pode
  confundir o jogo.
- A quantidade de uma pilha vai de 1 a 99 no painel. Que 99 é o limite do jogo é uma
  suposição (o maior número visto no save foi 98).
- O painel mostra todos os personagens, sem marcar quais 4 estão no time da batalha.
- A ROM enxertada muda 12 bytes do ARM9 dentro da "área segura" (0x4000 a 0x7FFF da
  ROM: o gancho e a posição da lista de autoload). Emuladores e cartões com ROMs
  decifradas não conferem essa área; um cartão original conferiria.
- A rolagem da camada BG0 do motor B é só de escrita: ao fechar, volta a 0.
- X e Y não são usados: no DS só o ARM7 lê esses dois botões.
- Textos sem acento (a fonte só tem ASCII).
- Só para a versão YWSE (EUA). O `enxertar.py` confere a versão e os bytes que muda e
  recusa qualquer outra ROM.
