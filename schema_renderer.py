"""
schema_renderer.py — renders {schema, values} into a PDF.

One renderer for every form. See SCHEMA.md for the contract.
White paper, cheap to print.
"""
import io
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_RIGHT, TA_CENTER
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, PageBreak,
)
from reportlab.pdfbase.pdfmetrics import stringWidth

MARGIN = 18 * mm
PW = A4[0] - 2 * MARGIN

INK   = colors.HexColor('#1a1814')
SOFT  = colors.HexColor('#504840')
ACC   = colors.HexColor('#2c4a52')
HEAD  = colors.HexColor('#eeeeee')
RULE  = colors.HexColor('#b8b0a6')
TINT  = colors.HexColor('#f7f7f7')
NOTE  = colors.HexColor('#f5f8fa')
WHITE = colors.white

FN, FB, FI = 'Helvetica', 'Helvetica-Bold', 'Helvetica-Oblique'


def _s(name, **kw):
    base = dict(fontName=FN, fontSize=9, leading=12.5, textColor=INK)
    base.update(kw)
    return ParagraphStyle(name, **base)


S_LABEL = _s('label', fontSize=7,   textColor=SOFT, leading=9)
S_VAL   = _s('val',   fontSize=9.5, leading=13)
S_PRE   = _s('pre',   fontSize=9.5, leading=13, fontName=FB)
S_TH    = _s('th',    fontSize=8,   textColor=SOFT, leading=10)
S_TD    = _s('td',    fontSize=9,   leading=12)
S_TITLE = _s('title', fontSize=14,  fontName=FB, alignment=TA_CENTER, leading=18)
S_SUB   = _s('sub',   fontSize=8,   fontName=FI, alignment=TA_CENTER, leading=11, textColor=SOFT)
S_NOTE  = _s('note',  fontSize=8,   fontName=FI, textColor=SOFT, leading=11.5)
S_TINY  = _s('tiny',  fontSize=7.5, fontName=FI, textColor=SOFT, leading=10)
S_BODY  = _s('body',  fontSize=9.5, leading=14.5)
S_FOOT  = _s('foot',  fontSize=7.5, textColor=SOFT, leading=11)


def _gap(n=1.0):
    return Spacer(1, n * 3 * mm)


# ── column widths ───────────────────────────────────────────────────────────
def _column_widths(headers, rows, narrow, flex, fs=9):
    """min word / natural string / content score — see SCHEMA.md."""
    n = len(headers)
    pad = 6 * mm
    narrow = set(narrow or [])

    mins, nats, scores = [], [], []
    for c in range(n):
        cells = [str(headers[c])] + [str(r[c]) if c < len(r) else '' for r in rows]
        widest_word = 0
        for cell in cells:
            for word in cell.split():
                widest_word = max(widest_word, stringWidth(word, FN, fs))
        mins.append(widest_word + pad * 0.6)
        nats.append(max(stringWidth(x, FN, fs) for x in cells) + pad)
        scores.append(sum(stringWidth(x, FN, fs) for x in cells[1:]))

    fx = flex if (flex is not None and 0 <= flex < n) else None

    if sum(nats) <= PW:
        # Everything fits unwrapped. Hand the slack out.
        widths = nats[:]
        slack = PW - sum(nats)
        if fx is not None:
            widths[fx] += slack
        else:
            # weight by content volume AND natural size, so an empty column
            # never swallows the row
            w = [scores[c] + nats[c] if c not in narrow else 0.0 for c in range(n)]
            if sum(w) <= 0:
                w = [1.0] * n
            for c in range(n):
                widths[c] += slack * w[c] / sum(w)
        return widths

    # Too wide: start every column at its unbreakable minimum, then hand out
    # what is left in proportion to content volume, capping at natural width.
    # This is what stops one long single string (a Grade cell) from starving
    # a column that carries far more total text (a Subject cell).
    widths = mins[:]
    slack = PW - sum(mins)
    if slack <= 0:
        return widths

    open_cols = set(range(n))
    weights = [max(scores[c], 1.0) for c in range(n)]
    if fx is not None:
        weights[fx] *= 1.5  # explicit flex gets a thumb on the scale

    for _ in range(n + 1):
        pool = sum(weights[c] for c in open_cols)
        if not open_cols or pool <= 0 or slack <= 0.5:
            break
        spilled = 0.0
        for c in list(open_cols):
            want = widths[c] + slack * weights[c] / pool
            if want >= nats[c]:
                spilled += want - nats[c]
                widths[c] = nats[c]
                open_cols.discard(c)
            else:
                widths[c] = want
        slack = spilled
    return widths


