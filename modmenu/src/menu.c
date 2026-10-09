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

#define VERSAO "0.10"
#define COMBO_ABRIR (TECLA_L | TECLA_R | TECLA_SELECT)

/* src/cache.s: faz o processador ver instruções do jogo que o painel trocou na RAM */
void sincronizar_codigo(u32 inicio, u32 fim);

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
    u16 via;          /* P_ESQUADRAO: se não for 0, o esquadrão + via guarda um ponteiro, e
                         o campo fica em (esse ponteiro) + endereco. 0 = no próprio esquadrão */
} Campo;

/* De onde vêm os endereços dos campos de uma página. */
enum {
    P_FIXO,      /* endereço absoluto: o campo mora sempre no mesmo lugar */
    P_ESQUADRAO, /* deslocamento dentro do esquadrão (CGamePlayerSquad), que mora no heap */
    P_MEMBRO,    /* deslocamento no vetor de atributos do personagem escolhido */
    P_GRUPO,     /* não tem campos: é a lista de personagens (n = qual lista: FONTE_*) */
    P_ACOES,     /* ações rápidas de batalha */
    P_ITENS,     /* não tem campos fixos: "dar item" e as pilhas do inventário */
    P_TRUQUES,   /* trocas de instruções do jogo na RAM, liga/desliga (os cheats de código) */
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
    {"Aneis (carteira)", 0x114, F_INT, 1, 0, 999999, 0},
    /* CHEATS.md, pasta XP: o XP é um só para o grupo todo, num objeto apontado pelo
     * esquadrão em +0x48, campo +0x50. Cada personagem converte esse número em nível pela
     * sua curva (Adv_<nome>.gda); o nível 30 pede até 2643707 (Eggman). Subir de nível
     * só acontece no fim da próxima batalha vencida, e não tem volta. */
    {"XP do grupo", 0x50, F_INT, 1, 0, 2700000, 0x48},
};

/* Atributos de um membro do grupo: deslocamentos no vetor de atributos (CHEATS.md). */
static const Campo campos_membro[] = {
    {"HP", 0x00, F_INT, 1, 0, 9999},
    {"HP maximo", 0xA0, F_INT, 1, 1, 9999},
    {"PP", 0xB0, F_FX, 1, 0, 999},
    {"PP maximo", 0xB8, F_INT, 1, 0, 999},
    /* CHEATS.md, pasta POW: posição 75 do vetor = os pontos que a tela "POW Moves" do
     * perfil gasta para subir um golpe de nível; 69 a 74 = o nível (0 a 3) de cada um
     * dos 6 golpes do personagem, na ordem da tela. */
    {"Pontos de POW", 0x12C, F_INT, 1, 0, 999},
    {"Golpe POW 1 (0-3)", 0x114, F_INT, 1, 0, 3},
    {"Golpe POW 2 (0-3)", 0x118, F_INT, 1, 0, 3},
    {"Golpe POW 3 (0-3)", 0x11C, F_INT, 1, 0, 3},
    {"Golpe POW 4 (0-3)", 0x120, F_INT, 1, 0, 3},
    {"Golpe POW 5 (0-3)", 0x124, F_INT, 1, 0, 3},
    {"Golpe POW 6 (0-3)", 0x128, F_INT, 1, 0, 3},
    {"Speed", 0x94, F_INT, 1, 0, 999},
    {"Attack (acerto)", 0x98, F_INT, 1, 0, 999},
    {"Defense (esquiva)", 0x9C, F_INT, 1, 0, 999},
    {"Power (dano)", 0xA4, F_INT, 0, 0, 999},
    {"Grit (armadura)", 0xA8, F_INT, 0, 0, 999},
    {"Luck", 0xAC, F_INT, 1, 0, 999},
    /* posição 114: quantas vezes age por rodada (Combat_BuildTurnQueue lê no começo de
     * cada rodada; Sonic 3, Tails e Rouge 2, Omega 1 no Capítulo 10) */
    {"Acoes por rodada", 0x1C8, F_INT, 1, 1, 9},
    /* posições 20 a 25: resistência a cada elemento em %, ponto fixo (100 = imune,
     * negativo = fraqueza). O dano com o elemento é multiplicado por 1 - R/100. */
    {"Resist. Fogo %", 0x50, F_FX, 1, -100, 100},
    {"Resist. Agua %", 0x54, F_FX, 1, -100, 100},
    {"Resist. Terra %", 0x58, F_FX, 1, -100, 100},
    {"Resist. Vento %", 0x5C, F_FX, 1, -100, 100},
    {"Resist. Raio %", 0x60, F_FX, 1, -100, 100},
    {"Resist. Gelo %", 0x64, F_FX, 1, -100, 100},
};

#define N(v) ((u8)(sizeof v / sizeof v[0]))
static const Pagina paginas[] = {
    {"Regras de combate (74)", campos_regras, N(campos_regras), P_FIXO},
    {"Dificuldade dinamica", campos_dificuldade, N(campos_dificuldade), P_FIXO},
    {"Aneis e XP", campos_carteira, N(campos_carteira), P_ESQUADRAO},
    {"Grupo (personagens)", 0, 0 /* FONTE_GRUPO */, P_GRUPO},
    {"Inimigos (batalha)", 0, 1 /* FONTE_INIMIGOS */, P_GRUPO},
    {"Acoes rapidas", 0, 0, P_ACOES},
    {"Itens (inventario)", 0, 0, P_ITENS},
    {"Truques (liga/desliga)", 0, 0, P_TRUQUES},
};
#define N_PAGINAS ((int)N(paginas))
/* A página de atributos de um personagem: o título é desenhado com o nome dele. */
static const Pagina pagina_membro = {"", campos_membro, N(campos_membro), P_MEMBRO};

/* ---- Achar o endereço de um campo ---- */

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

