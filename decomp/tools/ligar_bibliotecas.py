"""Divide uma região de biblioteca do ARM9 em arquivos-fonte e liga os .o compilados.

nitrosdk.sh e nitrosystem.sh compilam o fonte decompilado das bibliotecas da
Nintendo, e achar_funcoes.py dá nome às funções. Este script dá o passo seguinte:
em vez de usar o assembly cortado do jogo, o build passa a ligar o .o compilado de
cada arquivo .c, e a ROM continua idêntica. É o "pronto quando" da Fase 2.

Como funciona:
  1. Percorre as funções do jogo na região, em ordem de endereço, e descobre de qual
     .o cada uma veio. O linker põe as funções de um arquivo juntas, então a região
     vira uma sequência de faixas, uma por arquivo. Quando uma função pequena existe
     em vários .o, vence o .o que cobre a faixa mais longa a partir dali.
  2. Acha os dados de cada arquivo (.data, .rodata, .bss) pelas relocações: se a
     função X do .o lê `.bss+8` e no jogo o ponteiro vale 0x0216abc8, a .bss daquele
     arquivo começa em 0x0216abc0. Os bytes de .data e .rodata são conferidos.
  3. Grava cada arquivo em delinks.txt como `complete` (o build liga o .o) e dá a cada
     símbolo do jogo o nome que o .o usa, marcando os `static` como `local`.
As funções que o SDK põe no ITCM (.itcm) e as variáveis do DTCM (.dtcm, .dtcm.bss)
seguem o mesmo caminho e vão para itcm/ e dtcm/ com o apelido "x.itcm.c"/"x.dtcm.c".

Uso: python3 ligar_bibliotecas.py NOME FONTE OBJ DE ATE [--aplicar]
  NOME   prefixo dos arquivos em delinks.txt (NitroSystem ou NitroSDK)
  FONTE  a pasta do fonte (work/NitroSystem), ou - quando não há fonte (o MSL)
  OBJ    a pasta dos .o compilados (work/bibliotecas/nitrosystem)
  DE ATE a região do ARM9
Sem --aplicar, só mostra a divisão e o que não bate.
"""
import bisect, glob, io, os, re, struct, sys
from elftools.elf.elffile import ELFFile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import achar_funcoes as af

REPO = af.REPO
SIMBOLOS = os.path.join(REPO, "config/YWSE/arm9/symbols.txt")
SIMBOLOS_ITCM = os.path.join(REPO, "config/YWSE/arm9/itcm/symbols.txt")
SIMBOLOS_DTCM = os.path.join(REPO, "config/YWSE/arm9/dtcm/symbols.txt")
DELINKS = os.path.join(REPO, "config/YWSE/arm9/delinks.txt")
RELOCS = os.path.join(REPO, "config/YWSE/arm9/relocs.txt")
BASE = 0x02000000
ITCM = (0x01ff8000, 0x01ffedd0)                     # o código que roda no ITCM
DTCM = 0x027e0000
# os três módulos do ARM9: (endereço, bytes)
MEMORIA = [(BASE, open(os.path.join(REPO, "work/extract/arm9/arm9.bin"), "rb").read()),
           (ITCM[0], open(os.path.join(REPO, "work/extract/arm9/itcm.bin"), "rb").read()),
           (DTCM, open(os.path.join(REPO, "work/extract/arm9/dtcm.bin"), "rb").read())]
DADOS = {".rodata": (0x020ef814, 0x020f4ff0), ".data": (0x020f5260, 0x021090e0),
         ".dtcm": (DTCM, 0x027e1040), ".version": (BASE, BASE + 0x1000),
         # as tabelas de exceções do C++ (o MSL e o Runtime as têm)
         ".exception": (0x020eccb4, 0x020ed01c), ".exceptix": (0x020ed01c, 0x020ed9c4)}
# as partes de um arquivo que ficam longe do resto e entram em delinks.txt com outro
# nome ("x.itcm.c"): seção do .o -> (apelido, módulo, seção do módulo). O ITCM e o DTCM
# são outros módulos; a .version ("[SDK+NINTENDO:BACKUP]") o .lcf da Nintendo punha no
# começo do ARM9, logo depois do crt0
OUTROS_MODULOS = {".itcm": ("itcm", "itcm", ".text"), ".dtcm": ("dtcm", "dtcm", ".data"),
                  ".dtcm.bss": ("dtcm", "dtcm", ".bss"), ".version": ("version", "main", ".text")}
ENDERECOS, THUMB, TODOS, FUNCOES = {}, set(), set(), []   # nome -> endereço; Thumb; com símbolo
NOMES_TODOS = set()
# para onde cada nome aponta, para desempatar pelas chamadas (concorda): os nomes do jogo
# e, depois da primeira volta, as funções que a volta achou (o expl do .o chama exp; o
# jogo ainda não tinha nome para exp)
ALVOS = {}
# os símbolos que montar_rom.sh define no .lcf (SDK_SYS_STACKSIZE...)
LINKER = set(re.findall(r"^\s*(\w+)\s*=", open(os.path.join(REPO, "config/YWSE/arm9/simbolos_linker.lcf")).read(), re.M))
# as seções de código do ARM9 (.text e .init), do cabeçalho de delinks.txt
CODIGO = [(int(a, 16), int(b, 16)) for a, b in re.findall(
    r"^    \.\w+ +start:(0x[0-9a-f]+) end:(0x[0-9a-f]+) kind:code", open(DELINKS).read(), re.M)]
# e os que o .lcf do dsd já define (o começo e o fim da tabela de exceções)
LINKER |= {"__exception_table_start__", "__exception_table_end__"}
for _f in (SIMBOLOS, SIMBOLOS_ITCM, SIMBOLOS_DTCM):
    for _l in open(_f):
        _m = re.match(r"(\S+) kind:(\S+).* addr:(0x[0-9a-f]+)", _l)
        if _m:
            _e = int(_m.group(3), 16)
            TODOS.add(_e)
            NOMES_TODOS.add(_m.group(1))
            ENDERECOS.setdefault(_m.group(1), _e)
            _t = re.match(r"function\((arm|thumb),size=(0x[0-9a-f]+)", _m.group(2))
            if _t:
                FUNCOES.append((_e, _e + int(_t.group(2), 16)))
                if _t.group(1) == "thumb":
                    THUMB.add(_e)
FUNCOES.sort()


def no_meio_de_funcao(end):
    i = bisect.bisect_right(FUNCOES, (end, 1 << 32)) - 1
    return i >= 0 and FUNCOES[i][0] < end < FUNCOES[i][1]


def escopo(s):
    """"local" (static), "weak" (SDK_WEAK_SYMBOL: pode ser trocada pelo jogo) ou "".
    O mwcc grava as "weak" com o código 14, específico da Metrowerks."""
    return {"STB_LOCAL": "local", "STB_WEAK": "weak", 14: "weak"}.get(s["st_info"]["bind"], "")


