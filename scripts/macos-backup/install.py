#!/usr/bin/env python3
"""Local installation helper. Password entry stays in a native hidden dialog."""
import argparse
import importlib.util
import os
from pathlib import Path
import plistlib
import re
import subprocess
import sys

spec = importlib.util.spec_from_file_location("studio_backup", Path(__file__).with_name("backup.py"))
backup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(backup)


def agent_definition(root):
    return {
        "Label": backup.LABEL,
        "ProgramArguments": ["/usr/bin/caffeinate", "-i", str(Path(sys.executable).resolve()),
                             "-I", "-B", str(root / "backup.py"), "--root", str(root), "--scheduled"],
        "StartCalendarInterval": {"Hour": 22, "Minute": 0},
        "RunAtLoad": True,
        "StartInterval": 3600,
        "ThrottleInterval": 300,
        "ProcessType": "Background",
        "LowPriorityIO": True,
        "Nice": 10,
        "Umask": 0o077,
        "StandardOutPath": str(root / "logs/launchd.out.log"),
        "StandardErrorPath": str(root / "logs/launchd.err.log"),
    }


def prepare(root, recipient):
    root = backup.prepare_root(root)
    if not re.fullmatch(r"age1[0-9a-z]{58}", recipient):
        raise backup.BackupError("Chiave pubblica non valida.")
    cfg = {
        "schemaVersion": 1, "ownerUid": os.getuid(),
        "host": "dpg-da5denjm8hqs73ca54bg-a.frankfurt-postgres.render.com",
        "port": 5432, "database": "sc_studio_infermieristico_production_db",
        "user": backup.ACCOUNT, "recipient": recipient,
        "pgDump": "/opt/homebrew/bin/pg_dump", "pgRestore": "/opt/homebrew/bin/pg_restore",
        "age": "/opt/homebrew/bin/age", "sslRootCert": "/etc/ssl/cert.pem",
    }
    path = root / "config/settings.json"
    if path.exists():
        raise backup.BackupError("Configurazione gia presente: non sovrascritta.")
    backup.save_json(path, cfg)
    backup.preflight(backup.load_configuration(root))
    print("Configurazione non segreta pronta. Nessun accesso al database o a chiavi private.")


def save_credential(root):
    backup.preflight(backup.load_configuration(root))
    # No password in argv, environment, model output, shell history or files.
    # security's interactive parser receives the command only through a pipe.
    presence = subprocess.run(["/usr/bin/security", "find-generic-password", "-s", backup.SERVICE,
                               "-a", backup.ACCOUNT], capture_output=True, check=False, timeout=15)
    if presence.returncode == 0:
        raise backup.BackupError("Credenziale dedicata gia presente: nessuna modifica eseguita.")
    value = confirmation = None
    try:
        for message in (
            "Inserisci la password POSTGRESQL dell'utente studio_backup, quella nuova che funziona su Windows. Non quella Microsoft, del Mac o di postgres locale.",
            "Ripeti la stessa password PostgreSQL studio_backup per conferma.",
        ):
            script = ('text returned of (display dialog "' + message + '" '
                      'with title "S.C. Studio - configurazione backup Mac" default answer "" '
                      'with hidden answer buttons {"Annulla", "Continua"} default button "Continua" '
                      'cancel button "Annulla" giving up after 600)')
            result = subprocess.run(["/usr/bin/osascript", "-e", script], capture_output=True,
                                    check=False, timeout=610)
            if result.returncode:
                raise backup.BackupError("Inserimento annullato: password non salvata.")
            entered = result.stdout.decode("utf-8").removesuffix("\n")
            if value is None:
                value = entered
            else:
                confirmation = entered
        if value != confirmation or len(value) < 20 or not re.fullmatch(r"[!-~]+", value):
            raise backup.BackupError("Password diverse o formato inatteso: nulla salvato.")
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        command = ('add-generic-password -a studio_backup -s ' + backup.SERVICE
                   + ' -T /usr/bin/security -w "' + escaped + '"\n')
        result = subprocess.run(["/usr/bin/security", "-i"], input=command.encode("utf-8"),
                                capture_output=True, check=False, timeout=60)
        if result.returncode:
            raise backup.BackupError("Salvataggio nel Portachiavi non riuscito.")
        if backup.keychain_password() != value:
            raise backup.BackupError("Verifica della credenziale nel Portachiavi non riuscita.")
        print("Credenziale dedicata salvata e verificata nel Portachiavi. Nessun accesso al database.")
    finally:
        value = confirmation = None