/* As listas de criaturas. O jogo guarda, em endereços fixos, listas do tipo
 * CGameObjectStorageList: {vtable, tipo, -1, quantos, capacidade, ponteiro para o vetor}.
 * Duas nos interessam:
 * - a do grupo (vetor em 0x02160B28, quantos em 0x02160B20): TODOS os que já entraram no
 *   grupo (11 no fim do jogo), não só os 4 da batalha. As posições variam: num jogo novo
 *   o Sonic está na posição 0 e a lista tem 1; num save carregado, a 0 fica vazia, o
 *   Sonic vai para a 1 e a lista tem 12. Cada um é um CGamePlayerCreature (0x020F9200);
 * - a dos inimigos (vetor em 0x02160AF8, quantos em 0x02160AF0): os da batalha atual (4
 *   Nocturne Decurion no teste); fora da batalha, quantos = 0. Cada um é um
 *   CGameCreature (0x020F5D20), com os atributos no mesmo formato.
 * Achadas no emulador (a dos inimigos, procurando quem aponta para um inimigo). Usamos o
 * "quantos" do jogo (depois dele há lixo ou criaturas de batalhas antigas, já
 * liberadas) e conferimos cada ponteiro e a vtable antes de usar: um ponteiro errado
 * faria o painel escrever em lugar aleatório. */
typedef struct {
    u32 vetor;  /* endereço fixo do ponteiro para o vetor; "quantos" fica 8 bytes antes */
    u32 vtable; /* a classe que cada criatura da lista tem que ter */
    const char *titulo, *prefixo;
} Fonte;
enum { FONTE_GRUPO, FONTE_INIMIGOS };
static const Fonte fontes[] = {
    {0x02160B28u, 0x020F9200u, "Grupo: escolha o personagem", "Grupo: "},
    {0x02160AF8u, 0x020F5D20u, "Inimigos da batalha", "Inimigo: "},
};

static u32 membros[MAX_MEMBROS];
static int n_membros;
static int fonte_atual;

static int achar_criaturas(int fonte, u32 *saida) {
    const Fonte *f = &fontes[fonte];
    int n = 0;
    u32 lista = *(volatile u32 *)f->vetor;
    s32 quantos = *(volatile s32 *)(f->vetor - 8);
    if (!ponteiro_ok(lista) || quantos <= 0) return 0;
    if (quantos > MAX_MEMBROS) quantos = MAX_MEMBROS;
    for (int i = 0; i < quantos; i++) {
        u32 c = *(volatile u32 *)(lista + 4u * i);
        if (!ponteiro_ok(c) || *(volatile u32 *)c != f->vtable) continue;
        int repetido = 0;
        for (int j = 0; j < n; j++) repetido |= saida[j] == c;
        if (!repetido) saida[n++] = c;
    }
    return n;
}

static void achar_membros(void) { n_membros = achar_criaturas(fonte_atual, membros); }

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
        if (s && c->via) {
            s = *(volatile u32 *)(s + c->via);
            if (!ponteiro_ok(s)) return 0;
        }
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

/* ---- Itens ----
 * O inventário é um CGameObjectInventory apontado pelo esquadrão (+0x40). Ele guarda uma
 * lista de pilhas (quantos em +0x2C, o vetor em +0x34); cada pilha é um CGameItem com o
 * número do item (linha de Items.gda) em +0xB8 (16 bits) e a quantidade em +0xBB (1
 * byte). Achado no emulador com o save do Capítulo 10 (61 pilhas) e conferido no código:
 * a função que tira um item do inventário (0x0202dacc) baixa exatamente esse byte. */
#define VTABLE_INVENTARIO 0x020F93DCu
#define VTABLE_ITEM 0x020F6120u
/* Quantos itens existem: a tabela Items.gda pode ganhar linhas (o item 288, Chili Dog,
 * do conteúdo novo), então o painel pergunta ao jogo em vez de supor 288. A função que
 * cria um item (0x0202dfc4) faz o mesmo: pede a tabela 22 ao gerente de tabelas
 * (0x0201f1dc(0x02109b00, 22)) e recusa um número >= linhas (método +0x18 da tabela).
 * Sem essa conferência o jogo aceitou "dar" o item 290, que não existe (visto no
 * emulador), por isso o limite vem daqui. Se algo não bater, ficamos nos 288 do jogo
 * original. O bit 0 de 0x02109a0c diz se o gerente já foi construído. */
#define ITENS_ORIGINAL 288
static int n_itens(void) {
    if (!(*(volatile u32 *)0x02109A0Cu & 1)) return ITENS_ORIGINAL;
    if (*(volatile u16 *)0x0201F1DC != 0xB570 || *(volatile u16 *)0x0201F1DE != 0x1C05) return ITENS_ORIGINAL;
    u32 (*tabela)(u32, int) = (u32 (*)(u32, int))0x0201F1DDu;
    u32 t = tabela(0x02109B00u, 22);
    if (!ponteiro_ok(t) || !ponteiro_ok(*(volatile u32 *)t)) return ITENS_ORIGINAL;
    u32 metodo = *(volatile u32 *)(*(volatile u32 *)t + 0x18);
    if (metodo < 0x02000000u || metodo >= 0x02400000u) return ITENS_ORIGINAL;
    s32 n = ((s32 (*)(u32))metodo)(t);
    return n >= ITENS_ORIGINAL && n < 4096 ? n : ITENS_ORIGINAL;
}

static u32 inventario(void) {
    u32 s = esquadrao();
    if (!s) return 0;
    u32 i = *(volatile u32 *)(s + 0x40);
    return ponteiro_ok(i) && *(volatile u32 *)i == VTABLE_INVENTARIO ? i : 0;
}

