FROM python:3.11-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PYTHONDONTWRITEBYTECODE=1 \
    TESTPILOT_CACHE_DIR=/tmp/testpilot/cache TESTPILOT_WORK_DIR=/tmp/testpilot/work
COPY requirements.txt requirements-dev.txt ./
RUN pip install -r requirements-dev.txt
RUN useradd --create-home --uid 1000 pilot
COPY --chown=pilot:pilot . .
USER pilot
ENTRYPOINT ["python", "-m", "testpilot.cli"]
CMD ["--help"]
