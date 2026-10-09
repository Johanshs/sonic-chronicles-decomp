# O som do jogo e o plano da trilha sonora

Este documento explica como o Sonic Chronicles guarda e toca música e efeitos, o que já
foi provado no emulador e o caminho para trocar ou recriar a trilha (por exemplo, com
músicas baseadas em outros jogos do Sonic). Tudo aqui foi lido da ROM YWSE; o que ainda
não foi testado está marcado como **a provar**.

Regra de sempre: **nenhum áudio vai para o Git**, nem do jogo nem de outros jogos. Só
ferramentas, documentação e metadados nossos. Os arquivos de áudio ficam na pasta do
projeto (`trilha-sonora/`), e as ROMs geradas são só para uso pessoal.

## 1. Onde fica o som

Todo o som está em dois arquivos do NitroFS:

| Arquivo | Tamanho | O que é |
|---|---|---|
| `sound_data.sdat` | 14,8 MB | O **arquivo de som** do NitroSDK (formato SDAT): músicas, efeitos, instrumentos e amostras |
| `sound_data.sadl` | 13 KB | Um cabeçalho C (`#define bgm01 0`...) com o **nome de cada item** do SDAT. Sobrou do build da BioWare e é ótimo para nós: dá nome a tudo |

Os vídeos `.vx` (Actimagine) têm som próprio, dentro do vídeo; ficam fora deste plano.

### O SDAT por dentro

O SDAT é o formato padrão do NitroSDK, usado por quase todo jogo de DS. Ele tem quatro
tipos de conteúdo, e entender a diferença entre eles é o que define o plano:

| Tipo | Analogia | Como toca | No Sonic Chronicles |
|---|---|---|---|
| **STRM** (stream) | um arquivo MP3 | áudio gravado, lido do cartão **aos poucos** enquanto toca | 10: as músicas de batalha, vitória e derrota |
| **SSEQ** (sequência) | um arquivo MIDI | uma partitura: "toque a nota tal no instrumento tal" | 16: as músicas de exploração, tema do título, fuga |
| **SBNK** (banco) | uma soundfont | diz qual amostra cada instrumento usa e em que tom | 60 |
| **SWAR** (arquivo de ondas) | uma pasta de samples | as amostras curtas (um "dó" de piano, um bumbo...) | 57 |
| **SSAR** (arquivo de sequências) | muitos MIDIs pequenos | os efeitos sonoros são sequências curtas | 1, com 392 efeitos |

Por que isso importa: **um STRM aceita qualquer gravação**. Trocar uma música de batalha
é converter um áudio e gravar no lugar. Já uma SSEQ é uma partitura: para trocar, é
preciso escrever a música nota por nota (ou converter de um MIDI) e ter instrumentos
que soem bem.

## 2. As músicas

### Batalha: 10 streams

Todos em **PCM de 8 bits, mono, 16364 Hz** (a taxa "redonda" do relógio do DS:
16756991 / 32 / 32). Para comparar: um CD é 16 bits, estéreo, 44100 Hz. Oito bits
dão um chiado de fundo constante, e 16 kHz corta os agudos. Além disso, os originais
foram masterizados muito altos: o pico bate no máximo o tempo todo (distorção por
corte). Isso explica boa parte do "som horrível".

| Nº | Nome | Duração | Repete | Onde toca |
|---|---|---|---|---|
| 0 | `victory` | 3,4 s | não | vitória |
| 1 | `battle_1` | 61,7 s | sim | **a provar** (provável: batalhas do Ato 1) |
| 2 | `battle_boss_1` | 82,3 s | sim | chefes **a provar** |
| 3 | `you_lose` | 2,2 s | não | derrota |
| 4 | `battle02` | 56,5 s | sim | **a provar** |
| 5 | `battle03` | 56,5 s | sim | **batalhas comuns em Nocturne** (provado, ver §5) |
| 6 | `battle04` | 83,0 s | sim | **a provar** |
| 7 | `ix_final_boss` | 169,4 s | sim | chefe final (pelo nome) |
| 8 | `ix_mini_boss` | 56,5 s | sim | **a provar** |
| 9 | `mini_boss` | 56,5 s | sim | **a provar** |

Cada stream é um bloco só com o áudio inteiro, em 1 canal. O tocador de streams do
SDAT (`PLAYER_STRM`) reserva **um canal de hardware só (o 6)**: por isso tudo é mono.

### Exploração: 16 sequências

A tabela `areas.gda` diz o que toca em cada área. Colunas `AreaSoundType` = 0 e
`AreaSound` = número da sequência:

| Sequência | Área |
|---|---|
| `bgm01` | Green Hill Zone |
| `bgm02` | Central City |
| `bgm03` | Mystic Ruins |
| `bgm04` | Blue Ridge Zone |
| `bgm05` | Metropolis |
| `bgm06` | Angel Island |
| `bgm07` | Metropolis Ground Zero |
| `bgm08` | Kron Colony |
| `bgm09` | N'rrgal Colony |
| `bgm10` | Zoah Colony |
| `bgm11` | Voxai Colony Beta |
| `bgm12` | Voxai Colony Alpha |
| `bgm13` | Nocturne |
| `f_good` / `f_lose` | fim da fuga (ganhou / perdeu) |
| `main_theme` | tema (provavelmente o título) |

