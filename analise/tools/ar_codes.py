#!/usr/bin/env python3
"""Interpretador de códigos Action Replay DS (fase A1 do plano do mod menu).

Faz o mesmo que o motor de cheats do cartão: executa a lista de códigos uma vez por
quadro, escrevendo na RAM. Serve para três coisas:

    python3 analise/tools/ar_codes.py validar cheats/YWSE.txt
        confere a forma de cada cheat (tipos conhecidos, endereços na RAM principal,
        condições fechadas) antes de gravar no cartão.

    python3 analise/tools/ar_codes.py simular cheats/YWSE.txt [TECLAS]
        roda cada cheat uma vez numa memória vazia e mostra o que ele escreveria.
        TECLAS = teclas apertadas, separadas por vírgula (ex.: L,R,UP).

    no emulador (py-desmume): Motor(cheats).quadro(MemoriaDesmume(emu)) a cada quadro;
        o emu_run.py faz isso com a ação "cheat ARQ".

Tipos de código (EnHacklopedia, "Action Replay DS"; o Pico Loader usa o motor do
NitroHax, que implementa os mesmos):

    0XXXXXXX YYYYYYYY  escreve 32 bits em X+offset       1 = 16 bits, 2 = 8 bits
    3..6     YYYYYYYY  se Y >, <, ==, != a palavra de 32 bits em X
    7..A     ZZZZYYYY  se Y >, <, ==, != (meia palavra em X) & ~Z
    BXXXXXXX           offset = palavra de 32 bits em X+offset (ponteiro)
    C0000000 YYYYYYYY  repete o bloco até D1/D2, Y vezes a mais
    D0 fim de um "se"; D1 fim de repetição; D2 fim de repetição e de tudo
    (no fim, zera as condições, o offset e o dado)
    D3 offset = Y; D4 dado += Y; D5 dado = Y; D6/D7/D8 grava o dado (32/16/8 bits)
    em Y+offset e avança o offset; D9/DA/DB lê o dado de Y+offset; DC offset += Y
    EXXXXXXX YYYYYYYY  copia os Y bytes que vêm nas linhas seguintes para X+offset
    FXXXXXXX YYYYYYYY  copia Y bytes de offset para X

Nos tipos 3..A, endereço 0 quer dizer "use o offset". Uma condição falsa pula os
códigos até o D0/D2 que a fecha (contando as condições de dentro).
"""
import sys

try:  # executado como script (python3 analise/tools/ar_codes.py) ou como módulo
    from usrcheat import ler_txt_pastas
except ImportError:  # pragma: no cover
    from analise.tools.usrcheat import ler_txt_pastas

M32 = 0xFFFFFFFF
RAM = (0x02000000, 0x02400000)   # RAM principal: 4 MB
TECLAS_IO = 0x04000130           # KEYINPUT: bit em 0 = apertado
TECLAS = {"A": 0, "B": 1, "SELECT": 2, "START": 3, "RIGHT": 4, "LEFT": 5, "UP": 6,
          "DOWN": 7, "R": 8, "L": 9}


class MemoriaFalsa:
    """Memória de mentira para testes: tudo começa em 0 e as escritas ficam anotadas."""

    def __init__(self, inicial=None, teclas=()):
        self.b = {}
        self.escritas = []
        for end, (tam, v) in (inicial or {}).items():
            self._poe(end, tam, v)
        apertadas = 0
        for t in teclas:
            apertadas |= 1 << TECLAS[t.upper()]
        self._poe(TECLAS_IO, 2, 0x3FF & ~apertadas)

    def _poe(self, end, tam, v):
        for i in range(tam):
            self.b[end + i] = (v >> (8 * i)) & 0xFF

    def ler(self, end, tam):
        return sum(self.b.get(end + i, 0) << (8 * i) for i in range(tam))

    def escrever(self, end, tam, v):
        self.escritas.append((end, tam, v))
        self._poe(end, tam, v)


class MemoriaDesmume:
    """Liga o motor ao py-desmume (emu = desmume.emulator.DeSmuME já com a ROM aberta)."""

    def __init__(self, emu):
        self.m = emu.memory

    def ler(self, end, tam):
        u = self.m.unsigned
        return {1: u.read_byte, 2: u.read_short, 4: u.read_long}[tam](end)

    def escrever(self, end, tam, v):
        {1: self.m.write_byte, 2: self.m.write_short, 4: self.m.write_long}[tam](end, v)


def linhas(codigos):
    """Lista plana de palavras → pares (a, b)."""
    return [(codigos[i], codigos[i + 1]) for i in range(0, len(codigos), 2)]


def _linhas_de_dados_e(n_bytes):
    return (n_bytes + 7) // 8


