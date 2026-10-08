# Referência dos formatos

Tudo little-endian. "Validado" = lido e reescrito byte a byte idêntico com a ROM real,
ou conferido contra o comportamento do jogo.

## ROM (`.nds`)
Cabeçalho padrão do DS. Usados: ARM9 em `0x20`, ARM7 em `0x30`, FNT `0x40`, FAT `0x48`,
tamanho usado `0x80`, capacidade `0x14` (128 KB << n), **CRC16 do cabeçalho** em
`0x15E` (polinômio 0xA001, início 0xFFFF, bytes `0x000..0x15D`). Arquivos alinhados
em `0x200`; o resto do cartucho é `0xFF`. ARM9 sem compressão e sem overlays;
autoload para ITCM (`0x01FF8000`, 0x6DE0 bytes) e DTCM (`0x027E0000`). *Validado.*

## HERF (pacote de recursos)
`u32 0x00F1A5C0, u32 n, n × {u32 hash, u32 tamanho, u32 offset}`. Índice **ordenado
por hash** (busca binária); dados na mesma ordem, alinhados em 4 com zeros, e o fim
também. Hash = DJB2 do nome com tabela de minúsculas e caractere **com sinal**
(função `0x02009b78`). *Validado (6 pacotes).*

**`erf.dict`** (dentro do `test.herf`): `u32 magic, u32 n, n × {u32 hash, char nome[128]}`,
ordenado por hash: os nomes oficiais de todos os recursos.

## `.small`
`u32 = tipo | tamanho << 8`. Tipo `0x00`: sem compressão. Tipo `0x10`: **LZ10** da
BIOS (flags de 8 itens, bit 1 = referência `3 + (b0>>4)` bytes a
`((b0&0xF)<<8 | b1) + 1` atrás). Ao comprimir, evite distância 1 (a rotina da
BIOS que escreve na VRAM grava 16 bits por vez). *Validado.*

## GFF V4.0 (contêiner BioWare)
`"GFF " "V4.0" plataforma tipo versão, u32 n_templates, u32 data_offset`; templates
`{label, n_campos, offset_campos, tamanho}`; campos `{u32 label, u32 tipo|flags<<16, u32 offset}`.
Flags: `0x8000` lista, `0x4000` struct, `0x2000` referência. Tipos: 0 u8, 1 s8,
2 u16, 3 s16, 4 u32, 5 s32, 6 u64, 7 s64, 8 f32, 9 f64, 10 vec3, 12 vec4, 13 quat,
14 ECString, 15 cor, 16 matriz, 17 TlkString `{id, rel}`, **18 ponto fixo 20.12
(Sonic)**, **20 string ASCII inline (Sonic)**, `0xFFFF` genérico `{tipo|flags, rel}`.
ECString: `u32 n` + texto, em 8 bits no TLK e em UTF-16 em DLG/ARE.
Usado por: TLK, GDA, DLG (`CONV`), ARE, GUI, PLO...

## TLK (textos)
Raiz → lista de `STRN {19002 id, 19003 texto}`. A lista é uma **tabela hash** com
sondagem linear (função `0x020989fc`): posição = `h(id) % n`, onde
```
u = (id << 15) - id - 1;  u = ((u >> 12) ^ u) * 5;  u = (u ^ (u >> 4)) * 0x809;  h = (u >> 16) ^ u
```
`id = 0xFFFFFFFF` é posição vazia. Textos em cp1252, com `\0` incluído no tamanho,
sem repetição, na ordem da primeira posição que os usa, alinhados em 4 com `0xFF`.
*Validado (5 idiomas).*

## GDA (tabelas)
GFF4 `G2DA`: `gtop {10002 colunas, 10003 linhas}`; coluna = `{u32 CRC32(nome.lower()
em UTF-16LE), u8 tipo, 3 × 0xFF}`; linhas de tamanho fixo (bytes livres `0xFF`).
Tipos de campo usados: 5 (s32), 0 (u8), 18 (ponto fixo), 20 por referência
(ASCII com `\0`, sem repetição, alinhado em 4 com `0xFF`). Nomes de coluna
conhecidos: 534 de 845 (tabela do xoreos). *Validado (229 tabelas).*

