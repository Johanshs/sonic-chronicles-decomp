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
  FONTE  a pasta do fonte (work/NitroSystem)
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
         ".dtcm": (DTCM, 0x027e1040), ".version": (BASE, BASE + 0x1000)}
# as partes de um arquivo que ficam longe do resto e entram em delinks.txt com outro
# nome ("x.itcm.c"): seção do .o -> (apelido, módulo, seção do módulo). O ITCM e o DTCM
# são outros módulos; a .version ("[SDK+NINTENDO:BACKUP]") o .lcf da Nintendo punha no
# começo do ARM9, logo depois do crt0
OUTROS_MODULOS = {".itcm": ("itcm", "itcm", ".text"), ".dtcm": ("dtcm", "dtcm", ".data"),
                  ".dtcm.bss": ("dtcm", "dtcm", ".bss"), ".version": ("version", "main", ".text")}
ENDERECOS, THUMB, TODOS, FUNCOES = {}, set(), set(), []   # nome -> endereço; Thumb; com símbolo
NOMES_TODOS = set()
# os símbolos que montar_rom.sh define no .lcf (SDK_SYS_STACKSIZE...)
LINKER = set(re.findall(r"^\s*(\w+)\s*=", open(os.path.join(REPO, "config/YWSE/arm9/simbolos_linker.lcf")).read(), re.M))
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
        for i, s in enumerate(elf.iter_sections()):
            if s.name in (".data", ".rodata", ".bss", ".sdata", ".sbss", ".dtcm", ".dtcm.bss", ".version") and s.data_size:
                corpo = None if s.header.sh_type == "SHT_NOBITS" else s.data()
                self.secoes[i] = (s.name, s.data_size, corpo)
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


def dividir(objs, de, ate, conhecidos, secao=".text"):
    """Passo 1: [(endereço, objeto, nome da função no .o)] para cada função da região.
    Só valem as funções do .o que estão na `secao` (.text no ARM9, .itcm no ITCM)."""
    jogo = sorted(f for fs in af.funcoes_jogo().values() for f in fs if de <= f[0] < ate)
    por_tam = {}
    for o in objs:
        for i, (n, c, m) in enumerate(o.funcoes):
            if o.nomes_sec[o.onde[n][0]] == secao:
                por_tam.setdefault(len(c), []).append((o, i, n, c, m))
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
        def nota(o):
            n = corrida(o, k)
            return (n, apontam(o, jogo[k][0], jogo[k + n - 1][0] + len(jogo[k + n - 1][2]), conhecidos),
                    concorda(o, escolher(o, k, set(), -1)[1], jogo[k][0]))
        o = max(opcoes.values(), key=nota)
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
    return seq, problemas, quebrados


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
        if not ini <= off < ini + tam or alvo not in ENDERECOS:
            continue
        d = destino(tipo, end + off - ini)
        if d is not None:
            pontos += 1 if (d - (add if tipo == 2 else 0)) & ~1 == ENDERECOS[alvo] else -1
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


def achar_dados(o, funcs, conhecidos):
    """Passo 2: {índice da seção: endereço no jogo} pelas relocações das funções."""
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
    mudou = True
    while mudou:
        mudou = False
        for onde, sym, add in alvos:
            s = o.simbolos[sym]
            sec = s["st_shndx"]
            if sec not in o.secoes:
                continue
            base = palavra(onde) - (s["st_value"] + add)
            if sec not in bases:
                bases[sec] = base
                mudou = True
                # os dados também apontam para dados (tabelas de ponteiros)
                for off, tipo, sym2, add2 in o.rels.get(sec, []):
                    if tipo == 2:
                        alvos.append((base + off, sym2, add2))
            elif bases[sec] != base:
                problemas.append(f"{o.secoes[sec][0]} com dois endereços: {bases[sec]:#x} e {base:#x}")
    # seções que nenhuma função do arquivo usa (tabelas de ponteiros que o resto do
    # jogo lê pelo nome): procura os bytes delas, com os ponteiros preenchidos
    ambiguas = []
    usadas_por = {}                                 # seção -> funções do .o que a usam
    for fsec, rl in o.rels.items():
        for off, tipo, sym, add in rl:
            alvo = o.simbolos[sym]["st_shndx"]
            usadas_por.setdefault(alvo, set()).update(
                n for n, (sc, ini, tm, _) in o.onde.items() if sc == fsec and ini <= off < ini + tm)
    for sec, (nome, tam, corpo) in o.secoes.items():
        if sec in bases or corpo is None:
            continue
        if usadas_por.get(sec):
            continue        # só funções que o linker descartou usam: foi descartada junto
        if not any(x["st_shndx"] == sec and x["st_info"]["bind"] == "STB_GLOBAL" for x in o.simbolos):
            continue        # ninguém usa e ninguém de fora pode usar: descartada
        esperado, ok = bytearray(corpo), True
        for off, tipo, sym, add in o.rels.get(sec, []):
            s = o.simbolos[sym]
            alvo = funcs.get(s.name, conhecidos.get(s.name)) if s.name else None
            if tipo != 2 or alvo is None:
                ok = False
                break
            thumb = 1 if alvo in THUMB else 0           # ponteiro para Thumb tem o bit 0 ligado
            struct.pack_into("<I", esperado, off, alvo + add + thumb)
        if not ok:
            continue
        faixa = DADOS[nome if nome in DADOS else ".data"]
        achados = [m.start() + faixa[0] for m in re.finditer(re.escape(bytes(esperado)),
                                                            ler(faixa[0], faixa[1] - faixa[0]))]
        achados = [a for a in achados if a % 4 == 0]
        if len(achados) == 1:
            bases[sec] = achados[0]
        elif len(achados) > 1:
            ambiguas.append((sec, nome, tam, achados))
    # bytes que aparecem várias vezes (um ponteiro de 4 bytes): vale a cópia colada
    # nas outras seções de mesmo nome deste arquivo, que o linker põe juntas
    while ambiguas:
        resolvidas = []
        for item in ambiguas:
            sec, nome, tam, achados = item
            vizinhas = [(bases[x], bases[x] + o.secoes[x][1]) for x in bases if o.secoes[x][0] == nome]
            colada = [a for a in achados if any(a == fim or a + tam == ini for ini, fim in vizinhas)]
            if len(colada) == 1:
                bases[sec] = colada[0]
                resolvidas.append(item)
        if not resolvidas:
            break
        ambiguas = [a for a in ambiguas if a not in resolvidas]
    for sec, nome, tam, achados in ambiguas:
        problemas.append(f"{nome} ({tam} bytes) aparece {len(achados)} vezes no jogo")
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


