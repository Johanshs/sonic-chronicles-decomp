/* ROM de teste: tudo na RAM principal a partir de 0x02000000. */
ENTRY(_start)
SECTIONS
{
    . = 0x02000000;
    .text : { *(.crt0) *(.text*) *(.rodata*) *(.data*) }
    . = ALIGN(4);
    __bss_inicio = .;
    .bss : { *(.bss*) *(COMMON) }
    . = ALIGN(4);
    __bss_fim = .;
    __pilha_fim = 0x023FC000;
    /DISCARD/ : { *(.ARM.exidx*) *(.ARM.attributes*) *(.comment) }
}
