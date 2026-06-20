# -*- coding: utf-8 -*-
"""
卡牌角标 / 边框 合成（共用于列表与组卡器）
==========================================
把 assets/Sprite/ 下的素材合成为「右上角类别角标」PNG，写到 assets/markers/。
卡图本体是远程图，边框(IconRarity) 与角标(marker) 在 HTML 里叠放在卡图之上。

角标规则：
  * 底框颜色按 attribute：IconType{001..005}L...  （1火2水3風4光5闇）
  * 不可觉醒：IconType{a}LImage.png(75x75) 中心贴 CardIcon{ct}LImage.png(60x60)
  * 觉醒：IconType{a}LImageAwakening.png(129x76)
        右(大圈,center 91,38,直径74) 贴 CardIcon{原始ct}(60x60)
        左(小圈,center 32,32,直径63) 贴 CardIcon{觉醒新增ct} 按圆比例缩放到 51x51
        组卡器中按条目只贴其一（base=只大圈 / add=只小圈）
  * 超觉醒：IconType{a}LImageSuperAwakening001.png(90x90) 中心贴 CardIcon{ct}(60x60)
边框：Ultimate(gradeType==2) 用 IconRarity08L，其余用 IconRarity06L（整张覆盖卡图）。
"""

import os
from PIL import Image

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SPRITE_DIR = os.path.join(SCRIPT_DIR, "assets", "Sprite")
MARKER_DIR = os.path.join(SCRIPT_DIR, "assets", "markers")
MARKER_REL = "assets/markers"

# 合成位置（中心坐标）/ 尺寸（实测自素材）
PLAIN_C = (37, 37)       # 75x75 单圈
SUPER_C = (45, 45)       # 90x90 单菱形
AWK_BIG = (91, 38)       # 129x76 右·大圈(直径74) -> 原始类别 CardIcon 60x60
AWK_SMALL = (32, 32)     # 129x76 左·小圈(直径63) -> 觉醒新增类别 CardIcon 按比例缩放
AWK_SMALL_SIZE = 51      # 60 * 63/74 ≈ 51，使小圈图标占比与大圈一致

_disk_cache = {}       # fname -> rel path（本次运行已写盘）
_img_cache = {}


def _img(name):
    if name not in _img_cache:
        _img_cache[name] = Image.open(os.path.join(SPRITE_DIR, name)).convert("RGBA")
    return _img_cache[name].copy()


def _paste_center(base, icon_name, center, size=None):
    ic = _img(icon_name)
    if size and size != ic.width:
        ic = ic.resize((size, size), Image.LANCZOS)
    x = int(round(center[0] - ic.width / 2.0))
    y = int(round(center[1] - ic.height / 2.0))
    base.alpha_composite(ic, (x, y))


def _ensure(fname, builder):
    if fname in _disk_cache:
        return _disk_cache[fname]
    os.makedirs(MARKER_DIR, exist_ok=True)
    builder().save(os.path.join(MARKER_DIR, fname))
    rel = MARKER_REL + "/" + fname
    _disk_cache[fname] = rel
    return rel


def marker_none(attr, ctype):
    def b():
        base = _img("IconType%03dLImage.png" % attr)
        _paste_center(base, "CardIcon%03dLImage.png" % ctype, PLAIN_C)
        return base
    return _ensure("mk_n_%d_%d.png" % (attr, ctype), b)


def marker_super(attr, ctype):
    def b():
        base = _img("IconType%03dLImageSuperAwakening001.png" % attr)
        _paste_center(base, "CardIcon%03dLImage.png" % ctype, SUPER_C)
        return base
    return _ensure("mk_s_%d_%d.png" % (attr, ctype), b)


def marker_awakening(attr, base_type, add_type, mode):
    """mode: 'full'(两圈) / 'base'(只大圈) / 'add'(只小圈)。"""
    def b():
        base = _img("IconType%03dLImageAwakening.png" % attr)
        if mode in ("full", "base"):
            _paste_center(base, "CardIcon%03dLImage.png" % base_type, AWK_BIG)
        if mode in ("full", "add"):
            _paste_center(base, "CardIcon%03dLImage.png" % add_type, AWK_SMALL, AWK_SMALL_SIZE)
        return base
    if mode == "base":
        key = "mk_ab_%d_%d.png" % (attr, base_type)
    elif mode == "add":
        key = "mk_aa_%d_%d.png" % (attr, add_type)
    else:
        key = "mk_a_%d_%d_%d.png" % (attr, base_type, add_type)
    return _ensure(key, b)


def marker_for(entry, context):
    """根据条目返回角标相对路径。context: 'list'(觉醒两圈都贴) / 'deck'(按条目只贴一圈)。"""
    attr = entry["attribute"]
    ct = entry["cardType"]
    awk = entry.get("awk", "none")
    if awk == "super":
        return marker_super(attr, ct)
    if awk == "awakening":
        bt, at = entry["baseType"], entry["addType"]
        if context == "list":
            return marker_awakening(attr, bt, at, "full")
        return marker_awakening(attr, bt, at, "base" if entry.get("role") == "base" else "add")
    return marker_none(attr, ct)


def frame_rel(is_ultimate):
    return "assets/Sprite/IconRarity0%dLImage.png" % (8 if is_ultimate else 6)
