from flask import Blueprint, render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user
from datetime import datetime
from models import db, Player, PilotShip, PilotImplant, SHIP_TYPES, WEAPON_TYPES, IMPLANT_NAMES

skills_bp = Blueprint('skills', __name__, url_prefix='/players')


@skills_bp.route('/<int:player_id>/skills', methods=['GET', 'POST'])
@login_required
def manage(player_id):
    player = Player.query.get_or_404(player_id)

    # Access: admin can edit anyone; player can edit own (and managed accounts)
    can_edit = current_user.is_admin or (player_id in current_user.get_accessible_player_ids())
    if not can_edit and not current_user.can_view_all:
        abort(403)

    if request.method == 'POST':
        if not can_edit:
            abort(403)

        # --- Ships ---
        PilotShip.query.filter_by(player_id=player_id).delete()
        for ship_type in SHIP_TYPES:
            field = f'ship_{ship_type.lower().replace(" ", "_")}'
            if request.form.get(field) == 'on':
                weapon = request.form.get(f'weapon_{ship_type.lower().replace(" ", "_")}', '')
                ps = PilotShip(player_id=player_id, ship_type=ship_type, weapon_type=weapon or None)
                db.session.add(ps)

        # --- Implants ---
        PilotImplant.query.filter_by(player_id=player_id).delete()
        for implant in IMPLANT_NAMES:
            field = f'implant_{implant.lower().replace(" ", "_")}'
            if request.form.get(field) == 'on':
                level = int(request.form.get(f'level_{implant.lower().replace(" ", "_")}', 1))
                level = max(1, min(45, level))
                pi = PilotImplant(player_id=player_id, implant_name=implant, level=level)
                db.session.add(pi)

        player.skills_updated_at = datetime.utcnow()
        db.session.commit()
        flash('Skills e implantes atualizados!', 'success')
        return redirect(url_for('skills.manage', player_id=player_id))

    # Load current data
    ships_data = {ps.ship_type: ps for ps in PilotShip.query.filter_by(player_id=player_id).all()}
    implants_data = {pi.implant_name: pi for pi in PilotImplant.query.filter_by(player_id=player_id).all()}

    return render_template('players/skills.html',
                           player=player,
                           ship_types=SHIP_TYPES,
                           weapon_types=WEAPON_TYPES,
                           implant_names=IMPLANT_NAMES,
                           ships_data=ships_data,
                           implants_data=implants_data,
                           can_edit=can_edit)
