#!/usr/bin/env python3
"""Standalone macOS backup agent. Never imports the website or its integrations."""
import argparse
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import fcntl
import hashlib
import http.client
import json
import os
from pathlib import Path
import re
import shutil
import signal
import stat
import ssl
import subprocess
import sys
import tempfile
import uuid
from zoneinfo import ZoneInfo

SERVICE = "it.scstudioinfermieristico.backup.postgres"
ACCOUNT = "studio_backup"
LABEL = "it.scstudioinfermieristico.backup"
MONITOR_SERVICE = SERVICE + ".healthchecks"
ARCHIVE_NAME = re.compile(r"sc-studio-\d{8}T\d{6}Z-[0-9a-f]{8}\Z")
FILES = {"backup.dump.age", "backup.dump.age.sha256", "manifest.json"}


class BackupError(Exception):
    """Deliberately contains no native output, credentials or database content."""


def safe_path(path):
    path = Path(os.path.abspath(path))
    for part in (path, *path.parents):
        if part.is_symlink():
            raise BackupError("Percorso con collegamenti simbolici rifiutato.")
    return path


def private(path, directory=False):
    path = safe_path(path)
    info = path.stat()
    if info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) & 0o077:
        raise BackupError("Permessi non privati o proprietario diverso.")
    if directory != stat.S_ISDIR(info.st_mode):
        raise BackupError("Tipo di file non valido.")
    if not directory and not stat.S_ISREG(info.st_mode):
        raise BackupError("File non regolare rifiutato.")
    return path


def prepare_root(root):
    root = safe_path(root)
    if root.name != "SCStudioBackup":
        raise BackupError("La destinazione deve chiamarsi SCStudioBackup.")
    for relative in ("", "config", "logs", ".work", "archivi", "archivi/giornalieri",
                     "archivi/settimanali", "archivi/mensili"):
        path = safe_path(root / relative)
        path.mkdir(mode=0o700, parents=True, exist_ok=True)
        private(path, directory=True)
    return root


