/*
 * CMoviePlayer - Decompiled Video & Audio Playback Subsystem
 *
 * Sonic Chronicles: The Dark Brotherhood (Nintendo DS)
 * Original assembly range: 0x0208AB00 - 0x0208C100
 *
 * Reconstructs the video/audio streaming synchronization engine faithfully matching
 * original CodeWarrior ARM9 assembly while resolving the four critical desync & deadlock flaws:
 * 1. Audio alarm reload period (ticks_per_sample << 7, fixing lsl r5, r4, #2 bug)
 * 2. Video sync logic (64-bit signed difference preventing negative underflow frame drop)
 * 3. Audio stream EOF & mute handling (muting buffer chunk to prevent loop buzz)
 * 4. Spin-lock deadlock elimination (yielding on buffer full instead of hard spin lock)
 */

#include "movie_player.h"

/* Singleton instance pointer (stored at 0x021A4468 in ARM9 RAM) */
static CMoviePlayer *s_moviePlayerInstance = NULL;

/* Default Subsystem Hook Implementations */
static u32  default_GetAudioRate(VXHandle vx) { (void)vx; return 44100; }
static u32  default_GetFrameRateFixed(VXHandle vx) { (void)vx; return 982057; } /* 14.985 fps in 16.16 */
static u32  default_GetAvailableAudioChunks(VXHandle vx) { (void)vx; return 23; }
static int  default_DecodeAudioChunk(VXHandle vx, s16 *dest) {
    (void)vx;
    if (dest != NULL) {
        memset(dest, 0, MOVIE_AUDIO_BLOCK_BYTES);
    }
    return 1;
}
static void default_SkipFrame(VXHandle vx) { (void)vx; }
static BOOL default_IsPlaying(VXHandle vx) { (void)vx; return TRUE; }
static void default_DecodeAndRender(CMoviePlayer *p, VXHandle t, VXHandle b) { (void)p; (void)t; (void)b; }

static void default_DC_FlushRange(const void *addr, u32 size) { (void)addr; (void)size; }
static void default_SND_LockChannel(u32 ch) { (void)ch; }
static void default_SND_UnlockChannel(u32 ch) { (void)ch; }
static void default_SND_SetupChannelPcm(int ch, int fmt, const void *data, int loop,
                                        int loopStart, int loopLen, int vol, int shift,
                                        int timer, int pan) {
    (void)ch; (void)fmt; (void)data; (void)loop; (void)loopStart;
    (void)loopLen; (void)vol; (void)shift; (void)timer; (void)pan;
}
static void default_SND_SetAlarm(int alarm, u32 tick, u32 period, void (*handler)(void *), void *arg) {
    (void)alarm; (void)tick; (void)period; (void)handler; (void)arg;
}
static void default_SND_StartAlarm(int alarm) { (void)alarm; }
static void default_SND_StopAlarm(int alarm) { (void)alarm; }

static const CMoviePlayerHooks s_defaultHooks = {
    .GetAudioRate = default_GetAudioRate,
    .GetFrameRateFixed = default_GetFrameRateFixed,
    .GetAvailableAudioChunks = default_GetAvailableAudioChunks,
    .DecodeAudioChunk = default_DecodeAudioChunk,
    .SkipFrame = default_SkipFrame,
    .IsPlaying = default_IsPlaying,
    .DecodeAndRender = default_DecodeAndRender,

    .DC_FlushRange = default_DC_FlushRange,
    .SND_LockChannel = default_SND_LockChannel,
    .SND_UnlockChannel = default_SND_UnlockChannel,
    .SND_SetupChannelPcm = default_SND_SetupChannelPcm,
    .SND_SetAlarm = default_SND_SetAlarm,
    .SND_StartAlarm = default_SND_StartAlarm,
    .SND_StopAlarm = default_SND_StopAlarm,
};

