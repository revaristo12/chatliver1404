#!/usr/bin/env python3
"""
Rotas para o chat em tempo real.
"""

from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for, current_app
from flask_login import login_required, current_user
from flask_socketio import emit, join_room, leave_room
from models import Room, RoomMember, Message, Attachment, RoomInvite, User, AccessRequest
from forms import MessageForm, InviteForm
from messages import MessageHandler, MessageEncryption, format_message_for_socket
from invites import InviteGenerator, InviteEmailService
import os
from werkzeug.utils import secure_filename
from datetime import datetime

chat_bp = Blueprint('chat', __name__)

# Configurações de upload
ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif', 'mp4', 'mp3', 'wav', 'doc', 'docx', 'xls', 'xlsx'}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@chat_bp.route('/chat/<slug>')
@login_required
def room(slug):
    """Página principal do chat"""
    db = current_app.extensions['sqlalchemy']
    room = db.session.query(Room).filter_by(slug=slug).first_or_404()
    
    # Verificar se o usuário é membro da sala
    member = db.session.query(RoomMember).filter_by(
        room_id=room.id, 
        user_id=current_user.id
    ).first()
    
    if not member:
        flash('Você não tem acesso a esta sala.', 'error')
        return redirect(url_for('rooms.index'))
    
    # Buscar mensagens recentes
    messages = db.session.query(Message).filter_by(room_id=room.id)\
        .order_by(Message.created_at.desc()).limit(50).all()
    
    # Buscar convites ativos (apenas para criadores/admins)
    invites = []
    if member.role in ['creator', 'admin']:
        invites = db.session.query(RoomInvite).filter_by(room_id=room.id, is_active=True).all()
    
    return render_template('chat/room.html', 
                         room=room, 
                         member=member, 
                         messages=messages,
                         invites=invites)

@chat_bp.route('/chat/<slug>/messages')
@login_required
def get_messages(slug):
    """API para buscar mensagens da sala"""
    db = current_app.extensions['sqlalchemy']
    room = db.session.query(Room).filter_by(slug=slug).first_or_404()
    
    # Verificar se o usuário é membro da sala
    member = db.session.query(RoomMember).filter_by(
        room_id=room.id, 
        user_id=current_user.id
    ).first()
    
    if not member:
        return jsonify({'error': 'Acesso negado'}), 403
    
    # Buscar mensagens
    page = request.args.get('page', 1, type=int)
    per_page = 50
    
    messages = db.session.query(Message).filter_by(room_id=room.id)\
        .order_by(Message.created_at.desc())\
        .offset((page - 1) * per_page).limit(per_page).all()
    
    # Formatar mensagens
    message_handler = MessageHandler(db.session)
    formatted_messages = []
    
    for msg in messages:
        formatted_msg = message_handler.format_message_for_socket(msg)
        formatted_messages.append(formatted_msg)
    
    return jsonify({
        'messages': formatted_messages,
        'has_more': len(messages) == per_page
    })

