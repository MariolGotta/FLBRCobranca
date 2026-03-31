"""
FLBR Corp Discord Bot
- Detecta novos membros e permite que admins criem conta no site
- Envia lembretes de dívidas a cada 48h para jogadores com discord_id
- Avisa jogadores sem ocupação definida
"""

import os
import requests
import discord
from discord.ui import Button, Modal, TextInput, View
from discord.ext import tasks
from dotenv import load_dotenv

load_dotenv()

DISCORD_TOKEN         = os.environ['DISCORD_TOKEN']
DISCORD_GUILD_ID      = int(os.environ['DISCORD_GUILD_ID'])
DISCORD_ADMIN_CHANNEL = int(os.environ['DISCORD_ADMIN_CHANNEL_ID'])
BOT_API_SECRET        = os.environ['BOT_API_SECRET']
FLASK_API_URL         = os.environ.get('FLASK_API_URL', 'http://localhost:30000')
SITE_URL              = os.environ.get('SITE_URL', '')


# ─────────────────────────── helpers ────────────────────────────

def _api_headers():
    return {'X-Bot-Token': BOT_API_SECRET, 'Content-Type': 'application/json'}


def create_player_on_site(name: str, category: str, discord_id: str) -> dict:
    try:
        resp = requests.post(
            f'{FLASK_API_URL}/api/bot/create-player',
            json={'name': name, 'category': category, 'discord_id': discord_id},
            headers=_api_headers(),
            timeout=10,
        )
        return resp.json()
    except Exception as e:
        return {'ok': False, 'error': str(e)}


def get_debtors() -> list:
    try:
        resp = requests.get(
            f'{FLASK_API_URL}/api/bot/debtors',
            headers=_api_headers(),
            timeout=10,
        )
        return resp.json().get('debtors', [])
    except Exception:
        return []


def get_players_without_occupation() -> list:
    try:
        resp = requests.get(
            f'{FLASK_API_URL}/api/bot/players-without-occupation',
            headers=_api_headers(),
            timeout=10,
        )
        return resp.json().get('players', [])
    except Exception:
        return []


# ─────────────────────────── Modal ──────────────────────────────

class CriarContaModal(Modal, title='Criar Conta no Site'):
    nome = TextInput(
        label='Nome do personagem in-game',
        placeholder='Ex: Grape',
        min_length=2,
        max_length=100,
    )
    categoria = TextInput(
        label='Categoria (Novato ou Piloto)',
        placeholder='Novato',
        default='Novato',
        min_length=5,
        max_length=10,
    )

    def __init__(self, member: discord.Member):
        super().__init__()
        self.member = member

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        name     = self.nome.value.strip()
        category = self.categoria.value.strip().capitalize()

        if category not in ('Novato', 'Piloto'):
            await interaction.followup.send(
                f'❌ Categoria inválida: **{category}**. Use `Novato` ou `Piloto`.',
                ephemeral=True,
            )
            return

        result = create_player_on_site(name, category, str(self.member.id))

        if result.get('ok'):
            dm_lines = [
                f'👋 Olá **{name}**! Sua conta na FLBR Corp foi criada.',
                '',
                f'🌐 **Site:** {SITE_URL}' if SITE_URL else '',
                f'👤 **Login:** `{name}`',
                f'🔑 **Senha inicial:** `{name}`',
                '',
                'Acesse o site e troque sua senha assim que possível.',
            ]
            dm_msg = '\n'.join(l for l in dm_lines if l is not None)

            try:
                await self.member.send(dm_msg)
                dm_status = '✅ DM enviada ao jogador.'
            except discord.Forbidden:
                dm_status = '⚠️ Não foi possível enviar DM (DMs bloqueadas).'

            embed = discord.Embed(title='✅ Conta criada com sucesso', color=discord.Color.green())
            embed.add_field(name='Personagem', value=name, inline=True)
            embed.add_field(name='Categoria', value=category, inline=True)
            embed.add_field(name='Discord', value=self.member.mention, inline=True)
            embed.set_footer(text=f'Criado por {interaction.user.display_name} • {dm_status}')

            await interaction.edit_original_response(embed=embed, view=None)
            await interaction.followup.send(f'✅ Conta **{name}** criada! {dm_status}', ephemeral=True)

        else:
            error = result.get('error', 'Erro desconhecido')
            await interaction.followup.send(f'❌ Erro: {error}', ephemeral=True)


