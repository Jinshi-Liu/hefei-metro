"""导出与 Beamer 逐页一致的 16:9 放映文件；可编辑母稿为 main.tex。"""
import argparse
import io
import re
from pathlib import Path

import pymupdf
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.oxml.xmlchemy import OxmlElement
from pptx.util import Inches

HERE = Path(__file__).resolve().parent
NAME = "合肥地铁换乘可达性_答辩"


def export(pdf, output):
    source = (HERE / "main.tex").read_text(encoding="utf-8")
    # Each frame has one plain-text speaker note (no TeX commands or nested braces).
    notes = re.findall(r"\\note\{([^{}]+)\}", source, flags=re.S)
    deck = Presentation()
    deck.slide_width, deck.slide_height = Inches(40/3), Inches(7.5)
    deck.core_properties.title = "合肥轨道交通的换乘可达性"
    deck.core_properties.subject = "复杂系统分析课程项目"
    deck.core_properties.author = "中国科学技术大学 · 课程项目组"
    with pymupdf.open(pdf) as pages:
        if len(pages) != len(notes):
            raise ValueError(f"{len(pages)} PDF pages, but {len(notes)} notes. Recompile main.tex.")
        for n, (page, note) in enumerate(zip(pages, notes), 1):
            slide = deck.slides.add_slide(deck.slide_layouts[6])
            scale = 2240 / page.rect.width
            pix = page.get_pixmap(matrix=pymupdf.Matrix(scale, scale), alpha=False)
            picture = slide.shapes.add_picture(io.BytesIO(pix.tobytes("png")), 0, 0,
                                               width=deck.slide_width, height=deck.slide_height)
            contents = page.get_text().strip()
            picture._element.nvPicPr.cNvPr.set("descr", contents)
            slide._element.cSld.set("name", deck.core_properties.title if n == 1 else contents.splitlines()[1])
            # Keep the bibliography / data-source links active in the projection copy.
            for link in page.get_links():
                uri = link.get("uri", "")
                if not uri.startswith(("https://", "http://")):
                    continue
                box = link["from"] & page.rect
                sx, sy = deck.slide_width / page.rect.width, deck.slide_height / page.rect.height
                hit = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, int(box.x0*sx), int(box.y0*sy),
                                             int(box.width*sx), int(box.height*sy))
                hit.fill.solid()
                hit.fill.fore_color.rgb = RGBColor(255, 255, 255)
                alpha = OxmlElement("a:alpha")
                alpha.set("val", "0")
                hit._element.spPr.solidFill.srgbClr.append(alpha)
                hit.line.fill.background()
                hit.click_action.hyperlink.address = uri
            slide.notes_slide.notes_text_frame.text = note.strip()
    deck.save(output)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdf", nargs="?", type=Path, default=HERE / "main.pdf")
    parser.add_argument("-o", "--output", type=Path, default=HERE / (NAME+".pptx"))
    args = parser.parse_args()
    export(args.pdf, args.output)
