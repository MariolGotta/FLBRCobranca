from flask import Blueprint, render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user
from datetime import date, datetime
from models import db, Player, Debt, Setting
from routes.discord_notify import remove_devedor_role_if_clear, notify_debt_paid, notify_all_paid

players_bp = Blueprint('players', __name__, url_prefix='/players')

CATEGORIES = ['Novato', 'Clone', 'Piloto', 'FC', 'Elite', 'Industrial',
              'Ministro', 'CEO', 'Contador', 'Administrador']
OCCUPATIONS = ['MINERADOR', 'PVE', 'PVP', 'ROLO']


def require_admin():
    if not current_user.is_admin:
        abort(403)


def require_view_all():
    if not current_user.can_view_all:
        abort(403)


@players_bp.route('/')
@login_required
def list_players():
    require_view_all()
    search = request.args.get('q', '').strip()
    category = request.args.get('category', '')
    show_inactive = request.args.get('inactive', '') == '1'

    query = Player.query
    if not show_inactive:
        query = query.filter_by(active=True)
    if search:
        query = query.filter(Player.name.ilike(f'%{search}%'))
    if category:
        query = query.filter_by(category=category)

    players = query.order_by(Player.name).all()

    # Annotate with debt info
    player_debts = {}
    for p in players:
        player_debts[p.id] = p.total_debt

    return render_template('players/list.html',
                           players=players,
                           player_debts=player_debts,
                           categories=CATEGORIES,
                           selected_category=category,
                           search=search,
                           show_inactive=show_inactive)


@players_bp.route('/<int:player_id>')
@login_required
def detail(player_id):
    player = Player.query.get_or_404(player_id)

    # Access check: admin/elite can see all; others can only see own + clones
    if not current_user.can_view_all:
        allowed = current_user.get_accessible_player_ids()
        if player_id not in allowed:
            abort(403)

    debts = Debt.query.filter_by(player_id=player_id).order_by(
        Debt.paid.asc(),       # não pagos primeiro
        Debt.month.desc(),     # mês mais recente no topo
        Debt.created_at.desc() # desempate pela data de criação
    ).all()

    FINE_TYPES = {'mining_fine', 'pvp_fine', 'doctrine_fine'}

    unpaid_debts = [d for d in debts if not d.paid]
    paid_debts   = [d for d in debts if d.paid]

    total_unpaid = sum(d.amount for d in unpaid_debts)

    # Contagens para os filtros do histórico
    def _is_manual(d):
        desc = d.description or ''
        return '(importado)' not in desc and '(parcelamento)' not in desc

    paid_counts = {
        'all':     len(paid_debts),
        'srp':     sum(1 for d in paid_debts if d.debt_type == 'srp'),
        'outpost': sum(1 for d in paid_debts if d.debt_type == 'outpost'),
        'multa':   sum(1 for d in paid_debts if d.debt_type in FINE_TYPES),
        'manual':  sum(1 for d in paid_debts if _is_manual(d)),
    }

    # Accounts managed by this player (via account_owner field OR parent_player_id)
    managed_accounts = player.get_managed_accounts()

    # If this player is owned by someone, find that owner player in the DB
    owner_player = None
    if player.account_owner:
        owner_player = Player.query.filter_by(name=player.account_owner, active=True).first()

    # Show "back to my accounts" button when viewing own profile and has managed accounts
    is_own_profile = (current_user.id == player_id)
    viewer_has_managed = bool(current_user.get_managed_accounts())
    can_edit_skills = current_user.is_admin or (player_id in current_user.get_accessible_player_ids())

    return render_template('players/detail.html',
                           player=player,
                           unpaid_debts=unpaid_debts,
                           paid_debts=paid_debts,
                           total_unpaid=total_unpaid,
                           managed_accounts=managed_accounts,
                           owner_player=owner_player,
                           is_admin=current_user.is_admin,
                           is_own_profile=is_own_profile,
                           viewer_has_managed=viewer_has_managed,
                           can_edit_skills=can_edit_skills,
                           paid_counts=paid_counts)


