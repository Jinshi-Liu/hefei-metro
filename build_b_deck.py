# -*- coding: utf-8 -*-
"""Build the B-item draft deck, matching A's deck design.

Design system lifted from 合肥轨道交通_A项数据与建模.pptx:
  bg 0E1B31 | card 172943 | teal 14B8A6 | gold F6C453 | muted AFC0D4 | white
  font Microsoft YaHei | 13.333 x 7.5 in
"""

from __future__ import annotations

import sys
from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Emu, Inches, Pt

sys.stdout.reconfigure(encoding="utf-8")

HERE = Path(__file__).resolve().parent
FIGS = HERE / "B任务成果" / "figures_deck"
OUT = HERE / "B任务成果" / "合肥轨道交通_B项中心性与单站换乘中断_草稿.pptx"

BG = RGBColor(0x0E, 0x1B, 0x31)
CARD = RGBColor(0x17, 0x29, 0x43)
TEAL = RGBColor(0x14, 0xB8, 0xA6)
GOLD = RGBColor(0xF6, 0xC4, 0x53)
MUTED = RGBColor(0xAF, 0xC0, 0xD4)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
BLUE = RGBColor(0x4F, 0x9C, 0xF7)
DIM = RGBColor(0x8A, 0xA0, 0xBB)
FONT = "Microsoft YaHei"

prs = Presentation()
prs.slide_width = Inches(13.333)
prs.slide_height = Inches(7.5)
BLANK = prs.slide_layouts[6]


# ---------------------------------------------------------------- helpers
def set_bg(slide):
    f = slide.background.fill
    f.solid()
    f.fore_color.rgb = BG


def textbox(slide, x, y, w, h, text, size, color, bold=False,
            align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP, spacing=None,
            line_spacing=None):
    tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = anchor
    tf.margin_left = 0
    tf.margin_right = 0
    tf.margin_top = 0
    tf.margin_bottom = 0
    lines = text.split("\n") if isinstance(text, str) else text
    for i, line in enumerate(lines):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        if spacing is not None:
            p.space_after = Pt(spacing)
        if line_spacing is not None:
            p.line_spacing = line_spacing
        r = p.add_run()
        r.text = line
        r.font.size = Pt(size)
        r.font.bold = bold
        r.font.color.rgb = color
        r.font.name = FONT
    return tb


def rich(slide, x, y, w, h, parts, anchor=MSO_ANCHOR.TOP):
    """parts = list of paragraphs; each paragraph = list of (text, size, color, bold)."""
    tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = anchor
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    for i, para in enumerate(parts):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        for text, size, color, bold in para:
            r = p.add_run()
            r.text = text
            r.font.size = Pt(size)
            r.font.bold = bold
            r.font.color.rgb = color
            r.font.name = FONT
    return tb


def rect(slide, x, y, w, h, color, shape=MSO_SHAPE.ROUNDED_RECTANGLE,
         radius=0.06, line=None):
    s = slide.shapes.add_shape(shape, Inches(x), Inches(y), Inches(w), Inches(h))
    s.fill.solid()
    s.fill.fore_color.rgb = color
    if line is None:
        s.line.fill.background()
    else:
        s.line.color.rgb = line
        s.line.width = Pt(1)
    s.shadow.inherit = False
    if shape == MSO_SHAPE.ROUNDED_RECTANGLE:
        try:
            s.adjustments[0] = radius
        except Exception:
            pass
    return s


def chrome(slide, num, kicker, title, footer):
    set_bg(slide)
    # left accent bar
    rect(slide, 0, 0, 0.13, 7.5, TEAL, shape=MSO_SHAPE.RECTANGLE)
    textbox(slide, 0.46, 0.32, 0.7, 0.3, f"{num:02d}", 12, TEAL, bold=True)
    textbox(slide, 1.14, 0.33, 11.5, 0.27, kicker, 10, MUTED)
    textbox(slide, 0.56, 0.91, 12.15, 0.6, title, 28, WHITE, bold=True)
    ln = slide.shapes.add_connector(1, Inches(0.55), Inches(1.65),
                                    Inches(12.7), Inches(1.65))
    ln.line.color.rgb = CARD
    ln.line.width = Pt(1)
    if footer:
        textbox(slide, 0.56, 7.13, 11.9, 0.2, footer, 9, MUTED)


