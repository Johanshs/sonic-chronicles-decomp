/* O painel de controle: páginas de campos que leem e escrevem a RAM do jogo.
 *
 * Ponto de entrada: modmenu_quadro(), que o gancho chama UMA vez por volta do laço
 * principal do jogo. Se L + R + SELECT estiverem apertados, o painel abre e o jogo fica
 * PAUSADO: não devolvemos o controle até o painel fechar. Enquanto isso, só as
 * interrupções do jogo continuam rodando (e o ARM7, que cuida do som, segue sozinho).
 *
 * Controles: CIMA/BAIXO escolhem, A entra, B volta (na tela inicial, fecha),
 * ESQUERDA/DIREITA mudam o valor em 1, L/R mudam em 10, START fecha de qualquer lugar.
 *
 * Os endereços vêm de docs/COMBATE.md e docs/CHEATS.md. A coluna "conf" diz como cada um
 * foi conferido: "emu" = no emulador; "est" = só na análise estática. */
#include "console.h"

#define VERSAO "0.2"
#define COMBO_ABRIR (TECLA_L | TECLA_R | TECLA_SELECT)

/* Como o jogo guarda cada número. O painel mostra e edita sempre o valor "humano". */
enum {
    F_INT,    /* inteiro de 32 bits com sinal */
    F_BOOL,   /* 0 ou 1, em 32 bits */
    F_FX,     /* ponto fixo do DS: valor x 4096 (por exemplo, o PP atual) */
    F_FX100,  /* o valor da tabela dividido por 100, em ponto fixo: 90 -> 0,90 x 4096 */
    F_FX1000, /* idem, dividido por 1000 */
    F_S8,     /* 1 byte com sinal */
    F_U8,     /* 1 byte sem sinal */
};

typedef struct {
    const char *nome; /* até 19 letras: cabe com o valor na linha de 32 */
    u32 endereco;     /* absoluto, ou o deslocamento no vetor de atributos (páginas do grupo) */
    u8 formato;
    u8 conferido;     /* 1 = conferido no emulador */
    s16 minimo, maximo;
} Campo;

typedef struct {
    const char *titulo;
    const Campo *campos;
    u8 n;
    u8 membro; /* 0 = endereços absolutos; 1 a 4 = membro do grupo */
} Pagina;

/* ---- As 74 regras de combate (combatrules.gda), na ordem da tabela ----
 * Mapa de analise/tools/mapa_regras.py (docs/CHEATS.md): todas moram em endereço fixo,
 * e os valores lidos no emulador depois do boot batem com a tabela. */
