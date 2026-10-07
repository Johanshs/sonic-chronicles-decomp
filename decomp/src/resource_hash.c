/* Hash dos nomes de recurso (usado pelos pacotes HERF).
 *
 * Assembly original: func_02009b78 (Thumb, 0x40 bytes)
 *     push {r3-r7, lr}
 *     ldr  r4, =0x1505          ; hash = 5381         <- constante do DJB2
 *     bl   func_020052f0        ; s = name->CStr()
 *     mov  r1, #0
 *     ldrsb r5, [r0, r1]        ; c = (signed char) s[0]
 *     ...
 *   loop:
 *     (se 0 <= c < 0x80)  ldrb r5, [r0, r5]   ; c = tabela_minusculas[c]
 *     lsl  r7, r4, #5           ; r7 = hash << 5      (hash * 32)
 *     add  r4, r7               ; hash = hash * 33
 *     add  r4, r5, r4           ; hash += c
 *     ldrsb r5, [r3, r6] ; add r3, #1 ; bne loop
 *     mov r0, r4 ; pop {...}
 *
 * Detalhe que só a leitura do assembly revela: o caractere é lido COM SINAL
 * (ldrsb). Bytes >= 0x80 não passam pela tabela e entram negativos na soma.
 * Isso não importa para nomes ASCII, mas um port fiel precisa reproduzir.
 */
#include "exo_string.h"

/* 0x020f4a50: tabela de 128 bytes que mapeia 'A'..'Z' -> 'a'..'z' */
static u8 s_toLower[128];

static void init_table(void)
{
    for (int i = 0; i < 128; i++)
        s_toLower[i] = (i >= 'A' && i <= 'Z') ? (u8)(i + 32) : (u8)i;
}

/* Nome sugerido; o original não tem símbolo. */
u32 HashResourceName(const CExoString *name)
{
    static int ready;
    if (!ready) { init_table(); ready = 1; }

    u32 hash = 5381;
    const s8 *s = (const s8 *)CExoString_CStr(name);
    for (s32 c = *s++; c != 0; c = *s++) {
        if (c >= 0 && c < 0x80)
            c = s_toLower[c];
        hash = hash * 33 + (u32)c;
    }
    return hash;
}
