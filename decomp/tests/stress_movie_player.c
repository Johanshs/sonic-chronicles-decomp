/*
 * Adversarial Stress Test Suite for CMoviePlayer Decompilation
 *
 * Designed by Empirical Challenger to stress-test edge cases:
 * 1. Ring buffer fullness (audio consumer halt -> check for deadlock or overflow)
 * 2. Ring buffer starvation (audio producer lag -> check recovery and underflow logic)
 * 3. Rapid video frame skipping under persistent underflow (dual-screen & single-screen)
 * 4. Unexpected stream EOF mid-playback across multiple lifecycle points
 * 5. Extreme sample rates (8k, 11k, 16k, 22k, 32k, 44.1k, 48k, 96k) and fps combinations
 * 6. Pointer wrapping boundary conditions (exact boundary, boundary + 1, canary integrity)
 * 7. High 64-bit counter wraparound stress test
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <assert.h>
#include "movie_player.h"

static int s_testsRun = 0;
static int s_testsPassed = 0;
static int s_testsFailed = 0;

#define STRESS_ASSERT(cond, msg) do { \
    if (!(cond)) { \
        printf("  [FAIL] %s:%d: %s\n", __FILE__, __LINE__, msg); \
        s_testsFailed++; \
        return 0; \
    } \
} while(0)

#define RUN_STRESS_TEST(fn) do { \
    printf("Running %s...\n", #fn); \
    s_testsRun++; \
    if (fn()) { \
        printf("  [PASS] %s\n", #fn); \
        s_testsPassed++; \
    } else { \
        printf("  [FAIL] %s\n", #fn); \
    } \
} while(0)

/* Mock state for stress tests */
typedef struct StressMockState {
    int decodeCallCount;
    int availableChunksToReturn;
    int eofAtCall;
    int skipCallCountTop;
    int skipCallCountBottom;
    int renderCallCount;
    u32 currentAudioRate;
    u32 currentFpsFixed;
    u32 lastAlarmPeriod;
    int returnZeroOnDecode;
} StressMockState;

static StressMockState s_stressMock;

static u32 mock_GetAudioRate(VXHandle vx) {
    (void)vx;
    return (s_stressMock.currentAudioRate > 0) ? s_stressMock.currentAudioRate : 44100;
}

static u32 mock_GetFrameRateFixed(VXHandle vx) {
    (void)vx;
    return (s_stressMock.currentFpsFixed > 0) ? s_stressMock.currentFpsFixed : 982057;
}

static u32 mock_GetAvailableAudioChunks(VXHandle vx) {
    (void)vx;
    return s_stressMock.availableChunksToReturn;
}

static int mock_DecodeAudioChunk(VXHandle vx, s16 *dest) {
    (void)vx;
    s_stressMock.decodeCallCount++;

    if (s_stressMock.eofAtCall > 0 && s_stressMock.decodeCallCount >= s_stressMock.eofAtCall) {
        return 0; /* Stream EOF */
    }

    if (s_stressMock.returnZeroOnDecode) {
        return 0;
    }

    if (dest != NULL) {
        for (int i = 0; i < MOVIE_AUDIO_BLOCK_SAMPLES; i++) {
            dest[i] = (s16)(s_stressMock.decodeCallCount & 0x7FFF);
        }
    }
    return 1;
}

static void mock_SkipFrame(VXHandle vx) {
    if (vx == (VXHandle)0x1) {
        s_stressMock.skipCallCountTop++;
    } else if (vx == (VXHandle)0x2) {
        s_stressMock.skipCallCountBottom++;
    } else {
        s_stressMock.skipCallCountTop++;
    }
}

static void mock_DecodeAndRender(CMoviePlayer *p, VXHandle t, VXHandle b) {
    (void)p; (void)t; (void)b;
    s_stressMock.renderCallCount++;
}

static void mock_SND_SetAlarm(int alarm, u32 tick, u32 period, void (*handler)(void *), void *arg) {
    (void)alarm; (void)tick; (void)handler; (void)arg;
    s_stressMock.lastAlarmPeriod = period;
}

