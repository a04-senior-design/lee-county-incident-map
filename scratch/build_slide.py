from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN

NAVY   = RGBColor(0x1E, 0x3A, 0x5F)
BLUE   = RGBColor(0x25, 0x63, 0xEB)
GREY   = RGBColor(0x44, 0x44, 0x44)
LIGHT  = RGBColor(0xF0, 0xF4, 0xF8)

prs = Presentation()
prs.slide_width  = Inches(13.333)
prs.slide_height = Inches(7.5)

slide = prs.slides.add_slide(prs.slide_layouts[6])  # blank layout

# ── Title ─────────────────────────────────────────────────────────────────
title_box = slide.shapes.add_textbox(Inches(0.4), Inches(0.25), Inches(12.5), Inches(0.7))
tf = title_box.text_frame
tf.text = "Registered User Reports — PDF Generation Design"
p = tf.paragraphs[0]
p.font.size = Pt(28)
p.font.bold = True
p.font.color.rgb = NAVY

subtitle_box = slide.shapes.add_textbox(Inches(0.4), Inches(0.85), Inches(12.5), Inches(0.4))
tf2 = subtitle_box.text_frame
tf2.text = "Server-side rendering pipeline: ReportLab + Matplotlib + staticmap"
p2 = tf2.paragraphs[0]
p2.font.size = Pt(15)
p2.font.italic = True
p2.font.color.rgb = GREY

# ── Bullet points (design decisions) ────────────────────────────────────────
bullets_box = slide.shapes.add_textbox(Inches(0.4), Inches(1.45), Inches(6.5), Inches(5.6))
btf = bullets_box.text_frame
btf.word_wrap = True

bullet_data = [
    ("ReportLab (Platypus) over WeasyPrint",
     "Assembles Paragraphs, Tables, and Images programmatically from in-memory "
     "BytesIO buffers — no HTML/CSS templating step and no Pango system "
     "dependency to embed dynamic charts."),
    ("staticmap over leaflet-image / html2canvas / dom-to-image",
     "Browser-side DOM/canvas capture hits the tainted-canvas limitation: OSM "
     "tiles don't send Access-Control-Allow-Origin, so cross-origin tile pixels "
     "can't be read client-side."),
    ("staticmap over Puppeteer",
     "A headless-Chromium screenshot server sidesteps CORS too, but adds heavy "
     "memory/startup cost and a system dependency that doesn't fit a lightweight "
     "Flask deployment."),
    ("Matplotlib with the Agg backend",
     "Renders bar/line charts headlessly straight into BytesIO PNG buffers — "
     "no display server, no temp files."),
    ("Fully in-memory request pipeline",
     "Map snapshot, charts, and final PDF are generated and streamed back within "
     "a single Flask request/response — no external processes."),
]

first = True
for heading, detail in bullet_data:
    p = btf.paragraphs[0] if first else btf.add_paragraph()
    first = False
    p.text = f"{heading}"
    p.font.size = Pt(15)
    p.font.bold = True
    p.font.color.rgb = NAVY
    p.space_after = Pt(2)

    d = btf.add_paragraph()
    d.text = detail
    d.font.size = Pt(12.5)
    d.font.color.rgb = GREY
    d.space_after = Pt(12)
    d.level = 1

# ── Chart figures ────────────────────────────────────────────────────────────
fig_caption = slide.shapes.add_textbox(Inches(7.2), Inches(1.45), Inches(5.7), Inches(0.35))
fc = fig_caption.text_frame
fc.text = "Example charts from a generated report"
fc.paragraphs[0].font.size = Pt(13)
fc.paragraphs[0].font.bold = True
fc.paragraphs[0].font.color.rgb = NAVY

slide.shapes.add_picture(
    "bar_chart.png", Inches(7.2), Inches(1.85), width=Inches(5.7)
)
slide.shapes.add_picture(
    "line_chart.png", Inches(7.2), Inches(4.55), width=Inches(5.7)
)

# footer note on chart provenance
note_box = slide.shapes.add_textbox(Inches(7.2), Inches(7.0), Inches(5.7), Inches(0.4))
nf = note_box.text_frame
nf.text = "Rendered with the project's own _bar_chart() / _line_chart() functions on sample data"
nf.paragraphs[0].font.size = Pt(9)
nf.paragraphs[0].font.italic = True
nf.paragraphs[0].font.color.rgb = GREY

prs.save("report_design_slide.pptx")
print("saved")