class Objeto:
    """Um .o compilado: funções, seções de dados, símbolos e relocações."""

    def __init__(self, caminho):
        self.caminho = caminho
        dados = open(caminho, "rb").read()
        self.funcoes = list(af.funcoes_elf(dados))
        elf = ELFFile(io.BytesIO(dados))
        self.secoes = {}            # índice -> (nome, tamanho, bytes ou None)
        self.alinhamento = {}       # índice -> alinhamento da seção
        for i, s in enumerate(elf.iter_sections()):
            if s.name in (".data", ".rodata", ".bss", ".sdata", ".sbss", ".dtcm", ".dtcm.bss", ".version",
                          ".exception", ".exceptix") and s.data_size:
                corpo = None if s.header.sh_type == "SHT_NOBITS" else s.data()
                self.secoes[i] = (s.name, s.data_size, corpo)
                self.alinhamento[i] = max(s.header.sh_addralign, 1)
        self.nomes_sec = [s.name for s in elf.iter_sections()]
        self.simbolos = list(elf.get_section_by_name(".symtab").iter_symbols())
        self.rels = {}              # índice da seção -> [(offset, tipo, símbolo, addend)]
        for s in elf.iter_sections():
            if s.header.sh_type in ("SHT_REL", "SHT_RELA"):
                self.rels.setdefault(s.header.sh_info, []).extend(
                    (r["r_offset"], r["r_info_type"], r["r_info_sym"], r.entry.get("r_addend", 0))
                    for r in s.iter_relocations())
        # onde cada função está no .o: nome -> (índice da seção, início, tamanho, escopo)
        self.onde = {}
        for s in self.simbolos:
            if s["st_info"]["type"] == "STT_FUNC" and isinstance(s["st_shndx"], int):
                self.onde[s.name] = (s["st_shndx"], s["st_value"] & ~1, s["st_size"],
                                     escopo(s))
        # código em assembly (o Mathlib: _d_add.s): a seção .text inteira é um bloco, sem
        # funções com tamanho. Os símbolos globais dentro dele viram as "funções", do
        # símbolo até o próximo; dois nomes no mesmo lugar (_d_add e _dadd) viram apelidos
        self.blocos = []                # [(seção, bytes, máscara, [(offset, nome, apelidos)])]
        for i, s in enumerate(elf.iter_sections()):
            if s.name != ".text" or not s.data_size or any(
                    x["st_shndx"] == i and x["st_size"] for x in self.simbolos
                    if x["st_info"]["type"] == "STT_FUNC" and not x.name.startswith("$")):
                continue
            mascara = set()
            for off, *_ in self.rels.get(i, []):
                mascara.update(range(off, off + 4))
            por_off = {}
            for x in self.simbolos:
                if (x["st_shndx"] == i and x.name and not x.name.startswith("$")
                        and x["st_info"]["type"] in ("STT_NOTYPE", "STT_FUNC")):
                    por_off.setdefault(x["st_value"] & ~1, []).append(x)
            nomes = []
            for off in sorted(por_off):
                xs = sorted(por_off[off], key=lambda x: (x.name not in ENDERECOS, x["st_info"]["bind"] != "STB_GLOBAL", x.name))
                nomes.append((off, xs[0].name, [x.name for x in xs[1:]]))
            for k, (off, nome, _) in enumerate(nomes):
                fim = nomes[k + 1][0] if k + 1 < len(nomes) else s.data_size
                x = por_off[off][0] if por_off[off][0].name == nome else next(y for y in por_off[off] if y.name == nome)
                self.onde[nome] = (i, off, fim - off, escopo(x))
            if nomes:
                self.blocos.append((i, s.data(), mascara, nomes))


def colocar_blocos(objs, de, ate):
    """Onde cada bloco em assembly está no jogo: [(endereço, objeto, bloco)]. Os bytes têm
    de bater (menos os da relocação); se o bloco aparece mais de uma vez, vale o lugar
    onde as chamadas e ponteiros dele caem nos endereços certos."""
    regiao = ler(de, ate - de)
    postos = []
    for o in objs:
        for bloco in o.blocos:
            sec, corpo, mascara, nomes = bloco
            padrao = b"".join(b"." if k in mascara else re.escape(corpo[k:k + 1]) for k in range(len(corpo)))
            achados = [de + m.start() for m in re.finditer(padrao, regiao, re.S) if m.start() % 2 == 0]
            if len(achados) > 1:
                def nota(base):
                    pontos = 0
                    for off, tipo, sym, add in o.rels.get(sec, []):
                        alvo = o.simbolos[sym].name
                        d = destino(tipo, base + off) if alvo in ENDERECOS else None
                        if d is not None:
                            pontos += 1 if (d - (add if tipo == 2 else 0)) & ~1 == ENDERECOS[alvo] else -1
                    return pontos
                notas = sorted(((nota(a), a) for a in achados), reverse=True)
                achados = [notas[0][1]] if notas[0][0] > notas[1][0] else []
            if len(achados) == 1:
                postos.append((achados[0], o, bloco))
    # um bloco que cai dentro de outro (_div32_common_f é o fim do _u32_div_f, com os
    # mesmos bytes) não é ele: fica o maior
    aceitos = []
    for a, o, bloco in sorted(postos, key=lambda x: -len(x[2][1])):
        if not any(a < b + len(bb[1]) and b < a + len(bloco[1]) for b, _, bb in aceitos):
            aceitos.append((a, o, bloco))
    return sorted(aceitos, key=lambda x: x[0])


def dividir(objs, de, ate, conhecidos, secao=".text", blocos=()):
    """Passo 1: [(endereço, objeto, nome da função no .o)] para cada função da região.
    Só valem as funções do .o que estão na `secao` (.text no ARM9, .itcm no ITCM). Os
    blocos em assembly já colocados (colocar_blocos) entram inteiros."""
    faixas = [(a, a + len(b[1])) for a, _, b in blocos]
    jogo = sorted(f for fs in af.funcoes_jogo().values() for f in fs if de <= f[0] < ate
                  and not any(a <= f[0] < b for a, b in faixas))
    por_tam = {}
    for o in objs:
        for i, (n, c, m) in enumerate(o.funcoes):
            if o.nomes_sec[o.onde[n][0]] == secao:
                por_tam.setdefault(len(c), []).append((o, i, n, c, m))
    # funções que o dsd não conseguiu medir (size=0, "unknown": __throw): o tamanho vem
    # da função do .o cujos bytes batem ali
    for k, (end, nome, b) in enumerate(jogo):
        if not b:
            tams = {t for t, fs in por_tam.items() for o, i, n, c, m in fs
                    if all(x == y for j, (x, y) in enumerate(zip(ler(end, t), c)) if j not in m)}
            if len(tams) == 1:
                jogo[k] = (end, nome, ler(end, tams.pop()))
    cand = [[(o, i, n) for o, i, n, c, m in por_tam.get(len(b), [])
             if all(b[k] == c[k] for k in range(len(c)) if k not in m)] for _, _, b in jogo]

    def escolher(o, k, usados, ultima):
        """A função de `o` para o endereço k. Funções iguais a menos das relocações
        (AllocatorFreeForExpHeap e AllocatorFreeForUnitHeap só diferem no que
        chamam) se separam pelo destino das chamadas no jogo; se ainda empatar
        (os NNS_G3dFree*, idênticos), vale a ordem do arquivo: o linker põe as
        funções na ordem das seções do .o, então vem a primeira depois da `ultima`."""
        livres = [(i, n) for oo, i, n in cand[k] if oo is o and i not in usados]
        if len(livres) > 1:
            livres.sort(key=lambda x: (-concorda(o, x[1], jogo[k][0]),
                                       -apontado(o, x[1], jogo[k][0], conhecidos),
                                       o.onde[x[1]][0] < ultima, o.onde[x[1]][0]))
        return livres[0] if livres else None

    def corrida(o, k):
        usados, j, ultima = set(), k, -1
        while j < len(jogo):
            x = escolher(o, j, usados, ultima)
            if x is None:
                break
            usados.add(x[0])
            ultima = o.onde[x[1]][0]
            j += 1
        return j - k

    seq, ja, k, problemas, feitos = [], set(), 0, [], set()
    quebrados = {}                                  # id(.o) -> por que ele não pode ser ligado
    while k < len(jogo):
        opcoes = {id(o): o for o, i, n in cand[k] if id(o) not in ja}
        if not opcoes:
            # um arquivo já usado que reaparece: alguma função no meio dele não bateu
            opcoes = {id(o): o for o, i, n in cand[k]}
            for o in opcoes.values():
                quebrados.setdefault(id(o), "uma função no meio dele não bate com o fonte")
        if not opcoes:
            seq.append((jogo[k][0], len(jogo[k][2]), None, jogo[k][1]))
            k += 1
            continue
        # empate (dois arquivos com o mesmo código): vale o arquivo cujos ponteiros
        # nos dados apontam para este trecho do código; depois, o que chama o que o
        # jogo chama (PXI_Init e CARD_WaitBackupAsync são o mesmo "pula para X", com
        # X diferente)
        # Mas antes de tudo vale o sinal do "concorda" da primeira função: os stubs de
        # 8 bytes "ldr r3, =X; bx r3" são iguais em dezenas de .o, e o math.o, com dois
        # seguidos, ganharia na corrida do w_exp.o, cujo exp pula para o __ieee754_exp
        # que o jogo pula
        def nota(o):
            n = corrida(o, k)
            c = concorda(o, escolher(o, k, set(), -1)[1], jogo[k][0])
            return (max(-1, min(c, 1)), n,
                    apontam(o, jogo[k][0], jogo[k + n - 1][0] + len(jogo[k + n - 1][2]), conhecidos), c)
        o = max(opcoes.values(), key=nota)
        if corrida(o, k) == 1 and len(jogo[k][2]) <= 2:
            # um arquivo inteiro de 2 bytes ("b .", o __rt_div0) é pouca prova: no jogo
            # esse "b ." era o fim de outra função, que o dsd cortou em três
            seq.append((jogo[k][0], len(jogo[k][2]), None, jogo[k][1]))
            k += 1
            continue
        ja.add(id(o))
        usados, ultima = set(), -1
        for _ in range(corrida(o, k)):
            i, n = escolher(o, k, usados, ultima)
            usados.add(i)
            ultima = o.onde[n][0]
            # o linker não troca a ordem das funções de um arquivo: fora de ordem quer
            # dizer que o nosso .o saiu diferente do da Nintendo
            if any(o.onde[m][0] > ultima for m in o.onde if (o, m) in feitos):
                quebrados.setdefault(id(o), f"as funções saem em outra ordem ({n})")
            feitos.add((o, n))
            seq.append((jogo[k][0], len(jogo[k][2]), o, n))
            k += 1
    trocar_gemeas(seq)
    for a, o, (sec, corpo, mascara, nomes) in blocos:
        for off, nome, _ in nomes:
            seq.append((a + off, o.onde[nome][2], o, nome))
    seq.sort(key=lambda x: x[0])
    return seq, problemas, quebrados


