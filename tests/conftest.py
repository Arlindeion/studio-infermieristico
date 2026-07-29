import os

# IMPORTANTE: va impostato prima che qualsiasi test importi `app`, così
# configurazione, scheduler e integrazioni esterne restano in modalità test.
os.environ['FLASK_ENV'] = 'testing'
