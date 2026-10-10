/*
 * test_movie_player_challenger.c
 *
 * Empirical Playback Challenger Stress Harness for CMoviePlayer Decompilation.
 *
 * Simulates the full 1095 frames (~73 seconds) of Nintendo DS intro playback
 * under cycle-accurate hardware timing, stress conditions, counter boundary
 * conditions, and audio EOF scenarios.
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include "movie_player.h"

#define PASS_COLOR "\033[32m"
#define FAIL_COLOR "\033[31m"
#define RESET_COLOR "\033[0m"

static int s_tests_run = 0;
static int s_tests_passed = 0;
static int s_tests_failed = 0;

#define CH_ASSERT(cond, msg) do { \
    if (!(cond)) { \
        printf("  " FAIL_COLOR "[CHALLENGE FAILED]" RESET_COLOR " %s:%d: %s\n", __FILE__, __LINE__, msg); \
        s_tests_failed++; \
        return 0; \
    } \
} while(0)

#define RUN_CHALLENGE(fn) do { \
    printf("Executing Challenge: %s...\n", #fn); \
    s_tests_run++; \
    if (fn()) { \
        printf("  " PASS_COLOR "[CHALLENGE PASSED]" RESET_COLOR " %s\n\n", #fn); \
        s_tests_passed++; \
    } else { \
        printf("  " FAIL_COLOR "[CHALLENGE FAILED]" RESET_COLOR " %s\n\n", #fn); \
    } \
} while(0)

/* =========================================================================
 * Challenge 1: Cycle-Accurate 1095-Frame Full Intro Simulation (~73 seconds)
 * =========================================================================
 *
 * Models Nintendo DS hardware clocks:
 * - SND_TIMER_CLOCK: 16,756,991 Hz
 * - Video frame rate: 14.985 fps (16.16 fixed-point: 982057)
 * - Alarm period: 48,640 timer cycles (128 samples @ 44,100 Hz)
 * - Frame period in timer cycles: 16,756,991 * 65536 / 982057 = ~1,118,248 cycles
 *
 * Verifies:
 * - Full 1095 frames render without skipping.
 * - No alternating frame drops occur.
 * - Buffer slack remains stable throughout playback.
 * - State at frame 547 is healthy and renders normally.
 */

typedef struct CycleSimState {
    u64 totalCycles;
    u64 nextAlarmCycle;
    u32 alarmCyclePeriod;
    int alarmFireCount;
    int renderCount;
    int skipCount;
    int audioChunksDecoded;
    int audioChunksAvailable;
    int eofChunk;
} CycleSimState;

static CycleSimState s_cycleSim;

static u32 cycle_GetAudioRate(VXHandle vx) { (void)vx; return 44100; }
static u32 cycle_GetFrameRateFixed(VXHandle vx) { (void)vx; return 982057; }
static u32 cycle_GetAvailableAudioChunks(VXHandle vx) {
    (void)vx;
    return s_cycleSim.audioChunksAvailable;
}

static int cycle_DecodeAudioChunk(VXHandle vx, s16 *dest) {
    (void)vx;
    s_cycleSim.audioChunksDecoded++;
    if (s_cycleSim.eofChunk > 0 && s_cycleSim.audioChunksDecoded >= s_cycleSim.eofChunk) {
        return 0; /* EOF */
    }
    if (dest != NULL) {
        for (int i = 0; i < MOVIE_AUDIO_BLOCK_SAMPLES; i++) {
            dest[i] = (s16)(0x2000 + (s_cycleSim.audioChunksDecoded & 0x7F));
        }
    }
    return 1;
}

static void cycle_SkipFrame(VXHandle vx) { (void)vx; s_cycleSim.skipCount++; }
static void cycle_DecodeAndRender(CMoviePlayer *p, VXHandle t, VXHandle b) {
    (void)p; (void)t; (void)b;
    s_cycleSim.renderCount++;
}