def trocar_gemeas(seq):
    """Duas funções iguais no mesmo .o (strtold e strtod, porque double e long double são
    o mesmo tipo no DS) empatam em tudo, e escolher() fica com a primeira. Mas o jogo
    guardou só uma, e quem diz qual é a função vizinha que a chama: o atof do .o chama
    strtod, e o atof do jogo aponta para este endereço. Se o nome errado ficasse, o build
    manteria as duas (uma pelo nome em symbols.txt, outra pelo atof)."""
    pos = {(id(o), n): j for j, (_, _, o, n) in enumerate(seq) if o}
    codigo = lambda o, n: next((c, m) for nn, c, m in o.funcoes if nn == n)
    for a, _, o, n in list(seq):
        if not o:
            continue
        sec, ini, tam, _ = o.onde[n]
        for off, tipo, sym, add in o.rels.get(sec, []):
            alvo = o.simbolos[sym].name
            if not ini <= off < ini + tam or alvo not in o.onde or (id(o), alvo) in pos \
                    or alvo not in {nn for nn, _, _ in o.funcoes}:
                continue
            d = destino(tipo, a + off - ini)
            if d is None:
                continue
            d = (d - (add if tipo == 2 else 0)) & ~1
            for j, (a2, t2, o2, n2) in enumerate(seq):
                if o2 is not o or a2 != d or n2 not in {nn for nn, _, _ in o.funcoes}:
                    continue
                (c, m), (c2, _) = codigo(o, alvo), codigo(o, n2)
                if len(c) == len(c2) and all(c[k] == c2[k] for k in range(len(c)) if k not in m) \
                        and concorda(o, alvo, a2) >= concorda(o, n2, a2):
                    print(f"   {n2} em {a2:#x} é na verdade {alvo}: {n} aponta para ele")
                    seq[j] = (a2, t2, o, alvo)
                    pos[(id(o), alvo)] = pos.pop((id(o), n2))


def apontam(o, ini, fim, conhecidos):
    """Ponteiros para funções do próprio .o, nos dados de endereço conhecido, que caem
    (+1) ou não (-1) no trecho [ini, fim) do jogo."""
    pontos = 0
    for s in o.simbolos:
        sec = s["st_shndx"]
        if sec not in o.secoes or s["st_info"]["bind"] != "STB_GLOBAL" or s.name not in conhecidos:
            continue
        base = conhecidos[s.name] - s["st_value"]
        for off, tipo, sym, add in o.rels.get(sec, []):
            if tipo == 2 and o.simbolos[sym].name in o.onde and s["st_value"] <= off < s["st_value"] + max(s["st_size"], 4):
                pontos += 1 if ini <= palavra(base + off) & ~1 < fim else -1
    return pontos


def apontado(o, nome, end, conhecidos):
    """Quantos dados do .o que apontam para a função `nome` aparecem no jogo apontando
    para `end`. Os destrutores do RTTI (~__class_type_info, ~__fundamental_type_info)
    têm o mesmo código e chamam a mesma função; só a vtable diz qual é qual. O ponteiro
    para `end` é procurado nos dados do jogo, e a vtable em volta dele é conferida byte a
    byte, seguindo os ponteiros (vtable -> typeinfo -> o nome "N10__cxxabiv117__class_type_infoE")."""
    pontos = 0
    for s in o.simbolos:
        sec = s["st_shndx"]
        if sec not in o.secoes or not o.secoes[sec][2] or s["st_info"]["type"] != "STT_OBJECT":
            continue
        for off, tipo, sym, add in o.rels.get(sec, []):
            if tipo != 2 or o.simbolos[sym].name != nome or not s["st_value"] <= off < s["st_value"] + s["st_size"]:
                continue
            achou = [a for a in palavras_do_jogo().get(end | (1 if end in THUMB else 0), [])
                     if bate_dados(o, s, a - (off - s["st_value"]), 3)]
            pontos += 1 if achou else 0
    return pontos


_PALAVRAS = {}
def palavras_do_jogo():
    """{palavra: [endereços]} nos dados do ARM9 (depois do código), para achar ponteiros."""
    if not _PALAVRAS:
        b = MEMORIA[0][1]
        for x in range(0x020f5260 - BASE, len(b) - 3, 4):
            _PALAVRAS.setdefault(struct.unpack_from("<I", b, x)[0], []).append(BASE + x)
    return _PALAVRAS


