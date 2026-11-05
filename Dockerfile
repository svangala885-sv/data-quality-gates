FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir .
COPY config ./config
COPY data ./data
RUN useradd --create-home app
USER app
ENTRYPOINT ["dq-gate"]
CMD ["--config", "config/orders.yaml", "--data", "data/orders_clean.csv"]
