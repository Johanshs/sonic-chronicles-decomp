"""Montador e fatiador de retratos e ícones em grade 2x2 (128x128 <-> 4x 64x64).

No Sonic Chronicles, os retratos de diálogos e ícones grandes de interface
são armazenados em 4 peças NCGR de 64x64 tiles:
- _0: canto superior esquerdo (x: 0..63, y: 0..63)
- _1: canto superior direito  (x: 64..127, y: 0..63)
- _2: canto inferior esquerdo (x: 0..63, y: 64..127)
- _3: canto inferior direito  (x: 64..127, y: 64..127)
Compartilhando um único arquivo NCLR com a paleta BGR555 comum.
"""

import os
from typing import List, Tuple, Dict
from PIL import Image

from .bgr555 import (
    quantize_image_to_ds_palette,
    map_pixels_to_palette,
)
from .ncgr_nclr import (
    create_nclr_binary,
    create_ncgr_binary,
    parse_nclr_binary,
    parse_ncgr_binary,
)


def split_128_to_quads(
    png_path: str,
    out_dir: str,
    base_name: str,
    bpp: int = 4
) -> List[str]:
    """Fatia uma imagem de 128x128 em 4 arquivos NCGR (64x64) e 1 NCLR compartilhado.

    Args:
        png_path: Caminho da imagem de entrada (deve ter 128x128 pixels).
        out_dir: Diretório de destino.
        base_name: Prefixo para os arquivos gerados (ex: 'PRTL_SonicGlad').
        bpp: 4 (16 cores) ou 8 (256 cores).

    Returns:
        Lista com os caminhos dos arquivos gerados.
    """
    img = Image.open(png_path).convert("RGBA")
    if img.size != (128, 128):
        img = img.resize((128, 128), Image.Resampling.LANCZOS)

    os.makedirs(out_dir, exist_ok=True)

    # 1. Quantiza a imagem inteira de 128x128 para obter uma paleta única e coerente
    max_colors = 16 if bpp == 4 else 256
    bgr_palette, rgba_palette = quantize_image_to_ds_palette(img, max_colors=max_colors)
    all_indexed = map_pixels_to_palette(img, rgba_palette)

    # 2. Grava a paleta NCLR compartilhada
    nclr_filename = f"{base_name}.nclr"
    nclr_path = os.path.join(out_dir, nclr_filename)
    nclr_data = create_nclr_binary(bgr_palette, bpp=bpp)
    with open(nclr_path, "wb") as f:
        f.write(nclr_data)

    generated_files = [nclr_path]

    # 3. Fatiamento em 4 blocos de 64x64
    quad_coords = [
        (0, 0),    # _0: top-left
        (64, 0),   # _1: top-right
        (0, 64),   # _2: bottom-left
        (64, 64),  # _3: bottom-right
    ]

    for quad_idx, (start_x, start_y) in enumerate(quad_coords):
        quad_pixels = []
        for y in range(start_y, start_y + 64):
            for x in range(start_x, start_x + 64):
                idx = y * 128 + x
                quad_pixels.append(all_indexed[idx])

        ncgr_filename = f"{base_name}_{quad_idx}.ncgr"
        ncgr_path = os.path.join(out_dir, ncgr_filename)
        ncgr_data = create_ncgr_binary(quad_pixels, 64, 64, bpp=bpp, linear=False)
        with open(ncgr_path, "wb") as f:
            f.write(ncgr_data)
        generated_files.append(ncgr_path)

    return generated_files


def merge_quads_to_128(
    quad_ncgr_paths: List[str],
    nclr_path: str,
    out_png_path: str
) -> str:
    """Remonta 4 peças NCGR (64x64) em uma imagem de 128x128 PNG usando a paleta NCLR fornecida.

    Args:
        quad_ncgr_paths: Lista com os 4 caminhos dos NCGR (_0, _1, _2, _3).
        nclr_path: Caminho da paleta NCLR compartilhada.
        out_png_path: Destino do PNG gerado.

    Returns:
        Caminho do arquivo PNG gerado.
    """
    if len(quad_ncgr_paths) != 4:
        raise ValueError("São necessários exatamente 4 caminhos de NCGR para a montagem 2x2.")

    with open(nclr_path, "rb") as f:
        nclr_data = f.read()
    bgr_palette, rgba_palette, bpp = parse_nclr_binary(nclr_data)

    final_img = Image.new("RGBA", (128, 128), (0, 0, 0, 0))

    quad_coords = [
        (0, 0),
        (64, 0),
        (0, 64),
        (64, 64),
    ]

    for quad_idx, ncgr_file in enumerate(quad_ncgr_paths):
        with open(ncgr_file, "rb") as f:
            ncgr_data = f.read()

        indexed_pixels, w, h, _, _ = parse_ncgr_binary(ncgr_data)
        quad_img = Image.new("RGBA", (w, h))
        rgba_data = [
            rgba_palette[idx] if idx < len(rgba_palette) else (255, 0, 255, 255)
            for idx in indexed_pixels
        ]
        quad_img.putdata(rgba_data)

        dest_x, dest_y = quad_coords[quad_idx]
        final_img.paste(quad_img, (dest_x, dest_y))

    os.makedirs(os.path.dirname(os.path.abspath(out_png_path)), exist_ok=True)
    final_img.save(out_png_path, "PNG")
    return out_png_path
