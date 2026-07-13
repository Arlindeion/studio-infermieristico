from pathlib import Path
from urllib.parse import quote

from reportlab.lib.colors import HexColor, white
from reportlab.pdfgen import canvas

from genera_pdf_percorso_sonno import (
    DEEP_GREEN,
    HEART_RED,
    H,
    INK,
    MIST,
    MUTED,
    PAGE,
    PAPER,
    SAGE,
    SOFT_RED,
    W,
    draw_button,
    draw_wrapped,
    pill,
    register_fonts,
    wrap_text,
)


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "output" / "pdf" / "consulenza_sonno_opzioni_prezzi_senza_foto.pdf"
LOGO_WHITE = ROOT / "static" / "img" / "logo.png"

WHATSAPP_TEXT = (
    "Buongiorno Selene, ho letto le opzioni della consulenza sonno e vorrei "
    "capire quale proposta è più adatta alla mia famiglia."
)
WHATSAPP_URL = f"https://wa.me/393806317175?text={quote(WHATSAPP_TEXT)}"


def draw_check(c, x, y, text, max_width, color=INK, size=8.4, leading=11.2,
               marker_color=HEART_RED):
    c.setStrokeColor(marker_color)
    c.setLineWidth(1.5)
    c.line(x, y + 3, x + 3, y)
    c.line(x + 3, y, x + 8, y + 7)
    return draw_wrapped(c, text, x + 14, y, max_width - 14, size=size,
                        leading=leading, color=color) - 2


def draw_not_included(c, x, y, text, max_width):
    c.setStrokeColor(MUTED)
    c.setLineWidth(1)
    c.line(x, y + 3, x + 7, y + 3)
    return draw_wrapped(c, text, x + 14, y, max_width - 14, size=7.7,
                        leading=10.3, color=MUTED) - 1


def header(c, eyebrow, title):
    c.setFillColor(DEEP_GREEN)
    c.rect(0, H - 64, W, 64, fill=1, stroke=0)
    c.drawImage(str(LOGO_WHITE), 16, H - 51, 28, 28, mask="auto", preserveAspectRatio=True)
    c.setFillColor(white)
    c.setFont("Helvetica-Bold", 7.3)
    c.drawString(50, H - 27, eyebrow)
    c.setFont("NewYork", 18.5)
    c.drawString(50, H - 48, title)


def page_one(c):
    c.setFillColor(PAPER)
    c.rect(0, 0, W, H, fill=1, stroke=0)

    header(c, "ANTEPRIMA RISERVATA · SONNO 0-12 MESI", "Informazioni e prezzi")

    pill(c, "In studio · Montesilvano", 18, H - 91, 118, DEEP_GREEN, white)

    c.setFillColor(INK)
    c.setFont("NewYork", 20.5)
    c.drawString(18, H - 119, "Una domanda precisa o")
    c.drawString(18, H - 143, "un percorso completo?")
    draw_wrapped(
        c,
        "La scelta dipende da quanto c'è da osservare. Prima di fissare l'incontro, "
        "una chiamata gratuita di 15 minuti ci aiuta a orientarci.",
        18,
        H - 166,
        W - 36,
        size=8.7,
        leading=11.5,
        color=MUTED,
    )

    main_y, main_h = 204, 136
    c.setFillColor(DEEP_GREEN)
    c.roundRect(18, main_y, W - 36, main_h, 14, fill=1, stroke=0)
    c.setFillColor(HEART_RED)
    c.roundRect(31, main_y + main_h - 29, 105, 18, 9, fill=1, stroke=0)
    c.setFillColor(white)
    c.setFont("Helvetica-Bold", 7.1)
    c.drawCentredString(83.5, main_y + main_h - 23, "PERCORSO PRINCIPALE")
    c.setFont("NewYork", 29)
    c.drawString(31, main_y + 72, "180 €")
    c.setFont("Helvetica-Bold", 10.5)
    c.drawString(137, main_y + 89, "Percorso personalizzato")
    c.setFillColor(HexColor("#D9E6DE"))
    c.setFont("Helvetica", 7.9)
    c.drawString(137, main_y + 74, "Per leggere il sonno nel suo insieme")
    y = main_y + 50
    y = draw_check(c, 31, y, "Diario di 5 giorni e incontro di 75 minuti", W - 62,
                   color=white, marker_color=HEART_RED)
    y = draw_check(c, 31, y, "Indicazioni scritte, verifica di 30 minuti e 7 giorni di supporto",
                   W - 62, color=white, marker_color=HEART_RED)

    small_y, small_h = 94, 94
    c.setFillColor(white)
    c.roundRect(18, small_y, W - 36, small_h, 14, fill=1, stroke=0)
    c.setStrokeColor(SAGE)
    c.setLineWidth(1)
    c.roundRect(18, small_y, W - 36, small_h, 14, fill=0, stroke=1)
    c.setFillColor(HEART_RED)
    c.setFont("NewYork", 24)
    c.drawString(31, small_y + 42, "75 €")
    c.setFillColor(INK)
    c.setFont("Helvetica-Bold", 10.2)
    c.drawString(111, small_y + 54, "Consulenza mirata")
    c.setFillColor(MUTED)
    c.setFont("Helvetica", 7.9)
    c.drawString(111, small_y + 39, "Per una sola difficoltà ben definita")
    c.drawString(111, small_y + 25, "Questionario breve · incontro di 50 minuti")
    c.setFillColor(DEEP_GREEN)
    c.setFont("Helvetica-Bold", 7.1)
    c.drawString(31, small_y + 14, "UNA RISPOSTA MIRATA, SENZA ACCOMPAGNAMENTO CONTINUATIVO")

    draw_button(c, 18, 38, W - 36, "Chiedi a Selene quale scegliere", WHATSAPP_URL)


