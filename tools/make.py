#!/usr/bin/env python3
"""動画の型1〜4 仕上げの道具（すぐ来るたいき・無料版）

使い方:
  python3 tools/make.py                 # genko.json と inbox/ の動画で仕上げる
  python3 tools/make.py --genko genko.json --inbox inbox --name 自己紹介
  python3 tools/make.py --check         # 道具がそろっているかだけ見る

genko.json（原稿）:
  {"kata": 1-4, "dai": "見出し", "rows": [["左", "右"], ...], "close": "最後の札（任意）"}
  型1・型2 … 左＝問い（画面の帯に出る）／右＝自分の答え（字幕になる）
  型3      … 左＝時刻（例 9:00）／右＝すること
  型4      … 左＝年（例 2015年）／右＝あったこと

inbox/ の動画:
  プロンプターで撮った k4_r1.mp4, k4_r2.mp4 … （r の番号＝原稿の行）。
  番号が無い時は名前順に1行ずつ当てる。1本だけの時は、無音で行の数に分ける。

出来上がり: out/<日付>_<名前>/kansei.mp4 と thumb.jpg
外の API は使いません（ffmpeg と Pillow だけ。字幕は原稿の文から作る）。
"""
import argparse, glob, json, os, re, shutil, subprocess, sys, time
from datetime import datetime, timezone, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VID_EXT = ('.mp4', '.mov', '.m4v', '.webm', '.mkv')
JST = timezone(timedelta(hours=9))


def log(*a):
    print('・', *a, flush=True)


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f'失敗しました: {" ".join(map(str, cmd[:5]))} …\n{r.stderr[-1500:]}')
    return r


# ---------- 道具さがし ----------
def find_font():
    cands = []
    if shutil.which('fc-match'):
        for q in ('Noto Sans CJK JP:style=Black', 'Noto Sans CJK JP:style=Bold'):
            r = subprocess.run(['fc-match', '-f', '%{file}', q], capture_output=True, text=True)
            if r.returncode == 0 and r.stdout.strip():
                cands.append(r.stdout.strip())
    cands += glob.glob('/usr/share/fonts/**/NotoSansCJK-Black.ttc', recursive=True)
    cands += glob.glob('/usr/share/fonts/**/NotoSansCJK-Bold.ttc', recursive=True)
    cands += ['/System/Library/Fonts/ヒラギノ角ゴシック W8.ttc', '/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc',
              '/System/Library/Fonts/Hiragino Sans GB.ttc']
    for c in cands:
        if c and os.path.exists(c) and ('CJK' in c or 'ヒラギノ' in c or 'Hiragino' in c):
            return c
    return None


def check():
    ok = True
    for t in ('ffmpeg', 'ffprobe'):
        p = shutil.which(t)
        print(f'{t}: {p or "ありません"}'); ok &= bool(p)
    try:
        import PIL; print(f'Pillow: {PIL.__version__}')
    except ImportError:
        print('Pillow: ありません'); ok = False
    f = find_font(); print(f'日本語フォント: {f or "ありません"}'); ok &= bool(f)
    print('準備OK' if ok else '足りない物があります → bash tools/setup.sh')
    return ok


# ---------- 型の見た目 ----------
def load_kata(n):
    return json.load(open(os.path.join(ROOT, 'kata', f'kata{n}.json'), encoding='utf-8'))


def probe(path):
    j = json.loads(run(['ffprobe', '-v', 'error', '-show_streams', '-show_format', '-of', 'json', path]).stdout)
    v = next((s for s in j['streams'] if s['codec_type'] == 'video'), None)
    if v is None:
        sys.exit(f'映像がありません: {path}')
    a = any(s['codec_type'] == 'audio' for s in j['streams'])
    rot = 0
    for sd in v.get('side_data_list', []) or []:
        if 'rotation' in sd: rot = int(sd['rotation'])
    rot = int(v.get('tags', {}).get('rotate', rot) or rot)
    w, h = int(v['width']), int(v['height'])
    if rot % 180: w, h = h, w
    d = float(j['format'].get('duration') or v.get('duration') or 0)
    return w, h, d, a