FOOT = "B 项｜中心性、路径评价与单站换乘中断｜2026年11月 草稿"


def statcard(slide, x, y, w, h, value, label, color=TEAL, vsize=32):
    rect(slide, x, y, w, h, CARD)
    textbox(slide, x + 0.23, y + 0.2, w - 0.4, 0.6, value, vsize, color, bold=True)
    textbox(slide, x + 0.23, y + h - 0.48, w - 0.4, 0.3, label, 12, MUTED)


def add_image(slide, name, x, y, w=None, h=None):
    p = FIGS / name
    kw = {}
    if w is not None:
        kw["width"] = Inches(w)
    if h is not None:
        kw["height"] = Inches(h)
    return slide.shapes.add_picture(str(p), Inches(x), Inches(y), **kw)


# ================================================================ 1 cover
s = prs.slides.add_slide(BLANK)
set_bg(s)
rect(s, 0, 0, 0.13, 7.5, TEAL, shape=MSO_SHAPE.RECTANGLE)
# decorative rings
for r, dx in ((7.2, 0.0), (5.8, 0.8)):
    c = rect(s, 8.3 + dx, -1.5 + dx / 2, r, r, BG, shape=MSO_SHAPE.OVAL, line=CARD)
rect(s, 0.84, 1.04, 3.25, 0.35, CARD)
textbox(s, 0.93, 1.1, 3.07, 0.21, "复杂系统分析 · B 项阶段成果", 10, TEAL, bold=True)
textbox(s, 0.84, 2.03, 11.5, 0.78, "中心性、路径评价与单站换乘中断", 37, WHITE, bold=True)
textbox(s, 0.86, 3.06, 10.3, 0.53,
        "结构排名 · 逐站出行损失 · 统一路径评价", 22, MUTED)
rect(s, 0.86, 4.04, 2.0, 0.035, TEAL, shape=MSO_SHAPE.RECTANGLE)
textbox(s, 0.86, 4.48, 9.7, 1.0,
        "关键换乘节点识别与出行鲁棒性\n——考虑绕行与换乘代价", 22, WHITE)
textbox(s, 0.86, 6.72, 9.6, 0.34,
        "基于1—8号线初步模型｜19座换乘站逐一中断｜2026年11月 草稿", 12, MUTED)

# ================================================================ 2 B任务
s = prs.slides.add_slide(BLANK)
chrome(s, 2, "B SCOPE", "B 项任务与研究问题", FOOT)

rect(s, 0.6, 2.03, 6.0, 3.6, CARD)
textbox(s, 0.9, 2.35, 5.5, 0.42, "核心研究问题", 18, TEAL, bold=True)
textbox(s, 0.9, 2.95, 5.35, 1.5,
        "中心性高的换乘站，是否也是换乘中断后出行损失最大的站？", 22, WHITE, bold=True)
rect(s, 0.96, 4.5, 1.6, 0.03, TEAL, shape=MSO_SHAPE.RECTANGLE)
textbox(s, 0.9, 4.72, 5.35, 0.75,
        "不预设结论：分别报告不可达比例\n与仍可达行程的绕行代价。", 13, MUTED, spacing=3)

rect(s, 6.85, 2.03, 5.8, 3.6, CARD)
textbox(s, 7.17, 2.36, 5.2, 0.42, "B 项交付（第 2 周）", 18, GOLD, bold=True)
items = [
    "中心性计算与基础排名",
    "统一路径评价（不可达／绕行／换乘分开统计）",
    "19 座换乘站逐一中断的逐站损失表",
    "换乘惩罚参数敏感性初检",
]
for i, t in enumerate(items):
    y = 3.02 + i * 0.62
    rect(s, 7.17, y + 0.09, 0.09, 0.09, TEAL, shape=MSO_SHAPE.OVAL)
    textbox(s, 7.45, y - 0.02, 5.0, 0.34, t, 14, WHITE)

