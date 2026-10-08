"""Compara uma função compilada (.o do mwccarm) com a mesma função no jogo.

É o "objdiff de bolso" da Fase 1: diz se os bytes batem e, se não, mostra o
assembly dos dois lado a lado.

Os bytes que dependem de endereço (o destino de um `bl`, um ponteiro no pool
de constantes) não podem bater no .o, porque ali o linker ainda não colocou
nada: o .o só tem uma "relocação" dizendo "ponha o endereço de X aqui". Por
isso esses bytes são mascarados (comparados como iguais) e marcados com `R`.

Uso:
  python3 comparar.py arquivo.o SIMBOLO_NO_O 0xENDERECO_NO_JOGO [arm9.bin]
  (SIMBOLO_NO_O é o nome como o compilador gerou; veja com --listar)
  python3 comparar.py arquivo.o --listar
Saída: código 0 se 100% igual, 1 se diferente.
"""
import struct, sys
from capstone import Cs, CS_ARCH_ARM, CS_MODE_ARM, CS_MODE_THUMB
from elftools.elf.elffile import ELFFile

BASE = 0x02000000


def carregar(obj_path):
    elf = ELFFile(open(obj_path, "rb"))
    simbolos, mapas = {}, []
    for sec in elf.iter_sections():
        if sec.header.sh_type == "SHT_SYMTAB":
            for s in sec.iter_symbols():
                if s.name in ("$t", "$a", "$d"):
                    # "mapping symbols": marcam onde começa código Thumb ($t),
                    # ARM ($a) ou dados ($d) dentro da seção
                    mapas.append((s["st_shndx"], s["st_value"], s.name))
                elif s["st_info"]["type"] == "STT_FUNC" and s["st_shndx"] != "SHN_UNDEF":
                    simbolos[s.name] = s
    return elf, simbolos, sorted(mapas)


def main():
    obj_path = sys.argv[1]
    elf, simbolos, mapas = carregar(obj_path)
    if sys.argv[2] == "--listar":
        for nome, s in simbolos.items():
            print(f"{nome}  tamanho={s['st_size']:#x}")
        return 0
    nome, endereco = sys.argv[2], int(sys.argv[3], 16)
    arm9_path = sys.argv[4] if len(sys.argv) > 4 else "work/extract/arm9/arm9.bin"
    if nome not in simbolos:
        print(f"símbolo {nome} não está no .o (use --listar)")
        return 1
    s = simbolos[nome]
    sec = elf.get_section(s["st_shndx"])
    dados = sec.data()
    ini = s["st_value"] & ~1
    modo = [m for (sh, v, m) in mapas if sh == s["st_shndx"] and v <= ini and m != "$d"]
    thumb = (s["st_value"] & 1) or (modo and modo[-1] == "$t")
    tam = s["st_size"]
    meu = dados[ini:ini + tam]

    # bytes que o linker ainda vai preencher (relocações dentro da função)
    mascara = set()
    # a seção de relocações que vale para ESTA seção (sh_info aponta para ela;
    # pode haver várias seções .text, por exemplo uma por função de template)
    for rel in elf.iter_sections():
        if rel.header.sh_type not in ("SHT_REL", "SHT_RELA") or rel.header.sh_info != s["st_shndx"]:
            continue
        for r in rel.iter_relocations():
            if ini <= r["r_offset"] < ini + tam:
                o = r["r_offset"] - ini     # bl Thumb, palavra do pool: 4 bytes
                mascara.update(range(o, o + 4))

    jogo = open(arm9_path, "rb").read()[endereco - BASE: endereco - BASE + tam]
    iguais = all(meu[i] == jogo[i] for i in range(tam) if i not in mascara)

    md = Cs(CS_ARCH_ARM, CS_MODE_THUMB if thumb else CS_MODE_ARM)
    passo = 2 if thumb else 4

    def instr(b, off):
        for i in md.disasm(b[off:off + 4], endereco + off):
            return i.size, f"{i.mnemonic} {i.op_str}"
        return passo, ".word " + b[off:off + passo].hex()

    off = 0
    print(f"{'jogo':<40} {'compilado':<40}")
    while off < tam:
        n1, t1 = instr(jogo, off)
        n2, t2 = instr(meu, off)
        n = max(n1, n2)
        mudou = any(meu[i] != jogo[i] for i in range(off, min(off + n, tam)) if i not in mascara)
        reloc = any(i in mascara for i in range(off, off + n))
        marca = "!!" if mudou else ("R " if reloc else "  ")
        print(f"{marca}{endereco + off:08x}  {t1:<30} {t2}")
        off += n
    print(f"tamanho {tam:#x}: {'100% IGUAL' if iguais else 'DIFERENTE'}"
          + (f" ({len(mascara)} bytes de relocação ignorados)" if mascara else ""))
    return 0 if iguais else 1


if __name__ == "__main__":
    sys.exit(main())
