FROM pytorch/pytorch:2.12.1-cuda12.6-cudnn9-runtime

WORKDIR /app

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    libpq-dev \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN pip3 install --no-cache-dir --break-system-packages -r requirements.txt

# Pre-download the large-v3 model into the container cache so it is baked-in
RUN python3 -c "from faster_whisper import WhisperModel; WhisperModel('large-v3', device='cpu', compute_type='int8')"

COPY . .

EXPOSE 8000

CMD ["sh", "-c", "python backend/main.py"]