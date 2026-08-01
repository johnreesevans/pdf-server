"""
Waiver PDF generator — Flask endpoint.
POST /generate-pdf  with JSON body → returns application/pdf
Deploy to Railway: add this repo, set start command to:
  gunicorn app:app --bind 0.0.0.0:$PORT
"""
from flask import Flask, request, send_file, jsonify
from flask_cors import CORS
import io, json
from pdf_builder import build_pdf

app = Flask(__name__)
CORS(app)

@app.route('/generate-pdf', methods=['POST', 'OPTIONS'])
def generate_pdf():
    if request.method == 'OPTIONS':
        return '', 204
    try:
        data = request.get_json(force=True)
        buf = build_pdf(data)
        buf.seek(0)
        return send_file(
            buf,
            mimetype='application/pdf',
            as_attachment=True,
            download_name='Educational_Waiver_Request_Rees-Evans.pdf'
        )
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/health')
def health():
    return 'ok'

if __name__ == '__main__':
    app.run(debug=True, port=5050)