# ── components ──────────────────────────────────────────────────────────────
def _sec_bar(text):
    t = Table([[Paragraph(text.upper(), _s('sb', fontSize=8, fontName=FB,
                                           textColor=WHITE, leading=10))]],
              colWidths=[PW])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), ACC),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
    ]))
    return t


def _field_row(fields, values):
    if not fields:
        return _gap(0.5)

    weights, cells, pre_flags = [], [], []
    for f in fields:
        v = str(values.get(f.get('id', ''), f.get('default', '')) or '')
        lbl = f.get('label', '')
        weights.append(max(stringWidth(lbl.upper(), FN, 7),
                           stringWidth(v, FN, 9.5)) + 9 * mm)
        pre = bool(f.get('prefill'))
        pre_flags.append(pre)
        cells.append([Paragraph(lbl.upper(), S_LABEL),
                      Paragraph(v, S_PRE if pre else S_VAL)])

    total = sum(weights) or 1
    widths = [PW * w / total for w in weights]

    t = Table([cells], colWidths=widths)
    style = [
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
    ]
    for i, pre in enumerate(pre_flags):
        style.append(('LINEBELOW', (i, 1), (i, 1), 0.4, ACC if pre else RULE))
    t.setStyle(TableStyle(style))
    return t


def _table(comp, values):
    tid = comp.get('id', '')
    headers = comp.get('headers', [])
    rows = values.get(tid) or comp.get('rows') or []
    rows = [r for r in rows if any(str(c).strip() for c in r)]
    if not rows:
        rows = [['—'] * len(headers)]

    widths = _column_widths(headers, rows, comp.get('narrow'), comp.get('flex'))

    data = [[Paragraph(str(h), S_TH) for h in headers]]
    for r in rows:
        data.append([Paragraph(str(r[c]) if c < len(r) else '', S_TD)
                     for c in range(len(headers))])

    t = Table(data, colWidths=widths, repeatRows=1)
    style = [
        ('BACKGROUND', (0, 0), (-1, 0), HEAD),
        ('LINEBELOW', (0, 0), (-1, 0), 0.5, RULE),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('LEFTPADDING', (0, 0), (-1, -1), 3),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]
    for i in range(1, len(rows) + 1):
        if i % 2 == 0:
            style.append(('BACKGROUND', (0, i), (-1, i), TINT))
    t.setStyle(TableStyle(style))

    out = [t]

    # totals — label spans every column except the last, so the figure lands
    # flush under the figures above it
    totals = comp.get('totals') or []
    if totals:
        val_w = widths[-1]
        lbl_w = sum(widths[:-1])
        for i, tot in enumerate(totals):
            key = f'{tid}__t{i}'
            val = str(values.get(key, tot.get('value', '')) or '')
            combined = len(tot.get('of', ['self'])) > 1 or tot.get('emphasis')
            ls = _s(f'tl{i}', fontSize=9, alignment=TA_RIGHT, leading=12,
                    textColor=INK if combined else SOFT,
                    fontName=FB if combined else FI)
            vs = _s(f'tv{i}', fontSize=10, fontName=FB, leading=13)
            row = Table([[Paragraph(tot.get('label', ''), ls),
                          Paragraph(val, vs)]],
                        colWidths=[lbl_w - 1 * mm, val_w + 1 * mm])
            row.setStyle(TableStyle([
                ('TOPPADDING', (0, 0), (-1, -1), 4),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
                ('LEFTPADDING', (0, 0), (-1, -1), 0),
                ('RIGHTPADDING', (0, 0), (-1, -1), 3),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('LINEABOVE', (0, 0), (-1, 0),
                 1.2 if combined else 0.4, INK if combined else RULE),
            ]))
            out.append(row)
    return out


def _note(text):
    inner = Table([[Paragraph(text, S_NOTE)]], colWidths=[PW])
    inner.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), NOTE),
        ('BOX', (0, 0), (-1, -1), 0.3, RULE),
        ('LINEBEFORE', (0, 0), (0, -1), 2.5, ACC),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
    ]))
    return inner


