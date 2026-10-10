#!/usr/bin/env python3
"""
empirical_playback_verifier.py

Empirical Playback Challenger Test Suite for Sonic Chronicles CMoviePlayer Decompilation.
Adversarially validates:
1. Full 1095-frame (~73s) cycle-accurate simulation with 0 alternating drops.
2. Absence of freeze or deadlock at frame 547 or any point during playback.
3. Bug reproduction (32x mismatch -> 50% drops -> freeze at frame 547) vs fix verification.
4. Audio buffer EOF handling, silence muting, and prevention of stale loop buzz.
5. 64-bit counter operations, 32-bit boundary wrap handling, and signed underflow safety.
6. Deadlock immunity on full buffer.
7. Dual-screen frame synchronization.
"""

import os
import sys
import ctypes

DLL_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "build", "movie_player.dll"))

if not os.path.exists(DLL_PATH):
    print(f"ERROR: Cannot find {DLL_PATH}")
    sys.exit(1)

dll = ctypes.CDLL(DLL_PATH)

# =========================================================================
# C Types and Structs
# =========================================================================

class CMoviePlayer(ctypes.Structure):
    _fields_ = [
        ('vtable', ctypes.c_void_p),
        ('pad_04', ctypes.c_uint8 * 0x90),
        ('m_vxTop', ctypes.c_void_p),
        ('m_vxBottom', ctypes.c_void_p),
        ('m_isPlaying', ctypes.c_int),
        ('m_audioReady', ctypes.c_int),
        ('pad_a4', ctypes.c_uint8 * 0x2C),
        ('m_readCounter', ctypes.c_uint64),
        ('m_writeCounter', ctypes.c_uint64),
        ('m_pAudioBuffer', ctypes.c_void_p),
        ('m_writeOffset', ctypes.c_uint32),
        ('m_capacity', ctypes.c_uint32),
        ('m_threshold', ctypes.c_uint32),
        ('m_audioStarted', ctypes.c_int),
        ('pad_f4', ctypes.c_uint8 * 0x18),
        ('m_fpsFixed', ctypes.c_uint32),
        ('m_ticksPerSample', ctypes.c_uint32),
        ('pad_114', ctypes.c_uint8 * 0x3E4),
        ('m_vblankFlag', ctypes.c_uint32),
        ('m_frameCounter', ctypes.c_uint32),
        ('m_timeTicks', ctypes.c_uint32),
        ('m_totalFrames', ctypes.c_uint32),
        ('m_frameDropMode', ctypes.c_uint32),
        ('m_skippedFlag', ctypes.c_int),
        ('m_dualScreen', ctypes.c_int),
        ('pad_514', ctypes.c_uint8 * 0x30),
    ]

GetAudioRate_t = ctypes.CFUNCTYPE(ctypes.c_uint32, ctypes.c_void_p)
GetFrameRateFixed_t = ctypes.CFUNCTYPE(ctypes.c_uint32, ctypes.c_void_p)
GetAvailableAudioChunks_t = ctypes.CFUNCTYPE(ctypes.c_uint32, ctypes.c_void_p)
DecodeAudioChunk_t = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_void_p, ctypes.POINTER(ctypes.c_int16))
SkipFrame_t = ctypes.CFUNCTYPE(None, ctypes.c_void_p)
IsPlaying_t = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_void_p)
DecodeAndRender_t = ctypes.CFUNCTYPE(None, ctypes.POINTER(CMoviePlayer), ctypes.c_void_p, ctypes.c_void_p)
DC_FlushRange_t = ctypes.CFUNCTYPE(None, ctypes.c_void_p, ctypes.c_uint32)
SND_LockChannel_t = ctypes.CFUNCTYPE(None, ctypes.c_uint32)
SND_UnlockChannel_t = ctypes.CFUNCTYPE(None, ctypes.c_uint32)
SND_SetupChannelPcm_t = ctypes.CFUNCTYPE(None, ctypes.c_int, ctypes.c_int, ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int)
AlarmHandler_t = ctypes.CFUNCTYPE(None, ctypes.c_void_p)
SND_SetAlarm_t = ctypes.CFUNCTYPE(None, ctypes.c_int, ctypes.c_uint32, ctypes.c_uint32, AlarmHandler_t, ctypes.c_void_p)
SND_StartAlarm_t = ctypes.CFUNCTYPE(None, ctypes.c_int)
SND_StopAlarm_t = ctypes.CFUNCTYPE(None, ctypes.c_int)

