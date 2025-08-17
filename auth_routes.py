from flask import Blueprint, render_template, request, flash, redirect, url_for
from flask_login import login_required, current_user
from forms import LoginForm, RegistrationForm, ChangePasswordForm
from auth import handle_login, handle_registration, change_password_handler

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('rooms.index'))
    
    form = LoginForm()
    if request.method == 'POST':
        if form.validate_on_submit():
            from flask import current_app
            result = handle_login(current_app.extensions['sqlalchemy'].session, form)
            if result['success']:
                flash('Login realizado com sucesso!', 'success')
                return redirect(url_for('rooms.index'))
            else:
                flash(result['message'], 'error')
        else:
            flash('Por favor, corrija os erros no formulário.', 'error')
    
    return render_template('auth/login.html', title='Login', form=form)

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('rooms.index'))
    
    form = RegistrationForm()
    if request.method == 'POST':
        if form.validate_on_submit():
            from flask import current_app
            result = handle_registration(current_app.extensions['sqlalchemy'].session, form)
            if result['success']:
                flash('Conta criada com sucesso!', 'success')
                return redirect(url_for('rooms.index'))
            else:
                flash(result['message'], 'error')
        else:
            flash('Por favor, corrija os erros no formulário.', 'error')
    
    return render_template('auth/register.html', title='Cadastro', form=form)

@auth_bp.route('/logout')
@login_required
def logout():
    """Faz logout do usuário"""
    from flask_login import logout_user
    logout_user()
    flash('Você foi desconectado com sucesso.', 'info')
    return redirect(url_for('auth.login'))

@auth_bp.route('/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    """Altera a senha do usuário"""
    form = ChangePasswordForm()
    
    if request.method == 'POST':
        if form.validate_on_submit():
            from flask import current_app
            result = change_password_handler(
                current_app.extensions['sqlalchemy'].session,
                current_user.id,
                form.current_password.data,
                form.new_password.data
            )
            
            if result['success']:
                flash(result['message'], 'success')
                return redirect(url_for('rooms.index'))
            else:
                flash(result['message'], 'error')
        else:
            flash('Por favor, corrija os erros no formulário.', 'error')
    
    return render_template('auth/change_password.html', title='Alterar Senha', form=form)
