"""CLI unificada do Chronicles Studio (Framework de Assets para Sonic Chronicles)."""

import argparse
import sys
import os
import json

from .core.ncgr_nclr import encode_png_to_ncgr_nclr, decode_ncgr_nclr_to_png
from .core.composite_2x2 import split_128_to_quads, merge_quads_to_128
from .core.nsbmd_inspector import NSBMDInspector
from .core.obj_to_imd import convert_obj_to_imd
from .studio.item_generator import ItemGenerator
from .studio.pow_generator import PowGenerator
from .studio.vfx_studio import VfxStudio


def cmd_icon_encode(args):
    w, h = encode_png_to_ncgr_nclr(args.input_png, args.out_ncgr, args.out_nclr, bpp=args.bpp)
    print(f"[OK] Ícone codificado com sucesso: {w}x{h} ({args.bpp}bpp)")
    print(f"  • NCGR: {args.out_ncgr}")
    print(f"  • NCLR: {args.out_nclr}")


def cmd_icon_decode(args):
    w, h = decode_ncgr_nclr_to_png(args.input_ncgr, args.input_nclr, args.out_png)
    print(f"[OK] Imagem decodificada com sucesso: {w}x{h} -> {args.out_png}")


def cmd_portrait_split(args):
    files = split_128_to_quads(args.input_png, args.out_dir, args.base_name, bpp=args.bpp)
    print(f"[OK] Retrato fatiado em 2x2 com sucesso ({len(files)} arquivos gerados):")
    for f in files:
        print(f"  • {f}")


def cmd_portrait_merge(args):
    quads = [args.quad_0, args.quad_1, args.quad_2, args.quad_3]
    out = merge_quads_to_128(quads, args.input_nclr, args.out_png)
    print(f"[OK] Retrato 128x128 remontado com sucesso -> {out}")


def cmd_model_inspect(args):
    with open(args.model_file, "rb") as f:
        data = f.read()
    inspector = NSBMDInspector(data)
    if args.json:
        print(json.dumps(inspector.summary(), indent=2))
    else:
        inspector.print_report()


def cmd_obj_to_imd(args):
    out = convert_obj_to_imd(
        args.obj_file,
        args.out_imd,
        texture_name=args.texture_name,
        palette_name=args.palette_name,
        scale=args.scale
    )
    print(f"[OK] Modelo intermediário Nitro IMD gerado com sucesso -> {out}")


def cmd_item_new(args):
    gen = ItemGenerator(args.project_dir)
    res = gen.create_item(
        name=args.name,
        description=args.desc,
        item_id=args.id,
        cost=args.cost,
        heal_hp=args.heal_hp,
        heal_pp=args.heal_pp,
        boost_power=args.boost_power,
        boost_defense=args.boost_defense,
        icon_png_path=args.icon_png,
        add_to_store=args.store
    )
    print(f"[OK] Novo item criado com sucesso:")
    print(f"  • ID: {res['item_id']} | Nome: {res['name']}")
    print(f"  • String Refs: Nome={res['name_str_ref']}, Desc={res['desc_str_ref']}")
    print(f"  • Script 2DA: {res['itm_path']}")
    print(f"  • Ícone: {res['icon_name']} (Gerado: {res['icon_generated']})")


def cmd_pow_new(args):
    gen = PowGenerator(args.project_dir)
    partners = [int(p) for p in args.partners.split(",")] if args.partners else None
    res = gen.create_pow(
        name=args.name,
        description=args.desc,
        owner_id=args.owner,
        combo_id=args.id,
        partner_ids=partners,
        pp_cost=args.cost,
        damage_l1=args.dmg1,
        damage_l2=args.dmg2,
        damage_l3=args.dmg3,
        armor_piercing=args.armor_pierce,
        all_enemies=args.all_enemies,
        icon_png_path=args.icon_png
    )
    print(f"[OK] Novo golpe POW criado com sucesso:")
    print(f"  • Combo ID: {res['combo_id']} | Nome: {res['name']}")
    print(f"  • Dono: {res['owner']} (Slot atribuído: {res['creature_slot']})")
    print(f"  • Custo PP: {res['pp_cost']} | Dano L1-L3: {res['damage']}")
    print(f"  • Script 2DA: {res['spl_path']}")
    print(f"  • Badge: {res['icon_name']} (Gerado: {res['icon_generated']})")


