# Dockerfile para CHATLIVER1404 - Produção
FROM python:3.11-slim

# Definir variáveis de ambiente
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV FLASK_APP=app_production.py
ENV FLASK_ENV=production

# Instalar dependências do sistema
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    libffi-dev \
    libssl-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Criar diretório de trabalho
WORKDIR /app

# Copiar requirements de produção primeiro para cache de dependências
COPY requirements_production.txt requirements.txt

# Instalar dependências Python
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copiar código da aplicação
COPY . .

# Criar diretórios necessários
RUN mkdir -p static/uploads static/icons logs

# Gerar ícones do PWA
RUN python generate_icons.py

# Criar usuário não-root para segurança
RUN useradd --create-home --shell /bin/bash app && \
    chown -R app:app /app
USER app

# Expor porta
EXPOSE 5000

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:5000/health || exit 1

# Comando para iniciar a aplicação de produção
CMD ["python", "app_production.py"]
