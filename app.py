import logging
import re
import urllib.request
import urllib.error
import ssl
import certifi
from flask import Flask, render_template, request, redirect, url_for, flash, abort, session, jsonify
from dotenv import load_dotenv
import os
import secrets
import time
from zoneinfo import ZoneInfo
from apscheduler.schedulers.background import BackgroundScheduler
import icalendar
import recurring_ical_events
load_dotenv()
from config import config
from flask_sqlalchemy import SQLAlchemy
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
scheduler = BackgroundScheduler()
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.session_protection = 'basic'

talisman = Talisman(
    app,
    content_security_policy={
        'default-src': "'self'",
        'style-src': ["'self'"],
        'script-src': ["'self'"],
        'img-src': ["'self'", "data:"],
        'font-src': ["'self'"],
    },
    force_https=False,
    session_cookie_secure=os.environ.get('FLASK_ENV') == 'production',
    session_cookie_http_only=True,
    session_cookie_samesite='Lax',
)


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

# Slot orari prenotabili (durata 30 minuti ciascuno). È la stessa lista
# mostrata nei menu a tendina di prenota.html e modifica_appuntamento.html.
ORARI_DISPONIBILI = [
    '08:00', '08:30', '09:00', '09:30', '10:00', '10:30',
    '11:00', '11:30', '12:00', '12:30', '15:00', '15:30',
    '16:00', '16:30', '17:00', '17:30', '18:00', '18:30',
]
DURATA_SLOT_MINUTI = 30

FUSO_ORARIO = ZoneInfo('Europe/Rome')

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


def orari_occupati_da_calendario(data_str):
    """Restituisce l'insieme degli orari (stringhe 'HH:MM') di ORARI_DISPONIBILI
    che risultano occupati, per la data indicata, da eventi sul calendario
    Google (appuntamenti Arzamed o chiusure studio)."""
    calendario = _scarica_calendario_ics()
    if calendario is None:
        return set()

    try:
        giorno = datetime.strptime(data_str, '%Y-%m-%d').date()
    except ValueError:
        return set()

    inizio_giornata = datetime.combine(giorno, datetime.min.time(), tzinfo=FUSO_ORARIO)
    fine_giornata = inizio_giornata + timedelta(days=1)

    try:
        eventi = recurring_ical_events.of(calendario).between(inizio_giornata, fine_giornata)
    except Exception as e:
        logger.error(f'>>> Errore nell\'espansione degli eventi del calendario: {e}', exc_info=True)
        return set()

    occupati = set()
    for evento in eventi:
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

        for orario in ORARI_DISPONIBILI:
            ora, minuto = map(int, orario.split(':'))
            inizio_slot = datetime.combine(giorno, datetime.min.time(), tzinfo=FUSO_ORARIO).replace(hour=ora, minute=minuto)
            fine_slot = inizio_slot + timedelta(minutes=DURATA_SLOT_MINUTI)

            # Due intervalli si sovrappongono se ciascuno inizia prima che
            # l'altro finisca.
            if inizio_slot < fine_evento and inizio_evento < fine_slot:
                occupati.add(orario)

    return occupati


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


class Corso(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    titolo = db.Column(db.String(200), nullable=False)
    descrizione = db.Column(db.Text, nullable=True)
    data = db.Column(db.String(20), nullable=False)
    ora = db.Column(db.String(10), nullable=True)
    luogo = db.Column(db.String(200), nullable=True)
    creato_il = db.Column(db.DateTime, default=datetime.now)


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(Admin, int(user_id))


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
        logger.info('>>> Admin creato — username: admin | password: cambiami123')
    else:
        logger.info('>>> Database OK — Admin esistente')


# ─── EMAIL ───

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
                f'Per qualsiasi necessità puoi contattarci al numero 3806317175.\n\n'
                f'A presto,\n'
                f'S.C. Studio Infermieristico'
            )
        )
        mail.send(msg)
        logger.info('>>> Email conferma inviata con successo!')
    except Exception as e:
        logger.error(f'>>> Errore invio email conferma: {e}', exc_info=True)


def invia_email_spostamento(appuntamento):
    """Invia email di notifica quando un appuntamento viene riprogrammato."""
    try:
        logger.info(f'>>> Invio email spostamento a {appuntamento.email}...')
        msg = Message(
            subject='Appuntamento spostato - S.C. Studio Infermieristico',
            recipients=[appuntamento.email],
            body=(
                f'Gentile {appuntamento.nome},\n\n'
                f'ti informiamo che il tuo appuntamento è stato spostato '
                f'alle seguenti nuove data e ora:\n\n'
                f'Servizio:     {appuntamento.servizio}\n'
                f'Nuova data:   {appuntamento.data}\n'
                f'Nuovo orario: {appuntamento.ora}\n\n'
                f'Se hai domande o necessiti di ulteriori modifiche '
                f'puoi contattarci al numero 3806317175.\n\n'
                f'A presto,\n'
                f'S.C. Studio Infermieristico'
            )
        )
        mail.send(msg)
        logger.info('>>> Email spostamento inviata con successo!')
    except Exception as e:
        logger.error(f'>>> Errore invio email spostamento: {e}', exc_info=True)