rect(s, 0.68, 5.78, 12.0, 0.62, CARD)
textbox(s, 0.97, 5.95, 11.4, 0.3,
        "口径前提：代价 = 站数 + 换乘次数×惩罚（等效站数，非分钟）；OD 以物理站点为单位。",
        13, GOLD, bold=True)

# ================================================================ 3 口径
s = prs.slides.add_slide(BLANK)
chrome(s, 3, "METHOD & SCOPE", "实验口径：先定规则，再谈结论", FOOT)

cards = [
    ("物理车站网络", TEAL, ["195 节点 / 207 边", "同名换乘站合并", "算度、介数等结构排名"]),
    ("站点—线路网络", BLUE, ["215 个(站,线)节点", "207 运行边 + 21 换乘边", "用于区分乘车与换乘"]),
    ("关闭换乘边", GOLD, ["只删该站换乘连接", "保留运行边与上下车", "不是删除整座车站"]),
]
for i, (title, color, lines) in enumerate(cards):
    x = 0.64 + i * 4.12
    rect(s, x, 2.03, 3.87, 2.15, CARD)
    textbox(s, x + 0.28, 2.28, 3.3, 0.38, title, 17, color, bold=True)
    textbox(s, x + 0.28, 2.82, 3.3, 1.2, "\n".join("· " + l for l in lines), 13, WHITE,
            spacing=5)

rect(s, 0.64, 4.42, 12.06, 0.88, CARD)
textbox(s, 0.95, 4.6, 3.4, 0.3, "代价模型（基准）", 15, TEAL, bold=True)
textbox(s, 4.3, 4.6, 8.1, 0.3,
        "代价 = 乘车区间数 + 换乘次数 × 2 站　　乘 1 站 = 1，换 1 次 = 2", 15, WHITE)

rect(s, 0.64, 5.46, 12.06, 0.88, CARD)
textbox(s, 0.95, 5.64, 3.4, 0.3, "起终点与等权", 15, TEAL, bold=True)
textbox(s, 4.3, 5.64, 8.1, 0.3,
        "195 座物理站两两组合 = 18 915 个 OD，每对等权一次，线路副本不重复计需求", 14, WHITE)

textbox(s, 0.64, 6.62, 12.0, 0.3,
        "注意：21 条换乘边均为待核验状态，基准情景视为可通行属明确假设。", 12, GOLD)

# ================================================================ 4 网络图
s = prs.slides.add_slide(BLANK)
chrome(s, 4, "MODEL VALIDATION", "主实验网络：与 A 项模型完全一致", FOOT)
add_image(s, "deck_network.png", 0.62, 1.95, h=4.5)
statcard(s, 8.35, 1.95, 2.15, 1.35, "195", "物理车站", TEAL)
statcard(s, 10.65, 1.95, 2.15, 1.35, "207", "区间运行边", TEAL)
statcard(s, 8.35, 3.45, 2.15, 1.35, "21", "候选换乘边", GOLD)
statcard(s, 10.65, 3.45, 2.15, 1.35, "19", "换乘站", GOLD)
rect(s, 8.35, 5.0, 4.45, 1.35, CARD)
textbox(s, 8.6, 5.18, 4.0, 0.3, "校验结果", 14, TEAL, bold=True)
textbox(s, 8.6, 5.55, 4.0, 0.7,
        "重建网络与 A 项 GraphML 在\n节点、边、属性、边类型上完全一致", 12, WHITE, spacing=4)

