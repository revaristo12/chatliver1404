#!/bin/bash

# Script de Deploy para CHATLIVER1404
# VPS Ubuntu com Docker

set -e

# Cores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Função para log
log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')] $1${NC}"
}

warn() {
    echo -e "${YELLOW}[$(date +'%Y-%m-%d %H:%M:%S')] WARNING: $1${NC}"
}

error() {
    echo -e "${RED}[$(date +'%Y-%m-%d %H:%M:%S')] ERROR: $1${NC}"
    exit 1
}

# Verificar se é root
if [[ $EUID -eq 0 ]]; then
   error "Este script não deve ser executado como root"
fi

# Verificar sistema operacional
if [[ ! -f /etc/os-release ]]; then
    error "Sistema operacional não suportado"
fi

source /etc/os-release
if [[ "$ID" != "ubuntu" ]]; then
    error "Este script é específico para Ubuntu"
fi

log "🚀 Iniciando deploy do CHATLIVER1404..."

# Atualizar sistema
log "📦 Atualizando sistema..."
sudo apt update && sudo apt upgrade -y

# Instalar dependências
log "🔧 Instalando dependências..."
sudo apt install -y \
    apt-transport-https \
    ca-certificates \
    curl \
    gnupg \
    lsb-release \
    software-properties-common \
    git \
    htop \
    ufw \
    fail2ban

# Instalar Docker
log "🐳 Instalando Docker..."
if ! command -v docker &> /dev/null; then
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
    sudo apt update
    sudo apt install -y docker-ce docker-ce-cli containerd.io
    sudo usermod -aG docker $USER
    log "Docker instalado com sucesso"
else
    log "Docker já está instalado"
fi

# Instalar Docker Compose
log "🐙 Instalando Docker Compose..."
if ! command -v docker-compose &> /dev/null; then
    sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    sudo chmod +x /usr/local/bin/docker-compose
    log "Docker Compose instalado com sucesso"
else
    log "Docker Compose já está instalado"
fi

# Configurar firewall
log "🔥 Configurando firewall..."
sudo ufw --force enable
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow ssh
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw allow 22/tcp
log "Firewall configurado"

# Configurar fail2ban
log "🛡️ Configurando fail2ban..."
sudo systemctl enable fail2ban
sudo systemctl start fail2ban
log "Fail2ban configurado"

# Criar diretório do projeto
PROJECT_DIR="/opt/chatliver1404"
log "📁 Criando diretório do projeto: $PROJECT_DIR"
sudo mkdir -p $PROJECT_DIR
sudo chown $USER:$USER $PROJECT_DIR

# Clonar ou copiar código
if [ -d ".git" ]; then
    log "📋 Copiando código do projeto..."
    cp -r . $PROJECT_DIR/
else
    log "📋 Baixando código do projeto..."
    cd $PROJECT_DIR
    git clone https://github.com/seu-usuario/chatliver1404.git .
fi

cd $PROJECT_DIR

# Criar arquivo .env
log "⚙️ Criando arquivo de configuração..."
cat > .env << EOF
# Configurações do CHATLIVER1404
POSTGRES_PASSWORD=chatliver1404_secure_password_$(openssl rand -hex 16)
REDIS_PASSWORD=chatliver1404_redis_password_$(openssl rand -hex 16)
SECRET_KEY=$(openssl rand -hex 32)

# Configurações de email (opcional)
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USE_TLS=True
MAIL_USERNAME=seu-email@gmail.com
MAIL_PASSWORD=sua-senha-de-app

# Configurações de domínio
DOMAIN=chatliver1404.com
CERTBOT_EMAIL=admin@chatliver1404.com
EOF

log "Arquivo .env criado. Edite as configurações de email se necessário."

# Criar diretórios necessários
log "📂 Criando diretórios..."
mkdir -p nginx/ssl nginx/www logs

