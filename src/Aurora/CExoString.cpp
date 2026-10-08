// CExoString (só o que já foi decompilado; o resto continua em assembly).
#include "Aurora/CExoString.h"

// 0x020052f0 (Thumb, 0x10 bytes)
// O `ldr r0, [r0]` do original mostra que o "" vem de um ponteiro guardado
// numa variável global, e não do endereço da string direto.
const char* CExoString::CStr() const
{
    if (text != 0)
        return text;
    return g_emptyString;
}
