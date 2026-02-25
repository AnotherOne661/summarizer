FROM ollama/ollama:latest

RUN apt-get update && apt-get install -y \
    clinfo \
    pciutils \
    && rm -rf /var/lib/apt/lists/*

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 11434

ENV OLLAMA_CUDA=1
ENV OLLAMA_FLASH_ATTENTION=1

ENTRYPOINT ["/entrypoint.sh"]