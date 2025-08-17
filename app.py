import os
from flask import Flask, render_template, request, flash, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, current_user
from flask_socketio import SocketIO
from config import Config
from models import Base, User
from forms import LoginForm, RegistrationForm
from auth import handle_login, handle_registration, logout_user_handler

# Inicialização das extensões
db = SQLAlchemy()
login_manager = LoginManager()
socketio = SocketIO()

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    
    # Inicializar extensões
    db.init_app(app)
    login_manager.init_app(app)
    socketio.init_app(app, cors_allowed_origins="*")
    
    # Configurar login manager
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Por favor, faça login para acessar esta página.'
    login_manager.login_message_category = 'info'
    
    @login_manager.user_loader
    def load_user(user_id):
        return db.session.query(User).get(int(user_id))
    
    # Criar diretórios necessários
    os.makedirs('instance', exist_ok=True)
    os.makedirs('static/uploads', exist_ok=True)
    os.makedirs('templates', exist_ok=True)
    os.makedirs('templates/auth', exist_ok=True)
    os.makedirs('templates/rooms', exist_ok=True)
    
    # Registrar blueprints
    from auth_routes import auth_bp
    from rooms_routes import rooms_bp
    app.register_blueprint(auth_bp)
    app.register_blueprint(rooms_bp)
    
    # Rota principal
    @app.route('/')
    def index():
        if current_user.is_authenticated:
            return redirect(url_for('rooms.index'))
        return redirect(url_for('auth.login'))
    
    # Rota de erro 404
    @app.errorhandler(404)
    def not_found_error(error):
        return render_template('404.html'), 404
    
    # Rota de erro 500
    @app.errorhandler(500)
    def internal_error(error):
        db.session.rollback()
        return render_template('500.html'), 500
    
    return app

def init_db():
    """Inicializa o banco de dados"""
    with app.app_context():
        # Criar todas as tabelas
        Base.metadata.create_all(db.engine)
        print("Banco de dados inicializado com sucesso!")

if __name__ == '__main__':
    app = create_app()
    
    # Inicializar banco de dados se não existir
    if not os.path.exists('instance/chat.db'):
        init_db()
    
    # Executar aplicação
    socketio.run(app, debug=True, host='0.0.0.0', port=5000)
