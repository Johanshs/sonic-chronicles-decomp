"""Conversor de modelos 3D Wavefront .OBJ para formato intermediário Nitro (.imd - Intermediate Model Data).

O formato .imd é a especificação XML padronizada do Nintendo DS para compilação
em binários de geometria .nsbmd via g3dcvtr ou emuladores de pipeline.
"""

import os
from typing import List, Tuple, Dict, Optional
import xml.etree.ElementTree as ET
from xml.dom import minidom


class ObjMesh:
    def __init__(self):
        self.vertices: List[Tuple[float, float, float]] = []
        self.texcoords: List[Tuple[float, float]] = []
        self.normals: List[Tuple[float, float, float]] = []
        # faces: lista de tuplas de vértices [(v_idx, vt_idx, vn_idx), ...]
        self.faces: List[List[Tuple[int, int, int]]] = []
        self.material_name: str = "default_mat"


def parse_obj(obj_content: str) -> ObjMesh:
    """Faz o parsing simples de um arquivo Wavefront OBJ."""
    mesh = ObjMesh()

    for line in obj_content.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue

        parts = line.split()
        prefix = parts[0]

        if prefix == "v":
            mesh.vertices.append((float(parts[1]), float(parts[2]), float(parts[3])))
        elif prefix == "vt":
            mesh.texcoords.append((float(parts[1]), float(parts[2])))
        elif prefix == "vn":
            mesh.normals.append((float(parts[1]), float(parts[2]), float(parts[3])))
        elif prefix == "usemtl":
            mesh.material_name = parts[1]
        elif prefix == "f":
            face = []
            for token in parts[1:]:
                sub = token.split("/")
                v_idx = int(sub[0]) - 1
                vt_idx = int(sub[1]) - 1 if len(sub) > 1 and sub[1] else -1
                vn_idx = int(sub[2]) - 1 if len(sub) > 2 and sub[2] else -1
                face.append((v_idx, vt_idx, vn_idx))
            mesh.faces.append(face)

    return mesh


def convert_obj_to_imd(
    obj_path: str,
    out_imd_path: str,
    texture_name: Optional[str] = None,
    palette_name: Optional[str] = None,
    scale: float = 1.0
) -> str:
    """Converte um arquivo Wavefront OBJ para o formato intermediário Nitro IMD.

    Args:
        obj_path: Caminho do arquivo .obj de entrada.
        out_imd_path: Caminho de saída para o .imd XML gerado.
        texture_name: Nome do arquivo de textura associado (ex: 'sonic_tex').
        palette_name: Nome da paleta associada (ex: 'sonic_pal').
        scale: Fator de escala das coordenadas.
    """
    with open(obj_path, "r", encoding="utf-8", errors="replace") as f:
        obj_content = f.read()

    mesh = parse_obj(obj_content)
    base_name = os.path.splitext(os.path.basename(obj_path))[0]
    tex_name = texture_name or f"{base_name}_tex"
    pal_name = palette_name or f"{base_name}_pal"

    # Cria árvore XML do IMD
    root = ET.Element("imd", version="1.6.0")

    # Cabeçalho
    head = ET.SubElement(root, "head")
    create = ET.SubElement(head, "create", user="ChroniclesStudio", host="DS-Asset-Pipeline", date="2026-10-08")
    title = ET.SubElement(head, "title")
    title.text = f"Nitro 3D Model: {base_name}"

    body = ET.SubElement(root, "body")
    original_member = ET.SubElement(body, "original_member")

    model_info = ET.SubElement(
        body,
        "model_info",
        pos_scale="0",
        scaling_rule="standard",
        vertex_style="direct",
    )

    # Nós / Ossos (Nodes)
    node_array = ET.SubElement(body, "node_array", size="1")
    node = ET.SubElement(
        node_array,
        "node",
        index="0",
        name=f"root_{base_name}",
        kind="mesh",
        parent="-1",
        child="-1",
        brother_next="-1",
        brother_prev="-1",
        draw_mtx="load",
        billboard="off",
        scale="1.000000 1.000000 1.000000",
        rotate="0.000000 0.000000 0.000000",
        translate="0.000000 0.000000 0.000000",
    )

    # Materiais (Materials)
    mat_array = ET.SubElement(body, "material_array", size="1")
    mat = ET.SubElement(
        mat_array,
        "material",
        index="0",
        name=mesh.material_name,
        light="0 0 0 0",
        diffuse="31 31 31",
        ambient="16 16 16",
        specular="0 0 0",
        emission="0 0 0",
        polygon_mode="modulate",
        cull_mode="back",
        polygon_id="0",
        alpha="31",
        wireframe="off",
        depth_test="on",
        tex_image_name=tex_name,
        palette_name=pal_name,
    )

    # Malha e Primitivas (Polygon Array)
    poly_array = ET.SubElement(body, "polygon_array", size="1")
    poly = ET.SubElement(
        poly_array,
        "polygon",
        index="0",
        name=f"{base_name}_poly",
        primitive_type="triangles",
        vertex_size=str(len(mesh.faces) * 3),
    )

    # Monta lista de vértices da malha
    pos_data = []
    tex_data = []
    nrm_data = []

    for face in mesh.faces:
        # Triangula faces com mais de 3 vértices
        triangles = []
        if len(face) == 3:
            triangles.append(face)
        elif len(face) == 4:
            # Divide quad em dois triângulos
            triangles.append([face[0], face[1], face[2]])
            triangles.append([face[0], face[2], face[3]])
        else:
            # Fan triangulation
            for i in range(1, len(face) - 1):
                triangles.append([face[0], face[i], face[i+1]])

        for tri in triangles:
            for v_idx, vt_idx, vn_idx in tri:
                vx, vy, vz = mesh.vertices[v_idx]
                pos_data.append(f"{vx * scale:.4f} {vy * scale:.4f} {vz * scale:.4f}")

                if vt_idx >= 0 and vt_idx < len(mesh.texcoords):
                    tx, ty = mesh.texcoords[vt_idx]
                    tex_data.append(f"{tx:.4f} {1.0 - ty:.4f}")
                else:
                    tex_data.append("0.0000 0.0000")

                if vn_idx >= 0 and vn_idx < len(mesh.normals):
                    nx, ny, nz = mesh.normals[vn_idx]
                    nrm_data.append(f"{nx:.4f} {ny:.4f} {nz:.4f}")
                else:
                    nrm_data.append("0.0000 1.0000 0.0000")

    pos_elem = ET.SubElement(poly, "mtx_list")
    vtx_elem = ET.SubElement(poly, "vertex_list")
    vtx_elem.text = "\n" + "\n".join(pos_data) + "\n"

    tex_elem = ET.SubElement(poly, "texcoord_list")
    tex_elem.text = "\n" + "\n".join(tex_data) + "\n"

    nrm_elem = ET.SubElement(poly, "normal_list")
    nrm_elem.text = "\n" + "\n".join(nrm_data) + "\n"

    # Formatação com indentação legível
    rough_string = ET.tostring(root, "utf-8")
    reparsed = minidom.parseString(rough_string)
    pretty_xml = reparsed.toprettyxml(indent="  ", encoding="utf-8")

    os.makedirs(os.path.dirname(os.path.abspath(out_imd_path)), exist_ok=True)
    with open(out_imd_path, "wb") as f:
        f.write(pretty_xml)

    return out_imd_path
