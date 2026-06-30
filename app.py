import logging
import re
from flask import Flask, render_template, request, redirect, url_for, flash, abort, session, jsonify
from dotenv import load_dotenv
import os
import secrets
from apscheduler.schedulers.background import BackgroundScheduler
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

# ─── CONFIGURAZIONE EMAIL ───
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'sc.studioinfermieristico@gmail.com'
app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD')
app.config['MAIL_DEFAULT_SENDER'] = 'sc.studioinfermieristico@gmail.com'

db = SQLAlchemy(app)
mail = Mail(app)
scheduler = BackgroundScheduler()
scheduler.start()
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

# Pianifica il controllo dei promemoria per eseguirlo ogni ora
scheduler.add_job(
    func=controlla_e_invia_ricordi_24h,
    trigger="interval",
    hours=1,
    id='ricordi_24h_job',
    name='Controllo e invio ricordi 24h',
    replace_existing=True
)


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


@limiter.limit("5 per minute")
@app.route('/prenota', methods=['GET', 'POST'])
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

@limiter.limit("5 per minute")
@app.route('/admin/login', methods=['GET', 'POST'])
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
    orari = [ora for (ora,) in occupati]
    return jsonify(orari)


# ─── AVVIO ───

if __name__ == '__main__':
    app.run(debug=True)