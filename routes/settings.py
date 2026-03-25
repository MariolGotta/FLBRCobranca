from flask import Blueprint, render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user
from models import db, Setting

settings_bp = Blueprint('settings', __name__, url_prefix='/settings')


def require_admin():
    if not current_user.is_admin:
        abort(403)


@settings_bp.route('/', methods=['GET', 'POST'])
@login_required
def index():
    require_admin()

    if request.method == 'POST':
        for key in ['srp_price', 'srp_tec9', 'srp_tec8', 'srp_tec7', 'srp_tec6',
                    'outpost_price', 'mining_fine', 'pvp_fine', 'doctrine_fine']:
            val = request.form.get(key)
            if val is not None:
                try:
                    Setting.set(key, float(val))
                except ValueError:
                    flash(f'Valor inválido para {key}.', 'danger')
                    return redirect(url_for('settings.index'))
        flash('Configurações salvas! Novas cobranças usarão os novos valores.', 'success')
        return redirect(url_for('settings.index'))

    settings = {
        'srp_price':     Setting.get('srp_price'),
        'srp_tec9':      Setting.get('srp_tec9'),
        'srp_tec8':      Setting.get('srp_tec8'),
        'srp_tec7':      Setting.get('srp_tec7'),
        'srp_tec6':      Setting.get('srp_tec6'),
        'outpost_price': Setting.get('outpost_price'),
        'mining_fine':   Setting.get('mining_fine'),
        'pvp_fine':      Setting.get('pvp_fine'),
        'doctrine_fine': Setting.get('doctrine_fine'),
    }
    return render_template('settings.html', settings=settings)
