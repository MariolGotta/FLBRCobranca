from flask import Blueprint, render_template, request, abort
from flask_login import login_required, current_user
from datetime import date
from models import db, Player, Debt

reports_bp = Blueprint('reports', __name__, url_prefix='/reports')


def require_view_all():
    if not current_user.can_view_all:
        abort(403)


@reports_bp.route('/')
@login_required
def index():
    require_view_all()

    # Filter options
    month = request.args.get('month', '')
    debt_type = request.args.get('debt_type', '')
    only_unpaid = request.args.get('unpaid', '1') == '1'

    # Build debt query
    query = Debt.query.join(Player).filter(Player.active == True)
    if only_unpaid:
        query = query.filter(Debt.paid == False)
    if month:
        query = query.filter(Debt.month == month)
    if debt_type:
        query = query.filter(Debt.debt_type == debt_type)

    debts = query.order_by(Player.name, Debt.created_at.desc()).all()

    # Group by player
    player_debts = {}
    for debt in debts:
        if debt.player_id not in player_debts:
            player_debts[debt.player_id] = {
                'player': debt.player,
                'debts': [],
                'total': 0.0
            }
        player_debts[debt.player_id]['debts'].append(debt)
        player_debts[debt.player_id]['total'] += debt.amount

    # Sort by total debt descending
    sorted_debtors = sorted(player_debts.values(), key=lambda x: x['total'], reverse=True)

    grand_total = sum(x['total'] for x in sorted_debtors)

    # Monthly income summary
    today = date.today()
    current_month = today.strftime('%Y-%m')
    months = _get_months_list()

    monthly_income = {}
    for m in months:
        income = db.session.query(db.func.sum(Debt.amount)).filter(
            Debt.paid == True,
            Debt.month == m
        ).scalar() or 0.0
        monthly_income[m] = income

    # Income by type for current month
    income_by_type = {}
    for debt_type_key in ['srp', 'outpost', 'mining_fine', 'pvp_fine', 'doctrine_fine']:
        val = db.session.query(db.func.sum(Debt.amount)).filter(
            Debt.paid == True,
            Debt.month == current_month,
            Debt.debt_type == debt_type_key
        ).scalar() or 0.0
        income_by_type[debt_type_key] = val

    # Debt breakdown by type (unpaid)
    debt_by_type = {}
    for debt_type_key in ['srp', 'outpost', 'mining_fine', 'pvp_fine', 'doctrine_fine']:
        val = db.session.query(db.func.sum(Debt.amount)).filter(
            Debt.paid == False,
            Debt.debt_type == debt_type_key
        ).scalar() or 0.0
        debt_by_type[debt_type_key] = val

    return render_template('reports/index.html',
                           sorted_debtors=sorted_debtors,
                           grand_total=grand_total,
                           monthly_income=monthly_income,
                           income_by_type=income_by_type,
                           debt_by_type=debt_by_type,
                           current_month=current_month,
                           months=months,
                           selected_month=month,
                           selected_type=debt_type,
                           only_unpaid=only_unpaid)


def _get_months_list():
    """Get the last 12 months as YYYY-MM strings."""
    today = date.today()
    months = []
    for i in range(11, -1, -1):
        m = today.month - i
        y = today.year
        while m <= 0:
            m += 12
            y -= 1
        months.append(f'{y:04d}-{m:02d}')
    return months