@chat_bp.route('/chat/<slug>/send', methods=['POST'])
@login_required
def send_message(slug):
    """API para enviar mensagem"""
    db = current_app.extensions['sqlalchemy']
    room = db.session.query(Room).filter_by(slug=slug).first_or_404()
    
    # Verificar se o usuário é membro da sala
    member = db.session.query(RoomMember).filter_by(
        room_id=room.id, 
        user_id=current_user.id
    ).first()
    
    if not member:
        return jsonify({'error': 'Acesso negado'}), 403
    
    # Processar formulário
    content = request.form.get('content', '').strip()
    attachment = request.files.get('attachment')
    
    if not content and not attachment:
        return jsonify({'error': 'Mensagem ou anexo é obrigatório'}), 400
    
    try:
        # Processar anexo se houver
        attachment_path = None
        if attachment and attachment.filename:
            if not allowed_file(attachment.filename):
                return jsonify({'error': 'Tipo de arquivo não permitido'}), 400
            
            if attachment.content_length and attachment.content_length > MAX_FILE_SIZE:
                return jsonify({'error': 'Arquivo muito grande (máx. 10MB)'}), 400
            
            filename = secure_filename(attachment.filename)
            timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
            filename = f"{timestamp}_{filename}"
            
            # Criar diretório se não existir
            upload_dir = os.path.join(current_app.root_path, 'static', 'uploads')
            os.makedirs(upload_dir, exist_ok=True)
            
            attachment_path = os.path.join('uploads', filename)
            file_path = os.path.join(upload_dir, filename)
            attachment.save(file_path)
        
        # Criar mensagem
        message_handler = MessageHandler(db.session)
        message = message_handler.create_message(
            room_id=room.id,
            user_id=current_user.id,
            content=content,
            attachment_path=attachment_path
        )
        
        # Formatar mensagem para Socket.IO
        formatted_message = format_message_for_socket(message)
        
        # Emitir via Socket.IO
        from flask_socketio import emit
        emit('message', formatted_message, room=slug, namespace='/')
        
        return jsonify({'success': True, 'message': 'Mensagem enviada com sucesso!'})
        
    except Exception as e:
        return jsonify({'error': f'Erro ao enviar mensagem: {str(e)}'}), 500

@chat_bp.route('/chat/<slug>/invites')
@login_required
def manage_invites(slug):
    """Gerenciar convites da sala"""
    db = current_app.extensions['sqlalchemy']
    room = db.session.query(Room).filter_by(slug=slug).first_or_404()
    
    # Verificar se o usuário é criador ou admin
    member = db.session.query(RoomMember).filter_by(
        room_id=room.id, 
        user_id=current_user.id
    ).first()
    
    if not member or member.role not in ['creator', 'admin']:
        flash('Apenas criadores e administradores podem gerenciar convites.', 'error')
        return redirect(url_for('chat.room', slug=slug))
    
    # Buscar convites ativos
    invites = db.session.query(RoomInvite).filter_by(room_id=room.id, is_active=True).all()
    
    # Criar formulário para o template
    form = InviteForm()
    
    return render_template('chat/invites.html', room=room, invites=invites, form=form)

@chat_bp.route('/chat/<slug>/invites/create', methods=['POST'])
@login_required
def create_invite(slug):
    """Criar novo convite"""
    db = current_app.extensions['sqlalchemy']
    room = db.session.query(Room).filter_by(slug=slug).first_or_404()
    
    # Verificar se o usuário é criador ou admin
    member = db.session.query(RoomMember).filter_by(
        room_id=room.id, 
        user_id=current_user.id
    ).first()
    
    if not member or member.role not in ['creator', 'admin']:
        flash('Apenas criadores e administradores podem criar convites.', 'error')
        return redirect(url_for('chat.manage_invites', slug=slug))
    
    # Processar dados do formulário
    expires_in_hours = request.form.get('expires_in_hours', type=int)
    max_uses = request.form.get('max_uses', type=int)
    
    # Validações
    if not expires_in_hours or expires_in_hours < 1 or expires_in_hours > 168:
        flash('Horas de expiração deve ser entre 1 e 168.', 'error')
        return redirect(url_for('chat.manage_invites', slug=slug))
    
    if max_uses is not None and (max_uses < 1 or max_uses > 100):
        flash('Máximo de usos deve ser entre 1 e 100.', 'error')
        return redirect(url_for('chat.manage_invites', slug=slug))
    
    try:
        # Criar convite
        invite_generator = InviteGenerator(db.session)
        result = invite_generator.create_invite(
            room_id=room.id,
            created_by=current_user.id,
            expires_in_hours=expires_in_hours,
            max_uses=max_uses
        )
        
        if result['success']:
            flash('Convite criado com sucesso!', 'success')
        else:
            flash(f'Erro ao criar convite: {result["message"]}', 'error')
            
    except Exception as e:
        flash(f'Erro interno: {str(e)}', 'error')
    
    return redirect(url_for('chat.manage_invites', slug=slug))

