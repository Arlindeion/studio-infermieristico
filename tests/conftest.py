import os

# IMPORTANTE: questo va impostato PRIMA che qualsiasi test importi `app`.
# `app.py` inizializza il database (db.create_all()) e l'admin di default
# a livello di modulo, usando la configurazione attiva in quel momento.
# Se FLASK_ENV non è 'testing' a quel punto, l'inizializzazione avviene
# sul database reale (appuntamenti.db) invece che su quello in memoria,
# e il successivo db.drop_all() del fixture di test cancellerebbe le
# tabelle reali. pytest carica sempre conftest.py prima dei file di test,
# quindi impostando la variabile qui siamo certi che venga letta in tempo.
os.environ['FLASK_ENV'] = 'testing'