static CMoviePlayerHooks s_hooks = {
    .GetAudioRate = default_GetAudioRate,
    .GetFrameRateFixed = default_GetFrameRateFixed,
    .GetAvailableAudioChunks = default_GetAvailableAudioChunks,
    .DecodeAudioChunk = default_DecodeAudioChunk,
    .SkipFrame = default_SkipFrame,
    .IsPlaying = default_IsPlaying,
    .DecodeAndRender = default_DecodeAndRender,

    .DC_FlushRange = default_DC_FlushRange,
    .SND_LockChannel = default_SND_LockChannel,
    .SND_UnlockChannel = default_SND_UnlockChannel,
    .SND_SetupChannelPcm = default_SND_SetupChannelPcm,
    .SND_SetAlarm = default_SND_SetAlarm,
    .SND_StartAlarm = default_SND_StartAlarm,
    .SND_StopAlarm = default_SND_StopAlarm,
};

void CMoviePlayer_SetHooks(const CMoviePlayerHooks *hooks)
{
    if (hooks != NULL) {
#define MERGE_HOOK(f) s_hooks.f = (hooks->f != NULL) ? hooks->f : s_defaultHooks.f
        MERGE_HOOK(GetAudioRate);
        MERGE_HOOK(GetFrameRateFixed);
        MERGE_HOOK(GetAvailableAudioChunks);
        MERGE_HOOK(DecodeAudioChunk);
        MERGE_HOOK(SkipFrame);
        MERGE_HOOK(IsPlaying);
        MERGE_HOOK(DecodeAndRender);
        MERGE_HOOK(DC_FlushRange);
        MERGE_HOOK(SND_LockChannel);
        MERGE_HOOK(SND_UnlockChannel);
        MERGE_HOOK(SND_SetupChannelPcm);
        MERGE_HOOK(SND_SetAlarm);
        MERGE_HOOK(SND_StartAlarm);
        MERGE_HOOK(SND_StopAlarm);
#undef MERGE_HOOK
    } else {
        s_hooks = s_defaultHooks;
    }
}

void CMoviePlayer_ResetHooks(void)
{
    s_hooks = s_defaultHooks;
}

/*
 * CMoviePlayer_CalcThreshold
 *
 * Original assembly in CMoviePlayer::PlayMovie (0x0208B150 - 0x0208B164):
 *   0x0208B150: mov  r1, r0, lsl #16       ; r1 = sampleRate << 16
 *   0x0208B154: ldr  r0, [r4, #0x10c]      ; fpsFixed (16.16)
 *   0x0208B158: mov  r0, r0, lsl #7        ; r0 = fpsFixed << 7
 *   0x0208B15C: bl   #0x20eb168            ; __rt_udiv(r1, r0)
 *   0x0208B160: add  r0, r0, #1            ; threshold = div + 1
 *
 * For 44100 Hz, 14.985 fps (fpsFixed = 982057):
 *   (44100 << 16) / (982057 << 7) + 1 = 2890137600 / 125709824 + 1 = 22 + 1 = 23 chunks
 */
u32 CMoviePlayer_CalcThreshold(u32 sampleRate, u32 fpsFixed)
{
    u64 num = ((u64)sampleRate) << 16;
    u64 den = ((u64)fpsFixed) << 7;
    if (den == 0) return 1;
    return (u32)(num / den) + 1;
}

/*
 * CMoviePlayer_CalcCapacity
 *
 * Original assembly in CMoviePlayer::PlayMovie (0x0208B168 - 0x0208B16C):
 *   0x0208B168: add  r0, r0, r0, lsl #2    ; capacity = threshold + (threshold << 2) = threshold * 5
 *
 * For threshold = 23:
 *   capacity = 23 * 5 = 115 chunks
 */
u32 CMoviePlayer_CalcCapacity(u32 threshold)
{
    return threshold + (threshold << 2);
}