def bate_dados(o, s, end, prof):
    """O objeto `s` do .o está em `end` no jogo? Confere os bytes fora das relocações e,
    até `prof` níveis, os objetos do próprio .o para onde os ponteiros dele apontam."""
    sec = s["st_shndx"]
    if sec not in o.secoes or not o.secoes[sec][2]:
        return True                                 # .bss ou de fora: nada a conferir
    corpo, ini, tam = o.secoes[sec][2], s["st_value"], max(s["st_size"], 1)
    try:
        jogo = ler(end, tam)
    except ValueError:
        return False
    rels = [(off, tipo, sym, add) for off, tipo, sym, add in o.rels.get(sec, []) if ini <= off < ini + tam]
    mascara = {k for off, *_ in rels for k in range(off, off + 4)}
    if any(corpo[ini + k] != jogo[k] for k in range(tam) if ini + k not in mascara):
        return False
    for off, tipo, sym, add in rels:
        t = o.simbolos[sym]
        if tipo == 2 and prof and t["st_info"]["type"] == "STT_OBJECT" and t["st_shndx"] in o.secoes:
            if not bate_dados(o, t, palavra(end + off - ini) - add, prof - 1):
                return False
    return True


def ler(end, n):
    """n bytes do jogo a partir de `end`, no módulo onde o endereço cai."""
    for base, b in MEMORIA:
        if base <= end and end + n <= base + len(b):
            return b[end - base:end - base + n]
    raise ValueError(f"{end:#x} não está em nenhum módulo do ARM9")


def palavra(end):
    return struct.unpack("<I", ler(end, 4))[0]


def destino(tipo, end):
    """Para onde aponta a relocação no endereço `end` do jogo (bl Thumb, bl ARM, ponteiro)."""
    if tipo == 10:                                  # R_ARM_THM_CALL
        alto, baixo = struct.unpack("<HH", ler(end, 4))
        desl = ((alto & 0x7ff) << 12) | ((baixo & 0x7ff) << 1)
        desl -= 0x800000 if desl & 0x400000 else 0
        alvo = end + 4 + desl
        return alvo & ~3 if baixo >> 11 == 0x1d else alvo
    if tipo in (28, 29):                            # R_ARM_CALL / R_ARM_JUMP24
        w = palavra(end)
        desl = (w & 0xffffff) << 2
        desl -= 0x4000000 if desl & 0x2000000 else 0
        return end + 8 + desl + ((((w >> 24) & 1) << 1) if w >> 28 == 0xf else 0)
    if tipo == 2:                                   # R_ARM_ABS32
        return palavra(end)
    return None


def concorda(o, nome, end):
    """Quantas chamadas da função `nome` do .o caem, no jogo em `end`, no endereço que
    symbols.txt dá para o nome chamado (menos as que caem em outro lugar)."""
    sec, ini, tam, _ = o.onde[nome]
    pontos = 0
    for off, tipo, sym, add in o.rels.get(sec, []):
        alvo = o.simbolos[sym].name
        if not ini <= off < ini + tam or alvo not in ALVOS:
            continue
        d = destino(tipo, end + off - ini)
        if d is not None:
            pontos += 1 if (d - (add if tipo == 2 else 0)) & ~1 == ALVOS[alvo] else -1
    return pontos


def apontam_para_dentro(o, funcs, bases):
    """Ponteiros do arquivo para "símbolo + deslocamento" do próprio arquivo (o fim de
    uma pilha: OSi_IdleThreadStack + 200). O endereço final pode coincidir com o
    começo do arquivo seguinte, então a relocação tem de dizer qual é o símbolo."""
    achados = {}
    origens = [(funcs[n], o.onde[n][0], o.onde[n][1], o.onde[n][2]) for n in funcs]
    origens += [(b, sec, 0, o.secoes[sec][1]) for sec, b in bases.items()]
    for end, sec, ini, tam in origens:
        for off, tipo, sym, add in o.rels.get(sec, []):
            s = o.simbolos[sym]
            if tipo != 2 or add == 0 or not ini <= off < ini + tam:
                continue
            if s.name in funcs:
                base = funcs[s.name]
            elif s["st_shndx"] in bases:
                base = bases[s["st_shndx"]] + s["st_value"]
            else:
                continue
            achados[end + off - ini] = (base, base + add)
    return achados


def externos(o, funcs):
    """O que o arquivo usa de fora (SHN_UNDEF): {endereço no jogo: nome}, pelas instruções."""
    achados = {}
    for nome, end in funcs.items():
        sec, ini, tam, _ = o.onde[nome]
        for off, tipo, sym, add in o.rels.get(sec, []):
            s = o.simbolos[sym]
            if s["st_shndx"] != "SHN_UNDEF" or not ini <= off < ini + tam:
                continue
            d = destino(tipo, end + off - ini)
            if d is not None:
                # o addend só conta nos ponteiros; no bl Thumb ele é o -4 do PC
                achados.setdefault((d - (add if tipo == 2 else 0)) & ~1, set()).add(s.name)
    return achados