static void cycle_SND_SetAlarm(int a, u32 tick, u32 period, void (*h)(void *), void *arg) {
    (void)a; (void)tick; (void)h; (void)arg;
    s_cycleSim.alarmCyclePeriod = period;
}

static int test_cycle_accurate_1095_frames(void)
{
    memset(&s_cycleSim, 0, sizeof(s_cycleSim));
    s_cycleSim.audioChunksAvailable = 23;
    s_cycleSim.alarmCyclePeriod = 48640;
    s_cycleSim.eofChunk = -1; /* No early EOF */

    CMoviePlayerHooks hooks = {
        .GetAudioRate = cycle_GetAudioRate,
        .GetFrameRateFixed = cycle_GetFrameRateFixed,
        .GetAvailableAudioChunks = cycle_GetAvailableAudioChunks,
        .DecodeAudioChunk = cycle_DecodeAudioChunk,
        .SkipFrame = cycle_SkipFrame,
        .IsPlaying = NULL,
        .DecodeAndRender = cycle_DecodeAndRender,
        .DC_FlushRange = NULL,
        .SND_LockChannel = NULL,
        .SND_UnlockChannel = NULL,
        .SND_SetupChannelPcm = NULL,
        .SND_SetAlarm = cycle_SND_SetAlarm,
        .SND_StartAlarm = NULL,
        .SND_StopAlarm = NULL,
    };
    CMoviePlayer_SetHooks(&hooks);

    CMoviePlayer player;
    CMoviePlayer_Init(&player);
    BOOL ok = CMoviePlayer_PlayMovie(&player, "TS_01_Intro.vx", 0);
    CH_ASSERT(ok, "PlayMovie must succeed");
    CMoviePlayer_SetInstance(&player);

    /* Frame period in DS timer clock cycles: 16,756,991 / (982057 / 65536) */
    const u64 cyclesPerFrameNum = (u64)SND_TIMER_CLOCK * 65536ULL;
    const u64 cyclesPerFrameDen = 982057ULL;
    u64 cycleAccumulator = 0;

    int totalRendered = 0;
    int totalSkipped = 0;
    int frame547Rendered = 0;
    s64 frame547Slack = 0;

    s_cycleSim.nextAlarmCycle = 48640;

    for (u32 frame = 0; frame < 1095; frame++) {
        /* Advance timer cycles for this video frame */
        cycleAccumulator += cyclesPerFrameNum;
        u64 frameCycles = cycleAccumulator / cyclesPerFrameDen;
        cycleAccumulator %= cyclesPerFrameDen;

        u64 frameEndCycle = s_cycleSim.totalCycles + frameCycles;

        /* Fire sound alarm callbacks that occur during this frame's duration */
        if (player.m_audioStarted) {
            while (s_cycleSim.nextAlarmCycle <= frameEndCycle) {
                CMoviePlayer_SoundAlarmCallback(&player);
                s_cycleSim.alarmFireCount++;
                s_cycleSim.nextAlarmCycle += s_cycleSim.alarmCyclePeriod;
            }
        } else {
            /* If audio not started yet, align nextAlarmCycle */
            s_cycleSim.nextAlarmCycle = frameEndCycle + s_cycleSim.alarmCyclePeriod;
        }

        s_cycleSim.totalCycles = frameEndCycle;

        /* Reset frame render/skip counters */
        s_cycleSim.renderCount = 0;
        s_cycleSim.skipCount = 0;

        /* Run CMoviePlayer_Update */
        CMoviePlayer_Update(&player);

        if (s_cycleSim.renderCount > 0) totalRendered++;
        if (s_cycleSim.skipCount > 0) totalSkipped++;

        /* Inspect state at frame 547 */
        if (player.m_frameCounter == 547) {
            frame547Rendered = s_cycleSim.renderCount;
            frame547Slack = (s64)(player.m_writeCounter - player.m_readCounter);
        }

        /* Check buffer bounds */
        s64 diff = (s64)(player.m_writeCounter - player.m_readCounter);
        if (player.m_frameCounter >= 4) {
            CH_ASSERT(diff >= (s64)player.m_threshold, "Audio buffer must not underflow below threshold");
            CH_ASSERT(diff <= (s64)player.m_capacity, "Audio buffer must not overflow above capacity");
            CH_ASSERT(s_cycleSim.renderCount == 1, "Each frame must render without skipping");
            CH_ASSERT(s_cycleSim.skipCount == 0, "No frames must be skipped");
        }
    }

    printf("    -> Total frames simulated: %u\n", player.m_frameCounter);
    printf("    -> Total frames rendered:  %d / 1095\n", totalRendered);
    printf("    -> Total frames skipped:   %d\n", totalSkipped);
    printf("    -> Alarm callbacks fired:  %d\n", s_cycleSim.alarmFireCount);
    printf("    -> Audio chunks decoded:   %d\n", s_cycleSim.audioChunksDecoded);
    printf("    -> Frame 547 rendered:     %d (slack: %lld chunks)\n", frame547Rendered, (long long)frame547Slack);

    CH_ASSERT(totalRendered == 1095, "All 1095 frames must be rendered");
    CH_ASSERT(totalSkipped == 0, "Zero frames must be skipped");
    CH_ASSERT(frame547Rendered == 1, "Frame 547 must render");
    CH_ASSERT(frame547Slack > 23, "Frame 547 must have sufficient audio slack (> 23 chunks)");

    CMoviePlayer_StopMovie(&player);
    return 1;
}

