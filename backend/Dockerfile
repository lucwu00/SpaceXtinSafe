# Backend API image (Render). The React app is deployed separately on Vercel.
FROM python:3.13-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1 HF_HOME=/app/.hf SPACEXI_DB=/app/data/spacextinsafe.sqlite3
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
# Bake the sentence-transformer weights into the image so cold starts do not depend on Hugging Face.
RUN mkdir -p /app/data && python -c "from sentence_transformers import SentenceTransformer as S; S('sentence-transformers/all-MiniLM-L6-v2')" || echo "model download skipped"
EXPOSE 8000
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
