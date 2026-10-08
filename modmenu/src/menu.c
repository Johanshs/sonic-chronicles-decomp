/* O painel de controle: páginas de campos que leem e escrevem a RAM do jogo.
 *
 * Ponto de entrada: modmenu_quadro(), que o gancho chama UMA vez por quadro. Se L + R +
 * SELECT estiverem apertados, o painel abre e o jogo fica PAUSADO: não devolvemos o
 * controle até o painel fechar. Enquanto isso, só as interrupções do jogo continuam
 * rodando (e o ARM7, que cuida do som, segue sozinho).
 *
 * Controles: CIMA/BAIXO escolhem, A entra, B volta (na tela inicial, fecha),
 * ESQUERDA/DIREITA mudam o valor em 1, L/R mudam em 10, START fecha de qualquer lugar.
 *
 * Os endereços vêm de docs/COMBATE.md e docs/PLANO-MOD-MENU.md. A coluna "conf." diz se o
 * endereço já foi conferido no emulador ("emu") ou só na análise estática ("est"). */
#include "console.h"

#define VERSAO "0.1"
#define COMBO_ABRIR (TECLA_L | TECLA_R | TECLA_SELECT)

typedef struct {
    const char *nome; /* até 18 letras: cabe com o valor na linha de 32 */
    u32 endereco;
    u8 bytes;     /* 1, 2 ou 4 */
    u8 com_sinal; /* 1 = o jogo lê como número com sinal */
    u8 conferido; /* 1 = conferido no emulador */
    s32 minimo, maximo;
} Campo;

typedef struct {
    const char *titulo;
    const Campo *campos;
    int n;
} Pagina;

static const Campo campos_regras[] = {
    /* COMBATE.md seção 5: dano = 0,9 x Power + k/100 x (3dP/3) - Grit */
    {"R44 k dano grupo", 0x020F64C0, 4, 1, 1, 0, 9999},
    {"R45 k dano inimigo", 0x020F64BC, 4, 1, 1, 0, 9999},
    /* COMBATE.md seção 7: Defender soma Defense x R7/10 e Grit x R8/10 */
    {"R7 Defender:Defense", 0x020F6470, 4, 1, 1, 0, 100},
    {"R8 Defender:Grit", 0x020F64FC, 4, 1, 0, 0, 100},
};

static const Campo campos_dificuldade[] = {
    /* COMBATE.md seção 14: nível de -4 a +6 (byte com sinal) e a chave que o liga */
    {"Nivel (-4 a +6)", 0x02160E54, 1, 1, 1, -4, 6},
    {"Chave (0/1)", 0x02160E58, 1, 0, 0, 0, 1},
};

static const Pagina paginas[] = {
    {"Regras de combate", campos_regras, sizeof campos_regras / sizeof campos_regras[0]},
    {"Dificuldade dinamica", campos_dificuldade,
     sizeof campos_dificuldade / sizeof campos_dificuldade[0]},
};
#define N_PAGINAS ((int)(sizeof paginas / sizeof paginas[0]))

static s32 ler(const Campo *c) {
    switch (c->bytes) {
    case 1: return c->com_sinal ? *(volatile s8 *)c->endereco : *(volatile u8 *)c->endereco;
    case 2: return c->com_sinal ? *(volatile s16 *)c->endereco : *(volatile u16 *)c->endereco;
    default: return *(volatile s32 *)c->endereco;
    }
}

static void escrever(const Campo *c, s32 v) {
    if (v < c->minimo) v = c->minimo;
    if (v > c->maximo) v = c->maximo;
    switch (c->bytes) {
    case 1: *(volatile u8 *)c->endereco = (u8)v; break;
    case 2: *(volatile u16 *)c->endereco = (u16)v; break;
    default: *(volatile u32 *)c->endereco = (u32)v; break;
    }
}

/* ---- Teclado: borda de descida e repetição ao segurar ---- */

static u16 teclas_antes;
static int repete_quadros;

static u16 teclas_agora(void) { return (u16)(~REG_KEYINPUT & TECLAS_TODAS); }

/* Devolve as teclas que "dispararam" neste quadro: as recém-apertadas e, depois de
 * segurar 20 quadros, uma repetição a cada 4 (para correr por valores grandes). */
