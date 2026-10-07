#include "exo_string.h"

/* 0x020ef814: ponteiro global para "" (usado quando o texto é NULL) */
static const char s_empty[] = "";

/* 0x020052f0  (Thumb, 12 bytes)
 *   ldr r0, [r0, #0x4]      ; r0 = self->text
 *   cmp r0, #0x0
 *   bne fim                 ; se não for NULL, devolve
 *   ldr r0, =data_020ef814  ; senão devolve *(&ponteiro_para_vazio)
 *   ldr r0, [r0, #0x0]
 * fim: bx lr
 */
const char *CExoString_CStr(const CExoString *self)
{
    if (self->text != NULL)
        return self->text;
    return s_empty;
}
