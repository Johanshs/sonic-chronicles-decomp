#!/usr/bin/env python3
"""
Desenha os 8 quadros do efeito visual "Sonic Boom" (onda de choque supersônica).

Arte 100% original, gerada só por código (nada copiado do jogo).

Uso:
    python3 desenhar_sprites.py [PASTA_SAIDA]
    (padrão: pasta "sprites/" ao lado deste script)

Por que tantos limites? A textura vai para o DS no formato A3I5:
  - cada pixel ocupa 1 byte: 5 bits de índice de cor + 3 bits de alfa;
  - 5 bits = 32 cores na paleta (a transparência vem do alfa, não de uma cor);
    usamos no máximo 31 para sobrar folga;
  - 3 bits de alfa = só 8 níveis de transparência (0, 36, 73 ... 255);
  - por isso nada de anti-aliasing comum: a "suavidade" vem só desses 8 níveis;
  - borda de 1 px transparente porque o hardware pode repetir/esticar a borda.
Os 8 quadros dividem UMA paleta, então a soma de cores de todos fica <= 31.
"""

import math
import os
import sys

from PIL import Image

# ---------------------------------------------------------------------------
# Limites do formato
# ---------------------------------------------------------------------------
TAM = 32                 # quadro de 32x32 px
NUM_QUADROS = 8
MAX_CORES = 31           # 5 bits de cor = 32; deixamos 1 de folga
# Os 8 níveis de alfa (3 bits): nível k -> round(k * 255 / 7)
NIVEIS_ALFA = [round(k * 255 / 7) for k in range(8)]   # 0,36,73,...,255

# Centro da explosão: o meio exato da imagem (entre os pixels 15 e 16),
# assim o desenho fica simétrico.
CX = CY = TAM / 2

# ---------------------------------------------------------------------------
# Paleta (cores do Sonic: azul, ciano, branco + um toque de amarelo)
# ---------------------------------------------------------------------------
BRANCO = (255, 255, 255)
CIANO_CLARO = (176, 248, 255)
CIANO = (56, 216, 255)
AZUL_CLARO = (32, 152, 255)
AZUL = (24, 88, 232)
AZUL_ESCURO = (16, 40, 160)
AMARELO_CLARO = (255, 248, 168)


class Quadro:
    """Um quadro 32x32. Cada pixel guarda (cor, nível de alfa 0..7)."""

    def __init__(self):
        self.cor = [[None] * TAM for _ in range(TAM)]
        self.nivel = [[0] * TAM for _ in range(TAM)]

    def pintar(self, x, y, cor, nivel):
        """Pinta 1 pixel. O pixel mais opaco vence (empate: o último vence)."""
        nivel = max(0, min(7, int(nivel)))
        # Fora da área útil (borda de 1 px) não desenha nada.
        if nivel == 0 or not (1 <= x <= TAM - 2 and 1 <= y <= TAM - 2):
            return
        if nivel >= self.nivel[y][x]:
            self.cor[y][x] = cor
            self.nivel[y][x] = nivel

    def imagem(self):
        """Converte para uma imagem RGBA do Pillow."""
        img = Image.new("RGBA", (TAM, TAM), (0, 0, 0, 0))
        px = img.load()
        for y in range(TAM):
            for x in range(TAM):
                if self.nivel[y][x] > 0:
                    px[x, y] = self.cor[y][x] + (NIVEIS_ALFA[self.nivel[y][x]],)
        return img


def distancia(x, y):
    """Distância do centro do pixel (x, y) até o centro da explosão."""
    return math.hypot(x + 0.5 - CX, y + 0.5 - CY)


# ---------------------------------------------------------------------------
# Ferramentas de desenho
# ---------------------------------------------------------------------------
def faixas_radiais(q, raio, faixas):
    """Desenha anéis/discos. Cada faixa = (de, ate, cor, nivel), medida em
    'u = distância - raio'. Com raio=0 vira um disco cheio em camadas."""
    for y in range(TAM):
        for x in range(TAM):
            u = distancia(x, y) - raio
            for de, ate, cor, nivel in faixas:
                if de <= u < ate:
                    q.pintar(x, y, cor, nivel)
                    break


def anel_choque(q, raio, forca, largura=1.0):
    """O anel principal: halo ciano por fora, linha branca na frente,
    borda ciano e brilho azul por dentro. 'forca' = alfa máximo (0..7)."""
    w = largura
    # Branco com alfa baixo vira cinza sobre o chão escuro; então, se o anel
    # é fraco, a "frente" usa ciano claro no lugar do branco.
    frente = BRANCO if forca >= 6 else CIANO_CLARO
    faixas_radiais(q, raio, [
        (0.6, 0.6 + 0.9 * w, CIANO, forca - 3),               # halo externo
        (-0.5, 0.6, frente, forca),                            # frente branca
        (-0.5 - 1.0 * w, -0.5, CIANO, forca),                  # borda ciano
        (-0.5 - 2.0 * w, -0.5 - 1.0 * w, AZUL_CLARO, forca - 2),
        (-0.5 - 3.0 * w, -0.5 - 2.0 * w, AZUL, forca - 4),     # brilho interno
        (-0.5 - 4.0 * w, -0.5 - 3.0 * w, AZUL_ESCURO, forca - 5),
    ])


