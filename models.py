from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, date

db = SQLAlchemy()

ADMIN_ROLES = {'Ministro', 'CEO', 'Contador', 'Administrador'}
VIEW_ALL_ROLES = {'Ministro', 'CEO', 'Contador', 'Administrador', 'Elite'}
NOVATO_ROLES = {'Novato'}
EXEMPT_FROM_EVENT_FINE = {'Novato', 'Clone'}


class Setting(db.Model):
    __tablename__ = 'settings'
    key = db.Column(db.String(64), primary_key=True)
    value = db.Column(db.Float, nullable=False)

    DEFAULTS = {
        'srp_price': 150.0,
        'outpost_price': 250.0,
        'mining_fine': 200.0,
        'pvp_fine': 100.0,
        'doctrine_fine': 50.0,
    }

    @staticmethod
    def get(key):
        s = Setting.query.get(key)
        return s.value if s else Setting.DEFAULTS.get(key, 0.0)

    @staticmethod
    def set(key, value):
        s = Setting.query.get(key)
        if s:
            s.value = value
        else:
            s = Setting(key=key, value=value)
            db.session.add(s)
        db.session.commit()


class Player(UserMixin, db.Model):
    __tablename__ = 'players'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    category = db.Column(db.String(50), nullable=False)  # Novato, Clone, Piloto, Elite, Ministro, CEO, Contador, Administrador, Industrial
    occupation = db.Column(db.String(50))  # MINERADOR, PVE, PVP, ROLO
    account_owner = db.Column(db.String(100))  # nome real do dono
    parent_player_id = db.Column(db.Integer, db.ForeignKey('players.id'), nullable=True)
    doctrine_ship_1 = db.Column(db.String(100))
    doctrine_ship_2 = db.Column(db.String(100))
    doctrine_ship_3 = db.Column(db.String(100))
    has_outpost = db.Column(db.Boolean, default=False)
    join_date = db.Column(db.Date, default=date.today)
    password_hash = db.Column(db.String(256))
    active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    skills_updated_at = db.Column(db.DateTime, nullable=True)

    # Relationships
    clones = db.relationship('Player', backref=db.backref('parent', remote_side=[id]),
                             foreign_keys=[parent_player_id])
    debts = db.relationship('Debt', backref='player', lazy='dynamic',
                            foreign_keys='Debt.player_id')
    attendances = db.relationship('EventAttendance', backref='player', lazy='dynamic')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        if not self.password_hash:
            return False
        return check_password_hash(self.password_hash, password)

    @property
    def is_novato(self):
        return self.category == 'Novato'

    @property
    def is_clone(self):
        return self.category == 'Clone'

    @property
    def is_admin(self):
        return self.category in ADMIN_ROLES

    @property
    def can_view_all(self):
        return self.category in VIEW_ALL_ROLES

    @property
    def has_doctrine_ship(self):
        return bool(self.doctrine_ship_1 or self.doctrine_ship_2 or self.doctrine_ship_3)

    @property
    def novato_over_limit(self):
        """Returns True if player is Novato for more than 3 months."""
        if not self.is_novato:
            return False
        delta = date.today() - self.join_date
        return delta.days > 90

    @property
    def needs_skills_update(self):
        """Returns True if skills haven't been updated in the last 60 days."""
        if not self.skills_updated_at:
            return True
        delta = datetime.utcnow() - self.skills_updated_at
        return delta.days > 60

    @property
    def total_debt(self):
        return db.session.query(db.func.sum(Debt.amount)).filter(
            Debt.player_id == self.id,
            Debt.paid == False
        ).scalar() or 0.0

    def get_accessible_player_ids(self):
        """
        Returns list of player_ids this player can access:
        - Self
        - Players linked via parent_player_id (structural clones)
        - Players where account_owner == self.name (same real owner)
        """
        ids = {self.id}

        # 1. Structural clones (parent_player_id FK)
        for clone in self.clones:
            if clone.active:
                ids.add(clone.id)

        # 2. Players owned by the same real person (account_owner matches this player's name)
        owned = Player.query.filter(
            Player.account_owner == self.name,
            Player.active == True
        ).all()
        for p in owned:
            ids.add(p.id)

        return list(ids)

    def get_managed_accounts(self):
        """Returns all other active players this player can manage (excluding self)."""
        all_ids = self.get_accessible_player_ids()
        return Player.query.filter(
            Player.id.in_(all_ids),
            Player.id != self.id,
            Player.active == True
        ).order_by(Player.name).all()