# ================================================================ 5 结构排名
s = prs.slides.add_slide(BLANK)
chrome(s, 5, "CENTRALITY", "基础排名：物理车站网络的介数中心性", FOOT)
add_image(s, "deck_centrality.png", 0.62, 1.92, w=8.35)
rect(s, 9.2, 1.92, 3.5, 4.3, CARD)
textbox(s, 9.48, 2.15, 3.0, 0.36, "前 5 名（金）", 15, GOLD, bold=True)
top5 = [
    ("洪岗", "3;6", "0.324"),
    ("合肥南站", "1;4;5", "0.314"),
    ("市第三医院", "5;6", "0.307"),
    ("东七里", "2;4", "0.264"),
    ("尧渡河路", "4;6", "0.261"),
]
for i, (n, l, v) in enumerate(top5):
    y = 2.62 + i * 0.62
    textbox(s, 9.48, y, 1.55, 0.32, n, 14, WHITE, bold=True)
    textbox(s, 11.05, y, 0.85, 0.32, l, 11, MUTED)
    textbox(s, 11.85, y, 0.75, 0.32, v, 13, TEAL, bold=True, align=PP_ALIGN.RIGHT)
textbox(s, 9.48, 5.72, 3.0, 0.4, "平均最短路 14.4 站\n直径 42 站", 11, MUTED, spacing=3)

# ================================================================ 6 逐站损失
s = prs.slides.add_slide(BLANK)
chrome(s, 6, "DISRUPTION RESULT", "逐站换乘中断：19 座站的出行损失", FOOT)
add_image(s, "deck_loss.png", 0.55, 1.9, w=10.4)
rect(s, 11.15, 1.9, 1.62, 4.5, CARD)
textbox(s, 11.32, 2.12, 1.3, 0.3, "前三名", 13, GOLD, bold=True)
textbox(s, 11.32, 2.55, 1.3, 0.3, "紫庐", 14, WHITE, bold=True)
textbox(s, 11.32, 2.92, 1.3, 0.3, "合肥南站", 14, WHITE, bold=True)
textbox(s, 11.32, 3.29, 1.3, 0.3, "繁华大道", 14, WHITE, bold=True)
textbox(s, 11.32, 3.95, 1.3, 0.3, "末位", 12, MUTED, bold=True)
textbox(s, 11.32, 4.32, 1.3, 0.3, "海棠", 13, MUTED)
textbox(s, 11.32, 5.05, 1.3, 1.2, "损失指数\n= 全OD平均增量\n÷ 基线平均", 10, MUTED, spacing=2)

# ================================================================ 7 不可达=0
s = prs.slides.add_slide(BLANK)
chrome(s, 7, "KEY FINDING", "重要发现：单站关闭不会造成不可达", FOOT)

rect(s, 0.64, 2.03, 6.0, 2.35, CARD)
textbox(s, 0.94, 2.28, 5.4, 0.7, "0 / 18915", 34, TEAL, bold=True)
textbox(s, 0.94, 3.05, 5.4, 0.35, "19 座换乘站逐一关闭后的不可达 OD", 14, WHITE)
textbox(s, 0.94, 3.55, 5.4, 0.55,
        "8 条线由 19 座换乘站互联，任一站关闭仍有替代路径", 12, MUTED)

rect(s, 6.85, 2.03, 5.8, 2.35, CARD)
textbox(s, 7.15, 2.28, 5.2, 0.38, "因此", 17, GOLD, bold=True)
textbox(s, 7.15, 2.78, 5.2, 1.35,
        "不可达比例在本数据上\n不构成区分指标；\n单站损失只能由绕行代价体现。",
        15, WHITE, spacing=4)

rect(s, 0.64, 4.62, 12.01, 1.75, CARD)
textbox(s, 0.94, 4.85, 2.6, 0.32, "对 C 项的提示", 15, GOLD, bold=True)
textbox(s, 0.94, 5.3, 11.4, 0.95,
        "要让「不可达」成为有效指标，需要同时关闭多座站（相同中断站数的随机／针对性对比），"
        "或引入 S1、站外换乘等情景——这正是第 3 周的内容。",
        14, WHITE, spacing=4)

textbox(s, 0.64, 6.58, 12.0, 0.3,
        "这是数据结构的客观结论，不美化、不掩盖。", 12, MUTED)

