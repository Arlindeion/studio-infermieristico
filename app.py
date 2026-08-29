import logging
import calendar as calendar_module
import click
import csv
import io
import json
import re
from urllib.parse import urlsplit
from flask import Flask, render_template, request, redirect, url_for, flash, abort, session, jsonify, Response
from dotenv import load_dotenv
import os
import secrets
import threading
import time
from collections import defaultdict
from zoneinfo import ZoneInfo
from apscheduler.schedulers.background import BackgroundScheduler
import icalendar
import google_auth_httplib2
import httplib2
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
from datetime import datetime, date, time as datetime_time, timedelta, timezone
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.middleware.proxy_fix import ProxyFix
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_talisman import Talisman
from sqlalchemy import text as sql_text

# Configurazione del logging: su Render si usa soltanto stdout/stderr. Il file
# locale resta disponibile in sviluppo e non viene mai usato come archivio.
config_name = os.environ.get('FLASK_ENV', 'development')
log_handlers = [logging.StreamHandler()]
if config_name == 'development':
    log_handlers.insert(0, logging.FileHandler('app.log'))
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s:%(name)s: %(message)s',
    handlers=log_handlers,
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Caricamento della configurazione
app.config.from_object(config[config_name])
if config_name == 'production':
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

# Limite applicativo aggregato per IP sulle sole richieste dinamiche. I limiti
# più stretti dei moduli vengono applicati separatamente ai soli POST.
def _escludi_dal_limite_generale():
    return request.endpoint in {'static', 'healthz'}


limiter = Limiter(
    get_remote_address,
    app=app,
    application_limits=["10000 per day", "1000 per hour"],
    application_limits_exempt_when=_escludi_dal_limite_generale,
    headers_enabled=True,
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
        'style-src': ["'self'", "'unsafe-inline'"],
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
            "https://behold.pictures",
            "https://cdn2.behold.pictures",
            "https://*.cdninstagram.com",
            "https://www.google-analytics.com",
        ],
        'media-src': ["'self'", "https://*.cdninstagram.com"],
        'font-src': ["'self'"],
        'frame-src': ["'self'", "https://www.google.com"],
    },
    force_https=config_name == 'production',
    session_cookie_secure=os.environ.get('FLASK_ENV') == 'production',
    session_cookie_http_only=True,
    session_cookie_samesite='Lax',
)


@app.context_processor
def inject_tracking_config():
    return {
        'google_analytics_id': app.config.get('GOOGLE_ANALYTICS_ID'),
        'public_url': public_url,
        'prestazioni_categorie': PRESTAZIONI_CATEGORIE,
        'servizi_prenotabili': SERVIZI_PRENOTABILI,
    }


# ─── COSTANTI ───

PRESTAZIONI_CATEGORIE = [
    {
        'nome': 'Terapie e somministrazioni',
        'slug': 'terapie-somministrazioni',
        'prestazioni': [
            {'nome': 'Iniezione intramuscolare', 'prezzo': '12 €'},
            {'nome': 'Iniezione sottocutanea', 'prezzo': '10 €'},
            {'nome': 'Terapia infusionale / flebo', 'prezzo': 'da 20 €'},
            {'nome': 'Posizionamento accesso venoso', 'prezzo': '15 €'},
            {'nome': 'Gestione e medicazione PICC/CVC', 'prezzo': 'da 25 €'},
            {'nome': 'Lavaggio e mantenimento PICC/CVC', 'prezzo': 'da 20 €'},
            {'nome': 'Gestione della terapia farmacologica', 'prezzo': 'su valutazione'},
        ],
    },
    {
        'nome': 'Medicazioni',
        'slug': 'medicazioni',
        'nota': 'Il prezzo può variare in base alle condizioni della lesione, al tempo necessario e ai materiali utilizzati.',
        'prestazioni': [
            {'nome': 'Medicazione semplice', 'prezzo': '15 €'},
            {'nome': 'Medicazione chirurgica', 'prezzo': 'da 20 €'},
            {'nome': 'Rimozione punti di sutura o graffette', 'prezzo': '20 €'},
            {'nome': 'Medicazione avanzata di lesioni complesse', 'prezzo': 'da 30 €'},
            {'nome': 'Valutazione infermieristica della lesione', 'prezzo': '20 €'},
            {'nome': 'Cambio o gestione cannula tracheostomica', 'prezzo': 'da 25 €'},
        ],
    },
    {
        'nome': 'Controlli e diagnostica',
        'slug': 'controlli-diagnostica',
        'prestazioni': [
            {'nome': 'Controllo parametri vitali', 'prezzo': '10 €'},
            {'nome': 'Glicemia capillare', 'prezzo': '5 €'},
            {'nome': 'Elettrocardiogramma con referto', 'prezzo': '20 €'},
            {'nome': 'Holter pressorio 24 ore', 'prezzo': '55 €'},
            {'nome': 'Holter ECG 24 ore', 'prezzo': '80 €'},
            {'nome': 'Profilo lipidico capillare', 'prezzo': '20 €'},
            {'nome': 'Emoglobina glicata - HbA1c', 'prezzo': '15 €'},
            {'nome': 'Vitamina D', 'prezzo': '20 €'},
            {'nome': 'PSA', 'prezzo': '15 €'},
            {'nome': 'Profilo tiroideo TSH, FT3 e FT4', 'prezzo': '30 €'},
        ],
    },
    {
        'nome': 'Altre prestazioni',
        'slug': 'altre-prestazioni',
        'prestazioni': [
            {'nome': 'Lavaggio auricolare', 'prezzo': '30 €'},
            {'nome': 'Clistere evacuativo', 'prezzo': '30 €'},
            {'nome': 'Gestione stomia', 'prezzo': 'da 20 €'},
            {'nome': 'Gestione PEG', 'prezzo': 'da 20 €'},
            {'nome': 'Cateterismo vescicale', 'prezzo': 'da 25 €'},
            {'nome': 'Sostituzione catetere vescicale', 'prezzo': 'da 30 €'},
            {'nome': 'Educazione del caregiver', 'prezzo': 'da 30 €'},
            {'nome': 'Consulenza infermieristica', 'prezzo': '30 € all’ora'},
        ],
    },
]

SERVIZI_PRENOTABILI = [
    prestazione['nome']
    for categoria in PRESTAZIONI_CATEGORIE
    for prestazione in categoria['prestazioni']
]

# Mantiene validi i nomi usati dalle richieste create prima del nuovo listino.
SERVIZI_VALIDI = list(dict.fromkeys(SERVIZI_PRENOTABILI + [
    'Flebo e terapia infusionale',
    'Medicazione complessa',
    'Assistenza domiciliare',
    'Gestione terapia farmacologica',
]))