static int n_pilhas(u32 inv) {
    s32 n = *(volatile s32 *)(inv + 0x2C);
    if (n < 0 || !ponteiro_ok(*(volatile u32 *)(inv + 0x34))) return 0;
    return n > 255 ? 255 : n;
}

static u32 pilha(u32 inv, int k) {
    u32 p = *(volatile u32 *)(*(volatile u32 *)(inv + 0x34) + 4u * k);
    return ponteiro_ok(p) && *(volatile u32 *)p == VTABLE_ITEM ? p : 0;
}

/* A lista do inventário pode ter buracos: quando a última unidade de uma pilha sai, a
 * função do jogo apaga o item e põe 0 na posição, sem encolher a lista (visto no
 * emulador: depois de tirar o único POW Candy, a lista ficou com 1 posição vazia). O
 * painel mostra só as posições com item: a linha i da página é a i-ésima pilha cheia. */
static int n_cheias(u32 inv) {
    int n = n_pilhas(inv), c = 0;
    for (int k = 0; k < n; k++)
        if (pilha(inv, k)) c++;
    return c;
}

static int posicao_da(u32 inv, int i) {
    int n = n_pilhas(inv);
    for (int k = 0; k < n; k++)
        if (pilha(inv, k) && i-- == 0) return k;
    return -1;
}

/* Dar um item usando a PRÓPRIA função do jogo (0x0202dc6c), a mesma que as recompensas
 * e o roubo da Rouge chamam: ela procura uma pilha do mesmo item e soma 1, ou cria um
 * CGameItem novo e o põe no inventário. Assim o jogo fica coerente (o objeto é criado
 * como ele mesmo cria), o que não aconteceria escrevendo bytes na mão.
 * Argumentos, lidos no assembly dos chamadores: (inventário, número do item, vetor onde
 * ela anota as pilhas mexidas, marcar como "novo", 1). O vetor é um CExoArrayList
 * {quantos, capacidade, dados}; começa zerado e depois liberamos a memória dele com a
 * função do jogo (0x020146d8). Antes de chamar, conferimos os primeiros bytes da função
 * (push {r4-r7, lr}; sub sp, #0x2c): se não baterem, não é a ROM que conhecemos. */
static int dar_item(int id) {
    u32 inv = inventario();
    if (!inv || id < 0 || id >= n_itens()) return 0;
    if (*(volatile u16 *)0x0202DC6C != 0xB5F0 || *(volatile u16 *)0x0202DC6E != 0xB08B) return 0;
    if (*(volatile u16 *)0x020146D8 != 0xB510) return 0; /* push {r4, lr} */
    int (*adicionar)(u32, int, u32 *, int, int) = (int (*)(u32, int, u32 *, int, int))0x0202DC6Du;
    void (*liberar)(u32 *) = (void (*)(u32 *))0x020146D9u; /* +1: código Thumb */
    u32 vetor[3];
    vetor[0] = vetor[1] = vetor[2] = 0;
    int ok = adicionar(inv, id, vetor, 0, 1);
    liberar(vetor);
    return ok;
}

/* Tirar 1 unidade de uma pilha usando a função do jogo (0x0202dacc), a mesma que o
 * combate chama quando um item é usado. Argumentos, lidos no assembly dos chamadores:
 * (inventário, posição da pilha na lista). Com mais de 1 unidade, ela só desconta 1;
 * com 1, apaga o CGameItem, tira a pilha da lista e, se o item for de história, desliga
 * a marca (plot) que diz que o grupo o tem, como o jogo faz ao entregar um item.
 * Os 4 primeiros meios-palavras são conferidos (os 2 primeiros sozinhos são iguais aos
 * da função de atributos 0x02007e60). */
static int tirar_item(int k) {
    u32 inv = inventario();
    if (!inv || k < 0 || k >= n_pilhas(inv) || !pilha(inv, k)) return 0;
    volatile u16 *f = (volatile u16 *)0x0202DACC;
    if (f[0] != 0xB5F8 || f[1] != 0xB084 || f[2] != 0x1C05 || f[3] != 0x6AE8) return 0;
    int (*tirar)(u32, int) = (int (*)(u32, int))0x0202DACDu;
    /* com o truque "Itens nao acabam" ligado, a função não desconta: desligamos só
     * durante a chamada (as instruções ficam nesta mesma função, em 0x0202DB4C) */
    volatile u16 *q = (volatile u16 *)0x0202DB4C;
    int truque = q[0] == 0x46C0 && q[1] == 0x46C0;
    if (truque) { q[0] = 0xDD07; q[1] = 0x1E49; sincronizar_codigo(0x0202DB4C, 0x0202DB50); }
    int ok = tirar(inv, k);
    if (truque) { q[0] = q[1] = 0x46C0; sincronizar_codigo(0x0202DB4C, 0x0202DB50); }
    return ok;
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
        if (a) { con_numero(20, lin, cor, ler(a, c->formato), 7); vazio = 0; }
        else con_texto(20, lin, COR_CINZA, "   ---");
        con_texto(27, lin, COR_CINZA, c->conferido ? "emu" : "est");
    }
    /* setas de rolagem quando a lista não cabe */
    if (topo > 0) con_texto(31, LINHA_1, COR_VERDE, "^");
    if (topo + VISIVEIS < p->n) con_texto(31, LINHA_1 + VISIVEIS - 1, COR_VERDE, "v");
    if (vazio) con_texto(1, 20, COR_CINZA, "(nao achado: fora do jogo?)");
    if (sel < p->n && p->campos[sel].maximo >= 100000)
        rodape("<> -1000/+1000  L R -/+100000", "B volta   START fecha");
    else rodape("<> -1/+1   L R -10/+10", "B volta   START fecha");
}

