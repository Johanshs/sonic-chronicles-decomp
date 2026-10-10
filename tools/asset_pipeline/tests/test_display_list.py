import unittest
import os
import tempfile
from ..core.nitro_display_list import NitroDisplayListBuilder, compile_obj_to_display_list


class TestNitroDisplayList(unittest.TestCase):
    def test_builder_basic(self):
        builder = NitroDisplayListBuilder()
        builder.begin_vtxs(NitroDisplayListBuilder.PRIMITIVE_TRIANGLES)
        builder.set_color(31, 0, 0)
        builder.set_vertex_16(0.0, 1.0, 0.0)
        builder.set_vertex_16(-1.0, -1.0, 0.0)
        builder.set_vertex_16(1.0, -1.0, 0.0)
        builder.end_vtxs()

        binary = builder.compile()
        self.assertGreater(len(binary), 0)
        # Deve ter tamanho alinhado a 4 bytes
        self.assertEqual(len(binary) % 4, 0)

    def test_compile_obj_file(self):
        with tempfile.NamedTemporaryFile("w", suffix=".obj", delete=False) as f:
            f.write("v 0.0 1.0 0.0\n")
            f.write("v -1.0 -1.0 0.0\n")
            f.write("v 1.0 -1.0 0.0\n")
            f.write("f 1 2 3\n")
            temp_path = f.name

        try:
            binary, stats = compile_obj_to_display_list(temp_path)
            self.assertEqual(stats["polygons"], 1)
            self.assertEqual(stats["triangles"], 1)
            self.assertEqual(stats["vertices"], 3)
            self.assertGreater(stats["byte_size"], 0)
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)


if __name__ == "__main__":
    unittest.main()
