"""
html_renderer.py — a client's climb page as a professionally typeset PDF.

The composer on tk.sas.vc sends the same HTML it publishes as the client's web
page. It is wrapped here in a print layout (A4, a cover band with the logo,
running footer with the coordinator's details and "Page 2 of 9") and typeset by
WeasyPrint, so the text is real, selectable text in Outfit, photos and price
tables are never split across pages, and headings stay with what follows them.

Fonts are bundled in ./fonts so the PDF never depends on Google Fonts.
"""
import html as _html
import io
import os

from weasyprint import HTML

HERE = os.path.dirname(os.path.abspath(__file__))

PRINT_CSS = """
@font-face{font-family:Outfit;src:url(fonts/Outfit-Regular.ttf);font-weight:400}
@font-face{font-family:Outfit;src:url(fonts/Outfit-Medium.ttf);font-weight:500}
@font-face{font-family:Outfit;src:url(fonts/Outfit-SemiBold.ttf);font-weight:600}
@font-face{font-family:Outfit;src:url(fonts/Outfit-Bold.ttf);font-weight:700}

@page{
  size:A4; margin:22mm 18mm 22mm 18mm;
  @bottom-left{content:__FOOTER__;font:400 7.8pt Outfit;color:#6B7280}
  @bottom-right{content:"Page " counter(page) " of " counter(pages);font:400 7.8pt Outfit;color:#6B7280}
}
@page :first{ margin-top:12mm }

html{font-family:Outfit,sans-serif;color:#2B3340}
body{margin:0;font-size:10.4pt;line-height:1.55}

/* cover band */
.band{display:flex;align-items:center;justify-content:space-between;
  border-bottom:2pt solid #D98A1C;padding:0 0 9pt;margin:0 0 16pt}
.band img{height:34pt}
.band .who{text-align:right;font-size:8.6pt;color:#6B7280;line-height:1.4}
.band .who b{color:#111827;font-weight:600}
h1.title{font:600 22pt/1.15 Outfit;letter-spacing:-.02em;color:#111827;margin:0 0 3pt}
h1.title span{color:#D98A1C}
.sub{font-size:9.5pt;color:#6B7280;margin:0 0 16pt}

/* the letter: written for email with inline styles, re-set for print */
.doc > div{max-width:none !important;font-family:Outfit,sans-serif !important;
  font-size:10.4pt !important;line-height:1.55 !important;color:#2B3340 !important}
.doc p{orphans:3;widows:3}
.doc img{max-width:100% !important;max-height:92mm;width:auto !important;height:auto !important;
  display:block;margin:0 auto;border-radius:6pt;break-inside:avoid}
.doc table, .doc ul, .doc ol, .doc li{break-inside:avoid}
.doc p[style*="font-weight:bold"], .doc p[style*="font-weight: bold"]{break-after:avoid}
.doc a{color:#2E4D72;text-decoration:none}
"""


def _css_string(s):
    """A safe CSS string literal for the page footer."""
    return '"' + s.replace('\\', '\\\\').replace('"', '\\"').replace('\n', ' ') + '"'


def render_climb_pdf(body_html, title='Your Kilimanjaro climb', prepared_by='',
                     contact='', date_text='', logo_url=''):
    """Return a BytesIO holding the PDF."""
    esc = _html.escape
    t = esc(title or 'Your Kilimanjaro climb')
    footer = ' · '.join(x for x in ['Team Kilimanjaro', prepared_by, contact] if x)
    who = ''
    if prepared_by:
        who = '<div class="who">Prepared by <b>%s</b>%s%s</div>' % (
            esc(prepared_by),
            ('<br>' + esc(contact)) if contact else '',
            ('<br>' + esc(date_text)) if date_text else '')
    logo = ('<img src="%s" alt="Team Kilimanjaro">' % esc(logo_url)) if logo_url else '<b>Team Kilimanjaro</b>'
    doc = ('<!doctype html><html lang="en-GB"><head><meta charset="utf-8"><style>%s</style></head><body>'
           '<div class="band">%s%s</div>'
           '<h1 class="title">%s<span>.</span></h1>'
           '<article class="doc">%s</article>'
           '</body></html>') % (PRINT_CSS.replace('__FOOTER__', _css_string(footer)), logo, who, t, body_html)
    buf = io.BytesIO()
    HTML(string=doc, base_url=HERE + '/').write_pdf(buf)
    buf.seek(0)
    return buf
