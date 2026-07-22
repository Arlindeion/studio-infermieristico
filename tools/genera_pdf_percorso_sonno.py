from io import BytesIO
from pathlib import Path
from urllib.parse import quote

from PIL import Image
from reportlab.lib.colors import HexColor, white
from reportlab.lib.pagesizes import portrait
from reportlab.lib.utils import ImageReader
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "output" / "pdf" / "percorso_sonno_pilota.pdf"
PHOTO = ROOT / "static" / "img" / "selene-hero-home.jpg"
PHOTO_PROFILE = ROOT / "static" / "img" / "selene-chi-sono.jpg"
LOGO_WHITE = ROOT / "static" / "img" / "logo.png"
LOGO_BLACK = ROOT / "static" / "img" / "logo_black.png"

PAGE = portrait((108 * mm, 192 * mm))
W, H = PAGE

PAPER = HexColor("#F5F2E9")
DEEP_GREEN = HexColor("#21483E")
SAGE = HexColor("#93A88F")
MIST = HexColor("#DCE5DC")
INK = HexColor("#18312B")
MUTED = HexColor("#586963")
HEART_RED = HexColor("#C7473F")
SOFT_RED = HexColor("#F2DDDA")

WHATSAPP_TEXT = (
    "Buongiorno Selene, ho ricevuto l'anteprima del percorso sonno "
    "e vorrei richiedere la chiamata conoscitiva gratuita."
)
WHATSAPP_URL = f"https://wa.me/393806317175?text={quote(WHATSAPP_TEXT)}"


def register_fonts():
    pdfmetrics.registerFont(TTFont("NewYork", "/System/Library/Fonts/NewYork.ttf"))
    pdfmetrics.registerFont(
        TTFont("GeorgiaItalic", "/System/Library/Fonts/Supplemental/Georgia Italic.ttf")
    )


def fit_crop(path, width_px, height_px, focus=(0.5, 0.5)):
    image = Image.open(path).convert("RGB")
    target_ratio = width_px / height_px
    source_ratio = image.width / image.height
    if source_ratio > target_ratio:
        crop_width = int(image.height * target_ratio)
        available = image.width - crop_width
        left = int(available * focus[0])
        image = image.crop((left, 0, left + crop_width, image.height))
    else:
        crop_height = int(image.width / target_ratio)
        available = image.height - crop_height
        top = int(available * focus[1])
        image = image.crop((0, top, image.width, top + crop_height))
    image = image.resize((width_px, height_px), Image.Resampling.LANCZOS)
    buffer = BytesIO()
    image.save(buffer, format="JPEG", quality=93, optimize=True)
    buffer.seek(0)
    return ImageReader(buffer)


def wrap_text(text, font, size, max_width):
    words = text.split()
    lines = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if pdfmetrics.stringWidth(candidate, font, size) <= max_width:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def draw_wrapped(c, text, x, y, max_width, font="Helvetica", size=10, leading=14,
                 color=INK, max_lines=None):
    lines = wrap_text(text, font, size, max_width)
    if max_lines:
        lines = lines[:max_lines]
    c.setFont(font, size)
    c.setFillColor(color)
    for line in lines:
        c.drawString(x, y, line)
        y -= leading
    return y


def pill(c, text, x, y, width, fill, text_color, font_size=7.2):
    c.setFillColor(fill)
    c.roundRect(x, y, width, 18, 9, fill=1, stroke=0)
    c.setFillColor(text_color)
    c.setFont("Helvetica-Bold", font_size)
    c.drawCentredString(x + width / 2, y + 6, text.upper())


def draw_thread(c, x, y_top, y_bottom, color=HEART_RED):
    path = c.beginPath()
    path.moveTo(x, y_top)
    path.curveTo(x - 20, y_top - 28, x + 28, y_top - 52, x + 4, y_top - 84)
    path.curveTo(x - 16, y_top - 112, x + 15, y_bottom + 26, x, y_bottom)
    c.setStrokeColor(color)
    c.setLineWidth(1.8)
    c.setLineCap(1)
    c.drawPath(path, stroke=1, fill=0)


def draw_button(c, x, y, width, label, href):
    height = 31
    c.setFillColor(HEART_RED)
    c.roundRect(x, y, width, height, 15.5, fill=1, stroke=0)
    c.setFillColor(white)
    c.setFont("Helvetica-Bold", 9.6)
    c.drawCentredString(x + width / 2, y + 10.4, label)
    c.linkURL(href, (x, y, x + width, y + height), relative=0, thickness=0)


def draw_bullet(c, x, y, text, max_width, color=INK, size=8.9, leading=12.2):
    c.setFillColor(HEART_RED)
    c.circle(x + 2.7, y + 3.7, 2.1, fill=1, stroke=0)
    return draw_wrapped(c, text, x + 11, y, max_width - 11, size=size,
                        leading=leading, color=color) - 2


