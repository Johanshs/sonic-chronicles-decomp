#!/usr/bin/env bash
# Fase 2.1: acha e nomeia no jogo as funções do NitroSDK 4.2.30001.
#
# O jogo foi feito com o NitroSDK 4.2.30001 (o número 0x04027531 no ARM9). Esse
# SDK foi decompilado pela comunidade (github.com/ntrtwl/NitroSDK, o mesmo que o
# decomp do Pokémon Platinum usa). Este script:
#   1. baixa o fonte numa versão fixa para work/NitroSDK
#   2. compila cada arquivo do ARM9 como a Nintendo compilou: mwccarm 2.0/sp1p2
#      com as flags do meson.build do próprio SDK, mas em Thumb (SDK_CODE_THUMB):
#      o jogo ligou a versão Thumb das bibliotecas
#   3. procura cada função compilada no jogo (achar_funcoes.py) e grava os
#      nomes sem ambiguidade em config/YWSE/arm9/symbols.txt
#
# Uso: decomp/tools/nitrosdk.sh [--so-compilar]
#      (depois de ferramentas.sh e montar_rom.sh)
set -euo pipefail
REPO="$(cd "$(dirname "$0")/../.." && pwd)"
F="${FERRAMENTAS:-$REPO/work/ferramentas}"
SDK="$REPO/work/NitroSDK"
OBJ="$REPO/work/build/nitrosdk"
REV=eaae40f199c0a8827947afbc33227b6ba2f9d45c
MSL="$F/metroskrew/lib/metroskrew/sdk/ds/2.0/sp1p2/msl/MSL_C"
cd "$REPO"

if [ ! -d "$SDK/.git" ]; then
    echo "== baixando o NitroSDK decompilado"
    git clone -q https://github.com/ntrtwl/NitroSDK "$SDK"
fi
git -C "$SDK" checkout -q "$REV"
mkdir -p "$OBJ/gen/nitro/fx"
python3 "$SDK/gen/nitro/fx/gen_fx_const.py" "$SDK/gen/nitro/fx/fx_const.csv" "$OBJ/gen/nitro/fx/fx_const.h"

echo "== compilando (mwccarm 2.0/sp1p2, Thumb)"
python3 - "$SDK" "$OBJ" "$F" "$MSL" <<'PY'
import glob, os, re, subprocess, sys
from concurrent.futures import ThreadPoolExecutor
sdk, obj, ferr, msl = sys.argv[1:5]
# os arquivos do ARM9: as listas files(...) dos meson.build, menos as do ARM7
fontes = set()
for mb in glob.glob(f"{sdk}/libraries/**/meson.build", recursive=True):
    for m in re.finditer(r"(\w+)\s*=\s*files\(([^)]*)\)", open(mb).read()):
        if "arm7" not in m.group(1).lower():
            fontes.update(os.path.normpath(os.path.join(os.path.dirname(mb), f))
                          for f in re.findall(r"'([^']+\.c)'", m.group(2)))
fontes = sorted(f for f in fontes if "/ARM7/" not in f)
# caminhos relativos: o mwccarm (via wibo) não aceita bem os absolutos no -prefix
os.chdir(sdk)
inc = ["-i", os.path.relpath(f"{obj}/gen"), "-i", "include", "-i", "include/pch"]
for d in sorted(glob.glob("libraries/*/include") + glob.glob("libraries/*/*/include")):
    inc += ["-i", d]
flags = ["-c", "-O4,p", "-proc", "arm946e", "-thumb", "-enum", "int", "-lang", "c99",
         "-Cpp_exceptions", "off", "-gccext,on", "-msgstyle", "gcc", "-ipa", "file",
         "-interworking", "-inline", "on,noauto", "-char", "signed", "-nosyspath", "-stdinc",
         "-DSP1P3_BUG_FOR_CONDITIONAL_ASM_INSTRUCTIONS", "-DSDK_CW_FORCE_EXPORT_SUPPORT",
         "-DSDK_TS", "-DSDK_4M", "-DSDK_ARM9", "-DSDK_CW", "-DSDK_FINALROM",
         "-DSDK_CODE_THUMB", "-DNNS_FINALROM", "-cwd", "include", *inc,
         "-I-", "-ir", os.path.relpath(f"{msl}/MSL_Common/Include"),
         "-ir", os.path.relpath(f"{msl}/MSL_ARM/Include"), "-prefix", "nitro_pch.h"]
def compilar(f):
    o = os.path.join(obj, os.path.relpath(f, sdk).replace("/", "_")[:-2] + ".o")
    r = subprocess.run([f"{ferr}/bin/wibo", f"{ferr}/mwccarm/2.0/sp1p2/mwccarm.exe",
                        *flags, os.path.relpath(f), "-o", o], capture_output=True, text=True)
    return f, r.returncode
erros = [f for f, c in ThreadPoolExecutor(8).map(compilar, fontes) if c]
print(f"   {len(fontes) - len(erros)} arquivos compilados, {len(erros)} com erro")
for f in erros:
    print("   erro:", os.path.relpath(f, sdk))
PY
[ "${1:-}" = "--so-compilar" ] && exit 0

echo "== procurando no jogo e gravando os nomes"
# as regiões onde o SDK foi ligado: o grosso do ARM9, o ITCM e o crt0 (_start)
for faixa in "0x020d4000 0x020e09d0" "0x01ff8000 0x02000000" "0x02000000 0x02000c00"; do
    set -- $faixa
    python3 decomp/tools/achar_funcoes.py --min 8 --de "$1" --ate "$2" --aplicar "$OBJ"/*.o | tail -1
done
