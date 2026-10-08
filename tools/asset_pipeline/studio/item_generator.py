"""Gerador automatizado de novos itens para Sonic Chronicles (compatível com sonic-mod e Aurora Engine).

Automatiza ponta a ponta:
1. Alocação de IDs e inserção em tabelas/test/Items.csv
2. Criação do script de efeito 2DA em arquivos/test/Item<ID>.ITM
3. Inserção de textos no TLK (textos/en.csv)
4. Conversão do ícone PNG (32x32) para binários Nitro NCGR e NCLR
5. Inclusão opcional em lojas (Store*.csv)
"""

import os
import csv
from typing import Dict, Any, Optional, List
from ..core.ncgr_nclr import encode_png_to_ncgr_nclr


# Constantes dos atributos lógicos (conforme docs/COMBATE.md e analise/tools/combate_tabelas.py)
ATTR_HP = 0
ATTR_SPEED = 21
ATTR_ATTACK = 22
ATTR_DEFENSE = 23
ATTR_MAX_HP = 24
ATTR_POWER = 25
ATTR_GRIT = 26
ATTR_LUCK = 27
ATTR_PP = 28
ATTR_MAX_PP = 36

TARGET_ENEMY = 0
TARGET_ALLY = 1
TARGET_ALL_ENEMIES = 2
TARGET_ALL_ALLIES = 3
TARGET_SELF = 5
TARGET_KO_ALLY = 6

DURATION_INSTANT = 0
DURATION_PERMANENT = 1
DURATION_EQUIPPED = 2
DURATION_TEMPORARY = 3


def generate_item_2da(
    item_id: int,
    target: int = TARGET_ALLY,
    duration_mode: int = DURATION_INSTANT,
    duration_rounds: int = 0,
    heal_hp: int = 0,
    heal_pp: int = 0,
    boost_power: int = 0,
    boost_defense: int = 0,
    cure_status_mask: int = 0,
    revive_percent: int = 0
) -> str:
    """Gera o conteúdo em texto 2DA V2.0 para o arquivo .ITM de efeitos do item."""
    lines = [
        "2DA V2.0",
        "",
        "Label\tID\tEffectId\tData\tSData1\tSData2\tSData3\tPulse"
    ]

    row_idx = 0

    # 1. Cabeçalho de Alvo (SpellData)
    lines.append(f"SpellData\t{row_idx}\t{target}\t****\t****\t****\t****\t****")
    row_idx += 1

    # 2. Cabeçalho de Coleta e Duração (CollectionData_Use)
    time_ms = duration_rounds * 1000 if duration_mode == DURATION_TEMPORARY else "****"
    lines.append(f"CollectionData_Use\t{row_idx}\t0\t{duration_mode}\t0\t{time_ms}\t****\t****")
    row_idx += 1

    # 3. Efeito: Reviver (EffectId 6)
    if revive_percent > 0:
        lines.append(f"Revive\t{row_idx}\t6\t{revive_percent}\t****\t****\t****\t****")
        row_idx += 1

    # 4. Efeito: Cura de HP (EffectId 1, Atributo 0)
    if heal_hp > 0:
        # SData2 = 0 (soma absoluta)
        lines.append(f"HealHP\t{row_idx}\t1\t{heal_hp}\t{ATTR_HP}\t0\t****\t****")
        row_idx += 1

    # 5. Efeito: Recupera PP (EffectId 1, Atributo 28)
    if heal_pp > 0:
        lines.append(f"RestorePP\t{row_idx}\t1\t{heal_pp}\t{ATTR_PP}\t0\t****\t****")
        row_idx += 1

    # 6. Efeito: Buff de Power (EffectId 1, Atributo 25)
    if boost_power != 0:
        lines.append(f"ModPower\t{row_idx}\t1\t{boost_power}\t{ATTR_POWER}\t0\t****\t****")
        row_idx += 1

    # 7. Efeito: Buff de Defense (EffectId 1, Atributo 23)
    if boost_defense != 0:
        lines.append(f"ModDefense\t{row_idx}\t1\t{boost_defense}\t{ATTR_DEFENSE}\t0\t****\t****")
        row_idx += 1

    # 8. Efeito: Remover status (EffectId 7)
    # 1022 = todos os debuffs (Poison, Weak, Vuln, Distracted, Sluggish, Cursed, Stunned)
    if cure_status_mask > 0:
        lines.append(f"CureStatus\t{row_idx}\t7\t{cure_status_mask}\t****\t****\t****\t****")
        row_idx += 1

    return "\n".join(lines) + "\n"


