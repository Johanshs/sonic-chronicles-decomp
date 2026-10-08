#!/usr/bin/env python3
"""Testes do interpretador de códigos AR e do formato de texto dos cheats (sem a ROM).

    python3 -m unittest discover -s analise/tools -p 'test_*.py'
"""
import os
import struct
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ar_codes  # noqa: E402
import usrcheat  # noqa: E402
from ar_codes import MemoriaFalsa, executar, validar  # noqa: E402

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
YWSE = os.path.join(RAIZ, "cheats", "YWSE.txt")


def roda(codigos, inicial=None, teclas=()):
    mem = MemoriaFalsa(inicial, teclas)
    executar(codigos, mem)
    return mem


class TestMotor(unittest.TestCase):
    def test_escritas_32_16_8(self):
        m = roda([0x020F64C0, 0x3E8, 0x12000000, 0xABCD1234, 0x22160E54, 0xFC])
        self.assertEqual(m.escritas, [(0x020F64C0, 4, 0x3E8), (0x02000000, 2, 0x1234),
                                      (0x02160E54, 1, 0xFC)])

    def test_botoes_L_R(self):
        cheat = [0x94000130, 0xFCFF0000, 0x22160E54, 0xFC, 0xD0000000, 0]
        self.assertEqual(roda(cheat).escritas, [])
        self.assertEqual(roda(cheat, teclas=["L"]).escritas, [])
        self.assertEqual(roda(cheat, teclas=["L", "R"]).escritas, [(0x02160E54, 1, 0xFC)])
        # outras teclas apertadas junto não atrapalham: a máscara as ignora
        self.assertEqual(len(roda(cheat, teclas=["L", "R", "A"]).escritas), 1)

    def test_L_cima_sem_R(self):
        cheat = [0x94000130, 0xFCBF0100, 0x020F64C0, 1000, 0xD0000000, 0]
        self.assertEqual(len(roda(cheat, teclas=["L", "UP"]).escritas), 1)
        # com R junto é o atalho da dificuldade (L+R): este não deve disparar
        self.assertEqual(roda(cheat, teclas=["L", "R", "UP"]).escritas, [])

    def test_condicao_falsa_pula_ate_o_D0_certo(self):
        cheat = [0x52000000, 1,            # se [0x02000000] == 1 (falso)
                 0x52000004, 0,            #   se ... (aninhado, também pulado)
                 0x02000010, 5,
                 0xD0000000, 0,
                 0x02000014, 6,
                 0xD0000000, 0,
                 0x02000018, 7]            # fora: sempre roda
        self.assertEqual(roda(cheat).escritas, [(0x02000018, 4, 7)])

    def test_comparacoes_32_bits(self):
        ini = {0x02000000: (4, 10)}
        for tipo, alvo, esperado in [(3, 11, True), (3, 10, False), (4, 9, True),
                                     (5, 10, True), (6, 10, False), (6, 1, True)]:
            m = roda([(tipo << 28) | 0x02000000, alvo, 0x02000100, 1, 0xD2000000, 0], ini)
            self.assertEqual(bool(m.escritas), esperado, (tipo, alvo))

    def test_ponteiro(self):
        # o código público de dinheiro: se o ponteiro existe, escreve em ponteiro + 0x114
        ini = {0x021D10AC: (4, 0x02230000)}
        cheat = [0x621D10AC, 0, 0xB21D10AC, 0, 0x00000114, 0x0001869F, 0xD2000000, 0]
        self.assertEqual(roda(cheat, ini).escritas[-1:], [(0x02230114, 4, 99999)])
        self.assertEqual(roda(cheat).escritas, [])   # ponteiro nulo: nada

    def test_codigo_E(self):
        cheat = [0xE2000100, 6, 0x44332211, 0x00006655]
        m = roda(cheat)
        self.assertEqual([v for _, _, v in m.escritas], [0x11, 0x22, 0x33, 0x44, 0x55, 0x66])

    def test_laco_e_dado(self):
        # grava 1 em 3 posições seguidas (D6 avança o offset)
        cheat = [0xD5000000, 1, 0xD3000000, 0x02000000, 0xC0000000, 2,
                 0xD6000000, 0, 0xD2000000, 0]
        m = roda(cheat)
        self.assertEqual([(e, v) for e, _, v in m.escritas],
                         [(0x02000000, 1), (0x02000004, 1), (0x02000008, 1)])