/*
 * CMoviePlayer_CalcCapacityBytes
 *
 * Original assembly in CMoviePlayer::PlayMovie (0x0208B170 - 0x0208B174):
 *   0x0208B170: lsl  r0, r0, #8            ; capacity << 8 = capacity * 256 bytes
 *
 * For capacity = 115:
 *   115 << 8 = 29,440 bytes (14,720 samples * 2 bytes/sample)
 */
u32 CMoviePlayer_CalcCapacityBytes(u32 capacity)
{
    return capacity << 8;
}

/*
 * CMoviePlayer_CalcTicksPerSample
 *
 * Original assembly in CMoviePlayer::StartAudio (0x0208BDE0 - 0x0208BDE8):
 *   0x0208BDE0: ldr  r0, [pc, #0x9c]       ; 0x00FFB0FF = 16,756,991 (SND_TIMER_CLOCK)
 *   0x0208BDE4: bl   #0x20eb168            ; __rt_udiv(16756991, sampleRate)
 *   0x0208BDE8: mov  r4, r0                ; r4 = 380 cycles/sample
 */
u32 CMoviePlayer_CalcTicksPerSample(u32 sampleRate)
{
    if (sampleRate == 0) return 0;
    /* Rounded timer clock division: 16,756,991 / 44,100 = 379.977 -> 380 cycles/sample */
    return (SND_TIMER_CLOCK + (sampleRate >> 1)) / sampleRate;
}

/*
 * CMoviePlayer_CalcAlarmPeriod
 *
 * FIX 1: Audio alarm reload period calculation.
 *
 * Original buggy assembly at 0x0208BDF8:
 *   0x0208BDF8: lsl  r5, r4, #2            ; BUG! r5 = r4 << 2 (380 * 4 = 1520 ticks = 4 samples!)
 *
 * Fixed assembly:
 *   lsl r5, r4, #7                         ; FIX! r5 = r4 << 7 (380 * 128 = 48,640 ticks = 128 samples)
 *
 * Matches alarm frequency to audio block consumption:
 *   44100 / 128 = 344.53 Hz, perfectly tracking the chunk production rate.
 */
u32 CMoviePlayer_CalcAlarmPeriod(u32 ticksPerSample)
{
    return ticksPerSample << 7;
}

/*
 * CMoviePlayer_Init
 *
 * Initializes CMoviePlayer state fields to clean default values.
 */
void CMoviePlayer_Init(CMoviePlayer *this)
{
    if (this == NULL) return;
    memset(this, 0, sizeof(CMoviePlayer));
    this->m_fpsFixed = 982057; /* 14.985 fps */
    this->m_threshold = 23;
    this->m_capacity = 115;
}

/*
 * CMoviePlayer_PlayMovie
 *
 * Implements 0x0208B140 / 0x0208B400: opens video, allocates circular buffer,
 * resets 64-bit consumer/producer counters, sets playing flag.
 */
BOOL CMoviePlayer_PlayMovie(CMoviePlayer *this, const char *name, u32 flags)
{
    (void)name;
    if (this == NULL || this->m_isPlaying) return FALSE;

    this->m_frameCounter = 0;
    this->m_skippedFlag = FALSE;
    this->m_audioStarted = FALSE;
    this->m_writeOffset = 0;
    this->m_readCounter = 0;
    this->m_writeCounter = 0;

    if (flags & 1) {
        this->m_dualScreen = TRUE;
    }

    u32 rate = (s_hooks.GetAudioRate != NULL) ? s_hooks.GetAudioRate(this->m_vxTop) : 44100;
    if (rate == 0) rate = 44100;

    u32 fpsFixed = (s_hooks.GetFrameRateFixed != NULL) ? s_hooks.GetFrameRateFixed(this->m_vxTop) : 982057;
    if (fpsFixed == 0) fpsFixed = 982057;
    this->m_fpsFixed = fpsFixed;

    this->m_threshold = CMoviePlayer_CalcThreshold(rate, fpsFixed);
    this->m_capacity = CMoviePlayer_CalcCapacity(this->m_threshold);

    u32 bufBytes = CMoviePlayer_CalcCapacityBytes(this->m_capacity);
    if (this->m_pAudioBuffer != NULL) {
        free(this->m_pAudioBuffer);
        this->m_pAudioBuffer = NULL;
    }
    this->m_pAudioBuffer = (s16 *)malloc(bufBytes);
    if (this->m_pAudioBuffer == NULL) {
        return FALSE;
    }
    memset(this->m_pAudioBuffer, 0, bufBytes);

    this->m_isPlaying = TRUE;
    return TRUE;
}

