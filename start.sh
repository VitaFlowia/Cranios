#!/bin/bash

# Espera por variáveis de ambiente críticas (opcionalmente adicione validações aqui)

# Inicializa o app FastAPI com Gunicorn
exec gunicorn main_application:app --workers 1 --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:5678

# Script de inicialização da aplicação Crânios
echo "🚀 Iniciando aplicação Crânios..."

# Aguarda banco de dados estar pronto
echo "⏳ Aguardando banco de dados..."
while ! nc -z postgres 5432; do
  sleep 1
done
echo "✅ Banco de dados conectado!"

# Aguarda Redis estar pronto
echo "⏳ Aguardando Redis..."
while ! nc -z redis 6379; do
  sleep 1
done
echo "✅ Redis conectado!"

# Executa migrações se necessário
echo "🔄 Executando setup inicial..."
python setup_database.py

# Inicia aplicação em modo produção
echo "🎯 Iniciando servidor FastAPI..."
exec gunicorn main:app \
  --workers 4 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000 \
  --timeout 120 \
  --keep-alive 2 \
  --max-requests 1000 \
  --max-requests-jitter 50 \
  --preload \
  --log-level info \
  --access-logfile /app/logs/access.log \
  --error-logfile /app/logs/error.log