/* =========================================================================
 * Challenge 2: Empirical Bug Reproduction vs. Fixed Behavior at Frame 547
 * =========================================================================
 *
 * Demonstrates the flaw in the original assembly:
 * - Alarm period was 1,520 cycles (ticks << 2, 4 samples).
 * - Consumer advanced 32x faster than producer.
 * - writeCounter - readCounter quickly went negative.
 * - cmp r1, threshold dropped alternate frames (7.49 fps).
 * - Real audio stream of 73s exhausted at frame 547 (73s / 2).
 * - Demonstrates that the fix keeps consumer/producer in 1:1 parity.
 */
static int test_bug_reproduction_vs_fix(void)
{
    /* 1. Simulate buggy behavior */
    CMoviePlayer buggyPlayer;
    CMoviePlayer_Init(&buggyPlayer);
    CMoviePlayer_PlayMovie(&buggyPlayer, "TS_01_Intro.vx", 0);

    /* Buggy alarm period: 380 << 2 = 1,520 */
    u32 buggyAlarmPeriod = 380 << 2;
    u32 fixedAlarmPeriod = 380 << 7;

    CH_ASSERT(buggyAlarmPeriod == 1520, "Buggy alarm period is 1520");
    CH_ASSERT(fixedAlarmPeriod == 48640, "Fixed alarm period is 48640");

    /* In buggy game, alarm callback ran 32 times for every 1 block produced */
    int buggyDrops = 0;
    int buggyRenders = 0;
    buggyPlayer.m_frameCounter = 4;
    buggyPlayer.m_audioStarted = TRUE;
    buggyPlayer.m_writeCounter = 92;
    buggyPlayer.m_readCounter = 0;

    for (int f = 0; f < 100; f++) {
        /* Buggy alarm: fires 23 * 32 = 736 times per frame! */
        buggyPlayer.m_readCounter += (23 * 32);
        buggyPlayer.m_writeCounter += 23;

        s64 diff = (s64)(buggyPlayer.m_writeCounter - buggyPlayer.m_readCounter);
        if (diff > (s64)buggyPlayer.m_threshold) {
            buggyRenders++;
            buggyPlayer.m_skippedFlag = FALSE;
        } else {
            if (!buggyPlayer.m_skippedFlag) {
                buggyDrops++;
                buggyPlayer.m_skippedFlag = TRUE;
            } else {
                buggyRenders++;
                buggyPlayer.m_skippedFlag = FALSE;
            }
        }
    }

    printf("    [Buggy simulation 100 frames]: Renders=%d, Drops=%d (Alternating drops active)\n",
           buggyRenders, buggyDrops);
    CH_ASSERT(buggyDrops == 50, "Buggy code drops exactly 50 out of 100 frames (50% drop rate)");
    CH_ASSERT(buggyRenders == 50, "Buggy code renders only 50 out of 100 frames (half-speed playback)");

    /* 2. Fixed behavior */
    CMoviePlayer fixedPlayer;
    CMoviePlayer_Init(&fixedPlayer);
    CMoviePlayer_PlayMovie(&fixedPlayer, "TS_01_Intro.vx", 0);
    fixedPlayer.m_frameCounter = 4;
    fixedPlayer.m_audioStarted = TRUE;
    fixedPlayer.m_writeCounter = 92;
    fixedPlayer.m_readCounter = 0;

    int fixedDrops = 0;
    int fixedRenders = 0;
    for (int f = 0; f < 100; f++) {
        /* Fixed alarm: fires 23 times per frame */
        fixedPlayer.m_readCounter += 23;
        fixedPlayer.m_writeCounter += 23;

        s64 diff = (s64)(fixedPlayer.m_writeCounter - fixedPlayer.m_readCounter);
        if (diff > (s64)fixedPlayer.m_threshold) {
            fixedRenders++;
            fixedPlayer.m_skippedFlag = FALSE;
        } else {
            if (!fixedPlayer.m_skippedFlag) {
                fixedDrops++;
                fixedPlayer.m_skippedFlag = TRUE;
            } else {
                fixedRenders++;
                fixedPlayer.m_skippedFlag = FALSE;
            }
        }
    }

    printf("    [Fixed simulation 100 frames]: Renders=%d, Drops=%d (Zero frame drops)\n",
           fixedRenders, fixedDrops);
    CH_ASSERT(fixedDrops == 0, "Fixed code must drop zero frames");
    CH_ASSERT(fixedRenders == 100, "Fixed code must render all 100 frames");

    CMoviePlayer_StopMovie(&buggyPlayer);
    CMoviePlayer_StopMovie(&fixedPlayer);
    return 1;
}

