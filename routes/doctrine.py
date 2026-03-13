import os
from flask import Blueprint, render_template, current_app
from flask_login import login_required

doctrine_bp = Blueprint('doctrine', __name__, url_prefix='/doctrine')

DOCTRINE_FILE = 'Doutrina FLBR 2025.xlsx'

SLOT_ORDER = ['HIGH', 'MID', 'LOW', 'RIG', 'DRONE', 'CARGO', 'SUBSYSTEM', 'IMPLANT']


def _slot_sort_key(slot_name):
    """Sort slots in a logical order."""
    for i, prefix in enumerate(SLOT_ORDER):
        if slot_name.upper().startswith(prefix):
            return (i, slot_name)
    return (99, slot_name)


def _parse_doctrine_xlsx():
    """
    Parse the 'hitwarp' sheet from the doctrine xlsx.
    Returns a list of dicts: {name, slots: [{slot, item, qty}]}
    """
    try:
        import openpyxl
        base_dir = current_app.root_path
        path = os.path.join(base_dir, DOCTRINE_FILE)
        if not os.path.exists(path):
            return []

        wb = openpyxl.load_workbook(path, data_only=True)

        # Get ship names from Filtrohitwarp
        filter_ws = wb['Filtrohitwarp']
        ship_names = [row[0] for row in filter_ws.iter_rows(min_row=1, values_only=True) if row[0]]

        ws = wb['hitwarp']
        rows = list(ws.iter_rows(min_row=1, values_only=True))

        # Row 0: ship names at col 0, 3, 6, ...
        header_row = rows[0]
        ship_col_map = {}  # ship_name -> starting_col
        for i, val in enumerate(header_row):
            if val and str(val).strip() in ship_names:
                ship_col_map[str(val).strip()] = i

        ships = []
        for ship_name in ship_names:
            if ship_name not in ship_col_map:
                continue
            col = ship_col_map[ship_name]
            slot_dict = {}  # slot_label -> [(item, qty)]

            for row in rows[2:]:  # skip header rows
                slot = row[col] if col < len(row) else None
                item = row[col + 1] if col + 1 < len(row) else None
                qty = row[col + 2] if col + 2 < len(row) else None

                if not slot or not item:
                    continue
                slot = str(slot).strip()
                item = str(item).strip()
                if not slot or not item or item in ('0', 'None', 'Nada'):
                    continue
                try:
                    qty_int = int(qty) if qty is not None else 1
                except (ValueError, TypeError):
                    qty_int = 1

                if slot not in slot_dict:
                    slot_dict[slot] = []
                slot_dict[slot].append({'item': item, 'qty': qty_int})

            # Sort slots in logical order
            sorted_slots = sorted(slot_dict.items(), key=lambda x: _slot_sort_key(x[0]))

            ships.append({
                'name': ship_name,
                'slots': [{'slot': s, 'entries': items} for s, items in sorted_slots],
            })

        return ships

    except Exception as e:
        current_app.logger.error(f'Error parsing doctrine xlsx: {e}')
        return []


@doctrine_bp.route('/')
@login_required
def view():
    ships = _parse_doctrine_xlsx()
    return render_template('doctrine.html', ships=ships)