class TestValidar(unittest.TestCase):
    def test_condicao_aberta(self):
        erros = validar({"codigos": [0x94000130, 0xFCFF0000, 0x22160E54, 0xFC]})
        self.assertTrue(any("sem D0" in e for e in erros))

    def test_fora_da_ram(self):
        self.assertTrue(validar({"codigos": [0x01000000, 1]}))

    def test_E_sem_dados(self):
        self.assertTrue(validar({"codigos": [0xE2000100, 16, 0, 0]}))

    def test_bateria_do_projeto(self):
        for p in usrcheat.ler_txt_pastas(YWSE):
            for c in p["cheats"]:
                self.assertEqual(validar(c), [], c["nome"])


class TestTexto(unittest.TestCase):
    def test_pastas(self):
        txt = ("[Solto]\n020F64C0 000003E8\n@escolha Dif\n; so um\n"
               "[A]\n; desc A\n22160E54 000000FC\n[B]\n22160E54 00000006\n")
        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8") as f:
            f.write(txt)
        try:
            pastas = usrcheat.ler_txt_pastas(f.name)
            self.assertEqual([(p["nome"], p["um_so"], len(p["cheats"])) for p in pastas],
                             [("", False, 1), ("Dif", True, 2)])
            self.assertEqual(pastas[1]["desc"], "so um")
            self.assertEqual(pastas[1]["cheats"][0]["desc"], "desc A")
            self.assertEqual(len(usrcheat.ler_txt(f.name)), 3)
        finally:
            os.unlink(f.name)

    def test_ida_e_volta_no_banco(self):
        # bloco de jogo mínimo: nome, 9 palavras de cabeçalho, nenhum item
        blk = b"SONIC\0\0\0" + struct.pack("<9I", *([0] * 9))
        pastas = [("P1", "d1", [{"nome": "c1", "desc": "", "codigos": [0x020F64C0, 1000]}], False),
                  ("P2", "", [{"nome": "c2", "desc": "x", "codigos": [0x22160E54, 0xFC]},
                              {"nome": "c3", "desc": "", "codigos": [0x22160E54, 6]}], True)]
        novo = usrcheat.inserir_pastas(blk, pastas)
        nome, cab, itens = usrcheat.ler_bloco(novo)
        self.assertEqual(cab[0] & 0xFFFF, 5)
        self.assertEqual([(i["tipo"], i["nome"]) for i in itens],
                         [("pasta", "P1"), ("cheat", "c1"), ("pasta", "P2"),
                          ("cheat", "c2"), ("cheat", "c3")])
        self.assertFalse(itens[0]["flags"] & usrcheat.UM_SO)
        self.assertTrue(itens[2]["flags"] & usrcheat.UM_SO)
        self.assertEqual(itens[2]["filhos"], 2)
        self.assertEqual(itens[3]["codigos"], [0x22160E54, 0xFC])

    def test_troca_versao_anterior_e_mantem_o_resto(self):
        blk = b"SONIC\0\0\0" + struct.pack("<9I", *([0] * 9))
        c = {"nome": "c", "desc": "", "codigos": [0x020F64C0, 1]}
        blk = usrcheat.inserir_pasta(blk, "Miscellaneous Codes", "", [c])
        blk = usrcheat.inserir_pasta(blk, "Projeto antigo", "", [c, c])
        novo = usrcheat.inserir_pastas(blk, [("Projeto: novo", "", [c], False)])
        _, cab, itens = usrcheat.ler_bloco(novo)
        self.assertEqual([i["nome"] for i in itens if i["tipo"] == "pasta"],
                         ["Miscellaneous Codes", "Projeto: novo"])
        self.assertEqual(cab[0] & 0xFFFF, 4)


if __name__ == "__main__":
    unittest.main()
