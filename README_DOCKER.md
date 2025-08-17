# 🐳 CHATLIVER1404 - Deploy Docker para VPS

Este guia mostra como implantar o CHATLIVER1404 em uma VPS Ubuntu usando Docker.

## 📋 Pré-requisitos

- VPS Ubuntu 20.04+ com pelo menos 2GB RAM
- Domínio configurado (opcional, mas recomendado)
- Acesso SSH ao servidor
- Usuário com privilégios sudo

## 🚀 Deploy Automatizado

### 1. Conectar ao servidor
```bash
ssh usuario@seu-servidor.com
```

### 2. Executar script de deploy
```bash
# Baixar o script
curl -O https://raw.githubusercontent.com/seu-usuario/chatliver1404/main/deploy.sh

# Tornar executável
chmod +x deploy.sh

# Executar deploy
./deploy.sh
```

O script irá:
- ✅ Instalar Docker e Docker Compose
- ✅ Configurar firewall e fail2ban
- ✅ Baixar e configurar o projeto
- ✅ Criar containers e iniciar serviços
- ✅ Configurar backup automático
- ✅ Configurar monitoramento
- ✅ Configurar SSL automático

## 🔧 Deploy Manual

### 1. Instalar Docker
```bash
# Atualizar sistema
sudo apt update && sudo apt upgrade -y

# Instalar dependências
sudo apt install -y apt-transport-https ca-certificates curl gnupg lsb-release

# Adicionar repositório Docker
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# Instalar Docker
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io
sudo usermod -aG docker $USER

# Instalar Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose
```

### 2. Configurar projeto
```bash
# Criar diretório
sudo mkdir -p /opt/chatliver1404
sudo chown $USER:$USER /opt/chatliver1404
cd /opt/chatliver1404

# Clonar projeto
git clone https://github.com/seu-usuario/chatliver1404.git .

# Criar arquivo .env
cp .env.example .env
nano .env
```

### 3. Configurar variáveis de ambiente
Edite o arquivo `.env`:

```env
# Configurações do CHATLIVER1404
POSTGRES_PASSWORD=senha_super_segura_para_postgres
REDIS_PASSWORD=senha_super_segura_para_redis
SECRET_KEY=chave_secreta_para_flask

# Configurações de email (opcional)
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USE_TLS=True
MAIL_USERNAME=seu-email@gmail.com
MAIL_PASSWORD=sua-senha-de-app

# Configurações de domínio
DOMAIN=seu-dominio.com
CERTBOT_EMAIL=admin@seu-dominio.com
```

### 4. Iniciar serviços
```bash
# Construir e iniciar
docker-compose up -d

# Verificar status
docker-compose ps

# Ver logs
docker-compose logs -f
```

## 🔒 Configuração de Segurança

### Firewall
```bash
sudo ufw --force enable
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow ssh
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
```

### Fail2ban
```bash
sudo apt install -y fail2ban
sudo systemctl enable fail2ban
sudo systemctl start fail2ban
```

## 📊 Monitoramento

### Health Check
```bash
# Verificar status da aplicação
curl http://localhost/health

# Verificar logs
docker-compose logs -f app
```

### Backup Automático
O sistema configura backup automático diário às 2h da manhã:
- Banco de dados PostgreSQL
- Arquivos de upload
- Retenção de 30 dias

## 🔄 Manutenção

### Atualizar aplicação
```bash
cd /opt/chatliver1404
git pull
docker-compose build
docker-compose up -d
```

### Backup manual
```bash
./backup.sh
```

### Renovar SSL
```bash
./renew-ssl.sh
```

### Reiniciar serviços
```bash
docker-compose restart
```

## 🐛 Troubleshooting

### Verificar logs
```bash
# Logs de todos os serviços
docker-compose logs

# Logs específicos
docker-compose logs app
docker-compose logs nginx
docker-compose logs postgres
```

### Problemas comuns

#### Container não inicia
```bash
# Verificar recursos
docker system df
docker system prune

# Verificar logs
docker-compose logs app
```

#### Problemas de SSL
```bash
# Verificar certificados
docker-compose exec nginx ls -la /etc/nginx/ssl/

# Renovar certificados
./renew-ssl.sh
```

#### Problemas de banco
```bash
# Conectar ao banco
docker-compose exec postgres psql -U chatliver1404 -d chatliver1404

# Verificar conexão
docker-compose exec app python -c "from app_production import db; print(db.engine.execute('SELECT 1').scalar())"
```

## 📈 Performance

### Otimizações recomendadas

1. **Aumentar recursos do servidor**:
   - Mínimo: 2GB RAM, 1 CPU
   - Recomendado: 4GB RAM, 2 CPU

2. **Configurar swap**:
```bash
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

3. **Otimizar PostgreSQL**:
```bash
# Editar configuração do PostgreSQL
docker-compose exec postgres bash
nano /var/lib/postgresql/data/postgresql.conf
```

## 🔧 Comandos Úteis

```bash
# Ver status dos containers
docker-compose ps

# Ver logs em tempo real
docker-compose logs -f

# Parar todos os serviços
docker-compose down

# Reiniciar um serviço específico
docker-compose restart app

# Executar comando em container
docker-compose exec app python manage.py shell

# Backup manual
docker-compose exec postgres pg_dump -U chatliver1404 chatliver1404 > backup.sql

# Restaurar backup
docker-compose exec -T postgres psql -U chatliver1404 -d chatliver1404 < backup.sql
```

## 📞 Suporte

Se encontrar problemas:

1. Verifique os logs: `docker-compose logs -f`
2. Verifique o status: `docker-compose ps`
3. Teste o health check: `curl http://localhost/health`
4. Consulte a documentação do projeto

## 🎉 Pronto!

Após o deploy, o CHATLIVER1404 estará disponível em:
- **HTTP**: http://seu-servidor.com
- **HTTPS**: https://seu-dominio.com (se configurado)

**Recursos incluídos:**
- ✅ Chat em tempo real com Socket.IO
- ✅ Sistema de convites por email
- ✅ PWA para instalação no celular
- ✅ Backup automático
- ✅ SSL automático com Let's Encrypt
- ✅ Monitoramento e logs
- ✅ Rate limiting e segurança
- ✅ Compressão e otimizações

**🚀 CHATLIVER1404 - Privacidade e Segurança para Conversas**

