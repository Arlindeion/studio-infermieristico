"""Generate the public, non-personalized copy of the sleep-consultation terms."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.colors import HexColor
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    HRFlowable,
    KeepTogether,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sleep_terms import (  # noqa: E402
    SLEEP_TERMS_SECTIONS,
    SLEEP_TERMS_UPDATED_LABEL,
    SLEEP_TERMS_VERSION,
)


OUTPUT = ROOT / "output" / "pdf" / f"condizioni_contrattuali_consulenza_sonno_{SLEEP_TERMS_VERSION}.pdf"
LOGO = ROOT / "static" / "img" / "logo.png"

PAPER = HexColor("#F7F5F1")
SAGE = HexColor("#B1BBA5")
MIST = HexColor("#E5E9E0")
ACTION = HexColor("#506A59")
INK = HexColor("#304438")
DEEP = HexColor("#3F5948")
RED = HexColor("#9A4E56")
MUTED = HexColor("#58635C")
WHITE = colors.white

BODY_FONT = "Helvetica"
BODY_BOLD = "Helvetica-Bold"
DISPLAY_FONT = "Helvetica-Bold"

PUBLIC_TERMS_URL = "https://scstudioinfermieristico.it/condizioni-consulenza-sonno"
PRIVACY_URL = "https://scstudioinfermieristico.it/privacy"
PHONE_URL = "tel:+393806317175"
EMAIL_URL = "mailto:info@scstudioinfermieristico.it"


def _sanitize(text: str) -> str:
    return (
        text.replace("\u2011", "-")
        .replace("\u2013", "-")
        .replace("\u2014", "-")
    )


def _register_optional_brand_fonts() -> None:
    """Use brand TTFs when supplied; keep a dependency-free fallback."""
    global BODY_FONT, BODY_BOLD, DISPLAY_FONT
    font_dir_value = os.environ.get("STUDIO_PDF_FONT_DIR", "").strip()
    if not font_dir_value:
        return
    font_dir = Path(font_dir_value).expanduser()
    paths = {
        "Atkinson": font_dir / "AtkinsonHyperlegible-Regular.ttf",
        "Atkinson-Bold": font_dir / "AtkinsonHyperlegible-Bold.ttf",
        "Bricolage-Bold": font_dir / "BricolageGrotesque-Bold.ttf",
    }
    if not all(path.is_file() for path in paths.values()):
        missing = ", ".join(str(path) for path in paths.values() if not path.is_file())
        raise FileNotFoundError(f"Brand font files not found: {missing}")
    for name, path in paths.items():
        pdfmetrics.registerFont(TTFont(name, str(path)))
    BODY_FONT = "Atkinson"
    BODY_BOLD = "Atkinson-Bold"
    DISPLAY_FONT = "Bricolage-Bold"


def _styles():
    base = getSampleStyleSheet()
    return {
        "cover_eyebrow": ParagraphStyle(
            "CoverEyebrow",
            parent=base["Normal"],
            fontName=BODY_BOLD,
            fontSize=8.5,
            leading=10,
            textColor=RED,
            spaceAfter=4 * mm,
            uppercase=True,
        ),
        "cover_title": ParagraphStyle(
            "CoverTitle",
            parent=base["Title"],
            fontName=DISPLAY_FONT,
            fontSize=29,
            leading=31,
            textColor=INK,
            alignment=TA_LEFT,
            spaceAfter=5 * mm,
        ),
        "cover_subtitle": ParagraphStyle(
            "CoverSubtitle",
            parent=base["Normal"],
            fontName=BODY_FONT,
            fontSize=11,
            leading=15,
            textColor=MUTED,
            spaceAfter=6 * mm,
        ),
        "cover_meta": ParagraphStyle(
            "CoverMeta",
            parent=base["Normal"],
            fontName=BODY_FONT,
            fontSize=9,
            leading=12,
            textColor=INK,
        ),
        "intro_title": ParagraphStyle(
            "IntroTitle",
            parent=base["Heading2"],
            fontName=DISPLAY_FONT,
            fontSize=15,
            leading=18,
            textColor=INK,
            spaceAfter=2.5 * mm,
        ),
        "body": ParagraphStyle(
            "Body",
            parent=base["BodyText"],
            fontName=BODY_FONT,
            fontSize=9.5,
            leading=13.2,
            textColor=INK,
            spaceAfter=2.8 * mm,
            splitLongWords=False,
        ),
        "body_bold": ParagraphStyle(
            "BodyBold",
            parent=base["BodyText"],
            fontName=BODY_BOLD,
            fontSize=9.5,
            leading=13.2,
            textColor=INK,
            spaceAfter=2.8 * mm,
        ),
        "section": ParagraphStyle(
            "Section",
            parent=base["Heading2"],
            fontName=DISPLAY_FONT,
            fontSize=14.5,
            leading=17,
            textColor=INK,
            keepWithNext=True,
            spaceBefore=4.5 * mm,
            spaceAfter=1.8 * mm,
        ),
        "bullet": ParagraphStyle(
            "Bullet",
            parent=base["BodyText"],
            fontName=BODY_FONT,
            fontSize=9.2,
            leading=12.7,
            textColor=INK,
            leftIndent=0,
            spaceAfter=1.8 * mm,
        ),
        "bullet_mark": ParagraphStyle(
            "BulletMark",
            parent=base["Normal"],
            fontName=BODY_BOLD,
            fontSize=10,
            leading=12.7,
            textColor=RED,
            alignment=TA_CENTER,
        ),
        "index": ParagraphStyle(
            "Index",
            parent=base["Normal"],
            fontName=BODY_FONT,
            fontSize=7.25,
            leading=9,
            textColor=INK,
        ),
        "small": ParagraphStyle(
            "Small",
            parent=base["Normal"],
            fontName=BODY_FONT,
            fontSize=7.6,
            leading=10,
            textColor=MUTED,
        ),
        "contact": ParagraphStyle(
            "Contact",
            parent=base["Normal"],
            fontName=BODY_FONT,
            fontSize=8.5,
            leading=12,
            textColor=INK,
            alignment=TA_CENTER,
        ),
    }


def _draw_brand_mark(canvas, x, y, size):
    canvas.setFillColor(DEEP)
    canvas.roundRect(x, y, size, size, 4 * mm, fill=1, stroke=0)
    canvas.drawImage(
        str(LOGO),
        x + size * 0.19,
        y + size * 0.19,
        size * 0.62,
        size * 0.62,
        mask="auto",
        preserveAspectRatio=True,
    )


def _draw_cover(canvas, doc):
    width, height = A4
    canvas.saveState()
    canvas.setFillColor(PAPER)
    canvas.rect(0, 0, width, height, fill=1, stroke=0)
    canvas.setFillColor(SAGE)
    canvas.rect(0, height - 36 * mm, width, 36 * mm, fill=1, stroke=0)
    _draw_brand_mark(canvas, 18 * mm, height - 30 * mm, 22 * mm)
    canvas.setFillColor(INK)
    canvas.setFont(DISPLAY_FONT, 13)
    canvas.drawString(47 * mm, height - 17 * mm, "S.C. Studio Infermieristico")
    canvas.setFont(BODY_FONT, 9)
    canvas.drawString(47 * mm, height - 23 * mm, "Selene Campetta")
    canvas.setStrokeColor(RED)
    canvas.setLineWidth(2)
    canvas.line(width - 50 * mm, height - 36 * mm, width - 18 * mm, height - 36 * mm)
    _draw_footer(canvas, doc, cover=True)
    canvas.restoreState()


def _draw_content_page(canvas, doc):
    width, height = A4
    canvas.saveState()
    canvas.setFillColor(PAPER)
    canvas.rect(0, 0, width, height, fill=1, stroke=0)
    canvas.setFillColor(SAGE)
    canvas.rect(0, height - 20 * mm, width, 20 * mm, fill=1, stroke=0)
    _draw_brand_mark(canvas, 18 * mm, height - 16 * mm, 11 * mm)
    canvas.setFillColor(INK)
    canvas.setFont(DISPLAY_FONT, 9.5)
    canvas.drawString(34 * mm, height - 10.8 * mm, "Condizioni della consulenza sonno")
    canvas.setStrokeColor(RED)
    canvas.setLineWidth(1.5)
    canvas.line(width - 42 * mm, height - 20 * mm, width - 18 * mm, height - 20 * mm)
    _draw_footer(canvas, doc, cover=False)
    canvas.restoreState()


def _draw_page(canvas, doc):
    if doc.page == 1:
        _draw_cover(canvas, doc)
    else:
        _draw_content_page(canvas, doc)


def _draw_footer(canvas, doc, cover=False):
    width, _ = A4
    canvas.setStrokeColor(MIST)
    canvas.setLineWidth(0.7)
    canvas.line(18 * mm, 15 * mm, width - 18 * mm, 15 * mm)
    canvas.setFillColor(MUTED)
    canvas.setFont(BODY_FONT, 7)
    canvas.drawString(18 * mm, 10.5 * mm, f"Versione {SLEEP_TERMS_VERSION}")
    if not cover:
        canvas.drawCentredString(width / 2, 10.5 * mm, "S.C. Studio Infermieristico")
    canvas.drawRightString(width - 18 * mm, 10.5 * mm, f"Pagina {doc.page}")


def _cover_story(styles):
    story = [Spacer(1, 14 * mm)]
    story.append(Paragraph("DOCUMENTO CONTRATTUALE VERSIONATO", styles["cover_eyebrow"]))
    story.append(Paragraph("Condizioni della<br/>consulenza sonno", styles["cover_title"]))
    story.append(
        Paragraph(
            "Condizioni applicabili alla consulenza mirata e ai percorsi sul sonno infantile.",
            styles["cover_subtitle"],
        )
    )

    version_table = Table(
        [
            [Paragraph("Versione", styles["cover_meta"]), Paragraph(SLEEP_TERMS_VERSION, styles["body_bold"])],
            [Paragraph("Ultimo aggiornamento", styles["cover_meta"]), Paragraph(SLEEP_TERMS_UPDATED_LABEL, styles["body_bold"])],
            [Paragraph("Titolare del servizio", styles["cover_meta"]), Paragraph("S.C. Studio Infermieristico - Selene Campetta", styles["body_bold"])],
        ],
        colWidths=[48 * mm, 105 * mm],
        hAlign="LEFT",
    )
    version_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), MIST),
                ("TEXTCOLOR", (0, 0), (-1, -1), INK),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LINEBELOW", (0, 0), (-1, -2), 0.5, SAGE),
                ("BOX", (0, 0), (-1, -1), 0.7, SAGE),
                ("LEFTPADDING", (0, 0), (-1, -1), 9),
                ("RIGHTPADDING", (0, 0), (-1, -1), 9),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ]
        )
    )
    story.extend([version_table, Spacer(1, 6 * mm)])

    story.append(Paragraph("Come usare questo documento", styles["intro_title"]))
    story.append(
        Paragraph(
            "Questa è la copia generale delle condizioni. La proposta privata e la conferma via email "
            "riportano la formula scelta, il prezzo, il metodo di pagamento, la versione accettata e la "
            "scelta relativa all'avvio prima dei 14 giorni.",
            styles["body"],
        )
    )
    story.append(
        Paragraph(
            "Il contratto si perfeziona quando S.C. Studio Infermieristico ha formulato la proposta e il "
            "pagamento risulta confermato, secondo quanto specificato nelle sezioni seguenti.",
            styles["body"],
        )
    )

    index_cells = []
    titles = [_sanitize(section["title"]) for section in SLEEP_TERMS_SECTIONS]
    for row in range(8):
        index_cells.append(
            [
                Paragraph(titles[row], styles["index"]),
                Paragraph(titles[row + 8], styles["index"]),
            ]
        )
    index_table = Table(index_cells, colWidths=[76.5 * mm, 76.5 * mm], hAlign="LEFT")
    index_table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 7),
                ("RIGHTPADDING", (0, 0), (-1, -1), 7),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("LINEBELOW", (0, 0), (-1, -2), 0.35, MIST),
                ("BOX", (0, 0), (-1, -1), 0.7, SAGE),
            ]
        )
    )
    story.extend([Spacer(1, 3 * mm), Paragraph("Indice", styles["intro_title"]), index_table])

    contact = Paragraph(
        "<b>S.C. Studio Infermieristico</b> · Selene Campetta · P. IVA 02439230687<br/>"
        "Via C. D'Agnese 43, 65015 Montesilvano (PE) · "
        f"<link href='{PHONE_URL}' color='#304438'>380 631 7175</link> · "
        f"<link href='{EMAIL_URL}' color='#304438'>info@scstudioinfermieristico.it</link>",
        styles["contact"],
    )
    story.extend([Spacer(1, 6 * mm), contact, PageBreak()])
    return story


def _section_story(styles):
    story = []
    intro = (
        "Le presenti condizioni disciplinano la prenotazione, il pagamento e lo svolgimento dei "
        "servizi di consulenza sul sonno proposti da S.C. Studio Infermieristico."
    )
    story.append(Paragraph(intro, styles["body_bold"]))
    story.append(Spacer(1, 2 * mm))

    for section in SLEEP_TERMS_SECTIONS:
        paragraphs = [_sanitize(text) for text in section.get("paragraphs", [])]
        heading_group = [
            Paragraph(_sanitize(section["title"]), styles["section"]),
            HRFlowable(width="18%", thickness=1.8, color=RED, spaceAfter=3 * mm, hAlign="LEFT"),
        ]
        if paragraphs:
            heading_group.append(Paragraph(paragraphs[0], styles["body"]))
            paragraphs = paragraphs[1:]
        story.append(KeepTogether(heading_group))
        story.extend(Paragraph(text, styles["body"]) for text in paragraphs)

        items = section.get("items", [])
        if items:
            bullet_table = Table(
                [
                    [
                        Paragraph("•", styles["bullet_mark"]),
                        Paragraph(_sanitize(item), styles["bullet"]),
                    ]
                    for item in items
                ],
                colWidths=[6 * mm, 147 * mm],
                hAlign="LEFT",
            )
            bullet_table.setStyle(
                TableStyle(
                    [
                        ("VALIGN", (0, 0), (-1, -1), "TOP"),
                        ("LEFTPADDING", (0, 0), (-1, -1), 0),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                        ("TOPPADDING", (0, 0), (-1, -1), 0),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 1.8 * mm),
                    ]
                )
            )
            story.append(bullet_table)
            story.append(Spacer(1, 0.4 * mm))
        story.extend(
            Paragraph(_sanitize(text), styles["body"])
            for text in section.get("paragraphs_after", [])
        )
        story.append(Spacer(1, 1.5 * mm))

    story.append(Spacer(1, 4 * mm))
    story.append(HRFlowable(width="100%", thickness=0.7, color=SAGE, spaceAfter=4 * mm))
    story.append(Paragraph("Riferimenti", styles["intro_title"]))
    story.append(
        Paragraph(
            "Il testo pubblico aggiornato è disponibile nella pagina "
            f"<link href='{PUBLIC_TERMS_URL}' color='#9A4E56'>Condizioni della consulenza sonno</link>. "
            "Il trattamento dei dati personali è descritto nella "
            f"<link href='{PRIVACY_URL}' color='#9A4E56'>Privacy Policy</link>.",
            styles["body"],
        )
    )
    story.append(
        Paragraph(
            "Per comunicazioni relative al contratto: "
            f"<link href='{EMAIL_URL}' color='#9A4E56'>info@scstudioinfermieristico.it</link> · "
            f"<link href='{PHONE_URL}' color='#9A4E56'>380 631 7175</link>.",
            styles["body"],
        )
    )
    return story


def build():
    _register_optional_brand_fonts()
    styles = _styles()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)

    doc = BaseDocTemplate(
        str(OUTPUT),
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=27 * mm,
        bottomMargin=21 * mm,
        title="Condizioni contrattuali della consulenza sonno",
        author="S.C. Studio Infermieristico - Selene Campetta",
        subject=f"Condizioni versione {SLEEP_TERMS_VERSION}, diritto di recesso e svolgimento del servizio",
        creator="S.C. Studio Infermieristico",
    )
    frame = Frame(
        doc.leftMargin,
        doc.bottomMargin,
        doc.width,
        doc.height,
        id="main-frame",
        leftPadding=0,
        rightPadding=0,
        topPadding=0,
        bottomPadding=0,
    )
    doc.addPageTemplates([PageTemplate(id="all-pages", frames=[frame], onPage=_draw_page)])
    story = _cover_story(styles) + _section_story(styles)
    doc.build(story)
    print(OUTPUT)


if __name__ == "__main__":
    build()