# ================================================================ 8 排名对照
s = prs.slides.add_slide(BLANK)
chrome(s, 8, "RANK COMPARISON", "结构排名 ≠ 出行损失排名（ρ = 0.461）", FOOT)
add_image(s, "deck_rank.png", 0.55, 1.85, h=4.55)

rect(s, 7.25, 1.85, 5.42, 1.2, CARD)
textbox(s, 7.5, 2.0, 1.6, 0.3, "Spearman ρ", 12, MUTED, bold=True)
textbox(s, 9.1, 1.95, 1.5, 0.5, "0.461", 26, TEAL, bold=True)
textbox(s, 10.55, 2.0, 2.0, 0.3, "前5重合 2 座", 12, MUTED)
textbox(s, 10.55, 2.35, 2.0, 0.3, "中等正相关", 12, GOLD, bold=True)

panels = [
    ("结构高、损失低", TEAL, "洪岗 1→9　市第三医院 3→12\n朱岗 6→17　尧渡河路 5→10"),
    ("结构低、损失高", GOLD, "紫庐 8→1　繁华大道 10→3\n西七里塘 9→4　云谷路 16→6"),
]
for i, (title, color, body) in enumerate(panels):
    y = 3.2 + i * 1.62
    rect(s, 7.25, y, 5.42, 1.45, CARD)
    textbox(s, 7.5, y + 0.16, 4.95, 0.32, title, 15, color, bold=True)
    textbox(s, 7.5, y + 0.6, 4.95, 0.75, body, 12.5, WHITE, spacing=2)

textbox(s, 0.62, 6.55, 12.0, 0.3,
        "格式：站点 结构排名→损失排名", 11, MUTED)

# ================================================================ 9 紫庐案例
s = prs.slides.add_slide(BLANK)
chrome(s, 9, "CASE STUDY", "代表案例：紫庐为何损失最大", FOOT)
add_image(s, "deck_case.png", 0.55, 1.92, w=9.3)

rect(s, 10.05, 1.88, 2.72, 1.32, CARD)
textbox(s, 10.28, 2.02, 2.3, 0.3, "结构排名", 11, MUTED, bold=True)
textbox(s, 10.28, 2.3, 2.3, 0.5, "第 8", 22, WHITE, bold=True)
rect(s, 10.05, 3.32, 2.72, 1.32, CARD)
textbox(s, 10.28, 3.46, 2.3, 0.3, "损失排名", 11, MUTED, bold=True)
textbox(s, 10.28, 3.74, 2.3, 0.5, "第 1", 22, GOLD, bold=True)

rect(s, 10.05, 4.78, 2.72, 1.6, CARD)
textbox(s, 10.25, 4.92, 2.35, 0.3, "原因", 11, MUTED, bold=True)
textbox(s, 10.25, 5.2, 2.35, 1.1,
        "1 号线与 7 号线\n唯一换乘点\n\n替代性极差", 11.5, WHITE, spacing=2)

textbox(s, 0.62, 6.55, 12.0, 0.3,
        "紫庐在外围，介数不高；但关闭后 1298 个 OD 需长距离绕行，平均 +9.6 等效站。", 12, GOLD)

# ================================================================ 10 对比
s = prs.slides.add_slide(BLANK)
chrome(s, 10, "WHY NOT HIGHEST", "为什么洪岗中心性第 1、损失却排第 9", FOOT)

rows = [
    ("", "洪岗 (3;6)", "紫庐 (1;7)", TEAL),
    ("结构排名（介数）", "第 1（0.324）", "第 8（0.185）", WHITE),
    ("基线换乘 OD", "1523", "1373", WHITE),
    ("受影响 OD", "1369", "1298", WHITE),
    ("平均绕行", "3.17 等效站", "9.60 等效站", GOLD),
    ("损失排名", "第 9", "第 1", GOLD),
]
y0, rh = 2.02, 0.7
for i, (label, a, b, color) in enumerate(rows):
    y = y0 + i * rh
    head = i == 0
    rect(s, 0.64, y, 12.01, rh - 0.08, CARD if not head else BG)
    if head:
        textbox(s, 0.94, y + 0.18, 3.6, 0.34, "对比项", 14, MUTED, bold=True)
        textbox(s, 4.9, y + 0.18, 3.4, 0.34, a, 15, TEAL, bold=True)
        textbox(s, 8.6, y + 0.18, 3.4, 0.34, b, 15, GOLD, bold=True)
    else:
        textbox(s, 0.94, y + 0.18, 3.6, 0.34, label, 14, MUTED)
        textbox(s, 4.9, y + 0.18, 3.4, 0.34, a, 14, color, bold=(color != WHITE))
        textbox(s, 8.6, y + 0.18, 3.4, 0.34, b, 14, color, bold=(color != WHITE))

