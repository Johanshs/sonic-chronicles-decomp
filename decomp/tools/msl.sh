#!/usr/bin/env bash
# Fase 2.3: o MSL (biblioteca C/C++ da Metrowerks) e o Runtime, ligados dos .a originais.
#
# Diferente do NitroSDK e da NitroSystem, o MSL não tem fonte público: ele vem pronto,
# em bibliotecas .a, junto com cada versão do CodeWarrior (versao_msl.sh mostrou que o
# jogo usou as da 2.0/sp2, na variante Thumb). Um .a é só um pacote de arquivos .o.
# Este script tira cada .o de dentro dos três .a para work/bibliotecas/msl/, com um
# nome único (os nomes dentro do .a são cortados em 16 letras e alguns se repetem):
#   C_alloc.o, CPP_locale.o, Runtime_new.o...
# Depois, "ligar_bibliotecas.py MSL - work/bibliotecas/msl 0x020e09d0 0x020eccb4" faz o
# build ligar esses .o no lugar do assembly, como faz com o SDK. montar_rom.sh chama
# este script sozinho quando work/bibliotecas/msl não existe.
#
# Uso: decomp/tools/msl.sh [--so-compilar]   (o nome da opção é o mesmo dos outros)
set -euo pipefail
REPO="$(cd "$(dirname "$0")/../.." && pwd)"
F="${FERRAMENTAS:-$REPO/work/ferramentas}"
L="$F/metroskrew/lib/metroskrew/sdk/ds/2.0/sp2"
OBJ="$REPO/work/bibliotecas/msl"
mkdir -p "$OBJ"
cd "$REPO"
python3 - "$OBJ" "C=$L/msl/MSL_C/MSL_ARM/Lib/MSL_C_NITRO_T_LE.a" \
    "CPP=$L/msl/MSL_C++/MSL_ARM/Lib/MSL_CPP_NITRO_T_LE.a" \
    "Runtime=$L/Runtime/Runtime_ARM/Runtime_NITRO/Lib/NITRO_Runtime_T_LE.a" \
    "Math=$L/Mathlib/lib/FP_fastI_v5t_LE.a" <<'PY'
import os, re, sys
sys.path.insert(0, "decomp/tools")
import achar_funcoes as af
obj = sys.argv[1]
total = 0
for arg in sys.argv[2:]:
    lib, caminho = arg.split("=", 1)
    vistos = {}
    for nome, corpo in af.membros_ar(open(caminho, "rb").read()):
        base = re.sub(r"\.o$", "", nome).replace(".", "_")
        vistos[base] = vistos.get(base, 0) + 1
        if vistos[base] > 1:
            base += f"_{vistos[base]}"
        open(os.path.join(obj, f"{lib}_{base}.o"), "wb").write(corpo)
        total += 1
print(f"   {total} arquivos .o extraídos para {obj}")
PY
