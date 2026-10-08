#!/usr/bin/env bash
# Instala as ferramentas do build "matching" em work/ferramentas/ (fora do Git).
#
#   dsd     ds-decomp: extrai a ROM, corta o ARM9 em .o (delink), gera o
#           script do linker (LCF) e monta a ROM de volta. Compilado do fonte.
#   wibo    roda executáveis Windows de 32 bits no Linux (bem menor que o Wine).
#   mwccarm compiladores e linker da Metrowerks para DS, o mesmo pacote que o
#           decomp.me usa. Não vêm junto com este repositório.
#
# Versões fixas e conferidas por SHA-256: o mesmo build hoje e daqui a um ano.
set -euo pipefail
REPO="$(cd "$(dirname "$0")/../.." && pwd)"
DEST="${FERRAMENTAS:-$REPO/work/ferramentas}"
mkdir -p "$DEST"

DSD_REV=c4080635ac38aaf9608ca23751defa9fa19cf81a        # ds-decomp 0.12.1
WIBO_URL=https://github.com/decompals/wibo/releases/download/0.6.16/wibo
WIBO_SHA=8a8490a6172aa4f0f6ddcadb144ca96f51da6e90e6648ce9adaf4f6babb6e00b
MWCC_URL=https://github.com/decompme/compilers/releases/download/compilers/mwccarm.zip
MWCC_SHA=dc386e37b2176e960954a733de928337d9b7e7620b9e94228008c31774339ace

baixar() {  # baixar URL SHA256 destino
    [ -f "$3" ] && echo "$2  $3" | sha256sum -c --quiet 2>/dev/null && return
    echo "   baixando $1"
    curl -fsSL -o "$3.tmp" "$1"
    echo "$2  $3.tmp" | sha256sum -c --quiet || { echo "SHA-256 não confere: $1"; exit 1; }
    mv "$3.tmp" "$3"
}

if [ ! -x "$DEST/bin/dsd" ] || ! "$DEST/bin/dsd" --version | grep -q 0.12.1; then
    echo "== dsd (compilando do fonte, alguns minutos)"
    cargo install --quiet --locked --git https://github.com/AetiasHax/ds-decomp \
        --rev "$DSD_REV" ds-decomp-cli --root "$DEST"
fi

echo "== wibo"
mkdir -p "$DEST/bin"
baixar "$WIBO_URL" "$WIBO_SHA" "$DEST/bin/wibo"
chmod +x "$DEST/bin/wibo"

echo "== mwccarm"
baixar "$MWCC_URL" "$MWCC_SHA" "$DEST/mwccarm.zip"
[ -d "$DEST/mwccarm" ] || (cd "$DEST" && unzip -q mwccarm.zip)

"$DEST/bin/dsd" --version
"$DEST/bin/wibo" "$DEST/mwccarm/2.0/sp1p5/mwldarm.exe" -version | grep -m1 Version
echo "Pronto: ferramentas em $DEST"