class Debt(db.Model):
    __tablename__ = 'debts'

    id = db.Column(db.Integer, primary_key=True)
    player_id = db.Column(db.Integer, db.ForeignKey('players.id'), nullable=False)
    debt_type = db.Column(db.String(30), nullable=False)  # srp, outpost, mining_fine, pvp_fine, doctrine_fine
    amount = db.Column(db.Float, nullable=False)  # TRAVADO na criação
    description = db.Column(db.String(255))
    reference_id = db.Column(db.Integer)  # event_id para multas de evento
    month = db.Column(db.String(7))  # 'YYYY-MM' para cobranças mensais
    paid = db.Column(db.Boolean, default=False)
    paid_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    LABELS = {
        'srp': 'SRP',
        'outpost': 'Outpost',
        'mining_fine': 'Multa Mineração',
        'pvp_fine': 'Multa PVP',
        'doctrine_fine': 'Multa Nave Doutrina',
    }

    @property
    def label(self):
        return self.LABELS.get(self.debt_type, self.debt_type)

    def mark_paid(self):
        self.paid = True
        self.paid_at = datetime.utcnow()


class Event(db.Model):
    __tablename__ = 'events'

    id = db.Column(db.Integer, primary_key=True)
    event_type = db.Column(db.String(20), nullable=False)  # mining, pvp
    event_date = db.Column(db.Date, nullable=False)
    description = db.Column(db.String(255))
    fine_amount = db.Column(db.Float, nullable=False)  # TRAVADO na criação
    fines_applied = db.Column(db.Boolean, default=False)  # se multas já foram geradas
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    attendances = db.relationship('EventAttendance', backref='event', lazy='dynamic',
                                  cascade='all, delete-orphan')

    @property
    def type_label(self):
        return 'Mineração' if self.event_type == 'mining' else 'PVP'

    @property
    def attendance_count(self):
        return self.attendances.filter_by(attended=True).count()

    @property
    def absent_count(self):
        return self.attendances.filter_by(attended=False).count()


class EventAttendance(db.Model):
    __tablename__ = 'event_attendance'

    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey('events.id'), nullable=False)
    player_id = db.Column(db.Integer, db.ForeignKey('players.id'), nullable=False)
    attended = db.Column(db.Boolean, default=False)

    __table_args__ = (
        db.UniqueConstraint('event_id', 'player_id', name='uq_event_player'),
    )


class TextContent(db.Model):
    """Stores editable text content (tutorial, announcements, etc.)."""
    __tablename__ = 'text_content'

    key = db.Column(db.String(64), primary_key=True)
    content = db.Column(db.Text, nullable=False, default='')
    updated_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_by = db.Column(db.String(100))

    @staticmethod
    def get(key, default=''):
        row = TextContent.query.get(key)
        return row.content if row else default

    @staticmethod
    def set(key, content, updated_by=None):
        row = TextContent.query.get(key)
        if row:
            row.content = content
            row.updated_at = datetime.utcnow()
            row.updated_by = updated_by
        else:
            row = TextContent(key=key, content=content, updated_by=updated_by)
            db.session.add(row)
        db.session.commit()


SHIP_TYPES = ['Fragata', 'Destroyer', 'Cruzador', 'Battle Cruiser', 'Battleship', 'Dread', 'Carrier', 'Super']
WEAPON_TYPES = ['Canhão', 'Canhão de Raios', 'Drone', 'Laser', 'Míssil']
IMPLANT_NAMES = [
    'Defesa Tática', 'Mísseis Táticos', 'Projeção de Suporte', 'Carga de Ogiva',
    'Blindagem Remota', 'Repressão Saraivada', 'Escudo Remoto', 'Circulação Térmica',
    'Táticas de Bombarda', 'Cristal de Fogo', 'Cristal de Pulso', 'Multifrequência',
    'Tecnologia de Mira', 'Artilharia', 'Bobina de Energia Alta',
]


class PilotShip(db.Model):
    """Ships a pilot has skills for, and which weapon they use."""
    __tablename__ = 'pilot_ships'

    id = db.Column(db.Integer, primary_key=True)
    player_id = db.Column(db.Integer, db.ForeignKey('players.id'), nullable=False)
    ship_type = db.Column(db.String(50), nullable=False)
    weapon_type = db.Column(db.String(50))

    player = db.relationship('Player', backref=db.backref('pilot_ships', lazy='dynamic'))

    __table_args__ = (
        db.UniqueConstraint('player_id', 'ship_type', name='uq_pilot_ship'),
    )


class PilotImplant(db.Model):
    """Implants a pilot has and their level (1–5)."""
    __tablename__ = 'pilot_implants'

    id = db.Column(db.Integer, primary_key=True)
    player_id = db.Column(db.Integer, db.ForeignKey('players.id'), nullable=False)
    implant_name = db.Column(db.String(100), nullable=False)
    level = db.Column(db.Integer, nullable=False, default=1)

    player = db.relationship('Player', backref=db.backref('pilot_implants', lazy='dynamic'))

    __table_args__ = (
        db.UniqueConstraint('player_id', 'implant_name', name='uq_pilot_implant'),
    )