def invia_email_annullamento(appuntamento):
    """Invia email di cancellazione al paziente."""
    try:
        logger.info(f'>>> Invio email annullamento a {appuntamento.email}...')
        msg = Message(
            subject='Appuntamento cancellato - S.C. Studio Infermieristico',
            recipients=[appuntamento.email],
            body=(
                f'Gentile {appuntamento.nome},\n\n'
                f'ti informiamo che il tuo appuntamento è stato cancellato.\n\n'
                f'Servizio: {appuntamento.servizio}\n'
                f'Data:     {appuntamento.data}\n'
                f'Ora:      {appuntamento.ora}\n\n'
                f'Se desideri fissare un nuovo appuntamento puoi prenotare '
                f'direttamente dal nostro sito o contattarci al numero 3806317175.\n\n'
                f'Ci scusiamo per l\'inconveniente.\n\n'
                f'A presto,\n'
                f'S.C. Studio Infermieristico'
            )
        )
        mail.send(msg)
        logger.info('>>> Email annullamento inviata con successo!')
    except Exception as e:
        logger.error(f'>>> Errore invio email annullamento: {e}', exc_info=True)


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
    except Exception as e:
        logger.error(f'>>> Errore invio email alert: {e}', exc_info=True)


def invia_email_ricordo_24h(appuntamento):
    """Invia email di promemoria 24 ore prima dell'appuntamento."""
    try:
        logger.info(f'>>> Invio email ricordo 24h a {appuntamento.email}...')
        msg = Message(
            subject='Ricordo: Appuntamento domani - S.C. Studio Infermieristico',
            recipients=[appuntamento.email],
            body=(
                f'Gentile {appuntamento.nome},\n\n'
                f'Ti ricordiamo che hai un appuntamento domani:\n\n'
                f'Servizio: {appuntamento.servizio}\n'
                f'Data:     {appuntamento.data}\n'
                f'Ora:      {appuntamento.ora}\n\n'
                f'Se hai bisogno di modificare o cancellare l\'appuntamento, '
                f'puoi contattarci al numero 3806317175.\n\n'
                f'A presto,\n'
                f'S.C. Studio Infermieristico'
            )
        )
        mail.send(msg)
        logger.info('>>> Email ricordo 24h inviata con successo!')
    except Exception as e:
        logger.error(f'>>> Errore invio email ricordo 24h: {e}', exc_info=True)


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


@app.route('/prestazioni-infermieristiche')
def prestazioni():
    return render_template('prestazioni_infermieristiche.html')


@app.route('/prima-della-nascita')
def prima_della_nascita():
    return render_template('prima_della_nascita.html')


@app.route('/dopo-la-nascita')
def dopo_la_nascita():
    return render_template('dopo_la_nascita.html')


@app.route('/consulenze-online')
def consulenze_online():
    return render_template('consulenze_online.html')


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

        # Verifica che lo slot non sia già occupato (in DB o su Arzamed/Google
        # Calendar). Il form disabilita già questi orari via JavaScript, ma
        # questo controllo lato server evita doppie prenotazioni nel caso in
        # cui qualcuno invii comunque la richiesta (bypassando il JS, o per
        # una prenotazione fatta nel frattempo da un altro utente).
        gia_occupato_db = Appuntamento.query.filter(
            Appuntamento.data == data_scelta,
            Appuntamento.ora == ora,
            Appuntamento.stato != 'Annullato'
        ).first() is not None
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
            return redirect(next_page or url_for('admin'))
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
    return render_template('admin.html',
                           appuntamenti=appuntamenti,
                           corsi=corsi,
                           filtro=filtro,
                           in_attesa_count=in_attesa_count)


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
    elif stato == 'Annullato':
        invia_email_annullamento(appuntamento)
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
        appuntamento.data = request.form['data']
        appuntamento.ora = request.form['ora']
        appuntamento.stato = 'Confermato'
        db.session.commit()
        invia_email_spostamento(appuntamento)
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
    corso = Corso(
        titolo=request.form['titolo'],
        descrizione=request.form.get('descrizione', ''),
        data=request.form['data'],
        ora=request.form.get('ora', ''),
        luogo=request.form.get('luogo', '')
    )
    db.session.add(corso)
    db.session.commit()
    return redirect(url_for('admin'))


@app.route('/admin/corso/elimina/<int:id>')
@login_required
def elimina_corso(id):
    # Protezione CSRF (stesso ragionamento di aggiorna_stato)
    token = request.args.get('token')
    if not token or token != session.get('_csrf_token'):
        flash('Richiesta non valida. Riprova.', 'error')
        return redirect(url_for('admin'))
    corso = db.get_or_404(Corso, id)
    db.session.delete(corso)
    db.session.commit()
    return redirect(url_for('admin'))


@app.route('/api/orari-occupati/<data>')
def orari_occupati(data):
    # Restituisce la lista degli orari occupati per la data specificata (YYYY-MM-DD)
    # Escludi gli appuntamenti annullati (stato != 'Annullato') in quanto liberano lo slot
    occupati = Appuntamento.query.filter(
        Appuntamento.data == data,
        Appuntamento.stato != 'Annullato'
    ).with_entities(Appuntamento.ora).all()
    # Converti la lista di tuple in una lista di stringhe
    orari = {ora for (ora,) in occupati}
    # Aggiungi gli orari occupati su Arzamed/Google Calendar (appuntamenti e chiusure studio)
    orari |= orari_occupati_da_calendario(data)
    return jsonify(sorted(orari))


# ─── AVVIO ───

if __name__ == '__main__':
    app.run(debug=True)