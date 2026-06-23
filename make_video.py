#!/usr/bin/env python3
"""
大嵓埜「ふうりん」夏季限定コース - SNS動画生成スクリプト
縦型 (1080x1920) Instagram Reels / TikTok 向け
"""

import os
import subprocess
import math
import shutil
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance
import numpy as np

FFMPEG = "/usr/local/lib/python3.11/dist-packages/imageio_ffmpeg/binaries/ffmpeg-linux-x86_64-v7.0.2"
FONT_GOTHIC = "/usr/share/fonts/truetype/fonts-japanese-gothic.ttf"
IMG_DIR = "/home/user/okurano0625/images"

# ファイル名のUnicode正規化差異を吸収するマッピングを構築
import unicodedata as _ud
_actual_files = {_ud.normalize("NFC", f): f for f in os.listdir(IMG_DIR) if f.endswith(".jpg")}
def _resolve(name):
    return _actual_files.get(_ud.normalize("NFC", name), name)
OUT_DIR = "/tmp/video_frames"
OUT_VIDEO = "/home/user/okurano0625/furin_summer_2025.mp4"

W, H = 1080, 1920
FPS = 30

os.makedirs(OUT_DIR, exist_ok=True)

def font(size):
    return ImageFont.truetype(FONT_GOTHIC, size)

def load_img(name):
    path = os.path.join(IMG_DIR, _resolve(name))
    return Image.open(path).convert("RGB")

def make_bg(img, w, h):
    """背景用: coverでクロップしてぼかし"""
    iw, ih = img.size
    bg_scale = max(w / iw, h / ih)
    bg_w, bg_h = int(iw * bg_scale), int(ih * bg_scale)
    bg = img.resize((bg_w, bg_h), Image.LANCZOS)
    bx, by = (bg_w - w) // 2, (bg_h - h) // 2
    bg = bg.crop((bx, by, bx + w, by + h))
    bg = bg.filter(ImageFilter.GaussianBlur(radius=30))
    return ImageEnhance.Brightness(bg).enhance(0.35)

def make_fg(img, w, h):
    """前景用: containで全体表示。(fg画像, paste_x, paste_y) を返す"""
    iw, ih = img.size
    fg_scale = min(w / iw, h / ih)
    fg_w, fg_h = int(iw * fg_scale), int(ih * fg_scale)
    fg = img.resize((fg_w, fg_h), Image.LANCZOS)
    px = (w - fg_w) // 2
    py = (h - fg_h) // 2
    return fg, px, py

