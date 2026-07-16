import logging
import json
import re
import urllib.request
import urllib.error
import ssl
import certifi
from urllib.parse import urlsplit
from flask import Flask, render_template, request, redirect, url_for, flash, abort, session, jsonify, Response
from dotenv import load_dotenv
import os
import secrets
import time
from collections import defaultdict
from zoneinfo import ZoneInfo
from apscheduler.schedulers.background import BackgroundScheduler
import icalendar
import recurring_ical_events
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
load_dotenv()
from config import config
from flask_sqlalchemy import SQLAlchemy
try:
    from flask_migrate import Migrate
except ImportError:  # Flask-Migrate è dichiarato in requirements, ma resta opzionale in locale finché non reinstalli.
    Migrate = None
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from flask_mail import Mail, Message
from datetime import datetime, date, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_talisman import Talisman

# Configurazione del logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s:%(name)s: %(message)s',
    handlers=[
        logging.FileHandler('app.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Caricamento della configurazione
config_name = os.environ.get('FLASK_ENV', 'development')
app.config.from_object(config[config_name])

# Limitazione del traffico
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["200 per day", "50 per hour"],
    storage_uri="memory://",
)

# Protezione CSRF
def generate_csrf_token():
    if '_csrf_token' not in session:
        session['_csrf_token'] = secrets.token_hex(32)
    return session['_csrf_token']

app.jinja_env.globals['csrf_token'] = generate_csrf_token

# La configurazione email (server, porta, TLS, username, password, mittente)
# è già definita in config.py a partire dalle variabili d'ambiente in .env.
# NON va duplicata/sovrascritta qui: farlo renderebbe inutile qualsiasi
# modifica al file .env. Assicurati che nel tuo .env siano presenti sia
# MAIL_USERNAME che MAIL_PASSWORD.

db = SQLAlchemy(app)
mail = Mail(app)
migrate = Migrate(app, db) if Migrate else None
scheduler = BackgroundScheduler()
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.session_protection = 'basic'

talisman = Talisman(
    app,
    content_security_policy={
        'default-src': "'self'",
        'style-src': ["'self'", "'unsafe-inline'", "https://fonts.googleapis.com"],
        'script-src': ["'self'", "https://w.behold.so", "https://www.googletagmanager.com"],
        'connect-src': [
            "'self'",
            "https://feeds.behold.so",
            "https://www.google-analytics.com",
            "https://region1.google-analytics.com",
            "https://analytics.google.com",
        ],
        'img-src': [
            "'self'",
            "data:",
            "https://cdn2.behold.pictures",
            "https://*.cdninstagram.com",
            "https://www.google-analytics.com",
        ],
        'media-src': ["'self'", "https://*.cdninstagram.com"],
        'font-src': ["'self'", "https://fonts.gstatic.com"],
        'frame-src': ["'self'", "https://www.google.com"],
    },
    force_https=False,
    session_cookie_secure=os.environ.get('FLASK_ENV') == 'production',
    session_cookie_http_only=True,
    session_cookie_samesite='Lax',
)


@app.context_processor
def inject_tracking_config():
    return {
        'google_analytics_id': app.config.get('GOOGLE_ANALYTICS_ID')
    }


# ─── COSTANTI ───

SERVIZI_VALIDI = [
    'Iniezione intramuscolare',
    'Iniezione sottocutanea',
    'Flebo e terapia infusionale',
    'Medicazione semplice',
    'Medicazione complessa',
    'Controllo parametri vitali',
    'Assistenza domiciliare',
    'Gestione terapia farmacologica',
]

STATI_VALIDI = ['Confermato', 'Annullato', 'In attesa']
STATI_CALL_SONNO_VALIDI = ['In attesa', 'Confermata', 'Annullata', 'Conclusa']
FORMULE_SONNO = {
    'mirata': 'Consulenza mirata',
    'percorso': 'Percorso sonno personalizzato',
}
DIFFICOLTA_SONNO = [
    'Addormentamento difficile la sera',
    'Risvegli notturni frequenti',
    'Pisolini difficili o brevi',
    'Addormentamento solo con forte supporto (braccio/seno)',
    'Cambiamenti / regressioni / distacchi',
    'Altro',
]
QUESTIONARIO_SONNO_LABELS = {
    'nome_bambino': 'Nome del bambino',
    'data_nascita': 'Data di nascita',
    'nascita': 'Nascita e prematurità',
    'eta_corretta': 'Età corretta',
    'gestione_sonno': 'Chi gestisce il sonno',
    'alimentazione': 'Alimentazione',
    'poppate_notturne': 'Poppate o pasti notturni',
    'addormentamento_seno': 'Addormentamento al seno',
    'risveglio_mattino': 'Risveglio del mattino',
    'pisolini': 'Pisolini',
    'routine_serale': 'Routine serale',
    'ora_addormentamento': 'Orario di addormentamento',
    'cambiamenti_routine': 'Cambiamenti della routine',
    'dove_si_addormenta': 'Dove si addormenta',
    'dove_dorme': 'Dove dorme',
    'supporti_addormentamento': 'Supporti per addormentarsi',
    'risvegli_dettaglio': 'Risvegli',
    'riaddormentamento': 'Come si riaddormenta',
    'risveglio_precoce': 'Risveglio precoce',
    'durata_difficolta': 'Durata della difficoltà',
    'tentativi_fatti': 'Tentativi già fatti',
    'eventi_recenti': 'Eventi recenti',
    'momento_piu_difficile': 'Momento più difficile',
    'cambiamento_desiderato': 'Cambiamento desiderato',
    'cosa_non_cambiare': 'Cosa non cambiare',
    'partecipanti_consulenza': 'Partecipanti alla consulenza',
    'condizioni_note': 'Condizioni già valutate',
    'terapie_indicazioni': 'Terapie o indicazioni',
    'professionisti_coinvolti': 'Professionisti coinvolti',
    'note_finali': 'Note finali',
}
DURATA_CALL_SONNO_MINUTI = 20
BLOCCO_CALL_SONNO_MINUTI = 30
ORARI_CALL_SONNO = [
    f'{ora:02d}:{minuto:02d}'
    for ora in [8, 9, 10, 11, 12, 15, 16, 17, 18]
    for minuto in [0, 30]
]
STATI_ISCRIZIONE_VALIDI = ['Nuova', 'Contattato', 'Confermato', 'Annullato']
STATI_CORSO_VALIDI = ['Aperto', 'Completo', 'Chiuso', 'Annullato', 'Concluso']
STATI_PERCORSO_ACCOMPAGNAMENTO_VALIDI = ['Bozza', 'Aperto', 'Chiuso', 'Concluso']

TIPI_RICHIESTA_CORSO = {
    'richiesta_iscrizione': 'Richiesta iscrizione',
    'open_day': 'Open day',
    'iscrizione_effettiva': 'Iscrizione effettiva',
    'ricontatto': 'Da ricontattare',
}

CORSI_ADMIN_TIPI = {
    'bls-d': {
        'label': 'BLSD',
        'titolo': 'BLSD',
        'durata_ore': 4,
    },
    'disostruzione-pediatrica': {
        'label': 'Disostruzione pediatrica e tagli sicuri',
        'titolo': 'Disostruzione pediatrica e tagli sicuri',
        'durata_ore': 2,
    },
    'accompagnamento-nascita': {
        'label': 'Corso di accompagnamento alla nascita',
        'titolo': 'Corso di accompagnamento alla nascita',
        'durata_ore': 2,
    },
    'laboratorio-infanzia': {
        'label': "Laboratorio per l'infanzia",
        'titolo': "Laboratorio per l'infanzia",
        'durata_ore': 2,
    },
}

CORSI_ISCRIVIBILI = {
    'bls-d': {
        'titolo': 'Corso BLSD',
        'partecipazione_options': ['Iscrizione individuale'],
    },
    'disostruzione-pediatrica': {
        'titolo': 'Disostruzione pediatrica e tagli sicuri',
        'partecipazione_options': ['Singolo 34 euro', 'Coppia 60 euro'],
    },
    'accompagnamento-nascita': {
        'titolo': 'Corso di accompagnamento alla nascita',
    },
    'laboratorio-infanzia': {
        'titolo': 'Laboratori svezzamento, gioco e sviluppo',
        'partecipazione_options': ['Iscrizione individuale'],
    },
}

STUDIO_MAP_EMBED_SRC = "https://www.google.com/maps?q=Via%20C.%20D%27Agnese%2043%2C%2065015%20Montesilvano%20PE&output=embed"
STUDIO_MAP_LINK = "https://www.google.com/maps/search/?api=1&query=Via%20C.%20D%27Agnese%2043%2C%2065015%20Montesilvano%20PE"


FAQ_ITEMS = [
    {
        'id': 'corsi-disponibili',
        'question': 'Quali corsi in presenza sono disponibili per famiglie, genitori e aziende?',
        'answer': "I corsi principali sono BLSD, disostruzione pediatrica e tagli sicuri, corso di accompagnamento alla nascita e laboratori per l'infanzia. I corsi sono pensati per trasformare dubbi e paura in gesti pratici, con una guida sanitaria chiara e vicina alle famiglie.",
        'link_href': '/iscrizione-corsi',
        'link_text': 'Scopri i corsi',
    },
    {
        'id': 'iscrizione-corsi-online',
        'question': 'Come funziona l\'iscrizione online ai corsi?',
        'answer': "Dalla pagina corsi scegli il corso, compili il modulo e invii la richiesta. Se c'è una data aperta, la richiesta viene collegata a quella data; se non ci sono date disponibili, puoi lasciare i tuoi dati e ti ricontatterò quando si apre una nuova possibilità.",
        'link_href': '/iscrizione-corsi',
        'link_text': 'Vai alle iscrizioni',
    },
    {
        'id': 'blsd-privati-aziende',
        'question': 'Come posso iscrivermi a un corso BLSD o richiederlo per un\'azienda?',
        'answer': "Il BLSD ha due percorsi separati: i privati possono usare il modulo di iscrizione individuale per le date aperte, mentre aziende e gruppi devono contattare direttamente lo studio per organizzare un corso personalizzato in studio o in azienda.",
        'link_href': '/iscrizione-corsi/bls-d',
        'link_text': 'Vedi BLSD',
    },
    {
        'id': 'disostruzione-pediatrica-tagli-sicuri',
        'question': 'A cosa serve il corso di disostruzione pediatrica e tagli sicuri?',
        'answer': "Il corso aiuta genitori, nonni e caregiver a conoscere le manovre di disostruzione su lattante e bambino e a ridurre il rischio a tavola con indicazioni pratiche sui tagli sicuri degli alimenti.",
        'link_href': '/iscrizione-corsi/disostruzione-pediatrica',
        'link_text': 'Scopri disostruzione pediatrica',
    },
    {
        'id': 'accompagnamento-nascita-open-day',
        'question': 'Come funziona il corso di accompagnamento alla nascita?',
        'answer': "Il primo passaggio è l'open day gratuito: serve a conoscere il percorso, fare domande e capire se il corso completo è adatto alla famiglia. L'iscrizione vera e propria al percorso completo avviene solo tramite link privato fornito successivamente dallo studio.",
        'link_href': '/iscrizione-corsi/accompagnamento-nascita',
        'link_text': 'Vai all\'open day',
    },
    {
        'id': 'percorso-privato-accompagnamento-nascita',
        'question': 'Il link privato del corso di accompagnamento alla nascita conferma direttamente l\'iscrizione?',
        'answer': "Sì. Il link privato è riservato al percorso completo: quando compili quel modulo, l'iscrizione viene registrata come confermata. Ricevi una email con riepilogo delle date, contatti dello studio e informazioni essenziali.",
        'link_href': '/iscrizione-corsi/accompagnamento-nascita',
        'link_text': 'Scopri il percorso nascita',
    },
    {
        'id': 'durata-corsi',
        'question': 'Quanto durano i corsi?',
        'answer': "La durata dipende dal tipo di corso: il BLSD dura circa 4 ore, disostruzione pediatrica e laboratori per l'infanzia durano circa 2 ore, mentre il corso completo di accompagnamento alla nascita è una serie di 9 incontri con infermiera, ostetrica, psicologa, osteopata e nutrizionista.",
        'link_href': '/iscrizione-corsi',
        'link_text': 'Vedi i corsi',
    },
    {
        'id': 'consulenza-sonno-infantile',
        'question': 'Quando può essere utile una consulenza sul sonno infantile?',
        'answer': "La consulenza è dedicata al sonno dei bambini da 0 a 12 mesi e può essere utile quando addormentamento, risvegli o pisolini sono diventati difficili da leggere. Partiamo da una call gratuita per capire la situazione e verificare insieme quale passo sia davvero adatto alla famiglia.",
        'link_href': '/consulenze-online',
        'link_text': 'Scopri la consulenza del sonno',
    },
    {
        'id': 'consulenze-online-presenza',
        'question': 'La consulenza sul sonno è online o in presenza?',
        'answer': "La consulenza può svolgersi online in tutta Italia o in studio a Montesilvano. Prima di iniziare puoi scegliere una call gratuita: mi serve per comprendere la difficoltà principale e verificare se il servizio è adatto.",
        'link_href': '/consulenze-online',
        'link_text': 'Vedi consulenze',
    },
    {
        'id': 'prenotare-prestazione-infermieristica',
        'question': 'Come posso prenotare una prestazione infermieristica?',
        'answer': "Puoi prenotare una prestazione infermieristica dalla pagina Prenota. Compili il modulo con i tuoi dati, scegli il servizio, la data e l'orario disponibili, accetti l'informativa privacy e invii la richiesta.",
        'link_href': '/prenota',
        'link_text': 'Vai alla prenotazione',
    },
    {
        'id': 'prenotazione-corsi',
        'question': 'La pagina Prenota serve anche per iscriversi ai corsi?',
        'answer': 'No. La pagina Prenota è dedicata alle prestazioni sanitarie. Le iscrizioni ai corsi, agli open day e alle richieste di ricontatto hanno un flusso separato nella sezione Corsi e iscrizioni.',
        'link_href': '/iscrizione-corsi',
        'link_text': 'Vai ai corsi',
    },
    {
        'id': 'prestazioni-disponibili',
        'question': 'Quali prestazioni infermieristiche posso prenotare?',
        'answer': 'Puoi richiedere iniezioni intramuscolari e sottocutanee, flebo e terapie infusionali, medicazioni semplici o complesse, controllo dei parametri vitali, assistenza domiciliare e supporto nella gestione della terapia farmacologica.',
        'link_href': '/prestazioni-infermieristiche',
        'link_text': 'Vedi le prestazioni',
    },
    {
        'id': 'giorni-orari-prenotabili',
        'question': 'In quali giorni e orari posso prenotare un appuntamento?',
        'answer': "Gli appuntamenti sono prenotabili dal lunedì al venerdì negli orari disponibili del calendario. Il sabato l'ultimo orario prenotabile è le 11:30. Domeniche e festivi non sono prenotabili.",
        'link_href': '/prenota',
        'link_text': 'Controlla gli orari disponibili',
    },
    {
        'id': 'dopo-invio-prenotazione',
        'question': 'Cosa succede dopo aver inviato una prenotazione sanitaria?',
        'answer': "Dopo l'invio, la richiesta arriva allo studio. Ricevi una email di conferma della richiesta e l'appuntamento viene gestito manualmente; quando viene confermato, può essere sincronizzato con il calendario collegato al gestionale.",
        'link_href': '/prenota',
        'link_text': 'Invia una richiesta',
    },
    {
        'id': 'privacy-dati-sanitari',
        'question': 'Come vengono trattati i dati personali e sanitari inviati dal sito?',
        'answer': "I dati inseriti nei moduli vengono usati per gestire prenotazioni, iscrizioni ai corsi e comunicazioni necessarie. I dati sanitari sono trattati come dati particolari ai sensi del GDPR e l'invio richiede l'accettazione dell'informativa privacy.",
        'link_href': '/privacy',
        'link_text': 'Leggi la privacy',
    },
    {
        'id': 'dove-si-trova-studio',
        'question': 'Dove si trova S.C. Studio Infermieristico e come posso contattarlo?',
        'answer': "Lo studio si trova in Via C. D'Agnese 43 a Montesilvano, in provincia di Pescara. Puoi contattarmi al numero 3806317175 o tramite il pulsante WhatsApp presente sul sito.",
        'map_embed_src': STUDIO_MAP_EMBED_SRC,
        'link_href': 'https://wa.me/393806317175',
        'link_text': 'Scrivimi su WhatsApp',
        'link_external': True,
    },
]

# Slot orari prenotabili (durata 30 minuti ciascuno). È la stessa lista
# mostrata nei menu a tendina di prenota.html e modifica_appuntamento.html.
ORARI_DISPONIBILI = [
    '08:00', '08:30', '09:00', '09:30', '10:00', '10:30',
    '11:00', '11:30', '12:00', '12:30', '15:00', '15:30',
    '16:00', '16:30', '17:00', '17:30', '18:00', '18:30',
]
DURATA_SLOT_MINUTI = 30
DURATA_CORSO_DEFAULT_ORE = 2
FESTIVI_FISSI = {
    (1, 1),    # Capodanno
    (1, 6),    # Epifania
    (4, 25),   # Festa della Liberazione
    (5, 1),    # Festa dei Lavoratori
    (6, 2),    # Festa della Repubblica
    (8, 15),   # Ferragosto
    (11, 1),   # Ognissanti
    (12, 8),   # Immacolata
    (12, 25),  # Natale
    (12, 26),  # Santo Stefano
}

FUSO_ORARIO = ZoneInfo('Europe/Rome')


def calcola_pasqua(anno):
    a = anno % 19
    b = anno // 100
    c = anno % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    mese = (h + l - 7 * m + 114) // 31
    giorno = ((h + l - 7 * m + 114) % 31) + 1
    return date(anno, mese, giorno)


def is_festivo(giorno):
    return (
        giorno.weekday() == 6
        or (giorno.month, giorno.day) in FESTIVI_FISSI
        or giorno == calcola_pasqua(giorno.year) + timedelta(days=1)
    )


def orario_prenotabile(data_str, ora):
    try:
        giorno = datetime.strptime(data_str, '%Y-%m-%d').date()
    except ValueError:
        return False

    if ora not in ORARI_DISPONIBILI or is_festivo(giorno):
        return False

    if giorno.weekday() == 5 and ora > '11:30':
        return False

    return True


def orari_non_prenotabili_per_chiusura(data_str):
    try:
        giorno = datetime.strptime(data_str, '%Y-%m-%d').date()
    except ValueError:
        return set(ORARI_DISPONIBILI)

    if is_festivo(giorno):
        return set(ORARI_DISPONIBILI)

    if giorno.weekday() == 5:
        return {ora for ora in ORARI_DISPONIBILI if ora > '11:30'}

    return set()


def is_safe_redirect_target(target):
    if not target:
        return False

    ref_url = urlsplit(request.host_url)
    test_url = urlsplit(target)
    return not test_url.netloc or test_url.netloc == ref_url.netloc

# ─── INTEGRAZIONE GOOGLE CALENDAR (via Arzamed) ───
#
# Arzamed sincronizza appuntamenti e chiusure studio su un calendario
# Google. Leggiamo quel calendario tramite il suo "indirizzo segreto in
# formato iCal" (nessuna credenziale API necessaria) per bloccare, anche
# sul sito, gli orari già impegnati su Arzamed.
#
# Il risultato del download viene tenuto in cache per qualche minuto
# (CALENDARIO_CACHE_SECONDI) per non interrogare Google ad ogni richiesta.

_cache_calendario = {'calendario': None, 'scaricato_il': 0}


def _scarica_calendario_ics():
    """Scarica e interpreta il feed iCal di Google Calendar, con cache in memoria.

    Restituisce un oggetto icalendar.Calendar, oppure None se l'URL non è
    configurato o se il download/parsing fallisce (in quel caso il sito
    continua a funzionare usando solo gli appuntamenti presi dal form).
    """
    url = app.config.get('GOOGLE_CALENDAR_ICS_URL')
    if not url:
        return None

    adesso = time.time()
    cache_valida_fino_a = _cache_calendario['scaricato_il'] + app.config.get('CALENDARIO_CACHE_SECONDI', 300)
    if _cache_calendario['calendario'] is not None and adesso < cache_valida_fino_a:
        return _cache_calendario['calendario']

    try:
        contesto_ssl = ssl.create_default_context(cafile=certifi.where())
        with urllib.request.urlopen(url, timeout=10, context=contesto_ssl) as risposta:
            contenuto = risposta.read()
        calendario = icalendar.Calendar.from_ical(contenuto)
        _cache_calendario['calendario'] = calendario
        _cache_calendario['scaricato_il'] = adesso
        return calendario
    except Exception as e:
        logger.error(f'>>> Errore nel download/lettura del calendario Google: {e}', exc_info=True)
        # Se il download fallisce ma avevamo già una copia in cache (anche se
        # "scaduta"), meglio riusarla piuttosto che non bloccare nessun orario.
        return _cache_calendario['calendario']


def _intervalli_calendario(data_str, ignore_google_event_id=None):
    """Restituisce gli intervalli occupati nel giorno richiesto.

    La forma a intervalli permette di confrontare durate diverse senza
    lasciare sovrapposizioni invisibili.
    """
    calendario = _scarica_calendario_ics()
    if calendario is None:
        return []

    try:
        giorno = datetime.strptime(data_str, '%Y-%m-%d').date()
    except ValueError:
        return []

    inizio_giornata = datetime.combine(giorno, datetime.min.time(), tzinfo=FUSO_ORARIO)
    fine_giornata = inizio_giornata + timedelta(days=1)

    try:
        eventi = recurring_ical_events.of(calendario).between(inizio_giornata, fine_giornata)
    except Exception as e:
        logger.error(f'>>> Errore nell\'espansione degli eventi del calendario: {e}', exc_info=True)
        return []

    intervalli = []
    for evento in eventi:
        uid = str(evento.get('UID') or '')
        if ignore_google_event_id and uid.startswith(ignore_google_event_id):
            continue
        inizio_evento = evento.get('DTSTART').dt
        fine_evento = evento.get('DTEND').dt if evento.get('DTEND') else inizio_evento

        # Un evento "tutto il giorno" ha date (non datetime) come inizio/fine:
        # lo trattiamo come se occupasse l'intera fascia oraria dello studio.
        if not isinstance(inizio_evento, datetime):
            inizio_evento = datetime.combine(inizio_evento, datetime.min.time(), tzinfo=FUSO_ORARIO)
        if not isinstance(fine_evento, datetime):
            fine_evento = datetime.combine(fine_evento, datetime.min.time(), tzinfo=FUSO_ORARIO)

        # Normalizza al fuso orario locale per confrontare correttamente con
        # gli slot orari dello studio (gli eventi Google possono arrivare in
        # UTC o con un altro fuso a seconda di come sono stati creati).
        if inizio_evento.tzinfo is None:
            inizio_evento = inizio_evento.replace(tzinfo=FUSO_ORARIO)
        else:
            inizio_evento = inizio_evento.astimezone(FUSO_ORARIO)
        if fine_evento.tzinfo is None:
            fine_evento = fine_evento.replace(tzinfo=FUSO_ORARIO)
        else:
            fine_evento = fine_evento.astimezone(FUSO_ORARIO)

        intervalli.append((inizio_evento, fine_evento))

    return intervalli


def intervallo_occupato_da_calendario(data_str, ora, durata_minuti, ignore_google_event_id=None):
    try:
        giorno = datetime.strptime(data_str, '%Y-%m-%d').date()
        ore, minuti = map(int, ora.split(':'))
    except (ValueError, TypeError):
        return True
    inizio_slot = datetime.combine(giorno, datetime.min.time(), tzinfo=FUSO_ORARIO).replace(
        hour=ore,
        minute=minuti,
    )
    fine_slot = inizio_slot + timedelta(minutes=durata_minuti)
    return any(
        inizio_slot < fine_evento and inizio_evento < fine_slot
        for inizio_evento, fine_evento in _intervalli_calendario(data_str, ignore_google_event_id)
    )


def orari_occupati_da_calendario(data_str):
    """Restituisce gli slot sanitari da 30 minuti occupati su Calendar."""
    occupati = {
        ora for ora in ORARI_DISPONIBILI
        if intervallo_occupato_da_calendario(data_str, ora, DURATA_SLOT_MINUTI)
    }

    return occupati


# ─── SCRITTURA SU GOOGLE CALENDAR (account di servizio) ───
#
# Quando un appuntamento viene confermato dall'area admin, creiamo un evento
# corrispondente sul calendario Google (lo stesso usato da Arzamed), così chi
# controlla il calendario vede anche le prenotazioni arrivate dal sito.
# Se l'appuntamento viene poi annullato o spostato, aggiorniamo/eliminiamo
# anche l'evento, per restare sincronizzati nei due sensi.
#
# A differenza della lettura (che usa il feed iCal pubblico/segreto), la
# scrittura richiede un vero accesso alle API di Google Calendar tramite un
# account di servizio con permesso di modifica sul calendario.

_servizio_calendario_cache = None


def _ottieni_servizio_calendario():
    """Restituisce un client autenticato per le API di Google Calendar, o None
    se la scrittura su Google Calendar non è configurata o fallisce."""
    global _servizio_calendario_cache
    if _servizio_calendario_cache is not None:
        return _servizio_calendario_cache

    percorso_chiave = app.config.get('GOOGLE_SERVICE_ACCOUNT_FILE')
    if not percorso_chiave:
        logger.warning('>>> Scrittura Google Calendar non configurata: GOOGLE_SERVICE_ACCOUNT_FILE mancante.')
        return None

    try:
        credenziali = service_account.Credentials.from_service_account_file(
            percorso_chiave,
            scopes=['https://www.googleapis.com/auth/calendar']
        )
        _servizio_calendario_cache = build('calendar', 'v3', credentials=credenziali, cache_discovery=False)
        return _servizio_calendario_cache
    except Exception as e:
        logger.error(f'>>> Errore nell\'autenticazione con Google Calendar: {e}', exc_info=True)
        return None


def _corpo_evento_da_appuntamento(appuntamento):
    """Costruisce il corpo dell'evento Google Calendar a partire da un Appuntamento."""
    ora, minuto = map(int, appuntamento.ora.split(':'))
    giorno = datetime.strptime(appuntamento.data, '%Y-%m-%d').date()
    inizio = datetime.combine(giorno, datetime.min.time(), tzinfo=FUSO_ORARIO).replace(hour=ora, minute=minuto)
    fine = inizio + timedelta(minutes=DURATA_SLOT_MINUTI)

    return {
        'summary': f'{appuntamento.nome} {appuntamento.servizio}',
        'description': (
            f'Telefono: {appuntamento.telefono}\n'
            f'Email: {appuntamento.email}\n'
            f'Note: {appuntamento.note or "Nessuna"}\n'
            f'(Prenotazione confermata dal sito web)'
        ),
        'start': {'dateTime': inizio.isoformat(), 'timeZone': 'Europe/Rome'},
        'end': {'dateTime': fine.isoformat(), 'timeZone': 'Europe/Rome'},
    }


def _corpo_evento_da_corso(corso):
    """Costruisce il corpo dell'evento Google Calendar a partire da un Corso."""
    giorno = datetime.strptime(corso.data, '%Y-%m-%d').date()
    descrizione = corso.descrizione or 'Nessuna descrizione'
    durata_ore = corso.durata_ore or DURATA_CORSO_DEFAULT_ORE
    corpo = {
        'summary': f'Corso: {corso.titolo}',
        'description': f'{descrizione}\n\n(Corso inserito dall\'area admin del sito web)',
    }
    if corso.luogo:
        corpo['location'] = corso.luogo

    if corso.ora:
        ora, minuto = map(int, corso.ora.split(':'))
        inizio = datetime.combine(giorno, datetime.min.time(), tzinfo=FUSO_ORARIO).replace(hour=ora, minute=minuto)
        fine = inizio + timedelta(hours=durata_ore)
        corpo['start'] = {'dateTime': inizio.isoformat(), 'timeZone': 'Europe/Rome'}
        corpo['end'] = {'dateTime': fine.isoformat(), 'timeZone': 'Europe/Rome'}
    else:
        corpo['start'] = {'date': giorno.isoformat()}
        corpo['end'] = {'date': (giorno + timedelta(days=1)).isoformat()}

    return corpo


def _durata_corso_da_form(valore, tipo_corso):
    durata_default = CORSI_ADMIN_TIPI.get(tipo_corso, {}).get('durata_ore', DURATA_CORSO_DEFAULT_ORE)
    if not valore:
        return durata_default
    try:
        durata = float(valore.replace(',', '.'))
    except ValueError:
        return durata_default
    if durata <= 0 or durata > 12:
        return durata_default
    return durata


def crea_o_aggiorna_evento_calendario(appuntamento):
    """Crea l'evento su Google Calendar per un appuntamento appena confermato,
    oppure aggiorna orario/contenuto se esiste già (es. dopo uno spostamento).
    Non blocca mai il flusso dell'admin: eventuali errori vengono registrati."""
    calendar_id = app.config.get('GOOGLE_CALENDAR_ID')
    servizio = _ottieni_servizio_calendario()
    if not calendar_id:
        logger.warning('>>> Scrittura Google Calendar non configurata: GOOGLE_CALENDAR_ID mancante.')
        registra_evento(
            'google_calendar',
            'avviso',
            'Evento appuntamento non creato: GOOGLE_CALENDAR_ID mancante.',
            'Appuntamento',
            appuntamento.id,
        )
        return False
    if servizio is None:
        registra_evento(
            'google_calendar',
            'errore',
            'Evento appuntamento non creato: servizio Google Calendar non disponibile.',
            'Appuntamento',
            appuntamento.id,
        )
        return False

    corpo = _corpo_evento_da_appuntamento(appuntamento)
    try:
        if appuntamento.google_event_id:
            servizio.events().patch(
                calendarId=calendar_id,
                eventId=appuntamento.google_event_id,
                body=corpo
            ).execute()
            logger.info(f'>>> Evento Google Calendar aggiornato per appuntamento {appuntamento.id}.')
            registra_evento(
                'google_calendar',
                'successo',
                'Evento Google Calendar aggiornato per appuntamento confermato.',
                'Appuntamento',
                appuntamento.id,
                {'google_event_id': appuntamento.google_event_id},
            )
        else:
            evento_creato = servizio.events().insert(calendarId=calendar_id, body=corpo).execute()
            appuntamento.google_event_id = evento_creato.get('id')
            db.session.commit()
            logger.info(f'>>> Evento Google Calendar creato per appuntamento {appuntamento.id}.')
            registra_evento(
                'google_calendar',
                'successo',
                'Evento Google Calendar creato per appuntamento confermato.',
                'Appuntamento',
                appuntamento.id,
                {'google_event_id': appuntamento.google_event_id},
            )
        return True
    except HttpError as e:
        logger.error(f'>>> Errore nella scrittura su Google Calendar per appuntamento {appuntamento.id}: {e}', exc_info=True)
        registra_evento(
            'google_calendar',
            'errore',
            'Errore Google Calendar durante la sincronizzazione di un appuntamento.',
            'Appuntamento',
            appuntamento.id,
            {'errore': str(e)},
        )
    except Exception as e:
        logger.error(f'>>> Errore imprevisto nella scrittura su Google Calendar: {e}', exc_info=True)
        registra_evento(
            'google_calendar',
            'errore',
            'Errore imprevisto durante la sincronizzazione Calendar di un appuntamento.',
            'Appuntamento',
            appuntamento.id,
            {'errore': str(e)},
        )
    return False


def _corpo_evento_da_call_sonno(call):
    inizio, fine = _intervallo_locale(call.data, call.ora, BLOCCO_CALL_SONNO_MINUTI)
    in_attesa = call.stato == 'In attesa'
    return {
        'summary': f'Call sonno{" (da confermare)" if in_attesa else ""}: {call.nome}',
        'description': (
            f'Telefono: {call.telefono}\n'
            f'Email: {call.email}\n'
            f'Stato: {call.stato}\n'
            f'(Richiesta dal sito web)'
        ),
        'start': {'dateTime': inizio.isoformat(), 'timeZone': 'Europe/Rome'},
        'end': {'dateTime': fine.isoformat(), 'timeZone': 'Europe/Rome'},
        'status': 'tentative' if in_attesa else 'confirmed',
        'transparency': 'opaque',
    }


def crea_o_aggiorna_evento_calendario_call_sonno(call):
    """Blocca subito la call su Calendar; il salvataggio DB resta prioritario."""
    calendar_id = app.config.get('GOOGLE_CALENDAR_ID')
    servizio = _ottieni_servizio_calendario()
    if not calendar_id or servizio is None:
        registra_evento(
            'google_calendar',
            'avviso',
            'Call sonno salvata, ma il blocco su Google Calendar non è stato creato.',
            'CallSonno',
            call.id,
        )
        return False
    corpo = _corpo_evento_da_call_sonno(call)
    try:
        if call.google_event_id:
            servizio.events().patch(
                calendarId=calendar_id,
                eventId=call.google_event_id,
                body=corpo,
            ).execute()
        else:
            evento = servizio.events().insert(calendarId=calendar_id, body=corpo).execute()
            call.google_event_id = evento.get('id')
            db.session.commit()
        _cache_calendario['scaricato_il'] = 0
        registra_evento(
            'google_calendar',
            'successo',
            'Call sonno sincronizzata su Google Calendar.',
            'CallSonno',
            call.id,
            {'google_event_id': call.google_event_id},
        )
        return True
    except Exception as errore:
        logger.error(f'>>> Errore Calendar per call sonno {call.id}: {errore}', exc_info=True)
        registra_evento(
            'google_calendar',
            'errore',
            'Errore durante la sincronizzazione Calendar della call sonno.',
            'CallSonno',
            call.id,
            {'errore': str(errore)},
        )
        return False


def elimina_evento_calendario_call_sonno(call):
    if not call.google_event_id:
        return True
    calendar_id = app.config.get('GOOGLE_CALENDAR_ID')
    servizio = _ottieni_servizio_calendario()
    if not calendar_id or servizio is None:
        registra_evento(
            'google_calendar',
            'errore',
            'Call annullata, ma il blocco non è stato rimosso da Google Calendar.',
            'CallSonno',
            call.id,
        )
        return False
    try:
        servizio.events().delete(calendarId=calendar_id, eventId=call.google_event_id).execute()
        call.google_event_id = None
        db.session.commit()
        _cache_calendario['scaricato_il'] = 0
        return True
    except HttpError as errore:
        if getattr(errore, 'status_code', None) not in (404, 410):
            registra_evento('google_calendar', 'errore', 'Errore eliminazione call sonno da Calendar.', 'CallSonno', call.id, {'errore': str(errore)})
            return False
        call.google_event_id = None
        db.session.commit()
        return True
    except Exception as errore:
        registra_evento('google_calendar', 'errore', 'Errore eliminazione call sonno da Calendar.', 'CallSonno', call.id, {'errore': str(errore)})
        return False


def crea_o_aggiorna_evento_calendario_corso(corso):
    """Crea o aggiorna l'evento Google Calendar collegato a un corso admin.
    Non blocca mai l'area admin: eventuali errori vengono registrati."""
    calendar_id = app.config.get('GOOGLE_CALENDAR_ID')
    servizio = _ottieni_servizio_calendario()
    if not calendar_id:
        logger.warning('>>> Scrittura Google Calendar non configurata: GOOGLE_CALENDAR_ID mancante.')
        registra_evento(
            'google_calendar',
            'avviso',
            'Evento corso non creato: GOOGLE_CALENDAR_ID mancante.',
            'Corso',
            corso.id,
        )
        return False
    if servizio is None:
        registra_evento(
            'google_calendar',
            'errore',
            'Evento corso non creato: servizio Google Calendar non disponibile.',
            'Corso',
            corso.id,
        )
        return False

    corpo = _corpo_evento_da_corso(corso)
    try:
        if corso.google_event_id:
            servizio.events().patch(
                calendarId=calendar_id,
                eventId=corso.google_event_id,
                body=corpo
            ).execute()
            logger.info(f'>>> Evento Google Calendar aggiornato per corso {corso.id}.')
            registra_evento(
                'google_calendar',
                'successo',
                'Evento Google Calendar aggiornato per corso.',
                'Corso',
                corso.id,
                {'google_event_id': corso.google_event_id},
            )
        else:
            evento_creato = servizio.events().insert(calendarId=calendar_id, body=corpo).execute()
            corso.google_event_id = evento_creato.get('id')
            db.session.commit()
            logger.info(f'>>> Evento Google Calendar creato per corso {corso.id}.')
            registra_evento(
                'google_calendar',
                'successo',
                'Evento Google Calendar creato per corso.',
                'Corso',
                corso.id,
                {'google_event_id': corso.google_event_id},
            )
        return True
    except HttpError as e:
        logger.error(f'>>> Errore nella scrittura su Google Calendar per corso {corso.id}: {e}', exc_info=True)
        registra_evento(
            'google_calendar',
            'errore',
            'Errore Google Calendar durante la sincronizzazione di un corso.',
            'Corso',
            corso.id,
            {'errore': str(e)},
        )
    except Exception as e:
        logger.error(f'>>> Errore imprevisto nella scrittura su Google Calendar per corso: {e}', exc_info=True)
        registra_evento(
            'google_calendar',
            'errore',
            'Errore imprevisto durante la sincronizzazione Calendar di un corso.',
            'Corso',
            corso.id,
            {'errore': str(e)},
        )
    return False


def elimina_evento_calendario(appuntamento):
    """Elimina l'evento Google Calendar collegato a un appuntamento (se esiste),
    ad esempio quando l'appuntamento viene annullato."""
    calendar_id = app.config.get('GOOGLE_CALENDAR_ID')
    servizio = _ottieni_servizio_calendario()
    if not appuntamento.google_event_id:
        return True
    if not calendar_id or servizio is None:
        registra_evento(
            'google_calendar',
            'errore',
            'Evento appuntamento non eliminato da Calendar: configurazione o servizio non disponibile.',
            'Appuntamento',
            appuntamento.id,
            {'google_event_id': appuntamento.google_event_id},
        )
        return False

    eliminato = False
    try:
        servizio.events().delete(calendarId=calendar_id, eventId=appuntamento.google_event_id).execute()
        eliminato = True
        registra_evento(
            'google_calendar',
            'successo',
            'Evento Google Calendar eliminato per appuntamento annullato.',
            'Appuntamento',
            appuntamento.id,
            {'google_event_id': appuntamento.google_event_id},
        )
    except HttpError as e:
        # Se l'evento è già stato cancellato manualmente su Google Calendar,
        # l'API risponde 410/404: non è un errore su cui allarmarsi.
        if getattr(e, 'status_code', None) not in (404, 410):
            logger.error(f'>>> Errore nell\'eliminazione dell\'evento Google Calendar per appuntamento {appuntamento.id}: {e}', exc_info=True)
            registra_evento(
                'google_calendar',
                'errore',
                'Errore Google Calendar durante l\'eliminazione di un appuntamento.',
                'Appuntamento',
                appuntamento.id,
                {'errore': str(e), 'google_event_id': appuntamento.google_event_id},
            )
            return False
        registra_evento(
            'google_calendar',
            'avviso',
            'Evento appuntamento già assente da Google Calendar.',
            'Appuntamento',
            appuntamento.id,
            {'google_event_id': appuntamento.google_event_id},
        )
        eliminato = True
    except Exception as e:
        logger.error(f'>>> Errore imprevisto nell\'eliminazione dell\'evento Google Calendar: {e}', exc_info=True)
        registra_evento(
            'google_calendar',
            'errore',
            'Errore imprevisto durante l\'eliminazione Calendar di un appuntamento.',
            'Appuntamento',
            appuntamento.id,
            {'errore': str(e), 'google_event_id': appuntamento.google_event_id},
        )
        return False

    if eliminato:
        appuntamento.google_event_id = None
        db.session.commit()
    return eliminato


def elimina_evento_calendario_corso(corso):
    """Elimina l'evento Google Calendar collegato a un corso (se esiste)."""
    calendar_id = app.config.get('GOOGLE_CALENDAR_ID')
    servizio = _ottieni_servizio_calendario()
    if not corso.google_event_id:
        return True
    if not calendar_id or servizio is None:
        registra_evento(
            'google_calendar',
            'errore',
            'Evento corso non eliminato da Calendar: configurazione o servizio non disponibile.',
            'Corso',
            corso.id,
            {'google_event_id': corso.google_event_id},
        )
        return False

    eliminato = False
    try:
        servizio.events().delete(calendarId=calendar_id, eventId=corso.google_event_id).execute()
        eliminato = True
        registra_evento(
            'google_calendar',
            'successo',
            'Evento Google Calendar eliminato per corso.',
            'Corso',
            corso.id,
            {'google_event_id': corso.google_event_id},
        )
    except HttpError as e:
        if getattr(e, 'status_code', None) not in (404, 410):
            logger.error(f'>>> Errore nell\'eliminazione dell\'evento Google Calendar per corso {corso.id}: {e}', exc_info=True)
            registra_evento(
                'google_calendar',
                'errore',
                'Errore Google Calendar durante l\'eliminazione di un corso.',
                'Corso',
                corso.id,
                {'errore': str(e), 'google_event_id': corso.google_event_id},
            )
            return False
        registra_evento(
            'google_calendar',
            'avviso',
            'Evento corso già assente da Google Calendar.',
            'Corso',
            corso.id,
            {'google_event_id': corso.google_event_id},
        )
        eliminato = True
    except Exception as e:
        logger.error(f'>>> Errore imprevisto nell\'eliminazione dell\'evento Google Calendar per corso: {e}', exc_info=True)
        registra_evento(
            'google_calendar',
            'errore',
            'Errore imprevisto durante l\'eliminazione Calendar di un corso.',
            'Corso',
            corso.id,
            {'errore': str(e), 'google_event_id': corso.google_event_id},
        )
        return False

    if eliminato:
        corso.google_event_id = None
        db.session.commit()
    return eliminato


# ─── MODELLI DATABASE ───

class Admin(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)


class Appuntamento(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    telefono = db.Column(db.String(20), nullable=False)
    email = db.Column(db.String(100), nullable=False)
    servizio = db.Column(db.String(100), nullable=False)
    data = db.Column(db.String(20), nullable=False)
    ora = db.Column(db.String(10), nullable=False)
    note = db.Column(db.Text, nullable=True)
    stato = db.Column(db.String(20), default='In attesa')
    creato_il = db.Column(db.DateTime, default=datetime.now)
    # ID dell'evento creato su Google Calendar quando l'appuntamento viene
    # confermato (None se non ancora confermato, o se la scrittura su
    # Google Calendar non è configurata/è fallita).
    google_event_id = db.Column(db.String(255), nullable=True)


class CallSonno(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    telefono = db.Column(db.String(20), nullable=False)
    email = db.Column(db.String(100), nullable=False)
    eta_bambino_mesi = db.Column(db.Integer, nullable=False)
    difficolta_principale = db.Column(db.String(120), nullable=False)
    difficolta_altro = db.Column(db.String(300), nullable=True)
    consenso_privacy = db.Column(db.Boolean, default=False, nullable=False)
    data = db.Column(db.String(20), nullable=False, index=True)
    ora = db.Column(db.String(10), nullable=False)
    stato = db.Column(db.String(20), default='In attesa', nullable=False, index=True)
    google_event_id = db.Column(db.String(255), nullable=True)
    formula_scelta = db.Column(db.String(30), nullable=True)
    token_questionario = db.Column(db.String(96), unique=True, nullable=True, index=True)
    questionario_inviato_il = db.Column(db.DateTime, nullable=True)
    creato_il = db.Column(db.DateTime, default=datetime.now, nullable=False)
    aggiornato_il = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now, nullable=False)


class QuestionarioSonno(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    call_sonno_id = db.Column(db.Integer, db.ForeignKey('call_sonno.id'), unique=True, nullable=False)
    risposte = db.Column(db.Text, nullable=False)
    consenso_dati_sanitari = db.Column(db.Boolean, default=False, nullable=False)
    consenso_marketing = db.Column(db.Boolean, default=False, nullable=False)
    compilato_il = db.Column(db.DateTime, default=datetime.now, nullable=False)
    call_sonno = db.relationship(
        'CallSonno',
        backref=db.backref('questionario', uselist=False, cascade='all, delete-orphan'),
    )

    def risposte_dict(self):
        try:
            return json.loads(self.risposte)
        except (TypeError, json.JSONDecodeError):
            return {}


class Corso(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    titolo = db.Column(db.String(200), nullable=False)
    tipo = db.Column(db.String(100), nullable=True)
    descrizione = db.Column(db.Text, nullable=True)
    data = db.Column(db.String(20), nullable=False)
    ora = db.Column(db.String(10), nullable=True)
    luogo = db.Column(db.String(200), nullable=True)
    durata_ore = db.Column(db.Float, default=DURATA_CORSO_DEFAULT_ORE, nullable=False)
    capienza_massima = db.Column(db.Integer, nullable=True)
    stato = db.Column(db.String(20), default='Aperto', nullable=False)
    creato_il = db.Column(db.DateTime, default=datetime.now)
    google_event_id = db.Column(db.String(255), nullable=True)


class PersonaCorso(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    telefono = db.Column(db.String(20), nullable=False)
    email = db.Column(db.String(100), nullable=True)
    codice_fiscale = db.Column(db.String(32), nullable=True)
    nome_bambino = db.Column(db.String(100), nullable=True)
    eta_bambino = db.Column(db.String(40), nullable=True)
    note = db.Column(db.Text, nullable=True)
    creato_il = db.Column(db.DateTime, default=datetime.now)
    aggiornato_il = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)


class PercorsoAccompagnamento(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    titolo = db.Column(db.String(200), nullable=False)
    slug = db.Column(db.String(120), unique=True, nullable=False)
    descrizione = db.Column(db.Text, nullable=True)
    capienza_coppie = db.Column(db.Integer, nullable=True)
    luogo = db.Column(db.String(200), nullable=True)
    contatti = db.Column(db.String(200), default='3806317175', nullable=True)
    stato = db.Column(db.String(20), default='Aperto', nullable=False)
    creato_il = db.Column(db.DateTime, default=datetime.now)


class IncontroAccompagnamento(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    percorso_id = db.Column(db.Integer, db.ForeignKey('percorso_accompagnamento.id'), nullable=False)
    numero = db.Column(db.Integer, nullable=False)
    data = db.Column(db.String(20), nullable=False)
    ora = db.Column(db.String(10), nullable=True)
    professionista = db.Column(db.String(100), nullable=False)
    tema = db.Column(db.String(200), nullable=False)
    luogo = db.Column(db.String(200), nullable=True)
    note = db.Column(db.Text, nullable=True)
    creato_il = db.Column(db.DateTime, default=datetime.now)
    percorso = db.relationship('PercorsoAccompagnamento', backref=db.backref('incontri', lazy=True, cascade='all, delete-orphan'))


class IscrizioneCorso(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    corso_id = db.Column(db.Integer, db.ForeignKey('corso.id'), nullable=True)
    persona_id = db.Column(db.Integer, db.ForeignKey('persona_corso.id'), nullable=True)
    percorso_accompagnamento_id = db.Column(db.Integer, db.ForeignKey('percorso_accompagnamento.id'), nullable=True)
    corso_tipo = db.Column(db.String(80), nullable=False)
    corso_titolo = db.Column(db.String(200), nullable=False)
    nome = db.Column(db.String(100), nullable=False)
    telefono = db.Column(db.String(20), nullable=False)
    email = db.Column(db.String(100), nullable=True)
    codice_fiscale = db.Column(db.String(32), nullable=False)
    data_corso = db.Column(db.String(20), nullable=True)
    partecipazione = db.Column(db.String(100), nullable=True)
    note = db.Column(db.Text, nullable=True)
    dati_extra = db.Column(db.Text, nullable=True)
    tipo_richiesta = db.Column(db.String(40), default='richiesta_iscrizione', nullable=False)
    posti = db.Column(db.Integer, default=1, nullable=False)
    consenso_privacy = db.Column(db.Boolean, default=False, nullable=False)
    consenso_immagini = db.Column(db.Boolean, default=False, nullable=False)
    stato = db.Column(db.String(20), default='Nuova', nullable=False)
    creato_il = db.Column(db.DateTime, default=datetime.now)
    corso = db.relationship('Corso', backref=db.backref('iscrizioni', lazy=True))
    persona = db.relationship('PersonaCorso', backref=db.backref('iscrizioni', lazy=True))
    percorso_accompagnamento = db.relationship(
        'PercorsoAccompagnamento',
        backref=db.backref('iscrizioni', lazy=True)
    )

    def extra_dict(self):
        if not self.dati_extra:
            return {}
        try:
            return json.loads(self.dati_extra)
        except json.JSONDecodeError:
            return {}


class PresenzaAccompagnamento(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    iscrizione_id = db.Column(db.Integer, db.ForeignKey('iscrizione_corso.id'), nullable=False)
    incontro_id = db.Column(db.Integer, db.ForeignKey('incontro_accompagnamento.id'), nullable=False)
    presente = db.Column(db.Boolean, nullable=True)
    note = db.Column(db.Text, nullable=True)
    aggiornata_il = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)
    iscrizione = db.relationship('IscrizioneCorso', backref=db.backref('presenze_accompagnamento', lazy=True))
    incontro = db.relationship('IncontroAccompagnamento', backref=db.backref('presenze', lazy=True))


class RegistroEvento(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    categoria = db.Column(db.String(40), nullable=False, index=True)
    esito = db.Column(db.String(20), nullable=False, default='info', index=True)
    messaggio = db.Column(db.Text, nullable=False)
    entita_tipo = db.Column(db.String(80), nullable=True, index=True)
    entita_id = db.Column(db.Integer, nullable=True, index=True)
    dettagli = db.Column(db.Text, nullable=True)
    creato_il = db.Column(db.DateTime, default=datetime.now, index=True)

    def dettagli_dict(self):
        if not self.dettagli:
            return {}
        try:
            return json.loads(self.dettagli)
        except json.JSONDecodeError:
            return {}


def registra_evento(categoria, esito, messaggio, entita_tipo=None, entita_id=None, dettagli=None):
    """Registra un evento operativo senza interrompere il flusso principale."""
    try:
        evento = RegistroEvento(
            categoria=categoria,
            esito=esito,
            messaggio=messaggio,
            entita_tipo=entita_tipo,
            entita_id=entita_id,
            dettagli=json.dumps(dettagli, ensure_ascii=False) if dettagli else None,
        )
        db.session.add(evento)
        db.session.commit()
        return evento
    except Exception as errore:
        db.session.rollback()
        logger.error(f'>>> Impossibile registrare evento operativo: {errore}', exc_info=True)
        return None


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(Admin, int(user_id))


def _intervallo_locale(data_str, ora, durata_minuti):
    giorno = datetime.strptime(data_str, '%Y-%m-%d').date()
    ore, minuti = map(int, ora.split(':'))
    inizio = datetime.combine(giorno, datetime.min.time(), tzinfo=FUSO_ORARIO).replace(
        hour=ore,
        minute=minuti,
    )
    return inizio, inizio + timedelta(minutes=durata_minuti)


def _intervalli_si_sovrappongono(primo, secondo):
    return primo[0] < secondo[1] and secondo[0] < primo[1]


def _giorno_lavorativo_call(giorno):
    return giorno.weekday() < 5 and not is_festivo(giorno)


def prima_data_call_disponibile(da_giorno=None):
    candidato = (da_giorno or date.today()) + timedelta(days=1)
    while not _giorno_lavorativo_call(candidato):
        candidato += timedelta(days=1)
    return candidato


def orario_call_prenotabile(data_str, ora):
    try:
        giorno = datetime.strptime(data_str, '%Y-%m-%d').date()
    except ValueError:
        return False
    return (
        ora in ORARI_CALL_SONNO
        and _giorno_lavorativo_call(giorno)
        and giorno >= prima_data_call_disponibile()
    )


def slot_occupato_db(data_str, ora, durata_minuti, ignore_call_id=None, ignore_appuntamento_id=None):
    """Controlla sovrapposizioni con prestazioni, call e corsi salvati."""
    try:
        intervallo_richiesto = _intervallo_locale(data_str, ora, durata_minuti)
    except (ValueError, TypeError):
        return True

    appuntamenti_query = Appuntamento.query.filter(
        Appuntamento.data == data_str,
        Appuntamento.stato != 'Annullato',
    )
    if ignore_appuntamento_id is not None:
        appuntamenti_query = appuntamenti_query.filter(Appuntamento.id != ignore_appuntamento_id)
    for appuntamento in appuntamenti_query.all():
        if _intervalli_si_sovrappongono(
            intervallo_richiesto,
            _intervallo_locale(appuntamento.data, appuntamento.ora, DURATA_SLOT_MINUTI),
        ):
            return True

    call_query = CallSonno.query.filter(
        CallSonno.data == data_str,
        CallSonno.stato != 'Annullata',
    )
    if ignore_call_id is not None:
        call_query = call_query.filter(CallSonno.id != ignore_call_id)
    for call in call_query.all():
        if _intervalli_si_sovrappongono(
            intervallo_richiesto,
            _intervallo_locale(call.data, call.ora, BLOCCO_CALL_SONNO_MINUTI),
        ):
            return True

    corsi = Corso.query.filter(Corso.data == data_str, Corso.stato != 'Annullato').all()
    for corso in corsi:
        if not corso.ora:
            return True
        durata = int((corso.durata_ore or DURATA_CORSO_DEFAULT_ORE) * 60)
        if _intervalli_si_sovrappongono(
            intervallo_richiesto,
            _intervallo_locale(corso.data, corso.ora, durata),
        ):
            return True
    return False


# ─── INIZIALIZZAZIONE DATABASE ───
# Questo blocco viene eseguito sia con flask run che con python3 app.py

with app.app_context():
    db.create_all()
    if not Admin.query.first():
        admin_utente = Admin(
            username='admin',
            password=generate_password_hash('cambiami123')
        )
        db.session.add(admin_utente)
        db.session.commit()
        logger.info('>>> Admin creato con credenziali di default. Cambiare la password al primo accesso.')
    else:
        logger.info('>>> Database OK — Admin esistente')


# ─── EMAIL ───

def invia_email_ricezione_call_sonno(call):
    try:
        msg = Message(
            subject='Richiesta call sonno ricevuta - attendi la conferma',
            recipients=[call.email],
            body=(
                f'Gentile {call.nome},\n\n'
                f'ho ricevuto la tua richiesta per la call gratuita sul sonno.\n\n'
                f'Data richiesta: {call.data}\n'
                f'Orario richiesto: {call.ora}\n'
                f'Durata indicativa: circa {DURATA_CALL_SONNO_MINUTI} minuti\n\n'
                f'Lo slot è riservato provvisoriamente, ma la call non è ancora confermata. '
                f'Attendi la mia email di conferma prima di considerare fissato l’appuntamento. '
                f'Ti confermerò lo slot oppure ti contatterò per concordare un orario diverso '
                f'entro il giorno lavorativo successivo.\n\n'
                f'S.C. Studio Infermieristico'
            ),
        )
        mail.send(msg)
        return True
    except Exception as errore:
        registra_evento('email', 'errore', 'Email ricezione call sonno non inviata.', 'CallSonno', call.id, {'errore': str(errore)})
        return False


def invia_email_alert_call_sonno(call):
    try:
        msg = Message(
            subject=f'Nuova call sonno da confermare - {call.nome}',
            recipients=['sc.studioinfermieristico@gmail.com'],
            body=(
                f'Nuova richiesta di call sonno.\n\n'
                f'Nome: {call.nome}\nTelefono: {call.telefono}\nEmail: {call.email}\n'
                f'Età bambino: {call.eta_bambino_mesi} mesi\n'
                f'Difficoltà: {call.difficolta_altro or call.difficolta_principale}\n'
                f'Quando: {call.data} alle {call.ora}\n\n'
                f'Lo slot è stato bloccato provvisoriamente. Gestiscilo dall’area admin.'
            ),
        )
        mail.send(msg)
        return True
    except Exception as errore:
        registra_evento('email', 'errore', 'Email alert call sonno non inviata allo studio.', 'CallSonno', call.id, {'errore': str(errore)})
        return False


def invia_email_conferma_call_sonno(call, modificata=False):
    try:
        call_url = app.config.get('SONNO_CALL_URL')
        istruzioni = (
            f'Collegamento per la call: {call_url}\n'
            if call_url
            else 'Ti comunicherò la modalità di collegamento prima della call.\n'
        )
        msg = Message(
            subject='Call sonno confermata - S.C. Studio Infermieristico',
            recipients=[call.email],
            body=(
                f'Gentile {call.nome},\n\n'
                f'la tua call gratuita è {"stata riprogrammata e " if modificata else ""}confermata.\n\n'
                f'Data: {call.data}\nOra: {call.ora}\nDurata indicativa: circa {DURATA_CALL_SONNO_MINUTI} minuti\n'
                f'{istruzioni}\n'
                f'Prima della call non devi compilare altri moduli.\n\n'
                f'Per necessità puoi contattarmi al 3806317175.\n\n'
                f'S.C. Studio Infermieristico'
            ),
        )
        mail.send(msg)
        return True
    except Exception as errore:
        registra_evento('email', 'errore', 'Email conferma call sonno non inviata.', 'CallSonno', call.id, {'errore': str(errore)})
        return False


def invia_email_annullamento_call_sonno(call):
    try:
        mail.send(Message(
            subject='Call sonno annullata - S.C. Studio Infermieristico',
            recipients=[call.email],
            body=(
                f'Gentile {call.nome},\n\nla call richiesta per il {call.data} alle {call.ora} '
                f'è stata annullata. Per fissare un nuovo momento puoi contattarmi al 3806317175.\n\n'
                f'S.C. Studio Infermieristico'
            ),
        ))
        return True
    except Exception as errore:
        registra_evento('email', 'errore', 'Email annullamento call sonno non inviata.', 'CallSonno', call.id, {'errore': str(errore)})
        return False


def invia_email_questionario_sonno(call):
    try:
        link = url_for('questionario_sonno', token=call.token_questionario, _external=True)
        formula = FORMULE_SONNO.get(call.formula_scelta, 'percorso scelto')
        mail.send(Message(
            subject='Il questionario per iniziare il percorso sul sonno',
            recipients=[call.email],
            body=(
                f'Gentile {call.nome},\n\ncome concordato dopo la call, puoi compilare il questionario '
                f'riservato per {formula}. Le risposte mi permetteranno di preparare il lavoro sulla vostra situazione reale.\n\n'
                f'Compila il questionario: {link}\n\n'
                f'Il collegamento è personale: non inoltrarlo. Se hai dubbi, scrivimi su WhatsApp.\n\n'
                f'S.C. Studio Infermieristico'
            ),
        ))
        return True
    except Exception as errore:
        registra_evento('email', 'errore', 'Email questionario sonno non inviata.', 'CallSonno', call.id, {'errore': str(errore)})
        return False


def invia_email_conferma(appuntamento):
    """Invia email di conferma al paziente dopo la conferma dell'appuntamento."""
    try:
        logger.info(f'>>> Invio email conferma a {appuntamento.email}...')
        msg = Message(
            subject='Appuntamento confermato - S.C. Studio Infermieristico',
            recipients=[appuntamento.email],
            body=(
                f'Gentile {appuntamento.nome},\n\n'
                f'il tuo appuntamento è stato confermato.\n\n'
                f'Servizio: {appuntamento.servizio}\n'
                f'Data:     {appuntamento.data}\n'
                f'Ora:      {appuntamento.ora}\n\n'
                f'Per qualsiasi necessità puoi contattarmi al numero 3806317175.\n\n'
                f'A presto,\n'
                f'S.C. Studio Infermieristico'
            )
        )
        mail.send(msg)
        logger.info('>>> Email conferma inviata con successo!')
        return True
    except Exception as e:
        logger.error(f'>>> Errore invio email conferma: {e}', exc_info=True)
        registra_evento('email', 'errore', 'Email di conferma appuntamento non inviata.', 'Appuntamento', appuntamento.id, {'errore': str(e)})
        return False


def invia_email_spostamento(appuntamento):
    """Invia email di notifica quando un appuntamento viene riprogrammato."""
    try:
        logger.info(f'>>> Invio email spostamento a {appuntamento.email}...')
        msg = Message(
            subject='Appuntamento spostato - S.C. Studio Infermieristico',
            recipients=[appuntamento.email],
            body=(
                f'Gentile {appuntamento.nome},\n\n'
                f'ti informo che il tuo appuntamento è stato spostato '
                f'alle seguenti nuove data e ora:\n\n'
                f'Servizio:     {appuntamento.servizio}\n'
                f'Nuova data:   {appuntamento.data}\n'
                f'Nuovo orario: {appuntamento.ora}\n\n'
                f'Se hai domande o necessiti di ulteriori modifiche '
                f'puoi contattarmi al numero 3806317175.\n\n'
                f'A presto,\n'
                f'S.C. Studio Infermieristico'
            )
        )
        mail.send(msg)
        logger.info('>>> Email spostamento inviata con successo!')
        return True
    except Exception as e:
        logger.error(f'>>> Errore invio email spostamento: {e}', exc_info=True)
        registra_evento('email', 'errore', 'Email di spostamento appuntamento non inviata.', 'Appuntamento', appuntamento.id, {'errore': str(e)})
        return False


def invia_email_annullamento(appuntamento):
    """Invia email di cancellazione al paziente."""
    try:
        logger.info(f'>>> Invio email annullamento a {appuntamento.email}...')
        msg = Message(
            subject='Appuntamento cancellato - S.C. Studio Infermieristico',
            recipients=[appuntamento.email],
            body=(
                f'Gentile {appuntamento.nome},\n\n'
                f'ti informo che il tuo appuntamento è stato cancellato.\n\n'
                f'Servizio: {appuntamento.servizio}\n'
                f'Data:     {appuntamento.data}\n'
                f'Ora:      {appuntamento.ora}\n\n'
                f'Se desideri fissare un nuovo appuntamento puoi prenotare '
                f'direttamente dal sito o contattarmi al numero 3806317175.\n\n'
                f'Ci scusiamo per l\'inconveniente.\n\n'
                f'A presto,\n'
                f'S.C. Studio Infermieristico'
            )
        )
        mail.send(msg)
        logger.info('>>> Email annullamento inviata con successo!')
        return True
    except Exception as e:
        logger.error(f'>>> Errore invio email annullamento: {e}', exc_info=True)
        registra_evento('email', 'errore', 'Email di annullamento appuntamento non inviata.', 'Appuntamento', appuntamento.id, {'errore': str(e)})
        return False


def invia_email_nuova_prenotazione(appuntamento):
    """Invia email di alert all'amministratore quando viene ricevuta una nuova richiesta di appuntamento."""
    try:
        logger.info('>>> Invio email alert nuova prenotazione...')
        msg = Message(
            subject=f'Nuova prenotazione - {appuntamento.nome}',
            recipients=['sc.studioinfermieristico@gmail.com'],
            body=(
                f'Hai ricevuto una nuova richiesta di appuntamento.\n\n'
                f'Nome:     {appuntamento.nome}\n'
                f'Telefono: {appuntamento.telefono}\n'
                f'Email:    {appuntamento.email}\n'
                f'Servizio: {appuntamento.servizio}\n'
                f'Data:     {appuntamento.data}\n'
                f'Ora:      {appuntamento.ora}\n'
                f'Note:     {appuntamento.note or "Nessuna"}\n\n'
                f'Accedi all\'area admin per gestire la prenotazione.'
            )
        )
        mail.send(msg)
        logger.info('>>> Email alert inviata con successo!')
        return True
    except Exception as e:
        logger.error(f'>>> Errore invio email alert: {e}', exc_info=True)
        registra_evento('email', 'errore', 'Email alert nuova prenotazione non inviata allo studio.', 'Appuntamento', appuntamento.id, {'errore': str(e)})
        return False


def invia_email_nuova_iscrizione(iscrizione):
    """Invia email di alert all'amministratore quando arriva una richiesta di iscrizione corso."""
    try:
        logger.info('>>> Invio email alert nuova iscrizione corso...')
        extra = iscrizione.extra_dict()
        dettagli_extra = ''
        if extra.get('ente_azienda'):
            dettagli_extra += f'Azienda/gruppo: {extra["ente_azienda"]}\n'
        if extra.get('numero_partecipanti'):
            dettagli_extra += f'Partecipanti: {extra["numero_partecipanti"]}\n'
        msg = Message(
            subject=f'Nuova iscrizione corso - {iscrizione.corso_titolo}',
            recipients=['sc.studioinfermieristico@gmail.com'],
            body=(
                f'Hai ricevuto una nuova richiesta di iscrizione corso.\n\n'
                f'Corso:    {iscrizione.corso_titolo}\n'
                f'Nome:     {iscrizione.nome}\n'
                f'Telefono: {iscrizione.telefono}\n'
                f'Email:    {iscrizione.email or "Non indicata"}\n'
                f'Data:     {iscrizione.data_corso or "Da definire"}\n'
                f'Tipo:     {iscrizione.partecipazione or "Non indicato"}\n\n'
                f'{dettagli_extra}'
                f'Accedi all\'area admin per gestire la richiesta.'
            )
        )
        mail.send(msg)
        logger.info('>>> Email alert iscrizione corso inviata con successo!')
        return True
    except Exception as e:
        logger.error(f'>>> Errore invio email alert iscrizione corso: {e}', exc_info=True)
        registra_evento('email', 'errore', 'Email alert iscrizione corso non inviata allo studio.', 'IscrizioneCorso', iscrizione.id, {'errore': str(e)})
        return False


def invia_email_iscrizione_accompagnamento(iscrizione, percorso):
    """Invia conferma alla famiglia per il modulo privato del percorso nascita."""
    if not iscrizione.email:
        return
    try:
        logger.info(f'>>> Invio email conferma percorso accompagnamento a {iscrizione.email}...')
        date_percorso = '\n'.join(_riepilogo_date_percorso(percorso)) or 'Le date verranno comunicate dallo studio.'
        contatti = percorso.contatti or '3806317175'
        msg = Message(
            subject='Iscrizione confermata - Corso di accompagnamento alla nascita',
            recipients=[iscrizione.email],
            body=(
                f'Gentile {iscrizione.nome},\n\n'
                f'la tua iscrizione al corso di accompagnamento alla nascita è confermata.\n\n'
                f'Percorso: {percorso.titolo}\n'
                f'Luogo:    Studio infermieristico\n\n'
                f'Calendario incontri:\n{date_percorso}\n\n'
                f'Per qualsiasi necessità puoi contattarmi al numero {contatti}.\n\n'
                f'A presto,\n'
                f'S.C. Studio Infermieristico'
            )
        )
        mail.send(msg)
        logger.info('>>> Email conferma percorso accompagnamento inviata con successo!')
        return True
    except Exception as e:
        logger.error(f'>>> Errore invio email conferma percorso accompagnamento: {e}', exc_info=True)
        registra_evento('email', 'errore', 'Email conferma percorso accompagnamento non inviata.', 'IscrizioneCorso', iscrizione.id, {'errore': str(e)})
        return False


def invia_email_alert_iscrizione_accompagnamento(iscrizione, percorso):
    """Invia notifica semplice allo studio per una nuova iscrizione confermata."""
    try:
        logger.info('>>> Invio email alert iscrizione percorso accompagnamento...')
        msg = Message(
            subject=f'Nuova iscrizione confermata - {percorso.titolo}',
            recipients=['sc.studioinfermieristico@gmail.com'],
            body=(
                f'Nuova iscrizione confermata al corso di accompagnamento alla nascita.\n\n'
                f'Percorso: {percorso.titolo}\n'
                f'Nome:     {iscrizione.nome}\n'
                f'Telefono: {iscrizione.telefono}\n'
                f'Email:    {iscrizione.email or "Non indicata"}\n\n'
                f'Accedi all\'area admin per vedere i dettagli.'
            )
        )
        mail.send(msg)
        logger.info('>>> Email alert percorso accompagnamento inviata con successo!')
        return True
    except Exception as e:
        logger.error(f'>>> Errore invio email alert percorso accompagnamento: {e}', exc_info=True)
        registra_evento('email', 'errore', 'Email alert percorso accompagnamento non inviata allo studio.', 'IscrizioneCorso', iscrizione.id, {'errore': str(e)})
        return False


def invia_email_ricordo_24h(appuntamento):
    """Invia email di promemoria 24 ore prima dell'appuntamento."""
    try:
        logger.info(f'>>> Invio email ricordo 24h a {appuntamento.email}...')
        msg = Message(
            subject='Ricordo: Appuntamento domani - S.C. Studio Infermieristico',
            recipients=[appuntamento.email],
            body=(
                f'Gentile {appuntamento.nome},\n\n'
                f'Ti ricordo che hai un appuntamento domani:\n\n'
                f'Servizio: {appuntamento.servizio}\n'
                f'Data:     {appuntamento.data}\n'
                f'Ora:      {appuntamento.ora}\n\n'
                f'Se hai bisogno di modificare o cancellare l\'appuntamento, '
                f'puoi contattarmi al numero 3806317175.\n\n'
                f'A presto,\n'
                f'S.C. Studio Infermieristico'
            )
        )
        mail.send(msg)
        logger.info('>>> Email ricordo 24h inviata con successo!')
        return True
    except Exception as e:
        logger.error(f'>>> Errore invio email ricordo 24h: {e}', exc_info=True)
        registra_evento('email', 'errore', 'Email promemoria 24h non inviata.', 'Appuntamento', appuntamento.id, {'errore': str(e)})
        return False


def controlla_e_invia_ricordi_24h():
    """Controlla gli appuntamenti che avvengono nelle prossime 24 ore e invia promemoria."""
    try:
        logger.info('>>> Controllo appuntamenti per invio ricordi 24h...')

        # Calcola la finestra temporale: ora + 24 ore +/- 30 minuti
        adesso = datetime.now()
        target_time = adesso + timedelta(hours=24)
        window_start = target_time - timedelta(minutes=30)
        window_end = target_time + timedelta(minutes=30)

        # Format data per il confronto con i campi stringa nel DB
        target_date = target_time.strftime('%Y-%m-%d')

        # Troviamo gli appuntamenti per la data target e controlliamo se l'ora è nella finestra
        appuntamenti = Appuntamento.query.filter(
            Appuntamento.data == target_date,
            Appuntamento.stato == 'Confermato'
        ).all()

        ricordi_inviati = 0
        for app in appuntamenti:
            try:
                app_datetime = datetime.strptime(f"{app.data} {app.ora}", '%Y-%m-%d %H:%M')
                if window_start <= app_datetime <= window_end:
                    invia_email_ricordo_24h(app)
                    ricordi_inviati += 1
            except ValueError:
                # Salta gli appuntamenti con formato data/ora non valido
                continue

        logger.info(f'> Inviati {ricordi_inviati} ricordi 24h')
    except Exception as e:
        logger.error(f'> Errore in controlla_e_invia_ricordi_24h: {e}', exc_info=True)

# Pianifica il controllo dei promemoria per eseguirlo ogni ora.
#
# Protezioni:
# - Non parte affatto durante i test (TESTING=True), per non inviare email
#   né lasciare thread in background attivi dopo la fine della test suite.
# - Non parte due volte in sviluppo: con `debug=True`, Werkzeug avvia un
#   processo "reloader" che riesegue l'intero modulo in un sottoprocesso.
#   Senza questo controllo, sia il processo padre che quello riavviato
#   registrano e avviano il proprio scheduler, con il risultato di due
#   promemoria 24h duplicati per ogni appuntamento (visibile in app.log
#   come doppio "Scheduler started").
if not app.config.get('TESTING') and (not app.debug or os.environ.get('WERKZEUG_RUN_MAIN') == 'true'):
    scheduler.add_job(
        func=controlla_e_invia_ricordi_24h,
        trigger="interval",
        hours=1,
        id='ricordi_24h_job',
        name='Controllo e invio ricordi 24h',
        replace_existing=True
    )
    scheduler.start()


# ─── PAGINE SITO ───

@app.route('/')
def homepage():
    corsi = Corso.query.order_by(Corso.data).all()
    return render_template('homepage.html', corsi=corsi)


@app.route('/chi-sono')
def chi_siamo():
    return render_template('chi_siamo.html')


@app.route('/faq')
def faq():
    return render_template('faq.html', faq_items=FAQ_ITEMS)


@app.route('/prestazioni-infermieristiche')
def prestazioni():
    return render_template(
        'prestazioni_infermieristiche.html',
        studio_map_embed_src=STUDIO_MAP_EMBED_SRC,
        studio_map_link=STUDIO_MAP_LINK,
    )


@app.route('/prima-della-nascita')
def prima_della_nascita():
    return render_template('prima_della_nascita.html')


@app.route('/dopo-la-nascita')
def dopo_la_nascita():
    return render_template('dopo_la_nascita.html')


@app.route('/consulenze-online')
def consulenze_online():
    return render_template('consulenze_online.html')


def _email_valida(email):
    return re.match(r'^[\w\.-]+@[\w\.-]+\.\w+$', email) is not None


def _telefono_valido(telefono):
    return re.match(r'^[\d\s\+\-\(\)]{7,20}$', telefono) is not None


def _normalizza_telefono(telefono):
    return re.sub(r'\D+', '', telefono or '')


def _checkbox_checked(field_name):
    return request.form.get(field_name) in ['on', 'si', 'ACCONSENTO', 'true', '1']


def _posti_iscrizione_da_partecipazione(partecipazione):
    if partecipazione and partecipazione.lower().startswith('coppia'):
        return 2
    return 1


def _tipo_richiesta_da_corso(corso_tipo, corso_id):
    if not corso_id:
        return 'ricontatto'
    if corso_tipo == 'accompagnamento-nascita':
        return 'open_day'
    return 'richiesta_iscrizione'


def _label_tipo_richiesta(tipo_richiesta):
    return TIPI_RICHIESTA_CORSO.get(tipo_richiesta, tipo_richiesta or 'Richiesta')


def _persona_corso_da_contatti(telefono='', email=''):
    email_normalizzata = (email or '').strip().lower()
    telefono_normalizzato = _normalizza_telefono(telefono)

    if email_normalizzata:
        persona = PersonaCorso.query.filter(db.func.lower(PersonaCorso.email) == email_normalizzata).first()
        if persona:
            return persona

    if telefono_normalizzato:
        for persona in PersonaCorso.query.filter(PersonaCorso.telefono.isnot(None)).all():
            if _normalizza_telefono(persona.telefono) == telefono_normalizzato:
                return persona
    return None


def _aggiorna_persona_corso(persona, nome='', telefono='', email='', codice_fiscale='',
                            nome_bambino='', eta_bambino='', note=''):
    if nome:
        persona.nome = nome
    if telefono:
        persona.telefono = telefono
    if email:
        persona.email = email
    if codice_fiscale:
        persona.codice_fiscale = codice_fiscale
    if nome_bambino:
        persona.nome_bambino = nome_bambino
    if eta_bambino:
        persona.eta_bambino = eta_bambino
    if note:
        if persona.note and note not in persona.note:
            persona.note = f'{persona.note}\n{note}'
        elif not persona.note:
            persona.note = note
    return persona


def _trova_o_crea_persona_corso(nome, telefono, email='', codice_fiscale='',
                                nome_bambino='', eta_bambino='', note=''):
    persona = _persona_corso_da_contatti(telefono=telefono, email=email)
    if persona:
        return _aggiorna_persona_corso(
            persona,
            nome=nome,
            telefono=telefono,
            email=email,
            codice_fiscale=codice_fiscale,
            nome_bambino=nome_bambino,
            eta_bambino=eta_bambino,
            note=note
        )

    persona = PersonaCorso(
        nome=nome,
        telefono=telefono,
        email=email or None,
        codice_fiscale=codice_fiscale or None,
        nome_bambino=nome_bambino or None,
        eta_bambino=eta_bambino or None,
        note=note or None,
    )
    db.session.add(persona)
    return persona


def _slugify(value):
    value = (value or '').strip().lower()
    value = re.sub(r'[^a-z0-9]+', '-', value)
    value = value.strip('-')
    return value or f'percorso-{secrets.token_hex(4)}'


def _slug_unico_percorso(base_slug):
    slug = _slugify(base_slug)
    candidate = slug
    counter = 2
    while PercorsoAccompagnamento.query.filter_by(slug=candidate).first():
        candidate = f'{slug}-{counter}'
        counter += 1
    return candidate


def _incontri_percorso(percorso):
    return sorted(percorso.incontri, key=lambda incontro: (incontro.numero or 0, incontro.data or '', incontro.ora or ''))


def _iscrizioni_percorso(percorso):
    return IscrizioneCorso.query.filter(
        IscrizioneCorso.percorso_accompagnamento_id == percorso.id,
        IscrizioneCorso.stato != 'Annullato'
    ).order_by(IscrizioneCorso.creato_il.desc()).all()


def _posti_liberi_percorso(percorso):
    if not percorso.capienza_coppie:
        return None
    iscritti = IscrizioneCorso.query.filter(
        IscrizioneCorso.percorso_accompagnamento_id == percorso.id,
        IscrizioneCorso.stato != 'Annullato'
    ).count()
    return max(percorso.capienza_coppie - iscritti, 0)


def _percorso_ha_posto(percorso):
    posti_liberi = _posti_liberi_percorso(percorso)
    return posti_liberi is None or posti_liberi > 0


def _riepilogo_date_percorso(percorso):
    righe = []
    for incontro in _incontri_percorso(percorso):
        data = _formatta_data_corso(incontro.data)
        ora = f' ore {incontro.ora}' if incontro.ora else ''
        luogo_testo = ' - Studio infermieristico'
        righe.append(
            f'{incontro.numero}. {data}{ora} - {incontro.professionista}: {incontro.tema}{luogo_testo}'
        )
    return righe


def _panoramica_percorsi_accompagnamento(percorsi):
    panoramica = []
    for percorso in percorsi:
        iscrizioni = _iscrizioni_percorso(percorso)
        incontri = _incontri_percorso(percorso)
        capienza = percorso.capienza_coppie
        posti_liberi = None if capienza is None else max(capienza - len(iscrizioni), 0)
        panoramica.append({
            'percorso': percorso,
            'iscrizioni': iscrizioni,
            'incontri': incontri,
            'iscritti_count': len(iscrizioni),
            'incontri_count': len(incontri),
            'capienza': capienza,
            'posti_liberi': posti_liberi,
        })
    return panoramica


def _presenze_per_percorso(percorso, iscrizioni=None, incontri=None):
    iscrizioni = iscrizioni if iscrizioni is not None else _iscrizioni_percorso(percorso)
    incontri = incontri if incontri is not None else _incontri_percorso(percorso)
    iscrizione_ids = [iscrizione.id for iscrizione in iscrizioni]
    incontro_ids = [incontro.id for incontro in incontri]
    presenze = {}
    if iscrizione_ids and incontro_ids:
        righe = PresenzaAccompagnamento.query.filter(
            PresenzaAccompagnamento.iscrizione_id.in_(iscrizione_ids),
            PresenzaAccompagnamento.incontro_id.in_(incontro_ids)
        ).all()
        presenze = {(p.iscrizione_id, p.incontro_id): p for p in righe}
    return presenze


def _escape_pdf_text(value):
    testo = str(value or '')
    return testo.replace('\\', '\\\\').replace('(', '\\(').replace(')', '\\)')


def _crea_pdf_testuale(titolo, righe):
    righe_pdf = [titolo, ''] + [str(riga) for riga in righe]
    righe_per_pagina = 42
    pagine = [righe_pdf[i:i + righe_per_pagina] for i in range(0, len(righe_pdf), righe_per_pagina)] or [[]]
    objects = [
        b'<< /Type /Catalog /Pages 2 0 R >>',
        None,
        b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>',
    ]
    page_ids = []
    for pagina in pagine:
        page_id = len(objects) + 1
        content_id = page_id + 1
        page_ids.append(page_id)
        commands = ['BT', '/F1 11 Tf', '50 800 Td', '14 TL']
        for riga in pagina:
            commands.append(f'({_escape_pdf_text(riga)}) Tj')
            commands.append('T*')
        commands.append('ET')
        content = '\n'.join(commands).encode('latin-1', 'replace')
        objects.append(f'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 3 0 R >> >> /Contents {content_id} 0 R >>'.encode('latin-1'))
        objects.append(f'<< /Length {len(content)} >>\nstream\n'.encode('latin-1') + content + b'\nendstream')

    kids = ' '.join(f'{page_id} 0 R' for page_id in page_ids)
    objects[1] = f'<< /Type /Pages /Kids [{kids}] /Count {len(page_ids)} >>'.encode('latin-1')

    pdf = bytearray(b'%PDF-1.4\n')
    offsets = [0]
    for index, obj in enumerate(objects, start=1):
        offsets.append(len(pdf))
        pdf.extend(f'{index} 0 obj\n'.encode('latin-1'))
        pdf.extend(obj)
        pdf.extend(b'\nendobj\n')
    xref_offset = len(pdf)
    pdf.extend(f'xref\n0 {len(objects) + 1}\n'.encode('latin-1'))
    pdf.extend(b'0000000000 65535 f \n')
    for offset in offsets[1:]:
        pdf.extend(f'{offset:010d} 00000 n \n'.encode('latin-1'))
    pdf.extend(
        f'trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF'.encode('latin-1')
    )
    return bytes(pdf)


def _formatta_data_corso(data_iso):
    try:
        return datetime.strptime(data_iso, '%Y-%m-%d').strftime('%d/%m/%Y')
    except (TypeError, ValueError):
        return data_iso or 'Data da definire'


def _etichetta_data_corso(corso):
    parti = [_formatta_data_corso(corso.data)]
    if corso.ora:
        parti.append(f'ore {corso.ora}')
    if corso.luogo:
        parti.append(corso.luogo)
    return ' - '.join(parti)


def _opzioni_date_corso(corso_tipo):
    oggi = date.today().strftime('%Y-%m-%d')
    corsi = Corso.query.filter(
        Corso.tipo == corso_tipo,
        Corso.data >= oggi,
        Corso.stato == 'Aperto'
    ).order_by(Corso.data, Corso.ora).all()
    return [
        {
            'value': str(corso.id),
            'corso_id': corso.id,
            'label': _etichetta_data_corso(corso),
        }
        for corso in corsi
    ]


def _corso_iscrivibile_con_date(corso_tipo):
    corso = dict(CORSI_ISCRIVIBILI[corso_tipo])
    corso['data_options'] = _opzioni_date_corso(corso_tipo)
    corso['has_open_dates'] = len(corso['data_options']) > 0
    return corso


def _render_iscrizione_con_errore(corso_tipo, messaggio):
    flash(messaggio, 'error')
    return render_template(
        'iscrizione_corso.html',
        corso_tipo=corso_tipo,
        corso=_corso_iscrivibile_con_date(corso_tipo),
        form_data=request.form
    )


@app.route('/iscrizione-corsi/<corso_tipo>', methods=['GET', 'POST'])
@limiter.limit("5 per minute")
def iscrizione_corso(corso_tipo):
    if corso_tipo not in CORSI_ISCRIVIBILI:
        abort(404)

    corso = _corso_iscrivibile_con_date(corso_tipo)
    if request.method == 'POST':
        token = session.pop('_csrf_token', None)
        if not token or token != request.form.get('_csrf_token'):
            return _render_iscrizione_con_errore(corso_tipo, 'Richiesta non valida. Riprova.')

        nome = request.form.get('nome', '').strip()
        telefono = request.form.get('telefono', '').strip()
        email = request.form.get('email', '').strip()
        codice_fiscale = request.form.get('codice_fiscale', '').strip()
        nome_bambino = request.form.get('nome_bambino', '').strip()
        eta_bambino = request.form.get('eta_bambino', '').strip()
        extra = {}
        data_corso_id = request.form.get('data_corso', '').strip()
        opzioni_date = {option['value']: option for option in corso['data_options']}
        corso_id = None
        if opzioni_date:
            if data_corso_id not in opzioni_date:
                return _render_iscrizione_con_errore(corso_tipo, 'Seleziona una data disponibile tra quelle aperte.')
            data_scelta = opzioni_date[data_corso_id]
            corso_id = data_scelta['corso_id']
            data_corso = data_scelta['label']
        else:
            data_corso = 'Da ricontattare per prossime date'
            extra['richiesta_prossime_date'] = True
        partecipazione = request.form.get('partecipazione', '').strip()
        consenso_privacy = _checkbox_checked('consenso_privacy')
        consenso_immagini = _checkbox_checked('consenso_immagini')
        tipo_richiesta = _tipo_richiesta_da_corso(corso_tipo, corso_id)

        if not nome or len(nome) > 100:
            return _render_iscrizione_con_errore(corso_tipo, 'Inserisci nome e cognome.')
        if not codice_fiscale or len(codice_fiscale) > 32:
            return _render_iscrizione_con_errore(corso_tipo, 'Inserisci il codice fiscale.')
        if not telefono or not _telefono_valido(telefono):
            return _render_iscrizione_con_errore(corso_tipo, 'Inserisci un numero di telefono valido.')
        if email and not _email_valida(email):
            return _render_iscrizione_con_errore(corso_tipo, 'Inserisci un indirizzo email valido.')
        if len(nome_bambino) > 100:
            return _render_iscrizione_con_errore(corso_tipo, 'Il nome del bambino è troppo lungo.')
        if len(eta_bambino) > 40:
            return _render_iscrizione_con_errore(corso_tipo, 'L\'età del bambino è troppo lunga.')

        if nome_bambino:
            extra['nome_bambino'] = nome_bambino
        if eta_bambino:
            extra['eta_bambino'] = eta_bambino

        if corso_tipo == 'bls-d':
            if partecipazione not in corso['partecipazione_options']:
                return _render_iscrizione_con_errore(corso_tipo, 'Seleziona il tipo di partecipazione.')
            dichiarazioni = {
                'prove_pratiche': _checkbox_checked('prove_pratiche'),
                'buono_stato_salute': _checkbox_checked('buono_stato_salute'),
                'richiesta_non_conferma': _checkbox_checked('richiesta_non_conferma'),
            }
            if not all(dichiarazioni.values()):
                return _render_iscrizione_con_errore(corso_tipo, 'Per procedere devi accettare tutte le dichiarazioni obbligatorie.')
            if not consenso_privacy:
                return _render_iscrizione_con_errore(corso_tipo, 'Devi autorizzare il trattamento dei dati personali.')
            if request.form.get('conferma_finale') != 'on':
                return _render_iscrizione_con_errore(corso_tipo, 'Devi confermare la richiesta di iscrizione al corso.')

            extra = {
                **extra,
                **dichiarazioni,
            }

        elif corso_tipo == 'disostruzione-pediatrica':
            if partecipazione not in corso['partecipazione_options']:
                return _render_iscrizione_con_errore(corso_tipo, 'Seleziona se partecipi da solo/a o in coppia.')
            nome_secondo = request.form.get('nome_secondo_partecipante', '').strip()
            cf_secondo = request.form.get('codice_fiscale_secondo_partecipante', '').strip()
            if partecipazione == 'Coppia 60 euro' and (not nome_secondo or not cf_secondo):
                return _render_iscrizione_con_errore(
                    corso_tipo,
                    'Per la partecipazione in coppia inserisci nome e codice fiscale del secondo partecipante.'
                )

            dichiarazioni = {
                'scopo_informativo': _checkbox_checked('scopo_informativo'),
                'no_certificazione': _checkbox_checked('no_certificazione'),
                'buono_stato_salute': _checkbox_checked('buono_stato_salute'),
            }
            if not all(dichiarazioni.values()):
                return _render_iscrizione_con_errore(corso_tipo, 'Per procedere devi accettare tutte le dichiarazioni obbligatorie.')
            if not consenso_privacy:
                return _render_iscrizione_con_errore(corso_tipo, 'Devi autorizzare il trattamento dei dati personali.')

            extra = {
                **extra,
                'nome_secondo_partecipante': nome_secondo,
                'codice_fiscale_secondo_partecipante': cf_secondo,
                **dichiarazioni,
            }

        elif corso_tipo == 'accompagnamento-nascita':
            required_fields = {
                'data_nascita': 'Inserisci la data di nascita.',
                'luogo_nascita': 'Inserisci il luogo di nascita.',
                'indirizzo': 'Inserisci l\'indirizzo di residenza.',
                'citta': 'Inserisci la città.',
                'provincia': 'Inserisci la provincia.',
                'cap': 'Inserisci il CAP.',
                'data_presunta_parto': 'Inserisci la data presunta del parto.',
                'settimana_gravidanza': 'Inserisci la settimana di gravidanza attuale.',
            }
            for field_name, error_message in required_fields.items():
                if not request.form.get(field_name, '').strip():
                    return _render_iscrizione_con_errore(corso_tipo, error_message)
            if not consenso_privacy:
                return _render_iscrizione_con_errore(corso_tipo, 'Devi acconsentire al trattamento dei dati personali.')
            if request.form.get('conferma_finale') != 'on':
                return _render_iscrizione_con_errore(corso_tipo, 'Devi confermare la richiesta di iscrizione al corso.')

            extra = {
                **extra,
                'data_nascita': request.form.get('data_nascita', '').strip(),
                'luogo_nascita': request.form.get('luogo_nascita', '').strip(),
                'indirizzo': request.form.get('indirizzo', '').strip(),
                'citta': request.form.get('citta', '').strip(),
                'provincia': request.form.get('provincia', '').strip(),
                'cap': request.form.get('cap', '').strip(),
                'data_presunta_parto': request.form.get('data_presunta_parto', '').strip(),
                'settimana_gravidanza': request.form.get('settimana_gravidanza', '').strip(),
                'gravidanza_regolare': request.form.get('gravidanza_regolare', '').strip(),
                'nome_partner': request.form.get('nome_partner', '').strip(),
                'telefono_partner': request.form.get('telefono_partner', '').strip(),
            }

        elif corso_tipo == 'laboratorio-infanzia':
            if partecipazione not in corso['partecipazione_options']:
                return _render_iscrizione_con_errore(corso_tipo, 'Seleziona il tipo di partecipazione.')
            if not consenso_privacy:
                return _render_iscrizione_con_errore(corso_tipo, 'Devi autorizzare il trattamento dei dati personali.')
            if request.form.get('conferma_finale') != 'on':
                return _render_iscrizione_con_errore(corso_tipo, 'Devi confermare la richiesta di iscrizione al laboratorio.')

        persona = _trova_o_crea_persona_corso(
            nome=nome,
            telefono=telefono,
            email=email,
            codice_fiscale=codice_fiscale,
            nome_bambino=nome_bambino,
            eta_bambino=eta_bambino,
        )

        iscrizione = IscrizioneCorso(
            corso_id=corso_id,
            persona=persona,
            corso_tipo=corso_tipo,
            corso_titolo=corso['titolo'],
            nome=nome,
            telefono=telefono,
            email=email,
            codice_fiscale=codice_fiscale,
            data_corso=data_corso,
            partecipazione=partecipazione,
            note=request.form.get('note', '').strip(),
            dati_extra=json.dumps(extra, ensure_ascii=False),
            tipo_richiesta=tipo_richiesta,
            posti=0 if tipo_richiesta == 'ricontatto' else _posti_iscrizione_da_partecipazione(partecipazione),
            consenso_privacy=consenso_privacy,
            consenso_immagini=consenso_immagini,
        )
        db.session.add(iscrizione)
        db.session.commit()
        invia_email_nuova_iscrizione(iscrizione)
        return redirect(url_for('conferma_iscrizione_corso'))

    return render_template('iscrizione_corso.html', corso_tipo=corso_tipo, corso=corso, form_data={})


@app.route('/iscrizione-corsi')
def iscrizione_corsi():
    return render_template('iscrizione_corsi.html')


@app.route('/iscrizione-corsi/conferma')
def conferma_iscrizione_corso():
    return render_template('conferma_iscrizione_corso.html')


def _render_accompagnamento_privato(percorso, messaggio=None):
    if messaggio:
        flash(messaggio, 'error')
    incontri = _incontri_percorso(percorso)
    posti_liberi = _posti_liberi_percorso(percorso)
    form_disponibile = percorso.stato == 'Aperto' and _percorso_ha_posto(percorso)
    return render_template(
        'iscrizione_accompagnamento_privata.html',
        percorso=percorso,
        incontri=incontri,
        posti_liberi=posti_liberi,
        form_disponibile=form_disponibile,
        form_data=request.form if request.method == 'POST' else {}
    )


@app.route('/iscrizione-accompagnamento/<slug>', methods=['GET', 'POST'])
@limiter.limit("5 per minute")
def iscrizione_accompagnamento_privata(slug):
    percorso = PercorsoAccompagnamento.query.filter_by(slug=slug).first_or_404()

    if request.method == 'POST':
        token = session.pop('_csrf_token', None)
        if not token or token != request.form.get('_csrf_token'):
            return _render_accompagnamento_privato(percorso, 'Richiesta non valida. Riprova.')
        if percorso.stato != 'Aperto':
            return _render_accompagnamento_privato(percorso, 'Le iscrizioni a questo percorso non sono aperte.')
        if not _percorso_ha_posto(percorso):
            return _render_accompagnamento_privato(percorso, 'Il percorso ha raggiunto la capienza massima.')

        nome = request.form.get('nome', '').strip()
        telefono = request.form.get('telefono', '').strip()
        email = request.form.get('email', '').strip()
        codice_fiscale = request.form.get('codice_fiscale', '').strip()
        data_presunta_parto = request.form.get('data_presunta_parto', '').strip()
        partner_presente = request.form.get('partner_presente', '').strip()
        note = request.form.get('note', '').strip()
        consenso_privacy = _checkbox_checked('consenso_privacy')
        consenso_immagini = _checkbox_checked('consenso_immagini')

        if not nome or len(nome) > 100:
            return _render_accompagnamento_privato(percorso, 'Inserisci nome e cognome.')
        if not telefono or not _telefono_valido(telefono):
            return _render_accompagnamento_privato(percorso, 'Inserisci un numero di telefono valido.')
        if not email or not _email_valida(email):
            return _render_accompagnamento_privato(percorso, 'Inserisci un indirizzo email valido.')
        if not codice_fiscale or len(codice_fiscale) > 32:
            return _render_accompagnamento_privato(percorso, 'Inserisci il codice fiscale.')
        if not data_presunta_parto:
            return _render_accompagnamento_privato(percorso, 'Inserisci la data presunta del parto.')
        if partner_presente not in ['Si', 'No']:
            return _render_accompagnamento_privato(percorso, 'Indica se il partner sarà presente.')
        if not consenso_privacy:
            return _render_accompagnamento_privato(percorso, 'Devi autorizzare il trattamento dei dati personali.')

        persona = _trova_o_crea_persona_corso(
            nome=nome,
            telefono=telefono,
            email=email,
            codice_fiscale=codice_fiscale,
        )
        extra = {
            'iscrizione_privata_accompagnamento': True,
            'data_presunta_parto': data_presunta_parto,
            'partner_presente': partner_presente,
        }
        iscrizione = IscrizioneCorso(
            percorso_accompagnamento=percorso,
            persona=persona,
            corso_tipo='accompagnamento-nascita',
            corso_titolo=percorso.titolo,
            nome=nome,
            telefono=telefono,
            email=email,
            codice_fiscale=codice_fiscale,
            data_corso=f'Percorso di {len(_incontri_percorso(percorso))} incontri',
            partecipazione=f'Coppia - partner {partner_presente.lower()}',
            note=note,
            dati_extra=json.dumps(extra, ensure_ascii=False),
            tipo_richiesta='iscrizione_effettiva',
            posti=1,
            consenso_privacy=consenso_privacy,
            consenso_immagini=consenso_immagini,
            stato='Confermato',
        )
        db.session.add(iscrizione)
        db.session.flush()
        for incontro in _incontri_percorso(percorso):
            db.session.add(PresenzaAccompagnamento(iscrizione=iscrizione, incontro=incontro))
        db.session.commit()
        invia_email_iscrizione_accompagnamento(iscrizione, percorso)
        invia_email_alert_iscrizione_accompagnamento(iscrizione, percorso)
        return redirect(url_for('conferma_iscrizione_accompagnamento'))

    return _render_accompagnamento_privato(percorso)


@app.route('/iscrizione-accompagnamento/conferma')
def conferma_iscrizione_accompagnamento():
    return render_template('conferma_iscrizione_accompagnamento.html')


def _orari_call_occupati(data_str, ignore_call_id=None, ignore_google_event_id=None):
    return {
        ora for ora in ORARI_CALL_SONNO
        if slot_occupato_db(data_str, ora, BLOCCO_CALL_SONNO_MINUTI, ignore_call_id)
        or intervallo_occupato_da_calendario(
            data_str,
            ora,
            BLOCCO_CALL_SONNO_MINUTI,
            ignore_google_event_id,
        )
    }


@app.route('/prenota-call-sonno', methods=['GET', 'POST'])
@limiter.limit('5 per hour')
def prenota_call_sonno():
    prima_data = prima_data_call_disponibile().isoformat()
    if request.method == 'POST':
        token = session.pop('_csrf_token', None)
        if not token or token != request.form.get('_csrf_token'):
            flash('Richiesta non valida. Riprova.', 'error')
            return render_template('prenota_call_sonno.html', form_data=request.form, prima_data=prima_data,
                                   difficolta_sonno=DIFFICOLTA_SONNO, orari_call=ORARI_CALL_SONNO)

        nome = request.form.get('nome', '').strip()
        telefono = request.form.get('telefono', '').strip()
        email = request.form.get('email', '').strip()
        difficolta = request.form.get('difficolta_principale', '').strip()
        difficolta_altro = request.form.get('difficolta_altro', '').strip()
        data_scelta = request.form.get('data', '').strip()
        ora = request.form.get('ora', '').strip()
        eta_raw = request.form.get('eta_bambino_mesi', '').strip()

        errori = []
        try:
            eta_mesi = int(eta_raw)
        except ValueError:
            eta_mesi = -1
        if not nome or len(nome) > 100:
            errori.append('Inserisci nome e cognome (massimo 100 caratteri).')
        if not re.match(r'^[\d\s\+\-\(\)]{7,20}$', telefono):
            errori.append('Inserisci un numero di telefono valido.')
        if not re.match(r'^[\w\.-]+@[\w\.-]+\.\w+$', email):
            errori.append('Inserisci un indirizzo email valido.')
        if eta_mesi < 0 or eta_mesi > 12:
            errori.append('L’età del bambino deve essere compresa tra 0 e 12 mesi.')
        if difficolta not in DIFFICOLTA_SONNO:
            errori.append('Seleziona la difficoltà principale.')
        if difficolta == 'Altro' and not difficolta_altro:
            errori.append('Descrivi brevemente la difficoltà principale.')
        if len(difficolta_altro) > 300:
            errori.append('La descrizione può contenere al massimo 300 caratteri.')
        if not request.form.get('consenso_privacy'):
            errori.append('Devi accettare l’informativa privacy per procedere.')
        if not orario_call_prenotabile(data_scelta, ora):
            errori.append('Scegli un giorno lavorativo e uno degli orari disponibili.')
        elif (
            slot_occupato_db(data_scelta, ora, BLOCCO_CALL_SONNO_MINUTI)
            or intervallo_occupato_da_calendario(data_scelta, ora, BLOCCO_CALL_SONNO_MINUTI)
        ):
            errori.append('Questo orario non è più disponibile. Scegline un altro.')

        if errori:
            for errore in errori:
                flash(errore, 'error')
            return render_template('prenota_call_sonno.html', form_data=request.form, prima_data=prima_data,
                                   difficolta_sonno=DIFFICOLTA_SONNO, orari_call=ORARI_CALL_SONNO)

        nuova_call = CallSonno(
            nome=nome,
            telefono=telefono,
            email=email,
            eta_bambino_mesi=eta_mesi,
            difficolta_principale=difficolta,
            difficolta_altro=difficolta_altro if difficolta == 'Altro' else None,
            consenso_privacy=True,
            data=data_scelta,
            ora=ora,
        )
        db.session.add(nuova_call)
        db.session.commit()
        crea_o_aggiorna_evento_calendario_call_sonno(nuova_call)
        invia_email_ricezione_call_sonno(nuova_call)
        invia_email_alert_call_sonno(nuova_call)
        session['ultima_call_sonno'] = nuova_call.id
        return redirect(url_for('conferma_call_sonno'))

    return render_template('prenota_call_sonno.html', form_data={}, prima_data=prima_data,
                           difficolta_sonno=DIFFICOLTA_SONNO, orari_call=ORARI_CALL_SONNO)


@app.route('/prenota-call-sonno/conferma')
def conferma_call_sonno():
    call_id = session.get('ultima_call_sonno')
    call = db.session.get(CallSonno, call_id) if call_id else None
    return render_template('conferma_call_sonno.html', call=call)


@app.route('/api/orari-call-sonno/<data_str>')
@limiter.limit('30 per minute')
def api_orari_call_sonno(data_str):
    if not re.match(r'^\d{4}-\d{2}-\d{2}$', data_str):
        abort(400)
    if not _giorno_lavorativo_call(datetime.strptime(data_str, '%Y-%m-%d').date()):
        return jsonify({'occupati': ORARI_CALL_SONNO})
    return jsonify({'occupati': sorted(_orari_call_occupati(data_str))})


@app.route('/questionario-sonno/<token>', methods=['GET', 'POST'])
@limiter.limit('10 per hour')
def questionario_sonno(token):
    if not re.match(r'^[A-Za-z0-9_-]{32,96}$', token):
        abort(404)
    call = CallSonno.query.filter_by(token_questionario=token).first_or_404()
    if not call.formula_scelta:
        abort(404)
    if call.questionario:
        return render_template('questionario_sonno_completato.html', call=call)

    if request.method == 'POST':
        csrf = session.pop('_csrf_token', None)
        if not csrf or csrf != request.form.get('_csrf_token'):
            flash('Richiesta non valida. Riprova.', 'error')
            return render_template('questionario_sonno.html', call=call, form_data=request.form, formule_sonno=FORMULE_SONNO)
        if not request.form.get('consenso_dati_sanitari'):
            flash('Il consenso al trattamento dei dati sanitari è necessario per inviare il questionario.', 'error')
            return render_template('questionario_sonno.html', call=call, form_data=request.form, formule_sonno=FORMULE_SONNO)

        campi = [
            'nome_bambino', 'data_nascita', 'nascita', 'eta_corretta', 'gestione_sonno',
            'alimentazione', 'poppate_notturne', 'addormentamento_seno', 'risveglio_mattino',
            'pisolini', 'routine_serale', 'ora_addormentamento', 'cambiamenti_routine',
            'dove_si_addormenta', 'dove_dorme', 'supporti_addormentamento', 'risvegli_dettaglio',
            'riaddormentamento', 'risveglio_precoce', 'durata_difficolta', 'tentativi_fatti',
            'eventi_recenti', 'momento_piu_difficile', 'cambiamento_desiderato',
            'cosa_non_cambiare', 'partecipanti_consulenza', 'condizioni_note',
            'terapie_indicazioni', 'professionisti_coinvolti', 'note_finali',
        ]
        risposte = {campo: request.form.get(campo, '').strip()[:2000] for campo in campi}
        obbligatori = ['nome_bambino', 'data_nascita', 'alimentazione', 'dove_dorme',
                       'durata_difficolta', 'cambiamento_desiderato']
        if any(not risposte[campo] for campo in obbligatori):
            flash('Completa tutti i campi contrassegnati come obbligatori.', 'error')
            return render_template('questionario_sonno.html', call=call, form_data=request.form, formule_sonno=FORMULE_SONNO)

        db.session.add(QuestionarioSonno(
            call_sonno=call,
            risposte=json.dumps(risposte, ensure_ascii=False),
            consenso_dati_sanitari=True,
            consenso_marketing=bool(request.form.get('consenso_marketing')),
        ))
        db.session.commit()
        registra_evento('questionario_sonno', 'successo', 'Questionario sonno compilato.', 'CallSonno', call.id)
        return redirect(url_for('questionario_sonno', token=token))

    return render_template('questionario_sonno.html', call=call, form_data={}, formule_sonno=FORMULE_SONNO)


def _panoramica_corsi(corsi):
    iscrizioni_per_corso = defaultdict(list)
    corso_ids = [corso.id for corso in corsi]
    if corso_ids:
        iscrizioni = IscrizioneCorso.query.filter(
            IscrizioneCorso.corso_id.in_(corso_ids)
        ).order_by(IscrizioneCorso.creato_il.desc()).all()
        for iscrizione in iscrizioni:
            iscrizioni_per_corso[iscrizione.corso_id].append(iscrizione)

    panoramica = []
    for corso in corsi:
        iscrizioni_corso = iscrizioni_per_corso.get(corso.id, [])
        attive = [i for i in iscrizioni_corso if i.stato != 'Annullato']
        confermate = [i for i in attive if i.stato == 'Confermato']
        open_day = [i for i in attive if i.tipo_richiesta == 'open_day']
        effettive = [i for i in attive if i.tipo_richiesta == 'iscrizione_effettiva']
        richieste = [
            i for i in attive
            if i.tipo_richiesta in ['richiesta_iscrizione', 'iscrizione_effettiva']
        ]
        posti_attivi = sum(i.posti or _posti_iscrizione_da_partecipazione(i.partecipazione) for i in attive)
        capienza = corso.capienza_massima
        posti_liberi = None if capienza is None else max(capienza - posti_attivi, 0)
        panoramica.append({
            'corso': corso,
            'iscrizioni': iscrizioni_corso,
            'attive_count': len(attive),
            'confermate_count': len(confermate),
            'open_day_count': len(open_day),
            'effettive_count': len(effettive),
            'richieste_count': len(richieste),
            'posti_attivi': posti_attivi,
            'capienza': capienza,
            'posti_liberi': posti_liberi,
            'stato': corso.stato or 'Aperto',
        })
    return panoramica


@app.route('/prenota', methods=['GET', 'POST'])
@limiter.limit("5 per minute")
def prenota():
    if request.method == 'POST':
        # Protezione CSRF
        token = session.pop('_csrf_token', None)
        if not token or token != request.form.get('_csrf_token'):
            flash('Richiesta non valida. Riprova.', 'error')
            return render_template('prenota.html', form_data=request.form)

        if not request.form.get('consenso_privacy'):
            flash('Devi accettare l\'informativa privacy per procedere.')
            return render_template('prenota.html', form_data=request.form)

        # Estrai i dati del modulo
        nome = request.form.get('nome', '').strip()
        telefono = request.form.get('telefono', '').strip()
        email = request.form.get('email', '').strip()
        servizio = request.form.get('servizio', '').strip()
        data_scelta = request.form.get('data', '').strip()
        ora = request.form.get('ora', '').strip()
        note = request.form.get('note', '').strip()

        # Valida i campi obbligatori
        if not nome:
            flash('Il nome è obbligatorio.')
            return render_template('prenota.html', form_data=request.form)
        if not telefono:
            flash('Il telefono è obbligatorio.')
            return render_template('prenota.html', form_data=request.form)
        if not email:
            flash('L\'email è obbligatoria.')
            return render_template('prenota.html', form_data=request.form)
        if not servizio:
            flash('Il servizio è obbligatorio.')
            return render_template('prenota.html', form_data=request.form)
        if not data_scelta:
            flash('La data è obbligatoria.')
            return render_template('prenota.html', form_data=request.form)
        if not ora:
            flash('L\'ora è obbligatoria.')
            return render_template('prenota.html', form_data=request.form)

        # Valida la lunghezza del nome
        if len(nome) > 100:
            flash('Il nome è troppo lungo (max 100 caratteri).')
            return render_template('prenota.html', form_data=request.form)

        # Valida il formato del telefono (consenti cifre, spazi, +, -, (), lunghezza 7-20)
        if not re.match(r'^[\d\s\+\-\(\)]{7,20}$', telefono):
            flash('Il numero di telefono non è valido.')
            return render_template('prenota.html', form_data=request.form)

        # Valida il formato dell'email
        if not re.match(r'^[\w\.-]+@[\w\.-]+\.\w+$', email):
            flash('L\'indirizzo email non è valido.')
            return render_template('prenota.html', form_data=request.form)

        # Valida il servizio
        if servizio not in SERVIZI_VALIDI:
            flash('Servizio non valido. Seleziona un servizio dalla lista.')
            return render_template('prenota.html', form_data=request.form)

        # Valida che la data non sia nel passato
        oggi = date.today().strftime('%Y-%m-%d')
        if data_scelta < oggi:
            flash('Non puoi prenotare una data nel passato.')
            return render_template('prenota.html', form_data=request.form)

        # Valida la lunghezza delle note (opzionale)
        if len(note) > 500:
            flash('Le note sono troppo lunghe (max 500 caratteri).')
            return render_template('prenota.html', form_data=request.form)

        # Valida che l'orario sia uno di quelli previsti
        if ora not in ORARI_DISPONIBILI:
            flash('Orario non valido. Seleziona un orario dalla lista.')
            return render_template('prenota.html', form_data=request.form)

        if not orario_prenotabile(data_scelta, ora):
            flash('Lo studio è chiuso nella data o nell\'orario selezionato. Scegli un altro appuntamento.')
            return render_template('prenota.html', form_data=request.form)

        # Verifica che lo slot non sia già occupato (in DB o su Arzamed/Google
        # Calendar). Il form disabilita già questi orari via JavaScript, ma
        # questo controllo lato server evita doppie prenotazioni nel caso in
        # cui qualcuno invii comunque la richiesta (bypassando il JS, o per
        # una prenotazione fatta nel frattempo da un altro utente).
        gia_occupato_db = slot_occupato_db(data_scelta, ora, DURATA_SLOT_MINUTI)
        gia_occupato_calendario = ora in orari_occupati_da_calendario(data_scelta)
        if gia_occupato_db or gia_occupato_calendario:
            flash('Questo orario non è più disponibile. Scegline un altro.')
            return render_template('prenota.html', form_data=request.form)

        # Crea l'appuntamento
        nuovo = Appuntamento(
            nome=nome,
            telefono=telefono,
            email=email,
            servizio=servizio,
            data=data_scelta,
            ora=ora,
            note=note
        )
        db.session.add(nuovo)
        db.session.commit()
        invia_email_nuova_prenotazione(nuovo)
        return redirect(url_for('conferma'))

    return render_template('prenota.html')


@app.route('/conferma')
def conferma():
    return render_template('conferma.html')


@app.route('/privacy')
def privacy():
    return render_template('privacy.html')


# ─── LOGIN / LOGOUT ───

@app.route('/admin/login', methods=['GET', 'POST'])
@limiter.limit("5 per minute")
def login():
    if current_user.is_authenticated:
        return redirect(url_for('admin'))
    if request.method == 'POST':
        # Protezione CSRF
        token = session.pop('_csrf_token', None)
        if not token or token != request.form.get('_csrf_token'):
            flash('Richiesta non valida. Riprova.', 'error')
            return render_template('login.html')
        username = request.form['username']
        password = request.form['password']
        utente = Admin.query.filter_by(username=username).first()
        if utente and check_password_hash(utente.password, password):
            login_user(utente, remember=True)
            next_page = request.args.get('next')
            if is_safe_redirect_target(next_page):
                return redirect(next_page)
            return redirect(url_for('admin'))
        else:
            flash('Username o password errati.')
    return render_template('login.html')


@app.route('/admin/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))


# ─── AREA ADMIN ───

@app.route('/admin')
@login_required
def admin():
    oggi = date.today().strftime('%Y-%m-%d')
    filtro = request.args.get('filtro', 'in_attesa')

    # Pulizia degli appuntamenti annullati vecchi (>30 giorni)
    trenta_giorni_fa = datetime.today() - timedelta(days=30)
    vecchi = Appuntamento.query.filter(
        Appuntamento.stato == 'Annullato',
        Appuntamento.creato_il < trenta_giorni_fa
    ).all()
    for v in vecchi:
        db.session.delete(v)
    db.session.commit()

    # Query gli appuntamenti in base al filtro
    if filtro == 'in_attesa':
        appuntamenti = Appuntamento.query.filter(
            Appuntamento.stato == 'In attesa'
        ).order_by(Appuntamento.data, Appuntamento.ora).all()
        in_attesa_count = len(appuntamenti)  # riusa il conteggio
    else:
        # Per gli altri filtri, abbiamo comunque bisogno del conto di "In attesa" per il badge
        in_attesa_count = Appuntamento.query.filter(
            Appuntamento.stato == 'In attesa'
        ).count()
        if filtro == 'confermati':
            appuntamenti = Appuntamento.query.filter(
                Appuntamento.stato == 'Confermato',
                Appuntamento.data >= oggi
            ).order_by(Appuntamento.data, Appuntamento.ora).all()
        elif filtro == 'annullati':
            appuntamenti = Appuntamento.query.filter(
                Appuntamento.stato == 'Annullato'
            ).order_by(Appuntamento.data, Appuntamento.ora).all()
        elif filtro == 'passati':
            appuntamenti = Appuntamento.query.filter(
                Appuntamento.data < oggi,
                Appuntamento.stato != 'Annullato'
            ).order_by(Appuntamento.data.desc(), Appuntamento.ora.desc()).all()
        else:
            appuntamenti = []

    corsi = Corso.query.order_by(Corso.data).all()
    panoramica_corsi = _panoramica_corsi(corsi)
    persone_corsi = PersonaCorso.query.order_by(PersonaCorso.nome).all()
    percorsi_accompagnamento = PercorsoAccompagnamento.query.order_by(PercorsoAccompagnamento.creato_il.desc()).all()
    panoramica_percorsi_accompagnamento = _panoramica_percorsi_accompagnamento(percorsi_accompagnamento)
    presenze_accompagnamento = {}
    for item in panoramica_percorsi_accompagnamento:
        percorso = item['percorso']
        presenze = _presenze_per_percorso(percorso, item['iscrizioni'], item['incontri'])
        presenze_accompagnamento[percorso.id] = {
            f'{chiave[0]}-{chiave[1]}': presenza for chiave, presenza in presenze.items()
    }
    corso_filtro_id = request.args.get('corso_id', type=int)
    filtro_iscrizioni = request.args.get('iscrizioni', '').strip()
    filtro_tipo_corso = request.args.get('tipo_corso', '').strip()
    if filtro_tipo_corso not in CORSI_ADMIN_TIPI:
        filtro_tipo_corso = ''
    filtro_tipo_corso_label = (
        CORSI_ADMIN_TIPI[filtro_tipo_corso]['label']
        if filtro_tipo_corso
        else ''
    )
    corso_filtro_attivo = db.session.get(Corso, corso_filtro_id) if corso_filtro_id else None
    iscrizioni_per_tipo_count = {
        tipo: 0
        for tipo in CORSI_ADMIN_TIPI
    }
    conteggi_tipo = db.session.query(
        IscrizioneCorso.corso_tipo,
        db.func.count(IscrizioneCorso.id)
    ).group_by(IscrizioneCorso.corso_tipo).all()
    for tipo, count in conteggi_tipo:
        if tipo in iscrizioni_per_tipo_count:
            iscrizioni_per_tipo_count[tipo] = count

    iscrizioni_query = IscrizioneCorso.query
    if corso_filtro_attivo:
        iscrizioni_query = iscrizioni_query.filter(IscrizioneCorso.corso_id == corso_filtro_attivo.id)
    else:
        if filtro_tipo_corso:
            iscrizioni_query = iscrizioni_query.filter(IscrizioneCorso.corso_tipo == filtro_tipo_corso)
        if filtro_iscrizioni == 'ricontatto':
            iscrizioni_query = iscrizioni_query.filter(IscrizioneCorso.tipo_richiesta == 'ricontatto')
        elif filtro_iscrizioni == 'open_day':
            iscrizioni_query = iscrizioni_query.filter(IscrizioneCorso.tipo_richiesta == 'open_day')

    iscrizioni_corsi = iscrizioni_query.order_by(IscrizioneCorso.creato_il.desc()).all()
    iscrizioni_totali_count = IscrizioneCorso.query.count()
    iscrizioni_nuove_count = IscrizioneCorso.query.filter_by(stato='Nuova').count()
    call_sonno = CallSonno.query.order_by(CallSonno.data, CallSonno.ora).all()
    call_sonno_in_attesa_count = CallSonno.query.filter_by(stato='In attesa').count()
    registro_eventi = RegistroEvento.query.order_by(RegistroEvento.creato_il.desc()).limit(30).all()
    eventi_critici_count = RegistroEvento.query.filter(
        RegistroEvento.esito.in_(['errore', 'avviso']),
        RegistroEvento.creato_il >= datetime.now() - timedelta(days=7)
    ).count()
    return render_template('admin.html',
                           appuntamenti=appuntamenti,
                           corsi=corsi,
                           panoramica_corsi=panoramica_corsi,
                           corsi_admin_tipi=CORSI_ADMIN_TIPI,
                           persone_corsi=persone_corsi,
                           panoramica_percorsi_accompagnamento=panoramica_percorsi_accompagnamento,
                           presenze_accompagnamento=presenze_accompagnamento,
                           stati_percorso_accompagnamento=STATI_PERCORSO_ACCOMPAGNAMENTO_VALIDI,
                           iscrizioni_corsi=iscrizioni_corsi,
                           iscrizioni_totali_count=iscrizioni_totali_count,
                           persone_corsi_count=len(persone_corsi),
                           iscrizioni_nuove_count=iscrizioni_nuove_count,
                           call_sonno=call_sonno,
                           call_sonno_in_attesa_count=call_sonno_in_attesa_count,
                           formule_sonno=FORMULE_SONNO,
                           registro_eventi=registro_eventi,
                           eventi_critici_count=eventi_critici_count,
                           tipo_richiesta_labels=TIPI_RICHIESTA_CORSO,
                           corso_filtro_attivo=corso_filtro_attivo,
                           filtro_tipo_corso=filtro_tipo_corso,
                           filtro_tipo_corso_label=filtro_tipo_corso_label,
                           iscrizioni_per_tipo_count=iscrizioni_per_tipo_count,
                           iscrizioni_filtrate_count=len(iscrizioni_corsi),
                           filtro_iscrizioni=filtro_iscrizioni,
                           filtro=filtro,
                           in_attesa_count=in_attesa_count)


def _csrf_admin_valido():
    token = request.form.get('_csrf_token')
    return bool(token and token == session.get('_csrf_token'))


@app.route('/admin/call-sonno/<int:id>/conferma', methods=['POST'])
@login_required
def conferma_call_sonno_admin(id):
    if not _csrf_admin_valido():
        abort(400)
    call = db.get_or_404(CallSonno, id)
    if call.stato == 'Annullata':
        abort(400)
    call.stato = 'Confermata'
    db.session.commit()
    invia_email_conferma_call_sonno(call)
    if not crea_o_aggiorna_evento_calendario_call_sonno(call):
        flash('Call confermata, ma Calendar non è stato aggiornato. Controlla il registro eventi.', 'error')
    else:
        flash('Call confermata e comunicazione inviata.', 'success')
    return redirect(url_for('admin') + '#admin-call-sonno')


@app.route('/admin/call-sonno/<int:id>/annulla', methods=['POST'])
@login_required
def annulla_call_sonno_admin(id):
    if not _csrf_admin_valido():
        abort(400)
    call = db.get_or_404(CallSonno, id)
    call.stato = 'Annullata'
    db.session.commit()
    invia_email_annullamento_call_sonno(call)
    if not elimina_evento_calendario_call_sonno(call):
        flash('Call annullata, ma il blocco Calendar non è stato rimosso.', 'error')
    else:
        flash('Call annullata.', 'success')
    return redirect(url_for('admin') + '#admin-call-sonno')


@app.route('/admin/call-sonno/<int:id>/modifica', methods=['GET', 'POST'])
@login_required
def modifica_call_sonno_admin(id):
    call = db.get_or_404(CallSonno, id)
    if request.method == 'POST':
        token = session.pop('_csrf_token', None)
        if not token or token != request.form.get('_csrf_token'):
            flash('Richiesta non valida. Riprova.', 'error')
            return render_template('modifica_call_sonno.html', call=call, orari_call=ORARI_CALL_SONNO)
        nuova_data = request.form.get('data', '').strip()
        nuova_ora = request.form.get('ora', '').strip()
        try:
            giorno = datetime.strptime(nuova_data, '%Y-%m-%d').date()
        except ValueError:
            giorno = None
        valido = (
            giorno is not None and giorno >= date.today() and _giorno_lavorativo_call(giorno)
            and nuova_ora in ORARI_CALL_SONNO
        )
        occupato = valido and (
            slot_occupato_db(nuova_data, nuova_ora, BLOCCO_CALL_SONNO_MINUTI, call.id)
            or intervallo_occupato_da_calendario(
                nuova_data,
                nuova_ora,
                BLOCCO_CALL_SONNO_MINUTI,
                call.google_event_id,
            )
        )
        if not valido or occupato:
            flash('Data o orario non disponibile. Verifica gli impegni e riprova.', 'error')
            return render_template('modifica_call_sonno.html', call=call, orari_call=ORARI_CALL_SONNO)
        call.data = nuova_data
        call.ora = nuova_ora
        call.stato = 'Confermata'
        db.session.commit()
        invia_email_conferma_call_sonno(call, modificata=True)
        if not crea_o_aggiorna_evento_calendario_call_sonno(call):
            flash('Nuovo orario salvato, ma Calendar non è stato aggiornato.', 'error')
        else:
            flash('Nuovo orario confermato e comunicato alla famiglia.', 'success')
        return redirect(url_for('admin') + '#admin-call-sonno')
    return render_template('modifica_call_sonno.html', call=call, orari_call=ORARI_CALL_SONNO)


@app.route('/admin/call-sonno/<int:id>/questionario', methods=['GET'])
@login_required
def visualizza_questionario_sonno_admin(id):
    call = db.get_or_404(CallSonno, id)
    if not call.questionario:
        abort(404)
    risposte = call.questionario.risposte_dict()
    risposte_ordinate = [
        (etichetta, risposte.get(campo, ''))
        for campo, etichetta in QUESTIONARIO_SONNO_LABELS.items()
        if risposte.get(campo)
    ]
    return render_template(
        'admin_questionario_sonno.html',
        call=call,
        risposte=risposte_ordinate,
        formula=FORMULE_SONNO.get(call.formula_scelta, call.formula_scelta),
    )


@app.route('/admin/call-sonno/<int:id>/questionario', methods=['POST'])
@login_required
def invia_questionario_sonno_admin(id):
    if not _csrf_admin_valido():
        abort(400)
    call = db.get_or_404(CallSonno, id)
    formula = request.form.get('formula_scelta', '').strip()
    if formula not in FORMULE_SONNO:
        flash('Seleziona la formula concordata.', 'error')
        return redirect(url_for('admin') + '#admin-call-sonno')
    call.formula_scelta = formula
    call.stato = 'Conclusa'
    if not call.token_questionario:
        call.token_questionario = secrets.token_urlsafe(48)
    call.questionario_inviato_il = datetime.now()
    db.session.commit()
    if invia_email_questionario_sonno(call):
        flash('Questionario privato inviato.', 'success')
    else:
        flash('Il link è stato creato, ma l’email non è partita. Controlla il registro eventi.', 'error')
    return redirect(url_for('admin') + '#admin-call-sonno')


@app.route('/admin/aggiorna/<int:id>/<stato>')
@login_required
def aggiorna_stato(id, stato):
    if stato not in STATI_VALIDI:
        abort(400)
    # Protezione CSRF: questi link puntano a un'azione che modifica dati,
    # quindi vanno protetti come un form. Non usiamo session.pop() perché
    # più link nella stessa pagina admin condividono lo stesso token: se lo
    # consumassimo al primo click, i click successivi (senza ricaricare la
    # pagina) fallirebbero.
    token = request.args.get('token')
    if not token or token != session.get('_csrf_token'):
        flash('Richiesta non valida. Riprova.', 'error')
        return redirect(url_for('admin', filtro=request.args.get('filtro', 'in_attesa')))
    appuntamento = db.get_or_404(Appuntamento, id)
    appuntamento.stato = stato
    db.session.commit()
    if stato == 'Confermato':
        invia_email_conferma(appuntamento)
        if not crea_o_aggiorna_evento_calendario(appuntamento):
            flash('Appuntamento confermato, ma Google Calendar non è stato aggiornato. Controlla il registro eventi.', 'error')
    elif stato == 'Annullato':
        invia_email_annullamento(appuntamento)
        if not elimina_evento_calendario(appuntamento):
            flash('Appuntamento annullato, ma Google Calendar non è stato aggiornato. Controlla il registro eventi.', 'error')
    return redirect(url_for('admin', filtro=request.args.get('filtro', 'in_attesa')))


@app.route('/admin/modifica/<int:id>', methods=['GET', 'POST'])
@login_required
def modifica_appuntamento(id):
    appuntamento = db.get_or_404(Appuntamento, id)
    if request.method == 'POST':
        # Protezione CSRF
        token = session.pop('_csrf_token', None)
        if not token or token != request.form.get('_csrf_token'):
            flash('Richiesta non valida. Riprova.', 'error')
            return render_template('modifica_appuntamento.html', a=appuntamento)

        nuova_data = request.form.get('data', '').strip()
        nuova_ora = request.form.get('ora', '').strip()
        oggi = date.today().strftime('%Y-%m-%d')

        if not nuova_data or not nuova_ora:
            flash('Data e ora sono obbligatorie.', 'error')
            return render_template('modifica_appuntamento.html', a=appuntamento)
        if nuova_data < oggi:
            flash('Non puoi spostare un appuntamento a una data nel passato.', 'error')
            return render_template('modifica_appuntamento.html', a=appuntamento)
        if not orario_prenotabile(nuova_data, nuova_ora):
            flash('Lo studio è chiuso nella data o nell\'orario selezionato. Scegli un altro appuntamento.', 'error')
            return render_template('modifica_appuntamento.html', a=appuntamento)

        gia_occupato_db = slot_occupato_db(
            nuova_data,
            nuova_ora,
            DURATA_SLOT_MINUTI,
            ignore_appuntamento_id=appuntamento.id,
        )
        orari_occupati_calendario = orari_occupati_da_calendario(nuova_data)
        if nuova_data == appuntamento.data:
            orari_occupati_calendario.discard(appuntamento.ora)
        gia_occupato_calendario = nuova_ora in orari_occupati_calendario
        if gia_occupato_db or gia_occupato_calendario:
            flash('Questo orario non è più disponibile. Scegline un altro.', 'error')
            return render_template('modifica_appuntamento.html', a=appuntamento)

        appuntamento.data = nuova_data
        appuntamento.ora = nuova_ora
        appuntamento.stato = 'Confermato'
        db.session.commit()
        invia_email_spostamento(appuntamento)
        if not crea_o_aggiorna_evento_calendario(appuntamento):
            flash('Appuntamento modificato, ma Google Calendar non è stato aggiornato. Controlla il registro eventi.', 'error')
        return redirect(url_for('admin', filtro='in_attesa'))
    return render_template('modifica_appuntamento.html', a=appuntamento)


@app.route('/admin/corso/aggiungi', methods=['POST'])
@login_required
def aggiungi_corso():
    # Protezione CSRF
    token = session.pop('_csrf_token', None)
    if not token or token != request.form.get('_csrf_token'):
        flash('Richiesta non valida. Riprova.', 'error')
        return redirect(url_for('admin'))
    tipo_corso = request.form.get('tipo', '').strip()
    if tipo_corso not in CORSI_ADMIN_TIPI:
        flash('Seleziona un tipo di corso valido.', 'error')
        return redirect(url_for('admin'))
    corso = Corso(
        titolo=request.form['titolo'],
        tipo=tipo_corso,
        descrizione=request.form.get('descrizione', ''),
        data=request.form['data'],
        ora=request.form.get('ora', ''),
        luogo=request.form.get('luogo', ''),
        durata_ore=_durata_corso_da_form(request.form.get('durata_ore', ''), tipo_corso),
        capienza_massima=request.form.get('capienza_massima', type=int),
        stato=request.form.get('stato', 'Aperto') if request.form.get('stato') in STATI_CORSO_VALIDI else 'Aperto',
    )
    db.session.add(corso)
    db.session.commit()
    if not crea_o_aggiorna_evento_calendario_corso(corso):
        flash('Corso salvato, ma Google Calendar non è stato aggiornato. Controlla il registro eventi.', 'error')
    return redirect(url_for('admin'))


@app.route('/admin/percorso-accompagnamento/aggiungi', methods=['POST'])
@login_required
def aggiungi_percorso_accompagnamento():
    token = session.pop('_csrf_token', None)
    if not token or token != request.form.get('_csrf_token'):
        flash('Richiesta non valida. Riprova.', 'error')
        return redirect(url_for('admin') + '#admin-percorsi-accompagnamento')

    titolo = request.form.get('titolo', '').strip() or 'Iscrizione al corso'
    slug_richiesto = request.form.get('slug', '').strip() or titolo
    stato = request.form.get('stato', 'Aperto').strip()
    if stato not in STATI_PERCORSO_ACCOMPAGNAMENTO_VALIDI:
        stato = 'Aperto'

    capienza_coppie = request.form.get('capienza_coppie', type=int)
    if capienza_coppie is not None and capienza_coppie < 1:
        capienza_coppie = None

    percorso = PercorsoAccompagnamento(
        titolo=titolo,
        slug=_slug_unico_percorso(slug_richiesto),
        descrizione=request.form.get('descrizione', '').strip(),
        capienza_coppie=capienza_coppie,
        luogo='Studio infermieristico',
        contatti=request.form.get('contatti', '').strip() or '3806317175',
        stato=stato,
    )
    db.session.add(percorso)
    db.session.commit()
    flash('Edizione privata del percorso creata.', 'success')
    return redirect(url_for('admin') + '#admin-percorsi-accompagnamento')


@app.route('/admin/percorso-accompagnamento/<int:id>/incontro/aggiungi', methods=['POST'])
@login_required
def aggiungi_incontro_accompagnamento(id):
    token = session.pop('_csrf_token', None)
    if not token or token != request.form.get('_csrf_token'):
        flash('Richiesta non valida. Riprova.', 'error')
        return redirect(url_for('admin') + '#admin-percorsi-accompagnamento')

    percorso = db.get_or_404(PercorsoAccompagnamento, id)
    numero = request.form.get('numero', type=int)
    data = request.form.get('data', '').strip()
    professionista = request.form.get('professionista', '').strip()
    tema = request.form.get('tema', '').strip()
    if not numero or numero < 1 or numero > 9:
        flash('Inserisci un numero incontro da 1 a 9.', 'error')
        return redirect(url_for('admin') + '#admin-percorsi-accompagnamento')
    if not data or not professionista or not tema:
        flash('Data, professionista e tema sono obbligatori.', 'error')
        return redirect(url_for('admin') + '#admin-percorsi-accompagnamento')
    incontro_esistente = IncontroAccompagnamento.query.filter_by(
        percorso_id=percorso.id,
        numero=numero
    ).first()
    if incontro_esistente:
        flash('Esiste già un incontro con questo numero per il percorso selezionato.', 'error')
        return redirect(url_for('admin') + '#admin-percorsi-accompagnamento')

    incontro = IncontroAccompagnamento(
        percorso=percorso,
        numero=numero,
        data=data,
        ora=request.form.get('ora', '').strip(),
        professionista=professionista,
        tema=tema,
        luogo='Studio infermieristico',
        note=request.form.get('note', '').strip(),
    )
    db.session.add(incontro)
    db.session.flush()
    for iscrizione in _iscrizioni_percorso(percorso):
        db.session.add(PresenzaAccompagnamento(iscrizione=iscrizione, incontro=incontro))
    db.session.commit()
    flash('Incontro aggiunto al percorso.', 'success')
    return redirect(url_for('admin') + '#admin-percorsi-accompagnamento')


@app.route('/admin/percorso-accompagnamento/<int:id>/presenze', methods=['POST'])
@login_required
def aggiorna_presenze_accompagnamento(id):
    token = session.pop('_csrf_token', None)
    if not token or token != request.form.get('_csrf_token'):
        flash('Richiesta non valida. Riprova.', 'error')
        return redirect(url_for('admin') + '#admin-percorsi-accompagnamento')

    percorso = db.get_or_404(PercorsoAccompagnamento, id)
    iscrizioni = _iscrizioni_percorso(percorso)
    incontri = _incontri_percorso(percorso)
    presenze = _presenze_per_percorso(percorso, iscrizioni, incontri)

    for iscrizione in iscrizioni:
        for incontro in incontri:
            campo = f'presenza_{iscrizione.id}_{incontro.id}'
            valore = request.form.get(campo, '').strip()
            presenza = presenze.get((iscrizione.id, incontro.id))
            if not presenza:
                presenza = PresenzaAccompagnamento(iscrizione=iscrizione, incontro=incontro)
                db.session.add(presenza)
            if valore == 'presente':
                presenza.presente = True
            elif valore == 'assente':
                presenza.presente = False
            else:
                presenza.presente = None
    db.session.commit()
    flash('Registro presenze aggiornato.', 'success')
    return redirect(url_for('admin') + '#admin-percorsi-accompagnamento')


@app.route('/admin/percorso-accompagnamento/<int:id>/export-pdf')
@login_required
def esporta_percorso_accompagnamento_pdf(id):
    percorso = db.get_or_404(PercorsoAccompagnamento, id)
    iscrizioni = _iscrizioni_percorso(percorso)
    incontri = _incontri_percorso(percorso)
    presenze = _presenze_per_percorso(percorso, iscrizioni, incontri)

    righe = [
        f'Percorso: {percorso.titolo}',
        f'Stato: {percorso.stato}',
        f'Capienza coppie: {percorso.capienza_coppie or "non impostata"}',
        f'Iscrizioni confermate/attive: {len(iscrizioni)}',
        '',
        'Calendario incontri:',
    ]
    righe.extend(_riepilogo_date_percorso(percorso) or ['Date non ancora inserite.'])
    righe.extend(['', 'Iscritti:'])
    for iscrizione in iscrizioni:
        extra = iscrizione.extra_dict()
        consenso_immagini = 'Si' if iscrizione.consenso_immagini else 'No'
        righe.append(
            f'- {iscrizione.nome} | Tel {iscrizione.telefono} | Email {iscrizione.email or "non indicata"} | '
            f'DPP {extra.get("data_presunta_parto", "non indicata")} | Partner {extra.get("partner_presente", "non indicato")} | '
            f'Immagini {consenso_immagini}'
        )
        if incontri:
            stati = []
            for incontro in incontri:
                presenza = presenze.get((iscrizione.id, incontro.id))
                if not presenza or presenza.presente is None:
                    valore = '-'
                else:
                    valore = 'P' if presenza.presente else 'A'
                stati.append(f'{incontro.numero}:{valore}')
            righe.append(f'  Presenze: {" ".join(stati)}')

    pdf = _crea_pdf_testuale(f'Iscritti - {percorso.titolo}', righe)
    filename = f'{percorso.slug}-iscritti.pdf'
    return Response(
        pdf,
        mimetype='application/pdf',
        headers={'Content-Disposition': f'attachment; filename="{filename}"'}
    )


@app.route('/admin/iscrizione-corso/aggiungi', methods=['POST'])
@login_required
def aggiungi_iscrizione_corso_manuale():
    token = session.pop('_csrf_token', None)
    if not token or token != request.form.get('_csrf_token'):
        flash('Richiesta non valida. Riprova.', 'error')
        return redirect(url_for('admin') + '#admin-corsi')

    corso_id = request.form.get('corso_id', type=int)
    corso = db.session.get(Corso, corso_id) if corso_id else None
    if not corso:
        flash('Seleziona un corso o laboratorio valido.', 'error')
        return redirect(url_for('admin') + '#admin-corsi')

    persona_id = request.form.get('persona_id', type=int)
    persona = db.session.get(PersonaCorso, persona_id) if persona_id else None

    nome = request.form.get('nome', '').strip()
    telefono = request.form.get('telefono', '').strip()
    email = request.form.get('email', '').strip()
    codice_fiscale = request.form.get('codice_fiscale', '').strip()
    nome_bambino = request.form.get('nome_bambino', '').strip()
    eta_bambino = request.form.get('eta_bambino', '').strip()
    note_persona = request.form.get('note_persona', '').strip()

    if persona:
        _aggiorna_persona_corso(
            persona,
            nome=nome,
            telefono=telefono,
            email=email,
            codice_fiscale=codice_fiscale,
            nome_bambino=nome_bambino,
            eta_bambino=eta_bambino,
            note=note_persona
        )
    else:
        if not nome or len(nome) > 100:
            flash('Inserisci nome e cognome della persona.', 'error')
            return redirect(url_for('admin') + '#admin-corsi')
        if not telefono or not _telefono_valido(telefono):
            flash('Inserisci un numero di telefono valido.', 'error')
            return redirect(url_for('admin') + '#admin-corsi')
        persona = _trova_o_crea_persona_corso(
            nome=nome,
            telefono=telefono,
            email=email,
            codice_fiscale=codice_fiscale,
            nome_bambino=nome_bambino,
            eta_bambino=eta_bambino,
            note=note_persona
        )

    nome = nome or persona.nome
    telefono = telefono or persona.telefono
    email = email or persona.email or ''
    codice_fiscale = codice_fiscale or persona.codice_fiscale or ''
    nome_bambino = nome_bambino or persona.nome_bambino or ''
    eta_bambino = eta_bambino or persona.eta_bambino or ''

    if not nome or len(nome) > 100:
        flash('Inserisci nome e cognome della persona.', 'error')
        return redirect(url_for('admin') + '#admin-corsi')
    if not telefono or not _telefono_valido(telefono):
        flash('Inserisci un numero di telefono valido.', 'error')
        return redirect(url_for('admin') + '#admin-corsi')
    if email and not _email_valida(email):
        flash('Inserisci un indirizzo email valido.', 'error')
        return redirect(url_for('admin') + '#admin-corsi')
    if len(codice_fiscale) > 32:
        flash('Il codice fiscale è troppo lungo.', 'error')
        return redirect(url_for('admin') + '#admin-corsi')
    if len(nome_bambino) > 100:
        flash('Il nome del bambino è troppo lungo.', 'error')
        return redirect(url_for('admin') + '#admin-corsi')
    if len(eta_bambino) > 40:
        flash('L\'età del bambino è troppo lunga.', 'error')
        return redirect(url_for('admin') + '#admin-corsi')

    tipo_richiesta = request.form.get('tipo_richiesta', 'iscrizione_effettiva').strip()
    if tipo_richiesta not in TIPI_RICHIESTA_CORSO:
        tipo_richiesta = 'iscrizione_effettiva'

    stato = request.form.get('stato', 'Confermato').strip()
    if stato not in STATI_ISCRIZIONE_VALIDI:
        stato = 'Confermato'

    partecipazione = request.form.get('partecipazione', '').strip() or 'Inserimento manuale'
    posti = request.form.get('posti', type=int)
    if posti is None or posti < 0:
        posti = _posti_iscrizione_da_partecipazione(partecipazione)
    if tipo_richiesta == 'ricontatto':
        posti = 0

    extra = {
        'inserimento_admin': True,
        'nome_bambino': nome_bambino,
        'eta_bambino': eta_bambino,
    }
    extra = {chiave: valore for chiave, valore in extra.items() if valore not in ['', None]}

    iscrizione = IscrizioneCorso(
        corso_id=corso.id,
        persona=persona,
        corso_tipo=corso.tipo or '',
        corso_titolo=corso.titolo,
        nome=nome,
        telefono=telefono,
        email=email,
        codice_fiscale=codice_fiscale,
        data_corso=_etichetta_data_corso(corso),
        partecipazione=partecipazione,
        note=request.form.get('note', '').strip(),
        dati_extra=json.dumps(extra, ensure_ascii=False),
        tipo_richiesta=tipo_richiesta,
        posti=posti,
        consenso_privacy=_checkbox_checked('consenso_privacy'),
        consenso_immagini=_checkbox_checked('consenso_immagini'),
        stato=stato,
    )
    db.session.add(iscrizione)
    db.session.commit()
    flash('Iscritto aggiunto al corso e salvato in rubrica.', 'success')
    return redirect(url_for('admin', corso_id=corso.id) + '#admin-corsi')


@app.route('/admin/corso/elimina/<int:id>')
@login_required
def elimina_corso(id):
    # Protezione CSRF (stesso ragionamento di aggiorna_stato)
    token = request.args.get('token')
    if not token or token != session.get('_csrf_token'):
        flash('Richiesta non valida. Riprova.', 'error')
        return redirect(url_for('admin'))
    corso = db.get_or_404(Corso, id)
    iscrizioni_attive = IscrizioneCorso.query.filter(
        IscrizioneCorso.corso_id == corso.id,
        IscrizioneCorso.stato != 'Annullato'
    ).count()
    if iscrizioni_attive:
        flash('Non puoi eliminare un corso con iscrizioni attive. Annulla prima le iscrizioni o chiudi il corso.', 'error')
        return redirect(url_for('admin') + '#admin-corsi')
    if not elimina_evento_calendario_corso(corso):
        flash('Il corso non è stato eliminato perché Google Calendar non è stato aggiornato. Controlla il registro eventi.', 'error')
        return redirect(url_for('admin') + '#admin-corsi')
    db.session.delete(corso)
    db.session.commit()
    return redirect(url_for('admin'))


@app.route('/admin/iscrizione-corso/<int:id>/<stato>')
@login_required
def aggiorna_stato_iscrizione_corso(id, stato):
    if stato not in STATI_ISCRIZIONE_VALIDI:
        abort(400)
    token = request.args.get('token')
    if not token or token != session.get('_csrf_token'):
        flash('Richiesta non valida. Riprova.', 'error')
        return redirect(url_for('admin'))
    iscrizione = db.get_or_404(IscrizioneCorso, id)
    iscrizione.stato = stato
    db.session.commit()
    return redirect(url_for('admin'))


@app.route('/api/orari-occupati/<data>')
def orari_occupati(data):
    # Restituisce la lista degli orari occupati per la data specificata (YYYY-MM-DD)
    ignore_id = request.args.get('ignore_id', type=int)
    orari = {
        ora for ora in ORARI_DISPONIBILI
        if slot_occupato_db(
            data,
            ora,
            DURATA_SLOT_MINUTI,
            ignore_appuntamento_id=ignore_id,
        )
    }
    # Aggiungi chiusure ricorrenti dello studio: domeniche, festivi e sabato pomeriggio
    orari |= orari_non_prenotabili_per_chiusura(data)
    # Aggiungi gli orari occupati su Arzamed/Google Calendar (appuntamenti e chiusure studio)
    orari |= orari_occupati_da_calendario(data)
    if ignore_id:
        appuntamento_ignorato = db.session.get(Appuntamento, ignore_id)
        if appuntamento_ignorato and appuntamento_ignorato.data == data:
            orari.discard(appuntamento_ignorato.ora)
    return jsonify(sorted(orari))


# ─── AVVIO ───

if __name__ == '__main__':
    app.run(debug=True)
