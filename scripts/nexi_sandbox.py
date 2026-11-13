"""Start a disposable local demo without reading .env or any real database."""

import argparse
import getpass
import os
from pathlib import Path
import secrets
import sys


def main():
    parser = argparse.ArgumentParser(description='Collaudo isolato Nexi, solo pagamenti simulati.')
    parser.add_argument('--port', type=int, default=5055)
    parser.add_argument('--public-base-url', help='Origine HTTPS della sola copia di collaudo.')
    parser.add_argument('--no-key', action='store_true', help='Apri la proposta senza collegarti a Nexi.')
    parser.add_argument('--probe', action='store_true', help='Verifica solo le credenziali sandbox, senza avviare il server.')
    args = parser.parse_args()
    os.environ['PYTHON_DOTENV_DISABLED'] = '1'
    os.environ['FLASK_ENV'] = 'payment_sandbox'
    os.environ['DISABLE_SCHEDULER'] = 'true'
    if args.public_base_url:
        from urllib.parse import urlsplit
        origin = urlsplit(args.public_base_url)
        if origin.scheme != 'https' or not origin.hostname or origin.path not in {'', '/'}:
            parser.error('--public-base-url richiede un’origine HTTPS senza percorso.')
        os.environ['NEXI_SANDBOX_PUBLIC_BASE_URL'] = args.public_base_url.rstrip('/')
    if args.no_key:
        os.environ.pop('NEXI_SANDBOX_API_KEY', None)
    elif not os.environ.get('NEXI_SANDBOX_API_KEY'):
        os.environ['NEXI_SANDBOX_API_KEY'] = getpass.getpass('API Key sandbox Nexi (input nascosto): ').strip()

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    if args.probe:
        from nexi_gateway import NexiError, NexiSandboxClient
        try:
            NexiSandboxClient(os.environ.get('NEXI_SANDBOX_API_KEY')).get_order('NX' + secrets.token_hex(8))
        except NexiError as error:
            if error.status != 404:
                print('Verifica non riuscita. Controllare chiave sandbox e collegamento di rete.')
                return 1
        print('Credenziali accettate dal gateway sandbox. Nessun pagamento avviato.')
        return 0

    from app import app, db, CallSonno, utc_now, timedelta
    with app.app_context():
        db.create_all()
        token = secrets.token_urlsafe(48)
        demo = CallSonno(
            nome='Famiglia di prova', telefono='0000000000', email='famiglia@example.invalid',
            eta_bambino_mesi=8, difficolta_principale='Prova sintetica',
            consenso_privacy=True, data='2026-12-01', ora='10:00', stato='Conclusa',
            proposta_tipo='percorso', proposta_token=token,
            proposta_scade_il=utc_now() + timedelta(days=7),
        )
        db.session.add(demo)
        db.session.commit()
    print('Ambiente temporaneo: database in memoria, email simulate, Calendar disabilitato.')
    print(f'Proposta fittizia: http://127.0.0.1:{args.port}/offerta-sonno/{token}')
    if not app.config.get('PUBLIC_BASE_URL'):
        print('Per il checkout completo serve --public-base-url con un’origine HTTPS raggiungibile.')
    app.run(host='127.0.0.1', port=args.port, debug=False, use_reloader=False, threaded=False)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