/*
 * CMoviePlayer_StopMovie
 *
 * Implements 0x0208B5C0: stops audio playback and frees circular audio buffer.
 */
void CMoviePlayer_StopMovie(CMoviePlayer *this)
{
    if (this == NULL || !this->m_isPlaying) return;

    CMoviePlayer_StopAudio(this);

    if (this->m_pAudioBuffer != NULL) {
        free(this->m_pAudioBuffer);
        this->m_pAudioBuffer = NULL;
    }

    this->m_isPlaying = FALSE;
    this->m_audioStarted = FALSE;
    this->m_writeOffset = 0;
}

/*
 * CMoviePlayer_StartAudio
 *
 * Implements 0x0208BDD4: configures hardware sound channel and starts repeating alarm.
 */
void CMoviePlayer_StartAudio(CMoviePlayer *this, u32 sampleRate)
{
    if (this == NULL || sampleRate == 0) return;

    u32 sampleTicks = CMoviePlayer_CalcTicksPerSample(sampleRate);
    this->m_ticksPerSample = sampleTicks;

    u32 bufferBytes = CMoviePlayer_CalcCapacityBytes(this->m_capacity);

    /* FIX 1: Compute alarm period for 128 samples (<< 7) instead of 4 samples (<< 2) */
    u32 alarmPeriod = CMoviePlayer_CalcAlarmPeriod(sampleTicks);

    if (this->m_pAudioBuffer != NULL && s_hooks.DC_FlushRange != NULL) {
        s_hooks.DC_FlushRange(this->m_pAudioBuffer, bufferBytes);
    }

    if (s_hooks.SND_LockChannel != NULL) {
        s_hooks.SND_LockChannel(1); /* Lock Sound Channel 0 */
    }

    /* Setup circular PCM16 playback channel */
    u32 loopLenWords = (this->m_capacity << 7) >> 1; /* capacity * 64 words */
    if (s_hooks.SND_SetupChannelPcm != NULL) {
        s_hooks.SND_SetupChannelPcm(
            0,                                      /* Channel 0 */
            SND_WAVE_FORMAT_PCM16,                  /* 16-bit PCM (1) */
            this->m_pAudioBuffer,                   /* Buffer ptr */
            SND_CHANNEL_LOOP_REPEAT,                /* Repeat loop (1) */
            0,                                      /* Loop start */
            (int)loopLenWords,                      /* Loop length in words (7,360) */
            SND_VOLUME_MAX,                         /* Volume 127 */
            SND_CHANNEL_DATASHIFT_NONE,             /* Shift 0 */
            (int)sampleTicks,                       /* Timer ticks per sample (380) */
            SND_PAN_CENTER                          /* Pan center (64) */
        );
    }

    /* Setup periodic alarm callback matching audio chunk consumption rate */
    if (s_hooks.SND_SetAlarm != NULL) {
        s_hooks.SND_SetAlarm(
            0,                                      /* Alarm 0 */
            alarmPeriod,                            /* Initial tick (48,640) */
            alarmPeriod,                            /* Periodic tick (48,640) */
            CMoviePlayer_SoundAlarmCallback,        /* Callback handler (0x0208BD60) */
            this                                    /* Callback argument */
        );
    }
    if (s_hooks.SND_StartAlarm != NULL) {
        s_hooks.SND_StartAlarm(0);
    }
    this->m_audioStarted = TRUE;
}

