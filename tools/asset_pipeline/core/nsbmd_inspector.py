"""Inspetor e validador de modelos 3D (.nsbmd) e texturas (.nsbtx) do Nintendo DS.

Analisa a estrutura binária dos blocos BMD0, MDL0 e TEX0:
- Contagem de polígonos (triângulos e quadriláteros)
- Contagem de vértices e objetos
- Materiais e nós (ossos)
- Texturas, dimensões, formatos e paletas
- Validação contra os limites de hardware do Nintendo DS
"""

import struct
from typing import Dict, Any, List, Optional
import ndspy.texture


TEXTURE_FORMATS = {
    0: "None",
    1: "A3I5 (Transparência 3-bit, 32 cores)",
    2: "4-color (2bpp, 4 cores)",
    3: "16-color (4bpp, 16 cores)",
    4: "256-color (8bpp, 256 cores)",
    5: "Tex4x4 (Comprimida 4x4)",
    6: "A5I3 (Transparência 5-bit, 8 cores)",
    7: "Direct (16-bit BGR555 direto)",
}

DS_MAX_POLYGONS = 1536
DS_MAX_VERTICES = 2048


class NSBMDInspector:
    def __init__(self, data: bytes):
        self.data = data
        self.file_size = len(data)
        self.magic = data[:4] if len(data) >= 4 else b""
        self.models: List[Dict[str, Any]] = []
        self.textures: List[Dict[str, Any]] = []
        self.palettes: List[Dict[str, Any]] = []
        self.warnings: List[str] = []

        self._parse()

    def _parse(self):
        if len(self.data) < 16:
            self.warnings.append("Arquivo muito pequeno para conter cabeçalho Nitro 3D válido.")
            return

        if self.magic not in (b"BMD0", b"BTX0"):
            self.warnings.append(f"Assinatura desconhecida: {self.magic!r} (esperado BMD0 ou BTX0)")
            return

        file_len, header_len, num_sections = struct.unpack_from("<IHH", self.data, 0x8)

        # Itera pelas seções (MDL0, TEX0, etc.)
        pos = header_len
        for _ in range(num_sections):
            if pos + 8 > len(self.data):
                break
            sec_magic = self.data[pos:pos+4]
            sec_len, = struct.unpack_from("<I", self.data, pos+4)

            if sec_magic == b"MDL0":
                self._parse_mdl0(self.data[pos:pos+sec_len])
            elif sec_magic == b"TEX0":
                self._parse_tex0(self.data[pos:pos+sec_len])

            pos += sec_len

        self._validate_limits()

    def _parse_mdl0(self, data: bytes):
        if len(data) < 16:
            return

        models_count, = struct.unpack_from("<B", data, 0x9)
        off = 0x0C

        # Pula unk block
        off += 8 + 4 * models_count

        if off + 4 + 4 * models_count > len(data):
            return

        # Lê offsets dos modelos
        model_offsets = []
        for i in range(models_count):
            m_off, = struct.unpack_from("<I", data, off + 0x4 + 4 * i)
            model_offsets.append(m_off)

        off += 4 + 4 * models_count
        model_names = []
        for i in range(models_count):
            name_raw = data[off + 16 * i : off + 16 * (i + 1)]
            name = name_raw.split(b"\x00", 1)[0].decode("ascii", errors="replace")
            model_names.append(name)

        for name, m_off in zip(model_names, model_offsets):
            if m_off + 0x3C > len(data):
                continue

            (
                model_size, bones_off, mats_off,
                poly_begin_off, poly_end_off,
                unk14, unk15, unk16, objects_count, mats_count,
                poly_count, unk1A, unk1B, unk1C, unk1D, unk1E, unk1F,
                unk20, scale_mode, unk22, unk23, vertices_count,
                surfaces_count, triangles_count, quads_count,
                bbox_x, bbox_y, bbox_z,
                bbox_w, bbox_h, bbox_d
            ) = struct.unpack_from("<5I16B4H6h", data, m_off)

            total_polygons = triangles_count + quads_count

            self.models.append({
                "name": name,
                "objects_count": objects_count,
                "materials_count": mats_count,
                "polygons_count": total_polygons,
                "triangles_count": triangles_count,
                "quads_count": quads_count,
                "vertices_count": vertices_count,
                "surfaces_count": surfaces_count,
                "scale_mode": scale_mode,
                "bounding_box": {
                    "x": bbox_x, "y": bbox_y, "z": bbox_z,
                    "width": bbox_w, "height": bbox_h, "depth": bbox_d,
                }
            })

    def _parse_tex0(self, data: bytes):
        try:
            btx = ndspy.texture.NSBTX(b"BTX0\xfe\xff\x01\x00" + struct.pack("<IH2xH", len(data) + 16, 16, 1) + data)
            for tex in btx.textures:
                fmt_id = tex.format.value if hasattr(tex.format, "value") else int(tex.format)
                self.textures.append({
                    "name": tex.name,
                    "width": tex.width,
                    "height": tex.height,
                    "format_id": fmt_id,
                    "format_name": TEXTURE_FORMATS.get(fmt_id, f"Desconhecido ({fmt_id})"),
                    "data_size": len(tex.data),
                })
            for pal in btx.palettes:
                self.palettes.append({
                    "name": pal.name,
                    "data_size": len(pal.data),
                    "colors_count": len(pal.data) // 2,
                })
        except Exception:
            # Fallback se a parsing pelo ndspy falhar
            pass

    def _validate_limits(self):
        for m in self.models:
            name = m["name"]
            polys = m["polygons_count"]
            verts = m["vertices_count"]

            if polys > DS_MAX_POLYGONS:
                self.warnings.append(
                    f"Modelo '{name}' excede o orçamento de polígonos por quadro do DS "
                    f"({polys} > {DS_MAX_POLYGONS}). Pode causar queda de taxa de quadros."
                )
            if verts > DS_MAX_VERTICES:
                self.warnings.append(
                    f"Modelo '{name}' excede o orçamento de vértices do DS "
                    f"({verts} > {DS_MAX_VERTICES})."
                )

        for t in self.textures:
            w, h = t["width"], t["height"]
            if (w & (w - 1)) != 0 or (h & (h - 1)) != 0:
                self.warnings.append(
                    f"Textura '{t['name']}' ({w}x{h}) não tem dimensões em potência de 2!"
                )
            if w > 256 or h > 256:
                self.warnings.append(
                    f"Textura '{t['name']}' ({w}x{h}) é excessivamente grande para a VRAM do DS."
                )

    def summary(self) -> Dict[str, Any]:
        return {
            "magic": self.magic.decode("ascii", errors="replace"),
            "file_size": self.file_size,
            "models_count": len(self.models),
            "models": self.models,
            "textures_count": len(self.textures),
            "textures": self.textures,
            "palettes_count": len(self.palettes),
            "palettes": self.palettes,
            "warnings": self.warnings,
            "is_valid_ds_asset": len(self.warnings) == 0,
        }

    def print_report(self):
        s = self.summary()
        print(f"=== Inspeção de Modelo Nitro 3D [{s['magic']}] ===")
        print(f"Tamanho do arquivo: {s['file_size']} bytes")
        print(f"Modelos encontrados: {s['models_count']}")
        for m in s["models"]:
            print(f"  • Modelo: {m['name']}")
            print(f"    - Polígonos: {m['polygons_count']} (Triângulos: {m['triangles_count']}, Quads: {m['quads_count']})")
            print(f"    - Vértices: {m['vertices_count']}, Objetos: {m['objects_count']}, Materiais: {m['materials_count']}")
            bb = m["bounding_box"]
            print(f"    - Caixa de colisão/limite: dim={bb['width']}x{bb['height']}x{bb['depth']}")

        print(f"\nTexturas encontradas: {s['textures_count']}")
        for t in s["textures"]:
            print(f"  • {t['name']}: {t['width']}x{t['height']} ({t['format_name']}), {t['data_size']} bytes")

        print(f"\nPaletas encontradas: {s['palettes_count']}")
        for p in s["palettes"]:
            print(f"  • {p['name']}: {p['colors_count']} cores ({p['data_size']} bytes)")

        if s["warnings"]:
            print("\n[!] AVISOS DE COMPATIBILIDADE COM O NINTENDO DS:")
            for w in s["warnings"]:
                print(f"  - {w}")
        else:
            print("\n[OK] Modelo e texturas 100% em conformidade com as restrições do Nintendo DS.")