/* A lista de personagens: nome e HP de cada um, para escolher qual abrir. */
static void desenhar_grupo(int sel, int topo) {
    cabecalho(fontes[fonte_atual].titulo);
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
    if (!n_membros)
        con_texto(1, 20, COR_CINZA, fonte_atual == FONTE_INIMIGOS ? "(nenhum: fora da batalha?)"
                                                                   : "(nenhum: fora do jogo?)");
    rodape("A abre   B volta", "START fecha");
}

/* O nome de um item, pelo jogo: o mesmo caminho da mensagem "você ganhou um item".
 * 0x020c2cfc monta um "ItemInfo" (0x8C bytes) a partir da linha de Items.gda; o nome é
 * o primeiro campo, um texto localizado {número no TLK, CExoString, marcas}; 0x0201cad0
 * busca o texto no TLK (lê do cartão, se preciso) e devolve o CExoString, que é
 * {vtable, ponteiro para as letras, tamanho}; 0x020c2d48 libera tudo. Como ler do
 * cartão é lento, guardamos os últimos 16 nomes. Os primeiros bytes das três funções
 * são conferidos antes, como em dar_item(). */
#define NOMES_GUARDADOS 16
#define NOME_MAX 14
static s16 nome_id[NOMES_GUARDADOS];
static char nome_txt[NOMES_GUARDADOS][NOME_MAX + 1];
static int nome_prox;

static void esquecer_nomes(void) {
    for (int i = 0; i < NOMES_GUARDADOS; i++) nome_id[i] = -1;
}

static const char *nome_item(int id) {
    for (int i = 0; i < NOMES_GUARDADOS; i++)
        if (nome_id[i] == id) return nome_txt[i];
    if (*(volatile u16 *)0x020C2CFC != 0xB538 || *(volatile u16 *)0x020C2D48 != 0xB510 ||
        *(volatile u16 *)0x0201CAD0 != 0xB510)
        return "?";
    void (*montar)(u32 *, int) = (void (*)(u32 *, int))0x020C2CFDu;
    u32 *(*texto)(u32 *) = (u32 * (*)(u32 *))0x0201CAD1u;
    void (*desmontar)(u32 *) = (void (*)(u32 *))0x020C2D49u;
    u32 info[40]; /* 160 bytes; o ItemInfo usa 0x8C */
    montar(info, id);
    u32 *cexo = texto(info);
    int slot = nome_prox;
    nome_prox = (nome_prox + 1) % NOMES_GUARDADOS;
    char *dst = nome_txt[slot];
    int n = 0;
    u32 letras = cexo ? cexo[1] : 0;
    if (letras >= 0x02000000u && letras < 0x023FFFF0u)
        while (n < NOME_MAX) {
            char ch = *(volatile char *)(letras + n);
            if (ch < 0x20 || ch > 0x7E) break;
            dst[n++] = ch;
        }
    if (!n) { const char *s = "(sem nome)"; while (s[n]) { dst[n] = s[n]; n++; } }
    dst[n] = 0;
    desmontar(info);
    nome_id[slot] = (s16)id;
    return dst;
}

/* Página de itens: a linha 0 dá um item pelo número; as outras são as pilhas. */
static int id_dar = 0;
static const char *aviso_item = "";
static int id_aviso = 0;   /* o item da última ação ("dado!", "tirado!") */

static void desenhar_itens(int sel, int topo) {
    cabecalho("Itens (inventario)");
    u32 inv = inventario();
    int n = inv ? n_cheias(inv) : 0;
    con_texto(1, 3, COR_CINZA, "item            num  qtd");
    for (int i = topo; i <= n && i < topo + VISIVEIS; i++) {
        int lin = LINHA_1 + i - topo;
        int cor = i == sel ? COR_AMARELO : COR_BRANCO;
        con_texto(0, lin, cor, i == sel ? ">" : " ");
        if (i == 0) {
            con_texto(1, lin, cor, "Dar 1 (A), item");  /* nas pilhas, A tira 1 */
            con_numero(17, lin, cor, id_dar, 3);
            continue;
        }
        int k = posicao_da(inv, i - 1);
        u32 p = k >= 0 ? pilha(inv, k) : 0;
        if (!p) { con_texto(1, lin, COR_CINZA, "?"); continue; }
        s16 id = *(volatile s16 *)(p + 0xB8);
        con_texto(1, lin, cor, nome_item(id));
        con_numero(17, lin, cor, id, 3);
        con_numero(20, lin, cor, *(volatile u8 *)(p + 0xBB), 4);
    }
    if (topo > 0) con_texto(31, LINHA_1, COR_VERDE, "^");
    if (topo + VISIVEIS < n + 1) con_texto(31, LINHA_1 + VISIVEIS - 1, COR_VERDE, "v");
    if (!inv) con_texto(1, 20, COR_CINZA, "(inventario nao achado)");
    else {
        con_texto(1, 20, COR_CINZA, "item");
        /* a linha 20 diz de que item se trata: o da última ação, enquanto o aviso dela
         * estiver na tela (a pilha tirada pode ter sumido); senão, o da linha escolhida */
        int id = id_dar;
        if (aviso_item[0]) id = id_aviso;
        else if (sel > 0) {
            int k = posicao_da(inv, sel - 1);
            u32 p = k >= 0 ? pilha(inv, k) : 0;
            if (p) id = *(volatile s16 *)(p + 0xB8);
        }
        con_numero(5, 20, COR_CINZA, id, 3);
        con_texto(9, 20, COR_BRANCO, nome_item(id));
        con_texto(24, 20, COR_VERDE, aviso_item);
    }
    rodape(sel == 0 ? "<> -1/+1  L R -10/+10  A da 1" : "<> -1/+1  L R -10/+10  A tira 1",
           "B volta   START fecha");
}

