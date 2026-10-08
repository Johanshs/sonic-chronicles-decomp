/* O painel dentro do Sonic Chronicles (YWSE).
 *
 * O heap do jogo vai de 0x021B9500 (OS_GetInitArenaLo) até 0x023E0000
 * (OS_GetInitArenaHi, literal em 0x020d8c9c). O painel mora nos últimos 32 KB, e o
 * enxerto abaixa o fim do heap para 0x023D8000 (a v0.5 usava 16 KB; o painel cresceu).
 *
 * Por que no FIM, e não no começo (como na v0.2)? O jogo aloca a partir do começo do
 * heap. Se o começo muda, TODOS os objetos do heap mudam de lugar (na v0.2, 0x2EA0
 * bytes), e os cheats que usam endereços do heap (como o 0x021D10AC dos anéis) deixam
 * de funcionar na ROM com o painel. Tirando o espaço do fim, o começo fica igual ao do
 * jogo original e os endereços do heap também (conferido por testar_no_jogo.py). */
ENTRY(gancho)
SECTIONS
{
    . = 0x023D8000;
    __painel_inicio = .;
    .text : { *(.text.gancho) *(.text*) *(.rodata*) *(.data*) }
    . = ALIGN(4);
    __painel_fim_carregado = .;
    .bss (NOLOAD) : { *(.bss*) *(COMMON) }
    . = ALIGN(32);
    __painel_fim = .;
    /DISCARD/ : { *(.ARM.exidx*) *(.ARM.attributes*) *(.comment) }
}
ASSERT(__painel_fim <= 0x023E0000, "o painel passou de 32 KB: aumente o espaço ou enxugue o código")