rect(s, 0.64, 6.3, 12.01, 0.52, CARD)
textbox(s, 0.94, 6.44, 11.4, 0.3,
        "结论：中心性衡量「经过多少」，不衡量「替代方案多远」。", 14, GOLD, bold=True)
# ================================================================ 11 双维度
s = prs.slides.add_slide(BLANK)
chrome(s, 11, "TWO DIMENSIONS", "两个维度必须分开报告", FOOT)

rect(s, 0.64, 2.05, 5.9, 2.6, CARD)
textbox(s, 0.94, 2.28, 5.3, 0.36, "受影响 OD 数：谁牵扯面广", 16, BLUE, bold=True)
textbox(s, 0.94, 2.8, 5.3, 0.45, "合肥南站　3438 个", 20, WHITE, bold=True)
textbox(s, 0.94, 3.45, 5.3, 0.95,
        "三线换乘站，基线 3614 个 OD 在此换乘\n但替代入口多，单位绕行最小（+3.41）", 12.5, MUTED, spacing=3)

rect(s, 6.75, 2.05, 5.9, 2.6, CARD)
textbox(s, 7.05, 2.28, 5.3, 0.36, "单次绕行幅度：谁最难替代", 16, GOLD, bold=True)
textbox(s, 7.05, 2.8, 5.3, 0.45, "紫庐　+9.60 等效站", 20, WHITE, bold=True)
textbox(s, 7.05, 3.45, 5.3, 0.95,
        "只影响 1298 个 OD，数量不是最多\n但每个都绕得很远，难替代", 12.5, MUTED, spacing=3)

rect(s, 0.64, 4.95, 12.01, 1.05, CARD)
textbox(s, 0.94, 5.15, 11.4, 0.7,
        "只报一个排名会产生误读：合肥南站「影响最广」但不是「绕行最重」。",
        15, WHITE, bold=True)
textbox(s, 0.64, 6.3, 12.0, 0.3,
        "轨道运营里，这两件事对应不同的应对手段：疏导 vs. 绕行提示。", 12, GOLD)

# ================================================================ 12 敏感性
s = prs.slides.add_slide(BLANK)
chrome(s, 12, "SENSITIVITY", "参数敏感性：结论对换乘惩罚稳健", FOOT)
add_image(s, "deck_sens.png", 0.55, 1.9, w=8.6)

statcard(s, 9.4, 1.9, 1.55, 1.25, "0", "站 (stations)", TEAL, 26)
statcard(s, 11.1, 1.9, 1.55, 1.25, "1", "站 (×1)", BLUE, 26)
statcard(s, 9.4, 3.25, 1.55, 1.25, "2", "站 (基准)", GOLD, 26)

rect(s, 11.1, 3.25, 1.55, 1.25, CARD)
textbox(s, 11.25, 3.45, 1.3, 0.3, "前三名", 11, MUTED, bold=True)
textbox(s, 11.25, 3.78, 1.3, 0.55, "完全一致", 13, TEAL, bold=True)

rect(s, 9.4, 4.7, 3.25, 1.28, CARD)
textbox(s, 9.65, 4.85, 2.8, 0.3, "秩相关 ≥ 0.918", 13, WHITE, bold=True)
textbox(s, 9.65, 5.2, 2.8, 0.7,
        "×1 vs ×2：0.982\nstations vs ×1：0.940", 11, MUTED, spacing=2)

