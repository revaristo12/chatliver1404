# Visão geral

Um sistema de bate‑papo (chat) multi‑salas para rodar em VPS Linux (Ubuntu), feito com **Flask (Python)**, **Flask‑SocketIO** para tempo real e **SQLite** como banco de dados. Inclui:

* Cadastro/login por e‑mail e senha (hash com Argon2/Passlib).
* Listagem de salas com controle de acesso (membros e convidados).
* Criação de sala privada, convites por link/token e gestão completa pelo criador (banir/excluir membros, limpar histórico, limitar mídias, excluir sala e todo conteúdo).
* Criptografia:

  * **Padrão (simples)**: criptografia "em repouso" no servidor (AES‑GCM com chave do servidor por sala).
  * **Opcional (E2EE)**: criptografia ponta‑a‑ponta no cliente (TweetNaCl/libsodium) com distribuição de chaves por membro (sealed box), para que apenas usuários permitidos consigam ler as mensagens.
* Upload controlado de mídias (imagens/vídeos), com limites configuráveis por sala.

> **Observação:** O modo E2EE exige criptografia no navegador (JS). O servidor não verá conteúdo em texto puro — apenas metadados — e recursos como busca no histórico por palavra não funcionarão sem índices no cliente.

---

## Stack e dependências

* Python 3.11+
* Flask, Flask‑Login, Flask‑WTF, Flask‑SocketIO
* gunicorn + eventlet (produção)
* passlib\[argon2] (hashing de senha)
* SQLAlchemy + Alembic (migrations) ou SQLModel (opcional). Aqui usaremos SQLAlchemy.
* itsdangerous (tokens de convite)
* python‑dotenv (config)
* cryptography (AES‑GCM) e **PyNaCl** (E2EE opcional)

**requirements.txt**

```
Flask==3.0.3
Flask-Login==0.6.3
Flask-WTF==1.2.1
Flask-SocketIO==5.3.7
python-dotenv==1.0.1
passlib[argon2]==1.7.4
SQLAlchemy==2.0.32
alembic==1.13.2
cryptography==43.0.1
PyNaCl==1.5.0
email-validator==2.2.0
itsdangerous==2.2.0
python-magic==0.4.27
```

---

## Estrutura de pastas

```
chatapp/
  app.py
  config.py
  models.py
  forms.py
  auth.py
  rooms.py
  sockets.py
  crypto.py
  invites.py
  media.py
  utils.py
  requirements.txt
  alembic.ini
  migrations/            # gerado pelo alembic
  instance/
    chat.db              # SQLite
    .secret              # chaves do servidor (600)
  templates/
    base.html
    auth/
      login.html
      register.html
    rooms/
      index.html         # lista de salas
      room.html          # chat + socket
  static/
    js/
      e2ee.js            # E2EE opcional (TweetNaCl)
    uploads/
      <room_id>/...
  .env
```

---

## Modelo de dados (SQLAlchemy)

