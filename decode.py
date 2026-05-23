#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════╗
║                   P H A S E G R I D   D E C O D E R             ║
║        Spatio-Temporal Optical Credential Decoder v0.3           ║
╚══════════════════════════════════════════════════════════════════╝
Usage:
  python phasegrid_decode.py video.mp4
  python phasegrid_decode.py video.mp4 -s 42
  python phasegrid_decode.py video.mp4 --show-signal
  python phasegrid_decode.py video.mp4 --no-preview
"""

import sys, os, time, argparse, hashlib
import numpy as np
import cv2

# ── Terminal colors ──────────────────────────────────────────────
class C:
    RESET  = '\033[0m';  BOLD   = '\033[1m';  DIM    = '\033[2m'
    CYAN   = '\033[96m'; GREEN  = '\033[92m'; YELLOW = '\033[93m'
    RED    = '\033[91m'; WHITE  = '\033[97m'; GREY   = '\033[90m'
    MAGENTA= '\033[95m'

def col(text, c): return f"{c}{text}{C.RESET}"
def cyan(t):    return col(t, C.CYAN)
def green(t):   return col(t, C.GREEN)
def yellow(t):  return col(t, C.YELLOW)
def red(t):     return col(t, C.RED)
def dim(t):     return col(t, C.DIM + C.GREY)
def white(t):   return col(t, C.WHITE)
def bold(t):    return col(t, C.BOLD)
def magenta(t): return col(t, C.MAGENTA)

W = 68

BANNER = f"""{C.CYAN}{C.BOLD}
  ██████╗ ██╗  ██╗ █████╗ ███████╗███████╗ ██████╗ ██████╗ ██╗██████╗ 
  ██╔══██╗██║  ██║██╔══██╗██╔════╝██╔════╝██╔════╝ ██╔══██╗██║██╔══██╗
  ██████╔╝███████║███████║███████╗█████╗  ██║  ███╗██████╔╝██║██║  ██║
  ██╔═══╝ ██╔══██║██╔══██║╚════██║██╔══╝  ██║   ██║██╔══██╗██║██║  ██║
  ██║     ██║  ██║██║  ██║███████║███████╗╚██████╔╝██║  ██║██║██████╔╝
  ╚═╝     ╚═╝  ╚═╝╚═╝  ╚═╝╚══════╝╚══════╝ ╚═════╝ ╚═╝  ╚═╝╚═╝╚═════╝
{C.RESET}"""

# ════════════════════════════════════════════════════════════════
#  PARAMETERS — must match encoder exactly
# ════════════════════════════════════════════════════════════════
ALPHABET  = list("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
K         = 26
FPS_DEF   = 30
T_CHAR    = 4.0
T_DELIM   = 0.5
GRID_N    = 10
SEED_DEF  = 42


# ════════════════════════════════════════════════════════════════
#  BASIS FUNCTIONS — identical to encoder
# ════════════════════════════════════════════════════════════════
def build_spatial_dct_bases(K=26, N=10):
    modes = []
    for u in range(N):
        for v in range(N):
            mode = np.zeros((N, N))
            for x in range(N):
                for y in range(N):
                    cu = np.sqrt(1/N) if u == 0 else np.sqrt(2/N)
                    cv = np.sqrt(1/N) if v == 0 else np.sqrt(2/N)
                    mode[x, y] = (cu * cv *
                                  np.cos(np.pi*(2*x+1)*u/(2*N)) *
                                  np.cos(np.pi*(2*y+1)*v/(2*N)))
            modes.append((u+v, u, v, mode.flatten()))
    modes.sort(key=lambda m: (m[0], m[1], m[2]))
    bases = np.array([m[3] for m in modes[:K]])
    bases /= (np.linalg.norm(bases, axis=1, keepdims=True) + 1e-10)
    return bases


def build_temporal_bases(K=26, T=120, fps=30, t_char=4.0):
    t = np.arange(T) / fps
    bases = [np.ones(T) / np.sqrt(T)]
    f = 1
    while len(bases) < K:
        freq_hz = f / t_char
        bases.append(np.sqrt(2/T) * np.cos(2 * np.pi * freq_hz * t))
        if len(bases) < K:
            bases.append(np.sqrt(2/T) * np.sin(2 * np.pi * freq_hz * t))
        f += 1
    return np.array(bases[:K])


def build_codebook(K=26, seed=42):
    np.random.seed(seed)
    R = np.random.randn(K, K)
    Q, _ = np.linalg.qr(R)
    vecs = Q * 3.0
    return {ALPHABET[i]: vecs[i] for i in range(K)}, vecs


# ════════════════════════════════════════════════════════════════
#  STEP 1 — LOAD VIDEO
# ════════════════════════════════════════════════════════════════
def load_frames(path):
    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        print(red(f"  ✗ Cannot open: {path}")); sys.exit(1)
    fps    = cap.get(cv2.CAP_PROP_FPS)
    total  = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    W_px   = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    H_px   = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    frames = []
    i = 0
    while True:
        ret, frame = cap.read()
        if not ret: break
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY).astype(np.float32) / 255.0
        frames.append(gray)
        i += 1
        if i % 60 == 0:
            _progress("  Loading frames", i, total)
    _progress("  Loading frames", total, total)
    print()
    cap.release()
    return frames, fps, W_px, H_px


# ════════════════════════════════════════════════════════════════
#  STEP 2 — EXTRACT CELL TIME-SERIES  (full-frame grid)
# ════════════════════════════════════════════════════════════════
def extract_cell_signals(frames, W_px, H_px):
    """
    The grid IS the full frame.
    Returns shape (n_frames, 100) — mean brightness of each 10×10 cell.
    """
    N = GRID_N
    cell_w = W_px / N
    cell_h = H_px / N
    n = len(frames)
    signals = np.zeros((n, N*N), dtype=np.float32)

    for t, frame in enumerate(frames):
        for r in range(N):
            for c in range(N):
                y0 = int(r * cell_h);     y1 = int((r+1) * cell_h)
                x0 = int(c * cell_w);     x1 = int((c+1) * cell_w)
                # Trim 2px border that encoder drew
                y0b = min(y0+2, y1-1);    y1b = max(y1-2, y0b+1)
                x0b = min(x0+2, x1-1);    x1b = max(x1-2, x0b+1)
                patch = frame[y0b:y1b, x0b:x1b]
                signals[t, r*N+c] = patch.mean() if patch.size > 0 else 0.0
        if t % 60 == 0:
            _progress("  Extracting cells", t+1, n)

    _progress("  Extracting cells", n, n); print()
    return signals   # (n_frames, 100)


# ════════════════════════════════════════════════════════════════
#  STEP 3 — SYNC DETECTION  (frame-diff method — robust)
# ════════════════════════════════════════════════════════════════
def detect_sync_end(global_means, fps, diff_threshold=50.0, min_sync_frames=20):
    """
    Sync burst = large absolute difference between consecutive frames
    (sync diff ≈ 235 on [0,255] scale, char diff ≈ 7).
    We look for the FIRST time the high-diff region ends.

    Returns: first frame of the first character.
    """
    means255 = global_means * 255.0
    diffs    = np.abs(np.diff(means255))        # length n-1

    # Smooth with a 3-frame window
    diffs_sm = np.convolve(diffs, np.ones(3)/3, mode='same')

    in_sync = False
    sync_count = 0

    for i, d in enumerate(diffs_sm):
        if d > diff_threshold:
            in_sync = True
            sync_count += 1
        else:
            if in_sync and sync_count >= min_sync_frames:
                # sync just ended at frame i
                return i + 1   # first char frame
            if in_sync:
                sync_count = 0
                in_sync = False

    # Fallback: assume 2s of sync
    return int(2.0 * fps)


# ════════════════════════════════════════════════════════════════
#  STEP 4 — FEATURE PROJECTION  (matched filter)
# ════════════════════════════════════════════════════════════════
def extract_features(window, sb, tb):
    """
    window: (T, 100) float32 — one character window (already normalised)
    Returns v_hat: (K,) float64
    """
    T_actual = window.shape[0]
    T_canon  = tb.shape[1]

    # Resample time axis if fps differs
    if T_actual != T_canon:
        idx = np.round(np.linspace(0, T_actual-1, T_canon)).astype(int)
        window = window[idx]

    sp   = window @ sb.T          # (T, K)  — spatial projection per frame
    vhat = np.einsum('kt,tk->k', tb, sp) / T_canon
    return vhat


# ════════════════════════════════════════════════════════════════
#  STEP 5 — NEAREST-NEIGHBOUR CLASSIFY
# ════════════════════════════════════════════════════════════════
def classify(vhat, cv):
    dists = np.linalg.norm(cv - vhat, axis=1)
    order = np.argsort(dists)
    d0, d1 = dists[order[0]], dists[order[1]]
    conf   = (d1 - d0) / (d1 + 1e-8)
    top5   = [(ALPHABET[order[i]], float(dists[order[i]])) for i in range(5)]
    return ALPHABET[order[0]], float(conf), float(d0), top5


# ════════════════════════════════════════════════════════════════
#  TERMINAL VISUALIZATIONS
# ════════════════════════════════════════════════════════════════
def _progress(label, current, total, width=30):
    pct    = current / max(total, 1)
    filled = int(pct * width)
    bar    = '█' * filled + '░' * (width - filled)
    print(f"\r  {dim(f'{label:<22}')} {C.CYAN}{bar}{C.RESET} {cyan(f'{pct*100:5.1f}%')}",
          end='', flush=True)


def section(title):
    print(f"\n  {cyan('◈')} {white(title)}")
    print(f"  {dim('─' * (W-2))}")


def step(label, detail=''):
    lbl = white(f" {label:<28}")
    det = dim(f" {detail}") if detail else ''
    print(f"  {cyan('›')}{lbl}{det}")


def ok(msg):   print(f"  {green('✓')} {dim(msg)}")
def info(msg): print(f"  {dim('·')} {dim(msg)}")
def warn(msg): print(f"  {yellow('⚠')} {yellow(msg)}")


def draw_signal_graph(global_means, sync_end, char_starts, fps, width=64, height=12):
    """Render an ASCII waveform of the brightness signal."""
    n = len(global_means)
    # Downsample to width columns
    col_frames = np.linspace(0, n-1, width, dtype=int)
    values     = global_means[col_frames] * 255.0
    v_min, v_max = 0, 255

    print(f"\n  {dim('Signal waveform — global brightness over time')}")
    print(f"  {dim('255')} {dim('┐')}")

    rows = []
    for row in range(height-1, -1, -1):
        threshold = v_min + (row / (height-1)) * (v_max - v_min)
        line_chars = []
        for ci, fi in enumerate(col_frames):
            v = values[ci]
            # Determine color zone
            t_sec = fi / fps
            if fi < sync_end:
                zone = 'sync'
            elif any(abs(fi - cs) < 15 for cs in char_starts):
                zone = 'delim'
            else:
                zone = 'char'

            if v >= threshold:
                if zone == 'sync':
                    line_chars.append(f"{C.CYAN}█{C.RESET}")
                elif zone == 'delim':
                    line_chars.append(f"{C.YELLOW}█{C.RESET}")
                else:
                    line_chars.append(f"{C.GREEN}█{C.RESET}")
            else:
                line_chars.append(f"{C.GREY}·{C.RESET}")
        rows.append(''.join(line_chars))

    for row in rows:
        print(f"  {dim('│')} {row}")

    print(f"  {dim('  0')} {dim('└' + '─' * width)}")

    # Time axis labels
    n_labels = 8
    label_positions = np.linspace(0, width-1, n_labels, dtype=int)
    label_times     = np.linspace(0, n/fps, n_labels)
    label_row = ' ' * 5
    for pos, t in zip(label_positions, label_times):
        s = f"{t:.0f}s"
        label_row += s.ljust(width // n_labels)
    print(f"  {dim(label_row)}")

    # Legend
    print(f"\n  {C.CYAN}█{C.RESET} {dim('sync burst')}   "
          f"{C.GREEN}█{C.RESET} {dim('character window')}   "
          f"{C.YELLOW}█{C.RESET} {dim('delimiter')}")


def draw_confidence_bars(results, width=40):
    """Bar chart of confidence per decoded character."""
    print(f"\n  {dim('Per-character classification confidence')}\n")

    char_colors = {
        'H': C.CYAN, 'E': C.GREEN, 'L': C.YELLOW,
        'O': C.RED,  'W': C.MAGENTA
    }

    for i, r in enumerate(results):
        char = r['char']
        conf = r['confidence']
        dist = r['distance']
        col_  = char_colors.get(char, C.CYAN)

        filled = int(conf * width)
        bar    = '█' * filled + '░' * (width - filled)

        # Confidence color
        if conf > 0.4:   bar_col = C.GREEN
        elif conf > 0.2: bar_col = C.YELLOW
        else:            bar_col = C.RED

        char_display = col(f" {char} ", col_ + C.BOLD)
        bar_display  = col(bar, bar_col)
        conf_display = green(f"{conf*100:5.1f}%") if conf > 0.4 else yellow(f"{conf*100:5.1f}%")
        dist_display = dim(f"d={dist:.3f}")

        print(f"  {char_display} {bar_display} {conf_display}  {dist_display}")

        # Show top-3 alternatives
        alts = r['top5'][1:4]
        alt_str = '  '.join([f"{dim(c)}:{dim(f'{d:.2f}')}" for c, d in alts])
        print(f"       {dim('alternatives:')} {alt_str}")
        print()


def draw_grid_preview(grid_10x10, label='', color=C.CYAN):
    """Print a 10×10 grid as block chars in terminal."""
    print(f"  {dim(label)}")
    for row in grid_10x10:
        print('  ', end='')
        for cell in row:
            if cell > 0.5:
                print(f"{color}██{C.RESET}", end='')
            else:
                print(f"{C.GREY}··{C.RESET}", end='')
        print()


def draw_result_box(text, results):
    """Final decoded message in a big box."""
    conf_avg = np.mean([r['confidence'] for r in results]) if results else 0
    overall  = green("HIGH") if conf_avg > 0.4 else yellow("MEDIUM") if conf_avg > 0.2 else red("LOW")

    print(f"\n  {dim('╔' + '═'*64 + '╗')}")
    print(f"  {dim('║')}  {cyan('DECODED MESSAGE'):<60}{dim('║')}")
    print(f"  {dim('║')}{' '*66}{dim('║')}")

    msg_display = ''
    char_colors = {'H': C.CYAN, 'E': C.GREEN, 'L': C.YELLOW, 'O': C.RED}
    for r in results:
        col_ = char_colors.get(r['char'], C.WHITE)
        msg_display += col(r['char'], col_ + C.BOLD)

    pad = max(0, 62 - len(results)*2)
    print(f"  {dim('║')}  {msg_display}{' '*pad}{dim('║')}")
    print(f"  {dim('║')}{' '*66}{dim('║')}")
    print(f"  {dim('║')}  {dim(f'Characters: {len(results)}')}   "
          f"{dim('Avg confidence:')} {conf_avg*100:.1f}%   "
          f"{dim('Signal quality:')} {overall}"
          f"{'':>10}{dim('║')}")
    print(f"  {dim('╚' + '═'*64 + '╝')}")


# ════════════════════════════════════════════════════════════════
#  MAIN DECODER
# ════════════════════════════════════════════════════════════════
def decode(path, seed=SEED_DEF, show_signal=True, show_preview=True):
    t_start = time.time()

    # ── Banner ──
    print(BANNER)
    print(f"  {dim('Spatio-Temporal Optical Credential Decoder')}  {cyan('v0.3')}")
    print(f"  {dim('─' * (W-2))}")

    section("INPUT")
    step("Video file", os.path.basename(path))
    step("Seed", str(seed))
    step("Alphabet", f"A–Z  ({len(ALPHABET)} chars)")

    # ── Build bases ──
    section("BUILDING SIGNAL MODEL")
    step("Spatial DCT bases", f"K={K}, N={GRID_N}")
    sb = build_spatial_dct_bases(K, GRID_N)
    ok("26 lowest-frequency 2D DCT modes")

    T_canon = int(T_CHAR * FPS_DEF)
    step("Temporal cosine bases", f"T={T_canon}")
    tb = build_temporal_bases(K, T_canon, FPS_DEF, T_CHAR)
    ok("DC + harmonics ≤ 4 Hz")

    step("Orthogonal codebook", f"seed={seed}")
    codebook, cv = build_codebook(K, seed)
    ok(f"d_min = 4.2426  (all {K*(K-1)//2} pairs equal)")

    # ── Load video ──
    section("LOADING VIDEO")
    frames, fps, W_px, H_px = load_frames(path)
    n_frames = len(frames)
    duration = n_frames / fps
    ok(f"{n_frames} frames  ·  {fps:.1f}fps  ·  {duration:.1f}s  ·  {W_px}×{H_px}px")

    # ── Extract cell signals ──
    section("EXTRACTING CELL TIME-SERIES")
    info(f"Grid: {GRID_N}×{GRID_N} cells  →  {GRID_N*GRID_N} time series")
    cell_sigs = extract_cell_signals(frames, W_px, H_px)   # (n_frames, 100)
    ok(f"Signal matrix: {cell_sigs.shape[0]} × {cell_sigs.shape[1]}")

    # Global mean (raw, pre-normalization — needed for sync detection)
    global_means = cell_sigs.mean(axis=1)   # (n_frames,)

    # ── Normalize ──
    step("Zero-mean normalise per cell", "removes brightness drift & exposure bias")
    mu  = cell_sigs.mean(axis=0, keepdims=True)
    std = cell_sigs.std(axis=0,  keepdims=True)
    cell_sigs_norm = (cell_sigs - mu) / (std + 1e-6)
    ok("Normalised to zero-mean unit variance per cell")

    # ── Sync detection ──
    section("SYNC DETECTION")
    step("Frame-diff method", "sync diff≈235 vs char diff≈7  →  trivially separable")
    sync_end = detect_sync_end(global_means, fps)
    sync_dur = sync_end / fps
    ok(f"Sync burst ends at frame {sync_end}  ({sync_dur:.2f}s)")

    # ── Segment characters ──
    section("DECODING CHARACTERS")
    T_actual  = int(T_CHAR   * fps)
    T_del     = int(T_DELIM  * fps)
    T_slot    = T_actual + T_del

    info(f"Character window : {T_actual} frames ({T_CHAR}s)")
    info(f"Delimiter        : {T_del} frames ({T_DELIM}s)")
    info(f"Slot size        : {T_slot} frames ({T_CHAR + T_DELIM}s)")

    results    = []
    char_starts = []
    pos        = sync_end

    while pos + T_actual <= n_frames:
        window = cell_sigs_norm[pos : pos + T_actual]    # (T_actual, 100)

        # Skip if this looks like another sync burst (closing sync)
        global_diffs = np.abs(np.diff(global_means[pos:pos+T_actual] * 255))
        if global_diffs.mean() > 80:
            ok(f"Closing sync detected at frame {pos} — stopping")
            break

        vhat         = extract_features(window, sb, tb)
        char, conf, dist, top5 = classify(vhat, cv)

        char_starts.append(pos)
        results.append({
            'char': char, 'confidence': conf,
            'distance': dist, 'top5': top5,
            'frame': pos, 'time': pos/fps
        })

        conf_color = C.GREEN if conf > 0.4 else C.YELLOW if conf > 0.2 else C.RED
        print(f"  {cyan(f'[{len(results):02d}]')} "
              f"t={pos/fps:5.1f}s  "
              f"→  {col(f' {char} ', conf_color + C.BOLD)}  "
              f"conf={col(f'{conf:.3f}', conf_color)}  "
              f"d={dist:.3f}  "
              f"{dim('top3: ' + ' '.join(f'{c}({d:.2f})' for c,d in top5[:3]))}")

        pos += T_slot

    # ── Results ──
    section("RESULTS")
    draw_result_box(''.join(r['char'] for r in results), results)

    # ── Confidence bars ──
    if show_preview and results:
        section("CONFIDENCE CHART")
        draw_confidence_bars(results)

    # ── Signal graph ──
    if show_signal:
        section("SIGNAL WAVEFORM")
        draw_signal_graph(global_means, sync_end, char_starts, fps)

    # ── Frame grid previews ──
    if show_preview and results:
        section("FRAME SAMPLES")
        char_colors_map = {
            'H': C.CYAN, 'E': C.GREEN, 'L': C.YELLOW,
            'O': C.RED
        }
        seen = set()
        for r in results:
            ch = r['char']
            if ch in seen: continue
            seen.add(ch)
            fi = r['frame'] + T_actual // 2    # mid-window frame
            if fi < len(frames):
                frame_f = frames[fi]
                grid = np.zeros((GRID_N, GRID_N), dtype=np.float32)
                cell_w = W_px / GRID_N
                cell_h = H_px / GRID_N
                for row in range(GRID_N):
                    for c in range(GRID_N):
                        y0 = int(row*cell_h)+2; y1 = int((row+1)*cell_h)-2
                        x0 = int(c*cell_w)+2;   x1 = int((c+1)*cell_w)-2
                        patch = frame_f[y0:y1, x0:x1]
                        grid[row, c] = patch.mean() if patch.size > 0 else 0
                col_ = char_colors_map.get(ch, C.CYAN)
                draw_grid_preview(grid, f"'{ch}' — t={r['time']+T_CHAR/2:.1f}s (mid-window)", col_)
                print()

    # ── Fingerprint ──
    section("SIGNAL FINGERPRINT")
    raw_bytes = b''.join(r['char'].encode() for r in results)
    fp = hashlib.sha256(raw_bytes).hexdigest()
    print(f"  {dim('Message hash (decoded content):')}")
    print(f"  {cyan(fp[:32])}")
    print(f"  {cyan(fp[32:])}")

    # ── Summary ──
    elapsed = time.time() - t_start
    section("SUMMARY")
    decoded_text = ''.join(r['char'] for r in results)
    avg_conf     = np.mean([r['confidence'] for r in results]) if results else 0

    print(f"""
  {dim('┌─────────────────────────────────────────────────────────')}
  {dim('│')}  {white('Video    ')}  {cyan(os.path.basename(path))}
  {dim('│')}  {white('Seed     ')}  {yellow(str(seed))}
  {dim('│')}  {white('Decoded  ')}  {green(decoded_text)}
  {dim('│')}  {white('Chars    ')}  {str(len(results))}
  {dim('│')}  {white('Avg conf ')}  {green(f'{avg_conf*100:.1f}%')}
  {dim('│')}  {white('Duration ')}  {dim(f'{duration:.1f}s')}
  {dim('│')}  {white('Elapsed  ')}  {dim(f'{elapsed:.2f}s')}
  {dim('└─────────────────────────────────────────────────────────')}
