# The receiver and the board: one image, two commands. Build from the
# repository root: docker build -f app/Dockerfile .
#
#   python -m record_consumers.receiver
#   python -m record_consumers.board
#
# The base image is pinned by tag and digest; change both together. Every
# Python package is installed from requirements.txt with its hash checked.

FROM python:3.13-slim@sha256:e48f59cdba69a3cbd9ed2cf0f348d90d45a8d350d98134cf1070bc106ee9ed90 AS base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app
COPY app/requirements.txt .
RUN pip install --require-hashes -r requirements.txt
COPY app/record_consumers record_consumers

# docker build --target test: the same image with pytest and the tests.
FROM base AS test
COPY app/requirements-test.txt .
RUN pip install --require-hashes -r requirements-test.txt
COPY app/tests tests
COPY samples samples
USER 10001:10001
CMD ["python", "-m", "pytest", "-q", "-p", "no:cacheprovider", "tests"]

FROM base
LABEL org.opencontainers.image.source="https://github.com/USAREUR-AF/hello-galaxy-record-consumers" \
      org.opencontainers.image.licenses="Apache-2.0"
# A numeric user, so that Kubernetes can check runAsNonRoot.
USER 10001:10001
EXPOSE 8080
CMD ["python", "-m", "record_consumers.receiver"]