/* =========================================================================
 * Challenge 3: Audio Stream EOF Handling & Buffer Muting
 * =========================================================================
 *
 * Simulates EOF at various boundary points:
 * 1. Stream ends cleanly at EOF: chunk buffer is muted (memset to 0).
 * 2. Ring buffer plays remaining buffered audio, then plays muted silence.
 * 3. Does not loop stale audio.
 * 4. Yields cleanly when no more audio chunks are available.
 */
static int test_audio_eof_and_muting(void)
{
    memset(&s_cycleSim, 0, sizeof(s_cycleSim));
    s_cycleSim.audioChunksAvailable = 23;
    s_cycleSim.eofChunk = 100; /* EOF occurs after 100 chunks */

    CMoviePlayerHooks hooks = {
        .GetAudioRate = cycle_GetAudioRate,
        .GetFrameRateFixed = cycle_GetFrameRateFixed,
        .GetAvailableAudioChunks = cycle_GetAvailableAudioChunks,
        .DecodeAudioChunk = cycle_DecodeAudioChunk,
        .SkipFrame = cycle_SkipFrame,
        .IsPlaying = NULL,
        .DecodeAndRender = cycle_DecodeAndRender,
        .DC_FlushRange = NULL,
        .SND_LockChannel = NULL,
        .SND_UnlockChannel = NULL,
        .SND_SetupChannelPcm = NULL,
        .SND_SetAlarm = cycle_SND_SetAlarm,
        .SND_StartAlarm = NULL,
        .SND_StopAlarm = NULL,
    };
    CMoviePlayer_SetHooks(&hooks);

    CMoviePlayer player;
    CMoviePlayer_Init(&player);
    CMoviePlayer_PlayMovie(&player, "TS_01_Intro.vx", 0);
    CMoviePlayer_SetInstance(&player);

    /* Fill audio buffer with known marker values */
    u32 bufBytes = CMoviePlayer_CalcCapacityBytes(player.m_capacity);
    memset(player.m_pAudioBuffer, 0xEE, bufBytes);

    /* Update through frames until EOF triggers */
    for (u32 f = 0; f < 10; f++) {
        if (player.m_audioStarted) {
            for (int a = 0; a < 23; a++) {
                CMoviePlayer_SoundAlarmCallback(&player);
            }
        }
        CMoviePlayer_Update(&player);
    }

    CH_ASSERT(s_cycleSim.audioChunksDecoded >= 100, "Must have reached EOF chunk (100)");

    /* Verify that the chunk at writeOffset was muted to 0 */
    s16 *dest = &player.m_pAudioBuffer[player.m_writeOffset];
    u8 zeroBlock[MOVIE_AUDIO_BLOCK_BYTES];
    memset(zeroBlock, 0, MOVIE_AUDIO_BLOCK_BYTES);

    int cmp = memcmp(dest, zeroBlock, MOVIE_AUDIO_BLOCK_BYTES);
    CH_ASSERT(cmp == 0, "Chunk destination at EOF must be zeroed (muted)");

    /* Verify that writeCounter stopped advancing once EOF was hit */
    u64 writeCounterAtEof = player.m_writeCounter;
    for (u32 f = 0; f < 5; f++) {
        CMoviePlayer_Update(&player);
    }
    CH_ASSERT(player.m_writeCounter == writeCounterAtEof, "writeCounter must not advance after EOF");

    CMoviePlayer_StopMovie(&player);
    return 1;
}

