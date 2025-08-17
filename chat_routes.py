#!/usr/bin/env python3
"""
Rotas para o chat em tempo real.
"""

from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for, current_app
from flask_login import login_required, current_user
from flask_socketio import emit, join_room, leave_room
from models import User, Room, RoomMember, RoomInvite, Message, Attachment, AccessRequest, Advertisement, AdminMessage
from forms import MessageForm, InviteForm, AccessRequestForm, AdvertisementForm
from messages import MessageHandler, MessageEncryption, format_message_for_socket
from invites import InviteGenerator, InviteEmailService
import os
from werkzeug.utils import secure_filename
from datetime import datetime, timezone


chat_bp = Blueprint('chat', __name__)

# Configurações de upload
ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif', 'mp4', 'mp3', 'wav', 'doc', 'docx', 'xls', 'xlsx'}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@chat_bp.route('/<slug>')
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
    
    # Buscar anúncios ativos da sala
    now = datetime.utcnow()
    active_advertisements = db.session.query(Advertisement).filter(
        Advertisement.room_id == room.id,
        Advertisement.is_active == True,
        Advertisement.start_date <= now,
        Advertisement.end_date >= now
    ).order_by(Advertisement.priority.desc(), Advertisement.created_at.desc()).all()
    
    # Buscar mensagens do administrador ativas (globais)
    active_admin_messages = db.session.query(AdminMessage).filter(
        AdminMessage.is_active == True,
        AdminMessage.start_date <= now,
        AdminMessage.end_date >= now
    ).order_by(AdminMessage.priority.desc(), AdminMessage.created_at.desc()).all()
    
    return render_template('chat/room.html', 
                         room=room, 
                         member=member, 
                         messages=messages,
                         active_advertisements=active_advertisements,
                         active_admin_messages=active_admin_messages)

@chat_bp.route('/<slug>/messages')
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
        # Buscar usuário da mensagem
        user = db.session.query(User).get(msg.user_id)
        if user:
            formatted_msg = format_message_for_socket(msg, user)
            formatted_messages.append(formatted_msg)
    
    return jsonify({
        'messages': formatted_messages,
        'has_more': len(messages) == per_page
    })

@chat_bp.route('/<slug>/send', methods=['POST'])
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
            timestamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
            filename = f"{timestamp}_{filename}"
            
            # Criar diretório se não existir
            upload_dir = os.path.join(current_app.root_path, 'static', 'uploads')
            os.makedirs(upload_dir, exist_ok=True)
            
            # Usar barras normais para o caminho no banco (compatível com URLs)
            attachment_path = f"uploads/{filename}"
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
        formatted_message = format_message_for_socket(message, current_user)
        
        # Emitir via Socket.IO para todos na sala
        from flask_socketio import emit
        emit('message', formatted_message, room=slug, namespace='/')
        
        # Retornar mensagem formatada para o cliente
        return jsonify({'success': True, 'message': formatted_message})
        
    except Exception as e:
        return jsonify({'error': f'Erro ao enviar mensagem: {str(e)}'}), 500

@chat_bp.route('/<slug>/invites')
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

@chat_bp.route('/<slug>/invites/create', methods=['POST'])
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

@chat_bp.route('/<slug>/invites/<int:invite_id>/delete', methods=['POST'])
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

@chat_bp.route('/<slug>/access-requests')
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

@chat_bp.route('/<slug>/access-requests/<int:request_id>/approve', methods=['POST'])
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
        access_request.processed_at = datetime.now(timezone.utc)
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

@chat_bp.route('/<slug>/access-requests/<int:request_id>/reject', methods=['POST'])
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
        access_request.processed_at = datetime.now(timezone.utc)
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

