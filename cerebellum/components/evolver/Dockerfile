FROM python:3.12-slim
WORKDIR /app
COPY . .
RUN pip install --no-cache-dir .
RUN useradd --create-home --uid 10002 evolver
USER 10002:10002
ENTRYPOINT ["evolver"]
CMD ["--help"]