def achar_dados(o, funcs, conhecidos, multi):
    """Passo 2: {índice da seção: endereço no jogo} pelas relocações das funções.
    `multi` recebe {nome: endereço} dos nomes de fora que os dados citam e dos dados
    "multidef" que o jogo tem de outra cópia."""
    bases, problemas = {}, []
    # uma variável global do arquivo que outro arquivo usa já tem endereço conhecido
    for s in o.simbolos:
        sec = s["st_shndx"]
        if sec in o.secoes and s["st_info"]["bind"] == "STB_GLOBAL" and s.name in conhecidos:
            bases.setdefault(sec, conhecidos[s.name] - s["st_value"])
    alvos = []                                      # (endereço no jogo da palavra, símbolo, addend)
    for nome, end in funcs.items():
        sec, ini, tam, _ = o.onde[nome]
        for off, tipo, sym, add in o.rels.get(sec, []):
            if tipo == 2 and ini <= off < ini + tam:
                alvos.append((end + off - ini, sym, add))
    # O typeinfo de std::exception (_ZTISt9exception) é "multidef" (bind 13): cada .o
    # que o usa leva uma cópia, e o linker fica com uma só. Às vezes é a deste .o (o de
    # std::bad_exception, colado nos outros dados do exceptionhandler.o), às vezes a de
    # outro arquivo, longe daqui (o de std::exception, de um arquivo do jogo). Veja
    # separar_multidef(), mais abaixo.
    multidef = {sec for sec in o.secoes
                if (nomes := [x for x in o.simbolos if x["st_shndx"] == sec and x.name
                              and x["st_info"]["type"] != "STT_SECTION"])
                and all(x["st_info"]["bind"] == "STB_LOPROC" for x in nomes)}

    def seguir(alvos):
        """Acha as seções para onde os ponteiros apontam, e segue os ponteiros delas."""
        for onde, sym, add in alvos:
            s = o.simbolos[sym]
            sec = s["st_shndx"]
            if sec not in o.secoes:
                continue
            base = palavra(onde) - (s["st_value"] + add)
            if sec not in bases:
                bases[sec] = base
                # os dados também apontam para dados (tabelas de ponteiros)
                for off, tipo, sym2, add2 in o.rels.get(sec, []):
                    if tipo == 2:
                        alvos.append((base + off, sym2, add2))
            elif bases[sec] != base:
                problemas.append(f"{o.secoes[sec][0]} com dois endereços: {bases[sec]:#x} e {base:#x}")
    # e os ponteiros dos dados que já têm endereço pelo nome (a vtable de
    # __si_class_type_info, que o typeinfo de std::bad_exception usa)
    alvos += [(base + off, sym, add) for sec, base in bases.items()
              for off, tipo, sym, add in o.rels.get(sec, []) if tipo == 2]
    seguir(alvos)
    # seções que nenhuma função do arquivo usa (tabelas de ponteiros que o resto do
    # jogo lê pelo nome): procura os bytes delas, com os ponteiros preenchidos
    ambiguas = []
    usadas_por = {}                                 # seção -> funções do .o que a usam
    for fsec, rl in o.rels.items():
        for off, tipo, sym, add in rl:
            alvo = o.simbolos[sym]["st_shndx"]
            usadas_por.setdefault(alvo, set()).update(
                n for n, (sc, ini, tm, _) in o.onde.items() if sc == fsec and ini <= off < ini + tm)
    # e as seções de dados deste .o que apontam para cada seção (a tabela de RTTI que
    # aponta para os nomes "v\0", "i\0")
    dados_que_usam = {}
    for fsec, rl in o.rels.items():
        if fsec in o.secoes:
            for off, tipo, sym, add in rl:
                dados_que_usam.setdefault(o.simbolos[sym]["st_shndx"], set()).add(fsec)
    for sec, (nome, tam, corpo) in o.secoes.items():
        if sec in bases or corpo is None or sec in multidef:
            continue
        # o índice de exceções (.exceptix) de uma função: vai e vem junto com ela
        if nome == ".exceptix":
            funcao = [o.simbolos[sym].name for off, _, sym, _ in o.rels.get(sec, []) if off == 0]
            if not funcao or funcao[0] not in funcs:
                continue
        elif usadas_por.get(sec):
            continue        # só funções que o linker descartou usam: foi descartada junto
        elif dados_que_usam.get(sec) and not dados_que_usam[sec] & set(bases):
            continue        # só dados deste arquivo que não estão no jogo usam
        elif not any(x["st_shndx"] == sec and x["st_info"]["bind"] == "STB_GLOBAL" for x in o.simbolos):
            continue        # ninguém usa e ninguém de fora pode usar: descartada
        esperado, ok, coringa = bytearray(corpo), True, set()
        for off, tipo, sym, add in o.rels.get(sec, []):
            s = o.simbolos[sym]
            alvo = funcs.get(s.name, conhecidos.get(s.name)) if s.name else None
            if tipo == 2 and alvo is None and nome == ".exceptix" and s["st_shndx"] in o.secoes:
                coringa.update(range(off, off + 4))     # o ponteiro para a .exception, ainda sem lugar
                continue
            if tipo != 2 or alvo is None:
                ok = False
                break
            thumb = 1 if alvo in THUMB else 0           # ponteiro para Thumb tem o bit 0 ligado
            struct.pack_into("<I", esperado, off, alvo + add + thumb)
        if not ok:
            continue
        faixa = DADOS[nome if nome in DADOS else ".data"]
        padrao = b"".join(b"." if k in coringa else re.escape(esperado[k:k + 1]) for k in range(tam))
        achados = [m.start() + faixa[0] for m in re.finditer(padrao, ler(faixa[0], faixa[1] - faixa[0]), re.S)]
        achados = [a for a in achados if a % 4 == 0]
        if len(achados) == 1:
            bases[sec] = achados[0]
            # e o que ela aponta: a .exception, ou a .bss dos buffers de stdin/stdout
            # para onde a tabela __files aponta
            seguir([(achados[0] + off, sym, add) for off, tipo, sym, add in o.rels.get(sec, []) if tipo == 2])
        elif len(achados) > 1:
            ambiguas.append((sec, nome, tam, achados))
    # bytes que aparecem várias vezes (um ponteiro de 4 bytes): vale a cópia colada
    # nas outras seções de mesmo nome deste arquivo, que o linker põe juntas (com o
    # enchimento do alinhamento entre elas: "v\0" e "i\0" ficam a 4 bytes um do outro)
    def acima(x, al):
        return (x + al - 1) // al * al
    while ambiguas:
        resolvidas = []
        for item in ambiguas:
            sec, nome, tam, achados = item
            al = o.alinhamento[sec]
            vizinhas = [(bases[x], bases[x] + o.secoes[x][1]) for x in bases if o.secoes[x][0] == nome]
            colada = [a for a in achados if any(a == acima(fim, al) or acima(a + tam, al) == ini
                                                for ini, fim in vizinhas)]
            if len(colada) == 1:
                bases[sec] = colada[0]
                resolvidas.append(item)
        if not resolvidas:
            break
        ambiguas = [a for a in ambiguas if a not in resolvidas]
    for sec, nome, tam, achados in ambiguas:
        problemas.append(f"{nome} ({tam} bytes) aparece {len(achados)} vezes no jogo")
    separar_multidef(o, bases, multidef, multi)
    # os nomes de fora que os dados citam: o ponteiro no jogo diz onde eles estão
    for sec, base in bases.items():
        if o.secoes[sec][2] is None:
            continue
        for off, tipo, sym, add in o.rels.get(sec, []):
            x = o.simbolos[sym]
            if tipo == 2 and x["st_shndx"] == "SHN_UNDEF" and x.name:
                end = palavra(base + off) - add
                multi.setdefault(x.name, end - 1 if end & 1 and end - 1 in THUMB else end)
    # confere os bytes de .data/.rodata fora das relocações
    for sec, base in bases.items():
        nome, tam, corpo = o.secoes[sec]
        if corpo is None:
            continue
        mascara = set()
        for off, tipo, _, _ in o.rels.get(sec, []):
            mascara.update(range(off, off + 4))
        jogo = ler(base, tam)
        if any(jogo[i] != corpo[i] for i in range(tam) if i not in mascara):
            problemas.append(f"{nome} em {base:#x}: bytes diferentes")
        # e os ponteiros cujo alvo já sabemos onde está
        for off, tipo, sym, add in o.rels.get(sec, []):
            alvo_nome = o.simbolos[sym].name
            alvo = funcs.get(alvo_nome, conhecidos.get(alvo_nome))
            if tipo == 2 and alvo is not None and (palavra(base + off) - add) & ~1 != alvo:
                problemas.append(f"{nome} em {base:#x}+{off:#x}: o ponteiro para {alvo_nome} "
                                 f"vale {palavra(base + off):#x}, esperado {alvo:#x}")
    return bases, problemas


def separar_multidef(o, bases, multidef, multi):
    """Uma seção multidef só é deste arquivo se ela fica colada nos outros dados dele (com
    no máximo o enchimento do alinhamento entre eles). As outras são a cópia de outro
    arquivo: saem de `bases`, e o endereço ganha o nome em `multi`, para o assembly do
    jogo defini-lo e o linker descartar a cópia deste .o."""
    aceitas = {sec for sec in bases if sec not in multidef}
    mudou = True
    while mudou:
        mudou = False
        for sec in sorted(set(bases) & multidef - aceitas):
            nome, tam, _ = o.secoes[sec]
            if any(o.secoes[x][0] == nome and bases[sec] <= bases[x] + o.secoes[x][1] + 8
                   and bases[x] <= bases[sec] + tam + 8 for x in aceitas):
                aceitas.add(sec)
                mudou = True
    for sec in set(bases) - aceitas:
        for x in o.simbolos:
            if x["st_shndx"] == sec and x.name and x["st_info"]["type"] != "STT_SECTION":
                multi[x.name] = bases[sec] + x["st_value"]
        del bases[sec]


def entre_modulos(o):
    """Símbolos "static" que uma parte do arquivo usa de outra (OS_ResetSystem, no ARM9,
    chama OSi_DoResetSystem, no ITCM). Para o linker é o mesmo .o, mas para o dsd são
    dois arquivos (x.c e x.itcm.c), e ele não deixa um usar um símbolo local do outro:
    esses ficam globais em symbols.txt."""
    def mod(sec):
        return OUTROS_MODULOS.get(o.nomes_sec[sec], ("",))[0] if isinstance(sec, int) else None
    nomes = set()
    for sec, rl in o.rels.items():
        for _, _, sym, _ in rl:
            alvo = o.simbolos[sym]
            if mod(alvo["st_shndx"]) in (None, mod(sec)):
                continue
            if alvo["st_info"]["type"] == "STT_SECTION":
                # "a .bss + 8": vale para as variáveis daquela seção
                nomes.update(s.name for s in o.simbolos if s["st_shndx"] == alvo["st_shndx"]
                             and s.name and s["st_info"]["type"] != "STT_SECTION")
            else:
                nomes.add(alvo.name)
    return nomes


