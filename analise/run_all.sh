#!/usr/bin/env bash
# Pipeline completo: ROM -> análise -> nomes -> assembly -> pseudo-C -> dados legíveis.
# Uso: ./run_all.sh caminho/para/rom.nds [--sem-ghidra]
#
# Requisitos: python3 (+ pip: ndspy capstone), cargo (Rust), cc (para os testes)
#             Ghidra 11.x (opcional, para o pseudo-C). Defina GHIDRA_HOME.
set -euo pipefail

ROM="${1:?uso: ./run_all.sh rom.nds [--sem-ghidra]}"
SKIP_GHIDRA="${2:-}"
HERE="$(cd "$(dirname "$0")" && pwd)"     # analise/
REPO="$(dirname "$HERE")"                  # raiz do repositório
WORK="${WORK:-$REPO/work}"
T="$HERE/tools"
mkdir -p "$WORK"

echo "== 0. dependências"
python3 -c "import ndspy, capstone" 2>/dev/null || pip install ndspy capstone
if ! command -v dsd >/dev/null; then
    echo "   instalando dsd (ds-decomp, feito em Rust)..."
    cargo install --git https://github.com/AetiasHax/ds-decomp ds-decomp-cli
fi

echo "== 1. extrair a ROM (código + arquivos)"
python3 "$T/extract_rom.py" "$ROM" "$WORK/extracted"
dsd rom extract --rom "$ROM" --output-path "$WORK/dsd_extract"

echo "== 2. achar todas as funções (dsd init)"
# --allow-unknown-function-calls: há 2 funções escritas à mão em assembly
# (0x020ecc3c, 0x020ecc74, estilo setjmp) que a análise automática não reconhece.
rm -rf "$WORK/config" "$WORK/build"
dsd init --rom-config "$WORK/dsd_extract/config.yaml" --output-path "$WORK/config" \
         --build-path "$WORK/build" --allow-unknown-function-calls >/dev/null
cp "$WORK/config/arm9/symbols.txt" "$WORK/config/arm9/symbols.orig.txt"

echo "== 3. recuperar classes C++ pelo RTTI e nomear funções"
python3 "$T/rtti.py" "$WORK/extracted/arm9.bin" "$WORK/config/arm9/symbols.orig.txt" \
        "$WORK/config/arm9/relocs.txt" "$WORK/rtti"
python3 "$T/apply_names.py" "$HERE/symbols_manual.txt" "$WORK/rtti/symbols_renamed.txt" \
        "$WORK/config/arm9/symbols.txt"

echo "== 4. assembly completo com os nomes"
rm -rf "$WORK/asm"
dsd dis --config-path "$WORK/config/arm9/config.yaml" --asm-path "$WORK/asm"

echo "== 5. extrair o pacote HERF (8691 arquivos; nomes pelo erf.dict oficial + dicionário)"
python3 "$T/herf.py" "$WORK/extracted/files/test.herf" "$WORK/herf" \
        "$WORK/extracted/arm9.bin" "$WORK/extracted/files"

echo "== 6. dados legíveis"
mkdir -p "$WORK/output"
python3 "$T/dump_dialogs.py" "$WORK/herf" "$WORK/extracted/files/strings.tlk" "$WORK/output/roteiro_en.txt"
python3 "$T/gda.py" "$WORK/herf" "$WORK/output/tabelas" "$WORK/extracted/arm9.bin" "$WORK"/extracted/files/*.2da

echo "== 7. validar a decompilação manual contra o jogo (C)"
make -C "$REPO/decomp" test HERF_DIR="$WORK/herf"

echo "== 8. testes da biblioteca Rust (engine/)"
(cd "$REPO/engine" && cargo test --release -q)

if [ "$SKIP_GHIDRA" != "--sem-ghidra" ] && [ -n "${GHIDRA_HOME:-}" ]; then
    echo "== 9. pseudo-C de todas as funções (Ghidra headless, ~15-20 min)"
    python3 "$T/ghidra_symbols.py" "$WORK/config" > "$WORK/ghidra_syms.tsv"
    rm -rf "$WORK/ghidra_proj" "$WORK/decomp_c"; mkdir -p "$WORK/ghidra_proj"
    "$GHIDRA_HOME/support/analyzeHeadless" "$WORK/ghidra_proj" sonic \
        -import "$WORK/extracted/arm9.bin" -loader BinaryLoader -loader-baseAddr 0x02000000 \
        -processor ARM:LE:32:v5t -scriptPath "$HERE/ghidra_scripts" \
        -preScript SetupSonic.java "$WORK/ghidra_syms.tsv" \
        -postScript DecompileAll.java "$WORK/decomp_c" -analysisTimeoutPerFile 3600
else
    echo "== 9. (pulado) defina GHIDRA_HOME para gerar o pseudo-C"
fi
echo "Pronto. Resultados em $WORK"
