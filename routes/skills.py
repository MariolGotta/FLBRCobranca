from flask import Blueprint, render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user
from datetime import datetime
from models import (db, Player, PilotShip, PilotImplant,
                    SHIP_TYPES, SHIPS_WITH_WEAPONS, SHIPS_WITHOUT_WEAPONS,
                    WEAPON_TYPES, IMPLANT_NAMES, IMPLANT_LEVEL_RANGES)

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
            ship_slug = ship_type.lower().replace(' ', '_')
            field = f'ship_{ship_slug}'
            if request.form.get(field) == 'on':
                weapons = []
                if ship_type in SHIPS_WITH_WEAPONS:
                    # Collect all checked weapon checkboxes for this ship
                    all_weapons = WEAPON_TYPES + (['Logística'] if ship_type == 'Battle Cruiser' else [])
                    for w in all_weapons:
                        w_slug = w.lower().replace(' ', '_')
                        if request.form.get(f'weapon_{ship_slug}_{w_slug}') == 'on':
                            weapons.append(w)
                weapon_str = ','.join(weapons) if weapons else None
                ps = PilotShip(player_id=player_id, ship_type=ship_type, weapon_type=weapon_str)
                db.session.add(ps)

        # --- Implants ---
        PilotImplant.query.filter_by(player_id=player_id).delete()
        for implant in IMPLANT_NAMES:
            implant_slug = implant.lower().replace(' ', '_')
            field = f'implant_{implant_slug}'
            if request.form.get(field) == 'on':
                level = request.form.get(f'level_{implant_slug}', '1-15')
                if level not in IMPLANT_LEVEL_RANGES:
                    level = '1-15'
                pi = PilotImplant(player_id=player_id, implant_name=implant, level=level)
                db.session.add(pi)

        player.skills_updated_at = datetime.utcnow()
        db.session.commit()
        flash('Skills e implantes atualizados!', 'success')
        return redirect(url_for('skills.manage', player_id=player_id))

    # Load current data
    # ships_data: { ship_type: set_of_weapons }  (only present for selected ships)
    ships_data = {}
    for ps in PilotShip.query.filter_by(player_id=player_id).all():
        weapons = set(ps.weapon_type.split(',')) if ps.weapon_type else set()
        ships_data[ps.ship_type] = weapons

    # implants_data: { implant_name: PilotImplant }
    implants_data = {pi.implant_name: pi for pi in PilotImplant.query.filter_by(player_id=player_id).all()}

    return render_template('players/skills.html',
                           player=player,
                           ship_types=SHIP_TYPES,
                           ships_with_weapons=SHIPS_WITH_WEAPONS,
                           ships_without_weapons=SHIPS_WITHOUT_WEAPONS,
                           weapon_types=WEAPON_TYPES,
                           implant_names=IMPLANT_NAMES,
                           implant_level_ranges=IMPLANT_LEVEL_RANGES,
                           ships_data=ships_data,
                           implants_data=implants_data,
                           can_edit=can_edit)