@chat_bp.route('/join-invite', methods=['GET', 'POST'])
@login_required
def join_invite_form():
    """Formulário para entrar em sala via código de convite"""
    if request.method == 'POST':
        invite_code = request.form.get('invite_code', '').strip().upper()
        
        if not invite_code:
            flash('Por favor, digite o código do convite.', 'error')
            return render_template('chat/join_invite.html')
        
        try:
            # Usar o código do convite
            db_session = current_app.extensions['sqlalchemy'].session
            invite_generator = InviteGenerator(db_session)
            result = invite_generator.use_invite(invite_code, current_user.id)
            
            if result['success']:
                flash(f'Você entrou na sala "{result["room_name"]}" com sucesso!', 'success')
                return redirect(url_for('chat.room', slug=result['room_slug']))
            else:
                flash(result['message'], 'error')
                
        except Exception as e:
            flash(f'Erro ao usar convite: {str(e)}', 'error')
    
    return render_template('chat/join_invite.html')

@chat_bp.route('/<slug>/messages/<int:message_id>/delete', methods=['POST'])
@login_required
def delete_message(slug, message_id):
    """Deleta uma mensagem (apenas o autor ou admin pode deletar)"""
    try:
        print(f"=== INICIANDO DELETE MESSAGE ===")
        print(f"Slug: {slug}, Message ID: {message_id}")
        print(f"Usuário atual: {current_user.username} (ID: {current_user.id})")
        
        # Verificar se o usuário está logado
        if not current_user.is_authenticated:
            print("Usuário não autenticado")
            return jsonify({'success': False, 'error': 'Usuário não autenticado'}), 401
        
        # Obter sessão do banco
        db = current_app.extensions['sqlalchemy']
        print("Sessão do banco obtida com sucesso")
        
        # Buscar a sala
        room = db.session.query(Room).filter_by(slug=slug).first()
        if not room:
            print(f"Sala não encontrada: {slug}")
            return jsonify({'success': False, 'error': 'Sala não encontrada'}), 404
        
        print(f"Sala encontrada: {room.name} (ID: {room.id})")
        
        # Verificar se o usuário é membro da sala
        member = db.session.query(RoomMember).filter_by(
            room_id=room.id,
            user_id=current_user.id
        ).first()
        
        if not member:
            print("Usuário não é membro da sala")
            return jsonify({'success': False, 'error': 'Acesso negado'}), 403
        
        print(f"Usuário é membro da sala com role: {member.role}")
        
        # Buscar a mensagem
        message = db.session.query(Message).filter_by(
            id=message_id,
            room_id=room.id
        ).first()
        
        if not message:
            print(f"Mensagem não encontrada: ID {message_id}")
            return jsonify({'success': False, 'error': 'Mensagem não encontrada'}), 404
        
        print(f"Mensagem encontrada: ID {message.id}, Autor: {message.user_id}")
        
        # Verificar permissões: apenas o autor ou admin/creator pode deletar
        can_delete = (
            message.user_id == current_user.id or  # Autor da mensagem
            member.role in ['creator', 'admin']     # Admin da sala
        )
        
        if not can_delete:
            print("Usuário não tem permissão para deletar")
            return jsonify({'success': False, 'error': 'Sem permissão para deletar esta mensagem'}), 403
        
        print("Permissão confirmada, deletando mensagem...")
        
        # Deletar a mensagem (simples, sem anexos por enquanto)
        db.session.delete(message)
        db.session.commit()
        print("Mensagem deletada com sucesso do banco")
        
        # Retornar sucesso (a página será recarregada no frontend)
        return jsonify({
            'success': True,
            'message': 'Mensagem deletada com sucesso'
        })
        
    except Exception as e:
        print(f"=== ERRO NA FUNÇÃO DELETE_MESSAGE ===")
        print(f"Erro: {str(e)}")
        print(f"Tipo do erro: {type(e).__name__}")
        import traceback
        traceback.print_exc()
        
        # Tentar fazer rollback se possível
        try:
            if 'db' in locals() and hasattr(db, 'session'):
                db.session.rollback()
                print("Rollback realizado")
        except Exception as rollback_error:
            print(f"Erro no rollback: {rollback_error}")
        
        return jsonify({
            'success': False,
            'error': f'Erro interno do servidor: {str(e)}'
        }), 500

# ============================================================================
# ROTAS PARA GERENCIAR ANÚNCIOS
# ============================================================================

