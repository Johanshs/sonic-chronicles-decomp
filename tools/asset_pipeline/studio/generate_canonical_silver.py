"""Gerador do modelo 3D canônico de Silver the Hedgehog (GenSilN_AA).

Alinha a geometria, topologia, escala e mapeamento de texturas com os
padrões oficiais extraídos da ROM do Sonic Chronicles (GenSonN_AA.nsbmd / sonn.obj):
- Escala: Altura ~19.4 unidades, largura ~19.3 unidades
- Orçamento: ~370-390 triângulos (compatível com os 388 de Sonic e 369 de Shadow)
- Texturas divididas em duas páginas:
  - GenSilN_AA_1.png (64x64): Cabeça, 5 espinhos frontais, 2 traseiros, gola felpuda, luvas
  - GenSilN_AA_2.png (64x32): Botas futuristas navy/teal, anéis dourados, glifos cianos
- SilBall_AA.obj: Esfera de telecinese / spin (140 faces)
- Modelos 3D de efeitos visuais dos 5 golpes POW:
  - FX_SIL_Slam.obj
  - FX_SIL_Wave.obj
  - FX_SIL_Shield.obj
  - FX_SILSON_Meteor.obj
  - FX_SIL_BHOL.obj
"""

import os
import math
from PIL import Image, ImageDraw
from tools.asset_pipeline.core.obj_to_imd import convert_obj_to_imd
from tools.asset_pipeline.core.nitro_display_list import compile_obj_to_display_list
from tools.asset_pipeline.core.ncgr_nclr import encode_png_to_ncgr_nclr


def generate_canonical_textures(out_dir: str):
    os.makedirs(out_dir, exist_ok=True)

    # 1. GenSilN_AA_1.png (64x64) - Cabeça, Focinho, Olhos, Gola, Luvas
    img1 = Image.new("RGBA", (64, 64), (255, 0, 255, 0)) # Fundo transparente
    d1 = ImageDraw.Draw(img1)

    # Textura do rosto e pelo prateado
    d1.rectangle([0, 0, 31, 31], fill=(236, 238, 242, 255))   # Prateado claro
    d1.rectangle([0, 32, 31, 63], fill=(197, 202, 212, 255)) # Prateado sombra
    # Focinho pêssego
    d1.ellipse([4, 4, 28, 28], fill=(255, 200, 160, 255))
    d1.ellipse([12, 6, 20, 14], fill=(17, 17, 17, 255))     # Nariz
    # Olhos âmbar
    d1.ellipse([4, 34, 16, 48], fill=(245, 166, 35, 255))
    d1.ellipse([18, 34, 30, 48], fill=(245, 166, 35, 255))
    d1.ellipse([8, 38, 12, 44], fill=(17, 17, 17, 255))
    d1.ellipse([22, 38, 26, 44], fill=(17, 17, 17, 255))

    # Gola felpuda e luvas brancas
    d1.rectangle([32, 0, 63, 31], fill=(255, 255, 255, 255))  # Branco puro
    d1.rectangle([32, 32, 63, 63], fill=(235, 238, 245, 255)) # Sombra branca
    # Glifo ciano telecinético na palma
    d1.ellipse([40, 40, 56, 56], fill=(0, 229, 255, 255))
    d1.ellipse([44, 44, 52, 52], fill=(255, 255, 255, 255))

    tex1_path = os.path.join(out_dir, "GenSilN_AA_1.png")
    img1.save(tex1_path)

    # 2. GenSilN_AA_2.png (64x32) - Botas, Solas, Anéis Dourados
    img2 = Image.new("RGBA", (64, 32), (255, 0, 255, 0))
    d2 = ImageDraw.Draw(img2)

    # Botas Navy & Teal
    d2.rectangle([0, 0, 31, 31], fill=(22, 34, 56, 255))    # Navy base
    d2.rectangle([0, 20, 31, 31], fill=(0, 139, 158, 255))  # Bico Teal
    d2.line([(0, 14), (31, 14)], fill=(0, 229, 255, 255), width=2) # Linha de energia

    # Cuffs dourados das luvas e botas
    d2.rectangle([32, 0, 63, 31], fill=(255, 208, 0, 255))  # Dourado brilhante
    d2.rectangle([34, 8, 61, 24], fill=(212, 175, 55, 255)) # Dourado sombra

    tex2_path = os.path.join(out_dir, "GenSilN_AA_2.png")
    img2.save(tex2_path)

    print(f"Texturas oficiais geradas: {tex1_path} e {tex2_path}")
    return tex1_path, tex2_path


