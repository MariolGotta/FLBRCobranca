import os
from datetime import date
from flask import Blueprint, request, jsonify
from models import db, Player, Debt

api_bp = Blueprint('api', __name__, url_prefix='/api')

BOT_API_SECRET = os.environ.get('BOT_API_SECRET', '')

ALLOWED_CATEGORIES = {'Novato', 'Piloto'}


def _check_token():
    token = request.headers.get('X-Bot-Token', '')
    if not BOT_API_SECRET or token != BOT_API_SECRET:
        return False
    return True


@api_bp.route('/bot/create-player', methods=['POST'])
def create_player():
    if not _check_token():
        return jsonify({'ok': False, 'error': 'Unauthorized'}), 401

    data = request.get_json(silent=True) or {}
    name       = (data.get('name') or '').strip()
    category   = (data.get('category') or 'Novato').strip()
    discord_id = (data.get('discord_id') or '').strip() or None

    if not name:
        return jsonify({'ok': False, 'error': 'Nome é obrigatório'}), 400

    if category not in ALLOWED_CATEGORIES:
        return jsonify({'ok': False, 'error': f'Categoria inválida: {category}'}), 400

    existing = Player.query.filter_by(name=name).first()
    if existing:
        return jsonify({'ok': False, 'error': f'Jogador "{name}" já existe no sistema'}), 400

    try:
        player = Player(
            name=name,
            category=category,
            join_date=date.today(),
            discord_id=discord_id,
        )
        player.set_password(name)
        db.session.add(player)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({'ok': False, 'error': str(e)}), 500

    return jsonify({'ok': True, 'name': name, 'category': category}), 201


@api_bp.route('/bot/debtors', methods=['GET'])
def get_debtors():
    """Retorna jogadores com discord_id que têm dívidas em aberto."""
    if not _check_token():
        return jsonify({'ok': False, 'error': 'Unauthorized'}), 401

    players = Player.query.filter(
        Player.active == True,
        Player.discord_id != None,
        Player.discord_id != '',
    ).all()

    debtors = []
    for player in players:
        open_debts = [d for d in player.debts if not d.paid]
        if not open_debts:
            continue
        debtors.append({
            'discord_id': player.discord_id,
            'name': player.name,
            'total': sum(d.amount for d in open_debts),
            'debts': [
                {'type': d.debt_type, 'amount': d.amount, 'description': d.description or ''}
                for d in open_debts
            ],
        })

    return jsonify({'ok': True, 'debtors': debtors})


@api_bp.route('/bot/players-without-occupation', methods=['GET'])
def players_without_occupation():
    """Retorna jogadores com discord_id que ainda não definiram ocupação."""
    if not _check_token():
        return jsonify({'ok': False, 'error': 'Unauthorized'}), 401

    players = Player.query.filter(
        Player.active == True,
        Player.discord_id != None,
        Player.discord_id != '',
        (Player.occupation == None) | (Player.occupation == ''),
    ).all()

    result = [{'discord_id': p.discord_id, 'name': p.name} for p in players]
    return jsonify({'ok': True, 'players': result})