#define R(n, nome, end, fmt) {"R" #n " " nome, end, fmt, 1, -9999, 30000}
static const Campo campos_regras[] = {
    R(0, "nao usada", 0x020F6480, F_INT),
    R(1, "inic: base", 0x020F6474, F_INT),
    R(2, "inic: dado 1dN", 0x020F6484, F_INT),
    R(3, "inic: x Speed", 0x021A57B4, F_FX),
    R(4, "?", 0x020F6478, F_BOOL),
    R(5, "minijogo POW", 0x020F64E0, F_INT),
    R(6, "minijogo POW", 0x020F64DC, F_INT),
    R(7, "Defender: Def", 0x020F6470, F_INT),
    R(8, "Defender: Grit", 0x020F64FC, F_INT),
    R(9, "?", 0x020F64D8, F_INT),
    R(10, "?", 0x020F64F4, F_INT),
    R(11, "Defender: PP", 0x020F64F0, F_INT),
    R(12, "?", 0x020F64EC, F_INT),
    R(13, "?", 0x020F64E8, F_INT),
    R(14, "?", 0x020F64E4, F_INT),
    R(15, "minijogo POW", 0x021AC29C, F_FX),
    R(16, "minijogo POW", 0x021AC2A0, F_FX),
    R(17, "minijogo POW", 0x021AC2A4, F_FX),
    R(18, "minijogo POW", 0x021AC2D8, F_FX),
    R(19, "minijogo POW", 0x021AC2DC, F_FX),
    R(20, "minijogo POW", 0x021AC2E0, F_FX),
    R(21, "minijogo POW", 0x021AC2A8, F_FX),
    R(22, "minijogo POW", 0x021AC2AC, F_FX),
    R(23, "minijogo POW", 0x021AC2B0, F_FX),
    R(24, "minijogo POW", 0x021AC2B4, F_FX),
    R(25, "minijogo POW", 0x021AC2B8, F_FX),
    R(26, "minijogo POW", 0x021AC2BC, F_FX),
    R(27, "minijogo POW", 0x021AC2C0, F_FX),
    R(28, "minijogo POW", 0x021AC2C4, F_FX),
    R(29, "minijogo POW", 0x021AC2C8, F_FX),
    R(30, "minijogo POW", 0x021AC2FC, F_FX),
    R(31, "minijogo POW", 0x021AC300, F_FX),
    R(32, "minijogo POW", 0x021AC304, F_FX),
    R(33, "inic: divisor", 0x020F64F8, F_INT),
    R(34, "explor: combate", 0x021A57F0, F_BOOL),
    R(35, "GUI tempo real", 0x021A57E8, F_FX1000),
    R(36, "?", 0x021AC288, F_INT),
    R(37, "?", 0x021AC28C, F_INT),
    R(38, "GUI tempo real", 0x020F944C, F_INT),
    R(39, "dano basico", 0x020F64D4, F_INT),
    R(40, "desempenho POW", 0x020F64D0, F_INT),
    R(41, "desempenho POW", 0x020F64CC, F_INT),
    R(42, "desempenho POW", 0x020F64C8, F_INT),
    R(43, "dano: fixo", 0x020F64C4, F_INT),
    R(44, "dano: k grupo", 0x020F64C0, F_INT),
    R(45, "dano: k inimigo", 0x020F64BC, F_INT),
    R(46, "?", 0x020F64B8, F_INT),
    R(47, "emboscada: dado", 0x020F64B4, F_INT),
    R(48, "minijogo POW", 0x021AC2CC, F_FX),
    R(49, "minijogo POW", 0x021AC2D0, F_FX),
    R(50, "minijogo POW", 0x021AC2D4, F_FX),
    R(51, "?", 0x021A57E0, F_FX100),
    R(52, "?", 0x021A57DC, F_FX100),
    R(53, "explor: combate", 0x021A57EC, F_FX1000),
    R(54, "?", 0x021A57D8, F_FX100),
    R(55, "?", 0x020F64B0, F_INT),
    R(56, "?", 0x020F64AC, F_INT),
    R(57, "dific+ Defense", 0x021A57D4, F_INT),
    R(58, "dific+ Power", 0x020F64A8, F_INT),
    R(59, "dific+ Attack", 0x020F64A4, F_INT),
    R(60, "dific+ Grit", 0x021A57D0, F_INT),
    R(61, "dific+ HP max", 0x020F64A0, F_INT),
    R(62, "dific+ divisor", 0x020F649C, F_INT),
    R(63, "dific: nivel max", 0x020F6498, F_INT),
    R(64, "dific: nivel min", 0x021A57CC, F_INT),
    R(65, "dific- divisor", 0x020F6494, F_INT),
    R(66, "dific- Defense", 0x021A57C8, F_INT),
    R(67, "dific- Power", 0x020F6490, F_INT),
    R(68, "dific- Attack", 0x020F648C, F_INT),
    R(69, "dific- Grit", 0x020F6488, F_INT),
    R(70, "dific- HP max", 0x021A57C4, F_INT),
    R(71, "POW escala nv1", 0x021A57C0, F_FX100),
    R(72, "POW escala nv2", 0x021A57BC, F_FX100),
    R(73, "POW escala nv3", 0x021A57B8, F_FX100),
};
#undef R

static const Campo campos_dificuldade[] = {
    /* COMBATE.md seção 14: nível de -4 a +6 (byte com sinal) e a chave que o liga */
    {"Nivel (-4 a +6)", 0x02160E54, F_S8, 1, -4, 6},
    {"Chave (0/1)", 0x02160E58, F_U8, 0, 0, 1},
};

static const Campo campos_aneis[] = {
    /* CHEATS.md: o contador do HUD (achado no emulador: pegar um anel soma 1 aqui) */
    {"Aneis", 0x02160EB0, F_INT, 1, 0, 9999},
};

/* Atributos de um membro do grupo: deslocamentos no vetor de atributos (CHEATS.md). */
static const Campo campos_membro[] = {
    {"HP", 0x00, F_INT, 1, 0, 9999},
    {"HP maximo", 0xA0, F_INT, 1, 1, 9999},
    {"PP", 0xB0, F_FX, 1, 0, 999},
    {"PP maximo", 0xB8, F_INT, 1, 0, 999},
    {"Speed", 0x94, F_INT, 1, 0, 999},
    {"Attack (acerto)", 0x98, F_INT, 1, 0, 999},
    {"Defense (esquiva)", 0x9C, F_INT, 1, 0, 999},
    {"Power (dano)", 0xA4, F_INT, 0, 0, 999},
    {"Grit (armadura)", 0xA8, F_INT, 0, 0, 999},
    {"Luck", 0xAC, F_INT, 1, 0, 999},
};

