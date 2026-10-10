"""Conversão de cores e quantização para o espaço de cores BGR555 do Nintendo DS.

No Nintendo DS, cores são representadas em 15 bits (BGR555):
- 5 bits para Vermelho (bits 0-4)
- 5 bits para Verde (bits 5-9)
- 5 bits para Azul (bits 10-14)
- Bit 15: frequentemente reservado ou flag de transparência/alfa.

Paletas 4bpp suportam 16 cores (índice 0 é transparente).
Paletas 8bpp suportam 256 cores (índice 0 é transparente).
"""

from typing import List, Tuple, Dict, Optional
from PIL import Image


def rgb_to_bgr555(r: int, g: int, b: int) -> int:
    """Converte valores RGB (0-255) para um inteiro BGR555 (15 bits, 0-32767)."""
    r5 = (r >> 3) & 0x1F
    g5 = (g >> 3) & 0x1F
    b5 = (b >> 3) & 0x1F
    return r5 | (g5 << 5) | (b5 << 10)


def bgr555_to_rgb(val: int) -> Tuple[int, int, int]:
    """Converte um inteiro BGR555 para uma tupla RGB (0-255)."""
    r5 = val & 0x1F
    g5 = (val >> 5) & 0x1F
    b5 = (val >> 10) & 0x1F
    # Expande 5 bits para 8 bits fielmente: (val * 255 + 15) // 31
    r = (r5 * 255 + 15) // 31
    g = (g5 * 255 + 15) // 31
    b = (b5 * 255 + 15) // 31
    return (r, g, b)


def quantize_image_to_ds_palette(
    image: Image.Image,
    max_colors: int = 16,
    transparent_magenta: bool = True
) -> Tuple[List[int], List[Tuple[int, int, int, int]]]:
    """Quantiza uma imagem PIL RGBA para o espaço de cores do DS.

    Args:
        image: Imagem de entrada (RGBA).
        max_colors: 16 (4bpp) ou 256 (8bpp).
        transparent_magenta: Se True, atribui a cor de fundo transparente como magenta (255, 0, 255).

    Returns:
        Uma tupla contendo:
        - lista de inteiros BGR555 (comprimento max_colors)
        - lista de tuplas RGBA (0-255) para renderização
    """
    img = image.convert("RGBA")
    width, height = img.size
    pixels = list(img.getdata())

    # Separa pixels transparentes dos opacos
    opaque_pixels = []
    has_transparency = False
    for p in pixels:
        if p[3] < 128:
            has_transparency = True
        else:
            opaque_pixels.append(p[:3])

    target_opaque_colors = max_colors - 1 if has_transparency else max_colors

    if not opaque_pixels:
        # Imagem totalmente vazia/transparente
        bgr_pal = [0] * max_colors
        rgba_pal = [(0, 0, 0, 0)] + [(255, 255, 255, 255)] * (max_colors - 1)
        return bgr_pal, rgba_pal

    # Cria imagem temporária RGB com os pixels opacos para quantização
    temp_img = Image.new("RGB", (len(opaque_pixels), 1))
    temp_img.putdata(opaque_pixels)
    quantized_temp = temp_img.quantize(colors=target_opaque_colors, method=Image.Quantize.MEDIANCUT)
    raw_palette = quantized_temp.getpalette()[:target_opaque_colors * 3]

    # Constrói paletas finais com o índice 0 como transparente
    bgr_palette = []
    rgba_palette = []

    if has_transparency:
        # Cor 0 é transparente
        if transparent_magenta:
            bgr_palette.append(rgb_to_bgr555(255, 0, 255))
            rgba_palette.append((255, 0, 255, 0))
        else:
            bgr_palette.append(0)
            rgba_palette.append((0, 0, 0, 0))
    else:
        # Se não tiver transparência, ainda assim reservamos o índice 0 para consistência de hardware
        bgr_palette.append(0)
        rgba_palette.append((0, 0, 0, 0))

    for i in range(0, len(raw_palette), 3):
        r, g, b = raw_palette[i], raw_palette[i+1], raw_palette[i+2]
        # Quantiza no espaço de 5 bits
        bgr = rgb_to_bgr555(r, g, b)
        r_ds, g_ds, b_ds = bgr555_to_rgb(bgr)
        bgr_palette.append(bgr)
        rgba_palette.append((r_ds, g_ds, b_ds, 255))

    # Preenche até o tamanho total da paleta
    while len(bgr_palette) < max_colors:
        bgr_palette.append(0)
        rgba_palette.append((0, 0, 0, 255))

    return bgr_palette[:max_colors], rgba_palette[:max_colors]


def map_pixels_to_palette(
    image: Image.Image,
    rgba_palette: List[Tuple[int, int, int, int]]
) -> List[int]:
    """Mapeia os pixels da imagem para os índices da paleta (distância euclidiana)."""
    img = image.convert("RGBA")
    pixels = list(img.getdata())
    indexed_indices = []

    for r, g, b, a in pixels:
        if a < 128:
            indexed_indices.append(0)  # Transparência
            continue

        best_idx = 1
        best_dist = float("inf")
        # Procura a cor opaca mais próxima (índices 1 até fim da paleta)
        for idx in range(1, len(rgba_palette)):
            pr, pg, pb, pa = rgba_palette[idx]
            dist = (r - pr)**2 + (g - pg)**2 + (b - pb)**2
            if dist < best_dist:
                best_dist = dist
                best_idx = idx

        indexed_indices.append(best_idx)

    return indexed_indices
