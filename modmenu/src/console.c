/* Console de texto na tela de baixo, que devolve a tela ao jogo intacta.
 *
 * Como o DS desenha texto: a camada de fundo (BG) é uma grade de 32x24 "tiles" de 8x8
 * pixels. A VRAM guarda (1) os desenhos dos tiles, aqui um por letra, em 4 bits por pixel,
 * e (2) o "mapa": 32x24 números de 16 bits dizendo qual tile e qual paleta vai em cada
 * casa. Escrever "OI" é pôr o número do tile do 'O' e do 'I' em duas casas do mapa.
 *
 * O cuidado principal: a tela de baixo é do jogo. Antes de desenhar, copiamos para a RAM
 * exatamente os pedaços que vamos sobrescrever (registradores, paleta, a área da VRAM
 * da fonte e do mapa). Ao fechar, copiamos tudo de volta.
 *
 * Onde desenhamos na VRAM do motor B:
 *   fonte: bloco de tiles 1  = 0x06204000, 95 tiles x 32 bytes = 3040 bytes
 *   mapa:  bloco de mapa 15  = 0x06207800, 32x32 x 2 bytes     = 2048 bytes
 * Os dois ficam nos primeiros 32 KB, que existem com qualquer banco que o jogo tenha
 * ligado ao motor B (o C tem 128 KB, o H tem 32 KB).
 *
 * Limite conhecido: os registradores de rolagem (BG0HOFS/VOFS) são só de escrita. Não dá
 * para salvá-los; ao fechar, voltam a 0. Se o jogo rolar a BG0 da tela de baixo e não a
 * reescrever todo quadro, ela fica deslocada até o jogo mexer nela de novo. O teste
 * no jogo (fase B2) é que vai dizer se isso acontece. */
#include "console.h"

#define BLOCO_FONTE 1
#define BLOCO_MAPA 15
#define END_FONTE (VRAM_BG_B + BLOCO_FONTE * 0x4000)
#define END_MAPA (VRAM_BG_B + BLOCO_MAPA * 0x800)
#define TAM_FONTE (95 * 32)
#define TAM_MAPA (32 * 32 * 2)

extern const u8 fonte8x8[95][8];

/* O que o jogo tinha. Ficam no BSS do painel: ~5,6 KB. */
static u32 salvo_dispcnt;
static u16 salvo_bg0cnt, salvo_bldcnt, salvo_brilho;
static u16 salvo_paleta[256];
static u32 salvo_fonte[TAM_FONTE / 4];
static u32 salvo_mapa[TAM_MAPA / 4];

/* Cópia em palavras de 32 bits: a VRAM não aceita escrita de 8 bits. */
static void copiar32(volatile u32 *dst, const volatile u32 *src, int palavras) {
    for (int i = 0; i < palavras; i++) dst[i] = src[i];
}

void esperar_quadro(void) {
    /* Sem usar interrupções: só olhamos a linha atual. Primeiro saímos do VBlank (se já
     * estivermos nele), depois esperamos a linha 192, a primeira fora da tela. */
    while (REG_VCOUNT >= 192) {}
    while (REG_VCOUNT < 192) {}
}

/* Há VRAM ligada ao motor B? Escrevemos o inverso de uma palavra e lemos de volta. Sem
 * banco ligado, a escrita se perde e a leitura não muda. A palavra é restaurada. */
static int vram_presente(void) {
    volatile u16 *p = (volatile u16 *)END_MAPA;
    u16 antes = *p;
    *p = (u16)~antes;
    int ok = (*p == (u16)~antes);
    *p = antes;
    return ok;
}

static void enviar_fonte(void) {
    /* Converte cada linha de 1 bit por pixel (o byte da fonte) para 4 bits por pixel
     * (uma palavra de 32 bits). Pixel aceso = cor 1 do banco de paleta; apagado = cor 0,
     * transparente, que deixa ver a cor de fundo (backdrop). */
    volatile u32 *dst = (volatile u32 *)END_FONTE;
    for (int c = 0; c < 95; c++) {
        for (int y = 0; y < 8; y++) {
            u8 linha = fonte8x8[c][y];
            u32 px = 0;
            for (int x = 0; x < 8; x++)
                if (linha & (1 << x)) px |= 1u << (x * 4);
            *dst++ = px;
        }
    }
}