def speech_spans(path, total, db=-35, min_sil=0.45, pad=0.15):
    """声のある所 [(a,b),...]。無音で切る（ジャンプカット）。"""
    r = subprocess.run(['ffmpeg', '-v', 'info', '-i', path, '-af', f'silencedetect=noise={db}dB:d={min_sil}',
                        '-f', 'null', '-'], capture_output=True, text=True)
    sil, s0 = [], None
    for line in r.stderr.splitlines():
        m = re.search(r'silence_start: ([\d.]+)', line)
        if m: s0 = float(m.group(1))
        m = re.search(r'silence_end: ([\d.]+)', line)
        if m and s0 is not None: sil.append((s0, float(m.group(1)))); s0 = None
    if s0 is not None: sil.append((s0, total))
    spans, t = [], 0.0
    for a, b in sil:
        if a - t > 0.2: spans.append((max(0, t - pad), min(total, a + pad)))
        t = b
    if total - t > 0.2: spans.append((max(0, t - pad), total))
    # くっつきすぎを1つに
    out = []
    for a, b in spans:
        if out and a - out[-1][1] < 0.25: out[-1] = (out[-1][0], b)
        else: out.append((a, b))
    return out or [(0, total)]


# ---------- 文字の画像 ----------
def font(path, size):
    from PIL import ImageFont
    try:
        return ImageFont.truetype(path, size, index=0)
    except Exception:
        return ImageFont.truetype(path, size)


def text_w(draw, s, f):
    b = draw.textbbox((0, 0), s, font=f)
    return b[2] - b[0]


def wrap(s, max_chars):
    """文節っぽく max_chars で区切る（句読点の後ろで切る・句読点から始めない）。"""
    s = s.strip()
    out, cur = [], ''
    for ch in s:
        if len(cur) >= max_chars and ch not in '、。！？」）ー':
            out.append(cur); cur = ''
        cur += ch
        if ch in '。！？' and len(cur) >= max_chars * 0.5:
            out.append(cur); cur = ''
    if cur: out.append(cur)
    return [x.strip() for x in out if x.strip()]


