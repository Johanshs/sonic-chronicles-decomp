"""Procura no jogo as funções de bibliotecas já compiladas (.o ou .a).

Se o jogo foi ligado com uma biblioteca (o MSL da Metrowerks, o NitroSDK...),
cada função dela aparece no ARM9 com os mesmos bytes, só com os endereços
preenchidos. Este script compara cada função da biblioteca com todas as
funções do jogo de mesmo tamanho, ignorando os bytes de relocação, e lista as
que batem: assim elas ganham o nome verdadeiro, e a contagem de acertos diz
qual versão da biblioteca o jogo usou.

Uso:
  python3 achar_funcoes.py [--min 8] [--nomes] [--de 0x...] [--aplicar] lib.a [mais.a arquivo.o ...]
    --min N    ignora funções menores que N bytes (as triviais batem com tudo)
    --nomes    lista cada função achada (endereço, nome, de onde veio)
    --de END   só considera funções do jogo a partir deste endereço (a região
               onde a biblioteca foi ligada)
    --aplicar  grava os nomes em symbols.txt, mas só os sem ambiguidade: a
               função da biblioteca bate com UM endereço e o endereço com UM
               nome. Funções idênticas (abs e labs, por exemplo) ficam de fora.
Lê config/YWSE/arm9/symbols.txt e work/extract/arm9/arm9.bin (e o ITCM).
"""
import io, os, re, sys
from elftools.elf.elffile import ELFFile

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def membros_ar(dados):
    """Arquivos dentro de um .a (formato ar): (nome, bytes)."""
    pos, longos = 8, b""
    while pos + 60 <= len(dados):
        cab = dados[pos:pos + 60]
        nome = cab[:16].decode("latin1").strip()
        tam = int(cab[48:58])
        corpo = dados[pos + 60:pos + 60 + tam]
        if nome == "//":
            longos = corpo
        elif nome.startswith("/") and nome[1:].isdigit():
            i = int(nome[1:])
            nome = longos[i:longos.index(b"\n", i)].decode("latin1").rstrip("/")
        if nome not in ("/", "//") and corpo[:4] == b"\x7fELF":
            yield nome.rstrip("/"), corpo
        pos += 60 + tam + (tam & 1)


def funcoes_elf(dados):
    """Funções de um .o: (nome, bytes, posições de relocação)."""
    elf = ELFFile(io.BytesIO(dados))
    simtab = elf.get_section_by_name(".symtab")
    if simtab is None:
        return
    rels = {}
    for sec in elf.iter_sections():
        if sec.header.sh_type in ("SHT_REL", "SHT_RELA"):
            rels.setdefault(sec.header.sh_info, []).extend(r["r_offset"] for r in sec.iter_relocations())
    for s in simtab.iter_symbols():
        if (s["st_info"]["type"] != "STT_FUNC" or s.name.startswith("$")
                or s["st_shndx"] in ("SHN_UNDEF", "SHN_ABS") or s["st_size"] == 0):
            continue
        ini, tam = s["st_value"] & ~1, s["st_size"]
        corpo = elf.get_section(s["st_shndx"]).data()[ini:ini + tam]
        mascara = set()
        for o in rels.get(s["st_shndx"], []):
            if ini <= o < ini + tam:
                mascara.update(range(o - ini, min(o - ini + 4, tam)))
        yield s.name, corpo, mascara


def funcoes_jogo():
    """Funções do jogo por tamanho: {tamanho: [(endereço, nome, bytes)]}."""
    mods = [("config/YWSE/arm9/symbols.txt", "work/extract/arm9/arm9.bin", 0x02000000),
            ("config/YWSE/arm9/itcm/symbols.txt", "work/extract/arm9/itcm.bin", 0x01ff8000)]
    por_tam = {}
    for simb, binario, base in mods:
        dados = open(os.path.join(REPO, binario), "rb").read()
        for linha in open(os.path.join(REPO, simb)):
            m = re.match(r"(\S+) kind:function\((?:arm|thumb),size=(0x[0-9a-f]+)[^)]*\) addr:(0x[0-9a-f]+)", linha)
            if m:
                nome, tam, end = m.group(1), int(m.group(2), 16), int(m.group(3), 16)
                por_tam.setdefault(tam, []).append((end, nome, dados[end - base:end - base + tam]))
    return por_tam


def main():
    args = sys.argv[1:]
    minimo, listar, aplicar, de = 8, False, False, 0
    if "--min" in args:
        i = args.index("--min"); minimo = int(args[i + 1]); del args[i:i + 2]
    if "--de" in args:
        i = args.index("--de"); de = int(args[i + 1], 16); del args[i:i + 2]
    if "--nomes" in args:
        args.remove("--nomes"); listar = True
    if "--aplicar" in args:
        args.remove("--aplicar"); aplicar = True
    jogo = {t: [f for f in fs if f[0] >= de] for t, fs in funcoes_jogo().items()}
    total = achadas = 0
    pares = []
    for caminho in args:
        dados = open(caminho, "rb").read()
        membros = membros_ar(dados) if dados[:8] == b"!<arch>\n" else [(os.path.basename(caminho), dados)]
        for membro, obj in membros:
            for nome, corpo, mascara in funcoes_elf(obj):
                if len(corpo) < minimo:
                    continue
                total += 1
                iguais = [(end, n) for end, n, b in jogo.get(len(corpo), [])
                          if all(b[i] == corpo[i] for i in range(len(corpo)) if i not in mascara)]
                pares.extend((end, nome) for end, _ in iguais)
                if iguais:
                    achadas += 1
                    if listar:
                        for end, n in iguais:
                            print(f"{end:#010x} {nome:40} {membro}" + (f"  (hoje: {n})" if n != nome else ""))
    print(f"# {achadas} de {total} funções (>= {minimo} bytes) achadas no jogo")
    if aplicar:
        aplicar_nomes(pares)


def aplicar_nomes(pares):
    por_nome, por_end = {}, {}
    for end, nome in set(pares):
        por_nome.setdefault(nome, set()).add(end)
        por_end.setdefault(end, set()).add(nome)
    novos = {end: nome for end, nome in set(pares)
             if len(por_nome[nome]) == 1 and len(por_end[end]) == 1 and "@" not in nome}
    caminho = os.path.join(REPO, "config/YWSE/arm9/symbols.txt")
    linhas = open(caminho).read().split("\n")
    existentes = {l.split(" ", 1)[0] for l in linhas if l}
    trocados = 0
    for i, linha in enumerate(linhas):
        m = re.match(r"(\S+) (kind:function.* addr:(0x[0-9a-f]+))", linha)
        if m and int(m.group(3), 16) in novos:
            nome = novos[int(m.group(3), 16)]
            if nome != m.group(1) and nome not in existentes:
                linhas[i] = f"{nome} {m.group(2)}"
                existentes.add(nome)
                trocados += 1
    open(caminho, "w").write("\n".join(linhas))
    print(f"# {trocados} nomes gravados em {caminho} ({len(novos)} sem ambiguidade)")


if __name__ == "__main__":
    main()
