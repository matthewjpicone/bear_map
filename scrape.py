import io
import os
import random
import re
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

import cv2
import numpy as np
import pytesseract
from PIL import Image

# ---------------------------
# ADB SETUP
# ---------------------------


def get_emulator() -> str:
    result = subprocess.check_output(["adb", "devices"], text=True)
    for line in result.splitlines():
        if line.startswith("emulator-"):
            return line.split()[0]
    raise RuntimeError("No emulator found")


EMULATOR = get_emulator()
ADB = ["adb", "-s", EMULATOR]


def adb_cmd(cmd: str) -> None:
    # NOTE: simple split is fine for your current usage; keep it consistent.
    subprocess.run(ADB + cmd.split(), check=True)


# ---------------------------
# SCREENSHOT
# ---------------------------

SCREENSHOT_DIR = Path("screenshots")
SCREENSHOT_DIR.mkdir(exist_ok=True)


def screenshot(save: bool = True):
    raw = subprocess.check_output(ADB + ["exec-out", "screencap", "-p"])
    img = Image.open(io.BytesIO(raw)).convert("RGB")

    if not save:
        return img, None

    filename = (
        SCREENSHOT_DIR / f"screenshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
    )
    img.save(filename)
    return img, filename


# ---------------------------
# TEMPLATE MATCHING
# ---------------------------


def find_template(
    screen_img: Image.Image,
    template_path: str,
    threshold: float = 0.8,
) -> Optional[tuple[int, int, float]]:
    screen = cv2.cvtColor(np.array(screen_img), cv2.COLOR_RGB2BGR)
    template = cv2.imread(template_path)

    if template is None:
        raise FileNotFoundError(f"Template not found/readable: {template_path}")

    res = cv2.matchTemplate(screen, template, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, max_loc = cv2.minMaxLoc(res)

    if max_val < threshold:
        return None

    h, w = template.shape[:2]
    cx = max_loc[0] + w // 2
    cy = max_loc[1] + h // 2
    return (cx, cy, float(max_val))


# ---------------------------
# INPUT ACTIONS
# ---------------------------


def rand_in_range(min_val: int, max_val: int) -> int:
    return random.randint(min_val, max_val)


def rand_delay(min_s: float = 0.25, max_s: float = 0.6) -> None:
    time.sleep(random.uniform(min_s, max_s))


def rand_centered(min_val: int, max_val: int, sigma_ratio: float = 0.15) -> int:
    center = (min_val + max_val) / 2
    sigma = (max_val - min_val) * sigma_ratio
    v = random.gauss(center, sigma)
    return int(max(min_val, min(max_val, v)))


def tap(x_min: int, x_max: int, y_min: int, y_max: int) -> None:
    x = rand_centered(x_min, x_max)
    y = rand_centered(y_min, y_max)
    adb_cmd(f"shell input tap {x} {y}")


def swipe(x1: int, y1: int, x2: int, y2: int) -> None:
    adb_cmd(f"shell input swipe {x1} {y1} {x2} {y2}")


# -----------------------------
# Regex (tolerant to OCR errors)
# -----------------------------

POWER_M_RE = re.compile(r"(\d+(?:\.\d+)?)\s*[mM]\b")
POWER_NUM_RE = re.compile(r"\b(\d{1,3}(?:,\d{3})+|\d{4,})\b")
LV_RE = re.compile(r"\b(?:Lv|Lw|Iv|Wv|wv)\.?\s*(\d{1,2})\b", re.I)


def parse_power(text: str) -> Optional[int]:
    text = text.replace("O", "0")
    m = POWER_M_RE.search(text)
    if m:
        return int(float(m.group(1)) * 1_000_000)

    m = POWER_NUM_RE.search(text)
    if m:
        return int(m.group(1).replace(",", ""))

    return None


def parse_level(text: str) -> Optional[int]:
    m = LV_RE.search(text)
    if not m:
        return None
    lvl = int(m.group(1))
    return lvl if 1 <= lvl <= 60 else None


def clean_name(s: str) -> str:
    s = s.strip()
    s = re.sub(r"^(R[1-5]\s+)", "", s, flags=re.I)
    s = re.sub(r"\s{2,}", " ", s).strip()
    # keep latin + digits + underscore + spaces + CJK
    s = re.sub(r"^[^0-9A-Za-z\u4e00-\u9fff\u3040-\u30ff\uac00-\ud7af]+", "", s)
    s = re.sub(r"[^0-9A-Za-z\u4e00-\u9fff\u3040-\u30ff\uac00-\ud7af_ ]+$", "", s)
    return s.strip()


def valid_name(s: str) -> bool:
    if len(s) < 2:
        return False
    return bool(re.search(r"[0-9A-Za-z\u4e00-\u9fff\u3040-\u30ff\uac00-\ud7af]", s))


# -----------------------------
# OCR preprocessing tuned for white text on dark card
# -----------------------------


def prep_for_ocr(bgr: np.ndarray) -> np.ndarray:
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    inv = 255 - gray
    inv = cv2.GaussianBlur(inv, (3, 3), 0)
    _, thr = cv2.threshold(inv, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    thr = cv2.morphologyEx(thr, cv2.MORPH_OPEN, np.ones((2, 2), np.uint8))
    return thr


def ocr_text(bgr: np.ndarray, lang: str = "eng+chi_sim+jpn+kor", psm: int = 6) -> str:
    thr = prep_for_ocr(bgr)
    cfg = f"--oem 1 --psm {psm}"
    return pytesseract.image_to_string(thr, lang=lang, config=cfg)


# -----------------------------
# “Online” heuristic (green label area)
# -----------------------------


def detect_online(card_bgr: np.ndarray) -> bool:
    h, w = card_bgr.shape[:2]
    roi = card_bgr[int(h * 0.70) : int(h * 0.95), 0 : int(w * 0.30)]
    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, (35, 60, 60), (90, 255, 255))
    return (mask.mean() / 255.0) > 0.02


# -----------------------------
# Candidate card detection (shape/edges > color)
# -----------------------------


def detect_card_candidates(img_bgr: np.ndarray) -> list[tuple[int, int, int, int]]:
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 50, 150)
    edges = cv2.dilate(edges, np.ones((3, 3), np.uint8), iterations=1)

    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    boxes: list[tuple[int, int, int, int]] = []
    h_img, w_img = img_bgr.shape[:2]

    for c in contours:
        x, y, w, h = cv2.boundingRect(c)
        area = w * h
        if area < 60_000:
            continue

        ar = w / float(h)
        if not (1.6 <= ar <= 6.0):
            continue

        if x <= 0 or y <= 0 or x + w >= w_img - 1 or y + h >= h_img - 1:
            continue

        boxes.append((x, y, w, h))

    boxes = sorted(boxes, key=lambda b: b[2] * b[3], reverse=True)

    kept: list[tuple[int, int, int, int]] = []
    for x, y, w, h in boxes:
        bx1, by1, bx2, by2 = x, y, x + w, y + h
        overlapped = False

        for kx, ky, kw, kh in kept:
            kx1, ky1, kx2, ky2 = kx, ky, kx + kw, ky + kh
            ix1, iy1 = max(bx1, kx1), max(by1, ky1)
            ix2, iy2 = min(bx2, kx2), min(by2, ky2)
            inter = max(0, ix2 - ix1) * max(0, iy2 - iy1)

            if inter / float(w * h) > 0.6:
                overlapped = True
                break

        if not overlapped:
            kept.append((x, y, w, h))

    return kept


