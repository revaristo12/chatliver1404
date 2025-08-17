import os
from datetime import timedelta

class ProductionConfig:
    """Configuração para produção com Docker"""
    
    # Configurações básicas
    SECRET_KEY = os.environ.get('SECRET_KEY', 'your-super-secret-key-change-this-in-production')
    DEBUG = False
    TESTING = False
    
    # Banco de dados PostgreSQL
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', 'postgresql://chatliver1404:chatliver1404_secure_password@postgres:5432/chatliver1404')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_size': 10,
        'pool_recycle': 3600,
        'pool_pre_ping': True
    }
    
    # Redis para cache e sessões
    REDIS_URL = os.environ.get('REDIS_URL', 'redis://:chatliver1404_redis_password@redis:6379/0')
    
    # Configurações de email
    MAIL_SERVER = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
    MAIL_PORT = int(os.environ.get('MAIL_PORT', 587))
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'True').lower() == 'true'
    MAIL_USE_SSL = os.environ.get('MAIL_USE_SSL', 'False').lower() == 'true'
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME', '')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD', '')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER', 'noreply@chatliver1404.com')
    
    # Configurações de upload
    MAX_CONTENT_LENGTH = 20 * 1024 * 1024  # 20MB
    UPLOAD_FOLDER = '/app/static/uploads'
    ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif', 'mp4', 'mp3', 'wav', 'doc', 'docx', 'xls', 'xlsx'}
    
    # Configurações de segurança
    WTF_CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = 3600
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    PERMANENT_SESSION_LIFETIME = timedelta(days=7)
    
    # Configurações do Socket.IO
    SOCKETIO_ASYNC_MODE = 'eventlet'
    SOCKETIO_PING_TIMEOUT = 60
    SOCKETIO_PING_INTERVAL = 25
    
    # Configurações de logging
    LOG_LEVEL = 'INFO'
    LOG_FILE = '/app/logs/chatliver1404.log'
    
    # Configurações de performance
    SQLALCHEMY_RECORD_QUERIES = False
    SQLALCHEMY_ECHO = False
    
    # Configurações de cache
    CACHE_TYPE = 'redis'
    CACHE_REDIS_URL = REDIS_URL
    CACHE_DEFAULT_TIMEOUT = 300
    
    # Configurações de rate limiting
    RATELIMIT_STORAGE_URL = REDIS_URL
    RATELIMIT_DEFAULT = "200 per day;50 per hour;10 per minute"
    
    # Configurações de backup
    BACKUP_ENABLED = True
    BACKUP_SCHEDULE = '0 2 * * *'  # 2 AM diariamente
    BACKUP_RETENTION_DAYS = 30
    
    # Configurações de monitoramento
    ENABLE_METRICS = True
    METRICS_PORT = 9090
    
    # Configurações de SSL/TLS
    SSL_REDIRECT = True
    HSTS_PRELOAD = True
    HSTS_MAX_AGE = 31536000
    HSTS_INCLUDE_SUBDOMAINS = True
    
    # Configurações de compressão
    COMPRESS_MIMETYPES = [
        'text/html', 'text/css', 'text/xml',
        'application/json', 'application/javascript'
    ]
    COMPRESS_LEVEL = 6
    COMPRESS_MIN_SIZE = 500