## 2DA (texto)
`2DA V2.0`, linha de padrão, cabeçalho e linhas separados por TAB. Usado por
`.ITM` (efeitos de itens), `.SPL` (golpes), mapas de paleta dos cenários.

## Cenários
- `.cbgt`: índice de 4096 × `{u16 tamanho, u16 offset/512}` + tiles LZ10 de
  64×64 a 8 bpp, organizados em blocos de 8×8; tiles linha a linha.
- `.pal`: paletas de 256 cores BGR555 (512 bytes); o índice 0 (magenta) é transparente.
- `.2da`: grade com `paletteNN.pal` por tile; as paletas pertencem a blocos de 2×2, numerados coluna a coluna.
- `.cdpth`: mesmo índice; tiles LZ10 de 64×64 × u16 **lineares**; `0x7FFF` = sem objeto.

*Validado visualmente (62 áreas), com a ordem escolhida pela continuidade das bordas.*

## Gráficos Nitro
NCLR (`RLCN`/`TTLP`) e NCGR (`RGCN`/`RAHC`), formatos padrão do NitroSDK. Retratos
e ícones vêm em 4 peças 64×64 (`_0`..`_3`, em 2×2). Paleta de cada imagem: struct
`IMG` das telas `.gui` (60004 = ncgr, 60015 = nclr) ou linhas de GDA.

## Modelos 3D (`.nsbmd`, `.nsbtx`, `.nsbca`)
Os personagens são **modelos 3D** do NitroSystem, não sprites. Para cada um (ex.: Shadow):
- `GenSha_AA.nsbmd` (`BMD0`): geometria e esqueleto. Ainda sem leitor nosso.
- `GenSha_AA.nsbtx` (`BTX0`/`TEX0`): as texturas, pequenas e indexadas (64×64 e 32×32 a
  256 cores), cada uma com a paleta `<textura>_pl` em BGR555. Leitor e escritor de paleta:
  `analise/tools/nsbtx.py` (o layout está no topo do script). Ida e volta (`exportar` +
  `importar`) dá os 584 `.nsbtx` do jogo idênticos byte a byte.
- `SHA_CB_*.nsbca` (batalha) e `SHA_EX_*.nsbca` (exploração): animações do esqueleto.
  Ainda sem leitor nosso.

Tabelas: `creatures.gda` → coluna `Appearance` → `appearances.gda` (escala, nome do modelo
na coluna `col_7e7d1786`, `Skeleton`). Em `animations.gda` cada coluna depois de
`col_16ac1851` (o nome genérico da ação, como `EX_IDLE`) é um esqueleto, e a linha 0 dá o
prefixo dos arquivos (`SHA_`, `SON_`, `KNU_`...). Isto último é inferido da leitura da
tabela, não conferido no jogo. O Sonic e o Shadow jogáveis (aparências 0 e 4) têm o
`Type` 4 e o nome do modelo vazio; como o jogo acha o modelo deles ainda não sabemos.

*Validado no emulador:* com só as paletas de `GenSonN_AA.nsbtx` trocadas (azul → verde)
e a ROM gerada pelo `sonic-mod pack`, o Sonic aparece verde na exploração (save do
Capítulo 10). Ou seja, o Sonic jogável usa essa textura, apesar do nome vazio na tabela.

## Diálogos (`.dlg`, GFF4 `CONV`)
`12002` nós `NTRY`: `12201` texto (TlkString), `12202` retrato (`prtl_<personagem><emoção>`),
`12208`/`12209` condição e ação (`PLOT`), `12400` links. `12000` entradas `STRT`.

## Ainda não decifrados
Vídeos `.vx` (Actimagine), layout das telas `.gui` (peças esticadas/repetidas),
paletas dos Chao, 311 nomes de colunas GDA.
