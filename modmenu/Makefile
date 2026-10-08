# Painel de controle (mod menu) do Sonic Chronicles.
#
# Compilador: o clang e o ld.lld do LLVM, que já geram código para o ARM9 do DS
# (ARM946E-S, arquitetura ARMv5TE) sem instalar devkitARM. Qualquer clang >= 14 serve.
#
#   make          compila o painel e a ROM de teste (build/painel_teste.nds)
#   make testar   roda a ROM de teste no DeSmuME (py-desmume) e confere tudo
#   make tamanho  mostra quanto o painel ocupa (código + dados + BSS)

CC      := clang
LD      := ld.lld
OBJCOPY := llvm-objcopy
SIZE    := llvm-size
PY      := python3

# -mthumb: instruções de 16 bits, o código fica ~30% menor (importa: no jogo o espaço
# livre é pouco). -ffreestanding/-nostdlib: sem biblioteca C, só o nosso código.
ALVO    := --target=armv5te-none-eabi -mcpu=arm946e-s
CFLAGS  := $(ALVO) -mthumb -Os -ffreestanding -fno-builtin -nostdlib \
           -ffunction-sections -fdata-sections -fno-unwind-tables -Wall -Wextra -Werror -Iinclude
ASFLAGS := $(ALVO)

B := build
PAINEL := $(B)/menu.o $(B)/console.o $(B)/fonte.o

all: $(B)/painel_teste.nds tamanho

$(B):
	mkdir -p $@

$(B)/%.o: src/%.c include/ds.h src/console.h | $(B)
	$(CC) $(CFLAGS) -c $< -o $@

$(B)/teste_main.o: teste/teste_main.c include/ds.h | $(B)
	$(CC) $(CFLAGS) -c $< -o $@

$(B)/crt0.o: teste/crt0.s | $(B)
	$(CC) $(ASFLAGS) -c $< -o $@

$(B)/arm7.o: teste/arm7.s | $(B)
	$(CC) $(ASFLAGS) -c $< -o $@

# O painel sozinho, como um objeto único: é isto que irá para dentro do jogo.
$(B)/painel.o: $(PAINEL)
	$(LD) -r --gc-sections -e modmenu_quadro $^ -o $@

$(B)/teste9.elf: $(B)/crt0.o $(B)/teste_main.o $(PAINEL) teste/link.ld
	$(LD) -T teste/link.ld --gc-sections $(filter %.o,$^) -o $@

$(B)/teste7.elf: $(B)/arm7.o teste/link7.ld
	$(LD) -T teste/link7.ld $< -o $@

$(B)/%.bin: $(B)/%.elf
	$(OBJCOPY) -O binary $< $@

$(B)/painel_teste.nds: $(B)/teste9.bin $(B)/teste7.bin ferramentas/mknds.py
	$(PY) ferramentas/mknds.py $(B)/teste9.bin $(B)/teste7.bin $@

tamanho: $(B)/painel.o
	@$(SIZE) -A $< | awk '$$1 ~ /^\.bss/ {b+=$$2} $$1 ~ /^\.(text|rodata|data)/ {c+=$$2} \
	  END {printf "painel: codigo+dados %d bytes, BSS %d bytes\n", c, b}'

testar: $(B)/painel_teste.nds
	SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy $(PY) ferramentas/testar.py $< $(B)/capturas

clean:
	rm -rf $(B)

.PHONY: all tamanho testar clean
