# Chat App - Sistema de Bate-papo em Tempo Real

Um sistema completo de chat em tempo real com criptografia, gerenciamento de salas, convites e envio de emails.

## Funcionalidades

### ✅ Implementadas
- **Autenticação de usuários**: Registro, login e logout
- **Gerenciamento de salas**: Criar, visualizar e excluir salas
- **Chat em tempo real**: Usando Flask-SocketIO
- **Sistema de convites**: Códigos de convite com expiração e limite de uso
- **Envio de emails**: Convites e solicitações de acesso
- **Upload de arquivos**: Suporte a imagens, vídeos, documentos
- **Criptografia**: Mensagens criptografadas usando Fernet
- **Listagem de salas**: Visualizar todas as salas públicas e solicitar acesso
- **Exclusão de salas**: Criadores podem excluir suas salas

### 🔧 Tecnologias Utilizadas
- **Backend**: Flask (Python)
- **Banco de dados**: SQLite com SQLAlchemy ORM
- **Autenticação**: Flask-Login com Passlib (Argon2)
- **Tempo real**: Flask-SocketIO
- **Email**: Flask-Mail
- **Frontend**: Bootstrap 5 + Font Awesome
- **Criptografia**: Cryptography (Fernet)

## Instalação

### 1. Clone o repositório
```bash
git clone <url-do-repositorio>
cd bate_papo
```

### 2. Crie um ambiente virtual
```bash
python -m venv venv
# Windows
venv\Scripts\activate
# Linux/Mac
source venv/bin/activate
```

### 3. Instale as dependências
```bash
pip install -r requirements.txt
```

### 4. Configure as variáveis de ambiente
Crie um arquivo `.env` na raiz do projeto:

```env
# Configurações da aplicação
SECRET_KEY=your-super-secret-key-change-this-in-production
FLASK_ENV=development
FLASK_DEBUG=1

# Configurações de email (Gmail)
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USE_TLS=true
MAIL_USE_SSL=false
MAIL_USERNAME=your-email@gmail.com
MAIL_PASSWORD=your-app-password
MAIL_DEFAULT_SENDER=your-email@gmail.com

# Configurações do banco de dados
DATABASE_URL=sqlite:///instance/chat.db
```

**Importante**: Para usar Gmail, você precisa:
1. Ativar autenticação de 2 fatores
2. Gerar uma "senha de app" específica
3. Usar essa senha no `MAIL_PASSWORD`

### 5. Inicialize o banco de dados
```bash
python init_db.py
```

### 6. Execute a aplicação
```bash
python app_simple.py
```

A aplicação estará disponível em `http://localhost:5000`

## Uso

### 1. Registro e Login
- Acesse `/auth/register` para criar uma conta
- Faça login em `/auth/login`

### 2. Criar uma Sala
- Clique em "Nova Sala" no menu
- Configure nome, descrição e permissões
- A sala será criada e você será o criador

### 3. Gerenciar Convites
- Na sua sala, clique em "Gerenciar Convites"
- Crie convites com expiração e limite de uso
- Os convites serão enviados por email

### 4. Entrar em uma Sala
- Use um código de convite em `/join/<codigo>`
- Ou solicite acesso em "Todas as Salas"

### 5. Chat em Tempo Real
- Entre na sala e comece a conversar
- Suporte a texto, emojis e anexos
- Indicador de digitação

## Estrutura do Projeto

```
bate_papo/
├── app_simple.py          # Aplicação principal
├── config.py              # Configurações
├── models.py              # Modelos do banco de dados
├── forms.py               # Formulários Flask-WTF
├── auth.py                # Lógica de autenticação
├── auth_routes.py         # Rotas de autenticação
├── rooms_routes.py        # Rotas de gerenciamento de salas
├── chat_routes.py         # Rotas do chat e Socket.IO
├── messages.py            # Sistema de mensagens e criptografia
├── invites.py             # Sistema de convites e emails
├── requirements.txt       # Dependências Python
├── init_db.py            # Script de inicialização do banco
├── .env                   # Variáveis de ambiente
├── .flaskenv             # Configurações do Flask
├── instance/             # Banco de dados SQLite
├── static/               # Arquivos estáticos
│   └── uploads/         # Arquivos enviados pelos usuários
└── templates/            # Templates Jinja2
    ├── base.html         # Template base
    ├── auth/             # Templates de autenticação
    ├── rooms/            # Templates de salas
    └── chat/             # Templates do chat
```

## Configuração de Email

### Gmail
```env
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USE_TLS=true
MAIL_USERNAME=seu-email@gmail.com
MAIL_PASSWORD=sua-senha-de-app
```

### Outlook/Hotmail
```env
MAIL_SERVER=smtp-mail.outlook.com
MAIL_PORT=587
MAIL_USE_TLS=true
MAIL_USERNAME=seu-email@outlook.com
MAIL_PASSWORD=sua-senha
```

## Segurança

- **Senhas**: Hashadas com Argon2
- **Sessões**: Gerenciadas pelo Flask-Login
- **CSRF**: Proteção automática com Flask-WTF
- **Uploads**: Validação de tipos e tamanhos de arquivo
- **Criptografia**: Mensagens criptografadas por sala

## Desenvolvimento

### Modo Debug
```bash
export FLASK_DEBUG=1
python app_simple.py
```

### Recriar Banco de Dados
```bash
rm instance/chat.db
python init_db.py
```

### Logs
A aplicação exibe logs no console para:
- Criação de convites
- Envio de emails
- Erros de Socket.IO
- Operações de banco de dados

## Contribuição

1. Fork o projeto
2. Crie uma branch para sua feature
3. Commit suas mudanças
4. Push para a branch
5. Abra um Pull Request

## Licença

Este projeto está sob a licença MIT. Veja o arquivo `LICENSE` para mais detalhes.