# ─────────────────────────── View (botões) ──────────────────────

class AprovarMembroView(View):
    def __init__(self, member: discord.Member):
        super().__init__(timeout=86400)
        self.member = member

    @discord.ui.button(label='✅ Adicionar ao site', style=discord.ButtonStyle.success)
    async def adicionar(self, interaction: discord.Interaction, button: Button):
        modal = CriarContaModal(member=self.member)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label='❌ Ignorar', style=discord.ButtonStyle.secondary)
    async def ignorar(self, interaction: discord.Interaction, button: Button):
        embed = discord.Embed(
            title='❌ Ignorado',
            description=f'{self.member.mention} (`{self.member.display_name}`) não foi adicionado ao site.',
            color=discord.Color.dark_gray(),
        )
        embed.set_footer(text=f'Ignorado por {interaction.user.display_name}')
        await interaction.response.edit_message(embed=embed, view=None)


# ─────────────────────────── Bot ────────────────────────────────

intents = discord.Intents.default()
intents.members = True

bot = discord.Client(intents=intents)


@tasks.loop(hours=48)
async def periodic_reminders():
    """A cada 48h: envia lembretes de dívidas e avisa jogadores sem ocupação."""

    # 1. Lembretes de dívidas
    debtors = get_debtors()
    for debtor in debtors:
        try:
            user = await bot.fetch_user(int(debtor['discord_id']))
            lines = [
                f"⚠️ **FLBR Corp — Dívidas em Aberto**",
                f"Personagem: **{debtor['name']}**\n",
            ]
            for d in debtor['debts']:
                lines.append(f"• {d['description']} — **{d['amount']:.0f}M**")
            lines.append(f"\nTotal: **{debtor['total']:.0f}M**")
            if SITE_URL:
                lines.append(f"Acesse: {SITE_URL}")
            await user.send('\n'.join(lines))
        except Exception:
            pass

    # 2. Aviso de ocupação não definida
    without_occ = get_players_without_occupation()
    for p in without_occ:
        try:
            user = await bot.fetch_user(int(p['discord_id']))
            await user.send(
                f"👋 Olá **{p['name']}**!\n"
                f"Sua **ocupação** ainda não foi definida no sistema da FLBR Corp.\n"
                f"Por favor, acesse {SITE_URL + ' → ' if SITE_URL else ''}seu perfil e selecione: "
                f"**PVP**, **PVE**, **MINERADOR** ou **ROLO**.\n"
                f"Isso é importante para calcular suas cobranças corretamente! ⚔️"
            )
        except Exception:
            pass


@bot.event
async def on_ready():
    print(f'[FLBR Bot] Logado como {bot.user} (ID: {bot.user.id})')
    if not periodic_reminders.is_running():
        periodic_reminders.start()


@bot.event
async def on_member_join(member: discord.Member):
    if member.guild.id != DISCORD_GUILD_ID:
        return

    channel = bot.get_channel(DISCORD_ADMIN_CHANNEL)
    if channel is None:
        print(f'[FLBR Bot] Canal admin {DISCORD_ADMIN_CHANNEL} não encontrado!')
        return

    embed = discord.Embed(title='🆕 Novo membro no servidor', color=discord.Color.blurple())
    embed.add_field(name='Discord', value=f'{member.mention}', inline=True)
    embed.add_field(name='Username', value=member.name, inline=True)
    embed.add_field(
        name='Conta criada em',
        value=f'<t:{int(member.created_at.timestamp())}:D>',
        inline=True,
    )
    embed.set_thumbnail(url=member.display_avatar.url)
    embed.set_footer(text='Adicionar ao site FLBR Corp?')

    view = AprovarMembroView(member=member)
    await channel.send(embed=embed, view=view)


bot.run(DISCORD_TOKEN)