def raio_veloz(q, angulo, r_ini, r_fim, nivel_cabeca, nivel_cauda):
    """Risco radial de velocidade: cabeça branca (fora), cauda ciano (dentro).
    Pixels a até 0.6 px da linha entram: 2 px de grossura nos eixos e 1 px
    nas diagonais (riscos limpos, sem 'bolotas')."""
    a = math.radians(angulo)
    dx, dy = math.cos(a), math.sin(a)
    for y in range(TAM):
        for x in range(TAM):
            px, py = x + 0.5 - CX, y + 0.5 - CY
            ao_longo = px * dx + py * dy          # distância ao longo do risco
            de_lado = abs(-px * dy + py * dx)     # distância para os lados
            if r_ini <= ao_longo <= r_fim and de_lado < 0.6:
                t = (ao_longo - r_ini) / (r_fim - r_ini)   # 0 = cauda, 1 = ponta
                nivel = round(nivel_cauda + (nivel_cabeca - nivel_cauda) * t)
                # Branco só onde está bem opaco (senão parece cinza).
                if nivel >= 6:
                    cor = BRANCO
                elif nivel >= 4:
                    cor = CIANO_CLARO
                else:
                    cor = CIANO
                q.pintar(x, y, cor, nivel)


# Faíscas: (ângulo em graus, raio no quadro 4, velocidade em px por quadro).
# Ficam perto das diagonais, onde há mais espaço até a borda da imagem.
FAISCAS = [
    (36, 12.5, 2.4),
    (127, 12.0, 2.2),
    (214, 12.8, 2.5),
    (303, 12.2, 2.3),
    (82, 11.5, 1.2),
    (172, 11.8, 1.3),
]


def faiscas(q, num_quadro):
    """Faíscas voando para fora. Estilo muda conforme o quadro."""
    passo = num_quadro - 4
    for i, (ang, r0, vel) in enumerate(FAISCAS):
        r = r0 + vel * passo
        a = math.radians(ang)
        dx, dy = math.cos(a), math.sin(a)
        x, y = int(math.floor(CX + dx * r)), int(math.floor(CY + dy * r))
        # Pixel um pouco atrás (rumo ao centro) para o rastro.
        xt, yt = int(math.floor(CX + dx * (r - 1.3))), int(math.floor(CY + dy * (r - 1.3)))
        xt2, yt2 = int(math.floor(CX + dx * (r - 2.6))), int(math.floor(CY + dy * (r - 2.6)))
        brilho = AMARELO_CLARO if i % 2 == 0 else BRANCO
        if num_quadro == 4:          # cruzinha brilhante
            q.pintar(x, y, brilho, 7)
            for ox, oy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                q.pintar(x + ox, y + oy, CIANO, 5)
        elif num_quadro == 5:        # ponto + rastro
            q.pintar(x, y, brilho, 7)
            q.pintar(xt, yt, CIANO, 5)
            q.pintar(xt2, yt2, AZUL_CLARO, 2)
        elif num_quadro == 6:
            q.pintar(x, y, brilho, 5)
            q.pintar(xt, yt, CIANO, 3)
        elif num_quadro == 7 and i < 4:
            q.pintar(x, y, CIANO_CLARO, 3)
        elif num_quadro == 8 and i < 2:
            q.pintar(x, y, CIANO_CLARO, 2)


# ---------------------------------------------------------------------------
# Os 8 quadros
# ---------------------------------------------------------------------------
DIRECOES = [0, 45, 90, 135, 180, 225, 270, 315]


def quadro_1():
    """Clarão: núcleo branco/ciano pequeno e muito forte, com 4 pontas."""
    q = Quadro()
    faixas_radiais(q, 0, [
        (0.0, 2.2, BRANCO, 7),
        (2.2, 3.3, CIANO_CLARO, 7),
        (3.3, 4.3, CIANO, 5),
        (4.3, 5.3, AZUL_CLARO, 3),
        (5.3, 6.3, AZUL, 1),
    ])
    for ang in (0, 90, 180, 270):           # cruz de luz
        raio_veloz(q, ang, 2.0, 8.0, 3, 7)
    for ang in (45, 135, 225, 315):         # pontas diagonais menores
        raio_veloz(q, ang, 2.0, 5.5, 3, 5)
    return q


