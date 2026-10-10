"""Script de geração completa dos 5 golpes POW para Silver the Hedgehog.

Gera:
1. 5 badges 32x32 (PNG -> NCGR + NCLR)
2. 5 retratos 128x128 (PNG -> 4x 64x64 NCGR + NCLR composite 2x2)
3. 5 scripts 2DA (.SPL)
4. 5 emissores de partículas (.emit + .json)
5. Atualização da definição de criaturas (creatures_silver_entry.csv)
6. Registro de combos (combo_silver_moves.csv)
"""

import os
from PIL import Image, ImageDraw
from tools.asset_pipeline.core.ncgr_nclr import encode_png_to_ncgr_nclr
from tools.asset_pipeline.core.composite_2x2 import split_128_to_quads
from tools.asset_pipeline.studio.vfx_studio import VfxStudio
from tools.asset_pipeline.studio.pow_generator import generate_spell_2da


def create_all_silver_pows(out_dir: str):
    os.makedirs(out_dir, exist_ok=True)
    vfx_studio = VfxStudio(out_dir)

    moves = [
        {
            "id": 170,
            "name": "PsychokinesisSlam",
            "title_pt": "Arremesso Psicocinético",
            "vfx_preset": "psychic_cyan",
            "vfx_id": 14,
            "target": 0,
            "status_attr": 4, # Stun
            "status_val": 1,
            "pp_cost": 4,
            "dmg": (140, 185, 240),
            "partners": [],
            "badge_colors": {"bg": (15, 23, 42), "accent": (0, 229, 255), "core": (255, 255, 255)},
            "theme": "slam"
        },
        {
            "id": 171,
            "name": "ESPStasisWave",
            "title_pt": "Onda de Estase Psíquica",
            "vfx_preset": "stasis_shockwave",
            "vfx_id": 18,
            "target": 2, # All enemies
            "status_attr": 3, # Sluggish
            "status_val": 1,
            "pp_cost": 7,
            "dmg": (95, 135, 180),
            "partners": [],
            "badge_colors": {"bg": (20, 24, 48), "accent": (0, 255, 220), "core": (100, 200, 255)},
            "theme": "wave"
        },
        {
            "id": 172,
            "name": "PsychoShield",
            "title_pt": "Barreira Telecinética",
            "vfx_preset": "psycho_shield",
            "vfx_id": 20,
            "target": 1, # Ally
            "status_attr": 7, # Shield Buff
            "status_val": 2,
            "pp_cost": 5,
            "dmg": (0, 0, 0),
            "partners": [],
            "badge_colors": {"bg": (10, 32, 36), "accent": (94, 234, 212), "core": (255, 208, 0)},
            "theme": "shield"
        },
        {
            "id": 173,
            "name": "MeteorSpinVortex",
            "title_pt": "Vórtice Meteórico",
            "vfx_preset": "meteor_spin",
            "vfx_id": 22,
            "target": 0,
            "status_attr": 8, # Armor Break
            "status_val": 1,
            "pp_cost": 12,
            "dmg": (260, 340, 440),
            "partners": [0], # Sonic (ID 0)
            "badge_colors": {"bg": (16, 28, 56), "accent": (0, 180, 255), "core": (255, 140, 0)},
            "theme": "meteor"
        },
        {
            "id": 174,
            "name": "EventHorizon",
            "title_pt": "Horizonte de Eventos",
            "vfx_preset": "event_horizon",
            "vfx_id": 25,
            "target": 2, # All enemies
            "status_attr": 9, # Confusion + Sluggish
            "status_val": 1,
            "pp_cost": 14,
            "dmg": (220, 310, 420),
            "partners": [],
            "badge_colors": {"bg": (24, 8, 48), "accent": (0, 229, 255), "core": (255, 255, 255)},
            "theme": "singularity"
        }
    ]

    for m in moves:
        mname = m["name"]
        print(f"Processando POW: {mname}...")

        # 1. Gera Ícone 32x32
        img32 = Image.new("RGB", (32, 32), (255, 0, 255))
        d32 = ImageDraw.Draw(img32)
        d32.rectangle([2, 2, 29, 29], fill=m["badge_colors"]["bg"])

        th = m["theme"]
        if th == "slam":
            d32.ellipse([10, 10, 22, 22], fill=m["badge_colors"]["accent"])
            d32.ellipse([12, 12, 20, 20], fill=m["badge_colors"]["core"])
            d32.line([(6, 26), (6, 6)], fill=m["badge_colors"]["accent"], width=2)
            d32.line([(25, 26), (25, 6)], fill=m["badge_colors"]["accent"], width=2)
        elif th == "wave":
            d32.ellipse([4, 4, 27, 27], outline=m["badge_colors"]["accent"], width=2)
            d32.ellipse([8, 8, 23, 23], outline=m["badge_colors"]["core"], width=2)
            d32.ellipse([12, 12, 19, 19], fill=(255, 255, 255))
        elif th == "shield":
            d32.polygon([(16, 4), (27, 10), (27, 22), (16, 28), (5, 22), (5, 10)], outline=m["badge_colors"]["accent"], width=2)
            d32.polygon([(16, 8), (24, 12), (24, 20), (16, 24), (8, 20), (8, 12)], fill=m["badge_colors"]["accent"])
            d32.ellipse([13, 13, 19, 19], fill=m["badge_colors"]["core"])
        elif th == "meteor":
            d32.ellipse([6, 6, 25, 25], outline=m["badge_colors"]["accent"], width=2)
            d32.ellipse([10, 10, 21, 21], fill=(0, 102, 204)) # Azul Sonic
            d32.line([(4, 28), (28, 4)], fill=m["badge_colors"]["core"], width=2)
            d32.ellipse([12, 12, 19, 19], fill=(255, 200, 0))
        elif th == "singularity":
            d32.ellipse([5, 5, 26, 26], fill=(50, 0, 80))
            d32.ellipse([9, 9, 22, 22], outline=m["badge_colors"]["accent"], width=2)
            d32.ellipse([12, 12, 19, 19], fill=(10, 0, 20)) # Vácuo negro
            d32.ellipse([14, 14, 17, 17], fill=(255, 255, 255)) # Ponto singular

        icon32_path = os.path.join(out_dir, f"POW_{mname}_32.png")
        img32.save(icon32_path)
        encode_png_to_ncgr_nclr(
            icon32_path,
            os.path.join(out_dir, f"POW_{mname}.ncgr"),
            os.path.join(out_dir, f"POW_{mname}.nclr"),
            bpp=4
        )

        # 2. Gera Retrato 128x128
        img128 = Image.new("RGB", (128, 128), (255, 0, 255))
        d128 = ImageDraw.Draw(img128)
        d128.rectangle([4, 4, 123, 123], fill=m["badge_colors"]["bg"])
        d128.rectangle([6, 6, 121, 121], outline=m["badge_colors"]["accent"], width=2)

        # Desenha elemento ampliado em 128x128
        if th == "slam":
            d128.ellipse([34, 34, 94, 94], fill=m["badge_colors"]["accent"])
            d128.ellipse([46, 46, 82, 82], fill=m["badge_colors"]["core"])
            d128.ellipse([54, 54, 74, 74], fill=m["badge_colors"]["accent"])
            d128.polygon([(20, 100), (28, 20), (36, 100)], fill=(0, 229, 255))
            d128.polygon([(92, 100), (100, 20), (108, 100)], fill=(0, 229, 255))
        elif th == "wave":
            d128.ellipse([16, 16, 111, 111], outline=m["badge_colors"]["accent"], width=4)
            d128.ellipse([32, 32, 95, 95], outline=m["badge_colors"]["core"], width=3)
            d128.ellipse([48, 48, 79, 79], fill=(255, 255, 255))
        elif th == "shield":
            d128.polygon([(64, 14), (110, 36), (110, 92), (64, 114), (18, 92), (18, 36)], outline=m["badge_colors"]["accent"], width=4)
            d128.polygon([(64, 26), (98, 44), (98, 84), (64, 102), (30, 84), (30, 44)], fill=m["badge_colors"]["accent"])
            d128.ellipse([48, 48, 80, 80], fill=m["badge_colors"]["core"])
        elif th == "meteor":
            d128.ellipse([24, 24, 103, 103], outline=m["badge_colors"]["accent"], width=4)
            d128.ellipse([36, 36, 91, 91], fill=(0, 102, 204))
            d128.line([(16, 112), (112, 16)], fill=m["badge_colors"]["core"], width=6)
            d128.ellipse([46, 46, 81, 81], fill=(255, 200, 0))
        elif th == "singularity":
            d128.ellipse([18, 18, 109, 109], fill=(50, 0, 80))
            d128.ellipse([30, 30, 97, 97], outline=m["badge_colors"]["accent"], width=4)
            d128.ellipse([42, 42, 85, 85], fill=(10, 0, 20))
            d128.ellipse([54, 54, 73, 73], fill=(255, 255, 255))

        icon128_path = os.path.join(out_dir, f"POW_{mname}_128.png")
        img128.save(icon128_path)
        split_128_to_quads(icon128_path, out_dir, f"POW_{mname}_Big", bpp=4)

        # 3. Gera Script 2DA (.SPL)
        spl_code = generate_spell_2da(
            spell_name=mname,
            target=m["target"],
            vfx_id=m["vfx_id"],
            status_attr=m["status_attr"],
            status_val=m["status_val"]
        )
        spl_path = os.path.join(out_dir, f"Spell_{mname}.SPL")
        with open(spl_path, "w", encoding="latin-1") as f:
            f.write(spl_code)

        # 4. Gera Emissor de Partículas (.emit + .json)
        emitter_def = vfx_studio.create_emitter_definition(m["vfx_preset"], custom_name=f"VFX_{mname}")
        vfx_studio.export_emitter_json(emitter_def, os.path.join(out_dir, f"vfx_{mname.lower()}.json"))
        vfx_studio.export_emitter_binary(emitter_def, os.path.join(out_dir, f"vfx_{mname.lower()}.emit"))

    # 5. Gera Tabela combo_silver_moves.csv
    combo_csv_path = os.path.join(out_dir, "combo_silver_moves.csv")
    with open(combo_csv_path, "w", encoding="utf-8") as f:
        f.write("ID,Name,Description,Owner,Participants,Partner1,Cost,Damage1,Damage2,Damage3,ArmorPiercing\n")
        for m in moves:
            p_count = 1 + len(m["partners"])
            p1 = str(m["partners"][0]) if m["partners"] else ""
            ap = "1" if m["theme"] in ("slam", "meteor", "singularity") else "0"
            f.write(f"{m['id']},995{m['id']},995{m['id']+1},11,{p_count},{p1},{m['pp_cost']},{m['dmg'][0]},{m['dmg'][1]},{m['dmg'][2]},{ap}\n")

    # 6. Atualiza creatures_silver_entry.csv com os 5 combos
    creature_path = os.path.join(out_dir, "creatures_silver_entry.csv")
    with open(creature_path, "w", encoding="utf-8") as f:
        f.write("ID,NameStrRef,Class,HitPoints,MaxHitPoints,Fatigue,MaxFatigue,Attack,Defense,Speed,Health,Power,Grit,Luck,NumActions,MoveSpeed,ScaleModifier,PortraitResRef,ModelResRef,Combo1,Combo2,Combo3,Combo4,Combo5,Combo6,Combo7,Combo8,Combo9,Combo10\n")
        f.write("11,996000,2,38,38,12,12,7,11,8,10,9,5,6,2,140.0,100.0,prtl_silverglad,silver_the_hedgehog,170,171,172,173,174,-1,-1,-1,-1,-1\n")

    print("\nTodos os 5 golpes POW do Silver foram gerados com sucesso!")


if __name__ == "__main__":
    create_all_silver_pows("assets_showcase/silver_showcase")
