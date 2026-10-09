"""Som do Sonic Chronicles: lista, extrai e troca músicas do `sound_data.sdat`.

Uso:
  python3 som.py listar  <rom.nds>
  python3 som.py extrair <rom.nds> <pasta>
  python3 som.py trocar  <rom.nds> <musicas> <audio> <saida.nds> [opções]
  python3 som.py tons    <rom.nds> <saida.nds>
  python3 som.py qual    <gravacao.wav>

`tons` e `qual` descobrem onde cada stream toca: `tons` troca o stream N por um tom puro
de 300 + 100×N Hz (no lugar, então savestates da ROM original continuam valendo); jogue
essa ROM até a música que quer identificar, grave com `gravar_som.py`, e `qual` diz, a
cada segundo da gravação, qual tom (= qual stream) estava tocando.

`musicas` é o nome (ex.: battle_1) ou o número do stream (0 a 9); várias separadas por
vírgula recebem o mesmo áudio. `audio` é qualquer
arquivo que o ffmpeg abra (wav, mp3, ogg, flac...). Opções de `trocar`:
  --formato pcm8|pcm16   pcm8 é o que o jogo usa (padrão); pcm16 tem bem menos chiado
                         e ocupa o dobro
  --taxa N               amostras por segundo (padrão 16364, a do jogo; 32728 = o dobro)
  --loop S               segundo onde a repetição recomeça (padrão 0 = do começo);
                         --sem-loop para tocar uma vez só
  --volume DB            ganho extra em dB (padrão 0: o áudio é normalizado para a
                         mesma intensidade média das músicas originais)

Por que só os streams (por enquanto): as 10 músicas de batalha são STRM, áudio gravado
que o jogo lê do cartão aos poucos enquanto toca. Qualquer gravação vira um STRM, sem
mexer em código. As músicas de exploração são SSEQ (partitura + instrumentos), que
precisam de outro caminho (ver docs/SOM.md).

Nada do jogo é gravado fora da ROM de saída; os WAV de `extrair` são do jogo e não vão
para o Git. Requer: pip install ndspy numpy; ffmpeg no PATH (só para `trocar`).
"""
import struct
import subprocess
import sys
import wave

import numpy as np
import ndspy
import ndspy.soundArchive

ARQUIVO_SDAT = 'sound_data.sdat'
RELOGIO_DS = 16756991          # Hz; a taxa real do DS é RELOGIO_DS / 32 / tempo
RMS_ORIGINAL = 35 / 128        # intensidade média das músicas de batalha originais


# ----------------------------------------------------------------------------- ROM

def _u32(b, o):
    return struct.unpack_from('<I', b, o)[0]


def _arquivos(rom):
    """Lista (nome, índice) dos arquivos do NitroFS que ficam na raiz (o jogo só usa a raiz)."""
    fnt = _u32(rom, 0x40)
    primeiro = struct.unpack_from('<H', rom, fnt + 4)[0]
    o, i, saida = fnt + _u32(rom, fnt), primeiro, []
    while rom[o]:
        n = rom[o] & 0x7F
        if rom[o] & 0x80:      # subpasta: o jogo não tem, mas não quebra a contagem
            o += 1 + n + 2
            continue
        saida.append((rom[o + 1:o + 1 + n].decode('latin1'), i))
        o += 1 + n
        i += 1
    return saida


def achar(rom, nome):
    for n, i in _arquivos(rom):
        if n == nome:
            return i
    raise SystemExit(f'{nome} não está na ROM')


def ler_arquivo(rom, i):
    fat = _u32(rom, 0x48)
    ini, fim = struct.unpack_from('<II', rom, fat + 8 * i)
    return bytes(rom[ini:fim])


def crc16(dados):
    crc = 0xFFFF
    for b in dados:
        crc ^= b
        for _ in range(8):
            crc = (crc >> 1) ^ 0xA001 if crc & 1 else crc >> 1
    return crc