def ken_burns_frames(raw_img, total_frames, zoom_start=1.0, zoom_end=1.05, pan=(0, 0)):
    """背景にのみKen Burnsを適用し、前景は静止させてcompositeしたフレームリストを返す"""
    bg_base = make_bg(raw_img, W, H)
    fg, px, py = make_fg(raw_img, W, H)
    frames = []
    for i in range(total_frames):
        t = i / max(total_frames - 1, 1)
        zoom = zoom_start + (zoom_end - zoom_start) * t
        # 背景のみズーム＋パン
        nw, nh = int(W * zoom), int(H * zoom)
        bg = bg_base.resize((nw, nh), Image.LANCZOS)
        cx = nw // 2 + int(pan[0] * t * 30)
        cy = nh // 2 + int(pan[1] * t * 30)
        bx = max(0, min(cx - W // 2, nw - W))
        by = max(0, min(cy - H // 2, nh - H))
        bg = bg.crop((bx, by, bx + W, by + H))
        # 前景を静止して合成（切れなし）
        canvas = bg.copy()
        canvas.paste(fg, (px, py))
        frames.append(canvas)
    return frames

def draw_text_with_shadow(draw, text, x, y, fnt, color=(255,255,255), shadow=(0,0,0), anchor="mm"):
    for dx, dy in [(-2,-2),(2,-2),(-2,2),(2,2),(0,3),(3,0)]:
        draw.text((x+dx, y+dy), text, font=fnt, fill=shadow + (200,), anchor=anchor)
    draw.text((x, y), text, font=fnt, fill=color + (255,), anchor=anchor)

def overlay_gradient_top(img, strength=0.5):
    arr = np.array(img).astype(float)
    grad = np.linspace(strength, 0, H // 3)
    grad = np.concatenate([grad, np.zeros(H - H // 3)])
    mask = grad[:, np.newaxis, np.newaxis]
    arr = arr * (1 - mask)
    return Image.fromarray(arr.clip(0, 255).astype(np.uint8))

def overlay_gradient_bottom(img, strength=0.6):
    arr = np.array(img).astype(float)
    grad = np.linspace(0, strength, H // 2)
    grad = np.concatenate([np.zeros(H - H // 2), grad])
    mask = grad[:, np.newaxis, np.newaxis]
    arr = arr * (1 - mask)
    return Image.fromarray(arr.clip(0, 255).astype(np.uint8))

def add_telop(base, lines, y_positions, sizes, colors=None, align="center"):
    """テロップを重ねる"""
    img = base.copy().convert("RGBA")
    overlay = Image.new("RGBA", img.size, (0,0,0,0))
    draw = ImageDraw.Draw(overlay)
    if colors is None:
        colors = [(255,255,255)] * len(lines)
    for text, y, size, color in zip(lines, y_positions, sizes, colors):
        fnt = font(size)
        x = W // 2 if align == "center" else 80
        draw_text_with_shadow(draw, text, x, y, fnt, color=color, anchor="mm" if align=="center" else "lm")
    return Image.alpha_composite(img, overlay).convert("RGB")

def black_fade(img, alpha):
    """黒へフェード (alpha=0: 元画像, alpha=1: 黒)"""
    black = Image.new("RGB", img.size, (0, 0, 0))
    return Image.blend(img, black, alpha)

def white_line(img, y, thickness=3, alpha=180):
    overlay = Image.new("RGBA", (W, H), (0,0,0,0))
    draw = ImageDraw.Draw(overlay)
    draw.rectangle([80, y, W-80, y+thickness], fill=(255,220,150,alpha))
    base = img.convert("RGBA")
    return Image.alpha_composite(base, overlay).convert("RGB")

# ===== シーン定義 =====
# 各シーン: (画像ファイル名, 秒数, Ken Burns設定, テロップリスト)

scenes = [
    # --- オープニング: 黒背景タイトル --- 2.5s
    ("_BLACK_", 2.5, {}, [
        ("大　嵓　埜", H//4 - 60, 110, (220, 190, 130)),
        ("OKURANO", H//4 + 60, 36, (200, 170, 110)),
        ("夏　の　饗　宴", H//4 + 150, 52, (255, 255, 255)),
    ]),

    # --- 職人・調理イメージ1（骨切りイメージ） --- 3.0s
    ("イメージ_調理イメージ0003.jpg", 3.0, {"zoom_start":1.0,"zoom_end":1.1,"pan":(1,0)}, [
        ("職 人 の 技", 120, 80, (255,220,140)),
        ("鱧 の 骨 切 り", 230, 52, (255,255,255)),
        ("一 本 の 刃 に 、 魂 を 込 め て", 305, 32, (220,220,220)),
    ]),

    # --- 調理イメージ2 --- 2.0s
    ("イメージ_調理イメージ0006.jpg", 2.0, {"zoom_start":1.0,"zoom_end":1.0,"pan":(0,0)}, [
        ("目 利 き が 選 ぶ", 130, 68, (255,220,140)),
        ("旬 の 鱧", 220, 52, (255,255,255)),
    ]),

    # --- 調理イメージ3 (魚を捌くシーン) --- 2.0s
    ("イメージ_調理イメージ0023.jpg", 2.0, {"zoom_start":1.0,"zoom_end":1.05,"pan":(0,-1)}, [
        ("丁 寧 に 捌 く", 130, 72, (255,220,140)),
        ("職 人 の 手 さ ば き", 220, 40, (255,255,255)),
    ]),

    # --- 0027 捌くシーン④ --- 2.0s
    ("イメージ_調理イメージ0027 (1).jpg", 2.0, {"zoom_start":1.0,"zoom_end":1.05,"pan":(0,0)}, [
        ("骨 切 り の 技 法", 130, 72, (255,220,140)),
        ("一 刀 一 刀 に 魂 を 込 め て", 215, 38, (255,255,255)),
    ]),

    # --- 0051 炭火① --- 1.5s
    ("イメージ_調理イメージ0051.jpg", 1.5, {"zoom_start":1.0,"zoom_end":1.05,"pan":(-1,0)}, [
        ("炭 火 で 焼 く", 140, 72, (255,180,80)),
        ("香 ば し さ と 旨 み", 220, 38, (255,255,255)),
    ]),

    # --- 0054 炭火② --- 1.5s
    ("イメージ_調理イメージ0054.jpg", 1.5, {"zoom_start":1.0,"zoom_end":1.05,"pan":(0,1)}, [
        ("炭 火 の 芸 術", 140, 72, (255,180,80)),
        ("じ っ く り 、 丁 寧 に", 220, 38, (255,255,255)),
    ]),

    # --- 0076 湯引き① --- 1.5s
    ("イメージ_調理イメージ0076.jpg", 1.5, {"zoom_start":1.0,"zoom_end":1.05,"pan":(1,0)}, [
        ("湯 引 き  ―  白 い 芸 術", 130, 68, (180,220,255)),
        ("柔 ら か く 、 上 品 に", 215, 38, (255,255,255)),
    ]),

    # --- 0078 湯引き② --- 1.5s
    ("イメージ_調理イメージ0078.jpg", 1.5, {"zoom_start":1.0,"zoom_end":1.05,"pan":(-1,0)}, [
        ("鱧 の 湯 引 き", 130, 72, (180,220,255)),
        ("繊 細 な 技 が 生 み 出 す 美 味", 215, 36, (255,255,255)),
    ]),

    # --- 0094 湯引き③ --- 2.0s
    ("イメージ_調理イメージ0094.jpg", 2.0, {"zoom_start":1.0,"zoom_end":1.05,"pan":(0,-1)}, [
        ("湯 引 き の 美 し さ", 130, 68, (180,220,255)),
        ("五 感 で 味 わ う 日 本 料 理", 215, 40, (255,255,255)),
    ]),

    # --- コース料理: ふうりん --- 3.0s
    ("コース_ふうりん0007修.jpg", 3.0, {"zoom_start":1.0,"zoom_end":1.06,"pan":(0,-1)}, [
        ("夏 季 限 定", 100, 52, (255,220,140)),
        ("「 ふ う り ん 」", 210, 90, (255,200,80)),
    ]),

    # --- コース: 造里 --- 2.5s
    ("コース_ふうりん_造里0011修.jpg", 2.5, {"zoom_start":1.05,"zoom_end":1.0,"pan":(-1,0)}, [
        ("旬 の 食 材 を 職 人 が 厳 選", 110, 46, (255,220,140)),
        ("季 節 の 美 し さ を  一 皿 に", 175, 40, (255,255,255)),
    ]),

    # --- コース: 温物 --- 2.5s
    ("コース_ふうりん_温物0005修.jpg", 2.5, {"zoom_start":1.0,"zoom_end":1.08,"pan":(1,0)}, [
        ("特 別 な 夏 の 思 い 出 を", 110, 52, (255,255,255)),
        ("大 切 な 方 と と も に", 180, 52, (220,220,220)),
    ]),

    # --- クロージング --- 4.0s
    ("_BLACK_", 4.0, {}, [
        ("夏 の 風 物 詩", H//4 - 130, 58, (255,220,140)),
        ("「 ふ う り ん 」", H//4 - 25, 100, (255,200,60)),
        ("〜 8 月 3 1 日 ま で 〜", H//4 + 100, 44, (255,255,255)),
        ("季 節 限 定  ／  完 全 予 約 制", H//4 + 165, 36, (200,200,200)),
        ("大　嵓　埜", H//4 + 310, 80, (220,190,130)),
        ("OKURANO", H//4 + 420, 34, (180,160,100)),
    ]),
]
# 合計: 2.5+3.0+2.0+2.0+2.0+1.5+1.5+1.5+1.5+2.0+3.0+2.5+2.5+4.0 = 31.0s → フェード重複で実質30s

# QRコードを読み込んでおく
_qr_file = next(f for f in os.listdir(IMG_DIR) if "QR" in f or "qr" in f)
_qr_raw = Image.open(os.path.join(IMG_DIR, _qr_file)).convert("RGBA")
QR_SIZE = 360
_qr_img = _qr_raw.resize((QR_SIZE, QR_SIZE), Image.LANCZOS)

def paste_qr(img, alpha=1.0):
    """QRコードを画面下部中央に貼る"""
    canvas = img.convert("RGBA")
    qr = _qr_img.copy()
    # 白背景のパディング
    pad = 12
    bg = Image.new("RGBA", (QR_SIZE + pad*2, QR_SIZE + pad*2), (255,255,255,230))
    bg.paste(qr, (pad, pad), qr)
    # アルファ調整
    if alpha < 1.0:
        r, g, b, a = bg.split()
        a = a.point(lambda x: int(x * alpha))
        bg = Image.merge("RGBA", (r, g, b, a))
    qx = (W - bg.width) // 2
    qy = H - bg.height - 280
    canvas.paste(bg, (qx, qy), bg)
    return canvas.convert("RGB")

frame_idx = 0

def write_frame(img, count=1):
    global frame_idx
    arr = np.array(img)
    for _ in range(count):
        path = os.path.join(OUT_DIR, f"frame_{frame_idx:06d}.png")
        Image.fromarray(arr).save(path, optimize=False)
        frame_idx += 1

def ease_in_out(t):
    return t * t * (3 - 2 * t)

print("フレーム生成開始...")

for scene_i, (img_name, duration, kb, telops) in enumerate(scenes):
    total = int(duration * FPS)
    fade_frames = int(0.4 * FPS)  # 0.4秒フェード

    print(f"  シーン {scene_i+1}/{len(scenes)}: {img_name} ({duration}s, {total}frames)")

    if img_name == "_BLACK_":
        base = Image.new("RGB", (W, H), (10, 8, 6))
        kb_frames = [base.copy() for _ in range(total)]
    else:
        raw = load_img(img_name)
        raw = ImageEnhance.Contrast(raw).enhance(1.05)
        raw = ImageEnhance.Color(raw).enhance(1.1)
        kb_frames = ken_burns_frames(raw, total,
            zoom_start=kb.get("zoom_start", 1.0),
            zoom_end=kb.get("zoom_end", 1.05),
            pan=kb.get("pan", (0, 0)))

    for i, frame in enumerate(kb_frames):
        t = i / max(total - 1, 1)

        # グラデーションオーバーレイ
        if img_name != "_BLACK_":
            frame = overlay_gradient_top(frame, 0.35)
            frame = overlay_gradient_bottom(frame, 0.55)

        # テロップ
        lines = [t[0] for t in telops]
        ys = [t[1] for t in telops]
        sizes = [t[2] for t in telops]
        colors = [t[3] for t in telops]

        # テロップのフェードイン (0.5秒)
        telop_fade = min(1.0, i / (0.5 * FPS))
        frame_rgba = frame.convert("RGBA")
        telop_layer = Image.new("RGBA", (W, H), (0,0,0,0))
        draw = ImageDraw.Draw(telop_layer)
        for text, y, size, color in zip(lines, ys, sizes, colors):
            fnt = font(size)
            alpha = int(255 * ease_in_out(telop_fade))
            draw_text_with_shadow(draw, text, W//2, y, fnt, color=color, shadow=(0,0,0))
        # アルファ調整
        r, g, b, a = telop_layer.split()
        a = a.point(lambda x: int(x * ease_in_out(telop_fade)))
        telop_layer = Image.merge("RGBA", (r, g, b, a))
        frame = Image.alpha_composite(frame_rgba, telop_layer).convert("RGB")

        # クロージングシーン（最後の_BLACK_）にQRコードを表示
        if img_name == "_BLACK_" and scene_i == len(scenes) - 1:
            qr_fade = ease_in_out(min(1.0, (i - fade_frames) / (0.8 * FPS))) if i > fade_frames else 0.0
            if qr_fade > 0:
                frame = paste_qr(frame, alpha=qr_fade)

        # フェードイン/アウト
        if i < fade_frames:
            alpha = ease_in_out(i / fade_frames)
            frame = Image.blend(Image.new("RGB", (W, H), (0,0,0)), frame, alpha)
        elif i >= total - fade_frames:
            alpha = ease_in_out((total - i) / fade_frames)
            frame = Image.blend(Image.new("RGB", (W, H), (0,0,0)), frame, alpha)

        write_frame(frame)

print(f"総フレーム数: {frame_idx}")
print("動画エンコード中...")

cmd = [
    FFMPEG, "-y",
    "-framerate", str(FPS),
    "-i", os.path.join(OUT_DIR, "frame_%06d.png"),
    "-c:v", "libx264",
    "-crf", "18",
    "-preset", "slow",
    "-pix_fmt", "yuv420p",
    "-movflags", "+faststart",
    OUT_VIDEO
]

result = subprocess.run(cmd, capture_output=True, text=True)
if result.returncode != 0:
    print("エラー:", result.stderr[-2000:])
else:
    size_mb = os.path.getsize(OUT_VIDEO) / 1024 / 1024
    duration_total = frame_idx / FPS
    print(f"完成: {OUT_VIDEO}")
    print(f"  サイズ: {size_mb:.1f} MB")
    print(f"  尺: {duration_total:.1f} 秒")

# 後片付け
shutil.rmtree(OUT_DIR, ignore_errors=True)
