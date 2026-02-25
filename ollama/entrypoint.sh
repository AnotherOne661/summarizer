#!/bin/bash
set -e

# Verificar si hay GPUs disponibles (sin usar nvidia-smi)
echo "=== Verificando dispositivos NVIDIA ==="
if [ -e /dev/nvidia0 ]; then
    echo "✅ Dispositivo NVIDIA encontrado en /dev/nvidia0"
else
    echo "⚠️  No se encontraron dispositivos NVIDIA. ¿Están los drivers instalados en el host?"
fi

ollama serve &

# Esperar a que el servidor esté listo
until ollama list > /dev/null 2>&1; do
    echo "Esperando a que Ollama se inicie..."
    sleep 2
done

# Descargar modelo
MODEL=${OLLAMA_MODEL:-llama3.2:3b}
echo "Descargando modelo: $MODEL"
ollama pull "$MODEL"

wait