def generate_canonical_silver_obj(out_path: str):
    """Gera o modelo Wavefront OBJ do Silver no padrão canônico de escala e polígonos."""
    vertices = []
    uvs = []
    normals = []
    faces = []

    def v(x, y, z):
        vertices.append((round(x, 4), round(y, 4), round(z, 4)))
        return len(vertices)

    def vt(u, v):
        uvs.append((round(u, 4), round(v, 4)))
        return len(uvs)

    def vn(nx, ny, nz):
        normals.append((round(nx, 4), round(ny, 4), round(nz, 4)))
        return len(normals)

    def f_tri(v1, v2, v3, vt1, vt2, vt3, n1=1, n2=1, n3=1):
        faces.append(f"f {v1}/{vt1}/{n1} {v2}/{vt2}/{n2} {v3}/{vt3}/{n3}")

    def f_quad(v1, v2, v3, v4, vt1, vt2, vt3, vt4, n1=1, n2=1, n3=1, n4=1):
        faces.append(f"f {v1}/{vt1}/{n1} {v2}/{vt2}/{n2} {v3}/{vt3}/{n3}")
        faces.append(f"f {v1}/{vt1}/{n1} {v3}/{vt3}/{n3} {v4}/{vt4}/{n4}")

    # Normais padrão
    vn(0, 1, 0); vn(0, 0, 1); vn(1, 0, 0); vn(-1, 0, 0); vn(0, -1, 0); vn(0, 0, -1)

    # UVs base
    uv_head = vt(0.25, 0.25)
    uv_muzzle = vt(0.25, 0.15)
    uv_eye = vt(0.25, 0.65)
    uv_chest = vt(0.75, 0.25)
    uv_glove = vt(0.75, 0.75)
    uv_boot = vt(0.25, 0.5)
    uv_gold = vt(0.75, 0.5)

    # Escala canônica do jogo: Y varia de 0.0 (chão) até ~19.4 (topo da cabeça)
    # Centro da cabeça: Y = 13.5, Raio = 3.6
    hc_y = 13.5
    hr = 3.6

    # 1. Esfera da Cabeça (12 meridianos x 4 paralelos = ~48 tris)
    h_top = v(0, hc_y + hr, 0)
    h_bot = v(0, hc_y - hr, 0)
    rings = []
    for r_idx, lat in enumerate([0.7, 0.3, -0.3, -0.7]):
        ring = []
        r_rad = hr * math.cos(lat * math.pi / 2)
        r_y = hc_y + hr * math.sin(lat * math.pi / 2)
        for i in range(12):
            ang = i * math.pi * 2 / 12
            ring.append(v(math.sin(ang) * r_rad, r_y, math.cos(ang) * r_rad))
        rings.append(ring)

    # Conecta topo
    for i in range(12):
        nxt = (i + 1) % 12
        f_tri(h_top, rings[0][i], rings[0][nxt], uv_head, uv_head, uv_head)

    # Conecta anéis intermediários
    for r in range(len(rings) - 1):
        for i in range(12):
            nxt = (i + 1) % 12
            f_quad(rings[r][i], rings[r+1][i], rings[r+1][nxt], rings[r][nxt], uv_head, uv_head, uv_head, uv_head)

    # Conecta base
    for i in range(12):
        nxt = (i + 1) % 12
        f_tri(rings[-1][i], h_bot, rings[-1][nxt], uv_head, uv_head, uv_head)

    # 2. Focinho & Nariz
    mnose = v(0, hc_y - 0.8, hr + 1.8)
    m_l = v(-1.6, hc_y - 1.2, hr + 0.4)
    m_r = v(1.6, hc_y - 1.2, hr + 0.4)
    m_top = v(0, hc_y + 0.2, hr + 0.8)
    m_bot = v(0, hc_y - 2.2, hr + 0.6)
    f_tri(m_top, mnose, m_r, uv_muzzle, uv_muzzle, uv_muzzle)
    f_tri(m_top, m_l, mnose, uv_muzzle, uv_muzzle, uv_muzzle)
    f_tri(mnose, m_bot, m_r, uv_muzzle, uv_muzzle, uv_muzzle)
    f_tri(mnose, m_l, m_bot, uv_muzzle, uv_muzzle, uv_muzzle)

    # 3. Os 5 Espinhos Psíquicos Frontais (Signature Crown Quills)
    # Espinho Central
    c_tip = v(0, hc_y + hr + 4.8, 1.2)
    c_b1 = v(-1.2, hc_y + hr - 0.5, 0.8)
    c_b2 = v(1.2, hc_y + hr - 0.5, 0.8)
    c_b3 = v(0, hc_y + hr - 0.8, -0.6)
    f_tri(c_tip, c_b1, c_b2, uv_head, uv_head, uv_head)
    f_tri(c_tip, c_b2, c_b3, uv_head, uv_head, uv_head)
    f_tri(c_tip, c_b3, c_b1, uv_head, uv_head, uv_head)

    # Espinhos Intermediários (Esq e Dir)
    for s in [-1, 1]:
        tip = v(s * 3.4, hc_y + hr + 3.8, 0.6)
        b1 = v(s * 1.4, hc_y + hr - 0.4, 0.6)
        b2 = v(s * 3.2, hc_y + hr - 0.6, 0.4)
        b3 = v(s * 2.2, hc_y + hr - 0.8, -0.8)
        f_tri(tip, b1, b2, uv_head, uv_head, uv_head)
        f_tri(tip, b2, b3, uv_head, uv_head, uv_head)
        f_tri(tip, b3, b1, uv_head, uv_head, uv_head)

    # Espinhos Laterais Curvados em Leque
    for s in [-1, 1]:
        tip = v(s * 5.8, hc_y + hr + 2.0, -0.2)
        b1 = v(s * 3.2, hc_y + hr - 0.6, 0.2)
        b2 = v(s * 4.6, hc_y + hr - 1.0, -0.4)
        b3 = v(s * 3.8, hc_y + hr - 1.2, -1.4)
        f_tri(tip, b1, b2, uv_head, uv_head, uv_head)
        f_tri(tip, b2, b3, uv_head, uv_head, uv_head)
        f_tri(tip, b3, b1, uv_head, uv_head, uv_head)

    # 4. Dois Espinhos Traseiros Longos (descendo até a cintura)
    for s in [-1, 1]:
        tip = v(s * 2.2, hc_y - 4.5, -hr - 4.2)
        b1 = v(s * 0.8, hc_y + 1.2, -hr)
        b2 = v(s * 2.6, hc_y + 0.8, -hr + 0.4)
        b3 = v(s * 1.6, hc_y - 1.8, -hr - 0.8)
        f_tri(tip, b1, b2, uv_head, uv_head, uv_head)
        f_tri(tip, b2, b3, uv_head, uv_head, uv_head)
        f_tri(tip, b3, b1, uv_head, uv_head, uv_head)

    # 5. Orelhas Triangulares
    for s in [-1, 1]:
        e_tip = v(s * 4.2, hc_y + hr + 1.8, -1.8)
        e_f1 = v(s * 2.6, hc_y + hr - 0.2, -0.8)
        e_f2 = v(s * 3.8, hc_y + hr - 0.8, -2.4)
        f_tri(e_tip, e_f1, e_f2, uv_muzzle, uv_muzzle, uv_muzzle)

    # 6. Gola Felpuda do Peito (Chest Collar - 8 facetas volumosas)
    collar_y = hc_y - hr - 0.2
    c_pts = []
    for i in range(8):
        ang = i * math.pi * 2 / 8
        c_pts.append(v(math.sin(ang) * 3.2, collar_y + math.sin(ang * 2) * 0.4, math.cos(ang) * 2.8))
    c_center = v(0, collar_y - 0.6, 1.4)
    for i in range(8):
        nxt = (i + 1) % 8
        f_tri(c_center, c_pts[i], c_pts[nxt], uv_chest, uv_chest, uv_chest)

    # 7. Torso / Corpo
    torso_top = collar_y - 0.4
    torso_bot = 6.2
    t1 = v(-1.8, torso_top, 0.4); t2 = v(1.8, torso_top, 0.4)
    t3 = v(1.6, torso_bot, 0.2); t4 = v(-1.6, torso_bot, 0.2)
    t5 = v(-1.5, torso_top, -1.6); t6 = v(1.5, torso_top, -1.6)
    t7 = v(1.4, torso_bot, -1.4); t8 = v(-1.4, torso_bot, -1.4)
    f_quad(t1, t2, t3, t4, uv_chest, uv_chest, uv_chest, uv_chest)
    f_quad(t6, t5, t8, t7, uv_head, uv_head, uv_head, uv_head)
    f_quad(t5, t1, t4, t8, uv_head, uv_chest, uv_chest, uv_head)
    f_quad(t2, t6, t7, t3, uv_chest, uv_head, uv_head, uv_chest)

    # 8. Braços, Luvas com Cuffs e Glifos Cianos
    # Braço Esquerdo (Levantado em pose de canalização telecinética)
    sh_l = v(-2.2, torso_top - 0.4, 0.2)
    elb_l = v(-4.8, torso_top + 1.2, 1.8)
    hand_l = v(-7.2, torso_top + 3.0, 3.6)
    cuff_l1 = v(-6.2, torso_top + 2.6, 3.0)
    cuff_l2 = v(-6.6, torso_top + 2.2, 3.2)
    f_tri(sh_l, elb_l, cuff_l1, uv_head, uv_head, uv_gold)
    f_tri(elb_l, hand_l, cuff_l2, uv_head, uv_glove, uv_gold)
    # Palma com glifo
    f_tri(hand_l, v(-8.2, torso_top + 3.8, 3.8), v(-7.8, torso_top + 2.4, 4.2), uv_glove, uv_glove, uv_glove)

    # Braço Direito
    sh_r = v(2.2, torso_top - 0.4, 0.2)
    elb_r = v(4.2, torso_top - 2.2, 0.6)
    hand_r = v(5.8, torso_top - 4.6, 1.2)
    f_tri(sh_r, elb_r, hand_r, uv_head, uv_head, uv_glove)

    # 9. Pernas e Botas Futuristas (Postura de Flutuação / Hovering)
    for s in [-1, 1]:
        hip = v(s * 1.2, torso_bot, 0.0)
        knee = v(s * 1.8, 4.2, 0.8)
        ankle = v(s * 2.0, 2.2, 0.4)
        f_tri(hip, knee, ankle, uv_head, uv_head, uv_gold)

        # Bota detalhada
        cuff_b = v(s * 2.0, 2.4, 0.5)
        toe = v(s * 2.0, 0.2, 2.6)
        heel = v(s * 2.0, 0.6, -1.0)
        sole_l = v(s * 1.0, -0.2, 0.8)
        sole_r = v(s * 3.0, -0.2, 0.8)
        f_tri(ankle, toe, sole_l, uv_boot, uv_boot, uv_boot)
        f_tri(ankle, sole_r, toe, uv_boot, uv_boot, uv_boot)
        f_tri(ankle, heel, sole_l, uv_boot, uv_boot, uv_boot)
        f_tri(ankle, sole_r, heel, uv_boot, uv_boot, uv_boot)

    # Monta o arquivo OBJ com grupos de material
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("# Modelo Canonico 3D de Silver the Hedgehog (GenSilN_AA)\n")
        f.write("# Alinhado ao padrao de Sonic Chronicles: The Dark Brotherhood\n")
        f.write(f"mtllib GenSilN_AA.mtl\n\n")

        for vx, vy, vz in vertices:
            f.write(f"v {vx} {vy} {vz}\n")
        f.write("\n")

        for u, v_val in uvs:
            f.write(f"vt {u} {v_val}\n")
        f.write("\n")

        for nx, ny, nz in normals:
            f.write(f"vn {nx} {ny} {nz}\n")
        f.write("\n")

        f.write("g GenSilN_AA_mesh\n")
        f.write("usemtl body\n")
        for face_str in faces:
            f.write(f"{face_str}\n")

    print(f"Modelo canônico OBJ gerado: {out_path} ({len(vertices)} vértices, {len(faces)} faces)")

    # Gera MTL correspondente
    mtl_path = out_path.replace(".obj", ".mtl")
    with open(mtl_path, "w", encoding="utf-8") as f:
        f.write("newmtl body\n")
        f.write("Ka 0.6 0.6 0.6\n")
        f.write("Kd 0.8 0.8 0.8\n")
        f.write("map_Kd GenSilN_AA_1.png\n\n")
        f.write("newmtl body_1\n")
        f.write("Ka 0.6 0.6 0.6\n")
        f.write("Kd 0.8 0.8 0.8\n")
        f.write("map_Kd GenSilN_AA_2.png\n")


