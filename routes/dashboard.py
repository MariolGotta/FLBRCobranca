from flask import Blueprint, render_template
from flask_login import login_required, current_user
from datetime import date
from models import db, Player, Debt, Event

dashboard_bp = Blueprint('dashboard', __name__)


@dashboard_bp.route('/')
@login_required
def index():
    if current_user.can_view_all:
        # Admin/Elite view
        total_players = Player.query.filter_by(active=True).count()
        novatos_alert = Player.query.filter(
            Player.active == True,
            Player.category == 'Novato',
            Player.join_date <= date.today().replace(
                day=date.today().day
            )
        ).all()
        # Filter novatos over 90 days
        novatos_alert = [p for p in novatos_alert if p.novato_over_limit]

        total_debt = db.session.query(db.func.sum(Debt.amount)).filter(
            Debt.paid == False
        ).scalar() or 0.0

        debtors_count = db.session.query(Debt.player_id).filter(
            Debt.paid == False
        ).distinct().count()

        recent_events = Event.query.order_by(Event.event_date.desc()).limit(5).all()

        # Monthly income (paid debts this month)
        today = date.today()
        month_str = today.strftime('%Y-%m')
        monthly_income = db.session.query(db.func.sum(Debt.amount)).filter(
            Debt.paid == True,
            Debt.month == month_str
        ).scalar() or 0.0

        return render_template('dashboard.html',
                               total_players=total_players,
                               novatos_alert=novatos_alert,
                               total_debt=total_debt,
                               debtors_count=debtors_count,
                               recent_events=recent_events,
                               monthly_income=monthly_income,
                               is_admin=current_user.is_admin)
    else:
        # Regular player / account owner view
        managed = current_user.get_managed_accounts()

        if managed:
            # Has other accounts — show multi-account overview
            all_ids = current_user.get_accessible_player_ids()
            total_debt = db.session.query(db.func.sum(Debt.amount)).filter(
                Debt.player_id.in_(all_ids),
                Debt.paid == False
            ).scalar() or 0.0

            accounts_info = []
            for pid in all_ids:
                p = Player.query.get(pid)
                if p:
                    accounts_info.append({
                        'player': p,
                        'debt': p.total_debt,
                    })
            accounts_info.sort(key=lambda x: x['player'].name)

            return render_template('dashboard_player.html',
                                   managed=managed,
                                   accounts_info=accounts_info,
                                   total_debt=total_debt)
        else:
            # Single account — go straight to own profile
            from flask import redirect, url_for
            return redirect(url_for('players.detail', player_id=current_user.id))