def page_two(c):
    c.setFillColor(PAPER)
    c.rect(0, 0, W, H, fill=1, stroke=0)
    header(c, "NON DEVI SCEGLIERE DA SOLA", "Quale proposta è adatta?")

    c.setFillColor(white)
    c.roundRect(18, 348, W - 36, 117, 13, fill=1, stroke=0)
    c.setFillColor(HEART_RED)
    c.setFont("NewYork", 20)
    c.drawString(31, 438, "Consulenza mirata · 75 €")
    c.setFillColor(INK)
    c.setFont("Helvetica-Bold", 8.6)
    c.drawString(31, 420, "È adatta quando hai una domanda circoscritta, ad esempio:")
    y = 401
    y = draw_check(c, 31, y, "un passaggio specifico nella routine serale", W - 62)
    y = draw_check(c, 31, y, "un dubbio preciso su sonnellini o addormentamento", W - 62)
    draw_check(c, 31, y, "una situazione recente che vuoi leggere meglio", W - 62)
    c.setFillColor(MUTED)
    c.setFont("Helvetica", 7.3)
    c.drawString(31, 359, "Ricevi una sintesi essenziale, non un piano completo o assistenza successiva.")

    c.setFillColor(MIST)
    c.roundRect(18, 210, W - 36, 126, 13, fill=1, stroke=0)
    c.setFillColor(DEEP_GREEN)
    c.setFont("NewYork", 20)
    c.drawString(31, 308, "Percorso personalizzato · 180 €")
    c.setFillColor(INK)
    c.setFont("Helvetica-Bold", 8.6)
    c.drawString(31, 289, "È la scelta giusta quando:")
    y = 270
    y = draw_check(c, 31, y, "risvegli, sonnellini e addormentamento si influenzano tra loro", W - 62)
    y = draw_check(c, 31, y, "la difficoltà dura nel tempo o cambia da un giorno all'altro", W - 62)
    y = draw_check(c, 31, y, "hai bisogno di provare i cambiamenti e verificarli insieme", W - 62)
    c.setFillColor(DEEP_GREEN)
    c.setFont("Helvetica-Bold", 7.4)
    c.drawString(31, 221, "OSSERVAZIONE COMPLETA · PIANO SCRITTO · ACCOMPAGNAMENTO")

    c.setFillColor(SOFT_RED)
    c.roundRect(18, 153, W - 36, 45, 12, fill=1, stroke=0)
    c.setFillColor(INK)
    c.setFont("Helvetica-Bold", 8.2)
    c.drawString(31, 181, "Se il problema coinvolge più aspetti, te lo dirò prima di fissare.")
    c.setFont("Helvetica", 7.5)
    c.drawString(31, 166, "La chiamata conoscitiva serve anche a evitare una consulenza non adatta.")

    c.setFillColor(white)
    c.roundRect(18, 62, W - 36, 79, 12, fill=1, stroke=0)
    c.setFillColor(HEART_RED)
    c.roundRect(30, 74, 4, 55, 2, fill=1, stroke=0)
    c.setFillColor(INK)
    c.setFont("NewYork", 14.5)
    c.drawString(46, 113, "Selene Campetta")
    c.setFillColor(HEART_RED)
    c.setFont("Helvetica-Bold", 7.1)
    c.drawString(46, 97, "INFERMIERA · ALBO OPI PESCARA")
    c.setFillColor(MUTED)
    c.setFont("Helvetica", 7.7)
    c.drawString(46, 81, "380 631 7175 · Via C. D'Agnese 43, Montesilvano")

    c.setFillColor(DEEP_GREEN)
    c.roundRect(18, 20, W - 36, 31, 15.5, fill=1, stroke=0)
    c.setFillColor(white)
    c.setFont("Helvetica-Bold", 9)
    c.drawCentredString(W / 2, 30.5, "Scrivimi: scegliamo insieme da dove iniziare")
    c.linkURL(WHATSAPP_URL, (18, 20, W - 18, 51), relative=0, thickness=0)

    disclaimer = (
        "Il servizio offre educazione e accompagnamento. Non sostituisce il pediatra, "
        "non formula diagnosi e non garantisce un risultato specifico."
    )
    lines = wrap_text(disclaimer, "Helvetica", 5.8, W - 36)
    c.setFillColor(MUTED)
    c.setFont("Helvetica", 5.8)
    y = 10
    for line in lines:
        c.drawCentredString(W / 2, y, line)
        y -= 6.5


def build():
    register_fonts()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    c = canvas.Canvas(str(OUTPUT), pagesize=PAGE, pageCompression=1)
    c.setTitle("Consulenza sonno - opzioni e prezzi")
    c.setAuthor("S.C. Studio Infermieristico - Selene Campetta")
    c.setSubject("Consulenza mirata e percorso sonno personalizzato 0-12 mesi")
    page_one(c)
    c.showPage()
    page_two(c)
    c.save()
    print(OUTPUT)


if __name__ == "__main__":
    build()