```python
# models.py
from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, DateTime, Boolean, ForeignKey, Text, LargeBinary,
    UniqueConstraint
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    email = Column(String(255), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    # E2EE opcional
    public_key = Column(LargeBinary)   # chave pública (NaCl)
    enc_private_key = Column(LargeBinary)  # privada cifrada com senha do usuário

class Room(Base):
    __tablename__ = 'rooms'
    id = Column(Integer, primary_key=True)
    name = Column(String(120), nullable=False)
    slug = Column(String(160), unique=True, nullable=False)
    owner_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    allow_images = Column(Boolean, default=True)
    allow_videos = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    # Criptografia em repouso (padrão): chave AES-GCM cifrada com KEK do servidor
    enc_room_key = Column(LargeBinary)  # chave simétrica da sala cifrada

    owner = relationship('User')

class RoomMember(Base):
    __tablename__ = 'room_members'
    id = Column(Integer, primary_key=True)
    room_id = Column(Integer, ForeignKey('rooms.id'), nullable=False)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    role = Column(String(20), default='member')  # owner, admin, member
    joined_at = Column(DateTime, default=datetime.utcnow)
    __table_args__ = (UniqueConstraint('room_id','user_id', name='uix_room_user'),)

class RoomInvite(Base):
    __tablename__ = 'room_invites'
    id = Column(Integer, primary_key=True)
    room_id = Column(Integer, ForeignKey('rooms.id'), nullable=False)
    email = Column(String(255), nullable=True)  # pode ser nulo p/ link aberto (token)
    token = Column(String(255), unique=True, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    used = Column(Boolean, default=False)

class Message(Base):
    __tablename__ = 'messages'
    id = Column(Integer, primary_key=True)
    room_id = Column(Integer, ForeignKey('rooms.id'), index=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    # Em repouso: conteúdo cifrado no servidor (AES-GCM)
    nonce = Column(LargeBinary)
    ciphertext = Column(LargeBinary)
    # E2EE opcional: armazenar blob opaco
    e2ee = Column(Boolean, default=False)

class Attachment(Base):
    __tablename__ = 'attachments'
    id = Column(Integer, primary_key=True)
    message_id = Column(Integer, ForeignKey('messages.id'), index=True)
    room_id = Column(Integer, ForeignKey('rooms.id'))
    filename = Column(String(255))
    mimetype = Column(String(100))
    size = Column(Integer)
    path = Column(String(500))  # caminho relativo
    uploaded_at = Column(DateTime, default=datetime.utcnow)
```

---

## Criptografia

### 1) Padrão (em repouso no servidor)

* Cada sala tem uma **chave simétrica** aleatória (32 bytes) para AES‑GCM.
* A chave da sala é cifrada com uma **KEK** (Key Encryption Key) do servidor e armazenada em `Room.enc_room_key`.
* Ao salvar mensagem: servidor decifra `room_key` em memória, cifra o texto e armazena `(nonce, ciphertext)`.
* Ao entregar mensagem a um membro: servidor decifra e envia texto em claro **apenas via WebSocket** para usuários autorizados.

### 2) Opcional E2EE (ponta‑a‑ponta)

* Cada usuário possui par de chaves **NaCl box** (Curve25519). A privada fica **cifrada** com uma chave derivada da senha (Argon2 KDF) e só é aberta no cliente.
* Cada sala possui uma "room\_key" simétrica. O dono (ou admin) **cifra a room\_key com a chave pública** de cada membro e distribui via servidor (que não consegue ler o conteúdo).
* Mensagens são **cifradas no cliente** com a room\_key (NaCl secretbox). O servidor armazena apenas blobs opacos (`ciphertext`, `nonce`, `e2ee=True`).
* Para novos membros, o admin reenvia a room\_key cifrada ao usuário.

> Você pode iniciar com o modo em repouso, e evoluir para E2EE quando o front estiver pronto.

---

## Fluxos principais

1. **Cadastro/Login**

* Cadastro: validação de e‑mail, hash de senha (Argon2), opcionalmente gerar par de chaves E2EE e cifrar privada com senha.
* Login: autentica e cria sessão Flask‑Login.

2. **Listar salas**

* Página `GET /rooms`: mostra todas as salas do sistema, indicando a que o usuário tem acesso (membro/convidado). Botão para "Pedir acesso" quando aplicável.

3. **Criar sala + convites**

* `POST /rooms/create`: cria sala, define permissões de mídia, gera `room_key` e `enc_room_key`.
* `POST /rooms/<slug>/invites`: criar convite por e‑mail (envio com token) ou gerar link único com expiração.

4. **Entrar na sala**

* Verifica se usuário é membro ou se possui convite válido.
* Ao entrar, abre Socket.IO room `<room_id>`.

5. **Mensagens**

* Evento `send_message`: valida membro, aplica criptografia (em repouso ou E2EE), persiste e emite para a sala.

6. **Administração da sala (criador/admin)**

* `DELETE /rooms/<slug>/messages` (limpar histórico)
* `DELETE /rooms/<slug>` (excluir sala + conversas + mídias)
* `POST /rooms/<slug>/members/<user_id>/remove`
* `PATCH /rooms/<slug>/settings` (permitir/bloquear imagens/vídeos, rate limit)

