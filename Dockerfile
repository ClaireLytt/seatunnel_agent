FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml .
COPY src/ src/

RUN pip install --no-cache-dir -e ".[all,ui]"

COPY examples/ examples/
COPY .env.example .env.example

EXPOSE 7860

CMD ["seatunnel-agent", "ui", "--host", "0.0.0.0"]
