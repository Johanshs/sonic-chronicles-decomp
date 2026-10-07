#!/usr/bin/env python3
"""Gera, a partir de um projeto do `sonic-mod unpack`, as tabelas de combate em Markdown.

Uso:
    python3 analise/tools/combate_tabelas.py <projeto> [saida_dir]

<projeto> é a pasta criada por `sonic-mod unpack rom.nds <projeto>`. Sem `saida_dir`,
escreve em `<projeto>/combate/`. Os arquivos gerados contêm dados do jogo, por isso
ficam fora do Git: o repositório só guarda este gerador e a explicação em
`docs/COMBATE.md`.

Arquivos gerados:
    golpes.md       todos os POW (combo.gda) com dono, parceiros, custo, dano e efeitos
    efeitos.md      cada .SPL (spells.gda) decodificado: alvo, duração, efeitos
    itens.md        cada item (Items.gda) com seu .ITM decodificado e habilidades especiais
    criaturas.md    atributos base das criaturas e curvas de nível (Adv_*)
    regras.md       CombatRules com o significado conhecido de cada regra

O significado de cada coluna e de cada código está explicado em docs/COMBATE.md;
as constantes abaixo repetem só o necessário para tornar a saída legível.
"""
import csv
import os
import sys

# Atributo lógico n (SData1 de um efeito tipo 1). Ver docs/COMBATE.md, seção 2.
ATRIBUTOS = {
    0: "HP", 21: "Speed", 22: "Attack", 23: "Defense", 24: "HP máx", 25: "Power",
    26: "Grit", 27: "Luck", 28: "PP", 36: "PP máx", 70: "Classe", 122: "Desconto POW",
    123: "Ações/rodada",
}
ELEMENTOS = ["Fogo", "Água", "Terra", "Vento", "Raio", "Gelo"]
for i, e in enumerate(ELEMENTOS):
    ATRIBUTOS[75 + i] = f"Resist. {e}"
    ATRIBUTOS[107 + i] = f"Dano {e}"
STATUS = ["KO", "Tinkered", "Poisoned", "Weakened", "Vulnerable", "Distracted",
          "Sluggish", "Cursed", "Stunned", "(9)", "Empowered", "Fortified", "Focused",
          "Hyper", "Lucky", "BugSpray"]
for i, s in enumerate(STATUS):
    ATRIBUTOS[39 + i] = f"status {s}"

ALVOS = {"0": "inimigo", "1": "aliado", "2": "todos inimigos", "3": "todos aliados",
         "5": "si mesmo", "6": "aliado nocauteado"}
DURACAO = {"0": "instantâneo", "1": "permanente", "2": "enquanto equipado", "3": "temporário"}

# Habilidades especiais (colunas de habilidade de Items.gda e EffectId 10).
HABILIDADES = {
    0: "POW sempre perfeito", 1: "chance de KO instantâneo (%)", 2: "contra-ataque",
    3: "revive 1x por batalha (% HP)", 4: "evitado pelos inimigos", 5: "atrai ataques",
    6: "esquiva ataques básicos", 7: "regenera HP do time (%)", 9: "regenera HP (%)",
    10: "recupera PP", 11: "sorte do time", 12: "bônus de XP (%)",
    13: "status aleatório ao acertar", 14: "reduz dano e divide com o time (%)",
    15: "fuga/perseguição mais rápida", 18: "inimigos fogem mais", 19: "ovos de Chao raros",
    21: "chance de emboscar (%)", 22: "reduz chance de ser emboscado (%)",
    23: "item extra na recompensa", 25: "Phased (imune a dano)", 26: "Agile (esquiva)",
    27: "auto-reparo", 28: "drena PP do atacante (%)", 29: "regenera PP do time",
    30: "regenera PP", 31: "imunidade",
}


def ler_csv(caminho):
    with open(caminho, encoding="utf-8") as f:
        linhas = list(csv.reader(f))
    return [dict(zip(linhas[0], l)) for l in linhas[1:]]


