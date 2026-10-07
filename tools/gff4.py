"""Leitor de GFF V4.0 (formato da BioWare usado no Sonic Chronicles e no Dragon Age).

Estrutura do arquivo:
  cabeçalho  "GFF " "V4.0" plataforma(4) tipo(4) versao_tipo(4)
             u32 struct_count, u32 data_offset
  templates  struct_count x { label(4), field_count, field_offset, struct_size }
  campos     por template: field_count x { u32 label, u32 tipo|flags<<16, u32 offset }
  dados      a partir de data_offset; struct raiz = template 0, em data_offset

Os campos são identificados por NÚMEROS (labels), não nomes. Ex.: no TLK,
19002 = ID da string e 19003 = texto.

Tipo do campo = 16 bits baixos; flags = 16 bits altos:
  0x8000 LISTA     0x4000 STRUCT (tipo = índice do template)     0x2000 REFERÊNCIA
Uso: python3 gff4.py arquivo [saida.json]
"""
import json, struct, sys

LIST, STRUCT, REF = 0x8000, 0x4000, 0x2000
NULL = 0xFFFFFFFF
SIMPLE = {0: ('<B', 1), 1: ('<b', 1), 2: ('<H', 2), 3: ('<h', 2), 4: ('<I', 4), 5: ('<i', 4),
          6: ('<Q', 8), 7: ('<q', 8), 8: ('<f', 4), 9: ('<d', 8),
          10: ('<3f', 12), 12: ('<4f', 16), 13: ('<4f', 16), 15: ('<4f', 16), 16: ('<16f', 64)}
TYPE_SIZE = {**{k: v[1] for k, v in SIMPLE.items()}, 14: 4, 17: 8, 0xFFFF: 8}


class GFF4:
    def __init__(self, data):
        self.d = data
        magic, ver, plat, ftype, fver = struct.unpack_from('<4s4s4s4s4s', data, 0)
        if magic != b'GFF ' or ver != b'V4.0':
            raise ValueError(f'nao suportado: {magic} {ver}')
        self.platform, self.type, self.type_version = plat.decode(), ftype.decode().strip(), fver.decode()
        count, self.data_off = struct.unpack_from('<II', data, 0x14)
        self.templates = []
        for i in range(count):
            label, nf, foff, size = struct.unpack_from('<4sIII', data, 0x1C + 16 * i)
            fields = [struct.unpack_from('<III', data, foff + 12 * k) for k in range(nf)]
            self.templates.append({'label': label.decode('latin-1'), 'size': size, 'fields': fields})

    def u32(self, o):
        return struct.unpack_from('<I', self.d, o)[0]

    def string(self, rel):
        """ECString: u32 tamanho + texto.
        No Dragon Age (PC) o texto é UTF-16; no Sonic Chronicles (DS) a BioWare
        usou 1 byte por caractere (cp1252) para economizar memória."""
        if rel == NULL or self.data_off + rel + 4 > len(self.d):
            return None
        o = self.data_off + rel
        n = self.u32(o)
        raw = self.d[o + 4:o + 4 + 2 * n]
        # Os dois existem no jogo: TLK usa 8 bits, DLG/ARE usam UTF-16.
        # Heurística: em UTF-16 de texto latino todo byte ímpar é zero.
        if n and len(raw) == 2 * n and raw[1::2].count(0) >= 0.9 * n:
            return raw.decode('utf-16-le', errors='replace').rstrip('\0')
        return self.d[o + 4:o + 4 + n].decode('cp1252', errors='replace').rstrip('\0')

    def value(self, typ, o):
        if typ in SIMPLE:
            fmt, _ = SIMPLE[typ]
            v = struct.unpack_from(fmt, self.d, o)
            return list(v) if len(v) > 1 else v[0]
        if typ == 14:
            return self.string(self.u32(o))
        if typ == 17:   # TlkString: id no TLK + string local opcional
            rel = self.u32(o + 4)       # 0 ou 0xFFFFFFFF = sem texto local
            return {'tlk_id': self.u32(o), 'text': self.string(rel) if rel not in (0, NULL) else None}
        if typ == 18:   # ponto fixo do DS: inteiro de 32 bits com 12 bits de fração
            return struct.unpack_from('<i', self.d, o)[0] / 4096.0
        if typ == 20:   # string ASCII inline (só existe no Sonic): u32 tamanho + bytes
            n = self.u32(o)
            return self.d[o + 4:o + 4 + n].decode('cp1252', errors='replace').rstrip('\0')
        if typ == 0xFFFF:   # "generic": {u32 tipo|flags, u32 offset} -> valor de tipo variável
            tf, rel = struct.unpack_from('<II', self.d, o)
            if rel == NULL:
                return None
            try:
                return self.read_field(tf & 0xFFFF, tf >> 16, self.data_off + rel, 1)
            except (struct.error, IndexError):
                return {'generic_raw': [tf, rel]}
        return {'unknown_type': typ}

    def read_struct(self, tidx, o, depth=0):
        t = self.templates[tidx]
        out = {'_type': t['label']}
        for label, tf, foff in t['fields']:
            try:
                out[str(label)] = self.read_field(tf & 0xFFFF, tf >> 16, o + foff, depth)
            except (struct.error, IndexError, UnicodeError) as e:
                out[str(label)] = {'erro': f'tipo {tf:#x}: {e.__class__.__name__}'}
        return out

    def read_field(self, typ, flags, o, depth):
        if depth > 32:
            return '<profundidade>'
        is_list, is_struct, is_ref = flags & LIST, flags & STRUCT, flags & REF
        if is_list:
            rel = self.u32(o)
            if rel == NULL:
                return []
            lo = self.data_off + rel
            n = self.u32(lo)
            items, p = [], lo + 4
            for _ in range(n):
                if typ == 0xFFFF and not is_struct:   # lista de genéricos: {tipo, offset} inline
                    items.append(self.value(typ, p))
                    p += 8
                elif is_struct and not is_ref:
                    items.append(self.read_struct(typ, p, depth + 1))
                    p += self.templates[typ]['size']
                elif is_struct or is_ref:
                    r = self.u32(p)
                    items.append(None if r == NULL else
                                 (self.read_struct(typ, self.data_off + r, depth + 1) if is_struct
                                  else self.value(typ, self.data_off + r)))
                    p += 4
                else:
                    items.append(self.value(typ, p))
                    p += TYPE_SIZE.get(typ, 4)
            return items
        if is_struct:
            if is_ref:
                r = self.u32(o)
                return None if r == NULL else self.read_struct(typ, self.data_off + r, depth + 1)
            return self.read_struct(typ, o, depth + 1)
        if is_ref:
            r = self.u32(o)
            return None if r == NULL else self.value(typ, self.data_off + r)
        return self.value(typ, o)

    def root(self):
        return self.read_struct(0, self.data_off)


def tlk_strings(path):
    """TLK: raiz 'TLK ' -> lista 19001 de structs 'STRN' {19002: id, 19003: texto}."""
    g = GFF4(open(path, 'rb').read())
    r = g.root()
    return {e['19002']: e['19003'] for e in r['19001']}


if __name__ == '__main__':
    g = GFF4(open(sys.argv[1], 'rb').read())
    j = {'type': g.type, 'version': g.type_version, 'root': g.root()}
    s = json.dumps(j, indent=1, ensure_ascii=False)
    if len(sys.argv) > 2:
        open(sys.argv[2], 'w').write(s)
    else:
        print(s[:3000])
