#!/usr/bin/env python3
"""
Sistema de convites para salas de chat.
"""

import secrets
import string
from datetime import datetime, timedelta
from models import RoomInvite, Room, RoomMember, User
from flask import current_app, url_for
from flask_mail import Mail, Message as MailMessage

class InviteGenerator:
    """Classe para gerar e gerenciar convites"""
    
    def __init__(self, db_session):
        self.db = db_session
    
    def generate_invite_code(self, length=12):
        """Gera um código de convite único"""
        characters = string.ascii_letters + string.digits
        while True:
            code = ''.join(secrets.choice(characters) for _ in range(length))
            # Verificar se o código já existe
            existing = self.db.query(RoomInvite).filter_by(code=code).first()
            if not existing:
                return code
    
    def create_invite(self, room_id, created_by, expires_in_hours=24, max_uses=None):
        """Cria um novo convite"""
        try:
            invite = RoomInvite(
                room_id=room_id,
                code=self.generate_invite_code(),
                created_by=created_by,
                expires_at=datetime.utcnow() + timedelta(hours=expires_in_hours),
                max_uses=max_uses,
                used_count=0,
                created_at=datetime.utcnow()
            )
            
            self.db.add(invite)
            self.db.commit()
            
            return invite
        except Exception as e:
            self.db.rollback()
            raise e
    
    def validate_invite(self, code):
        """Valida um código de convite"""
        try:
            # Busca case-insensitive
            invite = self.db.query(RoomInvite).filter(
                RoomInvite.code.ilike(code)
            ).first()
            
            if not invite:
                return None, "Convite não encontrado"
            
            # Verificar se expirou
            if invite.expires_at < datetime.utcnow():
                return None, "Convite expirado"
            
            # Verificar limite de usos
            if invite.max_uses and invite.used_count >= invite.max_uses:
                return None, "Limite de usos do convite atingido"
            
            return invite, None
        except Exception as e:
            return None, f"Erro ao validar convite: {str(e)}"
    
    def use_invite(self, code, user_id):
        """Usa um convite para adicionar usuário à sala"""
        try:
            invite, error = self.validate_invite(code)
            if error:
                return {'success': False, 'message': error}
            
            # Verificar se usuário já é membro da sala
            existing_member = self.db.query(RoomMember).filter_by(
                room_id=invite.room_id,
                user_id=user_id
            ).first()
            
            if existing_member:
                return {'success': False, 'message': 'Você já é membro desta sala'}
            
            # Adicionar usuário como membro
            member = RoomMember(
                room_id=invite.room_id,
                user_id=user_id,
                role='member',
                joined_at=datetime.utcnow()
            )
            
            self.db.add(member)
            
            # Incrementar contador de usos
            invite.used_count += 1
            
            self.db.commit()
            
            # Buscar informações da sala para retorno
            room = self.db.query(Room).get(invite.room_id)
            
            return {
                'success': True,
                'room_name': room.name,
                'room_slug': room.slug
            }
            
        except Exception as e:
            self.db.rollback()
            return {'success': False, 'message': f'Erro interno: {str(e)}'}
    
    def get_room_invites(self, room_id):
        """Busca todos os convites de uma sala"""
        try:
            invites = self.db.query(RoomInvite).filter_by(room_id=room_id).all()
            return invites
        except Exception as e:
            return []
    
    def delete_invite(self, invite_id):
        """Deleta um convite"""
        try:
            invite = self.db.query(RoomInvite).get(invite_id)
            if invite:
                self.db.delete(invite)
                self.db.commit()
                return True
            return False
        except Exception as e:
            self.db.rollback()
            return False
    
    def revoke_invite(self, invite_id):
        """Revoga um convite (marca como expirado)"""
        try:
            invite = self.db.query(RoomInvite).get(invite_id)
            if invite:
                invite.expires_at = datetime.utcnow()
                self.db.commit()
                return True
            return False
        except Exception as e:
            self.db.rollback()
            return False

