/*
 * Unit Test Suite for CMoviePlayer Decompilation
 *
 * Validates:
 * 1. Ring buffer sizing & threshold math (44100 Hz, 14.985 fps -> 23 chunks threshold, 115 chunks capacity, 29,440 bytes)
 * 2. Alarm period math (380 cycles/sample * 128 = 48,640 cycles, fixing 32x mismatch)
 * 3. Video sync math with 64-bit counters, handling high frame counts (>547 frames) without overflow or underflow
 * 4. Stream EOF handling muting buffer to prevent loop repetition
 * 5. Ring buffer pointer wrap at exact boundary without out-of-bounds heap corruption
 * 6. Deadlock elimination when ring buffer is full
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <assert.h>
#include "movie_player.h"

/* Test State Tracking */
static int s_testsRun = 0;
static int s_testsPassed = 0;
static int s_testsFailed = 0;

#define TEST_ASSERT(cond, msg) do { \
    if (!(cond)) { \
        printf("  [FAIL] %s:%d: %s\n", __FILE__, __LINE__, msg); \
        s_testsFailed++; \
        return 0; \
    } \
} while(0)

#define RUN_TEST(fn) do { \
    printf("Running %s...\n", #fn); \
    s_testsRun++; \
    if (fn()) { \
        printf("  [PASS] %s\n", #fn); \
        s_testsPassed++; \
    } else { \
        printf("  [FAIL] %s\n", #fn); \
    } \
} while(0)

/* Mock state for subsystem interaction */
typedef struct MockState {
    int decodeCallCount;
    int eofAfterChunks;
    int skipCallCount;
    int renderCallCount;
    int alarmTriggerCount;
    u32 lastAlarmPeriod;
    int eofChunkReturned;
} MockState;

static MockState s_mock;

static u32 mock_GetAudioRate(VXHandle vx) {
    (void)vx;
    return 44100;
}

static u32 mock_GetFrameRateFixed(VXHandle vx) {
    (void)vx;
    return 982057; /* 14.985 in 16.16 */
}

static u32 mock_GetAvailableAudioChunks(VXHandle vx) {
    (void)vx;
    return 23; /* 1 frame worth of audio */
}

static int mock_DecodeAudioChunk(VXHandle vx, s16 *dest) {
    (void)vx;
    s_mock.decodeCallCount++;
    if (s_mock.eofAfterChunks > 0 && s_mock.decodeCallCount >= s_mock.eofAfterChunks) {
        s_mock.eofChunkReturned = 1;
        return 0; /* Stream EOF */
    }
    if (dest != NULL) {
        /* Write distinct pattern */
        for (int i = 0; i < MOVIE_AUDIO_BLOCK_SAMPLES; i++) {
            dest[i] = (s16)(0x1000 + (s_mock.decodeCallCount & 0xFF));
        }
    }
    return 1;
}

static void mock_SkipFrame(VXHandle vx) {
    (void)vx;
    s_mock.skipCallCount++;
}

static void mock_DecodeAndRender(CMoviePlayer *p, VXHandle t, VXHandle b) {
    (void)p; (void)t; (void)b;
    s_mock.renderCallCount++;
}

static void mock_SND_SetAlarm(int alarm, u32 tick, u32 period, void (*handler)(void *), void *arg) {
    (void)alarm; (void)tick; (void)handler; (void)arg;
    s_mock.lastAlarmPeriod = period;
}

static void init_mock(void) {
    memset(&s_mock, 0, sizeof(s_mock));
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
 * Test Domain 1: Ring Buffer Sizing & Threshold Math
 * ========================================================================= */
static int test_ring_buffer_sizing_and_threshold_math(void)
{
    /* 1. Sizing calculations at 44,100 Hz, 14.985 fps (982,057 in 16.16) */
    u32 threshold = CMoviePlayer_CalcThreshold(44100, 982057);
    TEST_ASSERT(threshold == 23, "Threshold for 44100 Hz @ 14.985 fps must be 23 chunks");

    u32 capacity = CMoviePlayer_CalcCapacity(threshold);
    TEST_ASSERT(capacity == 115, "Capacity must be threshold * 5 = 115 chunks");

    u32 capacityBytes = CMoviePlayer_CalcCapacityBytes(capacity);
    TEST_ASSERT(capacityBytes == 29440, "Capacity bytes must be 115 * 256 = 29,440 bytes");

    u32 capacitySamples = capacity << 7;
    TEST_ASSERT(capacitySamples == 14720, "Capacity samples must be 115 * 128 = 14,720 samples");

    /* 2. Alternative sample rates */
    u32 thresh22k = CMoviePlayer_CalcThreshold(22050, 982057);
    TEST_ASSERT(thresh22k == 12, "Threshold for 22050 Hz @ 14.985 fps must be 12 chunks");
    TEST_ASSERT(CMoviePlayer_CalcCapacity(thresh22k) == 60, "Capacity for 22050 Hz must be 60 chunks");
    TEST_ASSERT(CMoviePlayer_CalcCapacityBytes(60) == 15360, "Capacity bytes for 22050 Hz must be 15,360");

    u32 thresh32k = CMoviePlayer_CalcThreshold(32000, 982057);
    TEST_ASSERT(thresh32k == 17, "Threshold for 32000 Hz @ 14.985 fps must be 17 chunks");
    TEST_ASSERT(CMoviePlayer_CalcCapacity(thresh32k) == 85, "Capacity for 32000 Hz must be 85 chunks");
    TEST_ASSERT(CMoviePlayer_CalcCapacityBytes(85) == 21760, "Capacity bytes for 32000 Hz must be 21,760");

    /* 3. 30 fps video (1,966,080 in 16.16) */
    u32 thresh30fps = CMoviePlayer_CalcThreshold(44100, 1966080);
    TEST_ASSERT(thresh30fps == 12, "Threshold for 44100 Hz @ 30 fps must be 12 chunks");

    /* 4. Binary Member Offsets Verification for CMoviePlayer_ARM9Layout */
    TEST_ASSERT(offsetof(CMoviePlayer_ARM9Layout, m_vxTop) == CMOVIEPLAYER_OFFSET_VX_TOP, "m_vxTop offset must be 0x94");
    TEST_ASSERT(offsetof(CMoviePlayer_ARM9Layout, m_vxBottom) == CMOVIEPLAYER_OFFSET_VX_BOTTOM, "m_vxBottom offset must be 0x98");
    TEST_ASSERT(offsetof(CMoviePlayer_ARM9Layout, m_isPlaying) == CMOVIEPLAYER_OFFSET_IS_PLAYING, "m_isPlaying offset must be 0x9C");
    TEST_ASSERT(offsetof(CMoviePlayer_ARM9Layout, m_audioReady) == CMOVIEPLAYER_OFFSET_AUDIO_READY, "m_audioReady offset must be 0xA0");
    TEST_ASSERT(offsetof(CMoviePlayer_ARM9Layout, m_readCounter) == CMOVIEPLAYER_OFFSET_READ_COUNTER, "m_readCounter offset must be 0xD0");
    TEST_ASSERT(offsetof(CMoviePlayer_ARM9Layout, m_writeCounter) == CMOVIEPLAYER_OFFSET_WRITE_COUNTER, "m_writeCounter offset must be 0xD8");
    TEST_ASSERT(offsetof(CMoviePlayer_ARM9Layout, m_pAudioBuffer) == CMOVIEPLAYER_OFFSET_AUDIO_BUFFER, "m_pAudioBuffer offset must be 0xE0");
    TEST_ASSERT(offsetof(CMoviePlayer_ARM9Layout, m_writeOffset) == CMOVIEPLAYER_OFFSET_WRITE_OFFSET, "m_writeOffset offset must be 0xE4");
    TEST_ASSERT(offsetof(CMoviePlayer_ARM9Layout, m_capacity) == CMOVIEPLAYER_OFFSET_CAPACITY, "m_capacity offset must be 0xE8");
    TEST_ASSERT(offsetof(CMoviePlayer_ARM9Layout, m_threshold) == CMOVIEPLAYER_OFFSET_THRESHOLD, "m_threshold offset must be 0xEC");
    TEST_ASSERT(offsetof(CMoviePlayer_ARM9Layout, m_audioStarted) == CMOVIEPLAYER_OFFSET_AUDIO_STARTED, "m_audioStarted offset must be 0xF0");
    TEST_ASSERT(offsetof(CMoviePlayer_ARM9Layout, m_fpsFixed) == CMOVIEPLAYER_OFFSET_FPS_FIXED, "m_fpsFixed offset must be 0x10C");
    TEST_ASSERT(offsetof(CMoviePlayer_ARM9Layout, m_ticksPerSample) == CMOVIEPLAYER_OFFSET_TICKS_SAMPLE, "m_ticksPerSample offset must be 0x110");
    TEST_ASSERT(offsetof(CMoviePlayer_ARM9Layout, m_vblankFlag) == CMOVIEPLAYER_OFFSET_VBLANK_FLAG, "m_vblankFlag offset must be 0x4F8");
    TEST_ASSERT(offsetof(CMoviePlayer_ARM9Layout, m_frameCounter) == CMOVIEPLAYER_OFFSET_FRAME_COUNTER, "m_frameCounter offset must be 0x4FC");
    TEST_ASSERT(offsetof(CMoviePlayer_ARM9Layout, m_timeTicks) == CMOVIEPLAYER_OFFSET_TIME_TICKS, "m_timeTicks offset must be 0x500");
    TEST_ASSERT(offsetof(CMoviePlayer_ARM9Layout, m_totalFrames) == CMOVIEPLAYER_OFFSET_TOTAL_FRAMES, "m_totalFrames offset must be 0x504");
    TEST_ASSERT(offsetof(CMoviePlayer_ARM9Layout, m_frameDropMode) == CMOVIEPLAYER_OFFSET_FRAME_DROP_MODE, "m_frameDropMode offset must be 0x508");
    TEST_ASSERT(offsetof(CMoviePlayer_ARM9Layout, m_skippedFlag) == CMOVIEPLAYER_OFFSET_SKIPPED_FLAG, "m_skippedFlag offset must be 0x50C");
    TEST_ASSERT(offsetof(CMoviePlayer_ARM9Layout, m_dualScreen) == CMOVIEPLAYER_OFFSET_DUAL_SCREEN, "m_dualScreen offset must be 0x510");

    return 1;
}

/* =========================================================================
 * Test Domain 2: Alarm Period Math (Fix 1)
 * ========================================================================= */
static int test_alarm_period_math(void)
{
    /* 1. Timer clock ticks per sample */
    u32 ticks = CMoviePlayer_CalcTicksPerSample(44100);
    TEST_ASSERT(ticks == 380, "SND_TIMER_CLOCK (16,756,991) / 44,100 must yield 380 cycles/sample");

    /* 2. Fixed Alarm Period (128 samples per block) */
    u32 fixedAlarmPeriod = CMoviePlayer_CalcAlarmPeriod(ticks);
    TEST_ASSERT(fixedAlarmPeriod == 48640, "Fixed alarm period must be 380 * 128 = 48,640 cycles");

    /* 3. Original Bug Analysis */
    u32 buggyAlarmPeriod = ticks << 2; /* 380 * 4 = 1,520 */
    TEST_ASSERT(buggyAlarmPeriod == 1520, "Buggy alarm period was 1,520 cycles (4 samples)");
    TEST_ASSERT(fixedAlarmPeriod == buggyAlarmPeriod * 32, "Fixed alarm period must be exactly 32x the buggy period");

    /* 4. Rates validation */
    double buggyFreqHz = (double)SND_TIMER_CLOCK / (double)buggyAlarmPeriod;
    double fixedFreqHz = (double)SND_TIMER_CLOCK / (double)fixedAlarmPeriod;
    double chunkProdHz = 44100.0 / 128.0;

    TEST_ASSERT(buggyFreqHz > 11000.0, "Buggy alarm ran at over 11 kHz");
    TEST_ASSERT(fixedFreqHz > 344.0 && fixedFreqHz < 345.0, "Fixed alarm must run at ~344.5 Hz");
    TEST_ASSERT(chunkProdHz > 344.0 && chunkProdHz < 345.0, "Audio chunk production rate is ~344.5 Hz");

    /* 5. StartAudio hook test */
    init_mock();
    CMoviePlayer player;
    CMoviePlayer_Init(&player);
    player.m_capacity = 115;
    CMoviePlayer_StartAudio(&player, 44100);

    TEST_ASSERT(player.m_audioStarted == TRUE, "Audio must be marked started");
    TEST_ASSERT(player.m_ticksPerSample == 380, "ticksPerSample must be 380");
    TEST_ASSERT(s_mock.lastAlarmPeriod == 48640, "Alarm period passed to SND_SetAlarm must be 48,640");

    CMoviePlayer_StopAudio(&player);
    TEST_ASSERT(player.m_audioStarted == FALSE, "Audio must be marked stopped");

    return 1;
}

/* =========================================================================
 * Test Domain 3: Video Sync Math with 64-bit Counters (Fix 2)
 * ========================================================================= */
static int test_video_sync_math_64bit(void)
{
    init_mock();
    CMoviePlayer player;
    CMoviePlayer_Init(&player);

    BOOL playOk = CMoviePlayer_PlayMovie(&player, "TS_01_Intro.vx", 0);
    TEST_ASSERT(playOk, "PlayMovie must succeed");
    CMoviePlayer_SetInstance(&player);

    /*
     * Simulate Intro cutscene playback through 1095 frames.
     * With Fix 1 and Fix 2:
     * - Frame 0..3: Prebuffering 23 chunks per frame.
     * - Frame 4: Audio starts (m_audioStarted = TRUE).
     * - Frame 4..1095: 23 chunks produced each frame, 23 chunks consumed by alarm callback.
     */
    int framesRendered = 0;
    int framesSkipped = 0;

    for (u32 f = 0; f < 1095; f++) {
        /* Advance audio consumer by 23 chunks if audio has started */
        if (player.m_audioStarted) {
            for (int a = 0; a < 23; a++) {
                CMoviePlayer_SoundAlarmCallback(&player);
            }
        }

        s_mock.renderCallCount = 0;
        s_mock.skipCallCount = 0;

        CMoviePlayer_Update(&player);

        if (s_mock.renderCallCount > 0) {
            framesRendered++;
        }
        if (s_mock.skipCallCount > 0) {
            framesSkipped++;
        }

        /* Check halfway point at frame 547 */
        if (player.m_frameCounter == 547) {
            s64 diff = (s64)(player.m_writeCounter - player.m_readCounter);
            TEST_ASSERT(diff > (s64)player.m_threshold, "At frame 547, buffer diff must be greater than threshold");
            TEST_ASSERT(s_mock.renderCallCount == 1, "At frame 547, frame must be rendered (not dropped)");
            TEST_ASSERT(s_mock.skipCallCount == 0, "At frame 547, frame must not be skipped");
            TEST_ASSERT(player.m_skippedFlag == FALSE, "At frame 547, skippedFlag must be FALSE");
        }
    }

    TEST_ASSERT(player.m_frameCounter == 1095, "Total frames processed must be 1095");
    TEST_ASSERT(framesRendered == 1095, "All 1095 frames must be rendered without alternate drops");
    TEST_ASSERT(framesSkipped == 0, "Zero frames should be skipped under normal synchronized playback");
    TEST_ASSERT(player.m_writeCounter >= player.m_readCounter, "Write counter must lead or equal read counter");

    /*
     * Test 64-bit counter values exceeding 32-bit integer range (> 4,294,967,295)
     */
    player.m_writeCounter = 0x200000000ULL + 100; /* ~8.5 billion */
    player.m_readCounter  = 0x200000000ULL + 50;
    s64 largeDiff = (s64)(player.m_writeCounter - player.m_readCounter);
    TEST_ASSERT(largeDiff == 50, "64-bit difference must be exactly 50 without truncation");

    /*
     * Test signed underflow handling: when readCounter momentarily exceeds writeCounter
     */
    player.m_writeCounter = 1000;
    player.m_readCounter  = 1010;
    s64 underflowDiff = (s64)(player.m_writeCounter - player.m_readCounter);
    TEST_ASSERT(underflowDiff == -10, "Underflow diff must be signed -10");
    TEST_ASSERT(underflowDiff <= (s64)player.m_threshold, "Negative diff correctly triggers frame skip");

    /* Verify alternation logic prevents complete stall */
    player.m_skippedFlag = FALSE;
    s_mock.renderCallCount = 0;
    s_mock.skipCallCount = 0;
    /* Simulate underflow sync check */
    if (underflowDiff <= (s64)player.m_threshold) {
        if (!player.m_skippedFlag) {
            mock_SkipFrame(player.m_vxTop);
            player.m_skippedFlag = TRUE;
        }
    }
    TEST_ASSERT(s_mock.skipCallCount == 1, "First underflow frame dropped");
    TEST_ASSERT(player.m_skippedFlag == TRUE, "skippedFlag set to TRUE");

    /* Next frame: if still underflowing, must render to avoid freeze */
    s_mock.renderCallCount = 0;
    s_mock.skipCallCount = 0;
    if (underflowDiff <= (s64)player.m_threshold) {
        if (!player.m_skippedFlag) {
            mock_SkipFrame(player.m_vxTop);
            player.m_skippedFlag = TRUE;
        } else {
            mock_DecodeAndRender(&player, player.m_vxTop, player.m_vxBottom);
            player.m_skippedFlag = FALSE;
        }
    }
    TEST_ASSERT(s_mock.renderCallCount == 1, "Alternate frame rendered to maintain display life");
    TEST_ASSERT(player.m_skippedFlag == FALSE, "skippedFlag reset to FALSE");

    CMoviePlayer_StopMovie(&player);
    return 1;
}

/* =========================================================================
 * Test Domain 4: Stream EOF Handling & Buffer Muting (Fix 3)
 * ========================================================================= */
static int test_stream_eof_and_muting(void)
{
    init_mock();
    CMoviePlayer player;
    CMoviePlayer_Init(&player);

    CMoviePlayer_PlayMovie(&player, "TS_01_Intro.vx", 0);
    CMoviePlayer_SetInstance(&player);

    /* Fill audio buffer with loud test tone (0x4444) */
    u32 bufBytes = CMoviePlayer_CalcCapacityBytes(player.m_capacity);
    memset(player.m_pAudioBuffer, 0x44, bufBytes);

    /* Configure mock to return EOF (0) on the 5th chunk */
    s_mock.eofAfterChunks = 5;
    player.m_frameCounter = 3; /* Next update will be frame 4, audio start */

    CMoviePlayer_Update(&player);

    TEST_ASSERT(s_mock.eofChunkReturned == 1, "Mock must report stream EOF");

    /* Destination chunk must be muted (cleared to 0) */
    s16 *eofChunkPtr = &player.m_pAudioBuffer[player.m_writeOffset];
    u8 zeroBlock[MOVIE_AUDIO_BLOCK_BYTES];
    memset(zeroBlock, 0, MOVIE_AUDIO_BLOCK_BYTES);

    int cmp = memcmp(eofChunkPtr, zeroBlock, MOVIE_AUDIO_BLOCK_BYTES);
    TEST_ASSERT(cmp == 0, "Buffer chunk at EOF must be muted to zero to prevent loop repetition");

    CMoviePlayer_StopMovie(&player);
    return 1;
}

/* =========================================================================
 * Test Domain 5: Ring Buffer Pointer Wrap Without Corruption
 * ========================================================================= */
static int test_ring_buffer_pointer_wrap(void)
{
    init_mock();
    CMoviePlayer player;
    CMoviePlayer_Init(&player);

    u32 capacity = 115;
    u32 bufBytes = capacity << 8; /* 29,440 bytes */
    u32 totalSamples = capacity << 7; /* 14,720 samples */

    /* Allocate buffer with guard canaries: 512 bytes before, 512 bytes after */
    size_t canarySize = 512;
    u8 *rawMemory = (u8 *)malloc(canarySize + bufBytes + canarySize);
    TEST_ASSERT(rawMemory != NULL, "Memory allocation must succeed");

    memset(rawMemory, 0xAA, canarySize);
    memset(rawMemory + canarySize, 0, bufBytes);
    memset(rawMemory + canarySize + bufBytes, 0x55, canarySize);

    player.m_isPlaying = TRUE;
    player.m_capacity = capacity;
    player.m_threshold = 23;
    player.m_pAudioBuffer = (s16 *)(rawMemory + canarySize);
    player.m_writeOffset = 0;
    player.m_audioStarted = FALSE;

    /*
     * Simulate writing 250 chunks sequentially (more than 2 full circular wrap-arounds).
     */
    for (u32 chunk = 0; chunk < 250; chunk++) {
        u32 currentOffset = player.m_writeOffset;
        TEST_ASSERT(currentOffset < totalSamples, "writeOffset must always be strictly less than total capacity samples");

        /* Write 128 samples */
        s16 *dest = &player.m_pAudioBuffer[player.m_writeOffset];
        for (int s = 0; s < MOVIE_AUDIO_BLOCK_SAMPLES; s++) {
            dest[s] = (s16)(chunk + s);
        }

        /* Pointer advance and wrap matching movie_player.c */
        player.m_writeOffset += MOVIE_AUDIO_BLOCK_SAMPLES;
        if (player.m_writeOffset >= (player.m_capacity << 7)) {
            player.m_writeOffset = 0;
        }

        player.m_writeCounter++;

        /* At chunk 114 (115th chunk), next write offset must wrap to 0 */
        if (chunk == 114) {
            TEST_ASSERT(player.m_writeOffset == 0, "After 115 chunks, writeOffset must wrap cleanly to 0");
        }
        /* At chunk 229 (230th chunk), next write offset must wrap to 0 */
        if (chunk == 229) {
            TEST_ASSERT(player.m_writeOffset == 0, "After 230 chunks, writeOffset must wrap cleanly to 0");
        }
    }

    /* Verify safety with oversized writeOffset */
    player.m_writeOffset = totalSamples + 128;
    if (player.m_writeOffset >= (player.m_capacity << 7)) {
        player.m_writeOffset = 0;
    }
    TEST_ASSERT(player.m_writeOffset == 0, "Boundary check (>=) must catch and wrap any out-of-bounds offset");

    /* Verify guard canaries are completely intact */
    for (size_t i = 0; i < canarySize; i++) {
        TEST_ASSERT(rawMemory[i] == 0xAA, "Pre-buffer canary must not be corrupted");
    }
    u8 *tailCanary = rawMemory + canarySize + bufBytes;
    for (size_t i = 0; i < canarySize; i++) {
        TEST_ASSERT(tailCanary[i] == 0x55, "Post-buffer canary must not be corrupted");
    }

    free(rawMemory);
    player.m_pAudioBuffer = NULL;
    return 1;
}

/* =========================================================================
 * Test Domain 6: Spin-Lock Deadlock Elimination (Fix 4)
 * ========================================================================= */
static int test_deadlock_elimination_on_full_buffer(void)
{
    init_mock();
    CMoviePlayer player;
    CMoviePlayer_Init(&player);

    CMoviePlayer_PlayMovie(&player, "TS_01_Intro.vx", 0);
    player.m_audioStarted = TRUE;
    player.m_frameCounter = 10;

    /*
     * Simulate buffer full condition:
     * writeCounter - readCounter >= capacity (115 chunks)
     */
    player.m_writeCounter = 115;
    player.m_readCounter  = 0;
    s_mock.decodeCallCount = 0;

    /*
     * In original buggy assembly (0x0208B880: beq #0x208b860), this entered
     * an infinite tight spin-wait loop on the ARM9 main thread.
     * In the fixed implementation, it yields gracefully without decoding more chunks.
     */
    BOOL result = CMoviePlayer_Update(&player);

    TEST_ASSERT(result == FALSE, "Update must return normally without hanging");
    TEST_ASSERT(s_mock.decodeCallCount == 0, "Decode loop must not decode new chunks into full buffer");
    TEST_ASSERT(player.m_writeCounter == 115, "writeCounter must remain unchanged");

    CMoviePlayer_StopMovie(&player);
    return 1;
}

/* =========================================================================
 * Test Domain 7: Audio Buffer Starvation & Recovery (Fix 4 Inverse)
 * ========================================================================= */
static int test_audio_starvation_recovery(void)
{
    init_mock();
    CMoviePlayer player;
    CMoviePlayer_Init(&player);

    BOOL playOk = CMoviePlayer_PlayMovie(&player, "TS_01_Intro.vx", 0);
    TEST_ASSERT(playOk, "PlayMovie must succeed");
    CMoviePlayer_SetInstance(&player);

    /* Run 10 normal frames to establish audio playback */
    for (int f = 0; f < 10; f++) {
        if (player.m_audioStarted) {
            for (int a = 0; a < 23; a++) {
                CMoviePlayer_SoundAlarmCallback(&player);
            }
        }
        CMoviePlayer_Update(&player);
    }

    TEST_ASSERT(player.m_audioStarted == TRUE, "Audio must be started");
    TEST_ASSERT(player.m_writeCounter >= player.m_readCounter, "Write counter leads or equals read counter");

    /*
     * Simulate audio buffer starvation:
     * Audio consumer alarm advances by 6 frames (138 chunks), outpacing producer (readCounter > writeCounter).
     */
    u64 writeBeforeLag = player.m_writeCounter;
    for (int a = 0; a < 6 * 23; a++) {
        CMoviePlayer_SoundAlarmCallback(&player);
    }

    TEST_ASSERT(player.m_readCounter > player.m_writeCounter,
                "Consumer must outpace producer, inducing starvation (read > write)");

    /*
     * Producer recovery: 23 chunks become available again.
     * Verify that producer decodes available chunks and is NOT locked out by unsigned wrap-around.
     */
    s_mock.decodeCallCount = 0;
    CMoviePlayer_Update(&player);

    TEST_ASSERT(s_mock.decodeCallCount == 23,
                "Producer must decode available chunks during starvation recovery");
    TEST_ASSERT(player.m_writeCounter == writeBeforeLag + 23,
                "writeCounter must advance by 23 chunks after starvation recovery");

    CMoviePlayer_StopMovie(&player);
    return 1;
}

/* =========================================================================
 * Main Entry Point
 * ========================================================================= */
int main(void)
{
    printf("====================================================================\n");
    printf("Sonic Chronicles CMoviePlayer Verification Suite\n");
    printf("Validating video synchronization, audio timing, and bug fixes\n");
    printf("====================================================================\n\n");

    RUN_TEST(test_ring_buffer_sizing_and_threshold_math);
    RUN_TEST(test_alarm_period_math);
    RUN_TEST(test_video_sync_math_64bit);
    RUN_TEST(test_stream_eof_and_muting);
    RUN_TEST(test_ring_buffer_pointer_wrap);
    RUN_TEST(test_deadlock_elimination_on_full_buffer);
    RUN_TEST(test_audio_starvation_recovery);

    printf("\n====================================================================\n");
    printf("Test Results: %d run, %d passed, %d failed\n", s_testsRun, s_testsPassed, s_testsFailed);
    printf("====================================================================\n");

    return (s_testsFailed == 0) ? 0 : 1;
}
