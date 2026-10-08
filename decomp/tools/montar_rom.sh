#!/usr/bin/env bash
# Build "matching": reconstrói a ROM a partir das partes desmontadas e confere
# que ela saiu idêntica à original, byte a byte (SHA-1).
#
#   1. extrair    dsd rom extract: código (arm9.bin, itcm, dtcm, arm7) e arquivos
#   2. delink     dsd delink: corta o ARM9 em arquivos-objeto ELF (.o) seguindo
#                 config/YWSE/arm9/delinks.txt. Cada .o tem o código, os
#                 símbolos (symbols.txt) e as relocações (relocs.txt): onde o
#                 código aponta para outro endereço, fica uma referência por nome
#   3. lcf        dsd lcf: escreve o script do linker (ordem dos .o na memória)
#   4. link       mwldarm, o linker original da Metrowerks, junta tudo de novo e
#                 resolve as referências. Se algum endereço sair diferente, os
#                 bytes mudam e a verificação falha
#   5. rom        dsd rom config + rom build: monta o .nds
#   6. conferir   dsd check modules (ARM9/ITCM/DTCM) e SHA-1 da ROM inteira
#
# Quando o C decompilado entrar (Fase 1+), os .o dele substituem os pedaços
# correspondentes do passo 2, e este mesmo script prova que nada mudou.
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
[ -x "$DSD" ] || { echo "faltam ferramentas: rode decomp/tools/ferramentas.sh"; exit 1; }

echo "== 1. extrair (work/extract)"
rm -rf work/extract
"$DSD" rom extract --rom "$ROM" --output-path work/extract >/dev/null
python3 decomp/tools/banner_sem_perda.py "$ROM" work/extract/banner

echo "== 2. delink"
rm -rf work/build
"$DSD" delink -c "$CFG" >/dev/null
echo "   $(ls work/build/delinks | wc -l) arquivo(s) .o"

echo "== 3. lcf"
"$DSD" lcf -c "$CFG" >/dev/null

echo "== 4. link (mwldarm)"
# -dead: descarta o que ninguém usa; -m Entry: ponto de entrada; -map: gera
# work/build/arm9.o.xMAP, o mapa de onde cada símbolo foi parar
"$F/bin/wibo" "$MWLD" -proc arm946e -dead -nostdlib -interworking \
    -map closure,unused -msgstyle gcc -m Entry \
    @work/build/objects.txt work/build/arm9.lcf -o work/build/arm9.o

echo "== 5. montar a ROM"
"$DSD" rom config --elf work/build/arm9.o -c "$CFG" >/dev/null
"$DSD" rom build --config work/build/build/rom_config.yaml --rom "$SAIDA" >/dev/null
python3 decomp/tools/crc_area_segura.py "$ROM" "$SAIDA"

echo "== 6. conferir"
"$DSD" check modules -c "$CFG" --fail 2>&1 | sed 's/^\[INFO \] /   /'
"$DSD" check symbols -c "$CFG" -e work/build/arm9.o --fail
ESPERADO=$(sha1sum "$ROM" | cut -d' ' -f1)
OBTIDO=$(sha1sum "$SAIDA" | cut -d' ' -f1)
echo "   original:      $ESPERADO"
echo "   reconstruída:  $OBTIDO"
if [ "$ESPERADO" != "$OBTIDO" ]; then
    echo "DIFERENTE. Primeiros bytes que mudaram (offset, original, novo):"
    cmp -l "$ROM" "$SAIDA" | head -10 | awk '{printf "   0x%x %02x %02x\n", $1-1, strtonum("0"$2), strtonum("0"$3)}'
    exit 1
fi
echo "IDÊNTICA. ROM em $SAIDA"