static u16 ler_teclas(void) {
    u16 agora = teclas_agora();
    u16 novas = agora & ~teclas_antes;
    if (agora && agora == teclas_antes) {
        if (++repete_quadros >= 20) { novas = agora; repete_quadros = 16; }
    } else {
        repete_quadros = 0;
    }
    teclas_antes = agora;
    return novas;
}

static void esperar_soltar(void) {
    while (teclas_agora()) esperar_quadro();
}

/* ---- Desenho ---- */

static void cabecalho(const char *sub) {
    con_texto(0, 0, COR_VERDE, "SONIC CHRONICLES  PAINEL v" VERSAO);
    con_texto(0, 1, COR_CINZA, "--------------------------------");
    con_texto(0, 2, COR_BRANCO, sub);
}

static void rodape(const char *l1, const char *l2) {
    con_texto(0, 21, COR_CINZA, "--------------------------------");
    con_texto(0, 22, COR_CINZA, l1);
    con_texto(0, 23, COR_CINZA, l2);
}

static void desenhar_inicio(int sel) {
    cabecalho("Escolha uma pagina:");
    for (int i = 0; i < N_PAGINAS; i++) {
        int cor = i == sel ? COR_AMARELO : COR_BRANCO;
        con_texto(1, 4 + i, cor, i == sel ? ">" : " ");
        con_texto(3, 4 + i, cor, paginas[i].titulo);
    }
    con_texto(0, 18, COR_CINZA, "O jogo fica pausado enquanto o");
    con_texto(0, 19, COR_CINZA, "painel esta aberto.");
    rodape("A entra   B/START fecha", "Abrir: L + R + SELECT");
}

static void desenhar_pagina(const Pagina *p, int sel) {
    cabecalho(p->titulo);
    con_texto(1, 3, COR_CINZA, "campo               valor conf");
    for (int i = 0; i < p->n; i++) {
        const Campo *c = &p->campos[i];
        int cor = i == sel ? COR_AMARELO : COR_BRANCO;
        con_texto(0, 5 + i, cor, i == sel ? ">" : " ");
        con_texto(1, 5 + i, cor, c->nome);
        con_numero(20, 5 + i, cor, ler(c), 6);
        con_texto(28, 5 + i, COR_CINZA, c->conferido ? "emu" : "est");
    }
    rodape("<> -1/+1   L R -10/+10", "B volta   START fecha");
}

/* ---- Laço do painel ---- */

static void painel(void) {
    int pagina = -1; /* -1 = tela inicial */
    int sel_inicio = 0, sel = 0;
    for (;;) {
        esperar_quadro();
        con_reafirmar();
        u16 t = ler_teclas();
        if (t & TECLA_START) return;

        if (pagina < 0) {
            if (t & TECLA_B) return;
            if (t & TECLA_CIMA) sel_inicio = sel_inicio ? sel_inicio - 1 : N_PAGINAS - 1;
            if (t & TECLA_BAIXO) sel_inicio = sel_inicio + 1 < N_PAGINAS ? sel_inicio + 1 : 0;
            if (t & TECLA_A) { pagina = sel_inicio; sel = 0; }
        } else {
            const Pagina *p = &paginas[pagina];
            const Campo *c = &p->campos[sel];
            if (t & TECLA_B) pagina = -1;
            if (t & TECLA_CIMA) sel = sel ? sel - 1 : p->n - 1;
            if (t & TECLA_BAIXO) sel = sel + 1 < p->n ? sel + 1 : 0;
            s32 d = 0;
            if (t & TECLA_DIREITA) d += 1;
            if (t & TECLA_ESQUERDA) d -= 1;
            if (t & TECLA_R) d += 10;
            if (t & TECLA_L) d -= 10;
            if (d) escrever(c, ler(c) + d);
        }

        con_limpar();
        if (pagina < 0) desenhar_inicio(sel_inicio);
        else desenhar_pagina(&paginas[pagina], sel);
    }
}

/* Chamado pelo gancho uma vez por quadro. Precisa ser barato quando o painel está
 * fechado: é só uma leitura de registrador e uma comparação. */
void modmenu_quadro(void) {
    if ((teclas_agora() & COMBO_ABRIR) != COMBO_ABRIR) return;
    if (!con_abrir()) return;
    teclas_antes = teclas_agora(); /* o combo de abrir não conta como tecla nova */
    repete_quadros = 0;
    painel();
    esperar_soltar(); /* o jogo não deve ver o START/B que fechou o painel */
    con_fechar();
}
