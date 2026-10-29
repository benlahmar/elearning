# syntax=docker/dockerfile:1
# Official MinIO source, pinned to a release commit (AGPL-3.0).
FROM golang:1.24.6 AS build
RUN --mount=type=secret,id=proxy_ca \
    if [ -f /run/secrets/proxy_ca ]; then export GIT_SSL_CAINFO=/run/secrets/proxy_ca SSL_CERT_FILE=/run/secrets/proxy_ca; fi; \
    git clone --depth 1 --branch RELEASE.2025-09-07T16-13-09Z https://github.com/minio/minio.git /src \
    && cd /src \
    && test "$(git rev-parse HEAD)" = 07c3a429bfed433e49018cb0f78a52145d4bedeb \
    && CGO_ENABLED=0 go build -trimpath -o /minio .
FROM alpine:3.22
COPY --from=build /minio /usr/local/bin/minio
EXPOSE 9000
ENTRYPOINT ["minio"]
