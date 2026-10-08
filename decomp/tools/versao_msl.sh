#!/usr/bin/env bash
# Qual versão do CodeWarrior gerou as bibliotecas ligadas no jogo?
#
# O MSL (biblioteca C/C++) e o Runtime vêm prontos com cada versão do
# CodeWarrior, e mudam um pouco de uma versão para outra. Procurando no jogo
# as funções das bibliotecas de cada versão (achar_funcoes.py), a versão
# certa é a que acha TODAS as funções que alguma versão acha.
#
# Uso: decomp/tools/versao_msl.sh   (depois de ferramentas.sh e montar_rom.sh)
set -euo pipefail
REPO="$(cd "$(dirname "$0")/../.." && pwd)"
L="${FERRAMENTAS:-$REPO/work/ferramentas}/metroskrew/lib/metroskrew/sdk/ds/2.0"
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
cd "$REPO"
libs() {  # as bibliotecas Thumb (T) e ARM com interworking (Ai) de uma versão
    for t in T Ai; do
        echo "$1/msl/MSL_C/MSL_ARM/Lib/MSL_C_NITRO_${t}_LE.a"
        echo "$1/msl/MSL_C++/MSL_ARM/Lib/MSL_CPP_NITRO_${t}_LE.a"
        echo "$1/Runtime/Runtime_ARM/Runtime_NITRO/Lib/NITRO_Runtime_${t}_LE.a"
    done
}
# 0x020e09d0: onde começa o MSL no ARM9 (abort, a primeira função dele)
for d in "$L"/*; do
    v="$(basename "$d")"
    python3 decomp/tools/achar_funcoes.py --nomes --de 0x020e09d0 $(libs "$d") |
        grep -v '^#' | awk '{print $1}' | sort -u > "$TMP/$v"
done
sort -u "$TMP"/* > "$TMP/todas"
printf "%-8s %s\n" "versão" "endereços achados (de $(wc -l < "$TMP/todas") que alguma versão acha)"
for f in "$TMP"/*; do
    v="$(basename "$f")"; [ "$v" = todas ] && continue
    printf "%-8s %s\n" "$v" "$(wc -l < "$f")"
done
