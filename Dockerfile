# The PDF service: reportlab for the forms, WeasyPrint for the climb pages.
# WeasyPrint needs Pango and HarfBuzz from the system, which this installs.
FROM python:3.12-slim

RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz0b libharfbuzz-subset0 \
      fontconfig fonts-dejavu-core shared-mime-info \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

CMD gunicorn app:app --bind 0.0.0.0:${PORT:-8080} --workers 2 --timeout 90
