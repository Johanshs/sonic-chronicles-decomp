"""Recupera classes C++ do ARM9 a partir do RTTI (ABI Itanium) e nomeia funções.

Layout encontrado no Sonic Chronicles (compilador Metrowerks, ABI Itanium):

  typeinfo (12+ bytes):
     +0  ponteiro p/ vtable da classe de typeinfo (__class_type_info & cia)
     +4  ponteiro p/ nome "mangled", ex.: "13CGameCreature" (13 = tamanho)
     +8  (herança simples) ponteiro p/ typeinfo da classe base

  vtable:
     -8  offset_to_top (0 na vtable primária, negativo nas secundárias)
     -4  ponteiro p/ typeinfo
      0  <- "address point": é este endereço que fica gravado no objeto
     +0  função virtual 0, +4 função virtual 1, ... (bit 0 = 1 -> Thumb)

Atenção: no CodeWarrior o destrutor virtual NÃO fica no slot 0 (como na ABI
Itanium pura); fica na ordem em que foi declarado. Por isso o destrutor é
identificado pelo comportamento: é o método virtual que grava a vtable da
própria classe em this (construtores nunca são virtuais).

Uso: python3 rtti.py arm9.bin symbols.txt relocs.txt saida_dir
Gera: classes.json, symbols_renamed.txt (para o dsd) e um relatório.
"""
import bisect, json, os, re, struct, sys

BASE = 0x02000000


def demangle_class(m):
    """'13CGameCreature' -> 'CGameCreature'; 'N5Outer5InnerE' -> 'Outer::Inner'."""
    def parse_name(s, i):
        j = i
        while j < len(s) and s[j].isdigit():
            j += 1
        if j == i:
            return None, i
        n = int(s[i:j])
        return s[j:j + n], j + n
    if m.startswith('N') and m.endswith('E'):
        parts, i = [], 1
        while i < len(m) - 1:
            p, i2 = parse_name(m, i)
            if p is None:
                return m
            parts.append(p)
            i = i2
        return '::'.join(parts)
    name, end = parse_name(m, 0)
    if name is None:
        return m
    rest = m[end:]
    return name + (f'<{rest}>' if rest else '')


