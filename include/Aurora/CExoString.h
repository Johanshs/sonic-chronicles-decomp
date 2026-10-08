// CExoString: a string do motor Aurora da BioWare.
// Layout deduzido do assembly de CExoString::CStr (0x020052f0):
//   +0x0  vtable  (a classe tem RTTI "10CExoString", logo tem vtable)
//   +0x4  char*   texto (pode ser NULL)
#ifndef AURORA_CEXOSTRING_H
#define AURORA_CEXOSTRING_H

class CExoString {
public:
    void* vtable;   // +0x0  (ainda não declaramos os métodos virtuais)
    char* text;     // +0x4

    const char* CStr() const;
};

// 0x020ef814: ponteiro global para "" (CStr devolve isto quando text é NULL)
extern const char* const g_emptyString;

#endif