class Projeto:
    def __init__(self, raiz):
        self.raiz = raiz
        self.tab = os.path.join(raiz, "tabelas", "test")
        self.arq = os.path.join(raiz, "arquivos", "test")
        self.textos = {int(r["id"]): r["texto"]
                       for r in ler_csv(os.path.join(raiz, "textos", "en.csv"))}
        self.minusculos = {f.lower(): f for f in os.listdir(self.arq)}

    def tabela(self, nome):
        return ler_csv(os.path.join(self.tab, nome + ".csv"))

    def texto(self, ref):
        try:
            i = int(float(ref))
        except ValueError:
            return ""
        return self.textos.get(i, "") if i >= 0 else ""

    def efeitos(self, nome):
        """Lê um .ITM/.SPL (texto 2DA). Cada linha: (rótulo, ID, EffectId, Data, SData1,
        SData2, SData3, Pulse). A linha `SpellData` diz o alvo (EffectId); as linhas
        `CollectionData*` dizem a duração (Data = modo, SData1 = categoria, SData2 = tempo)."""
        real = self.minusculos.get(nome.lower())
        if not real:
            return None
        linhas = []
        with open(os.path.join(self.arq, real), encoding="latin-1") as f:
            for l in f.read().splitlines()[2:]:
                c = [x.strip() for x in l.split("\t")]
                if not c or not c[0]:
                    continue
                v = [x for x in c[1:] if x != ""]
                while len(v) < 7:
                    v.append("")
                linhas.append([c[0]] + v[:7])
        return linhas


def descreve_efeito(v):
    """Uma linha (EffectId, Data, SData1, SData2, ...) em português."""
    _rotulo, _id, eid, data, s1, s2, _s3, pulse = v
    try:
        eid = int(eid)
    except ValueError:
        return None
    if eid == 1:
        attr = ATRIBUTOS.get(int(s1), f"atributo {s1}")
        flags = int(s2) if s2.lstrip("-").isdigit() else 0
        modo = (flags >> 1) & 3
        base = "define" if flags & 1 else ""
        unidade = ["", "% do valor base", "% do HP máx", "% do PP máx"][modo]
        txt = f"{attr} {base}{'+' if int(data) >= 0 and not base else ' '}{data}{unidade}"
        if pulse == "1000":
            txt += " por rodada"
        return txt.replace("  ", " ")
    if eid == 5:
        return None  # efeito visual
    if eid == 6:
        return "revive"
    if eid == 7:
        return f"remove status (máscara {data})"
    if eid == 8:
        return "atrai os ataques"
    if eid == 9:
        return f"aplica o efeito {data}"
    if eid == 10:
        return f"habilidade: {HABILIDADES.get(int(data), data)}"
    return f"EffectId {eid} ({data})"


def resumo_arquivo(proj, nome, colecao="CollectionData"):
    linhas = proj.efeitos(nome)
    if linhas is None:
        return "(arquivo ausente)", "", ""
    alvo, dur, efs = "", "", []
    for v in linhas:
        rotulo = v[0]
        if rotulo.startswith("SpellData"):
            alvo = ALVOS.get(v[2], v[2])
        elif rotulo.startswith("CollectionData"):
            if rotulo == colecao or (not dur and colecao == "CollectionData"):
                dur = DURACAO.get(v[3], v[3])
                if v[3] == "3":
                    dur += f" {int(v[5]) / 1000:g} rodadas"
        elif v[2] not in ("-1", ""):
            e = descreve_efeito(v)
            if e:
                efs.append(e)
    return alvo, dur, "; ".join(efs)


