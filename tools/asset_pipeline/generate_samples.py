"""Gera uma suíte completa de assets de demonstração validando o pipeline."""

import os
from PIL import Image, ImageDraw

from .core.ncgr_nclr import encode_png_to_ncgr_nclr, decode_ncgr_nclr_to_png
from .core.composite_2x2 import split_128_to_quads, merge_quads_to_128
from .core.obj_to_imd import convert_obj_to_imd
from .studio.vfx_studio import VfxStudio
from .studio.item_generator import ItemGenerator
from .studio.pow_generator import PowGenerator


def generate_samples(output_dir: str = "assets_showcase"):
    os.makedirs(output_dir, exist_ok=True)
    print(f"=== Gerando Assets de Demonstração em '{output_dir}' ===")

    # 1. Ícone de Item 32x32 (Chili Dog / Anel de Energia)
    icon_png = os.path.join(output_dir, "icon_ring_energy.png")
    img = Image.new("RGBA", (32, 32), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    # Borda externa dourada escura
    draw.ellipse([3, 3, 28, 28], outline=(140, 90, 0, 255), width=2)
    # Anel dourado brilhante
    draw.ellipse([5, 5, 26, 26], outline=(255, 215, 0, 255), width=3)
    # Brilho de energia ciano no centro
    draw.ellipse([10, 10, 21, 21], fill=(0, 230, 255, 255), outline=(0, 100, 180, 255))
    img.save(icon_png)

    ncgr_path = os.path.join(output_dir, "ITM_RingEnergy.ncgr")
    nclr_path = os.path.join(output_dir, "ITM_RingEnergy.nclr")
    encode_png_to_ncgr_nclr(icon_png, ncgr_path, nclr_path, bpp=4)
    print(f"[1/5] Ícone 32x32 codificado: {ncgr_path} + {nclr_path}")

    # Decodifica de volta para conferência
    decoded_icon = os.path.join(output_dir, "icon_ring_energy_decoded.png")
    decode_ncgr_nclr_to_png(ncgr_path, nclr_path, decoded_icon)

    # 2. Retrato de Diálogo 128x128
    portrait_png = os.path.join(output_dir, "PRTL_SonicShowcase.png")
    p_img = Image.new("RGBA", (128, 128), (0, 0, 0, 0))
    p_draw = ImageDraw.Draw(p_img)
    # Fundo estilizado de vinheta circular
    p_draw.ellipse([4, 4, 123, 123], fill=(20, 40, 80, 255), outline=(10, 20, 50, 255), width=2)
    # Cabeça azul do Sonic
    p_draw.ellipse([24, 24, 104, 104], fill=(16, 64, 208, 255), outline=(0, 0, 0, 255), width=3)
    # Olhos expressivos
    p_draw.ellipse([40, 36, 64, 76], fill=(255, 255, 255, 255), outline=(0, 0, 0, 255), width=2)
    p_draw.ellipse([64, 36, 88, 76], fill=(255, 255, 255, 255), outline=(0, 0, 0, 255), width=2)
    # Pupilas verdes
    p_draw.ellipse([52, 48, 62, 68], fill=(0, 200, 80, 255), outline=(0, 0, 0, 255), width=1)
    p_draw.ellipse([66, 48, 76, 68], fill=(0, 200, 80, 255), outline=(0, 0, 0, 255), width=1)
    # Focinho / Pele pêssego
    p_draw.ellipse([42, 68, 86, 98], fill=(255, 200, 160, 255), outline=(0, 0, 0, 255), width=2)
    # Nariz preto
    p_draw.ellipse([60, 64, 68, 72], fill=(0, 0, 0, 255))
    p_img.save(portrait_png)

    split_dir = os.path.join(output_dir, "portrait_quads")
    split_files = split_128_to_quads(portrait_png, split_dir, "PRTL_SonicShowcase", bpp=4)
    print(f"[2/5] Retrato 128x128 fatiado em 2x2: {len(split_files)} arquivos em {split_dir}")

    # Remonta
    remounted_png = os.path.join(output_dir, "PRTL_SonicShowcase_remounted.png")
    merge_quads_to_128(split_files[1:], split_files[0], remounted_png)

    # 3. Modelo 3D Wavefront OBJ -> Nitro IMD (Chaos Emerald Low-Poly)
    obj_path = os.path.join(output_dir, "chaos_emerald.obj")
    obj_content = """# Low-Poly Chaos Emerald
v 0.0 1.2 0.0
v -0.8 0.4 -0.8
v 0.8 0.4 -0.8
v 0.8 0.4 0.8
v -0.8 0.4 0.8
v 0.0 -1.0 0.0
vt 0.5 1.0
vt 0.0 0.5
vt 1.0 0.5
vt 0.5 0.0
vn 0.0 1.0 0.0
vn 0.0 -1.0 0.0
# Top facets
f 1/1/1 2/2/1 3/3/1
f 1/1/1 3/2/1 4/3/1
f 1/1/1 4/2/1 5/3/1
f 1/1/1 5/2/1 2/3/1
# Bottom facets
f 6/4/2 3/3/2 2/2/2
f 6/4/2 4/3/2 3/2/2
f 6/4/2 5/3/2 4/2/2
f 6/4/2 2/3/2 5/2/2
"""
    with open(obj_path, "w", encoding="utf-8") as f:
        f.write(obj_content)

    imd_path = os.path.join(output_dir, "chaos_emerald.imd")
    convert_obj_to_imd(obj_path, imd_path, texture_name="emerald_tex", palette_name="emerald_pal", scale=1.0)
    print(f"[3/5] Modelo 3D convertido para Nitro IMD: {imd_path}")

    # 4. Efeitos Visuais (VFX Presets)
    vfx = VfxStudio()
    for preset_key in ("chaos_energy", "fire_burst", "heal_sparkle"):
        defn = vfx.create_emitter_definition(preset_key)
        vfx.export_emitter_json(defn, os.path.join(output_dir, f"vfx_{preset_key}.json"))
        vfx.export_emitter_binary(defn, os.path.join(output_dir, f"vfx_{preset_key}.emit"))
    print(f"[4/5] Presets de partículas exportados (.json e .emit)")

    # 5. Scaffold de Item e POW
    sample_proj = os.path.join(output_dir, "sample_mod_project")
    item_gen = ItemGenerator(sample_proj)
    item_res = item_gen.create_item(
        name="Chaos Nectar",
        description="Essência pura de esmeralda. Restaura 200 HP e 10 PP.",
        cost=500,
        heal_hp=200,
        heal_pp=10,
        icon_png_path=icon_png
    )
    pow_gen = PowGenerator(sample_proj)
    pow_res = pow_gen.create_pow(
        name="Sonic Boom Slash",
        description="Lâmina de vácuo sônica que retalha as defesas do oponente.",
        owner_id=0,
        pp_cost=6,
        damage_l1=150,
        damage_l2=200,
        damage_l3=260,
        armor_piercing=True,
        icon_png_path=icon_png
    )
    print(f"[5/5] Item '{item_res['name']}' e POW '{pow_res['name']}' gerados no mod project")
    print("\n[OK] Todos os assets de demonstração gerados com sucesso!")


if __name__ == "__main__":
    generate_samples()
