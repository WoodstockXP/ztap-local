FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY gateway/ gateway/
COPY agent/ agent/
COPY baseline/ baseline/
COPY client/ client/
COPY eval/ eval/
COPY policies/ policies/
EXPOSE 8001
CMD ["uvicorn", "gateway.main:app", "--host", "0.0.0.0", "--port", "8001"]