def trocar_arquivo(rom, i, novo):
    """Mesma regra do `replace_file` do engine (nds.rs): no lugar se couber, senão no fim
    do cartucho (alinhado em 0x200), que cresce para a próxima potência de 2. Atualiza a
    FAT, o tamanho usado (0x80), a capacidade (0x14) e o CRC16 do cabeçalho."""
    fat, n = _u32(rom, 0x48), _u32(rom, 0x4C) // 8
    ents = [struct.unpack_from('<II', rom, fat + 8 * k) for k in range(n)]
    usado = _u32(rom, 0x80)
    ini, fim = ents[i]
    limite = min([s for s, _ in ents if s >= fim and s > ini] + [usado])
    limite = min(limite, max(usado, fim))
    if ini + len(novo) <= limite:
        novo_ini, lugar = ini, 'no lugar'
    else:
        novo_ini, lugar = (usado + 0x1FF) & ~0x1FF, 'no fim do cartucho'
    novo_fim = novo_ini + len(novo)
    if novo_fim > len(rom):
        cap = 1 << (novo_fim - 1).bit_length()
        rom.extend(b'\xFF' * (cap - len(rom)))
    rom[novo_ini:novo_fim] = novo
    struct.pack_into('<II', rom, fat + 8 * i, novo_ini, novo_fim)
    if lugar != 'no lugar':
        struct.pack_into('<I', rom, 0x80, novo_fim)
    k = 0
    while (128 * 1024) << k < len(rom):
        k += 1
    rom[0x14] = k
    struct.pack_into('<H', rom, 0x15E, crc16(rom[:0x15E]))
    return lugar


# ----------------------------------------------------------------------------- SDAT

def abrir_sdat(rom):
    i = achar(rom, ARQUIVO_SDAT)
    return i, ndspy.soundArchive.SDAT(ler_arquivo(rom, i))


def achar_stream(sdat, musica):
    nomes = [n for n, _ in sdat.streams]
    if musica.isdigit() and int(musica) < len(nomes):
        return int(musica)
    if musica in nomes:
        return nomes.index(musica)
    raise SystemExit(f'stream "{musica}" não existe; os nomes são: {", ".join(nomes)}')


def pcm_do_stream(s):
    """Amostras em float (-1..1), uma linha por canal. Só PCM8/PCM16 (o que o jogo usa)."""
    canais = []
    for blocos in s.channels:
        dados = b''.join(blocos)
        if s.waveType == 0:
            canais.append(np.frombuffer(dados, dtype=np.int8).astype(np.float32) / 128)
        elif s.waveType == 1:
            canais.append(np.frombuffer(dados, dtype='<i2').astype(np.float32) / 32768)
        else:
            raise SystemExit('stream em ADPCM: o jogo original não tem nenhum')
    return np.array(canais)


def salvar_wav(arq, amostras, taxa):
    with wave.open(arq, 'wb') as w:
        w.setnchannels(amostras.shape[0])
        w.setsampwidth(2)
        w.setframerate(taxa)
        w.writeframes((np.clip(amostras.T, -1, 1) * 32767).astype('<i2').tobytes())


# ----------------------------------------------------------------------------- comandos

def listar(rom_arq):
    rom = bytearray(open(rom_arq, 'rb').read())
    _, s = abrir_sdat(rom)
    print('Streams (áudio gravado, lido do cartão enquanto toca):')
    for k, (nome, st) in enumerate(s.streams):
        tipo = {0: 'PCM8', 1: 'PCM16', 2: 'ADPCM'}[int(st.waveType)]
        n = sum(len(b) for b in st.channels[0]) // (2 if st.waveType == 1 else 1)
        print(f'  {k}  {nome:<14} {tipo} {len(st.channels)} canal {st.sampleRate} Hz '
              f'{n / st.sampleRate:6.1f} s  {"repete" if st.isLooped else "uma vez"}')
    print('Sequências (partitura tocada pelos instrumentos de um banco):')
    for k, (nome, sq) in enumerate(s.sequences):
        print(f'  {k:2}  {nome:<11} banco {sq.bankID} ({s.banks[sq.bankID][0]})')
    print(f'Efeitos: {len(s.sequenceArchives[0][1].sequences)} sequências em '
          f'{s.sequenceArchives[0][0]}, {len(s.waveArchives)} arquivos de amostras')