def nome_fonte(fonte_dir, nome_lib, obj_dir):
    """De 'libraries_fnd_src_list.o' para 'NitroSystem/libraries/fnd/src/list.c'. Sem
    fonte (FONTE = "-", o MSL), o nome vem do .o: 'C_alloc.o' -> 'MSL/C_alloc.c'. (O
    prefixo fica no nome: o .lcf chama cada .o só pelo nome do arquivo, e o MSL também
    tem um mem.c e um math.c, como a NitroSystem e o SDK.)"""
    mapa = {}
    if fonte_dir == "-":
        for f in glob.glob(f"{obj_dir}/*.o"):
            mapa[os.path.basename(f)] = f"{nome_lib}/{os.path.basename(f)[:-2]}.c"
        return mapa
    for f in glob.glob(f"{fonte_dir}/libraries/**/*.c", recursive=True):
        rel = os.path.relpath(f, fonte_dir)
        mapa[rel.replace("/", "_")[:-2] + ".o"] = f"{nome_lib}/{rel}"
    return mapa


def segmentos(seqs, fontes, quebrados):
    """As faixas de cada arquivo e o que eles usam de fora (MSL, SDK, dados globais de
    outros arquivos), com o endereço tirado da própria instrução do jogo. Os arquivos
    que não podem ser ligados ficam de fora: continuam vindo do assembly.
    `seqs`: [(seção, divisão)], a do ARM9 (.text) e a do ITCM (.itcm)."""
    por_obj = {}                                    # id -> [fonte, objeto, {nome: end}, {seção: faixa}]
    for secao, seq in seqs:
        for end, tam, o, n in seq:
            if o is None or id(o) in quebrados:
                continue
            a = por_obj.setdefault(id(o), [fontes[os.path.basename(o.caminho)], o, {}, {}])
            a[2][n] = end
            faixa = a[3].setdefault(secao, [end, end])
            faixa[1] = (end + tam + 3) & ~3
    arquivos = list(por_obj.values())
    fora = {}
    for fonte, o, funcs, _ in arquivos:
        for end, nomes in externos(o, funcs).items():
            fora.setdefault(end, set()).update(nomes)
    return arquivos, fora


