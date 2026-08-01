#!/usr/bin/env python3
"""
test_render.py — regression guard for schema_renderer.py

Renders forms/waiver.json and asserts the layout invariants that broke
repeatedly during the original build. Run after ANY renderer change:

    python3 test_render.py

Exit 0 = safe. Exit 1 = you have regressed something expensive.
"""
import json
import os
import re
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from schema_renderer import render_schema  # noqa: E402

FAILS = []


def check(label, ok, detail=''):
    print(f"  {'PASS' if ok else 'FAIL'}  {label}")
    if not ok:
        FAILS.append(f'{label}{" — " + detail if detail else ""}')


def compute_values(schema):
    """Mirror what form.html's collect() sends."""
    values, tables = {}, {}
    for comp in schema['sections']:
        kind = comp.get('type')
        if kind == 'table':
            tables[comp['id']] = comp
            values[comp['id']] = comp.get('rows', [])
        elif kind == 'field_row':
            for f in comp['fields']:
                values[f['id']] = f.get('default', '')
        elif kind == 'textarea':
            values[comp['id']] = comp.get('default', '')

    def col_sum(tid):
        sc = tables[tid].get('sum_col')
        if sc is None:
            return 0.0
        total = 0.0
        for row in values[tid]:
            try:
                total += float(row[sc])
            except (ValueError, IndexError, TypeError):
                pass
        return total

    for tid, comp in tables.items():
        for i, tot in enumerate(comp.get('totals', [])):
            of = tot.get('of', ['self'])
            srcs = [tid] if of == ['self'] else of
            v = sum(col_sum(s) for s in srcs)
            values[f'{tid}__t{i}'] = str(int(v)) if v == int(v) else str(v)
    return values, tables


def main():
    schema = json.load(open(os.path.join(HERE, 'forms', 'waiver.json')))
    values, tables = compute_values(schema)

    buf = render_schema(schema, values)
    data = buf.getvalue()

    print('\nRendering forms/waiver.json …\n')
    check('PDF produced', data.startswith(b'%PDF') and len(data) > 5000,
          f'{len(data)} bytes')

    tmp = tempfile.mktemp(suffix='.pdf')
    open(tmp, 'wb').write(data)
    try:
        text = subprocess.run(['pdftotext', '-layout', tmp, '-'],
                              capture_output=True, text=True).stdout
    except FileNotFoundError:
        print('\n  (pdftotext unavailable — text assertions skipped)')
        text = None

    if text:
        lines = text.split('\n')

        # 1. Totals: label and figure on ONE line. This broke for hours under
        #    jsPDF autoTable and again when the label column was a fixed %.
        for tid, comp in tables.items():
            for i, tot in enumerate(comp.get('totals', [])):
                label = re.sub(r'<[^>]+>', '', tot.get('label', '')).strip()
                expect = values[f'{tid}__t{i}']
                hit = [l for l in lines if label in l]
                check(f'total intact on one line: "{label}"',
                      bool(hit) and any(expect in l for l in hit),
                      'label wrapped or figure detached')

        # 2. No word broken across lines by an over-tight column.
        check('no hyphen-broken words at line ends',
              not any(re.search(r'[a-z]-$', l.rstrip()) for l in lines))

        # 3. The flex column must actually be wide. The PPL Subject cell
        #    starved to 11 lines when `narrow` was read as "never compress".
        #    Measure the contiguous row block only — a fixed window spills
        #    into the following section and counts unrelated lines.
        ppl = [i for i, l in enumerate(lines) if 'PPL Theoretical' in l]
        if ppl:
            n = 0
            for l in lines[ppl[0]:]:
                if not l.strip():
                    break
                n += 1
            check('PPL Subject column not starved', n <= 5,
                  f'row occupies {n} lines — flex column too narrow')

        # 4. Justification text fully present, not clipped at the box edge.
        check('justification renders to its final word',
              'supporting evidence and footnotes' in text)

        # 5. Every page carries the PROTECT band.
        pages = text.split('\f')
        pages = [p for p in pages if p.strip()]
        check('PROTECT header on every page',
              all('PROTECT' in p for p in pages), f'{len(pages)} pages')

        # 6. Signature block survived to the end.
        check('signature block present', 'Signature:' in text)

    os.path.exists(tmp) and os.remove(tmp)

    print()
    if FAILS:
        print(f'{len(FAILS)} REGRESSION(S):')
        for f in FAILS:
            print('  - ' + f)
        print('\nSee README.md — these invariants were expensive to get right.')
        return 1
    print('All invariants hold.\n')
    return 0


if __name__ == '__main__':
    sys.exit(main())
