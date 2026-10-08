/* ROM de teste: um "jogo de mentira" para provar o painel sem precisar do jogo.
 *
 * Ela faz o papel do Sonic Chronicles: liga as telas, desenha um padrão xadrez na tela de
 * baixo NO MESMO lugar da VRAM que o painel usa (o pior caso para salvar e restaurar),
 * põe nos endereços do jogo os valores que o jogo teria e chama modmenu_quadro() uma
 * vez por quadro, como o gancho fará no jogo de verdade.
 *
 * O roteiro ferramentas/testar.py abre o painel, muda valores, fecha e confere byte a
 * byte que a tela de baixo voltou como estava. */
#include "ds.h"

void modmenu_quadro(void);

/* Contador de quadros do "jogo", num endereço fixo para o roteiro de teste ler. Se o
 * painel pausa o jogo de verdade, ele para de subir enquanto o painel está aberto. */
#define CONTADOR (*(volatile u32 *)0x02100000)

static void esperar_vblank(void) {
    while (REG_VCOUNT >= 192) {}
    while (REG_VCOUNT < 192) {}
}

void teste_main(void) {
    /* Liga LCD (bit 0), motores A (1) e B (9); bit 15: motor A na tela de cima. */
    REG_POWCNT1 = 0x8203;
    /* Banco C (128 KB) como VRAM de fundos do motor B: ligado (bit 7), MST = 4. */
    REG_VRAMCNT_C = 0x84;

    /* Tela de cima: só a cor de fundo, verde-escuro. */
    REG_DISPCNT_A = 1u << 16;
    *(volatile u16 *)0x05000000 = RGB15(0, 8, 0);

    /* Tela de baixo do "jogo": BG0 e BG1 ligadas, tiles e mapa nos blocos que o painel
     * também usa (1 e 15), prioridade 3, e algo no brilho e na mistura, para o teste ver
     * se tudo volta. */
    REG_DISPCNT_B = (1u << 16) | (1u << 8) | (1u << 9);
    REG_BG0CNT_B = (u16)(3 | (1 << 2) | (15 << 8));
    REG_BG1CNT_B = (u16)(2 | (1 << 2) | (14 << 8));
    REG_BLDCNT_B = 0x0041;
    REG_MASTER_BRIGHT_B = 0x4002;

    /* Paleta: 256 cores diferentes, todas não nulas. */
    for (int i = 0; i < 256; i++) PALETA_BG_B[i] = (u16)(0x1234 + i * 0x0101);
    /* Tiles do bloco 1: um padrão que muda a cada palavra, em toda a área da fonte e um
     * pouco além. */
    volatile u32 *t = (volatile u32 *)(VRAM_BG_B + 0x4000);
    for (int i = 0; i < 1024; i++) t[i] = 0x11112222u ^ (u32)(i * 0x01010101u);
    /* Mapa do bloco 15: xadrez de tiles 1 e 2. */
    volatile u16 *m = (volatile u16 *)(VRAM_BG_B + 15 * 0x800);
    for (int i = 0; i < 32 * 32; i++) m[i] = (u16)(1 + (((i >> 5) ^ i) & 1));

    /* Os valores que o jogo carrega no boot (COMBATE.md, seções 7, 14 e 15). */
    *(volatile s32 *)0x020F64C0 = 110;
    *(volatile s32 *)0x020F64BC = 60;
    *(volatile s32 *)0x020F6470 = 7;
    *(volatile s32 *)0x020F64FC = 20;
    *(volatile s8 *)0x02160E54 = 0;
    *(volatile u8 *)0x02160E58 = 0;

    CONTADOR = 0;
    for (;;) {
        esperar_vblank();
        CONTADOR = CONTADOR + 1;
        modmenu_quadro(); /* no jogo, quem chama isto é o gancho */
    }
}
