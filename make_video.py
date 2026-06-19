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

def fit_cover(img, w, h):
    """画像をw×hにcoverフィット（中央クロップ）"""
    iw, ih = img.size
    scale = max(w / iw, h / ih)
    nw, nh = int(iw * scale), int(ih * scale)
    img = img.resize((nw, nh), Image.LANCZOS)
    x = (nw - w) // 2
    y = (nh - h) // 2
    return img.crop((x, y, x + w, y + h))

def ken_burns(img, total_frames, zoom_start=1.0, zoom_end=1.08, pan=(0, 0)):
    """Ken Burnsエフェクト（ズーム＋パン）でフレームリストを生成"""
    frames = []
    iw, ih = img.size
    for i in range(total_frames):
        t = i / max(total_frames - 1, 1)
        zoom = zoom_start + (zoom_end - zoom_start) * t
        nw, nh = int(W * zoom), int(H * zoom)
        resized = img.resize((nw, nh), Image.LANCZOS)
        cx = nw // 2 + int(pan[0] * t * 40)
        cy = nh // 2 + int(pan[1] * t * 40)
        x = max(0, min(cx - W // 2, nw - W))
        y = max(0, min(cy - H // 2, nh - H))
        frames.append(resized.crop((x, y, x + W, y + H)))
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
        ("大　嵓　埜", H//2 - 120, 110, (220, 190, 130)),
        ("OKURANO", H//2 - 10, 36, (200, 170, 110)),
        ("夏　の　饗　宴", H//2 + 90, 52, (255, 255, 255)),
    ]),

    # --- 職人・調理イメージ1（骨切りイメージ） --- 3.0s
    ("イメージ_調理イメージ0003.jpg", 3.0, {"zoom_start":1.0,"zoom_end":1.1,"pan":(1,0)}, [
        ("職 人 の 技", H//5, 80, (255,220,140)),
        ("鱧 の 骨 切 り", H//5 + 120, 52, (255,255,255)),
        ("一 本 の 刃 に 、 魂 を 込 め て", H//5 + 200, 32, (220,220,220)),
    ]),

    # --- 調理イメージ2 --- 2.0s
    ("イメージ_調理イメージ0006.jpg", 2.0, {"zoom_start":1.05,"zoom_end":1.0,"pan":(-1,0)}, [
        ("目 利 き が 選 ぶ", H*2//5, 68, (255,220,140)),
        ("旬 の 鱧", H*2//5 + 100, 52, (255,255,255)),
    ]),

    # --- 調理イメージ3 (炭火イメージ) --- 2.0s
    ("イメージ_調理イメージ0023.jpg", 2.0, {"zoom_start":1.0,"zoom_end":1.08,"pan":(0,-1)}, [
        ("炭 火 で 焼 く", H*2//5, 72, (255,180,80)),
        ("香 ば し さ と 旨 み", H*2//5 + 110, 40, (255,255,255)),
    ]),

    # --- 連続コマ: 0027 湯引き --- 2.0s
    ("イメージ_調理イメージ0027 (1).jpg", 2.0, {"zoom_start":1.02,"zoom_end":1.08,"pan":(1,1)}, [
        ("湯 引 き  ―  白 い 芸 術", H*2//5, 68, (180,220,255)),
        ("柔 ら か く 、 上 品 に", H*2//5 + 100, 38, (255,255,255)),
    ]),

    # --- 調理イメージ連続: 0051 --- 1.5s
    ("イメージ_調理イメージ0051.jpg", 1.5, {"zoom_start":1.08,"zoom_end":1.0,"pan":(-1,0)}, [
        ("職 人 の 仕 事", H//3, 80, (255,220,140)),
    ]),

    # --- 調理イメージ 0054 --- 1.5s
    ("イメージ_調理イメージ0054.jpg", 1.5, {"zoom_start":1.0,"zoom_end":1.1,"pan":(0,1)}, [
        ("丁 寧 に 、 丁 寧 に", H//3, 68, (255,255,255)),
    ]),

    # --- 調理: 0076 --- 1.5s
    ("イメージ_調理イメージ0076.jpg", 1.5, {"zoom_start":1.05,"zoom_end":1.0,"pan":(1,-1)}, [
        ("素 材 と 向 き 合 う 時 間", H//3, 52, (220,220,220)),
    ]),

    # --- 調理: 0078 --- 1.5s
    ("イメージ_調理イメージ0078.jpg", 1.5, {"zoom_start":1.0,"zoom_end":1.08,"pan":(-1,0)}, [
        ("一 皿 に 込 め た 想 い", H//3, 52, (255,220,140)),
    ]),

    # --- 調理: 0094 --- 2.0s
    ("イメージ_調理イメージ0094.jpg", 2.0, {"zoom_start":1.0,"zoom_end":1.1,"pan":(0,-1)}, [
        ("五 感 で 味 わ う 日 本 料 理", H*2//5, 52, (255,255,255)),
    ]),

    # --- コース料理: ふうりん --- 3.0s
    ("コース_ふうりん0007修.jpg", 3.0, {"zoom_start":1.0,"zoom_end":1.06,"pan":(0,-1)}, [
        ("夏 季 限 定", H - 600, 52, (255,220,140)),
        ("大 嵓 埜 の コ ー ス", H - 500, 80, (255,255,255)),
        ("「 ふ う り ん 」", H - 390, 90, (255,200,80)),
    ]),

    # --- コース: 造里 --- 2.5s
    ("コース_ふうりん_造里0011修.jpg", 2.5, {"zoom_start":1.05,"zoom_end":1.0,"pan":(-1,0)}, [
        ("旬 の 食 材 を 職 人 が 厳 選", H//4, 46, (255,220,140)),
        ("季 節 の 美 し さ を  一 皿 に", H//4 + 80, 40, (255,255,255)),
    ]),

    # --- コース: 温物 --- 2.5s
    ("コース_ふうりん_温物0005修.jpg", 2.5, {"zoom_start":1.0,"zoom_end":1.08,"pan":(1,0)}, [
        ("特 別 な 夏 の 思 い 出 を", H - 520, 52, (255,255,255)),
        ("大 切 な 方 と と も に", H - 430, 52, (220,220,220)),
    ]),

    # --- クロージング --- 4.0s
    ("_BLACK_", 4.0, {}, [
        ("夏 の 風 物 詩", H//2 - 250, 58, (255,220,140)),
        ("「 ふ う り ん 」", H//2 - 155, 100, (255,200,60)),
        ("〜 8 月 3 1 日 ま で 〜", H//2 - 30, 44, (255,255,255)),
        ("季 節 限 定  ／  完 全 予 約 制", H//2 + 60, 36, (200,200,200)),
        ("大　嵓　埜", H//2 + 200, 80, (220,190,130)),
        ("OKURANO", H//2 + 310, 34, (180,160,100)),
    ]),
]
# 合計: 2.5+3.0+2.0+2.0+2.0+1.5+1.5+1.5+1.5+2.0+3.0+2.5+2.5+4.0 = 31.0s → フェード重複で実質30s

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
    else:
        raw = load_img(img_name)
        base = fit_cover(raw, W, H)
        base = ImageEnhance.Contrast(base).enhance(1.05)
        base = ImageEnhance.Color(base).enhance(1.1)

    # Ken Burns フレーム生成
    if img_name != "_BLACK_":
        kb_frames = ken_burns(base, total,
            zoom_start=kb.get("zoom_start", 1.0),
            zoom_end=kb.get("zoom_end", 1.08),
            pan=kb.get("pan", (0, 0)))
    else:
        kb_frames = [base.copy() for _ in range(total)]

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
