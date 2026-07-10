# Cloud Run image — same Flask app as App Engine, plus a real LaTeX engine
# (App Engine Standard has no apt-get access, so PDF report generation there
# can only degrade gracefully; Cloud Run's Dockerfile lets us install TeX Live).
FROM python:3.10-slim

# Scoped TeX Live install (not texlive-full, which is several GB) — covers every
# package used by backend/report_generator.py and backend/financial_report_pdf.py:
# geometry, graphicx, amssymb, xcolor, enumitem, booktabs, array, tabularx,
# helvet, fancyhdr, hyperref.
RUN apt-get update && apt-get install -y --no-install-recommends \
    texlive-latex-base \
    texlive-latex-recommended \
    texlive-latex-extra \
    texlive-fonts-recommended \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PORT=8080
EXPOSE 8080

CMD exec gunicorn -b :$PORT --workers 1 --threads 8 --timeout 120 app:app