Cada `bgmNN` tem um banco próprio (`bgmusicNN`) e um arquivo de ondas próprio, com
**4 a 17 amostras** e 10 a 42 KB, quase tudo em ADPCM a 16 kHz. A `bgm01` tem 6
trilhas e 6 instrumentos. É pouco: uma música de Sonic Rush ou Sonic Colors DS usa
bancos bem maiores. Isso explica o som "pobre" das músicas de exploração.

### Interiores: amostras longas

Os interiores (lojas, cavernas, bases) usam `AreaSoundType` = 1: em vez de uma
sequência, tocam um **efeito** do SSAR (`interior_s1_i01`...) cujo banco
(`AreaSoundBank`) tem uma amostra só, longa, em loop: 128 KB de ADPCM a 16 kHz, uns
16 segundos. É o mais perto de um "stream" que existe fora da batalha.

## 3. Os efeitos sonoros

São 392 sequências curtas no `SEQARC_000`, em 8 bancos: `sfx_gui` (interface),
`sfx_xpl` (exploração), `sfx_cbt` e `sfx_cbt_act1` a `act5` (combate). As amostras são
quase todas ADPCM de 16 a 32 kHz. Os nomes vêm do `.sadl`: `ringpick` (pegar anel),
`jumpsnd`, `dash`, `combat_hit01`..`75`, `combat_vox01`..`13` (vozes), `chao_hatch`...

Quem escolhe qual efeito toca são **tabelas**, que o `sonic-mod` já edita:

| Tabela | Coluna | Uso |
|---|---|---|
| `combatsounds.gda` | `Bank1`..`Bank5` | os sons de combate (uma coluna por conjunto de combate) |
| `MovementSounds.gda` | `SoundID` | passos, pulos |
| `PlaceableStates.gda` | `Sound`, `SoundLooping` | objetos do cenário |
| `FleeObstacles.gda` | `CollisionSound` | obstáculos da fuga |
| `aN_sM_ex_la_soundmap.gda` | `Sound`, `Looping`, `BaseVolume` | sons de ambiente de cada área (cachoeira, pássaros) |
| `areas.gda` | `SoundMap`, `SoundMapBank`, `AreaSound*` | o que toca em cada área |

Ou seja, há dois jeitos de mexer num efeito: **trocar a amostra** (o som em si) ou
**trocar o número na tabela** (usar outro efeito que já existe). O segundo não precisa
de ferramenta nova.

## 4. A ferramenta: `analise/tools/som.py`

```
python3 analise/tools/som.py listar  rom.nds
python3 analise/tools/som.py extrair rom.nds pasta
python3 analise/tools/som.py trocar  rom.nds battle03 musica.mp3 saida.nds [--formato pcm16 --taxa 32728] [--loop 12.5]
```

- `listar` mostra streams e sequências.
- `extrair` salva os 10 streams em WAV (para ouvir e comparar).
- `trocar` converte qualquer áudio (via ffmpeg) para o formato do stream e grava na ROM.
  Detalhes que importam:
  - **Normaliza o volume** para a mesma intensidade média das músicas originais, para a
    música nova não ficar muito mais alta ou baixa que o resto do jogo.
  - **Taxa válida do DS:** o hardware só toca taxas = 16756991 / 32 / inteiro. A
    ferramenta arredonda (32000 vira 32728).
  - **Grava no lugar quando cabe:** se o stream novo é menor que o antigo, nenhum outro
    arquivo do SDAT muda de posição. Isso é mais seguro e permite testar a partir de um
    savestate feito na ROM original (o jogo guarda a tabela de arquivos do SDAT na RAM).
    Se não cabe, o SDAT é remontado (com o ndspy, que remonta o original byte a byte
    idêntico) e, se preciso, vai para o fim do cartucho, com a mesma regra do
    `sonic-mod pack`.
  - **Confere:** reabre a ROM gerada e lê o stream de volta.
  - `--loop S` diz onde a repetição recomeça. Muitas músicas têm uma introdução que não
    se repete: o loop deve começar depois dela.

## 5. O que já foi provado (emulador)

Em 09/10/2026, no py-desmume, com o seu save (slot do Capítulo 10, Nocturne):

1. **Gravar o som do emulador.** A biblioteca do DeSmuME exporta `WAV_Begin`, que grava
   a saída do chip de som sincronizada com a emulação. Assim dá para **ouvir** o
   resultado e medir com números, sem depender de ninguém escutar.
2. **Qual stream toca em Nocturne.** Troquei cada um dos 10 streams por um tom puro de
   frequência diferente (300 Hz no 0, 400 Hz no 1... 1200 Hz no 9), andei pelo mapa até
   uma batalha e procurei os tons na gravação: tocou o de 800 Hz, o **stream 5
   (`battle03`)**. A mesma técnica descobre os outros: basta chegar numa batalha de
   cada tipo.
