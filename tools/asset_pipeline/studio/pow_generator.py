"""Gerador automatizado de novos golpes POW para Sonic Chronicles.

Automatiza:
1. Inserção na tabela tabelas/test/combo.csv (dono, parceiros, custo PP, dano L1-L3, armadura)
2. Atribuição à criatura em tabelas/test/creatures.csv (Combo1..Combo10)
3. Criação do script de efeito arquivos/test/Spell_<Nome>.SPL (alvo, dano, VFX, status)
4. Inserção de textos no TLK (textos/en.csv)
5. Conversão e registro do badge/ícone POW (NCGR/NCLR)
"""

import os
import csv
from typing import Dict, Any, Optional, List
from ..core.ncgr_nclr import encode_png_to_ncgr_nclr

# IDs das criaturas jogáveis em creatures.gda
CREATURE_SONIC = 0
CREATURE_KNUCKLES = 1
CREATURE_TAILS = 2
CREATURE_AMY = 3
CREATURE_SHADOW = 4
CREATURE_ROUGE = 5
CREATURE_BIG = 6
CREATURE_CREAM = 7
CREATURE_OMEGA = 8
CREATURE_EGGMAN = 9
CREATURE_SHADE = 10  # Marcador em combo.gda (criatura real é 27)

CREATURE_NAMES = {
    0: "Sonic", 1: "Knuckles", 2: "Tails", 3: "Amy", 4: "Shadow",
    5: "Rouge", 6: "Big", 7: "Cream", 8: "Omega", 9: "Eggman", 10: "Shade"
}


def generate_spell_2da(
    spell_name: str,
    target: int = 0,            # 0 = inimigo, 2 = todos inimigos, 1 = aliado
    vfx_id: int = 1,            # ID do efeito visual
    status_attr: int = 0,       # Atributo modificado ou status
    status_val: int = 0
) -> str:
    """Gera script 2DA para o arquivo de efeito .SPL do golpe POW."""
    lines = [
        "2DA V2.0",
        "",
        "Label\tID\tEffectId\tData\tSData1\tSData2\tSData3\tPulse"
    ]

    row_idx = 0
    # 1. Alvo do golpe
    lines.append(f"SpellData\t{row_idx}\t{target}\t****\t****\t****\t****\t****")
    row_idx += 1

    # 2. Dados da coleção
    lines.append(f"CollectionData\t{row_idx}\t0\t0\t0\t****\t****\t****")
    row_idx += 1

    # 3. Efeito Visual de Impacto (EffectId 5)
    if vfx_id > 0:
        lines.append(f"VisualEffect\t{row_idx}\t5\t{vfx_id}\t****\t****\t****\t****")
        row_idx += 1

    # 4. Modificador de Atributo ou Status Secundário (EffectId 1)
    if status_attr > 0 and status_val != 0:
        lines.append(f"ApplyStatus\t{row_idx}\t1\t{status_val}\t{status_attr}\t0\t****\t****")
        row_idx += 1

    return "\n".join(lines) + "\n"