@chat_bp.route('/chat/<slug>/invites/<int:invite_id>/delete', methods=['POST'])
@login_required
def delete_invite(slug, invite_id):
    """Deletar convite"""
    db = current_app.extensions['sqlalchemy']
    room = db.session.query(Room).filter_by(slug=slug).first_or_404()
    
    # Verificar se o usuário é criador ou admin
    member = db.session.query(RoomMember).filter_by(
        room_id=room.id, 
        user_id=current_user.id
    ).first()
    
    if not member or member.role not in ['creator', 'admin']:
        return jsonify({'error': 'Acesso negado'}), 403
    
    invite = db.session.query(RoomInvite).filter_by(id=invite_id, room_id=room.id).first_or_404()
    
    try:
        invite_generator = InviteGenerator(db.session)
        if invite_generator.delete_invite(invite.id):
            return jsonify({'success': True, 'message': 'Convite deletado com sucesso!'})
        else:
            return jsonify({'error': 'Erro ao deletar convite'}), 500
    except Exception as e:
        return jsonify({'error': f'Erro interno: {str(e)}'}), 500

@chat_bp.route('/chat/<slug>/access-requests')
@login_required
def manage_access_requests(slug):
    """Gerenciar solicitações de acesso da sala"""
    db = current_app.extensions['sqlalchemy']
    room = db.session.query(Room).filter_by(slug=slug).first_or_404()
    
    # Verificar se o usuário é criador ou admin
    member = db.session.query(RoomMember).filter_by(
        room_id=room.id, 
        user_id=current_user.id
    ).first()
    
    if not member or member.role not in ['creator', 'admin']:
        flash('Apenas criadores e administradores podem gerenciar solicitações de acesso.', 'error')
        return redirect(url_for('chat.room', slug=slug))
    
    # Buscar solicitações pendentes
    pending_requests = db.session.query(AccessRequest).filter_by(
        room_id=room.id,
        status='pending'
    ).order_by(AccessRequest.requested_at.desc()).all()
    
    # Buscar solicitações processadas (aprovadas/rejeitadas)
    processed_requests = db.session.query(AccessRequest).filter(
        AccessRequest.room_id == room.id,
        AccessRequest.status != 'pending'
    ).order_by(AccessRequest.processed_at.desc()).limit(20).all()
    
    return render_template('chat/access_requests.html', 
                         room=room, 
                         pending_requests=pending_requests,
                         processed_requests=processed_requests)