def activate(root):
    # Never enable a real job without a first real successful local archive.
    backup.preflight(backup.load_configuration(root))
    backup.check(root, backup.datetime.now(backup.timezone.utc))
    path = backup.safe_path(Path.home() / "Library/LaunchAgents" / (backup.LABEL + ".plist"))
    if path.exists():
        raise backup.BackupError("LaunchAgent gia presente: non sovrascritto.")
    with path.open("xb") as stream:
        plistlib.dump(agent_definition(root), stream)
        stream.flush()
        os.fsync(stream.fileno())
    result = subprocess.run(["/bin/launchctl", "bootstrap", "gui/" + str(os.getuid()), str(path)],
                            capture_output=True, check=False, timeout=30)
    if result.returncode:
        raise backup.BackupError("Job non caricato: il plist resta disponibile per diagnosi.")
    print("Backup Mac pianificato alle 22:00, recupero all'accesso e tentativi ogni ora.")


def save_monitor(root):
    if (root / "config/monitor.json").exists():
        raise backup.BackupError("Monitor gia configurato: nessuna sovrascrittura.")
    presence = subprocess.run(["/usr/bin/security", "find-generic-password", "-s", backup.MONITOR_SERVICE,
                               "-a", backup.ACCOUNT], capture_output=True, timeout=15)
    if presence.returncode == 0:
        raise backup.BackupError("Elemento monitor gia presente.")
    script = ('text returned of (display dialog "Incolla il Ping URL del SOLO controllo Backup Mac di Healthchecks. Non la password del database." '
              'with title "S.C. Studio - avviso backup 72 ore" default answer "" '
              'with hidden answer buttons {"Annulla", "Salva"} default button "Salva" '
              'cancel button "Annulla" giving up after 600)')
    result = subprocess.run(["/usr/bin/osascript", "-e", script], capture_output=True, timeout=610)
    if result.returncode:
        raise backup.BackupError("Operazione annullata.")
    value = result.stdout.decode().strip()
    backup.monitor_path(value)
    command = ('add-generic-password -a studio_backup -s ' + backup.MONITOR_SERVICE
               + ' -T /usr/bin/security -w "' + value + '"\n')
    result = subprocess.run(["/usr/bin/security", "-i"], input=command.encode(), capture_output=True, timeout=30)
    if result.returncode:
        raise backup.BackupError("Salvataggio monitor non riuscito.")
    stored = backup.tool(["/usr/bin/security", "find-generic-password", "-s", backup.MONITOR_SERVICE,
                          "-a", backup.ACCOUNT, "-w"], timeout=15).decode().removesuffix("\n")
    if stored != value:
        raise backup.BackupError("Verifica monitor non riuscita.")
    backup.save_json(root / "config/monitor.json", {"enabled": True})
    print("Monitor Mac configurato; il primo segnale partira solo dopo un nuovo backup riuscito.")


def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.home() / "Library/Application Support/SCStudioBackup")
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--prepare", metavar="PUBLIC_AGE_RECIPIENT")
    action.add_argument("--credentials", action="store_true")
    action.add_argument("--activate", action="store_true")
    action.add_argument("--monitor", action="store_true")
    args = parser.parse_args()
    try:
        if args.prepare:
            prepare(args.root, args.prepare)
        elif args.credentials:
            save_credential(backup.prepare_root(args.root))
        elif args.monitor:
            save_monitor(backup.prepare_root(args.root))
        else:
            activate(backup.prepare_root(args.root))
        return 0
    except backup.BackupError as error:
        # These messages are defined by this package, never native tool output.
        print(str(error), file=sys.stderr)
        return 1
    except Exception:
        print("Operazione non completata; nessuna password o dettaglio riservato viene mostrato.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
