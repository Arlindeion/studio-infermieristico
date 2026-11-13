"""Update the existing commercial PDF while preserving its fonts and layout."""

import argparse
from datetime import datetime, timezone
from pathlib import Path
import tempfile

from pypdf import PdfReader, PdfWriter
from pypdf.generic import FloatObject, NameObject, TextStringObject


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PDF = ROOT / 'output/pdf/consulenza_sonno_formule_e_prezzi.pdf'
OLD_BOOKING_URL = 'https://sc-studio-infermieristico-production.onrender.com/prenota-call-sonno'
BOOKING_URL = 'https://scstudioinfermieristico.it/prenota-call-sonno'
OLD_DURATION_LINES = (
    'Circa 60 giorni, completabile entro 75',
    'Circa 60 giorni; conclusione entro 75',
)
DURATION_LINES = (
    'Circa 60 giorni; terza call entro 75 giorni',
    "dall'invio del questionario compilato.",
)


def extend_first_panel(operations):
    # Give the added second line the same bottom padding as the other panels.
    starts = [
        index for index, (args, op) in enumerate(operations)
        if op == b'm' and list(args) == [30, 184]
    ]
    if len(starts) != 1:
        raise ValueError('Unexpected first-page panel geometry')
    index = starts[0]
    while operations[index][1] != b'f*':
        args, op = operations[index]
        if op in {b'm', b'l', b'c'}:
            for coordinate in range(1, len(args), 2):
                if float(args[coordinate]) <= 196:
                    args[coordinate] = FloatObject(float(args[coordinate]) - 6)
        index += 1


def update_pdf(source, destination):
    writer = PdfWriter(clone_from=source)
    if len(writer.pages) != 2:
        raise ValueError('Expected the approved two-page commercial PDF')
    changed = False
    for number, page in enumerate(writer.pages):
        content = page.get_contents()
        operations = content.operations
        matches = [
            index for index, (args, op) in enumerate(operations)
            if op == b'Tj' and str(args[0]) == OLD_DURATION_LINES[number]
        ]
        if matches:
            if len(matches) != 1:
                raise ValueError('Ambiguous duration text')
            index = matches[0]
            operations[index] = ([TextStringObject(DURATION_LINES[0])], b'Tj')
            operations[index + 1:index + 1] = [
                ([], b'T*'), ([TextStringObject(DURATION_LINES[1])], b'Tj'),
            ]
            if number == 0:
                extend_first_panel(operations)
            content.operations = operations
            page.replace_contents(content)
            changed = True
        elif not all(line in page.extract_text() for line in DURATION_LINES):
            raise ValueError('Unexpected PDF wording; review the source before editing')

        for reference in page.get('/Annots', []):
            action = reference.get_object().get('/A')
            if action and action.get('/URI') == OLD_BOOKING_URL:
                action[NameObject('/URI')] = TextStringObject(BOOKING_URL)
                changed = True

    if not changed and source.resolve() == destination.resolve():
        return False
    writer.add_metadata({'/ModDate': datetime.now(timezone.utc).strftime('D:%Y%m%d%H%M%SZ')})
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=destination.parent, suffix='.pdf', delete=False) as stream:
        temporary = Path(stream.name)
    try:
        writer.write(temporary)
        PdfReader(temporary)
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, default=DEFAULT_PDF)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    updated = update_pdf(args.input, args.output or args.input)
    print('PDF aggiornato.' if updated else 'PDF già aggiornato.')


if __name__ == '__main__':
    main()