/*
 * CMoviePlayer_StopAudio
 *
 * Implements 0x0208BE8C: stops sound alarm and releases audio channel.
 */
void CMoviePlayer_StopAudio(CMoviePlayer *this)
{
    if (this == NULL) return;

    if (this->m_audioStarted) {
        if (s_hooks.SND_StopAlarm != NULL) {
            s_hooks.SND_StopAlarm(0);
        }
        if (s_hooks.SND_UnlockChannel != NULL) {
            s_hooks.SND_UnlockChannel(1);
        }
        this->m_audioStarted = FALSE;
    }
}

/*
 * CMoviePlayer_SoundAlarmCallback
 *
 * Implements 0x0208BD60: Sound alarm interrupt callback.
 * Invoked periodically every 128 samples by ARM7/ARM9 hardware sound timer.
 */
void CMoviePlayer_SoundAlarmCallback(void *arg)
{
    CMoviePlayer *player = (CMoviePlayer *)arg;
    if (player == NULL) {
        player = CMoviePlayer_GetInstance();
    }
    if (player != NULL) {
        CMoviePlayer_AdvanceConsumerCounter(player);
    }
}

/*
 * CMoviePlayer_AdvanceConsumerCounter
 *
 * Implements 0x0208BDB8:
 *   0x0208BDB8: ldr  r2, [r0, #0xd0]       ; m_readCounterLo
 *   0x0208BDBC: ldr  r1, [r0, #0xd4]       ; m_readCounterHi
 *   0x0208BDC0: adds r2, r2, #1            ; readCounterLo++
 *   0x0208BDC4: str  r2, [r0, #0xd0]
 *   0x0208BDC8: adc  r1, r1, #0            ; readCounterHi += carry
 *   0x0208BDCC: str  r1, [r0, #0xd4]
 */
void CMoviePlayer_AdvanceConsumerCounter(CMoviePlayer *this)
{
    if (this != NULL) {
        this->m_readCounter++;
    }
}

/*
 * CMoviePlayer_DecodeAndRenderFrame
 *
 * Implements 0x0208BEB8: renders top and bottom screens.
 */
void CMoviePlayer_DecodeAndRenderFrame(CMoviePlayer *this, VXHandle vxTop, VXHandle vxBottom)
{
    if (this == NULL) return;
    if (s_hooks.DecodeAndRender != NULL) {
        s_hooks.DecodeAndRender(this, vxTop, vxBottom);
    }
}

/*
 * CMoviePlayer_Update
 *
 * Implements 0x0208B70C: main frame update loop for movie playback.
 * Incorporates Fixes 2, 3, and 4.
 */
