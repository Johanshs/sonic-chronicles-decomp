// Hash dos nomes de recurso dos pacotes HERF: DJB2 sem diferenciar
// maiúsculas. Versão portável e testada contra 7893 nomes reais:
// decomp/src/resource_hash.c. Esta aqui é a "matching": compila para os
// mesmos bytes do jogo.
#include "Aurora/CExoString.h"

typedef unsigned char u8;
typedef unsigned int u32;

extern u8 __lower_map[];    // 0x020f4a50: tabela 'A'..'Z' -> 'a'..'z' (128 bytes, MSL)

// O tolower do MSL só para ASCII. O `||` com `?:` é o que gera, no original,
// o padrão "r7 = 1; se 0 <= c < 0x80 então r7 = 0; se r7 == 0, c = tab[c]".
inline int tolower_ascii(int c)
{
    return ((c < 0) || (c >= 0x80)) ? c : (int)__lower_map[c];
}

// 0x02009b78 (Thumb, 0x44 bytes)
// Com tudo numa expressão só, a última soma sai com os operandos trocados
// (`add r4, r4, r5` em vez de `add r4, r5, r4`). A variável `l` resolve.
u32 HashResourceName(const CExoString& name)
{
    u32 hash = 5381;
    const char* s = name.CStr();
    for (char c = *s++; c != 0; c = *s++) {
        int l = tolower_ascii(c);
        hash = (hash << 5) + hash + l;
    }
    return hash;
}
