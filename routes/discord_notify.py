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

TYPE_LABELS = {
    'srp':           'SRP Mensal',
    'outpost':       'Outpost',
    'mining_fine':   'Multa por ausência em evento de Mineração',
    'pvp_fine':      'Multa por ausência em evento de PVP',
    'doctrine_fine': 'Multa por não possuir Nave de Doutrina',
    'custom':        'Cobrança avulsa',
}


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

    label = TYPE_LABELS.get(debt.debt_type, debt.debt_type)
    site_line = f"\n🌐 Acesse {SITE_URL} para ver todas as suas cobranças." if SITE_URL else ""

    msg = (
        f"⚠️ **FLBR Corp — Nova cobrança registrada**\n\n"
        f"Personagem: **{player.name}**\n"
        f"Tipo: **{label}**\n"
        f"Valor: **{debt.amount:.0f}M ISK**\n"
        f"Referência: {debt.description or '—'}\n"
        f"{site_line}\n\n"
        f"_Caso tenha dúvidas, entre em contato com um Ministro ou Administrador._"
    )
    _send_dm(player.discord_id, msg)


def notify_debt_paid(player, debt):
    """Envia DM ao jogador quando uma dívida é marcada como paga."""
    if not player.discord_id or not BOT_TOKEN:
        return

    label = TYPE_LABELS.get(debt.debt_type, debt.debt_type)
    open_count = sum(1 for d in player.debts if not d.paid)
    site_line = f"\n🌐 Acesse {SITE_URL} para ver seu extrato." if SITE_URL else ""

    if open_count == 0:
        status_line = "✅ Você **não possui mais dívidas em aberto**. Obrigado!"
    else:
        status_line = f"ℹ️ Você ainda possui **{open_count}** cobrança(s) em aberto."

    msg = (
        f"✅ **FLBR Corp — Pagamento confirmado**\n\n"
        f"Personagem: **{player.name}**\n"
        f"Tipo: **{label}**\n"
        f"Valor: **{debt.amount:.0f}M ISK**\n"
        f"Referência: {debt.description or '—'}\n\n"
        f"{status_line}"
        f"{site_line}"
    )
    _send_dm(player.discord_id, msg)


def notify_all_paid(player, count):
    """Envia DM ao jogador quando todas as dívidas são quitadas de uma vez."""
    if not player.discord_id or not BOT_TOKEN:
        return

    site_line = f"\n🌐 Acesse {SITE_URL} para ver seu extrato." if SITE_URL else ""

    msg = (
        f"✅ **FLBR Corp — Todas as dívidas quitadas!**\n\n"
        f"Personagem: **{player.name}**\n"
        f"**{count}** cobrança(s) foram marcadas como pagas.\n\n"
        f"✅ Você **não possui mais dívidas em aberto**. Obrigado!"
        f"{site_line}"
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