BOOL CMoviePlayer_Update(CMoviePlayer *this)
{
    if (this == NULL || !this->m_isPlaying)
        return FALSE;

    if (s_hooks.IsPlaying != NULL && !s_hooks.IsPlaying(this->m_vxTop))
        return TRUE;

    this->m_frameCounter++;

    /* Audio start trigger on frame 4 */
    if (!this->m_audioStarted && this->m_frameCounter >= 4) {
        u32 rate = (s_hooks.GetAudioRate != NULL) ? s_hooks.GetAudioRate(this->m_vxTop) : 44100;
        CMoviePlayer_StartAudio(this, rate);
    }

    /* Audio chunk decode loop */
    u32 availableChunks = (s_hooks.GetAvailableAudioChunks != NULL) ?
                          s_hooks.GetAvailableAudioChunks(this->m_vxTop) : 0;

    for (u32 i = 0; i < availableChunks; i++) {
        if (this->m_audioStarted) {
            /*
             * FIX 4: Prevent spin-lock deadlock.
             * Original assembly at 0x0208B870 - 0x0208B880 entered an infinite busy-spin
             * loop on the ARM9 main thread (beq #0x208b860) when ring buffer was full.
             * Fix: check if buffer is full; if so, break gracefully and yield to next frame.
             */
            s64 diff = (s64)(this->m_writeCounter - this->m_readCounter);
            if (diff >= (s64)this->m_capacity) {
                break;
            }
        }

        if (this->m_pAudioBuffer == NULL) {
            break;
        }

        s16 *dest = &this->m_pAudioBuffer[this->m_writeOffset];
        int result = 0;
        if (s_hooks.DecodeAudioChunk != NULL) {
            result = s_hooks.DecodeAudioChunk(this->m_vxTop, dest);
        }

        /*
         * FIX 3: Audio EOF & mute handling.
         * Original assembly at 0x0208B894 ignored the return code of VX_DecodeAudioChunk.
         * When audio hits EOF (result <= 0), clear destination buffer to silence (0)
         * and exit loop to prevent SND_CHANNEL_LOOP_REPEAT from endlessly repeating stale audio.
         */
        if (result <= 0) {
            memset(dest, 0, MOVIE_AUDIO_BLOCK_BYTES);
            if (s_hooks.DC_FlushRange != NULL) {
                s_hooks.DC_FlushRange(dest, MOVIE_AUDIO_BLOCK_BYTES);
            }
            break;
        }

        if (s_hooks.DC_FlushRange != NULL) {
            s_hooks.DC_FlushRange(dest, MOVIE_AUDIO_BLOCK_BYTES);
        }

        /*
         * Fix: Ring buffer pointer wrap at exact boundary.
         * Advances by 128 samples and wraps using upper-bound inequality (>= capacity * 128).
         */
        this->m_writeOffset += MOVIE_AUDIO_BLOCK_SAMPLES;
        if (this->m_writeOffset >= (this->m_capacity << 7)) {
            this->m_writeOffset = 0;
        }

        /* 64-bit producer counter increment */
        this->m_writeCounter++;
    }

    /*
     * Video frame synchronization & frame drop logic (0x0208B934 - 0x0208B998)
     */
    if (this->m_frameCounter >= 4) {
        /*
         * FIX 2: Video sync logic with 64-bit counters.
         * Original assembly: subs r1, r2, r1; cmp r1, r0; bgt render; fallthrough: skip
         * In buggy version, 32x alarm mismatch caused write - read to be negative.
         * The signed comparison diff <= threshold dropped alternate frames, cutting framerate in half.
         *
         * With 64-bit counters and matching alarm rate, diff correctly reflects buffered audio.
         * When diff > threshold, the video renders smoothly at full 14.985 fps.
         */
        s64 diff = (s64)(this->m_writeCounter - this->m_readCounter);

        if (diff > (s64)this->m_threshold) {
            CMoviePlayer_DecodeAndRenderFrame(this, this->m_vxTop, this->m_vxBottom);
            this->m_skippedFlag = FALSE;
        } else {
            /* Audio buffer underflow: skip frame to let audio stream catch up */
            if (!this->m_skippedFlag) {
                if (s_hooks.SkipFrame != NULL) {
                    s_hooks.SkipFrame(this->m_vxTop);
                    if (this->m_dualScreen) {
                        s_hooks.SkipFrame(this->m_vxBottom);
                    }
                }
                this->m_skippedFlag = TRUE;
            } else {
                /* Must render at least alternate frames to prevent complete freeze */
                CMoviePlayer_DecodeAndRenderFrame(this, this->m_vxTop, this->m_vxBottom);
                this->m_skippedFlag = FALSE;
            }
        }
    } else {
        CMoviePlayer_DecodeAndRenderFrame(this, this->m_vxTop, this->m_vxBottom);
    }

    return FALSE;
}

/*
 * Singleton Accessor Functions
 */
CMoviePlayer *CMoviePlayer_GetInstance(void)
{
    return s_moviePlayerInstance;
}

void CMoviePlayer_SetInstance(CMoviePlayer *player)
{
    s_moviePlayerInstance = player;
}