static void init_stress_mock(void) {
    memset(&s_stressMock, 0, sizeof(s_stressMock));
    s_stressMock.availableChunksToReturn = 23;
    s_stressMock.currentAudioRate = 44100;
    s_stressMock.currentFpsFixed = 982057;

    CMoviePlayerHooks hooks = {
        .GetAudioRate = mock_GetAudioRate,
        .GetFrameRateFixed = mock_GetFrameRateFixed,
        .GetAvailableAudioChunks = mock_GetAvailableAudioChunks,
        .DecodeAudioChunk = mock_DecodeAudioChunk,
        .SkipFrame = mock_SkipFrame,
        .IsPlaying = NULL,
        .DecodeAndRender = mock_DecodeAndRender,
        .DC_FlushRange = NULL,
        .SND_LockChannel = NULL,
        .SND_UnlockChannel = NULL,
        .SND_SetupChannelPcm = NULL,
        .SND_SetAlarm = mock_SND_SetAlarm,
        .SND_StartAlarm = NULL,
        .SND_StopAlarm = NULL,
    };
    CMoviePlayer_SetHooks(&hooks);
}

/* =========================================================================
 * Challenge 1: Ring Buffer Fullness Edge Case (Consumer halts)
 * ========================================================================= */
static int test_stress_fullness_consumer_halt(void)
{
    init_stress_mock();
    CMoviePlayer player;
    CMoviePlayer_Init(&player);

    BOOL ok = CMoviePlayer_PlayMovie(&player, "test.vx", 0);
    STRESS_ASSERT(ok, "PlayMovie failed");
    CMoviePlayer_SetInstance(&player);

    /* Run 10 frames normally with consumer active */
    for (int f = 0; f < 10; f++) {
        if (player.m_audioStarted) {
            for (int a = 0; a < 23; a++) {
                CMoviePlayer_SoundAlarmCallback(&player);
            }
        }
        CMoviePlayer_Update(&player);
    }

    STRESS_ASSERT(player.m_audioStarted == TRUE, "Audio should have started");

    /* Record state before consumer halt */
    u64 readAtHalt = player.m_readCounter;

    /* Consumer now HALTS completely (SoundAlarmCallback never called again) */
    /* Run 200 more frames */
    for (int f = 0; f < 200; f++) {
        s_stressMock.renderCallCount = 0;
        s_stressMock.skipCallCountTop = 0;

        /* Call Update: should NOT hang, deadlock, or overrun buffer */
        CMoviePlayer_Update(&player);

        /* Consumer counter should remain halted */
        STRESS_ASSERT(player.m_readCounter == readAtHalt, "Read counter must not advance without consumer");

        /* Difference write - read must NEVER exceed capacity */
        u64 diff = player.m_writeCounter - player.m_readCounter;
        STRESS_ASSERT(diff <= (u64)player.m_capacity, "Producer must never exceed buffer capacity when full");

        /* Once buffer is full, write counter must not keep incrementing indefinitely */
        if (diff == (u64)player.m_capacity) {
            STRESS_ASSERT(player.m_writeCounter == readAtHalt + player.m_capacity, "writeCounter must cap at read + capacity");
        }
    }

    /* Verification: Producer reached capacity and stayed there smoothly */
    STRESS_ASSERT(player.m_writeCounter - player.m_readCounter == (u64)player.m_capacity,
                  "Buffer should be exactly at capacity");

    CMoviePlayer_StopMovie(&player);
    return 1;
}

/* =========================================================================
 * Challenge 2: Ring Buffer Starvation Edge Case (Producer lags behind)
 * ========================================================================= */