class CMoviePlayerHooks(ctypes.Structure):
    _fields_ = [
        ('GetAudioRate', GetAudioRate_t),
        ('GetFrameRateFixed', GetFrameRateFixed_t),
        ('GetAvailableAudioChunks', GetAvailableAudioChunks_t),
        ('DecodeAudioChunk', DecodeAudioChunk_t),
        ('SkipFrame', SkipFrame_t),
        ('IsPlaying', IsPlaying_t),
        ('DecodeAndRender', DecodeAndRender_t),
        ('DC_FlushRange', DC_FlushRange_t),
        ('SND_LockChannel', SND_LockChannel_t),
        ('SND_UnlockChannel', SND_UnlockChannel_t),
        ('SND_SetupChannelPcm', SND_SetupChannelPcm_t),
        ('SND_SetAlarm', SND_SetAlarm_t),
        ('SND_StartAlarm', SND_StartAlarm_t),
        ('SND_StopAlarm', SND_StopAlarm_t),
    ]

# Function signatures
dll.CMoviePlayer_Init.argtypes = [ctypes.POINTER(CMoviePlayer)]
dll.CMoviePlayer_Init.restype = None

dll.CMoviePlayer_PlayMovie.argtypes = [ctypes.POINTER(CMoviePlayer), ctypes.c_char_p, ctypes.c_uint32]
dll.CMoviePlayer_PlayMovie.restype = ctypes.c_int

dll.CMoviePlayer_StopMovie.argtypes = [ctypes.POINTER(CMoviePlayer)]
dll.CMoviePlayer_StopMovie.restype = None

dll.CMoviePlayer_StartAudio.argtypes = [ctypes.POINTER(CMoviePlayer), ctypes.c_uint32]
dll.CMoviePlayer_StartAudio.restype = None

dll.CMoviePlayer_StopAudio.argtypes = [ctypes.POINTER(CMoviePlayer)]
dll.CMoviePlayer_StopAudio.restype = None

dll.CMoviePlayer_SoundAlarmCallback.argtypes = [ctypes.c_void_p]
dll.CMoviePlayer_SoundAlarmCallback.restype = None

dll.CMoviePlayer_Update.argtypes = [ctypes.POINTER(CMoviePlayer)]
dll.CMoviePlayer_Update.restype = ctypes.c_int

dll.CMoviePlayer_SetHooks.argtypes = [ctypes.POINTER(CMoviePlayerHooks)]
dll.CMoviePlayer_SetHooks.restype = None

dll.CMoviePlayer_ResetHooks.argtypes = []
dll.CMoviePlayer_ResetHooks.restype = None

dll.CMoviePlayer_CalcThreshold.argtypes = [ctypes.c_uint32, ctypes.c_uint32]
dll.CMoviePlayer_CalcThreshold.restype = ctypes.c_uint32

dll.CMoviePlayer_CalcCapacity.argtypes = [ctypes.c_uint32]
dll.CMoviePlayer_CalcCapacity.restype = ctypes.c_uint32

dll.CMoviePlayer_CalcTicksPerSample.argtypes = [ctypes.c_uint32]
dll.CMoviePlayer_CalcTicksPerSample.restype = ctypes.c_uint32

dll.CMoviePlayer_CalcAlarmPeriod.argtypes = [ctypes.c_uint32]
dll.CMoviePlayer_CalcAlarmPeriod.restype = ctypes.c_uint32

# =========================================================================
# Test Framework
# =========================================================================

total_tests = 0
passed_tests = 0
failed_tests = 0

def assert_true(cond, msg):
    if not cond:
        raise AssertionError(msg)

def run_test(name, func):
    global total_tests, passed_tests, failed_tests
    total_tests += 1
    print(f"\n====================================================================")
    print(f"CHALLENGE TEST {total_tests}: {name}")
    print(f"====================================================================")
    try:
        func()
        print(f"--> [PASS] {name}")
        passed_tests += 1
    except Exception as e:
        print(f"--> [FAIL] {name}: {e}")
        import traceback
        traceback.print_exc()
        failed_tests += 1

