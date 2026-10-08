/* Registradores do Nintendo DS usados pelo painel.
 *
 * Não usamos a libnds nem o NitroSDK: escrevemos direto no hardware. Assim o painel
 * não depende de biblioteca nenhuma, cabe em poucos KB e pode morar dentro de um jogo
 * que tem as próprias bibliotecas. Endereços e significados: GBATEK
 * (https://problemkaputt.de/gbatek.htm), seções "DS Display" e "DS Keypad".
 *
 * "Motor A" e "motor B" são os dois processadores de vídeo 2D do DS. Normalmente o A
 * desenha a tela de cima e o B a de baixo (o bit 15 do POWCNT1 pode trocar). */
#ifndef DS_H
#define DS_H

typedef unsigned char u8;
typedef unsigned short u16;
typedef unsigned int u32;
typedef signed char s8;
typedef signed short s16;
typedef signed int s32;

#define REG8(a) (*(volatile u8 *)(a))
#define REG16(a) (*(volatile u16 *)(a))
#define REG32(a) (*(volatile u32 *)(a))

/* Linha que a tela está desenhando agora (0-191 visível, 192-262 VBlank). Só leitura. */
#define REG_VCOUNT REG16(0x04000006)

/* Botões. Bit em 0 = APERTADO (lógica invertida). X e Y não aparecem aqui: no DS eles
 * só são lidos pelo ARM7. */
#define REG_KEYINPUT REG16(0x04000130)
#define TECLA_A 0x0001
#define TECLA_B 0x0002
#define TECLA_SELECT 0x0004
#define TECLA_START 0x0008
#define TECLA_DIREITA 0x0010
#define TECLA_ESQUERDA 0x0020
#define TECLA_CIMA 0x0040
#define TECLA_BAIXO 0x0080
#define TECLA_R 0x0100
#define TECLA_L 0x0200
#define TECLAS_TODAS 0x03FF

/* Liga e desliga partes do vídeo. Bit 9 = motor B ligado. Leitura e escrita. */
#define REG_POWCNT1 REG16(0x04000304)

/* Motor B (tela de baixo). Todos de leitura e escrita, exceto onde dito. */
#define REG_DISPCNT_B REG32(0x04001000)
#define REG_BG0CNT_B REG16(0x04001008)
#define REG_BG1CNT_B REG16(0x0400100A)
#define REG_BG0HOFS_B REG16(0x04001010) /* SÓ ESCRITA: não dá para salvar */
#define REG_BG0VOFS_B REG16(0x04001012) /* SÓ ESCRITA: não dá para salvar */
#define REG_BLDCNT_B REG16(0x04001050)
#define REG_MASTER_BRIGHT_B REG16(0x0400106C)

/* Motor A (tela de cima), usado só pela ROM de teste. */
#define REG_DISPCNT_A REG32(0x04000000)

/* Bancos de VRAM. SÓ ESCRITA: por isso o painel nunca mexe neles no jogo. */
#define REG_VRAMCNT_C REG8(0x04000242)

/* Memória de vídeo do motor B: fundos (BG) a partir de 0x06200000 e paleta de fundos
 * em 0x05000400 (256 cores de 16 bits, formato 0BBBBBGGGGGRRRRR). */
#define VRAM_BG_B 0x06200000u
#define PALETA_BG_B ((volatile u16 *)0x05000400)

#define RGB15(r, g, b) ((u16)((r) | ((g) << 5) | ((b) << 10)))

#endif
