from flask import Flask, render_template, request, redirect, url_for, flash, abort
from dotenv import load_dotenv
import os
load_dotenv()
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from flask_mail import Mail, Message
from datetime import datetime, date, timedelta
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///appuntamenti.db'
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'fallback-solo-per-sviluppo')
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_SECURE'] = False
app.config['SESSION_COOKIE_HTTPONLY'] = True

print(f'>>> SECRET_KEY caricata: {app.config["SECRET_KEY"][:8]}...')

# ─── CONFIGURAZIONE EMAIL ───
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'sc.studioinfermieristico@gmail.com'
app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD')
app.config['MAIL_DEFAULT_SENDER'] = 'sc.studioinfermieristico@gmail.com'

db = SQLAlchemy(app)
mail = Mail(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.session_protection = 'basic'


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
        print('>>> Admin creato — username: admin | password: cambiami123')
    else:
        print('>>> Database OK — Admin esistente')


# ─── EMAIL ───

def invia_email_conferma(appuntamento):
    try:
        print(f'>>> Invio email conferma a {appuntamento.email}...')
        msg = Message(
            subject='Appuntamento confermato - S.C. Studio Infermieristico',
            recipients=[appuntamento.email],
            body=(
                f'Gentile {appuntamento.nome},\n\n'
                f'il tuo appuntamento e stato confermato.\n\n'
                f'Servizio: {appuntamento.servizio}\n'
                f'Data:     {appuntamento.data}\n'
                f'Ora:      {appuntamento.ora}\n\n'
                f'Per qualsiasi necessita puoi contattarci al numero 3806317175.\n\n'
                f'A presto,\n'
                f'S.C. Studio Infermieristico'
            )
        )
        mail.send(msg)
        print('>>> Email conferma inviata con successo!')
    except Exception as e:
        print(f'>>> Errore invio email conferma: {e}')


def invia_email_spostamento(appuntamento):
    try:
        print(f'>>> Invio email spostamento a {appuntamento.email}...')
        msg = Message(
            subject='Appuntamento spostato - S.C. Studio Infermieristico',
            recipients=[appuntamento.email],
            body=(
                f'Gentile {appuntamento.nome},\n\n'
                f'ti informiamo che il tuo appuntamento e stato spostato '
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
        print('>>> Email spostamento inviata con successo!')
    except Exception as e:
        print(f'>>> Errore invio email spostamento: {e}')


def invia_email_annullamento(appuntamento):
    try:
        print(f'>>> Invio email annullamento a {appuntamento.email}...')
        msg = Message(
            subject='Appuntamento cancellato - S.C. Studio Infermieristico',
            recipients=[appuntamento.email],
            body=(
                f'Gentile {appuntamento.nome},\n\n'
                f'ti informiamo che il tuo appuntamento e stato cancellato.\n\n'
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
        print('>>> Email annullamento inviata con successo!')
    except Exception as e:
        print(f'>>> Errore invio email annullamento: {e}')


def invia_email_nuova_prenotazione(appuntamento):
    try:
        print(f'>>> Invio email alert nuova prenotazione...')
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
        print('>>> Email alert inviata con successo!')
    except Exception as e:
        print(f'>>> Errore invio email alert: {e}')


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
def prenota():
    if request.method == 'POST':

        if not request.form.get('consenso_privacy'):
            flash('Devi accettare l\'informativa privacy per procedere.')
            return render_template('prenota.html', form_data=request.form)

        if request.form.get('servizio') not in SERVIZI_VALIDI:
            flash('Servizio non valido. Seleziona un servizio dalla lista.')
            return render_template('prenota.html', form_data=request.form)

        data_scelta = request.form['data']
        oggi = date.today().strftime('%Y-%m-%d')
        if data_scelta < oggi:
            flash('Non puoi prenotare una data nel passato.')
            return render_template('prenota.html', form_data=request.form)

        nuovo = Appuntamento(
            nome=request.form['nome'],
            telefono=request.form['telefono'],
            email=request.form['email'],
            servizio=request.form['servizio'],
            data=data_scelta,
            ora=request.form['ora'],
            note=request.form.get('note', '')
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
def login():
    if current_user.is_authenticated:
        return redirect(url_for('admin'))
    if request.method == 'POST':
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

    trenta_giorni_fa = datetime.today() - timedelta(days=30)
    vecchi = Appuntamento.query.filter(
        Appuntamento.stato == 'Annullato',
        Appuntamento.creato_il < trenta_giorni_fa
    ).all()
    for v in vecchi:
        db.session.delete(v)
    db.session.commit()

    if filtro == 'in_attesa':
        appuntamenti = Appuntamento.query.filter(
            Appuntamento.stato == 'In attesa'
        ).order_by(Appuntamento.data, Appuntamento.ora).all()
    elif filtro == 'confermati':
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

    in_attesa_count = Appuntamento.query.filter(
        Appuntamento.stato == 'In attesa'
    ).count()

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


# ─── AVVIO ───

if __name__ == '__main__':
    app.run(debug=True)