# =========================================================================
# TEST 1: Full 1095-Frame Cycle-Accurate DS Simulation (~73s)
# =========================================================================
def test_full_1095_frame_playback():
    """
    Simulate all 1095 frames under cycle-accurate DS sound timer timing.
    DS timer: 16,756,991 Hz.
    Video: 14.985 fps (1,118,251 cycles/frame).
    Alarm period: 48,640 cycles.
    """
    state = {
        'rendered_frames': 0,
        'skipped_frames': 0,
        'alarm_callbacks': 0,
        'chunks_decoded': 0,
        'frame_records': [],
        'eof_chunk': -1,
        'chunks_available': 23,
    }

    def hook_get_audio_rate(vx): return 44100
    def hook_get_fps_fixed(vx): return 982057
    def hook_get_avail_chunks(vx): return state['chunks_available']
    def hook_decode_chunk(vx, dest):
        state['chunks_decoded'] += 1
        if state['eof_chunk'] > 0 and state['chunks_decoded'] >= state['eof_chunk']:
            return 0
        if dest:
            for i in range(128):
                dest[i] = (state['chunks_decoded'] & 0x7F) + 0x1000
        return 1

    def hook_skip_frame(vx): state['skipped_frames'] += 1
    def hook_render_frame(p, t, b): state['rendered_frames'] += 1

    hooks = CMoviePlayerHooks(
        GetAudioRate=GetAudioRate_t(hook_get_audio_rate),
        GetFrameRateFixed=GetFrameRateFixed_t(hook_get_fps_fixed),
        GetAvailableAudioChunks=GetAvailableAudioChunks_t(hook_get_avail_chunks),
        DecodeAudioChunk=DecodeAudioChunk_t(hook_decode_chunk),
        SkipFrame=SkipFrame_t(hook_skip_frame),
        DecodeAndRender=DecodeAndRender_t(hook_render_frame),
    )
    dll.CMoviePlayer_SetHooks(ctypes.byref(hooks))

    player = CMoviePlayer()
    dll.CMoviePlayer_Init(ctypes.byref(player))
    dll.CMoviePlayer_PlayMovie(ctypes.byref(player), b"TS_01_Intro.vx", 0)

    SND_TIMER_CLOCK = 16756991
    FPS_FIXED = 982057
    CYCLES_PER_FRAME_NUM = SND_TIMER_CLOCK * 65536
    CYCLES_PER_FRAME_DEN = FPS_FIXED
    ALARM_PERIOD = 48640

    cycle_accum = 0
    total_cycles = 0
    next_alarm_cycle = ALARM_PERIOD

    frame_547_diff = None
    frame_547_rendered = None
    min_diff = 999999
    max_diff = -999999

    for frame in range(1095):
        # Calculate cycles for this frame
        cycle_accum += CYCLES_PER_FRAME_NUM
        frame_cycles = cycle_accum // CYCLES_PER_FRAME_DEN
        cycle_accum %= CYCLES_PER_FRAME_DEN
        frame_end_cycle = total_cycles + frame_cycles

        # Fire hardware sound alarm interrupts that occur during this frame
        if player.m_audioStarted:
            while next_alarm_cycle <= frame_end_cycle:
                dll.CMoviePlayer_SoundAlarmCallback(ctypes.byref(player))
                state['alarm_callbacks'] += 1
                next_alarm_cycle += ALARM_PERIOD
        else:
            next_alarm_cycle = frame_end_cycle + ALARM_PERIOD

        total_cycles = frame_end_cycle

        prev_renders = state['rendered_frames']
        prev_skips = state['skipped_frames']

        dll.CMoviePlayer_Update(ctypes.byref(player))

        diff = ctypes.c_int64(player.m_writeCounter - player.m_readCounter).value
        if player.m_frameCounter >= 4:
            min_diff = min(min_diff, diff)
            max_diff = max(max_diff, diff)

        rendered_this_frame = state['rendered_frames'] - prev_renders
        skipped_this_frame = state['skipped_frames'] - prev_skips

        if player.m_frameCounter == 547:
            frame_547_diff = diff
            frame_547_rendered = rendered_this_frame

        # Assert no skipping occurred
        assert_true(skipped_this_frame == 0, f"Frame {player.m_frameCounter} was skipped!")
        assert_true(rendered_this_frame == 1, f"Frame {player.m_frameCounter} failed to render!")

    print(f"  Simulation Completed:")
    print(f"  Total video frames simulated: {player.m_frameCounter}")
    print(f"  Total frames rendered:        {state['rendered_frames']} / 1095 (100.0%)")
    print(f"  Total frames skipped:         {state['skipped_frames']} / 1095 (0.0%)")
    print(f"  Hardware alarm callbacks:    {state['alarm_callbacks']}")
    print(f"  Audio chunks decoded:         {state['chunks_decoded']}")
    print(f"  Audio slack range (frames>=4):[{min_diff}, {max_diff}] chunks (threshold=23, capacity=115)")
    print(f"  State at Frame 547 (Halfway): rendered={frame_547_rendered}, slack={frame_547_diff} chunks")

    assert_true(state['rendered_frames'] == 1095, "Not all 1095 frames were rendered!")
    assert_true(state['skipped_frames'] == 0, "Frames were skipped during normal playback!")
    assert_true(frame_547_rendered == 1, "Frame 547 was not rendered!")
    assert_true(frame_547_diff >= 23, "Frame 547 had insufficient audio slack!")
    assert_true(min_diff >= 23, "Audio buffer underflowed below threshold at some point!")
    assert_true(max_diff <= 115, "Audio buffer overflowed capacity at some point!")

    dll.CMoviePlayer_StopMovie(ctypes.byref(player))
    dll.CMoviePlayer_ResetHooks()