@chat_bp.route('/<slug>/advertisements')
@login_required
def manage_advertisements(slug):
    """Gerenciar anúncios da sala"""
    try:
        db = current_app.extensions['sqlalchemy']
        
        # Buscar sala
        room = db.session.query(Room).filter_by(slug=slug).first()
        if not room:
            flash('Sala não encontrada', 'error')
            return redirect(url_for('rooms.index'))
        
        # Verificar se é membro
        member = db.session.query(RoomMember).filter_by(
            room_id=room.id,
            user_id=current_user.id
        ).first()
        if not member:
            flash('Acesso negado', 'error')
            return redirect(url_for('rooms.index'))
        
        # Verificar se é admin ou creator
        if member.role not in ['creator', 'admin']:
            flash('Apenas administradores podem gerenciar anúncios', 'error')
            return redirect(url_for('chat.room', slug=slug))
        
        # Buscar anúncios da sala
        advertisements = db.session.query(Advertisement).filter_by(
            room_id=room.id
        ).order_by(Advertisement.priority.desc(), Advertisement.created_at.desc()).all()
        
        form = AdvertisementForm()
        
        return render_template('chat/advertisements.html', 
                             room=room, 
                             member=member, 
                             advertisements=advertisements,
                             form=form)
        
    except Exception as e:
        print(f"Erro ao gerenciar anúncios: {e}")
        flash('Erro interno do servidor', 'error')
        return redirect(url_for('rooms.index'))


@chat_bp.route('/<slug>/advertisements/create', methods=['GET', 'POST'])
@login_required
def create_advertisement(slug):
    """Criar novo anúncio"""
    try:
        db = current_app.extensions['sqlalchemy']
        
        # Buscar sala
        room = db.session.query(Room).filter_by(slug=slug).first()
        if not room:
            flash('Sala não encontrada', 'error')
            return redirect(url_for('rooms.index'))
        
        # Verificar se é membro
        member = db.session.query(RoomMember).filter_by(
            room_id=room.id,
            user_id=current_user.id
        ).first()
        if not member:
            flash('Acesso negado', 'error')
            return redirect(url_for('rooms.index'))
        
        # Verificar se é admin ou creator
        if member.role not in ['creator', 'admin']:
            flash('Apenas administradores podem criar anúncios', 'error')
            return redirect(url_for('chat.room', slug=slug))
        
        form = AdvertisementForm()
        
        if form.validate_on_submit():
            # Validações adicionais de data
            from datetime import datetime, timedelta
            
            start_date = form.start_date.data
            end_date = form.end_date.data
            now = datetime.now()
            
            # Verificar se a data de início não é no passado
            if start_date < now:
                flash('Data de início não pode ser no passado', 'error')
                return render_template('chat/create_advertisement.html', 
                                     room=room, 
                                     member=member, 
                                     form=form)
            
            # Verificar se a data de fim é posterior à data de início
            if end_date <= start_date:
                flash('Data de fim deve ser posterior à data de início', 'error')
                return render_template('chat/create_advertisement.html', 
                                     room=room, 
                                     member=member, 
                                     form=form)
            
            # Verificar se a data de fim não é muito longe no futuro (máximo 1 ano)
            max_future_date = now + timedelta(days=365)
            if end_date > max_future_date:
                flash('Data de fim não pode ser mais de 1 ano no futuro', 'error')
                return render_template('chat/create_advertisement.html', 
                                     room=room, 
                                     member=member, 
                                     form=form)
            
            # Processar upload de imagem
            image_path = None
            if 'image' in request.files:
                file = request.files['image']
                if file and file.filename:
                    filename = secure_filename(file.filename)
                    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                    filename = f"{timestamp}_{filename}"
                    file_path = f"uploads/advertisements/{filename}"
                    
                    # Criar diretório se não existir
                    os.makedirs(os.path.join(current_app.static_folder, 'uploads/advertisements'), exist_ok=True)
                    
                    # Salvar arquivo
                    file.save(os.path.join(current_app.static_folder, file_path))
                    image_path = file_path
            
            # Criar anúncio
            advertisement = Advertisement(
                room_id=room.id,
                title=form.title.data,
                content=form.content.data,
                image_path=image_path,
                link=form.link.data,
                start_date=form.start_date.data,
                end_date=form.end_date.data,
                priority=int(form.priority.data),
                is_active=form.is_active.data,
                created_by=current_user.id
            )
            
            db.session.add(advertisement)
            db.session.commit()
            
            flash('Anúncio criado com sucesso!', 'success')
            return redirect(url_for('chat.manage_advertisements', slug=slug))
        
        return render_template('chat/create_advertisement.html', 
                             room=room, 
                             member=member, 
                             form=form)
        
    except Exception as e:
        print(f"Erro ao criar anúncio: {e}")
        flash('Erro interno do servidor', 'error')
        return redirect(url_for('chat.manage_advertisements', slug=slug))


