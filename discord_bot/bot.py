"""
FLBR Corp Discord Bot
Detecta novos membros e permite que admins criem conta no site via Discord.
"""

import os
import requests
import discord
from discord import app_commands
from discord.ui import Button, Modal, TextInput, View, Select
from dotenv import load_dotenv

load_dotenv()

DISCORD_TOKEN         = os.environ['DISCORD_TOKEN']
DISCORD_GUILD_ID      = int(os.environ['DISCORD_GUILD_ID'])
DISCORD_ADMIN_CHANNEL = int(os.environ['DISCORD_ADMIN_CHANNEL_ID'])
BOT_API_SECRET        = os.environ['BOT_API_SECRET']
FLASK_API_URL         = os.environ.get('FLASK_API_URL', 'http://localhost:5000')
SITE_URL              = os.environ.get('SITE_URL', '')


# ─────────────────────────── helpers ────────────────────────────

def create_player_on_site(name: str, category: str) -> dict:
    """Chama a API Flask para criar um jogador. Retorna dict com ok/error."""
    try:
        resp = requests.post(
            f'{FLASK_API_URL}/api/bot/create-player',
            json={'name': name, 'category': category},
            headers={'X-Bot-Token': BOT_API_SECRET},
            timeout=10,
        )
        return resp.json()
    except Exception as e:
        return {'ok': False, 'error': str(e)}


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

        name = self.nome.value.strip()
        category = self.categoria.value.strip().capitalize()

        if category not in ('Novato', 'Piloto'):
            await interaction.followup.send(
                f'❌ Categoria inválida: **{category}**. Use `Novato` ou `Piloto`.',
                ephemeral=True,
            )
            return

        result = create_player_on_site(name, category)

        if result.get('ok'):
            # Monta mensagem de DM para o novo membro
            dm_lines = [
                f'👋 Olá **{name}**! Sua conta na FLBR Corp foi criada.',
                f'',
                f'🌐 **Site:** {SITE_URL}' if SITE_URL else '',
                f'👤 **Login:** `{name}`',
                f'🔑 **Senha inicial:** `{name}`',
                f'',
                f'Acesse o site e troque sua senha assim que possível.',
            ]
            dm_msg = '\n'.join(l for l in dm_lines if l is not None)

            try:
                await self.member.send(dm_msg)
                dm_status = '✅ DM enviada ao jogador.'
            except discord.Forbidden:
                dm_status = '⚠️ Não foi possível enviar DM (DMs bloqueadas).'

            # Atualiza a mensagem original no canal admin
            embed = discord.Embed(
                title='✅ Conta criada com sucesso',
                color=discord.Color.green(),
            )
            embed.add_field(name='Personagem', value=name, inline=True)
            embed.add_field(name='Categoria', value=category, inline=True)
            embed.add_field(name='Discord', value=self.member.mention, inline=True)
            embed.set_footer(text=f'Criado por {interaction.user.display_name} • {dm_status}')

            await interaction.edit_original_response(embed=embed, view=None)
            await interaction.followup.send(
                f'✅ Conta **{name}** criada! {dm_status}', ephemeral=True
            )

        else:
            error = result.get('error', 'Erro desconhecido')
            await interaction.followup.send(f'❌ Erro: {error}', ephemeral=True)


# ─────────────────────────── View (botões) ──────────────────────

class AprovarMembroView(View):
    def __init__(self, member: discord.Member):
        super().__init__(timeout=86400)  # 24h
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


@bot.event
async def on_ready():
    print(f'[FLBR Bot] Logado como {bot.user} (ID: {bot.user.id})')


@bot.event
async def on_member_join(member: discord.Member):
    if member.guild.id != DISCORD_GUILD_ID:
        return

    channel = bot.get_channel(DISCORD_ADMIN_CHANNEL)
    if channel is None:
        print(f'[FLBR Bot] Canal admin {DISCORD_ADMIN_CHANNEL} não encontrado!')
        return

    embed = discord.Embed(
        title='🆕 Novo membro no servidor',
        color=discord.Color.blurple(),
    )
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