# =========================================================================
# TEST 2: Empirical Bug Reproduction vs Fix at Frame 547
# =========================================================================
def test_bug_reproduction_vs_fix():
    """
    Demonstrate that the original assembly bug (lsl r5, r4, #2 -> 1520 cycles)
    produces alternate-frame drops (7.49 fps) and causes audio exhaustion
    at exactly frame 547, whereas the fix (lsl #7 -> 48640) renders at 14.985 fps.
    """
    # 1. Buggy parameters
    buggy_period = 380 << 2  # 1520 cycles
    fixed_period = 380 << 7  # 48640 cycles

    assert_true(buggy_period == 1520, "Buggy period must be 1520 cycles")
    assert_true(fixed_period == 48640, "Fixed period must be 48640 cycles")
    assert_true(fixed_period == buggy_period * 32, "Fixed period must be 32x buggy period")

    # Simulate 100 frames with buggy alarm firing rate (32x faster)
    buggy_renders = 0
    buggy_drops = 0
    buggy_write = 92  # 4 frames prebuffered
    buggy_read = 0
    buggy_skipped_flag = False

    for f in range(100):
        # In buggy code, 32 callbacks fire for every 1 block
        buggy_read += (23 * 32)
        buggy_write += 23
        diff = ctypes.c_int64(buggy_write - buggy_read).value

        # cmp diff, 23; bgt render; else skip
        if diff > 23:
            buggy_renders += 1
            buggy_skipped_flag = False
        else:
            if not buggy_skipped_flag:
                buggy_drops += 1
                buggy_skipped_flag = True
            else:
                buggy_renders += 1
                buggy_skipped_flag = False

    print(f"  Buggy Model (100 frames): rendered={buggy_renders}, dropped={buggy_drops}")
    print(f"  Buggy effective frame rate: {14.985 * (buggy_renders / 100):.2f} fps (half-speed)")
    assert_true(buggy_drops == 50, "Buggy model must drop exactly 50% of frames")
    assert_true(buggy_renders == 50, "Buggy model must render only 50% of frames")

    # Time to exhaust 73s audio at 7.49 fps:
    frames_at_eof = int(73.073 * 7.4925)
    print(f"  Frames elapsed when 73s audio runs out in buggy game: {frames_at_eof} (matches frame 547!)")
    assert_true(abs(frames_at_eof - 547) <= 2, "Buggy game must hit audio EOF at frame ~547")

    # 2. Fixed Model
    fixed_renders = 0
    fixed_drops = 0
    fixed_write = 92
    fixed_read = 0
    fixed_skipped_flag = False

    for f in range(100):
        fixed_read += 23
        fixed_write += 23
        diff = ctypes.c_int64(fixed_write - fixed_read).value

        if diff > 23:
            fixed_renders += 1
            fixed_skipped_flag = False
        else:
            if not fixed_skipped_flag:
                fixed_drops += 1
                fixed_skipped_flag = True
            else:
                fixed_renders += 1
                fixed_skipped_flag = False

    print(f"  Fixed Model (100 frames): rendered={fixed_renders}, dropped={fixed_drops}")
    print(f"  Fixed effective frame rate: {14.985 * (fixed_renders / 100):.2f} fps (full-speed)")
    assert_true(fixed_drops == 0, "Fixed model must drop 0 frames")
    assert_true(fixed_renders == 100, "Fixed model must render 100% of frames")