void con_reafirmar(void) {
    /* Modo 0, só a BG0 visível, sem janelas, sem paletas estendidas, modo de exibição
     * normal (bit 16). */
    REG_DISPCNT_B = (1u << 16) | (1u << 8);
    /* Prioridade 0, tiles no bloco 1, 16 cores, mapa no bloco 15, tamanho 256x256. */
    REG_BG0CNT_B = (u16)((BLOCO_FONTE << 2) | (BLOCO_MAPA << 8));
    REG_BG0HOFS_B = 0;
    REG_BG0VOFS_B = 0;
    REG_BLDCNT_B = 0;
    REG_MASTER_BRIGHT_B = 0;
    PALETA_BG_B[0] = RGB15(2, 3, 9); /* fundo azul-escuro */
    PALETA_BG_B[COR_CINZA * 16 + 1] = RGB15(20, 20, 22);
    PALETA_BG_B[COR_VERDE * 16 + 1] = RGB15(8, 31, 12);
    PALETA_BG_B[COR_AMARELO * 16 + 1] = RGB15(31, 28, 4);
    PALETA_BG_B[COR_BRANCO * 16 + 1] = RGB15(31, 31, 31);
    enviar_fonte();
}

int con_abrir(void) {
    if (!(REG_POWCNT1 & (1 << 9))) return 0; /* motor B desligado */
    if (!vram_presente()) return 0;

    salvo_dispcnt = REG_DISPCNT_B;
    salvo_bg0cnt = REG_BG0CNT_B;
    salvo_bldcnt = REG_BLDCNT_B;
    salvo_brilho = REG_MASTER_BRIGHT_B;
    for (int i = 0; i < 256; i++) salvo_paleta[i] = PALETA_BG_B[i];
    copiar32(salvo_fonte, (volatile u32 *)END_FONTE, TAM_FONTE / 4);
    copiar32(salvo_mapa, (volatile u32 *)END_MAPA, TAM_MAPA / 4);

    /* Desliga a tela de baixo enquanto troca tudo, para não aparecer um quadro misturado. */
    REG_DISPCNT_B = 0;
    con_limpar();
    con_reafirmar();
    return 1;
}

void con_fechar(void) {
    REG_DISPCNT_B = 0;
    copiar32((volatile u32 *)END_FONTE, salvo_fonte, TAM_FONTE / 4);
    copiar32((volatile u32 *)END_MAPA, salvo_mapa, TAM_MAPA / 4);
    for (int i = 0; i < 256; i++) PALETA_BG_B[i] = salvo_paleta[i];
    REG_BG0CNT_B = salvo_bg0cnt;
    REG_BLDCNT_B = salvo_bldcnt;
    REG_MASTER_BRIGHT_B = salvo_brilho;
    REG_BG0HOFS_B = 0; /* ver "Limite conhecido" no topo */
    REG_BG0VOFS_B = 0;
    REG_DISPCNT_B = salvo_dispcnt; /* por último: a tela volta já completa */
}

void con_limpar(void) {
    /* Tile 0 é o espaço (fonte começa em 0x20); banco de paleta branco. */
    volatile u32 *m = (volatile u32 *)END_MAPA;
    u32 vazio = (u32)(COR_BRANCO << 12) * 0x10001u;
    for (int i = 0; i < TAM_MAPA / 4; i++) m[i] = vazio;
}

static void por_char(int col, int lin, int cor, char c) {
    if (col < 0 || col >= CON_COLUNAS || lin < 0 || lin >= CON_LINHAS) return;
    if (c < 0x20 || c > 0x7E) c = '?';
    volatile u16 *m = (volatile u16 *)END_MAPA;
    m[lin * 32 + col] = (u16)((c - 0x20) | (cor << 12));
}

void con_texto(int col, int lin, int cor, const char *s) {
    while (*s) por_char(col++, lin, cor, *s++);
}

void con_numero(int col, int lin, int cor, s32 v, int largura) {
    /* Sem divisão: o ARM946 não tem instrução de dividir e não queremos depender da
     * biblioteca do compilador. Subtraímos potências de 10. */
    static const u32 pot[] = {1000000000u, 100000000u, 10000000u, 1000000u, 100000u,
                              10000u,      1000u,      100u,      10u,      1u};
    char buf[12];
    int n = 0;
    u32 u = v < 0 ? (u32)(-v) : (u32)v;
    if (v < 0) buf[n++] = '-';
    int comecou = 0;
    for (int i = 0; i < 10; i++) {
        char d = '0';
        while (u >= pot[i]) { u -= pot[i]; d++; }
        if (d != '0' || comecou || i == 9) { buf[n++] = d; comecou = 1; }
    }
    for (int i = n; i < largura; i++) por_char(col++, lin, cor, ' ');
    for (int i = 0; i < n; i++) por_char(col++, lin, cor, buf[i]);
}
