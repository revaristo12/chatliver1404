from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, current_app
from flask_login import login_required, current_user
from datetime import datetime, timedelta
from sqlalchemy import func
from models import User, Room, Message, Advertisement, AdminMessage, RoomMember
from forms import AdminMessageForm
from werkzeug.utils import secure_filename
import os

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

def admin_required(f):
    """Decorator para verificar se o usuário é administrador"""
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            # Verificar se é uma requisição AJAX/API
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.path.startswith('/admin/messages/'):
                return jsonify({
                    'success': False,
                    'error': 'Acesso negado. Apenas administradores podem acessar esta área.'
                }), 403
            else:
                flash('Acesso negado. Apenas administradores podem acessar esta área.', 'error')
                return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

@admin_bp.route('/')
@login_required
@admin_required
def dashboard():
    """Dashboard do administrador com métricas do sistema"""
    db = current_app.extensions['sqlalchemy']
    
    # Métricas básicas
    total_users = db.session.query(User).count()
    total_rooms = db.session.query(Room).count()
    total_messages = db.session.query(Message).count()
    total_advertisements = db.session.query(Advertisement).count()
    total_admin_messages = db.session.query(AdminMessage).count()
    
    # Usuários online (últimos 5 minutos)
    five_minutes_ago = datetime.utcnow() - timedelta(minutes=5)
    online_users = db.session.query(User).filter(
        User.last_seen >= five_minutes_ago
    ).count()
    
    # Mensagens por dia (últimos 7 dias)
    seven_days_ago = datetime.utcnow() - timedelta(days=7)
    messages_per_day = db.session.query(
        func.date(Message.created_at).label('date'),
        func.count(Message.id).label('count')
    ).filter(
        Message.created_at >= seven_days_ago
    ).group_by(
        func.date(Message.created_at)
    ).order_by(
        func.date(Message.created_at)
    ).all()
    
    # Salas mais ativas
    active_rooms = db.session.query(
        Room,
        func.count(Message.id).label('message_count')
    ).outerjoin(Message).group_by(Room.id).order_by(
        func.count(Message.id).desc()
    ).limit(5).all()
    
    # Usuários mais ativos
    active_users = db.session.query(
        User,
        func.count(Message.id).label('message_count')
    ).outerjoin(Message).group_by(User.id).order_by(
        func.count(Message.id).desc()
    ).limit(5).all()
    
    # Anúncios ativos
    now = datetime.utcnow()
    active_advertisements = db.session.query(Advertisement).filter(
        Advertisement.is_active == True,
        Advertisement.start_date <= now,
        Advertisement.end_date >= now
    ).count()
    
    # Mensagens do admin ativas
    active_admin_messages = db.session.query(AdminMessage).filter(
        AdminMessage.is_active == True,
        AdminMessage.start_date <= now,
        AdminMessage.end_date >= now
    ).count()
    
    return render_template('admin/dashboard.html',
                         total_users=total_users,
                         total_rooms=total_rooms,
                         total_messages=total_messages,
                         total_advertisements=total_advertisements,
                         total_admin_messages=total_admin_messages,
                         online_users=online_users,
                         messages_per_day=messages_per_day,
                         active_rooms=active_rooms,
                         active_users=active_users,
                         active_advertisements=active_advertisements,
                         active_admin_messages=active_admin_messages)

@admin_bp.route('/messages')
@login_required
@admin_required
def manage_messages():
    """Gerenciar mensagens globais do administrador"""
    db = current_app.extensions['sqlalchemy']
    
    admin_messages = db.session.query(AdminMessage).order_by(
        AdminMessage.created_at.desc()
    ).all()
    
    return render_template('admin/messages.html', admin_messages=admin_messages)

