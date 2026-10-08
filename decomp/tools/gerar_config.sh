#!/usr/bin/env bash
# (Re)gera a configuração do dsd em config/YWSE/ a partir da ROM.
# Só é preciso uma vez: depois disso config/ é editado à mão (nomes de
# funções, divisão do ARM9 em arquivos-fonte) e versionado no Git.
# Rodar de novo APAGA essas edições; use só para recomeçar do zero.
#
# config/ não tem nada do jogo: só endereços, tamanhos e nomes que nós demos.
#
# Uso: decomp/tools/gerar_config.sh rom.nds
set -euo pipefail
ROM="${1:?uso: gerar_config.sh rom.nds}"
REPO="$(cd "$(dirname "$0")/../.." && pwd)"
DSD="${FERRAMENTAS:-$REPO/work/ferramentas}/bin/dsd"
T="$REPO/analise/tools"
cd "$REPO"

echo "== extrair a ROM (work/extract)"
rm -rf work/extract work/extracted
"$DSD" rom extract --rom "$ROM" --output-path work/extract
python3 "$T/extract_rom.py" "$ROM" work/extracted >/dev/null

echo "== achar as funções (dsd init)"
# --allow-unknown-function-calls: 2 funções escritas à mão em assembly
# (0x020ecc3c e 0x020ecc74, estilo setjmp) que a análise não reconhece.
rm -rf config/YWSE
"$DSD" init --rom-config work/extract/config.yaml --output-path config/YWSE \
       --build-path work/build --allow-unknown-function-calls >/dev/null 2>&1

echo "== dar nomes: RTTI (classes C++) + analise/symbols_manual.txt"
S=config/YWSE/arm9/symbols.txt
cp "$S" work/symbols.orig.txt
python3 "$T/rtti.py" work/extracted/arm9.bin work/symbols.orig.txt \
        config/YWSE/arm9/relocs.txt work/rtti | tail -1
python3 "$T/apply_names.py" analise/symbols_manual.txt work/rtti/symbols_renamed.txt "$S"
"$DSD" format -c config/YWSE/arm9/config.yaml >/dev/null 2>&1 || true
echo "Pronto: config/YWSE/"