static int test_stress_starvation_producer_lag(void)
{
    init_stress_mock();
    CMoviePlayer player;
    CMoviePlayer_Init(&player);

    BOOL ok = CMoviePlayer_PlayMovie(&player, "test.vx", 0);
    STRESS_ASSERT(ok, "PlayMovie failed");
    CMoviePlayer_SetInstance(&player);

    /* Run 10 frames normally to get audio rolling */
    for (int f = 0; f < 10; f++) {
        if (player.m_audioStarted) {
            for (int a = 0; a < 23; a++) {
                CMoviePlayer_SoundAlarmCallback(&player);
            }
        }
        CMoviePlayer_Update(&player);
    }

    STRESS_ASSERT(player.m_writeCounter >= player.m_readCounter, "Initial state write >= read");

    /*
     * Simulate severe producer lag:
     * Decoder produces 0 chunks for 5 frames while audio hardware keeps consuming 23 chunks/frame.
     */
    s_stressMock.availableChunksToReturn = 0;

    for (int f = 0; f < 5; f++) {
        /* Audio hardware alarm ticks */
        for (int a = 0; a < 23; a++) {
            CMoviePlayer_SoundAlarmCallback(&player);
        }
        CMoviePlayer_Update(&player);
    }

    /* Verify starvation condition: readCounter has outpaced writeCounter */
    printf("    [State] writeCounter=%llu, readCounter=%llu (read > write by %lld)\n",
           (unsigned long long)player.m_writeCounter,
           (unsigned long long)player.m_readCounter,
           (long long)(player.m_readCounter - player.m_writeCounter));

    STRESS_ASSERT(player.m_readCounter > player.m_writeCounter,
                  "Audio consumer must have outpaced producer, creating buffer starvation");

    /*
     * Producer now RECOVERS: chunks are available again (23 chunks ready to decode)!
     * Can the producer decode chunks, or does line 437 wrap around and block it?
     */
    s_stressMock.availableChunksToReturn = 23;
    u64 writeBeforeRecovery = player.m_writeCounter;
    int decodeBeforeRecovery = s_stressMock.decodeCallCount;

    /* Execute Update on recovered producer */
    CMoviePlayer_Update(&player);

    printf("    [Recovery Check] chunks decoded=%d, writeCounter advanced=%llu\n",
           s_stressMock.decodeCallCount - decodeBeforeRecovery,
           (unsigned long long)(player.m_writeCounter - writeBeforeRecovery));

    /*
     * CRITICAL EMPIRICAL CHALLENGE:
     * When starved, the buffer is NOT full. The producer MUST decode chunks to refill the buffer!
     * If the producer failed to decode any chunks, it is trapped in the unsigned wrap-around bug!
     */
    if (player.m_writeCounter == writeBeforeRecovery) {
        printf("    >>> CRITICAL BUG DETECTED: Producer is locked out! writeCounter did not advance during starvation recovery!\n");
        printf("    >>> Reason: in CMoviePlayer_Update, 'u64 diff = writeCounter - readCounter' underflows when read > write,\n");
        printf("    >>> producing ~1.84e19, which falsely evaluates 'diff >= capacity' and executes break!\n");
        CMoviePlayer_StopMovie(&player);
        STRESS_ASSERT(0, "STARVATION DEADLOCK: Producer cannot decode audio when readCounter > writeCounter");
    }

    CMoviePlayer_StopMovie(&player);
    return 1;
}

/* =========================================================================
 * Challenge 3: Rapid Video Frame Skipping Under Persistent Underflow
 * ========================================================================= */
static int test_stress_rapid_skip(void)
{
    init_stress_mock();
    CMoviePlayer player;
    CMoviePlayer_Init(&player);

    /* Test both single-screen and dual-screen */
    for (int dual = 0; dual <= 1; dual++) {
        BOOL ok = CMoviePlayer_PlayMovie(&player, "test.vx", dual ? 1 : 0);
        STRESS_ASSERT(ok, "PlayMovie failed");
        player.m_vxTop = (VXHandle)0x1;
        player.m_vxBottom = (VXHandle)0x2;
        player.m_audioStarted = TRUE;
        player.m_frameCounter = 3; /* Next frame is 4 */

        /* Force persistent underflow: writeCounter = 0, readCounter = 100 */
        player.m_writeCounter = 0;
        player.m_readCounter = 100;
        s_stressMock.availableChunksToReturn = 0; /* Keep starved */

        int skippedFrames = 0;
        int renderedFrames = 0;

        /* Run 100 frames under persistent starvation */
        for (int f = 0; f < 100; f++) {
            s_stressMock.skipCallCountTop = 0;
            s_stressMock.skipCallCountBottom = 0;
            s_stressMock.renderCallCount = 0;

            CMoviePlayer_Update(&player);

            if (s_stressMock.skipCallCountTop > 0) {
                skippedFrames++;
                if (dual) {
                    STRESS_ASSERT(s_stressMock.skipCallCountBottom == 1,
                                  "Dual screen must skip both top and bottom screens");
                }
            }
            if (s_stressMock.renderCallCount > 0) {
                renderedFrames++;
            }
        }

        /*
         * Alternation check:
         * Over 100 starved frames, it must alternate: 50 skipped, 50 rendered.
         * It must NEVER completely freeze (0 renders) or skip 2 frames consecutively.
         */
        STRESS_ASSERT(skippedFrames == 50, "Persistent starvation must alternate: exactly 50 skips");
        STRESS_ASSERT(renderedFrames == 50, "Persistent starvation must alternate: exactly 50 renders");

        CMoviePlayer_StopMovie(&player);
    }

    return 1;
}

