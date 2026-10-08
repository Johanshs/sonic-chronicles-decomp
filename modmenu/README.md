# Painel de controle (mod menu)

Código C nosso que roda **dentro** do Sonic Chronicles (EUA, YWSE): aperta-se
L + R + SELECT, o jogo pausa e uma das telas vira um painel para ler e mudar valores do
jogo ao vivo. O plano completo está em [`docs/PLANO-MOD-MENU.md`](../docs/PLANO-MOD-MENU.md)
(caminho B).

**Situação (08/10/2026), versão 0.8:**
- **Funciona dentro do jogo, no emulador**: conferido na exploração (num jogo novo e no
  save do Capítulo 10), num diálogo, na tela de perfil e **numa batalha** (ver "Como foi
  testado").
- **Testado num DS de verdade (v0.5)**: no R4i-SDHC, todas as páginas funcionaram (o
  usuário só evitou mudar as regras de combate). As versões 0.6 a 0.8 ainda não foram
  ao DS.
- Páginas: as **74 regras de combate**, a dificuldade dinâmica, os **anéis da carteira**
  e o **grupo inteiro**: a lista de todos os personagens que já entraram (11 no fim do
  jogo), com nome e HP; escolhendo um, os atributos dele (HP, PP, Speed, Attack, Defense,
  Power, Grit, Luck).
- **Batalha**: os inimigos da luta atual (nome, HP e atributos, editáveis) e três
  ações rápidas: curar o grupo (HP e PP cheios), deixar os inimigos com HP 1 e
  **nocautear os inimigos**. Nocautear usa a função do próprio jogo, então a batalha
  acaba como uma vitória normal: tela VICTORY, XP, item e subida de nível.
- **Itens**: o inventário com o nome de cada item (o jogo dá o nome), dar qualquer item
  pelo número (a linha de `Items.gda`) usando a função do próprio jogo, **tirar** 1
  unidade de uma pilha (também pela função do jogo; a última unidade some com a pilha)
  e mudar a quantidade de cada pilha.
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
jogo/painel.ld                  onde o painel mora na memória do jogo (0x023D8000)
teste/                          a ROM de teste: um "jogo de mentira" que chama o painel
ferramentas/enxertar.py         põe o painel numa cópia da ROM (o `sonic-mod menu` faz o mesmo)
ferramentas/testar.py           testa o painel na ROM de teste (26 checagens)
ferramentas/testar_no_jogo.py   testa o painel dentro do jogo enxertado (15 checagens)
ferramentas/contar_funcoes.py   conta quantas vezes cada função roda (como o gancho foi achado)
ferramentas/mknds.py            monta o .nds da ROM de teste
```

## Usar

**Sem compilar nada** (fase B8): o pacote de release das ferramentas traz o `sonic-mod`
e o painel já compilado (`painel_jogo.elf`) lado a lado.

```bash
sonic-mod menu "Sonic Chronicles.nds" sonic_painel.nds    # a original não muda
```

**Compilando:** precisa de `clang` e `ld.lld` (LLVM 14 ou mais novo) e `python3`. Para
os testes, `pip install py-desmume`. Não precisa de devkitARM: o clang já gera código
para o ARM9.

```bash
cd modmenu
make enxertar ROM="Sonic Chronicles.nds" SAIDA=sonic_painel.nds   # a original não muda
# ou, com o sonic-mod do repositório e o painel que o make gerou:
sonic-mod menu "Sonic Chronicles.nds" sonic_painel.nds build/painel_jogo.elf
```

O `sonic-mod menu` (Rust, `engine/crates/sonic-mod/src/menu.rs`) e o `enxertar.py`
fazem o mesmo enxerto. Conferido: com a mesma ROM e o mesmo painel, as duas saídas são
idênticas byte a byte.

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
make testar                        # ROM de teste, sem precisar do jogo (26 checagens)
make testar-jogo ROM=rom.nds       # enxerta e testa dentro do jogo (15 checagens)
```

## Como funciona

1. **Onde o código mora.** O painel ocupa ~10 KB de código e ~6 KB de variáveis. Ele
   vira um bloco novo de *autoload*: a lista que o início do programa (crt0 do NitroSDK)
   percorre para copiar blocos do ARM9 para a memória (o jogo já a usa para o ITCM e o
   DTCM). O heap do jogo vai de 0x021B9500 a 0x023E0000. O bloco vai para os últimos
   32 KB (0x023D8000), e o fim do heap (`OS_GetInitArenaHi`, literal em 0x020d8c9c)
   baixa para 0x023D8000. Assim o jogo nunca usa a nossa memória. É a técnica do
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
     e depois do último vem lixo, então o painel usa o "quantos" da lista (8 bytes
     antes do vetor, em `0x02160B20`) e confere cada posição;
   - **inimigos**: a lista da batalha atual fica em `0x02160AF8` (quantos em
     `0x02160AF0`; 0 fora da batalha), com `CGameCreature` (vtable `0x020F5D20`) no
     mesmo formato de atributos e nome. As duas listas são `CGameObjectStorageList` do
     jogo: {vtable, tipo, −1, quantos, capacidade, vetor};
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
9. **O nome do item também vem do jogo.** O painel não guarda nenhum texto do jogo: ele
   chama as funções que montam a mensagem "você ganhou um item" (0x020c2cfc monta as
   informações do item, 0x0201cad0 busca o nome no texto do jogo, 0x020c2d48 libera) e
   copia as letras. Como buscar o texto pode ler o cartão, ele guarda os últimos 16
   nomes.
10. **Nocautear também é com o jogo.** "Nocautear inimigos" chama a função que todo
   golpe usa para mudar um atributo (0x02007e60), pedindo HP 0. Depois de mudar o
   número, ela confere os limites da tabela de atributos e avisa a criatura que o HP
   chegou ao mínimo; é esse aviso que faz o nocaute (atributo 36 = 2, efeitos limpos).
   Com todos os inimigos no chão, a própria batalha percebe e termina em vitória.
11. **Tirar um item também é com o jogo.** A numa pilha chama a função que o combate
   usa quando um item é gasto (0x0202dacc: inventário, posição da pilha). Com mais de 1
   unidade ela desconta 1; com 1, apaga o item e, se ele for de história, desliga a
   marca que diz que o grupo o tem.

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
- **Inimigos e ações rápidas** (a mesma batalha): a página lista os 4 Nocturne
  Decurion com o HP certo (340, 293, 305, 340). "Curar o grupo" encheu HP e PP, e a
  tela da batalha mostrou os números cheios. "Inimigos com HP 1" funcionou, e o golpe
  que acertou derrubou o inimigo ("KO!"). **Erro meu que o teste pegou:** havia uma
  ação "HP 0 (nocaute)". Com HP 0 os inimigos continuaram lutando (e até se curaram),
  porque o nocaute do jogo não é só o HP. Num inimigo nocauteado de verdade, o atributo
  36 vale 2, os atributos 20 a 25 ficam zerados e o objeto solta dois ponteiros. A ação
  saiu do painel (e voltou na v0.7, do jeito certo: veja abaixo).
- **Tirar itens** (v0.8): num jogo novo (teste automático), dar 2 POW Candy e tirar 2
  deixa o inventário sem POW Candy; dar de novo funciona. No Capítulo 10, tirar 1 Med
  Emitter (87 → 86) e o único Spooky Charm: o Inventário do jogo mostrou "Med Emitter
  (86)", e depois de salvar, reiniciar e carregar, o inventário era o mesmo.
- **A lista do inventário fica com buracos.** Quando a última unidade sai, a função do
  jogo apaga o item e põe 0 na posição, sem encolher a lista (a lista do Capítulo 10
  ficou com 61 posições e 60 pilhas, e continuou assim depois de salvar e carregar). O
  próprio jogo faz isso ao usar um item na batalha, e a tela de Inventário lida bem. O
  painel passou a pular as posições vazias; na primeira versão do teste, o script lia
  a posição vazia como se fosse um item e via lixo.
- **Nocautear pela função do jogo** (v0.7, a mesma batalha, ROM ligada do zero):
  "Nocautear inimigos" levou os 4 Nocturne Decurion a HP 0 com o atributo 36 = 2 (o
  nocaute de verdade). A batalha acabou sozinha: tela **VICTORY** (nota A, 1 rodada),
  depois a recompensa (Med Emitter 87 → 88 no inventário, 8000 de XP) e a tela de
  **subida de nível** da Rouge. Sem dar um golpe. Repetido em mais 5 encontros (o robô
  andando por caminhos diferentes, inimigos com HP cheio ou já ferido): os 5 terminaram
  em VICTORY. Todos foram contra 4 Nocturne Decurion, o inimigo daquela área.
- **Itens** (Capítulo 10): dar o item 3 duas vezes criou uma pilha nova e depois somou 1
  nela; o Inventário do jogo, em "Consumables", mostrou **POW Candy (2)**. As outras
  quantidades do painel batem com as da tela (Med Emitter 87, Health Root 4, Refresher
  Wave 90). Num jogo novo, com o inventário vazio, também funciona (teste automático).
  Os nomes que o painel mostra batem com os do Inventário (item 5 Health Root, 6 Med
  Emitter, 8 POW Drink, 9 Refresher Wave, 10 Revival Ring, 11 Ring of Life).
- **O item sobrevive a salvar e carregar** (critério da fase B5): depois de dar um POW
  Candy, salvei pelo menu do jogo no slot do Capítulo 10 (no save do emulador, não no
  seu arquivo), reiniciei o emulador e carreguei o slot: o POW Candy continuava lá, e o
  inventário tinha as mesmas 62 pilhas.

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

- **Como o nocaute foi achado** (v0.7). Vigiando no emulador quem escreve o HP de um
  inimigo durante um golpe, a pilha de chamadas sempre termina na mesma função,
  0x02007e60, chamada por `Combat_ApplyDamage` → `EffectList_Add` →
  `EffectFn_ModifyAttribute`. Ela muda o atributo e depois confere os limites da tabela
  de atributos; com o HP no mínimo, avisa a criatura, e é esse aviso que nocauteia. O
  painel passou a chamar essa função em vez de escrever o número.
- **Erro meu na primeira tentativa:** chamei 0x02007e60 com 4 argumentos, como o
  descompilador mostrava. O HP foi a 0, mas ninguém caiu. No assembly, a função lê um
  **quinto argumento na pilha** (`ldr r0, [sp, #0x28]`) e só avisa a criatura se ele for
  0; a minha chamada deixava lixo ali. Passando 0, os 4 inimigos caíram. Lição: o
  descompilador pode perder argumentos que vêm pela pilha; conferir no assembly.

## Limites conhecidos

- **No DS real, só a v0.5 foi testada** (funcionou).
- "Nocautear inimigos" foi conferido em 6 encontros, mas todos contra o mesmo inimigo
  (4 Nocturne Decurion, Capítulo 10). Chefes podem ter regras próprias de fim de luta (cenas, fases) que o painel não
  conhece; se uma luta de chefe travar, use "inimigos com HP 1" e dê um golpe.
- **Itens:** prefira consumíveis, equipamentos e Chao. Dar itens de história
  (esmeraldas, objetos de missão) ou os "envelopes" de itens aleatórios (258–276, 287)
  pode confundir o jogo. Os nomes aparecem cortados em 14 letras. **Não tire itens de
  história**: tirar o último desliga a marca da história que diz que o grupo o tem, e
  uma missão pode ficar sem saída. A página não pede confirmação: cada A tira 1.
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
