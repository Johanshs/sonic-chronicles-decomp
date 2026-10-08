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
MWLD="$F/mwccarm/2.0/sp2/mwldarm.exe"
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
    case "$fonte" in
        # bibliotecas da Nintendo: o .o já compilado por nitrosdk.sh/nitrosystem.sh,
        # com o compilador e as flags delas (não as do jogo)
        NitroSDK/*|NitroSystem/*)
            lib="${fonte%%/*}"; resto="${fonte#*/}"
            # "x.itcm.c", "x.dtcm.c", "x.version.c": partes de x.c (veja o passo 3)
            resto="${resto/.itcm.c/.c}"; resto="${resto/.dtcm.c/.c}"; resto="${resto/.version.c/.c}"
            pronto="work/bibliotecas/${lib,,}/$(echo "${resto%.c}" | tr / _).o"
            if [ ! -f "$pronto" ]; then
                echo "   compilando a biblioteca: decomp/tools/${lib,,}.sh --so-compilar"
                [ "$lib" = NitroSystem ] && [ ! -d work/bibliotecas/nitrosdk ] &&
                    decomp/tools/nitrosdk.sh --so-compilar </dev/null
                "decomp/tools/${lib,,}.sh" --so-compilar </dev/null
            fi
            mkdir -p "$(dirname "$objeto")" && cp "$pronto" "$objeto" ;;
        *) decomp/tools/compilar.sh "$fonte" "$objeto" ;;
    esac
done

echo "== 3. lcf"
dsd lcf -c "$CFG"
# O jogo tem funções de biblioteca que ninguém chama (OS_DisableProtectionUnit): o
# linker da Nintendo as manteve, o nosso (-dead) jogaria fora. FORCE_ACTIVE no .lcf
# segura as funções globais dos arquivos ligados do fonte que existem no jogo. (A
# opção -force_active da linha de comando não serve: ela aborta passando de ~256
# caracteres.) E os símbolos de config/YWSE/arm9/simbolos_linker.lcf.
#
# Um arquivo do SDK pode ter funções no ITCM (OS_IrqHandler), variáveis no DTCM ou a
# string .version ("[SDK+NINTENDO:BACKUP]", que a Nintendo punha logo depois do crt0).
# O dsd não aceita o mesmo nome duas vezes, então essas partes aparecem em delinks.txt
# como "x.itcm.c", "x.dtcm.c", "x.version.c". O .o é um só (x.o), com as seções .itcm,
# .dtcm, .dtcm.bss e .version: aqui o .lcf passa a pedir essas seções a ele.
python3 -c '
import glob, re
obj = open("work/build/objects.txt").read().splitlines()
open("work/build/objects.txt", "w").write("\n".join(dict.fromkeys(obj)) + "\n")
from elftools.elf.elffile import ELFFile
jogo = set()
for l in open("config/YWSE/arm9/symbols.txt").readlines() + open("config/YWSE/arm9/itcm/symbols.txt").readlines():
    m = re.match(r"(\S+) kind:function", l)
    if m and not l.rstrip().endswith(" local"):
        jogo.add(m.group(1))
nomes = []
for f in sorted(glob.glob("work/build/NitroS*/**/*.o", recursive=True)):
    for s in ELFFile(open(f, "rb")).get_section_by_name(".symtab").iter_symbols():
        if (s["st_info"]["type"] == "STT_FUNC" and s["st_info"]["bind"] == "STB_GLOBAL"
                and s["st_shndx"] != "SHN_UNDEF" and s.name in jogo):
            nomes.append(s.name)
lcf = open("work/build/arm9.lcf").read()
for mod, sec, nova in (("itcm", "text", "itcm"), ("dtcm", "data", "dtcm"), ("dtcm", "bss", "dtcm.bss"),
                      ("version", "text", "version")):
    lcf = re.sub(rf"(\S+)\.{mod}\.o\(\.{sec}\)", rf"\1.o(.{nova})", lcf)
if nomes:
    bloco = "FORCE_ACTIVE {\n    " + ",\n    ".join(nomes) + "\n}\n\n"
    lcf = lcf.replace("KEEP_SECTION {", bloco + "KEEP_SECTION {", 1)
# os símbolos que o linker da Nintendo calculava (SDK_SYS_STACKSIZE...), no fim de SECTIONS
fim = lcf.rstrip().rindex("}")
lcf = lcf[:fim] + open("config/YWSE/arm9/simbolos_linker.lcf").read() + lcf[fim:]
open("work/build/arm9.lcf", "w").write(lcf)'

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
# Exceção: os "static" de um arquivo dividido em partes (OSi_DoResetSystem, no ITCM,
# chamada do ARM9) ficam globais em symbols.txt, porque o dsd não deixa uma parte usar
# um símbolo local da outra. No .o eles continuam static: só essa diferença passa.
"$DSD" check symbols -c "$CFG" -e work/build/arm9.o 2>&1 | python3 -c '
import glob, re, sys
from elftools.elf.elffile import ELFFile
divididos = set()
for f in glob.glob("work/build/NitroS*/**/*.o", recursive=True):
    elf = ELFFile(open(f, "rb"))
    if any(s.name in (".itcm", ".dtcm", ".dtcm.bss", ".version") for s in elf.iter_sections()):
        divididos |= {s.name for s in elf.get_section_by_name(".symtab").iter_symbols()
                      if s["st_info"]["bind"] == "STB_LOCAL" and s.name}
erros = [l for l in sys.stdin if l.startswith("[ERROR]")]
ruins = [l for l in erros if not (re.search(r"Symbol .(\S+). at .* expected to be global but is local", l)
                                  and re.search(r"Symbol .(\S+).", l).group(1).strip("\x27") in divididos)]
print(f"   símbolos: {len(erros) - len(ruins)} static de arquivos divididos em partes (esperado)")
sys.stdout.write("".join(ruins))
sys.exit(1 if ruins else 0)'
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
