"""
app.py — PDF generation service.

One renderer, every form.
  POST /generate-schema-pdf   {schema, values, filename} -> application/pdf
  GET  /health
"""
from flask import Flask, request, send_file, jsonify
from flask_cors import CORS
import io

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

@app.route('/health')
def health():
    return 'ok'

if __name__ == '__main__':
    app.run(debug=True, port=5050)