def main():
    args = sys.argv[1:]
    aplicar = "--aplicar" in args
    args = [a for a in args if a != "--aplicar"]
    nome_lib, fonte_dir, obj_dir, de, ate = args[0], args[1], args[2], int(args[3], 16), int(args[4], 16)
    objs = [Objeto(c) for c in sorted(glob.glob(f"{obj_dir}/*.o"))]
    fontes = nome_fonte(fonte_dir, nome_lib, obj_dir)
    # duas voltas: a primeira descobre os endereços das variáveis globais usadas de
    # fora; a segunda os usa para desempatar arquivos de código igual
    conhecidos = dict(ENDERECOS)
    ALVOS.update(ENDERECOS)
    blocos = colocar_blocos(objs, de, ate)
    for volta in (1, 2):
        seq, problemas, quebrados = dividir(objs, de, ate, conhecidos, ".text", blocos)
        # as funções que o SDK põe no ITCM (OS_IrqHandler): o mesmo, na região do ITCM
        seq_itcm, _, q = dividir(objs, *ITCM, conhecidos, ".itcm")
        for k, v in q.items():
            quebrados.setdefault(k, v)
        seqs = [(".text", seq), (".itcm", seq_itcm)]
        arquivos, fora = segmentos(seqs, fontes, quebrados)
        for end, nomes in fora.items():
            for n in nomes:
                conhecidos.setdefault(n, end)
        ALVOS.update({n: e for e, _, o, n in seq + seq_itcm
                      if o and n not in ENDERECOS and o.onde[n][3] != "local"})
    # um arquivo que define uma função global que o jogo tem em outro lugar (os modelos
    # do C++, shared_ptr<char>, que o msl_thread.o e o código do jogo têm cada um a sua
    # cópia; o linker ficou com uma só) daria "definida duas vezes": fica de fora
    for fonte, o, funcs, codigo in arquivos:
        for n, (sec, ini, tam, esc) in o.onde.items():
            if (esc == "" and tam and n in ENDERECOS and n not in funcs
                    and not any(a <= ENDERECOS[n] < b for a, b in codigo.values())):
                quebrados.setdefault(id(o), f"define {n}, que o jogo tem em {ENDERECOS[n]:#x}")
    # símbolos que o linker da Nintendo calculava (SDK_SYS_STACKSIZE, o fim da arena
    # do ITCM...) não existem no nosso arquivo de link: quem usa ainda não liga
    for fonte, o, funcs, _ in arquivos:
        for end, nomes in externos(o, funcs).items():
            if nomes <= LINKER:
                continue                            # definidos em simbolos_linker.lcf
            # fora do ARM9 principal (ITCM, DTCM) só vale um endereço que já tem símbolo
            fora_do_arm9 = not BASE <= end < 0x027e0000 and end not in TODOS
            if fora_do_arm9 or end not in TODOS and not no_meio_de_funcao(end) and end < 0x020f5260:
                quebrados.setdefault(id(o), f"usa algo sem símbolo no jogo ({', '.join(sorted(nomes))})")
    arquivos, fora = segmentos(seqs, fontes, quebrados)

    por_nome = {}
    for end, nomes in fora.items():
        for n in nomes:
            por_nome.setdefault(n, set()).add(end)
    renomear, apelidos = {}, []                     # renomear: endereço -> (nome, escopo, seção)
    # os outros nomes de um mesmo ponto de um bloco em assembly (_dadd = _d_add)
    for a, o, (sec, corpo, mascara, nomes) in blocos:
        if id(o) not in quebrados:
            apelidos += [(a + off, x) for off, _, outros in nomes for x in outros if x not in ENDERECOS]
    for end, nomes in sorted(fora.items()):
        nomes = nomes - LINKER                      # esses o .lcf define
        if not nomes:
            continue
        # dois nomes para a mesma função (_ll_mul e _ull_mul): o segundo vira um rótulo
        n, *outros = sorted(nomes, key=lambda x: (x not in ENDERECOS, x))
        apelidos += [(end, a) for a in outros if a not in ENDERECOS]
        if len(por_nome[n]) > 1:
            problemas.append(f"{n} aponta para {len(por_nome[n])} endereços")
        elif ENDERECOS.get(n, end) != end:
            problemas.append(f"{n}: o jogo chama {end:#x}, mas symbols.txt diz {ENDERECOS[n]:#x}")
        else:
            renomear[end] = (n, "", "fora")
    conhecidos = dict(ENDERECOS)
    conhecidos.update({n: end for end, (n, _, _) in renomear.items()})

    saida, tamanhos = [], {}                        # tamanhos: o do .o, para o dsd não esticar
    internos = {}                                   # de -> (símbolo, alvo): ponteiros com deslocamento
    # uma volta antes, só para saber onde ficam os nomes que os dados citam: o typeinfo
    # do exceptionhandler.o diz onde está a vtable que o cxxabi_rtti.o define
    for fonte, o, funcs, codigo in arquivos:
        multi = {}
        achar_dados(o, funcs, conhecidos, multi)
        for nome, end in multi.items():
            conhecidos.setdefault(nome, end)
    for fonte, o, funcs, codigo in arquivos:
        multi = {}
        bases, probs = achar_dados(o, funcs, conhecidos, multi)
        for nome, end in multi.items():
            if end not in renomear and ENDERECOS.get(nome, end) == end:
                renomear[end] = (nome, "", "fora")
        problemas += [f"{fonte}: {p}" for p in probs]
        faixas = {sec: tuple(f) for sec, f in codigo.items()}
        for sec, base in bases.items():
            nome, tam, _ = o.secoes[sec]
            a, b = faixas.get(nome, (base, base + tam))
            # o enchimento até o próximo múltiplo de 4 é do arquivo: o linker o põe depois dele
            # (vale também para a .exception: no .o ela diz alinhamento 1, mas o mwldarm
            # começa cada uma num múltiplo de 4; o @ET@ de 5 bytes ocupa 8)
            faixas[nome] = (min(a, base), (max(b, base + tam) + 3) // 4 * 4)
        semdados = [o.secoes[s][0] for s in o.secoes if s not in bases]
        ini, fim = faixas.get(".text", (0, 0))
        print(f"{ini:#010x}-{fim:#010x} {len(funcs):3d} funções  {fonte}"
              + "".join(f"  {n} {a:#x}-{b:#x}" for n, (a, b) in faixas.items() if n != ".text")
              + (f"  (descartadas pelo linker: {', '.join(semdados)})" if semdados else ""))
        saida.append((fonte, faixas))
        cruzados = entre_modulos(o)
        for nome, end in funcs.items():
            renomear[end] = (nome, "" if nome in cruzados else o.onde[nome][3], ".text")
            tamanhos.setdefault(end, o.onde[nome][2])
        for sec, base in bases.items():
            nome_sec, tam_sec, _ = o.secoes[sec]
            objetos = sorted((s["st_value"], s) for s in o.simbolos if s["st_shndx"] == sec
                             and s.name and s["st_info"]["type"] == "STT_OBJECT")
            for off, s in objetos:
                renomear[base + off] = (s.name, "" if s.name in cruzados else escopo(s), nome_sec)
                tamanhos[base + off] = s["st_size"]
            # o dsd corta os dados nos símbolos: o começo de cada seção precisa de um
            if base not in renomear:
                renomear[base] = (f"{nome_sec[1:].replace('.', '_')}_{base:08x}", "local", nome_sec)
                tamanhos[base] = objetos[0][0] if objetos else tam_sec
        internos.update(apontam_para_dentro(o, funcs, bases))
    sem_par = [f"{e:#x} {n}" for e, _, o, n in seq if o is None]
    if sem_par:
        print(f"funções sem par no fonte ({len(sem_par)}): {', '.join(sem_par)}")
    no_jogo = {id(o) for _, s in seqs for _, _, o, _ in s if o is not None}
    for o in objs:
        if id(o) in quebrados and id(o) in no_jogo:
            print(f"não liga: {fontes[os.path.basename(o.caminho)]}: {quebrados[id(o)]}")
    print(f"# {len(no_jogo)} arquivos da biblioteca estão no jogo")
    for p in problemas:
        print("PROBLEMA:", p)
    print(f"# {len(saida)} arquivos, {sum(len(a[2]) for a in arquivos)} funções, {len(problemas)} problemas")
    if aplicar and not problemas:
        gravar(saida, renomear, apelidos, tamanhos, internos,
               {s.name for o in objs for s in o.simbolos if s.name})


def modulo(caminho, mod):
    """O arquivo de config do módulo: arm9/x.txt, arm9/itcm/x.txt, arm9/dtcm/x.txt."""
    return caminho if mod == "main" else os.path.join(os.path.dirname(caminho), mod, os.path.basename(caminho))


def gravar(saida, renomear, apelidos, tamanhos, internos, nomes_lib):
    # delinks.txt de cada módulo: tira entradas antigas destes arquivos e acrescenta as
    # novas. A parte no ITCM/DTCM leva outro nome ("x.itcm.c"), porque o dsd não aceita
    # o mesmo arquivo em dois módulos; montar_rom.sh a liga com o mesmo x.o
    ordem = [".text", ".exception", ".exceptix", ".rodata", ".data", ".bss"]
    entradas = {}                                   # (apelido, módulo) -> [(nome, {seção: faixa})]
    partes = [("", "main")] + sorted({v[:2] for v in OUTROS_MODULOS.values()})
    for fonte, faixas in saida:
        for apelido, mod in partes:
            nome = f"{fonte[:-2]}.{apelido}.c" if apelido else fonte
            secs = {}
            for sec, faixa in faixas.items():
                a, _, destino_sec = OUTROS_MODULOS.get(sec, ("", "main", sec))
                if a == apelido:
                    secs[destino_sec] = faixa
            entradas.setdefault((apelido, mod), []).append((nome, secs))
    por_modulo = {}
    for (apelido, mod), lista in entradas.items():
        por_modulo.setdefault(mod, []).extend(lista)
    for mod, lista in por_modulo.items():
        caminho = modulo(DELINKS, mod)
        texto = open(caminho).read().rstrip("\n")
        for nome, secs in lista:
            texto = re.sub(rf"\n\n{re.escape(nome)}:\n(    .*\n?)*", "\n", texto)
        for nome, secs in lista:
            if secs:
                texto += f"\n\n{nome}:\n    complete\n"
                texto += "\n".join(f"    {n:<11} start:{a:#010x} end:{b:#010x}"
                                   for n, (a, b) in sorted(secs.items(), key=lambda x: ordem.index(x[0])))
        open(caminho, "w").write(re.sub(r"\n{3,}", "\n\n", texto).rstrip("\n") + "\n")
    # symbols.txt: o nome do .o em cada endereço; os static ficam "local"
    automatico = re.compile(r"(func|data)_[0-9a-f]{8}(_unk)?$|@E[TX]@[0-9a-f]{8}$|.*__vfunc\d+_[0-9a-f]{8}$")
    vistos, trocados = set(), 0

    def tipo(end, sec, atual):
        """O "kind" do símbolo. Os dados de um arquivo ligado levam o tamanho do .o:
        sem ele, o dsd estica o último até o próximo símbolo, dentro do vizinho."""
        if atual and "size=0x0,unknown" in atual and tamanhos.get(end):
            return atual.replace("size=0x0,", f"size={tamanhos[end]:#x},")   # __throw
        if sec in (".text", "fora") and atual or (atual and atual.startswith(("kind:function", "kind:label"))):
            return atual
        t = tamanhos.get(end)
        if sec in (".bss", ".dtcm.bss") or 0x021090e0 <= end < DTCM:
            return f"kind:bss(size={t:#x})" if t else "kind:bss"
        return f"kind:data(byte[{t:#x}])" if t else (atual or "kind:data(any)")
    # os símbolos que caem DENTRO de um arquivo ligado e que o .o não tem (data_021ade58,
    # um campo no meio de NNS_G3dGlb) saem: o dsd passa a apontar para o símbolo que
    # contém o endereço, mais o deslocamento, e o linker acha esse no .o
    faixas = [(a, b) for _, f in saida for (a, b) in f.values()]
    codigo = [f[s] for _, f in saida for s in (".text", ".itcm") if s in f]
    def dentro(end):
        if any(a < end < b for a, b in codigo):
            # um ponteiro para função Thumb tem o bit 0 ligado: conta como a função
            return end & ~1 not in renomear
        return any(a < end < b for a, b in faixas) and end not in renomear
    removidos, arquivos, primaria = 0, {}, {}
    for caminho in (SIMBOLOS_ITCM, SIMBOLOS_DTCM, SIMBOLOS):
        linhas = open(caminho).read().rstrip("\n").split("\n")
        antes = len(linhas)
        linhas = [l for l in linhas if not (re.search(r"addr:(0x[0-9a-f]+)", l)
                                           and dentro(int(re.search(r"addr:(0x[0-9a-f]+)", l).group(1), 16)))]
        removidos += antes - len(linhas)
        arquivos[caminho] = linhas
        for i, linha in enumerate(linhas):
            m = re.match(r"(\S+) (kind:\S+(?: \S+)*?) addr:(0x[0-9a-f]+)( local| weak)?$", linha)
            if not m:
                continue
            end = int(m.group(3), 16)
            if end in renomear and not m.group(1).startswith(".L") and end not in vistos:
                nome, local, sec = renomear[end]
                vistos.add(end)
                primaria[end] = i
                if sec == "fora" and not automatico.match(m.group(1)) and m.group(1) != nome:
                    # já tem um nome dado à mão (IntDivMod): o do fonte entra como rótulo
                    apelidos.append((end, nome))
                    continue
                if (not automatico.match(m.group(1)) and m.group(1) != nome
                        and m.group(1) not in nomes_lib):
                    # o nome dado à mão (Float_Add) fica como rótulo do verdadeiro
                    apelidos.append((end, m.group(1)))
                novo = f"{nome} {tipo(end, sec, m.group(2))} addr:{m.group(3)}" + (f" {local}" if local else "")
                if novo != linha:
                    linhas[i] = novo
                    trocados += 1

        # um rótulo antigo com o nome que a função do lado ganhou (__throw) ficaria repetido
        def repetido(j, linha):
            m = re.match(r"(\S+) kind:label\S* addr:(0x[0-9a-f]+)", linha)
            end = int(m.group(2), 16) if m else None
            return m and end in primaria and primaria[end] != j and renomear[end][0] == m.group(1)
        arquivos[caminho] = linhas = [l for j, l in enumerate(linhas) if not repetido(j, l)]
    for end, a in apelidos:
        print(f"   apelido: {a} em {end:#x}")
    # os símbolos de dados que o jogo não tinha: entram na ordem dos endereços
    novos = []
    for end, (nome, local, sec) in renomear.items():
        if end not in vistos and sec == "fora" and no_meio_de_funcao(end):
            # uma entrada no meio de outra função (_ll_sdiv cai dentro do _ll_div)
            novos.append((end, f"{nome} kind:label({'thumb' if end in THUMB else 'arm'}) addr:{end:#010x}"))
        elif end not in vistos and (end < 0x020f5260 and sec == "fora" or end < BASE):
            print(f"   AVISO: {nome} em {end:#x} não tem símbolo no jogo; não foi criado")
        elif end not in vistos:
            novos.append((end, f"{nome} {tipo(end, sec, None)} addr:{end:#010x}" + (f" {local}" if local else "")))
    existentes = {l for ls in arquivos.values() for l in ls}
    for end, a in apelidos:
        if a in LINKER:
            continue
        # um rótulo fora do código (__sinit__, o começo da tabela .ctor) é dado: como
        # "label(arm)" ele punha um $a na .ctor, e o linker achava que os ponteiros dela
        # eram código ARM chamando Thumb e criava um "veneer" para cada um
        if any(a_ <= end < b_ for a_, b_ in CODIGO + [ITCM]):
            linha = f"{a} kind:label({'thumb' if end in THUMB else 'arm'}) addr:{end:#010x}"
        else:
            linha = f"{a} kind:data(any) addr:{end:#010x}"
        if linha not in existentes:
            novos.append((end, linha))
    def endereco(l):
        m = re.search(r"addr:(0x[0-9a-f]+)", l)
        return int(m.group(1), 16) if m else 0
    # um rótulo automático (.L_020ead44) no endereço que ganhou nome sai: o dsd usa o
    # primeiro símbolo do endereço, e o .o da biblioteca não define o .L_ (o mwldarm
    # resolvia o nome que falta como 0 e punha um "veneer" de 8 bytes no meio do código)
    com_nome = set(renomear) | {end for end, _ in apelidos}
    for caminho in arquivos:
        arquivos[caminho] = [l for l in arquivos[caminho]
                             if not (re.match(r"\.L_[0-9a-f]{8} kind:label", l) and endereco(l) in com_nome)]
    for caminho, linhas in arquivos.items():
        # cada símbolo novo vai para o arquivo do módulo onde o endereço cai
        de, ate = {SIMBOLOS_ITCM: (0, BASE), SIMBOLOS_DTCM: (DTCM, 1 << 32), SIMBOLOS: (BASE, DTCM)}[caminho]
        chaves = [endereco(l) for l in linhas]
        for end, linha in sorted(novos, reverse=True):
            if de <= end < ate:
                linhas.insert(bisect.bisect_right(chaves, end), linha)
        open(caminho, "w").write("\n".join(linhas) + "\n")
    # relocs.txt: quem aponta para o meio de um arquivo ligado passa a apontar para o
    # símbolo do .o que contém o endereço, com o deslocamento ("add")
    simbolos_ok = sorted(e for e in renomear if any(a <= e < b for a, b in faixas))
    ajustadas, falsas = 0, []
    for caminho in (RELOCS, modulo(RELOCS, "itcm"), modulo(RELOCS, "dtcm")):
        ajustadas += ajustar_relocs(caminho, renomear, internos, simbolos_ok, faixas, dentro, falsas)
    print(f"# {ajustadas} relocações apontam agora para símbolo + deslocamento")
    for f in falsas:
        print(f"   relocação falsa removida: {f}")
    print(f"# delinks.txt atualizado; {trocados} símbolos renomeados, {len(novos)} novos, {removidos} removidos")


def ajustar_relocs(caminho, renomear, internos, simbolos_ok, faixas, dentro, falsas):
    texto, ajustadas = [], 0
    for linha in open(caminho).read().rstrip("\n").split("\n"):
        m = re.match(r"from:(0x[0-9a-f]+) kind:\S+ to:(0x[0-9a-f]+)( module:.*)$", linha)
        de = int(m.group(1), 16) if m else None
        if m and de in internos and internos[de][1] == int(m.group(2), 16) and internos[de][0] not in (internos[de][1],):
            base, alvo = internos[de]
            if alvo not in renomear:
                pass                                # o caso geral abaixo resolve
            else:
                linha = linha.replace(f"to:{m.group(2)}", f"to:{base:#010x} add:{alvo - base:#x}")
                ajustadas += 1
                texto.append(linha)
                continue
        if m and dentro(int(m.group(2), 16)):
            de, alvo = int(m.group(1), 16), int(m.group(2), 16)
            base = simbolos_ok[bisect.bisect_right(simbolos_ok, alvo) - 1]
            nome, local, _ = renomear[base]
            if local == "local" and not any(a <= de < b for a, b in faixas):
                # uma variável "static" só pode ser usada dentro do próprio arquivo: de
                # fora, a "relocação" era um número que parecia endereço (o dsd init
                # chuta). Sai da lista, e os bytes ficam como estão
                falsas.append(f"{de:#x} -> {alvo:#x} ({nome}+{alvo - base:#x})")
                continue
            linha = linha.replace(f"to:{m.group(2)}", f"to:{base:#010x} add:{alvo - base:#x}")
            ajustadas += 1
        texto.append(linha)
    open(caminho, "w").write("\n".join(texto) + "\n")
    return ajustadas


if __name__ == "__main__":
    main()
