/* Valida HashResourceName contra o jogo de verdade.
 * Entrada (stdin): linhas "hash_hex nome" do _manifest.json do HERF.
 * Se a decompilação estiver certa, TODOS os hashes batem. */
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include "exo_string.h"

u32 HashResourceName(const CExoString *name);

int main(void)
{
    char line[512];
    int ok = 0, bad = 0;
    while (fgets(line, sizeof line, stdin)) {
        char name[400]; unsigned expected;
        if (sscanf(line, "%x %399s", &expected, name) != 2) continue;
        CExoString s = { NULL, name };
        u32 h = HashResourceName(&s);
        if (h == expected) ok++;
        else { bad++; if (bad < 5) printf("DIFERENTE: %s %08x != %08x\n", name, h, expected); }
    }
    printf("hashes conferidos: %d corretos, %d errados\n", ok, bad);
    return bad != 0;
}
