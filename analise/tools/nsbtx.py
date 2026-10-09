"""Texturas e paletas dos modelos 3D (.nsbtx, formato BTX0 do NitroSystem).

Os personagens do jogo são modelos 3D: a geometria e o esqueleto ficam no `.nsbmd`
e as texturas no `.nsbtx` de mesmo nome (ex.: GenSonN_AA.nsbmd + GenSonN_AA.nsbtx).
As texturas são pequenas (64x64, 32x32) e indexadas: cada pixel é um número de cor,
e a cor de verdade vem de uma paleta à parte. Por isso **trocar só a paleta recolore
o personagem** sem mexer no desenho. Conferido no emulador: o Sonic ficou verde em
exploração com só a paleta de GenSonN_AA.nsbtx trocada (ver docs/FORMATOS.md, "Modelos 3D").

Uso:
  python3 nsbtx.py info     arquivo.nsbtx                 lista texturas e paletas
  python3 nsbtx.py png      arquivo.nsbtx pasta           cada textura vira um PNG (para ver)
  python3 nsbtx.py exportar arquivo.nsbtx paletas.csv     paletas em CSV (paleta,indice,r,g,b)
  python3 nsbtx.py importar arquivo.nsbtx paletas.csv saida.nsbtx
                                                          grava as cores do CSV num novo .nsbtx

O CSV usa cores de 0 a 255 para ficar fácil de editar, mas o DS só tem 5 bits por
canal (32 níveis): cada valor é arredondado para o múltiplo de 8,2 mais perto. Por isso
`exportar` seguido de `importar` sem editar nada dá um arquivo idêntico ao original.

Layout (o que este script lê), tudo little-endian:
  cabeçalho BTX0: 'BTX0', BOM, versão, tamanho (u32), tam. do cabeçalho (u16),
                  número de blocos (u16), deslocamento de cada bloco (u32...)
  bloco TEX0 (deslocamentos relativos ao começo do bloco):
    +0x0E u16  dicionário das texturas
    +0x14 u32  dados das texturas
    +0x30 u16  tamanho dos dados de paleta >> 3 (os 16 bits seguintes são marcas)
    +0x34 u32  dicionário das paletas
    +0x38 u32  dados das paletas
  dicionário: u8 revisão, u8 N, u16 tamanho, u16, u16, (N+1)*4 bytes de árvore,
              u16 tamanho de cada entrada, u16, N entradas, N nomes de 16 bytes
    entrada de textura (8 bytes): u16 deslocamento >> 3, u16 parâmetros, u32
      parâmetros: largura = 8 << bits 4-6, altura = 8 << bits 7-9, formato = bits 10-12
    entrada de paleta (4 bytes): u16 deslocamento >> 3, u16
  cor: BGR555 (bits 0-4 vermelho, 5-9 verde, 10-14 azul)
"""
import csv
import os
import struct
import sys

FORMATOS = {1: 'A3I5', 2: '4 cores', 3: '16 cores', 4: '256 cores',
            5: '4x4 comprimido', 6: 'A5I3', 7: 'cor direta'}
BITS = {2: 2, 3: 4, 4: 8}          # formatos indexados simples que sabemos desenhar


def dicionario(b, o):
    n = b[o + 1]
    entradas = o + 8 + (n + 1) * 4
    tam = struct.unpack_from('<H', b, entradas)[0]
    dados = entradas + 4
    nomes = dados + n * tam
    return [(b[nomes + 16 * i:nomes + 16 * i + 16].rstrip(b'\0').decode('ascii', 'replace'),
             b[dados + i * tam:dados + (i + 1) * tam]) for i in range(n)]


