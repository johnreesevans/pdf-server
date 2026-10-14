"""
app.py — PDF generation service.

One renderer, every form.
  POST /generate-schema-pdf   {schema, values, filename} -> application/pdf
  POST /html-pdf              {html, title, prepared_by, contact, date, logo, filename}
                              -> application/pdf   (needs header X-PDF-Key = PDF_KEY)
  GET  /health
"""
from flask import Flask, request, send_file, jsonify
from flask_cors import CORS
import hmac
import io
import os

from schema_renderer import render_schema

app = Flask(__name__)
CORS(app)

@app.route('/generate-schema-pdf', methods=['POST','OPTIONS'])
def generate_schema_pdf():
    if request.method == 'OPTIONS':
        return '', 204
    try:
        body   = request.get_json(force=True)
        schema = body.get('schema', {})
        values = body.get('values', {})
        fname  = body.get('filename', 'form.pdf')
        buf    = render_schema(schema, values)
        buf.seek(0)
        return send_file(buf, mimetype='application/pdf',
                         as_attachment=True,
                         download_name=fname)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/html-pdf', methods=['POST'])
def html_pdf():
    # Server to server only (tk.sas.vc), so it is locked with a key rather than
    # opened to browsers: it fetches the images named in the HTML.
    key = os.environ.get('PDF_KEY', '')
    if not key or not hmac.compare_digest(key, request.headers.get('X-PDF-Key', '')):
        return jsonify({'error': 'Not allowed'}), 403
    try:
        from html_renderer import render_climb_pdf   # loaded only when used
        body = request.get_json(force=True) or {}
        buf = render_climb_pdf(
            body.get('html', ''),
            title=body.get('title', 'Your Kilimanjaro climb'),
            prepared_by=body.get('prepared_by', ''),
            contact=body.get('contact', ''),
            date_text=body.get('date', ''),
            logo_url=body.get('logo', ''),
        )
        return send_file(buf, mimetype='application/pdf', as_attachment=True,
                         download_name=body.get('filename', 'climb.pdf'))
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/health')
def health():
    return 'ok'

if __name__ == '__main__':
    app.run(debug=True, port=5050)