#define N(v) ((u8)(sizeof v / sizeof v[0]))
static const Pagina paginas[] = {
    {"Regras de combate (74)", campos_regras, N(campos_regras), 0},
    {"Dificuldade dinamica", campos_dificuldade, N(campos_dificuldade), 0},
    {"Aneis", campos_aneis, N(campos_aneis), 0},
    {"Grupo: membro 1", campos_membro, N(campos_membro), 1},
    {"Grupo: membro 2", campos_membro, N(campos_membro), 2},
    {"Grupo: membro 3", campos_membro, N(campos_membro), 3},
    {"Grupo: membro 4", campos_membro, N(campos_membro), 4},
};
#define N_PAGINAS ((int)N(paginas))

/* ---- Achar o endereço de um campo ---- */

#define LISTA_DO_GRUPO 0x02160B28u
#define VTABLE_JOGADOR 0x020F9200u /* todo CGamePlayerCreature começa com isto */

static int ponteiro_ok(u32 p) { return p >= 0x02000000u && p < 0x02400000u && !(p & 3); }

/* A n-ésima criatura do grupo (n = 1 a 4), ou 0. 0x02160B28 aponta para um vetor de
 * ponteiros para as criaturas. No começo de um jogo novo, o Sonic está na posição 0 e
 * logo depois vem lixo; com o save do Johans (docs/CHEATS.md), o primeiro membro estava
 * na posição 1. Para servir aos dois casos, percorremos as 8 primeiras posições e
 * contamos só os ponteiros válidos que apontam para um CGamePlayerCreature (o primeiro
 * campo é a vtable da classe), sem repetir. Cada ponteiro é conferido antes de ser
 * lido: um ponteiro errado faria o painel escrever em lugar aleatório. */
static u32 membro(int n) {
    u32 lista = *(volatile u32 *)LISTA_DO_GRUPO;
    if (!ponteiro_ok(lista)) return 0;
    u32 vistos[4];
    int achados = 0;
    for (int i = 0; i < 8; i++) {
        u32 c = *(volatile u32 *)(lista + 4u * i);
        if (!ponteiro_ok(c) || *(volatile u32 *)c != VTABLE_JOGADOR) continue;
        int repetido = 0;
        for (int j = 0; j < achados; j++) repetido |= vistos[j] == c;
        if (repetido) continue;
        vistos[achados++] = c;
        if (achados == n) return c;
    }
    return 0;
}

/* Endereço do campo, ou 0 se ele não existe agora (membro vazio, fora do jogo...). */
static u32 endereco(const Pagina *p, const Campo *c) {
    if (!p->membro) return c->endereco;
    u32 criatura = membro(p->membro);
    if (!criatura) return 0;
    u32 atributos = *(volatile u32 *)(criatura + 0x1C);
    if (!ponteiro_ok(atributos)) return 0;
    return atributos + c->endereco;
}

/* ---- Conversão entre o valor guardado e o valor humano ----
 * Sem divisão (o ARM946 não tem) e só em 32 bits (no Thumb, a multiplicação de 64 bits
 * viraria uma chamada à biblioteca do compilador, que não temos): multiplicamos pelo
 * inverso em ponto fixo e deslocamos. Os limites dos campos (até 30000) garantem que as
 * contas cabem em 32 bits. */

static s32 humano(s32 bruto, int formato) {
    switch (formato) {
    case F_FX: return (bruto + 2048) >> 12;
    case F_FX100: return (bruto * 100 + 2048) >> 12;
    case F_FX1000: return (bruto * 1000 + 2048) >> 12;
    default: return bruto;
    }
}

static s32 bruto(s32 v, int formato) {
    switch (formato) {
    case F_FX: return v << 12;
    case F_FX100: return (v * 41943 + 512) >> 10;  /* 41943/1024 = 40,96 = 4096/100 */
    case F_FX1000: return (v * 4194 + 512) >> 10;  /* 4194/1024 = 4,096 = 4096/1000 */
    default: return v;
    }
}

static s32 ler(u32 a, int formato) {
    switch (formato) {
    case F_S8: return *(volatile s8 *)a;
    case F_U8: return *(volatile u8 *)a;
    default: return humano(*(volatile s32 *)a, formato);
    }
}