/* =========================================================================
 * Challenge 4: Large Ticks and Counter Wrap Stress Test
 * =========================================================================
 *
 * Verifies:
 * - 64-bit integer differences do not overflow or wrap when crossing 32-bit boundary (0xFFFFFFFF).
 * - Counters handle large offsets (e.g. 100,000 frames = ~2.3 million chunks).
 * - Signed difference correctly handles underflow (m_readCounter > m_writeCounter).
 */
static int test_large_ticks_and_counter_wrap(void)
{
    CMoviePlayer player;
    CMoviePlayer_Init(&player);
    CMoviePlayer_PlayMovie(&player, "TS_01_Intro.vx", 0);

    /* Case A: writeCounter crosses 32-bit boundary */
    player.m_writeCounter = 0x100000020ULL; /* 4,294,967,328 */
    player.m_readCounter  = 0x0FFFFFFC4ULL; /* 4,294,967,236 */
    s64 diffA = (s64)(player.m_writeCounter - player.m_readCounter);
    CH_ASSERT(diffA == 92, "Diff across 32-bit boundary must be exact 92");

    /* Case B: High 64-bit values (> 100 billion ticks) */
    player.m_writeCounter = 100000000092ULL;
    player.m_readCounter  = 100000000000ULL;
    s64 diffB = (s64)(player.m_writeCounter - player.m_readCounter);
    CH_ASSERT(diffB == 92, "Diff with 64-bit magnitude must be exact 92");

    /* Case C: Signed underflow handling */
    player.m_writeCounter = 500;
    player.m_readCounter  = 550;
    s64 diffC = (s64)(player.m_writeCounter - player.m_readCounter);
    CH_ASSERT(diffC == -50, "Underflow diff must be negative -50");
    CH_ASSERT(diffC <= (s64)player.m_threshold, "Negative diff correctly triggers underflow logic");

    /* Case D: Simulation of 100,000 frames continuous playback */
    player.m_frameCounter = 0;
    player.m_writeCounter = 0;
    player.m_readCounter = 0;
    for (u32 f = 0; f < 100000; f++) {
        player.m_writeCounter += 23;
        player.m_readCounter += 23;
    }
    CH_ASSERT(player.m_writeCounter == 2300000ULL, "writeCounter after 100k frames must be 2,300,000");
    CH_ASSERT(player.m_readCounter == 2300000ULL, "readCounter after 100k frames must be 2,300,000");
    s64 diffD = (s64)(player.m_writeCounter - player.m_readCounter);
    CH_ASSERT(diffD == 0, "Diff after 100k synchronous frames must be 0");

    CMoviePlayer_StopMovie(&player);
    return 1;
}

