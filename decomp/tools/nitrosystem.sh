#!/usr/bin/env bash
# Fase 2.2: acha e nomeia no jogo as funções da NitroSystem (NNS_G3d, NNS_G2d, NNS_Snd...).
#
# A NitroSystem é a biblioteca de 3D, 2D, som e memória que a Nintendo dava junto
# com o NitroSDK. Ela foi decompilada pela comunidade (github.com/ntrtwl/NitroSystem,
# versão 071126). Este script faz com ela o mesmo que nitrosdk.sh faz com o SDK:
#   1. baixa o fonte numa versão fixa para work/NitroSystem
#   2. compila cada arquivo com as flags do meson.build dela, em Thumb (como o
#      SDK, o jogo ligou a versão Thumb) e com a mwccarm 2.0/sp2
#   3. procura cada função no jogo e grava os nomes sem ambiguidade em
#      config/YWSE/arm9/symbols.txt
# Os cabeçalhos do NitroSDK vêm de work/NitroSDK: rode nitrosdk.sh antes.
#
# Uso: decomp/tools/nitrosystem.sh [--so-compilar]
#      (depois de ferramentas.sh, montar_rom.sh e nitrosdk.sh)
set -euo pipefail
REPO="$(cd "$(dirname "$0")/../.." && pwd)"
F="${FERRAMENTAS:-$REPO/work/ferramentas}"
NNS="$REPO/work/NitroSystem"
SDK="$REPO/work/NitroSDK"
OBJ="$REPO/work/bibliotecas/nitrosystem"
GEN="$REPO/work/bibliotecas/nitrosdk/gen"     # o fx_const.h que nitrosdk.sh gera
REV=d636fb5d2b212e8736f09859fff447be2bd0ac85
VERSAO="${MWCC_VERSAO:-2.0/sp2}"
MSL="$F/metroskrew/lib/metroskrew/sdk/ds/2.0/sp2/msl/MSL_C"
cd "$REPO"

if [ ! -f "$GEN/nitro/fx/fx_const.h" ]; then
    echo "falta o NitroSDK: rode decomp/tools/nitrosdk.sh --so-compilar antes" >&2
    exit 1
fi
if [ ! -d "$NNS/.git" ]; then
    echo "== baixando a NitroSystem decompilada"
    git clone -q https://github.com/ntrtwl/NitroSystem "$NNS"
fi
git -C "$NNS" checkout -q "$REV"
mkdir -p "$OBJ"

echo "== compilando (mwccarm $VERSAO, Thumb)"
python3 - "$NNS" "$SDK" "$OBJ" "$GEN" "$F" "$MSL" "$VERSAO" <<'PY'
import glob, os, re, subprocess, sys
from concurrent.futures import ThreadPoolExecutor
nns, sdk, obj, gen, ferr, msl, versao = sys.argv[1:8]
fontes = set()
for mb in glob.glob(f"{nns}/libraries/**/meson.build", recursive=True):
    for m in re.finditer(r"(\w+)\s*=\s*files\(([^)]*)\)", open(mb).read()):
        fontes.update(os.path.normpath(os.path.join(os.path.dirname(mb), f))
                      for f in re.findall(r"'([^']+\.c)'", m.group(2)))
fontes = sorted(fontes)
# como em nitrosdk.sh: caminhos relativos, rodando de dentro do SDK
os.chdir(sdk)
rel = os.path.relpath
inc = ["-i", rel(gen), "-i", "include", "-i", "include/pch", "-i", rel(f"{nns}/include")]
# cabeçalhos internos de cada biblioteca (heapcommoni.h, archive_block.h...)
for d in sorted(glob.glob(f"{nns}/libraries/*/include")) + [f"{nns}/libraries/g3d/src/binres"]:
    inc += ["-i", rel(d)]
flags = ["-c", "-O4,p", "-proc", "arm946e", "-thumb", "-enum", "int", "-lang", "c99",
         "-Cpp_exceptions", "off", "-gccext,on", "-msgstyle", "gcc", "-ipa", "file",
         "-interworking", "-inline", "on,noauto", "-char", "signed", "-nosyspath", "-stdinc",
         "-DSDK_CW_FORCE_EXPORT_SUPPORT", "-DSDK_TS", "-DSDK_4M", "-DSDK_ARM9", "-DSDK_CW",
         "-DSDK_FINALROM", "-DSDK_CODE_THUMB", "-DNNS_FINALROM", "-cwd", "include", *inc,
         "-I-", "-ir", rel(f"{msl}/MSL_Common/Include"), "-ir", rel(f"{msl}/MSL_ARM/Include"),
         "-prefix", "nitro_pch.h"]
def compilar(f):
    o = os.path.join(obj, os.path.relpath(f, nns).replace("/", "_")[:-2] + ".o")
    r = subprocess.run([f"{ferr}/bin/wibo", f"{ferr}/mwccarm/{versao}/mwccarm.exe",
                        *flags, rel(f), "-o", o], capture_output=True, text=True)
    return f, r.returncode
erros = [f for f, c in ThreadPoolExecutor(8).map(compilar, fontes) if c]
print(f"   {len(fontes) - len(erros)} arquivos compilados, {len(erros)} com erro")
for f in erros:
    print("   erro:", os.path.relpath(f, nns))
PY
[ "${1:-}" = "--so-compilar" ] && exit 0

echo "== procurando no jogo e gravando os nomes"
# a região onde a NitroSystem foi ligada: logo antes do NitroSDK
python3 decomp/tools/achar_funcoes.py --min 8 --de 0x020c8278 --ate 0x020d4394 --aplicar "$OBJ"/*.o | tail -1
