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

        srp_prices = {
            10: Setting.get('srp_price'),
            9:  Setting.get('srp_tec9'),
            8:  Setting.get('srp_tec8'),
            7:  Setting.get('srp_tec7'),
            6:  Setting.get('srp_tec6'),
        }
        outpost_price = Setting.get('outpost_price')
        doctrine_fine = Setting.get('doctrine_fine')

        players = Player.query.filter_by(active=True).all()
        created = 0

        for player in players:
            if player.is_novato:
                continue

            # SRP: valor baseado no tec nível do jogador
            tec = player.tech_level
            if tec and tec <= 5:
                srp_amount = srp_prices[10]  # tec 1-5 paga o mesmo que tec 10
            else:
                srp_amount = srp_prices.get(tec, srp_prices[10])

            existing_srp = Debt.query.filter_by(
                player_id=player.id, debt_type='srp', month=month
            ).first()
            if not existing_srp:
                tec_label = f' (Tec {tec})' if tec else ''
                debt = Debt(
                    player_id=player.id,
                    debt_type='srp',
                    amount=srp_amount,
                    description=f'SRP{tec_label} - {month}',
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
    """Manually add a custom debt to a player (supports multiple periods)."""
    require_admin()

    players = Player.query.filter_by(active=True).order_by(Player.name).all()
    debt_types = [
        ('srp', 'SRP'),
        ('outpost', 'Outpost'),
        ('mining_fine', 'Multa Mineração'),
        ('pvp_fine', 'Multa PVP'),
        ('doctrine_fine', 'Multa Nave Doutrina'),
        ('custom', 'Outro'),
    ]

    if request.method == 'POST':
        from datetime import datetime
        player_id = int(request.form.get('player_id'))
        debt_type = request.form.get('debt_type')
        amount = float(request.form.get('amount', 0))
        description = request.form.get('description', '').strip()
        month = request.form.get('month', '').strip() or None
        paid = request.form.get('paid') == 'on'
        quantity = max(1, int(request.form.get('quantity', 1)))

        # Labels padrão por tipo — geram descrição automaticamente
        TYPE_LABELS = {
            'srp':           'SRP',
            'outpost':       'Outpost',
            'mining_fine':   'Multa Mineração',
            'pvp_fine':      'Multa PVP',
            'doctrine_fine': 'Multa Nave Doutrina',
        }

        created = 0
        for i in range(quantity):
            # Calcula o mês de cada parcela
            if month and quantity > 1:
                year, base_month = map(int, month.split('-'))
                total_months = base_month + i
                y = year + (total_months - 1) // 12
                new_m = ((total_months - 1) % 12) + 1
                period_month = f'{y:04d}-{new_m:02d}'
            else:
                period_month = month

            # Descrição: tipos padrão usam formato fixo; 'custom' usa o que o usuário digitou
            if debt_type in TYPE_LABELS:
                if period_month:
                    desc = f'{TYPE_LABELS[debt_type]} - {period_month}'
                else:
                    desc = TYPE_LABELS[debt_type]
            else:
                # Tipo "Outro": mantém descrição livre com sufixo de parcela
                desc = f'{description} ({i + 1}/{quantity})' if quantity > 1 else description

            debt = Debt(
                player_id=player_id,
                debt_type=debt_type,
                amount=amount,
                description=desc,
                month=period_month,
                paid=paid,
            )
            if paid:
                debt.paid_at = datetime.utcnow()

            db.session.add(debt)
            created += 1

        db.session.commit()

        if quantity > 1:
            flash(f'{created} cobranças adicionadas (total: {amount * created:.0f}m ISK)!', 'success')
        else:
            flash('Cobrança manual adicionada!', 'success')

        return redirect(url_for('players.detail', player_id=player_id))

    return render_template('payments/add_manual.html',
                           players=players,
                           debt_types=debt_types,
                           today=date.today().strftime('%Y-%m-%d'))