textbox(s, 0.62, 6.55, 12.0, 0.3,
        "但第 4 名及以后会轻度重排（如云谷路 4→6）；头部稳定、中后段敏感。", 12, GOLD)

# ================================================================ 13 局限
s = prs.slides.add_slide(BLANK)
chrome(s, 13, "LIMITS", "模型局限（必须说明）", FOOT)

limits = [
    ("等效站数 ≠ 分钟", "无可靠区间与换乘时间数据，不得称为真实出行时间"),
    ("换乘边为待核验", "21 条候选边视为可通行是假设，非已核实通道"),
    ("同名合并假设", "同名站合并等价于「同名即可换乘」，需显式声明"),
    ("无客流／容量", "OD 等权；影响对数 ≠ 受影响乘客数"),
    ("不含公交接驳", "仅研究地铁内部绕行"),
    ("布局图非地理", "网络图为拓扑示意，不反映真实距离"),
]
for i, (h, b) in enumerate(limits):
    col, row = i % 2, i // 2
    x = 0.64 + col * 6.1
    y = 2.05 + row * 1.32
    rect(s, x, y, 5.85, 1.15, CARD)
    rect(s, x + 0.22, y + 0.22, 0.075, 0.7, GOLD, shape=MSO_SHAPE.RECTANGLE)
    textbox(s, x + 0.42, y + 0.18, 5.2, 0.32, h, 14, WHITE, bold=True)
    textbox(s, x + 0.42, y + 0.58, 5.2, 0.5, b, 11.5, MUTED)

textbox(s, 0.64, 6.55, 12.0, 0.3,
        "所有结论均限定在上述口径内；不含任何编造的分钟数。", 12, GOLD)

# ================================================================ 14 文献来源
s = prs.slides.add_slide(BLANK)
chrome(s, 14, "REFERENCES", "文献与数据来源", FOOT)

textbox(s, 0.64, 1.98, 5.9, 0.34, "数据来源", 15, TEAL, bold=True)
data_src = [
    ("合肥 1—8 号线线网", "高德地图—合肥地铁线路查询\nm.amap.com/service/subway/hefei-3401/"),
    ("S1 线试乘资料", "合肥轨道交通，2026-11-11\napi.app.anhuinews.com/appcontent/9739180.html"),
    ("换乘通道方式（历史）", "合肥市人民政府发布，2023-04-07\nhefei.gov.cn/public/1741/108752894.html"),
]
for i, (k, v) in enumerate(data_src):
    y = 2.4 + i * 1.12
    rect(s, 0.64, y, 5.9, 0.98, CARD)
    textbox(s, 0.88, y + 0.13, 5.4, 0.28, k, 12.5, WHITE, bold=True)
    textbox(s, 0.88, y + 0.46, 5.4, 0.46, v, 9.5, MUTED, spacing=1)

textbox(s, 6.86, 1.98, 5.8, 0.34, "方法参考文献（借思路，非原创算法）", 15, GOLD, bold=True)
refs = [
    ("[1] 杜斐等, 2016", "武汉大学学报(工学版) 49(5):701-707", "网络效率、针对性故障对照"),
    ("[2] Wu 等, 2018", "Physica A 492:553-563", "换乘偏好引入路径距离"),
    ("[3] Kopsidas 等, 2022", "Physica A 596:127123", "关键性取决于替代性（核心依据）"),
    ("[4] Kopsidas 等, 2023", "Applied Network Science", "仅理解中心性与客流之别"),
]
for i, (k, v, note) in enumerate(refs):
    y = 2.4 + i * 0.84
    rect(s, 6.86, y, 5.8, 0.72, CARD)
    textbox(s, 7.08, y + 0.08, 2.3, 0.28, k, 11.5, WHITE, bold=True)
    textbox(s, 9.35, y + 0.09, 3.2, 0.26, v, 9, MUTED)
    textbox(s, 7.08, y + 0.4, 5.4, 0.26, note, 9.5, TEAL)