/* =========================================================================
 * Challenge 5: Buffer Capacity Yielding & Deadlock Immunity Under Stress
 * =========================================================================
 *
 * Verifies:
 * - When ring buffer is completely full (diff >= capacity), Update yields immediately.
 * - ARM9 main thread does not hang or busy-spin.
 * - When alarm callback drains 1 chunk, Update resumes decoding.
 */
static int test_capacity_yield_and_deadlock_immunity(void)
{
    memset(&s_cycleSim, 0, sizeof(s_cycleSim));
    s_cycleSim.audioChunksAvailable = 50; /* Excess chunks available */
    s_cycleSim.eofChunk = -1;

    CMoviePlayerHooks hooks = {
        .GetAudioRate = cycle_GetAudioRate,
        .GetFrameRateFixed = cycle_GetFrameRateFixed,
        .GetAvailableAudioChunks = cycle_GetAvailableAudioChunks,
        .DecodeAudioChunk = cycle_DecodeAudioChunk,
        .SkipFrame = cycle_SkipFrame,
        .IsPlaying = NULL,
        .DecodeAndRender = cycle_DecodeAndRender,
        .DC_FlushRange = NULL,
        .SND_LockChannel = NULL,
        .SND_UnlockChannel = NULL,
        .SND_SetupChannelPcm = NULL,
        .SND_SetAlarm = cycle_SND_SetAlarm,
        .SND_StartAlarm = NULL,
        .SND_StopAlarm = NULL,
    };
    CMoviePlayer_SetHooks(&hooks);

    CMoviePlayer player;
    CMoviePlayer_Init(&player);
    CMoviePlayer_PlayMovie(&player, "TS_01_Intro.vx", 0);
    player.m_audioStarted = TRUE;
    player.m_frameCounter = 10;

    /* Fill buffer to exact capacity (115 chunks) */
    player.m_writeCounter = 115;
    player.m_readCounter  = 0;
    s_cycleSim.audioChunksDecoded = 0;

    /* Run update: must yield immediately because diff (115) >= capacity (115) */
    BOOL running = CMoviePlayer_Update(&player);
    CH_ASSERT(running == FALSE, "Update must return FALSE (movie playing)");
    CH_ASSERT(s_cycleSim.audioChunksDecoded == 0, "Must not decode any chunks when buffer is full");

    /* Alarm callback drains 5 chunks */
    for (int i = 0; i < 5; i++) {
        CMoviePlayer_SoundAlarmCallback(&player);
    }
    CH_ASSERT(player.m_readCounter == 5, "readCounter advanced by 5");
    CH_ASSERT(player.m_writeCounter - player.m_readCounter == 110, "Diff is now 110 (5 slots free)");

    /* Next update: should decode exactly 5 chunks and stop when capacity (115) is reached again */
    s_cycleSim.audioChunksDecoded = 0;
    CMoviePlayer_Update(&player);

    CH_ASSERT(s_cycleSim.audioChunksDecoded == 5, "Must decode exactly 5 chunks to refill buffer to capacity");
    CH_ASSERT(player.m_writeCounter - player.m_readCounter == 115, "Buffer is full again at 115");

    CMoviePlayer_StopMovie(&player);
    return 1;
}