static void teclas_itens(u16 t, int sel) {
    s32 d = 0;
    if (t & TECLA_DIREITA) d += 1;
    if (t & TECLA_ESQUERDA) d -= 1;
    if (t & TECLA_R) d += 10;
    if (t & TECLA_L) d -= 10;
    u32 inv = inventario();
    if (sel == 0) {
        id_dar += d;
        if (id_dar < 0) id_dar = 0;
        if (id_dar >= n_itens()) id_dar = n_itens() - 1;
        if (t & TECLA_A) {
            id_aviso = id_dar;
            aviso_item = dar_item(id_dar) ? "dado!" : "recusou";
        }
        else if (d) aviso_item = "";
        return;
    }
    int k = inv ? posicao_da(inv, sel - 1) : -1;
    if (k < 0) return;
    if (t & TECLA_A) {
        id_aviso = *(volatile s16 *)(pilha(inv, k) + 0xB8);
        aviso_item = tirar_item(k) ? "tirado!" : "recusou";
        return;
    }
    if (d) aviso_item = "";
    if (!d) return;
    u32 p = pilha(inv, k);
    if (!p) return;
    s32 q = *(volatile u8 *)(p + 0xBB) + d;
    if (q < 1) q = 1;   /* 0 deixaria uma pilha vazia: para tirar, A chama o jogo */
    if (q > 99) q = 99;
    *(volatile u8 *)(p + 0xBB) = (u8)q;
}

/* ---- Ações rápidas ----
 * "Curar" e "HP 1" escrevem nos mesmos atributos das páginas do grupo e dos inimigos,
 * em todos de uma vez. Quem está nocauteado (HP <= 0) não é mexido.
 * No jogo, o nocaute não é só o HP: um inimigo com HP posto em 0 escrevendo o número
 * CONTINUA lutando (visto no emulador). Quem nocauteia é a função que o jogo usa para
 * mudar um atributo, 0x02007e60 (atributos, criatura, número do atributo, &valor em
 * ponto fixo). Depois de mudar o valor ela confere os limites da tabela de atributos e,
 * se o HP chegou ao mínimo, dispara o nocaute (atributo 36 = 2 etc.). Todo golpe passa
 * por ela (a pilha de chamadas foi vista no emulador: Combat_ApplyDamage ->
 * EffectList_Add -> EffectFn_ModifyAttribute -> 0x02007e60). "Nocautear inimigos"
 * chama essa função com HP 0, como um golpe faria.
 * Para reviver alguém do grupo, dê um Revival Ring ou um Ring of Life (página Itens). */
static const char *const acoes[] = {
    "Curar o grupo (HP e PP cheios)",
    "Inimigos com HP 1",
    "Nocautear inimigos (pelo jogo)",
    "Chao: os seus no nivel Max",
    "Chao: ganhar os 45 (nivel Max)",
};
#define N_ACOES ((int)(sizeof acoes / sizeof acoes[0]))
static const char *aviso_acao = "";

/* Muda um atributo pela função do próprio jogo (veja acima). Os atributos ficam na
 * criatura + 8 (o vetor de valores que as páginas mostram é o de criatura + 0x1C, o
 * campo +0x14 desse objeto). Argumentos conferidos no emulador, nos golpes de uma
 * batalha: (criatura + 8, criatura, 0, &HP novo << 12) e um quinto, na pilha: com 0, a
 * função confere os limites e avisa a criatura (é o aviso que nocauteia); com outro
 * valor, só muda o número. Na primeira tentativa o quinto ficou de fora, a pilha tinha
 * lixo, e o HP foi a 0 sem nocaute: igual a escrever o número na mão. Antes de chamar,
 * conferimos os primeiros bytes (push {r3-r7, lr}; sub sp, #0x10). */
static int definir_atributo(u32 criatura, int numero, s32 valor_fx) {
    if (*(volatile u16 *)0x02007E60 != 0xB5F8 || *(volatile u16 *)0x02007E62 != 0xB084) return 0;
    void (*definir)(u32, u32, int, s32 *, int) = (void (*)(u32, u32, int, s32 *, int))0x02007E61u;
    s32 v = valor_fx;
    definir(criatura + 8, criatura, numero, &v, 0);
    return 1;
}

/* Os Chao (CHEATS.md, pasta Chao): 45 registros de 10 bytes a partir do esquadrão +
 * 0x424, na ordem do número: byte 0 = o número (0 a 44), byte 1 = nível (0 = não tem,
 * 3 = Max), byte 2 = cópias. O jardim conta quem tem cópias, então "ganhar" põe nível 3
 * e pelo menos 1 cópia. Os 40 a 44 só chegavam por troca sem fio com outro DS.
 * Conferimos o byte 0 de cada registro antes: se algum não bate, nada é escrito. */
#define N_CHAO 45
static int mexer_chao(int ganhar_todos) {
    u32 s = esquadrao();
    if (!s) return -1;
    volatile u8 *c = (volatile u8 *)(s + 0x424);
    for (int i = 0; i < N_CHAO; i++)
        if (c[10 * i] != i) return -1;
    int feitos = 0;
    for (int i = 0; i < N_CHAO; i++) {
        volatile u8 *r = c + 10 * i;
        if (r[2] == 0 && !ganhar_todos) continue; /* não tem este Chao */
        if (r[2] == 0) r[2] = 1;
        r[1] = 3;
        feitos++;
    }
    return feitos;
}

static void fazer_acao(int a) {
    if (a >= 3) {
        int f = mexer_chao(a == 4);
        aviso_acao = f < 0 ? "recusou (Chao nao achados)" : f ? "feito" : "nenhum Chao";
        return;
    }
    u32 cs[MAX_MEMBROS];
    int n = achar_criaturas(a == 0 ? FONTE_GRUPO : FONTE_INIMIGOS, cs);
    int feitos = 0, recusou = 0;
    for (int i = 0; i < n; i++) {
        s32 *at = atributos_de(cs[i]);
        if (!at || at[0] <= 0) continue;
        if (a == 0) {
            at[0] = at[0xA0 / 4];              /* HP = HP máximo */
            at[0xB0 / 4] = at[0xB8 / 4] << 12; /* PP (ponto fixo) = PP máximo */
        } else if (a == 1) {
            at[0] = 1;
        } else if (!definir_atributo(cs[i], 0, 0)) {
            recusou = 1;
            break;
        }
        feitos++;
    }
    aviso_acao = recusou ? "recusou (funcao do jogo nao bate)" : feitos ? "feito" : "ninguem para mudar";
}