def golpes(proj):
    criaturas = {r["ID"]: proj.texto(r["NameStrRef"]) for r in proj.tabela("creatures")}
    # Dono e parceiros: ID de criatura, mas a criatura 10 é um espaço vazio que os golpes
    # usam para a Shade (membro 10 de party.gda). Para esses casos, vale o nome do grupo.
    for m in proj.tabela("party"):
        if not criaturas.get(m["ID"]):
            criaturas[m["ID"]] = m["MemberName"]
    spells = {r["ID"]: r["Table"] for r in proj.tabela("spells")}
    out = ["# Golpes (POW)\n",
           "| ID | Nome | Dono | Parceiros | PP | Dano % (n1/n2/n3) | Efeito por nível (chance) | Marcas |",
           "|---|---|---|---|---|---|---|---|"]
    for r in proj.tabela("combo"):
        nome = proj.texto(r["NameStrRef"])
        if not nome:
            continue
        parceiros = [criaturas.get(r[c], r[c]) for c in
                     ("col_4fae1054", "col_56b52115", "col_19f4b7d2") if r[c] != "-1"]
        chances = [r["col_a9e4c4fc"], r["GUITypeAggressive"], r["col_9bd2a67e"]]
        efs = []
        for n in range(3):
            s = r[f"Spell{n + 1}"]
            if s != "-1":
                # Chance negativa: a rolagem nunca fica abaixo dela, então o status não é aplicado.
                ch = float(chances[n])
                efs.append(f"{spells.get(s, s)} ({f'{ch * 100:.0f}%' if ch >= 0 else 'nunca'})")
        marcas = [m for m in ("ArmorPiercing", "Inescapable", "Blast", "Scatter") if r[m] not in ("0", "")]
        if r["Leech"] not in ("0", ""):
            marcas.append(f"Leech {r['Leech']}%")
        if r["col_8b96e6f9"] not in ("0", ""):
            # Fração (0,5 = 50%), comparada com uma rolagem em 0x02010810.
            marcas.append(f"KO {float(r['col_8b96e6f9']) * 100:.0f}%")
        if r["col_46eddb98"] not in ("0", ""):
            marcas.append("todos do lado")
        el = int(r["ElementalDamage"] or 0)
        for b in range(17, 23):
            if el & (1 << b):
                marcas.append(ELEMENTOS[b - 17])
        dano = "/".join(r[f"Damage{i}"] for i in (1, 2, 3))
        out.append(f"| {r['ID']} | {nome} | {criaturas.get(r['col_64834397'], r['col_64834397'])} | "
                   f"{', '.join(parceiros)} | {r['Cost']} | {dano} | {'; '.join(efs)} | {', '.join(marcas)} |")
    return "\n".join(out) + "\n"


def efeitos(proj):
    out = ["# Efeitos (.SPL)\n", "| ID | Arquivo | Alvo | Duração | Efeitos |", "|---|---|---|---|---|"]
    for r in proj.tabela("spells"):
        alvo, dur, efs = resumo_arquivo(proj, r["Table"])
        out.append(f"| {r['ID']} | {r['Table']} | {alvo} | {dur} | {efs} |")
    return "\n".join(out) + "\n"


def itens(proj):
    slots = {"-1": "", "0": "pés", "1": "mãos", "2": "acessório", "4": "Chao"}
    tipos = {"0": "consumível", "1": "equipamento", "2": "chave", "3": "Chao"}
    personagens = [r for r in proj.tabela("creatures")][:10]
    out = ["# Itens\n",
           "| ID | Nome | Tipo | Slot | Quem equipa | Preço mín. | Alvo | Efeitos | Habilidades |",
           "|---|---|---|---|---|---|---|---|---|"]
    for r in proj.tabela("Items"):
        nome = proj.texto(r["Name"]) or f"(sem nome; aleatório {r['Random']})"
        quem = ""
        if r["Type"] == "1" and r["EquipSlot"] != "-1":
            m = int(r["AllowEquip"])
            quem = ", ".join(proj.texto(c["NameStrRef"]) for i, c in enumerate(personagens) if m & (1 << i))
        col = "CollectionData_Equip" if r["Type"] in ("1", "3") else "CollectionData_Use"
        alvo, _dur, efs = resumo_arquivo(proj, r["BaseItem1"], col) if r["BaseItem1"] else ("", "", "")
        habs = []
        for cod, val in (("col_ab33ab1a", "col_dee49bb0"), ("col_801ef8d9", "col_f5c9c873")):
            if r[cod] not in ("-1", ""):
                habs.append(f"{HABILIDADES.get(int(r[cod]), r[cod])} = {r[val]}")
        out.append(f"| {r['ID']} | {nome} | {tipos.get(r['Type'], r['Type'])} | {slots.get(r['EquipSlot'], r['EquipSlot'])} "
                   f"| {quem} | {r['MinimumCost']} | {alvo} | {efs} | {'; '.join(habs)} |")
    return "\n".join(out) + "\n"


