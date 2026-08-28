FROM python:3.13-alpine AS build

RUN apk add --no-cache build-base jpeg-dev zlib-dev
WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip wheel --no-cache-dir --wheel-dir /wheels . && \
    pip wheel --no-cache-dir --wheel-dir /wheels "httpx>=0.28,<1" "pillow>=11,<13"

FROM python:3.13-alpine

RUN apk add --no-cache jpeg zlib && addgroup -S app && adduser -S -G app app
WORKDIR /app
COPY --from=build /wheels /wheels
RUN pip install --no-cache-dir --no-index --find-links=/wheels immich-frigate-face-sync && \
    rm -rf /wheels
RUN mkdir -p /data && chown app:app /data
USER app
VOLUME ["/data"]
EXPOSE 8080
ENV PYTHONUNBUFFERED=1
CMD ["immich-frigate-face-sync"]
