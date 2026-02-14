FROM python:3.12-slim

WORKDIR /app

RUN addgroup --system appgroup && adduser --system --ingroup appgroup appuser

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
# Build version: 2026-02-14-v2
RUN chown -R appuser:appgroup /app

USER appuser

ENV FLASK_APP=run.py
ENV FLASK_ENV=production
ENV DATABASE_URL=postgresql://premia:premia@db:5432/premia

EXPOSE 5000

CMD ["sh", "-c", "flask db upgrade && gunicorn --bind 0.0.0.0:5000 --workers 4 --worker-class gevent --timeout 120 run:app"]
