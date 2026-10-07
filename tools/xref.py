"""Cruza strings do ARM9 com as funções que as referenciam.

Como funciona:
  - symbols.txt (gerado pelo dsd) diz onde começa e quanto mede cada função.
  - relocs.txt lista cada "load" de um endereço absoluto. No ARM, constantes de
    32 bits ficam num "literal pool" logo após a função; o reloc aponta do pool
    para o alvo. Se o alvo for uma string, sabemos que a função usa aquela string.
Saída: JSON {endereco_funcao: {"name":..., "strings":[...]}}
"""
import bisect, json, re, sys

BASE = 0x02000000

def load_symbols(path):
    funcs = []
    for line in open(path):
        m = re.match(r'(\S+) kind:function\((\w+),size=(0x[0-9a-f]+)\S*\) addr:(0x[0-9a-f]+)', line)
        if m:
            name, mode, size, addr = m.groups()
            funcs.append((int(addr, 16), int(size, 16), name, mode))
    funcs.sort()
    return funcs

def read_cstring(data, addr):
    off = addr - BASE
    if not (0 <= off < len(data)):
        return None
    end = data.find(b'\0', off, off + 256)
    if end <= off:
        return None
    raw = data[off:end]
    # só aceita texto ASCII imprimível (evita confundir dados com strings)
    if len(raw) < 4 or any(b < 0x20 or b > 0x7e for b in raw):
        return None
    return raw.decode('ascii')

def main(arm9, symbols, relocs, out):
    data = open(arm9, 'rb').read()
    funcs = load_symbols(symbols)
    starts = [f[0] for f in funcs]
    result = {}
    for line in open(relocs):
        m = re.match(r'from:(0x[0-9a-f]+) kind:load to:(0x[0-9a-f]+)', line)
        if not m:
            continue
        frm, to = int(m.group(1), 16), int(m.group(2), 16)
        s = read_cstring(data, to)
        if s is None:
            continue
        i = bisect.bisect_right(starts, frm) - 1
        if i < 0:
            continue
        addr, size, name, mode = funcs[i]
        # o literal pool fica logo depois do código; tolera uma folga
        if frm >= addr + size + 0x400:
            continue
        e = result.setdefault(f'{addr:#010x}', {'name': name, 'mode': mode, 'size': size, 'strings': []})
        if s not in e['strings']:
            e['strings'].append(s)
    json.dump(result, open(out, 'w'), indent=1, ensure_ascii=False)
    print(f'{len(funcs)} funcoes, {len(result)} referenciam strings')

if __name__ == '__main__':
    main(*sys.argv[1:5])