def executar(codigos, mem):
    """Executa uma vez a lista de códigos de um cheat (um quadro)."""
    ln = linhas(codigos)
    offset = dado = 0
    pilha = []                 # resultado de cada "se" aberto
    laco = None                # (índice do C0, repetições que faltam)
    i = 0
    while i < len(ln):
        a, b = ln[i]
        tipo = a >> 28
        ativo = all(pilha)
        if tipo == 0xD:
            sub = (a >> 24) & 0xF
            if sub == 0:
                if pilha:
                    pilha.pop()
            elif sub in (1, 2):
                # Volta ao começo do laço enquanto faltarem repetições; o D2 só
                # zera o estado (condições, offset e dado) quando o laço acaba.
                if laco and laco[1] > 0:
                    laco = (laco[0], laco[1] - 1)
                    i = laco[0] + 1
                    continue
                laco = None
                if sub == 2:
                    pilha.clear()
                    offset = dado = 0
            elif not ativo:
                pass
            elif sub == 3:
                offset = b
            elif sub == 4:
                dado = (dado + b) & M32
            elif sub == 5:
                dado = b
            elif sub in (6, 7, 8):
                tam = {6: 4, 7: 2, 8: 1}[sub]
                mem.escrever((b + offset) & M32, tam, dado & ((1 << (8 * tam)) - 1))
                offset = (offset + tam) & M32
            elif sub in (9, 0xA, 0xB):
                dado = mem.ler((b + offset) & M32, {9: 4, 0xA: 2, 0xB: 1}[sub])
            elif sub == 0xC:
                offset = (offset + b) & M32
            else:
                raise ValueError(f"código D{sub:X} desconhecido")
        elif 3 <= tipo <= 0xA:
            if not ativo:
                pilha.append(False)
            else:
                end = (a & 0x0FFFFFFF) or offset
                if tipo <= 6:
                    v, alvo = mem.ler(end, 4), b
                else:
                    v, alvo = mem.ler(end, 2) & ~(b >> 16) & 0xFFFF, b & 0xFFFF
                cmp = (tipo - 3) % 4   # 0: >, 1: <, 2: ==, 3: !=
                pilha.append([alvo > v, alvo < v, alvo == v, alvo != v][cmp])
        elif tipo == 0xE:
            n = _linhas_de_dados_e(b)
            if ativo:
                dados = b"".join(x.to_bytes(4, "little") + y.to_bytes(4, "little")
                                 for x, y in ln[i + 1:i + 1 + n])
                base = ((a & 0x0FFFFFFF) + offset) & M32
                for k in range(b):
                    mem.escrever(base + k, 1, dados[k])
            i += 1 + n
            continue
        elif not ativo:
            pass
        elif tipo <= 2:
            tam = {0: 4, 1: 2, 2: 1}[tipo]
            mem.escrever(((a & 0x0FFFFFFF) + offset) & M32, tam, b & ((1 << (8 * tam)) - 1))
        elif tipo == 0xB:
            offset = mem.ler(((a & 0x0FFFFFFF) + offset) & M32, 4)
        elif tipo == 0xC:
            if (a >> 24) & 0xF != 0:
                raise ValueError(f"código C{(a >> 24) & 0xF:X} não suportado no simulador")
            laco = (i, b)
        elif tipo == 0xF:
            origem = offset
            for k in range(b):
                mem.escrever((a & 0x0FFFFFFF) + k, 1, mem.ler(origem + k, 1))
        i += 1


def validar(cheat):
    """Lista de problemas na forma de um cheat (vazia = tudo certo)."""
    erros = []
    c = cheat["codigos"]
    if not c or len(c) % 2:
        return ["sem códigos ou com número ímpar de palavras"]
    ln = linhas(c)
    abertas, usa_offset = 0, False
    i = 0
    while i < len(ln):
        a, b = ln[i]
        tipo, sub = a >> 28, (a >> 24) & 0xF
        end = a & 0x0FFFFFFF
        pos = f"linha {i + 1} ({a:08X} {b:08X})"
        if tipo <= 2 and not usa_offset and not RAM[0] <= end < RAM[1]:
            erros.append(f"{pos}: escrita fora da RAM principal")
        elif 3 <= tipo <= 0xA:
            if end and not (RAM[0] <= end < RAM[1] or end == TECLAS_IO):
                erros.append(f"{pos}: condição lê fora da RAM e das teclas")
            abertas += 1
        elif tipo == 0xB:
            usa_offset = True
        elif tipo == 0xC and sub not in (0, 4, 5, 6):
            erros.append(f"{pos}: código C{sub:X} desconhecido")
        elif tipo == 0xD:
            if sub == 0:
                if abertas == 0:
                    erros.append(f"{pos}: D0 sem condição aberta")
                abertas = max(0, abertas - 1)
            elif sub == 2:
                abertas, usa_offset = 0, False
            elif sub == 3 or sub == 0xC:
                usa_offset = True
            elif sub > 0xC:
                erros.append(f"{pos}: código D{sub:X} desconhecido")
        elif tipo == 0xE:
            n = _linhas_de_dados_e(b)
            if i + n >= len(ln):
                erros.append(f"{pos}: faltam linhas de dados do código E ({n} esperadas)")
            i += 1 + n
            continue
        i += 1
    if abertas:
        # Os cheats ligados são executados em sequência: uma condição aberta aqui
        # passaria a valer também para o cheat seguinte.
        erros.append(f"{abertas} condição(ões) sem D0/D2 no fim")
    return erros


def _todos(caminho):
    return [(p["nome"], ch) for p in ler_txt_pastas(caminho) for ch in p["cheats"]]


def main():
    if len(sys.argv) < 3 or sys.argv[1] not in ("validar", "simular"):
        print(__doc__)
        sys.exit(1)
    acao, arq = sys.argv[1], sys.argv[2]
    ruins = 0
    for pasta, ch in _todos(arq):
        if acao == "validar":
            erros = validar(ch)
            ruins += bool(erros)
            print(f"{'ERRO' if erros else 'ok  '}  {pasta or '-'} / {ch['nome']}")
            for e in erros:
                print(f"        {e}")
        else:
            teclas = sys.argv[3].split(",") if len(sys.argv) > 3 and sys.argv[3] else ()
            mem = MemoriaFalsa(teclas=teclas)
            executar(ch["codigos"], mem)
            print(f"{pasta or '-'} / {ch['nome']}")
            for end, tam, v in mem.escritas:
                print(f"    escreve {tam * 8:2} bits em 0x{end:08X} = 0x{v:0{tam * 2}X} ({v})")
            if not mem.escritas:
                print("    (nada: as condições não foram atendidas)")
    if ruins:
        sys.exit(1)


if __name__ == "__main__":
    main()
