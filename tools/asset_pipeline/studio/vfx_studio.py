"""Estúdio de Efeitos Visuais (VFX) e Emissores de Partículas para Sonic Chronicles.

Gerencia:
1. Templates de emissores de partículas (.emit) para o motor Aurora / Nitro DS
2. Configurações de modos de transparência (alfa normal vs. aditivo / Additive_VFX)
3. Presets temáticos de efeitos para golpes POW, magias e impactos
"""

import json
import os
import struct
from typing import Dict, Any, List, Optional


# Presets canônicos do universo Sonic Chronicles
VFX_PRESETS = {
    "chaos_energy": {
        "name": "Chaos Energy",
        "blend_mode": "additive",
        "max_particles": 24,
        "lifespan_frames": 30,
        "emission_rate": 2.0,
        "color_start": [0, 255, 200, 31],   # Ciano esmeralda
        "color_end": [0, 100, 255, 0],      # Azul desvanecente
        "velocity_range": [-1.5, 1.5],
        "gravity": 0.05,
        "texture": "VFX_ChaosOrb",
        "description": "Explosão de partículas de energia do Chaos pulsante e brilhante."
    },
    "fire_burst": {
        "name": "Fire Burst",
        "blend_mode": "additive",
        "max_particles": 32,
        "lifespan_frames": 24,
        "emission_rate": 3.0,
        "color_start": [255, 200, 0, 31],   # Amarelo/Laranja brilhante
        "color_end": [255, 0, 0, 0],        # Vermelho esfumaçado
        "velocity_range": [-2.0, 2.0],
        "gravity": -0.1,                    # Fogo sobe
        "texture": "VFX_Flame",
        "description": "Labaredas e faíscas de fogo para golpes elementais."
    },
    "spin_dust": {
        "name": "Spin Dash Dust",
        "blend_mode": "alpha",
        "max_particles": 16,
        "lifespan_frames": 20,
        "emission_rate": 1.5,
        "color_start": [200, 180, 140, 25], # Poeira marrom/creme
        "color_end": [220, 200, 160, 0],
        "velocity_range": [-1.0, 1.0],
        "gravity": 0.02,
        "texture": "VFX_DustCloud",
        "description": "Nuvem de poeira e impacto clássica do Spin Dash do Sonic."
    },
    "electric_spark": {
        "name": "Electric Spark",
        "blend_mode": "additive",
        "max_particles": 20,
        "lifespan_frames": 15,
        "emission_rate": 2.5,
        "color_start": [255, 255, 255, 31], # Branco puro
        "color_end": [100, 200, 255, 0],    # Azul elétrico
        "velocity_range": [-3.0, 3.0],
        "gravity": 0.0,
        "texture": "VFX_Spark",
        "description": "Descargas e faíscas elétricas para robôs e ataques de choque."
    },
    "heal_sparkle": {
        "name": "Heal Sparkle",
        "blend_mode": "additive",
        "max_particles": 18,
        "lifespan_frames": 35,
        "emission_rate": 1.2,
        "color_start": [120, 255, 120, 31], # Verde regeneração
        "color_end": [255, 255, 180, 0],    # Dourado
        "velocity_range": [-0.8, 0.8],
        "gravity": -0.08,                   # Sobe suavemente
        "texture": "VFX_Star",
        "description": "Estrelas e brilhos ascendentes de cura e restauração de PP."
    },
    "psychic_cyan": {
        "name": "Psychic Cyan Spark",
        "blend_mode": "additive",
        "max_particles": 28,
        "lifespan_frames": 25,
        "emission_rate": 2.2,
        "color_start": [0, 229, 255, 31],   # Ciano vibrante do Silver
        "color_end": [0, 100, 180, 0],      # Azul turquesa suave
        "velocity_range": [-1.8, 1.8],
        "gravity": -0.05,                   # Flutua para cima (levitação)
        "texture": "VFX_PsychicGlow",
        "description": "Aura de telecinese e partículas de levitação psicocinética do Silver."
    },
    "stasis_shockwave": {
        "name": "ESP Stasis Shockwave",
        "blend_mode": "additive",
        "max_particles": 36,
        "lifespan_frames": 30,
        "emission_rate": 3.0,
        "color_start": [0, 255, 220, 31],   # Turquesa claro
        "color_end": [30, 80, 180, 0],      # Azul vácuo
        "velocity_range": [-2.5, 2.5],
        "gravity": 0.0,
        "texture": "VFX_RingWave",
        "description": "Onda de choque em anel desacelerando a iniciativa dos inimigos."
    },
    "psycho_shield": {
        "name": "Telekinetic Barrier",
        "blend_mode": "additive",
        "max_particles": 22,
        "lifespan_frames": 35,
        "emission_rate": 1.5,
        "color_start": [94, 234, 212, 31],  # Esmeralda menta
        "color_end": [0, 160, 210, 0],      # Ciano reflexivo
        "velocity_range": [-0.5, 0.5],
        "gravity": 0.0,
        "texture": "VFX_HexBarrier",
        "description": "Cúpula de força hexagonal que absorve impactos e reflete projéteis."
    },
    "meteor_spin": {
        "name": "Meteor Spin Vortex",
        "blend_mode": "additive",
        "max_particles": 40,
        "lifespan_frames": 22,
        "emission_rate": 3.5,
        "color_start": [0, 180, 255, 31],   # Azul Sonic + Ciano Silver
        "color_end": [180, 100, 30, 0],     # Fragmentos rochosos incandescentes
        "velocity_range": [-3.0, 3.0],
        "gravity": 0.08,
        "texture": "VFX_SpinDebris",
        "description": "Vórtice supersônico combinando Spin Dash com detritos telecinéticos."
    },
    "event_horizon": {
        "name": "Event Horizon Singularity",
        "blend_mode": "additive",
        "max_particles": 48,
        "lifespan_frames": 40,
        "emission_rate": 4.0,
        "color_start": [255, 255, 255, 31], # Branco estelar central
        "color_end": [40, 0, 90, 0],        # Roxo escuro vácuo cósmico
        "velocity_range": [-2.0, 2.0],
        "gravity": 0.20,                    # Colapso gravitacional em direção ao centro
        "texture": "VFX_Singularity",
        "description": "Micro-buraco negro atraindo matéria antes da detonação supernova."
    },
}


