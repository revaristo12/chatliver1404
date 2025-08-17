from passlib.hash import argon2
from flask_login import login_user, logout_user, login_required, current_user
from flask import flash, redirect, url_for, request
from urllib.parse import urlparse
from models import User, Room, RoomMember
from forms import LoginForm, RegistrationForm
import re
import secrets
import string
from datetime import datetime

def hash_password(password):
    """Gera hash da senha usando Argon2"""
    return argon2.hash(password)

def verify_password(password, password_hash):
    """Verifica se a senha está correta"""
    return argon2.verify(password, password_hash)

def is_valid_email(email):
    """Valida formato de email"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

def is_strong_password(password):
    """Verifica se a senha é forte o suficiente"""
    if len(password) < 8:
        return False, "A senha deve ter pelo menos 8 caracteres"
    
    if not re.search(r'[A-Z]', password):
        return False, "A senha deve conter pelo menos uma letra maiúscula"
    
    if not re.search(r'[a-z]', password):
        return False, "A senha deve conter pelo menos uma letra minúscula"
    
    if not re.search(r'\d', password):
        return False, "A senha deve conter pelo menos um número"
    
    return True, "Senha válida"

def generate_secure_token(length=32):
    """Gera token seguro para convites"""
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))

def register_user(db_session, email, password):
    """Registra um novo usuário"""
    # Verificar se email já existe
    existing_user = db_session.query(User).filter_by(email=email).first()
    if existing_user:
        return False, "Email já está em uso"
    
    # Validar email
    if not is_valid_email(email):
        return False, "Formato de email inválido"
    
    # Validar senha
    is_valid, message = is_strong_password(password)
    if not is_valid:
        return False, message
    
    # Criar usuário
    try:
        user = User(
            email=email.lower().strip(),
            password_hash=hash_password(password)
        )
        db_session.add(user)
        db_session.commit()
        return True, user
    except Exception as e:
        db_session.rollback()
        return False, f"Erro ao criar usuário: {str(e)}"

def authenticate_user(db_session, email, password):
    """Autentica um usuário"""
    user = db_session.query(User).filter_by(email=email.lower().strip()).first()
    
    if user and verify_password(password, user.password_hash):
        return user
    return None

def handle_login(db_session, form):
    """Processa o login do usuário"""
    try:
        user = db_session.query(User).filter_by(email=form.email.data).first()
        
        if user and argon2.verify(form.password.data, user.password_hash):
            login_user(user, remember=form.remember_me.data)
            return {'success': True, 'user': user}
        else:
            return {'success': False, 'message': 'Email ou senha inválidos'}
            
    except Exception as e:
        return {'success': False, 'message': f'Erro interno: {str(e)}'}

def handle_registration(db_session, form):
    """Processa o registro de novo usuário"""
    try:
        # Verificar se email já existe
        existing_user = db_session.query(User).filter_by(email=form.email.data).first()
        if existing_user:
            return {'success': False, 'message': 'Este email já está em uso'}
        
        # Verificar se username já existe
        existing_username = db_session.query(User).filter_by(username=form.username.data).first()
        if existing_username:
            return {'success': False, 'message': 'Este nome de usuário já está em uso'}
        
        # Criar hash da senha
        password_hash = argon2.hash(form.password.data)
        
        # Criar usuário
        user = User(
            username=form.username.data,
            email=form.email.data,
            password_hash=password_hash
        )
        
        db_session.add(user)
        db_session.commit()
        
        # Fazer login automaticamente
        login_user(user)
        
        return {'success': True, 'user': user}
        
    except Exception as e:
        db_session.rollback()
        return {'success': False, 'message': f'Erro interno: {str(e)}'}

def create_room_handler(db_session, form, user_id):
    """Cria uma nova sala"""
    try:
        # Gerar slug único
        base_slug = slugify(form.name.data)
        slug = base_slug
        counter = 1
        
        # Verificar se slug já existe
        while db_session.query(Room).filter_by(slug=slug).first():
            slug = f"{base_slug}-{counter}"
            counter += 1
        
        # Criar sala
        room = Room(
            name=form.name.data,
            slug=slug,
            description=form.description.data if hasattr(form, 'description') else None,
            is_private=form.is_private.data if hasattr(form, 'is_private') else False,
            allow_images=form.allow_images.data if hasattr(form, 'allow_images') else True,
            allow_videos=form.allow_videos.data if hasattr(form, 'allow_videos') else True,
            created_at=datetime.utcnow(),
            creator_id=user_id
        )
        
        db_session.add(room)
        db_session.commit()
        
        # Adicionar criador como membro
        member = RoomMember(
            room_id=room.id,
            user_id=user_id,
            role='creator',
            joined_at=datetime.utcnow()
        )
        db_session.add(member)
        db_session.commit()
        
        return {'success': True, 'room': room}
        
    except Exception as e:
        db_session.rollback()
        return {'success': False, 'message': str(e)}

def slugify(text):
    """Converte texto em slug para URLs"""
    text = text.lower()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[-\s]+', '-', text)
    return text.strip('-')

def get_safe_next_page(request):
    """Obtém a próxima página segura para redirecionamento"""
    next_page = request.args.get('next')
    if next_page:
        parsed_url = urlparse(next_page)
        if parsed_url.netloc == '':
            return next_page
    return None

def change_password_handler(db_session, user_id, current_password, new_password):
    """Altera a senha do usuário"""
    try:
        # Buscar o usuário
        user = db_session.query(User).get(user_id)
        if not user:
            return {'success': False, 'message': 'Usuário não encontrado'}
        
        # Verificar se a senha atual está correta
        if not verify_password(current_password, user.password_hash):
            return {'success': False, 'message': 'Senha atual incorreta'}
        
        # Verificar se a nova senha é diferente da atual
        if verify_password(new_password, user.password_hash):
            return {'success': False, 'message': 'A nova senha deve ser diferente da senha atual'}
        
        # Validar força da nova senha
        is_valid, message = is_strong_password(new_password)
        if not is_valid:
            return {'success': False, 'message': message}
        
        # Gerar hash da nova senha
        new_password_hash = hash_password(new_password)
        
        # Atualizar a senha
        user.password_hash = new_password_hash
        db_session.commit()
        
        return {'success': True, 'message': 'Senha alterada com sucesso!'}
        
    except Exception as e:
        db_session.rollback()
        return {'success': False, 'message': f'Erro ao alterar senha: {str(e)}'}