def quadro_2():
    """O clarão estoura num anel pequeno; riscos de velocidade curtos."""
    q = Quadro()
    faixas_radiais(q, 0, [(0.0, 1.8, CIANO_CLARO, 4), (1.8, 3.0, CIANO, 2)])
    anel_choque(q, 5.0, 7, largura=0.8)
    for ang in DIRECOES:
        raio_veloz(q, ang, 7.0, 10.5, 7, 4)
    return q


def quadro_3():
    q = Quadro()
    anel_choque(q, 7.5, 7, largura=1.0)
    for ang in DIRECOES:
        raio_veloz(q, ang, 10.0, 14.0, 6, 3)
    return q


def quadro_4():
    """Onda de choque nítida + anel interno + faíscas em cruz."""
    q = Quadro()
    anel_choque(q, 9.5, 7, largura=1.0)
    anel_choque(q, 4.5, 3, largura=0.7)
    faiscas(q, 4)
    return q


def quadro_5():
    q = Quadro()
    anel_choque(q, 11.2, 7, largura=1.0)
    anel_choque(q, 6.8, 4, largura=0.8)
    faiscas(q, 5)
    return q


def quadro_6():
    q = Quadro()
    anel_choque(q, 12.5, 6, largura=0.75)
    anel_choque(q, 9.2, 3, largura=0.6)
    faiscas(q, 6)
    return q


def quadro_7():
    """Anel fino e largo sumindo."""
    q = Quadro()
    faixas_radiais(q, 13.4, [
        (0.6, 1.2, CIANO, 1),
        (-0.5, 0.6, CIANO_CLARO, 5),
        (-1.5, -0.5, CIANO, 3),
        (-2.5, -1.5, AZUL, 2),
        (-3.5, -2.5, AZUL_ESCURO, 1),
    ])
    faiscas(q, 7)
    return q


def quadro_8():
    """Quase apagado, mas ainda visível."""
    q = Quadro()
    faixas_radiais(q, 14.0, [
        (-0.5, 0.5, CIANO, 2),
        (-1.5, -0.5, AZUL_CLARO, 1),
    ])
    faiscas(q, 8)
    return q


QUADROS = [quadro_1, quadro_2, quadro_3, quadro_4,
           quadro_5, quadro_6, quadro_7, quadro_8]


# ---------------------------------------------------------------------------
# Verificação dos limites (se algo quebrar, o script para com erro)
# ---------------------------------------------------------------------------
def verificar(imagens):
    assert len(imagens) == NUM_QUADROS, "precisa de exatamente 8 quadros"
    cores = set()
    for n, img in enumerate(imagens, 1):
        assert img.size == (TAM, TAM), f"quadro {n}: tamanho errado"
        assert img.mode == "RGBA", f"quadro {n}: precisa ser RGBA"
        px = img.load()
        visiveis = 0
        for y in range(TAM):
            for x in range(TAM):
                r, g, b, a = px[x, y]
                assert a in NIVEIS_ALFA, f"quadro {n}: alfa {a} inválido em {x},{y}"
                if a == 0:
                    assert (r, g, b) == (0, 0, 0), f"quadro {n}: transparente não é (0,0,0,0)"
                    continue
                borda = x in (0, TAM - 1) or y in (0, TAM - 1)
                assert not borda, f"quadro {n}: pixel visível na borda em {x},{y}"
                cores.add((r, g, b))
                visiveis += 1
        assert visiveis > 0, f"quadro {n}: está vazio"
    assert len(cores) <= MAX_CORES, f"{len(cores)} cores; o limite é {MAX_CORES}"
    return cores


def main():
    pasta = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "sprites")
    os.makedirs(pasta, exist_ok=True)

    imagens = [f().imagem() for f in QUADROS]
    cores = verificar(imagens)

    for n, img in enumerate(imagens, 1):
        img.save(os.path.join(pasta, f"boom_f{n}.png"))

    # Confere de novo lendo os arquivos do disco (o PNG salvo é o que vale).
    salvas = [Image.open(os.path.join(pasta, f"boom_f{n}.png")).convert("RGBA")
              for n in range(1, NUM_QUADROS + 1)]
    verificar(salvas)

    print(f"OK: {NUM_QUADROS} quadros {TAM}x{TAM} salvos em {pasta}")
    print(f"Cores usadas: {len(cores)} de {MAX_CORES}")
    for n, img in enumerate(salvas, 1):
        alfas = [img.getpixel((x, y))[3] for y in range(TAM) for x in range(TAM)
                 if img.getpixel((x, y))[3] > 0]
        print(f"  boom_f{n}.png: {len(alfas):3d} pixels visíveis, alfa máx {max(alfas)}")


if __name__ == "__main__":
    main()