def nome_fonte(fonte_dir, nome_lib):
    """De 'libraries_fnd_src_list.o' para 'NitroSystem/libraries/fnd/src/list.c'."""
    mapa = {}
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
    fontes = nome_fonte(fonte_dir, nome_lib)
    # duas voltas: a primeira descobre os endereços das variáveis globais usadas de
    # fora; a segunda os usa para desempatar arquivos de código igual
    conhecidos = dict(ENDERECOS)
    for volta in (1, 2):
        seq, problemas, quebrados = dividir(objs, de, ate, conhecidos)
        # as funções que o SDK põe no ITCM (OS_IrqHandler): o mesmo, na região do ITCM
        seq_itcm, _, q = dividir(objs, *ITCM, conhecidos, ".itcm")
        for k, v in q.items():
            quebrados.setdefault(k, v)
        seqs = [(".text", seq), (".itcm", seq_itcm)]
        arquivos, fora = segmentos(seqs, fontes, quebrados)
        for end, nomes in fora.items():
            for n in nomes:
                conhecidos.setdefault(n, end)
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
    for fonte, o, funcs, codigo in arquivos:
        bases, probs = achar_dados(o, funcs, conhecidos)
        problemas += [f"{fonte}: {p}" for p in probs]
        faixas = {sec: tuple(f) for sec, f in codigo.items()}
        for sec, base in bases.items():
            nome, tam, _ = o.secoes[sec]
            a, b = faixas.get(nome, (base, base + tam))
            # o enchimento até o próximo múltiplo de 4 é do arquivo: o linker o põe depois dele
            faixas[nome] = (min(a, base), (max(b, base + tam) + 3) & ~3)
        semdados = [o.secoes[s][0] for s in o.secoes if s not in bases]
        ini, fim = faixas.get(".text", (0, 0))
        print(f"{ini:#010x}-{fim:#010x} {len(funcs):3d} funções  {fonte}"
              + "".join(f"  {n} {a:#x}-{b:#x}" for n, (a, b) in faixas.items() if n != ".text")
              + (f"  (descartadas pelo linker: {', '.join(semdados)})" if semdados else ""))
        saida.append((fonte, faixas))
        cruzados = entre_modulos(o)
        for nome, end in funcs.items():
            renomear[end] = (nome, "" if nome in cruzados else o.onde[nome][3], ".text")
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
        gravar(saida, renomear, apelidos, tamanhos, internos)


def modulo(caminho, mod):
    """O arquivo de config do módulo: arm9/x.txt, arm9/itcm/x.txt, arm9/dtcm/x.txt."""
    return caminho if mod == "main" else os.path.join(os.path.dirname(caminho), mod, os.path.basename(caminho))


def gravar(saida, renomear, apelidos, tamanhos, internos):
    # delinks.txt de cada módulo: tira entradas antigas destes arquivos e acrescenta as
    # novas. A parte no ITCM/DTCM leva outro nome ("x.itcm.c"), porque o dsd não aceita
    # o mesmo arquivo em dois módulos; montar_rom.sh a liga com o mesmo x.o
    ordem = [".text", ".rodata", ".data", ".bss"]
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
    automatico = re.compile(r"(func|data)_[0-9a-f]{8}$|.*__vfunc\d+_[0-9a-f]{8}$")
    vistos, trocados = set(), 0

    def tipo(end, sec, atual):
        """O "kind" do símbolo. Os dados de um arquivo ligado levam o tamanho do .o:
        sem ele, o dsd estica o último até o próximo símbolo, dentro do vizinho."""
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
    removidos, arquivos = 0, {}
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
                if sec == "fora" and not automatico.match(m.group(1)) and m.group(1) != nome:
                    # já tem um nome dado à mão (IntDivMod): o do fonte entra como rótulo
                    apelidos.append((end, nome))
                    continue
                novo = f"{nome} {tipo(end, sec, m.group(2))} addr:{m.group(3)}" + (f" {local}" if local else "")
                if novo != linha:
                    linhas[i] = novo
                    trocados += 1
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
        linha = f"{a} kind:label({'thumb' if end in THUMB else 'arm'}) addr:{end:#010x}"
        if linha not in existentes:
            novos.append((end, linha))
    def endereco(l):
        m = re.search(r"addr:(0x[0-9a-f]+)", l)
        return int(m.group(1), 16) if m else 0
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