@players_bp.route('/new', methods=['GET', 'POST'])
@login_required
def new_player():
    require_admin()

    main_players = Player.query.filter(
        Player.active == True,
        Player.category != 'Clone'
    ).order_by(Player.name).all()

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        category = request.form.get('category', 'Novato')
        occupation = request.form.get('occupation', '')
        account_owner = request.form.get('account_owner', '').strip()
        parent_id = request.form.get('parent_player_id') or None
        if parent_id:
            parent_id = int(parent_id)
        doctrine_1 = request.form.get('doctrine_ship_1', '').strip() or None
        doctrine_2 = request.form.get('doctrine_ship_2', '').strip() or None
        doctrine_3 = request.form.get('doctrine_ship_3', '').strip() or None
        has_outpost = request.form.get('has_outpost') == 'on'
        join_date_str = request.form.get('join_date', '')

        if not name:
            flash('Nome é obrigatório.', 'danger')
            return render_template('players/form.html', categories=CATEGORIES,
                                   occupations=OCCUPATIONS, main_players=main_players)

        if Player.query.filter_by(name=name).first():
            flash('Já existe um jogador com esse nome.', 'danger')
            return render_template('players/form.html', categories=CATEGORIES,
                                   occupations=OCCUPATIONS, main_players=main_players)

        try:
            join_date = datetime.strptime(join_date_str, '%Y-%m-%d').date() if join_date_str else date.today()
        except ValueError:
            join_date = date.today()

        player = Player(
            name=name,
            category=category,
            occupation=occupation,
            account_owner=account_owner,
            parent_player_id=parent_id,
            doctrine_ship_1=doctrine_1,
            doctrine_ship_2=doctrine_2,
            doctrine_ship_3=doctrine_3,
            has_outpost=has_outpost,
            join_date=join_date,
        )
        player.set_password(name)  # initial password = name
        db.session.add(player)
        db.session.commit()
        flash(f'Jogador {name} adicionado! Senha inicial: {name}', 'success')
        return redirect(url_for('players.detail', player_id=player.id))

    return render_template('players/form.html',
                           categories=CATEGORIES,
                           occupations=OCCUPATIONS,
                           main_players=main_players)


@players_bp.route('/<int:player_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_player(player_id):
    require_admin()
    player = Player.query.get_or_404(player_id)

    main_players = Player.query.filter(
        Player.active == True,
        Player.category != 'Clone',
        Player.id != player_id
    ).order_by(Player.name).all()

    if request.method == 'POST':
        player.name = request.form.get('name', player.name).strip()
        player.category = request.form.get('category', player.category)
        player.occupation = request.form.get('occupation', player.occupation)
        player.account_owner = request.form.get('account_owner', '').strip()
        parent_id = request.form.get('parent_player_id') or None
        player.parent_player_id = int(parent_id) if parent_id else None
        player.doctrine_ship_1 = request.form.get('doctrine_ship_1', '').strip() or None
        player.doctrine_ship_2 = request.form.get('doctrine_ship_2', '').strip() or None
        player.doctrine_ship_3 = request.form.get('doctrine_ship_3', '').strip() or None
        player.has_outpost = request.form.get('has_outpost') == 'on'
        player.discord_id = request.form.get('discord_id', '').strip() or None
        join_date_str = request.form.get('join_date', '')
        try:
            player.join_date = datetime.strptime(join_date_str, '%Y-%m-%d').date()
        except ValueError:
            pass

        db.session.commit()
        flash('Jogador atualizado!', 'success')
        return redirect(url_for('players.detail', player_id=player.id))

    return render_template('players/form.html',
                           player=player,
                           categories=CATEGORIES,
                           occupations=OCCUPATIONS,
                           main_players=main_players)


@players_bp.route('/<int:player_id>/deactivate', methods=['POST'])
@login_required
def deactivate_player(player_id):
    require_admin()
    player = Player.query.get_or_404(player_id)
    player.active = False
    db.session.commit()
    flash(f'Jogador {player.name} removido (desativado).', 'warning')
    return redirect(url_for('players.list_players'))


@players_bp.route('/<int:player_id>/reset-password', methods=['POST'])
@login_required
def reset_password(player_id):
    require_admin()
    player = Player.query.get_or_404(player_id)
    player.set_password(player.name)
    db.session.commit()
    flash(f'Senha de {player.name} resetada para o nome do personagem.', 'success')
    return redirect(url_for('players.detail', player_id=player_id))


@players_bp.route('/<int:player_id>/reactivate', methods=['POST'])
@login_required
def reactivate_player(player_id):
    require_admin()
    player = Player.query.get_or_404(player_id)
    player.active = True
    db.session.commit()
    flash(f'Jogador {player.name} reativado.', 'success')
    return redirect(url_for('players.detail', player_id=player.id))


@players_bp.route('/<int:player_id>/mark-debt-paid', methods=['POST'])
@login_required
def mark_debt_paid(player_id):
    require_admin()
    debt_id = request.form.get('debt_id')
    debt = Debt.query.get_or_404(int(debt_id))
    if debt.player_id != player_id:
        abort(400)
    debt.mark_paid()
    db.session.commit()
    player = Player.query.get(player_id)
    if player:
        notify_debt_paid(player, debt)
        remove_devedor_role_if_clear(player)
    flash('Dívida marcada como paga!', 'success')
    return redirect(url_for('players.detail', player_id=player_id))


@players_bp.route('/<int:player_id>/mark-all-paid', methods=['POST'])
@login_required
def mark_all_paid(player_id):
    require_admin()
    debts = Debt.query.filter_by(player_id=player_id, paid=False).all()
    count = len(debts)
    for debt in debts:
        debt.mark_paid()
    db.session.commit()
    player = Player.query.get(player_id)
    if player:
        notify_all_paid(player, count)
        remove_devedor_role_if_clear(player)
    flash(f'{count} dívida(s) marcadas como pagas!', 'success')
    return redirect(url_for('players.detail', player_id=player_id))
