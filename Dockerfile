# One image serves both the Streamlit app and the one-shot ingestion job.
FROM docker.io/library/python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

RUN useradd --create-home --uid 1000 app

# Install dependencies against a stub package first so this layer is only
# rebuilt when pyproject.toml changes, not on every source edit. The install is
# editable because AppPaths resolves the project root from the package location.
COPY pyproject.toml README.md ./
RUN mkdir -p src/amu_admissions_rag \
    && touch src/amu_admissions_rag/__init__.py \
    && pip install -e .

COPY . .
RUN mkdir -p data/processed data/review && chown -R app:app data

USER app

EXPOSE 8501

CMD ["streamlit", "run", "streamlit_app.py", \
     "--server.address=0.0.0.0", "--server.port=8501", "--server.headless=true"]