static void desenhar_acoes(int sel) {
    cabecalho("Acoes rapidas");
    for (int i = 0; i < N_ACOES; i++) {
        int cor = i == sel ? COR_AMARELO : COR_BRANCO;
        con_texto(0, LINHA_1 + i, cor, i == sel ? ">" : " ");
        con_texto(1, LINHA_1 + i, cor, acoes[i]);
    }
    con_texto(1, LINHA_1 + N_ACOES + 1, COR_VERDE, aviso_acao);
    con_texto(0, 16, COR_CINZA, "Nocauteados nao sao curados:");
    con_texto(0, 17, COR_CINZA, "use um item de reviver.");
    con_texto(0, 18, COR_CINZA, "Nocautear: o jogo derruba os");
    con_texto(0, 19, COR_CINZA, "inimigos como num golpe.");
    rodape("A faz", "B volta   START fecha");
}

/* ---- Truques: instruções do jogo trocadas na RAM (os cheats de código) ----
 * Os cheats de código do Action Replay (docs/CHEATS.md) trocam algumas instruções do jogo
 * a cada quadro. O painel faz a mesma troca uma vez, quando você liga, e desfaz quando
 * desliga. O código do jogo é recarregado do cartão a cada boot, então tudo volta ao
 * normal ao religar o DS (nada disto vai para o save).
 * Cada truque é uma lista de endereços (meias-palavras de 16 bits, instruções Thumb) e,
 * para cada estado, o valor de cada uma; o estado 0 é o original do jogo. O estado atual
 * é LIDO da memória: se não bater com nenhum (um cheat do cartão mexeu, ou outra versão
 * do jogo), o painel mostra "?" e não mexe. Endereços e valores conferidos contra o ARM9
 * da YWSE; o efeito de cada um foi medido no emulador pela sessão dos cheats. */
typedef struct {
    const char *nome;
    u8 n_trocas, n_estados;
    const u32 *enderecos;
    const u16 *valores;           /* n_estados x n_trocas */
    const char *const *rotulos;   /* um por estado */
} Truque;


static const char *const rotulos_lig[] = {"desligado", "LIGADO"};
static const char *const rotulos_aneis[] = {"x1", "x2", "x5", "x10"};
static const char *const rotulos_andar[] = {"x1", "x2", "x4"};

/* Itens não acabam: na função que tira um item (0x0202dacc), "ble apagar" e "qtd - 1"
 * viram "não faz nada". Atenção: vender na loja também passa por ela (vender vira
 * dinheiro infinito), e a opção "tirar" da página Itens desliga isto por um instante. */
static const u32 end_itens[] = {0x0202DB4C, 0x0202DB4E};
static const u16 val_itens[] = {0xDD07, 0x1E49, 0x46C0, 0x46C0};
/* Pegar todos os anéis da área: os dois testes de distância (X e Y) até o Sonic */
static const u32 end_coletar[] = {0x02017A56, 0x02017A88};
static const u16 val_coletar[] = {0xD035, 0xD01C, 0x46C0, 0x46C0};
/* Loja de graça: o botão "Buy Item" acende sempre, a compra não confere nem desconta */
static const u32 end_loja[] = {0x020B2EC0, 0x020B3AD0, 0x020B3AD2};
static const u16 val_loja[] = {0xDC00, 0xDB15, 0x1A51, 0x46C0, 0x46C0, 0x1C11};
/* POW sem gastar pontos: a loja de golpes não confere nem desconta os pontos */
static const u32 end_pow[] = {0x0209451C, 0x0209457A};
static const u16 val_pow[] = {0xDC11, 0x1B01, 0x46C0, 0x1C01};
/* Anéis por anel pego: "carteira + 1" vira + 2, + 5 ou + 10 (adds r1, #N) */
static const u32 end_aneis[] = {0x02017648};
static const u16 val_aneis[] = {0x1C49, 0x3102, 0x3105, 0x310A};
/* Andar pelo direcional: veja direcional() abaixo. O estado LIGADO é um "bl" para uma
 * função do painel, então os dois valores são calculados quando o painel começa. */
static const u32 end_direcional[] = {0x0204D174, 0x0204D176};
static u16 val_direcional[] = {0xF7B5, 0xFAF8, 0, 0};
/* Velocidade de andar: o tempo do quadro em ms << 12 vira << 13 ou << 14 */
static const u32 end_andar[] = {0x02034B92};
static const u16 val_andar[] = {0x0320, 0x0360, 0x03A0};

#define T(nome, e, v, r) {nome, (u8)(sizeof e / sizeof e[0]), \
    (u8)(sizeof v / sizeof v[0] / (sizeof e / sizeof e[0])), e, v, r}
static const Truque truques[] = {
    T("Itens nao acabam", end_itens, val_itens, rotulos_lig),
    T("Pegar aneis da area", end_coletar, val_coletar, rotulos_lig),
    T("Loja de graca", end_loja, val_loja, rotulos_lig),
    T("POW sem gastar pontos", end_pow, val_pow, rotulos_lig),
    T("Aneis por anel", end_aneis, val_aneis, rotulos_aneis),
    T("Andar mais rapido", end_andar, val_andar, rotulos_andar),
    T("Andar pelo direcional", end_direcional, val_direcional, rotulos_lig),
};
#undef T
#define N_TRUQUES ((int)(sizeof truques / sizeof truques[0]))
static const char *aviso_truque = "";