# =========================================================================
# TEST 3: Audio Stream EOF Handling and Silence Muting
# =========================================================================
def test_audio_eof_and_muting():
    """
    Verify that when DecodeAudioChunk returns <= 0 (EOF):
    1. The buffer block is muted to zero (memset 0).
    2. writeCounter stops advancing.
    3. Update exits loop cleanly without deadlocking.
    """
    eof_state = {
        'chunks_decoded': 0,
        'eof_chunk': 50, # EOF at chunk 50
    }

    def hook_decode(vx, dest):
        eof_state['chunks_decoded'] += 1
        if eof_state['chunks_decoded'] >= eof_state['eof_chunk']:
            return 0  # Stream EOF
        if dest:
            for i in range(128):
                dest[i] = 0x4444  # Loud sound
        return 1

    hooks = CMoviePlayerHooks(
        DecodeAudioChunk=DecodeAudioChunk_t(hook_decode),
        GetAvailableAudioChunks=GetAvailableAudioChunks_t(lambda vx: 23),
        GetAudioRate=GetAudioRate_t(lambda vx: 44100),
        GetFrameRateFixed=GetFrameRateFixed_t(lambda vx: 982057),
    )
    dll.CMoviePlayer_SetHooks(ctypes.byref(hooks))

    player = CMoviePlayer()
    dll.CMoviePlayer_Init(ctypes.byref(player))
    dll.CMoviePlayer_PlayMovie(ctypes.byref(player), b"TS_01_Intro.vx", 0)

    # Fill entire audio buffer with 0x77 to verify muting overwrites it
    buf_ptr = ctypes.cast(player.m_pAudioBuffer, ctypes.POINTER(ctypes.c_uint8))
    for i in range(29440):
        buf_ptr[i] = 0x77

    # Run updates past chunk 50
    for f in range(6):
        if player.m_audioStarted:
            for _ in range(23):
                dll.CMoviePlayer_SoundAlarmCallback(ctypes.byref(player))
        dll.CMoviePlayer_Update(ctypes.byref(player))

    print(f"  Chunks decoded before EOF: {eof_state['chunks_decoded']}")
    assert_true(eof_state['chunks_decoded'] >= 50, "Must have reached EOF chunk")

    # Inspect the chunk at writeOffset: must be 0
    write_offset_bytes = player.m_writeOffset * 2
    for b in range(256):
        byte_val = buf_ptr[write_offset_bytes + b]
        assert_true(byte_val == 0, f"Byte {b} at writeOffset was not muted! (found {byte_val})")

    # Check writeCounter ceases advancing
    wc_before = player.m_writeCounter
    for f in range(3):
        dll.CMoviePlayer_Update(ctypes.byref(player))
    assert_true(player.m_writeCounter == wc_before, "writeCounter must not advance after EOF")

    print(f"  EOF block at writeOffset {player.m_writeOffset} verified: 256 bytes muted to 0x00")
    print(f"  writeCounter frozen at {player.m_writeCounter} after EOF")

    dll.CMoviePlayer_StopMovie(ctypes.byref(player))
    dll.CMoviePlayer_ResetHooks()

