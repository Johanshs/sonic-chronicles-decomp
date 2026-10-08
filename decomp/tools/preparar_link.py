"""Acerta os .o das bibliotecas em work/build para o link sair igual ao da Nintendo.

O linker da Nintendo recebia os .a inteiros do MSL e, com -dead, ficava só com o que o
jogo usa. O nosso recebe um .o por arquivo que o jogo tem, ao lado do assembly cortado
(_dsd_gap) do resto. Três coisas mudam com isso, e este script cuida de cada uma, sempre
nas CÓPIAS dos .o em work/build (os originais, em work/bibliotecas, ficam intactos):

1. Dados "multidef" (bind 13 da Metrowerks). O typeinfo de std::exception vai em todo .o
   que o usa, e o linker fica com uma cópia só. No jogo ficou a de um arquivo do jogo, que
   para nós está no assembly, com o nome global. O mwldarm aceita várias cópias multidef,
   mas não uma multidef e uma global ("Multiply-defined"). Então, quando o assembly define
   o nome, a cópia do .o vira "indefinida": quem a usa passa a usar a do jogo.

2. A tabela de exceções. O .lcf manda guardar toda seção .exceptix (KEEP_SECTION), porque
   a do assembly é um bloco de dados que ninguém cita. Mas no .o cada função tem a sua
   .exceptix, que aponta para ela: guardada, ela manteria viva a função que o jogo
   descartou (o strtold, o OS_AllocFromArenaLo que ele chama...). A .exceptix de uma
   função que o jogo não tem perde a marca SHF_ALLOC e o ponto do nome (vira "exceptix",
   porque o KEEP_SECTION escolhe pelo nome): passa a ser um dado fora da memória, como os
   de depuração, e o linker não a guarda nem segue o que ela cita.

3. Nomes que só código descartado cita. O math.o tem funções que o jogo não usa e que
   chamam outras que o jogo também não tem (powf chama pow). O mwldarm exige que todo nome
   citado exista, mesmo em código que ele vai descartar. Para cada um, work/build/mortos.c
   ganha um "void nome(void) {}". Ninguém vivo chama essas funções, então o -dead as
   descarta; se alguma ficasse, a ROM mudaria e o SHA-1 acusaria.
   O assembly do jogo, ao contrário, é código vivo: um nome que ele cita e que ninguém
   define é um erro (o mwldarm resolveria um .L_ que falta como 0, sem avisar, e poria um
   "veneer" de 8 bytes que desloca tudo depois dele).

Uso (montar_rom.sh chama, entre o .lcf e o link): python3 decomp/tools/preparar_link.py FERRAMENTAS
"""
import re, subprocess, sys
from elftools.elf.elffile import ELFFile

ferramentas = sys.argv[1]
SIMBOLOS = ("config/YWSE/arm9/symbols.txt", "config/YWSE/arm9/itcm/symbols.txt",
            "config/YWSE/arm9/dtcm/symbols.txt")
objetos = [l.strip().strip('"') for l in open("work/build/objects.txt") if l.strip()]
bibliotecas = [f for f in objetos if "_dsd_gap" not in f and f.startswith(("work/build/MSL/",
               "work/build/NitroSDK/", "work/build/NitroSystem/"))]


def tabelas(f):
    elf = ELFFile(open(f, "rb"))
    return elf, list(elf.iter_sections()), list(elf.get_section_by_name(".symtab").iter_symbols())


# 1. multidef: a cópia do .o cede o lugar à do jogo
do_assembly = set()
for f in objetos:
    if "_dsd_gap" in f:
        _, _, simbolos = tabelas(f)
        do_assembly |= {s.name for s in simbolos if s.name and s["st_shndx"] != "SHN_UNDEF"
                        and s["st_info"]["bind"] == "STB_GLOBAL"}
cedidos = 0
for f in bibliotecas:
    elf, secoes, simbolos = tabelas(f)
    dados = bytearray(open(f, "rb").read())
    tab = elf.get_section_by_name(".symtab").header
    for i, s in enumerate(simbolos):
        if s["st_info"]["bind"] == "STB_LOPROC" and s["st_shndx"] != "SHN_UNDEF" and s.name in do_assembly:
            p = tab.sh_offset + i * tab.sh_entsize
            dados[p + 4:p + 12] = bytes(8)              # st_value e st_size: 0
            dados[p + 12] = 0x10                        # st_info: global, sem tipo
            dados[p + 14:p + 16] = bytes(2)             # st_shndx: SHN_UNDEF
            cedidos += 1
    open(f, "wb").write(dados)
