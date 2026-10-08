"""Confere os nomes dados por achar_funcoes.py pelas chamadas entre funções.

Um nome pode estar certo por acaso (duas funções pequenas com os mesmos bytes).
Uma prova independente: se a função X do .o chama `bl Y`, então no jogo o `bl`
da função com nome X tem que apontar para a função com nome Y. O script segue
todas as chamadas (bl Thumb e ARM) e os ponteiros de 32 bits das funções
nomeadas e conta quantas apontam para o lugar certo.

Uso: python3 conferir_chamadas.py arquivo.o [mais.o ...]
"""
import re, struct, sys
from elftools.elf.elffile import ELFFile

nomes, tamanhos = {}, {}
for f in ("config/YWSE/arm9/symbols.txt", "config/YWSE/arm9/itcm/symbols.txt"):
    for linha in open(f):
        m = re.match(r"(\S+) kind:function\(\w+,size=(0x[0-9a-f]+).* addr:(0x[0-9a-f]+)", linha)
        if m:
            nomes[m.group(1)] = int(m.group(3), 16)
            tamanhos[m.group(1)] = int(m.group(2), 16)
arm9 = open("work/extract/arm9/arm9.bin", "rb").read()
BASE = 0x02000000


def destino(tipo, end):
    """Para onde a instrução/palavra no endereço `end` do jogo aponta."""
    dados = arm9[end - BASE:end - BASE + 4]
    if tipo == 10:                                  # R_ARM_THM_CALL: bl/blx Thumb
        alto, baixo = struct.unpack("<HH", dados)
        desl = ((alto & 0x7ff) << 12) | ((baixo & 0x7ff) << 1)
        if desl & 0x400000:
            desl -= 0x800000
        alvo = end + 4 + desl
        return alvo & ~3 if baixo >> 11 == 0x1d else alvo     # blx: vira ARM
    if tipo in (28, 29):                            # R_ARM_CALL / JUMP24: bl ARM
        w = struct.unpack("<I", dados)[0]
        desl = (w & 0xffffff) << 2
        if desl & 0x2000000:
            desl -= 0x4000000
        return end + 8 + desl + ((((w >> 24) & 1) << 1) if w >> 28 == 0xf else 0)
    if tipo == 2:                                   # R_ARM_ABS32: ponteiro
        return struct.unpack("<I", dados)[0] & ~1
    return None


certas, erradas = 0, []
for caminho in sys.argv[1:]:
    elf = ELFFile(open(caminho, "rb"))
    simbolos = list(elf.get_section_by_name(".symtab").iter_symbols())
    for rel in elf.iter_sections():
        if rel.header.sh_type not in ("SHT_REL", "SHT_RELA"):
            continue
        funcs = [s for s in simbolos if s["st_info"]["type"] == "STT_FUNC"
                 and s["st_shndx"] == rel.header.sh_info and s.name in nomes
                 # funções "static" de arquivos diferentes podem ter o mesmo nome
                 # (AlarmCallback): só vale a do mesmo tamanho que a do jogo
                 and s["st_size"] == tamanhos[s.name]]
        for r in rel.iter_relocations():
            alvo_nome = simbolos[r["r_info_sym"]].name
            if alvo_nome not in nomes:
                continue
            for f in funcs:
                ini = f["st_value"] & ~1
                if not ini <= r["r_offset"] < ini + f["st_size"]:
                    continue
                end = nomes[f.name] + r["r_offset"] - ini
                if not BASE <= end < BASE + len(arm9):
                    continue
                d = destino(r["r_info_type"], end)
                if d is None:
                    continue
                # um ponteiro pode apontar para dentro da função (o "addend",
                # ex.: o endereço de retorno guardado com `ldr lr, =rótulo`)
                extra = r["r_addend"] if r["r_info_type"] == 2 and "r_addend" in r.entry else 0
                if d == (nomes[alvo_nome] + extra) & ~1:
                    certas += 1
                else:
                    erradas.append((f.name, end, alvo_nome, d))
print(f"{certas} referências certas, {len(erradas)} erradas")
for f, end, alvo, d in erradas[:20]:
    print(f"   {f} em {end:#x} deveria chamar {alvo}, mas aponta para {d:#x}")
