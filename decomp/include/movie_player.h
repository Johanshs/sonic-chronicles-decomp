/*
 * CMoviePlayer - Decompiled Video & Audio Playback Subsystem
 *
 * Sonic Chronicles: The Dark Brotherhood (Nintendo DS)
 * Original binary range: 0x0208AB00 - 0x0208C100 (ARM mode)
 *
 * Matches Actimagine VXDS video playback and NitroSDK sound channel streaming.
 */

#ifndef MOVIE_PLAYER_H
#define MOVIE_PLAYER_H

#include "types.h"
#include <stddef.h>
#include <stdint.h>
#include <string.h>
#include <stdlib.h>

#ifndef TRUE
#define TRUE 1
#endif
#ifndef FALSE
#define FALSE 0
#endif

#ifndef NULL
#define NULL ((void *)0)
#endif

/* NitroSDK 64-bit integer definitions */
typedef uint64_t u64;
typedef int64_t  s64;

/* Video & Audio Hardware Constants */
#define SND_TIMER_CLOCK             0x00FFB0FFu  /* 16,756,991 Hz (DS hardware sound timer clock) */
#define MOVIE_AUDIO_BLOCK_SAMPLES   128          /* Samples per audio chunk */
#define MOVIE_AUDIO_SAMPLE_BYTES    sizeof(s16)  /* 2 bytes per 16-bit PCM sample */
#define MOVIE_AUDIO_BLOCK_BYTES     (MOVIE_AUDIO_BLOCK_SAMPLES * MOVIE_AUDIO_SAMPLE_BYTES) /* 256 bytes */

#define SND_WAVE_FORMAT_PCM16       1            /* 16-bit PCM wave format */
#define SND_CHANNEL_LOOP_REPEAT     1            /* Repeating circular channel loop */
#define SND_CHANNEL_DATASHIFT_NONE  0            /* No data shift */
#define SND_VOLUME_MAX              127          /* Maximum channel volume (0x7F) */
#define SND_PAN_CENTER              64           /* Center stereo pan (0x40) */

/* Original binary member offsets (0x0208AB00 - 0x0208C100) */
#define CMOVIEPLAYER_OFFSET_VX_TOP          0x094
#define CMOVIEPLAYER_OFFSET_VX_BOTTOM       0x098
#define CMOVIEPLAYER_OFFSET_IS_PLAYING      0x09C
#define CMOVIEPLAYER_OFFSET_AUDIO_READY     0x0A0
#define CMOVIEPLAYER_OFFSET_READ_COUNTER    0x0D0
#define CMOVIEPLAYER_OFFSET_WRITE_COUNTER   0x0D8
#define CMOVIEPLAYER_OFFSET_AUDIO_BUFFER    0x0E0
#define CMOVIEPLAYER_OFFSET_WRITE_OFFSET    0x0E4
#define CMOVIEPLAYER_OFFSET_CAPACITY        0x0E8
#define CMOVIEPLAYER_OFFSET_THRESHOLD       0x0EC
#define CMOVIEPLAYER_OFFSET_AUDIO_STARTED   0x0F0
#define CMOVIEPLAYER_OFFSET_FPS_FIXED       0x10C
#define CMOVIEPLAYER_OFFSET_TICKS_SAMPLE    0x110
#define CMOVIEPLAYER_OFFSET_VBLANK_FLAG     0x4F8
#define CMOVIEPLAYER_OFFSET_FRAME_COUNTER   0x4FC
#define CMOVIEPLAYER_OFFSET_TIME_TICKS      0x500
#define CMOVIEPLAYER_OFFSET_TOTAL_FRAMES    0x504
#define CMOVIEPLAYER_OFFSET_FRAME_DROP_MODE 0x508
#define CMOVIEPLAYER_OFFSET_SKIPPED_FLAG    0x50C
#define CMOVIEPLAYER_OFFSET_DUAL_SCREEN     0x510

/* Actimagine VXDS container types */
typedef void *VXHandle;

/* Forward declaration */
typedef struct CMoviePlayer CMoviePlayer;