/* ---- Andar pelo direcional (e pelo analógico do 3DS) ----
 * Na exploração o jogo só anda pela caneta. A cada quadro, a função que transforma o
 * toque em destino (0x0204d120) pergunta ao objeto da tela de toque (0x02109ab0) "a
 * caneta está na tela, e onde?" chamando 0x02002768(objeto, &x, &y), que devolve
 * objeto[4] (tocando) e copia objeto[2] e objeto[3]. Se sim, ela converte o ponto da tela
 * em ponto do mapa (câmera - (128, 96) + toque), vira o grupo para lá e manda andar; a
 * velocidade cresce com a distância entre o Sonic e a caneta.
 * O truque troca essa chamada (o "bl" em 0x0204d174) por uma chamada a direcional():
 * com a caneta na tela, responde o mesmo que o jogo; sem caneta e com o direcional
 * apertado, responde "tocando" num ponto a DISTANCIA pixels do Sonic, na direção das
 * setas. O resto (virar, andar, colidir, abrir portas) continua sendo o jogo.
 * No 3DS, em modo DS, o analógico chega ao jogo como o direcional, então serve também.
 * Só esta função pergunta pelo direcional: o toque de verdade, que os botões da tela e
 * as conversas usam, não muda. */
#define TOQUE_OBJETO 0x02109AB0u
#define MODE_SWITCHER 0x02109BA0u
#define MODE_SWITCHER_PRONTO (*(volatile u32 *)0x02109A08u) /* bit 0: já construído */
#define DISTANCIA 72

u32 direcional(volatile u32 *toque, u32 *x, u32 *y) {
    if (toque[4]) {
        *x = toque[2];
        *y = toque[3];
        return toque[4];
    }
    u16 k = teclas_agora();
    int dx = !!(k & TECLA_DIREITA) - !!(k & TECLA_ESQUERDA);
    int dy = !!(k & TECLA_BAIXO) - !!(k & TECLA_CIMA);
    if (!dx && !dy) return 0;
    /* Onde o Sonic está NA TELA: posição no mapa menos o canto da câmera, como a função
     * do jogo faz ao contrário (0x0204d23e: modo atual -> câmera, +0x30 e +0x38). Perto
     * da borda do mapa a câmera para e o Sonic sai do centro, por isso não dá para
     * supor o centro. */
    if (!(MODE_SWITCHER_PRONTO & 1)) return 0;
    u32 grupo = esquadrao();
    if (!grupo) return 0;
    u32 lugar = *(volatile u32 *)(grupo + 0x34);
    if (!ponteiro_ok(lugar)) return 0;
    u32 (*modo_atual)(u32) = (u32 (*)(u32))0x020310B5;
    u32 modo = modo_atual(MODE_SWITCHER);
    if (!ponteiro_ok(modo)) return 0;
    u32 (*camera_do_modo)(u32) = (u32 (*)(u32))(*(volatile u32 *)(*(volatile u32 *)modo + 0x1C));
    u32 cam = camera_do_modo(modo);
    if (!ponteiro_ok(cam)) return 0;
    s32 sx = (*(volatile s32 *)(lugar + 4) - *(volatile s32 *)(cam + 0x30)) / 4096 + 128;
    s32 sy = (*(volatile s32 *)(lugar + 8) - *(volatile s32 *)(cam + 0x38)) / 4096 + 96;
    /* na diagonal, 72 x 0,7 em cada eixo: a mesma distância (e a mesma velocidade) */
    s32 passo = dx && dy ? DISTANCIA * 7 / 10 : DISTANCIA;
    sx += dx * passo;
    sy += dy * passo;
    if (sx < 0) sx = 0;
    if (sx > 255) sx = 255;
    if (sy < 0) sy = 0;
    if (sy > 191) sy = 191;
    *x = (u32)sx;
    *y = (u32)sy;
    return 1;
}

/* Um "bl" Thumb de `de` para `para`: duas meias-palavras (F000 | parte alta, F800 | baixa) */
static void codificar_bl(u32 de, u32 para, u16 *meias) {
    s32 d = (s32)((para & ~1u) - (de + 4));
    meias[0] = (u16)(0xF000 | ((d >> 12) & 0x7FF));
    meias[1] = (u16)(0xF800 | ((d >> 1) & 0x7FF));
}

static int estado_truque(const Truque *t);
static void por_truque(const Truque *t, int e);

/* Na primeira volta do jogo: calcula o "bl" e liga o direcional (se o original estiver
 * lá; em outra versão do jogo, ou na ROM de teste, fica "?" e nada muda). */
static void preparar_direcional(void) {
    static int pronto;
    if (pronto) return;
    pronto = 1;
    codificar_bl(end_direcional[0], (u32)direcional, &val_direcional[2]);
    const Truque *q = &truques[N_TRUQUES - 1];
    if (estado_truque(q) == 0) por_truque(q, 1);
}

static int estado_truque(const Truque *t) {
    for (int e = 0; e < t->n_estados; e++) {
        int ok = 1;
        for (int k = 0; k < t->n_trocas && ok; k++)
            ok = *(volatile u16 *)t->enderecos[k] == t->valores[e * t->n_trocas + k];
        if (ok) return e;
    }
    return -1;
}

static void por_truque(const Truque *t, int e) {
    u32 menor = 0xFFFFFFFFu, maior = 0;
    for (int k = 0; k < t->n_trocas; k++) {
        u32 a = t->enderecos[k];
        *(volatile u16 *)a = t->valores[e * t->n_trocas + k];
        if (a < menor) menor = a;
        if (a + 2 > maior) maior = a + 2;
    }
    sincronizar_codigo(menor, maior);
}