def _textarea(comp, values):
    out = []
    if comp.get('instruction'):
        out += [Paragraph(comp['instruction'], S_TINY), _gap(0.4)]

    text = str(values.get(comp.get('id', ''), comp.get('default', '')) or '')
    paras = [p.strip() for p in text.split('\n') if p.strip()]
    inner = []
    for i, p in enumerate(paras):
        inner.append(Paragraph(p, S_BODY))
        if i < len(paras) - 1:
            inner.append(Spacer(1, 5))

    box = Table([[inner or Paragraph('', S_BODY)]], colWidths=[PW])
    box.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), 0.5, RULE),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
    ]))
    out.append(box)
    return out


def _signature():
    mid = PW - (22 + 18 + 55) * mm
    t = Table([[Paragraph('<b>Signature:</b>', S_FOOT), '',
                Paragraph('<b>Date:</b>', S_FOOT), '']],
              colWidths=[22 * mm, mid, 18 * mm, 55 * mm])
    t.setStyle(TableStyle([
        ('LINEBELOW', (1, 0), (1, 0), 0.5, RULE),
        ('LINEBELOW', (3, 0), (3, 0), 0.5, RULE),
        ('VALIGN', (0, 0), (-1, -1), 'BOTTOM'),
        ('TOPPADDING', (0, 0), (-1, -1), 14),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
    ]))
    return t


# ── page furniture ──────────────────────────────────────────────────────────
def _page_furniture(schema):
    ref = schema.get('reference', '')
    protect = schema.get('protect', True)

    def draw(canvas, doc):
        if not protect:
            return
        canvas.saveState()
        y = A4[1] - MARGIN
        canvas.setFont(FN, 7.5)
        canvas.setFillColor(SOFT)
        canvas.drawString(MARGIN, y, 'PROTECT – PERSONAL DATA')
        canvas.drawRightString(MARGIN + PW, y, ref)
        canvas.setStrokeColor(INK)
        canvas.setLineWidth(1.2)
        canvas.line(MARGIN, y - 3, MARGIN + PW, y - 3)
        canvas.restoreState()

    return draw


# ── entry point ─────────────────────────────────────────────────────────────
def render_schema(schema, values):
    values = values or {}
    buf = io.BytesIO()
    protect = schema.get('protect', True)

    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=MARGIN, rightMargin=MARGIN,
        topMargin=MARGIN + (7 * mm if protect else 0),
        bottomMargin=MARGIN,
        title=schema.get('title', 'Form'),
    )

    story = []
    if schema.get('title'):
        story += [Paragraph(schema['title'].upper(), S_TITLE), Spacer(1, 2)]
    if schema.get('subtitle'):
        story += [Paragraph(schema['subtitle'], S_SUB)]
    story += [_gap(1.6)]

    for comp in schema.get('sections', []):
        kind = comp.get('type')

        if kind == 'sec_bar':
            story += [_sec_bar(comp.get('text', '')), _gap(0.5)]
        elif kind == 'field_row':
            story += [_field_row(comp.get('fields', []), values), _gap(0.4)]
        elif kind == 'table':
            story += _table(comp, values) + [_gap(0.6)]
        elif kind == 'note':
            story += [_note(comp.get('text', '')), _gap(0.7)]
        elif kind == 'textarea':
            story += _textarea(comp, values) + [_gap(0.8)]
        elif kind == 'signature':
            story += [_signature()]
        elif kind == 'divider':
            story += [HRFlowable(width=PW, thickness=0.4, color=RULE,
                                 spaceBefore=3 * mm, spaceAfter=3 * mm)]
        elif kind == 'page_break':
            story += [PageBreak()]
        elif kind == 'text':
            story += [Paragraph(comp.get('text', ''), S_TINY), _gap(0.5)]
        elif kind == 'spacer':
            story += [_gap(float(comp.get('size', 1)))]

    footer = schema.get('footer') or {}
    if footer:
        story += [HRFlowable(width=PW, thickness=0.8, color=INK,
                             spaceBefore=3 * mm, spaceAfter=2 * mm)]
        if footer.get('return_to'):
            story += [Paragraph(f"<b>Return to:</b> {footer['return_to']}", S_FOOT)]
        for line in footer.get('lines', []):
            story += [Paragraph(line, S_FOOT)]

    draw = _page_furniture(schema)
    doc.build(story, onFirstPage=draw, onLaterPages=draw)
    return buf
