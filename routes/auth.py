from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from models import db, Player

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        password = request.form.get('password', '').strip()

        player = Player.query.filter_by(name=name, active=True).first()
        if player and player.check_password(password):
            login_user(player, remember=True)
            next_page = request.args.get('next')
            return redirect(next_page or url_for('dashboard.index'))
        flash('Nome ou senha inválidos.', 'danger')

    return render_template('login.html')


@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('auth.login'))


@auth_bp.route('/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    if request.method == 'POST':
        current_pw = request.form.get('current_password', '')
        new_pw = request.form.get('new_password', '')
        confirm_pw = request.form.get('confirm_password', '')

        if not current_user.check_password(current_pw):
            flash('Senha atual incorreta.', 'danger')
        elif new_pw != confirm_pw:
            flash('As novas senhas não coincidem.', 'danger')
        elif len(new_pw) < 4:
            flash('A nova senha deve ter pelo menos 4 caracteres.', 'danger')
        else:
            current_user.set_password(new_pw)
            db.session.commit()
            flash('Senha alterada com sucesso!', 'success')
            return redirect(url_for('dashboard.index'))

    return render_template('change_password.html')