# Configurar Nginx para SSL automático
log "🔒 Configurando Nginx para SSL..."
sed -i 's/chatliver1404.com/$DOMAIN/g' nginx/nginx.conf

# Construir e iniciar containers
log "🏗️ Construindo containers..."
docker-compose build

log "🚀 Iniciando serviços..."
docker-compose up -d

# Aguardar serviços iniciarem
log "⏳ Aguardando serviços iniciarem..."
sleep 30

# Verificar status
log "🔍 Verificando status dos serviços..."
docker-compose ps

# Verificar logs
log "📋 Logs dos serviços:"
docker-compose logs --tail=20

# Configurar backup automático
log "💾 Configurando backup automático..."
cat > backup.sh << 'EOF'
#!/bin/bash
BACKUP_DIR="/opt/backups/chatliver1404"
DATE=$(date +%Y%m%d_%H%M%S)

mkdir -p $BACKUP_DIR

# Backup do banco de dados
docker-compose exec -T postgres pg_dump -U chatliver1404 chatliver1404 > $BACKUP_DIR/db_backup_$DATE.sql

# Backup dos uploads
tar -czf $BACKUP_DIR/uploads_backup_$DATE.tar.gz -C /opt/chatliver1404 static/uploads/

# Manter apenas os últimos 30 backups
find $BACKUP_DIR -name "*.sql" -mtime +30 -delete
find $BACKUP_DIR -name "*.tar.gz" -mtime +30 -delete

echo "Backup concluído: $DATE"
EOF

chmod +x backup.sh

# Adicionar ao crontab
(crontab -l 2>/dev/null; echo "0 2 * * * /opt/chatliver1404/backup.sh") | crontab -

# Configurar monitoramento
log "📊 Configurando monitoramento..."
cat > monitor.sh << 'EOF'
#!/bin/bash
# Script de monitoramento simples
if ! curl -f http://localhost/health > /dev/null 2>&1; then
    echo "CHATLIVER1404 está offline!" | mail -s "Alerta: CHATLIVER1404 Offline" admin@chatliver1404.com
fi
EOF

chmod +x monitor.sh

# Adicionar monitoramento ao crontab
(crontab -l 2>/dev/null; echo "*/5 * * * * /opt/chatliver1404/monitor.sh") | crontab -

# Configurar renovação automática de SSL
log "🔄 Configurando renovação automática de SSL..."
cat > renew-ssl.sh << 'EOF'
#!/bin/bash
cd /opt/chatliver1404
docker-compose run --rm certbot renew
docker-compose restart nginx
EOF

chmod +x renew-ssl.sh

# Adicionar renovação SSL ao crontab
(crontab -l 2>/dev/null; echo "0 12 * * * /opt/chatliver1404/renew-ssl.sh") | crontab -

# Instruções finais
log "✅ Deploy concluído com sucesso!"
echo ""
echo -e "${BLUE}🎉 CHATLIVER1404 está rodando!${NC}"
echo ""
echo -e "${YELLOW}📋 Próximos passos:${NC}"
echo "1. Configure seu domínio para apontar para este servidor"
echo "2. Edite o arquivo .env com suas configurações de email"
echo "3. Execute: docker-compose restart"
echo "4. Acesse: https://seu-dominio.com"
echo ""
echo -e "${YELLOW}🔧 Comandos úteis:${NC}"
echo "docker-compose logs -f    # Ver logs em tempo real"
echo "docker-compose restart    # Reiniciar serviços"
echo "docker-compose down       # Parar serviços"
echo "docker-compose up -d      # Iniciar serviços"
echo ""
echo -e "${YELLOW}📁 Diretórios importantes:${NC}"
echo "Projeto: $PROJECT_DIR"
echo "Logs: $PROJECT_DIR/logs"
echo "Backups: /opt/backups/chatliver1404"
echo ""
echo -e "${GREEN}🚀 CHATLIVER1404 - Privacidade e Segurança para Conversas${NC}"

