"""Codificador e decodificador dos formatos gráficos Nitro do Nintendo DS:
- NCLR (Nitro Color Resource - paleta de cores BGR555)
- NCGR (Nitro Character Graphics Resource - tiles de 8x8 pixels a 4bpp ou 8bpp)
"""

import struct
from typing import Tuple, List, Optional
from PIL import Image

from .bgr555 import (
    quantize_image_to_ds_palette,
    map_pixels_to_palette,
    bgr555_to_rgb,
    rgb_to_bgr555,
)


def create_nclr_binary(bgr_colors: List[int], bpp: int = 4) -> bytes:
    """Cria o binário NCLR (RLCN + TTLP) a partir de uma lista de cores BGR555."""
    num_colors = 16 if bpp == 4 else 256
    colors = list(bgr_colors)
    while len(colors) < num_colors:
        colors.append(0)
    colors = colors[:num_colors]

    color_bytes = bytearray()
    for c in colors:
        color_bytes.extend(struct.pack("<H", c & 0xFFFF))

    # TTLP section
    # 0x00: b'TTLP'
    # 0x04: section_size (incluindo o header de 24 bytes + dados)
    # 0x08: bpp (3 para 4bpp, 4 para 8bpp)
    # 0x0C: reserved (0)
    # 0x10: data_size
    # 0x14: data_offset (relativo a 0x18, geralmente 0x00000008, apontando para 0x20)
    data_size = len(color_bytes)
    ttlp_header_size = 24
    ttlp_section_size = ttlp_header_size + data_size
    ttlp_header = struct.pack(
        "<4sIIIII",
        b"TTLP",
        ttlp_section_size,
        3 if bpp == 4 else 4,
        0,
        data_size,
        16,  # data_offset relativo a 0x18 (0x18 + 0x10 = 0x28, onde começam as cores)
    )
    ttlp_chunk = ttlp_header + color_bytes

    # RLCN header
    # 0x00: b'RLCN'
    # 0x04: byte_order (0xFEFF)
    # 0x06: version (0x0100)
    # 0x08: file_size
    # 0x0C: header_size (16)
    # 0x0E: num_sections (1)
    file_size = 16 + len(ttlp_chunk)
    rlcn_header = struct.pack(
        "<4sHHIHH",
        b"RLCN",
        0xFEFF,
        0x0100,
        file_size,
        16,
        1,
    )

    return rlcn_header + ttlp_chunk


def parse_nclr_binary(data: bytes) -> Tuple[List[int], List[Tuple[int, int, int, int]], int]:
    """Decodifica um binário NCLR.

    Returns:
        (bgr_palette, rgba_palette, bpp)
    """
    if len(data) < 40 or data[0:4] != b"RLCN":
        raise ValueError("Dados inválidos: assinatura RLCN não encontrada")

    ttlp_offset = 16
    if data[ttlp_offset:ttlp_offset+4] != b"TTLP":
        raise ValueError("Assinatura TTLP não encontrada")

    ttlp_magic, sec_size, bpp_val, res, data_sz, data_rel_off = struct.unpack_from(
        "<4sIIIII", data, ttlp_offset
    )
    bpp = 4 if bpp_val == 3 else 8
    actual_data_offset = 0x18 + data_rel_off
    raw_color_data = data[actual_data_offset:actual_data_offset + data_sz]

    bgr_palette = []
    rgba_palette = []

    for i in range(0, len(raw_color_data), 2):
        if i + 2 > len(raw_color_data):
            break
        val = struct.unpack_from("<H", raw_color_data, i)[0]
        bgr_palette.append(val)
        r, g, b = bgr555_to_rgb(val)
        # Índice 0 é transparente por convenção
        alpha = 0 if len(bgr_palette) == 1 else 255
        rgba_palette.append((r, g, b, alpha))

    return bgr_palette, rgba_palette, bpp