class InviteEmailService:
    """Serviço para enviar convites por email"""
    
    def __init__(self, app):
        self.app = app
        self.mail = Mail(app)
    
    def send_invite_email(self, invite, room):
        """Envia email com convite"""
        try:
            # Buscar criador do convite
            creator = self.app.extensions['sqlalchemy'].query(User).get(invite.created_by)
            
            # Buscar sala
            room_obj = self.app.extensions['sqlalchemy'].query(Room).get(invite.room_id)
            
            if not creator or not room_obj:
                return False
            
            # Gerar link direto
            join_url = url_for('chat.join_room_invite', code=invite.code, _external=True)
            
            # Configurar email
            subject = f"Convite para sala: {room_obj.name}"
            
            html_body = f"""
            <html>
            <body>
                <h2>Você foi convidado para uma sala!</h2>
                <p><strong>Sala:</strong> {room_obj.name}</p>
                <p><strong>Convidado por:</strong> {creator.username}</p>
                <p><strong>Código do convite:</strong> {invite.code}</p>
                <p><strong>Expira em:</strong> {invite.expires_at.strftime('%d/%m/%Y %H:%M')}</p>
                
                <p>Para entrar na sala, use um dos links abaixo:</p>
                <ul>
                    <li><a href="{join_url}">Link direto para entrar</a></li>
                    <li>Ou acesse: {join_url}</li>
                </ul>
                
                <p>Se você não tem uma conta, <a href="{url_for('auth.register', _external=True)}">registre-se aqui</a>.</p>
                
                <p>Atenciosamente,<br>Equipe do Chat</p>
            </body>
            </html>
            """
            
            text_body = f"""
            Você foi convidado para uma sala!
            
            Sala: {room_obj.name}
            Convidado por: {creator.username}
            Código do convite: {invite.code}
            Expira em: {invite.expires_at.strftime('%d/%m/%Y %H:%M')}
            
            Para entrar na sala, acesse: {join_url}
            
            Se você não tem uma conta, registre-se em: {url_for('auth.register', _external=True)}
            
            Atenciosamente,
            Equipe do Chat
            """
            
            # Enviar email (por enquanto, apenas simular)
            # Em produção, você configuraria as credenciais SMTP no config.py
            print(f"Email de convite seria enviado para a sala {room_obj.name}")
            print(f"Código: {invite.code}")
            print(f"Link: {join_url}")
            
            return True
            
        except Exception as e:
            print(f"Erro ao enviar email de convite: {e}")
            return False

    def send_access_request_email(self, requester, room, creator):
        """Envia email de solicitação de acesso"""
        try:
            # Gerar link para gerenciar convites
            invites_url = url_for('chat.manage_invites', slug=room.slug, _external=True)
            
            # Configurar email
            subject = f"Solicitação de acesso à sala: {room.name}"
            
            html_body = f"""
            <html>
            <body>
                <h2>Nova solicitação de acesso!</h2>
                <p><strong>Usuário:</strong> {requester.username} ({requester.email})</p>
                <p><strong>Sala:</strong> {room.name}</p>
                <p><strong>Data da solicitação:</strong> {datetime.utcnow().strftime('%d/%m/%Y %H:%M')}</p>
                
                <p>Para gerenciar convites e membros da sala, acesse:</p>
                <p><a href="{invites_url}">{invites_url}</a></p>
                
                <p>Atenciosamente,<br>Equipe do Chat</p>
            </body>
            </html>
            """
            
            text_body = f"""
            Nova solicitação de acesso!
            
            Usuário: {requester.username} ({requester.email})
            Sala: {room.name}
            Data da solicitação: {datetime.utcnow().strftime('%d/%m/%Y %H:%M')}
            
            Para gerenciar convites e membros da sala, acesse:
            {invites_url}
            
            Atenciosamente,
            Equipe do Chat
            """
            
            # Enviar email (por enquanto, apenas simular)
            print(f"Email de solicitação de acesso seria enviado para {creator.username}")
            print(f"Usuário: {requester.username} quer acessar a sala {room.name}")
            print(f"Link para gerenciar: {invites_url}")
            
            return True
            
        except Exception as e:
            print(f"Erro ao enviar email de solicitação: {e}")
            return False

    def send_access_approved_email(self, user, room):
        """Envia email de aprovação de acesso"""
        try:
            # Gerar link para entrar na sala
            room_url = url_for('chat.room', slug=room.slug, _external=True)
            
            # Configurar email
            subject = f"Acesso aprovado para a sala: {room.name}"
            
            html_body = f"""
            <html>
            <body>
                <h2>Seu acesso foi aprovado! 🎉</h2>
                <p><strong>Parabéns!</strong> Sua solicitação de acesso à sala foi aprovada.</p>
                
                <p><strong>Sala:</strong> {room.name}</p>
                <p><strong>Data da aprovação:</strong> {datetime.utcnow().strftime('%d/%m/%Y %H:%M')}</p>
                
                <p>Para acessar a sala, clique no link abaixo:</p>
                <p><a href="{room_url}">Entrar na sala {room.name}</a></p>
                
                <p>Atenciosamente,<br>Equipe do Chat</p>
            </body>
            </html>
            """
            
            text_body = f"""
            Seu acesso foi aprovado! 🎉
            
            Parabéns! Sua solicitação de acesso à sala foi aprovada.
            
            Sala: {room.name}
            Data da aprovação: {datetime.utcnow().strftime('%d/%m/%Y %H:%M')}
            
            Para acessar a sala, acesse: {room_url}
            
            Atenciosamente,
            Equipe do Chat
            """
            
            # Enviar email (por enquanto, apenas simular)
            print(f"Email de aprovação seria enviado para {user.username}")
            print(f"Usuário: {user.username} teve acesso aprovado para a sala {room.name}")
            print(f"Link da sala: {room_url}")
            
            return True
            
        except Exception as e:
            print(f"Erro ao enviar email de aprovação: {e}")
            return False

    def send_access_rejected_email(self, user, room):
        """Envia email de rejeição de acesso"""
        try:
            # Configurar email
            subject = f"Acesso negado para a sala: {room.name}"
            
            html_body = f"""
            <html>
            <body>
                <h2>Sobre sua solicitação de acesso</h2>
                <p>Infelizmente, sua solicitação de acesso à sala foi negada.</p>
                
                <p><strong>Sala:</strong> {room.name}</p>
                <p><strong>Data da resposta:</strong> {datetime.utcnow().strftime('%d/%m/%Y %H:%M')}</p>
                
                <p>Você pode tentar solicitar acesso novamente no futuro, ou entrar em contato com o administrador da sala.</p>
                
                <p>Atenciosamente,<br>Equipe do Chat</p>
            </body>
            </html>
            """
            
            text_body = f"""
            Sobre sua solicitação de acesso
            
            Infelizmente, sua solicitação de acesso à sala foi negada.
            
            Sala: {room.name}
            Data da resposta: {datetime.utcnow().strftime('%d/%m/%Y %H:%M')}
            
            Você pode tentar solicitar acesso novamente no futuro, ou entrar em contato com o administrador da sala.
            
            Atenciosamente,
            Equipe do Chat
            """
            
            # Enviar email (por enquanto, apenas simular)
            print(f"Email de rejeição seria enviado para {user.username}")
            print(f"Usuário: {user.username} teve acesso negado para a sala {room.name}")
            
            return True
            
        except Exception as e:
            print(f"Erro ao enviar email de rejeição: {e}")
            return False

def format_invite_for_display(invite, room, creator):
    """Formata convite para exibição"""
    return {
        'id': invite.id,
        'code': invite.code,
        'room': {
            'id': room.id,
            'name': room.name,
            'slug': room.slug
        },
        'creator': {
            'id': creator.id,
            'username': creator.username
        },
        'expires_at': invite.expires_at.isoformat(),
        'max_uses': invite.max_uses,
        'used_count': invite.used_count,
        'is_expired': invite.expires_at < datetime.utcnow(),
        'is_used_up': invite.max_uses and invite.used_count >= invite.max_uses,
        'created_at': invite.created_at.isoformat()
    }