def main(arm9, symbols, relocs, outdir):
    d = open(arm9, 'rb').read()
    end = BASE + len(d)
    u32 = lambda a: struct.unpack_from('<I', d, a - BASE)[0]

    def cstr(a):
        if not (BASE <= a < end):
            return None
        o = a - BASE
        e = d.find(b'\0', o, o + 128)
        r = d[o:e]
        return r.decode() if len(r) >= 2 and all(32 <= c < 127 for c in r) else None

    # --- funções conhecidas (para validar ponteiros de código)
    funcs = {}
    sym_lines = open(symbols).read().splitlines()
    for line in sym_lines:
        m = re.match(r'(\S+) kind:function\((\w+),size=(0x[0-9a-f]+)\S*\) addr:(0x[0-9a-f]+)', line)
        if m:
            funcs[int(m[4], 16)] = (m[1], m[2], int(m[3], 16))
    is_code = lambda p: (p & ~1) in funcs

    # --- 1. typeinfos: [vptr em .data][ptr p/ nome mangled]
    typeinfos = {}
    for o in range(0, len(d) - 12, 4):
        a = BASE + o
        w0, w1 = u32(a), u32(a + 4)
        if not (0x02109000 <= w0 < 0x021090e0):
            continue
        s = cstr(w1)
        if s and re.match(r'^(N?\d+[A-Za-z_]|St)', s):
            typeinfos[a] = {'mangled': s, 'name': demangle_class(s), 'kind_vptr': w0}
    # bases: herança simples (+8 aponta p/ outro typeinfo) ou múltipla (+12 = n, +16.. = bases)
    for a, t in typeinfos.items():
        b = u32(a + 8)
        if b in typeinfos:
            t['bases'] = [typeinfos[b]['name']]
        else:
            n = u32(a + 12)
            if 0 < n < 8:
                t['bases'] = [typeinfos[u32(a + 16 + 8 * k)]['name']
                              for k in range(n) if u32(a + 16 + 8 * k) in typeinfos]

    # --- 2. vtables: [offset_to_top][typeinfo][funcs...]
    vtables = []
    for o in range(4, len(d) - 8, 4):
        a = BASE + o
        ti = u32(a)
        if ti not in typeinfos:
            continue
        off = struct.unpack_from('<i', d, o - 4)[0]
        if not (-0x400 <= off <= 0):
            continue
        slots, p = [], a + 4
        while p < end:
            v = u32(p)
            if is_code(v):
                slots.append(v & ~1)
            elif v == 0 and slots is not None:     # slot puro-virtual/nulo
                slots.append(0)
            else:
                break
            p += 4
        while slots and slots[-1] == 0:
            slots.pop()
        if slots:
            vtables.append({'addr': a + 4, 'offset': off, 'class': typeinfos[ti]['name'], 'slots': slots})

    # --- 3. nomear funções virtuais: dono = classe com a MENOR vtable que contém
    #        a função naquele slot (classes base têm vtables menores)
    owner = {}
    for vt in sorted(vtables, key=lambda v: len(v['slots'])):
        if vt['offset'] != 0:
            continue
        for i, f in enumerate(vt['slots']):
            if f and f not in owner:
                owner[f] = (vt['class'], i)

    # --- 4. construtores: funções que carregam o address point de uma vtable
    #        E o gravam no offset 0 de um objeto (str rX, [rY] / [rY, #0]).
    #        Só carregar o endereço não basta: muitas funções apenas comparam
    #        ou repassam a vtable (ex.: registrar o destrutor de um singleton).
    import capstone
    md = {m: capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_THUMB if m == 'thumb' else capstone.CS_MODE_ARM)
          for m in ('thumb', 'arm')}

    def stores_vtable(func_addr, pool_addr):
        name, mode, size = funcs[func_addr]
        code = d[func_addr - BASE:func_addr - BASE + size]
        loaded = set()
        for ins in md[mode].disasm(code, func_addr):
            ops = ins.op_str
            if ins.mnemonic == 'ldr' and '[pc' in ops:
                # alvo do load relativo ao PC (Thumb alinha o PC em 4)
                m = re.search(r'#(0x[0-9a-f]+|\d+)\]', ops)
                off = int(m[1], 0) if m else 0
                pc = ((ins.address + 4) & ~3) if mode == 'thumb' else ins.address + 8
                if pc + off == pool_addr:
                    loaded.add(ops.split(',')[0])
            elif ins.mnemonic == 'str' and loaded:
                reg = ops.split(',')[0]
                if reg in loaded and re.search(r'\[\w+(, #0x0|, #0)?\]$', ops):
                    return True
        return False
    vt_by_addr = {vt['addr']: vt for vt in vtables}
    starts = sorted(funcs)
    ctor = {}
    vt_loads = []   # (função, endereço no literal pool, vtable)
    for line in open(relocs):
        m = re.match(r'from:(0x[0-9a-f]+) kind:load to:(0x[0-9a-f]+)', line)
        if not m:
            continue
        frm, to = int(m[1], 16), int(m[2], 16)
        if to in vt_by_addr and vt_by_addr[to]['offset'] == 0:
            i = bisect.bisect_right(starts, frm) - 1
            f = starts[i]
            if frm < f + funcs[f][2] + 0x400:
                vt_loads.append((f, frm, vt_by_addr[to]))
                if f not in owner and stores_vtable(f, frm):
                    ctor.setdefault(f, set()).add(vt_by_addr[to]['class'])

    def safe(n):
        return re.sub(r'[^A-Za-z0-9_]', '_', n.replace('::', '__'))

    names = {}
    for f, (cls, i) in owner.items():
        names[f] = f'{safe(cls)}__vfunc{i:02d}'
    # destrutor = método virtual que grava a vtable da PRÓPRIA classe em this
    for f, pool, vt in vt_loads:
        if f in owner and owner[f][0] == vt['class'] and stores_vtable(f, pool):
            names[f] = f'{safe(vt["class"])}__dtor'
    # Funções que chamam __register_global_object (0x020ec9d4) estão
    # inicializando um objeto 'static' (padrão singleton): o construtor foi
    # inlinado nelas, mas elas NÃO são o construtor.
    REGISTER_GLOBAL = 0x020ec9d4
    calls_register = set()
    for line in open(relocs):
        m = re.match(r'from:(0x[0-9a-f]+) kind:\w*call\w* to:(0x[0-9a-f]+)', line)
        if m and int(m[2], 16) == REGISTER_GLOBAL:
            i = bisect.bisect_right(starts, int(m[1], 16)) - 1
            calls_register.add(starts[i])
    for f, classes in ctor.items():
        if f in names:
            continue
        cls = '_'.join(sorted(safe(c) for c in classes))
        if f in calls_register or funcs[f][2] > 0x180 or len(classes) > 1:
            names[f] = f'constructs_{cls}'
        else:
            names[f] = f'{cls}__ctor'

    # --- saída
    os.makedirs(outdir, exist_ok=True)
    out_lines, renamed = [], 0
    for line in sym_lines:
        m = re.match(r'(\S+)( kind:function.* addr:(0x[0-9a-f]+).*)', line)
        if m and int(m[3], 16) in names and m[1].startswith('func_'):
            new = f'{names[int(m[3], 16)]}_{m[3][2:]}'  # sufixo com endereço evita colisão
            out_lines.append(new + m[2])
            renamed += 1
        else:
            out_lines.append(line)
    open(f'{outdir}/symbols_renamed.txt', 'w').write('\n'.join(out_lines) + '\n')

    classes = {}
    for a, t in typeinfos.items():
        classes[t['name']] = {'typeinfo': hex(a), 'bases': t.get('bases', []), 'vtables': []}
    for vt in vtables:
        classes[vt['class']]['vtables'].append(
            {'addr': hex(vt['addr']), 'offset': vt['offset'],
             'slots': [names.get(s, funcs[s][0]) if s else None for s in vt['slots']]})
    json.dump(classes, open(f'{outdir}/classes.json', 'w'), indent=1)
    print(f'typeinfos: {len(typeinfos)} | vtables: {len(vtables)} | '
          f'funcoes renomeadas: {renamed} (virtuais {len(owner)}, destrutores {sum(1 for n in names.values() if n.endswith("__dtor"))}, construtores {sum(1 for n in names.values() if n.endswith("__ctor"))}, '
          f'constroem inline {sum(1 for n in names.values() if n.startswith("constructs_"))})')


if __name__ == '__main__':
    main(*sys.argv[1:5])
