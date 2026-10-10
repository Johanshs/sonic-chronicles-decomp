#!/usr/bin/env python3
"""Lê e escreve bancos de cheats `usrcheat.dat` (formato "R4 CheatCode").

É o banco usado pelo Pico Launcher (`/_pico/usrcheat.dat`), pelos kernels de R4/Wood e
pelo TWiLight Menu++. Uso:

    python3 analise/tools/usrcheat.py listar  usrcheat.dat YWSE
    python3 analise/tools/usrcheat.py extrair usrcheat.dat saida.dat YWSE [OUTRO ...]
    python3 analise/tools/usrcheat.py inserir usrcheat.dat cheats/YWSE.txt saida.dat

`extrair` gera um banco menor só com os jogos pedidos (útil para o cartão carregar mais
rápido). `inserir` acrescenta, no fim da entrada do jogo, as pastas e os códigos de um
arquivo de texto (formato na função `ler_txt_pastas`). O arquivo original nunca é
alterado. Se o banco já tiver pastas nossas (nome começando por "Projeto"), elas são
trocadas pelas novas, então dá para rodar de novo sobre o banco que está no cartão. Antes
de gravar no cartão, confira a forma dos códigos com
`python3 analise/tools/ar_codes.py validar cheats/YWSE.txt`.

Formato (descoberto lendo o banco do DeadSkullzJr e conferido pela ida e volta):

    0x000  "R4 CheatCode\\0", u32 versão (0x100), título, ...
    0x04C  u32 codificação; 0x100: índice de jogos, 16 bytes por jogo:
           char código[4]   ex. "YWSE"
           u32  crc         ~crc32(cabeçalho da ROM, 0x200 bytes)
           u32  posição     absoluta, do bloco do jogo
           u32  0
           (o índice termina com uma entrada de 16 bytes zerados)

    bloco do jogo:
           nome\\0 (alinhado a 4)
           u32  nº de itens | flags (bits altos)
           u32  x8  "master codes" (identificação; normalmente 0, 1, 0...)
           itens, em sequência:
             pasta:  u32 (0x10000000 | nº de filhos)  [0x01000000 = só um ativo]
                     nome\\0 descrição\\0 (alinhado a 4)
             cheat:  u32 (nº de palavras a seguir) [0x01000000 = ligado]
                     nome\\0 descrição\\0 (alinhado a 4)
                     u32 nº de palavras de código, e as palavras (2 por linha AR)
"""
import struct
import sys
import zlib

PASTA = 0x10000000
UM_SO = 0x01000000
LIGADO = 0x01000000


def crc_da_rom(caminho_rom):
    """O identificador que o banco usa: ~CRC32 dos 0x200 bytes do cabeçalho."""
    with open(caminho_rom, "rb") as f:
        return zlib.crc32(f.read(0x200)) ^ 0xFFFFFFFF


def _cstr(b, p):
    n = b.index(b"\0", p)
    return b[p:n].decode("latin-1"), n + 1


def _alinha(p):
    return (p + 3) & ~3


class Banco:
    def __init__(self, dados):
        if not dados.startswith(b"R4 CheatCode"):
            raise ValueError("não é um usrcheat.dat (falta 'R4 CheatCode')")
        self.b = dados
        self.jogos = []  # (código, crc, posição)
        p = 0x100
        while True:
            cod, crc, pos, _ = struct.unpack_from("<4sIII", dados, p)
            if pos == 0 or cod == b"\0\0\0\0":
                self.fim_indice = p
                break
            self.jogos.append((cod.decode("latin-1"), crc, pos))
            p += 16

    def bloco(self, i):
        """Bytes do bloco do jogo i (vai até o início do próximo bloco)."""
        ini = self.jogos[i][2]
        fim = min((j[2] for j in self.jogos if j[2] > ini), default=len(self.b))
        return self.b[ini:fim]

    def achar(self, codigo, crc=None):
        return [i for i, j in enumerate(self.jogos) if j[0] == codigo and (crc is None or j[1] == crc)]


