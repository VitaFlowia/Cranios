FROM python:3.11-slim

# Define variáveis de ambiente
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV DEBIAN_FRONTEND=noninteractive

# Instala dependências do sistema
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    libpq-dev \
    curl \
    wget \
    git \
    wkhtmltopdf \
    xvfb \
    netcat-openbsd \
    && rm -rf /var/lib/apt/lists/*

# Cria diretório de trabalho
WORKDIR /app

# Copia requirements primeiro para cache das dependências
COPY requirements.txt .

# Instala dependências Python
RUN pip install --no-cache-dir -r requirements.txt

# Copia código da aplicação
COPY . .

# Cria diretórios necessários
RUN mkdir -p /app/logs /app/temp /app/uploads

# Define permissões
RUN chmod +x /app/start.sh

# Expõe porta
EXPOSE 5678

# Comando de inicialização
CMD ["./start.sh"]
