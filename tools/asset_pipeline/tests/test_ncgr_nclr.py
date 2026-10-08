import unittest
import os
import tempfile
from PIL import Image

from ..core.ncgr_nclr import (
    encode_png_to_ncgr_nclr,
    decode_ncgr_nclr_to_png,
    parse_nclr_binary,
    parse_ncgr_binary,
)


class TestNcgrNclr(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_encode_and_decode_roundtrip(self):
        # Cria um ícone de teste 32x32 com cantos transparentes e formas coloridas
        png_path = os.path.join(self.temp_dir.name, "test_icon.png")
        ncgr_path = os.path.join(self.temp_dir.name, "test_icon.ncgr")
        nclr_path = os.path.join(self.temp_dir.name, "test_icon.nclr")
        out_png_path = os.path.join(self.temp_dir.name, "decoded_icon.png")

        img = Image.new("RGBA", (32, 32), (0, 0, 0, 0))
        for y in range(4, 28):
            for x in range(4, 28):
                if (x + y) % 2 == 0:
                    img.putpixel((x, y), (0, 64, 200, 255))   # Azul Sonic
                else:
                    img.putpixel((x, y), (255, 200, 0, 255))  # Amarelo
        img.save(png_path)

        # 1. Codifica para NCGR e NCLR
        w, h = encode_png_to_ncgr_nclr(png_path, ncgr_path, nclr_path, bpp=4)
        self.assertEqual(w, 32)
        self.assertEqual(h, 32)

        # 2. Confere arquivos e assinaturas binárias
        with open(nclr_path, "rb") as f:
            nclr_data = f.read()
        self.assertTrue(nclr_data.startswith(b"RLCN"))
        self.assertIn(b"TTLP", nclr_data)

        with open(ncgr_path, "rb") as f:
            ncgr_data = f.read()
        self.assertTrue(ncgr_data.startswith(b"RGCN"))
        self.assertIn(b"RAHC", ncgr_data)

        # 3. Decodifica de volta para PNG
        dw, dh = decode_ncgr_nclr_to_png(ncgr_path, nclr_path, out_png_path)
        self.assertEqual(dw, 32)
        self.assertEqual(dh, 32)

        # 4. Confere imagem decodificada
        dec_img = Image.open(out_png_path)
        self.assertEqual(dec_img.size, (32, 32))

        # Canto deve ser transparente
        self.assertEqual(dec_img.getpixel((0, 0))[3], 0)

        # Centro deve ser opaco
        self.assertEqual(dec_img.getpixel((10, 10))[3], 255)


if __name__ == "__main__":
    unittest.main()