@admin_bp.route('/messages/create', methods=['GET', 'POST'])
@login_required
@admin_required
def create_message():
    """Criar nova mensagem global do administrador"""
    db = current_app.extensions['sqlalchemy']
    form = AdminMessageForm()
    
    if form.validate_on_submit():
        # Validações adicionais de data
        from datetime import datetime, timedelta
        start_date = form.start_date.data
        end_date = form.end_date.data
        now = datetime.now()
        
        if start_date < now:
            flash('Data de início não pode ser no passado', 'error')
            return render_template('admin/create_message.html', form=form)
        
        if end_date <= start_date:
            flash('Data de fim deve ser posterior à data de início', 'error')
            return render_template('admin/create_message.html', form=form)
        
        max_future_date = now + timedelta(days=365)
        if end_date > max_future_date:
            flash('Data de fim não pode ser mais de 1 ano no futuro', 'error')
            return render_template('admin/create_message.html', form=form)
        
        # Processar upload de imagem
        image_path = None
        if 'image' in request.files:
            file = request.files['image']
            if file and file.filename:
                filename = secure_filename(file.filename)
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                filename = f"{timestamp}_{filename}"
                file_path = f"uploads/admin_messages/{filename}"
                os.makedirs(os.path.join(current_app.static_folder, 'uploads/admin_messages'), exist_ok=True)
                file.save(os.path.join(current_app.static_folder, file_path))
                image_path = file_path
        
        # Criar mensagem do administrador
        admin_message = AdminMessage(
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
        
        db.session.add(admin_message)
        db.session.commit()
        
        flash('Mensagem do administrador criada com sucesso!', 'success')
        return redirect(url_for('admin.manage_messages'))
    
    return render_template('admin/create_message.html', form=form)

@admin_bp.route('/messages/<int:message_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_message(message_id):
    """Editar mensagem global do administrador"""
    db = current_app.extensions['sqlalchemy']
    
    admin_message = db.session.query(AdminMessage).get_or_404(message_id)
    form = AdminMessageForm(obj=admin_message)
    
    if form.validate_on_submit():
        # Validações adicionais de data
        from datetime import datetime, timedelta
        start_date = form.start_date.data
        end_date = form.end_date.data
        now = datetime.now()
        
        if start_date < now:
            flash('Data de início não pode ser no passado', 'error')
            return render_template('admin/edit_message.html', form=form, admin_message=admin_message)
        
        if end_date <= start_date:
            flash('Data de fim deve ser posterior à data de início', 'error')
            return render_template('admin/edit_message.html', form=form, admin_message=admin_message)
        
        max_future_date = now + timedelta(days=365)
        if end_date > max_future_date:
            flash('Data de fim não pode ser mais de 1 ano no futuro', 'error')
            return render_template('admin/edit_message.html', form=form, admin_message=admin_message)
        
        # Processar upload de nova imagem
        if 'image' in request.files:
            file = request.files['image']
            if file and file.filename:
                # Deletar imagem antiga se existir
                if admin_message.image_path:
                    old_image_path = os.path.join(current_app.static_folder, admin_message.image_path)
                    if os.path.exists(old_image_path):
                        os.remove(old_image_path)
                
                filename = secure_filename(file.filename)
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                filename = f"{timestamp}_{filename}"
                file_path = f"uploads/admin_messages/{filename}"
                os.makedirs(os.path.join(current_app.static_folder, 'uploads/admin_messages'), exist_ok=True)
                file.save(os.path.join(current_app.static_folder, file_path))
                admin_message.image_path = file_path
        
        # Atualizar dados
        admin_message.title = form.title.data
        admin_message.content = form.content.data
        admin_message.link = form.link.data
        admin_message.start_date = form.start_date.data
        admin_message.end_date = form.end_date.data
        admin_message.priority = int(form.priority.data)
        admin_message.is_active = form.is_active.data
        
        db.session.commit()
        flash('Mensagem do administrador atualizada com sucesso!', 'success')
        return redirect(url_for('admin.manage_messages'))
    
    return render_template('admin/edit_message.html', form=form, admin_message=admin_message)

@admin_bp.route('/messages/<int:message_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_message(message_id):
    """Deletar mensagem global do administrador"""
    db = current_app.extensions['sqlalchemy']
    
    admin_message = db.session.query(AdminMessage).get_or_404(message_id)
    
    # Deletar imagem se existir
    if admin_message.image_path:
        image_path = os.path.join(current_app.static_folder, admin_message.image_path)
        if os.path.exists(image_path):
            os.remove(image_path)
    
    db.session.delete(admin_message)
    db.session.commit()
    
    return jsonify({'success': True, 'message': 'Mensagem deletada com sucesso!'})

@admin_bp.route('/messages/<int:message_id>/toggle', methods=['POST'])
@login_required
@admin_required
def toggle_message(message_id):
    """Ativar/desativar mensagem global do administrador"""
    db = current_app.extensions['sqlalchemy']
    
    admin_message = db.session.query(AdminMessage).get_or_404(message_id)
    admin_message.is_active = not admin_message.is_active
    
    db.session.commit()
    
    status = 'ativada' if admin_message.is_active else 'desativada'
    return jsonify({
        'success': True, 
        'message': f'Mensagem {status} com sucesso!',
        'is_active': admin_message.is_active
    })

@admin_bp.route('/messages/<int:message_id>')
@login_required
@admin_required
def get_message(message_id):
    """API para buscar dados de uma mensagem específica"""
    db = current_app.extensions['sqlalchemy']
    
    try:
        admin_message = db.session.query(AdminMessage).get_or_404(message_id)
        creator = db.session.query(User).get(admin_message.created_by)
        
        return jsonify({
            'success': True,
            'admin_message': {
                'id': admin_message.id,
                'title': admin_message.title,
                'content': admin_message.content,
                'image_path': admin_message.image_path,
                'link': admin_message.link,
                'start_date': admin_message.start_date.isoformat() if admin_message.start_date else None,
                'end_date': admin_message.end_date.isoformat() if admin_message.end_date else None,
                'priority': admin_message.priority,
                'is_active': admin_message.is_active,
                'is_current': admin_message.is_current,
                'is_expired': admin_message.is_expired,
                'days_remaining': admin_message.days_remaining,
                'created_at': admin_message.created_at.isoformat() if admin_message.created_at else None,
                'creator': {
                    'id': creator.id,
                    'username': creator.username
                } if creator else None
            }
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
