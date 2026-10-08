import unittest
import os
import tempfile
import csv
from PIL import Image

from ..studio.item_generator import ItemGenerator, generate_item_2da
from ..studio.pow_generator import PowGenerator, generate_spell_2da


class TestGenerators(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.proj_dir = self.temp_dir.name

        # Inicializa estrutura mínima de tabelas simulando sonic-mod unpack
        tab_dir = os.path.join(self.proj_dir, "tabelas", "test")
        txt_dir = os.path.join(self.proj_dir, "textos")
        os.makedirs(tab_dir, exist_ok=True)
        os.makedirs(txt_dir, exist_ok=True)

        # Items.csv simulado
        with open(os.path.join(tab_dir, "Items.csv"), "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["ID", "Name", "Description", "Type", "SubType", "MinimumCost", "BaseItem1", "Icon"])
            writer.writerow(["1", "100", "101", "1", "1", "50", "Item1.ITM", "ITM_Seed"])

        # combo.csv simulado
        with open(os.path.join(tab_dir, "combo.csv"), "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["ID", "Name", "Description", "col_a66f4be0", "col_64834397", "Cost", "Damage1", "Damage2", "Damage3", "ArmorPiercing"])
            writer.writerow(["1", "200", "201", "1", "0", "3", "100", "140", "180", "0"])

        # creatures.csv simulado (linha 0 = Sonic)
        with open(os.path.join(tab_dir, "creatures.csv"), "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["ID", "NameStrRef", "Combo1", "Combo2", "Combo3"])
            writer.writerow(["0", "300", "1", "", ""])

        # en.csv simulado
        with open(os.path.join(txt_dir, "en.csv"), "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["id", "texto"])
            writer.writerow(["100", "Health Seed"])

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_create_item(self):
        # Cria um ícone PNG 32x32 de teste
        icon_path = os.path.join(self.proj_dir, "chili_dog.png")
        img = Image.new("RGBA", (32, 32), (255, 120, 0, 255))
        img.save(icon_path)

        gen = ItemGenerator(self.proj_dir)
        res = gen.create_item(
            name="Chili Dog",
            description="Delicioso lanche que recupera 150 de HP.",
            item_id=901,
            cost=250,
            heal_hp=150,
            icon_png_path=icon_path
        )

        self.assertEqual(res["item_id"], 901)
        self.assertEqual(res["name"], "Chili Dog")
        self.assertTrue(os.path.exists(res["itm_path"]))
        self.assertTrue(res["icon_generated"])

        # Confere conteúdo do arquivo 2DA .ITM
        with open(res["itm_path"], "r", encoding="latin-1") as f:
            content = f.read()
        self.assertTrue(content.startswith("2DA V2.0"))
        self.assertIn("HealHP\t2\t1\t150\t0\t0", content)

        # Confere se foi adicionado em Items.csv
        items_csv = os.path.join(self.proj_dir, "tabelas", "test", "Items.csv")
        with open(items_csv, "r", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[1]["ID"], "901")
        self.assertEqual(rows[1]["BaseItem1"], "Item901.ITM")

    def test_create_pow(self):
        gen = PowGenerator(self.proj_dir)
        res = gen.create_pow(
            name="Sonic Wind Surge",
            description="Poderoso turbilhão supersônico que perfura armaduras.",
            owner_id=0,  # Sonic
            combo_id=165,
            pp_cost=5,
            damage_l1=140,
            damage_l2=190,
            damage_l3=250,
            armor_piercing=True,
            all_enemies=True
        )

        self.assertEqual(res["combo_id"], 165)
        self.assertEqual(res["creature_slot"], "Combo2")  # Atribuído ao próximo livre
        self.assertTrue(os.path.exists(res["spl_path"]))

        # Confere conteúdo de combo.csv
        combo_csv = os.path.join(self.proj_dir, "tabelas", "test", "combo.csv")
        with open(combo_csv, "r", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[1]["ID"], "165")
        self.assertEqual(rows[1]["ArmorPiercing"], "1")
        self.assertEqual(rows[1]["Cost"], "5")

        # Confere criaturas.csv (slot Combo2 atualizado)
        creat_csv = os.path.join(self.proj_dir, "tabelas", "test", "creatures.csv")
        with open(creat_csv, "r", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        self.assertEqual(rows[0]["Combo2"], "165")


if __name__ == "__main__":
    unittest.main()