def select_cards(
    boxes: list[tuple[int, int, int, int]],
) -> tuple[list[tuple[int, int, int, int]], Optional[tuple[int, int, int, int]]]:
    if not boxes:
        return [], None

    heights = [h for _, _, _, h in boxes]
    max_h = max(heights)

    full = [b for b in boxes if b[3] >= 0.95 * max_h]
    top_card = min(boxes, key=lambda b: (b[1], -b[2]))  # smallest y, then widest
    return full, top_card


def parse_card(img_bgr: np.ndarray, box: tuple[int, int, int, int]) -> Optional[dict]:
    x, y, w, h = box
    card = img_bgr[y : y + h, x : x + w]

    x0 = int(w * 0.22)
    roi = card[:, x0:]

    txt = ocr_text(roi)
    lines = [ln.strip() for ln in txt.splitlines() if ln.strip()]
    if not lines:
        return None

    joined = " ".join(lines)
    power = parse_power(joined)
    level = parse_level(joined)

    if power is None or level is None:
        return None

    name = None
    for ln in lines[:4]:
        if LV_RE.search(ln):
            continue
        if re.search(r"\d", ln) and ("M" in ln or "," in ln):
            continue
        cand = clean_name(ln)
        if valid_name(cand):
            name = cand
            break

    if not name:
        name = clean_name(lines[0])

    if not valid_name(name):
        return None

    return {
        "name": name,
        "online": detect_online(card),
        "power": power,
        "level": level,
    }


def process_folder(folder: str = "screenshots") -> list[dict]:
    out: dict[str, dict] = {}

    for fn in sorted(os.listdir(folder)):
        if not fn.lower().endswith(".png"):
            continue

        path = os.path.join(folder, fn)
        img = cv2.imread(path)
        if img is None:
            continue

        boxes = detect_card_candidates(img)
        full_cards, top_card = select_cards(boxes)

        targets = list(full_cards)
        if top_card and top_card not in targets:
            targets.append(top_card)

        for b in targets:
            parsed = parse_card(img, b)
            if parsed:
                out[parsed["name"]] = parsed

    return sorted(out.values(), key=lambda p: (-p["power"], p["name"]))


if __name__ == "__main__":
    # Take Screenshots
    for _ in range(5):
        img, path = screenshot()
        print(f"Saved screenshot to: {path}")
        swipe(500, 1500, 490, 1300)
        rand_delay(2, 5)

    players = process_folder("screenshots")
    for p in players:
        print(p)
