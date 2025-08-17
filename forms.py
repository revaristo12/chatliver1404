from flask_wtf import FlaskForm
from flask_wtf.file import FileField
from wtforms import StringField, PasswordField, BooleanField, SubmitField, TextAreaField, IntegerField, DateTimeField, SelectField
from wtforms.validators import DataRequired, Email, EqualTo, Length, NumberRange, Optional, ValidationError, URL

class LoginForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Senha', validators=[DataRequired()])
    remember_me = BooleanField('Lembrar de mim')
    submit = SubmitField('Entrar')

class RegistrationForm(FlaskForm):
    username = StringField('Nome de usuário', validators=[
        DataRequired(), 
        Length(min=3, max=20, message='Nome de usuário deve ter entre 3 e 20 caracteres')
    ])
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Senha', validators=[
        DataRequired(),
        Length(min=6, message='Senha deve ter pelo menos 6 caracteres')
    ])
    password2 = PasswordField('Confirmar senha', validators=[
        DataRequired(), 
        EqualTo('password', message='Senhas devem ser iguais')
    ])
    submit = SubmitField('Registrar')

class RoomForm(FlaskForm):
    name = StringField('Nome da sala', validators=[
        DataRequired(),
        Length(min=3, max=50, message='Nome deve ter entre 3 e 50 caracteres')
    ])
    description = TextAreaField('Descrição (opcional)', validators=[
        Optional(),
        Length(max=200, message='Descrição deve ter no máximo 200 caracteres')
    ])
    is_private = BooleanField('Sala privada (apenas por convite)')
    allow_images = BooleanField('Permitir imagens', default=True)
    allow_videos = BooleanField('Permitir vídeos', default=True)
    submit = SubmitField('Criar Sala')

class MessageForm(FlaskForm):
    content = TextAreaField('Mensagem', validators=[
        Length(max=1000, message='Mensagem deve ter no máximo 1000 caracteres')
    ])
    attachment = FileField('Anexo')
    submit = SubmitField('Enviar')

class InviteForm(FlaskForm):
    expires_in_hours = IntegerField('Expira em (horas)', validators=[
        DataRequired(),
        NumberRange(min=1, max=168, message='Deve ser entre 1 e 168 horas (7 dias)')
    ], default=24)
    max_uses = IntegerField('Máximo de usos (opcional)', validators=[
        Optional(),
        NumberRange(min=1, max=100, message='Deve ser entre 1 e 100 usos')
    ], default=None)
    submit = SubmitField('Criar Convite')

class AccessRequestForm(FlaskForm):
    notes = TextAreaField('Observações (opcional)', validators=[Optional()])
    submit = SubmitField('Solicitar Acesso')


class AdvertisementForm(FlaskForm):
    title = StringField('Título do Anúncio', validators=[
        DataRequired(message='Título é obrigatório'),
        Length(min=3, max=100, message='Título deve ter entre 3 e 100 caracteres')
    ])
    content = TextAreaField('Conteúdo do Anúncio', validators=[
        DataRequired(message='Conteúdo é obrigatório'),
        Length(min=10, max=1000, message='Conteúdo deve ter entre 10 e 1000 caracteres')
    ])
    link = StringField('Link (opcional)', validators=[
        Optional(),
        URL(message='Por favor, insira uma URL válida (ex: https://exemplo.com)')
    ])
    start_date = DateTimeField('Data de Início', validators=[
        DataRequired(message='Data de início é obrigatória')
    ], format='%Y-%m-%dT%H:%M')
    end_date = DateTimeField('Data de Fim', validators=[
        DataRequired(message='Data de fim é obrigatória')
    ], format='%Y-%m-%dT%H:%M')
    priority = SelectField('Prioridade', choices=[
        ('1', 'Baixa'),
        ('2', 'Média'),
        ('3', 'Alta')
    ], default='1')
    is_active = BooleanField('Ativo')
    submit = SubmitField('Salvar Anúncio')
    
    def validate_start_date(self, field):
        """Validar data de início"""
        from datetime import datetime
        if field.data:
            # Verificar se a data de início não é no passado
            if field.data < datetime.now():
                raise ValidationError('Data de início não pode ser no passado')
    
    def validate_end_date(self, field):
        """Validar data de fim"""
        from datetime import datetime, timedelta
        if field.data and self.start_date.data:
            # Verificar se a data de fim é posterior à data de início
            if field.data <= self.start_date.data:
                raise ValidationError('Data de fim deve ser posterior à data de início')
            
            # Verificar se a data de fim não é muito longe no futuro (máximo 1 ano)
            max_future_date = datetime.now() + timedelta(days=365)
            if field.data > max_future_date:
                raise ValidationError('Data de fim não pode ser mais de 1 ano no futuro')


class AdminMessageForm(FlaskForm):
    title = StringField('Título da Mensagem', validators=[
        DataRequired(message='Título é obrigatório'),
        Length(min=3, max=100, message='Título deve ter entre 3 e 100 caracteres')
    ])
    content = TextAreaField('Conteúdo da Mensagem', validators=[
        DataRequired(message='Conteúdo é obrigatório'),
        Length(min=10, max=1000, message='Conteúdo deve ter entre 10 e 1000 caracteres')
    ])
    link = StringField('Link (opcional)', validators=[
        Optional(),
        URL(message='Por favor, insira uma URL válida (ex: https://exemplo.com)')
    ])
    start_date = DateTimeField('Data de Início', validators=[
        DataRequired(message='Data de início é obrigatória')
    ], format='%Y-%m-%dT%H:%M')
    end_date = DateTimeField('Data de Fim', validators=[
        DataRequired(message='Data de fim é obrigatória')
    ], format='%Y-%m-%dT%H:%M')
    priority = SelectField('Prioridade', choices=[
        ('1', 'Baixa'),
        ('2', 'Média'),
        ('3', 'Alta')
    ], default='1')
    is_active = BooleanField('Ativo')
    submit = SubmitField('Salvar Mensagem')
    
    def validate_start_date(self, field):
        """Validar data de início"""
        from datetime import datetime
        if field.data:
            # Verificar se a data de início não é no passado
            if field.data < datetime.now():
                raise ValidationError('Data de início não pode ser no passado')
    
    def validate_end_date(self, field):
        """Validar data de fim"""
        from datetime import datetime, timedelta
        if field.data and self.start_date.data:
            # Verificar se a data de fim é posterior à data de início
            if field.data <= self.start_date.data:
                raise ValidationError('Data de fim deve ser posterior à data de início')
            
            # Verificar se a data de fim não é muito longe no futuro (máximo 1 ano)
            max_future_date = datetime.now() + timedelta(days=365)
            if field.data > max_future_date:
                raise ValidationError('Data de fim não pode ser mais de 1 ano no futuro')


class ChangePasswordForm(FlaskForm):
    current_password = PasswordField('Senha Atual', validators=[
        DataRequired(message='Senha atual é obrigatória')
    ])
    new_password = PasswordField('Nova Senha', validators=[
        DataRequired(message='Nova senha é obrigatória'),
        Length(min=8, message='Nova senha deve ter pelo menos 8 caracteres')
    ])
    confirm_password = PasswordField('Confirmar Nova Senha', validators=[
        DataRequired(message='Confirmação de senha é obrigatória'),
        EqualTo('new_password', message='Senhas devem ser iguais')
    ])
    submit = SubmitField('Alterar Senha')
