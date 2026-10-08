import unittest
import os
import tempfile
from PIL import Image

from ..core.composite_2x2 import split_128_to_quads, merge_quads_to_128


class TestComposite2x2(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_split_and_merge_quads(self):
        # Cria imagem 128x128 com 4 quadrantes distintos
        png_path = os.path.join(self.temp_dir.name, "portrait_128.png")
        img = Image.new("RGBA", (128, 128), (0, 0, 0, 0))

        # Quad 0: Vermelho
        for y in range(0, 64):
            for x in range(0, 64):
                img.putpixel((x, y), (255, 0, 0, 255))
        # Quad 1: Verde
        for y in range(0, 64):
            for x in range(64, 128):
                img.putpixel((x, y), (0, 255, 0, 255))
        # Quad 2: Azul
        for y in range(64, 128):
            for x in range(0, 64):
                img.putpixel((x, y), (0, 0, 255, 255))
        # Quad 3: Amarelo
        for y in range(64, 128):
            for x in range(64, 128):
                img.putpixel((x, y), (255, 255, 0, 255))

        img.save(png_path)

        # 1. Fatia em 4 peças 64x64
        generated = split_128_to_quads(png_path, self.temp_dir.name, "PRTL_Test", bpp=4)
        self.assertEqual(len(generated), 5)  # 1 NCLR + 4 NCGR

        nclr_file = os.path.join(self.temp_dir.name, "PRTL_Test.nclr")
        quad_files = [
            os.path.join(self.temp_dir.name, f"PRTL_Test_{i}.ncgr")
            for i in range(4)
        ]

        self.assertTrue(os.path.exists(nclr_file))
        for q in quad_files:
            self.assertTrue(os.path.exists(q))

        # 2. Remonta em 128x128
        out_png = os.path.join(self.temp_dir.name, "remounted_128.png")
        merge_quads_to_128(quad_files, nclr_file, out_png)

        self.assertTrue(os.path.exists(out_png))
        remounted = Image.open(out_png)
        self.assertEqual(remounted.size, (128, 128))

        # Confere cores nos centros de cada quadrante
        # Quad 0 centro (32, 32): Vermelho
        p0 = remounted.getpixel((32, 32))
        self.assertGreater(p0[0], 200)
        self.assertEqual(p0[3], 255)

        # Quad 1 centro (96, 32): Verde
        p1 = remounted.getpixel((96, 32))
        self.assertGreater(p1[1], 200)
        self.assertEqual(p1[3], 255)

        # Quad 2 centro (32, 96): Azul
        p2 = remounted.getpixel((32, 96))
        self.assertGreater(p2[2], 200)
        self.assertEqual(p2[3], 255)


if __name__ == "__main__":
    unittest.main()
