#!/usr/bin/env bash
# Instala as ferramentas do build "matching" em work/ferramentas/ (fora do Git).
#
#   dsd     ds-decomp: extrai a ROM, corta o ARM9 em .o (delink), gera o
#           script do linker (LCF) e monta a ROM de volta. Binário da release.
#   wibo    roda executáveis Windows de 32 bits no Linux (bem menor que o Wine).
#   mwccarm compiladores e linker da Metrowerks para DS, o mesmo pacote que o
#           decomp.me usa. Não vêm junto com este repositório.
#   metroskrew  só pelas bibliotecas da Metrowerks (MSL, Runtime) de cada
#           versão do CodeWarrior, para achar as funções delas no jogo.
#
# Versões fixas e conferidas por SHA-256: o mesmo build hoje e daqui a um ano.
set -euo pipefail
REPO="$(cd "$(dirname "$0")/../.." && pwd)"
DEST="${FERRAMENTAS:-$REPO/work/ferramentas}"
mkdir -p "$DEST"

# Release, não o fonte: o `main` do ds-decomp (c408063) acusa "nome de
# arquivo duplicado" em todo pedaço sem fonte (_dsd_gap) assim que o ARM9 é
# dividido em mais de um arquivo; o binário da release 0.12.1 não tem o erro.
DSD_URL=https://github.com/AetiasHax/ds-decomp/releases/download/v0.12.1/dsd-linux-x86_64
DSD_SHA=256edde804dd8e5d7bc4c0e4187f85244ee4cd1f42bb427502e01fda6af43ceb
WIBO_URL=https://github.com/decompals/wibo/releases/download/0.6.16/wibo
WIBO_SHA=8a8490a6172aa4f0f6ddcadb144ca96f51da6e90e6648ce9adaf4f6babb6e00b
MWCC_URL=https://github.com/decompme/compilers/releases/download/compilers/mwccarm.zip
MWCC_SHA=dc386e37b2176e960954a733de928337d9b7e7620b9e94228008c31774339ace
SKREW_URL=https://github.com/mid-kid/metroskrew/releases/download/0.1.3/metroskrew-linux.tar.xz
SKREW_SHA=2fec5ba308690a25157afc532ed87411a413501d43d85892ae4bfb9eb3975790

baixar() {  # baixar URL SHA256 destino
    [ -f "$3" ] && echo "$2  $3" | sha256sum -c --quiet 2>/dev/null && return
    echo "   baixando $1"
    curl -fsSL -o "$3.tmp" "$1"
    echo "$2  $3.tmp" | sha256sum -c --quiet || { echo "SHA-256 não confere: $1"; exit 1; }
    mv "$3.tmp" "$3"
}

mkdir -p "$DEST/bin"
echo "== dsd"
baixar "$DSD_URL" "$DSD_SHA" "$DEST/bin/dsd"
chmod +x "$DEST/bin/dsd"

echo "== wibo"
baixar "$WIBO_URL" "$WIBO_SHA" "$DEST/bin/wibo"
chmod +x "$DEST/bin/wibo"

echo "== mwccarm"
baixar "$MWCC_URL" "$MWCC_SHA" "$DEST/mwccarm.zip"
[ -d "$DEST/mwccarm" ] || (cd "$DEST" && unzip -q mwccarm.zip)

echo "== bibliotecas da Metrowerks (metroskrew)"
baixar "$SKREW_URL" "$SKREW_SHA" "$DEST/metroskrew.tar.xz"
[ -d "$DEST/metroskrew" ] || (cd "$DEST" && tar xf metroskrew.tar.xz)

"$DEST/bin/dsd" --version
"$DEST/bin/wibo" "$DEST/mwccarm/2.0/sp2/mwldarm.exe" -version | grep -m1 Version
echo "Pronto: ferramentas em $DEST"
