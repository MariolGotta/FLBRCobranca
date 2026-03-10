from flask import Blueprint, render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user
from datetime import date
from models import db, Player, Debt, Setting

payments_bp = Blueprint('payments', __name__, url_prefix='/payments')


def require_admin():
    if not current_user.is_admin:
        abort(403)


@payments_bp.route('/generate-monthly', methods=['GET', 'POST'])
@login_required
def generate_monthly():
    require_admin()

    if request.method == 'POST':
        month = request.form.get('month')  # 'YYYY-MM'
        if not month:
            flash('Selecione o mês.', 'danger')
            return redirect(url_for('payments.generate_monthly'))

        srp_price = Setting.get('srp_price')
        outpost_price = Setting.get('outpost_price')
        doctrine_fine = Setting.get('doctrine_fine')

        players = Player.query.filter_by(active=True).all()
        created = 0

        for player in players:
            if player.is_novato:
                continue

            # SRP: everyone except Novato
            existing_srp = Debt.query.filter_by(
                player_id=player.id, debt_type='srp', month=month
            ).first()
            if not existing_srp:
                debt = Debt(
                    player_id=player.id,
                    debt_type='srp',
                    amount=srp_price,
                    description=f'SRP - {month}',
                    month=month
                )
                db.session.add(debt)
                created += 1

            # Outpost: only players with outpost marked
            if player.has_outpost:
                existing_out = Debt.query.filter_by(
                    player_id=player.id, debt_type='outpost', month=month
                ).first()
                if not existing_out:
                    debt = Debt(
                        player_id=player.id,
                        debt_type='outpost',
                        amount=outpost_price,
                        description=f'Outpost - {month} (vence dia 23)',
                        month=month
                    )
                    db.session.add(debt)
                    created += 1

            # Doctrine fine: non-novato without doctrine ship
            if not player.has_doctrine_ship:
                existing_doc = Debt.query.filter_by(
                    player_id=player.id, debt_type='doctrine_fine', month=month
                ).first()
                if not existing_doc:
                    debt = Debt(
                        player_id=player.id,
                        debt_type='doctrine_fine',
                        amount=doctrine_fine,
                        description=f'Multa Nave Doutrina - {month}',
                        month=month
                    )
                    db.session.add(debt)
                    created += 1

        db.session.commit()
        flash(f'{created} cobranças geradas para {month}!', 'success')
        return redirect(url_for('reports.index'))

    today = date.today()
    default_month = today.strftime('%Y-%m')
    return render_template('payments/generate_monthly.html', default_month=default_month)


@payments_bp.route('/add-manual', methods=['GET', 'POST'])
@login_required
def add_manual():
    """Manually add a custom debt to a player."""
    require_admin()

    players = Player.query.filter_by(active=True).order_by(Player.name).all()
    debt_types = [
        ('srp', 'SRP'),
        ('outpost', 'Outpost'),
        ('mining_fine', 'Multa Mineração'),
        ('pvp_fine', 'Multa PVP'),
        ('doctrine_fine', 'Multa Nave Doutrina'),
    ]

    if request.method == 'POST':
        player_id = int(request.form.get('player_id'))
        debt_type = request.form.get('debt_type')
        amount = float(request.form.get('amount', 0))
        description = request.form.get('description', '').strip()
        month = request.form.get('month', '').strip() or None
        paid = request.form.get('paid') == 'on'

        debt = Debt(
            player_id=player_id,
            debt_type=debt_type,
            amount=amount,
            description=description,
            month=month,
            paid=paid,
        )
        if paid:
            from datetime import datetime
            debt.paid_at = datetime.utcnow()

        db.session.add(debt)
        db.session.commit()
        flash('Cobrança manual adicionada!', 'success')
        return redirect(url_for('players.detail', player_id=player_id))

    return render_template('payments/add_manual.html',
                           players=players,
                           debt_types=debt_types,
                           today=date.today().strftime('%Y-%m-%d'))
