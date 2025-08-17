from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_from_directory
from flask_socketio import SocketIO, emit, join_room, leave_room
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from flask_mail import Mail
from werkzeug.utils import secure_filename
import os
from datetime import datetime
from config import Config
from models import Base, User, Room, RoomMember, RoomInvite, Message, Attachment, AccessRequest
from forms import LoginForm, RegistrationForm
from auth import handle_login, handle_registration
from auth_routes import auth_bp
from rooms_routes import rooms_bp
from chat_routes import chat_bp, register_socket_events
from admin_routes import admin_bp
from messages import MessageHandler
from invites import InviteGenerator, InviteEmailService

# Configuração da aplicação
app = Flask(__name__)
app.config.from_object(Config)

# Inicialização das extensões
from flask_sqlalchemy import SQLAlchemy
db = SQLAlchemy(app)
mail = Mail(app)
socketio = SocketIO(app, cors_allowed_origins="*")

# Registrar socketio no current_app para acesso pelas rotas
app.socketio = socketio

# Configuração do Login Manager
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'auth.login'
login_manager.login_message = 'Por favor, faça login para acessar esta página.'
login_manager.login_message_category = 'warning'

@login_manager.user_loader
def load_user(user_id):
    """Carrega o usuário para o Flask-Login"""
    return db.session.get(User, int(user_id))

# Registro dos blueprints
app.register_blueprint(auth_bp, url_prefix='/auth')
app.register_blueprint(rooms_bp, url_prefix='/rooms')
app.register_blueprint(chat_bp, url_prefix='/chat')
app.register_blueprint(admin_bp, url_prefix='/admin')

# Rota para página offline
@app.route('/offline.html')
def offline():
    """Página offline para PWA"""
    return send_from_directory('static', 'offline.html')

# Rota para manifest.json
@app.route('/static/manifest.json')
def manifest():
    """Serve o manifest.json para PWA"""
    return send_from_directory('static', 'manifest.json')

# Rota para service worker
@app.route('/static/sw.js')
def service_worker():
    """Serve o service worker para PWA"""
    response = app.make_response(send_from_directory('static', 'sw.js'))
    response.headers['Content-Type'] = 'application/javascript'
    return response

# Rota principal
@app.route('/')
def index():
    """Página inicial"""
    if current_user.is_authenticated:
        return redirect(url_for('rooms.index'))
    return redirect(url_for('auth.login'))

# Configuração do Socket.IO
def register_socket_events():
    """Registra os eventos do Socket.IO"""
    
    @socketio.on('connect')
    def handle_connect():
        print(f'Cliente conectado: {request.sid}')
        emit('status', {'msg': 'Conectado ao servidor'})
    
    @socketio.on('disconnect')
    def handle_disconnect():
        print(f'Cliente desconectado: {request.sid}')
    
    @socketio.on('join')
    def handle_join(data):
        room = data.get('room')
        if room:
            join_room(room)
            print(f'Usuário {current_user.username if current_user.is_authenticated else "Anônimo"} entrou na sala: {room}')
            emit('status', {'msg': f'Entrou na sala: {room}'}, room=room)
    
    @socketio.on('leave')
    def handle_leave(data):
        room = data.get('room')
        if room:
            leave_room(room)
            print(f'Usuário {current_user.username if current_user.is_authenticated else "Anônimo"} saiu da sala: {room}')
            emit('status', {'msg': f'Saiu da sala: {room}'}, room=room)
    
    @socketio.on('message')
    def handle_message(data):
        room = data.get('room')
        message = data.get('message')
        if room and message and current_user.is_authenticated:
            # Salvar mensagem no banco
            message_handler = MessageHandler(db)
            saved_message = message_handler.create_message(
                room_slug=room,
                user_id=current_user.id,
                content=message
            )
            
            if saved_message:
                # Formatar mensagem para envio
                formatted_message = message_handler.format_message_for_socket(saved_message, current_user)
                emit('message', formatted_message, room=room)
    
    @socketio.on('typing')
    def handle_typing(data):
        room = data.get('room')
        is_typing = data.get('is_typing', False)
        if room and current_user.is_authenticated:
            emit('typing', {
                'user': current_user.username,
                'is_typing': is_typing
            }, room=room, include_self=False)
    
    # Eventos específicos do chat
    @socketio.on('message_deleted')
    def handle_message_deleted(data):
        """Evento para mensagem deletada"""
        room = data.get('room')
        message_id = data.get('message_id')
        deleted_by = data.get('deleted_by')
        
        if room and message_id:
            print(f'Mensagem {message_id} deletada por {deleted_by} na sala {room}')
            # Emitir para todos na sala
            emit('message_deleted', {
                'message_id': message_id,
                'deleted_by': deleted_by
            }, room=room)
    
    @socketio.on('test_event')
    def handle_test_event(data):
        """Evento de teste para verificar se Socket.IO está funcionando"""
        print(f'Evento de teste recebido: {data}')
        room = data.get('room')
        if room:
            emit('test_response', {
                'message': 'Socket.IO funcionando!',
                'timestamp': datetime.now().isoformat()
            }, room=room)

# Registrar eventos do Socket.IO
register_socket_events()

if __name__ == '__main__':
    # Criar tabelas se não existirem
    with app.app_context():
        Base.metadata.create_all(db.engine)
    
    print("🚀 CHATLIVER1404 iniciando...")
    print("📱 PWA disponível para instalação no celular!")
    print("🌐 Acesse: http://localhost:5000")
    
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)