class ItemGenerator:
    def __init__(self, project_root: str):
        self.project_root = project_root
        self.tables_dir = os.path.join(project_root, "tabelas", "test")
        self.files_dir = os.path.join(project_root, "arquivos", "test")
        self.texts_dir = os.path.join(project_root, "textos")

    def create_item(
        self,
        name: str,
        description: str,
        item_id: Optional[int] = None,
        cost: int = 100,
        item_type: int = 1,
        sub_type: int = 1,
        icon_png_path: Optional[str] = None,
        icon_name: Optional[str] = None,
        target: int = TARGET_ALLY,
        heal_hp: int = 0,
        heal_pp: int = 0,
        boost_power: int = 0,
        boost_defense: int = 0,
        cure_status_mask: int = 0,
        revive_percent: int = 0,
        add_to_store: Optional[str] = None
    ) -> Dict[str, Any]:
        """Cria e injeta um novo item no projeto."""
        os.makedirs(self.tables_dir, exist_ok=True)
        os.makedirs(self.files_dir, exist_ok=True)
        os.makedirs(self.texts_dir, exist_ok=True)

        items_csv_path = os.path.join(self.tables_dir, "Items.csv")
        texts_en_path = os.path.join(self.texts_dir, "en.csv")

        # 1. Determina próximo ID disponível em Items.csv se não fornecido
        final_id = item_id
        if final_id is None:
            final_id = 900
            if os.path.exists(items_csv_path):
                with open(items_csv_path, "r", encoding="utf-8") as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        try:
                            cid = int(row.get("ID", 0))
                            if cid >= final_id:
                                final_id = cid + 1
                        except ValueError:
                            pass

        base_item_file = f"Item{final_id}.ITM"

        # 2. Insere textos de Nome e Descrição em en.csv
        name_str_ref = 990000 + final_id * 2
        desc_str_ref = name_str_ref + 1

        if os.path.exists(texts_en_path):
            with open(texts_en_path, "a", encoding="utf-8", newline="") as f:
                writer = csv.writer(f)
                writer.writerow([name_str_ref, name])
                writer.writerow([desc_str_ref, description])

        # 3. Gera arquivo 2DA do efeito .ITM
        itm_content = generate_item_2da(
            item_id=final_id,
            target=target,
            heal_hp=heal_hp,
            heal_pp=heal_pp,
            boost_power=boost_power,
            boost_defense=boost_defense,
            cure_status_mask=cure_status_mask,
            revive_percent=revive_percent
        )
        itm_path = os.path.join(self.files_dir, base_item_file)
        with open(itm_path, "w", encoding="latin-1") as f:
            f.write(itm_content)

        # 4. Processa Ícone (se fornecido)
        final_icon_name = icon_name or f"ITM_{final_id}"
        icon_generated = False
        if icon_png_path and os.path.exists(icon_png_path):
            ncgr_path = os.path.join(self.files_dir, f"{final_icon_name}.ncgr")
            nclr_path = os.path.join(self.files_dir, f"{final_icon_name}.nclr")
            encode_png_to_ncgr_nclr(icon_png_path, ncgr_path, nclr_path, bpp=4)
            icon_generated = True

        # 5. Adiciona linha em Items.csv
        if os.path.exists(items_csv_path):
            # Lê cabeçalho existente
            with open(items_csv_path, "r", encoding="utf-8") as f:
                header = next(csv.reader(f))

            new_row = {h: "" for h in header}
            new_row["ID"] = str(final_id)
            new_row["Name"] = str(name_str_ref)
            new_row["Description"] = str(desc_str_ref)
            new_row["Type"] = str(item_type)
            new_row["SubType"] = str(sub_type)
            new_row["MinimumCost"] = str(cost)
            new_row["BaseItem1"] = base_item_file
            if "Icon" in new_row:
                new_row["Icon"] = final_icon_name
            if "DefaultIcon" in new_row:
                new_row["DefaultIcon"] = final_icon_name

            with open(items_csv_path, "a", encoding="utf-8", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=header)
                writer.writerow(new_row)

        # 6. Insere opcionalmente na loja especificada
        if add_to_store:
            store_csv = os.path.join(self.tables_dir, f"{add_to_store}.csv")
            if os.path.exists(store_csv):
                with open(store_csv, "a", encoding="utf-8", newline="") as f:
                    writer = csv.writer(f)
                    writer.writerow([final_id, 99, cost])

        return {
            "item_id": final_id,
            "name": name,
            "name_str_ref": name_str_ref,
            "desc_str_ref": desc_str_ref,
            "base_item_file": base_item_file,
            "itm_path": itm_path,
            "icon_name": final_icon_name,
            "icon_generated": icon_generated,
        }
