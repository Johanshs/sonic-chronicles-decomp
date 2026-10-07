#include <stdio.h>
#include <string.h>
#include "types.h"
const char *GetTlkFileForLanguage(u8 language);
int main(void)
{
    const char *esperado[] = {"strings.tlk", "strings.tlk", "strings_fr-fr.tlk",
                              "strings_de-de.tlk", "strings_it-it.tlk", "strings_es-es.tlk", "strings.tlk"};
    int bad = 0;
    for (int i = 0; i < 7; i++) {
        const char *r = GetTlkFileForLanguage((u8)i);
        printf("idioma %d -> %s\n", i, r);
        bad += strcmp(r, esperado[i]) != 0;
    }
    return bad;
}
