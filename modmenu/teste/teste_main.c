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

int modmenu_quadro(void);

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
    *(volatile s32 *)0x021A57C0 = 3686;    /* regra 71: 0,90 x 4096 (formato fx/100) */

    /* Um grupo de mentira, com o mesmo formato do jogo (docs/CHEATS.md): 0x02160B28
     * aponta para a lista de ponteiros. Como num save carregado, a posição 0 fica vazia;
     * a 1 e a 3 são criaturas (o primeiro campo é a vtable de CGamePlayerCreature, +0x1C
     * aponta para o vetor de atributos e +0x98 para o nome); a 2 tem um ponteiro para
     * algo que NÃO é criatura e a 4 tem lixo (texto), como o jogo tem. O painel deve
     * listar só as duas criaturas. */
    volatile u32 *lista = (volatile u32 *)0x02110000;
    lista[0] = 0;
    lista[2] = 0x02110800;        /* aponta para algo que não começa com a vtable */
    lista[4] = 0x6C616D69;        /* lixo: "imal" */
    for (int k = 0; k < 2; k++) {
        volatile u32 *criatura = (volatile u32 *)(0x02110100 + 0x400 * k);
        volatile s32 *atributos = (volatile s32 *)(0x02110200 + 0x400 * k);
        lista[1 + 2 * k] = (u32)criatura;
        criatura[0] = 0x020F9200;
        criatura[0x1C / 4] = (u32)atributos;
        criatura[0x98 / 4] = (u32)(k ? "Amy" : "Sonic");
        atributos[0] = 33 - 10 * k;          /* HP */
        atributos[0xA0 / 4] = 33 - 10 * k;   /* HP máximo */
        atributos[0xB0 / 4] = (7 + k) << 12; /* PP, em ponto fixo */
        atributos[0xB8 / 4] = 9;             /* PP máximo */
    }
    *(volatile u32 *)0x02160B28 = (u32)lista;
    *(volatile s32 *)0x02160B20 = 5; /* quantos: posições 0 a 4 (o lixo fica dentro) */

    /* Os inimigos de mentira: a lista da batalha (vetor em 0x02160AF8, quantos em
     * 0x02160AF0) com um CGameCreature (vtable 0x020F5D20) de 340 de HP. */
    volatile u32 *inimigos = (volatile u32 *)0x02112000;
    volatile u32 *inimigo = (volatile u32 *)0x02112100;
    volatile s32 *atrib_inimigo = (volatile s32 *)0x02112200;
    inimigos[0] = (u32)inimigo;
    inimigo[0] = 0x020F5D20;
    inimigo[0x1C / 4] = (u32)atrib_inimigo;
    inimigo[0x98 / 4] = (u32)"Decurion";
    atrib_inimigo[0] = 340;
    atrib_inimigo[0xA0 / 4] = 340;
    *(volatile u32 *)0x02160AF8 = (u32)inimigos;
    *(volatile s32 *)0x02160AF0 = 1;

    /* O esquadrão de mentira: 0x02160C18 aponta para um objeto cujo primeiro campo é o
     * esquadrão; o esquadrão começa com a vtable de CGamePlayerSquad e tem a carteira
     * em +0x114. */
    volatile u32 *esquadrao = (volatile u32 *)0x02111000;
    esquadrao[0] = 0x020F9C08;
    esquadrao[0x114 / 4] = 8;     /* anéis na carteira */
    *(volatile u32 *)0x02110F00 = (u32)esquadrao;
    *(volatile u32 *)0x02160C18 = 0x02110F00;

    /* O inventário de mentira: esquadrão + 0x40 aponta para ele (vtable de
     * CGameObjectInventory); quantas pilhas em +0x2C e o vetor em +0x34. Cada pilha é um
     * CGameItem com o número do item em +0xB8 e a quantidade em +0xBB. Aqui não há a
     * função do jogo que dá itens: o painel deve conferir os bytes dela e recusar. */
    volatile u32 *inventario = (volatile u32 *)0x02111800;
    volatile u32 *pilhas = (volatile u32 *)0x02111900;
    for (int k = 0; k < 2; k++) {
        volatile u8 *item = (volatile u8 *)(0x02111A00 + 0x100 * k);
        *(volatile u32 *)item = 0x020F6120;
        *(volatile s16 *)(item + 0xB8) = (s16)(k ? 3 : 6);
        item[0xBB] = (u8)(k ? 2 : 87);
        pilhas[k] = (u32)item;
    }
    inventario[0] = 0x020F93DC;
    inventario[0x2C / 4] = 2;
    inventario[0x34 / 4] = (u32)pilhas;
    esquadrao[0x40 / 4] = (u32)inventario;

    CONTADOR = 0;
    for (;;) {
        esperar_vblank();
        CONTADOR = CONTADOR + 1;
        modmenu_quadro(); /* no jogo, quem chama isto é o gancho */
    }
}
