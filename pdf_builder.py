"""
pdf_builder.py  —  builds the Army Educational Waiver Request PDF.

Key principle: INTELLIGENT COLUMN WIDTHS
  For every table we measure the natural (unwrapped) pixel width of every
  cell string using the actual font metrics, then allocate page width
  proportionally — wide content gets wide columns, narrow content gets
  narrow columns.  No guessing.
"""
import io
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_RIGHT, TA_CENTER
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, KeepTogether, PageBreak
)
from reportlab.pdfbase.pdfmetrics import stringWidth

PW = A4[0] - 36*mm   # usable page width
MARGIN = 18*mm

# ── Colours ─────────────────────────────────────────────────────────────────
INK       = colors.HexColor('#1a1814')
SOFT      = colors.HexColor('#504840')
ACCENT    = colors.HexColor('#2c4a52')
WARM      = colors.HexColor('#eeeeee')
RULE      = colors.HexColor('#c0b8b0')
WHITE     = colors.white
TINT      = colors.HexColor('#fafafa')
NOTEFILL  = colors.HexColor('#f5f8fa')

# ── Styles ───────────────────────────────────────────────────────────────────
def ps(name, **kw):
    base = dict(fontName='Helvetica', fontSize=9, leading=13,
                textColor=INK, spaceBefore=0, spaceAfter=0)
    base.update(kw)
    return ParagraphStyle(name, **base)

sBody   = ps('body')
sSmall  = ps('small',  fontSize=8,   textColor=SOFT,   leading=11)
sTiny   = ps('tiny',   fontSize=7.5, textColor=SOFT,   leading=10,
             fontName='Helvetica-Oblique')
sLabel  = ps('label',  fontSize=7,   textColor=SOFT,   leading=9,
             fontName='Helvetica', spaceBefore=0)
sVal    = ps('val',    fontSize=9.5, leading=13)
sTH     = ps('th',     fontSize=8,   textColor=SOFT,   leading=10,
             fontName='Helvetica')
sTD     = ps('td',     fontSize=9,   leading=12)
sTDsm   = ps('tdsm',  fontSize=8.5, leading=11.5)
sTot    = ps('tot',    fontSize=9,   textColor=SOFT,   leading=12,
             fontName='Helvetica-Oblique', alignment=TA_RIGHT)
sTotV   = ps('totv',  fontSize=10,  textColor=INK,    leading=13,
             fontName='Helvetica-Bold')
sTitle  = ps('title', fontSize=14,  fontName='Helvetica-Bold',
             alignment=TA_CENTER,  leading=18, textColor=INK)
sSub    = ps('sub',   fontSize=8,   fontName='Helvetica-Oblique',
             alignment=TA_CENTER,  leading=11, textColor=SOFT)
sMeta   = ps('meta',  fontSize=7.5, textColor=SOFT,   leading=11)
sMetaR  = ps('metar', fontSize=7.5, textColor=SOFT,   leading=11,
             alignment=TA_RIGHT)
sNote   = ps('note',  fontSize=8,   fontName='Helvetica-Oblique',
             textColor=SOFT,       leading=11)
sFooter = ps('footer',fontSize=7.5, textColor=SOFT,   leading=11)
sFootB  = ps('footerb',fontSize=7.5,fontName='Helvetica-Bold',
             textColor=INK,        leading=11)

