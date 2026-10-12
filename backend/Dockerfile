# syntax=docker/dockerfile:1
FROM python:3.12.15-slim-trixie@sha256:a6e34c598f2467ed0e9a8d349809fcd8b5c603269512df273a0bb1784edc11b1 AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPATH=/app
WORKDIR /app

# The pinned base predates the Debian liblzma security update. Upgrade only the
# affected runtime library without adding packages or weakening apt signatures.
RUN apt-get update \
    && apt-get install --yes --no-install-recommends --only-upgrade liblzma5 \
    && rm -rf /var/lib/apt/lists/*

RUN addgroup --system app && adduser --system --ingroup app app
COPY requirements.txt /tmp/requirements.txt
# The optional CA bundle supports TLS-verifying builds behind an HTTPS proxy.
# Verify the approved installer before use; the application needs no installer.
RUN --mount=type=secret,id=proxy_ca \
    set -eu; \
    if [ -f /run/secrets/proxy_ca ]; then export PIP_CERT=/run/secrets/proxy_ca; fi; \
    printf '%s\n' 'pip==26.2 --hash=sha256:931c303696af6fa3417112103b1cad26890e5a07eccb5b99783700e33f2b8aad' \
        | python -m pip install --no-cache-dir --only-binary=:all: --no-deps --require-hashes -r /dev/stdin; \
    python -c 'import pip; assert pip.__version__ == "26.2", pip.__version__'; \
    python -m pip install --no-cache-dir -r /tmp/requirements.txt; \
    python -m pip check; \
    python -m pip uninstall --yes pip; \
    rm -rf /usr/local/lib/python3.12/ensurepip /tmp/requirements.txt
COPY alembic.ini /app/alembic.ini
COPY alembic /app/alembic
COPY app /app/app
COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint
RUN chmod 0755 /usr/local/bin/docker-entrypoint && chown -R app:app /app

USER app
ENTRYPOINT ["docker-entrypoint"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