def ler_bloco(blk):
    """Devolve (nome, cabeçalho de 9 palavras, itens). Item: dict com tipo, nome, desc..."""
    nome, p = _cstr(blk, 0)
    p = _alinha(p)
    cab = list(struct.unpack_from("<9I", blk, p))
    p += 36
    itens = []
    restantes = cab[0] & 0xFFFF
    while restantes > 0 and p + 4 <= len(blk):
        h = struct.unpack_from("<I", blk, p)[0]
        if h & PASTA:
            n, q = _cstr(blk, p + 4)
            d, q = _cstr(blk, q)
            q = _alinha(q)
            itens.append({"tipo": "pasta", "flags": h, "filhos": h & 0xFFFFFF & ~UM_SO, "nome": n, "desc": d})
            p = q
        else:
            palavras = h & 0xFFFFFF
            fim = p + 4 + palavras * 4
            n, q = _cstr(blk, p + 4)
            d, q = _cstr(blk, q)
            q = _alinha(q)
            nc = struct.unpack_from("<I", blk, q)[0]
            codigos = list(struct.unpack_from(f"<{nc}I", blk, q + 4))
            itens.append({"tipo": "cheat", "flags": h, "ligado": bool(h & LIGADO), "nome": n,
                          "desc": d, "codigos": codigos})
            p = fim
        restantes -= 1
    return nome, cab, itens


def _str_alinhadas(*textos):
    raw = b"".join(t.encode("latin-1") + b"\0" for t in textos)
    return raw + b"\0" * (_alinha(len(raw)) - len(raw))