# ── Helpers ──────────────────────────────────────────────────────────────────
def sec_bar(text):
    t = Table([[Paragraph(text.upper(), ps('sh', fontSize=8,
                fontName='Helvetica-Bold', textColor=WHITE,
                leading=10, charSpace=0.3))]],
              colWidths=[PW])
    t.setStyle(TableStyle([
        ('BACKGROUND',    (0,0), (-1,-1), ACCENT),
        ('TOPPADDING',    (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('LEFTPADDING',   (0,0), (-1,-1), 6),
        ('RIGHTPADDING',  (0,0), (-1,-1), 6),
    ]))
    return t

def field_row(pairs):
    """
    pairs = [(label, value), ...]
    Allocates column widths by measuring label+value strings,
    then proportional to max(label_w, value_w) per column.
    """
    if not pairs:
        return Spacer(1, 2*mm)
    # measure
    weights = []
    for lbl, val in pairs:
        lw = stringWidth(lbl.upper(), 'Helvetica', 7)
        vw = stringWidth(str(val),    'Helvetica', 9.5)
        weights.append(max(lw, vw) + 8*mm)  # 8mm breathing room
    total = sum(weights)
    col_w = [PW * w / total for w in weights]

    cells = []
    for (lbl, val), w in zip(pairs, col_w):
        cells.append([
            Paragraph(lbl.upper(), sLabel),
            Paragraph(str(val),    sVal),
        ])

    t = Table([cells], colWidths=col_w)
    t.setStyle(TableStyle([
        ('VALIGN',        (0,0), (-1,-1), 'TOP'),
        ('TOPPADDING',    (0,0), (-1,-1), 2),
        ('BOTTOMPADDING', (0,0), (-1,-1), 3),
        ('LEFTPADDING',   (0,0), (-1,-1), 0),
        ('RIGHTPADDING',  (0,0), (-1,-1), 6),
        ('LINEBELOW',     (0,1), (-1,1),  0.4, RULE),
    ]))
    return t


def smart_table(headers, rows, totals=None, font_size=9, small_cols=None, flex_col=None):
    """
    Build a Table with INTELLIGENT column widths.

    Algorithm:
      1. For each column, measure every cell string (header + all body cells)
         using the actual font at font_size.
      2. Natural width = max string width in that column + padding.
      3. If total natural width fits in PW → use natural widths.
      4. If too wide → identify 'flex' column (longest total content,
         usually the subject/description column) and compress only that one.
      5. small_cols: list of col indices that should be treated as narrow
         (dates, grades, points) — these are never compressed below their
         natural width.

    totals = [(label, value), ...]  drawn as right-aligned rows below table.
    """
    if not rows:
        rows = [['—'] * len(headers)]

    ncols = len(headers)
    PAD   = 6*mm   # left+right cell padding per column

    # measure natural widths
    fn_normal = 'Helvetica'
    fn_bold   = 'Helvetica-Bold'
    fs        = font_size
    fs_head   = fs - 1

    nat = []
    for ci in range(ncols):
        w = stringWidth(str(headers[ci]), fn_bold, fs_head) + PAD
        for row in rows:
            cell = str(row[ci]) if ci < len(row) else ''
            w = max(w, stringWidth(cell, fn_normal, fs) + PAD)
        nat.append(w)

    total_nat = sum(nat)

    if total_nat <= PW:
        col_w = nat[:]
        # distribute leftover to flex col
        leftover = PW - total_nat
        if flex_col is not None:
            flex = flex_col
        else:
            flex = nat.index(max(nat))
        col_w[flex] += leftover
    else:
        # compress: find the column with most total content (flex)
        # don't compress small_cols
        small = set(small_cols or [])
        if flex_col is not None:
            flex = flex_col
        else:
            content_scores = []
            for ci in range(ncols):
                if ci in small:
                    content_scores.append(0)
                else:
                    score = sum(len(str(r[ci])) for r in rows if ci < len(r))
                    content_scores.append(score)
            flex = content_scores.index(max(content_scores))
        fixed = sum(nat[ci] for ci in range(ncols) if ci != flex)
        col_w = nat[:]
        col_w[flex] = max(PW - fixed, 20*mm)

    # build header row
    head_cells = [Paragraph(str(h), sTH) for h in headers]
    data = [head_cells]
    for row in rows:
        data.append([Paragraph(str(row[ci]) if ci < len(row) else '', sTDsm)
                     for ci in range(ncols)])

    t = Table(data, colWidths=col_w, repeatRows=1)
    row_count = len(rows)
    style = [
        ('BACKGROUND',    (0,0),  (-1,0),         WARM),
        ('LINEBELOW',     (0,0),  (-1,0),          0.5, RULE),
        ('TOPPADDING',    (0,0),  (-1,-1),         3),
        ('BOTTOMPADDING', (0,0),  (-1,-1),         3),
        ('LEFTPADDING',   (0,0),  (-1,-1),         3),
        ('RIGHTPADDING',  (0,0),  (-1,-1),         4),
        ('VALIGN',        (0,0),  (-1,-1),         'TOP'),
        ('FONTNAME',      (0,0),  (-1,0),          'Helvetica'),
        ('FONTSIZE',      (0,0),  (-1,0),           fs_head),
        ('FONTNAME',      (0,1),  (-1,-1),         'Helvetica'),
        ('FONTSIZE',      (0,1),  (-1,-1),          fs),
    ]
    # alternate row shading
    for i in range(1, row_count + 1):
        if i % 2 == 0:
            style.append(('BACKGROUND', (0,i), (-1,i), TINT))
    t.setStyle(TableStyle(style))

    elements = [t]

    # totals: label right-aligns to points column, value in points column
    if totals:
        # points column is the last data col (col_w[-1])
        pts_w = col_w[-1]
        lbl_w = PW - pts_w
        for i, (lbl, val) in enumerate(totals):
            rule_w = 1.5 if i > 0 else 0.4
            rule_c = INK if i > 0 else RULE
            is_combined = i > 0
            lbl_style = ps(f'totlbl{i}',
                fontSize=9, textColor=INK if is_combined else SOFT,
                fontName='Helvetica-Bold' if is_combined else 'Helvetica-Oblique',
                leading=12, alignment=TA_RIGHT)
            val_style = ps(f'totval{i}',
                fontSize=10, textColor=INK,
                fontName='Helvetica-Bold', leading=13)
            tot_data = [[Paragraph(lbl, lbl_style), Paragraph(str(val), val_style)]]
            tot_t = Table(tot_data, colWidths=[lbl_w - 2*mm, pts_w + 2*mm])
            tot_style = [
                ('TOPPADDING',    (0,0), (-1,-1), 4),
                ('BOTTOMPADDING', (0,0), (-1,-1), 2),
                ('LEFTPADDING',   (0,0), (-1,-1), 0),
                ('RIGHTPADDING',  (0,0), (-1,-1), 2),
                ('VALIGN',        (0,0), (-1,-1), 'MIDDLE'),
                ('LINEABOVE',     (0,0), (-1,0),  rule_w, rule_c),
            ]
            tot_t.setStyle(TableStyle(tot_style))
            elements.append(tot_t)

    return elements


def note_box(text):
    """Blue-left-bordered note box."""
    inner = Table([[Paragraph(text, sNote)]], colWidths=[PW - 6*mm])
    inner.setStyle(TableStyle([
        ('BACKGROUND',    (0,0), (-1,-1), NOTEFILL),
        ('TOPPADDING',    (0,0), (-1,-1), 5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
        ('LEFTPADDING',   (0,0), (-1,-1), 6),
        ('RIGHTPADDING',  (0,0), (-1,-1), 6),
        ('LINEBEFOREAND', (0,0), (-1,-1), 2.5, ACCENT),
    ]))
    outer = Table([[inner]], colWidths=[PW])
    outer.setStyle(TableStyle([
        ('LINEBEFOREBORDER', (0,0), (-1,-1), 2.5, ACCENT),
        ('BOX',              (0,0), (-1,-1), 0.3, RULE),
        ('BACKGROUND',       (0,0), (-1,-1), NOTEFILL),
        ('TOPPADDING',       (0,0), (-1,-1), 0),
        ('BOTTOMPADDING',    (0,0), (-1,-1), 0),
        ('LEFTPADDING',      (0,0), (-1,-1), 0),
        ('RIGHTPADDING',     (0,0), (-1,-1), 0),
    ]))
    return outer


# ── Main builder ─────────────────────────────────────────────────────────────
def build_pdf(d):
    """
    d = dict from the HTML form JSON POST.
    Returns a BytesIO containing the PDF.
    """
    buf = io.BytesIO()

    def on_page(canvas, doc):
        """Header on every page after the first."""
        pass  # header is inline in story for page 1; later pages use frames

    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=MARGIN, rightMargin=MARGIN,
        topMargin=MARGIN, bottomMargin=MARGIN,
        title='Educational Waiver Request — John Rees-Evans',
    )

    def SP(n=1): return Spacer(1, n * 3*mm)
    def HR(): return HRFlowable(width=PW, thickness=0.4, color=RULE,
                                spaceAfter=2*mm, spaceBefore=1*mm)

    def g(key, default=''):
        return str(d.get(key, default) or default).strip()

    story = []

    # ── Page header (page 1) ─────────────────────────────────────────────────
    meta = Table(
        [[Paragraph('PROTECT – PERSONAL DATA<br/><i>Handle in accordance with Data Protection Act 2018</i>', sMeta),
          Paragraph('D-ARMY-864 (Revised 10 Sep 20)<br/><i>Educational Waiver Request Form</i>', sMetaR)]],
        colWidths=[PW*0.55, PW*0.45]
    )
    meta.setStyle(TableStyle([
        ('VALIGN',        (0,0), (-1,-1), 'TOP'),
        ('LEFTPADDING',   (0,0), (-1,-1), 0),
        ('RIGHTPADDING',  (0,0), (-1,-1), 0),
        ('TOPPADDING',    (0,0), (-1,-1), 0),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('LINEBELOW',     (0,0), (-1,0),  1.2, INK),
    ]))
    story += [meta, SP(1.5)]

    story += [
        Paragraph('EDUCATIONAL WAIVER REQUEST', sTitle),
        Spacer(1, 2),
        Paragraph('British Army Officer Entry &nbsp;·&nbsp; Complete all sections and return as PDF to RG-NRCAPTOfficer@mod.gov.uk', sSub),
        SP(2),
    ]

    # ── CANDIDATE PARTICULARS ────────────────────────────────────────────────
    story += [sec_bar('Candidate Particulars'), SP(0.5)]
    story += [field_row([('Forenames', 'John'), ('Surname', 'Rees-Evans')]), SP(0.5)]
    story += [field_row([
        ('Date of Birth',     '13/04/1978'),
        ('Current Age',       '48'),
        ('Candidate URN',     '2000005020715'),
        ('Type of Commission','Reserve'),
    ]), SP(0.5)]
    story += [field_row([('Current Occupation / Employment', g('occ'))]), SP(1)]

    # ── SECONDARY SCHOOLING ──────────────────────────────────────────────────
    story += [sec_bar('Secondary Level Schooling (Ages 11–16)'), SP(0.5)]
    story += [field_row([
        ('School Name',    g('s1n')),
        ('Location',       g('s1l')),
        ('Type',           g('s1t')),
        ('Years Attended', g('s1y')),
    ]), SP(1)]

    # ── GCSE TABLE ───────────────────────────────────────────────────────────
    story += [sec_bar('GCSE Qualifications (or Level 2 Equivalents)'), SP(0.5)]
    gcse_rows = d.get('gcse_rows', [])
    gcse_tot  = g('gcse_total', '69')
    story += smart_table(
        ['Type', 'Subject', 'Date Awarded', 'Grade', 'ALIS Points'],
        gcse_rows,
        totals=[('Total ALIS Points:', gcse_tot)],
        small_cols=[0, 2, 3, 4],   # type, date, grade, points stay natural
    )
    story += [SP(0.5), Paragraph(
        'ALIS Points: A*/9 = 8 &nbsp;·&nbsp; Low A*/High A/8 = 7.5 &nbsp;·&nbsp; '
        'A/7 = 7 &nbsp;·&nbsp; B/6 = 6 &nbsp;·&nbsp; C/4&amp;5 = 5 &nbsp;·&nbsp; D/3 = 4',
        sTiny), SP(1)]

    # ── PAGE BREAK ───────────────────────────────────────────────────────────
    story.append(PageBreak())

    # Page 2 header
    meta2 = Table(
        [[Paragraph('PROTECT – PERSONAL DATA', sMeta),
          Paragraph('D-ARMY-864 (Revised 10 Sep 20)', sMetaR)]],
        colWidths=[PW*0.55, PW*0.45]
    )
    meta2.setStyle(TableStyle([
        ('VALIGN',        (0,0), (-1,-1), 'TOP'),
        ('LEFTPADDING',   (0,0), (-1,-1), 0),
        ('RIGHTPADDING',  (0,0), (-1,-1), 0),
        ('TOPPADDING',    (0,0), (-1,-1), 0),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('LINEBELOW',     (0,0), (-1,0),  1.2, INK),
    ]))
    story += [meta2, SP(1)]

    # ── POST-16 ──────────────────────────────────────────────────────────────
    story += [sec_bar('Post-16 Education — A Level / AS Qualifications (Level 3)'), SP(0.5)]

    # Matric equivalency note
    story += [note_box(
        '<b>Note:</b> A communication from Army Recruitment dated 31 July 2026 confirmed '
        'that the South African National Senior Certificate (Matriculation) is recognised '
        'as equivalent to UK AS Levels for this application. UCAS points for Matriculation '
        'subjects are calculated on that basis.'
    ), SP(1)]

    # North Devon College
    story += [field_row([
        ('Establishment Name', g('s2n')),
        ('Location',           g('s2l')),
        ('Type',               g('s2t')),
        ('Years Attended',     g('s2y')),
    ]), SP(0.5)]
    al_rows = d.get('al_rows', [])
    al_tot  = g('al_total', '40')
    story += smart_table(
        ['Type', 'Subject', 'Date Awarded', 'Grade', 'UCAS Points'],
        al_rows,
        totals=[('North Devon College sub-total:', al_tot)],
        small_cols=[0, 2, 3, 4],
    )
    story += [HR()]

    # Jeppe Boys High School
    story += [field_row([
        ('Establishment Name (SA — Matriculation)', g('s3n')),
        ('Location',                                g('s3l')),
        ('Type',                                    g('s3t')),
        ('Years Attended',                          g('s3y')),
    ]), SP(0.5)]
    mat_rows  = d.get('mat_rows', [])
    mat_tot   = g('mat_total', '58')
    combined  = g('combined_total', '98')
    story += smart_table(
        ['Type', 'Subject', 'Date Awarded', 'Grade', 'UCAS Points'],
        mat_rows,
        totals=[
            ('Jeppe Boys High School sub-total:', mat_tot),
            ('Combined UCAS Points (both institutions):', combined),
        ],
        small_cols=[0, 2, 3, 4],
    )
    story += [SP(0.5)]
    story += [field_row([('Note on South African Matriculation', g('mat_note'))]), SP(1)]

    # ── UNIVERSITY ───────────────────────────────────────────────────────────
    story += [sec_bar('University / Higher Education (if applicable)'), SP(0.5)]
    story += smart_table(
        ['Establishment', 'Qualification', 'Subject', 'Grade', 'Years'],
        d.get('uni_rows', []),
        small_cols=[1, 2, 4],
    )
    story += [SP(1)]

    # ── OTHER QUALIFICATIONS ─────────────────────────────────────────────────
    story += [sec_bar('Other Academic Qualifications of Relevance to Waiver'), SP(0.5)]
    story += smart_table(
        ['Awarding Body', 'Qualification', 'Subject', 'Grade', 'Years'],
        d.get('oth_rows', []),
        small_cols=[0, 1, 3, 4],
        flex_col=2,
    )
    story += [SP(1)]

    # ── PROFESSIONAL BODIES ──────────────────────────────────────────────────
    story += [sec_bar('Membership of Professional Bodies'), SP(0.5)]
    prof = d.get('prof_rows', []) or [['None', '', '']]
    story += smart_table(
        ['Professional Body', 'Type / Level of Membership', 'Additional Information'],
        prof,
    )
    story += [SP(1)]

    # ── Page 3 header (no forced break — let reportlab flow) ─────────────


    # ── JUSTIFICATION ────────────────────────────────────────────────────────
    story += [sec_bar('Justification for Educational Waiver'), SP(0.5)]
    story += [field_row([
        ('Reason for Educational Waiver',    g('reason1')),
        ('Secondary Reason (if applicable)', g('reason2')),
    ]), SP(0.5)]
    story += [Paragraph(
        'State fully the grounds upon which the waiver is being requested. '
        'Include any mitigating circumstances. Attach supporting documents as '
        'separate PDFs. The SEA will rely entirely on what is provided here.',
        sTiny), SP(0.5)]

    # Justification text box
    just_text = g('justification')
    # Split paragraphs on newlines
    paras = [p.strip() for p in just_text.split('\n') if p.strip()]
    just_content = []
    for p in paras:
        just_content.append(Paragraph(p, ps('jp', fontSize=9.5, leading=15, textColor=INK)))
        just_content.append(Spacer(1, 4))
    if just_content and isinstance(just_content[-1], Spacer):
        just_content.pop()

    just_inner = Table(
        [[just_content]],
        colWidths=[PW - 8*mm]
    )
    just_inner.setStyle(TableStyle([
        ('BACKGROUND',    (0,0), (-1,-1), colors.HexColor('#fcfcfc')),
        ('BOX',           (0,0), (-1,-1), 0.5, RULE),
        ('TOPPADDING',    (0,0), (-1,-1), 8),
        ('BOTTOMPADDING', (0,0), (-1,-1), 8),
        ('LEFTPADDING',   (0,0), (-1,-1), 8),
        ('RIGHTPADDING',  (0,0), (-1,-1), 8),
    ]))
    story += [just_inner, SP(1.5)]

    # ── SUBMISSION FOOTER ────────────────────────────────────────────────────
    story += [HRFlowable(width=PW, thickness=0.8, color=INK,
                         spaceAfter=4, spaceBefore=0)]
    story += [
        Paragraph('<b>Return to:</b> RG-NRCAPTOfficer@mod.gov.uk', sFooter),
        Paragraph('Include this form and all supporting documentation as separate PDF attachments.', sFooter),
        Paragraph('<i>Any personal information provided will be dealt with in the strictest confidence.</i>', sFooter),
        SP(2),
    ]

    # Signature line
    sig = Table(
        [[Paragraph('<b>Signature:</b>', sFooter), '', Paragraph('<b>Date:</b>', sFooter), '']],
        colWidths=[22*mm, 80*mm, 18*mm, PW - 120*mm]
    )
    sig.setStyle(TableStyle([
        ('LINEBELOW',     (1,0), (1,0), 0.5, RULE),
        ('LINEBELOW',     (3,0), (3,0), 0.5, RULE),
        ('VALIGN',        (0,0), (-1,-1), 'BOTTOM'),
        ('TOPPADDING',    (0,0), (-1,-1), 10),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('LEFTPADDING',   (0,0), (-1,-1), 0),
        ('RIGHTPADDING',  (0,0), (-1,-1), 0),
    ]))
    story += [sig]

    doc.build(story)
    return buf