def page_one(c):
    c.setFillColor(DEEP_GREEN)
    c.rect(0, 0, W, H, fill=1, stroke=0)

    photo_height = 185
    photo = fit_crop(PHOTO, 1200, 720, focus=(0.47, 0.35))
    c.drawImage(photo, 0, H - photo_height, W, photo_height, mask="auto")

    c.setFillColor(DEEP_GREEN)
    c.setFillAlpha(0.92)
    c.rect(0, H - 34, W, 34, fill=1, stroke=0)
    c.setFillAlpha(1)
    c.drawImage(str(LOGO_WHITE), 15, H - 31, 22, 22, mask="auto", preserveAspectRatio=True)
    c.setFillColor(white)
    c.setFont("Helvetica-Bold", 8.2)
    c.drawString(42, H - 22, "S.C. STUDIO INFERMIERISTICO")

    pill(c, "Percorso personalizzato", 18, H - photo_height - 27, 125, HEART_RED, white)
    pill(c, "0-12 mesi · online", W - 130, H - photo_height - 27, 112, MIST, DEEP_GREEN)

    x = 18
    y = H - photo_height - 54
    c.setFillColor(white)
    c.setFont("NewYork", 27)
    for line in ["Quando il sonno", "diventa difficile", "da leggere."]:
        c.drawString(x, y, line)
        y -= 29

    y -= 2
    y = draw_wrapped(
        c,
        "Risvegli frequenti, addormentamenti lunghi o sonnellini irregolari? "
        "Osserviamo insieme cosa sta succedendo e costruiamo cambiamenti realistici "
        "per il tuo bambino e la vostra famiglia.",
        x,
        y,
        W - 48,
        size=10.1,
        leading=14,
        color=HexColor("#E7EFEA"),
    )

    draw_thread(c, W - 29, H - photo_height - 44, 121)

    card_x, card_y, card_w, card_h = 18, 70, W - 36, 91
    c.setFillColor(PAPER)
    c.roundRect(card_x, card_y, card_w, card_h, 14, fill=1, stroke=0)

    c.setFillColor(HEART_RED)
    c.setFont("Helvetica-Bold", 7.4)
    c.drawString(card_x + 13, card_y + card_h - 17, "PERCORSO SONNO PERSONALIZZATO")
    c.setFillColor(INK)
    c.setFont("NewYork", 30)
    c.drawString(card_x + 13, card_y + 38, "180 €")
    c.setFillColor(MUTED)
    c.setFont("Helvetica", 8.2)
    c.drawString(card_x + 105, card_y + 52, "Tre call · diario · analisi")
    c.drawString(card_x + 105, card_y + 39, "circa 60 giorni · massimo 75")
    c.setFillColor(SAGE)
    c.roundRect(card_x + 105, card_y + 12, card_w - 118, 17, 8.5, fill=1, stroke=0)
    c.setFillColor(DEEP_GREEN)
    c.setFont("Helvetica-Bold", 7.5)
    c.drawCentredString(card_x + 105 + (card_w - 118) / 2, card_y + 17.5,
                        "CHIAMATA GRATUITA · CIRCA 20 MINUTI")

    draw_button(c, 18, 25, W - 36, "Parla con Selene su WhatsApp", WHATSAPP_URL)
    c.setFillColor(HexColor("#BFD0C6"))
    c.setFont("Helvetica", 7.4)
    c.drawCentredString(W / 2, 11.5, "Tocca il pulsante: si aprirà una conversazione già pronta")