def abrir(caminho):
    b = bytearray(open(caminho, 'rb').read())
    if b[:4] != b'BTX0':
        raise SystemExit(f'{caminho}: não é um .nsbtx (começa com {bytes(b[:4])!r}, esperado BTX0)')
    t = struct.unpack_from('<I', b, 0x10)[0]
    if b[t:t + 4] != b'TEX0':
        raise SystemExit(f'{caminho}: bloco TEX0 não encontrado')
    u16 = lambda o: struct.unpack_from('<H', b, t + o)[0]
    u32 = lambda o: struct.unpack_from('<I', b, t + o)[0]
    texturas = []
    for nome, e in dicionario(b, t + u16(0x0E)):
        desl, p = struct.unpack_from('<HH', e)
        texturas.append({'nome': nome, 'inicio': t + u32(0x14) + (desl << 3),
                         'largura': 8 << ((p >> 4) & 7), 'altura': 8 << ((p >> 7) & 7),
                         'formato': (p >> 10) & 7})
    tam_pal = u16(0x30) << 3           # os 16 bits de cima são marcas, não tamanho
    ini_pal = t + u32(0x38)
    paletas = []
    if tam_pal == 0:                    # só texturas de cor direta: não há paletas
        return b, texturas, paletas
    pals = dicionario(b, t + u32(0x34))
    inicios = sorted({ini_pal + (struct.unpack_from('<H', e)[0] << 3) for _, e in pals}) + [ini_pal + tam_pal]
    for nome, e in pals:
        ini = ini_pal + (struct.unpack_from('<H', e)[0] << 3)
        fim = min(x for x in inicios if x > ini)          # até a próxima paleta
        paletas.append({'nome': nome, 'inicio': ini, 'cores': (fim - ini) // 2})
    return b, texturas, paletas


def cor(b, o):
    c = struct.unpack_from('<H', b, o)[0]
    return [round((c >> s & 31) * 255 / 31) for s in (0, 5, 10)], c & 0x8000


def info(caminho):
    _, texturas, paletas = abrir(caminho)
    for t in texturas:
        print(f"textura {t['nome']:16s} {t['largura']}x{t['altura']}  {FORMATOS.get(t['formato'], '?')}")
    for p in paletas:
        print(f"paleta  {p['nome']:16s} {p['cores']} cores")


def paleta_da(textura, paletas):
    # convenção do jogo: a paleta de "X" se chama "X_pl"
    for p in paletas:
        if p['nome'].lower() == (textura['nome'] + '_pl').lower():
            return p
    return paletas[0] if len(paletas) == 1 else None


def png(caminho, pasta):
    from PIL import Image
    b, texturas, paletas = abrir(caminho)
    os.makedirs(pasta, exist_ok=True)
    for t in texturas:
        bits, p = BITS.get(t['formato']), paleta_da(t, paletas)
        if bits is None or p is None:
            print(f"{t['nome']}: formato {FORMATOS.get(t['formato'], '?')} ainda não é desenhado (pulado)")
            continue
        img = Image.new('RGB', (t['largura'], t['altura']))
        por_byte = 8 // bits
        for i in range(t['largura'] * t['altura']):
            byte = b[t['inicio'] + i // por_byte]
            indice = (byte >> ((i % por_byte) * bits)) & ((1 << bits) - 1)   # pixel da esquerda nos bits baixos
            img.putpixel((i % t['largura'], i // t['largura']), tuple(cor(b, p['inicio'] + 2 * indice)[0]))
        saida = os.path.join(pasta, t['nome'] + '.png')
        img.save(saida)
        print(f'{saida} (paleta {p["nome"]})')


def exportar(caminho, saida_csv):
    b, _, paletas = abrir(caminho)
    with open(saida_csv, 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['paleta', 'indice', 'r', 'g', 'b'])
        for p in paletas:
            for i in range(p['cores']):
                w.writerow([p['nome'], i, *cor(b, p['inicio'] + 2 * i)[0]])
    print(f'{saida_csv}: {sum(p["cores"] for p in paletas)} cores de {len(paletas)} paletas')


def importar(caminho, entrada_csv, saida):
    b, _, paletas = abrir(caminho)
    por_nome = {p['nome']: p for p in paletas}
    trocadas = 0
    for n, linha in enumerate(csv.DictReader(open(entrada_csv)), start=2):
        p = por_nome.get(linha['paleta'])
        i = int(linha['indice'])
        if p is None or not 0 <= i < p['cores']:
            raise SystemExit(f'{entrada_csv} linha {n}: paleta {linha["paleta"]!r} ou índice {i} não existe')
        o = p['inicio'] + 2 * i
        _, alfa = cor(b, o)
        canais = [min(31, max(0, round(int(linha[k]) * 31 / 255))) for k in 'rgb']
        novo = canais[0] | canais[1] << 5 | canais[2] << 10 | alfa
        if novo != struct.unpack_from('<H', b, o)[0]:
            struct.pack_into('<H', b, o, novo)
            trocadas += 1
    open(saida, 'wb').write(b)
    print(f'{saida}: {trocadas} cores trocadas')


if __name__ == '__main__':
    acoes = {'info': (info, 1), 'png': (png, 2), 'exportar': (exportar, 2), 'importar': (importar, 3)}
    if len(sys.argv) < 2 or sys.argv[1] not in acoes or len(sys.argv) != acoes[sys.argv[1]][1] + 2:
        raise SystemExit(__doc__)
    acoes[sys.argv[1]][0](*sys.argv[2:])
