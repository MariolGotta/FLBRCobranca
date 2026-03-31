from flask import Blueprint, render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user
from datetime import date, datetime
from models import db, Player, Event, EventAttendance, Debt
from routes.discord_notify import notify_new_debt, add_devedor_role

events_bp = Blueprint('events', __name__, url_prefix='/events')


def require_admin():
    if not current_user.is_admin:
        abort(403)


def require_view_all():
    if not current_user.can_view_all:
        abort(403)


@events_bp.route('/')
@login_required
def list_events():
    require_view_all()
    event_type = request.args.get('type', '')
    query = Event.query
    if event_type:
        query = query.filter_by(event_type=event_type)
    events = query.order_by(Event.event_date.desc()).all()
    return render_template('events/list.html', events=events, selected_type=event_type)


@events_bp.route('/new', methods=['GET', 'POST'])
@login_required
def new_event():
    require_admin()

    from models import Setting
    mining_fine = Setting.get('mining_fine')
    pvp_fine = Setting.get('pvp_fine')

    if request.method == 'POST':
        event_type = request.form.get('event_type')
        event_date_str = request.form.get('event_date')
        description = request.form.get('description', '').strip()

        try:
            event_date = datetime.strptime(event_date_str, '%Y-%m-%d').date()
        except (ValueError, TypeError):
            flash('Data inválida.', 'danger')
            return render_template('events/form.html', mining_fine=mining_fine, pvp_fine=pvp_fine)

        fine_amount = mining_fine if event_type == 'mining' else pvp_fine

        event = Event(
            event_type=event_type,
            event_date=event_date,
            description=description,
            fine_amount=fine_amount,
        )
        db.session.add(event)
        db.session.flush()  # get event.id

        # Create attendance records for eligible players
        # Mining events: only MINERADOR players are required to attend
        # PVP events: all non-Novato, non-Clone players
        eligible_query = Player.query.filter(
            Player.active == True,
            Player.category.notin_(['Novato', 'Clone'])
        )
        if event_type == 'mining':
            eligible_query = eligible_query.filter(Player.occupation == 'MINERADOR')
        eligible = eligible_query.all()

        for player in eligible:
            att = EventAttendance(event_id=event.id, player_id=player.id, attended=False)
            db.session.add(att)

        db.session.commit()
        flash(f'Evento de {event.type_label} criado! Marque a presença agora.', 'success')
        return redirect(url_for('events.attendance', event_id=event.id))

    return render_template('events/form.html', mining_fine=mining_fine, pvp_fine=pvp_fine)


@events_bp.route('/<int:event_id>/attendance', methods=['GET', 'POST'])
@login_required
def attendance(event_id):
    require_admin()
    event = Event.query.get_or_404(event_id)

    if request.method == 'POST':
        # Get list of player IDs that attended
        attended_ids = set(int(x) for x in request.form.getlist('attended'))

        attendances = EventAttendance.query.filter_by(event_id=event_id).all()
        for att in attendances:
            att.attended = att.player_id in attended_ids

        db.session.commit()

        # Generate fines if requested
        if 'apply_fines' in request.form and not event.fines_applied:
            _apply_event_fines(event)
            event.fines_applied = True
            db.session.commit()
            flash('Presenças salvas e multas aplicadas!', 'success')
        else:
            flash('Presenças salvas!', 'success')

        return redirect(url_for('events.detail', event_id=event_id))

    attendances = EventAttendance.query.filter_by(event_id=event_id)\
        .join(Player).order_by(Player.name).all()

    return render_template('events/attendance.html', event=event, attendances=attendances)


@events_bp.route('/<int:event_id>')
@login_required
def detail(event_id):
    require_view_all()
    event = Event.query.get_or_404(event_id)

    attendances = EventAttendance.query.filter_by(event_id=event_id)\
        .join(Player).order_by(EventAttendance.attended.desc(), Player.name).all()

    # Get fines generated for this event
    fines = Debt.query.filter_by(reference_id=event_id).all()

    return render_template('events/detail.html',
                           event=event,
                           attendances=attendances,
                           fines=fines,
                           is_admin=current_user.is_admin)


@events_bp.route('/<int:event_id>/apply-fines', methods=['POST'])
@login_required
def apply_fines(event_id):
    require_admin()
    event = Event.query.get_or_404(event_id)

    if event.fines_applied:
        flash('Multas já foram aplicadas para este evento.', 'warning')
        return redirect(url_for('events.detail', event_id=event_id))

    count = _apply_event_fines(event)
    event.fines_applied = True
    db.session.commit()
    flash(f'{count} multa(s) aplicada(s)!', 'success')
    return redirect(url_for('events.detail', event_id=event_id))


def _apply_event_fines(event):
    """
    Apply fines for absent players.
    Clone rule: if player OR any clone attended → player not fined.
    Only the principal (non-clone) is fined.
    """
    # Get all attendances for this event
    attendances = {
        att.player_id: att.attended
        for att in EventAttendance.query.filter_by(event_id=event.id).all()
    }

    count = 0
    for player_id, attended in attendances.items():
        if attended:
            continue  # attended, no fine

        player = Player.query.get(player_id)
        if not player or not player.active:
            continue

        # Mining events: only MINERADOR players can be fined
        if event.event_type == 'mining' and player.occupation != 'MINERADOR':
            continue

        # Check if any clone attended
        clone_attended = False
        for clone in player.clones:
            if clone.active and clone.category == 'Clone':
                # Check if clone attended
                clone_att = EventAttendance.query.filter_by(
                    event_id=event.id, player_id=clone.id
                ).first()
                # Clones may not be in attendance list (they're exempt), so check separately
                # Actually clones are not in the eligible list, so we check a separate query
                if clone_att and clone_att.attended:
                    clone_attended = True
                    break

        if clone_attended:
            continue  # clone covered, no fine for principal

        # Check if fine already exists
        existing = Debt.query.filter_by(
            player_id=player_id,
            reference_id=event.id,
            debt_type='mining_fine' if event.event_type == 'mining' else 'pvp_fine'
        ).first()
        if existing:
            continue

        debt_type = 'mining_fine' if event.event_type == 'mining' else 'pvp_fine'
        label = 'Mineração' if event.event_type == 'mining' else 'PVP'
        debt = Debt(
            player_id=player_id,
            debt_type=debt_type,
            amount=event.fine_amount,
            description=f'Multa ausência evento {label} - {event.event_date.strftime("%d/%m/%Y")}',
            reference_id=event.id,
            month=event.event_date.strftime('%Y-%m'),
        )
        db.session.add(debt)
        count += 1

        # Notifica jogador via Discord
        player = Player.query.get(player_id)
        if player:
            notify_new_debt(player, debt)
            add_devedor_role(player)

    return count
