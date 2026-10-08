/* Console de texto 32x24 na tela de baixo (motor B, camada BG0). */
#ifndef CONSOLE_H
#define CONSOLE_H

#include "ds.h"

#define CON_COLUNAS 32
#define CON_LINHAS 24

/* Cores do texto: cada uma é um banco de paleta de 16 cores (só usamos a cor 1). */
enum { COR_CINZA = 12, COR_VERDE = 13, COR_AMARELO = 14, COR_BRANCO = 15 };

/* Salva o que o jogo tinha na tela de baixo e assume a tela. Devolve 0 (e não mexe em
 * nada) se não houver VRAM de fundo ligada ao motor B. */
int con_abrir(void);
/* Põe de volta, byte a byte, tudo o que con_abrir salvou. */
void con_fechar(void);
/* Reescreve nossos registradores e a fonte. Chamado a cada quadro, porque o jogo pode
 * mexer na tela de baixo pelas interrupções enquanto o painel está aberto. */
void con_reafirmar(void);

void con_limpar(void);
void con_texto(int col, int lin, int cor, const char *s);
/* Escreve um inteiro com sinal, em decimal, alinhado à direita em `largura` colunas. */
void con_numero(int col, int lin, int cor, s32 v, int largura);

/* Espera o começo do próximo VBlank (o intervalo entre um quadro e outro). */
void esperar_quadro(void);

#endif
