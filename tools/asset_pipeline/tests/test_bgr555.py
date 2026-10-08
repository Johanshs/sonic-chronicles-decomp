import unittest
from PIL import Image
from ..core.bgr555 import (
    rgb_to_bgr555,
    bgr555_to_rgb,
    quantize_image_to_ds_palette,
    map_pixels_to_palette,
)


class TestBgr555(unittest.TestCase):
    def test_rgb_to_bgr555_and_back(self):
        # Preto
        self.assertEqual(rgb_to_bgr555(0, 0, 0), 0)
        self.assertEqual(bgr555_to_rgb(0), (0, 0, 0))

        # Branco
        white_bgr = rgb_to_bgr555(255, 255, 255)
        self.assertEqual(white_bgr, 0x7FFF)
        self.assertEqual(bgr555_to_rgb(white_bgr), (255, 255, 255))

        # Vermelho puro (5-bit = 31)
        red_bgr = rgb_to_bgr555(255, 0, 0)
        self.assertEqual(red_bgr, 31)
        r, g, b = bgr555_to_rgb(red_bgr)
        self.assertEqual(r, 255)
        self.assertEqual(g, 0)
        self.assertEqual(b, 0)

        # Verde puro (5-bit = 31 << 5)
        green_bgr = rgb_to_bgr555(0, 255, 0)
        self.assertEqual(green_bgr, 31 << 5)

        # Azul puro (5-bit = 31 << 10)
        blue_bgr = rgb_to_bgr555(0, 0, 255)
        self.assertEqual(blue_bgr, 31 << 10)

    def test_quantize_palette_transparency(self):
        img = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
        # Adiciona um retângulo vermelho opaco no meio
        for y in range(4, 12):
            for x in range(4, 12):
                img.putpixel((x, y), (255, 0, 0, 255))

        bgr_pal, rgba_pal = quantize_image_to_ds_palette(img, max_colors=16)
        self.assertEqual(len(bgr_pal), 16)
        self.assertEqual(len(rgba_pal), 16)

        # Índice 0 deve ter alfa 0 (transparente)
        self.assertEqual(rgba_pal[0][3], 0)

        # Mapeia pixels e confere se cantos são 0 e centro é índice opaco
        indices = map_pixels_to_palette(img, rgba_pal)
        self.assertEqual(indices[0], 0)  # Canto transparente
        center_idx = indices[8 * 16 + 8]
        self.assertGreater(center_idx, 0)


if __name__ == "__main__":
    unittest.main()