/* =========================================================================
 * Challenge 4: Unexpected Stream EOF Mid-Playback Across Multiple Points
 * ========================================================================= */
static int test_stress_eof_scenarios(void)
{
    int testPoints[] = {
        1,        /* EOF on 1st chunk decoded */
        4,        /* EOF right at frame 4 audio start */
        23,       /* EOF at exact end of frame 4 */
        50,       /* EOF mid-stream */
        547 * 23, /* EOF at halfway point */
    };
    int numPoints = sizeof(testPoints) / sizeof(testPoints[0]);

    for (int p = 0; p < numPoints; p++) {
        int eofTarget = testPoints[p];
        init_stress_mock();
        s_stressMock.eofAtCall = eofTarget;

        CMoviePlayer player;
        CMoviePlayer_Init(&player);
        BOOL ok = CMoviePlayer_PlayMovie(&player, "intro.vx", 0);
        STRESS_ASSERT(ok, "PlayMovie failed");
        CMoviePlayer_SetInstance(&player);

        /* Run up to 600 frames or until movie end */
        for (u32 f = 0; f < 600; f++) {
            if (player.m_audioStarted) {
                for (int a = 0; a < 23; a++) {
                    CMoviePlayer_SoundAlarmCallback(&player);
                }
            }
            CMoviePlayer_Update(&player);
        }

        /* Check that EOF chunk is muted and player didn't crash */
        STRESS_ASSERT(player.m_frameCounter == 600, "Frame counter must reach 600 without crash");
        CMoviePlayer_StopMovie(&player);
        STRESS_ASSERT(player.m_pAudioBuffer == NULL, "Buffer must be cleanly freed on stop");
        STRESS_ASSERT(player.m_isPlaying == FALSE, "isPlaying must be FALSE on stop");
    }

    return 1;
}

/* =========================================================================
 * Challenge 5: Extreme Sample Rates & Fixed-Point Frame Rates
 * ========================================================================= */
static int test_stress_extreme_sample_and_frame_rates(void)
{
    u32 sampleRates[] = { 8000, 11025, 16000, 22050, 32000, 44100, 48000, 96000 };
    u32 fpsList[] = {
        655360,   /* 10.0 fps */
        982057,   /* 14.985 fps */
        1571291,  /* 23.976 fps */
        1966080,  /* 30.0 fps */
        3932160   /* 60.0 fps */
    };
    int numRates = sizeof(sampleRates) / sizeof(sampleRates[0]);
    int numFps = sizeof(fpsList) / sizeof(fpsList[0]);

    for (int r = 0; r < numRates; r++) {
        u32 rate = sampleRates[r];
        u32 ticks = CMoviePlayer_CalcTicksPerSample(rate);
        STRESS_ASSERT(ticks > 0, "Ticks per sample must be > 0");

        u32 alarmPeriod = CMoviePlayer_CalcAlarmPeriod(ticks);
        STRESS_ASSERT(alarmPeriod == ticks * 128, "Alarm period must equal ticks * 128");

        for (int f = 0; f < numFps; f++) {
            u32 fps = fpsList[f];
            u32 thresh = CMoviePlayer_CalcThreshold(rate, fps);
            STRESS_ASSERT(thresh >= 1, "Threshold must be >= 1");

            u32 cap = CMoviePlayer_CalcCapacity(thresh);
            STRESS_ASSERT(cap == thresh * 5, "Capacity must be threshold * 5");

            u32 capBytes = CMoviePlayer_CalcCapacityBytes(cap);
            STRESS_ASSERT(capBytes == cap * 256, "Capacity bytes must be capacity * 256");
            STRESS_ASSERT(capBytes < 1000000, "Capacity bytes must be reasonable for DS RAM");
        }
    }

    /* Edge cases: 0 fps, 0 sample rate */
    STRESS_ASSERT(CMoviePlayer_CalcThreshold(44100, 0) == 1, "Threshold with 0 fps must return 1");
    STRESS_ASSERT(CMoviePlayer_CalcTicksPerSample(0) == 0, "Ticks with 0 sample rate must return 0");

    /* Full multi-frame simulations for 22050 Hz, 32000 Hz, 48000 Hz */
    u32 testRates[] = { 22050, 32000, 48000 };
    for (int i = 0; i < 3; i++) {
        u32 targetRate = testRates[i];
        init_stress_mock();
        s_stressMock.currentAudioRate = targetRate;

        CMoviePlayer player;
        CMoviePlayer_Init(&player);
        BOOL ok = CMoviePlayer_PlayMovie(&player, "test.vx", 0);
        STRESS_ASSERT(ok, "PlayMovie failed");
        CMoviePlayer_SetInstance(&player);

        u32 thresh = player.m_threshold;
        s_stressMock.availableChunksToReturn = thresh;

        for (int f = 0; f < 300; f++) {
            if (player.m_audioStarted) {
                for (u32 a = 0; a < thresh; a++) {
                    CMoviePlayer_SoundAlarmCallback(&player);
                }
            }
            CMoviePlayer_Update(&player);
        }

        STRESS_ASSERT(player.m_frameCounter == 300, "Must simulate 300 frames cleanly");
        CMoviePlayer_StopMovie(&player);
    }

    return 1;
}