class PowGenerator:
    def __init__(self, project_root: str):
        self.project_root = project_root
        self.tables_dir = os.path.join(project_root, "tabelas", "test")
        self.files_dir = os.path.join(project_root, "arquivos", "test")
        self.texts_dir = os.path.join(project_root, "textos")

    def create_pow(
        self,
        name: str,
        description: str,
        owner_id: int = CREATURE_SONIC,
        combo_id: Optional[int] = None,
        partner_ids: Optional[List[int]] = None,
        pp_cost: int = 4,
        damage_l1: int = 120,
        damage_l2: int = 160,
        damage_l3: int = 210,
        armor_piercing: bool = False,
        all_enemies: bool = False,
        vfx_id: int = 1,
        icon_png_path: Optional[str] = None,
        icon_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """Cria e registra um novo golpe POW completo no projeto."""
        os.makedirs(self.tables_dir, exist_ok=True)
        os.makedirs(self.files_dir, exist_ok=True)
        os.makedirs(self.texts_dir, exist_ok=True)

        combo_csv_path = os.path.join(self.tables_dir, "combo.csv")
        creatures_csv_path = os.path.join(self.tables_dir, "creatures.csv")
        texts_en_path = os.path.join(self.texts_dir, "en.csv")

        # 1. Determina ID do combo
        final_id = combo_id
        if final_id is None:
            final_id = 160
            if os.path.exists(combo_csv_path):
                with open(combo_csv_path, "r", encoding="utf-8") as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        try:
                            cid = int(row.get("ID", 0))
                            if cid >= final_id:
                                final_id = cid + 1
                        except ValueError:
                            pass

        # 2. Textos no TLK
        name_str_ref = 995000 + final_id * 2
        desc_str_ref = name_str_ref + 1
        if os.path.exists(texts_en_path):
            with open(texts_en_path, "a", encoding="utf-8", newline="") as f:
                writer = csv.writer(f)
                writer.writerow([name_str_ref, name])
                writer.writerow([desc_str_ref, description])

        # 3. Gera arquivo .SPL do efeito
        clean_name = "".join(c for c in name if c.isalnum() or c == "_")
        spell_file = f"Spell_{clean_name}.SPL"
        spl_content = generate_spell_2da(
            spell_name=clean_name,
            target=2 if all_enemies else 0,
            vfx_id=vfx_id
        )
        spl_path = os.path.join(self.files_dir, spell_file)
        with open(spl_path, "w", encoding="latin-1") as f:
            f.write(spl_content)

        # 4. Processa Ícone/Badge POW
        final_icon_name = icon_name or f"POW_{clean_name}"
        icon_generated = False
        if icon_png_path and os.path.exists(icon_png_path):
            ncgr_path = os.path.join(self.files_dir, f"{final_icon_name}.ncgr")
            nclr_path = os.path.join(self.files_dir, f"{final_icon_name}.nclr")
            encode_png_to_ncgr_nclr(icon_png_path, ncgr_path, nclr_path, bpp=4)
            icon_generated = True

        # 5. Adiciona entrada em combo.csv
        partners = partner_ids or []
        num_participants = 1 + len(partners)

        if os.path.exists(combo_csv_path):
            with open(combo_csv_path, "r", encoding="utf-8") as f:
                header = next(csv.reader(f))

            new_row = {h: "" for h in header}
            new_row["ID"] = str(final_id)
            if "Name" in new_row:
                new_row["Name"] = str(name_str_ref)
            if "Description" in new_row:
                new_row["Description"] = str(desc_str_ref)

            # Colunas decodificadas de combo.gda (docs/COMBATE.md seção 8.1)
            # col_a66f4be0: número de participantes
            # col_64834397: dono do golpe
            # col_4fae1054, col_56b52115, col_19f4b7d2: parceiros
            for k in ("col_a66f4be0", "Participants"):
                if k in new_row:
                    new_row[k] = str(num_participants)
            for k in ("col_64834397", "Owner"):
                if k in new_row:
                    new_row[k] = str(owner_id)

            partner_cols = [("col_4fae1054", "Partner1"), ("col_56b52115", "Partner2"), ("col_19f4b7d2", "Partner3")]
            for idx, p_id in enumerate(partners[:3]):
                c1, c2 = partner_cols[idx]
                if c1 in new_row:
                    new_row[c1] = str(p_id)
                elif c2 in new_row:
                    new_row[c2] = str(p_id)

            if "Cost" in new_row:
                new_row["Cost"] = str(pp_cost)
            if "Damage1" in new_row:
                new_row["Damage1"] = str(damage_l1)
            if "Damage2" in new_row:
                new_row["Damage2"] = str(damage_l2)
            if "Damage3" in new_row:
                new_row["Damage3"] = str(damage_l3)
            if "ArmorPiercing" in new_row:
                new_row["ArmorPiercing"] = "1" if armor_piercing else "0"

            with open(combo_csv_path, "a", encoding="utf-8", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=header)
                writer.writerow(new_row)

        # 6. Vincula à criatura em creatures.csv (Combo1..Combo10)
        slot_assigned = None
        if os.path.exists(creatures_csv_path):
            with open(creatures_csv_path, "r", encoding="utf-8") as f:
                rows = list(csv.DictReader(f))
                fieldnames = rows[0].keys() if rows else []

            # Procura linha do dono (linha 0 Sonic, 1 Knuckles, etc.)
            owner_row = None
            for r in rows:
                if r.get("ID") == str(owner_id):
                    owner_row = r
                    break

            if owner_row:
                # Acha primeiro slot livre entre Combo1 e Combo10
                for s in range(1, 11):
                    col = f"Combo{s}"
                    if col in owner_row and (owner_row[col] == "" or owner_row[col] == "-1" or owner_row[col] == "0"):
                        owner_row[col] = str(final_id)
                        slot_assigned = col
                        break

                with open(creatures_csv_path, "w", encoding="utf-8", newline="") as f:
                    writer = csv.DictWriter(f, fieldnames=fieldnames)
                    writer.writeheader()
                    writer.writerows(rows)

        return {
            "combo_id": final_id,
            "name": name,
            "owner": CREATURE_NAMES.get(owner_id, f"ID {owner_id}"),
            "pp_cost": pp_cost,
            "damage": (damage_l1, damage_l2, damage_l3),
            "spell_file": spell_file,
            "spl_path": spl_path,
            "creature_slot": slot_assigned,
            "icon_name": final_icon_name,
            "icon_generated": icon_generated,
        }
