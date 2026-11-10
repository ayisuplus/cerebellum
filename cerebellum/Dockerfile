FROM rust:1.85-bookworm AS builder
WORKDIR /source
COPY . .
RUN cargo build --locked --release --bin cerebellumd --bin cerebellum

FROM debian:bookworm-slim
RUN useradd --create-home --uid 10001 cerebellum
COPY --from=builder /source/target/release/cerebellumd /usr/local/bin/cerebellumd
COPY --from=builder /source/target/release/cerebellum /usr/local/bin/cerebellum
USER 10001:10001
VOLUME ["/var/lib/cerebellum"]
ENTRYPOINT ["cerebellumd"]
CMD ["--data-dir", "/var/lib/cerebellum", "--bind", "127.0.0.1:3927"]