3. **A troca funciona, nos dois formatos.** Uma música de teste original (12,8 s, feita
   em código, não é de nenhum jogo) foi gravada nos 8 streams de batalha que repetem,
   em duas ROMs:
   - **A:** PCM 8 bits a 16364 Hz, o formato original;
   - **B:** PCM 16 bits a 32728 Hz, o dobro da taxa e 256 vezes mais níveis de volume.

   Do mesmo savestate (logo antes de uma batalha contra 4 Nocturne Decurion), as duas
   tocaram a música nova: a gravação bate com a música de teste com correlação 0,98
   (1,0 = idêntica; a original dá 0,10) e ela **repete** a cada 12,8 s. A batalha
   seguiu normal.

**A provar no DS de verdade:** se a ROM B toca sem engasgar no R4. Ela lê 64 KB/s do
cartão (4 vezes a original); o cartão aguenta, mas no R4 a leitura passa pelo SD.
Lembre do Sonic Boom: o emulador aprovou e o DS reprovou.

## 6. O plano

A ideia geral: **cada tipo de som tem o seu caminho**, do mais barato para o mais caro.

### Fase 1: músicas de batalha (pronta para usar)

O caminho mais fiel: a gravação da música que você quer (da trilha de outro Sonic que
você tem) vira o stream.

1. Descobrir onde toca cada um dos 10 streams (técnica dos tons, §5). Falta: 1, 2, 4,
   6, 8, 9.
2. Para cada stream, escolher a música e o ponto de loop (onde a música "dá a volta").
   Um editor como o Audacity mostra o ponto; a ferramenta recebe `--loop` em segundos.
3. Gerar a ROM, testar no DS.
4. Decidir o formato pelo teste no hardware: PCM16 a 32 kHz se não engasgar; senão
   PCM8 a 32 kHz (o dobro da taxa e o mesmo tamanho por segundo que o PCM16 a 16 kHz).

Espaço: em PCM16 a 32728 Hz, um minuto ocupa 3,9 MB. Dez músicas de 1,5 min dão uns
60 MB; a ROM vai de 128 para 256 MB, o que você já disse que não é problema (e a ROM
do conteúdo novo, de 256 MB, já abriu no seu DS).

**Estéreo (a provar):** exige ensinar o tocador de streams a usar 2 canais de
hardware, mexendo na definição `PLAYER_STRM` do SDAT. É um passo separado e pequeno, mas
só vale depois que o mono 16 bits passar no DS.

### Fase 2: efeitos sonoros

1. **Ouvir e listar** os que incomodam. Próximo passo de ferramenta: `som.py extrair`
   também salvar as amostras dos efeitos em WAV (falta um decodificador de ADPCM do DS,
   que é curto).
2. **Trocar o número na tabela** quando já existe um som melhor no jogo (via `sonic-mod`).
3. **Trocar a amostra** quando o som em si é ruim: um WAV vira ADPCM (ou PCM16) dentro do
   arquivo de ondas. Precisa de um codificador ADPCM do DS (também curto) e de cuidado
   com a memória: as amostras de efeitos ficam na RAM de som enquanto a área está
   carregada (**a medir**: quanto sobra no heap de som).

### Fase 3: músicas de exploração

Aqui há três caminhos. Do melhor resultado para o mais barato:

| Caminho | Como | Prós | Contras |
|---|---|---|---|
| **A. Stream na exploração** | um enxerto de código (como o do painel) faz a área tocar um STRM em vez da SSEQ | qualquer gravação, igual à batalha | precisa achar a função que toca a música da área e o ponto de troca; streams competem com o carregamento da área pelo cartão (**a provar**) |
| **B. MIDI para SSEQ** | um arranjo em MIDI vira SSEQ, com instrumentos novos (amostras de uma soundfont) num banco novo | é o jeito "nativo" do DS; ocupa pouco | precisa de um conversor MIDI → SSEQ e de montar bancos; o resultado depende do arranjo e dos instrumentos |
| **C. Amostra longa** | como nos interiores: uma sequência que toca uma amostra longa em loop | sem código novo | a amostra fica inteira na RAM: uns 16 s por música, no máximo (**a medir**) |

Recomendação: começar pelo **A**, porque reaproveita tudo da Fase 1 e resolve
"baseadas nas trilhas de outros jogos" com a fidelidade máxima. O primeiro passo é
investigar no código quem chama a sequência da área (as colunas `AreaSound` de
`areas.gda` levam até ela) e quem chama o stream da batalha. O **B** fica como plano
reserva e para músicas curtas (tema do título, fim da fuga).

## 7. O que ainda não sabemos

- Onde tocam os streams 1, 2, 4, 6, 8 e 9.
- Se PCM16 a 32 kHz toca sem engasgo no R4 e no 3DS.
- O tamanho do heap de som (limite para amostras maiores).
- A função do código que escolhe a música da área e a da batalha.