def create_ncgr_binary(
    indexed_pixels: List[int],
    width: int,
    height: int,
    bpp: int = 4,
    linear: bool = False
) -> bytes:
    """Cria o binário NCGR (RGCN + RAHC) a partir de índices de pixel organizados em blocos de 8x8."""
    if width % 8 != 0 or height % 8 != 0:
        raise ValueError(f"Largura ({width}) e altura ({height}) devem ser múltiplos de 8.")

    width_tiles = width // 8
    height_tiles = height // 8
    pixel_data = bytearray()

    if linear:
        # Modo linear de 1D
        if bpp == 4:
            for i in range(0, len(indexed_pixels), 2):
                p0 = indexed_pixels[i] & 0x0F
                p1 = indexed_pixels[i+1] & 0x0F if i+1 < len(indexed_pixels) else 0
                pixel_data.append(p0 | (p1 << 4))
        else:
            for p in indexed_pixels:
                pixel_data.append(p & 0xFF)
    else:
        # Modo de blocos 8x8 (tiled): padrão do Nintendo DS
        for tile_y in range(height_tiles):
            for tile_x in range(width_tiles):
                tile_indices = []
                for py in range(8):
                    for px in range(8):
                        gx = tile_x * 8 + px
                        gy = tile_y * 8 + py
                        idx = gy * width + gx
                        tile_indices.append(indexed_pixels[idx])

                if bpp == 4:
                    for i in range(0, 64, 2):
                        p0 = tile_indices[i] & 0x0F
                        p1 = tile_indices[i+1] & 0x0F
                        pixel_data.append(p0 | (p1 << 4))
                else:
                    for p in tile_indices:
                        pixel_data.append(p & 0xFF)

    # RAHC section
    # 0x00: b'RAHC'
    # 0x04: section_size (incluindo o header de 32 bytes + dados)
    # 0x08: height_tiles (u16)
    # 0x0A: width_tiles (u16)
    # 0x0C: bpp (3 para 4bpp, 4 para 8bpp)
    # 0x10: mapping_type (0 = 2D)
    # 0x14: tiled_flag (1 se linear, 0 se tiled 8x8)
    # 0x18: data_size
    # 0x1C: data_offset (relativo a 0x18, geralmente 0x00000010)
    data_size = len(pixel_data)
    rahc_header_size = 32
    rahc_section_size = rahc_header_size + data_size
    rahc_header = struct.pack(
        "<4sIHHIIIII",
        b"RAHC",
        rahc_section_size,
        height_tiles,
        width_tiles,
        3 if bpp == 4 else 4,
        0,  # 2D mapping
        1 if linear else 0,
        data_size,
        24,  # offset a partir de 0x18 (0x18 + 0x18 = 0x30, onde começam os pixels)
    )
    rahc_chunk = rahc_header + pixel_data

    # RGCN header (16 bytes)
    file_size = 16 + len(rahc_chunk)
    rgcn_header = struct.pack(
        "<4sHHIHH",
        b"RGCN",
        0xFEFF,
        0x0100,
        file_size,
        16,
        1,
    )

    return rgcn_header + rahc_chunk


