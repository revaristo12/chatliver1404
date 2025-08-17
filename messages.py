#!/usr/bin/env python3
"""
Sistema de mensagens com criptografia para o chat.
"""

import os
import base64
import json
from datetime import datetime
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from models import Message, Attachment, User, Room
from flask import current_app
from flask_login import current_user

class MessageEncryption:
    """Classe para gerenciar criptografia de mensagens"""
    
    def __init__(self, room_key=None):
        self.room_key = room_key or self._generate_room_key()
    
    def _generate_room_key(self):
        """Gera uma chave única para a sala"""
        return Fernet.generate_key()
    
    def _get_fernet(self):
        """Retorna instância do Fernet para criptografia"""
        return Fernet(self.room_key)
    
    def encrypt_message(self, text):
        """Criptografa uma mensagem"""
        if not text:
            return text
        
        fernet = self._get_fernet()
        encrypted = fernet.encrypt(text.encode())
        return base64.b64encode(encrypted).decode()
    
    def decrypt_message(self, encrypted_text):
        """Descriptografa uma mensagem"""
        if not encrypted_text:
            return encrypted_text
        
        try:
            fernet = self._get_fernet()
            encrypted_bytes = base64.b64decode(encrypted_text.encode())
            decrypted = fernet.decrypt(encrypted_bytes)
            return decrypted.decode()
        except Exception as e:
            return f"[Mensagem criptografada - Erro: {str(e)}]"

class MessageHandler:
    """Classe para gerenciar mensagens do chat"""
    
    def __init__(self, db_session):
        self.db = db_session
        self.encryption = MessageEncryption()
    
    def create_message(self, room_id, user_id, content, attachment_path=None):
        """Cria uma nova mensagem"""
        try:
            # Criptografar conteúdo se for texto
            if content:
                encrypted_content = self.encryption.encrypt_message(content)
            else:
                encrypted_content = content
            
            message = Message(
                room_id=room_id,
                user_id=user_id,
                content=content,  # Conteúdo original para exibição
                encrypted_content=encrypted_content,  # Conteúdo criptografado
                attachment_path=attachment_path,
                created_at=datetime.utcnow()
            )
            
            self.db.add(message)
            self.db.commit()
            
            return message
        except Exception as e:
            self.db.rollback()
            raise e
    
    def get_room_messages(self, room_id, limit=50, offset=0):
        """Busca mensagens de uma sala"""
        try:
            messages = self.db.query(Message).filter(
                Message.room_id == room_id
            ).order_by(Message.created_at.desc()).offset(offset).limit(limit).all()
            
            # Descriptografar mensagens
            for message in messages:
                if message.message_type == 'text' and message.content:
                    message.content = self.encryption.decrypt_message(message.content)
            
            return messages[::-1]  # Inverter para ordem cronológica
        except Exception as e:
            return []
    
    def delete_message(self, message_id, user_id):
        """Deleta uma mensagem (apenas o autor pode deletar)"""
        try:
            message = self.db.query(Message).filter(
                Message.id == message_id,
                Message.user_id == user_id
            ).first()
            
            if message:
                self.db.delete(message)
                self.db.commit()
                return True
            return False
        except Exception as e:
            self.db.rollback()
            return False
    
    def edit_message(self, message_id, user_id, new_content):
        """Edita uma mensagem (apenas o autor pode editar)"""
        try:
            message = self.db.query(Message).filter(
                Message.id == message_id,
                Message.user_id == user_id
            ).first()
            
            if message and message.message_type == 'text':
                encrypted_content = self.encryption.encrypt_message(new_content)
                message.content = encrypted_content
                message.updated_at = datetime.utcnow()
                self.db.commit()
                return True
            return False
        except Exception as e:
            self.db.rollback()
            return False

class AttachmentHandler:
    """Classe para gerenciar anexos de mensagens"""
    
    def __init__(self, db_session):
        self.db = db_session
    
    def save_attachment(self, file, room_id, user_id):
        """Salva um anexo"""
        try:
            if not file:
                return None
            
            # Verificar tipo de arquivo
            filename = file.filename
            file_ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''
            
            # Determinar tipo de mídia
            if file_ext in ['jpg', 'jpeg', 'png', 'gif', 'webp']:
                media_type = 'image'
            elif file_ext in ['mp4', 'avi', 'mov', 'wmv', 'flv']:
                media_type = 'video'
            elif file_ext in ['mp3', 'wav', 'ogg', 'flac']:
                media_type = 'audio'
            else:
                media_type = 'document'
            
            # Gerar nome único
            import uuid
            unique_filename = f"{uuid.uuid4()}_{filename}"
            file_path = os.path.join('static', 'uploads', unique_filename)
            
            # Salvar arquivo
            file.save(file_path)
            
            # Criar registro no banco
            attachment = Attachment(
                filename=filename,
                file_path=file_path,
                file_size=os.path.getsize(file_path),
                media_type=media_type,
                room_id=room_id,
                uploaded_by=user_id,
                created_at=datetime.utcnow()
            )
            
            self.db.add(attachment)
            self.db.commit()
            
            return attachment
        except Exception as e:
            self.db.rollback()
            raise e
    
    def delete_attachment(self, attachment_id, user_id):
        """Deleta um anexo"""
        try:
            attachment = self.db.query(Attachment).filter(
                Attachment.id == attachment_id,
                Attachment.uploaded_by == user_id
            ).first()
            
            if attachment:
                # Deletar arquivo físico
                if os.path.exists(attachment.file_path):
                    os.remove(attachment.file_path)
                
                self.db.delete(attachment)
                self.db.commit()
                return True
            return False
        except Exception as e:
            self.db.rollback()
            return False

def format_message_for_socket(message, user):
    """Formata mensagem para envio via Socket.IO"""
    attachment_data = None
    if message.attachment_path:
        # Usar os.path.basename para extrair o nome do arquivo independente do sistema operacional
        import os
        filename = os.path.basename(message.attachment_path)
        attachment_data = {
            'filename': filename,
            'file_path': message.attachment_path
        }
    
    return {
        'id': message.id,
        'content': message.content,
        'user': {
            'id': user.id,
            'username': user.username,
            'email': user.email
        },
        'created_at': message.created_at.isoformat(),
        'attachment': attachment_data
    }
