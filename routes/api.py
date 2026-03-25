import os
from datetime import date
from flask import Blueprint, request, jsonify
from models import db, Player

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
    name = (data.get('name') or '').strip()
    category = (data.get('category') or 'Novato').strip()

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
        )
        player.set_password(name)
        db.session.add(player)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({'ok': False, 'error': str(e)}), 500

    return jsonify({'ok': True, 'name': name, 'password': name, 'category': category}), 201