def balance(s, max_chars, nlines):
    """字幕の行を同じくらいの長さに分ける（最後の行が1〜2字だけにならない）。"""
    s = s.strip()
    if len(s) <= max_chars: return [s]
    n = min(nlines, -(-len(s) // max_chars))
    target = -(-len(s) // n)
    out, cur = [], ''
    for i, ch in enumerate(s):
        cur += ch
        rest = len(s) - i - 1
        if len(out) < n - 1 and len(cur) >= target - 2:
            nxt = s[i + 1] if rest else ''
            good = ch in '、。！？はがをにでとも' or len(cur) >= target + 1
            if good and nxt not in '、。！？」）ー' and rest > 2:
                out.append(cur); cur = ''
    if cur: out.append(cur)
    return out[:nlines]


def png_sub(lines, W, K, fp, path):
    """字幕：白い字・黒いふち（型2は帯なし、型1は黒い帯の上）"""
    from PIL import Image, ImageDraw
    sz, st = K['sub']['size'], K['sub']['outline']
    f = font(fp, sz)
    lh = int(sz * 1.3)
    h = lh * len(lines) + st * 2 + 10
    im = Image.new('RGBA', (W, h), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    for i, ln in enumerate(lines):
        x = (W - text_w(d, ln, f)) // 2
        d.text((x, st + i * lh), ln, font=f, fill='white', stroke_width=st, stroke_fill='black')
    im.save(path); return h


def rounded(d, box, r, fill):
    d.rounded_rectangle(box, radius=r, fill=fill)


def png_head(K, dai, q, W, fp, path):
    """上の帯：見出し（白）＋いまの問い（黄色い字の札）"""
    from PIL import Image, ImageDraw
    hd = K['head']
    im = Image.new('RGBA', (W, hd['height']), (0, 0, 0, 255 if hd.get('solid') else 0)); d = ImageDraw.Draw(im)
    if K['vertical']:
        f1, f2 = font(fp, hd['title_size']), font(fp, hd['q_size'])
        t = dai[:16]
        d.text(((W - text_w(d, t, f1)) // 2, 60), t, font=f1, fill='white', stroke_width=6, stroke_fill='#1b2a4a')
        if q:
            qq = q[:18]
            tw = text_w(d, qq, f2)
            x0 = (W - tw) // 2 - 40
            rounded(d, (x0, 150, x0 + tw + 80, 150 + hd['q_size'] + 44), 22, (38, 38, 42, 255))
            d.text((x0 + 40, 170), qq, font=f2, fill='#f2c94c')
    else:
        f1, f2 = font(fp, hd['title_size']), font(fp, hd['q_size'])
        t = dai[:30]
        tw = text_w(d, t, f1)
        rounded(d, (40, 30, 40 + tw + 48, 30 + hd['title_size'] + 30), 10, (30, 30, 34, 230))
        d.text((64, 44), t, font=f1, fill='white')
        if q:
            qq = q[:30]
            tw2 = text_w(d, qq, f2)
            rounded(d, (40, 100, 40 + tw2 + 48, 100 + hd['q_size'] + 28), 8, (242, 201, 76, 255))
            d.text((64, 112), qq, font=f2, fill='#1a1712')
    im.save(path)


def png_card(K, big, small, W, H, fp, path):
    """型3・型4：黒い画面に時刻／年（大きく）＋すること（小さく）"""
    from PIL import Image, ImageDraw
    im = Image.new('RGB', (W, H), 'black'); d = ImageDraw.Draw(im)
    f1, f2 = font(fp, K['card']['big']), font(fp, K['card']['small'])
    y = H // 2 - K['card']['big']
    d.text(((W - text_w(d, big, f1)) // 2, y), big, font=f1, fill='#f2c94c')
    if small:
        s = small[:14]
        d.text(((W - text_w(d, s, f2)) // 2, y + int(K['card']['big'] * 1.35)), s, font=f2, fill='white')
    im.save(path)


def png_nenpyo(K, rows, cur, fp, path):
    """型4：左上の年表（いまの行は黄色・ほかは灰色）／型3：左上にいまの時刻"""
    from PIL import Image, ImageDraw
    n = K['nenpyo']
    f1, f2 = font(fp, n['big']), font(fp, n['small'])
    show = rows if n.get('all') else [rows[cur]]
    lh = int(n['big'] * 1.0 + n['small'] * 1.25 + 18)
    W, H = n['width'], lh * len(show) + 40
    im = Image.new('RGBA', (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    rounded(d, (0, 0, W, H), 24, (0, 0, 0, 170))
    for i, (a, b) in enumerate(show):
        on = (i == cur) if n.get('all') else True
        c1 = '#f2c94c' if on else '#9a9a9a'
        c2 = '#f2c94c' if on else '#bdbdbd'
        y = 20 + i * lh
        d.text((28, y), a, font=f1, fill=c1)
        d.text((28, y + int(n['big'] * 1.05)), b[:12], font=f2, fill=c2)
    im.save(path)


# ---------- 1行ぶんを作る ----------
def clean(s):
    return re.sub(r'（ここは実際のことを）', '', s or '').strip()


def build_row(i, src, row, G, K, fp, work):
    W, H = K['size']
    vw, vh, total, has_a = probe(src)
    spans = speech_spans(src, total) if has_a else [(0, total)]
    keep = sum(b - a for a, b in spans)
    # 1) 切ってつなぐ・大きさをそろえる
    sel = '+'.join(f'between(t,{a:.3f},{b:.3f})' for a, b in spans)
    area = K.get('video_area', [0, 0, W, H])  # x,y,w,h
    aw, ah = area[2], area[3]
    other = (vh > vw) != (ah > aw)
    if other:  # 向きが違う → ぼかしの上に中央
        vf = (f"select='{sel}',setpts=N/FRAME_RATE/TB,split[a][b];"
              f"[a]scale={aw}:{ah}:force_original_aspect_ratio=increase,crop={aw}:{ah},boxblur=30:5[bg];"
              f"[b]scale={aw}:{ah}:force_original_aspect_ratio=decrease[fg];[bg][fg]overlay=(W-w)/2:(H-h)/2")
    else:
        vf = (f"select='{sel}',setpts=N/FRAME_RATE/TB,"
              f"scale={aw}:{ah}:force_original_aspect_ratio=increase,crop={aw}:{ah}")
    cut = f'{work}/r{i}_cut.mp4'
    cmd = ['ffmpeg', '-v', 'error', '-y', '-i', src, '-filter_complex', f'[0:v]fps=30,{vf}[v]']
    if has_a:
        cmd[-1] += f";[0:a]aselect='{sel}',asetpts=N/SR/TB[a]"
        cmd += ['-map', '[v]', '-map', '[a]']
    else:
        cmd += ['-map', '[v]']
    cmd += ['-c:v', 'libx264', '-preset', 'veryfast', '-crf', '18', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-ar', '48000', '-ac', '2', cut]
    run(cmd)
    if not has_a:
        run(['ffmpeg', '-v', 'error', '-y', '-i', cut, '-f', 'lavfi', '-i', 'anullsrc=r=48000:cl=stereo',
             '-shortest', '-c:v', 'copy', '-c:a', 'aac', f'{work}/r{i}_cut2.mp4'])
        os.replace(f'{work}/r{i}_cut2.mp4', cut)

    # 2) 重ねる絵
    ov = []  # (png, x, y, t0, t1)
    kata = G['kata']
    left, right = row[0], clean(row[1])
    if kata in (1, 2):
        hp = f'{work}/r{i}_head.png'; png_head(K, G.get('dai', ''), left, W, fp, hp)
        ov.append((hp, 0, 0, 0, keep))
        chunks = []
        for para in re.split(r'(?<=[。！？])', right):
            chunks += wrap(para, K['sub']['max_chars'] * K['sub']['lines'])
        chunks = [c for c in chunks if c]
        tot_chars = sum(len(c) for c in chunks) or 1
        t = 0.0
        for j, c in enumerate(chunks):
            dt = keep * len(c) / tot_chars
            lines = balance(c, K['sub']['max_chars'], K['sub']['lines'])
            sp = f'{work}/r{i}_s{j}.png'; sh = png_sub(lines, W, K, fp, sp)
            ov.append((sp, 0, H - K['sub']['bottom'] - sh, t, t + dt)); t += dt
    else:
        np_ = f'{work}/r{i}_nen.png'; png_nenpyo(K, G['rows'], i, fp, np_)
        ov.append((np_, K['nenpyo']['x'], K['nenpyo']['y'], 0, keep))

    body = f'{work}/r{i}_body.mp4'
    base = 'color=c=black:s={}x{}:r=30:d={:.3f}'.format(W, H, keep)
    inputs = ['-f', 'lavfi', '-i', base, '-i', cut]
    fc = f'[0:v][1:v]overlay={area[0]}:{area[1]}:shortest=1[v0]'
    last = 'v0'
    for k, (png, x, y, t0, t1) in enumerate(ov):
        inputs += ['-i', png]
        fc += f';[{last}][{k + 2}:v]overlay={x}:{y}:enable=\'between(t,{t0:.3f},{t1:.3f})\'[v{k + 1}]'
        last = f'v{k + 1}'
    run(['ffmpeg', '-v', 'error', '-y', *inputs, '-filter_complex', fc, '-map', f'[{last}]', '-map', '1:a',
         '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '20', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-ar', '48000', '-ac', '2',
         '-t', f'{keep:.3f}', body])

    parts = []
    if kata in (3, 4):  # 黒い札＋ピッ
        cp = f'{work}/r{i}_card.png'; png_card(K, left, right, W, H, fp, cp)
        card = f'{work}/r{i}_card.mp4'; cd = K['card']['sec']
        run(['ffmpeg', '-v', 'error', '-y', '-loop', '1', '-t', str(cd), '-i', cp,
             '-f', 'lavfi', '-t', str(cd), '-i', 'sine=f=1200:d=0.18,apad', '-filter_complex',
             '[0:v]fps=30,format=yuv420p,fade=in:st=0:d=0.15[v];[1:a]volume=0.35,aformat=sample_rates=48000:channel_layouts=stereo[a]',
             '-map', '[v]', '-map', '[a]', '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '20', '-c:a', 'aac', '-ar', '48000', '-ac', '2', card])
        parts.append(card)
    parts.append(body)
    return parts, keep


def close_card(G, K, fp, work):
    txt = (G.get('close') or '').strip()
    if not txt: return []
    W, H = K['size']
    from PIL import Image, ImageDraw
    im = Image.new('RGB', (W, H), 'black'); d = ImageDraw.Draw(im)
    f = font(fp, 72 if K['vertical'] else 80)
    lines = wrap(txt, 12 if K['vertical'] else 20)[:3]
    for j, ln in enumerate(lines):
        d.text(((W - text_w(d, ln, f)) // 2, H // 2 - 60 * len(lines) + j * 120), ln, font=f, fill='white')
    p = f'{work}/close.png'; im.save(p)
    out = f'{work}/close.mp4'
    run(['ffmpeg', '-v', 'error', '-y', '-loop', '1', '-t', '2', '-i', p, '-f', 'lavfi', '-t', '2', '-i', 'anullsrc=r=48000:cl=stereo',
         '-vf', 'fps=30,format=yuv420p,fade=in:st=0:d=0.3', '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '20', '-c:a', 'aac', '-shortest', out])
    return [out]


def assign(files, rows):
    """動画を原稿の行に当てる。k?_r{n} の n を優先、無ければ名前順。"""
    m = {}
    for f in files:
        g = re.search(r'_r(\d+)', os.path.basename(f))
        if g and 1 <= int(g.group(1)) <= len(rows): m.setdefault(int(g.group(1)) - 1, f)
    rest = [f for f in sorted(files) if f not in m.values()]
    for i in range(len(rows)):
        if i not in m and rest: m[i] = rest.pop(0)
    return m


def split_one(src, n, work):
    """1本だけの時：長い無音で n 個に分ける。"""
    _, _, total, has_a = probe(src)
    if not has_a or n <= 1: return [src]
    r = subprocess.run(['ffmpeg', '-v', 'info', '-i', src, '-af', 'silencedetect=noise=-35dB:d=1.0', '-f', 'null', '-'],
                       capture_output=True, text=True)
    mids = []
    s0 = None
    for line in r.stderr.splitlines():
        a = re.search(r'silence_start: ([\d.]+)', line); b = re.search(r'silence_end: ([\d.]+) \| silence_duration: ([\d.]+)', line)
        if a: s0 = float(a.group(1))
        if b and s0 is not None: mids.append(((s0 + float(b.group(1))) / 2, float(b.group(2)))); s0 = None
    mids = [m for m in mids if 1.0 < m[0] < total - 1.0]
    cuts = sorted(sorted(mids, key=lambda x: -x[1])[:n - 1])
    if len(cuts) < n - 1:
        log(f'無音の切れ目が {len(cuts)} か所しかありません（必要 {n - 1}）。ある分だけで分けます。')
    pts = [0] + [c[0] for c in cuts] + [total]
    outs = []
    for k in range(len(pts) - 1):
        o = f'{work}/split_r{k + 1}.mp4'
        run(['ffmpeg', '-v', 'error', '-y', '-ss', f'{pts[k]:.3f}', '-to', f'{pts[k + 1]:.3f}', '-i', src,
             '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '18', '-c:a', 'aac', o])
        outs.append(o)
    return outs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--genko', default=os.path.join(ROOT, 'genko.json'))
    ap.add_argument('--inbox', default=os.path.join(ROOT, 'inbox'))
    ap.add_argument('--name', default='')
    ap.add_argument('--check', action='store_true')
    a = ap.parse_args()
    if a.check: sys.exit(0 if check() else 1)
    if not check(): sys.exit(1)
    fp = find_font()
    G = json.load(open(a.genko, encoding='utf-8'))
    kata = int(G['kata']); G['kata'] = kata
    rows = [list(r) for r in G['rows']]; G['rows'] = rows
    K = load_kata(kata)
    files = [f for f in glob.glob(os.path.join(a.inbox, '*')) if f.lower().endswith(VID_EXT)]
    if not files: sys.exit(f'動画がありません: {a.inbox}/ に入れてください')
    stamp = datetime.now(JST).strftime('%Y%m%d_%H%M')
    name = re.sub(r'[^\w\-ぁ-んァ-ン一-龥ー]', '', a.name or G.get('dai', '') or f'kata{kata}')[:20] or f'kata{kata}'
    outdir = os.path.join(ROOT, 'out', f'{stamp}_{name}')
    work = os.path.join(outdir, 'work'); os.makedirs(work, exist_ok=True)
    if len(files) == 1 and len(rows) > 1:
        log('動画が1本なので、長い無音で行ごとに分けます')
        files = split_one(files[0], len(rows), work)
    m = assign(files, rows)
    parts, used = [], 0
    for i, row in enumerate(rows):
        if i not in m:
            log(f'{i + 1}行目の動画がないので飛ばします'); continue
        log(f'{i + 1}/{len(rows)} 行目: {os.path.basename(m[i])}')
        p, k = build_row(i, m[i], row, G, K, fp, work); parts += p; used += 1
    parts += close_card(G, K, fp, work)
    if not parts: sys.exit('作れる行がありませんでした')
    lst = f'{work}/list.txt'
    open(lst, 'w').write(''.join(f"file '{p}'\n" for p in parts))
    raw = f'{work}/join.mp4'
    run(['ffmpeg', '-v', 'error', '-y', '-f', 'concat', '-safe', '0', '-i', lst, '-c', 'copy', raw])
    out = os.path.join(outdir, 'kansei.mp4')
    run(['ffmpeg', '-v', 'error', '-y', '-i', raw, '-af', 'loudnorm=I=-16:TP=-1.5:LRA=11', '-c:v', 'libx264', '-preset', 'medium',
         '-crf', str(K.get('crf', 23)), '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '160k', '-movflags', '+faststart', out])
    run(['ffmpeg', '-v', 'error', '-y', '-ss', '0.5', '-i', out, '-frames:v', '1', '-q:v', '3', os.path.join(outdir, 'thumb.jpg')])
    shutil.rmtree(work, ignore_errors=True)
    _, _, d, _ = probe(out)
    mb = os.path.getsize(out) / 1e6
    log(f'できました: {os.path.relpath(out, ROOT)}（{d:.0f}秒・{mb:.1f}MB・{used}/{len(rows)}行）')
    if mb > 95: log('100MB を超えそうです。GitHub に入らないので、行を減らすか crf を上げてください。')


if __name__ == '__main__':
    main()