rect(s, 0.64, 6.42, 12.01, 0.52, CARD)
textbox(s, 0.94, 6.56, 11.5, 0.3,
        "完整清单含 DOI 与链接见 B项参考文献与数据来源.md；本仓库不含任何文献全文。",
        11.5, GOLD, bold=True)

# ================================================================ 15 交接
s = prs.slides.add_slide(BLANK)
chrome(s, 15, "HANDOFF", "B 项成果交接与 C 项建议", FOOT)

items = [
    ("基础排名", TEAL, "B01 全站排名 · B02 换乘站排名 · B03 网络指标"),
    ("逐站损失表", GOLD, "B04 单站中断 19 站 · B06 基线 OD 明细"),
    ("路径评价代码", TEAL, "routing.py 统一代价与不可达／绕行分列"),
    ("参数与种子", TEAL, "B07 敏感性 · B09 参数、种子、数据版本"),
]
for i, (k, color, v) in enumerate(items):
    y = 2.05 + i * 0.86
    rect(s, 0.68, y, 12.0, 0.72, CARD)
    textbox(s, 1.0, y + 0.19, 1.75, 0.34, k, 15, color, bold=True)
    textbox(s, 3.05, y + 0.2, 9.4, 0.34, v, 13, WHITE)

rect(s, 0.68, 5.62, 12.0, 1.28, CARD)
textbox(s, 0.98, 5.78, 2.6, 0.3, "给 C 项的三件事", 14, GOLD, bold=True)
textbox(s, 0.98, 6.16, 11.3, 0.7,
        "① 多站同时中断，让不可达指标生效　② 随机 vs 针对性（种子 20261116，重复≥100）"
        "　③ 换乘惩罚扩到 3—5 站", 13, WHITE)

# ================================================================ 15 总结
s = prs.slides.add_slide(BLANK)
set_bg(s)
rect(s, 0, 0, 0.13, 7.5, TEAL, shape=MSO_SHAPE.RECTANGLE)
rect(s, 0.85, 1.04, 1.55, 0.35, CARD)
textbox(s, 0.94, 1.1, 1.4, 0.21, "B 项小结", 10, TEAL, bold=True)
textbox(s, 0.85, 1.91, 11.6, 1.35,
        "中心性高的换乘站，\n并不必然是出行损失最大的站。", 30, WHITE, bold=True)
rect(s, 0.86, 3.5, 2.0, 0.035, TEAL, shape=MSO_SHAPE.RECTANGLE)

points = [
    ("结论", "ρ = 0.461，前 5 重合 2 座；存在双向错位", GOLD),
    ("机制", "中心性衡量经过量，损失衡量替代方案代价", TEAL),
    ("稳健", "换乘惩罚 0—2 站，前三名完全一致", TEAL),
    ("边界", "单站中断无不可达；需多站情景验证", GOLD),
]
for i, (k, v, color) in enumerate(points):
    y = 3.85 + i * 0.62
    textbox(s, 0.86, y, 1.0, 0.32, k, 14, color, bold=True)
    textbox(s, 2.0, y, 7.9, 0.32, v, 14, WHITE)

# 右侧三个关键数字，填补空白并强化记忆点
stat_values = [
    ("0.461", "结构 vs 损失 秩相关", TEAL),
    ("第8→第1", "紫庐：结构到损失", GOLD),
    ("2/5", "前五名重合", TEAL),
]
for i, (val, lab, color) in enumerate(stat_values):
    y = 3.05 + i * 0.86
    rect(s, 10.35, y, 2.4, 0.72, CARD)
    textbox(s, 10.55, y + 0.1, 2.0, 0.34, val, 16, color, bold=True)
    textbox(s, 10.55, y + 0.44, 2.0, 0.24, lab, 9, MUTED)

textbox(s, 0.85, 6.55, 11.6, 0.34,
        "数据版本 2026-11｜参数与种子见 B09_run_parameters.json", 11, MUTED)

OUT.parent.mkdir(parents=True, exist_ok=True)
prs.save(OUT)
print("saved:", OUT)
print("slides:", len(prs.slides.__iter__.__self__._sldIdLst))