static void escrever(u32 a, const Campo *c, s32 v) {
    if (c->formato == F_BOOL) v = v > 0;
    if (v < c->minimo) v = c->minimo;
    if (v > c->maximo) v = c->maximo;
    switch (c->formato) {
    case F_S8:
    case F_U8: *(volatile u8 *)a = (u8)v; break;
    default: *(volatile s32 *)a = bruto(v, c->formato); break;
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

#define LINHA_1 4  /* primeira linha da lista */
#define VISIVEIS 16 /* linhas da lista que cabem entre o cabeçalho e o rodapé */

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
        con_texto(1, LINHA_1 + i, cor, i == sel ? ">" : " ");
        con_texto(3, LINHA_1 + i, cor, paginas[i].titulo);
    }
    con_texto(0, 18, COR_CINZA, "O jogo fica pausado enquanto o");
    con_texto(0, 19, COR_CINZA, "painel esta aberto.");
    rodape("A entra   B/START fecha", "Abrir: L + R + SELECT");
}

static void desenhar_pagina(const Pagina *p, int sel, int topo) {
    cabecalho(p->titulo);
    con_texto(1, 3, COR_CINZA, "campo               valor conf");
    int vazio = 1;
    for (int i = topo; i < p->n && i < topo + VISIVEIS; i++) {
        const Campo *c = &p->campos[i];
        int lin = LINHA_1 + i - topo;
        int cor = i == sel ? COR_AMARELO : COR_BRANCO;
        u32 a = endereco(p, c);
        con_texto(0, lin, cor, i == sel ? ">" : " ");
        con_texto(1, lin, cor, c->nome);
        if (a) { con_numero(20, lin, cor, ler(a, c->formato), 6); vazio = 0; }
        else con_texto(20, lin, COR_CINZA, "   ---");
        con_texto(27, lin, COR_CINZA, c->conferido ? "emu" : "est");
    }
    /* setas de rolagem quando a lista não cabe */
    if (topo > 0) con_texto(31, LINHA_1, COR_VERDE, "^");
    if (topo + VISIVEIS < p->n) con_texto(31, LINHA_1 + VISIVEIS - 1, COR_VERDE, "v");
    if (vazio && p->membro) con_texto(1, 20, COR_CINZA, "(membro vazio ou fora do jogo)");
    rodape("<> -1/+1   L R -10/+10", "B volta   START fecha");
}

/* ---- Laço do painel ---- */

static void painel(void) {
    int pagina = -1; /* -1 = tela inicial */
    int sel_inicio = 0, sel = 0, topo = 0;
    for (;;) {
        esperar_quadro();
        con_reafirmar();
        u16 t = ler_teclas();
        if (t & TECLA_START) return;

        if (pagina < 0) {
            if (t & TECLA_B) return;
            if (t & TECLA_CIMA) sel_inicio = sel_inicio ? sel_inicio - 1 : N_PAGINAS - 1;
            if (t & TECLA_BAIXO) sel_inicio = sel_inicio + 1 < N_PAGINAS ? sel_inicio + 1 : 0;
            if (t & TECLA_A) { pagina = sel_inicio; sel = 0; topo = 0; }
        } else {
            const Pagina *p = &paginas[pagina];
            const Campo *c = &p->campos[sel];
            if (t & TECLA_B) pagina = -1;
            if (t & TECLA_CIMA) sel = sel ? sel - 1 : p->n - 1;
            if (t & TECLA_BAIXO) sel = sel + 1 < p->n ? sel + 1 : 0;
            if (sel < topo) topo = sel;
            if (sel >= topo + VISIVEIS) topo = sel - VISIVEIS + 1;
            s32 d = 0;
            if (t & TECLA_DIREITA) d += 1;
            if (t & TECLA_ESQUERDA) d -= 1;
            if (t & TECLA_R) d += 10;
            if (t & TECLA_L) d -= 10;
            u32 a = endereco(p, c);
            if (d && a) escrever(a, c, ler(a, c->formato) + d);
        }

        con_limpar();
        if (pagina < 0) desenhar_inicio(sel_inicio);
        else desenhar_pagina(&paginas[pagina], sel, topo);
    }
}

/* Chamado pelo gancho uma vez por volta do laço. Precisa ser barato quando o painel está
 * fechado: é só uma leitura de registrador e uma comparação. Devolve 1 se o painel
 * abriu (e o jogo ficou parado), para o gancho poder acertar o relógio do jogo. */
int modmenu_quadro(void) {
    if ((teclas_agora() & COMBO_ABRIR) != COMBO_ABRIR) return 0;
    if (!con_abrir()) return 0;
    teclas_antes = teclas_agora(); /* o combo de abrir não conta como tecla nova */
    repete_quadros = 0;
    painel();
    esperar_soltar(); /* o jogo não deve ver o START/B que fechou o painel */
    con_fechar();
    return 1;
}
