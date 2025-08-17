#!/bin/bash

# Script de Backup para CHATLIVER1404
# Backup automático do banco de dados e arquivos

set -e

# Configurações
BACKUP_DIR="/opt/backups/chatliver1404"
DATE=$(date +%Y%m%d_%H%M%S)
RETENTION_DAYS=30
PROJECT_DIR="/opt/chatliver1404"

# Cores para output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

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

# Verificar se estamos no diretório correto
if [ ! -f "$PROJECT_DIR/docker-compose.yml" ]; then
    error "Docker Compose não encontrado em $PROJECT_DIR"
fi

cd "$PROJECT_DIR"

# Criar diretório de backup
mkdir -p "$BACKUP_DIR"

log "🚀 Iniciando backup do CHATLIVER1404..."

# Backup do banco de dados PostgreSQL
log "📊 Fazendo backup do banco de dados..."
if docker-compose exec -T postgres pg_dump -U chatliver1404 chatliver1404 > "$BACKUP_DIR/db_backup_$DATE.sql"; then
    log "✅ Backup do banco de dados concluído: db_backup_$DATE.sql"
    
    # Comprimir backup do banco
    gzip "$BACKUP_DIR/db_backup_$DATE.sql"
    log "✅ Backup comprimido: db_backup_$DATE.sql.gz"
else
    error "❌ Falha no backup do banco de dados"
fi

# Backup dos uploads
log "📁 Fazendo backup dos uploads..."
if [ -d "static/uploads" ]; then
    if tar -czf "$BACKUP_DIR/uploads_backup_$DATE.tar.gz" -C static uploads/; then
        log "✅ Backup dos uploads concluído: uploads_backup_$DATE.tar.gz"
    else
        warn "⚠️ Falha no backup dos uploads"
    fi
else
    warn "⚠️ Diretório de uploads não encontrado"
fi

# Backup dos logs
log "📋 Fazendo backup dos logs..."
if [ -d "logs" ]; then
    if tar -czf "$BACKUP_DIR/logs_backup_$DATE.tar.gz" -C logs .; then
        log "✅ Backup dos logs concluído: logs_backup_$DATE.tar.gz"
    else
        warn "⚠️ Falha no backup dos logs"
    fi
else
    warn "⚠️ Diretório de logs não encontrado"
fi

# Backup da configuração
log "⚙️ Fazendo backup da configuração..."
if cp .env "$BACKUP_DIR/config_backup_$DATE.env"; then
    log "✅ Backup da configuração concluído: config_backup_$DATE.env"
else
    warn "⚠️ Falha no backup da configuração"
fi

# Criar arquivo de metadados do backup
cat > "$BACKUP_DIR/backup_metadata_$DATE.json" << EOF
{
    "timestamp": "$(date -Iseconds)",
    "backup_id": "$DATE",
    "version": "CHATLIVER1404",
    "files": [
        "db_backup_$DATE.sql.gz",
        "uploads_backup_$DATE.tar.gz",
        "logs_backup_$DATE.tar.gz",
        "config_backup_$DATE.env"
    ],
    "size": {
        "database": "$(du -h "$BACKUP_DIR/db_backup_$DATE.sql.gz" | cut -f1)",
        "uploads": "$(du -h "$BACKUP_DIR/uploads_backup_$DATE.tar.gz" | cut -f1)",
        "logs": "$(du -h "$BACKUP_DIR/logs_backup_$DATE.tar.gz" | cut -f1)"
    }
}
EOF

log "✅ Metadados do backup criados: backup_metadata_$DATE.json"

# Limpeza de backups antigos
log "🧹 Limpando backups antigos (mais de $RETENTION_DAYS dias)..."
find "$BACKUP_DIR" -name "*.sql.gz" -mtime +$RETENTION_DAYS -delete
find "$BACKUP_DIR" -name "*.tar.gz" -mtime +$RETENTION_DAYS -delete
find "$BACKUP_DIR" -name "*.env" -mtime +$RETENTION_DAYS -delete
find "$BACKUP_DIR" -name "*.json" -mtime +$RETENTION_DAYS -delete

# Verificar espaço em disco
DISK_USAGE=$(df "$BACKUP_DIR" | tail -1 | awk '{print $5}' | sed 's/%//')
if [ "$DISK_USAGE" -gt 80 ]; then
    warn "⚠️ Uso de disco alto: ${DISK_USAGE}%"
fi

# Estatísticas do backup
TOTAL_SIZE=$(du -sh "$BACKUP_DIR" | cut -f1)
BACKUP_COUNT=$(find "$BACKUP_DIR" -name "*.gz" | wc -l)

log "📊 Estatísticas do backup:"
log "   - Total de backups: $BACKUP_COUNT"
log "   - Tamanho total: $TOTAL_SIZE"
log "   - Retenção: $RETENTION_DAYS dias"

# Verificar integridade do backup
log "🔍 Verificando integridade do backup..."
if gzip -t "$BACKUP_DIR/db_backup_$DATE.sql.gz"; then
    log "✅ Backup do banco de dados é válido"
else
    error "❌ Backup do banco de dados corrompido"
fi

if [ -f "$BACKUP_DIR/uploads_backup_$DATE.tar.gz" ]; then
    if tar -tzf "$BACKUP_DIR/uploads_backup_$DATE.tar.gz" > /dev/null; then
        log "✅ Backup dos uploads é válido"
    else
        warn "⚠️ Backup dos uploads pode estar corrompido"
    fi
fi

log "🎉 Backup concluído com sucesso!"
log "📁 Localização: $BACKUP_DIR"
log "🕐 Timestamp: $DATE"

# Enviar notificação por email (opcional)
if command -v mail &> /dev/null; then
    echo "Backup do CHATLIVER1404 concluído em $(date)" | \
    mail -s "Backup CHATLIVER1404 - $DATE" admin@chatliver1404.com
fi

exit 0
