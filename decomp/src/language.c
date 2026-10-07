/* Escolha do arquivo de textos pelo idioma do console.
 *
 * Trecho de func_020148c8 (função grande de inicialização do jogo, 0x2bc bytes).
 * Aqui reescrevemos só a parte do idioma; o resto da função inicializa
 * singletons (CRules, CPlotManager, CTlkTable, CStringDisplayManager...).
 *
 *     add  r0, sp, #0x64
 *     bl   func_020d9894        ; OS_GetOwnerInfo(&info)   (NitroSDK)
 *     ldrb r0, [sp, #0x64]      ; info.language
 *     cmp  r0, #5 ; bhi default
 *     ...tabela de saltos (switch) com 6 casos...
 *
 * OS_GetOwnerInfo lê as configurações gravadas no firmware do DS (idioma,
 * nome, aniversário). Os 3 bits baixos do campo de idioma são:
 *   0 japonês, 1 inglês, 2 francês, 3 alemão, 4 italiano, 5 espanhol
 */
#include "types.h"

enum OSLanguage {
    OS_LANGUAGE_JAPANESE = 0, OS_LANGUAGE_ENGLISH = 1, OS_LANGUAGE_FRENCH = 2,
    OS_LANGUAGE_GERMAN   = 3, OS_LANGUAGE_ITALIAN = 4, OS_LANGUAGE_SPANISH = 5,
};

const char *GetTlkFileForLanguage(u8 language)
{
    switch (language) {
    case OS_LANGUAGE_FRENCH:  return "strings_fr-fr.tlk";  /* 0x020f5ea0 */
    case OS_LANGUAGE_GERMAN:  return "strings_de-de.tlk";  /* 0x020f5ec8 */
    case OS_LANGUAGE_ITALIAN: return "strings_it-it.tlk";  /* 0x020f5eb4 */
    case OS_LANGUAGE_SPANISH: return "strings_es-es.tlk";  /* 0x020f5edc */
    default:                  return "strings.tlk";        /* 0x020f5ef0: JP e EN */
    }
}