STATI_VALIDI = ['Confermato', 'Annullato', 'In attesa']
STATI_APPUNTAMENTO_ADMIN = ['In attesa', 'Confermato', 'Concluso', 'Assente', 'Annullato']
STATI_CALL_SONNO_VALIDI = ['In attesa', 'Confermata', 'Annullata', 'Conclusa']
FORMULE_SONNO = {
    'mirata': 'Consulenza mirata',
    'percorso': 'Percorso sonno personalizzato',
    'affiancamento': 'Percorso sonno con affiancamento',
}
DIFFICOLTA_SONNO = [
    'Addormentamento difficile la sera',
    'Risvegli notturni frequenti',
    'Pisolini difficili o brevi',
    'Addormentamento solo con forte supporto (braccio/seno)',
    'Cambiamenti / regressioni / distacchi',
    'Altro',
]
RUOLI_RICHIEDENTE_SONNO = [
    'Genitore con responsabilità genitoriale',
    'Tutore legale',
]
DURATE_DIFFICOLTA_SONNO = [
    'Da meno di 2 settimane',
    'Da 2 a 4 settimane',
    'Da 1 a 3 mesi',
    'Da più di 3 mesi',
    'Da sempre o quasi',
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
STATI_ISCRIZIONE_VALIDI = ['Nuova', 'Contattato', 'Confermato', 'Lista attesa', 'Invitato', 'Annullato']
STATI_LISTA_ATTESA = {'Lista attesa', 'Invitato'}
STATI_ISCRIZIONE_DA_GESTIRE = {'Nuova', 'Contattato', 'Lista attesa', 'Invitato'}
STATI_CORSO_VALIDI = ['Aperto', 'Completo', 'Chiuso', 'Annullato', 'Concluso']
STATI_PERCORSO_ACCOMPAGNAMENTO_VALIDI = ['Bozza', 'Aperto', 'Chiuso', 'Concluso']
STATI_RICHIESTA_AZIENDA = [
    'Nuova',
    'Contattata',
    'Qualificata',
    'Proposta inviata',
    'Confermata',
    'Chiusa',
]
TIPI_ORGANIZZAZIONE = [
    'Azienda',
    'Associazione',
    'Scuola o servizio educativo',
    'Gruppo privato',
    'Altro',
]
SEDI_AZIENDA = [
    'Presso lo studio',
    'Presso l’organizzazione',
    'Da valutare insieme',
]
MESI_ITALIANI = ['gennaio', 'febbraio', 'marzo', 'aprile', 'maggio', 'giugno', 'luglio', 'agosto', 'settembre', 'ottobre', 'novembre', 'dicembre']
GIORNI_SETTIMANA_BREVI = ['Lun', 'Mar', 'Mer', 'Gio', 'Ven', 'Sab', 'Dom']

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
        'durata_ore': 5,
    },
    'disostruzione-pediatrica': {
        'label': 'Disostruzione pediatrica e tagli sicuri',
        'titolo': 'Disostruzione pediatrica e tagli sicuri',
        'durata_ore': 2.5,
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

FORMAZIONE_AZIENDA_TIPI = {
    'bls-d': 'BLSD',
    'disostruzione-pediatrica': 'Disostruzione pediatrica e tagli sicuri',
    'altro': 'Altro corso o progetto da valutare',
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

CORSI_SLUG_PUBBLICI = {
    'bls-d': 'blsd',
}

COURSE_INTEREST_TOPICS = {
    'disostruzione-tagli-sicuri': {
        'label': 'Disostruzione pediatrica e tagli sicuri',
        'course_type': 'disostruzione-pediatrica',
    },
    'blsd': {
        'label': 'BLSD',
        'course_type': 'bls-d',
    },
    'accompagnamento-nascita': {
        'label': 'Accompagnamento alla nascita',
        'course_type': 'accompagnamento-nascita',
    },
    'laboratori': {
        'label': "Laboratori per l'infanzia",
        'course_type': 'laboratorio-infanzia',
    },
    'gioco-sviluppo': {
        'label': 'Gioco e sviluppo',
        'course_type': 'laboratorio-infanzia',
    },
}

COURSE_INTEREST_TOPIC_BY_TYPE = {
    'disostruzione-pediatrica': 'disostruzione-tagli-sicuri',
    'bls-d': 'blsd',
    'accompagnamento-nascita': 'accompagnamento-nascita',
    'laboratorio-infanzia': 'laboratori',
}

STUDIO_MAP_EMBED_SRC = "https://www.google.com/maps?q=Via%20C.%20D%27Agnese%2043%2C%2065015%20Montesilvano%20PE&output=embed"
STUDIO_MAP_LINK = "https://www.google.com/maps/search/?api=1&query=Via%20C.%20D%27Agnese%2043%2C%2065015%20Montesilvano%20PE"


FAQ_ITEMS = [
    {
        'id': 'corsi-disponibili',
        'question': 'Quali corsi in presenza sono disponibili per famiglie, genitori e aziende?',
        'answer': "Puoi scegliere tra BLSD, disostruzione pediatrica e tagli sicuri, corso di accompagnamento alla nascita e laboratori per l'infanzia. Ogni pagina indica a chi è rivolto il corso, che cosa si fa e come richiedere l'iscrizione.",
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
        'answer': "Se partecipi come privato, usa il modulo di iscrizione individuale per una delle date aperte. Per aziende e gruppi, contatta direttamente lo studio per concordare sede, data e numero di partecipanti.",
        'link_href': '/iscrizione-corsi/blsd',
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
        'answer': "Si comincia con un open day gratuito, durante il quale conosci il percorso e puoi fare domande. Se scegli il corso completo, lo studio ti invia in seguito il collegamento riservato per l'iscrizione.",
        'link_href': '/iscrizione-corsi/accompagnamento-nascita',
        'link_text': 'Vai all\'open day',
    },
    {
        'id': 'percorso-privato-accompagnamento-nascita',
        'question': 'Il link privato del corso di accompagnamento alla nascita conferma direttamente l\'iscrizione?',
        'answer': "No. Quando invii il modulo riservato, lo studio riceve la richiesta ma il posto non è ancora confermato. Riceverai l'email con la conferma, il calendario degli incontri e i contatti soltanto dopo la verifica dello studio.",
        'link_href': '/iscrizione-corsi/accompagnamento-nascita',
        'link_text': 'Scopri il percorso nascita',
    },
    {
        'id': 'durata-corsi',
        'question': 'Quanto durano i corsi?',
        'answer': "La durata dipende dal tipo di corso: il BLSD dura 5 ore, disostruzione pediatrica e tagli sicuri dura circa 2 ore e 30 minuti, i laboratori per l'infanzia durano circa 2 ore, mentre il corso completo di accompagnamento alla nascita è una serie di 9 incontri con infermiera, ostetrica, psicologa, osteopata e nutrizionista.",
        'link_href': '/iscrizione-corsi',
        'link_text': 'Vedi i corsi',
    },
    {
        'id': 'consulenza-sonno-infantile',
        'question': 'Quando può essere utile una consulenza sul sonno infantile?',
        'answer': "La consulenza è dedicata al sonno dei bambini da 0 a 12 mesi. Può essere utile quando addormentamento, risvegli o pisolini sono difficili da capire. La call gratuita serve a raccontare la difficoltà principale e verificare se il servizio è adatto alla famiglia.",
        'link_href': '/consulenze-online',
        'link_text': 'Scopri la consulenza del sonno',
    },
    {
        'id': 'consulenze-online-presenza',
        'question': 'La consulenza sul sonno è online o in presenza?',
        'answer': "La consulenza si svolge online in tutta Italia oppure in studio a Montesilvano. Prima di iniziare puoi prenotare una call gratuita per raccontarmi la difficoltà principale e verificare se il servizio è adatto.",
        'link_href': '/consulenze-online',
        'link_text': 'Vedi consulenze',
    },
    {
        'id': 'prenotare-prestazione-infermieristica',
        'question': 'Come posso prenotare una prestazione infermieristica?',
        'answer': "Dalla pagina Prenota inserisci i tuoi dati, scegli la prestazione, la data e l'orario, poi invii la richiesta. L'appuntamento è fissato solo dopo la conferma dello studio.",
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
        'answer': "Dopo l'invio, lo studio verifica manualmente disponibilità e indicazioni necessarie. L'appuntamento è fissato quando ricevi la conferma.",
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
APPOINTMENT_DURATION_MIN_MINUTES = 1
APPOINTMENT_DURATION_MAX_MINUTES = 480
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
UTC_TIMEZONE = timezone.utc


def utc_now():
    """Return an unambiguous UTC instant for timezone-naive DB columns."""
    return datetime.now(UTC_TIMEZONE).replace(tzinfo=None)


def local_now():
    """Return the current civil time in Italy for business-calendar rules."""
    return datetime.now(FUSO_ORARIO)


def local_now_naive():
    """Return Italian wall time for legacy business-deadline columns."""
    return local_now().replace(tzinfo=None)


def local_today():
    return local_now().date()


def as_local_time(value):
    """Convert a persisted UTC instant to Europe/Rome, including DST rules."""
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC_TIMEZONE)
    return value.astimezone(FUSO_ORARIO)


@app.template_filter('local_timestamp')
def format_local_timestamp(value, format_string='%d/%m/%Y %H:%M %Z'):
    local_value = as_local_time(value)
    return local_value.strftime(format_string) if local_value else ''


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


def parse_appointment_duration(value):
    try:
        duration_minutes = int(value)
    except (TypeError, ValueError):
        return None
    if (
        duration_minutes < APPOINTMENT_DURATION_MIN_MINUTES
        or duration_minutes > APPOINTMENT_DURATION_MAX_MINUTES
    ):
        return None
    return duration_minutes


def is_appointment_interval_bookable(data_str, ora, duration_minutes):
    if not orario_prenotabile(data_str, ora):
        return False
    try:
        start, end = _intervallo_locale(data_str, ora, duration_minutes)
    except (TypeError, ValueError):
        return False

    day = start.date()
    if day.weekday() == 5:
        closing_time = datetime.combine(day, datetime_time(12, 0), tzinfo=FUSO_ORARIO)
        return end <= closing_time

    if start.time() < datetime_time(14, 0):
        closing_time = datetime.combine(day, datetime_time(13, 0), tzinfo=FUSO_ORARIO)
    else:
        closing_time = datetime.combine(day, datetime_time(19, 0), tzinfo=FUSO_ORARIO)
    return end <= closing_time


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
# Arzamed sincronizza appuntamenti e chiusure studio sul calendario Google
# operativo. Il sito usa lo stesso account di servizio sia per leggere gli
# intervalli occupati sia per creare, modificare e cancellare i propri eventi.
# La lettura usa singleEvents=True, così Google espande anche le ricorrenze.

_cache_calendario = {
    'per_data': {},
    'errore_registrato_il': 0.0,
    'circuito_aperto_fino': 0.0,
    'ultimo_errore': None,
}
_lock_stato_calendario = threading.RLock()
_lock_letture_calendario = tuple(threading.Lock() for _ in range(16))
_lock_riconciliazione_admin = threading.Lock()
_ultima_riconciliazione_admin = 0.0


def _invalida_cache_calendario():
    with _lock_stato_calendario:
        _cache_calendario['per_data'].clear()


def _azzera_stato_calendario():
    """Azzera cache e circuito; usato dai test e dopo cambi di configurazione."""
    global _ultima_riconciliazione_admin
    with _lock_stato_calendario:
        _cache_calendario['per_data'].clear()
        _cache_calendario['errore_registrato_il'] = 0.0
        _cache_calendario['circuito_aperto_fino'] = 0.0
        _cache_calendario['ultimo_errore'] = None
    with _lock_riconciliazione_admin:
        _ultima_riconciliazione_admin = 0.0


def _chiave_cache_calendario(data_str):
    return app.config.get('GOOGLE_CALENDAR_ID') or '', data_str


def _lock_lettura_calendario(chiave):
    indice = sum(ord(carattere) for parte in chiave for carattere in parte) % len(
        _lock_letture_calendario
    )
    return _lock_letture_calendario[indice]


def _circuito_calendario_aperto(adesso=None):
    adesso = time.monotonic() if adesso is None else adesso
    with _lock_stato_calendario:
        return adesso < _cache_calendario['circuito_aperto_fino']


def _apri_circuito_calendario(errore):
    adesso = time.monotonic()
    durata = max(1, app.config.get('CALENDARIO_CACHE_ERRORE_SECONDI', 30))
    with _lock_stato_calendario:
        _cache_calendario['circuito_aperto_fino'] = max(
            _cache_calendario['circuito_aperto_fino'],
            adesso + durata,
        )
        _cache_calendario['ultimo_errore'] = type(errore).__name__


def _chiudi_circuito_calendario():
    with _lock_stato_calendario:
        _cache_calendario['circuito_aperto_fino'] = 0.0
        _cache_calendario['ultimo_errore'] = None


def _registra_errore_lettura_calendario(tipo_errore, adesso, durata_cache):
    with _lock_stato_calendario:
        if adesso < _cache_calendario['errore_registrato_il'] + durata_cache:
            return
        _cache_calendario['errore_registrato_il'] = adesso
    registra_evento(
        'google_calendar',
        'errore',
        'Lettura del calendario non disponibile; usata la copia in cache quando presente.',
        dettagli={'tipo_errore': tipo_errore},
    )


def _intervalli_cache_fallback(voce_cache, adesso):
    if not voce_cache:
        return []
    durata_stale = max(
        app.config.get('CALENDARIO_CACHE_SECONDI', 300),
        app.config.get('CALENDARIO_CACHE_STALE_SECONDI', 900),
    )
    if adesso <= voce_cache['scaricato_il'] + durata_stale:
        return voce_cache['intervalli']
    return []


def _datetime_evento_google(valore, timezone_evento=None):
    """Normalizza date e dateTime restituite dalla Calendar API."""
    if not valore:
        return None
    if 'T' not in valore:
        return datetime.combine(
            datetime.strptime(valore, '%Y-%m-%d').date(),
            datetime.min.time(),
            tzinfo=FUSO_ORARIO,
        )

    data_ora = datetime.fromisoformat(valore.replace('Z', '+00:00'))
    if data_ora.tzinfo is None:
        try:
            fuso_evento = ZoneInfo(timezone_evento) if timezone_evento else FUSO_ORARIO
        except (KeyError, ValueError):
            fuso_evento = FUSO_ORARIO
        data_ora = data_ora.replace(tzinfo=fuso_evento)
    return data_ora.astimezone(FUSO_ORARIO)


def _intervallo_da_evento_google(evento):
    inizio_dati = evento.get('start') or {}
    fine_dati = evento.get('end') or {}
    inizio = _datetime_evento_google(
        inizio_dati.get('dateTime') or inizio_dati.get('date'),
        inizio_dati.get('timeZone'),
    )
    fine = _datetime_evento_google(
        fine_dati.get('dateTime') or fine_dati.get('date'),
        fine_dati.get('timeZone'),
    )
    if inizio is None:
        return None
    if fine is None:
        fine = inizio
    return inizio, fine, str(evento.get('id') or '')


def _scarica_intervalli_calendario(data_str):
    """Legge via API gli intervalli di un giorno, con cache e fallback stale."""
    try:
        giorno = datetime.strptime(data_str, '%Y-%m-%d').date()
    except (TypeError, ValueError):
        return []

    if not _integrazione_calendar_abilitata():
        return []

    adesso = time.monotonic()
    durata_cache = app.config.get('CALENDARIO_CACHE_SECONDI', 300)
    chiave_cache = _chiave_cache_calendario(data_str)
    with _lock_stato_calendario:
        voce_cache = _cache_calendario['per_data'].get(chiave_cache)
    if voce_cache and adesso < voce_cache['scaricato_il'] + durata_cache:
        return voce_cache['intervalli']

    calendar_id = app.config.get('GOOGLE_CALENDAR_ID')
    if not calendar_id:
        return _intervalli_cache_fallback(voce_cache, adesso)
    if _circuito_calendario_aperto(adesso):
        return _intervalli_cache_fallback(voce_cache, adesso)

    # Più richieste possono arrivare insieme con cache fredda. Una sola legge
    # Google; le altre ricontrollano la cache dopo aver atteso lo stesso giorno.
    with _lock_lettura_calendario(chiave_cache):
        adesso = time.monotonic()
        with _lock_stato_calendario:
            voce_cache = _cache_calendario['per_data'].get(chiave_cache)
        if voce_cache and adesso < voce_cache['scaricato_il'] + durata_cache:
            return voce_cache['intervalli']
        if _circuito_calendario_aperto(adesso):
            return _intervalli_cache_fallback(voce_cache, adesso)

        servizio = _ottieni_servizio_calendario()
        if servizio is None:
            _registra_errore_lettura_calendario(
                'servizio_non_disponibile',
                adesso,
                durata_cache,
            )
            return _intervalli_cache_fallback(voce_cache, adesso)

        inizio_giornata = datetime.combine(giorno, datetime.min.time(), tzinfo=FUSO_ORARIO)
        fine_giornata = inizio_giornata + timedelta(days=1)
        intervalli = []
        page_token = None

        try:
            while True:
                parametri = {
                    'calendarId': calendar_id,
                    'timeMin': inizio_giornata.isoformat(),
                    'timeMax': fine_giornata.isoformat(),
                    'singleEvents': True,
                    'showDeleted': False,
                    'orderBy': 'startTime',
                    'maxResults': 2500,
                }
                if page_token:
                    parametri['pageToken'] = page_token
                richiesta = servizio.events().list(**parametri)
                risposta = _esegui_richiesta_calendario(richiesta)
                for evento in risposta.get('items', []):
                    if evento.get('status') == 'cancelled':
                        continue
                    intervallo = _intervallo_da_evento_google(evento)
                    if intervallo is not None:
                        intervalli.append(intervallo)
                page_token = risposta.get('nextPageToken')
                if not isinstance(page_token, str) or not page_token:
                    break

            with _lock_stato_calendario:
                _cache_calendario['per_data'][chiave_cache] = {
                    'intervalli': intervalli,
                    'scaricato_il': adesso,
                }
            return intervalli
        except Exception as errore:
            logger.error(
                '>>> Errore nella lettura Google Calendar API (%s).',
                type(errore).__name__,
                exc_info=True,
            )
            _registra_errore_lettura_calendario(
                type(errore).__name__,
                adesso,
                durata_cache,
            )
            return _intervalli_cache_fallback(voce_cache, adesso)


def _intervalli_calendario(data_str, ignore_google_event_id=None):
    """Restituisce gli intervalli occupati nel giorno richiesto."""
    return [
        (inizio, fine)
        for inizio, fine, event_id in _scarica_intervalli_calendario(data_str)
        if not ignore_google_event_id or event_id != ignore_google_event_id
    ]


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
    try:
        giorno = datetime.strptime(data_str, '%Y-%m-%d').date()
    except (TypeError, ValueError):
        return set()
    intervalli = _intervalli_calendario(data_str)
    occupati = set()
    for ora in ORARI_DISPONIBILI:
        ore, minuti = map(int, ora.split(':'))
        inizio_slot = datetime.combine(
            giorno,
            datetime.min.time(),
            tzinfo=FUSO_ORARIO,
        ).replace(hour=ore, minute=minuti)
        fine_slot = inizio_slot + timedelta(minutes=DURATA_SLOT_MINUTI)
        if any(
            inizio_slot < fine_evento and inizio_evento < fine_slot
            for inizio_evento, fine_evento in intervalli
        ):
            occupati.add(ora)
    return occupati


# ─── CLIENT GOOGLE CALENDAR (account di servizio) ───
#
# Quando un appuntamento viene confermato dall'area admin, creiamo un evento
# corrispondente sul calendario Google (lo stesso usato da Arzamed), così chi
# controlla il calendario vede anche le prenotazioni arrivate dal sito.
# Se l'appuntamento viene poi annullato o spostato, aggiorniamo/eliminiamo
# anche l'evento, per restare sincronizzati nei due sensi.
#
# Lettura e scrittura passano dalla stessa Calendar API e dallo stesso account
# di servizio, condiviso soltanto sul calendario operativo.

def _integrazione_calendar_abilitata():
    """Richiede l'opt-in esplicito soltanto nell'ambiente di staging."""
    return not (
        app.config.get('APP_ENV') == 'staging'
        and not app.config.get('STAGING_LIVE_INTEGRATIONS')
    )


def _ottieni_servizio_calendario():
    """Crea un client Calendar isolato con un proprio trasporto HTTP."""
    if not _integrazione_calendar_abilitata():
        return None
    if _circuito_calendario_aperto():
        return None

    percorso_chiave = app.config.get('GOOGLE_SERVICE_ACCOUNT_FILE')
    if not percorso_chiave:
        logger.warning('>>> Google Calendar non configurato: GOOGLE_SERVICE_ACCOUNT_FILE mancante.')
        return None

    try:
        credenziali = service_account.Credentials.from_service_account_file(
            percorso_chiave,
            scopes=['https://www.googleapis.com/auth/calendar.events']
        )
        trasporto = httplib2.Http(
            timeout=max(1, app.config.get('GOOGLE_CALENDAR_TIMEOUT_SECONDI', 5))
        )
        http_autorizzato = google_auth_httplib2.AuthorizedHttp(
            credenziali,
            http=trasporto,
        )
        return build(
            'calendar',
            'v3',
            http=http_autorizzato,
            cache_discovery=False,
        )
    except Exception as e:
        _apri_circuito_calendario(e)
        logger.error(f'>>> Errore nell\'autenticazione con Google Calendar: {e}', exc_info=True)
        return None


def _esegui_richiesta_calendario(richiesta, ignora_assenza_evento=False):
    """Esegue senza retry sincroni lunghi e aggiorna il circuito di errore."""
    try:
        risposta = richiesta.execute(num_retries=0)
    except Exception as errore:
        status = (
            getattr(getattr(errore, 'resp', None), 'status', None)
            or getattr(errore, 'status_code', None)
        )
        if not (ignora_assenza_evento and status in (404, 410)):
            _apri_circuito_calendario(errore)
        raise
    _chiudi_circuito_calendario()
    return risposta


def _corpo_evento_da_appuntamento(appuntamento):
    """Costruisce il corpo dell'evento Google Calendar a partire da un Appuntamento."""
    ora, minuto = map(int, appuntamento.ora.split(':'))
    giorno = datetime.strptime(appuntamento.data, '%Y-%m-%d').date()
    inizio = datetime.combine(giorno, datetime.min.time(), tzinfo=FUSO_ORARIO).replace(hour=ora, minute=minuto)
    fine = inizio + timedelta(
        minutes=appuntamento.duration_minutes or DURATA_SLOT_MINUTI
    )

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
        'extendedProperties': {'private': {
            'studioSource': 'sito-admin',
            'studioEntity': 'Appuntamento',
            'studioEntityId': str(appuntamento.id),
        }},
    }


def _corpo_evento_da_corso(corso):
    """Costruisce il corpo dell'evento Google Calendar a partire da un Corso."""
    giorno = datetime.strptime(corso.data, '%Y-%m-%d').date()
    descrizione = corso.descrizione or 'Nessuna descrizione'
    durata_ore = corso.durata_ore or DURATA_CORSO_DEFAULT_ORE
    corpo = {
        'summary': f'Corso: {corso.titolo}',
        'description': f'{descrizione}\n\n(Corso inserito dall\'area admin del sito web)',
        'extendedProperties': {'private': {
            'studioSource': 'sito-admin',
            'studioEntity': 'Corso',
            'studioEntityId': str(corso.id),
        }},
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
        appuntamento.sincronizzazione = 'errore'
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
        appuntamento.sincronizzazione = 'errore'
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
            _esegui_richiesta_calendario(servizio.events().patch(
                calendarId=calendar_id,
                eventId=appuntamento.google_event_id,
                body=corpo
            ))
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
            evento_creato = _esegui_richiesta_calendario(
                servizio.events().insert(calendarId=calendar_id, body=corpo)
            )
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
        appuntamento.sincronizzazione = 'sincronizzato'
        appuntamento.difformita_calendario = None
        db.session.commit()
        _invalida_cache_calendario()
        return True
    except HttpError as e:
        appuntamento.sincronizzazione = 'errore'
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
        appuntamento.sincronizzazione = 'errore'
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
        'extendedProperties': {'private': {
            'studioSource': 'sito-admin',
            'studioEntity': 'CallSonno',
            'studioEntityId': str(call.id),
        }},
    }


def crea_o_aggiorna_evento_calendario_call_sonno(call):
    """Blocca subito la call su Calendar; il salvataggio DB resta prioritario."""
    calendar_id = app.config.get('GOOGLE_CALENDAR_ID')
    servizio = _ottieni_servizio_calendario()
    if not calendar_id or servizio is None:
        call.sincronizzazione = 'errore'
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
            _esegui_richiesta_calendario(servizio.events().patch(
                calendarId=calendar_id,
                eventId=call.google_event_id,
                body=corpo,
            ))
        else:
            evento = _esegui_richiesta_calendario(
                servizio.events().insert(calendarId=calendar_id, body=corpo)
            )
            call.google_event_id = evento.get('id')
            db.session.commit()
        call.sincronizzazione = 'sincronizzato'
        call.difformita_calendario = None
        db.session.commit()
        _invalida_cache_calendario()
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
        call.sincronizzazione = 'errore'
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
        _esegui_richiesta_calendario(
            servizio.events().delete(calendarId=calendar_id, eventId=call.google_event_id),
            ignora_assenza_evento=True,
        )
        call.google_event_id = None
        db.session.commit()
        _invalida_cache_calendario()
        return True
    except HttpError as errore:
        if getattr(errore, 'status_code', None) not in (404, 410):
            registra_evento('google_calendar', 'errore', 'Errore eliminazione call sonno da Calendar.', 'CallSonno', call.id, {'errore': str(errore)})
            return False
        call.google_event_id = None
        db.session.commit()
        _invalida_cache_calendario()
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
        corso.sincronizzazione = 'errore'
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
        corso.sincronizzazione = 'errore'
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
            _esegui_richiesta_calendario(servizio.events().patch(
                calendarId=calendar_id,
                eventId=corso.google_event_id,
                body=corpo
            ))
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
            evento_creato = _esegui_richiesta_calendario(
                servizio.events().insert(calendarId=calendar_id, body=corpo)
            )
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
        corso.sincronizzazione = 'sincronizzato'
        db.session.commit()
        _invalida_cache_calendario()
        return True
    except HttpError as e:
        corso.sincronizzazione = 'errore'
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
        corso.sincronizzazione = 'errore'
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
        _esegui_richiesta_calendario(
            servizio.events().delete(calendarId=calendar_id, eventId=appuntamento.google_event_id),
            ignora_assenza_evento=True,
        )
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
        _invalida_cache_calendario()
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
        _esegui_richiesta_calendario(
            servizio.events().delete(calendarId=calendar_id, eventId=corso.google_event_id),
            ignora_assenza_evento=True,
        )
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
        corso.sincronizzazione = 'non_collegato'
        db.session.commit()
        _invalida_cache_calendario()
    return eliminato


def _corpo_evento_da_incontro(incontro):
    durata = 120
    inizio, fine = _intervallo_locale(incontro.data, incontro.ora or '09:00', durata)
    return {
        'summary': f'{incontro.percorso.titolo} · {incontro.numero}/9 · {incontro.tema}',
        'description': (
            f'Professionista: {incontro.professionista}\n'
            f'Note: {incontro.note or "Nessuna"}\n'
            '(Incontro inserito dall’area admin del sito web)'
        ),
        'location': incontro.luogo or 'Studio infermieristico',
        'start': {'dateTime': inizio.isoformat(), 'timeZone': 'Europe/Rome'},
        'end': {'dateTime': fine.isoformat(), 'timeZone': 'Europe/Rome'},
        'extendedProperties': {'private': {
            'studioSource': 'sito-admin',
            'studioEntity': 'IncontroAccompagnamento',
            'studioEntityId': str(incontro.id),
        }},
    }


def _corpo_evento_da_blocco(blocco):
    inizio, fine = _intervallo_locale(blocco.data, blocco.ora, blocco.durata_minuti)
    return {
        'summary': f'Blocco studio: {blocco.titolo}',
        'description': blocco.note or 'Pausa o chiusura inserita dall’area admin.',
        'start': {'dateTime': inizio.isoformat(), 'timeZone': 'Europe/Rome'},
        'end': {'dateTime': fine.isoformat(), 'timeZone': 'Europe/Rome'},
        'transparency': 'opaque',
        'extendedProperties': {'private': {
            'studioSource': 'sito-admin',
            'studioEntity': 'BloccoAgenda',
            'studioEntityId': str(blocco.id),
        }},
    }


def _sincronizza_evento_generico(entita, tipo, corpo):
    calendar_id = app.config.get('GOOGLE_CALENDAR_ID')
    servizio = _ottieni_servizio_calendario()
    if not calendar_id or servizio is None:
        entita.sincronizzazione = 'errore'
        db.session.commit()
        registra_evento('google_calendar', 'errore', f'{tipo} salvato, ma Calendar non è disponibile.', tipo, entita.id)
        return False
    try:
        if entita.google_event_id:
            _esegui_richiesta_calendario(
                servizio.events().patch(
                    calendarId=calendar_id,
                    eventId=entita.google_event_id,
                    body=corpo,
                )
            )
        else:
            evento = _esegui_richiesta_calendario(
                servizio.events().insert(calendarId=calendar_id, body=corpo)
            )
            entita.google_event_id = evento.get('id')
        entita.sincronizzazione = 'sincronizzato'
        db.session.commit()
        _invalida_cache_calendario()
        registra_evento('google_calendar', 'successo', f'{tipo} sincronizzato su Google Calendar.', tipo, entita.id, {'google_event_id': entita.google_event_id})
        return True
    except Exception as errore:
        entita.sincronizzazione = 'errore'
        db.session.commit()
        registra_evento('google_calendar', 'errore', f'Errore Calendar durante la sincronizzazione di {tipo}.', tipo, entita.id, {'errore': str(errore)})
        return False


def crea_o_aggiorna_evento_calendario_incontro(incontro):
    return _sincronizza_evento_generico(incontro, 'IncontroAccompagnamento', _corpo_evento_da_incontro(incontro))


def crea_o_aggiorna_evento_calendario_blocco(blocco):
    return _sincronizza_evento_generico(blocco, 'BloccoAgenda', _corpo_evento_da_blocco(blocco))


def elimina_evento_calendario_generico(entita, tipo):
    if not entita.google_event_id:
        entita.sincronizzazione = 'non_collegato'
        db.session.commit()
        return True
    calendar_id = app.config.get('GOOGLE_CALENDAR_ID')
    servizio = _ottieni_servizio_calendario()
    if not calendar_id or servizio is None:
        entita.sincronizzazione = 'errore'
        db.session.commit()
        registra_evento('google_calendar', 'errore', f'{tipo} archiviato, ma l’evento Calendar non è stato rimosso.', tipo, entita.id)
        return False
    try:
        _esegui_richiesta_calendario(
            servizio.events().delete(calendarId=calendar_id, eventId=entita.google_event_id),
            ignora_assenza_evento=True,
        )
    except HttpError as errore:
        if getattr(errore, 'status_code', None) not in (404, 410):
            entita.sincronizzazione = 'errore'
            db.session.commit()
            registra_evento('google_calendar', 'errore', f'Errore eliminazione Calendar di {tipo}.', tipo, entita.id, {'errore': str(errore)})
            return False
    entita.google_event_id = None
    entita.sincronizzazione = 'non_collegato'
    db.session.commit()
    _invalida_cache_calendario()
    return True


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
    duration_minutes = db.Column(
        db.Integer,
        default=DURATA_SLOT_MINUTI,
        nullable=False,
    )
    note = db.Column(db.Text, nullable=True)
    consenso_privacy = db.Column(db.Boolean, default=False, nullable=False)
    stato = db.Column(db.String(20), default='In attesa')
    creato_il = db.Column(db.DateTime, default=utc_now)
    # ID dell'evento creato su Google Calendar quando l'appuntamento viene
    # confermato (None se non ancora confermato, o se la scrittura su
    # Google Calendar non è configurata/è fallita).
    google_event_id = db.Column(db.String(255), nullable=True)
    scadenza_gestione = db.Column(db.DateTime, nullable=True, index=True)
    sincronizzazione = db.Column(db.String(30), default='da_sincronizzare', nullable=False, index=True)
    difformita_calendario = db.Column(db.Text, nullable=True)
    creato_da_admin = db.Column(db.Boolean, default=False, nullable=False)
    archiviato_il = db.Column(db.DateTime, nullable=True, index=True)


class CallSonno(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    telefono = db.Column(db.String(20), nullable=False)
    email = db.Column(db.String(100), nullable=False)
    eta_bambino_mesi = db.Column(db.Integer, nullable=False)
    difficolta_principale = db.Column(db.String(120), nullable=False)
    difficolta_altro = db.Column(db.String(300), nullable=True)
    ruolo_richiedente = db.Column(db.String(60), nullable=True)
    durata_difficolta = db.Column(db.String(60), nullable=True)
    obiettivo_call = db.Column(db.String(300), nullable=True)
    presa_visione_offerta = db.Column(db.Boolean, default=False, nullable=False)
    conferma_ambito = db.Column(db.Boolean, default=False, nullable=False)
    consenso_privacy = db.Column(db.Boolean, default=False, nullable=False)
    data = db.Column(db.String(20), nullable=False, index=True)
    ora = db.Column(db.String(10), nullable=False)
    stato = db.Column(db.String(20), default='In attesa', nullable=False, index=True)
    google_event_id = db.Column(db.String(255), nullable=True)
    formula_scelta = db.Column(db.String(30), nullable=True)
    token_questionario = db.Column(db.String(96), unique=True, nullable=True, index=True)
    questionario_inviato_il = db.Column(db.DateTime, nullable=True)
    promemoria_email_24h_il = db.Column(db.DateTime, nullable=True)
    promemoria_email_2h_il = db.Column(db.DateTime, nullable=True)
    utm_source = db.Column(db.String(100), nullable=True)
    utm_medium = db.Column(db.String(100), nullable=True)
    utm_campaign = db.Column(db.String(100), nullable=True)
    utm_content = db.Column(db.String(100), nullable=True)
    creato_il = db.Column(db.DateTime, default=utc_now, nullable=False)
    aggiornato_il = db.Column(db.DateTime, default=utc_now, onupdate=utc_now, nullable=False)
    scadenza_gestione = db.Column(db.DateTime, nullable=True, index=True)
    sincronizzazione = db.Column(db.String(30), default='da_sincronizzare', nullable=False, index=True)
    difformita_calendario = db.Column(db.Text, nullable=True)
    archiviata_il = db.Column(db.DateTime, nullable=True, index=True)


class QuestionarioSonno(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    call_sonno_id = db.Column(db.Integer, db.ForeignKey('call_sonno.id'), unique=True, nullable=False)
    risposte = db.Column(db.Text, nullable=False)
    consenso_dati_sanitari = db.Column(db.Boolean, default=False, nullable=False)
    consenso_marketing = db.Column(db.Boolean, default=False, nullable=False)
    compilato_il = db.Column(db.DateTime, default=utc_now, nullable=False)
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
    creato_il = db.Column(db.DateTime, default=utc_now)
    google_event_id = db.Column(db.String(255), nullable=True)
    sincronizzazione = db.Column(db.String(30), default='da_sincronizzare', nullable=False, index=True)
    archiviato_il = db.Column(db.DateTime, nullable=True, index=True)


class PersonaCorso(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    telefono = db.Column(db.String(20), nullable=True)
    email = db.Column(db.String(100), nullable=True)
    codice_fiscale = db.Column(db.String(32), nullable=True)
    nome_bambino = db.Column(db.String(100), nullable=True)
    eta_bambino = db.Column(db.String(40), nullable=True)
    note = db.Column(db.Text, nullable=True)
    creato_il = db.Column(db.DateTime, default=utc_now)
    aggiornato_il = db.Column(db.DateTime, default=utc_now, onupdate=utc_now)


class PercorsoAccompagnamento(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    titolo = db.Column(db.String(200), nullable=False)
    slug = db.Column(db.String(120), unique=True, nullable=False)
    descrizione = db.Column(db.Text, nullable=True)
    capienza_coppie = db.Column(db.Integer, nullable=True)
    luogo = db.Column(db.String(200), nullable=True)
    contatti = db.Column(db.String(200), default='3806317175', nullable=True)
    stato = db.Column(db.String(20), default='Aperto', nullable=False)
    creato_il = db.Column(db.DateTime, default=utc_now)


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
    creato_il = db.Column(db.DateTime, default=utc_now)
    google_event_id = db.Column(db.String(255), nullable=True)
    sincronizzazione = db.Column(db.String(30), default='da_sincronizzare', nullable=False, index=True)
    archiviato_il = db.Column(db.DateTime, nullable=True, index=True)
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
    data_corso = db.Column(db.String(255), nullable=True)
    partecipazione = db.Column(db.String(100), nullable=True)
    note = db.Column(db.Text, nullable=True)
    dati_extra = db.Column(db.Text, nullable=True)
    tipo_richiesta = db.Column(db.String(40), default='richiesta_iscrizione', nullable=False)
    posti = db.Column(db.Integer, default=1, nullable=False)
    consenso_privacy = db.Column(db.Boolean, default=False, nullable=False)
    consenso_immagini = db.Column(db.Boolean, default=False, nullable=False)
    stato = db.Column(db.String(20), default='Nuova', nullable=False)
    creato_il = db.Column(db.DateTime, default=utc_now)
    scadenza_gestione = db.Column(db.DateTime, nullable=True, index=True)
    posti_richiesti = db.Column(db.Integer, default=1, nullable=False)
    token_lista_attesa = db.Column(db.String(96), unique=True, nullable=True, index=True)
    invito_lista_attesa_il = db.Column(db.DateTime, nullable=True)
    scadenza_invito_lista_attesa = db.Column(db.DateTime, nullable=True, index=True)
    superamento_capienza_motivo = db.Column(db.Text, nullable=True)
    archiviata_il = db.Column(db.DateTime, nullable=True, index=True)
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


class RichiestaAzienda(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    organizzazione = db.Column(db.String(160), nullable=False, index=True)
    referente = db.Column(db.String(100), nullable=False, index=True)
    telefono = db.Column(db.String(20), nullable=False)
    email = db.Column(db.String(100), nullable=False, index=True)
    tipo_organizzazione = db.Column(db.String(60), nullable=False)
    corso_tipo = db.Column(db.String(80), nullable=False, index=True)
    partecipanti_stimati = db.Column(db.Integer, nullable=True)
    sede_preferita = db.Column(db.String(60), nullable=False)
    periodo_preferito = db.Column(db.String(160), nullable=True)
    note = db.Column(db.Text, nullable=True)
    consenso_privacy = db.Column(db.Boolean, default=False, nullable=False)
    stato = db.Column(db.String(30), default='Nuova', nullable=False, index=True)
    scadenza_gestione = db.Column(db.DateTime, nullable=True, index=True)
    corso_generato_id = db.Column(db.Integer, db.ForeignKey('corso.id'), nullable=True, index=True)
    creato_il = db.Column(db.DateTime, default=utc_now, nullable=False, index=True)
    aggiornato_il = db.Column(db.DateTime, default=utc_now, onupdate=utc_now, nullable=False)
    archiviata_il = db.Column(db.DateTime, nullable=True, index=True)
    corso_generato = db.relationship(
        'Corso',
        foreign_keys=[corso_generato_id],
        backref=db.backref('richiesta_azienda_origine', uselist=False),
    )


class PresenzaAccompagnamento(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    iscrizione_id = db.Column(db.Integer, db.ForeignKey('iscrizione_corso.id'), nullable=False)
    incontro_id = db.Column(db.Integer, db.ForeignKey('incontro_accompagnamento.id'), nullable=False)
    presente = db.Column(db.Boolean, nullable=True)
    note = db.Column(db.Text, nullable=True)
    aggiornata_il = db.Column(db.DateTime, default=utc_now, onupdate=utc_now)
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
    creato_il = db.Column(db.DateTime, default=utc_now, index=True)
    risolto_il = db.Column(db.DateTime, nullable=True, index=True)
    nota_risoluzione = db.Column(db.Text, nullable=True)

    def dettagli_dict(self):
        if not self.dettagli:
            return {}
        try:
            return json.loads(self.dettagli)
        except json.JSONDecodeError:
            return {}


class AttivitaAdmin(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    titolo = db.Column(db.String(180), nullable=False)
    stato = db.Column(db.String(20), default='Aperta', nullable=False, index=True)
    scadenza = db.Column(db.DateTime, nullable=False, index=True)
    entita_tipo = db.Column(db.String(40), nullable=True, index=True)
    entita_id = db.Column(db.Integer, nullable=True, index=True)
    note = db.Column(db.Text, nullable=True)
    creata_il = db.Column(db.DateTime, default=utc_now, nullable=False)
    aggiornata_il = db.Column(db.DateTime, default=utc_now, onupdate=utc_now, nullable=False)


class NotaAdmin(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    entita_tipo = db.Column(db.String(40), nullable=False, index=True)
    entita_id = db.Column(db.Integer, nullable=False, index=True)
    testo = db.Column(db.Text, nullable=False)
    creata_il = db.Column(db.DateTime, default=utc_now, nullable=False, index=True)
    aggiornata_il = db.Column(db.DateTime, default=utc_now, onupdate=utc_now, nullable=False)


class EmailOperativa(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    entita_tipo = db.Column(db.String(40), nullable=True, index=True)
    entita_id = db.Column(db.Integer, nullable=True, index=True)
    destinatario = db.Column(db.String(255), nullable=False)
    oggetto = db.Column(db.String(255), nullable=False)
    corpo = db.Column(db.Text, nullable=False)
    stato = db.Column(db.String(20), nullable=False, index=True)
    errore = db.Column(db.Text, nullable=True)
    inviata_il = db.Column(db.DateTime, nullable=True, index=True)
    creata_il = db.Column(db.DateTime, default=utc_now, nullable=False)
    scade_il = db.Column(db.DateTime, nullable=False, index=True)


class PropostaSlot(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    token = db.Column(db.String(96), unique=True, nullable=False, index=True)
    entita_tipo = db.Column(db.String(40), nullable=False, index=True)
    entita_id = db.Column(db.Integer, nullable=False, index=True)
    data_proposta = db.Column(db.String(20), nullable=False)
    ora_proposta = db.Column(db.String(10), nullable=False)
    durata_minuti = db.Column(db.Integer, nullable=False, default=30)
    stato = db.Column(db.String(20), nullable=False, default='Inviata', index=True)
    scade_il = db.Column(db.DateTime, nullable=False, index=True)
    creata_il = db.Column(db.DateTime, default=utc_now, nullable=False)
    accettata_il = db.Column(db.DateTime, nullable=True)


class BloccoAgenda(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    titolo = db.Column(db.String(160), nullable=False)
    data = db.Column(db.String(20), nullable=False, index=True)
    ora = db.Column(db.String(10), nullable=False)
    durata_minuti = db.Column(db.Integer, nullable=False, default=30)
    note = db.Column(db.Text, nullable=True)
    google_event_id = db.Column(db.String(255), nullable=True)
    sincronizzazione = db.Column(db.String(30), default='da_sincronizzare', nullable=False, index=True)
    creato_il = db.Column(db.DateTime, default=utc_now, nullable=False, index=True)
    archiviato_il = db.Column(db.DateTime, nullable=True, index=True)


class RegistroModifica(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    azione = db.Column(db.String(80), nullable=False, index=True)
    entita_tipo = db.Column(db.String(40), nullable=False, index=True)
    entita_id = db.Column(db.Integer, nullable=False, index=True)
    dettagli = db.Column(db.Text, nullable=True)
    admin_id = db.Column(db.Integer, db.ForeignKey('admin.id'), nullable=True)
    creato_il = db.Column(db.DateTime, default=utc_now, nullable=False, index=True)


class CollegamentoPersona(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    persona_id = db.Column(db.Integer, db.ForeignKey('persona_corso.id'), nullable=False, index=True)
    entita_tipo = db.Column(db.String(40), nullable=False, index=True)
    entita_id = db.Column(db.Integer, nullable=False, index=True)
    creato_il = db.Column(db.DateTime, default=utc_now, nullable=False)
    persona = db.relationship('PersonaCorso', backref=db.backref('collegamenti_pratiche', lazy=True))
    __table_args__ = (db.UniqueConstraint('entita_tipo', 'entita_id', name='uq_collegamento_persona_pratica'),)


class ConsensoPrivacyPaziente(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    persona_id = db.Column(db.Integer, db.ForeignKey('persona_corso.id'), nullable=False, index=True)
    entita_tipo = db.Column(db.String(40), nullable=False, index=True)
    entita_id = db.Column(db.Integer, nullable=False, index=True)
    accettato = db.Column(db.Boolean, default=False, nullable=False)
    accettato_il = db.Column(db.DateTime, nullable=True)
    creato_il = db.Column(db.DateTime, default=utc_now, nullable=False)
    persona = db.relationship(
        'PersonaCorso',
        backref=db.backref('consensi_privacy', lazy=True, cascade='all, delete-orphan'),
    )
    __table_args__ = (
        db.UniqueConstraint(
            'entita_tipo',
            'entita_id',
            name='uq_consenso_privacy_pratica',
        ),
    )


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


def registra_modifica(azione, entita_tipo, entita_id, dettagli=None):
    """Conserva una traccia append-only delle operazioni amministrative."""
    admin_id = current_user.id if current_user.is_authenticated else None
    record = RegistroModifica(
        azione=azione,
        entita_tipo=entita_tipo,
        entita_id=entita_id,
        dettagli=json.dumps(dettagli, ensure_ascii=False) if dettagli else None,
        admin_id=admin_id,
    )
    db.session.add(record)
    db.session.commit()
    return record


def prossima_scadenza_lavorativa(adesso=None):
    """Restituisce le 18 del primo giorno lavorativo successivo."""
    riferimento = adesso or local_now()
    candidato = riferimento.date() + timedelta(days=1)
    while candidato.weekday() >= 6 or is_festivo(candidato):
        candidato += timedelta(days=1)
    return datetime.combine(candidato, datetime_time(hour=18))


def _scadenza_da_form(valore, fallback=None):
    if valore:
        try:
            return datetime.fromisoformat(valore)
        except ValueError:
            pass
    return fallback or prossima_scadenza_lavorativa()


def _invia_email_tracciata(msg, entita_tipo=None, entita_id=None):
    """Invia via SMTP e conserva per 24 mesi la copia esatta collegata alla pratica."""
    destinatario = ', '.join(str(destinatario or '') for destinatario in (msg.recipients or []))
    record = EmailOperativa(
        entita_tipo=entita_tipo,
        entita_id=entita_id,
        destinatario=destinatario,
        oggetto=msg.subject or '',
        corpo=msg.body or '',
        stato='in_preparazione',
        scade_il=utc_now() + timedelta(days=730),
    )
    db.session.add(record)
    db.session.commit()
    try:
        mail.send(msg)
        record.stato = 'soppressa' if app.config.get('MAIL_SUPPRESS_SEND') else 'inviata'
        record.inviata_il = utc_now()
        db.session.commit()
        return True
    except Exception as errore:
        record.stato = 'fallita'
        record.errore = str(errore)
        db.session.commit()
        raise


def elimina_email_scadute(adesso=None):
    """Applica la conservazione di 24 mesi senza toccare le pratiche collegate."""
    limite = adesso or utc_now()
    eliminate = EmailOperativa.query.filter(EmailOperativa.scade_il <= limite).delete(
        synchronize_session=False
    )
    if eliminate:
        db.session.commit()
    return eliminate


def genera_promemoria_richieste(adesso=None):
    """Trasforma le scadenze superate in attività visibili, senza sbloccare lo slot."""
    limite = adesso or local_now_naive()
    create = 0
    gruppi = [
        ('Appuntamento', Appuntamento.query.filter(Appuntamento.stato == 'In attesa', Appuntamento.scadenza_gestione <= limite, Appuntamento.archiviato_il.is_(None)).all()),
        ('CallSonno', CallSonno.query.filter(CallSonno.stato == 'In attesa', CallSonno.scadenza_gestione <= limite, CallSonno.archiviata_il.is_(None)).all()),
        ('IscrizioneCorso', IscrizioneCorso.query.filter(IscrizioneCorso.stato.in_(['Nuova', 'Contattato']), IscrizioneCorso.scadenza_gestione <= limite, IscrizioneCorso.archiviata_il.is_(None)).all()),
        ('RichiestaAzienda', RichiestaAzienda.query.filter(RichiestaAzienda.stato.notin_(['Confermata', 'Chiusa']), RichiestaAzienda.scadenza_gestione <= limite, RichiestaAzienda.archiviata_il.is_(None)).all()),
    ]
    for tipo, elementi in gruppi:
        for entita in elementi:
            esistente = AttivitaAdmin.query.filter_by(
                stato='Aperta',
                entita_tipo=tipo,
                entita_id=entita.id,
            ).first()
            if esistente:
                continue
            db.session.add(AttivitaAdmin(
                titolo=f'Richiesta scaduta · {_nome_entita_admin(tipo, entita)}',
                scadenza=limite,
                entita_tipo=tipo,
                entita_id=entita.id,
                note='Promemoria automatico: la pratica resta bloccante finché non viene gestita.',
            ))
            create += 1
    if create:
        db.session.commit()
    return create


def _entita_admin(tipo, entita_id):
    modelli = {
        'Appuntamento': Appuntamento,
        'CallSonno': CallSonno,
        'IscrizioneCorso': IscrizioneCorso,
        'Corso': Corso,
        'IncontroAccompagnamento': IncontroAccompagnamento,
        'BloccoAgenda': BloccoAgenda,
        'RichiestaAzienda': RichiestaAzienda,
    }
    modello = modelli.get(tipo)
    return db.session.get(modello, entita_id) if modello else None


def _nome_entita_admin(tipo, entita):
    if tipo in {'Appuntamento', 'CallSonno', 'IscrizioneCorso'}:
        return entita.nome
    if tipo == 'RichiestaAzienda':
        return f'{entita.organizzazione} · {entita.referente}'
    if tipo in {'Corso', 'BloccoAgenda'}:
        return entita.titolo
    if tipo == 'IncontroAccompagnamento':
        return f'Incontro {entita.numero}: {entita.tema}'
    return tipo


def _riferimento_registro_evento(evento):
    if not evento.entita_tipo or not evento.entita_id:
        return None
    entita = _entita_admin(evento.entita_tipo, evento.entita_id)
    if entita is None:
        return None
    nome = _nome_entita_admin(evento.entita_tipo, entita)
    if evento.entita_tipo == 'IscrizioneCorso' and entita.corso_titolo:
        return f'{nome} · {entita.corso_titolo}'
    return nome


def _modelli_sincronizzabili():
    return [
        ('Appuntamento', Appuntamento, lambda elemento: elemento.stato == 'Confermato' and elemento.archiviato_il is None, _corpo_evento_da_appuntamento),
        ('CallSonno', CallSonno, lambda elemento: elemento.stato in {'In attesa', 'Confermata'} and elemento.archiviata_il is None, _corpo_evento_da_call_sonno),
        ('Corso', Corso, lambda elemento: elemento.stato != 'Annullato' and elemento.archiviato_il is None, _corpo_evento_da_corso),
        ('IncontroAccompagnamento', IncontroAccompagnamento, lambda elemento: elemento.archiviato_il is None, _corpo_evento_da_incontro),
        ('BloccoAgenda', BloccoAgenda, lambda elemento: elemento.archiviato_il is None, _corpo_evento_da_blocco),
    ]


def _sincronizza_entita_calendar(tipo, entita):
    sincronizzatori = {
        'Appuntamento': crea_o_aggiorna_evento_calendario,
        'CallSonno': crea_o_aggiorna_evento_calendario_call_sonno,
        'Corso': crea_o_aggiorna_evento_calendario_corso,
        'IncontroAccompagnamento': crea_o_aggiorna_evento_calendario_incontro,
        'BloccoAgenda': crea_o_aggiorna_evento_calendario_blocco,
    }
    sincronizzatore = sincronizzatori.get(tipo)
    return sincronizzatore(entita) if sincronizzatore else False


def _chiudi_errori_calendar_risolti(tipo, entita_id):
    RegistroEvento.query.filter(
        RegistroEvento.categoria.in_(['google_calendar', 'riconciliazione_calendar']),
        RegistroEvento.esito.in_(['errore', 'avviso']),
        RegistroEvento.entita_tipo == tipo,
        RegistroEvento.entita_id == entita_id,
        RegistroEvento.risolto_il.is_(None),
    ).update({
        'risolto_il': utc_now(),
        'nota_risoluzione': 'Riallineamento automatico completato.',
    }, synchronize_session=False)
    db.session.commit()


def _recupera_evento_calendar_esistente(tipo, entita_id):
    """Ricollega un evento già creato se la risposta dell'insert era andata persa."""
    calendar_id = app.config.get('GOOGLE_CALENDAR_ID')
    servizio = _ottieni_servizio_calendario()
    if not calendar_id or servizio is None:
        raise RuntimeError('Google Calendar non disponibile durante il recupero evento.')
    risposta = _esegui_richiesta_calendario(
        servizio.events().list(
            calendarId=calendar_id,
            privateExtendedProperty=f'studioEntityId={entita_id}',
            showDeleted=False,
            maxResults=10,
        )
    )
    corrispondenze = []
    for evento in risposta.get('items', []):
        proprieta = ((evento.get('extendedProperties') or {}).get('private') or {})
        if (
            proprieta.get('studioEntity') == tipo
            and proprieta.get('studioEntityId') == str(entita_id)
            and evento.get('id')
        ):
            corrispondenze.append(evento['id'])
    if len(corrispondenze) > 1:
        raise RuntimeError('Più eventi Calendar risultano collegati alla stessa pratica.')
    return corrispondenze[0] if corrispondenze else None


def riallinea_calendar_automaticamente():
    """Riprova le sincronizzazioni fallite senza sovrascrivere anomalie esterne."""
    stati_da_riprovare = ('da_sincronizzare', 'errore', 'mancante')
    risultato = {'tentati': 0, 'riusciti': 0, 'falliti': 0, 'dettagli': []}

    for tipo, modello, deve_esistere, _ in _modelli_sincronizzabili():
        candidati = modello.query.filter(
            modello.sincronizzazione.in_(stati_da_riprovare)
        ).all()
        for entita in candidati:
            if not deve_esistere(entita):
                continue
            risultato['tentati'] += 1
            riuscito = False
            try:
                if not entita.google_event_id:
                    evento_esistente_id = _recupera_evento_calendar_esistente(
                        tipo,
                        entita.id,
                    )
                    if evento_esistente_id:
                        entita.google_event_id = evento_esistente_id
                        db.session.commit()
                riuscito = _sincronizza_entita_calendar(tipo, entita)
            except Exception as errore:
                db.session.rollback()
                registra_evento(
                    'google_calendar',
                    'errore',
                    'Errore imprevisto durante il riallineamento automatico Calendar.',
                    tipo,
                    entita.id,
                    {'errore': str(errore)},
                )
            if riuscito:
                risultato['riusciti'] += 1
                _chiudi_errori_calendar_risolti(tipo, entita.id)
            else:
                risultato['falliti'] += 1
            risultato['dettagli'].append({
                'tipo': tipo,
                'id': entita.id,
                'esito': 'riuscito' if riuscito else 'fallito',
            })

    if risultato['tentati']:
        invia_email_esito_riallineamento_calendar(risultato)
    return risultato


def _valore_evento_google(corpo, campo):
    valore = (corpo.get(campo) or {}).get('dateTime') or (corpo.get(campo) or {}).get('date')
    if not valore:
        return None
    if 'T' not in valore:
        return valore
    istante = _datetime_evento_google(valore, (corpo.get(campo) or {}).get('timeZone'))
    return istante.isoformat(timespec='minutes') if istante else None


def _differenze_evento(desiderato, remoto):
    differenze = {}
    confronti = {
        'titolo': (desiderato.get('summary') or '', remoto.get('summary') or ''),
        'inizio': (_valore_evento_google(desiderato, 'start'), _valore_evento_google(remoto, 'start')),
        'fine': (_valore_evento_google(desiderato, 'end'), _valore_evento_google(remoto, 'end')),
    }
    for campo, (locale, calendar) in confronti.items():
        if locale != calendar:
            differenze[campo] = {'sito': locale, 'calendar': calendar}
    return differenze


def _registra_anomalia_sync(tipo, entita_id, messaggio, dettagli=None):
    esistente = RegistroEvento.query.filter_by(
        categoria='riconciliazione_calendar',
        entita_tipo=tipo,
        entita_id=entita_id,
        risolto_il=None,
    ).first()
    if esistente:
        esistente.messaggio = messaggio
        esistente.dettagli = json.dumps(dettagli, ensure_ascii=False) if dettagli else None
        db.session.commit()
        return esistente
    evento = registra_evento(
        'riconciliazione_calendar',
        'errore',
        messaggio,
        tipo,
        entita_id,
        dettagli,
    )
    destinatario = app.config.get('MAIL_ADMIN_RECIPIENT')
    if evento and destinatario:
        msg = Message(
            subject=f'Errore critico Calendar · {tipo} #{entita_id}',
            recipients=[destinatario],
            body=(f'{messaggio}\n\nPratica: {tipo} #{entita_id}\n'
                  'Apri l’area admin, verifica il confronto e scegli se riscrivere Calendar.'),
        )
        try:
            _invia_email_tracciata(msg, tipo, entita_id)
        except Exception as errore:
            logger.error('>>> Notifica email errore critico non inviata (%s).', type(errore).__name__)
    return evento


def _chiudi_anomalie_sync(tipo, entita_id, nota='Riconciliazione successiva senza differenze.'):
    RegistroEvento.query.filter_by(
        categoria='riconciliazione_calendar',
        entita_tipo=tipo,
        entita_id=entita_id,
        risolto_il=None,
    ).update({
        'risolto_il': utc_now(),
        'nota_risoluzione': nota,
    })


def _segna_evento_eliminato_esternamente(tipo, entita):
    differenza = {'evento': {'sito': 'presente', 'calendar': 'eliminato'}}
    entita.sincronizzazione = 'eliminato_esternamente'
    if hasattr(entita, 'difformita_calendario'):
        entita.difformita_calendario = json.dumps(differenza, ensure_ascii=False)
    db.session.commit()
    _registra_anomalia_sync(
        tipo,
        entita.id,
        'Evento collegato eliminato da Google Calendar.',
        differenza,
    )


def riconcilia_calendario():
    """Confronta DB e Calendar senza applicare modifiche esterne al DB."""
    calendar_id = app.config.get('GOOGLE_CALENDAR_ID')
    servizio = _ottieni_servizio_calendario()
    risultato = {'controllati': 0, 'difformi': 0, 'mancanti': 0, 'errore': None}
    if not calendar_id or servizio is None:
        risultato['errore'] = 'Google Calendar non disponibile.'
        return risultato

    for tipo, modello, deve_esistere, corpo_builder in _modelli_sincronizzabili():
        for entita in modello.query.all():
            if not deve_esistere(entita):
                continue
            if not entita.google_event_id:
                entita.sincronizzazione = 'mancante'
                if hasattr(entita, 'difformita_calendario'):
                    entita.difformita_calendario = json.dumps({'evento': {'sito': 'richiesto', 'calendar': 'mancante'}}, ensure_ascii=False)
                db.session.commit()
                _registra_anomalia_sync(tipo, entita.id, 'Pratica attiva senza evento collegato su Google Calendar.')
                risultato['mancanti'] += 1
                continue
            risultato['controllati'] += 1
            try:
                remoto = _esegui_richiesta_calendario(
                    servizio.events().get(
                        calendarId=calendar_id,
                        eventId=entita.google_event_id,
                    ),
                    ignora_assenza_evento=True,
                )
            except HttpError as errore:
                status = getattr(getattr(errore, 'resp', None), 'status', None) or getattr(errore, 'status_code', None)
                if status in (404, 410):
                    _segna_evento_eliminato_esternamente(tipo, entita)
                    risultato['mancanti'] += 1
                    continue
                risultato['errore'] = f'Errore Calendar: {type(errore).__name__}'
                registra_evento('google_calendar', 'errore', 'Riconciliazione Calendar interrotta da un errore API.', tipo, entita.id, {'errore': str(errore)})
                return risultato
            except Exception as errore:
                risultato['errore'] = f'Errore Calendar: {type(errore).__name__}'
                registra_evento('google_calendar', 'errore', 'Riconciliazione Calendar interrotta.', tipo, entita.id, {'errore': str(errore)})
                return risultato

            if not isinstance(remoto, dict):
                risultato['errore'] = 'Errore Calendar: risposta non valida'
                registra_evento(
                    'google_calendar',
                    'errore',
                    'Riconciliazione Calendar interrotta da una risposta non valida.',
                    tipo,
                    entita.id,
                )
                return risultato
            if remoto.get('status') == 'cancelled':
                _segna_evento_eliminato_esternamente(tipo, entita)
                risultato['mancanti'] += 1
                continue

            differenze = _differenze_evento(corpo_builder(entita), remoto)
            if differenze:
                entita.sincronizzazione = 'difforme'
                if hasattr(entita, 'difformita_calendario'):
                    entita.difformita_calendario = json.dumps(differenze, ensure_ascii=False)
                db.session.commit()
                _registra_anomalia_sync(tipo, entita.id, 'Evento Calendar modificato esternamente: serve conferma.', differenze)
                risultato['difformi'] += 1
            else:
                entita.sincronizzazione = 'sincronizzato'
                if hasattr(entita, 'difformita_calendario'):
                    entita.difformita_calendario = None
                _chiudi_anomalie_sync(tipo, entita.id)
                db.session.commit()
    return risultato


def _riconciliazione_admin_se_necessaria(adesso_monotonic=None):
    """Esegue al massimo un controllo rapido per finestra di freschezza."""
    global _ultima_riconciliazione_admin
    if not _integrazione_calendar_abilitata():
        return None
    if not (
        app.config.get('GOOGLE_CALENDAR_ID')
        and app.config.get('GOOGLE_SERVICE_ACCOUNT_FILE')
    ):
        return None

    adesso = time.monotonic() if adesso_monotonic is None else adesso_monotonic
    freschezza = max(
        0,
        app.config.get('CALENDARIO_RICONCILIAZIONE_ADMIN_SECONDI', 180),
    )
    with _lock_riconciliazione_admin:
        if (
            _ultima_riconciliazione_admin
            and adesso < _ultima_riconciliazione_admin + freschezza
        ):
            return None
        try:
            return riconcilia_calendario()
        finally:
            _ultima_riconciliazione_admin = adesso


def _segna_riconciliazione_admin_fresca():
    global _ultima_riconciliazione_admin
    with _lock_riconciliazione_admin:
        _ultima_riconciliazione_admin = time.monotonic()


def _dettagli_anomalia_calendar(tipo, entita):
    if getattr(entita, 'difformita_calendario', None):
        try:
            return json.loads(entita.difformita_calendario)
        except json.JSONDecodeError:
            pass
    anomalia = RegistroEvento.query.filter_by(
        categoria='riconciliazione_calendar',
        entita_tipo=tipo,
        entita_id=entita.id,
        risolto_il=None,
    ).order_by(RegistroEvento.creato_il.desc()).first()
    return anomalia.dettagli_dict() if anomalia else {}


def _valore_conflitto_leggibile(valore):
    if not valore:
        return '—'
    if valore == 'eliminato':
        return 'EVENTO ELIMINATO'
    if isinstance(valore, str) and 'T' in valore:
        try:
            istante = datetime.fromisoformat(valore.replace('Z', '+00:00'))
            if istante.tzinfo:
                istante = istante.astimezone(FUSO_ORARIO)
            return istante.strftime('%d/%m/%Y %H:%M')
        except ValueError:
            pass
    return str(valore)


def _conflitti_calendar_prioritari():
    conflitti = []
    for tipo, modello, _, _ in _modelli_sincronizzabili():
        entita_conflitto = modello.query.filter(
            modello.sincronizzazione.in_(('difforme', 'eliminato_esternamente'))
        ).all()
        for entita in entita_conflitto:
            dettagli = _dettagli_anomalia_calendar(tipo, entita)
            righe = [
                {
                    'campo': campo,
                    'sito': _valore_conflitto_leggibile(valori.get('sito')),
                    'calendar': _valore_conflitto_leggibile(valori.get('calendar')),
                }
                for campo, valori in dettagli.items()
                if isinstance(valori, dict)
            ]
            campi = set(dettagli)
            conflitti.append({
                'tipo': tipo,
                'id': entita.id,
                'nome': _nome_entita_admin(tipo, entita),
                'prestazione': (
                    getattr(entita, 'servizio', None)
                    or ('Call gratuita sul sonno' if tipo == 'CallSonno' else tipo)
                ),
                'data': getattr(entita, 'data', ''),
                'stato': entita.sincronizzazione,
                'righe': righe,
                'puo_accettare_calendar': (
                    tipo in {'Appuntamento', 'CallSonno'}
                    and entita.sincronizzazione == 'difforme'
                    and bool(campi.intersection({'inizio', 'fine'}))
                ),
                'puo_annullare': (
                    tipo in {'Appuntamento', 'CallSonno'}
                    and entita.sincronizzazione == 'eliminato_esternamente'
                ),
            })
    return sorted(conflitti, key=lambda voce: (voce['data'], voce['tipo'], voce['id']))


def _eventi_calendar_esterni(data_inizio, data_fine):
    """Mostra titolo e orario degli eventi non creati dal sito, senza importarli."""
    calendar_id = app.config.get('GOOGLE_CALENDAR_ID')
    servizio = _ottieni_servizio_calendario()
    if not calendar_id or servizio is None:
        return []
    collegati = {
        entita.google_event_id
        for _, modello, _, _ in _modelli_sincronizzabili()
        for entita in modello.query.filter(modello.google_event_id.isnot(None)).all()
    }
    inizio = datetime.combine(data_inizio, datetime.min.time(), tzinfo=FUSO_ORARIO)
    fine = datetime.combine(data_fine + timedelta(days=1), datetime.min.time(), tzinfo=FUSO_ORARIO)
    try:
        risposta = _esegui_richiesta_calendario(
            servizio.events().list(
                calendarId=calendar_id,
                timeMin=inizio.isoformat(),
                timeMax=fine.isoformat(),
                singleEvents=True,
                showDeleted=False,
                orderBy='startTime',
                maxResults=2500,
            )
        )
    except Exception:
        logger.warning('>>> Agenda esterna non disponibile.', exc_info=True)
        return []
    eventi = []
    for evento in risposta.get('items', []):
        if evento.get('id') in collegati or evento.get('status') == 'cancelled':
            continue
        intervallo = _intervallo_da_evento_google(evento)
        if not intervallo:
            continue
        eventi.append({
            'tipo': 'Esterno',
            'id': evento.get('id'),
            'titolo': evento.get('summary') or 'Impegno esterno',
            'inizio': intervallo[0],
            'fine': intervallo[1],
            'stato': 'Calendar / Arzamed',
            'sincronizzazione': 'esterno',
            'url': None,
        })
    return eventi


def _agenda_operativa(data_inizio, data_fine):
    limite_inizio = data_inizio.isoformat()
    limite_fine = data_fine.isoformat()
    eventi = []

    def aggiungi(
        tipo,
        entita,
        titolo,
        data_str,
        ora,
        durata,
        stato,
        sync,
        endpoint=None,
        dettagli=None,
        note=None,
        anchor=None,
    ):
        if not ora:
            ora = '09:00'
        inizio, fine = _intervallo_locale(data_str, ora, durata)
        eventi.append({
            'tipo': tipo,
            'id': entita.id,
            'titolo': titolo,
            'inizio': inizio,
            'fine': fine,
            'stato': stato,
            'sincronizzazione': sync,
            'url': (
                url_for(endpoint, tipo=tipo, entita_id=entita.id, _anchor=anchor)
                if endpoint
                else None
            ),
            'dettagli': [
                (etichetta, valore)
                for etichetta, valore in (dettagli or [])
                if valore not in (None, '')
            ],
            'note': note,
        })

    for elemento in Appuntamento.query.filter(Appuntamento.data.between(limite_inizio, limite_fine), Appuntamento.stato != 'Annullato', Appuntamento.archiviato_il.is_(None)).all():
        aggiungi(
            'Appuntamento', elemento, f'{elemento.nome} · {elemento.servizio}',
            elemento.data, elemento.ora, elemento.duration_minutes or 30,
            elemento.stato, elemento.sincronizzazione, 'dettaglio_admin',
            dettagli=[
                ('Prestazione', elemento.servizio),
                ('Persona', elemento.nome),
                ('Telefono', elemento.telefono),
                ('Email', elemento.email),
            ],
            note=elemento.note,
        )
    for elemento in CallSonno.query.filter(CallSonno.data.between(limite_inizio, limite_fine), CallSonno.stato != 'Annullata', CallSonno.archiviata_il.is_(None)).all():
        aggiungi(
            'CallSonno', elemento, f'{elemento.nome} · call sonno',
            elemento.data, elemento.ora, BLOCCO_CALL_SONNO_MINUTI,
            elemento.stato, elemento.sincronizzazione, 'dettaglio_admin',
            dettagli=[
                ('Prestazione', 'Call sonno'),
                ('Persona', elemento.nome),
                ('Età bambino', f'{elemento.eta_bambino_mesi} mesi'),
                ('Difficoltà', elemento.difficolta_principale),
                ('Da quanto', elemento.durata_difficolta),
                ('Obiettivo', elemento.obiettivo_call),
                ('Formula', elemento.formula_scelta),
                ('Ruolo', elemento.ruolo_richiedente),
                ('Telefono', elemento.telefono),
                ('Email', elemento.email),
            ],
            note=elemento.difficolta_altro,
        )
    for elemento in Corso.query.filter(Corso.data.between(limite_inizio, limite_fine), Corso.stato != 'Annullato', Corso.archiviato_il.is_(None)).all():
        aggiungi(
            'Corso', elemento, elemento.titolo, elemento.data, elemento.ora,
            int((elemento.durata_ore or 2) * 60), elemento.stato,
            elemento.sincronizzazione, 'dettaglio_admin',
            dettagli=[
                ('Tipologia', CORSI_ADMIN_TIPI.get(elemento.tipo, {}).get('label', elemento.tipo)),
                ('Luogo', elemento.luogo),
                ('Capienza', f'{elemento.capienza_massima} persone' if elemento.capienza_massima else None),
            ],
            note=elemento.descrizione,
            anchor='partecipanti-corso',
        )
    for elemento in IncontroAccompagnamento.query.filter(IncontroAccompagnamento.data.between(limite_inizio, limite_fine), IncontroAccompagnamento.archiviato_il.is_(None)).all():
        aggiungi(
            'IncontroAccompagnamento', elemento,
            f'{elemento.percorso.titolo} · {elemento.tema}', elemento.data,
            elemento.ora, 120, 'Programmato', elemento.sincronizzazione,
            'dettaglio_admin',
            dettagli=[
                ('Percorso', elemento.percorso.titolo),
                ('Tema', elemento.tema),
                ('Professionista', elemento.professionista),
                ('Luogo', elemento.luogo),
            ],
            note=elemento.note,
        )
    for elemento in BloccoAgenda.query.filter(BloccoAgenda.data.between(limite_inizio, limite_fine), BloccoAgenda.archiviato_il.is_(None)).all():
        aggiungi(
            'BloccoAgenda', elemento, elemento.titolo, elemento.data,
            elemento.ora, elemento.durata_minuti, 'Blocco',
            elemento.sincronizzazione, 'dettaglio_admin',
            note=elemento.note,
        )
    eventi.extend(_eventi_calendar_esterni(data_inizio, data_fine))
    return sorted(eventi, key=lambda elemento: elemento['inizio'])


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
    return giorno.weekday() < 6 and not is_festivo(giorno)


def prima_data_call_disponibile(da_giorno=None):
    candidato = (da_giorno or local_today()) + timedelta(days=1)
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
        Appuntamento.archiviato_il.is_(None),
    )
    if ignore_appuntamento_id is not None:
        appuntamenti_query = appuntamenti_query.filter(Appuntamento.id != ignore_appuntamento_id)
    for appuntamento in appuntamenti_query.all():
        if _intervalli_si_sovrappongono(
            intervallo_richiesto,
            _intervallo_locale(
                appuntamento.data,
                appuntamento.ora,
                appuntamento.duration_minutes or DURATA_SLOT_MINUTI,
            ),
        ):
            return True

    call_query = CallSonno.query.filter(
        CallSonno.data == data_str,
        CallSonno.stato != 'Annullata',
        CallSonno.archiviata_il.is_(None),
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

    blocchi = BloccoAgenda.query.filter(
        BloccoAgenda.data == data_str,
        BloccoAgenda.archiviato_il.is_(None),
    ).all()
    for blocco in blocchi:
        if _intervalli_si_sovrappongono(
            intervallo_richiesto,
            _intervallo_locale(blocco.data, blocco.ora, blocco.durata_minuti),
        ):
            return True
    return False


# ─── INIZIALIZZAZIONE DATABASE ───
# Questo blocco viene eseguito sia con flask run che con python3 app.py

def crea_amministratore_iniziale(username, password):
    """Crea il primo amministratore senza incorporare credenziali nel codice."""
    username = (username or '').strip()
    password = password or ''

    if Admin.query.first():
        raise ValueError('Esiste già un amministratore.')
    if not 3 <= len(username) <= 100:
        raise ValueError('Il nome utente deve contenere da 3 a 100 caratteri.')
    if len(password) < 16:
        raise ValueError('La password deve contenere almeno 16 caratteri.')

    admin_utente = Admin(
        username=username,
        password=generate_password_hash(password),
    )
    db.session.add(admin_utente)
    db.session.commit()
    logger.info('>>> Amministratore iniziale creato in modo sicuro.')
    return admin_utente


def valida_configurazione_staging():
    """Blocca uno staging privo della protezione HTTP obbligatoria."""
    if app.config.get('APP_ENV') == 'staging':
        staging_username = app.config.get('STAGING_AUTH_USERNAME')
        staging_password = app.config.get('STAGING_AUTH_PASSWORD')
        if not staging_username or not staging_password:
            raise RuntimeError(
                'Lo staging richiede STAGING_AUTH_USERNAME e STAGING_AUTH_PASSWORD.'
            )
        if len(staging_password) < 16:
            raise RuntimeError('La password dello staging deve contenere almeno 16 caratteri.')


def public_url(path=None):
    """Costruisce un URL assoluto senza ereditare per forza l'host richiesto."""
    base_url = (app.config.get('PUBLIC_BASE_URL') or request.url_root).rstrip('/')
    if path is None:
        path = request.path
    if not path.startswith('/'):
        path = f'/{path}'
    return f'{base_url}{path}'


def _campi_integrazioni_mancanti():
    campi_obbligatori = {
        'MAIL_SERVER': app.config.get('MAIL_SERVER'),
        'MAIL_USERNAME': app.config.get('MAIL_USERNAME'),
        'MAIL_PASSWORD': app.config.get('MAIL_PASSWORD'),
        'MAIL_DEFAULT_SENDER': app.config.get('MAIL_DEFAULT_SENDER'),
        'MAIL_ADMIN_RECIPIENT': app.config.get('MAIL_ADMIN_RECIPIENT'),
        'GOOGLE_SERVICE_ACCOUNT_FILE': app.config.get('GOOGLE_SERVICE_ACCOUNT_FILE'),
        'GOOGLE_CALENDAR_ID': app.config.get('GOOGLE_CALENDAR_ID'),
    }
    return [nome for nome, valore in campi_obbligatori.items() if not valore]


def _valida_integrazioni_reali():
    mancanti = _campi_integrazioni_mancanti()
    if mancanti:
        raise RuntimeError(f'Configurazione integrazioni incompleta: {", ".join(mancanti)}.')
    if app.config.get('MAIL_SERVER') != 'smtp.mail.ovh.net':
        raise RuntimeError('MAIL_SERVER deve essere smtp.mail.ovh.net.')
    if app.config.get('MAIL_PORT') != 587:
        raise RuntimeError('MAIL_PORT deve essere 587.')
    if not app.config.get('MAIL_USE_TLS') or app.config.get('MAIL_USE_SSL'):
        raise RuntimeError('SMTP Zimbra richiede MAIL_USE_TLS=true e MAIL_USE_SSL=false.')
    if app.config.get('MAIL_USERNAME') != 'info@scstudioinfermieristico.it':
        raise RuntimeError('MAIL_USERNAME deve usare la casella Zimbra approvata.')
    mittente = app.config.get('MAIL_DEFAULT_SENDER')
    indirizzo_mittente = (
        mittente[1]
        if isinstance(mittente, (tuple, list)) and len(mittente) == 2
        else str(mittente)
    )
    if 'info@scstudioinfermieristico.it' not in indirizzo_mittente:
        raise RuntimeError('MAIL_DEFAULT_SENDER deve usare la casella Zimbra approvata.')
    if not os.path.isfile(app.config['GOOGLE_SERVICE_ACCOUNT_FILE']):
        raise RuntimeError('File segreto Google Calendar non disponibile.')


def valida_configurazione_runtime():
    """Rifiuta configurazioni insicure prima di staging o produzione."""
    ambiente = app.config.get('APP_ENV')
    if ambiente not in {'staging', 'production'}:
        return

    valida_configurazione_staging()
    if config_name != 'production':
        raise RuntimeError('Staging e produzione richiedono FLASK_ENV=production.')
    if app.config.get('SECRET_KEY_IS_EPHEMERAL') or len(app.config.get('SECRET_KEY', '')) < 32:
        raise RuntimeError('Configurare una SECRET_KEY stabile di almeno 32 caratteri.')
    database_url = app.config.get('SQLALCHEMY_DATABASE_URI', '')
    if not app.config.get('DATABASE_URL_IS_EXPLICIT') or not database_url.startswith('postgresql+psycopg://'):
        raise RuntimeError('Staging e produzione richiedono DATABASE_URL PostgreSQL esplicita.')
    if app.config.get('MAIL_USE_TLS') and app.config.get('MAIL_USE_SSL'):
        raise RuntimeError('MAIL_USE_TLS e MAIL_USE_SSL non possono essere entrambe attive.')

    valori_segreti = [
        app.config.get('SECRET_KEY'),
        app.config.get('ADMIN_BOOTSTRAP_PASSWORD'),
        app.config.get('STAGING_AUTH_PASSWORD'),
    ]
    valori_presenti = [valore for valore in valori_segreti if valore]
    if len(valori_presenti) != len(set(valori_presenti)):
        raise RuntimeError('Usare segreti distinti per sessione, amministratore e staging.')

    if ambiente == 'staging':
        integrazioni_reali = app.config.get('STAGING_LIVE_INTEGRATIONS')
        if not integrazioni_reali and not app.config.get('MAIL_SUPPRESS_SEND'):
            raise RuntimeError(
                'Lo staging gratuito richiede MAIL_SUPPRESS_SEND=true; '
                'per la preproduzione pagata impostare STAGING_LIVE_INTEGRATIONS=true.'
            )
        if integrazioni_reali:
            if app.config.get('MAIL_SUPPRESS_SEND'):
                raise RuntimeError(
                    'La preproduzione con integrazioni reali richiede MAIL_SUPPRESS_SEND=false.'
                )
            _valida_integrazioni_reali()
        return

    if app.config.get('MAIL_SUPPRESS_SEND'):
        raise RuntimeError('La produzione richiede MAIL_SUPPRESS_SEND=false.')
    _valida_integrazioni_reali()
    public_base_url = app.config.get('PUBLIC_BASE_URL')
    if not public_base_url:
        raise RuntimeError('La produzione richiede PUBLIC_BASE_URL esplicita.')
    parsed_public_url = urlsplit(public_base_url)
    if (
        parsed_public_url.scheme != 'https'
        or not parsed_public_url.netloc
        or parsed_public_url.path not in {'', '/'}
        or parsed_public_url.query
        or parsed_public_url.fragment
    ):
        raise RuntimeError('PUBLIC_BASE_URL deve essere un’origine HTTPS senza percorso.')


def inizializza_amministratore():
    """Verifica o crea il primo admin dopo l'applicazione delle migrazioni."""
    admin_esistente = Admin.query.first()
    ambiente_produzione = app.config.get('ENV') == 'production' or config_name == 'production'
    if admin_esistente:
        credenziale_legacy = (
            admin_esistente.username == 'admin'
            and check_password_hash(admin_esistente.password, 'cambiami123')
        )
        if credenziale_legacy and ambiente_produzione:
            raise RuntimeError(
                'Credenziale amministratore legacy rilevata: cambiarla prima della produzione.'
            )
        if credenziale_legacy:
            logger.warning(
                '>>> Credenziale amministratore legacy rilevata. Sostituirla prima del deploy.'
            )
        logger.info('>>> Database OK — Admin esistente')
        return

    username = app.config.get('ADMIN_BOOTSTRAP_USERNAME')
    password = app.config.get('ADMIN_BOOTSTRAP_PASSWORD')
    if bool(username) != bool(password):
        raise RuntimeError(
            'Configurare insieme ADMIN_BOOTSTRAP_USERNAME e ADMIN_BOOTSTRAP_PASSWORD.'
        )
    if username and password:
        crea_amministratore_iniziale(username, password)
        return
    if ambiente_produzione:
        raise RuntimeError(
            'Database senza amministratore: configurare le credenziali di bootstrap sicure.'
        )

    logger.warning(
        '>>> Database senza amministratore. Eseguire `flask --app app create-admin` '
        'oppure configurare credenziali di bootstrap esplicite.'
    )


def inizializza_database():
    """Helper per test e database locali nuovi; la produzione usa Alembic."""
    db.create_all()
    valida_configurazione_runtime()
    inizializza_amministratore()


@app.cli.command('create-admin')
@click.option('--username', prompt='Nome utente amministratore')
@click.password_option(
    '--password',
    prompt='Password amministratore',
    confirmation_prompt=True,
)
def create_admin_command(username, password):
    """Crea in modo interattivo il primo amministratore locale."""
    try:
        crea_amministratore_iniziale(username, password)
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc
    click.echo('Amministratore creato.')


@app.cli.command('bootstrap-admin')
def bootstrap_admin_command():
    """Verifica o crea il primo amministratore da segreti d'ambiente."""
    try:
        valida_configurazione_runtime()
        inizializza_amministratore()
    except (RuntimeError, ValueError) as exc:
        raise click.ClickException(str(exc)) from exc
    click.echo('Bootstrap amministratore verificato.')


@app.cli.command('validate-config')
def validate_config_command():
    """Verifica la configurazione senza mostrare i valori sensibili."""
    try:
        valida_configurazione_runtime()
    except RuntimeError as exc:
        raise click.ClickException(str(exc)) from exc
    click.echo(f'Configurazione {app.config.get("APP_ENV")} valida.')


valida_configurazione_runtime()


@app.before_request
def proteggi_staging():
    """Limita l'accesso allo staging e impedisce l'indicizzazione accidentale."""
    if app.config.get('APP_ENV') != 'staging':
        return None
    if request.path == '/healthz':
        return None
    if request.path == '/robots.txt':
        return Response(
            'User-agent: *\nDisallow: /\n',
            mimetype='text/plain',
            headers={'X-Robots-Tag': 'noindex, nofollow, noarchive'},
        )

    auth = request.authorization
    username = app.config['STAGING_AUTH_USERNAME']
    password = app.config['STAGING_AUTH_PASSWORD']
    credenziali_valide = (
        auth is not None
        and secrets.compare_digest(auth.username or '', username)
        and secrets.compare_digest(auth.password or '', password)
    )
    if credenziali_valide:
        return None
    return Response(
        'Staging riservato.',
        401,
        {'WWW-Authenticate': 'Basic realm="Staging S.C. Studio Infermieristico"'},
    )


@app.after_request
def impedisci_indicizzazione_staging(response):
    if app.config.get('APP_ENV') == 'staging':
        response.headers['X-Robots-Tag'] = 'noindex, nofollow, noarchive'
    return response


@app.route('/healthz')
@limiter.exempt
def healthz():
    try:
        db.session.execute(sql_text('SELECT 1'))
    except Exception:
        logger.exception('>>> Health check database fallito.')
        return jsonify({'status': 'unhealthy'}), 503
    return jsonify({'status': 'ok'})


@app.errorhandler(404)
def not_found(_errore):
    return render_template(
        'errore.html',
        titolo='Pagina non trovata',
        messaggio=(
            'Il collegamento potrebbe essere cambiato oppure la pagina non è disponibile.'
        ),
    ), 404


@app.errorhandler(429)
def troppe_richieste(errore):
    limite = getattr(errore, 'description', 'limite configurato')
    logger.warning(
        '>>> Limite richieste superato: endpoint=%s metodo=%s limite=%s',
        request.endpoint or 'sconosciuto',
        request.method,
        limite,
    )
    messaggio = (
        'Hai effettuato troppe richieste in poco tempo. '
        'Attendi e riprova più tardi.'
    )
    if request.endpoint == 'api_orari_call_sonno':
        return jsonify({'errore': messaggio}), 429
    return render_template(
        'errore.html',
        titolo='Troppe richieste',
        messaggio=messaggio,
    ), 429


@app.errorhandler(500)
def server_error(_errore):
    db.session.rollback()
    return render_template(
        'errore.html',
        titolo='Non è stato possibile completare la richiesta',
        messaggio=(
            'Riprova tra poco. Se il problema continua, contatta direttamente lo studio.'
        ),
    ), 500


# ─── EMAIL ───

def invia_email_ricezione_call_sonno(call):
    try:
        msg = Message(
            subject='Richiesta call sonno ricevuta: attendi la conferma',
            recipients=[call.email],
            body=(
                f'Gentile {call.nome},\n\n'
                f'ho ricevuto la tua richiesta per la call gratuita sul sonno.\n\n'
                f'Data richiesta: {call.data}\n'
                f'Orario richiesto: {call.ora}\n'
                f'Durata indicativa: circa {DURATA_CALL_SONNO_MINUTI} minuti\n\n'
                f'Lo slot è riservato provvisoriamente. Considera fissato l’appuntamento solo dopo la mia email di conferma. '
                f'Ti confermerò l’orario oppure ti contatterò per concordarne uno diverso '
                f'entro il giorno lavorativo successivo.\n\n'
                f'S.C. Studio Infermieristico'
            ),
        )
        _invia_email_tracciata(msg, 'CallSonno', call.id)
        return True
    except Exception as errore:
        registra_evento('email', 'errore', 'Email ricezione call sonno non inviata.', 'CallSonno', call.id, {'errore': str(errore)})
        return False


def invia_email_alert_call_sonno(call):
    try:
        msg = Message(
            subject=f'Nuova call sonno da confermare - {call.nome}',
            recipients=[app.config['MAIL_ADMIN_RECIPIENT']],
            body=(
                f'Nuova richiesta di call sonno.\n\n'
                f'Nome: {call.nome}\nTelefono: {call.telefono}\nEmail: {call.email}\n'
                f'Ruolo: {call.ruolo_richiedente}\n'
                f'Età bambino: {call.eta_bambino_mesi} mesi\n'
                f'Difficoltà: {call.difficolta_altro or call.difficolta_principale}\n'
                f'Durata: {call.durata_difficolta}\n'
                f'Obiettivo della call: {call.obiettivo_call}\n'
                f'Quando: {call.data} alle {call.ora}\n\n'
                f'Lo slot è stato bloccato provvisoriamente. Gestiscilo dall’area admin.'
            ),
        )
        _invia_email_tracciata(msg, 'CallSonno', call.id)
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
                f'Se hai bisogno di contattarmi, chiama il 3806317175.\n\n'
                f'S.C. Studio Infermieristico'
            ),
        )
        calendario = icalendar.Calendar()
        calendario.add('prodid', '-//S.C. Studio Infermieristico//Call sonno//IT')
        calendario.add('version', '2.0')
        evento = icalendar.Event()
        inizio, _ = _intervallo_locale(call.data, call.ora, DURATA_CALL_SONNO_MINUTI)
        evento.add('summary', 'Appuntamento con S.C. Studio Infermieristico')
        evento.add('dtstart', inizio)
        evento.add('dtend', inizio + timedelta(minutes=DURATA_CALL_SONNO_MINUTI))
        evento.add('description', istruzioni.strip())
        calendario.add_component(evento)
        msg.attach(
            'appuntamento-sc-studio.ics',
            'text/calendar',
            calendario.to_ical(),
            disposition='attachment',
        )
        _invia_email_tracciata(msg, 'CallSonno', call.id)
        return True
    except Exception as errore:
        registra_evento('email', 'errore', 'Email conferma call sonno non inviata.', 'CallSonno', call.id, {'errore': str(errore)})
        return False


def invia_email_annullamento_call_sonno(call):
    try:
        msg = Message(
            subject='Call sonno annullata - S.C. Studio Infermieristico',
            recipients=[call.email],
            body=(
                f'Gentile {call.nome},\n\nla call richiesta per il {call.data} alle {call.ora} '
                f'è stata annullata. Per fissare un nuovo momento puoi contattarmi al 3806317175.\n\n'
                f'S.C. Studio Infermieristico'
            ),
        )
        _invia_email_tracciata(msg, 'CallSonno', call.id)
        return True
    except Exception as errore:
        registra_evento('email', 'errore', 'Email annullamento call sonno non inviata.', 'CallSonno', call.id, {'errore': str(errore)})
        return False


def invia_email_questionario_sonno(call):
    try:
        link = public_url(url_for('questionario_sonno', token=call.token_questionario))
        formula = FORMULE_SONNO.get(call.formula_scelta, 'percorso scelto')
        msg = Message(
            subject='Il questionario per iniziare il percorso sul sonno',
            recipients=[call.email],
            body=(
                f'Gentile {call.nome},\n\ncome concordato dopo la call, puoi compilare il questionario '
                f'riservato per {formula}. Le risposte mi permetteranno di preparare il lavoro sulla vostra situazione reale.\n\n'
                f'Compila il questionario: {link}\n\n'
                f'Il collegamento è personale: non inoltrarlo. Se hai dubbi, scrivimi su WhatsApp.\n\n'
                f'S.C. Studio Infermieristico'
            ),
        )
        _invia_email_tracciata(msg, 'CallSonno', call.id)
        return True
    except Exception as errore:
        registra_evento('email', 'errore', 'Email questionario sonno non inviata.', 'CallSonno', call.id, {'errore': str(errore)})
        return False


def invia_email_promemoria_call_sonno(call, ore_prima):
    """Invia un promemoria neutro per una call sonno già confermata."""
    try:
        call_url = app.config.get('SONNO_CALL_URL')
        collegamento = (
            f'Collegamento: {call_url}\n\n'
            if call_url
            else 'Trovi le modalità di collegamento nell’email di conferma.\n\n'
        )
        msg = Message(
            subject='Promemoria appuntamento - S.C. Studio Infermieristico',
            recipients=[call.email],
            body=(
                f'Gentile {call.nome},\n\n'
                f'ti ricordiamo l’appuntamento del {call.data} alle {call.ora}.\n'
                f'Durata indicativa: circa {DURATA_CALL_SONNO_MINUTI} minuti.\n\n'
                f'{collegamento}'
                f'Se non puoi partecipare, avvisaci appena possibile.\n\n'
                f'S.C. Studio Infermieristico'
            ),
        )
        _invia_email_tracciata(msg, 'CallSonno', call.id)
        return True
    except Exception as errore:
        registra_evento(
            'email',
            'errore',
            f'Email promemoria call sonno {ore_prima}h non inviata.',
            'CallSonno',
            call.id,
            {'errore': str(errore)},
        )
        return False


def invia_email_conferma(appuntamento):
    """Invia email di conferma al paziente dopo la conferma dell'appuntamento."""
    try:
        logger.info('>>> Invio email conferma appuntamento %s...', appuntamento.id)
        msg = Message(
            subject='Appuntamento confermato - S.C. Studio Infermieristico',
            recipients=[appuntamento.email],
            body=(
                f'Gentile {appuntamento.nome},\n\n'
                f'il tuo appuntamento è stato confermato.\n\n'
                f'Servizio: {appuntamento.servizio}\n'
                f'Data:     {appuntamento.data}\n'
                f'Ora:      {appuntamento.ora}\n'
                f'Durata:   {appuntamento.duration_minutes} minuti\n\n'
                f'Per qualsiasi necessità puoi contattarmi al numero 3806317175.\n\n'
                f'A presto,\n'
                f'S.C. Studio Infermieristico\n'
                f"Via C. D'Agnese 43\n"
                f'65015 Montesilvano (PE)'
            )
        )
        _invia_email_tracciata(msg, 'Appuntamento', appuntamento.id)
        logger.info('>>> Email conferma inviata con successo!')
        return True
    except Exception as e:
        logger.error('>>> Errore invio email conferma (%s).', type(e).__name__)
        registra_evento('email', 'errore', 'Email di conferma appuntamento non inviata.', 'Appuntamento', appuntamento.id, {'errore': str(e)})
        return False


def invia_email_spostamento(appuntamento):
    """Invia email di notifica quando un appuntamento viene riprogrammato."""
    try:
        logger.info('>>> Invio email spostamento appuntamento %s...', appuntamento.id)
        msg = Message(
            subject='Appuntamento spostato - S.C. Studio Infermieristico',
            recipients=[appuntamento.email],
            body=(
                f'Gentile {appuntamento.nome},\n\n'
                f'il tuo appuntamento è stato spostato. Qui trovi i nuovi dettagli:\n\n'
                f'Servizio:     {appuntamento.servizio}\n'
                f'Nuova data:   {appuntamento.data}\n'
                f'Nuovo orario: {appuntamento.ora}\n'
                f'Durata:       {appuntamento.duration_minutes} minuti\n\n'
                f'Se hai domande o devi chiedere un’altra modifica, '
                f'puoi contattarmi al 3806317175.\n\n'
                f'A presto,\n'
                f'S.C. Studio Infermieristico'
            )
        )
        _invia_email_tracciata(msg, 'Appuntamento', appuntamento.id)
        logger.info('>>> Email spostamento inviata con successo!')
        return True
    except Exception as e:
        logger.error('>>> Errore invio email spostamento (%s).', type(e).__name__)
        registra_evento('email', 'errore', 'Email di spostamento appuntamento non inviata.', 'Appuntamento', appuntamento.id, {'errore': str(e)})
        return False


def invia_email_annullamento(appuntamento):
    """Invia email di cancellazione al paziente."""
    try:
        logger.info('>>> Invio email annullamento appuntamento %s...', appuntamento.id)
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
                f'A presto,\n'
                f'S.C. Studio Infermieristico'
            )
        )
        _invia_email_tracciata(msg, 'Appuntamento', appuntamento.id)
        logger.info('>>> Email annullamento inviata con successo!')
        return True
    except Exception as e:
        logger.error('>>> Errore invio email annullamento (%s).', type(e).__name__)
        registra_evento('email', 'errore', 'Email di annullamento appuntamento non inviata.', 'Appuntamento', appuntamento.id, {'errore': str(e)})
        return False


def invia_email_nuova_prenotazione(appuntamento):
    """Invia email di alert all'amministratore quando viene ricevuta una nuova richiesta di appuntamento."""
    try:
        logger.info('>>> Invio email alert nuova prenotazione...')
        link_admin = public_url(url_for('admin'))
        msg = Message(
            subject=f'Nuova prenotazione - {appuntamento.nome}',
            recipients=[app.config['MAIL_ADMIN_RECIPIENT']],
            body=(
                f'Hai ricevuto una nuova richiesta di appuntamento.\n\n'
                f'Nome:     {appuntamento.nome}\n'
                f'Telefono: {appuntamento.telefono}\n'
                f'Email:    {appuntamento.email}\n'
                f'Servizio: {appuntamento.servizio}\n'
                f'Data:     {appuntamento.data}\n'
                f'Ora:      {appuntamento.ora}\n'
                f'Note:     {appuntamento.note or "Nessuna"}\n\n'
                f'Gestisci la prenotazione nell\'area admin:\n{link_admin}'
            )
        )
        _invia_email_tracciata(msg, 'Appuntamento', appuntamento.id)
        logger.info('>>> Email alert inviata con successo!')
        return True
    except Exception as e:
        logger.error('>>> Errore invio email alert (%s).', type(e).__name__)
        registra_evento('email', 'errore', 'Email alert nuova prenotazione non inviata allo studio.', 'Appuntamento', appuntamento.id, {'errore': str(e)})
        return False


def invia_email_esito_riallineamento_calendar(risultato):
    """Invia un solo riepilogo amministrativo per ogni ciclo di retry Calendar."""
    destinatario = app.config.get('MAIL_ADMIN_RECIPIENT')
    if not destinatario:
        registra_evento(
            'email',
            'avviso',
            'Esito riallineamento Calendar non notificato: destinatario admin mancante.',
        )
        return False

    falliti = risultato['falliti']
    if falliti == 0:
        stato = 'riuscito'
    elif risultato['riusciti']:
        stato = 'parziale'
    else:
        stato = 'fallito'
    righe = '\n'.join(
        f"- {dettaglio['tipo']} #{dettaglio['id']}: {dettaglio['esito']}"
        for dettaglio in risultato['dettagli']
    )
    base_url = (app.config.get('PUBLIC_BASE_URL') or '').rstrip('/')
    link_admin = f'{base_url}/admin#admin-errori' if base_url else '/admin#admin-errori'
    msg = Message(
        subject=(
            f"Riallineamento Calendar {stato} · "
            f"{risultato['riusciti']}/{risultato['tentati']} riusciti"
        ),
        recipients=[destinatario],
        body=(
            'Il tentativo automatico di riallineamento con Google Calendar '
            f'è {stato}.\n\n'
            f"Tentati: {risultato['tentati']}\n"
            f"Riusciti: {risultato['riusciti']}\n"
            f"Falliti: {falliti}\n\n"
            f'{righe}\n\n'
            f'Controlla gli esiti nell’area admin:\n{link_admin}'
        ),
    )
    try:
        _invia_email_tracciata(msg, 'RiallineamentoCalendar', None)
        return True
    except Exception as errore:
        registra_evento(
            'email',
            'errore',
            'Email esito riallineamento Calendar non inviata.',
            dettagli={'errore': str(errore)},
        )
        return False


def invia_email_alert_nuova_iscrizione(iscrizione):
    """Invia email di alert all'amministratore quando arriva una richiesta di iscrizione corso."""
    try:
        logger.info('>>> Invio email alert nuova iscrizione corso...')
        extra = iscrizione.extra_dict()
        is_course_interest = iscrizione.tipo_richiesta == 'ricontatto'
        dettagli_extra = ''
        if extra.get('ente_azienda'):
            dettagli_extra += f'Azienda/gruppo: {extra["ente_azienda"]}\n'
        if extra.get('numero_partecipanti'):
            dettagli_extra += f'Partecipanti: {extra["numero_partecipanti"]}\n'
        msg = Message(
            subject=(
                f'Nuovo interesse corso - {iscrizione.corso_titolo}'
                if is_course_interest
                else f'Nuova iscrizione corso - {iscrizione.corso_titolo}'
            ),
            recipients=[app.config['MAIL_ADMIN_RECIPIENT']],
            body=(
                f'Hai ricevuto una nuova richiesta di {"ricontatto" if is_course_interest else "iscrizione corso"}.\n\n'
                f'Corso:    {iscrizione.corso_titolo}\n'
                f'Nome:     {iscrizione.nome}\n'
                f'Telefono: {iscrizione.telefono}\n'
                f'Email:    {iscrizione.email or "Non indicata"}\n'
                f'Data:     {iscrizione.data_corso or "Da definire"}\n'
                f'Tipo:     {iscrizione.partecipazione or "Non indicato"}\n'
                f'Note:     {iscrizione.note or "Nessuna"}\n\n'
                f'{dettagli_extra}'
                f'Accedi all\'area admin per gestire la richiesta.'
            )
        )
        _invia_email_tracciata(msg, 'IscrizioneCorso', iscrizione.id)
        logger.info('>>> Email alert iscrizione corso inviata con successo!')
        return True
    except Exception as e:
        logger.error('>>> Errore invio email alert corso (%s).', type(e).__name__)
        registra_evento('email', 'errore', 'Email alert iscrizione corso non inviata allo studio.', 'IscrizioneCorso', iscrizione.id, {'errore': str(e)})
        return False


def _invia_email_partecipante_corso(iscrizione, subject, body, failure_message):
    """Invia una comunicazione successiva alla richiesta senza modificare il dato principale."""
    if iscrizione.stato in STATI_LISTA_ATTESA:
        return None
    if not iscrizione.email:
        return None
    msg = Message(subject=subject, recipients=[iscrizione.email], body=body)
    try:
        _invia_email_tracciata(msg, 'IscrizioneCorso', iscrizione.id)
        return True
    except Exception as errore:
        registra_evento(
            'email',
            'errore',
            failure_message,
            'IscrizioneCorso',
            iscrizione.id,
            {'errore': str(errore)},
        )
        return False


def _firma_email_studio():
    """Restituisce i recapiti pubblici approvati per le comunicazioni ai partecipanti."""
    return (
        'S.C. Studio Infermieristico\n'
        'Telefono: 380 631 7175\n'
        'Email: info@scstudioinfermieristico.it'
    )


def invia_email_conferma_iscrizione_corso(iscrizione):
    """Comunica la conferma soltanto dopo il passaggio admin a Confermato."""
    if iscrizione.percorso_accompagnamento:
        return invia_email_iscrizione_accompagnamento(
            iscrizione,
            iscrizione.percorso_accompagnamento,
        )
    data_confermata = (
        _etichetta_data_corso(iscrizione.corso)
        if iscrizione.corso
        else re.sub(
            r'\s*·\s*lista d’attesa\s*$',
            '',
            iscrizione.data_corso or 'Da definire',
            flags=re.IGNORECASE,
        )
    )
    return _invia_email_partecipante_corso(
        iscrizione,
        f'Posto confermato - {iscrizione.corso_titolo}',
        (
            f'Buongiorno {iscrizione.nome},\n\n'
            f'il tuo posto per {iscrizione.corso_titolo} è confermato.\n\n'
            f'Data e luogo: {data_confermata}\n'
            f'Partecipazione: {iscrizione.partecipazione or "Non indicata"}\n\n'
            'Se hai bisogno di comunicare una variazione, contatta lo studio.\n\n'
            f'{_firma_email_studio()}'
        ),
        'Email di conferma iscrizione corso non inviata al partecipante.',
    )


def invia_email_annullamento_iscrizione_corso(iscrizione, stato_precedente):
    """Comunica l'annullamento distinguendo una richiesta da un posto già confermato."""
    descrizione = 'iscrizione' if stato_precedente == 'Confermato' else 'richiesta di iscrizione'
    return _invia_email_partecipante_corso(
        iscrizione,
        f'{descrizione.capitalize()} annullata - {iscrizione.corso_titolo}',
        (
            f'Buongiorno {iscrizione.nome},\n\n'
            f'la tua {descrizione} per {iscrizione.corso_titolo} è stata annullata.\n\n'
            f'Edizione: {iscrizione.data_corso or "Da definire"}\n\n'
            'Per chiarimenti o per valutare una data diversa, contatta lo studio.\n\n'
            f'{_firma_email_studio()}'
        ),
        'Email di annullamento iscrizione corso non inviata al partecipante.',
    )


def invia_email_spostamento_iscrizione_corso(iscrizione, edizione_precedente):
    """Comunica la nuova edizione senza trasformare una richiesta in conferma."""
    stato_posto = (
        'Il posto resta confermato.'
        if iscrizione.stato == 'Confermato'
        else 'Il posto non è ancora confermato: riceverai una mail separata dopo la verifica dello studio.'
    )
    return _invia_email_partecipante_corso(
        iscrizione,
        f'Nuova edizione - {iscrizione.corso_titolo}',
        (
            f'Buongiorno {iscrizione.nome},\n\n'
            f'la tua richiesta per {iscrizione.corso_titolo} è stata spostata.\n\n'
            f'Edizione precedente: {edizione_precedente or "Da definire"}\n'
            f'Nuova edizione: {iscrizione.data_corso or "Da definire"}\n\n'
            f'{stato_posto}\n\n'
            f'{_firma_email_studio()}'
        ),
        'Email di spostamento iscrizione corso non inviata al partecipante.',
    )


def invia_email_annullamento_edizione_corso(iscrizione, corso, etichetta_edizione):
    """Avvisa un partecipante confermato che l'intera edizione è stata annullata."""
    return _invia_email_partecipante_corso(
        iscrizione,
        f'Edizione annullata - {corso.titolo}',
        (
            f'Buongiorno {iscrizione.nome},\n\n'
            f'ti informo che l’edizione di {corso.titolo} è stata annullata.\n\n'
            f'Data e luogo previsti: {etichetta_edizione}\n\n'
            'Per conoscere le prossime date disponibili o chiedere chiarimenti, '
            'puoi contattare lo studio ai seguenti recapiti:\n\n'
            f'{_firma_email_studio()}'
        ),
        'Email di annullamento corso non inviata al partecipante.',
    )


def invia_email_richiesta_azienda(richiesta):
    """Conferma la ricezione e avvisa lo studio senza bloccare il salvataggio."""
    corso_label = CORSI_ADMIN_TIPI.get(richiesta.corso_tipo, {}).get('label', 'Formazione da definire')
    riuscite = 0
    messaggi = [
        Message(
            subject='Richiesta corso ricevuta',
            recipients=[richiesta.email],
            body=(
                f'Buongiorno {richiesta.referente},\n\n'
                f'ho ricevuto la richiesta per {richiesta.organizzazione}. '
                'Verificherò obiettivo, sede, numero di partecipanti e periodo prima di formulare una proposta.\n\n'
                'L’invio non conferma ancora data, disponibilità o preventivo. '
                'Ti ricontatterò entro il prossimo giorno lavorativo.\n\n'
                'S.C. Studio Infermieristico'
            ),
        ),
    ]
    if app.config.get('MAIL_ADMIN_RECIPIENT'):
        messaggi.append(Message(
            subject=f'Nuova richiesta azienda · {richiesta.organizzazione}',
            recipients=[app.config['MAIL_ADMIN_RECIPIENT']],
            body=(
                'Nuova richiesta dedicata ad azienda o gruppo.\n\n'
                f'Organizzazione: {richiesta.organizzazione}\n'
                f'Referente: {richiesta.referente}\n'
                f'Telefono: {richiesta.telefono}\n'
                f'Email: {richiesta.email}\n'
                f'Corso: {corso_label}\n'
                f'Partecipanti stimati: {richiesta.partecipanti_stimati or "Da definire"}\n'
                f'Sede: {richiesta.sede_preferita}\n'
                f'Periodo: {richiesta.periodo_preferito or "Da definire"}\n\n'
                'Apri la richiesta nell’area admin per registrare la prossima azione.'
            ),
        ))
    for messaggio in messaggi:
        try:
            _invia_email_tracciata(messaggio, 'RichiestaAzienda', richiesta.id)
            riuscite += 1
        except Exception as errore:
            registra_evento(
                'email',
                'errore',
                'Email relativa alla richiesta azienda non inviata.',
                'RichiestaAzienda',
                richiesta.id,
                {'errore': str(errore)},
            )
    return riuscite == len(messaggi)


def invia_email_iscrizione_accompagnamento(iscrizione, percorso):
    """Invia conferma alla famiglia per il modulo privato del percorso nascita."""
    if not iscrizione.email:
        return
    try:
        logger.info('>>> Invio email conferma iscrizione corso %s...', iscrizione.id)
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
        _invia_email_tracciata(msg, 'IscrizioneCorso', iscrizione.id)
        logger.info('>>> Email conferma percorso accompagnamento inviata con successo!')
        return True
    except Exception as e:
        logger.error('>>> Errore invio email conferma percorso (%s).', type(e).__name__)
        registra_evento('email', 'errore', 'Email conferma percorso accompagnamento non inviata.', 'IscrizioneCorso', iscrizione.id, {'errore': str(e)})
        return False


def invia_email_alert_iscrizione_accompagnamento(iscrizione, percorso):
    """Invia allo studio la notifica della nuova richiesta al percorso nascita."""
    try:
        logger.info('>>> Invio email alert iscrizione percorso accompagnamento...')
        msg = Message(
            subject=f'Nuova richiesta di iscrizione - {percorso.titolo}',
            recipients=[app.config['MAIL_ADMIN_RECIPIENT']],
            body=(
                f'Nuova richiesta di iscrizione al corso di accompagnamento alla nascita.\n'
                f'Il posto non è ancora confermato.\n\n'
                f'Percorso: {percorso.titolo}\n'
                f'Nome:     {iscrizione.nome}\n'
                f'Telefono: {iscrizione.telefono}\n'
                f'Email:    {iscrizione.email or "Non indicata"}\n\n'
                f'Accedi all\'area admin per vedere i dettagli.'
            )
        )
        _invia_email_tracciata(msg, 'IscrizioneCorso', iscrizione.id)
        logger.info('>>> Email alert percorso accompagnamento inviata con successo!')
        return True
    except Exception as e:
        logger.error('>>> Errore invio email alert percorso (%s).', type(e).__name__)
        registra_evento('email', 'errore', 'Email alert percorso accompagnamento non inviata allo studio.', 'IscrizioneCorso', iscrizione.id, {'errore': str(e)})
        return False


def invia_email_ricordo_24h(appuntamento):
    """Invia email di promemoria 24 ore prima dell'appuntamento."""
    try:
        logger.info('>>> Invio email ricordo appuntamento %s...', appuntamento.id)
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
        _invia_email_tracciata(msg, 'Appuntamento', appuntamento.id)
        logger.info('>>> Email ricordo 24h inviata con successo!')
        return True
    except Exception as e:
        logger.error('>>> Errore invio email ricordo 24h (%s).', type(e).__name__)
        registra_evento('email', 'errore', 'Email promemoria 24h non inviata.', 'Appuntamento', appuntamento.id, {'errore': str(e)})
        return False


def controlla_e_invia_ricordi_24h():
    """Controlla gli appuntamenti che avvengono nelle prossime 24 ore e invia promemoria."""
    try:
        logger.info('>>> Controllo appuntamenti per invio ricordi 24h...')

        # Calcola la finestra temporale: ora + 24 ore +/- 30 minuti
        adesso = local_now()
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
                app_datetime, _ = _intervallo_locale(
                    app.data,
                    app.ora,
                    app.duration_minutes,
                )
                if window_start <= app_datetime <= window_end:
                    invia_email_ricordo_24h(app)
                    ricordi_inviati += 1
            except (TypeError, ValueError):
                # Salta gli appuntamenti con formato data/ora non valido
                continue

        logger.info(f'> Inviati {ricordi_inviati} ricordi 24h')
    except Exception as e:
        logger.error('> Errore controllo ricordi 24h (%s).', type(e).__name__)


def controlla_e_invia_promemoria_call_sonno(adesso=None):
    """Invia una sola volta i promemoria 24h e 2h delle call confermate."""
    adesso = adesso or local_now()
    oggi = adesso.date().isoformat()
    limite = (adesso.date() + timedelta(days=1)).isoformat()
    calls = CallSonno.query.filter(
        CallSonno.stato == 'Confermata',
        CallSonno.data >= oggi,
        CallSonno.data <= limite,
    ).all()

    for call in calls:
        try:
            inizio, _ = _intervallo_locale(
                call.data, call.ora, DURATA_CALL_SONNO_MINUTI
            )
        except (TypeError, ValueError):
            continue
        secondi_mancanti = (inizio - adesso).total_seconds()
        if secondi_mancanti <= 0:
            continue

        ore_promemoria = None
        if secondi_mancanti <= 2 * 3600 and call.promemoria_email_2h_il is None:
            ore_promemoria = 2
        elif (
            secondi_mancanti <= 24 * 3600
            and secondi_mancanti > 2 * 3600
            and call.promemoria_email_24h_il is None
        ):
            ore_promemoria = 24

        if ore_promemoria is None:
            continue

        invia_email_promemoria_call_sonno(call, ore_promemoria)
        timestamp = utc_now()
        if ore_promemoria == 24:
            call.promemoria_email_24h_il = timestamp
        else:
            call.promemoria_email_2h_il = timestamp

        db.session.commit()


def esegui_ricordi_24h_con_contesto():
    with app.app_context():
        controlla_e_invia_ricordi_24h()


def esegui_promemoria_call_sonno_con_contesto():
    with app.app_context():
        controlla_e_invia_promemoria_call_sonno()


def esegui_riconciliazione_con_contesto():
    with app.app_context():
        riallineamento = riallinea_calendar_automaticamente()
        riconciliazione = riconcilia_calendario()
        _segna_riconciliazione_admin_fresca()
        return {
            'riallineamento': riallineamento,
            'riconciliazione': riconciliazione,
        }


def esegui_manutenzione_admin_con_contesto():
    with app.app_context():
        elimina_email_scadute()


def esegui_promemoria_richieste_con_contesto():
    with app.app_context():
        genera_promemoria_richieste()

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
if (
    not app.config.get('TESTING')
    and os.environ.get('DISABLE_SCHEDULER', '').lower() not in {'1', 'true', 'yes'}
    and (not app.debug or os.environ.get('WERKZEUG_RUN_MAIN') == 'true')
):
    scheduler.add_job(
        func=esegui_ricordi_24h_con_contesto,
        trigger="interval",
        hours=1,
        id='ricordi_24h_job',
        name='Controllo e invio ricordi 24h',
        replace_existing=True
    )
    scheduler.add_job(
        func=esegui_promemoria_call_sonno_con_contesto,
        trigger="interval",
        minutes=15,
        id='promemoria_call_sonno_job',
        name='Controllo promemoria call sonno 24h e 2h',
        replace_existing=True,
    )
    scheduler.add_job(
        func=esegui_promemoria_richieste_con_contesto,
        trigger='interval',
        hours=1,
        id='promemoria_richieste_job',
        name='Promemoria richieste operative scadute',
        replace_existing=True,
    )
    scheduler.add_job(
        func=esegui_riconciliazione_con_contesto,
        trigger='interval',
        hours=1,
        id='riconciliazione_calendar_job',
        name='Riallineamento e riconciliazione oraria Google Calendar',
        replace_existing=True,
    )
    scheduler.add_job(
        func=esegui_manutenzione_admin_con_contesto,
        trigger='interval',
        days=1,
        id='manutenzione_admin_job',
        name='Pulizia email operative oltre 24 mesi',
        replace_existing=True,
    )
    scheduler.start()

@app.route('/da-dove-parto')
def da_dove_parto():
    """Orientamento non clinico verso i flussi pubblici già approvati."""
    return render_template('da_dove_parto.html')



# ─── PAGINE SITO ───

@app.route('/')
def homepage():
    oggi = local_today().isoformat()
    corsi = Corso.query.filter(
        Corso.data >= oggi,
        Corso.stato == 'Aperto',
    ).order_by(Corso.data, Corso.ora).all()
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
        prestazioni_categorie=PRESTAZIONI_CATEGORIE,
        prestazioni_totale=len(SERVIZI_PRENOTABILI),
        studio_map_embed_src=STUDIO_MAP_EMBED_SRC,
        studio_map_link=STUDIO_MAP_LINK,
    )


@app.route('/corso-accompagnamento-nascita')
def prima_della_nascita():
    return render_template('prima_della_nascita.html')


@app.route('/prima-della-nascita')
def prima_della_nascita_legacy():
    return redirect(url_for('prima_della_nascita'), code=301)


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


def _posti_attivi_corso(corso_id):
    iscrizioni = IscrizioneCorso.query.filter(
        IscrizioneCorso.corso_id == corso_id,
        IscrizioneCorso.stato.notin_(['Annullato', 'Lista attesa', 'Invitato']),
        IscrizioneCorso.archiviata_il.is_(None),
    ).all()
    return sum(
        iscrizione.posti
        if iscrizione.posti is not None
        else _posti_iscrizione_da_partecipazione(iscrizione.partecipazione)
        for iscrizione in iscrizioni
    )


def _posti_liberi_corso(corso):
    if corso.capienza_massima is None:
        return None
    return max(corso.capienza_massima - _posti_attivi_corso(corso.id), 0)


def _corso_accetta_prenotazione_online(corso, posti_richiesti=1):
    """Applica il limite online: si prenota solo se prima restano posti.

    Una coppia può occupare l'ultimo posto nominale e portare l'edizione a
    capienza + 1. Quando la capienza nominale è già raggiunta, il sito chiude.
    """
    if corso.capienza_massima is None:
        return True
    occupati = _posti_attivi_corso(corso.id)
    return occupati < corso.capienza_massima and occupati + posti_richiesti <= corso.capienza_massima + 1


def _corso_ha_posti(corso):
    return _corso_accetta_prenotazione_online(corso, 1)


def _label_tipo_richiesta(tipo_richiesta):
    return TIPI_RICHIESTA_CORSO.get(tipo_richiesta, tipo_richiesta or 'Richiesta')


def _persona_corso_da_contatti(telefono='', email='', codice_fiscale=''):
    codice_normalizzato = re.sub(r'\s+', '', codice_fiscale or '').upper()
    if codice_normalizzato:
        persona = PersonaCorso.query.filter(
            db.func.upper(PersonaCorso.codice_fiscale) == codice_normalizzato
        ).first()
        if persona:
            return persona
    return None


def _possibili_duplicati_persona(persona):
    """Segnala corrispondenze deboli senza unire automaticamente le pratiche."""
    duplicati = []
    email = (persona.email or '').strip().lower()
    telefono = _normalizza_telefono(persona.telefono)
    for candidata in PersonaCorso.query.filter(PersonaCorso.id != persona.id).all():
        stessa_email = email and (candidata.email or '').strip().lower() == email
        stesso_telefono = telefono and _normalizza_telefono(candidata.telefono) == telefono
        if stessa_email or stesso_telefono:
            duplicati.append(candidata)
    return duplicati


def _storico_persona_admin(persona):
    """Restituisce le pratiche collegate senza modificare i recapiti storici."""
    storico = [
        {
            'tipo': 'IscrizioneCorso',
            'id': iscrizione.id,
            'titolo': iscrizione.corso_titolo,
            'data': iscrizione.data_corso or '',
            'creato_il': iscrizione.creato_il,
        }
        for iscrizione in persona.iscrizioni
    ]
    for collegamento in persona.collegamenti_pratiche:
        pratica = _entita_admin(collegamento.entita_tipo, collegamento.entita_id)
        if pratica:
            titolo = (
                getattr(pratica, 'servizio', None)
                or ('Call sonno' if collegamento.entita_tipo == 'CallSonno' else None)
                or _nome_entita_admin(collegamento.entita_tipo, pratica)
            )
            storico.append({
                'tipo': collegamento.entita_tipo,
                'id': pratica.id,
                'titolo': titolo,
                'data': getattr(pratica, 'data', '') or '',
                'creato_il': getattr(pratica, 'creato_il', collegamento.creato_il),
            })
    return sorted(
        storico,
        key=lambda voce: voce['creato_il'] or datetime.min,
        reverse=True,
    )


def _sync_patient_privacy_consent(persona, entita_tipo, entita):
    """Copy the practice consent evidence into the patient's consent history."""
    db.session.flush()
    consent = ConsensoPrivacyPaziente.query.filter_by(
        entita_tipo=entita_tipo,
        entita_id=entita.id,
    ).first()
    if consent is None:
        consent = ConsensoPrivacyPaziente(
            persona=persona,
            entita_tipo=entita_tipo,
            entita_id=entita.id,
        )
        db.session.add(consent)
    else:
        consent.persona = persona
    consent.accettato = bool(getattr(entita, 'consenso_privacy', False))
    consent.accettato_il = (
        getattr(entita, 'creato_il', None) if consent.accettato else None
    )
    return consent


def _patient_privacy_history(persona):
    history = []
    consents = ConsensoPrivacyPaziente.query.filter_by(
        persona_id=persona.id,
    ).order_by(
        ConsensoPrivacyPaziente.accettato_il.desc(),
        ConsensoPrivacyPaziente.creato_il.desc(),
    ).all()
    for consent in consents:
        practice = _entita_admin(consent.entita_tipo, consent.entita_id)
        if consent.entita_tipo == 'Appuntamento' and practice:
            title = practice.servizio
            practice_date = f'{practice.data} · ore {practice.ora}'
        elif consent.entita_tipo == 'IscrizioneCorso' and practice:
            title = practice.corso_titolo
            practice_date = practice.data_corso or 'Data non indicata'
        elif consent.entita_tipo == 'CallSonno' and practice:
            title = 'Call sonno'
            practice_date = f'{practice.data} · ore {practice.ora}'
        else:
            title = f'{consent.entita_tipo} #{consent.entita_id}'
            practice_date = 'Pratica non più disponibile'
        history.append({
            'consent': consent,
            'title': title,
            'practice_date': practice_date,
            'practice_available': practice is not None,
        })
    return history


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
    persona = _persona_corso_da_contatti(
        telefono=telefono,
        email=email,
        codice_fiscale=codice_fiscale,
    )
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


def _ensure_patient_for_appointment(appointment):
    """Create and link a patient only when an appointment is confirmed."""
    existing_link = CollegamentoPersona.query.filter_by(
        entita_tipo='Appuntamento',
        entita_id=appointment.id,
    ).first()
    if existing_link:
        _sync_patient_privacy_consent(
            existing_link.persona,
            'Appuntamento',
            appointment,
        )
        return existing_link.persona, False

    patient = PersonaCorso(
        nome=appointment.nome,
        telefono=appointment.telefono or None,
        email=appointment.email or None,
    )
    db.session.add(patient)
    db.session.flush()
    db.session.add(CollegamentoPersona(
        persona=patient,
        entita_tipo='Appuntamento',
        entita_id=appointment.id,
    ))
    _sync_patient_privacy_consent(patient, 'Appuntamento', appointment)
    return patient, True


def _ensure_patient_for_course_registration(registration):
    """Create or link the primary registrant when they enter the patient list."""
    if registration.persona:
        _sync_patient_privacy_consent(
            registration.persona,
            'IscrizioneCorso',
            registration,
        )
        return registration.persona, False

    extra = registration.extra_dict()
    existing_patient = _persona_corso_da_contatti(
        codice_fiscale=registration.codice_fiscale,
    )
    patient = _trova_o_crea_persona_corso(
        nome=registration.nome,
        telefono=registration.telefono,
        email=registration.email or '',
        codice_fiscale=registration.codice_fiscale,
        nome_bambino=extra.get('nome_bambino', ''),
        eta_bambino=extra.get('eta_bambino', ''),
    )
    registration.persona = patient
    _sync_patient_privacy_consent(patient, 'IscrizioneCorso', registration)
    return patient, existing_patient is None


def _audit_automatic_course_patient_link(registration, patient, patient_created,
                                         creation_action):
    registra_modifica(
        'collegamento_paziente_automatico',
        'IscrizioneCorso',
        registration.id,
        {'persona_id': patient.id, 'nuova_anagrafica': patient_created},
    )
    if patient_created:
        registra_modifica(
            creation_action,
            'PersonaCorso',
            patient.id,
            {'tipo_pratica': 'IscrizioneCorso', 'pratica_id': registration.id},
        )


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
    return sorted(
        [incontro for incontro in percorso.incontri if incontro.archiviato_il is None],
        key=lambda incontro: (incontro.numero or 0, incontro.data or '', incontro.ora or ''),
    )


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


def _etichetta_data_e_ora_corso(corso):
    parti = [_formatta_data_corso(corso.data)]
    if corso.ora:
        parti.append(f'ore {corso.ora}')
    return ' - '.join(parti)


def _opzioni_date_corso(corso_tipo):
    oggi = local_today().strftime('%Y-%m-%d')
    corsi = Corso.query.filter(
        Corso.tipo == corso_tipo,
        Corso.data >= oggi,
        Corso.stato == 'Aperto'
    ).order_by(Corso.data, Corso.ora).all()
    opzioni = []
    for corso in corsi:
        posti_disponibili = _corso_ha_posti(corso)
        data_label = _etichetta_data_e_ora_corso(corso)
        etichetta_completa = _etichetta_data_corso(corso)
        opzioni.append({
            'value': str(corso.id),
            'corso_id': corso.id,
            'label': (
                etichetta_completa
                if posti_disponibili
                else f'{etichetta_completa} · lista d’attesa'
            ),
            'date_label': (
                data_label
                if posti_disponibili
                else f'{data_label} · lista d’attesa'
            ),
            'location': corso.luogo or 'Sede da definire',
            'posti_disponibili': posti_disponibili,
        })
    return opzioni


def _corso_iscrivibile_con_date(corso_tipo):
    corso = dict(CORSI_ISCRIVIBILI[corso_tipo])
    corso['data_options'] = _opzioni_date_corso(corso_tipo)
    corso['has_open_dates'] = len(corso['data_options']) > 0
    corso['interest_topic'] = COURSE_INTEREST_TOPIC_BY_TYPE[corso_tipo]
    return corso


def _luogo_corso_per_modulo(corso, form_data):
    valore_selezionato = str(form_data.get('data_corso', '') or '')
    for option in corso['data_options']:
        if option['value'] == valore_selezionato:
            return option['location']
    return ''


def _slug_pubblico_corso(corso_tipo):
    return CORSI_SLUG_PUBBLICI.get(corso_tipo, corso_tipo)


def _render_iscrizione_con_errore(corso_tipo, messaggio, campo=None):
    flash(messaggio, 'error')
    corso = _corso_iscrivibile_con_date(corso_tipo)
    return render_template(
        'iscrizione_corso.html',
        corso_tipo=corso_tipo,
        corso_slug=_slug_pubblico_corso(corso_tipo),
        corso=corso,
        form_data=request.form,
        form_error_field=campo,
        selected_course_location=_luogo_corso_per_modulo(corso, request.form),
    )


def _render_richiesta_azienda_error(messaggio):
    flash(messaggio, 'error')
    return render_template(
        'richiesta_azienda.html',
        tipi_organizzazione=TIPI_ORGANIZZAZIONE,
        corsi_azienda=FORMAZIONE_AZIENDA_TIPI,
        sedi_azienda=SEDI_AZIENDA,
        form_data=request.form,
    )


@app.route('/aziende-e-gruppi', methods=['GET', 'POST'])
@limiter.limit('5 per minute', methods=['POST'])
def richiesta_azienda():
    """Raccoglie richieste organizzative senza usare il modulo individuale."""
    if request.method == 'POST':
        token = session.pop('_csrf_token', None)
        if not token or token != request.form.get('_csrf_token'):
            return _render_richiesta_azienda_error('Richiesta non valida. Riprova.')

        organizzazione = request.form.get('organizzazione', '').strip()
        referente = request.form.get('referente', '').strip()
        telefono = request.form.get('telefono', '').strip()
        email = request.form.get('email', '').strip()
        tipo_organizzazione = request.form.get('tipo_organizzazione', '').strip()
        corso_tipo = request.form.get('corso_tipo', '').strip()
        sede_preferita = request.form.get('sede_preferita', '').strip()
        periodo_preferito = request.form.get('periodo_preferito', '').strip()
        note = request.form.get('note', '').strip()
        partecipanti_raw = request.form.get('partecipanti_stimati', '').strip()
        partecipanti = int(partecipanti_raw) if partecipanti_raw.isdigit() else None

        if not organizzazione or len(organizzazione) > 160:
            return _render_richiesta_azienda_error('Inserisci il nome dell’azienda o del gruppo.')
        if not referente or len(referente) > 100:
            return _render_richiesta_azienda_error('Inserisci il nome del referente.')
        if not _telefono_valido(telefono):
            return _render_richiesta_azienda_error('Inserisci un numero di telefono valido.')
        if not _email_valida(email):
            return _render_richiesta_azienda_error('Inserisci un indirizzo email valido.')
        if tipo_organizzazione not in TIPI_ORGANIZZAZIONE:
            return _render_richiesta_azienda_error('Seleziona il tipo di organizzazione.')
        if corso_tipo not in FORMAZIONE_AZIENDA_TIPI:
            return _render_richiesta_azienda_error('Seleziona il corso o il progetto da valutare.')
        if sede_preferita not in SEDI_AZIENDA:
            return _render_richiesta_azienda_error('Seleziona una preferenza per la sede.')
        if partecipanti_raw and (partecipanti is None or not 2 <= partecipanti <= 500):
            return _render_richiesta_azienda_error('Indica un numero stimato di partecipanti tra 2 e 500.')
        if len(periodo_preferito) > 160 or len(note) > 2000:
            return _render_richiesta_azienda_error('Riduci la lunghezza del periodo o delle note.')
        if not _checkbox_checked('consenso_privacy'):
            return _render_richiesta_azienda_error('Devi autorizzare il trattamento dei dati personali.')

        scadenza = prossima_scadenza_lavorativa()
        nuova = RichiestaAzienda(
            organizzazione=organizzazione,
            referente=referente,
            telefono=telefono,
            email=email,
            tipo_organizzazione=tipo_organizzazione,
            corso_tipo=corso_tipo,
            partecipanti_stimati=partecipanti,
            sede_preferita=sede_preferita,
            periodo_preferito=periodo_preferito,
            note=note,
            consenso_privacy=True,
            scadenza_gestione=scadenza,
        )
        db.session.add(nuova)
        db.session.flush()
        db.session.add(AttivitaAdmin(
            titolo=f'Qualificare richiesta · {organizzazione}',
            scadenza=scadenza,
            entita_tipo='RichiestaAzienda',
            entita_id=nuova.id,
            note='Verificare obiettivo, partecipanti, sede e periodo prima della proposta.',
        ))
        db.session.commit()
        invia_email_richiesta_azienda(nuova)
        return redirect(url_for('richiesta_azienda_conferma'))

    return render_template(
        'richiesta_azienda.html',
        tipi_organizzazione=TIPI_ORGANIZZAZIONE,
        corsi_azienda=FORMAZIONE_AZIENDA_TIPI,
        sedi_azienda=SEDI_AZIENDA,
        form_data={},
    )


@app.route('/aziende-e-gruppi/conferma')
def richiesta_azienda_conferma():
    return render_template('conferma_richiesta_azienda.html')


def _render_course_interest_error(message):
    flash(message, 'error')
    return render_template(
        'interesse_corsi.html',
        topics=COURSE_INTEREST_TOPICS,
        form_data=request.form,
    )


@app.route('/iscrizione-corsi/interesse', methods=['GET', 'POST'])
@limiter.limit('5 per minute', methods=['POST'])
def course_interest():
    if request.method == 'POST':
        token = session.pop('_csrf_token', None)
        if not token or token != request.form.get('_csrf_token'):
            return _render_course_interest_error('Richiesta non valida. Riprova.')

        name = request.form.get('nome', '').strip()
        phone = request.form.get('telefono', '').strip()
        email = request.form.get('email', '').strip()
        topic_key = request.form.get('tematica', '').strip()
        notes = request.form.get('note', '').strip()
        privacy_consent = _checkbox_checked('consenso_privacy')
        topic = COURSE_INTEREST_TOPICS.get(topic_key)

        if not name or len(name) > 100:
            return _render_course_interest_error('Inserisci nome e cognome.')
        if not phone or not _telefono_valido(phone):
            return _render_course_interest_error('Inserisci un numero di telefono valido.')
        if email and not _email_valida(email):
            return _render_course_interest_error('Inserisci un indirizzo email valido.')
        if not topic:
            return _render_course_interest_error('Seleziona il corso o la tematica che ti interessa.')
        if len(notes) > 2000:
            return _render_course_interest_error('Le note sono troppo lunghe.')
        if not privacy_consent:
            return _render_course_interest_error('Devi autorizzare il trattamento dei dati personali.')

        interest = IscrizioneCorso(
            corso_id=None,
            corso_tipo=topic['course_type'],
            corso_titolo=topic['label'],
            nome=name,
            telefono=phone,
            email=email,
            codice_fiscale='',
            data_corso='Da ricontattare per prossime date',
            partecipazione=None,
            note=notes,
            dati_extra=json.dumps({
                'richiesta_prossime_date': True,
                'tematica_interesse': topic_key,
            }, ensure_ascii=False),
            tipo_richiesta='ricontatto',
            posti=0,
            consenso_privacy=privacy_consent,
            consenso_immagini=False,
            scadenza_gestione=prossima_scadenza_lavorativa(),
            posti_richiesti=0,
        )
        db.session.add(interest)
        db.session.commit()
        invia_email_alert_nuova_iscrizione(interest)
        return redirect(url_for('course_interest_confirmation'))

    topic_key = request.args.get('tematica', '').strip()
    form_data = {'tematica': topic_key} if topic_key in COURSE_INTEREST_TOPICS else {}
    return render_template(
        'interesse_corsi.html',
        topics=COURSE_INTEREST_TOPICS,
        form_data=form_data,
    )


@app.route('/iscrizione-corsi/interesse/conferma')
def course_interest_confirmation():
    return render_template('conferma_interesse_corsi.html')


@app.route('/iscrizione-corsi/<corso_tipo>', methods=['GET', 'POST'])
@limiter.limit("5 per minute", methods=['POST'])
def iscrizione_corso(corso_tipo):
    if corso_tipo == 'bls-d':
        return redirect(
            url_for('iscrizione_corso', corso_tipo='blsd'),
            code=308 if request.method == 'POST' else 301,
        )

    corso_tipo = next(
        (tipo for tipo, slug in CORSI_SLUG_PUBBLICI.items() if slug == corso_tipo),
        corso_tipo,
    )
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
                return _render_iscrizione_con_errore(
                    corso_tipo,
                    'Seleziona una data disponibile tra quelle aperte.',
                    'data_corso',
                )
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
            return _render_iscrizione_con_errore(corso_tipo, 'Inserisci nome e cognome.', 'nome')
        if not codice_fiscale or len(codice_fiscale) > 32:
            return _render_iscrizione_con_errore(corso_tipo, 'Inserisci il codice fiscale.', 'codice_fiscale')
        if not telefono or not _telefono_valido(telefono):
            return _render_iscrizione_con_errore(corso_tipo, 'Inserisci un numero di telefono valido.', 'telefono')
        if corso_id and not email:
            return _render_iscrizione_con_errore(
                corso_tipo,
                'Inserisci un indirizzo email: verrà usato per comunicarti la conferma del posto.',
                'email',
            )
        if email and not _email_valida(email):
            return _render_iscrizione_con_errore(corso_tipo, 'Inserisci un indirizzo email valido.', 'email')
        if len(nome_bambino) > 100:
            return _render_iscrizione_con_errore(corso_tipo, 'Il nome del bambino è troppo lungo.', 'nome_bambino')
        if len(eta_bambino) > 40:
            return _render_iscrizione_con_errore(corso_tipo, 'L\'età del bambino è troppo lunga.', 'eta_bambino')

        if nome_bambino:
            extra['nome_bambino'] = nome_bambino
        if eta_bambino:
            extra['eta_bambino'] = eta_bambino

        if corso_tipo == 'bls-d':
            if partecipazione not in corso['partecipazione_options']:
                return _render_iscrizione_con_errore(corso_tipo, 'Seleziona il tipo di partecipazione.', 'partecipazione')
            dichiarazioni = {
                'prove_pratiche': _checkbox_checked('prove_pratiche'),
                'buono_stato_salute': _checkbox_checked('buono_stato_salute'),
                'richiesta_non_conferma': _checkbox_checked('richiesta_non_conferma'),
            }
            if not all(dichiarazioni.values()):
                campo_mancante = next(campo for campo, valore in dichiarazioni.items() if not valore)
                return _render_iscrizione_con_errore(
                    corso_tipo,
                    'Per procedere devi accettare tutte le dichiarazioni obbligatorie.',
                    campo_mancante,
                )
            if not consenso_privacy:
                return _render_iscrizione_con_errore(corso_tipo, 'Devi autorizzare il trattamento dei dati personali.', 'consenso_privacy')
            if request.form.get('conferma_finale') != 'on':
                return _render_iscrizione_con_errore(corso_tipo, 'Devi confermare la richiesta di iscrizione al corso.', 'conferma_finale')

            extra = {
                **extra,
                **dichiarazioni,
            }

        elif corso_tipo == 'disostruzione-pediatrica':
            if partecipazione not in corso['partecipazione_options']:
                return _render_iscrizione_con_errore(corso_tipo, 'Seleziona se partecipi da solo/a o in coppia.', 'partecipazione')
            partecipazione_coppia = partecipazione == 'Coppia 60 euro'
            nome_secondo = request.form.get('nome_secondo_partecipante', '').strip() if partecipazione_coppia else ''
            cf_secondo = request.form.get('codice_fiscale_secondo_partecipante', '').strip() if partecipazione_coppia else ''
            if partecipazione_coppia and (not nome_secondo or len(nome_secondo) > 100):
                return _render_iscrizione_con_errore(
                    corso_tipo,
                    'Per la partecipazione in coppia inserisci il nome del secondo partecipante.',
                    'nome_secondo_partecipante',
                )
            if len(cf_secondo) > 32:
                return _render_iscrizione_con_errore(
                    corso_tipo,
                    'Il codice fiscale del secondo partecipante è troppo lungo.',
                    'codice_fiscale_secondo_partecipante',
                )

            dichiarazioni = {
                'scopo_informativo': _checkbox_checked('scopo_informativo'),
                'no_certificazione': _checkbox_checked('no_certificazione'),
                'buono_stato_salute': _checkbox_checked('buono_stato_salute'),
            }
            if not all(dichiarazioni.values()):
                campo_mancante = next(campo for campo, valore in dichiarazioni.items() if not valore)
                return _render_iscrizione_con_errore(
                    corso_tipo,
                    'Per procedere devi accettare tutte le dichiarazioni obbligatorie.',
                    campo_mancante,
                )
            if not consenso_privacy:
                return _render_iscrizione_con_errore(corso_tipo, 'Devi autorizzare il trattamento dei dati personali.', 'consenso_privacy')

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
                    return _render_iscrizione_con_errore(corso_tipo, error_message, field_name)
            if not consenso_privacy:
                return _render_iscrizione_con_errore(corso_tipo, 'Devi acconsentire al trattamento dei dati personali.', 'consenso_privacy')
            if request.form.get('conferma_finale') != 'on':
                return _render_iscrizione_con_errore(corso_tipo, 'Devi confermare la richiesta di iscrizione al corso.', 'conferma_finale')

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
                return _render_iscrizione_con_errore(corso_tipo, 'Seleziona il tipo di partecipazione.', 'partecipazione')
            if not consenso_privacy:
                return _render_iscrizione_con_errore(corso_tipo, 'Devi autorizzare il trattamento dei dati personali.', 'consenso_privacy')
            if request.form.get('conferma_finale') != 'on':
                return _render_iscrizione_con_errore(corso_tipo, 'Devi confermare la richiesta di iscrizione al laboratorio.', 'conferma_finale')

        posti_richiesti = 0 if tipo_richiesta == 'ricontatto' else _posti_iscrizione_da_partecipazione(partecipazione)
        in_lista_attesa = False
        if corso_id:
            corso_selezionato = Corso.query.filter_by(id=corso_id).with_for_update().first()
            if not corso_selezionato or corso_selezionato.stato != 'Aperto':
                db.session.rollback()
                return _render_iscrizione_con_errore(
                    corso_tipo,
                    'La data scelta non è più aperta. Seleziona un’altra edizione.',
                    'data_corso',
                )
            in_lista_attesa = not _corso_accetta_prenotazione_online(
                corso_selezionato,
                posti_richiesti,
            )

        iscrizione = IscrizioneCorso(
            corso_id=corso_id,
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
            posti=0 if in_lista_attesa else posti_richiesti,
            posti_richiesti=posti_richiesti,
            scadenza_gestione=prossima_scadenza_lavorativa(),
            consenso_privacy=consenso_privacy,
            consenso_immagini=consenso_immagini,
            stato='Lista attesa' if in_lista_attesa else 'Nuova',
            token_lista_attesa=secrets.token_urlsafe(48) if in_lista_attesa else None,
        )
        db.session.add(iscrizione)
        patient = None
        patient_created = False
        if in_lista_attesa:
            patient, patient_created = _ensure_patient_for_course_registration(iscrizione)
        db.session.commit()
        if patient:
            _audit_automatic_course_patient_link(
                iscrizione,
                patient,
                patient_created,
                'creazione_anagrafica_da_lista_attesa',
            )
        invia_email_alert_nuova_iscrizione(iscrizione)
        if in_lista_attesa:
            return redirect(url_for('conferma_iscrizione_corso', lista_attesa='1'))
        return redirect(url_for('conferma_iscrizione_corso'))

    corso_id_preselezionato = request.args.get('corso_id', type=int)
    opzioni_disponibili = {option['corso_id'] for option in corso['data_options']}
    form_data = (
        {'data_corso': str(corso_id_preselezionato)}
        if corso_id_preselezionato in opzioni_disponibili
        else {}
    )
    return render_template(
        'iscrizione_corso.html',
        corso_tipo=corso_tipo,
        corso_slug=_slug_pubblico_corso(corso_tipo),
        corso=corso,
        form_data=form_data,
        form_error_field=None,
        selected_course_location=_luogo_corso_per_modulo(corso, form_data),
    )


@app.route('/iscrizione-corsi')
def iscrizione_corsi():
    oggi = local_today().isoformat()
    corsi_in_calendario = Corso.query.filter(
        Corso.tipo.in_(tuple(CORSI_ISCRIVIBILI)),
        Corso.data >= oggi,
        Corso.stato.in_(['Aperto', 'Completo']),
        Corso.archiviato_il.is_(None),
    ).order_by(Corso.data, Corso.ora).all()
    edizioni_programmate = []
    for corso in corsi_in_calendario:
        corso_slug = _slug_pubblico_corso(corso.tipo)
        iscrivibile = corso.stato == 'Aperto'
        destinazione = url_for(
            'iscrizione_corso',
            corso_tipo=corso_slug,
            **({'corso_id': corso.id} if iscrivibile else {}),
        )
        if iscrivibile:
            ancora = 'iscrizione-individuale' if corso.tipo == 'bls-d' else 'modulo-iscrizione-corso'
            destinazione = f'{destinazione}#{ancora}'
        edizioni_programmate.append({
            'corso': corso,
            'data_label': _formatta_data_corso(corso.data),
            'destinazione': destinazione,
            'stato_label': 'Lista d’attesa' if iscrivibile and not _corso_ha_posti(corso) else corso.stato,
            'iscrivibile': iscrivibile,
        })
    return render_template(
        'iscrizione_corsi.html',
        edizioni_programmate=edizioni_programmate,
    )


@app.route('/iscrizione-corsi/conferma')
def conferma_iscrizione_corso():
    return render_template(
        'conferma_iscrizione_corso.html',
        lista_attesa=request.args.get('lista_attesa') == '1',
    )


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
@limiter.limit("5 per minute", methods=['POST'])
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

        percorso = PercorsoAccompagnamento.query.filter_by(
            id=percorso.id
        ).with_for_update().first()
        if not percorso:
            abort(404)
        if (
            percorso.stato != 'Aperto'
            or not _percorso_ha_posto(percorso)
        ):
            db.session.rollback()
            return _render_accompagnamento_privato(
                percorso,
                'Il percorso ha raggiunto la capienza massima.'
            )

        extra = {
            'iscrizione_privata_accompagnamento': True,
            'data_presunta_parto': data_presunta_parto,
            'partner_presente': partner_presente,
        }
        iscrizione = IscrizioneCorso(
            percorso_accompagnamento=percorso,
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
            stato='Nuova',
            scadenza_gestione=prossima_scadenza_lavorativa(),
        )
        db.session.add(iscrizione)
        db.session.flush()
        for incontro in _incontri_percorso(percorso):
            db.session.add(PresenzaAccompagnamento(iscrizione=iscrizione, incontro=incontro))
        db.session.commit()
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
@limiter.limit('5 per hour', methods=['POST'])
def prenota_call_sonno():
    prima_data = prima_data_call_disponibile().isoformat()
    template_context = {
        'prima_data': prima_data,
        'difficolta_sonno': DIFFICOLTA_SONNO,
        'durate_difficolta_sonno': DURATE_DIFFICOLTA_SONNO,
        'ruoli_richiedente_sonno': RUOLI_RICHIEDENTE_SONNO,
        'orari_call': ORARI_CALL_SONNO,
    }
    if request.method == 'POST':
        token = session.pop('_csrf_token', None)
        if not token or token != request.form.get('_csrf_token'):
            flash('Richiesta non valida. Riprova.', 'error')
            return render_template(
                'prenota_call_sonno.html', form_data=request.form, **template_context
            )

        nome = request.form.get('nome', '').strip()
        telefono = request.form.get('telefono', '').strip()
        email = request.form.get('email', '').strip()
        difficolta = request.form.get('difficolta_principale', '').strip()
        difficolta_altro = request.form.get('difficolta_altro', '').strip()
        ruolo_richiedente = request.form.get('ruolo_richiedente', '').strip()
        durata_difficolta = request.form.get('durata_difficolta', '').strip()
        obiettivo_call = request.form.get('obiettivo_call', '').strip()
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
        if ruolo_richiedente not in RUOLI_RICHIEDENTE_SONNO:
            errori.append('Indica se sei genitore o tutore legale del bambino.')
        if difficolta not in DIFFICOLTA_SONNO:
            errori.append('Seleziona la difficoltà principale.')
        if difficolta == 'Altro' and not difficolta_altro:
            errori.append('Descrivi brevemente la difficoltà principale.')
        if len(difficolta_altro) > 300:
            errori.append('La descrizione può contenere al massimo 300 caratteri.')
        if durata_difficolta not in DURATE_DIFFICOLTA_SONNO:
            errori.append('Indica da quanto tempo osservi la difficoltà.')
        if not obiettivo_call or len(obiettivo_call) > 300:
            errori.append('Indica cosa vorresti capire durante la call (massimo 300 caratteri).')
        if not request.form.get('presa_visione_offerta'):
            errori.append('Conferma di aver visto modalità e prezzi delle consulenze.')
        if not request.form.get('conferma_ambito'):
            errori.append('Conferma che la richiesta non riguarda un’urgenza o una diagnosi.')
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
            return render_template(
                'prenota_call_sonno.html', form_data=request.form, **template_context
            )

        utm = {
            campo: request.form.get(campo, '').strip()[:100] or None
            for campo in ['utm_source', 'utm_medium', 'utm_campaign', 'utm_content']
        }

        nuova_call = CallSonno(
            nome=nome,
            telefono=telefono,
            email=email,
            eta_bambino_mesi=eta_mesi,
            difficolta_principale=difficolta,
            difficolta_altro=difficolta_altro if difficolta == 'Altro' else None,
            ruolo_richiedente=ruolo_richiedente,
            durata_difficolta=durata_difficolta,
            obiettivo_call=obiettivo_call,
            presa_visione_offerta=True,
            conferma_ambito=True,
            consenso_privacy=True,
            data=data_scelta,
            ora=ora,
            scadenza_gestione=prossima_scadenza_lavorativa(),
            **utm,
        )
        db.session.add(nuova_call)
        db.session.commit()
        crea_o_aggiorna_evento_calendario_call_sonno(nuova_call)
        invia_email_ricezione_call_sonno(nuova_call)
        invia_email_alert_call_sonno(nuova_call)
        session['ultima_call_sonno'] = nuova_call.id
        return redirect(url_for('conferma_call_sonno'))

    form_data = {
        campo: request.args.get(campo, '').strip()[:100]
        for campo in ['utm_source', 'utm_medium', 'utm_campaign', 'utm_content']
    }
    return render_template(
        'prenota_call_sonno.html', form_data=form_data, **template_context
    )


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
@limiter.limit('10 per hour', methods=['POST'])
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
        attive = [i for i in iscrizioni_corso if i.stato not in {'Annullato', 'Lista attesa', 'Invitato'} and i.archiviata_il is None]
        lista_attesa = [i for i in iscrizioni_corso if i.stato in {'Lista attesa', 'Invitato'}]
        confermate = [i for i in attive if i.stato == 'Confermato']
        open_day = [i for i in attive if i.tipo_richiesta == 'open_day']
        effettive = [i for i in attive if i.tipo_richiesta == 'iscrizione_effettiva']
        richieste = [
            i for i in attive
            if i.tipo_richiesta in ['richiesta_iscrizione', 'iscrizione_effettiva']
        ]
        posti_attivi = _posti_attivi_corso(corso.id)
        posti_confermati = sum(
            iscrizione.posti
            if iscrizione.posti is not None
            else _posti_iscrizione_da_partecipazione(iscrizione.partecipazione)
            for iscrizione in confermate
        )
        capienza = corso.capienza_massima
        posti_liberi = None if capienza is None else max(capienza - posti_attivi, 0)
        stato = corso.stato or 'Aperto'
        if stato == 'Aperto' and posti_liberi == 0:
            stato = 'Completo'
        panoramica.append({
            'corso': corso,
            'iscrizioni': iscrizioni_corso,
            'attive_count': len(attive),
            'lista_attesa_count': len(lista_attesa),
            'confermate_count': len(confermate),
            'open_day_count': len(open_day),
            'effettive_count': len(effettive),
            'richieste_count': len(richieste),
            'posti_attivi': posti_attivi,
            'posti_confermati': posti_confermati,
            'capienza': capienza,
            'posti_liberi': posti_liberi,
            'stato': stato,
        })
    return panoramica


@app.route('/prenota', methods=['GET', 'POST'])
@limiter.limit("5 per minute", methods=['POST'])
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
        oggi = local_today().strftime('%Y-%m-%d')
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
            note=note,
            consenso_privacy=True,
            scadenza_gestione=prossima_scadenza_lavorativa(),
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
@limiter.limit("5 per minute", methods=['POST'])
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
            login_user(utente, remember=False)
            session.permanent = True
            session.pop('conflitti_calendar_rimandati', None)
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
    session.pop('conflitti_calendar_rimandati', None)
    logout_user()
    return redirect(url_for('login'))


# ─── AREA ADMIN ───

@app.route('/admin')
@login_required
def admin():
    esito_controllo_calendar = _riconciliazione_admin_se_necessaria()
    oggi = local_today().strftime('%Y-%m-%d')
    filtro = request.args.get('filtro', 'in_attesa')

    # Gli appuntamenti confermati già trascorsi diventano conclusi; lo stato
    # resta sempre correggibile dalla scheda pratica.
    adesso_locale = local_now()
    for elemento in Appuntamento.query.filter_by(stato='Confermato').all():
        try:
            fine = _intervallo_locale(
                elemento.data,
                elemento.ora,
                elemento.duration_minutes or DURATA_SLOT_MINUTI,
            )[1]
        except (TypeError, ValueError):
            continue
        if fine < adesso_locale:
            elemento.stato = 'Concluso'
            db.session.add(RegistroModifica(
                azione='stato_automatico',
                entita_tipo='Appuntamento',
                entita_id=elemento.id,
                dettagli=json.dumps(
                    {'da': 'Confermato', 'a': 'Concluso'},
                    ensure_ascii=False,
                ),
                admin_id=current_user.id,
            ))
    db.session.commit()

    vista_agenda = request.args.get('vista', 'mese')
    if vista_agenda not in {'giorno', 'settimana', 'mese'}:
        vista_agenda = 'mese'
    mese_richiesto = request.args.get('mese', '').strip()
    try:
        if vista_agenda == 'mese' and mese_richiesto:
            data_agenda = datetime.strptime(mese_richiesto, '%Y-%m').date().replace(day=1)
        else:
            data_agenda = datetime.strptime(request.args.get('data', oggi), '%Y-%m-%d').date()
    except ValueError:
        data_agenda = local_today()
    if vista_agenda == 'mese':
        inizio_agenda = data_agenda.replace(day=1)
        ultimo_giorno = calendar_module.monthrange(inizio_agenda.year, inizio_agenda.month)[1]
        fine_agenda = inizio_agenda.replace(day=ultimo_giorno)
        agenda_precedente = (inizio_agenda - timedelta(days=1)).replace(day=1)
        agenda_successiva = (fine_agenda + timedelta(days=1)).replace(day=1)
    else:
        inizio_agenda = data_agenda
        fine_agenda = data_agenda + timedelta(days=6 if vista_agenda == 'settimana' else 0)
        passo = 7 if vista_agenda == 'settimana' else 1
        agenda_precedente = inizio_agenda - timedelta(days=passo)
        agenda_successiva = inizio_agenda + timedelta(days=passo)
    agenda = _agenda_operativa(inizio_agenda, fine_agenda)
    agenda_per_giorno = defaultdict(list)
    for evento_agenda in agenda:
        agenda_per_giorno[evento_agenda['inizio'].date()].append(evento_agenda)
    calendario_mese = []
    if vista_agenda == 'mese':
        for settimana in calendar_module.Calendar(firstweekday=0).monthdatescalendar(
            inizio_agenda.year,
            inizio_agenda.month,
        ):
            calendario_mese.append([
                {
                    'data': giorno,
                    'nel_mese': giorno.month == inizio_agenda.month,
                    'oggi': giorno == local_today(),
                    'eventi': agenda_per_giorno.get(giorno, []),
                }
                for giorno in settimana

            ])
    etichetta_mese = f'{MESI_ITALIANI[inizio_agenda.month - 1]} {inizio_agenda.year}'
    richieste_admin = []
    for elemento in Appuntamento.query.filter(Appuntamento.stato == 'In attesa', Appuntamento.archiviato_il.is_(None)).all():
        richieste_admin.append({'tipo': 'Appuntamento', 'id': elemento.id, 'nome': elemento.nome, 'oggetto': elemento.servizio, 'scadenza': elemento.scadenza_gestione, 'stato': elemento.stato})
    for elemento in CallSonno.query.filter(CallSonno.stato == 'In attesa', CallSonno.archiviata_il.is_(None)).all():
        richieste_admin.append({'tipo': 'CallSonno', 'id': elemento.id, 'nome': elemento.nome, 'oggetto': 'Call sonno', 'scadenza': elemento.scadenza_gestione, 'stato': elemento.stato})
    filtro_tipo_richieste = request.args.get('tipo_corso', '').strip()
    iscrizioni_richieste_query = IscrizioneCorso.query.filter(IscrizioneCorso.stato.in_(['Nuova', 'Contattato', 'Lista attesa', 'Invitato']), IscrizioneCorso.archiviata_il.is_(None))
    if filtro_tipo_richieste in CORSI_ADMIN_TIPI:
        iscrizioni_richieste_query = iscrizioni_richieste_query.filter(IscrizioneCorso.corso_tipo == filtro_tipo_richieste)
    for elemento in iscrizioni_richieste_query.all():
        richieste_admin.append({'tipo': 'IscrizioneCorso', 'id': elemento.id, 'nome': elemento.nome, 'oggetto': elemento.corso_titolo, 'scadenza': elemento.scadenza_gestione, 'stato': elemento.stato})
    richieste_azienda = RichiestaAzienda.query.filter(
        RichiestaAzienda.archiviata_il.is_(None),
    ).order_by(RichiestaAzienda.creato_il.desc()).all()
    for elemento in richieste_azienda:
        if elemento.stato not in {'Confermata', 'Chiusa'}:
            richieste_admin.append({'tipo': 'RichiestaAzienda', 'id': elemento.id, 'nome': elemento.organizzazione, 'oggetto': FORMAZIONE_AZIENDA_TIPI.get(elemento.corso_tipo, 'Progetto da valutare'), 'scadenza': elemento.scadenza_gestione, 'stato': elemento.stato})

    richieste_admin.sort(key=lambda elemento: elemento['scadenza'] or datetime.max)
    for elemento in richieste_admin:
        elemento['urgente'] = bool(elemento['scadenza'] and elemento['scadenza'] < local_now_naive())

    attivita_admin = AttivitaAdmin.query.filter(AttivitaAdmin.stato != 'Chiusa').order_by(AttivitaAdmin.scadenza).all()
    errori_aperti = RegistroEvento.query.filter(
        RegistroEvento.esito.in_(['errore', 'avviso']),
        RegistroEvento.risolto_il.is_(None),
    ).order_by(RegistroEvento.creato_il.desc()).all()
    conflitti_calendar = _conflitti_calendar_prioritari()
    conflitti_calendar_chiavi = {
        f"{voce['tipo']}:{voce['id']}"
        for voce in conflitti_calendar
    }
    if not conflitti_calendar:
        session.pop('conflitti_calendar_rimandati', None)
    conflitti_rimandati_salvati = session.get('conflitti_calendar_rimandati', [])
    conflitti_rimandati = set(
        conflitti_rimandati_salvati
        if isinstance(conflitti_rimandati_salvati, list)
        else []
    )
    mostra_modal_conflitti = bool(
        conflitti_calendar_chiavi - conflitti_rimandati
    )
    fine_settimana = (local_today() + timedelta(days=7)).isoformat()
    corsi_settimana = Corso.query.filter(
        Corso.data.between(oggi, fine_settimana),
        Corso.stato != 'Annullato',
        Corso.archiviato_il.is_(None),
    ).all()
    posti_corsi_settimana = sum(_posti_attivi_corso(corso.id) for corso in corsi_settimana)
    capienza_corsi_settimana = sum(corso.capienza_massima or 0 for corso in corsi_settimana)
    funnel_sonno = {
        'in_attesa': CallSonno.query.filter_by(stato='In attesa').count(),
        'confermate': CallSonno.query.filter_by(stato='Confermata').count(),
        'concluse': CallSonno.query.filter_by(stato='Conclusa').count(),
    }

    ricerca = request.args.get('q', '').strip()
    risultati_ricerca = []
    pazienti_query = PersonaCorso.query
    if ricerca:
        criterio = f'%{ricerca}%'
        pazienti_query = pazienti_query.filter(db.or_(
            PersonaCorso.nome.ilike(criterio),
            PersonaCorso.telefono.ilike(criterio),
            PersonaCorso.email.ilike(criterio),
            PersonaCorso.codice_fiscale.ilike(criterio),
        ))
        for elemento in Appuntamento.query.filter(db.or_(Appuntamento.nome.ilike(criterio), Appuntamento.telefono.ilike(criterio), Appuntamento.email.ilike(criterio))).limit(20):
            risultati_ricerca.append({'tipo': 'Appuntamento', 'id': elemento.id, 'nome': elemento.nome, 'dettaglio': f'{elemento.telefono} · {elemento.servizio}'})
        for elemento in CallSonno.query.filter(db.or_(CallSonno.nome.ilike(criterio), CallSonno.telefono.ilike(criterio), CallSonno.email.ilike(criterio))).limit(20):
            risultati_ricerca.append({'tipo': 'CallSonno', 'id': elemento.id, 'nome': elemento.nome, 'dettaglio': f'{elemento.telefono} · call sonno'})
        for elemento in IscrizioneCorso.query.filter(db.or_(IscrizioneCorso.nome.ilike(criterio), IscrizioneCorso.telefono.ilike(criterio), IscrizioneCorso.email.ilike(criterio), IscrizioneCorso.codice_fiscale.ilike(criterio))).limit(20):
            risultati_ricerca.append({'tipo': 'IscrizioneCorso', 'id': elemento.id, 'nome': elemento.nome, 'dettaglio': f'{elemento.telefono} · {elemento.corso_titolo}'})

        for elemento in RichiestaAzienda.query.filter(db.or_(RichiestaAzienda.organizzazione.ilike(criterio), RichiestaAzienda.referente.ilike(criterio), RichiestaAzienda.telefono.ilike(criterio), RichiestaAzienda.email.ilike(criterio))).limit(20):
            risultati_ricerca.append({'tipo': 'RichiestaAzienda', 'id': elemento.id, 'nome': elemento.organizzazione, 'dettaglio': f'{elemento.referente} · {elemento.telefono}'})
    pazienti = pazienti_query.order_by(PersonaCorso.nome).all()
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

    corsi = Corso.query.filter(
        Corso.data >= oggi,
        Corso.stato != 'Annullato',
        Corso.archiviato_il.is_(None),
    ).order_by(Corso.data, Corso.ora).all()
    corsi_archivio = Corso.query.filter(db.or_(
        Corso.data < oggi,
        Corso.stato == 'Annullato',
        Corso.archiviato_il.is_not(None),
    )).order_by(Corso.data.desc(), Corso.ora.desc()).all()
    panoramica_corsi = _panoramica_corsi(corsi)
    panoramica_corsi_archivio = _panoramica_corsi(corsi_archivio)
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
    if filtro_iscrizioni not in {'', 'ricontatto', 'open_day'}:
        filtro_iscrizioni = ''
    if filtro_iscrizioni == 'open_day' and filtro_tipo_corso != 'accompagnamento-nascita':
        filtro_iscrizioni = ''
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
    filtri_iscrizioni_da_gestire = (
        IscrizioneCorso.archiviata_il.is_(None),
        db.or_(
            IscrizioneCorso.stato.in_(STATI_ISCRIZIONE_DA_GESTIRE),
            db.and_(
                IscrizioneCorso.tipo_richiesta == 'ricontatto',
                IscrizioneCorso.stato != 'Annullato',
            ),
        ),
    )
    conteggi_tipo = db.session.query(
        IscrizioneCorso.corso_tipo,
        db.func.count(IscrizioneCorso.id)
    ).filter(*filtri_iscrizioni_da_gestire).group_by(IscrizioneCorso.corso_tipo).all()
    for tipo, count in conteggi_tipo:
        if tipo in iscrizioni_per_tipo_count:
            iscrizioni_per_tipo_count[tipo] = count

    iscrizioni_query = IscrizioneCorso.query.filter(*filtri_iscrizioni_da_gestire)
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
    iscrizioni_totali_count = IscrizioneCorso.query.filter(*filtri_iscrizioni_da_gestire).count()
    iscrizioni_nuove_count = IscrizioneCorso.query.filter(
        IscrizioneCorso.stato == 'Nuova',
        IscrizioneCorso.archiviata_il.is_(None),
    ).count()
    call_sonno = CallSonno.query.order_by(CallSonno.data, CallSonno.ora).all()
    call_sonno_in_attesa_count = CallSonno.query.filter_by(stato='In attesa').count()
    registro_eventi = RegistroEvento.query.order_by(RegistroEvento.creato_il.desc()).limit(30).all()
    riferimenti_eventi = {
        evento.id: _riferimento_registro_evento(evento)
        for evento in [*errori_aperti, *registro_eventi]
    }
    eventi_critici_count = RegistroEvento.query.filter(
        RegistroEvento.esito.in_(['errore', 'avviso']),
        RegistroEvento.creato_il >= utc_now() - timedelta(days=7)
    ).count()
    return render_template('admin.html',
                           agenda_per_giorno=dict(agenda_per_giorno),
                           inizio_agenda=inizio_agenda,
                           fine_agenda=fine_agenda,
                           agenda_precedente=agenda_precedente,
                           agenda_successiva=agenda_successiva,
                           calendario_mese=calendario_mese,
                           etichetta_mese=etichetta_mese,
                           giorni_settimana_brevi=GIORNI_SETTIMANA_BREVI,
                           richieste_azienda=richieste_azienda,
                           oggi_admin=local_today(),
                           formazione_azienda_tipi=FORMAZIONE_AZIENDA_TIPI,
                           richieste_azienda_aperte_count=sum(1 for elemento in richieste_azienda if elemento.stato not in {'Confermata', 'Chiusa'}),
                           adesso_admin=local_now_naive(),
                           vista_agenda=vista_agenda,
                           richieste_admin=richieste_admin,
                           richieste_urgenti_count=sum(1 for elemento in richieste_admin if elemento['urgente']),
                           richieste_nuove_count=len(richieste_admin),
                           attivita_admin=attivita_admin,
                           errori_aperti=errori_aperti,
                           conflitti_calendar=conflitti_calendar,
                           conflitti_calendar_chiavi=conflitti_calendar_chiavi,
                           mostra_modal_conflitti=mostra_modal_conflitti,
                           errore_controllo_calendar=(
                               esito_controllo_calendar.get('errore')
                               if esito_controllo_calendar
                               else None
                           ),
                           ricerca=ricerca,
                           risultati_ricerca=risultati_ricerca,
                           pazienti=pazienti,
                           calendar_configurato=bool(app.config.get('GOOGLE_CALENDAR_ID') and app.config.get('GOOGLE_SERVICE_ACCOUNT_FILE')),
                           mail_soppressa=bool(app.config.get('MAIL_SUPPRESS_SEND')),
                           eventi_oggi_count=sum(len(eventi) for giorno, eventi in agenda_per_giorno.items() if giorno == local_today()),
                           corsi_settimana_count=len(corsi_settimana),
                           posti_corsi_settimana=posti_corsi_settimana,
                           capienza_corsi_settimana=capienza_corsi_settimana,
                           funnel_sonno=funnel_sonno,
                           appuntamenti=appuntamenti,
                           corsi=corsi,
                           corsi_archivio=corsi_archivio,
                           panoramica_corsi=panoramica_corsi,
                           panoramica_corsi_archivio=panoramica_corsi_archivio,
                           corsi_admin_tipi=CORSI_ADMIN_TIPI,
                           persone_corsi=persone_corsi,
                           panoramica_percorsi_accompagnamento=panoramica_percorsi_accompagnamento,
                           presenze_accompagnamento=presenze_accompagnamento,
                           stati_percorso_accompagnamento=STATI_PERCORSO_ACCOMPAGNAMENTO_VALIDI,
                           iscrizioni_corsi=iscrizioni_corsi,
                           iscrizioni_totali_count=iscrizioni_totali_count,
                           persone_corsi_count=len(persone_corsi),
                           pazienti_count=len(persone_corsi),
                           iscrizioni_nuove_count=iscrizioni_nuove_count,
                           call_sonno=call_sonno,
                           call_sonno_in_attesa_count=call_sonno_in_attesa_count,
                           formule_sonno=FORMULE_SONNO,
                           registro_eventi=registro_eventi,
                           riferimenti_eventi=riferimenti_eventi,
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


def _url_dettaglio_admin(tipo, entita_id):
    return url_for('dettaglio_admin', tipo=tipo, entita_id=entita_id)


@app.route('/admin/pratica/<tipo>/<int:entita_id>')
@login_required
def dettaglio_admin(tipo, entita_id):
    entita = _entita_admin(tipo, entita_id)
    if entita is None:
        abort(404)
    note = NotaAdmin.query.filter_by(entita_tipo=tipo, entita_id=entita_id).order_by(NotaAdmin.creata_il.desc()).all()
    email = EmailOperativa.query.filter_by(entita_tipo=tipo, entita_id=entita_id).order_by(EmailOperativa.creata_il.desc()).all()
    modifiche = RegistroModifica.query.filter_by(entita_tipo=tipo, entita_id=entita_id).order_by(RegistroModifica.creato_il.desc()).all()
    difformita = {}
    if getattr(entita, 'difformita_calendario', None):
        try:
            difformita = json.loads(entita.difformita_calendario)
        except json.JSONDecodeError:
            difformita = {'dettaglio': entita.difformita_calendario}
    elif getattr(entita, 'sincronizzazione', None) in {
        'difforme', 'eliminato_esternamente'
    }:
        difformita = _dettagli_anomalia_calendar(tipo, entita)
    duplicati = _possibili_duplicati_persona(entita.persona) if tipo == 'IscrizioneCorso' and entita.persona else []
    corsi_disponibili = Corso.query.filter(
        Corso.data >= local_today().isoformat(),
        Corso.stato != 'Annullato',
        Corso.archiviato_il.is_(None),
    ).order_by(Corso.data, Corso.ora).all()
    collegamento_persona = CollegamentoPersona.query.filter_by(entita_tipo=tipo, entita_id=entita_id).first()
    persona_collegata = entita.persona if tipo == 'IscrizioneCorso' else (collegamento_persona.persona if collegamento_persona else None)
    storico_persona = _storico_persona_admin(persona_collegata) if persona_collegata else []
    iscrizioni_corso = (
        IscrizioneCorso.query.filter_by(corso_id=entita.id).order_by(IscrizioneCorso.nome).all()
        if tipo == 'Corso'
        else []
    )
    destinatari_aggiornamento_corso = [
        iscrizione
        for iscrizione in iscrizioni_corso
        if iscrizione.email
        and iscrizione.stato not in STATI_LISTA_ATTESA | {'Annullato'}
        and iscrizione.archiviata_il is None
    ]
    return render_template(
        'admin_dettaglio.html',
        tipo=tipo,
        entita=entita,
        nome_entita=_nome_entita_admin(tipo, entita),
        note_admin=note,
        email_admin=email,
        modifiche_admin=modifiche,
        difformita=difformita,
        duplicati=duplicati,
        corsi_disponibili=corsi_disponibili,
        iscrizioni_corso=iscrizioni_corso,
        destinatari_aggiornamento_corso=destinatari_aggiornamento_corso,
        persone_disponibili=PersonaCorso.query.order_by(PersonaCorso.nome).all(),
        persona_collegata=persona_collegata,
        storico_persona=storico_persona,
        stati_appuntamento=STATI_APPUNTAMENTO_ADMIN,
        stati_richiesta_azienda=STATI_RICHIESTA_AZIENDA,
        corsi_admin_tipi=CORSI_ADMIN_TIPI,
        formazione_azienda_tipi=FORMAZIONE_AZIENDA_TIPI,
    )


@app.route('/admin/pratica/<tipo>/<int:entita_id>/nota', methods=['POST'])
@login_required
def aggiungi_nota_admin(tipo, entita_id):
    if not _csrf_admin_valido() or _entita_admin(tipo, entita_id) is None:
        abort(400)
    testo = request.form.get('testo', '').strip()
    if not testo or len(testo) > 4000:
        flash('Inserisci una nota da 1 a 4000 caratteri.', 'error')
    else:
        db.session.add(NotaAdmin(entita_tipo=tipo, entita_id=entita_id, testo=testo))
        db.session.commit()
        registra_modifica('nota_aggiunta', tipo, entita_id)
        flash('Nota aggiunta.', 'success')
    return redirect(_url_dettaglio_admin(tipo, entita_id))


@app.route('/admin/pratica/<tipo>/<int:entita_id>/collega-persona', methods=['POST'])
@login_required
def collega_persona_admin(tipo, entita_id):
    if not _csrf_admin_valido() or tipo not in {'Appuntamento', 'CallSonno'}:
        abort(400)
    pratica = _entita_admin(tipo, entita_id)
    if pratica is None:
        abort(404)
    persona = db.session.get(PersonaCorso, request.form.get('persona_id', type=int))
    if not persona:
        flash('Seleziona una persona valida.', 'error')
        return redirect(_url_dettaglio_admin(tipo, entita_id))
    collegamento = CollegamentoPersona.query.filter_by(entita_tipo=tipo, entita_id=entita_id).first()
    if collegamento:
        collegamento.persona = persona
    else:
        db.session.add(CollegamentoPersona(persona=persona, entita_tipo=tipo, entita_id=entita_id))
    _sync_patient_privacy_consent(persona, tipo, pratica)
    db.session.commit()
    registra_modifica('collegamento_persona', tipo, entita_id, {'persona_id': persona.id})
    flash('Pratica collegata manualmente alla persona.', 'success')
    return redirect(_url_dettaglio_admin(tipo, entita_id))


@app.route('/admin/pratica/<tipo>/<int:entita_id>/crea-paziente', methods=['POST'])
@login_required
def crea_paziente_da_pratica_admin(tipo, entita_id):
    if not _csrf_admin_valido() or tipo not in {'Appuntamento', 'CallSonno'}:
        abort(400)
    pratica = _entita_admin(tipo, entita_id)
    if pratica is None:
        abort(404)
    if CollegamentoPersona.query.filter_by(entita_tipo=tipo, entita_id=entita_id).first():
        flash('La pratica è già collegata a un paziente.', 'error')
        return redirect(_url_dettaglio_admin(tipo, entita_id))
    if pratica.telefono and not _telefono_valido(pratica.telefono):
        flash('Correggi prima il numero di telefono della pratica.', 'error')
        return redirect(_url_dettaglio_admin(tipo, entita_id))
    if pratica.email and not _email_valida(pratica.email):
        flash('Correggi prima l’indirizzo email della pratica.', 'error')
        return redirect(_url_dettaglio_admin(tipo, entita_id))
    paziente = PersonaCorso(
        nome=pratica.nome,
        telefono=pratica.telefono,
        email=pratica.email or None,
        eta_bambino=(
            f'{pratica.eta_bambino_mesi} mesi'
            if tipo == 'CallSonno' and pratica.eta_bambino_mesi is not None
            else None
        ),
    )
    db.session.add(paziente)
    db.session.flush()
    db.session.add(CollegamentoPersona(
        persona=paziente,
        entita_tipo=tipo,
        entita_id=entita_id,
    ))
    _sync_patient_privacy_consent(paziente, tipo, pratica)
    db.session.commit()
    registra_modifica(
        'creazione_anagrafica_da_pratica',
        'PersonaCorso',
        paziente.id,
        {'tipo_pratica': tipo, 'pratica_id': entita_id},
    )
    flash('Paziente creato e pratica collegata.', 'success')
    return redirect(url_for('dettaglio_paziente_admin', id=paziente.id))


@app.route('/admin/paziente/aggiungi', methods=['POST'])
@login_required
def aggiungi_paziente_admin():
    if not _csrf_admin_valido():
        abort(400)
    nome = request.form.get('nome', '').strip()
    telefono = request.form.get('telefono', '').strip()
    email = request.form.get('email', '').strip()
    codice_fiscale = re.sub(r'\s+', '', request.form.get('codice_fiscale', '')).upper()
    if not nome or len(nome) > 100:
        flash('Inserisci nome e cognome del paziente (massimo 100 caratteri).', 'error')
        return redirect(url_for('admin') + '#admin-pazienti')
    if telefono and not _telefono_valido(telefono):
        flash('Inserisci un numero di telefono valido oppure lascia il campo vuoto.', 'error')
        return redirect(url_for('admin') + '#admin-pazienti')
    if email and not _email_valida(email):
        flash('Inserisci un indirizzo email valido.', 'error')
        return redirect(url_for('admin') + '#admin-pazienti')
    if len(codice_fiscale) > 32:
        flash('Il codice fiscale è troppo lungo.', 'error')
        return redirect(url_for('admin') + '#admin-pazienti')
    if codice_fiscale:
        esistente = _persona_corso_da_contatti(codice_fiscale=codice_fiscale)
        if esistente:
            flash('Esiste già un paziente con questo codice fiscale.', 'error')
            return redirect(url_for('dettaglio_paziente_admin', id=esistente.id))
    paziente = PersonaCorso(
        nome=nome,
        telefono=telefono or None,
        email=email or None,
        codice_fiscale=codice_fiscale or None,
    )
    db.session.add(paziente)
    db.session.commit()
    registra_modifica('creazione_anagrafica', 'PersonaCorso', paziente.id)
    flash('Paziente aggiunto all’anagrafica.', 'success')
    return redirect(url_for('dettaglio_paziente_admin', id=paziente.id))


@app.route('/admin/paziente/<int:id>')
@login_required
def dettaglio_paziente_admin(id):
    paziente = db.get_or_404(PersonaCorso, id)
    consensi_privacy = _patient_privacy_history(paziente)
    return render_template(
        'admin_paziente.html',
        paziente=paziente,
        duplicati=_possibili_duplicati_persona(paziente),
        storico_persona=_storico_persona_admin(paziente),
        consensi_privacy=consensi_privacy,
        privacy_accettata=any(
            item['consent'].accettato for item in consensi_privacy
        ),
    )


@app.route('/admin/paziente/<int:id>/modifica', methods=['POST'])
@login_required
def modifica_paziente_admin(id):
    if not _csrf_admin_valido():
        abort(400)
    paziente = db.get_or_404(PersonaCorso, id)
    valori = {
        'nome': request.form.get('nome', '').strip(),
        'telefono': request.form.get('telefono', '').strip(),
        'email': request.form.get('email', '').strip(),
        'codice_fiscale': re.sub(r'\s+', '', request.form.get('codice_fiscale', '')).upper(),
        'nome_bambino': request.form.get('nome_bambino', '').strip(),
        'eta_bambino': request.form.get('eta_bambino', '').strip(),
        'note': request.form.get('note', '').strip(),
    }
    if not valori['nome'] or len(valori['nome']) > 100:
        flash('Inserisci nome e cognome del paziente (massimo 100 caratteri).', 'error')
        return redirect(url_for('dettaglio_paziente_admin', id=id))
    if valori['telefono'] and not _telefono_valido(valori['telefono']):
        flash('Inserisci un numero di telefono valido oppure lascia il campo vuoto.', 'error')
        return redirect(url_for('dettaglio_paziente_admin', id=id))
    if valori['email'] and not _email_valida(valori['email']):
        flash('Inserisci un indirizzo email valido.', 'error')
        return redirect(url_for('dettaglio_paziente_admin', id=id))
    limiti = {
        'email': 100,
        'codice_fiscale': 32,
        'nome_bambino': 100,
        'eta_bambino': 40,
        'note': 4000,
    }
    for campo, limite in limiti.items():
        if len(valori[campo]) > limite:
            flash(f'Il campo {campo.replace("_", " ")} supera il limite consentito.', 'error')
            return redirect(url_for('dettaglio_paziente_admin', id=id))
    if valori['codice_fiscale']:
        esistente = PersonaCorso.query.filter(
            PersonaCorso.id != paziente.id,
            db.func.upper(PersonaCorso.codice_fiscale) == valori['codice_fiscale'],
        ).first()
        if esistente:
            flash('Il codice fiscale appartiene già a un’altra anagrafica.', 'error')
            return redirect(url_for('dettaglio_paziente_admin', id=id))
    campi_modificati = [
        campo for campo, valore in valori.items()
        if (getattr(paziente, campo) or '') != valore
    ]
    for campo, valore in valori.items():
        setattr(paziente, campo, valore or None)
    db.session.commit()
    if campi_modificati:
        registra_modifica(
            'modifica_anagrafica',
            'PersonaCorso',
            paziente.id,
            {'campi': campi_modificati},
        )
    flash('Anagrafica del paziente aggiornata.', 'success')
    return redirect(url_for('dettaglio_paziente_admin', id=id))


@app.route('/admin/pratica/<tipo>/<int:entita_id>/azione', methods=['POST'])
@login_required
def azione_rapida_admin(tipo, entita_id):
    if not _csrf_admin_valido():
        abort(400)
    entita = _entita_admin(tipo, entita_id)
    if entita is None:
        abort(404)
    azione = request.form.get('azione', '')
    etichette = {
        'chiamato': 'Contatto telefonico effettuato.',
        'nessuna_risposta': 'Tentativo di contatto senza risposta.',
        'richiamare': 'Da richiamare.',
        'chiuso': 'Gestione della richiesta chiusa.',
    }
    if azione not in etichette:
        abort(400)
    db.session.add(NotaAdmin(entita_tipo=tipo, entita_id=entita_id, testo=etichette[azione]))
    scadenza = _scadenza_da_form(request.form.get('scadenza'), prossima_scadenza_lavorativa())
    if hasattr(entita, 'scadenza_gestione'):
        entita.scadenza_gestione = None if azione == 'chiuso' else scadenza
    if tipo == 'RichiestaAzienda' and azione == 'chiuso':
        entita.stato = 'Chiusa'
        _sostituisci_attivita_azienda(entita)

    if azione == 'richiamare':
        db.session.add(AttivitaAdmin(
            titolo=f'Richiamare {_nome_entita_admin(tipo, entita)}',
            scadenza=scadenza,
            entita_tipo=tipo,
            entita_id=entita_id,
        ))
    db.session.commit()
    registra_modifica(azione, tipo, entita_id, {'scadenza': scadenza.isoformat() if azione != 'chiuso' else None})
    flash('Azione registrata.', 'success')
    return redirect(_url_dettaglio_admin(tipo, entita_id))


def _sostituisci_attivita_azienda(richiesta, titolo=None, scadenza=None, note=None):
    AttivitaAdmin.query.filter_by(
        entita_tipo='RichiestaAzienda',
        entita_id=richiesta.id,
        stato='Aperta',
    ).update({'stato': 'Chiusa', 'aggiornata_il': utc_now()})
    if titolo:
        db.session.add(AttivitaAdmin(
            titolo=titolo,
            scadenza=scadenza or prossima_scadenza_lavorativa(),
            entita_tipo='RichiestaAzienda',
            entita_id=richiesta.id,
            note=note,
        ))


@app.route('/admin/azienda/<int:id>/stato', methods=['POST'])
@login_required
def aggiorna_stato_richiesta_azienda(id):
    if not _csrf_admin_valido():
        abort(400)
    richiesta = db.get_or_404(RichiestaAzienda, id)
    nuovo_stato = request.form.get('stato', '').strip()
    if nuovo_stato not in STATI_RICHIESTA_AZIENDA:
        abort(400)
    scadenza = _scadenza_da_form(request.form.get('scadenza'))
    prossime_azioni = {
        'Nuova': 'Qualificare richiesta',
        'Contattata': 'Completare la qualificazione',
        'Qualificata': 'Preparare proposta',
        'Proposta inviata': 'Verificare esito proposta',
        'Confermata': 'Programmare il corso riservato',
    }
    stato_precedente = richiesta.stato
    richiesta.stato = nuovo_stato
    richiesta.scadenza_gestione = None if nuovo_stato == 'Chiusa' else scadenza
    titolo = prossime_azioni.get(nuovo_stato)
    if nuovo_stato == 'Confermata' and richiesta.corso_generato_id:
        titolo = None
    _sostituisci_attivita_azienda(
        richiesta,
        f'{titolo} · {richiesta.organizzazione}' if titolo else None,
        scadenza,
    )
    db.session.commit()
    registra_modifica('cambio_stato', 'RichiestaAzienda', richiesta.id, {'da': stato_precedente, 'a': nuovo_stato})
    flash('Stato e prossima attività aggiornati.', 'success')
    return redirect(_url_dettaglio_admin('RichiestaAzienda', richiesta.id))


@app.route('/admin/azienda/<int:id>/invia-proposta', methods=['POST'])
@login_required
def invia_proposta_azienda_admin(id):
    if not _csrf_admin_valido() or request.form.get('conferma_invio') != '1':
        abort(400)
    richiesta = db.get_or_404(RichiestaAzienda, id)
    oggetto = request.form.get('oggetto_email', '').strip()
    corpo = request.form.get('corpo_email', '').strip()
    if not oggetto or len(oggetto) > 255 or not corpo or len(corpo) > 10000:
        flash('Inserisci oggetto e testo della proposta.', 'error')
        return redirect(_url_dettaglio_admin('RichiestaAzienda', richiesta.id))
    try:
        _invia_email_tracciata(
            Message(subject=oggetto, recipients=[richiesta.email], body=corpo),
            'RichiestaAzienda',
            richiesta.id,
        )
        richiesta.stato = 'Proposta inviata'
        richiesta.scadenza_gestione = _scadenza_da_form(request.form.get('scadenza'))
        _sostituisci_attivita_azienda(
            richiesta,
            f'Verificare esito proposta · {richiesta.organizzazione}',
            richiesta.scadenza_gestione,
        )
        db.session.commit()
        registra_modifica('proposta_inviata', 'RichiestaAzienda', richiesta.id, {'oggetto': oggetto})
        flash('Proposta inviata e ricontatto programmato.', 'success')
    except Exception:
        flash('La proposta non è partita. Il testo è conservato nel registro email.', 'error')
    return redirect(_url_dettaglio_admin('RichiestaAzienda', richiesta.id))


@app.route('/admin/azienda/<int:id>/crea-corso', methods=['POST'])
@login_required
def crea_corso_da_richiesta_azienda(id):
    if not _csrf_admin_valido():
        abort(400)
    richiesta = db.get_or_404(RichiestaAzienda, id)
    if richiesta.corso_generato_id:
        flash('Questa richiesta è già collegata a un corso.', 'error')
        return redirect(_url_dettaglio_admin('RichiestaAzienda', richiesta.id))
    tipo = request.form.get('tipo', '').strip()
    titolo = request.form.get('titolo', '').strip()
    data_corso = request.form.get('data', '').strip()
    ora = request.form.get('ora', '').strip()
    luogo = request.form.get('luogo', '').strip()
    try:
        durata_ore = float(request.form.get('durata_ore', ''))
        capienza = int(request.form.get('capienza_massima', ''))
        giorno = datetime.strptime(data_corso, '%Y-%m-%d').date()
        datetime.strptime(ora, '%H:%M')
    except (TypeError, ValueError):
        durata_ore, capienza, giorno = 0, 0, None
    if tipo not in CORSI_ADMIN_TIPI or not titolo or len(titolo) > 200:
        flash('Seleziona una tipologia e inserisci un titolo valido.', 'error')
        return redirect(_url_dettaglio_admin('RichiestaAzienda', richiesta.id))
    if giorno is None or giorno < local_today() or not 0.5 <= durata_ore <= 12 or not 1 <= capienza <= 500 or not luogo:
        flash('Controlla data, ora, durata, capienza e luogo del corso.', 'error')
        return redirect(_url_dettaglio_admin('RichiestaAzienda', richiesta.id))
    corso = Corso(
        titolo=titolo,
        tipo=tipo,
        descrizione=f'Edizione riservata a {richiesta.organizzazione}.',
        data=data_corso,
        ora=ora,
        luogo=luogo,
        durata_ore=durata_ore,
        capienza_massima=capienza,
        stato='Chiuso',
    )
    db.session.add(corso)
    db.session.flush()
    richiesta.corso_generato_id = corso.id
    richiesta.stato = 'Confermata'
    richiesta.scadenza_gestione = None
    _sostituisci_attivita_azienda(richiesta)
    db.session.commit()
    calendar_ok = crea_o_aggiorna_evento_calendario_corso(corso)
    registra_modifica('conversione_in_corso', 'RichiestaAzienda', richiesta.id, {'corso_id': corso.id})
    flash(
        'Corso riservato creato e collegato.' if calendar_ok else 'Corso riservato creato; Calendar richiede verifica.',
        'success' if calendar_ok else 'error',
    )
    return redirect(_url_dettaglio_admin('Corso', corso.id))


@app.route('/admin/appuntamento/aggiungi', methods=['POST'])
@login_required
def aggiungi_appuntamento_admin():
    if not _csrf_admin_valido():
        abort(400)
    risposta_json = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

    def errore_modulo(messaggio, status=422, richiede_conferma=False):
        if risposta_json:
            return jsonify({
                'ok': False,
                'message': messaggio,
                'requires_missing_contacts_confirmation': richiede_conferma,
            }), status
        flash(messaggio, 'error')
        return redirect(url_for('admin') + '#admin-agenda')

    persona = db.session.get(PersonaCorso, request.form.get('persona_id', type=int)) if request.form.get('persona_id') else None
    nome = request.form.get('nome', '').strip() or (persona.nome if persona else '')
    telefono = request.form.get('telefono', '').strip() or (persona.telefono if persona else '')
    email = request.form.get('email', '').strip() or (persona.email if persona else '')
    servizio = request.form.get('servizio', '').strip()
    data_str = request.form.get('data', '').strip()
    ora = request.form.get('ora', '').strip()
    if not ora:
        ora_ore = request.form.get('ora_ore', '').strip()
        ora_minuti = request.form.get('ora_minuti', '').strip()
        if re.fullmatch(r'([01]\d|2[0-3])', ora_ore) and re.fullmatch(r'[0-5]\d', ora_minuti):
            ora = f'{ora_ore}:{ora_minuti}'
    durata = parse_appointment_duration(request.form.get('duration_minutes'))
    if not nome or not servizio or not data_str or not ora or durata is None:
        return errore_modulo('Completa nome, prestazione, data, ora e durata con valori validi.')
    try:
        _intervallo_locale(data_str, ora, durata)
    except (TypeError, ValueError):
        return errore_modulo('Inserisci una data e un orario validi.')
    if telefono and not _telefono_valido(telefono):
        return errore_modulo('Il telefono inserito non è valido: correggilo oppure lascialo vuoto.')
    if email and not _email_valida(email):
        return errore_modulo('L’indirizzo email inserito non è valido: correggilo oppure lascialo vuoto.')

    contatti_mancanti = [
        etichetta
        for etichetta, valore in [('telefono', telefono), ('email', email)]
        if not valore
    ]
    if contatti_mancanti and request.form.get('confirm_missing_contacts') != '1':
        elenco = ' e '.join(contatti_mancanti)
        return errore_modulo(
            f'Mancano {elenco}. Conferma se vuoi creare comunque l’appuntamento.',
            status=409,
            richiede_conferma=True,
        )
    if slot_occupato_db(data_str, ora, durata) or intervallo_occupato_da_calendario(data_str, ora, durata):
        return errore_modulo('L’intervallo scelto è occupato. Verifica agenda e Calendar.', status=409)
    appuntamento = Appuntamento(
        nome=nome,
        telefono=telefono,
        email=email,
        servizio=servizio,
        data=data_str,
        ora=ora,
        duration_minutes=durata,
        note=request.form.get('note', '').strip(),
        consenso_privacy=_checkbox_checked('consenso_privacy'),
        stato='In attesa',
        scadenza_gestione=_scadenza_da_form(request.form.get('scadenza_gestione')),
        creato_da_admin=True,
        sincronizzazione='non_collegato',
    )
    db.session.add(appuntamento)
    db.session.flush()
    if persona:
        db.session.add(CollegamentoPersona(
            persona=persona,
            entita_tipo='Appuntamento',
            entita_id=appuntamento.id,
        ))
        _sync_patient_privacy_consent(persona, 'Appuntamento', appuntamento)
    db.session.commit()
    registra_modifica(
        'creazione_admin',
        'Appuntamento',
        appuntamento.id,
        {'contatti_mancanti': contatti_mancanti} if contatti_mancanti else None,
    )
    flash('Appuntamento creato in attesa di conferma.', 'success')
    destinazione = _url_dettaglio_admin('Appuntamento', appuntamento.id)
    if risposta_json:
        return jsonify({'ok': True, 'redirect': destinazione})
    return redirect(destinazione)


@app.route('/admin/blocco/aggiungi', methods=['POST'])
@login_required
def aggiungi_blocco_admin():
    if not _csrf_admin_valido():
        abort(400)
    durata = parse_appointment_duration(request.form.get('durata_minuti'))
    blocco = BloccoAgenda(
        titolo=request.form.get('titolo', '').strip() or 'Pausa studio',
        data=request.form.get('data', '').strip(),
        ora=request.form.get('ora', '').strip(),
        durata_minuti=durata or 30,
        note=request.form.get('note', '').strip(),
    )
    try:
        _intervallo_locale(blocco.data, blocco.ora, blocco.durata_minuti)
    except (TypeError, ValueError):
        flash('Inserisci data, ora e durata valide.', 'error')
        return redirect(url_for('admin') + '#admin-agenda')
    db.session.add(blocco)
    db.session.commit()
    registra_modifica('creazione', 'BloccoAgenda', blocco.id)
    sincronizzato = crea_o_aggiorna_evento_calendario_blocco(blocco)
    flash('Blocco aggiunto all’agenda.' if sincronizzato else 'Blocco salvato; sincronizzazione Calendar da verificare.', 'success' if sincronizzato else 'error')
    return redirect(url_for('admin', data=blocco.data) + '#admin-agenda')


@app.route('/admin/blocco/<int:id>/archivia', methods=['POST'])
@login_required
def archivia_blocco_admin(id):
    if not _csrf_admin_valido():
        abort(400)
    blocco = db.get_or_404(BloccoAgenda, id)
    blocco.archiviato_il = utc_now()
    db.session.commit()
    elimina_evento_calendario_generico(blocco, 'BloccoAgenda')
    registra_modifica('archiviazione', 'BloccoAgenda', blocco.id)
    flash('Blocco archiviato.', 'success')
    return redirect(url_for('admin') + '#admin-agenda')


@app.route('/admin/attivita/aggiungi', methods=['POST'])
@login_required
def aggiungi_attivita_admin():
    if not _csrf_admin_valido():
        abort(400)
    titolo = request.form.get('titolo', '').strip()
    if not titolo:
        flash('Inserisci il titolo dell’attività.', 'error')
        return redirect(url_for('admin') + '#admin-attivita')
    attivita = AttivitaAdmin(
        titolo=titolo,
        scadenza=_scadenza_da_form(request.form.get('scadenza')),
        note=request.form.get('note', '').strip(),
    )
    db.session.add(attivita)
    db.session.commit()
    registra_modifica('creazione', 'AttivitaAdmin', attivita.id)
    return redirect(url_for('admin') + '#admin-attivita')


@app.route('/admin/attivita/<int:id>/chiudi', methods=['POST'])
@login_required
def chiudi_attivita_admin(id):
    if not _csrf_admin_valido():
        abort(400)
    attivita = db.get_or_404(AttivitaAdmin, id)
    attivita.stato = 'Chiusa'
    db.session.commit()
    registra_modifica('chiusura', 'AttivitaAdmin', attivita.id)
    return redirect(url_for('admin') + '#admin-attivita')


@app.route('/admin/errore/<int:id>/risolvi', methods=['POST'])
@login_required
def risolvi_errore_admin(id):
    if not _csrf_admin_valido():
        abort(400)
    evento = db.get_or_404(RegistroEvento, id)
    entita = _entita_admin(evento.entita_tipo, evento.entita_id)
    if (
        evento.categoria == 'riconciliazione_calendar'
        and entita is not None
        and getattr(entita, 'sincronizzazione', None) in {
            'difforme', 'eliminato_esternamente'
        }
    ):
        flash(
            'Il conflitto Calendar richiede una decisione sulla pratica e non può essere segnato come risolto.',
            'error',
        )
        return redirect(_url_dettaglio_admin(evento.entita_tipo, evento.entita_id))
    nota = request.form.get('nota_risoluzione', '').strip()
    if not nota:
        flash('La nota di risoluzione è obbligatoria.', 'error')
        return redirect(url_for('admin') + '#admin-errori')
    evento.risolto_il = utc_now()
    evento.nota_risoluzione = nota
    db.session.commit()
    registra_modifica('risoluzione_errore', 'RegistroEvento', evento.id)
    return redirect(url_for('admin') + '#admin-errori')


def _sincronizza_entita_admin(tipo, entita):
    return _sincronizza_entita_calendar(tipo, entita)


@app.route('/admin/calendar/riconcilia', methods=['POST'])
@login_required
def riconcilia_calendario_admin():
    if not _csrf_admin_valido():
        abort(400)
    risultato = riconcilia_calendario()
    _segna_riconciliazione_admin_fresca()
    if risultato['errore']:
        flash(risultato['errore'], 'error')
    else:
        flash(f"Controllati {risultato['controllati']} eventi: {risultato['difformi']} difformi, {risultato['mancanti']} mancanti.", 'success')
    return redirect(url_for('admin') + '#admin-errori')


@app.route('/admin/calendar/sincronizza', methods=['POST'])
@login_required
def sincronizza_selezionati_admin():
    if not _csrf_admin_valido():
        abort(400)
    selezionati = request.form.getlist('elementi')
    riusciti = 0
    for valore in selezionati:
        try:
            tipo, id_str = valore.split(':', 1)
            entita = _entita_admin(tipo, int(id_str))
        except (ValueError, TypeError):
            continue
        if (
            entita
            and getattr(entita, 'sincronizzazione', None) not in {
                'difforme', 'eliminato_esternamente'
            }
            and _sincronizza_entita_admin(tipo, entita)
        ):
            riusciti += 1
            registra_modifica('forza_sincronizzazione', tipo, entita.id)
    flash(f'Sincronizzati {riusciti} elementi su {len(selezionati)} selezionati.', 'success' if riusciti == len(selezionati) else 'error')
    return redirect(url_for('admin') + '#admin-errori')


@app.route('/admin/calendar/forza/<tipo>/<int:entita_id>', methods=['POST'])
@login_required
def forza_calendar_admin(tipo, entita_id):
    if not _csrf_admin_valido():
        abort(400)
    entita = _entita_admin(tipo, entita_id)
    if entita is None:
        abort(404)
    if entita.sincronizzazione == 'eliminato_esternamente':
        riuscito = _ripristina_evento_calendar(tipo, entita)
        messaggio = (
            'Evento ripristinato su Calendar senza inviare nuove comunicazioni.'
            if riuscito
            else 'Ripristino Calendar non riuscito; il dato locale resta invariato e verrà ritentato.'
        )
    else:
        riuscito = _sincronizza_entita_admin(tipo, entita)
        if riuscito:
            _chiudi_anomalie_sync(
                tipo,
                entita_id,
                'Dati del sito confermati e riscritti su Calendar.',
            )
            db.session.commit()
        registra_modifica('sovrascrittura_calendar', tipo, entita_id, {'esito': riuscito})
        messaggio = 'Dati del sito riscritti su Calendar.' if riuscito else 'Scrittura Calendar fallita.'
    flash(messaggio, 'success' if riuscito else 'error')
    return redirect(_url_dettaglio_admin(tipo, entita_id))


def _ripristina_evento_calendar(tipo, entita):
    precedente_google_event_id = entita.google_event_id
    entita.google_event_id = None
    entita.sincronizzazione = 'da_sincronizzare'
    if hasattr(entita, 'difformita_calendario'):
        entita.difformita_calendario = None
    db.session.commit()
    riuscito = _sincronizza_entita_admin(tipo, entita)
    if riuscito:
        _chiudi_anomalie_sync(
            tipo,
            entita.id,
            'Evento eliminato esternamente e ripristinato su Calendar.',
        )
        db.session.commit()
    registra_modifica(
        'ripristino_calendar',
        tipo,
        entita.id,
        {
            'esito': riuscito,
            'google_event_id_precedente': precedente_google_event_id,
            'google_event_id_nuovo': entita.google_event_id,
        },
    )
    return riuscito


def _evento_calendar_collegato(entita):
    calendar_id = app.config.get('GOOGLE_CALENDAR_ID')
    servizio = _ottieni_servizio_calendario()
    if not calendar_id or servizio is None or not entita.google_event_id:
        raise RuntimeError('Google Calendar non è disponibile.')
    return _esegui_richiesta_calendario(
        servizio.events().get(
            calendarId=calendar_id,
            eventId=entita.google_event_id,
        ),
        ignora_assenza_evento=True,
    )


@app.route('/admin/calendar/accetta/<tipo>/<int:entita_id>', methods=['POST'])
@login_required
def accetta_calendar_admin(tipo, entita_id):
    if not _csrf_admin_valido() or tipo not in {'Appuntamento', 'CallSonno'}:
        abort(400)
    entita = _entita_admin(tipo, entita_id)
    if entita is None:
        abort(404)
    if entita.sincronizzazione != 'difforme':
        flash('La pratica non presenta più una modifica Calendar da accettare.', 'error')
        return redirect(_url_dettaglio_admin(tipo, entita_id))

    try:
        remoto = _evento_calendar_collegato(entita)
    except Exception as errore:
        flash(f'Calendar non disponibile: {type(errore).__name__}. Il dato locale non è stato modificato.', 'error')
        return redirect(_url_dettaglio_admin(tipo, entita_id))
    if not isinstance(remoto, dict):
        flash('Calendar ha restituito una risposta non valida. Il dato locale non è stato modificato.', 'error')
        return redirect(_url_dettaglio_admin(tipo, entita_id))
    if remoto.get('status') == 'cancelled':
        _segna_evento_eliminato_esternamente(tipo, entita)
        flash('L’evento risulta eliminato: scegli se ripristinarlo o annullare la pratica.', 'error')
        return redirect(_url_dettaglio_admin(tipo, entita_id))

    start = remoto.get('start') or {}
    end = remoto.get('end') or {}
    if not start.get('dateTime') or not end.get('dateTime'):
        flash('Un evento senza orario preciso non può essere applicato automaticamente alla pratica.', 'error')
        return redirect(_url_dettaglio_admin(tipo, entita_id))
    intervallo = _intervallo_da_evento_google(remoto)
    if not intervallo:
        flash('Calendar non ha restituito un intervallo valido.', 'error')
        return redirect(_url_dettaglio_admin(tipo, entita_id))
    inizio, fine, _ = intervallo
    durata = int((fine - inizio).total_seconds() // 60)
    if inizio.second or fine.second or durata <= 0 or durata > 480:
        flash('L’intervallo Calendar non è compatibile con una pratica del sito.', 'error')
        return redirect(_url_dettaglio_admin(tipo, entita_id))

    nuova_data = inizio.date().isoformat()
    nuova_ora = inizio.strftime('%H:%M')
    prima = {
        'data': entita.data,
        'ora': entita.ora,
        'durata_minuti': (
            entita.duration_minutes if tipo == 'Appuntamento' else BLOCCO_CALL_SONNO_MINUTI
        ),
    }
    if tipo == 'Appuntamento':
        valido = (
            inizio.date() >= local_today()
            and is_appointment_interval_bookable(nuova_data, nuova_ora, durata)
        )
        occupato = valido and (
            slot_occupato_db(
                nuova_data,
                nuova_ora,
                durata,
                ignore_appuntamento_id=entita.id,
            )
            or intervallo_occupato_da_calendario(
                nuova_data,
                nuova_ora,
                durata,
                ignore_google_event_id=entita.google_event_id,
            )
        )
    else:
        valido = (
            durata == BLOCCO_CALL_SONNO_MINUTI
            and inizio.date() >= local_today()
            and _giorno_lavorativo_call(inizio.date())
            and nuova_ora in ORARI_CALL_SONNO
        )
        occupato = valido and (
            slot_occupato_db(
                nuova_data,
                nuova_ora,
                durata,
                ignore_call_id=entita.id,
            )
            or intervallo_occupato_da_calendario(
                nuova_data,
                nuova_ora,
                durata,
                ignore_google_event_id=entita.google_event_id,
            )
        )
    if not valido or occupato:
        flash('Il nuovo intervallo non rispetta disponibilità o regole operative; il dato locale non è stato modificato.', 'error')
        return redirect(_url_dettaglio_admin(tipo, entita_id))

    dopo = {'data': nuova_data, 'ora': nuova_ora, 'durata_minuti': durata}
    if prima == dopo:
        flash('Calendar non contiene una modifica di data, ora o durata applicabile al sito.', 'error')
        return redirect(_url_dettaglio_admin(tipo, entita_id))
    entita.data = nuova_data
    entita.ora = nuova_ora
    if tipo == 'Appuntamento':
        entita.duration_minutes = durata
    db.session.commit()

    calendar_ok = _sincronizza_entita_admin(tipo, entita)
    email_ok = (
        invia_email_spostamento(entita)
        if tipo == 'Appuntamento'
        else invia_email_conferma_call_sonno(entita, modificata=True)
    )
    _chiudi_anomalie_sync(
        tipo,
        entita.id,
        'Data e orario modificati su Calendar accettati esplicitamente nell’admin.',
    )
    db.session.commit()
    registra_modifica(
        'accettazione_modifica_calendar',
        tipo,
        entita.id,
        {'prima': prima, 'dopo': dopo, 'email_inviata': email_ok, 'calendar_ok': calendar_ok},
    )
    if calendar_ok and email_ok:
        flash('Modifica Calendar applicata al sito e comunicata al destinatario.', 'success')
    elif not email_ok:
        flash('Modifica applicata, ma l’email di spostamento non è partita. Controlla il registro eventi.', 'error')
    else:
        flash('Modifica applicata; il riallineamento Calendar verrà ritentato.', 'error')
    return redirect(_url_dettaglio_admin(tipo, entita_id))


@app.route('/admin/calendar/annulla/<tipo>/<int:entita_id>', methods=['POST'])
@login_required
def annulla_da_conflitto_calendar_admin(tipo, entita_id):
    if not _csrf_admin_valido() or tipo not in {'Appuntamento', 'CallSonno'}:
        abort(400)
    entita = _entita_admin(tipo, entita_id)
    if entita is None:
        abort(404)
    if entita.sincronizzazione != 'eliminato_esternamente':
        flash('La pratica non presenta più un evento eliminato da gestire.', 'error')
        return redirect(_url_dettaglio_admin(tipo, entita_id))

    if tipo == 'Appuntamento':
        entita.stato = 'Annullato'
        db.session.commit()
        email_ok = invia_email_annullamento(entita)
        calendar_ok = elimina_evento_calendario(entita)
    else:
        entita.stato = 'Annullata'
        db.session.commit()
        email_ok = invia_email_annullamento_call_sonno(entita)
        calendar_ok = elimina_evento_calendario_call_sonno(entita)
    if calendar_ok:
        entita.sincronizzazione = 'non_collegato'
    if hasattr(entita, 'difformita_calendario'):
        entita.difformita_calendario = None
    _chiudi_anomalie_sync(
        tipo,
        entita.id,
        'Evento eliminato esternamente: pratica annullata con il normale flusso amministrativo.',
    )
    db.session.commit()
    registra_modifica(
        'annullamento_da_conflitto_calendar',
        tipo,
        entita.id,
        {'email_inviata': email_ok, 'calendar_ok': calendar_ok},
    )
    if email_ok:
        flash('Pratica annullata e comunicazione inviata.', 'success')
    else:
        flash('Pratica annullata, ma l’email non è partita. Controlla il registro eventi.', 'error')
    return redirect(_url_dettaglio_admin(tipo, entita_id))


@app.route('/admin/calendar/decidi-dopo', methods=['POST'])
@login_required
def rimanda_conflitti_calendar_admin():
    if not _csrf_admin_valido():
        abort(400)
    session['conflitti_calendar_rimandati'] = [
        f"{voce['tipo']}:{voce['id']}"
        for voce in _conflitti_calendar_prioritari()
    ]
    flash('Decisione rimandata: i conflitti Calendar restano aperti e visibili.', 'error')
    return redirect(url_for('admin') + '#conflitti-calendar')


@app.route('/admin/email/<int:id>/reinvia', methods=['POST'])
@login_required
def reinvia_email_admin(id):
    if not _csrf_admin_valido():
        abort(400)
    precedente = db.get_or_404(EmailOperativa, id)
    if precedente.stato != 'fallita':
        abort(400)
    msg = Message(subject=precedente.oggetto, recipients=[precedente.destinatario], body=precedente.corpo)
    try:
        _invia_email_tracciata(msg, precedente.entita_tipo, precedente.entita_id)
        flash('Email reinviata.', 'success')
    except Exception:
        flash('Nuovo invio fallito. Controlla il registro errori.', 'error')
    return redirect(_url_dettaglio_admin(precedente.entita_tipo, precedente.entita_id))


@app.route('/admin/pratica/<tipo>/<int:entita_id>/proponi-slot', methods=['POST'])
@login_required
def proponi_slot_admin(tipo, entita_id):
    if not _csrf_admin_valido() or tipo not in {'Appuntamento', 'CallSonno'}:
        abort(400)
    entita = _entita_admin(tipo, entita_id)
    if entita is None:
        abort(404)
    data_proposta = request.form.get('data_proposta', '').strip()
    ora_proposta = request.form.get('ora_proposta', '').strip()
    durata = parse_appointment_duration(request.form.get('durata_minuti'))
    try:
        _intervallo_locale(data_proposta, ora_proposta, durata)
    except (TypeError, ValueError):
        flash('Data, ora o durata della proposta non valide.', 'error')
        return redirect(_url_dettaglio_admin(tipo, entita_id))
    token = secrets.token_urlsafe(48)
    proposta = PropostaSlot(
        token=token,
        entita_tipo=tipo,
        entita_id=entita_id,
        data_proposta=data_proposta,
        ora_proposta=ora_proposta,
        durata_minuti=durata,
        scade_il=utc_now() + timedelta(hours=48),
    )
    db.session.add(proposta)
    db.session.commit()
    link = public_url(url_for('accetta_proposta_slot', token=token))
    corpo_default = (
        f'Buongiorno {entita.nome},\n\n'
        f'le proponiamo {data_proposta} alle {ora_proposta}. '
        f'Può accettare entro 48 ore da questo link:\n{link}\n\n'
        'Studio infermieristico'
    )
    corpo = request.form.get('corpo_email', '').strip() or corpo_default
    oggetto = request.form.get('oggetto_email', '').strip() or 'Proposta di nuovo orario'
    if request.form.get('conferma_invio') != '1':
        abort(400)
    msg = Message(subject=oggetto, recipients=[entita.email], body=corpo)
    try:
        _invia_email_tracciata(msg, tipo, entita_id)
        flash('Proposta inviata. Lo slot verrà ricontrollato al momento dell’accettazione.', 'success')
    except Exception:
        flash('Proposta salvata, ma l’email non è partita.', 'error')
    registra_modifica('proposta_slot', tipo, entita_id, {'data': data_proposta, 'ora': ora_proposta, 'scade_il': proposta.scade_il.isoformat()})
    return redirect(_url_dettaglio_admin(tipo, entita_id))


@app.route('/proposta-slot/<token>', methods=['GET', 'POST'])
@limiter.limit('10 per hour', methods=['POST'])
def accetta_proposta_slot(token):
    proposta = PropostaSlot.query.filter_by(token=token).first_or_404()
    entita = _entita_admin(proposta.entita_tipo, proposta.entita_id)
    valida = bool(entita and proposta.stato == 'Inviata' and proposta.scade_il > utc_now())
    if request.method == 'POST' and valida:
        ignore_call = entita.id if proposta.entita_tipo == 'CallSonno' else None
        ignore_appuntamento = entita.id if proposta.entita_tipo == 'Appuntamento' else None
        occupato = slot_occupato_db(
            proposta.data_proposta,
            proposta.ora_proposta,
            proposta.durata_minuti,
            ignore_call_id=ignore_call,
            ignore_appuntamento_id=ignore_appuntamento,
        ) or intervallo_occupato_da_calendario(
            proposta.data_proposta,
            proposta.ora_proposta,
            proposta.durata_minuti,
            ignore_google_event_id=entita.google_event_id,
        )
        if occupato:
            proposta.stato = 'Non disponibile'
            db.session.commit()
            return render_template('accetta_proposta_slot.html', proposta=proposta, entita=entita, valida=False, occupato=True)
        entita.data = proposta.data_proposta
        entita.ora = proposta.ora_proposta
        if proposta.entita_tipo == 'Appuntamento':
            entita.duration_minutes = proposta.durata_minuti
            entita.stato = 'Confermato'
        else:
            entita.stato = 'Confermata'
        proposta.stato = 'Accettata'
        proposta.accettata_il = utc_now()
        db.session.commit()
        _sincronizza_entita_admin(proposta.entita_tipo, entita)
        if proposta.entita_tipo == 'Appuntamento':
            invia_email_conferma(entita)
        else:
            invia_email_conferma_call_sonno(entita)
        return render_template('accetta_proposta_slot.html', proposta=proposta, entita=entita, valida=False, accettata=True)
    return render_template('accetta_proposta_slot.html', proposta=proposta, entita=entita, valida=valida)


def _segnala_prossimo_lista_attesa(corso):
    candidato = IscrizioneCorso.query.filter_by(
        corso_id=corso.id,
        stato='Lista attesa',
    ).order_by(IscrizioneCorso.creato_il).first()
    if not candidato or not _corso_accetta_prenotazione_online(corso, candidato.posti_richiesti or 1):
        return None
    scadenza = prossima_scadenza_lavorativa()
    candidato.scadenza_gestione = scadenza
    attivita_esistente = AttivitaAdmin.query.filter_by(
        stato='Aperta',
        entita_tipo='IscrizioneCorso',
        entita_id=candidato.id,
    ).first()
    if not attivita_esistente:
        db.session.add(AttivitaAdmin(
            titolo=f'Contattare {candidato.nome}: posto disponibile in {corso.titolo}',
            scadenza=scadenza,
            entita_tipo='IscrizioneCorso',
            entita_id=candidato.id,
            note='Contatto telefonico: non inviare email alle persone in lista d’attesa.',
        ))
    db.session.commit()
    return candidato


@app.route('/lista-attesa/<token>', methods=['GET', 'POST'])
@limiter.limit('10 per hour', methods=['POST'])
def accetta_invito_lista_attesa(token):
    iscrizione = IscrizioneCorso.query.filter_by(token_lista_attesa=token).first_or_404()
    corso = iscrizione.corso
    valida = bool(
        corso
        and iscrizione.stato == 'Invitato'
        and iscrizione.scadenza_invito_lista_attesa
        and iscrizione.scadenza_invito_lista_attesa > utc_now()
        and _corso_accetta_prenotazione_online(corso, iscrizione.posti_richiesti or 1)
    )
    if request.method == 'POST' and valida:
        iscrizione.stato = 'Nuova'
        iscrizione.posti = iscrizione.posti_richiesti or 1
        iscrizione.scadenza_gestione = prossima_scadenza_lavorativa()
        db.session.commit()
        invia_email_alert_nuova_iscrizione(iscrizione)
        return render_template('accetta_lista_attesa.html', iscrizione=iscrizione, corso=corso, valida=False, accettata=True)
    return render_template('accetta_lista_attesa.html', iscrizione=iscrizione, corso=corso, valida=valida)


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
    email_inviata = invia_email_conferma_call_sonno(call)
    calendar_aggiornato = crea_o_aggiorna_evento_calendario_call_sonno(call)
    if not email_inviata and not calendar_aggiornato:
        flash(
            'Call confermata, ma email e Calendar non sono stati aggiornati. '
            'Controlla il registro eventi.',
            'error',
        )
    elif not calendar_aggiornato:
        flash('Call confermata, ma Calendar non è stato aggiornato. Controlla il registro eventi.', 'error')
    elif not email_inviata:
        flash(
            'Call confermata e Calendar aggiornato, ma l’email non è partita. '
            'Controlla il registro eventi.',
            'error',
        )
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
    email_inviata = invia_email_annullamento_call_sonno(call)
    calendar_aggiornato = elimina_evento_calendario_call_sonno(call)
    if not email_inviata and not calendar_aggiornato:
        flash(
            'Call annullata, ma email e Calendar non sono stati aggiornati. '
            'Controlla il registro eventi.',
            'error',
        )
    elif not calendar_aggiornato:
        flash('Call annullata, ma il blocco Calendar non è stato rimosso.', 'error')
    elif not email_inviata:
        flash(
            'Call annullata e Calendar aggiornato, ma l’email non è partita. '
            'Controlla il registro eventi.',
            'error',
        )
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
            giorno is not None and giorno >= local_today() and _giorno_lavorativo_call(giorno)
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
        email_inviata = invia_email_conferma_call_sonno(call, modificata=True)
        calendar_aggiornato = crea_o_aggiorna_evento_calendario_call_sonno(call)
        if not email_inviata and not calendar_aggiornato:
            flash(
                'Nuovo orario salvato, ma email e Calendar non sono stati aggiornati. '
                'Controlla il registro eventi.',
                'error',
            )
        elif not calendar_aggiornato:
            flash('Nuovo orario salvato, ma Calendar non è stato aggiornato.', 'error')
        elif not email_inviata:
            flash(
                'Nuovo orario salvato e Calendar aggiornato, ma l’email non è partita. '
                'Controlla il registro eventi.',
                'error',
            )
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
    call.questionario_inviato_il = utc_now()
    db.session.commit()
    if invia_email_questionario_sonno(call):
        flash('Questionario privato inviato.', 'success')
    else:
        flash('Il link è stato creato, ma l’email non è partita. Controlla il registro eventi.', 'error')
    return redirect(url_for('admin') + '#admin-call-sonno')


@app.route('/admin/aggiorna/<int:id>/<stato>', methods=['POST'])
@login_required
def aggiorna_stato(id, stato):
    if stato not in STATI_APPUNTAMENTO_ADMIN:
        abort(400)
    # Il token resta riutilizzabile nella stessa pagina admin, dove sono
    # disponibili più azioni POST prima del successivo caricamento.
    token = request.form.get('_csrf_token')
    if not token or token != session.get('_csrf_token'):
        flash('Richiesta non valida. Riprova.', 'error')
        return redirect(url_for('admin', filtro=request.form.get('filtro', 'in_attesa')))
    appuntamento = db.get_or_404(Appuntamento, id)

    if stato == 'Confermato':
        duration_minutes = parse_appointment_duration(
            request.form.get('duration_minutes')
        )
        if duration_minutes is None:
            flash(
                'Indica una durata valida, da 1 a 480 minuti.',
                'error',
            )
            return redirect(url_for('admin', filtro=request.form.get('filtro', 'in_attesa')))
        if not is_appointment_interval_bookable(
            appuntamento.data,
            appuntamento.ora,
            duration_minutes,
        ):
            flash(
                'La durata scelta supera l’orario di apertura dello studio.',
                'error',
            )
            return redirect(url_for('admin', filtro=request.form.get('filtro', 'in_attesa')))
        unavailable_in_database = slot_occupato_db(
            appuntamento.data,
            appuntamento.ora,
            duration_minutes,
            ignore_appuntamento_id=appuntamento.id,
        )
        unavailable_in_calendar = intervallo_occupato_da_calendario(
            appuntamento.data,
            appuntamento.ora,
            duration_minutes,
            ignore_google_event_id=appuntamento.google_event_id,
        )
        if unavailable_in_database or unavailable_in_calendar:
            flash(
                'La durata scelta si sovrappone a un altro impegno. '
                'Modifica l’appuntamento prima di confermarlo.',
                'error',
            )
            return redirect(url_for('admin', filtro=request.form.get('filtro', 'in_attesa')))
        appuntamento.duration_minutes = duration_minutes

    patient = None
    patient_created = False
    appuntamento.stato = stato
    if stato == 'Confermato':
        patient, patient_created = _ensure_patient_for_appointment(appuntamento)
    db.session.commit()
    registra_modifica('cambio_stato', 'Appuntamento', appuntamento.id, {'stato': stato})
    if patient:
        registra_modifica(
            'collegamento_paziente_automatico',
            'Appuntamento',
            appuntamento.id,
            {'persona_id': patient.id, 'nuova_anagrafica': patient_created},
        )
    if patient_created:
        registra_modifica(
            'creazione_anagrafica_da_conferma',
            'PersonaCorso',
            patient.id,
            {'tipo_pratica': 'Appuntamento', 'pratica_id': appuntamento.id},
        )
    if stato == 'Confermato':
        email_inviata = invia_email_conferma(appuntamento)
        calendar_aggiornato = crea_o_aggiorna_evento_calendario(appuntamento)
        if not email_inviata and not calendar_aggiornato:
            flash(
                'Appuntamento confermato, ma email e Google Calendar non sono stati aggiornati. '
                'Controlla il registro eventi.',
                'error',
            )
        elif not calendar_aggiornato:
            flash('Appuntamento confermato, ma Google Calendar non è stato aggiornato. Controlla il registro eventi.', 'error')
        elif not email_inviata:
            flash(
                'Appuntamento confermato e Google Calendar aggiornato, ma l’email non è partita. '
                'Controlla il registro eventi.',
                'error',
            )
    elif stato == 'Annullato':
        email_inviata = invia_email_annullamento(appuntamento)
        calendar_aggiornato = elimina_evento_calendario(appuntamento)
        if not email_inviata and not calendar_aggiornato:
            flash(
                'Appuntamento annullato, ma email e Google Calendar non sono stati aggiornati. '
                'Controlla il registro eventi.',
                'error',
            )
        elif not calendar_aggiornato:
            flash('Appuntamento annullato, ma Google Calendar non è stato aggiornato. Controlla il registro eventi.', 'error')
        elif not email_inviata:
            flash(
                'Appuntamento annullato e Google Calendar aggiornato, ma l’email non è partita. '
                'Controlla il registro eventi.',
                'error',
            )
    return redirect(url_for('admin', filtro=request.form.get('filtro', 'in_attesa')))


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
        duration_minutes = parse_appointment_duration(
            request.form.get('duration_minutes')
        )
        oggi = local_today().strftime('%Y-%m-%d')

        if not nuova_data or not nuova_ora or duration_minutes is None:
            flash(
                'Data, ora e una durata valida da 1 a 480 minuti sono obbligatorie.',
                'error',
            )
            return render_template('modifica_appuntamento.html', a=appuntamento)
        if nuova_data < oggi:
            flash('Non puoi spostare un appuntamento a una data nel passato.', 'error')
            return render_template('modifica_appuntamento.html', a=appuntamento)
        if not is_appointment_interval_bookable(
            nuova_data,
            nuova_ora,
            duration_minutes,
        ):
            flash(
                'Lo studio è chiuso durante l’intervallo selezionato. '
                'Scegli un altro orario o una durata diversa.',
                'error',
            )
            return render_template('modifica_appuntamento.html', a=appuntamento)

        gia_occupato_db = slot_occupato_db(
            nuova_data,
            nuova_ora,
            duration_minutes,
            ignore_appuntamento_id=appuntamento.id,
        )
        gia_occupato_calendario = intervallo_occupato_da_calendario(
            nuova_data,
            nuova_ora,
            duration_minutes,
            ignore_google_event_id=appuntamento.google_event_id,
        )
        if gia_occupato_db or gia_occupato_calendario:
            flash(
                'L’intervallo selezionato non è più disponibile. '
                'Scegli un altro orario o una durata diversa.',
                'error',
            )
            return render_template('modifica_appuntamento.html', a=appuntamento)

        was_pending = appuntamento.stato == 'In attesa'
        appuntamento.data = nuova_data
        appuntamento.ora = nuova_ora
        appuntamento.duration_minutes = duration_minutes
        appuntamento.stato = 'Confermato'
        db.session.commit()
        if was_pending:
            email_inviata = invia_email_conferma(appuntamento)
        else:
            email_inviata = invia_email_spostamento(appuntamento)
        calendar_aggiornato = crea_o_aggiorna_evento_calendario(appuntamento)
        if not email_inviata and not calendar_aggiornato:
            flash(
                'Appuntamento modificato, ma email e Google Calendar non sono stati aggiornati. '
                'Controlla il registro eventi.',
                'error',
            )
        elif not calendar_aggiornato:
            flash('Appuntamento modificato, ma Google Calendar non è stato aggiornato. Controlla il registro eventi.', 'error')
        elif not email_inviata:
            flash(
                'Appuntamento modificato e Google Calendar aggiornato, ma l’email non è partita. '
                'Controlla il registro eventi.',
                'error',
            )
        return redirect(url_for('admin', filtro='in_attesa'))
    return render_template('modifica_appuntamento.html', a=appuntamento)


@app.route('/admin/corso/aggiungi', methods=['POST'])
@login_required
def aggiungi_corso():
    # Protezione CSRF
    token = session.pop('_csrf_token', None)
    if not token or token != request.form.get('_csrf_token'):
        flash('Richiesta non valida. Riprova.', 'error')
        return redirect(url_for('admin') + '#admin-nuovo-corso')
    tipo_corso = request.form.get('tipo', '').strip()
    if tipo_corso not in CORSI_ADMIN_TIPI:
        flash('Seleziona un tipo di corso valido.', 'error')
        return redirect(url_for('admin') + '#admin-nuovo-corso')
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
    return redirect(url_for('admin') + '#admin-corsi')


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
    sincronizzato = crea_o_aggiorna_evento_calendario_incontro(incontro)
    registra_modifica('creazione', 'IncontroAccompagnamento', incontro.id)
    flash('Incontro aggiunto e sincronizzato.' if sincronizzato else 'Incontro aggiunto; sincronizzazione Calendar da verificare.', 'success' if sincronizzato else 'error')
    return redirect(url_for('admin') + '#admin-percorsi-accompagnamento')


@app.route('/admin/incontro-accompagnamento/<int:id>/modifica', methods=['POST'])
@login_required
def modifica_incontro_accompagnamento(id):
    if not _csrf_admin_valido():
        abort(400)
    incontro = db.get_or_404(IncontroAccompagnamento, id)
    destinatari = [i for i in _iscrizioni_percorso(incontro.percorso) if i.email]
    if destinatari and request.form.get('conferma_notifiche') != '1':
        flash(f'Conferma l’invio dell’aggiornamento ai {len(destinatari)} partecipanti.', 'error')
        return redirect(url_for('admin') + '#admin-percorsi-accompagnamento')
    precedente = {'data': incontro.data, 'ora': incontro.ora, 'tema': incontro.tema, 'professionista': incontro.professionista}
    incontro.data = request.form.get('data', '').strip()
    incontro.ora = request.form.get('ora', '').strip()
    incontro.tema = request.form.get('tema', '').strip()
    incontro.professionista = request.form.get('professionista', '').strip()
    incontro.note = request.form.get('note', '').strip()
    if not incontro.data or not incontro.tema or not incontro.professionista:
        db.session.rollback()
        flash('Data, tema e professionista sono obbligatori.', 'error')
        return redirect(url_for('admin') + '#admin-percorsi-accompagnamento')
    db.session.commit()
    crea_o_aggiorna_evento_calendario_incontro(incontro)
    registra_modifica('modifica', 'IncontroAccompagnamento', incontro.id, {'prima': precedente, 'dopo': {'data': incontro.data, 'ora': incontro.ora, 'tema': incontro.tema, 'professionista': incontro.professionista}})
    if destinatari:
        for iscrizione in destinatari:
            msg = Message(
                subject=f'Aggiornamento incontro · {incontro.percorso.titolo}',
                recipients=[iscrizione.email],
                body=(f'Buongiorno {iscrizione.nome},\n\nl’incontro {incontro.numero} è stato aggiornato: '
                      f'{incontro.data} alle {incontro.ora or "orario da definire"}, tema “{incontro.tema}”.\n\nStudio infermieristico'),
            )
            try:
                _invia_email_tracciata(msg, 'IscrizioneCorso', iscrizione.id)
            except Exception:
                registra_evento('email', 'errore', 'Aggiornamento incontro non inviato a un partecipante.', 'IscrizioneCorso', iscrizione.id)
    flash('Incontro aggiornato.', 'success')
    return redirect(url_for('admin') + '#admin-percorsi-accompagnamento')


@app.route('/admin/incontro-accompagnamento/<int:id>/archivia', methods=['POST'])
@login_required
def archivia_incontro_accompagnamento(id):
    if not _csrf_admin_valido():
        abort(400)
    incontro = db.get_or_404(IncontroAccompagnamento, id)
    incontro.archiviato_il = utc_now()
    db.session.commit()
    elimina_evento_calendario_generico(incontro, 'IncontroAccompagnamento')
    registra_modifica('archiviazione', 'IncontroAccompagnamento', incontro.id)
    flash('Incontro archiviato; lo storico delle presenze resta conservato.', 'success')
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
    tipo_richiesta = request.form.get('tipo_richiesta', 'iscrizione_effettiva').strip()
    if tipo_richiesta not in TIPI_RICHIESTA_CORSO:
        tipo_richiesta = 'iscrizione_effettiva'
    if tipo_richiesta == 'open_day' and corso.tipo != 'accompagnamento-nascita':
        flash('Il flusso open day è disponibile soltanto per il corso di accompagnamento alla nascita.', 'error')
        return redirect(url_for('admin', corso_id=corso.id) + '#admin-corsi')

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

    stato = request.form.get('stato', 'Confermato').strip()
    if stato not in STATI_ISCRIZIONE_VALIDI:
        stato = 'Confermato'

    partecipazione = request.form.get('partecipazione', '').strip() or 'Inserimento manuale'
    posti = request.form.get('posti', type=int)
    if posti is None or posti < 0:
        posti = _posti_iscrizione_da_partecipazione(partecipazione)
    if tipo_richiesta == 'ricontatto':
        posti = 0

    oltre_limite_online = bool(
        corso.capienza_massima is not None
        and _posti_attivi_corso(corso.id) + posti > corso.capienza_massima + 1
    )
    motivo_superamento = request.form.get('superamento_capienza_motivo', '').strip()
    if oltre_limite_online and (request.form.get('conferma_superamento_capienza') != '1' or not motivo_superamento):
        flash('L’admin può superare il limite online, ma deve confermare l’eccezione e indicarne il motivo.', 'error')
        return redirect(url_for('admin', corso_id=corso.id) + '#admin-corsi')

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
        posti_richiesti=posti,
        scadenza_gestione=prossima_scadenza_lavorativa() if stato in {'Nuova', 'Contattato'} else None,
        superamento_capienza_motivo=motivo_superamento or None,
    )
    db.session.add(iscrizione)
    db.session.flush()
    _sync_patient_privacy_consent(persona, 'IscrizioneCorso', iscrizione)
    db.session.commit()
    if stato == 'Confermato' and tipo_richiesta != 'ricontatto':
        email_inviata = invia_email_conferma_iscrizione_corso(iscrizione)
        if email_inviata is True:
            flash('Iscritto aggiunto, salvato in rubrica ed email di conferma inviata.', 'success')
        elif email_inviata is None:
            flash('Iscritto aggiunto e confermato, ma l’email è mancante: contattalo manualmente.', 'error')
        else:
            flash('Iscritto aggiunto e confermato, ma l’email non è partita. Controlla il registro eventi.', 'error')
    else:
        flash('Iscritto aggiunto al corso e salvato in rubrica.', 'success')
    return redirect(url_for('admin', corso_id=corso.id) + '#admin-corsi')


@app.route('/admin/corso/elimina/<int:id>', methods=['POST'])
@login_required
def elimina_corso(id):
    token = request.form.get('_csrf_token')
    if not token or token != session.get('_csrf_token'):
        flash('Richiesta non valida. Riprova.', 'error')
        return redirect(url_for('admin'))

    corso = db.get_or_404(Corso, id)

    if corso.archiviato_il is not None:
        flash('Edizione già archiviata; nessuna nuova email inviata.', 'success')
        return redirect(url_for('admin') + '#admin-corsi')

    # Salva i dati dell'edizione prima dell'archiviazione.
    etichetta_edizione = _etichetta_data_corso(corso)

    # Recupera i partecipanti che avevano già un posto confermato.
    destinatari = IscrizioneCorso.query.filter(
        IscrizioneCorso.corso_id == corso.id,
        IscrizioneCorso.stato == 'Confermato',
        IscrizioneCorso.archiviata_il.is_(None),
    ).all()

    # L'annullamento del corso deve essere salvato anche se Calendar
    # o l'invio delle email dovessero successivamente fallire.
    corso.archiviato_il = utc_now()
    corso.stato = 'Annullato'
    db.session.commit()

    calendar_ok = elimina_evento_calendario_corso(corso)

    registra_modifica(
        'archiviazione',
        'Corso',
        corso.id,
        {'stato': 'Annullato'}
    )

    # Avvisa tutti i partecipanti con posto già confermato.
    email_inviate = 0
    email_fallite = 0
    email_mancanti = 0

    for iscrizione in destinatari:
        risultato_email = invia_email_annullamento_edizione_corso(
            iscrizione,
            corso,
            etichetta_edizione,
        )

        if risultato_email is True:
            email_inviate += 1
        elif risultato_email is False:
            email_fallite += 1
        else:
            email_mancanti += 1

    if not calendar_ok or email_fallite or email_mancanti:
        problemi = []
        if not calendar_ok:
            problemi.append('Calendar richiede verifica.')
        if email_fallite or email_mancanti:
            problemi.append(
                'Controlla il registro eventi e contatta manualmente chi non ha ricevuto l’avviso.'
            )
        flash(
            f'Edizione archiviata. Email inviate: {email_inviate}; '
            f'email non inviate: {email_fallite}; '
            f'email mancanti: {email_mancanti}. '
            f'{" ".join(problemi)}',
            'error'
        )
    elif destinatari:
        flash(
            f'Edizione archiviata e partecipanti confermati avvisati '
            f'via email ({email_inviate}).',
            'success'
        )
    else:
        flash(
            'Edizione archiviata; non risultano partecipanti confermati da avvisare.',
            'success'
        )

    return redirect(url_for('admin') + '#admin-corsi')


@app.route('/admin/corso/<int:id>/modifica', methods=['POST'])
@login_required
def modifica_corso_admin(id):
    if not _csrf_admin_valido():
        abort(400)
    corso = db.get_or_404(Corso, id)
    precedente = {campo: getattr(corso, campo) for campo in ['titolo', 'data', 'ora', 'luogo', 'durata_ore', 'capienza_massima', 'stato']}
    corso.titolo = request.form.get('titolo', '').strip()
    corso.data = request.form.get('data', '').strip()
    corso.ora = request.form.get('ora', '').strip()
    corso.luogo = request.form.get('luogo', '').strip()
    corso.descrizione = request.form.get('descrizione', '').strip()
    corso.durata_ore = _durata_corso_da_form(request.form.get('durata_ore', ''), corso.tipo)
    capienza = request.form.get('capienza_massima', type=int)
    corso.capienza_massima = capienza if capienza and capienza > 0 else None
    stato = request.form.get('stato', corso.stato)
    corso.stato = stato if stato in STATI_CORSO_VALIDI else corso.stato
    if not corso.titolo or not corso.data:
        db.session.rollback()
        flash('Titolo e data del corso sono obbligatori.', 'error')
        return redirect(url_for('admin') + '#admin-corsi')
    dopo = {campo: getattr(corso, campo) for campo in precedente}
    modifiche_organizzative = any(precedente[campo] != dopo[campo] for campo in ['titolo', 'data', 'ora', 'luogo'])
    destinatari = IscrizioneCorso.query.filter(
        IscrizioneCorso.corso_id == corso.id,
        IscrizioneCorso.stato.notin_(['Annullato', 'Lista attesa', 'Invitato']),
        IscrizioneCorso.email != '',
        IscrizioneCorso.archiviata_il.is_(None),
    ).all()
    invia_aggiornamento = (
        modifiche_organizzative
        and bool(destinatari)
        and request.form.get('conferma_notifiche') == '1'
    )
    db.session.commit()
    calendar_ok = crea_o_aggiorna_evento_calendario_corso(corso)
    registra_modifica('modifica', 'Corso', corso.id, {'prima': precedente, 'dopo': dopo})
    if invia_aggiornamento:
        for iscrizione in destinatari:
            msg = Message(
                subject=f'Aggiornamento · {corso.titolo}',
                recipients=[iscrizione.email],
                body=(
                    f'Buongiorno {iscrizione.nome},\n\n'
                    f'sono stati aggiornati i dettagli dell’edizione di {corso.titolo}.\n\n'
                    f'Data e luogo: {_etichetta_data_corso(corso)}\n\n'
                    'Per chiarimenti o per comunicare una variazione, puoi contattare '
                    'lo studio ai seguenti recapiti:\n\n'
                    f'{_firma_email_studio()}'
                ),
            )
            try:
                _invia_email_tracciata(msg, 'IscrizioneCorso', iscrizione.id)
            except Exception:
                registra_evento('email', 'errore', 'Aggiornamento corso non inviato a un partecipante.', 'IscrizioneCorso', iscrizione.id)
    if modifiche_organizzative and destinatari and not invia_aggiornamento:
        messaggio = 'Corso aggiornato; nessuna email inviata ai partecipanti.'
    else:
        messaggio = 'Corso aggiornato.'
    if not calendar_ok:
        messaggio += ' Sincronizzazione Calendar da verificare.'
    flash(messaggio, 'success' if calendar_ok else 'error')
    return redirect(url_for('admin') + '#admin-corsi')


@app.route('/admin/corso/<int:id>/duplica', methods=['POST'])
@login_required
def duplica_corso_admin(id):
    if not _csrf_admin_valido():
        abort(400)
    origine = db.get_or_404(Corso, id)
    nuova_data = request.form.get('data', '').strip()
    if not nuova_data:
        flash('Indica la data della nuova edizione.', 'error')
        return redirect(url_for('admin') + '#admin-corsi')
    duplicato = Corso(
        titolo=origine.titolo,
        tipo=origine.tipo,
        descrizione=origine.descrizione,
        data=nuova_data,
        ora=request.form.get('ora', '').strip() or origine.ora,
        luogo=origine.luogo,
        durata_ore=origine.durata_ore,
        capienza_massima=origine.capienza_massima,
        stato='Aperto',
    )
    db.session.add(duplicato)
    db.session.commit()
    crea_o_aggiorna_evento_calendario_corso(duplicato)
    registra_modifica('duplicazione', 'Corso', duplicato.id, {'origine_id': origine.id})
    flash('Nuova edizione duplicata senza iscritti.', 'success')
    return redirect(url_for('admin', corso_id=duplicato.id) + '#admin-corsi')


@app.route('/admin/corso/<int:id>/unisci', methods=['POST'])
@login_required
def unisci_corso_admin(id):
    if not _csrf_admin_valido():
        abort(400)
    origine = db.get_or_404(Corso, id)
    destinazione = db.session.get(Corso, request.form.get('corso_destinazione_id', type=int))
    if not destinazione or destinazione.id == origine.id:
        flash('Seleziona un’edizione di destinazione diversa.', 'error')
        return redirect(url_for('admin') + '#admin-corsi')
    iscrizioni = IscrizioneCorso.query.filter_by(corso_id=origine.id).all()
    for iscrizione in iscrizioni:
        iscrizione.corso = destinazione
        iscrizione.corso_tipo = destinazione.tipo or iscrizione.corso_tipo
        iscrizione.corso_titolo = destinazione.titolo
        iscrizione.data_corso = _etichetta_data_corso(destinazione)
    origine.archiviato_il = utc_now()
    origine.stato = 'Annullato'
    db.session.commit()
    elimina_evento_calendario_corso(origine)
    registra_modifica('fusione_edizioni', 'Corso', destinazione.id, {'origine_id': origine.id, 'iscrizioni_spostate': len(iscrizioni)})
    flash(f'Edizioni unite: spostate {len(iscrizioni)} iscrizioni.', 'success')
    return redirect(url_for('admin', corso_id=destinazione.id) + '#admin-corsi')


@app.route('/admin/iscrizione-corso/<int:id>/sposta', methods=['POST'])
@login_required
def sposta_iscrizione_corso_admin(id):
    if not _csrf_admin_valido():
        abort(400)
    iscrizione = db.get_or_404(IscrizioneCorso, id)
    destinazione = db.session.get(Corso, request.form.get('corso_destinazione_id', type=int))
    if not destinazione:
        abort(400)
    origine_id = iscrizione.corso_id
    edizione_precedente = iscrizione.data_corso
    iscrizione.corso = destinazione
    iscrizione.corso_tipo = destinazione.tipo or iscrizione.corso_tipo
    iscrizione.corso_titolo = destinazione.titolo
    iscrizione.data_corso = _etichetta_data_corso(destinazione)
    db.session.commit()
    registra_modifica('spostamento_edizione', 'IscrizioneCorso', iscrizione.id, {'origine_id': origine_id, 'destinazione_id': destinazione.id})
    if origine_id:
        origine = db.session.get(Corso, origine_id)
        if origine:
            _segnala_prossimo_lista_attesa(origine)
    in_lista_attesa = iscrizione.stato in STATI_LISTA_ATTESA
    email_inviata = None if in_lista_attesa else invia_email_spostamento_iscrizione_corso(
        iscrizione,
        edizione_precedente,
    )
    if in_lista_attesa:
        flash('Persona spostata; nessuna email inviata perché è in lista d’attesa. Contattala telefonicamente.', 'success')
    elif email_inviata is True:
        flash('Partecipante spostato; email inviata con la nuova edizione.', 'success')
    elif email_inviata is None:
        flash('Partecipante spostato, ma l’email è mancante: contattalo manualmente.', 'error')
    else:
        flash('Partecipante spostato, ma l’email non è partita. Controlla il registro eventi.', 'error')
    return redirect(_url_dettaglio_admin('IscrizioneCorso', iscrizione.id))


@app.route('/admin/corso/<int:id>/export.csv')
@login_required
def esporta_corso_csv(id):
    corso = db.get_or_404(Corso, id)
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(['nome', 'telefono', 'email', 'codice_fiscale', 'partecipazione', 'posti', 'stato', 'note'])
    for iscrizione in IscrizioneCorso.query.filter_by(corso_id=corso.id).order_by(IscrizioneCorso.nome):
        writer.writerow([iscrizione.nome, iscrizione.telefono, iscrizione.email, iscrizione.codice_fiscale, iscrizione.partecipazione, iscrizione.posti, iscrizione.stato, iscrizione.note])
    return Response(buffer.getvalue(), mimetype='text/csv; charset=utf-8', headers={'Content-Disposition': f'attachment; filename="corso-{corso.id}-iscritti.csv"'})


@app.route('/admin/corso/<int:id>/export.pdf')
@login_required
def esporta_corso_pdf(id):
    corso = db.get_or_404(Corso, id)
    iscrizioni = IscrizioneCorso.query.filter_by(corso_id=corso.id).order_by(IscrizioneCorso.nome).all()
    righe = [f'Corso: {corso.titolo}', f'Data: {_etichetta_data_corso(corso)}', f'Capienza nominale: {corso.capienza_massima or "non impostata"}', '', 'Partecipanti:']
    righe.extend([f'- {i.nome} | {i.telefono} | {i.email or "email non indicata"} | posti {i.posti} | {i.stato}' for i in iscrizioni] or ['Nessuna iscrizione.'])
    pdf = _crea_pdf_testuale(f'Iscritti - {corso.titolo}', righe)
    return Response(pdf, mimetype='application/pdf', headers={'Content-Disposition': f'attachment; filename="corso-{corso.id}-iscritti.pdf"'})


@app.route('/admin/iscrizione-corso/<int:id>/<stato>', methods=['POST'])
@login_required
def aggiorna_stato_iscrizione_corso(id, stato):
    if stato not in STATI_ISCRIZIONE_VALIDI:
        abort(400)
    token = request.form.get('_csrf_token')
    if not token or token != session.get('_csrf_token'):
        flash('Richiesta non valida. Riprova.', 'error')
        return redirect(url_for('admin'))
    iscrizione = db.get_or_404(IscrizioneCorso, id)
    stato_precedente = iscrizione.stato
    patient = None
    patient_created = False
    if stato == stato_precedente and stato in STATI_LISTA_ATTESA and not iscrizione.persona:
        patient, patient_created = _ensure_patient_for_course_registration(iscrizione)
        db.session.commit()
        _audit_automatic_course_patient_link(
            iscrizione,
            patient,
            patient_created,
            'creazione_anagrafica_da_lista_attesa',
        )
        flash('Stato invariato; scheda paziente collegata alla lista d’attesa.', 'success')
        return redirect(url_for('admin'))
    if stato == stato_precedente:
        flash('Stato invariato; nessuna nuova email inviata.', 'success')
        return redirect(url_for('admin'))
    if (
        stato == 'Confermato'
        and iscrizione.tipo_richiesta == 'ricontatto'
        and not iscrizione.corso
        and not iscrizione.percorso_accompagnamento
    ):
        flash('Collega prima la richiesta di interesse a un’edizione: il posto non può ancora essere confermato.', 'error')
        return redirect(url_for('admin'))
    iscrizione.stato = stato
    if stato not in {'Lista attesa', 'Invitato'} and iscrizione.posti == 0:
        iscrizione.posti = iscrizione.posti_richiesti or 1
    if stato == 'Confermato' or stato in STATI_LISTA_ATTESA:
        patient, patient_created = _ensure_patient_for_course_registration(iscrizione)
    db.session.commit()
    registra_modifica('cambio_stato', 'IscrizioneCorso', iscrizione.id, {'da': stato_precedente, 'a': stato})
    if patient:
        _audit_automatic_course_patient_link(
            iscrizione,
            patient,
            patient_created,
            (
                'creazione_anagrafica_da_conferma'
                if stato == 'Confermato'
                else 'creazione_anagrafica_da_lista_attesa'
            ),
        )
    email_inviata = None
    if stato == 'Confermato':
        email_inviata = invia_email_conferma_iscrizione_corso(iscrizione)
    elif stato == 'Annullato' and stato_precedente not in STATI_LISTA_ATTESA:
        email_inviata = invia_email_annullamento_iscrizione_corso(
            iscrizione,
            stato_precedente,
        )
    if stato == 'Annullato' and iscrizione.corso:
        _segnala_prossimo_lista_attesa(iscrizione.corso)
    if stato in {'Confermato', 'Annullato'}:
        azione = 'confermata' if stato == 'Confermato' else 'annullata'
        if stato == 'Annullato' and stato_precedente in STATI_LISTA_ATTESA:
            flash('Iscrizione annullata; nessuna email inviata perché era in lista d’attesa.', 'success')
        elif email_inviata is True:
            flash(f'Iscrizione {azione}; email inviata al partecipante.', 'success')
        elif email_inviata is None:
            flash(f'Iscrizione {azione}, ma l’email è mancante: contatta il partecipante manualmente.', 'error')
        else:
            flash(f'Iscrizione {azione}, ma l’email non è partita. Controlla il registro eventi.', 'error')
    else:
        flash('Stato iscrizione aggiornato.', 'success')
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