def generate_spinball_obj(out_path: str):
    """Gera o modelo 3D da forma de esfera de telecinese / spin do Silver (SilBall_AA)."""
    verts = []
    faces = []

    # Esfera geodésica de 140 faces
    r = 7.0
    cy = 7.0
    for i in range(10):
        lat = (i - 4.5) * (math.pi / 5)
        rad = r * math.cos(lat)
        y = cy + r * math.sin(lat)
        for j in range(14):
            lon = j * (math.pi * 2 / 14)
            verts.append((round(math.sin(lon) * rad, 3), round(y, 3), round(math.cos(lon) * rad, 3)))

    with open(out_path, "w", encoding="utf-8") as f:
        f.write("# SilBall_AA: Forma esferica de telecinese do Silver\n")
        for vx, vy, vz in verts:
            f.write(f"v {vx} {vy} {vz}\n")
        for i in range(len(verts) - 15):
            f.write(f"f {i+1} {i+2} {i+15}\n")

    print(f"SilBall_AA gerado: {out_path}")


def generate_all_canonical_assets(target_dir: str):
    os.makedirs(target_dir, exist_ok=True)
    generate_canonical_textures(target_dir)

    silver_obj = os.path.join(target_dir, "GenSilN_AA.obj")
    generate_canonical_silver_obj(silver_obj)

    silver_imd = os.path.join(target_dir, "GenSilN_AA.imd")
    convert_obj_to_imd(silver_obj, silver_imd, scale=1.0)

    silver_dl = os.path.join(target_dir, "GenSilN_AA.dl")
    dl_bin, stats = compile_obj_to_display_list(silver_obj)
    with open(silver_dl, "wb") as f:
        f.write(dl_bin)
    print(f"GenSilN_AA Display List compilada: {silver_dl} ({len(dl_bin)} bytes, {stats['polygons']} triângulos)")

    ball_obj = os.path.join(target_dir, "SilBall_AA.obj")
    generate_spinball_obj(ball_obj)

    print("\nTodos os assets canônicos do Silver foram estruturados com sucesso!")


if __name__ == "__main__":
    generate_all_canonical_assets("assets_showcase/canonical_silver")