/*
 * CMoviePlayer_ARM9Layout
 *
 * Strict 32-bit layout matching the Nintendo DS ARM9 binary at 0x0208AB00 - 0x0208C100.
 * Offsets are verified against disassembly:
 * - m_vxTop at 0x94, m_vxBottom at 0x98, m_isPlaying at 0x9C
 * - m_readCounter at 0xD0 (low: 0xD0, high: 0xD4)
 * - m_writeCounter at 0xD8 (low: 0xD8, high: 0xDC)
 * - m_pAudioBuffer at 0xE0, m_writeOffset at 0xE4, m_capacity at 0xE8, m_threshold at 0xEC
 * - m_frameCounter at 0x4FC, m_skippedFlag at 0x50C, m_dualScreen at 0x510
 */
typedef struct CMoviePlayer_ARM9Layout {
    u32 vtable;                        /* 0x000 */
    u8  pad_04[0x90];                  /* 0x004 - 0x093 */
    u32 m_vxTop;                       /* 0x094 */
    u32 m_vxBottom;                    /* 0x098 */
    BOOL m_isPlaying;                  /* 0x09C */
    BOOL m_audioReady;                 /* 0x0A0 */
    u8  pad_a4[0x2C];                  /* 0x0A4 - 0x0CF */
    u64 m_readCounter;                 /* 0x0D0 (low: 0xD0, high: 0xD4) */
    u64 m_writeCounter;                /* 0x0D8 (low: 0xD8, high: 0xDC) */
    u32 m_pAudioBuffer;                /* 0x0E0 */
    u32 m_writeOffset;                 /* 0x0E4 (in samples) */
    u32 m_capacity;                    /* 0x0E8 (in 128-sample chunks) */
    u32 m_threshold;                   /* 0x0EC (in 128-sample chunks) */
    BOOL m_audioStarted;               /* 0x0F0 */
    u8  pad_f4[0x18];                  /* 0x0F4 - 0x10B */
    u32 m_fpsFixed;                    /* 0x10C (16.16 fixed-point) */
    u32 m_ticksPerSample;              /* 0x110 */
    u8  pad_114[0x3E4];                /* 0x114 - 0x4F7 */
    u32 m_vblankFlag;                  /* 0x4F8 */
    u32 m_frameCounter;                /* 0x4FC */
    u32 m_timeTicks;                   /* 0x500 */
    u32 m_totalFrames;                 /* 0x504 */
    u32 m_frameDropMode;               /* 0x508 */
    BOOL m_skippedFlag;                /* 0x50C */
    BOOL m_dualScreen;                 /* 0x510 */
    u8  pad_514[0x30];                 /* 0x514 - 0x543 */
} CMoviePlayer_ARM9Layout;

/*
 * CMoviePlayer struct definition
 * Supports both 32-bit native target and host test harnesses with dual naming conventions.
 */
struct CMoviePlayer {
    void *vtable;                      /* Virtual method table */
    u8 pad_04[0x90];
    VXHandle m_vxTop;                  /* 0x094: Top screen video handle */
    VXHandle m_vxBottom;               /* 0x098: Bottom screen video handle */
    BOOL m_isPlaying;                  /* 0x09C: Playback active */
    BOOL m_audioReady;                 /* 0x0A0: Audio stream available */
    u8 pad_a4[0x2C];
    union {
        u64 m_readCounter;             /* 0x0D0: Audio consumer counter (advanced by alarm) */
        u64 m_audioTicks;
    };
    union {
        u64 m_writeCounter;            /* 0x0D8: Audio producer counter (advanced by decoder) */
        u64 m_audioDecodedTicks;
    };
    union {
        s16 *m_pAudioBuffer;           /* 0x0E0: Circular PCM16 audio buffer */
        s16 *m_audioBuffer;
    };
    union {
        u32 m_writeOffset;             /* 0x0E4: Buffer write offset in samples */
        u32 m_audioWriteOffset;
    };
    union {
        u32 m_capacity;                /* 0x0E8: Buffer capacity in 128-sample blocks (115) */
        u32 m_audioCapacity;
    };
    union {
        u32 m_threshold;               /* 0x0EC: Buffer threshold in 128-sample blocks (23) */
        u32 m_audioThreshold;
    };
    union {
        BOOL m_audioStarted;           /* 0x0F0: Sound channel & alarm initialized */
        BOOL m_audioPlaying;
    };
    u8 pad_f4[0x18];
    u32 m_fpsFixed;                    /* 0x10C: Video frame rate in 16.16 format */
    u32 m_ticksPerSample;              /* 0x110: Hardware timer ticks per sample */
    u8 pad_114[0x3E4];
    u32 m_vblankFlag;                  /* 0x4F8 */
    union {
        u32 m_frameCounter;            /* 0x4FC: Current video frame index */
        u32 m_currentFrameIndex;
    };
    u32 m_timeTicks;                   /* 0x500 */
    u32 m_totalFrames;                 /* 0x504: Total video frames (e.g. 1095) */
    u32 m_frameDropMode;               /* 0x508 */
    union {
        BOOL m_skippedFlag;            /* 0x50C: Video frame skip toggle flag */
        BOOL m_stalled;
    };
    BOOL m_dualScreen;                 /* 0x510: Dual screen movie playback flag */
    u8 pad_514[0x30];
};