def page_two(c):
    c.setFillColor(PAPER)
    c.rect(0, 0, W, H, fill=1, stroke=0)

    c.setFillColor(DEEP_GREEN)
    c.rect(0, H - 64, W, 64, fill=1, stroke=0)
    c.drawImage(str(LOGO_WHITE), 16, H - 51, 28, 28, mask="auto", preserveAspectRatio=True)
    c.setFillColor(white)
    c.setFont("Helvetica-Bold", 7.5)
    c.drawString(49, H - 28, "PERCORSO SONNO 0-12 MESI")
    c.setFont("NewYork", 20)
    c.drawString(49, H - 48, "Come lavoriamo")

    x = 18
    col_w = W - 36
    y = H - 89
    steps = [
        ("1", "Osserviamo", "Raccogliamo le informazioni iniziali e il diario del sonno."),
        ("2", "Ci incontriamo", "Prima call da 60-75 minuti per leggere ritmi, risvegli e routine."),
        ("3", "Verifichiamo", "Seconda call orientativamente dopo 30 giorni."),
        ("4", "Concludiamo", "Terza call entro 75 giorni dall'avvio, salvo indisponibilità di Selene."),
    ]
    for number, title, body in steps:
        c.setFillColor(SOFT_RED)
        c.circle(x + 11, y + 3, 11, fill=1, stroke=0)
        c.setFillColor(HEART_RED)
        c.setFont("Helvetica-Bold", 9.5)
        c.drawCentredString(x + 11, y, number)
        c.setFillColor(INK)
        c.setFont("Helvetica-Bold", 9.6)
        c.drawString(x + 31, y + 4, title)
        y = draw_wrapped(c, body, x + 31, y - 9, col_w - 31, size=8.5,
                         leading=11.5, color=MUTED) - 11

    box_y = 205
    c.setFillColor(MIST)
    c.roundRect(18, box_y, W - 36, 91, 12, fill=1, stroke=0)
    c.setFillColor(DEEP_GREEN)
    c.setFont("NewYork", 15)
    c.drawString(31, box_y + 68, "Può essere utile se...")
    bullet_y = box_y + 49
    bullet_y = draw_bullet(c, 31, bullet_y, "i risvegli sono frequenti o difficili da gestire", W - 63)
    bullet_y = draw_bullet(c, 31, bullet_y, "addormentamento e sonnellini non hanno un ritmo leggibile", W - 63)
    draw_bullet(c, 31, bullet_y, "vuoi cambiare qualcosa senza applicare un metodo rigido", W - 63)

    profile_y = 85
    c.setFillColor(white)
    c.roundRect(18, profile_y, W - 36, 105, 12, fill=1, stroke=0)
    profile = fit_crop(PHOTO_PROFILE, 420, 520, focus=(0.5, 0.2))
    path = c.beginPath()
    path.roundRect(28, profile_y + 13, 66, 79, 8)
    c.saveState()
    c.clipPath(path, stroke=0, fill=0)
    c.drawImage(profile, 28, profile_y + 13, 66, 79, mask="auto")
    c.restoreState()

    c.setFillColor(INK)
    c.setFont("NewYork", 14)
    c.drawString(108, profile_y + 76, "Selene Campetta")
    c.setFillColor(HEART_RED)
    c.setFont("Helvetica-Bold", 7.4)
    c.drawString(108, profile_y + 61, "INFERMIERA · MASTER IN COORDINAMENTO")
    draw_wrapped(
        c,
        "Ti accompagno online con osservazione, ascolto e attenzione alla sicurezza, "
        "rispettando il bambino e gli equilibri della famiglia.",
        108,
        profile_y + 43,
        W - 126,
        size=8.1,
        leading=11.2,
        color=MUTED,
    )

    c.setFillColor(DEEP_GREEN)
    c.roundRect(18, 29, W - 36, 42, 12, fill=1, stroke=0)
    c.setFillColor(white)
    c.setFont("Helvetica-Bold", 8.7)
    c.drawString(31, 52, "Vuoi capire se è il percorso giusto?")
    c.setFont("Helvetica", 7.7)
    c.drawString(31, 38.5, "380 631 7175 · Via C. D'Agnese 43, Montesilvano")
    c.setFillColor(HEART_RED)
    c.roundRect(W - 92, 36, 61, 25, 12.5, fill=1, stroke=0)
    c.setFillColor(white)
    c.setFont("Helvetica-Bold", 8)
    c.drawCentredString(W - 61.5, 45, "SCRIVIMI")
    c.linkURL(WHATSAPP_URL, (W - 92, 36, W - 31, 61), relative=0, thickness=0)

    c.setFillColor(MUTED)
    disclaimer = (
        "Il percorso offre educazione e accompagnamento. Non sostituisce il pediatra, "
        "non formula diagnosi e non garantisce un risultato specifico."
    )
    lines = wrap_text(disclaimer, "Helvetica", 5.9, W - 36)
    c.setFont("Helvetica", 5.9)
    disclaimer_y = 17
    for line in lines:
        c.drawCentredString(W / 2, disclaimer_y, line)
        disclaimer_y -= 7
    c.setFont("Helvetica-Bold", 6.4)
    c.drawCentredString(W / 2, 3.5, "@sc.studioinfermieristico")


def build():
    register_fonts()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    c = canvas.Canvas(str(OUTPUT), pagesize=PAGE, pageCompression=1)
    c.setTitle("Percorso sonno personalizzato - S.C. Studio Infermieristico")
    c.setAuthor("S.C. Studio Infermieristico - Selene Campetta")
    c.setSubject("Anteprima del percorso sonno personalizzato 0-12 mesi")
    page_one(c)
    c.showPage()
    page_two(c)
    c.save()
    print(OUTPUT)


if __name__ == "__main__":
    build()
