#!/usr/bin/env bash
# Build "matching": reconstrói a ROM a partir das partes desmontadas e confere
# que ela saiu idêntica à original, byte a byte (SHA-1).
#
#   1. extrair    dsd rom extract: código (arm9.bin, itcm, dtcm, arm7) e arquivos
#   2. delink     dsd delink: corta o ARM9 em arquivos-objeto ELF (.o) seguindo
#                 config/YWSE/arm9/delinks.txt. Cada .o tem o código, os
#                 símbolos (symbols.txt) e as relocações (relocs.txt): onde o
#                 código aponta para outro endereço, fica uma referência por nome
#   2b. compilar  os arquivos marcados "complete" em delinks.txt já foram
#                 decompilados: em vez do pedaço cortado do jogo, entra o .o
#                 compilado do nosso C++ (src/)
#   3. lcf        dsd lcf: escreve o script do linker (ordem dos .o na memória)
#   4. link       mwldarm, o linker original da Metrowerks, junta tudo de novo e
#                 resolve as referências. Se algum endereço sair diferente, os
#                 bytes mudam e a verificação falha
#   5. rom        dsd rom config + rom build: monta o .nds
#   6. conferir   dsd check modules (ARM9/ITCM/DTCM) e SHA-1 da ROM inteira
#
# Se o C++ de src/ não gerar exatamente os bytes do jogo, a ROM muda e o
# passo 6 falha: é assim que se prova que a decompilação está certa.
#
# Uso: decomp/tools/montar_rom.sh rom_original.nds
set -euo pipefail
ROM="$(realpath "${1:?uso: montar_rom.sh rom_original.nds}")"
REPO="$(cd "$(dirname "$0")/../.." && pwd)"
F="${FERRAMENTAS:-$REPO/work/ferramentas}"
DSD="$F/bin/dsd"
MWLD="$F/mwccarm/2.0/sp1p5/mwldarm.exe"
CFG=config/YWSE/arm9/config.yaml
SAIDA=work/build/sonic_rebuilt.nds
cd "$REPO"
# o dsd escreve "[INFO ] ..." a cada passo; esconde só essas linhas
dsd() { "$DSD" "$@" 2>&1 | { grep -v '^\[INFO \] Load\|^\[INFO \] Saving\|^\[INFO \] Extracting' || true; }; }
[ -x "$DSD" ] || { echo "faltam ferramentas: rode decomp/tools/ferramentas.sh"; exit 1; }

echo "== 1. extrair (work/extract)"
rm -rf work/extract
dsd rom extract --rom "$ROM" --output-path work/extract
python3 decomp/tools/banner_sem_perda.py "$ROM" work/extract/banner

echo "== 2. delink"
rm -rf work/build
dsd delink -c "$CFG"
echo "   $(find work/build/delinks -name '*.o' | wc -l) arquivo(s) .o"

echo "== 2b. compilar o C++ decompilado (src/)"
"$DSD" json delinks -c "$CFG" | python3 -c '
import json, sys
for f in json.load(sys.stdin)["files"]:
    if f["object_to_link"] != f["delink_file"]:
        print(f["name"], f["object_to_link"])' | while read -r fonte objeto; do
    echo "   $fonte"
    decomp/tools/compilar.sh "$fonte" "$objeto"
done

echo "== 3. lcf"
dsd lcf -c "$CFG"

echo "== 4. link (mwldarm)"
# -dead: descarta o que ninguém usa; -m Entry: ponto de entrada; -map: gera
# work/build/arm9.o.xMAP, o mapa de onde cada símbolo foi parar
"$F/bin/wibo" "$MWLD" -proc arm946e -dead -nostdlib -interworking \
    -map closure,unused -msgstyle gcc -m Entry \
    @work/build/objects.txt work/build/arm9.lcf -o work/build/arm9.o

echo "== 5. montar a ROM"
dsd rom config --elf work/build/arm9.o -c "$CFG"
dsd rom build --config work/build/build/rom_config.yaml --rom "$SAIDA"
python3 decomp/tools/crc_area_segura.py "$ROM" "$SAIDA"

echo "== 6. conferir"
dsd check modules -c "$CFG" | sed 's/^\[INFO \] /   /'
dsd check symbols -c "$CFG" -e work/build/arm9.o --fail
ESPERADO=$(sha1sum "$ROM" | cut -d' ' -f1)
OBTIDO=$(sha1sum "$SAIDA" | cut -d' ' -f1)
echo "   original:      $ESPERADO"
echo "   reconstruída:  $OBTIDO"
if [ "$ESPERADO" != "$OBTIDO" ]; then
    echo "DIFERENTE. Primeiros bytes que mudaram:"
    python3 - "$ROM" "$SAIDA" <<'PY'
import struct, sys
a, b = (open(p, "rb").read() for p in sys.argv[1:3])
arm9_off, _, arm9_ram, arm9_tam = struct.unpack_from("<4I", a, 0x20)
difs = [i for i in range(min(len(a), len(b))) if a[i] != b[i]][:10]
for o in difs:
    onde = f" (ARM9 {o - arm9_off + arm9_ram:#010x})" if arm9_off <= o < arm9_off + arm9_tam else ""
    print(f"   offset {o:#x}{onde}: {a[o]:02x} -> {b[o]:02x}")
PY
    echo "Ache a função em config/YWSE/arm9/symbols.txt e compare com decomp/tools/comparar.py"
    exit 1
fi
echo "IDÊNTICA. ROM em $SAIDA"
