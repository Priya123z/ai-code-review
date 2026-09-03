# Hugging Face Spaces image for the demo API.
# Spaces expects the app on 7860 and runs the container as uid 1000.
FROM python:3.12-slim

RUN useradd --create-home --uid 1000 user
USER user

ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH

WORKDIR /home/user/app

COPY --chown=user server/requirements.txt server/requirements.txt
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r server/requirements.txt

COPY --chown=user ai_review ai_review
COPY --chown=user server server

EXPOSE 7860

CMD ["uvicorn", "server.app:app", "--host", "0.0.0.0", "--port", "7860"]