def parse_ncgr_binary(data: bytes) -> Tuple[List[int], int, int, int, bool]:
    """Decodifica um binário NCGR.

    Returns:
        (indexed_pixels, width, height, bpp, linear)
    """
    if len(data) < 48 or data[0:4] != b"RGCN":
        raise ValueError("Dados inválidos: assinatura RGCN não encontrada")

    rahc_offset = 16
    if data[rahc_offset:rahc_offset+4] != b"RAHC":
        raise ValueError("Assinatura RAHC não encontrada")

    magic, sec_sz, h_tiles, w_tiles, bpp_val, map_type, tiled_flg, data_sz, data_rel_off = struct.unpack_from(
        "<4sIHHIIIII", data, rahc_offset
    )
    bpp = 4 if bpp_val == 3 else 8
    linear = (tiled_flg & 0xFF) == 1

    actual_data_offset = 0x18 + data_rel_off
    raw_pixel_data = data[actual_data_offset:actual_data_offset + data_sz]

    width = w_tiles * 8 if w_tiles != 0 and w_tiles != 0xFFFF else 0
    height = h_tiles * 8 if h_tiles != 0 and h_tiles != 0xFFFF else 0

    # Decodifica pixels brutos
    tile_indices = []
    if bpp == 4:
        for b in raw_pixel_data:
            tile_indices.append(b & 0x0F)
            tile_indices.append((b >> 4) & 0x0F)
    else:
        tile_indices = list(raw_pixel_data)

    if width == 0 or height == 0:
        # Se dimensões não informadas, estima com base no total de tiles
        total_tiles = len(tile_indices) // 64
        w_tiles = min(total_tiles, 8) if total_tiles > 0 else 1
        h_tiles = (total_tiles + w_tiles - 1) // w_tiles if w_tiles > 0 else 1
        width = w_tiles * 8
        height = h_tiles * 8

    # Reconstrói a grade linear x, y a partir do modo de blocos se não for linear
    if linear:
        indexed_pixels = tile_indices[:width * height]
    else:
        indexed_pixels = [0] * (width * height)
        idx = 0
        width_tiles = width // 8
        height_tiles = height // 8
        for tile_y in range(height_tiles):
            for tile_x in range(width_tiles):
                for py in range(8):
                    for px in range(8):
                        if idx < len(tile_indices):
                            gx = tile_x * 8 + px
                            gy = tile_y * 8 + py
                            if gx < width and gy < height:
                                indexed_pixels[gy * width + gx] = tile_indices[idx]
                            idx += 1

    return indexed_pixels, width, height, bpp, linear


def encode_png_to_ncgr_nclr(
    png_path: str,
    out_ncgr_path: str,
    out_nclr_path: str,
    bpp: int = 4
) -> Tuple[int, int]:
    """Converte um arquivo PNG em arquivos NCGR e NCLR válidos do Nintendo DS.

    Returns:
        (largura, altura) da imagem codificada.
    """
    img = Image.open(png_path).convert("RGBA")
    w, h = img.size

    # Ajusta dimensões para múltiplos de 8 se necessário
    if w % 8 != 0 or h % 8 != 0:
        pad_w = ((w + 7) // 8) * 8
        pad_h = ((h + 7) // 8) * 8
        padded = Image.new("RGBA", (pad_w, pad_h), (0, 0, 0, 0))
        padded.paste(img, (0, 0))
        img = padded
        w, h = pad_w, pad_h

    max_colors = 16 if bpp == 4 else 256
    bgr_palette, rgba_palette = quantize_image_to_ds_palette(img, max_colors=max_colors)
    indexed_pixels = map_pixels_to_palette(img, rgba_palette)

    nclr_data = create_nclr_binary(bgr_palette, bpp=bpp)
    ncgr_data = create_ncgr_binary(indexed_pixels, w, h, bpp=bpp, linear=False)

    with open(out_nclr_path, "wb") as f:
        f.write(nclr_data)

    with open(out_ncgr_path, "wb") as f:
        f.write(ncgr_data)

    return w, h


def decode_ncgr_nclr_to_png(
    ncgr_path: str,
    nclr_path: str,
    out_png_path: str
) -> Tuple[int, int]:
    """Decodifica arquivos NCGR e NCLR para uma imagem PNG.

    Returns:
        (largura, altura) da imagem gerada.
    """
    with open(ncgr_path, "rb") as f:
        ncgr_data = f.read()
    with open(nclr_path, "rb") as f:
        nclr_data = f.read()

    bgr_palette, rgba_palette, pal_bpp = parse_nclr_binary(nclr_data)
    indexed_pixels, w, h, ncgr_bpp, linear = parse_ncgr_binary(ncgr_data)

    img = Image.new("RGBA", (w, h))
    rgba_pixels = []
    for idx in indexed_pixels:
        if idx < len(rgba_palette):
            rgba_pixels.append(rgba_palette[idx])
        else:
            rgba_pixels.append((255, 0, 255, 255))  # Cor de erro

    img.putdata(rgba_pixels)
    img.save(out_png_path, "PNG")
    return w, h