def cmd_vfx(args):
    vfx = VfxStudio()
    if args.list:
        print("Presets de VFX disponíveis:")
        for p in vfx.list_presets():
            preset = vfx.get_preset(p)
            print(f"  • {p:<15} - {preset['name']}: {preset['description']}")
    elif args.export_preset:
        defn = vfx.create_emitter_definition(args.export_preset, custom_name=args.name)
        out_json = f"{args.export_preset}.json"
        out_emit = f"{args.export_preset}.emit"
        vfx.export_emitter_json(defn, out_json)
        vfx.export_emitter_binary(defn, out_emit)
        print(f"[OK] Preset de VFX '{args.export_preset}' exportado:")
        print(f"  • JSON: {out_json}")
        print(f"  • Binário EMIT: {out_emit}")


def main():
    parser = argparse.ArgumentParser(
        prog="chronicles-studio",
        description="Sonic Chronicles: The Dark Brotherhood - Studio & Pipeline de Assets"
    )
    sub = parser.add_subparsers(dest="subcommand", required=True)

    # 1. icon-encode
    p_icon_enc = sub.add_parser("icon-encode", help="Converte PNG para NCGR (tiles) e NCLR (paleta)")
    p_icon_enc.add_argument("input_png", help="Caminho do PNG de entrada")
    p_icon_enc.add_argument("out_ncgr", help="Destino do arquivo .ncgr")
    p_icon_enc.add_argument("out_nclr", help="Destino do arquivo .nclr")
    p_icon_enc.add_argument("--bpp", type=int, choices=[4, 8], default=4, help="Bits por pixel (4 para 16 cores, 8 para 256)")
    p_icon_enc.set_defaults(func=cmd_icon_encode)

    # 2. icon-decode
    p_icon_dec = sub.add_parser("icon-decode", help="Decodifica NCGR e NCLR para PNG para inspeção")
    p_icon_dec.add_argument("input_ncgr", help="Caminho do .ncgr")
    p_icon_dec.add_argument("input_nclr", help="Caminho do .nclr")
    p_icon_dec.add_argument("out_png", help="Destino da imagem PNG")
    p_icon_dec.set_defaults(func=cmd_icon_decode)

    # 3. portrait-split
    p_port_split = sub.add_parser("portrait-split", help="Fatia retrato 128x128 em 4 peças 64x64 NCGR e 1 NCLR")
    p_port_split.add_argument("input_png", help="Caminho do PNG de 128x128")
    p_port_split.add_argument("out_dir", help="Diretório de saída")
    p_port_split.add_argument("base_name", help="Prefixo dos arquivos gerados (ex: PRTL_SonicGlad)")
    p_port_split.add_argument("--bpp", type=int, choices=[4, 8], default=4)
    p_port_split.set_defaults(func=cmd_portrait_split)

    # 4. portrait-merge
    p_port_merge = sub.add_parser("portrait-merge", help="Remonta 4 peças 64x64 NCGR em 1 PNG de 128x128")
    p_port_merge.add_argument("quad_0", help="Caminho de _0.ncgr (superior esquerdo)")
    p_port_merge.add_argument("quad_1", help="Caminho de _1.ncgr (superior direito)")
    p_port_merge.add_argument("quad_2", help="Caminho de _2.ncgr (inferior esquerdo)")
    p_port_merge.add_argument("quad_3", help="Caminho de _3.ncgr (inferior direito)")
    p_port_merge.add_argument("input_nclr", help="Caminho do .nclr compartilhado")
    p_port_merge.add_argument("out_png", help="Destino da imagem PNG 128x128")
    p_port_merge.set_defaults(func=cmd_portrait_merge)

    # 5. model-inspect
    p_mod_insp = sub.add_parser("model-inspect", help="Inspeciona e valida limites de modelos 3D NSBMD/NSBTX")
    p_mod_insp.add_argument("model_file", help="Caminho do arquivo .nsbmd ou .nsbtx")
    p_mod_insp.add_argument("--json", action="store_true", help="Saída em JSON estruturado")
    p_mod_insp.set_defaults(func=cmd_model_inspect)

    # 6. obj-to-imd
    p_obj_imd = sub.add_parser("obj-to-imd", help="Converte Wavefront OBJ para formato intermediário Nitro IMD")
    p_obj_imd.add_argument("obj_file", help="Caminho do arquivo .obj")
    p_obj_imd.add_argument("out_imd", help="Destino do arquivo .imd")
    p_obj_imd.add_argument("--texture-name", help="Nome da textura vinculada")
    p_obj_imd.add_argument("--palette-name", help="Nome da paleta vinculada")
    p_obj_imd.add_argument("--scale", type=float, default=1.0, help="Escala dos vértices")
    p_obj_imd.set_defaults(func=cmd_obj_to_imd)

    # 7. item-new
    p_item_new = sub.add_parser("item-new", help="Cria um novo item ponta a ponta no projeto")
    p_item_new.add_argument("--project-dir", default=".", help="Diretório raiz do projeto sonic-mod")
    p_item_new.add_argument("--name", required=True, help="Nome do item no jogo")
    p_item_new.add_argument("--desc", required=True, help="Descrição do item")
    p_item_new.add_argument("--id", type=int, help="ID customizado do item")
    p_item_new.add_argument("--cost", type=int, default=100, help="Preço de compra")
    p_item_new.add_argument("--heal-hp", type=int, default=0, help="Quantidade de HP restaurada")
    p_item_new.add_argument("--heal-pp", type=int, default=0, help="Quantidade de PP restaurada")
    p_item_new.add_argument("--boost-power", type=int, default=0, help="Modificador de Power")
    p_item_new.add_argument("--boost-defense", type=int, default=0, help="Modificador de Defense")
    p_item_new.add_argument("--icon-png", help="PNG (32x32) com o ícone do item")
    p_item_new.add_argument("--store", help="Nome da tabela da loja para adicionar (ex: Store1)")
    p_item_new.set_defaults(func=cmd_item_new)

    # 8. pow-new
    p_pow_new = sub.add_parser("pow-new", help="Cria um novo golpe POW ponta a ponta no projeto")
    p_pow_new.add_argument("--project-dir", default=".", help="Diretório raiz do projeto sonic-mod")
    p_pow_new.add_argument("--name", required=True, help="Nome do golpe POW")
    p_pow_new.add_argument("--desc", required=True, help="Descrição do golpe")
    p_pow_new.add_argument("--owner", type=int, default=0, help="ID da criatura dona (0 Sonic, 1 Knuckles, 2 Tails, etc.)")
    p_pow_new.add_argument("--id", type=int, help="ID customizado do combo")
    p_pow_new.add_argument("--partners", help="IDs dos parceiros separados por vírgula (para combo em equipe)")
    p_pow_new.add_argument("--cost", type=int, default=4, help="Custo em PP")
    p_pow_new.add_argument("--dmg1", type=int, default=120, help="Dano nível 1 (%)")
    p_pow_new.add_argument("--dmg2", type=int, default=160, help="Dano nível 2 (%)")
    p_pow_new.add_argument("--dmg3", type=int, default=210, help="Dano nível 3 (%)")
    p_pow_new.add_argument("--armor-pierce", action="store_true", help="Perfura armadura (ignora Grit do inimigo)")
    p_pow_new.add_argument("--all-enemies", action="store_true", help="Ataca todos os inimigos")
    p_pow_new.add_argument("--icon-png", help="PNG (24x24 ou 32x32) com o badge do POW")
    p_pow_new.set_defaults(func=cmd_pow_new)

    # 9. vfx
    p_vfx = sub.add_parser("vfx", help="Gerencia presets e definições de VFX/partículas")
    p_vfx.add_argument("--list", action="store_true", help="Lista presets disponíveis")
    p_vfx.add_argument("--export-preset", help="Exporta preset para JSON e binário .emit")
    p_vfx.add_argument("--name", help="Nome customizado para o emissor exportado")
    p_vfx.set_defaults(func=cmd_vfx)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
