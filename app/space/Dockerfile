# Container for the public demo (Hugging Face Spaces, Docker SDK). The container is the hard
# boundary around visitor code: non-root user, no secrets, limits come from the host.
FROM python:3.11-slim
RUN useradd -m -u 1000 user
USER user
ENV PATH="/home/user/.local/bin:$PATH" PYTHONUNBUFFERED=1
WORKDIR /home/user/app
COPY --chown=user requirements.txt requirements-demo.txt ./
RUN pip install --no-cache-dir -r requirements-demo.txt
COPY --chown=user testpilot ./testpilot
COPY --chown=user app ./app
COPY --chown=user results/evaluation.md ./results/evaluation.md
EXPOSE 7860
CMD ["streamlit", "run", "app/streamlit_app.py", "--server.port=7860", "--server.address=0.0.0.0", "--server.headless=true", "--browser.gatherUsageStats=false"]
