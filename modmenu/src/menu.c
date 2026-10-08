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

#define VERSAO "0.3"
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
    s32 minimo, maximo;
} Campo;

/* De onde vêm os endereços dos campos de uma página. */
enum {
    P_FIXO,      /* endereço absoluto: o campo mora sempre no mesmo lugar */
    P_ESQUADRAO, /* deslocamento dentro do esquadrão (CGamePlayerSquad), que mora no heap */
    P_MEMBRO,    /* deslocamento no vetor de atributos do personagem escolhido */
    P_GRUPO,     /* não tem campos: é a lista de personagens, para escolher um */
};

typedef struct {
    const char *titulo;
    const Campo *campos;
    u8 n;
    u8 tipo;
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

static const Campo campos_carteira[] = {
    /* CHEATS.md: os anéis que você gasta (os do Inventário e da tela de save) moram no
     * esquadrão, em +0x114. 999999 é o maior número que cabe na tela do jogo.
     * (A v0.2 mexia em 0x02160EB0, que é outro contador: o do HUD, não a carteira.) */
    {"Aneis (carteira)", 0x114, F_INT, 1, 0, 999999},
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
    {"Regras de combate (74)", campos_regras, N(campos_regras), P_FIXO},
    {"Dificuldade dinamica", campos_dificuldade, N(campos_dificuldade), P_FIXO},
    {"Aneis", campos_carteira, N(campos_carteira), P_ESQUADRAO},
    {"Grupo (personagens)", 0, 0, P_GRUPO},
};
#define N_PAGINAS ((int)N(paginas))
/* A página de atributos de um personagem: o título é desenhado com o nome dele. */
static const Pagina pagina_membro = {"", campos_membro, N(campos_membro), P_MEMBRO};

/* ---- Achar o endereço de um campo ---- */

#define LISTA_DO_GRUPO 0x02160B28u
#define VTABLE_JOGADOR 0x020F9200u   /* todo CGamePlayerCreature começa com isto */
#define GLOBAL_ESQUADRAO 0x02160C18u /* aponta para um ponteiro para o esquadrão */
#define VTABLE_ESQUADRAO 0x020F9C08u /* todo CGamePlayerSquad começa com isto */
#define MAX_MEMBROS 16

static int ponteiro_ok(u32 p) { return p >= 0x02000000u && p < 0x02400000u && !(p & 3); }

/* O esquadrão (CGamePlayerSquad), ou 0. Ele mora no heap, então o endereço dele depende
 * de tudo o que o jogo alocou antes. O caminho fixo até ele: a global 0x02160C18 aponta
 * para um objeto cujo primeiro campo é o esquadrão. Achado no emulador procurando, de
 * trás para a frente, quem aponta para o esquadrão; conferido em 8 estados do jogo
 * (título, Green Hill, Capítulo 10) e com o heap em lugares diferentes. */
static u32 esquadrao(void) {
    u32 p = *(volatile u32 *)GLOBAL_ESQUADRAO;
    if (!ponteiro_ok(p)) return 0;
    u32 s = *(volatile u32 *)p;
    if (!ponteiro_ok(s) || *(volatile u32 *)s != VTABLE_ESQUADRAO) return 0;
    return s;
}

/* Os personagens do grupo, na ordem da lista. 0x02160B28 aponta para um vetor de
 * ponteiros com TODOS os que já entraram no grupo (11 no fim do jogo), não só os 4 da
 * batalha. As posições variam: num jogo novo o Sonic está na posição 0; num save
 * carregado, a 0 fica vazia e o Sonic vai para a 1. Depois do último vem lixo (pedaços
 * de texto). Por isso percorremos as primeiras posições e ficamos só com os ponteiros
 * válidos que apontam para um CGamePlayerCreature (o primeiro campo é a vtable da
 * classe), sem repetir. Um ponteiro errado faria o painel escrever em lugar aleatório. */
static u32 membros[MAX_MEMBROS];
static int n_membros;

static void achar_membros(void) {
    n_membros = 0;
    u32 lista = *(volatile u32 *)LISTA_DO_GRUPO;
    if (!ponteiro_ok(lista)) return;
    for (int i = 0; i < MAX_MEMBROS && lista + 4u * i < 0x02400000u; i++) {
        u32 c = *(volatile u32 *)(lista + 4u * i);
        if (!ponteiro_ok(c) || *(volatile u32 *)c != VTABLE_JOGADOR) continue;
        int repetido = 0;
        for (int j = 0; j < n_membros; j++) repetido |= membros[j] == c;
        if (!repetido) membros[n_membros++] = c;
    }
}

static s32 *atributos_de(u32 criatura) {
    u32 a = *(volatile u32 *)(criatura + 0x1C);
    return ponteiro_ok(a) ? (s32 *)a : 0;
}

/* O nome do personagem: a criatura guarda em +0x98 um ponteiro para o texto ("Sonic",
 * "Amy"...), conferido no emulador para os 11. Copiamos no máximo `max` letras e só
 * ASCII visível; se algo não bater, fica "?". */
static void nome_de(u32 criatura, char *buf, int max) {
    u32 p = *(volatile u32 *)(criatura + 0x98);
    int n = 0;
    if (p >= 0x02000000u && p < 0x023FFFF0u)
        while (n < max) {
            char ch = *(volatile char *)(p + n);
            if (ch < 0x20 || ch > 0x7E) break;
            buf[n++] = ch;
        }
    if (!n) buf[n++] = '?';
    buf[n] = 0;
}

static int membro_sel; /* o personagem aberto na página de atributos */

/* Endereço do campo, ou 0 se ele não existe agora (fora do jogo, personagem sumiu...). */
static u32 endereco(const Pagina *p, const Campo *c) {
    switch (p->tipo) {
    case P_FIXO: return c->endereco;
    case P_ESQUADRAO: {
        u32 s = esquadrao();
        return s ? s + c->endereco : 0;
    }
    case P_MEMBRO: {
        if (membro_sel >= n_membros) return 0;
        s32 *a = atributos_de(membros[membro_sel]);
        return a ? (u32)a + c->endereco : 0;
    }
    default: return 0;
    }
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

static void desenhar_pagina(const Pagina *p, const char *titulo, int sel, int topo) {
    cabecalho(titulo);
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
    if (vazio) con_texto(1, 20, COR_CINZA, "(nao achado: fora do jogo?)");
    rodape("<> -1/+1   L R -10/+10", "B volta   START fecha");
}

/* A lista de personagens: nome e HP de cada um, para escolher qual abrir. */
static void desenhar_grupo(int sel, int topo) {
    cabecalho("Grupo: escolha o personagem");
    con_texto(1, 3, COR_CINZA, "nome             HP / max");
    for (int i = topo; i < n_membros && i < topo + VISIVEIS; i++) {
        int lin = LINHA_1 + i - topo;
        int cor = i == sel ? COR_AMARELO : COR_BRANCO;
        char nome[13];
        nome_de(membros[i], nome, 12);
        con_texto(0, lin, cor, i == sel ? ">" : " ");
        con_texto(1, lin, cor, nome);
        s32 *a = atributos_de(membros[i]);
        if (a) {
            con_numero(15, lin, cor, a[0], 5);
            con_texto(21, lin, COR_CINZA, "/");
            con_numero(22, lin, cor, a[0xA0 / 4], 5);
        }
    }
    if (topo > 0) con_texto(31, LINHA_1, COR_VERDE, "^");
    if (topo + VISIVEIS < n_membros) con_texto(31, LINHA_1 + VISIVEIS - 1, COR_VERDE, "v");
    if (!n_membros) con_texto(1, 20, COR_CINZA, "(nenhum: fora do jogo?)");
    rodape("A abre   B volta", "START fecha");
}

/* ---- Laço do painel ---- */

/* Sobe/desce `sel` numa lista de n itens (dando a volta) e acerta a rolagem. */
static void mover(u16 t, int *sel, int *topo, int n) {
    if (n <= 0) { *sel = *topo = 0; return; }
    if (t & TECLA_CIMA) *sel = *sel ? *sel - 1 : n - 1;
    if (t & TECLA_BAIXO) *sel = *sel + 1 < n ? *sel + 1 : 0;
    if (*sel >= n) *sel = n - 1;
    if (*sel < *topo) *topo = *sel;
    if (*sel >= *topo + VISIVEIS) *topo = *sel - VISIVEIS + 1;
}

#define TELA_INICIO -1
#define TELA_MEMBRO -2

static void painel(void) {
    int tela = TELA_INICIO; /* ou o número da página aberta */
    int sel_inicio = 0, sel = 0, topo = 0;
    int sel_grupo = 0, topo_grupo = 0, tela_grupo = 0;
    for (;;) {
        esperar_quadro();
        con_reafirmar();
        achar_membros(); /* barato: no máximo 16 ponteiros */
        u16 t = ler_teclas();
        if (t & TECLA_START) return;

        if (tela == TELA_INICIO) {
            if (t & TECLA_B) return;
            mover(t, &sel_inicio, &topo, N_PAGINAS);
            topo = 0;
            if (t & TECLA_A) { tela = sel_inicio; sel = topo = 0; }
        } else if (tela >= 0 && paginas[tela].tipo == P_GRUPO) {
            if (t & TECLA_B) tela = TELA_INICIO;
            mover(t, &sel_grupo, &topo_grupo, n_membros);
            if ((t & TECLA_A) && sel_grupo < n_membros) {
                membro_sel = sel_grupo;
                tela_grupo = tela; /* para o B voltar à lista */
                tela = TELA_MEMBRO;
                sel = topo = 0;
            }
        } else {
            const Pagina *p = tela == TELA_MEMBRO ? &pagina_membro : &paginas[tela];
            if (t & TECLA_B) tela = tela == TELA_MEMBRO ? tela_grupo : TELA_INICIO;
            mover(t, &sel, &topo, p->n);
            const Campo *c = &p->campos[sel];
            s32 d = 0;
            if (t & TECLA_DIREITA) d += 1;
            if (t & TECLA_ESQUERDA) d -= 1;
            if (t & TECLA_R) d += 10;
            if (t & TECLA_L) d -= 10;
            u32 a = endereco(p, c);
            if (d && a) escrever(a, c, ler(a, c->formato) + d);
        }

        con_limpar();
        if (tela == TELA_INICIO) desenhar_inicio(sel_inicio);
        else if (tela == TELA_MEMBRO) {
            /* "Grupo: " + o nome, montado à mão (sem biblioteca C não há strcpy) */
            char titulo[28];
            const char *g = "Grupo: ";
            for (int i = 0; i < 8; i++) titulo[i] = g[i];
            if (membro_sel < n_membros) nome_de(membros[membro_sel], titulo + 7, 20);
            desenhar_pagina(&pagina_membro, titulo, sel, topo);
        } else if (paginas[tela].tipo == P_GRUPO) desenhar_grupo(sel_grupo, topo_grupo);
        else desenhar_pagina(&paginas[tela], paginas[tela].titulo, sel, topo);
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
