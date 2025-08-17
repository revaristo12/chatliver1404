#!/usr/bin/env python3
"""
CHATLIVER1404 - Aplicação de Produção
Versão otimizada para VPS com Docker
"""

import os
import logging
import structlog
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_from_directory
from flask_socketio import SocketIO, emit, join_room, leave_room
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from flask_mail import Mail
from flask_compress import Compress
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from werkzeug.utils import secure_filename
import redis
from datetime import datetime
from config_production import ProductionConfig
from models import Base, User, Room, RoomMember, RoomInvite, Message, Attachment, AccessRequest
from forms import LoginForm, RegistrationForm
from auth import handle_login, handle_registration
from auth_routes import auth_bp
from rooms_routes import rooms_bp
from chat_routes import chat_bp
from messages import MessageHandler
from invites import InviteGenerator, InviteEmailService

# Configuração de logging estruturado
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()

def create_app():
    """Factory para criar a aplicação Flask"""
    app = Flask(__name__)
    app.config.from_object(ProductionConfig)
    
    # Configurar logging
    if not app.debug:
        logging.basicConfig(
            filename=app.config['LOG_FILE'],
            level=getattr(logging, app.config['LOG_LEVEL']),
            format='%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
        )
    
    # Inicialização das extensões
    from flask_sqlalchemy import SQLAlchemy
    db = SQLAlchemy(app)
    mail = Mail(app)
    
    # Socket.IO com configurações de produção
    socketio = SocketIO(
        app, 
        cors_allowed_origins="*",
        async_mode='eventlet',
        ping_timeout=60,
        ping_interval=25,
        logger=True,
        engineio_logger=True
    )
    
    # Compressão
    Compress(app)
    
    # Rate limiting
    limiter = Limiter(
        app=app,
        key_func=get_remote_address,
        default_limits=["200 per day", "50 per hour"]
    )
    
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
    
    # Health check
    @app.route('/health')
    def health_check():
        """Health check para monitoramento"""
        try:
            # Verificar banco de dados
            db.session.execute('SELECT 1')
            # Verificar Redis
            redis_client = redis.from_url(app.config['REDIS_URL'])
            redis_client.ping()
            
            return jsonify({
                'status': 'healthy',
                'timestamp': datetime.utcnow().isoformat(),
                'database': 'connected',
                'redis': 'connected'
            }), 200
        except Exception as e:
            logger.error("Health check failed", error=str(e))
            return jsonify({
                'status': 'unhealthy',
                'timestamp': datetime.utcnow().isoformat(),
                'error': str(e)
            }), 500
    
    # Configuração do Socket.IO
    def register_socket_events():
        """Registra os eventos do Socket.IO"""
        
        @socketio.on('connect')
        def handle_connect():
            logger.info("Cliente conectado", sid=request.sid)
            emit('status', {'msg': 'Conectado ao servidor'})
        
        @socketio.on('disconnect')
        def handle_disconnect():
            logger.info("Cliente desconectado", sid=request.sid)
        
        @socketio.on('join')
        def handle_join(data):
            room = data.get('room')
            if room:
                join_room(room)
                username = current_user.username if current_user.is_authenticated else "Anônimo"
                logger.info("Usuário entrou na sala", user=username, room=room)
                emit('status', {'msg': f'Entrou na sala: {room}'}, room=room)
        
        @socketio.on('leave')
        def handle_leave(data):
            room = data.get('room')
            if room:
                leave_room(room)
                username = current_user.username if current_user.is_authenticated else "Anônimo"
                logger.info("Usuário saiu da sala", user=username, room=room)
                emit('status', {'msg': f'Saiu da sala: {room}'}, room=room)
        
        @socketio.on('message')
        def handle_message(data):
            room = data.get('room')
            message = data.get('message')
            if room and message and current_user.is_authenticated:
                try:
                    # Salvar mensagem no banco
                    message_handler = MessageHandler(db.session)
                    saved_message = message_handler.create_message(
                        room_slug=room,
                        user_id=current_user.id,
                        content=message
                    )
                    
                    if saved_message:
                        # Formatar mensagem para envio
                        formatted_message = message_handler.format_message_for_socket(saved_message, current_user)
                        emit('message', formatted_message, room=room)
                        logger.info("Mensagem enviada", user=current_user.username, room=room)
                except Exception as e:
                    logger.error("Erro ao processar mensagem", error=str(e), user=current_user.username, room=room)
        
        @socketio.on('typing')
        def handle_typing(data):
            room = data.get('room')
            is_typing = data.get('is_typing', False)
            if room and current_user.is_authenticated:
                emit('typing', {
                    'user': current_user.username,
                    'is_typing': is_typing
                }, room=room, include_self=False)
    
    # Registrar eventos do Socket.IO
    register_socket_events()
    
    return app, db, mail, socketio

# Criar aplicação
app, db, mail, socketio = create_app()

if __name__ == '__main__':
    # Criar tabelas se não existirem
    with app.app_context():
        Base.metadata.create_all(db.engine)
    
    logger.info("🚀 CHATLIVER1404 iniciando em modo produção...")
    logger.info("📱 PWA disponível para instalação no celular!")
    logger.info("🌐 Acesse: https://chatliver1404.com")
    
    # Executar com eventlet para produção
    import eventlet
    eventlet.monkey_patch()
    socketio.run(app, host='0.0.0.0', port=5000, debug=False)
