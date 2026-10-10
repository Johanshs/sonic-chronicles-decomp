"""Compilador de Display Lists para a GPU 3D do Nintendo DS (NitroSystem G3D).

Codifica vértices, primitivas, normais, coordenadas UV e cores
no formato binário de comandos da GPU de geometria do DS (G3D Engine).
Em conformidade com as especificações do hardware Nitro (GBATEK / NitroSDK).
"""

import struct
from typing import List, Tuple, Optional, Dict, Any


class NitroDisplayListBuilder:
    """Construtor de Display Lists binárias para o hardware do Nintendo DS."""

    # Tipos de primitivas (BEGIN_VTXS)
    PRIMITIVE_TRIANGLES = 0
    PRIMITIVE_QUADS = 1
    PRIMITIVE_TRIANGLE_STRIP = 2
    PRIMITIVE_QUAD_STRIP = 3

    # Opcodes da GPU Nitro 3D
    OP_NOP = 0x00
    OP_MTX_MODE = 0x10
    OP_MTX_PUSH = 0x11
    OP_MTX_POP = 0x12
    OP_MTX_STORE = 0x13
    OP_MTX_RESTORE = 0x14
    OP_MTX_IDENTITY = 0x15
    OP_COLOR = 0x20
    OP_NORMAL = 0x21
    OP_TEXCOORD = 0x22
    OP_VTX_16 = 0x23
    OP_VTX_10 = 0x24
    OP_VTX_XY = 0x25
    OP_VTX_XZ = 0x26
    OP_VTX_YZ = 0x27
    OP_VTX_DIFF = 0x28
    OP_POLYGON_ATTR = 0x29
    OP_BEGIN_VTXS = 0x40
    OP_END_VTXS = 0x41

    def __init__(self):
        self._commands: List[Tuple[int, List[int]]] = []
        self.poly_count = 0
        self.vertex_count = 0

    def add_command(self, opcode: int, params: Optional[List[int]] = None):
        """Adiciona um comando e sua lista de parâmetros de 32 bits."""
        self._commands.append((opcode, params or []))

    def begin_vtxs(self, primitive_type: int = PRIMITIVE_TRIANGLES):
        """Inicia uma lista de vértices (0=TRIANGLES, 1=QUADS, etc.)."""
        self.add_command(self.OP_BEGIN_VTXS, [primitive_type & 0x03])

    def end_vtxs(self):
        """Finaliza a lista de vértices."""
        self.add_command(self.OP_END_VTXS, [])

    def set_color(self, r: int, g: int, b: int):
        """Define a cor do vértice em 5 bits por canal (0..31). BGR555."""
        bgr = (r & 0x1F) | ((g & 0x1F) << 5) | ((b & 0x1F) << 10)
        self.add_command(self.OP_COLOR, [bgr])

    def set_bgr555(self, bgr555: int):
        """Define a cor do vértice usando valor BGR555 direto."""
        self.add_command(self.OP_COLOR, [bgr555 & 0x7FFF])

    def set_normal(self, nx: float, ny: float, nz: float):
        """Define vetor normal em formato fixo de 10 bits por componente (-1.0 .. 1.0)."""
        def float_to_v10(v: float) -> int:
            val = int(round(v * 511.0))
            if val < -512: val = -512
            if val > 511: val = 511
            return val & 0x3FF

        ix = float_to_v10(nx)
        iy = float_to_v10(ny)
        iz = float_to_v10(nz)
        param = ix | (iy << 10) | (iz << 20)
        self.add_command(self.OP_NORMAL, [param])

    def set_texcoord(self, u: float, v: float, tex_w: int = 128, tex_h: int = 128):
        """Define coordenadas de textura (ponto fixo 12.4)."""
        s_fix = int(round(u * tex_w * 16.0)) & 0xFFFF
        t_fix = int(round(v * tex_h * 16.0)) & 0xFFFF
        param = s_fix | (t_fix << 16)
        self.add_command(self.OP_TEXCOORD, [param])

    def set_vertex_16(self, x: float, y: float, z: float, scale: float = 4096.0):
        """Adiciona vértice com coordenadas em ponto fixo s16 (dois parâmetros de 32 bits)."""
        ix = int(round(x * scale)) & 0xFFFF
        iy = int(round(y * scale)) & 0xFFFF
        iz = int(round(z * scale)) & 0xFFFF
        param0 = ix | (iy << 16)
        param1 = iz
        self.add_command(self.OP_VTX_16, [param0, param1])
        self.vertex_count += 1

    def set_polygon_attr(self, light_mask: int = 0x0F, poly_mode: int = 0, cull_back: bool = True, alpha: int = 31):
        """Define atributos do polígono (luzes, alpha, face culling)."""
        # Bits: 0-3 = Lights, 4-5 = Mode (0=Modulation, 1=Decal, 2=Toon/Highlight, 3=Shadow),
        # 6 = Cull Front, 7 = Cull Back, 16-20 = Alpha (0-31)
        val = (light_mask & 0x0F) | ((poly_mode & 0x03) << 4)
        if cull_back:
            val |= (1 << 7)
        val |= ((alpha & 0x1F) << 16)
        self.add_command(self.OP_POLYGON_ATTR, [val])

    def compile(self) -> bytes:
        """Compila os comandos e parâmetros empacotando 4 opcodes por palavra de comando."""
        output = bytearray()
        i = 0
        total = len(self._commands)

        while i < total:
            # Pega até 4 comandos para o bloco atual
            chunk = self._commands[i:i + 4]
            opcodes = [cmd[0] for cmd in chunk]
            params_list = [cmd[1] for cmd in chunk]

            # Preenche opcodes restantes com NOP (0x00)
            while len(opcodes) < 4:
                opcodes.append(self.OP_NOP)

            # Palavra de 4 opcodes
            op_word = opcodes[0] | (opcodes[1] << 8) | (opcodes[2] << 16) | (opcodes[3] << 24)
            output.extend(struct.pack("<I", op_word))

            # Parâmetros dos comandos (na ordem dos opcodes do bloco)
            for params in params_list:
                for p in params:
                    output.extend(struct.pack("<I", p))

            i += 4

        return bytes(output)