print(f"   {cedidos} dado(s) multidef ficam com a cópia do jogo")

# 2. a .exceptix das funções que o jogo descartou sai do link
funcoes_jogo = {m.group(1) for f in SIMBOLOS[:2]
                for m in re.finditer(r"^(\S+) kind:(?:function|label)", open(f).read(), re.M)}
desligadas = 0
for f in bibliotecas:
    elf, secoes, simbolos = tabelas(f)
    dados = bytearray(open(f, "rb").read())
    for rel in secoes:
        alvo = secoes[rel.header.sh_info] if rel.header.sh_type in ("SHT_REL", "SHT_RELA") else None
        if alvo is None or alvo.name != ".exceptix" or not alvo.header.sh_flags & 2:
            continue
        funcao = next(simbolos[r["r_info_sym"]].name for r in rel.iter_relocations() if r["r_offset"] == 0)
        if funcao not in funcoes_jogo:
            cab = elf.header.e_shoff + rel.header.sh_info * elf.header.e_shentsize
            flags = int.from_bytes(dados[cab + 8:cab + 12], "little")
            dados[cab + 8:cab + 12] = (flags & ~2).to_bytes(4, "little")
            nome = int.from_bytes(dados[cab:cab + 4], "little")
            dados[cab:cab + 4] = (nome + 1).to_bytes(4, "little")
            desligadas += 1
    open(f, "wb").write(dados)
print(f"   {desligadas} .exceptix de funções que o jogo descartou ficam fora do link")

# 3. os nomes que só código descartado cita ganham uma função vazia
existem = {m.group(1) for f in SIMBOLOS for m in re.finditer(r"^(\S+) kind:", open(f).read(), re.M)}
do_lcf = set(re.findall(r"(\w+)\s*=[^=]", open("work/build/arm9.lcf").read()))
definidos, citados, do_jogo = set(), set(), set()
for f in objetos:
    elf, secoes, simbolos = tabelas(f)
    definidos |= {s.name for s in simbolos if s.name and s["st_shndx"] != "SHN_UNDEF"
                  and s["st_info"]["bind"] != "STB_LOCAL"}
    for sec in secoes:
        if sec.header.sh_type in ("SHT_REL", "SHT_RELA") and secoes[sec.header.sh_info].header.sh_flags & 2:
            nomes = {simbolos[r["r_info_sym"]].name for r in sec.iter_relocations()
                     if simbolos[r["r_info_sym"]]["st_shndx"] == "SHN_UNDEF"}
            (do_jogo if "_dsd_gap" in f else citados).update(nomes)
faltam = sorted(n for n in do_jogo - definidos - do_lcf if n)
if faltam:
    sys.exit(f"o código do jogo cita nomes que nenhum .o define: {', '.join(faltam[:20])}")
mortos = sorted(n for n in citados - definidos - existem - do_lcf if n)
estranhos = [n for n in mortos if not re.fullmatch(r"[A-Za-z_]\w*", n)]
if estranhos:
    sys.exit(f"nomes que não dá para escrever em C: {', '.join(estranhos)}")
with open("work/build/mortos.c", "w") as c:
    c.write("/* gerado por decomp/tools/preparar_link.py: veja o comentário lá */\n")
    c.writelines(f"void {n}(void) {{}}\n" for n in mortos)
r = subprocess.run([f"{ferramentas}/bin/wibo", f"{ferramentas}/mwccarm/2.0/sp2/mwccarm.exe",
                    "-c", "-proc", "arm946e", "-thumb", "-msgstyle", "gcc", "-nosyspath",
                    "work/build/mortos.c", "-o", "work/build/mortos.o"],
                   capture_output=True, text=True)
if r.returncode:
    sys.exit(r.stdout + r.stderr)
with open("work/build/objects.txt", "a") as f:
    f.write('"work/build/mortos.o"\n')
lcf = open("work/build/arm9.lcf").read()
lcf = lcf.replace("        ARM9_TEXT_END = .;", "        mortos.o(.text)\n        ARM9_TEXT_END = .;", 1)
open("work/build/arm9.lcf", "w").write(lcf)
print(f"   {len(mortos)} nome(s) que só código descartado cita: work/build/mortos.c")