@chat_bp.route('/<slug>/advertisements/<int:advertisement_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_advertisement(slug, advertisement_id):
    """Editar anúncio existente"""
    try:
        db = current_app.extensions['sqlalchemy']
        
        # Buscar sala
        room = db.session.query(Room).filter_by(slug=slug).first()
        if not room:
            flash('Sala não encontrada', 'error')
            return redirect(url_for('rooms.index'))
        
        # Verificar se é membro
        member = db.session.query(RoomMember).filter_by(
            room_id=room.id,
            user_id=current_user.id
        ).first()
        if not member:
            flash('Acesso negado', 'error')
            return redirect(url_for('rooms.index'))
        
        # Verificar se é admin ou creator
        if member.role not in ['creator', 'admin']:
            flash('Apenas administradores podem editar anúncios', 'error')
            return redirect(url_for('chat.room', slug=slug))
        
        # Buscar anúncio
        advertisement = db.session.query(Advertisement).filter_by(
            id=advertisement_id,
            room_id=room.id
        ).first()
        if not advertisement:
            flash('Anúncio não encontrado', 'error')
            return redirect(url_for('chat.manage_advertisements', slug=slug))
        
        form = AdvertisementForm(obj=advertisement)
        
        if form.validate_on_submit():
            # Validações adicionais de data
            from datetime import datetime, timedelta
            
            start_date = form.start_date.data
            end_date = form.end_date.data
            now = datetime.now()
            
            # Verificar se a data de início não é no passado
            if start_date < now:
                flash('Data de início não pode ser no passado', 'error')
                return render_template('chat/edit_advertisement.html', 
                                     room=room, 
                                     member=member, 
                                     advertisement=advertisement,
                                     form=form)
            
            # Verificar se a data de fim é posterior à data de início
            if end_date <= start_date:
                flash('Data de fim deve ser posterior à data de início', 'error')
                return render_template('chat/edit_advertisement.html', 
                                     room=room, 
                                     member=member, 
                                     advertisement=advertisement,
                                     form=form)
            
            # Verificar se a data de fim não é muito longe no futuro (máximo 1 ano)
            max_future_date = now + timedelta(days=365)
            if end_date > max_future_date:
                flash('Data de fim não pode ser mais de 1 ano no futuro', 'error')
                return render_template('chat/edit_advertisement.html', 
                                     room=room, 
                                     member=member, 
                                     advertisement=advertisement,
                                     form=form)
            
            # Processar upload de nova imagem
            if 'image' in request.files:
                file = request.files['image']
                if file and file.filename:
                    # Deletar imagem antiga se existir
                    if advertisement.image_path:
                        old_file_path = os.path.join(current_app.static_folder, advertisement.image_path)
                        if os.path.exists(old_file_path):
                            os.remove(old_file_path)
                    
                    filename = secure_filename(file.filename)
                    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                    filename = f"{timestamp}_{filename}"
                    file_path = f"uploads/advertisements/{filename}"
                    
                    # Criar diretório se não existir
                    os.makedirs(os.path.join(current_app.static_folder, 'uploads/advertisements'), exist_ok=True)
                    
                    # Salvar arquivo
                    file.save(os.path.join(current_app.static_folder, file_path))
                    advertisement.image_path = file_path
            
            # Atualizar anúncio
            advertisement.title = form.title.data
            advertisement.content = form.content.data
            advertisement.link = form.link.data
            advertisement.start_date = form.start_date.data
            advertisement.end_date = form.end_date.data
            advertisement.priority = int(form.priority.data)
            advertisement.is_active = form.is_active.data
            
            db.session.commit()
            
            flash('Anúncio atualizado com sucesso!', 'success')
            return redirect(url_for('chat.manage_advertisements', slug=slug))
        
        return render_template('chat/edit_advertisement.html', 
                             room=room, 
                             member=member, 
                             advertisement=advertisement,
                             form=form)
        
    except Exception as e:
        print(f"Erro ao editar anúncio: {e}")
        flash('Erro interno do servidor', 'error')
        return redirect(url_for('chat.manage_advertisements', slug=slug))


@chat_bp.route('/<slug>/advertisements/<int:advertisement_id>/delete', methods=['POST'])
@login_required
def delete_advertisement(slug, advertisement_id):
    """Deletar anúncio"""
    try:
        db = current_app.extensions['sqlalchemy']
        
        # Buscar sala
        room = db.session.query(Room).filter_by(slug=slug).first()
        if not room:
            return jsonify({'success': False, 'error': 'Sala não encontrada'}), 404
        
        # Verificar se é membro
        member = db.session.query(RoomMember).filter_by(
            room_id=room.id,
            user_id=current_user.id
        ).first()
        if not member:
            return jsonify({'success': False, 'error': 'Acesso negado'}), 403
        
        # Verificar se é admin ou creator
        if member.role not in ['creator', 'admin']:
            return jsonify({'success': False, 'error': 'Apenas administradores podem deletar anúncios'}), 403
        
        # Buscar anúncio
        advertisement = db.session.query(Advertisement).filter_by(
            id=advertisement_id,
            room_id=room.id
        ).first()
        if not advertisement:
            return jsonify({'success': False, 'error': 'Anúncio não encontrado'}), 404
        
        # Deletar imagem se existir
        if advertisement.image_path:
            file_path = os.path.join(current_app.static_folder, advertisement.image_path)
            if os.path.exists(file_path):
                os.remove(file_path)
        
        # Deletar anúncio
        db.session.delete(advertisement)
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Anúncio deletado com sucesso'})
        
    except Exception as e:
        print(f"Erro ao deletar anúncio: {e}")
        return jsonify({'success': False, 'error': 'Erro interno do servidor'}), 500


@chat_bp.route('/<slug>/advertisements/<int:advertisement_id>/toggle', methods=['POST'])
@login_required
def toggle_advertisement(slug, advertisement_id):
    """Ativar/desativar anúncio"""
    try:
        db = current_app.extensions['sqlalchemy']
        
        # Buscar sala
        room = db.session.query(Room).filter_by(slug=slug).first()
        if not room:
            return jsonify({'success': False, 'error': 'Sala não encontrada'}), 404
        
        # Verificar se é membro
        member = db.session.query(RoomMember).filter_by(
            room_id=room.id,
            user_id=current_user.id
        ).first()
        if not member:
            return jsonify({'success': False, 'error': 'Acesso negado'}), 403
        
        # Verificar se é admin ou creator
        if member.role not in ['creator', 'admin']:
            return jsonify({'success': False, 'error': 'Apenas administradores podem alterar anúncios'}), 403
        
        # Buscar anúncio
        advertisement = db.session.query(Advertisement).filter_by(
            id=advertisement_id,
            room_id=room.id
        ).first()
        if not advertisement:
            return jsonify({'success': False, 'error': 'Anúncio não encontrado'}), 404
        
        # Alternar status
        advertisement.is_active = not advertisement.is_active
        db.session.commit()
        
        status = 'ativado' if advertisement.is_active else 'desativado'
        return jsonify({
            'success': True, 
            'message': f'Anúncio {status} com sucesso',
            'is_active': advertisement.is_active
        })
        
    except Exception as e:
        print(f"Erro ao alternar anúncio: {e}")
        return jsonify({'success': False, 'error': 'Erro interno do servidor'}), 500


@chat_bp.route('/<slug>/advertisements/<int:advertisement_id>')
@login_required
def get_advertisement(slug, advertisement_id):
    """API para buscar dados de um anúncio específico"""
    try:
        db = current_app.extensions['sqlalchemy']
        
        # Buscar sala
        room = db.session.query(Room).filter_by(slug=slug).first()
        if not room:
            return jsonify({'success': False, 'error': 'Sala não encontrada'}), 404
        
        # Verificar se é membro
        member = db.session.query(RoomMember).filter_by(
            room_id=room.id,
            user_id=current_user.id
        ).first()
        if not member:
            return jsonify({'success': False, 'error': 'Acesso negado'}), 403
        
        # Buscar anúncio
        advertisement = db.session.query(Advertisement).filter_by(
            id=advertisement_id,
            room_id=room.id
        ).first()
        if not advertisement:
            return jsonify({'success': False, 'error': 'Anúncio não encontrado'}), 404
        
        # Buscar criador do anúncio
        creator = db.session.query(User).get(advertisement.created_by)
        
        return jsonify({
            'success': True,
            'advertisement': {
                'id': advertisement.id,
                'title': advertisement.title,
                'content': advertisement.content,
                'image_path': advertisement.image_path,
                'link': advertisement.link,
                'start_date': advertisement.start_date.isoformat(),
                'end_date': advertisement.end_date.isoformat(),
                'priority': advertisement.priority,
                'is_active': advertisement.is_active,
                'is_current': advertisement.is_current,
                'is_expired': advertisement.is_expired,
                'days_remaining': advertisement.days_remaining,
                'created_at': advertisement.created_at.isoformat(),
                'creator': {
                    'id': creator.id,
                    'username': creator.username
                } if creator else None
            }
        })
        
    except Exception as e:
        print(f"Erro ao buscar anúncio: {e}")
        return jsonify({'success': False, 'error': 'Erro interno do servidor'}), 500


# ============================================================================
# EVENTOS SOCKET.IO
# ============================================================================

def register_socket_events(socketio):
    """Registra eventos do Socket.IO"""
    
    @socketio.on('join')
    def on_join(data):
        """Usuário entra na sala"""
        room_slug = data.get('room')
        if room_slug:
            join_room(room_slug)
            emit('status', {'msg': f'{current_user.username} entrou na sala.'}, room=room_slug)
    
    @socketio.on('leave')
    def on_leave(data):
        """Usuário sai da sala"""
        room_slug = data.get('room')
        if room_slug:
            leave_room(room_slug)
            emit('status', {'msg': f'{current_user.username} saiu da sala.'}, room=room_slug)
    
    @socketio.on('message')
    def on_message(data):
        """Nova mensagem"""
        room_slug = data.get('room')
        content = data.get('content', '').strip()
        
        if not room_slug or not content:
            return
        
        # Verificar se o usuário é membro da sala
        db = current_app.extensions['sqlalchemy']
        room = db.session.query(Room).filter_by(slug=room_slug).first()
        
        if not room:
            return
            
        member = db.session.query(RoomMember).filter_by(
            room_id=room.id,
            user_id=current_user.id
        ).first()
        
        if not member:
            return
        
        try:
            # Criar mensagem
            message_handler = MessageHandler(db.session)
            message = message_handler.create_message(
                room_id=room.id,
                user_id=current_user.id,
                content=content
            )
            
            # Formatar mensagem para Socket.IO
            formatted_message = format_message_for_socket(message, current_user)
            
            # Emitir para todos na sala
            emit('message', formatted_message, room=room_slug)
            
        except Exception as e:
            print(f"Erro ao processar mensagem: {e}")
    
    @socketio.on('typing')
    def on_typing(data):
        """Usuário está digitando"""
        room_slug = data.get('room')
        is_typing = data.get('is_typing', False)
        
        if room_slug:
            emit('typing', {
                'user': current_user.username,
                'is_typing': is_typing
            }, room=room_slug, include_self=False)