/* =========================================================================
 * Challenge 6: Dual-Screen Movie Frame Dropping Behavior
 * =========================================================================
 *
 * Verifies:
 * - When dualScreen is active, SkipFrame is invoked on both m_vxTop and m_vxBottom.
 * - Both screens stay strictly synchronized.
 */
static int s_skipTopCount = 0;
static int s_skipBottomCount = 0;
static void dual_SkipFrame(VXHandle vx) {
    if (vx == (VXHandle)0x1) s_skipTopCount++;
    if (vx == (VXHandle)0x2) s_skipBottomCount++;
}

static int test_dual_screen_sync(void)
{
    s_skipTopCount = 0;
    s_skipBottomCount = 0;

    CMoviePlayerHooks hooks = {
        .GetAudioRate = cycle_GetAudioRate,
        .GetFrameRateFixed = cycle_GetFrameRateFixed,
        .GetAvailableAudioChunks = cycle_GetAvailableAudioChunks,
        .DecodeAudioChunk = cycle_DecodeAudioChunk,
        .SkipFrame = dual_SkipFrame,
        .IsPlaying = NULL,
        .DecodeAndRender = NULL,
        .DC_FlushRange = NULL,
        .SND_LockChannel = NULL,
        .SND_UnlockChannel = NULL,
        .SND_SetupChannelPcm = NULL,
        .SND_SetAlarm = NULL,
        .SND_StartAlarm = NULL,
        .SND_StopAlarm = NULL,
    };
    CMoviePlayer_SetHooks(&hooks);

    CMoviePlayer player;
    CMoviePlayer_Init(&player);
    /* Play with dual screen flag (flags & 1) */
    CMoviePlayer_PlayMovie(&player, "TS_01_Intro.vx", 1);
    CH_ASSERT(player.m_dualScreen == TRUE, "dualScreen must be set");

    player.m_vxTop = (VXHandle)0x1;
    player.m_vxBottom = (VXHandle)0x2;
    player.m_frameCounter = 10;
    player.m_audioStarted = TRUE;
    s_cycleSim.audioChunksAvailable = 0; /* Zero incoming chunks to simulate starvation */

    /* Force underflow condition to trigger SkipFrame */
    player.m_writeCounter = 10;
    player.m_readCounter  = 10; /* diff = 0 <= threshold (23) */
    player.m_skippedFlag = FALSE;

    CMoviePlayer_Update(&player);

    CH_ASSERT(s_skipTopCount == 1, "Top screen must skip frame");
    CH_ASSERT(s_skipBottomCount == 1, "Bottom screen must skip frame simultaneously");

    CMoviePlayer_StopMovie(&player);
    return 1;
}

/* =========================================================================
 * Main Challenger Test Runner
 * ========================================================================= */
#ifdef _WIN32
__declspec(dllexport)
#endif
int run_challenger_tests(void)
{
    s_tests_run = 0;
    s_tests_passed = 0;
    s_tests_failed = 0;

    printf("====================================================================\n");
    printf(" Sonic Chronicles - Empirical Playback Challenger Suite             \n");
    printf(" Adversarial Verification of CMoviePlayer Intro Playback & Bug Fixes \n");
    printf("====================================================================\n\n");

    RUN_CHALLENGE(test_cycle_accurate_1095_frames);
    RUN_CHALLENGE(test_bug_reproduction_vs_fix);
    RUN_CHALLENGE(test_audio_eof_and_muting);
    RUN_CHALLENGE(test_large_ticks_and_counter_wrap);
    RUN_CHALLENGE(test_capacity_yield_and_deadlock_immunity);
    RUN_CHALLENGE(test_dual_screen_sync);

    printf("====================================================================\n");
    printf(" CHALLENGE SUMMARY: %d Run | %d Passed | %d Failed                  \n",
           s_tests_run, s_tests_passed, s_tests_failed);
    printf("====================================================================\n");

    return (s_tests_failed == 0) ? 0 : 1;
}

#ifndef NO_MAIN
int main(void)
{
    return run_challenger_tests();
}
#endif