static void teclas_truques(u16 t, int sel) {
    int d = 0;
    if (t & (TECLA_DIREITA | TECLA_A)) d = 1;
    if (t & TECLA_ESQUERDA) d = -1;
    if (!d) return;
    const Truque *q = &truques[sel];
    int e = estado_truque(q);
    if (e < 0) { aviso_truque = "mexido por outro cheat: nao mexo"; return; }
    e += d;
    if (e < 0) e = q->n_estados - 1;
    if (e >= q->n_estados) e = 0;
    por_truque(q, e);
    aviso_truque = "";
}

static void desenhar_truques(int sel) {
    cabecalho("Truques (liga/desliga)");
    for (int i = 0; i < N_TRUQUES; i++) {
        int cor = i == sel ? COR_AMARELO : COR_BRANCO;
        int e = estado_truque(&truques[i]);
        con_texto(0, LINHA_1 + i, cor, i == sel ? ">" : " ");
        con_texto(1, LINHA_1 + i, cor, truques[i].nome);
        con_texto(23, LINHA_1 + i, e > 0 ? COR_VERDE : cor, e < 0 ? "?" : truques[i].rotulos[e]);
    }
    con_texto(1, LINHA_1 + N_TRUQUES + 1, COR_VERDE, aviso_truque);
    con_texto(0, 15, COR_CINZA, "Trocam instrucoes do jogo na");
    con_texto(0, 16, COR_CINZA, "memoria. Desligar desfaz. Ao");
    con_texto(0, 17, COR_CINZA, "religar o DS, tudo volta ao");
    con_texto(0, 18, COR_CINZA, "normal. Nao use junto com o");
    con_texto(0, 19, COR_CINZA, "mesmo cheat ligado no cartao.");
    rodape("<> ou A troca o estado", "B volta   START fecha");
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
            if (t & TECLA_A) {
                tela = sel_inicio;
                sel = topo = 0;
                aviso_item = aviso_acao = aviso_truque = "";
                esquecer_nomes();
                if (paginas[tela].tipo == P_GRUPO) {
                    fonte_atual = paginas[tela].n;
                    sel_grupo = topo_grupo = 0;
                }
            }
        } else if (tela >= 0 && paginas[tela].tipo == P_ITENS) {
            if (t & TECLA_B) tela = TELA_INICIO;
            u32 inv = inventario();
            int antes = sel;
            mover(t, &sel, &topo, 1 + (inv ? n_cheias(inv) : 0));
            if (sel != antes) aviso_item = "";
            teclas_itens(t, sel);
            /* tirar a última unidade some com a pilha: a seleção não pode passar do fim */
            int n_linhas = 1 + (inv ? n_cheias(inv) : 0);
            if (sel >= n_linhas) sel = n_linhas - 1;
            if (topo > sel) topo = sel;
        } else if (tela >= 0 && paginas[tela].tipo == P_TRUQUES) {
            if (t & TECLA_B) tela = TELA_INICIO;
            int antes = sel;
            mover(t, &sel, &topo, N_TRUQUES);
            if (sel != antes) aviso_truque = "";
            teclas_truques(t, sel);
        } else if (tela >= 0 && paginas[tela].tipo == P_ACOES) {
            if (t & TECLA_B) tela = TELA_INICIO;
            mover(t, &sel, &topo, N_ACOES);
            if (t & TECLA_A) fazer_acao(sel);
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
            /* números grandes (anéis, XP) andam de 1000 e de 100000; os outros, de 1 e 10 */
            s32 passo = c->maximo >= 100000 ? 1000 : 1;
            if (t & TECLA_DIREITA) d += passo;
            if (t & TECLA_ESQUERDA) d -= passo;
            if (t & TECLA_R) d += passo * (passo > 1 ? 100 : 10);
            if (t & TECLA_L) d -= passo * (passo > 1 ? 100 : 10);
            u32 a = endereco(p, c);
            if (d && a) escrever(a, c, ler(a, c->formato) + d);
        }

        con_limpar();
        if (tela == TELA_INICIO) desenhar_inicio(sel_inicio);
        else if (tela == TELA_MEMBRO) {
            /* "Grupo: " + o nome, montado à mão (sem biblioteca C não há strcpy) */
            char titulo[32];
            const char *g = fontes[fonte_atual].prefixo;
            int k = 0;
            while (g[k]) { titulo[k] = g[k]; k++; }
            titulo[k] = 0;
            if (membro_sel < n_membros) nome_de(membros[membro_sel], titulo + k, 20);
            desenhar_pagina(&pagina_membro, titulo, sel, topo);
        } else if (paginas[tela].tipo == P_GRUPO) desenhar_grupo(sel_grupo, topo_grupo);
        else if (paginas[tela].tipo == P_ITENS) desenhar_itens(sel, topo);
        else if (paginas[tela].tipo == P_ACOES) desenhar_acoes(sel);
        else if (paginas[tela].tipo == P_TRUQUES) desenhar_truques(sel);
        else desenhar_pagina(&paginas[tela], paginas[tela].titulo, sel, topo);
    }
}

/* Chamado pelo gancho uma vez por volta do laço. Precisa ser barato quando o painel está
 * fechado: é só uma leitura de registrador e uma comparação. Devolve 1 se o painel
 * abriu (e o jogo ficou parado), para o gancho poder acertar o relógio do jogo. */
int modmenu_quadro(void) {
    preparar_direcional();
    if ((teclas_agora() & COMBO_ABRIR) != COMBO_ABRIR) return 0;
    if (!con_abrir()) return 0;
    teclas_antes = teclas_agora(); /* o combo de abrir não conta como tecla nova */
    repete_quadros = 0;
    painel();
    esperar_soltar(); /* o jogo não deve ver o START/B que fechou o painel */
    con_fechar();
    return 1;
}
