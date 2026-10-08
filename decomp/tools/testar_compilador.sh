#!/usr/bin/env bash
# Fase 1: compila as funções de decomp/compilador/casos.txt com cada versão do
# mwccarm e alguns níveis de otimização, e conta quantas saem 100% iguais ao
# jogo. Uma configuração só "serve" se acertar todas.
#
# Uso: decomp/tools/testar_compilador.sh   (depois de ferramentas.sh e montar_rom.sh)
set -uo pipefail
REPO="$(cd "$(dirname "$0")/../.." && pwd)"
F="${FERRAMENTAS:-$REPO/work/ferramentas}"
CASOS="$REPO/decomp/compilador/casos.txt"
ARM9="$REPO/work/extract/arm9/arm9.bin"
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
[ -f "$ARM9" ] || { echo "falta $ARM9: rode decomp/tools/montar_rom.sh rom.nds"; exit 1; }
cd "$REPO"
OPTS=(-O4,p -O4,s -O3,p -O2)
TOTAL=$(grep -vc '^#' "$CASOS")

printf "%-12s" "versão"; for o in "${OPTS[@]}"; do printf "%-8s" "$o"; done; echo
for dir in "$F"/mwccarm/1.2/* "$F"/mwccarm/2.0/* "$F"/mwccarm/dsi/*; do
    v="${dir#"$F"/mwccarm/}"
    printf "%-12s" "$v"
    for o in "${OPTS[@]}"; do
        ok=0; n=0
        while read -r fonte sim end; do
            case "$fonte" in ""|\#*) continue;; esac
            n=$((n + 1))
            # a opção do fim da linha de comando vence a -O4,p de compilar.sh
            MWCC_VERSAO="$v" decomp/tools/compilar.sh "$fonte" "$TMP/$n.o" "$o" >/dev/null 2>&1 &&
                python3 decomp/tools/comparar.py "$TMP/$n.o" "$sim" "$end" "$ARM9" >/dev/null &&
                ok=$((ok + 1))
        done < "$CASOS"
        printf "%-8s" "$ok/$TOTAL"
    done
    echo
done