def extrair(rom_arq, pasta):
    import os
    os.makedirs(pasta, exist_ok=True)
    rom = bytearray(open(rom_arq, 'rb').read())
    _, s = abrir_sdat(rom)
    for k, (nome, st) in enumerate(s.streams):
        arq = os.path.join(pasta, f'stream{k}_{nome}.wav')
        salvar_wav(arq, pcm_do_stream(st), st.sampleRate)
        print(arq)


def ler_audio(arq, taxa):
    """Decodifica qualquer áudio para mono float na taxa pedida (ffmpeg faz a reamostragem)."""
    p = subprocess.run(['ffmpeg', '-v', 'error', '-i', arq, '-ac', '1', '-ar', str(taxa),
                        '-f', 's16le', '-'], capture_output=True)
    if p.returncode:
        raise SystemExit(f'ffmpeg não abriu {arq}: {p.stderr.decode(errors="replace")}')
    return np.frombuffer(p.stdout, dtype='<i2').astype(np.float32) / 32768


def _slot_do_stream(sdat, k):
    """(índice na FAT, início, tamanho, limite) do arquivo do stream k dentro do SDAT.
    O limite é onde começa o arquivo seguinte: até ali dá para gravar sem mover nada."""
    info, fat = _u32(sdat, 0x18), _u32(sdat, 0x20)
    lista = info + _u32(sdat, info + 8 + 4 * 7)           # 8ª lista do INFO = streams
    fid = struct.unpack_from('<H', sdat, info + _u32(sdat, lista + 4 + 4 * k))[0]
    n = _u32(sdat, fat + 8)
    ents = [struct.unpack_from('<II', sdat, fat + 12 + 16 * j) for j in range(n)]
    ini, tam = ents[fid]
    limite = min([o for o, _ in ents if o > ini] + [len(sdat)])
    return fat + 12 + 16 * fid, ini, tam, limite


def codificar(a, formato):
    if formato == 'pcm8':
        # ruído triangular de 1 bit antes de arredondar: troca o chiado "granulado" do
        # corte de 16 para 8 bits por um chiado constante, menos incômodo
        r = np.random.default_rng(0)
        d = (r.random(len(a)) - r.random(len(a))) / 127
        return np.round(np.clip(a + d, -1, 1) * 127).astype(np.int8).tobytes(), 0
    if formato == 'pcm16':
        return np.round(a * 32767).astype('<i2').tobytes(), 1
    raise SystemExit('--formato tem de ser pcm8 ou pcm16')


def trocar(rom_arq, musicas, audio_arq, saida, formato='pcm8', taxa=16364, loop=0.0,
           repetir=True, volume=0.0):
    rom = bytearray(open(rom_arq, 'rb').read())
    i_sdat, s = abrir_sdat(rom)
    sdat = bytearray(ler_arquivo(rom, i_sdat))
    tempo = round(RELOGIO_DS / 32 / taxa)   # o hardware só toca taxas = relógio / 32 / inteiro
    taxa = int(RELOGIO_DS / 32 / tempo)
    a = ler_audio(audio_arq, taxa)
    rms = float(np.sqrt(np.mean(a ** 2))) or 1.0
    a = a * (RMS_ORIGINAL / rms) * 10 ** (volume / 20)
    cortadas = float(np.mean(np.abs(a) > 1))
    dados, tipo = codificar(np.clip(a, -1, 1), formato)
    n = len(a)
    ks = [achar_stream(s, m) for m in musicas.split(',')]
    for k in ks:
        nome, st = s.streams[k]
        # Mesmo layout dos streams do jogo: 1 canal, 1 bloco só com o áudio inteiro.
        st.waveType = ndspy.WaveType(tipo)
        st.channels = [[dados]]
        st.sampleRate, st.time = taxa, tempo
        st.isLooped = repetir
        st.loopOffset = int(loop * taxa) if repetir else 0
        st.samplesPerBlock = st.samplesInLastBlock = n
        strm = st.save()[0]
        pos_fat, ini, tam, limite = _slot_do_stream(sdat, k)
        if ini + len(strm) <= limite:
            # cabe no espaço do antigo: grava ali e só corrige o tamanho na FAT do SDAT.
            # Nenhum outro arquivo anda, então o resto do SDAT fica igual byte a byte.
            sdat[ini:ini + len(strm)] = strm
            sdat[ini + len(strm):ini + tam] = bytes(max(0, tam - len(strm)))
            struct.pack_into('<I', sdat, pos_fat + 4, len(strm))
            como = 'no lugar do antigo'
        else:
            s = ndspy.soundArchive.SDAT(bytes(sdat))
            s.streams[k] = (nome, st)
            sdat = bytearray(s.save())
            como = 'SDAT remontado (os arquivos depois dele mudaram de posição)'
        s = ndspy.soundArchive.SDAT(bytes(sdat))
        print(f'stream {k} ({nome}): {n / taxa:.1f} s, {formato}, {taxa} Hz, '
              f'{len(dados) / 1e6:.2f} MB, {como}')
    lugar = trocar_arquivo(rom, i_sdat, bytes(sdat))
    open(saida, 'wb').write(rom)
    # confere: reabre a ROM gerada e lê cada stream de volta
    _, s2 = abrir_sdat(bytearray(open(saida, 'rb').read()))
    for k in ks:
        st2 = s2.streams[k][1]
        assert b''.join(st2.channels[0]) == dados and st2.sampleRate == taxa
    print(f'sound_data.sdat gravado {lugar}; ROM de {len(rom) // 2**20} MB; conferido')
    if cortadas > 0.001:
        print(f'aviso: {cortadas:.1%} das amostras passaram do máximo e foram cortadas; '
              'use --volume -3 (ou menos) se soar distorcido')


