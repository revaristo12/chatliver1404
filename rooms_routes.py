from flask import Blueprint, render_template, request, flash, redirect, url_for, current_app, jsonify
from flask_login import login_required, current_user
from models import Room, RoomMember, RoomInvite, AccessRequest, User, Message, Attachment
from forms import RoomForm
from auth import create_room_handler
from invites import InviteEmailService
import os

rooms_bp = Blueprint('rooms', __name__)

@rooms_bp.route('/')
@login_required
def index():
    """Lista as salas do usuário"""
    db = current_app.extensions['sqlalchemy']
    
    # Buscar salas onde o usuário é membro
    user_rooms = db.session.query(Room).join(RoomMember).filter(
        RoomMember.user_id == current_user.id
    ).all()
    
    # Para cada sala, buscar informações do membro
    rooms_with_member = []
    for room in user_rooms:
        member = db.session.query(RoomMember).filter_by(
            room_id=room.id, 
            user_id=current_user.id
        ).first()
        
        rooms_with_member.append({
            'room': room,
            'member': member
        })
    
    return render_template('rooms/index.html', rooms=rooms_with_member)

@rooms_bp.route('/create', methods=['GET', 'POST'])
@login_required
def create():
    """Criar nova sala"""
    form = RoomForm()
    
    if form.validate_on_submit():
        db = current_app.extensions['sqlalchemy']
        result = create_room_handler(db.session, form, current_user.id)
        
        if result['success']:
            flash('Sala criada com sucesso!', 'success')
            return redirect(url_for('rooms.view', slug=result['room'].slug))
        else:
            flash(f'Erro ao criar sala: {result["message"]}', 'error')
    
    return render_template('rooms/create.html', form=form)

@rooms_bp.route('/<slug>')
@login_required
def view(slug):
    """Visualizar sala específica"""
    db = current_app.extensions['sqlalchemy']
    
    room = db.session.query(Room).filter_by(slug=slug).first()
    if not room:
        flash('Sala não encontrada.', 'error')
        return redirect(url_for('rooms.index'))
    
    # Verificar se o usuário é membro da sala
    member = db.session.query(RoomMember).filter_by(
        room_id=room.id, 
        user_id=current_user.id
    ).first()
    
    if not member:
        flash('Você não tem acesso a esta sala.', 'error')
        return redirect(url_for('rooms.index'))
    
    return render_template('rooms/view.html', room=room, member=member)

@rooms_bp.route('/<slug>/delete', methods=['POST'])
@login_required
def delete(slug):
    """Excluir sala"""
    db = current_app.extensions['sqlalchemy']
    
    room = db.session.query(Room).filter_by(slug=slug).first()
    if not room:
        flash('Sala não encontrada.', 'error')
        return redirect(url_for('rooms.index'))
    
    # Verificar se o usuário é o criador da sala
    member = db.session.query(RoomMember).filter_by(
        room_id=room.id, 
        user_id=current_user.id,
        role='creator'
    ).first()
    
    if not member:
        flash('Apenas o criador da sala pode excluí-la.', 'error')
        return redirect(url_for('rooms.view', slug=slug))
    
    try:
        # Excluir membros da sala
        db.session.query(RoomMember).filter_by(room_id=room.id).delete()
        
        # Excluir convites da sala
        db.session.query(RoomInvite).filter_by(room_id=room.id).delete()
        
        # Excluir mensagens da sala
        db.session.query(Message).filter_by(room_id=room.id).delete()
        
        # Excluir a sala
        db.session.delete(room)
        db.session.commit()
        
        flash('Sala excluída com sucesso!', 'success')
        return redirect(url_for('rooms.index'))
        
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao excluir sala: {str(e)}', 'error')
        return redirect(url_for('rooms.view', slug=slug))

