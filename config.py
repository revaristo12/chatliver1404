import os
from pathlib import Path

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    
    # Database
    basedir = Path(__file__).parent.absolute()
    SQLALCHEMY_DATABASE_URI = f'sqlite:///{basedir}/instance/chat.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Email configuration
    MAIL_SERVER = os.environ.get('MAIL_SERVER') or 'smtp.gmail.com'
    MAIL_PORT = int(os.environ.get('MAIL_PORT') or 587)
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'true').lower() in ['true', 'on', '1']
    MAIL_USE_SSL = os.environ.get('MAIL_USE_SSL', 'false').lower() in ['true', 'on', '1']
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER')
    
    # File upload
    MAX_CONTENT_LENGTH = 10 * 1024 * 1024  # 10MB max file size
    UPLOAD_FOLDER = 'static/uploads'
    
    # Security
    WTF_CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = 3600  # 1 hour
    
    # Configurações de criptografia
    CRYPTO_KEY_SIZE = 32  # bytes para AES-256
    E2EE_ENABLED = os.environ.get('E2EE_ENABLED', 'False').lower() == 'true'
    
    # Configurações de convite
    INVITE_EXPIRY_HOURS = 72  # 3 dias
    
    # Configurações de rate limiting
    MESSAGE_RATE_LIMIT = 10  # mensagens por minuto
    UPLOAD_RATE_LIMIT = 5    # uploads por hora