def item_cheat(nome, desc, codigos, ligado=False):
    corpo = _str_alinhadas(nome, desc) + struct.pack(f"<I{len(codigos)}I", len(codigos), *codigos)
    return struct.pack("<I", (len(corpo) // 4) | (LIGADO if ligado else 0)) + corpo


def item_pasta(nome, desc, filhos, um_so=False):
    return struct.pack("<I", PASTA | (UM_SO if um_so else 0) | filhos) + _str_alinhadas(nome, desc)


PASTA_PADRAO = "Projeto sonic-chronicles-decomp"


def ler_txt_pastas(caminho):
    """Formato de texto dos nossos cheats:

        # comentário
        @pasta Nome da pasta        (os cheats seguintes ficam nela)
        @escolha Nome da pasta      (pasta em que só um cheat pode ficar ligado)
        ; descrição da pasta (opcional, logo depois do @)
        [Nome do cheat]
        ; descrição (opcional, uma linha)
        020F64C0 000003E8

    Devolve [{"nome", "desc", "um_so", "cheats"}]. Cheats antes de qualquer @ ficam
    numa pasta de nome vazio (o `inserir` a chama de PASTA_PADRAO).
    """
    pastas = [{"nome": "", "desc": "", "um_so": False, "cheats": []}]
    atual = None
    with open(caminho, encoding="utf-8") as f:
        texto = f.read().splitlines()
    for linha in texto:
        linha = linha.strip()
        if not linha or linha.startswith("#"):
            continue
        if linha.startswith(("@pasta ", "@escolha ")):
            tipo, nome = linha[1:].split(None, 1)
            pastas.append({"nome": nome.strip(), "desc": "", "um_so": tipo == "escolha",
                           "cheats": []})
            atual = pastas[-1]
        elif linha.startswith("[") and linha.endswith("]"):
            atual = {"nome": linha[1:-1], "desc": "", "codigos": []}
            pastas[-1]["cheats"].append(atual)
        elif linha.startswith(";"):
            atual["desc"] = linha[1:].strip()
        else:
            a, v = linha.split()[:2]
            atual["codigos"] += [int(a, 16), int(v, 16)]
    return [p for p in pastas if p["cheats"]]


def ler_txt(caminho):
    """Todos os cheats do arquivo, sem as pastas."""
    return [c for p in ler_txt_pastas(caminho) for c in p["cheats"]]


def montar(banco, blocos):
    """Monta um banco novo: cabeçalho do original + os blocos [(código, crc, bytes)]."""
    cab = bytearray(banco.b[:0x100])
    indice = 0x100 + 16 * (len(blocos) + 1)
    pos = _alinha(indice)
    saida_idx, corpo = bytearray(), bytearray()
    for cod, crc, blk in blocos:
        saida_idx += struct.pack("<4sIII", cod.encode("latin-1"), crc, pos + len(corpo), 0)
        corpo += blk
    saida_idx += b"\0" * 16  # fim do índice: entrada zerada
    return bytes(cab + saida_idx + b"\0" * (pos - indice) + corpo)


def inserir_pastas(blk, pastas, trocar="Projeto"):
    """Acrescenta as `pastas` [(nome, desc, cheats, um_so)] no fim do bloco de um jogo.

    O formato só tem um nível de pasta: cada pasta nossa vira uma pasta do jogo. As
    pastas que já existirem com nome começando por `trocar` (uma versão anterior dos
    nossos cheats) são removidas antes, com os cheats delas; o resto fica intacto.
    """
    nome, cab, itens = ler_bloco(blk)
    ini = _alinha(len(nome.encode("latin-1")) + 1)
    # Onde cada item começa e termina (o bloco pode ter preenchimento depois).
    p, trechos = ini + 36, []
    for it in itens:
        h = struct.unpack_from("<I", blk, p)[0]
        if it["tipo"] == "pasta":
            q = p + 4
            for _ in range(2):
                q = blk.index(b"\0", q) + 1
            fim = _alinha(q)
        else:
            fim = p + 4 + (h & 0xFFFFFF) * 4
        trechos.append(blk[p:fim])
        p = fim
    mantidos, pular = [], 0
    for it, raw in zip(itens, trechos):
        if pular:
            pular -= 1
        elif trocar and it["tipo"] == "pasta" and it["nome"].startswith(trocar):
            pular = it["filhos"]
        else:
            mantidos.append(raw)
    novos = []
    for nome_pasta, desc, cheats, um_so in pastas:
        novos.append(item_pasta(nome_pasta, desc, len(cheats), um_so))
        novos += [item_cheat(c["nome"], c["desc"], c["codigos"]) for c in cheats]
    n = len(mantidos) + len(novos)
    cab[0] = (cab[0] & ~0xFFFF) | n
    return blk[:ini] + struct.pack("<9I", *cab) + b"".join(mantidos) + b"".join(novos)


def inserir_pasta(blk, nome_pasta, desc, cheats):
    """Acrescenta uma pasta com `cheats` no fim do bloco de um jogo (sem trocar nada)."""
    return inserir_pastas(blk, [(nome_pasta, desc, cheats, False)], trocar=None)


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    acao, arq = sys.argv[1], sys.argv[2]
    banco = Banco(open(arq, "rb").read())
    if acao == "listar":
        for i in banco.achar(sys.argv[3]):
            cod, crc, pos = banco.jogos[i]
            nome, cab, itens = ler_bloco(banco.bloco(i))
            print(f"{cod} crc={crc:08X} @0x{pos:X}  {nome}  ({cab[0] & 0xFFFF} itens)")
            for it in itens:
                if it["tipo"] == "pasta":
                    print(f"  [pasta] {it['nome']}  ({it['filhos']} cheats) {it['desc']}")
                else:
                    print(f"    - {it['nome']}{'  (' + it['desc'] + ')' if it['desc'] else ''}")
                    c = it["codigos"]
                    for k in range(0, len(c), 2):
                        print(f"        {c[k]:08X} {c[k + 1]:08X}")
    elif acao == "extrair":
        saida, codigos = sys.argv[3], set(sys.argv[4:])
        blocos = [(j[0], j[1], banco.bloco(i)) for i, j in enumerate(banco.jogos) if j[0] in codigos]
        open(saida, "wb").write(montar(banco, blocos))
        print(f"{len(blocos)} jogos → {saida}")
    elif acao == "inserir":
        pastas = [(p["nome"] or PASTA_PADRAO, p["desc"], p["cheats"], p["um_so"])
                  for p in ler_txt_pastas(sys.argv[3])]
        saida = sys.argv[4]
        cod = sys.argv[5] if len(sys.argv) > 5 else "YWSE"
        blocos = []
        for i, j in enumerate(banco.jogos):
            blk = banco.bloco(i)
            if j[0] == cod:
                blk = inserir_pastas(blk, pastas)
            blocos.append((j[0], j[1], blk))
        open(saida, "wb").write(montar(banco, blocos))
        n = sum(len(p[2]) for p in pastas)
        print(f"{n} cheats em {len(pastas)} pastas inseridos em {cod} → {saida}")
    else:
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