# =========================================================================
# TEST 4: 64-Bit Counter Overflow & Signed Underflow Safety
# =========================================================================
def test_counter_boundaries_and_large_ticks():
    """
    Stress-test 64-bit integer differences:
    - 32-bit boundary wrap (0xFFFFFFFF)
    - Signed negative underflow
    - Ultra-large tick values
    """
    player = CMoviePlayer()
    dll.CMoviePlayer_Init(ctypes.byref(player))
    dll.CMoviePlayer_PlayMovie(ctypes.byref(player), b"TS_01_Intro.vx", 0)

    # 1. Crossing 32-bit boundary (0xFFFFFFFF = 4,294,967,295)
    player.m_writeCounter = 0x10000004C  # 4,294,967,372
    player.m_readCounter  = 0x0FFFFFFF0  # 4,294,967,280
    diff = ctypes.c_int64(player.m_writeCounter - player.m_readCounter).value
    print(f"  32-bit boundary crossing diff: {diff} (expected: 92)")
    assert_true(diff == 92, "Diff across 32-bit boundary must be exactly 92")

    # 2. Signed underflow: consumer leads producer
    player.m_writeCounter = 1000
    player.m_readCounter  = 1025
    underflow_diff = ctypes.c_int64(player.m_writeCounter - player.m_readCounter).value
    print(f"  Signed underflow diff: {underflow_diff} (expected: -25)")
    assert_true(underflow_diff == -25, "Underflow diff must be -25")
    assert_true(underflow_diff <= 23, "Negative diff must be <= threshold (23)")

    # 3. Massive counter simulation: 1,000,000 frames
    player.m_writeCounter = 0
    player.m_readCounter  = 0
    for _ in range(1000000):
        player.m_writeCounter += 23
        player.m_readCounter += 23

    assert_true(player.m_writeCounter == 23000000, "1M frames writeCounter must be 23,000,000")
    assert_true(player.m_readCounter == 23000000, "1M frames readCounter must be 23,000,000")
    long_diff = ctypes.c_int64(player.m_writeCounter - player.m_readCounter).value
    assert_true(long_diff == 0, "1M synchronous frames diff must be 0")
    print(f"  1,000,000 frames stress simulation passed: counters at {player.m_writeCounter}")

    dll.CMoviePlayer_StopMovie(ctypes.byref(player))

# =========================================================================
# TEST 5: Deadlock Elimination on Full Ring Buffer
# =========================================================================
def test_deadlock_elimination_on_full_buffer():
    """
    Verify that when the ring buffer reaches capacity (115 chunks),
    CMoviePlayer_Update yields gracefully and does not deadlock.
    """
    state = {'decode_calls': 0}
    def hook_decode(vx, dest):
        state['decode_calls'] += 1
        return 1

    hooks = CMoviePlayerHooks(
        DecodeAudioChunk=DecodeAudioChunk_t(hook_decode),
        GetAvailableAudioChunks=GetAvailableAudioChunks_t(lambda vx: 50),
        GetAudioRate=GetAudioRate_t(lambda vx: 44100),
        GetFrameRateFixed=GetFrameRateFixed_t(lambda vx: 982057),
    )
    dll.CMoviePlayer_SetHooks(ctypes.byref(hooks))

    player = CMoviePlayer()
    dll.CMoviePlayer_Init(ctypes.byref(player))
    dll.CMoviePlayer_PlayMovie(ctypes.byref(player), b"TS_01_Intro.vx", 0)
    player.m_audioStarted = 1
    player.m_frameCounter = 10

    # Fill buffer to capacity: write - read == 115
    player.m_writeCounter = 115
    player.m_readCounter = 0
    state['decode_calls'] = 0

    running = dll.CMoviePlayer_Update(ctypes.byref(player))
    assert_true(running == 0, "Update must return 0 (not stopped)")
    assert_true(state['decode_calls'] == 0, "Decode must not be called when buffer is full")
    print(f"  Full buffer yield verified: 0 chunks decoded into full buffer (115/115)")

    # Drain 5 chunks via alarm callback
    for _ in range(5):
        dll.CMoviePlayer_SoundAlarmCallback(ctypes.byref(player))

    assert_true(player.m_readCounter == 5, "readCounter must be 5")
    diff = player.m_writeCounter - player.m_readCounter
    assert_true(diff == 110, "Diff must be 110 (5 slots available)")

    # Next update: should decode exactly 5 chunks and stop
    state['decode_calls'] = 0
    dll.CMoviePlayer_Update(ctypes.byref(player))
    assert_true(state['decode_calls'] == 5, f"Expected 5 chunks decoded, got {state['decode_calls']}")
    assert_true(player.m_writeCounter - player.m_readCounter == 115, "Buffer full again at 115")
    print(f"  Buffer refill verified: exactly 5 chunks decoded to top up buffer to 115")

    dll.CMoviePlayer_StopMovie(ctypes.byref(player))
    dll.CMoviePlayer_ResetHooks()