/* Calculation & Configuration Helpers */
u32 CMoviePlayer_CalcThreshold(u32 sampleRate, u32 fpsFixed);
u32 CMoviePlayer_CalcCapacity(u32 threshold);
u32 CMoviePlayer_CalcCapacityBytes(u32 capacity);
u32 CMoviePlayer_CalcTicksPerSample(u32 sampleRate);
u32 CMoviePlayer_CalcAlarmPeriod(u32 ticksPerSample);

/* Core CMoviePlayer Lifecycle & Playback Methods */
void CMoviePlayer_Init(CMoviePlayer *this);
BOOL CMoviePlayer_PlayMovie(CMoviePlayer *this, const char *name, u32 flags);
void CMoviePlayer_StopMovie(CMoviePlayer *this);
void CMoviePlayer_StartAudio(CMoviePlayer *this, u32 sampleRate);
void CMoviePlayer_StopAudio(CMoviePlayer *this);
void CMoviePlayer_SoundAlarmCallback(void *arg);
void CMoviePlayer_AdvanceConsumerCounter(CMoviePlayer *this);
BOOL CMoviePlayer_Update(CMoviePlayer *this);
void CMoviePlayer_DecodeAndRenderFrame(CMoviePlayer *this, VXHandle vxTop, VXHandle vxBottom);

/* Singleton Accessors */
CMoviePlayer *CMoviePlayer_GetInstance(void);
void CMoviePlayer_SetInstance(CMoviePlayer *player);

/* Subsystem Hooks (for hardware integration and unit test mocking) */
typedef struct CMoviePlayerHooks {
    u32  (*GetAudioRate)(VXHandle vx);
    u32  (*GetFrameRateFixed)(VXHandle vx);
    u32  (*GetAvailableAudioChunks)(VXHandle vx);
    int  (*DecodeAudioChunk)(VXHandle vx, s16 *dest);
    void (*SkipFrame)(VXHandle vx);
    BOOL (*IsPlaying)(VXHandle vx);
    void (*DecodeAndRender)(CMoviePlayer *player, VXHandle vxTop, VXHandle vxBottom);

    void (*DC_FlushRange)(const void *addr, u32 size);
    void (*SND_LockChannel)(u32 chMask);
    void (*SND_UnlockChannel)(u32 chMask);
    void (*SND_SetupChannelPcm)(int ch, int fmt, const void *data, int loop, int loopStart, int loopLen, int vol, int shift, int timer, int pan);
    void (*SND_SetAlarm)(int alarm, u32 tick, u32 period, void (*handler)(void *), void *arg);
    void (*SND_StartAlarm)(int alarm);
    void (*SND_StopAlarm)(int alarm);
} CMoviePlayerHooks;

void CMoviePlayer_SetHooks(const CMoviePlayerHooks *hooks);
void CMoviePlayer_ResetHooks(void);

#endif /* MOVIE_PLAYER_H */
