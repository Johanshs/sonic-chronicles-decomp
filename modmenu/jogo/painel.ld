/* O painel dentro do Sonic Chronicles (YWSE).
 *
 * 0x021B9500 é onde o BSS do ARM9 termina e o heap do jogo começaria (OS_GetInitArenaLo,
 * 0x020d8cbc). O enxerto empurra o começo do heap para depois do painel, então este
 * espaço passa a ser só nosso. */
ENTRY(gancho)
SECTIONS
{
    . = 0x021B9500;
    .text : { *(.text.gancho) *(.text*) *(.rodata*) *(.data*) }
    . = ALIGN(4);
    __painel_fim_carregado = .;
    .bss (NOLOAD) : { *(.bss*) *(COMMON) }
    . = ALIGN(32);
    __painel_fim = .;
    /DISCARD/ : { *(.ARM.exidx*) *(.ARM.attributes*) *(.comment) }
}
