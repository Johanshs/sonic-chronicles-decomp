"""Regrava o ícone do banner (bitmap.png e palette.png) sem perder informação.

Por quê: o `dsd rom extract` salva o ícone como PNG em cores RGB. Na volta
(`dsd rom build`), cada pixel é convertido de novo para um índice da paleta
procurando a PRIMEIRA cor igual. A paleta do Sonic Chronicles tem duas
entradas com a mesma cor (2 e 4 valem 0x2083), então todo pixel de índice 4
volta como índice 2. Resultado: 16 bytes do ícone e o CRC do banner mudam, e a
ROM reconstruída não sai idêntica.

Como resolve: a cor do DS tem 5 bits por canal e o PNG tem 8. Na volta o
ds-rom só usa os 5 bits altos (`valor >> 3`), então os 3 bits baixos são
livres. Este script dá a cada entrada repetida da paleta um valor diferente
nesses bits baixos. A cor do DS continua a mesma, mas cada índice passa a ter
uma cor PNG única, e a volta fica exata.

Uso: python3 banner_sem_perda.py rom.nds dir_extraido/banner
"""
import struct, sys
from PIL import Image

rom_path, banner_dir = sys.argv[1], sys.argv[2]
with open(rom_path, "rb") as f:
    rom = f.read()
banner = struct.unpack_from("<I", rom, 0x68)[0]
bitmap = rom[banner + 0x20: banner + 0x220]   # 32x32, 4 bits por pixel, em tiles 8x8
palette = struct.unpack_from("<16H", rom, banner + 0x220)

cores = []
vistas = {}
for i, c in enumerate(palette):
    r, g, b = (c & 31) << 3, ((c >> 5) & 31) << 3, ((c >> 10) & 31) << 3
    a = 255 if i > 0 else 0
    n = vistas.get((r, g, b, a), 0)          # quantas vezes essa cor já apareceu
    vistas[(r, g, b, a)] = n + 1
    cores.append((r | n, g, b, a))           # n < 8: só mexe nos 3 bits ignorados
assert len(set(cores)) == 16, "paleta com mais de 8 cores iguais"

pal_img = Image.new("RGBA", (16, 1))
for i, c in enumerate(cores):
    pal_img.putpixel((i, 0), c)

bmp_img = Image.new("RGBA", (32, 32))
for tile in range(16):
    tx, ty = (tile % 4) * 8, (tile // 4) * 8
    for p in range(64):
        byte = bitmap[tile * 32 + p // 2]
        idx = (byte >> 4) if p % 2 else (byte & 15)
        bmp_img.putpixel((tx + p % 8, ty + p // 8), cores[idx])

pal_img.save(f"{banner_dir}/palette.png")
bmp_img.save(f"{banner_dir}/bitmap.png")
print(f"banner: {sum(v - 1 for v in vistas.values())} cor(es) repetida(s) na paleta separada(s)")
