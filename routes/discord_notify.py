"""
Helpers para notificações Flask → Discord.
Usado para enviar DMs e gerenciar o cargo Devedor sem depender do bot estar rodando.
"""
import os
import threading
import requests

BOT_TOKEN       = os.environ.get('DISCORD_BOT_TOKEN', '')
GUILD_ID        = os.environ.get('DISCORD_GUILD_ID', '')
DEVEDOR_ROLE_ID = os.environ.get('DISCORD_DEVEDOR_ROLE_ID', '')
SITE_URL        = os.environ.get('SITE_URL', '')

_BASE = 'https://discord.com/api/v10'


def _headers():
    return {'Authorization': f'Bot {BOT_TOKEN}', 'Content-Type': 'application/json'}


def _send_dm(discord_id: str, message: str):
    """Cria canal DM e envia mensagem. Executa em thread daemon para não bloquear a request."""
    if not discord_id or not BOT_TOKEN:
        return

    def _task():
        try:
            r = requests.post(
                f'{_BASE}/users/@me/channels',
                json={'recipient_id': discord_id},
                headers=_headers(),
                timeout=5,
            )
            channel_id = r.json().get('id')
            if channel_id:
                requests.post(
                    f'{_BASE}/channels/{channel_id}/messages',
                    json={'content': message},
                    headers=_headers(),
                    timeout=5,
                )
        except Exception:
            pass

    threading.Thread(target=_task, daemon=True).start()


def notify_new_debt(player, debt):
    """Envia DM imediata ao jogador quando uma nova dívida é criada."""
    if not player.discord_id or not BOT_TOKEN:
        return

    type_labels = {
        'srp':           'SRP Mensal',
        'outpost':       'Outpost',
        'mining_fine':   'Multa Mineração',
        'pvp_fine':      'Multa PVP',
        'doctrine_fine': 'Multa Nave Doutrina',
    }
    label = type_labels.get(debt.debt_type, debt.debt_type)

    msg = (
        f"⚠️ **Nova dívida registrada — FLBR Corp**\n"
        f"Tipo: **{label}** | Valor: **{debt.amount:.0f}M**\n"
        f"Descrição: {debt.description or '—'}\n"
        + (f"Acesse {SITE_URL} para mais detalhes." if SITE_URL else "")
    )
    _send_dm(player.discord_id, msg)


def add_devedor_role(player):
    """Adiciona o cargo Devedor ao membro no Discord."""
    if not player.discord_id or not BOT_TOKEN or not GUILD_ID or not DEVEDOR_ROLE_ID:
        return

    def _task():
        try:
            requests.put(
                f'{_BASE}/guilds/{GUILD_ID}/members/{player.discord_id}/roles/{DEVEDOR_ROLE_ID}',
                headers=_headers(),
                timeout=5,
            )
        except Exception:
            pass

    threading.Thread(target=_task, daemon=True).start()


def remove_devedor_role_if_clear(player):
    """Remove o cargo Devedor se o jogador não tiver mais dívidas em aberto."""
    if not player.discord_id or not BOT_TOKEN or not GUILD_ID or not DEVEDOR_ROLE_ID:
        return

    has_open_debt = any(not d.paid for d in player.debts)
    if has_open_debt:
        return

    def _task():
        try:
            requests.delete(
                f'{_BASE}/guilds/{GUILD_ID}/members/{player.discord_id}/roles/{DEVEDOR_ROLE_ID}',
                headers=_headers(),
                timeout=5,
            )
        except Exception:
            pass

    threading.Thread(target=_task, daemon=True).start()
