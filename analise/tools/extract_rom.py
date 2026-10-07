"""Extrai arm9.bin, arm7.bin e os arquivos do NitroFS de uma ROM .nds (via ndspy).
Mostra também os dados do cabeçalho que importam para a análise."""
import os, sys
import ndspy.rom

def main(rom_path, out):
    rom = ndspy.rom.NintendoDSRom.fromFile(rom_path)
    os.makedirs(f'{out}/files', exist_ok=True)
    open(f'{out}/arm9.bin', 'wb').write(rom.arm9)
    open(f'{out}/arm7.bin', 'wb').write(rom.arm7)
    print(f'{rom.name.decode()} ({rom.idCode.decode()}) | ARM9 {len(rom.arm9):#x} bytes em '
          f'{rom.arm9RamAddress:#x}, entrada {rom.arm9EntryAddress:#x} | overlays: {len(rom.loadArm9Overlays())}')
    n = 0
    def walk(folder, prefix=''):
        nonlocal n
        for i, name in enumerate(folder.files):
            path = os.path.join(out, 'files', prefix, name)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            open(path, 'wb').write(rom.files[folder.firstID + i])
            n += 1
        for name, sub in folder.folders:
            walk(sub, os.path.join(prefix, name))
    walk(rom.filenames)
    print(f'{n} arquivos extraidos')

if __name__ == '__main__':
    main(*sys.argv[1:3])