@chat_bp.route('/chat/<slug>/access-requests/<int:request_id>/approve', methods=['POST'])
@login_required
def approve_access_request(slug, request_id):
    """Aprovar solicitação de acesso"""
    db = current_app.extensions['sqlalchemy']
    room = db.session.query(Room).filter_by(slug=slug).first_or_404()
    
    # Verificar se o usuário é criador ou admin
    member = db.session.query(RoomMember).filter_by(
        room_id=room.id, 
        user_id=current_user.id
    ).first()
    
    if not member or member.role not in ['creator', 'admin']:
        return jsonify({'error': 'Acesso negado'}), 403
    
    access_request = db.session.query(AccessRequest).filter_by(
        id=request_id,
        room_id=room.id,
        status='pending'
    ).first_or_404()
    
    try:
        # Aprovar solicitação
        access_request.status = 'approved'
        access_request.processed_at = datetime.utcnow()
        access_request.processed_by = current_user.id
        
        # Adicionar usuário como membro da sala
        new_member = RoomMember(
            room_id=room.id,
            user_id=access_request.user_id,
            role='member'
        )
        db.session.add(new_member)
        db.session.commit()
        
        # Enviar email de notificação
        try:
            email_service = InviteEmailService(current_app)
            email_service.send_access_approved_email(access_request.user, room)
        except Exception as e:
            print(f"Erro ao enviar email de aprovação: {e}")
        
        return jsonify({'success': True, 'message': 'Acesso aprovado com sucesso!'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Erro interno: {str(e)}'}), 500

@chat_bp.route('/chat/<slug>/access-requests/<int:request_id>/reject', methods=['POST'])
@login_required
def reject_access_request(slug, request_id):
    """Rejeitar solicitação de acesso"""
    db = current_app.extensions['sqlalchemy']
    room = db.session.query(Room).filter_by(slug=slug).first_or_404()
    
    # Verificar se o usuário é criador ou admin
    member = db.session.query(RoomMember).filter_by(
        room_id=room.id, 
        user_id=current_user.id
    ).first()
    
    if not member or member.role not in ['creator', 'admin']:
        return jsonify({'error': 'Acesso negado'}), 403
    
    access_request = db.session.query(AccessRequest).filter_by(
        id=request_id,
        room_id=room.id,
        status='pending'
    ).first_or_404()
    
    try:
        # Rejeitar solicitação
        access_request.status = 'rejected'
        access_request.processed_at = datetime.utcnow()
        access_request.processed_by = current_user.id
        
        db.session.commit()
        
        # Enviar email de notificação
        try:
            email_service = InviteEmailService(current_app)
            email_service.send_access_rejected_email(access_request.user, room)
        except Exception as e:
            print(f"Erro ao enviar email de rejeição: {e}")
        
        return jsonify({'success': True, 'message': 'Solicitação rejeitada com sucesso!'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Erro interno: {str(e)}'}), 500

@chat_bp.route('/join/<code>')
@login_required
def join_room_invite(code):
    """Entrar em sala via código de convite"""
    db = current_app.extensions['sqlalchemy']
    
    try:
        invite_generator = InviteGenerator(db.session)
        result = invite_generator.use_invite(code, current_user.id)
        
        if result['success']:
            flash(f'Você entrou na sala "{result["room_name"]}" com sucesso!', 'success')
            return redirect(url_for('chat.room', slug=result['room_slug']))
        else:
            flash(result['message'], 'error')
            return redirect(url_for('rooms.index'))
            
    except Exception as e:
        flash(f'Erro ao usar convite: {str(e)}', 'error')
        return redirect(url_for('rooms.index'))

def register_socket_events(socketio):
    """Registra eventos do Socket.IO"""
    
    @socketio.on('join')
    def on_join(data):
        """Usuário entra na sala"""
        room = data.get('room')
        if room:
            join_room(room)
            emit('status', {'msg': f'{current_user.username} entrou na sala.'}, room=room)
    
    @socketio.on('leave')
    def on_leave(data):
        """Usuário sai da sala"""
        room = data.get('room')
        if room:
            leave_room(room)
            emit('status', {'msg': f'{current_user.username} saiu da sala.'}, room=room)
    
    @socketio.on('message')
    def on_message(data):
        """Nova mensagem"""
        room = data.get('room')
        content = data.get('content', '').strip()
        
        if not room or not content:
            return
        
        # Verificar se o usuário é membro da sala
        db = current_app.extensions['sqlalchemy']
        member = db.session.query(RoomMember).filter_by(
            room_id=room,
            user_id=current_user.id
        ).first()
        
        if not member:
            return
        
        try:
            # Criar mensagem
            message_handler = MessageHandler(db.session)
            message = message_handler.create_message(
                room_id=room,
                user_id=current_user.id,
                content=content
            )
            
            # Formatar mensagem para Socket.IO
            formatted_message = format_message_for_socket(message)
            
            # Emitir para todos na sala
            emit('message', formatted_message, room=room)
            
        except Exception as e:
            print(f"Erro ao processar mensagem: {e}")
    
    @socketio.on('typing')
    def on_typing(data):
        """Usuário está digitando"""
        room = data.get('room')
        is_typing = data.get('is_typing', False)
        
        if room:
            emit('typing', {
                'user': current_user.username,
                'is_typing': is_typing
            }, room=room, include_self=False)



