"""Monta um efeito visual (VFX) novo do tipo 3 a partir de quadros PNG nossos.

Uso: python3 montar_vfx.py PASTA_ORIGINAIS PASTA_QUADROS PASTA_SAIDA NOME [MOLDE]

  PASTA_ORIGINAIS  a pasta `herf/test` de um `sonic-dump` da SUA ROM (de lá vêm os moldes)
  PASTA_QUADROS    boom_f1.png ... boom_f8.png: 8 quadros RGBA de 32x32 (ver abaixo)
  PASTA_SAIDA      onde gravar; normalmente <projeto do sonic-mod>/arquivos/test
  NOME             nome dos arquivos novos, ex.: FX_SonicBoom
  MOLDE            efeito do jogo usado de molde (padrão FX_SmokePuff)

Por que um molde: na batalha o jogo só desenha efeitos do tipo 3 (modelo 3D + textura,
ver docs/DIARIO.md seção 22). Fazer um modelo 3D do zero é muito trabalho; o
FX_SmokePuff já é o que precisamos: um quadrado (o .nsbmd) que troca de textura 8 vezes,
como um "flipbook" (o .nsbtp diz quando trocar). Então copiamos o modelo e o flipbook
como estão e trocamos só o DESENHO das 8 texturas (o .nsbtx) pelos nossos quadros.
O resultado são três arquivos NOME.nsbmd/.nsbtx/.nsbtp que o `sonic-mod pack` coloca na
ROM como arquivos novos. Eles contêm partes do jogo (o modelo e o flipbook): ficam só no
seu projeto de mod, nunca no Git. O que vai para o Git são os quadros e este script.

O formato das texturas é A3I5: cada pixel é 1 byte = 3 bits de transparência (8 níveis)
+ 5 bits de cor (índice numa paleta de até 32 cores, em 15 bits BGR555). Por isso os
quadros precisam: 32x32, no máximo 32 cores no total e alfa em 8 níveis. O script avisa
se algo não couber. Todas as texturas passam a usar uma única paleta (a do molde tinha
uma por quadro).
"""
import os
import shutil
import struct
import sys

from PIL import Image


def dicionario(d, off):
    """Lê um dicionário Nitro: devolve [(nome, posição_dos_dados, dados)]."""
    n = d[off + 1]
    p = off + 12 + 4 * n                       # pula cabeçalho e a árvore de busca
    unidade = struct.unpack_from('<H', d, p)[0]
    nomes = p + 4 + unidade * n
    return [(d[nomes + 16 * i:nomes + 16 * (i + 1)].rstrip(b'\0').decode(),
             p + 4 + unidade * i, d[p + 4 + unidade * i:p + 4 + unidade * (i + 1)])
            for i in range(n)]


def secao_tex0(d):
    assert d[:4] == b'BTX0', 'não é um .nsbtx'
    t = struct.unpack_from('<I', d, 0x10)[0]
    assert d[t:t + 4] == b'TEX0'
    return t


def pixels(im):
    # o Pillow 12 renomeou getdata(); aceitamos as duas versões
    return im.get_flattened_data() if hasattr(im, 'get_flattened_data') else im.getdata()


def a3i5(quadros):
    """Converte os quadros RGBA em (paleta BGR555, [bytes A3I5 de cada quadro])."""
    cores = []
    for im in quadros:
        for r, g, b, a in pixels(im):
            if a and (r, g, b) not in cores:
                cores.append((r, g, b))
    if len(cores) > 32:
        raise SystemExit(f'{len(cores)} cores: o formato A3I5 aceita no máximo 32')
    paleta = b''.join(struct.pack('<H', (r >> 3) | (g >> 3) << 5 | (b >> 3) << 10)
                      for r, g, b in cores + [(0, 0, 0)] * (32 - len(cores)))
    texturas = []
    for im in quadros:
        texturas.append(bytes(0 if a == 0 else (round(a * 7 / 255) << 5) | cores.index((r, g, b))
                              for r, g, b, a in pixels(im)))
    return paleta, texturas, len(cores)


def main(originais, pasta_quadros, saida, nome, molde='FX_SmokePuff'):
    d = bytearray(open(os.path.join(originais, molde + '.nsbtx'), 'rb').read())
    t = secao_tex0(d)
    tex = dicionario(d, t + struct.unpack_from('<H', d, t + 0x0E)[0])
    pal = dicionario(d, t + struct.unpack_from('<H', d, t + 0x34)[0])
    dados_tex = t + struct.unpack_from('<I', d, t + 0x14)[0]
    dados_pal = t + struct.unpack_from('<I', d, t + 0x38)[0]
    tam_pal = struct.unpack_from('<I', d, t + 0x30)[0] << 3

    arquivos = sorted((f for f in os.listdir(pasta_quadros) if f.lower().endswith('.png')),
                      key=lambda f: int(''.join(c for c in f.rsplit('_f', 1)[-1] if c.isdigit())))
    quadros = [Image.open(os.path.join(pasta_quadros, f)).convert('RGBA') for f in arquivos]
    if len(quadros) != len(tex):
        raise SystemExit(f'o molde {molde} tem {len(tex)} texturas e há {len(quadros)} quadros')
    paleta, texturas, n_cores = a3i5(quadros)

    for (nome_tex, _, info), im, px in zip(tex, quadros, texturas):
        p0 = struct.unpack_from('<I', info)[0]
        w, h, fmt = 8 << ((p0 >> 20) & 7), 8 << ((p0 >> 23) & 7), (p0 >> 26) & 7
        if fmt != 1 or im.size != (w, h):
            raise SystemExit(f'{nome_tex}: o molde espera {w}x{h} em A3I5, o quadro é {im.size}')
        pos = dados_tex + ((p0 & 0xFFFF) << 3)
        d[pos:pos + w * h] = px
    assert tam_pal >= len(paleta), 'a área de paletas do molde é pequena demais'
    d[dados_pal:dados_pal + len(paleta)] = paleta          # uma paleta só, no início
    for _, pos, _ in pal:
        struct.pack_into('<H', d, pos, 0)                   # todas as texturas apontam para ela

    os.makedirs(saida, exist_ok=True)
    open(os.path.join(saida, nome + '.nsbtx'), 'wb').write(d)
    for ext in ('nsbmd', 'nsbtp'):
        shutil.copyfile(os.path.join(originais, f'{molde}.{ext}'), os.path.join(saida, f'{nome}.{ext}'))
    print(f'{nome}: {len(quadros)} quadros, {n_cores} cores, molde {molde}')
    print('  ' + ', '.join(f'{nome}.{e}' for e in ('nsbmd', 'nsbtx', 'nsbtp')), '->', saida)


if __name__ == '__main__':
    if len(sys.argv) not in (5, 6):
        raise SystemExit(__doc__)
    main(*sys.argv[1:])