/* =========================================================================
 * Challenge 6: Pointer Wrapping at Exact Boundary and Boundary + 1
 * ========================================================================= */
static int test_stress_pointer_wrap_boundary_conditions(void)
{
    init_stress_mock();
    CMoviePlayer player;
    CMoviePlayer_Init(&player);

    u32 capacity = 115;
    u32 totalSamples = capacity << 7; /* 14,720 samples */
    u32 bufBytes = capacity << 8;    /* 29,440 bytes */

    /* Allocate buffer surrounded by guard canaries */
    size_t canarySize = 1024;
    u8 *raw = (u8 *)malloc(canarySize + bufBytes + canarySize);
    STRESS_ASSERT(raw != NULL, "Alloc failed");

    memset(raw, 0xEE, canarySize);
    memset(raw + canarySize, 0, bufBytes);
    memset(raw + canarySize + bufBytes, 0xFF, canarySize);

    player.m_isPlaying = TRUE;
    player.m_capacity = capacity;
    player.m_threshold = 23;
    player.m_pAudioBuffer = (s16 *)(raw + canarySize);
    player.m_audioStarted = FALSE;

    /*
     * 1. Boundary Condition 1: exact boundary wrapping over 500,000 chunks
     */
    player.m_writeOffset = 0;
    for (u32 c = 0; c < 500000; c++) {
        STRESS_ASSERT(player.m_writeOffset < totalSamples, "writeOffset must never exceed totalSamples");

        /* Simulate chunk write */
        s16 *dest = &player.m_pAudioBuffer[player.m_writeOffset];
        dest[0] = (s16)(c & 0x7FFF);
        dest[MOVIE_AUDIO_BLOCK_SAMPLES - 1] = (s16)(c & 0x7FFF);

        /* Wrap check matching implementation */
        player.m_writeOffset += MOVIE_AUDIO_BLOCK_SAMPLES;
        if (player.m_writeOffset >= (player.m_capacity << 7)) {
            player.m_writeOffset = 0;
        }
    }

    /* Check canaries after 500k chunks */
    for (size_t i = 0; i < canarySize; i++) {
        STRESS_ASSERT(raw[i] == 0xEE, "Pre-buffer canary corrupted during circular write");
        STRESS_ASSERT(raw[canarySize + bufBytes + i] == 0xFF, "Post-buffer canary corrupted during circular write");
    }

    /*
     * 2. Boundary Condition 2: Exact boundary test.
     * When writeOffset is at (capacity - 1) * 128 = 14592:
     * Next offset becomes 14720, which is exactly (capacity << 7).
     * Must wrap immediately to 0.
     */
    player.m_writeOffset = (capacity - 1) * MOVIE_AUDIO_BLOCK_SAMPLES;
    STRESS_ASSERT(player.m_writeOffset == 14592, "Last valid block offset is 14592");

    player.m_writeOffset += MOVIE_AUDIO_BLOCK_SAMPLES;
    STRESS_ASSERT(player.m_writeOffset == 14720, "Advance hits exact boundary 14720");
    if (player.m_writeOffset >= (player.m_capacity << 7)) {
        player.m_writeOffset = 0;
    }
    STRESS_ASSERT(player.m_writeOffset == 0, "Exact boundary must wrap to 0");

    /*
     * 3. Boundary Condition 3: Boundary + 1 sample test.
     * What if writeOffset somehow arrived at boundary + 1 (14,721) or boundary + 128 (14,848)?
     */
    player.m_writeOffset = (player.m_capacity << 7) + 1;
    if (player.m_writeOffset >= (player.m_capacity << 7)) {
        player.m_writeOffset = 0;
    }
    STRESS_ASSERT(player.m_writeOffset == 0, "Boundary + 1 must wrap to 0");

    player.m_writeOffset = (player.m_capacity << 7) + 128;
    if (player.m_writeOffset >= (player.m_capacity << 7)) {
        player.m_writeOffset = 0;
    }
    STRESS_ASSERT(player.m_writeOffset == 0, "Boundary + 128 must wrap to 0");

    free(raw);
    player.m_pAudioBuffer = NULL;
    return 1;
}