@rooms_bp.route('/all')
@login_required
def all_rooms():
    """Lista todas as salas públicas"""
    db = current_app.extensions['sqlalchemy']
    
    # Buscar todas as salas públicas
    public_rooms = db.session.query(Room).filter_by(is_private=False).all()
    
    # Para cada sala, verificar se o usuário é membro e preparar dados esperados pelo template
    rooms_with_status = []
    for room in public_rooms:
        member = db.session.query(RoomMember).filter_by(
            room_id=room.id, 
            user_id=current_user.id
        ).first()
        
        # Verificar se há solicitação pendente
        pending_request = db.session.query(AccessRequest).filter_by(
            room_id=room.id,
            user_id=current_user.id,
            status='pending'
        ).first()
        
        rooms_with_status.append({
            'room': room,
            # Campos esperados pelo template
            'status': 'member' if member else 'not_member',
            'role': (member.role if member else None),
            'creator': (getattr(room, 'creator', None) or (db.session.query(User).get(room.creator_id) if hasattr(room, 'creator_id') else None)),
            'pending_request': pending_request is not None
        })
    
    return render_template('rooms/all_rooms.html', rooms=rooms_with_status)

@rooms_bp.route('/<slug>/request-access', methods=['POST'])
@login_required
def request_access(slug):
    """Solicitar acesso a uma sala"""
    db = current_app.extensions['sqlalchemy']
    
    room = db.session.query(Room).filter_by(slug=slug).first()
    if not room:
        flash('Sala não encontrada.', 'error')
        return redirect(url_for('rooms.all_rooms'))
    
    # Verificar se já é membro
    member = db.session.query(RoomMember).filter_by(
        room_id=room.id, 
        user_id=current_user.id
    ).first()
    
    if member:
        flash('Você já é membro desta sala.', 'info')
        return redirect(url_for('rooms.all_rooms'))
    
    # Verificar se já há uma solicitação pendente
    existing_request = db.session.query(AccessRequest).filter_by(
        room_id=room.id,
        user_id=current_user.id,
        status='pending'
    ).first()
    
    if existing_request:
        flash('Você já tem uma solicitação pendente para esta sala.', 'info')
        return redirect(url_for('rooms.all_rooms'))
    
    try:
        # Criar solicitação de acesso
        access_request = AccessRequest(
            room_id=room.id,
            user_id=current_user.id,
            notes=request.form.get('message', '')
        )
        
        db.session.add(access_request)
        db.session.commit()
        
        flash('Solicitação de acesso enviada com sucesso!', 'success')
        return redirect(url_for('rooms.all_rooms'))
        
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao enviar solicitação: {str(e)}', 'error')
        return redirect(url_for('rooms.all_rooms'))

@rooms_bp.route('/<slug>/members')
@login_required
def manage_members(slug):
    """Gerenciar membros da sala (apenas para administradores)"""
    db = current_app.extensions['sqlalchemy']
    
    room = db.session.query(Room).filter_by(slug=slug).first()
    if not room:
        flash('Sala não encontrada.', 'error')
        return redirect(url_for('rooms.index'))
    
    # Verificar se o usuário é administrador da sala (criador ou admin)
    member = db.session.query(RoomMember).filter_by(
        room_id=room.id, 
        user_id=current_user.id
    ).first()
    
    if not member or member.role not in ['creator', 'admin']:
        flash('Apenas administradores podem gerenciar membros da sala.', 'error')
        return redirect(url_for('rooms.view', slug=slug))
    
    # Buscar todos os membros da sala
    members = db.session.query(RoomMember).filter_by(room_id=room.id).all()
    
    return render_template('rooms/manage_members.html', room=room, members=members, current_member=member)