def save_json(path, value):
    path = safe_path(path)
    fd, name = tempfile.mkstemp(prefix=".json-", dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(value, stream, ensure_ascii=True)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        directory_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        temporary.unlink(missing_ok=True)


def read_json(path):
    private(path)
    return json.loads(path.read_text(encoding="utf-8"))


def utc(value):
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.tzinfo is None:
        raise BackupError("Data senza fuso orario.")
    return result.astimezone(timezone.utc)


def local_zone():
    with open("/etc/localtime", "rb") as stream:
        return ZoneInfo.from_file(stream)


def child_environment(extra=None):
    environment = {key: value for key, value in os.environ.items()
                   if not key.startswith("PG") and key != "DATABASE_URL"}
    environment.update(extra or {})
    return environment


def tool(arguments, environment=None, timeout=900):
    try:
        result = subprocess.run(arguments, env=child_environment(environment),
                                capture_output=True, timeout=timeout, check=False)
    except (OSError, subprocess.TimeoutExpired):
        raise BackupError("Strumento non disponibile o tempo massimo superato.") from None
    if result.returncode:
        raise BackupError("Strumento non riuscito; dettagli riservati non registrati.")
    return result.stdout


def load_configuration(root):
    cfg = read_json(root / "config/settings.json")
    if (cfg.get("schemaVersion") != 1 or cfg.get("ownerUid") != os.getuid()
            or not re.fullmatch(r"[a-zA-Z0-9.-]+\.render\.com", cfg.get("host", ""))
            or not re.fullmatch(r"[a-zA-Z0-9_-]+", cfg.get("database", ""))
            or cfg.get("user") != ACCOUNT or cfg.get("port") != 5432
            or not re.fullmatch(r"age1[0-9a-z]{58}", cfg.get("recipient", ""))):
        raise BackupError("Configurazione non valida per questo account.")
    for name in ("pgDump", "pgRestore", "age", "sslRootCert"):
        if not Path(cfg[name]).is_absolute() or not Path(cfg[name]).is_file():
            raise BackupError("Percorso degli strumenti o certificati non valido.")
    return cfg


def preflight(cfg):
    if sys.platform != "darwin":
        raise BackupError("Il job operativo richiede macOS.")
    if tool(["/usr/bin/fdesetup", "status"], timeout=15).strip() != b"FileVault is On.":
        raise BackupError("FileVault non risulta attivo: backup fermato.")
    for name in ("pgDump", "pgRestore", "age"):
        tool([cfg[name], "--version"], timeout=15)


def keychain_password():
    # Only this dedicated item is read. Never inspect unrelated Keychain entries.
    value = tool(["/usr/bin/security", "find-generic-password", "-s", SERVICE,
                  "-a", ACCOUNT, "-w"], timeout=60).decode("utf-8").removesuffix("\n")
    if not value or "\x00" in value or "\n" in value or "\r" in value:
        raise BackupError("Credenziale dedicata assente o non valida.")
    return value


def checksum(path):
    private(path)
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def verify_archive(directory):
    directory = private(directory, directory=True)
    if {item.name for item in directory.iterdir()} != FILES:
        raise BackupError("Archivio incompleto o con file estranei.")
    for name in FILES:
        private(directory / name)
    manifest = read_json(directory / "manifest.json")
    encrypted = directory / "backup.dump.age"
    expected = (directory / "backup.dump.age.sha256").read_text(encoding="ascii").strip()
    digest = checksum(encrypted)
    if (manifest.get("schemaVersion") != 1 or manifest.get("format") != "pg-custom-age-v1"
            or manifest.get("sha256") != digest
            or expected != digest + "  backup.dump.age"
            or manifest.get("bytes") != encrypted.stat().st_size
            or encrypted.stat().st_size <= 0):
        raise BackupError("Integrita dell'archivio non valida.")
    utc(manifest["createdUtc"])
    return manifest


def archive_from_status(root, status):
    relative = status.get("archive", "")
    parts = Path(relative).parts
    if len(parts) != 3 or parts[:2] != ("archivi", "giornalieri") or not ARCHIVE_NAME.fullmatch(parts[2]):
        raise BackupError("Riferimento all'archivio non valido.")
    return safe_path(root / relative)


def read_status(root):
    path = root / "logs/status.json"
    return read_json(path) if path.exists() else {}


def write_status(root, state, stage, previous, archive=None, now=None):
    now = now or datetime.now(timezone.utc)
    last = now.isoformat() if state == "success" else previous.get("lastSuccessUtc")
    save_json(root / "logs/status.json", {
        "state": state, "stage": stage, "attemptedUtc": now.isoformat(),
        "lastSuccessUtc": last, "archive": archive or previous.get("archive"),
    })


def due(root, now):
    previous = read_status(root)
    if previous.get("state") != "success" or not previous.get("lastSuccessUtc"):
        return True
    if utc(previous["lastSuccessUtc"]) > now + timedelta(minutes=5):
        return True
    local = now.astimezone(local_zone())
    target = local.replace(hour=22, minute=0, second=0, microsecond=0)
    if local < target:
        target -= timedelta(days=1)
    if utc(previous["lastSuccessUtc"]) < target.astimezone(timezone.utc):
        return True
    try:
        verify_archive(archive_from_status(root, previous))
    except (BackupError, OSError, ValueError, KeyError):
        return True
    return False


def check(root, now):
    status = read_status(root)
    if status.get("state") != "success" or not status.get("lastSuccessUtc"):
        raise BackupError("Ultimo tentativo non riuscito o backup assente.")
    age = now - utc(status["lastSuccessUtc"])
    if age < timedelta(minutes=-5) or age > timedelta(hours=24):
        raise BackupError("Ultimo backup troppo vecchio o orologio incoerente.")
    verify_archive(archive_from_status(root, status))


@contextmanager
def lock(root):
    path = safe_path(root / ".work/backup.lock")
    descriptor = os.open(path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        private(path)
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise BackupError("Un backup e gia in esecuzione.") from None
        yield
    finally:
        os.close(descriptor)


def months_ago(now, months):
    import calendar
    year, month = divmod(now.year * 12 + now.month - 1 - months, 12)
    return now.replace(year=year, month=month + 1,
                       day=min(now.day, calendar.monthrange(year, month + 1)[1]))


def retain(root, now):
    thresholds = {"giornalieri": now - timedelta(days=14),
                  "settimanali": now - timedelta(days=56), "mensili": months_ago(now, 12)}
    for bucket, threshold in thresholds.items():
        parent = private(root / "archivi" / bucket, directory=True)
        for directory in parent.iterdir():
            if not ARCHIVE_NAME.fullmatch(directory.name):
                continue
            manifest = verify_archive(directory)
            if utc(manifest["createdUtc"]) < threshold:
                # No recursion: only the three verified files in this owned directory.
                for name in FILES:
                    private(directory / name).unlink()
                directory.rmdir()


def publish(root, staging, now):
    name = "sc-studio-" + now.strftime("%Y%m%dT%H%M%SZ-") + uuid.uuid4().hex[:8]
    local = now.astimezone(local_zone())
    buckets = ["giornalieri"]
    if local.weekday() == 6:
        buckets.append("settimanali")
    if local.day == 1:
        buckets.append("mensili")
    # Stage and validate every copy before making any of them visible.
    for bucket in buckets:
        copy = staging.parent / bucket
        shutil.copytree(staging, copy)
        verify_archive(copy)
        for filename in FILES:
            with (copy / filename).open("rb") as stream:
                os.fsync(stream.fileno())
    for bucket in buckets:
        target = private(root / "archivi" / bucket, directory=True) / name
        if target.exists():
            raise BackupError("Archivio gia esistente: pubblicazione fermata.")
        os.rename(staging.parent / bucket, target)
        descriptor = os.open(target.parent, os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    return "archivi/giornalieri/" + name


def run_backup(root, cfg, now, password_provider=keychain_password):
    previous = read_status(root)
    stage = "spazio"
    write_status(root, "running", stage, previous)
    try:
        if shutil.disk_usage(root).free < 1024**3:
            raise BackupError("Meno di 1 GB disponibile sul disco.")
        # Plaintext never goes to /tmp or a cloud-synced directory.
        with tempfile.TemporaryDirectory(prefix="run-", dir=root / ".work") as work_name:
            work = Path(work_name)
            raw = work / "database.dump"
            staging = work / "publish"
            staging.mkdir(mode=0o700)
            stage = "portachiavi"
            environment = {
                "PGHOST": cfg["host"], "PGPORT": str(cfg["port"]),
                "PGDATABASE": cfg["database"], "PGUSER": cfg["user"],
                "PGPASSWORD": password_provider(), "PGSSLMODE": "verify-full",
                "PGSSLROOTCERT": cfg["sslRootCert"], "PGCONNECT_TIMEOUT": "15",
                "PGOPTIONS": "-c default_transaction_read_only=on -c statement_timeout=900000",
            }
            try:
                stage = "dump"
                tool([cfg["pgDump"], "--no-password", "--format=custom", "--compress=9",
                      "--no-owner", "--no-acl", "--file", str(raw)], environment)
            finally:
                environment.clear()
            stage = "verifica_dump"
            private(raw)
            if raw.stat().st_size <= 0:
                raise BackupError("Dump vuoto.")
            tool([cfg["pgRestore"], "--list", str(raw)])
            stage = "cifratura"
            encrypted = staging / "backup.dump.age"
            tool([cfg["age"], "--encrypt", "--recipient", cfg["recipient"],
                  "--output", str(encrypted), str(raw)])
            raw.unlink()
            digest = checksum(encrypted)
            (staging / "backup.dump.age.sha256").write_text(digest + "  backup.dump.age\n", encoding="ascii")
            save_json(staging / "manifest.json", {
                "schemaVersion": 1, "format": "pg-custom-age-v1", "createdUtc": now.isoformat(),
                "bytes": encrypted.stat().st_size, "sha256": digest,
            })
            stage = "pubblicazione"
            verify_archive(staging)
            archive = publish(root, staging, now)
        stage = "conservazione"
        try:
            retain(root, now)
        except (BackupError, OSError, ValueError, KeyError):
            write_status(root, "warning", stage, {"lastSuccessUtc": now.isoformat()}, archive)
            return 2
        write_status(root, "success", "completato", previous, archive)
        return 0
    except Exception:
        write_status(root, "error", stage, previous)
        return 1


def interrupted(signum, frame):
    raise BackupError("Operazione interrotta.")


def monitor_path(value):
    if not re.fullmatch(r"https://hc-ping\.com/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", value):
        raise BackupError("Indirizzo monitor non valido.")
    return value.removeprefix("https://hc-ping.com")


def signal_new_backup(root):
    """Only called after an actual new archive, never on checks or skipped runs."""
    settings = root / "config/monitor.json"
    if not settings.exists():
        return
    connection = None
    try:
        if read_json(settings) != {"enabled": True}:
            raise BackupError("Configurazione monitor non valida.")
        status = read_status(root)
        check(root, datetime.now(timezone.utc))
        value = tool(["/usr/bin/security", "find-generic-password", "-s", MONITOR_SERVICE,
                      "-a", ACCOUNT, "-w"], timeout=15).decode().removesuffix("\n")
        path = monitor_path(value)
        connection = http.client.HTTPSConnection("hc-ping.com", timeout=8,
                                               context=ssl.create_default_context())
        connection.request("POST", path, body=b"", headers={"User-Agent": "StudioBackup/1"})
        response = connection.getresponse()
        if response.status != 200 or response.read(128).strip() != b"OK":
            raise BackupError("Segnale non confermato.")
        save_json(root / "logs/monitor.json", {"state": "success",
                  "backupUtc": status["lastSuccessUtc"],
                  "attemptedUtc": datetime.now(timezone.utc).isoformat()})
    except Exception:
        # Monitor errors must never invalidate or delete a valid backup.
        try:
            save_json(root / "logs/monitor.json", {"state": "error",
                      "attemptedUtc": datetime.now(timezone.utc).isoformat()})
        except Exception:
            pass
    finally:
        if connection:
            connection.close()


def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser(description="Backup PostgreSQL cifrato indipendente per macOS")
    parser.add_argument("--root", type=Path, default=Path.home() / "Library/Application Support/SCStudioBackup")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--scheduled", action="store_true")
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--preflight", action="store_true")
    args = parser.parse_args()
    for number in (signal.SIGTERM, signal.SIGINT):
        signal.signal(number, interrupted)
    try:
        root = prepare_root(args.root)
        if args.check:
            check(root, datetime.now(timezone.utc))
            print("Backup recente e integrita verificata; nessun accesso al database.")
            return 0
        if args.preflight:
            preflight(load_configuration(root))
            print("Controlli locali superati; nessun accesso a Portachiavi o database.")
            return 0
        with lock(root):
            try:
                cfg = load_configuration(root)
                preflight(cfg)
            except Exception:
                previous = {}
                try:
                    previous = read_json(root / "logs/status.json")
                except Exception:
                    pass
                write_status(root, "error", "preparazione", previous)
                raise
            now = datetime.now(timezone.utc)
            if args.scheduled and not due(root, now):
                return 0
            result = run_backup(root, cfg, now)
            if result == 0:
                signal_new_backup(root)
        print("Backup cifrato completato e verificato." if result == 0 else
              "Backup non riuscito o avviso: controllare logs/status.json.")
        return result
    except Exception:
        # Do not echo exception strings: native output can contain patient data.
        print("Operazione fermata: controllare configurazione, permessi e strumenti.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