def criaturas(proj):
    cols = ["HitPoints", "Speed", "Attack", "Defense", "Power", "Grit", "Luck", "MaxFatigue", "NumActions"]
    out = ["# Criaturas\n", "| ID | Nome | Tipo | Nível | " + " | ".join(cols) + " | Fuga |",
           "|---|---|---|---|" + "---|" * len(cols) + "---|"]
    for r in proj.tabela("creatures"):
        nome = proj.texto(r["NameStrRef"])
        if not nome:
            continue
        out.append(f"| {r['ID']} | {nome} | {r['Type']} | {r['Level']} | "
                   + " | ".join(r[c] for c in cols) + f" | {float(r['FleeProbability']):.2f} |")
    for nome in sorted(f[:-4] for f in os.listdir(proj.tab) if f.startswith("Adv_")):
        linhas = proj.tabela(nome)
        if not linhas:
            continue
        cab = [k for k in linhas[0] if k != "ID"]
        out += [f"\n## {nome}\n", "| " + " | ".join(cab) + " |", "|" + "---|" * len(cab)]
        out += ["| " + " | ".join(l[k] for k in cab) + " |" for l in linhas]
    return "\n".join(out) + "\n"


SIGNIFICADO_REGRAS = {
    1: "base da iniciativa", 2: "dado da iniciativa (1dN)", 3: "peso do Speed na iniciativa",
    7: "Defend: +Defense (x/10)", 8: "Defend: +Grit (x/10)", 11: "Defend: recupera PP",
    33: "divisor do intervalo mínimo entre ações", 39: "chance de KO (base)",
    43: "dano: parte fixa (%)", 44: "dano: k do grupo", 45: "dano: k do inimigo",
    47: "dado da emboscada", 57: "dificuldade: Defense (+)", 58: "dificuldade: Power (+)",
    59: "dificuldade: Attack (+)", 60: "dificuldade: Grit (+)", 61: "dificuldade: HP máx (+)",
    63: "dificuldade: nível máximo", 64: "dificuldade: nível mínimo",
    66: "dificuldade: Defense (−)", 67: "dificuldade: Power (−)", 68: "dificuldade: Attack (−)",
    69: "dificuldade: Grit (−)", 70: "dificuldade: HP máx (−)", 62: "dificuldade: divisor (+)",
    65: "dificuldade: divisor (−)", 15: "minijogo de toque (POW)", 16: "minijogo de toque (POW)",
    17: "minijogo de toque (POW)", 40: "POW: desempenho (vfunc05 0x02070928)",
    41: "POW: desempenho (vfunc05 0x02070928)", 42: "POW: desempenho (vfunc05 0x02070928)",
    71: "minijogo POW nível 1 (x/100)", 72: "minijogo POW nível 2 (x/100)",
    73: "minijogo POW nível 3 (x/100)",
}


def regras(proj):
    out = ["# CombatRules\n", "| Regra | Valor | Significado (docs/COMBATE.md) |", "|---|---|---|"]
    for r in proj.tabela("CombatRules"):
        out.append(f"| {r['ID']} | {r['Value']} | {SIGNIFICADO_REGRAS.get(int(r['ID']), '')} |")
    return "\n".join(out) + "\n"


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    proj = Projeto(sys.argv[1])
    saida = sys.argv[2] if len(sys.argv) > 2 else os.path.join(sys.argv[1], "combate")
    os.makedirs(saida, exist_ok=True)
    for nome, func in (("golpes", golpes), ("efeitos", efeitos), ("itens", itens),
                       ("criaturas", criaturas), ("regras", regras)):
        with open(os.path.join(saida, nome + ".md"), "w", encoding="utf-8") as f:
            f.write(func(proj))
        print(f"{saida}/{nome}.md")


if __name__ == "__main__":
    main()
