"""Confere as funções decompiladas SEM a ROM (para o CI do GitHub).

O build completo (montar_rom.sh) precisa da ROM, que não pode ir para o
GitHub. Mas para saber se uma mudança em src/ quebrou o match, basta comparar
os bytes de cada função compilada com os do jogo. Em vez dos bytes, guardamos
só o SHA-1 deles em decomp/compilador/esperado.txt: o hash permite conferir
sem conter nada do jogo (e esses bytes são exatamente o que o nosso C++ gera,
então não há segredo neles).

Os bytes que o linker ainda vai preencher (relocações) são zerados dos dois
lados antes do hash, como no comparar.py.

Uso:
  python3 conferir_sem_rom.py                  compila e confere (o que o CI roda)
  python3 conferir_sem_rom.py --gerar arm9.bin regrava esperado.txt a partir do jogo
"""
import hashlib, os, subprocess, sys, tempfile
from elftools.elf.elffile import ELFFile

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CASOS = os.path.join(REPO, "decomp/compilador/casos.txt")
ESPERADO = os.path.join(REPO, "decomp/compilador/esperado.txt")
BASE = 0x02000000


def funcao(obj, nome):
    """Bytes da função no .o e as posições de relocação dentro dela."""
    elf = ELFFile(open(obj, "rb"))
    for s in elf.get_section_by_name(".symtab").iter_symbols():
        if s.name == nome and s["st_shndx"] != "SHN_UNDEF":
            break
    else:
        raise SystemExit(f"{nome} não está em {obj}")
    ini, tam = s["st_value"] & ~1, s["st_size"]
    dados = elf.get_section(s["st_shndx"]).data()[ini:ini + tam]
    mascara = set()
    for rel in elf.iter_sections():
        if rel.header.sh_type in ("SHT_REL", "SHT_RELA") and rel.header.sh_info == s["st_shndx"]:
            for r in rel.iter_relocations():
                if ini <= r["r_offset"] < ini + tam:
                    mascara.update(range(r["r_offset"] - ini, r["r_offset"] - ini + 4))
    return dados, mascara


def sha(dados, mascara):
    return hashlib.sha1(bytes(0 if i in mascara else b for i, b in enumerate(dados))).hexdigest()


def main():
    gerar = len(sys.argv) > 2 and sys.argv[1] == "--gerar"
    arm9 = open(sys.argv[2], "rb").read() if gerar else None
    esperado = {}
    if not gerar:
        for linha in open(ESPERADO):
            if linha.strip() and not linha.startswith("#"):
                nome, h = linha.split()
                esperado[nome] = h
    saida, falhas = [], 0
    with tempfile.TemporaryDirectory() as tmp:
        for n, linha in enumerate(open(CASOS)):
            if not linha.strip() or linha.startswith("#"):
                continue
            fonte, nome, end = linha.split()
            obj = os.path.join(tmp, f"{n}.o")
            subprocess.run([os.path.join(REPO, "decomp/tools/compilar.sh"), fonte, obj],
                           cwd=REPO, check=True, stdout=subprocess.DEVNULL)
            dados, mascara = funcao(obj, nome)
            if gerar:
                jogo = arm9[int(end, 16) - BASE:int(end, 16) - BASE + len(dados)]
                saida.append(f"{nome} {sha(jogo, mascara)}")
                continue
            ok = sha(dados, mascara) == esperado.get(nome)
            falhas += not ok
            print(f"{'OK   ' if ok else 'FALHA'} {end} {nome} ({fonte})")
    if gerar:
        with open(ESPERADO, "w") as f:
            f.write("# SHA-1 dos bytes de cada função do jogo (relocações zeradas).\n"
                    "# Gerado por: python3 decomp/tools/conferir_sem_rom.py --gerar arm9.bin\n")
            f.write("\n".join(saida) + "\n")
        print(f"{len(saida)} funções gravadas em {ESPERADO}")
        return 0
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main())