@rooms_bp.route('/<slug>/members/<int:user_id>/remove', methods=['POST'])
@login_required
def remove_member(slug, user_id):
    """Remover membro da sala"""
    db = current_app.extensions['sqlalchemy']
    
    room = db.session.query(Room).filter_by(slug=slug).first()
    if not room:
        return jsonify({'success': False, 'error': 'Sala não encontrada'}), 404
    
    # Verificar se o usuário é administrador da sala
    current_member = db.session.query(RoomMember).filter_by(
        room_id=room.id, 
        user_id=current_user.id
    ).first()
    
    if not current_member or current_member.role not in ['creator', 'admin']:
        return jsonify({'success': False, 'error': 'Apenas administradores podem remover membros'}), 403
    
    # Verificar se está tentando remover a si mesmo
    if user_id == current_user.id:
        return jsonify({'success': False, 'error': 'Você não pode remover a si mesmo da sala'}), 400
    
    # Verificar se está tentando remover o criador da sala
    target_member = db.session.query(RoomMember).filter_by(
        room_id=room.id, 
        user_id=user_id
    ).first()
    
    if not target_member:
        return jsonify({'success': False, 'error': 'Usuário não é membro desta sala'}), 404
    
    if target_member.role == 'creator':
        return jsonify({'success': False, 'error': 'Não é possível remover o criador da sala'}), 400
    
    try:
        # Remover o membro
        db.session.delete(target_member)
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Membro removido com sucesso'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': f'Erro ao remover membro: {str(e)}'}), 500

@rooms_bp.route('/<slug>/members/<int:user_id>/promote', methods=['POST'])
@login_required
def promote_member(slug, user_id):
    """Promover membro a administrador"""
    db = current_app.extensions['sqlalchemy']
    
    room = db.session.query(Room).filter_by(slug=slug).first()
    if not room:
        return jsonify({'success': False, 'error': 'Sala não encontrada'}), 404
    
    # Verificar se o usuário é criador da sala
    current_member = db.session.query(RoomMember).filter_by(
        room_id=room.id, 
        user_id=current_user.id
    ).first()
    
    if not current_member or current_member.role != 'creator':
        return jsonify({'success': False, 'error': 'Apenas o criador da sala pode promover membros'}), 403
    
    # Verificar se está tentando promover a si mesmo
    if user_id == current_user.id:
        return jsonify({'success': False, 'error': 'Você não pode promover a si mesmo'}), 400
    
    # Verificar se o membro existe
    target_member = db.session.query(RoomMember).filter_by(
        room_id=room.id, 
        user_id=user_id
    ).first()
    
    if not target_member:
        return jsonify({'success': False, 'error': 'Usuário não é membro desta sala'}), 404
    
    if target_member.role == 'creator':
        return jsonify({'success': False, 'error': 'O criador da sala já tem o papel máximo'}), 400
    
    if target_member.role == 'admin':
        return jsonify({'success': False, 'error': 'Usuário já é administrador'}), 400
    
    try:
        # Promover o membro a administrador
        target_member.role = 'admin'
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Membro promovido a administrador com sucesso'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': f'Erro ao promover membro: {str(e)}'}), 500

@rooms_bp.route('/<slug>/members/<int:user_id>/demote', methods=['POST'])
@login_required
def demote_member(slug, user_id):
    """Rebaixar administrador a membro"""
    db = current_app.extensions['sqlalchemy']
    
    room = db.session.query(Room).filter_by(slug=slug).first()
    if not room:
        return jsonify({'success': False, 'error': 'Sala não encontrada'}), 404
    
    # Verificar se o usuário é criador da sala
    current_member = db.session.query(RoomMember).filter_by(
        room_id=room.id, 
        user_id=current_user.id
    ).first()
    
    if not current_member or current_member.role != 'creator':
        return jsonify({'success': False, 'error': 'Apenas o criador da sala pode rebaixar administradores'}), 403
    
    # Verificar se está tentando rebaixar a si mesmo
    if user_id == current_user.id:
        return jsonify({'success': False, 'error': 'Você não pode rebaixar a si mesmo'}), 400
    
    # Verificar se o membro existe
    target_member = db.session.query(RoomMember).filter_by(
        room_id=room.id, 
        user_id=user_id
    ).first()
    
    if not target_member:
        return jsonify({'success': False, 'error': 'Usuário não é membro desta sala'}), 404
    
    if target_member.role == 'creator':
        return jsonify({'success': False, 'error': 'Não é possível rebaixar o criador da sala'}), 400
    
    if target_member.role == 'member':
        return jsonify({'success': False, 'error': 'Usuário já é membro comum'}), 400
    
    try:
        # Rebaixar o administrador a membro
        target_member.role = 'member'
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Administrador rebaixado a membro com sucesso'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': f'Erro ao rebaixar administrador: {str(e)}'}), 500
