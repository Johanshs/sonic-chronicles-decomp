import unittest
import os
import tempfile
import struct
import xml.etree.ElementTree as ET

from ..core.obj_to_imd import convert_obj_to_imd
from ..core.nsbmd_inspector import NSBMDInspector, DS_MAX_POLYGONS


class TestModelPipeline(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_obj_to_imd_conversion(self):
        # Cria um modelo OBJ simples de um prisma triangular (6 vértices, 8 faces)
        obj_content = """# Sonic Chronicles Low-Poly Test Prop
v -1.0 -1.0 0.0
v 1.0 -1.0 0.0
v 0.0 1.0 0.0
v -1.0 -1.0 2.0
v 1.0 -1.0 2.0
v 0.0 1.0 2.0
vt 0.0 0.0
vt 1.0 0.0
vt 0.5 1.0
vn 0.0 0.0 1.0
f 1/1/1 2/2/1 3/3/1
f 4/1/1 5/2/1 6/3/1
f 1/1/1 2/2/1 5/2/1 4/1/1
"""
        obj_path = os.path.join(self.temp_dir.name, "prop.obj")
        with open(obj_path, "w", encoding="utf-8") as f:
            f.write(obj_content)

        imd_path = os.path.join(self.temp_dir.name, "prop.imd")
        convert_obj_to_imd(
            obj_path,
            imd_path,
            texture_name="prop_tex",
            palette_name="prop_pal",
            scale=1.0
        )

        self.assertTrue(os.path.exists(imd_path))

        # Valida estrutura do XML IMD
        tree = ET.parse(imd_path)
        root = tree.getroot()
        self.assertEqual(root.tag, "imd")

        body = root.find("body")
        self.assertIsNotNone(body)

        mat_array = body.find("material_array")
        self.assertIsNotNone(mat_array)
        mat = mat_array.find("material")
        self.assertEqual(mat.attrib.get("tex_image_name"), "prop_tex")
        self.assertEqual(mat.attrib.get("palette_name"), "prop_pal")

        poly_array = body.find("polygon_array")
        self.assertIsNotNone(poly_array)
        poly = poly_array.find("polygon")
        self.assertIsNotNone(poly)
        vtx_list = poly.find("vertex_list")
        self.assertIsNotNone(vtx_list)
        self.assertTrue(len(vtx_list.text.strip()) > 0)

    def test_nsbmd_inspector_warnings(self):
        # Monta um binário sintético BMD0 com modelo excedendo limites do DS
        model_name = b"oversized_boss"
        model_header = bytearray(0x40)
        # 5I (20 bytes), 16B (16 bytes), 4H (vertices=2500, surfaces=10, triangles=2000, quads=0)
        struct.pack_into("<5I16B4H", model_header, 0, *([0]*5), *([0]*16), 2500, 10, 2000, 0)

        # Monta bloco MDL0
        mdl0_body = bytearray()
        mdl0_body.extend(b"\x00\x01\x00\x00")  # count = 1
        mdl0_body.extend(b"\x08\x00\x00\x00\x7f\x01\x00\x00")  # unk block
        mdl0_body.extend(b"\x00\x00\x00\x00")  # unk entry
        mdl0_body.extend(b"\x00\x00\x00\x00")  # info len
        mdl0_body.extend(b"\x30\x00\x00\x00")  # model offset = 0x30 (48)
        mdl0_body.extend(model_name.ljust(16, b"\x00"))
        mdl0_body.extend(model_header)

        mdl0_sec = b"MDL0" + struct.pack("<I", len(mdl0_body) + 8) + mdl0_body
        bmd0_file = b"BMD0\xfe\xff\x01\x00" + struct.pack("<IHH", len(mdl0_sec) + 16, 16, 1) + mdl0_sec

        inspector = NSBMDInspector(bmd0_file)
        summary = inspector.summary()
        self.assertEqual(summary["models_count"], 1)
        self.assertEqual(summary["models"][0]["name"], "oversized_boss")
        self.assertGreater(summary["models"][0]["polygons_count"], DS_MAX_POLYGONS)

        # Deve gerar avisos de compatibilidade com DS
        self.assertFalse(summary["is_valid_ds_asset"])
        self.assertTrue(any("excede o orçamento de polígonos" in w for w in summary["warnings"]))
        self.assertTrue(any("excede o orçamento de vértices" in w for w in summary["warnings"]))


if __name__ == "__main__":
    unittest.main()
