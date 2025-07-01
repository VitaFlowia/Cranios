#!/bin/bash

echo "🚀 Iniciando aplicação Crânios..."

# Executa setup se necessário
if [ -f "setup_database.py" ]; then
echo "📋 Executando setup inicial..."
python setup_database.py
fi

# Inicia aplicação
echo "🚀 Iniciando servidor FastAPI..."
exec gunicorn main_application:app \
--workers 1 \
--worker-class uvicorn.workers.UvicornWorker \
--bind 0.0.0.0:5678 \
--timeout 120 \
--log-level info
