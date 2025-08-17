from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, DateTime, Boolean, ForeignKey, Text, LargeBinary,
    UniqueConstraint, Index
)
from sqlalchemy.orm import declarative_base, relationship
from flask_login import UserMixin

Base = declarative_base()

class User(Base, UserMixin):
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True)
    username = Column(String(80), unique=True, nullable=False)
    email = Column(String(120), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    is_admin = Column(Boolean, default=False)  # Campo para identificar administradores
    created_at = Column(DateTime, default=datetime.utcnow)
    last_seen = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)
    
    # Relacionamentos
    rooms_created = relationship('Room', back_populates='creator')
    room_memberships = relationship('RoomMember', back_populates='user')
    messages = relationship('Message', back_populates='user')
    created_advertisements = relationship('Advertisement', back_populates='creator')
    created_admin_messages = relationship('AdminMessage', back_populates='creator')
    created_invites = relationship('RoomInvite', back_populates='creator')
    access_requests = relationship('AccessRequest', foreign_keys='AccessRequest.user_id', back_populates='user')
    processed_requests = relationship('AccessRequest', foreign_keys='AccessRequest.processed_by', back_populates='processor')

class Room(Base):
    __tablename__ = 'rooms'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    slug = Column(String(100), unique=True, nullable=False)
    description = Column(Text)
    is_private = Column(Boolean, default=False)
    allow_images = Column(Boolean, default=True)
    allow_videos = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    creator_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    
    # Relacionamentos
    creator = relationship('User', back_populates='rooms_created')
    members = relationship('RoomMember', back_populates='room', cascade='all, delete-orphan')
    messages = relationship('Message', back_populates='room', cascade='all, delete-orphan')
    invites = relationship('RoomInvite', back_populates='room', cascade='all, delete-orphan')
    access_requests = relationship('AccessRequest', back_populates='room', cascade='all, delete-orphan')
    advertisements = relationship('Advertisement', back_populates='room', cascade='all, delete-orphan')

class RoomMember(Base):
    __tablename__ = 'room_members'
    
    id = Column(Integer, primary_key=True)
    room_id = Column(Integer, ForeignKey('rooms.id'), nullable=False)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    role = Column(String(20), default='member')  # creator, admin, member
    joined_at = Column(DateTime, default=datetime.utcnow)
    
    # Relacionamentos
    room = relationship('Room', back_populates='members')
    user = relationship('User', back_populates='room_memberships')

class RoomInvite(Base):
    __tablename__ = 'room_invites'
    
    id = Column(Integer, primary_key=True)
    room_id = Column(Integer, ForeignKey('rooms.id'), nullable=False)
    code = Column(String(20), unique=True, nullable=False)
    created_by = Column(Integer, ForeignKey('users.id'), nullable=False)
    expires_at = Column(DateTime, nullable=False)
    max_uses = Column(Integer)
    used_count = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relacionamentos
    room = relationship('Room', back_populates='invites')
    creator = relationship('User', back_populates='created_invites')

class Message(Base):
    __tablename__ = 'messages'
    
    id = Column(Integer, primary_key=True)
    room_id = Column(Integer, ForeignKey('rooms.id'), nullable=False)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    content = Column(Text, nullable=False)
    attachment_path = Column(String(255))
    encrypted_content = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relacionamentos
    room = relationship('Room', back_populates='messages')
    user = relationship('User', back_populates='messages')
    attachments = relationship('Attachment', back_populates='message', cascade='all, delete-orphan')

class Attachment(Base):
    __tablename__ = 'attachments'
    
    id = Column(Integer, primary_key=True)
    message_id = Column(Integer, ForeignKey('messages.id'), nullable=False)
    filename = Column(String(255), nullable=False)
    file_path = Column(String(255), nullable=False)
    file_size = Column(Integer)
    mime_type = Column(String(100))
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relacionamentos
    message = relationship('Message', back_populates='attachments')

class AccessRequest(Base):
    """Solicitações de acesso a salas"""
    __tablename__ = 'access_requests'
    
    id = Column(Integer, primary_key=True)
    room_id = Column(Integer, ForeignKey('rooms.id'), nullable=False)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    requested_at = Column(DateTime, default=datetime.utcnow)
    status = Column(String(20), default='pending')  # pending, approved, rejected
    processed_at = Column(DateTime, nullable=True)
    processed_by = Column(Integer, ForeignKey('users.id'), nullable=True)
    notes = Column(Text, nullable=True)
    
    # Relacionamentos
    room = relationship('Room', back_populates='access_requests')
    user = relationship('User', foreign_keys=[user_id], back_populates='access_requests')
    processor = relationship('User', foreign_keys=[processed_by], back_populates='processed_requests')
    
    @property
    def is_pending(self):
        return self.status == 'pending'
    
    @property
    def is_approved(self):
        return self.status == 'approved'
    
    @property
    def is_rejected(self):
        return self.status == 'rejected'


class Advertisement(Base):
    """Anúncios exibidos no chat"""
    __tablename__ = 'advertisements'
    id = Column(Integer, primary_key=True)
    room_id = Column(Integer, ForeignKey('rooms.id'), nullable=False)
    title = Column(String(100), nullable=False)
    content = Column(Text, nullable=False)
    image_path = Column(String(255), nullable=True)
    link = Column(String(500), nullable=True)  # URL para redirecionamento
    start_date = Column(DateTime, nullable=False)
    end_date = Column(DateTime, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    created_by = Column(Integer, ForeignKey('users.id'), nullable=False)
    priority = Column(Integer, default=1)  # 1=baixa, 2=média, 3=alta
    
    room = relationship('Room', back_populates='advertisements')
    creator = relationship('User', back_populates='created_advertisements')
    
    @property
    def is_expired(self):
        """Verifica se o anúncio expirou"""
        return datetime.utcnow() > self.end_date
    
    @property
    def is_current(self):
        """Verifica se o anúncio está ativo no período atual"""
        now = datetime.utcnow()
        return (self.is_active and 
                now >= self.start_date and 
                now <= self.end_date)
    
    @property
    def days_remaining(self):
        """Retorna quantos dias restam até o fim"""
        if self.is_expired:
            return 0
        delta = self.end_date - datetime.utcnow()
        return max(0, delta.days)


class AdminMessage(Base):
    """Mensagens globais do administrador exibidas em todas as salas"""
    __tablename__ = 'admin_messages'
    id = Column(Integer, primary_key=True)
    title = Column(String(100), nullable=False)
    content = Column(Text, nullable=False)
    image_path = Column(String(255), nullable=True)
    link = Column(String(500), nullable=True)  # URL para redirecionamento
    start_date = Column(DateTime, nullable=False)
    end_date = Column(DateTime, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    created_by = Column(Integer, ForeignKey('users.id'), nullable=False)
    priority = Column(Integer, default=1)  # 1=baixa, 2=média, 3=alta
    
    creator = relationship('User', back_populates='created_admin_messages')
    
    @property
    def is_expired(self):
        """Verifica se a mensagem expirou"""
        return datetime.utcnow() > self.end_date
    
    @property
    def is_current(self):
        """Verifica se a mensagem está ativa no período atual"""
        now = datetime.utcnow()
        return (self.is_active and 
                now >= self.start_date and 
                now <= self.end_date)
    
    @property
    def days_remaining(self):
        """Retorna quantos dias restam até o fim"""
        if self.is_expired:
            return 0
        delta = self.end_date - datetime.utcnow()
        return max(0, delta.days)