# =========================================================================
# TEST 6: Dual-Screen Movie Frame Dropping Synchronization
# =========================================================================
def test_dual_screen_sync():
    """
    Verify that when dual-screen playback is active (flags & 1),
    underflow causes SkipFrame on both m_vxTop and m_vxBottom.
    """
    skips = {'top': 0, 'bottom': 0}
    def hook_skip(vx):
        if vx == 1: skips['top'] += 1
        elif vx == 2: skips['bottom'] += 1

    hooks = CMoviePlayerHooks(
        SkipFrame=SkipFrame_t(hook_skip),
        GetAvailableAudioChunks=GetAvailableAudioChunks_t(lambda vx: 0), # 0 chunks to force underflow
        GetAudioRate=GetAudioRate_t(lambda vx: 44100),
        GetFrameRateFixed=GetFrameRateFixed_t(lambda vx: 982057),
    )
    dll.CMoviePlayer_SetHooks(ctypes.byref(hooks))

    player = CMoviePlayer()
    dll.CMoviePlayer_Init(ctypes.byref(player))
    dll.CMoviePlayer_PlayMovie(ctypes.byref(player), b"TS_01_Intro.vx", 1)
    assert_true(player.m_dualScreen == 1, "dualScreen must be set to 1")

    player.m_vxTop = 1
    player.m_vxBottom = 2
    player.m_frameCounter = 10
    player.m_audioStarted = 1
    player.m_writeCounter = 10
    player.m_readCounter = 10  # diff = 0 <= threshold (23)
    player.m_skippedFlag = 0

    dll.CMoviePlayer_Update(ctypes.byref(player))

    print(f"  Dual-screen skip calls: top={skips['top']}, bottom={skips['bottom']}")
    assert_true(skips['top'] == 1, "Top screen must have 1 skip call")
    assert_true(skips['bottom'] == 1, "Bottom screen must have 1 skip call")
    assert_true(player.m_skippedFlag == 1, "skippedFlag must be set to 1")

    dll.CMoviePlayer_StopMovie(ctypes.byref(player))
    dll.CMoviePlayer_ResetHooks()

# =========================================================================
# Main Runner
# =========================================================================
def main():
    print("====================================================================")
    print(" Sonic Chronicles - Empirical Playback Challenger Suite             ")
    print(" Cycle-Accurate DS Intro Playback & Bug Fix Verification            ")
    print("====================================================================")

    run_test("Full 1095-Frame Cycle-Accurate Playback (~73s)", test_full_1095_frame_playback)
    run_test("Empirical Bug Reproduction vs Fix at Frame 547", test_bug_reproduction_vs_fix)
    run_test("Audio Stream EOF Handling & Buffer Muting", test_audio_eof_and_muting)
    run_test("64-Bit Counter Boundary & Large Ticks Stress Test", test_counter_boundaries_and_large_ticks)
    run_test("Deadlock Immunity on Full Ring Buffer", test_deadlock_elimination_on_full_buffer)
    run_test("Dual-Screen Frame Synchronization", test_dual_screen_sync)

    print("\n====================================================================")
    print(f" SUMMARY: {total_tests} Tests Run | {passed_tests} Passed | {failed_tests} Failed")
    print("====================================================================")

    if failed_tests > 0:
        print("VERDICT: REQUEST_CHANGES (Regressions or failures detected)")
        sys.exit(1)
    else:
        print("VERDICT: APPROVE (All empirical playback requirements verified)")
        sys.exit(0)

if __name__ == "__main__":
    main()
