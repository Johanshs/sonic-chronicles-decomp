/* CExoString: a string do motor Aurora da BioWare.
 * Layout deduzido do assembly de func_020052f0 (CExoString::CStr):
 *   +0x0  vtable    (a classe tem RTTI "10CExoString", logo tem vtable)
 *   +0x4  char*     texto (pode ser NULL)
 */
#ifndef EXO_STRING_H
#define EXO_STRING_H
#include "types.h"

typedef struct CExoString {
    const void *vtable;   /* +0x0 */
    char       *text;     /* +0x4 */
} CExoString;

/* 0x020052f0 */
const char *CExoString_CStr(const CExoString *self);
#endif