def compile_obj_to_display_list(obj_path: str, scale_factor: float = 1.0) -> Tuple[bytes, Dict[str, Any]]:
    """Lê um arquivo Wavefront OBJ e compila para Nitro Display List binária."""
    vertices = []
    normals = []
    texcoords = []
    faces = []

    with open(obj_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split()
            if parts[0] == "v":
                vertices.append([float(parts[1]) * scale_factor, float(parts[2]) * scale_factor, float(parts[3]) * scale_factor])
            elif parts[0] == "vn":
                normals.append([float(parts[1]), float(parts[2]), float(parts[3])])
            elif parts[0] == "vt":
                texcoords.append([float(parts[1]), float(parts[2])])
            elif parts[0] == "f":
                face_v = []
                for p in parts[1:]:
                    vals = p.split("/")
                    v_idx = int(vals[0]) - 1
                    vt_idx = int(vals[1]) - 1 if len(vals) > 1 and vals[1] else None
                    vn_idx = int(vals[2]) - 1 if len(vals) > 2 and vals[2] else None
                    face_v.append((v_idx, vt_idx, vn_idx))
                faces.append(face_v)

    builder = NitroDisplayListBuilder()
    builder.set_polygon_attr(light_mask=0x01, poly_mode=2, cull_back=True, alpha=31)  # Cel-Shading Toon mode

    # Agrupa triângulos e quads
    tris = [f for f in faces if len(f) == 3]
    quads = [f for f in faces if len(f) == 4]

    # Processa Triângulos
    if tris:
        builder.begin_vtxs(NitroDisplayListBuilder.PRIMITIVE_TRIANGLES)
        for face in tris:
            for v_idx, vt_idx, vn_idx in face:
                if vn_idx is not None and vn_idx < len(normals):
                    nx, ny, nz = normals[vn_idx]
                    builder.set_normal(nx, ny, nz)
                if vt_idx is not None and vt_idx < len(texcoords):
                    u, v = texcoords[vt_idx]
                    builder.set_texcoord(u, v)
                vx, vy, vz = vertices[v_idx]
                builder.set_vertex_16(vx, vy, vz)
            builder.poly_count += 1
        builder.end_vtxs()

    # Processa Quads
    if quads:
        builder.begin_vtxs(NitroDisplayListBuilder.PRIMITIVE_QUADS)
        for face in quads:
            for v_idx, vt_idx, vn_idx in face:
                if vn_idx is not None and vn_idx < len(normals):
                    nx, ny, nz = normals[vn_idx]
                    builder.set_normal(nx, ny, nz)
                if vt_idx is not None and vt_idx < len(texcoords):
                    u, v = texcoords[vt_idx]
                    builder.set_texcoord(u, v)
                vx, vy, vz = vertices[v_idx]
                builder.set_vertex_16(vx, vy, vz)
            builder.poly_count += 1
        builder.end_vtxs()

    dl_binary = builder.compile()
    stats = {
        "vertices": builder.vertex_count,
        "polygons": builder.poly_count,
        "byte_size": len(dl_binary),
        "triangles": len(tris),
        "quads": len(quads)
    }

    return dl_binary, stats
