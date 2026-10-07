"""Extrator de pacotes HERF do Sonic Chronicles.

Formato (descoberto analisando test.herf):
  u32 magic = 0x00F1A5C0
  u32 count
  count x { u32 hash_do_nome, u32 tamanho, u32 offset }
  ...dados

O nome do arquivo não é guardado, só o hash DJB2 do nome em minúsculas:
    h = 5381; para cada byte c: h = h*33 + c   (mod 2^32)
Para recuperar os nomes montamos um dicionário de candidatos (strings do
código ARM9, nomes de arquivos soltos, nomes encontrados dentro dos próprios
arquivos extraídos) e testamos o hash de cada um. É um "ataque de dicionário".

Uso: python3 herf.py arquivo.herf saida_dir [arm9.bin] [dir_com_outros_arquivos]
"""
import json, os, re, struct, sys

MAGIC = 0x00F1A5C0

# extensões vistas no jogo: usadas para gerar candidatos a partir de nomes-base
EXTS = ['gda', 'gff', 'gui', 'are', 'dlg', 'ncgr', 'nclr', 'nscr', 'ncer', 'nanr',
        'nsbmd', 'nsbtx', 'nsbca', 'nsbta', 'nsbtp', 'nsbma', 'emit', 'small',
        'tlk', 'utc', 'uti', 'utp', 'ute', 'plo', 'ptm', 'cbgt', 'pal', 'cdpth', 'txt']

MAGICS = {b'GFF ': 'gff', b'RGCN': 'ncgr', b'RLCN': 'nclr', b'RCSN': 'nscr',
          b'RECN': 'ncer', b'RNAN': 'nanr', b'BMD0': 'nsbmd', b'BTX0': 'nsbtx',
          b'BCA0': 'nsbca', b'BTA0': 'nsbta', b'BTP0': 'nsbtp', b'BMA0': 'nsbma',
          b'2DA ': '2da', b'SDAT': 'sdat'}


def djb2(name):
    h = 5381
    for c in name.lower().encode('latin-1'):
        h = (h * 33 + c) & 0xffffffff
    return h


def read_index(data):
    magic, count = struct.unpack_from('<II', data, 0)
    if magic != MAGIC:
        raise ValueError(f'nao e HERF (magic {magic:#x})')
    return [struct.unpack_from('<III', data, 8 + 12 * i) for i in range(count)]


NAME_RE = re.compile(rb'[A-Za-z0-9_\-]{2,48}(?:\.[A-Za-z0-9]{2,5})?')


def maybe_decompress(blob):
    """Arquivos '.small': cabeçalho u32 = tipo (8 bits) | tamanho << 8.
      tipo 0x00 -> sem compressão (só tira o cabeçalho)
      tipo 0x10 -> LZ10 (formato da BIOS do DS)
    Devolve (dados, era_small)."""
    if len(blob) > 4 and blob[0] == 0x00:
        size = int.from_bytes(blob[1:4], 'little')
        if size == len(blob) - 4 and size > 0:
            return blob[4:], True
    if len(blob) > 4 and blob[0] == 0x10:
        size = int.from_bytes(blob[1:4], 'little')
        if 0 < size < 64 * 1024 * 1024:
            try:
                import ndspy.lz10
                out = ndspy.lz10.decompress(blob)
                if len(out) == size:
                    return out, True
            except Exception:
                pass
    return blob, False


def candidates_from_bytes(b):
    """Pega tudo que parece nome em ASCII e também em UTF-16 (GFF4 usa UTF-16)."""
    out = set(m.decode() for m in NAME_RE.findall(b))
    try:
        u = b.decode('utf-16-le', errors='ignore').encode('latin-1', errors='ignore')
        out |= set(m.decode() for m in NAME_RE.findall(u))
    except Exception:
        pass
    return out


def expand(words):
    out = set()
    for w in words:
        out.add(w)
        stem = w.rsplit('.', 1)[0] if '.' in w else w
        for e in EXTS:
            out.add(f'{stem}.{e}')
            out.add(f'{stem}.{e}.small')   # versão comprimida (LZ10)
        if not w.lower().endswith('.small'):
            out.add(w + '.small')
    return out


def parse_name_dict(blob):
    """erf.dict: o próprio jogo traz os nomes! u32 magic, u32 count,
    count x {u32 hash, char nome[128]}. Só aceita nomes cujo hash confere."""
    if len(blob) < 8:
        return None
    magic, count = struct.unpack_from('<II', blob, 0)
    if magic != MAGIC or len(blob) != 8 + 132 * count:
        return None
    out = {}
    for i in range(count):
        h = struct.unpack_from('<I', blob, 8 + 132 * i)[0]
        name = blob[12 + 132 * i:12 + 132 * i + 128].split(b'\0')[0].decode('latin-1')
        if name and djb2(name) == h:
            out[h] = name
    return out


def main(herf_path, outdir, arm9=None, loose_dir=None):
    data = open(herf_path, 'rb').read()
    index = read_index(data)
    want = {h for h, _, _ in index}
    known = {}

    def try_names(words):
        new = 0
        for w in expand(words):
            h = djb2(w)
            if h in want and h not in known:
                known[h] = w
                new += 1
        return new

    seeds = set()
    if arm9:
        seeds |= candidates_from_bytes(open(arm9, 'rb').read())
    if loose_dir:
        for f in os.listdir(loose_dir):
            seeds.add(f)
            if f.endswith(('.2da', '.gda')):
                seeds |= candidates_from_bytes(open(os.path.join(loose_dir, f), 'rb').read())
    rounds = [try_names(seeds)]
    # repete: conteúdo dos arquivos já nomeados pode citar outros arquivos
    while True:
        words = set()
        for h, size, off in index:
            words |= candidates_from_bytes(maybe_decompress(data[off:off + size])[0])
        n = try_names(words)
        rounds.append(n)
        if n == 0:
            break

    # Fonte principal: o dicionário oficial (erf.dict) dentro do próprio pacote.
    # Ele também corrige colisões que o ataque de dicionário aceitou por engano.
    official = 0
    for h, size, off in index:
        d = parse_name_dict(maybe_decompress(data[off:off + size])[0])
        if d:
            official += len(d)
            known.update({k: v for k, v in d.items() if k in want})
    if official:
        print(f'erf.dict: {official} nomes oficiais')

    os.makedirs(outdir, exist_ok=True)
    manifest = []
    for h, size, off in index:
        blob, comp = maybe_decompress(data[off:off + size])
        name = known.get(h)
        # Validação: dado comprimido (LZ10) sempre vem de um nome '.small'.
        # Se o nome achado não termina assim, foi colisão de hash -> descarta.
        if name and comp and not name.lower().endswith('.small'):
            del known[h]
            name = None
        if name is None:
            ext = MAGICS.get(blob[:4], 'bin')
            name = f'_unk_{h:08x}.{ext}'
        if comp and name.lower().endswith('.small'):
            name = name[:-6]          # grava já descomprimido, sem o sufixo
        open(os.path.join(outdir, name), 'wb').write(blob)
        manifest.append({'hash': f'{h:08x}', 'name': name, 'size': size,
                         'compressed': comp, 'named': h in known})
    json.dump(manifest, open(os.path.join(outdir, '_manifest.json'), 'w'), indent=1)
    print(f'{os.path.basename(herf_path)}: {len(index)} arquivos, {len(known)} nomes recuperados '
          f'({100 * len(known) / len(index):.1f}%), rodadas: {rounds}')


if __name__ == '__main__':
    main(*sys.argv[1:])