""")

    return decoded_text, results


# ════════════════════════════════════════════════════════════════
#  CLI
# ════════════════════════════════════════════════════════════════
def main():
    parser = argparse.ArgumentParser(
        prog='phasegrid_decode',
        description='PhaseGrid Decoder — Spatio-Temporal Optical Credential Protocol',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
examples:
  python phasegrid_decode.py HELLO_optical.mp4
  python phasegrid_decode.py HELLO_optical.mp4 -s 42
  python phasegrid_decode.py HELLO_optical.mp4 --no-signal
  python phasegrid_decode.py HELLO_optical.mp4 --no-preview
        """
    )
    parser.add_argument('video',         type=str, help='Path to encoded PhaseGrid video')
    parser.add_argument('-s','--seed',   type=int, default=SEED_DEF,
                        help=f'Codebook seed (must match encoder, default: {SEED_DEF})')
    parser.add_argument('--no-signal',   action='store_true', help='Skip waveform graph')
    parser.add_argument('--no-preview',  action='store_true', help='Skip grid previews & confidence bars')

    args = parser.parse_args()

    if not os.path.exists(args.video):
        print(red(f"  ✗ File not found: {args.video}")); sys.exit(1)

    decode(
        path         = args.video,
        seed         = args.seed,
        show_signal  = not args.no_signal,
        show_preview = not args.no_preview,
    )


if __name__ == '__main__':
    main()