/* =========================================================================
 * Challenge 7: High 64-bit Counter Wraparound Stress Test
 * ========================================================================= */
static int test_stress_counter_overflow_wrap(void)
{
    init_stress_mock();
    CMoviePlayer player;
    CMoviePlayer_Init(&player);

    /* Test counter operations near 64-bit unsigned limit */
    player.m_isPlaying = TRUE;
    player.m_audioStarted = TRUE;
    player.m_threshold = 23;
    player.m_capacity = 115;

    /* Producer and consumer near UINT64_MAX */
    player.m_writeCounter = 0xFFFFFFFFFFFFFF00ULL + 50;
    player.m_readCounter  = 0xFFFFFFFFFFFFFF00ULL;

    s64 diff = (s64)(player.m_writeCounter - player.m_readCounter);
    STRESS_ASSERT(diff == 50, "Signed diff near 64-bit limit must be 50");
    STRESS_ASSERT(diff > (s64)player.m_threshold, "50 > 23 chunks threshold");

    /* Test negative diff underflow signed conversion */
    player.m_writeCounter = 0xFFFFFFFFFFFFFF00ULL;
    player.m_readCounter  = 0xFFFFFFFFFFFFFF00ULL + 10;
    s64 underflowDiff = (s64)(player.m_writeCounter - player.m_readCounter);
    STRESS_ASSERT(underflowDiff == -10, "Underflow signed diff must be -10");
    STRESS_ASSERT(underflowDiff <= (s64)player.m_threshold, "-10 <= 23 threshold");

    return 1;
}

/* =========================================================================
 * Main Entry Point
 * ========================================================================= */
int main(void)
{
    printf("====================================================================\n");
    printf("Sonic Chronicles CMoviePlayer Adversarial Stress Suite\n");
    printf("Stress testing edge cases, boundary wrapping, starvation & fullness\n");
    printf("====================================================================\n\n");

    RUN_STRESS_TEST(test_stress_fullness_consumer_halt);
    RUN_STRESS_TEST(test_stress_starvation_producer_lag);
    RUN_STRESS_TEST(test_stress_rapid_skip);
    RUN_STRESS_TEST(test_stress_eof_scenarios);
    RUN_STRESS_TEST(test_stress_extreme_sample_and_frame_rates);
    RUN_STRESS_TEST(test_stress_pointer_wrap_boundary_conditions);
    RUN_STRESS_TEST(test_stress_counter_overflow_wrap);

    printf("\n====================================================================\n");
    printf("Stress Test Results: %d run, %d passed, %d failed\n", s_testsRun, s_testsPassed, s_testsFailed);
    printf("====================================================================\n");

    return (s_testsFailed == 0) ? 0 : 1;
}
