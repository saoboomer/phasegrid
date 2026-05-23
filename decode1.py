#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════╗
║               P H A S E G R I D   D E C O D E R  v2.0          ║
╚══════════════════════════════════════════════════════════════════╝
"""

import sys, os, time, argparse, hashlib
import numpy as np
import cv2

# ── Colors ──────────────────────────────────────────────────────
class C:
    RESET='\033[0m'; BOLD='\033[1m'; DIM='\033[2m'
    CYAN='\033[96m'; GREEN='\033[92m'; YELLOW='\033[93m'
    RED='\033[91m';  WHITE='\033[97m'; GREY='\033[90m'

def col(t,c): return f"{c}{t}{C.RESET}"
def cyan(t):  return col(t,C.CYAN)
def green(t): return col(t,C.GREEN)
def yellow(t):return col(t,C.YELLOW)
def red(t):   return col(t,C.RED)
def dim(t):   return col(t,C.DIM+C.GREY)
def white(t): return col(t,C.WHITE)

W=68

BANNER=f"""{C.CYAN}{C.BOLD}
  ██████╗ ██╗  ██╗ █████╗ ███████╗███████╗ ██████╗ ██████╗ ██╗██████╗ 
  ██╔══██╗██║  ██║██╔══██╗██╔════╝██╔════╝██╔════╝ ██╔══██╗██║██╔══██╗
  ██████╔╝███████║███████║███████╗█████╗  ██║  ███╗██████╔╝██║██║  ██║
  ██╔═══╝ ██╔══██║██╔══██║╚════██║██╔══╝  ██║   ██║██╔══██╗██║██║  ██║
  ██║     ██║  ██║██║  ██║███████║███████╗╚██████╔╝██║  ██║██║██████╔╝
  ╚═╝     ╚═╝  ╚═╝╚═╝  ╚═╝╚══════╝╚══════╝ ╚═════╝ ╚═╝  ╚═╝╚═╝╚═════╝
{C.RESET}"""

# ── PARAMETERS ──────────────────────────────────────────────────
ALPHABET=list("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
K=26; FPS_DEF=30; T_CHAR=4.0
GRID_N=10; FADE_F=10; THRESHOLD=0.5; SEED_DEF=42
T=int(T_CHAR*FPS_DEF)

# ── SIGNAL MATH ────────────────────────────────────────────────
def build_spatial_dct_bases(K=26,N=10):
    modes=[]
    for u in range(N):
        for v in range(N):
            mode=np.zeros((N,N))
            for x in range(N):
                for y in range(N):
                    cu=np.sqrt(1/N) if u==0 else np.sqrt(2/N)
                    cv_=np.sqrt(1/N) if v==0 else np.sqrt(2/N)
                    mode[x,y]=cu*cv_*np.cos(np.pi*(2*x+1)*u/(2*N))*np.cos(np.pi*(2*y+1)*v/(2*N))
            modes.append((u+v,u,v,mode.flatten()))
    modes.sort(key=lambda m:(m[0],m[1],m[2]))
    bases=np.array([m[3] for m in modes[:K]])
    bases/=(np.linalg.norm(bases,axis=1,keepdims=True)+1e-10)
    return bases

def build_temporal_bases(K=26,T=120,fps=30,t_char=4.0):
    t=np.arange(T)/fps
    bases=[np.ones(T)/np.sqrt(T)]
    f=1
    while len(bases)<K:
        freq_hz=f/t_char
        bases.append(np.sqrt(2/T)*np.cos(2*np.pi*freq_hz*t))
        if len(bases)<K:
            bases.append(np.sqrt(2/T)*np.sin(2*np.pi*freq_hz*t))
        f+=1
    return np.array(bases[:K])

def build_raw_codebook(K=26,seed=42):
    np.random.seed(seed)
    R=np.random.randn(K,K)
    Q,_=np.linalg.qr(R)
    return {ALPHABET[i]:Q[i]*3.0 for i in range(K)}

def render_trajectory(v,sb,tb,T=120):
    signal=(v[:,None]*tb).T@sb
    window=np.ones(T)
    for i in range(FADE_F):
        w=0.5*(1-np.cos(np.pi*i/FADE_F))
        window[i]=w; window[T-1-i]=w
    signal*=window[:,None]
    lo,hi=signal.min(),signal.max()
    signal=(signal-lo)/(hi-lo+1e-8)
    return (signal>THRESHOLD).astype(np.float64).reshape(T,100)

def build_enc_trajs(sb,tb,seed=42):
    raw=build_raw_codebook(K,seed)
    return {ch: render_trajectory(raw[ch],sb,tb) for ch in ALPHABET}

# ── VIDEO LOADING ───────────────────────────────────────────────
def load_cell_signals(path):
    cap=cv2.VideoCapture(path)
    if not cap.isOpened():
        print(red(f"Cannot open {path}"))
        sys.exit(1)

    fps=int(cap.get(cv2.CAP_PROP_FPS))
    W_px=int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    H_px=int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    N=GRID_N
    cp=W_px//N
    pad=max(1,cp//25)

    signals=[]
    while True:
        ret,f=cap.read()
        if not ret: break

        gray=cv2.cvtColor(f,cv2.COLOR_BGR2GRAY).astype(np.float32)/255.0
        lo,hi=gray.min(),gray.max()
        if hi-lo>0.05:
            gray=(gray-lo)/(hi-lo)

        cells=np.zeros(N*N,dtype=np.float32)

        for r in range(N):
            for c in range(N):
                y0=r*cp+pad; y1=(r+1)*cp-pad
                x0=c*cp+pad; x1=(c+1)*cp-pad

                if y1>y0 and x1>x0:
                    cells[r*N+c]=gray[y0:y1,x0:x1].mean()

        signals.append(cells)

    cap.release()
    return np.array(signals,dtype=np.float32), fps, W_px, H_px, cp

# ── SYNC DETECTION ──────────────────────────────────────────────
def detect_sync_end(global_means,fps,diff_thr=80.0,min_sync=20):
    means255=global_means*255.0
    diffs=np.abs(np.diff(means255))
    sm=np.convolve(diffs,np.ones(3)/3,mode='same')

    in_sync=False; count=0
    for i,d in enumerate(sm):
        if d>diff_thr:
            in_sync=True
            count+=1
        else:
            if in_sync and count>=min_sync:
                return i+1
            in_sync=False
            count=0

    return int(2.0*fps)

# ── DELIMITER DETECTION (FIXED) ────────────────────────────────
def find_delim_groups(global_means,start,thr=0.05,min_gap=5):
    nz=[i for i in range(start,len(global_means)) if global_means[i]<thr]

    groups=[]
    sg=None
    prev=None

    for i in nz:
        if sg is None:
            sg=i
            prev=i
        elif i>prev+min_gap:
            groups.append((sg,prev))
            sg=i
        prev=i

    if sg is not None:
        groups.append((sg,prev))

    return groups

# ── SCORING ─────────────────────────────────────────────────────
def soft_score(window,enc):
    return float((window*enc + (1-window)*(1-enc)).mean())

def decode_character(cell_sigs,rough,enc_trajs,radius=25):
    n=len(cell_sigs)
    char_bests=[]

    for ch in ALPHABET:
        enc=enc_trajs[ch]
        best_sc=-1e9
        best_s=rough

        for off in range(-radius,radius+1):
            s=rough+off
            if s<0 or s+len(enc)>n:
                continue

            sc=soft_score(cell_sigs[s:s+len(enc)],enc)

            if sc>best_sc:
                best_sc=sc
                best_s=s

        char_bests.append((best_sc,ch,best_s))

    char_bests.sort(reverse=True)

    best_score,best_char,best_start=char_bests[0]
    margin=best_score-char_bests[1][0]

    top5=[(c,float(s)) for s,c,_ in char_bests[:5]]

    return best_char,best_start,best_score,margin,top5

# ── DISPLAY ─────────────────────────────────────────────────────
def draw_grid_sample(cell_sigs,start,char,cp,fps,color=C.CYAN):
    mid=start+T//2
    if mid>=len(cell_sigs): return

    frame=(cell_sigs[mid]>0.5).reshape(GRID_N,GRID_N)
    lbl=f"'{char}' at t={mid/fps:.1f}s"

    print(dim(lbl))
    for row in frame:
        print("  ",end="")
        for cell in row:
            print(f"{color}██{C.RESET}" if cell else f"{C.GREY}··{C.RESET}",end="")
        print()

# ── MAIN DECODE ────────────────────────────────────────────────
def decode(path,seed=SEED_DEF):
    print(BANNER)

    sb=build_spatial_dct_bases(K,GRID_N)
    tb=build_temporal_bases(K,T,FPS_DEF,T_CHAR)
    enc_trajs=build_enc_trajs(sb,tb,seed)

    cell_sigs,fps,W_px,H_px,cp=load_cell_signals(path)

    global_mean=cell_sigs.mean(axis=1)
    sync_end=detect_sync_end(global_mean,fps)

    groups=find_delim_groups(global_mean,sync_end-5)

    rough=[]
    if groups:
        rough.append(groups[0][1]+1)
        for g in groups[1:-1]:
            rough.append(g[1]+1)
    else:
        rough=[sync_end]

    results=[]

    for i,r in enumerate(rough):
        ch,s,sc,mg,top5=decode_character(cell_sigs,r,enc_trajs)

        results.append({
            "char":ch,
            "start":s,
            "score":sc,
            "margin":mg,
            "top5":top5
        })

        print(f"[{i}] {ch} score={sc:.3f} margin={mg:.3f}")

    print("\nRESULT:", "".join(r["char"] for r in results))

    for r in results:
        draw_grid_sample(cell_sigs,r["start"],r["char"],cp,fps,C.CYAN)

# ── CLI ────────────────────────────────────────────────────────
def main():
    p=argparse.ArgumentParser()
    p.add_argument("video")
    a=p.parse_args()

    decode(a.video)

if __name__=="__main__":
    main()