def tons(rom_arq, saida):
    rom = bytearray(open(rom_arq, 'rb').read())
    i_sdat, s = abrir_sdat(rom)
    sdat = bytearray(ler_arquivo(rom, i_sdat))
    for k, (nome, st) in enumerate(s.streams):
        _, ini, tam, _ = _slot_do_stream(sdat, k)
        dados = 0x68 + ini                      # o áudio começa logo depois do cabeçalho
        n = tam - 0x68
        if st.waveType != 0:
            raise SystemExit('esperava PCM8 (ROM original)')
        t = np.arange(n) / st.sampleRate
        sdat[dados:dados + n] = (np.sin(2 * np.pi * (300 + 100 * k) * t) * 90).astype(np.int8).tobytes()
        print(f'stream {k} ({nome}): {300 + 100 * k} Hz')
    trocar_arquivo(rom, i_sdat, bytes(sdat))
    open(saida, 'wb').write(rom)


def qual(gravacao):
    with wave.open(gravacao) as w:
        taxa, nc = w.getframerate(), w.getnchannels()
        a = np.frombuffer(w.readframes(w.getnframes()), dtype='<i2').reshape(-1, nc).mean(1)
    f = np.fft.rfftfreq(taxa, 1 / taxa)
    for k in range(0, len(a) - taxa, taxa):
        esp = np.abs(np.fft.rfft(a[k:k + taxa] * np.hanning(taxa)))
        achados = []
        for n in range(10):
            alvo = 300 + 100 * n
            pico = esp[(f > alvo - 3) & (f < alvo + 3)].max()
            fundo = np.median(esp[(f > alvo - 60) & (f < alvo + 60)]) + 1
            if pico / fundo > 1000:             # um tom puro sobra muito acima do resto
                achados.append(n)
        if achados:
            print(f'{k // taxa:5d} s: stream {", ".join(map(str, achados))}')


def main(args):
    if len(args) >= 2 and args[0] == 'listar':
        return listar(args[1])
    if len(args) >= 3 and args[0] == 'extrair':
        return extrair(args[1], args[2])
    if len(args) >= 3 and args[0] == 'tons':
        return tons(args[1], args[2])
    if len(args) >= 2 and args[0] == 'qual':
        return qual(args[1])
    if len(args) >= 5 and args[0] == 'trocar':
        pos, op = [], {}
        it = iter(args[1:])
        for a in it:
            if a == '--sem-loop':
                op['repetir'] = False
            elif a.startswith('--'):
                op[a[2:]] = next(it)
            else:
                pos.append(a)
        return trocar(*pos, formato=op.get('formato', 'pcm8'), taxa=int(op.get('taxa', 16364)),
                      loop=float(op.get('loop', 0)), repetir=op.get('repetir', True),
                      volume=float(op.get('volume', 0)))
    print(__doc__)
    sys.exit(2)


if __name__ == '__main__':
    main(sys.argv[1:])
