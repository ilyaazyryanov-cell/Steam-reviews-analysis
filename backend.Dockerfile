FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip
RUN pip install --no-cache-dir --prefer-binary -r requirements.txt \
    filelock networkx sympy fsspec jinja2 mpmath typing_extensions \
    requests numpy joblib scikit-learn spacy sentence-transformers
RUN pip install --no-cache-dir --no-deps torch -i https://mirrors.aliyun.com/pypi/simple/
RUN python -m spacy download en_core_web_sm
COPY backend/ backend/
COPY scripts/ scripts/
COPY .env.example .env

CMD ["python", "-m", "uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]