class VfxStudio:
    def __init__(self, out_dir: Optional[str] = None):
        self.out_dir = out_dir or "."

    def list_presets(self) -> List[str]:
        return list(VFX_PRESETS.keys())

    def get_preset(self, preset_key: str) -> Optional[Dict[str, Any]]:
        return VFX_PRESETS.get(preset_key)

    def create_emitter_definition(
        self,
        preset_key: str,
        custom_name: Optional[str] = None,
        custom_texture: Optional[str] = None
    ) -> Dict[str, Any]:
        """Gera uma definição estruturada de emissor de partículas."""
        preset = VFX_PRESETS.get(preset_key)
        if not preset:
            raise ValueError(f"Preset desconhecido: {preset_key}. Opções: {list(VFX_PRESETS.keys())}")

        definition = dict(preset)
        if custom_name:
            definition["name"] = custom_name
        if custom_texture:
            definition["texture"] = custom_texture

        return definition

    def export_emitter_json(self, definition: Dict[str, Any], filepath: str) -> str:
        """Salva definição de emissor em JSON legível."""
        os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(definition, f, indent=2, ensure_ascii=False)
        return filepath

    def export_emitter_binary(self, definition: Dict[str, Any], filepath: str) -> str:
        """Gera binário compacto de emissor (.emit).

        Layout binário (.emit):
        - u32 magic: b'EMIT' (0x54494D45)
        - u32 version: 1
        - u16 max_particles
        - u16 lifespan_frames
        - u8 blend_mode: 0 = alpha, 1 = additive
        - u8 pad
        - f32 emission_rate
        - f32 gravity
        - 4 x u8 color_start (RGBA 0-31)
        - 4 x u8 color_end (RGBA 0-31)
        - char texture_name[32] (null-padded)
        """
        magic = b"EMIT"
        version = 1
        max_particles = definition.get("max_particles", 20)
        lifespan = definition.get("lifespan_frames", 30)
        blend = 1 if definition.get("blend_mode") == "additive" else 0
        emission = float(definition.get("emission_rate", 2.0))
        gravity = float(definition.get("gravity", 0.0))

        c_start = definition.get("color_start", [255, 255, 255, 31])
        c_end = definition.get("color_end", [255, 255, 255, 0])

        # Converte para canal 5-bit (0-31)
        c_start_5b = [c_start[0] >> 3, c_start[1] >> 3, c_start[2] >> 3, c_start[3] & 0x1F]
        c_end_5b = [c_end[0] >> 3, c_end[1] >> 3, c_end[2] >> 3, c_end[3] & 0x1F]

        tex_bytes = definition.get("texture", "default").encode("ascii", errors="replace")[:31]
        tex_padded = tex_bytes.ljust(32, b"\x00")

        header = struct.pack(
            "<4sIHHBBff4B4B32s",
            magic,
            version,
            max_particles,
            lifespan,
            blend,
            0,
            emission,
            gravity,
            *c_start_5b,
            *c_end_5b,
            tex_padded
        )

        os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)
        with open(filepath, "wb") as f:
            f.write(header)

        return filepath
