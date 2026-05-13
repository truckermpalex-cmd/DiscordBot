import os
import json
import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import time

TOKEN = os.environ.get("DISCORD_TOKEN")
GUILD_ID = 1503750714273304649
GUILD = discord.Object(id=GUILD_ID)

RECRUITMENT_CATEGORY_NAME = "📋 RECRUITMENT DIVISION"
ACTIVE_APPS_CATEGORY_NAME = "📥 ACTIVE APPLICATIONS"
OLD_APPS_CATEGORY_NAME = "🗂 OLD APPLICATIONS"
APPLICATIONS_CHANNEL_NAME = "📥│applications"
RANK_MESSAGE_FILE = "bot/rank_message.json"
OLD_TICKETS_CATEGORY_NAME = "🗂 OLD TICKETS"
GENERAL_CHAT_NAME = "💬│general-chat"
RECRUITMENT_MESSAGE_FILE = "bot/recruitment_message.json"
DISCIPLINARY_LOG_FILE = "bot/disciplinary_log.json"
RECRUITMENT_LOG_CHANNEL_NAME = "📈│recruitment-logs"

TICKET_TYPE_CATEGORIES = {
    "General Support":    "🎫 GENERAL SUPPORT",
    "Supervisor":         "👮 SUPERVISOR TICKETS",
    "High Command":       "🔺 HIGH COMMAND TICKETS",
    "Training Officer":   "🎓 TRAINING OFFICER TICKETS",
}
ALL_ACTIVE_TICKET_CATEGORIES = list(TICKET_TYPE_CATEGORIES.values())

RANK_SECTIONS = [
    ("🔺 HIGH COMMAND", [
        ("Chief Commander", ["🛡 Chief Commander", "🎖 Chief Commander"], "[HC]"),
        ("Deputy Commander", ["⭐ Deputy Commander", "🎖 Deputy Commander"], "[HC]"),
        ("Internal Affairs", ["🕵 Internal Affairs"], "[HC]"),
    ]),
    ("👮 LOW COMMAND", [
        ("Captain", ["👮 Captain"], "[LC]"),
        ("Lieutenant", ["👮 Lieutenant"], "[LC]"),
    ]),
    ("🔰 SUPERVISOR", [
        ("Sergeant", ["👮 Sergeant"], "[SV]"),
        ("Corporal", ["👮 Corporal"], "[SV]"),
    ]),
    ("🚔 PATROL GRADE", [
        ("Senior Patrol Officer", ["🚔 Senior Patrol Officer"], "[HRT]"),
        ("Patrol Officer", ["🚓 Patrol Officer"], "[HRT]"),
    ]),
    ("🪖 TRAINING PROGRAM", [
        ("Cadet", ["🪖 HRT Cadet"], "[CADET]"),
    ]),
]

# Flat list of all ranks: (display_name, role_names, tag)
ALL_RANKS = [
    (display, role_names, tag)
    for _, ranks in RANK_SECTIONS
    for display, role_names, tag in ranks
]

# Map every role name variant → its tag
ROLE_TO_TAG = {rn: tag for _, role_names, tag in ALL_RANKS for rn in role_names}

# All known tags (for stripping old ones from nicknames)
ALL_TAGS = ["[HC]", "[LC]", "[SV]", "[HRT]", "[CADET]"]


def load_rank_message():
    try:
        with open(RANK_MESSAGE_FILE, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_rank_message(data: dict):
    with open(RANK_MESSAGE_FILE, "w") as f:
        json.dump(data, f)
        
def build_rank_embed(guild: discord.Guild) -> discord.Embed:

    embed = discord.Embed(
        title="📊 HRT — RANK STRUCTURE",
        description="Live roster showing all members by rank. Updates automatically on promotions and demotions.",
        color=discord.Color.dark_blue()
    )

    for section_name, ranks in RANK_SECTIONS:

        embed.add_field(
            name=f"━━━━━━ {section_name} ━━━━━━",
            value="\u200b",
            inline=False
        )

        for display_name, role_names, _tag in ranks:

            role = None
            matched_name = display_name

            for role_name in role_names:
                role = discord.utils.get(guild.roles, name=role_name)

                if role:
                    matched_name = role.name
                    break

            members = []

            if role:

                fresh_members = [
                    m for m in guild.members
                    if role in m.roles
                ]

                sorted_members = sorted(
                    fresh_members,
                    key=lambda m: m.joined_at or discord.utils.utcnow()
                )

                members = [m.mention for m in sorted_members]

            member_text = "\n".join(members)

            # Discord embed field value limit
            if len(member_text) > 1000:
                member_text = member_text[:1000] + "\n..."

            embed.add_field(
                name=f"{matched_name} ({len(members)})",
                value=member_text if members else "*None*",
                inline=False
            )

    embed.set_footer(
        text="HRT • Auto-updates on rank changes"
    )

    return embed

async def update_member_tag(member: discord.Member):
    # Find the tag for their highest rank role
    new_tag = None
    for _display, role_names, tag in ALL_RANKS:
        for role_name in role_names:
            if any(r.name == role_name for r in member.roles):
                new_tag = tag
                break
        if new_tag:
            break

    # Strip all existing tags from their current display name
    base = member.nick if member.nick else member.name
    for t in ALL_TAGS:
        base = base.replace(f" {t}", "").replace(t, "").strip()

    new_nick = f"{base} {new_tag}" if new_tag else base

    # Don't edit if nothing changed
    current = member.nick or ""
    if new_nick == current or (not member.nick and new_nick == member.name):
        return

    try:
        await member.edit(nick=new_nick)
    except discord.Forbidden:
        pass  # Can't edit server owner or someone with higher perms


async def update_rank_board(guild: discord.Guild):

    data = load_rank_message()

    channel_id = data.get("channel_id")
    message_id = data.get("message_id")

    if not channel_id or not message_id:
        print("[DEBUG] No saved rank board message.")
        return

    try:
        channel = await bot.fetch_channel(int(channel_id))
        message = await channel.fetch_message(int(message_id))

        # Refresh member cache
        await guild.chunk(cache=True)

        new_embed = build_rank_embed(guild)

        print(f"[DEBUG] Total embed fields: {len(new_embed.fields)}")

        await message.edit(embed=new_embed)

        print("[DEBUG] Rank board updated successfully.")

    except Exception as e:
        print(f"[RANK BOARD ERROR] {e}")
        
intents = discord.Intents.default()
intents.members = True
intents.guilds = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_app_command_error(interaction: discord.Interaction, error):
    print(f"[APP COMMAND ERROR] {error}")

    try:
        if interaction.response.is_done():
            await interaction.followup.send(
                f"❌ Error: {error}",
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                f"❌ Error: {error}",
                ephemeral=True
            )

    except Exception as e:
        print(f"[ERROR HANDLER FAILED] {e}")

@bot.event
async def on_error(event, *args, **kwargs):
    import traceback

    print(f"[EVENT ERROR] {event}")
    traceback.print_exc()

def trainer_check(member):
    """Recruiter, Training Officer, and High Command — for /accept, /cadet, /officer, and application buttons."""
    allowed_roles = [
        "📋 Recruiter", "🎓 Training Officer",
        "⭐ Deputy Commander", "🛡 Chief Commander", "🎖 Chief Commander",
    ]
    return any(role.name in allowed_roles for role in member.roles)


def supervisor_check(member):
    """Lieutenant and above — for /promote and /demote."""
    allowed_roles = [
        "👮 Lieutenant",
        "👮 Captain",
        "⭐ Deputy Commander",
        "🛡 Chief Commander",
        "🎖 Chief Commander",
    ]
    return any(role.name in allowed_roles for role in member.roles)


def recruiter_check(member):
    """Recruiter and above — for /recruitment."""
    allowed_roles = [
        "📋 Recruiter",
        "🎓 Training Officer",
        "👮 Sergeant",
        "👮 Lieutenant",
        "👮 Captain",
        "⭐ Deputy Commander",
        "🛡 Chief Commander",
        "🎖 Chief Commander",
    ]
    return any(role.name in allowed_roles for role in member.roles)


def recruiter_only_check(member):
    """Recruiter role only (plus High Command)."""
    allowed_roles = [
        "📋 Recruiter",
        "⭐ Deputy Commander",
        "🛡 Chief Commander",
        "🎖 Chief Commander",
    ]
    return any(role.name in allowed_roles for role in member.roles)


def high_command_check(member):
    """Deputy Commander and Chief Commander only — for setup commands."""
    allowed_roles = [
        "⭐ Deputy Commander",
        "🛡 Chief Commander",
        "🎖 Chief Commander",
    ]
    return any(role.name in allowed_roles for role in member.roles)


# =========================================================
# APPLICATION SYSTEM
# =========================================================

async def get_or_create_category(guild: discord.Guild, name: str, position_after: str = None):
    category = discord.utils.get(guild.categories, name=name)
    if category is None:
        category = await guild.create_category(name)
        if position_after:
            ref = discord.utils.get(guild.categories, name=position_after)
            if ref:
                await category.edit(position=ref.position + 1)
    return category


async def archive_channel(channel: discord.TextChannel, guild: discord.Guild):
    old_apps = await get_or_create_category(guild, OLD_APPS_CATEGORY_NAME, position_after=ACTIVE_APPS_CATEGORY_NAME)
    everyone = guild.default_role
    overwrites = {
        everyone: discord.PermissionOverwrite(read_messages=False, send_messages=False)
    }
    for role in guild.roles:
        if role.name in ["⭐ Deputy Commander", "🎖 Deputy Commander", "🛡 Chief Commander", "🎖 Chief Commander"]:
            overwrites[role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
    await channel.edit(category=old_apps, overwrites=overwrites)


class ApplicationDecisionView(discord.ui.View):
    def __init__(self, applicant: discord.Member | None):
        super().__init__(timeout=None)
        self.applicant = applicant

    async def _resolve_applicant(self, interaction: discord.Interaction):
        if self.applicant:
            return self.applicant

        topic = interaction.channel.topic

        if topic:
            user_id = topic.split(" | ")[0]

            if user_id.isdigit():
                try:
                    return await interaction.guild.fetch_member(int(user_id))
                except (discord.NotFound, discord.HTTPException):
                    return None

        return None

    @discord.ui.button(
        label="🔒 Claim",
        style=discord.ButtonStyle.secondary,
        custom_id="app_claim"
    )
    async def claim_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        if not trainer_check(interaction.user):
            return await interaction.response.send_message(
                "❌ No permission.",
                ephemeral=True
            )

        await interaction.response.send_message(
            f"🔒 This application has been claimed by {interaction.user.mention}."
        )

    @discord.ui.button(
        label="🔓 Unclaim",
        style=discord.ButtonStyle.secondary,
        custom_id="app_unclaim"
    )
    async def unclaim_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        if not trainer_check(interaction.user):
            return await interaction.response.send_message(
                "❌ No permission.",
                ephemeral=True
            )

        await interaction.response.send_message(
            f"🔓 This application has been unclaimed by {interaction.user.mention}."
        )

    @discord.ui.button(
        label="✅ Accept",
        style=discord.ButtonStyle.success,
        custom_id="app_accept"
    )
    async def accept_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        if not trainer_check(interaction.user):
            return await interaction.response.send_message(
                "❌ No permission.",
                ephemeral=True
            )

        applicant = await self._resolve_applicant(interaction)

        if not applicant:
            return await interaction.response.send_message(
                "⚠️ Applicant could not be found.",
                ephemeral=True
            )
        )

@bot.event
async def on_ready():

    print(f"Logged in as {bot.user}")

    try:
        bot.add_view(ApplyButtonView())
        bot.add_view(ApplicationDecisionView(None))
        bot.add_view(VerifyButtonView())
        bot.add_view(SupportTicketView())
        bot.add_view(TicketCloseView())

        try:
            synced = await bot.tree.sync(guild=GUILD)
            print(f"Guild synced: {len(synced)}")

        except Exception as e:
            print(f"Guild sync failed: {e}")

            synced = await bot.tree.sync()
            print(f"Global synced: {len(synced)}")

        guild = bot.get_guild(GUILD_ID)

        print(f"[DEBUG] Guild found: {guild}")

        if guild:
            await update_rank_board(guild)
            print("[STARTUP] Rank board refreshed.")

    except Exception as e:
        print(f"[READY ERROR] {e}")

# =========================================================
# SLASH COMMANDS
# =========================================================

class VerifyButtonView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="✅ Verify", style=discord.ButtonStyle.success, custom_id="verify_member")
    async def verify_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        verified = discord.utils.get(interaction.guild.roles, name="✅ Verified")
        if not verified:
            return await interaction.response.send_message(
                "❌ Verified role not found. Contact an admin.", ephemeral=True
            )
        if verified in interaction.user.roles:
            return await interaction.response.send_message(
                "✅ You are already verified.", ephemeral=True
            )
        await interaction.user.add_roles(verified)
        await interaction.response.send_message("✅ You are now verified!", ephemeral=True)


@bot.tree.command(name="setup_verify", description="Post the verification embed with the Verify button", guild=GUILD)
async def setup_verify(interaction: discord.Interaction):
    if not high_command_check(interaction.user):
        return await interaction.response.send_message("❌ You don't have permission to use this command.", ephemeral=True)

    embed = discord.Embed(
        title="✅ HRT — VERIFICATION",
        description=(
            "Welcome to **HRT**!\n\n"
            "To gain access to the server, click the button below to verify yourself.\n\n"
            "By verifying, you confirm that you have read and agree to follow all server rules."
        ),
        color=discord.Color.green()
    )
    embed.add_field(
        name="📋 Before You Verify",
        value=(
            "• Read the rules channel carefully.\n"
            "• Ensure your username follows server naming conventions.\n"
            "• Reach out to staff if you have any questions."
        ),
        inline=False
    )
    embed.set_footer(text="HRT • Click the button below to verify")

    await interaction.channel.send(embed=embed, view=VerifyButtonView())
    await interaction.response.send_message("✅ Verification embed posted.", ephemeral=True)


# =========================================================
# SUPPORT TICKET SYSTEM
# =========================================================

class TicketCloseView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    def _is_staff(self, user: discord.Member) -> bool:
        return supervisor_check(user) or any(
            r.name in ["🎓 Training Officer", "🎫 Support Team"] for r in user.roles
        )

    @discord.ui.button(label="🔏 Claim", style=discord.ButtonStyle.secondary, custom_id="ticket_claim")
    async def claim_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self._is_staff(interaction.user):
            return await interaction.response.send_message("❌ No permission.", ephemeral=True)
        await interaction.response.send_message(
            f"🔏 This ticket has been **claimed** by {interaction.user.mention}."
        )

    @discord.ui.button(label="🔓 Unclaim", style=discord.ButtonStyle.secondary, custom_id="ticket_unclaim")
    async def unclaim_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self._is_staff(interaction.user):
            return await interaction.response.send_message("❌ No permission.", ephemeral=True)
        await interaction.response.send_message(
            f"🔓 This ticket has been **unclaimed** by {interaction.user.mention}."
        )

    @discord.ui.button(label="🔒 Close Ticket", style=discord.ButtonStyle.danger, custom_id="ticket_close")
    async def close_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self._is_staff(interaction.user):
            return await interaction.response.send_message("❌ No permission.", ephemeral=True)
        await interaction.response.send_message("🔒 Closing ticket and moving to archive...")
        guild = interaction.guild
        channel = interaction.channel
        topic = channel.topic or ""
        opener_id = int(topic.split(" | ")[0]) if " | " in topic else None
        ticket_type = topic.split(" | ")[1] if " | " in topic else "Unknown"

        # Build transcript before archiving
        messages = []
        async for msg in channel.history(limit=200, oldest_first=True):
            if msg.author.bot and not msg.content:
                continue
            ts = msg.created_at.strftime("%d/%m/%Y %H:%M")
            content = msg.content or "[embed/attachment]"
            messages.append(f"[{ts}] {msg.author} ({msg.author.id}): {content}")
        transcript_text = "\n".join(messages) if messages else "No messages found."
        transcript_bytes = transcript_text.encode("utf-8")
        transcript_file = discord.File(
            fp=__import__("io").BytesIO(transcript_bytes),
            filename=f"transcript-{channel.name}.txt"
        )

        last_active_cat = ALL_ACTIVE_TICKET_CATEGORIES[-1]
        old_cat = await get_or_create_category(guild, OLD_TICKETS_CATEGORY_NAME, position_after=last_active_cat)
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False, send_messages=False)
        }
        for role in guild.roles:
            if role.name in ["⭐ Deputy Commander", "🎖 Deputy Commander", "🛡 Chief Commander", "🎖 Chief Commander"]:
                overwrites[role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
        await channel.edit(category=old_cat, overwrites=overwrites)

        # DM the opener
        if opener_id:
            opener = guild.get_member(opener_id)
            if opener:
                dm_embed = discord.Embed(
                    title="🔒 Your Ticket Has Been Closed",
                    description=(
                        f"Your **{ticket_type}** ticket in **{guild.name}** has been closed by "
                        f"{interaction.user.mention}.\n\n"
                        "A transcript of the conversation is attached below."
                    ),
                    color=discord.Color.red()
                )
                dm_embed.set_footer(text="HRT Support")
                transcript_file_dm = discord.File(
                    fp=__import__("io").BytesIO(transcript_bytes),
                    filename=f"transcript-{channel.name}.txt"
                )
                try:
                    await opener.send(embed=dm_embed, file=transcript_file_dm)
                except discord.Forbidden:
                    pass

        log_embed = discord.Embed(
            title="🔒 Ticket Closed",
            color=discord.Color.red()
        )
        opener_mention = f"<@{opener_id}>" if opener_id else "Unknown"
        log_embed.add_field(name="Opened By", value=opener_mention, inline=True)
        log_embed.add_field(name="Closed By", value=f"{interaction.user.mention} (`{interaction.user}`)", inline=True)
        log_embed.add_field(name="Type", value=ticket_type, inline=True)
        log_embed.add_field(name="Channel", value=channel.mention, inline=True)
        log_embed.set_footer(text=f"Closed by ID: {interaction.user.id}")
        await send_ticket_log(guild, log_embed, file=transcript_file)


async def send_ticket_log(guild: discord.Guild, embed: discord.Embed, file: discord.File = None):
    """Send an embed to the ticket-logs channel if it exists."""
    log_channel = discord.utils.find(
        lambda c: "ticket-logs" in c.name.lower(), guild.text_channels
    )
    if log_channel:
        try:
            if file:
                await log_channel.send(embed=embed, file=file)
            else:
                await log_channel.send(embed=embed)
        except discord.Forbidden:
            pass


async def _open_ticket(
    interaction: discord.Interaction,
    ticket_type: str,
    staff_role_names: list[str]
):

    await interaction.response.defer(ephemeral=True)

    guild = interaction.guild
    user = interaction.user

    safe_name = user.name.lower().replace(" ", "-")
    type_slug = ticket_type.lower().replace(" ", "-")
    channel_name = f"ticket-{type_slug}-{safe_name}"

    # Count all open tickets
    open_tickets = [
        ch for ch in guild.text_channels
        if ch.category
        and ch.category.name in ALL_ACTIVE_TICKET_CATEGORIES
        and ch.topic
        and ch.topic.startswith(str(user.id))
    ]

    if len(open_tickets) >= 3:
        mentions = ", ".join(ch.mention for ch in open_tickets)

        return await interaction.followup.send(
            f"⚠️ You already have **{len(open_tickets)}/3** tickets open: {mentions}\n"
            "Please wait for one to be resolved before opening another.",
            ephemeral=True
        )

    # Also block duplicate of the exact same type
    existing_same_type = discord.utils.get(guild.text_channels, name=channel_name)
    if existing_same_type and existing_same_type.category and existing_same_type.category.name in ALL_ACTIVE_TICKET_CATEGORIES:
        return await interaction.followup.send(
            f"⚠️ You already have an open {ticket_type} ticket: {existing_same_type.mention}", ephemeral=True
        )

    category_name = TICKET_TYPE_CATEGORIES[ticket_type]
    category = await get_or_create_category(guild, category_name)
    everyone = guild.default_role
    overwrites = {
        everyone: discord.PermissionOverwrite(read_messages=False),
        user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
    }
    for role in guild.roles:
        if role.name in staff_role_names + ["⭐ Deputy Commander", "🛡 Chief Commander", "🎖 Chief Commander"]:
            overwrites[role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)

    channel = await guild.create_text_channel(
        name=channel_name,
        category=category,
        overwrites=overwrites,
        topic=f"{user.id} | {ticket_type}"
    )

    pings = " ".join(
        role.mention for role in guild.roles if role.name in staff_role_names
    )

    embed = discord.Embed(
        title=f"🎫 {ticket_type} Ticket",
        description=(
            f"Hey {user.mention}! Your ticket has been created.\n\n"
            f"**Type:** {ticket_type}\n"
            f"Please describe your issue and a staff member will be with you shortly."
        ),
        color=discord.Color.blurple()
    )
    embed.set_footer(text="HRT Support • Use the button below to close when resolved.")
    await channel.send(content=pings if pings else None, embed=embed, view=TicketCloseView())
    await interaction.followup.send(
    f"✅ Your ticket has been opened: {channel.mention}",
    ephemeral=True
)

    log_embed = discord.Embed(
        title="🎫 Ticket Opened",
        color=discord.Color.green()
    )
    log_embed.add_field(name="User", value=f"{user.mention} (`{user}`)", inline=True)
    log_embed.add_field(name="Type", value=ticket_type, inline=True)
    log_embed.add_field(name="Channel", value=channel.mention, inline=True)
    log_embed.set_footer(text=f"User ID: {user.id}")
    await send_ticket_log(guild, log_embed)


class SupportTicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🎫 General Support", style=discord.ButtonStyle.primary, custom_id="ticket_general")
    async def general_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await _open_ticket(interaction, "General Support", ["🎫 Support Team"])

    @discord.ui.button(label="👮 Supervisor", style=discord.ButtonStyle.secondary, custom_id="ticket_supervisor")
    async def supervisor_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await _open_ticket(interaction, "Supervisor", ["👮 Sergeant", "👮 Lieutenant", "👮 Captain"])

    @discord.ui.button(label="🔺 High Command", style=discord.ButtonStyle.danger, custom_id="ticket_hc")
    async def hc_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await _open_ticket(interaction, "High Command", ["⭐ Deputy Commander", "🎖 Deputy Commander", "🛡 Chief Commander", "🎖 Chief Commander"])

    @discord.ui.button(label="🎓 Training Officer", style=discord.ButtonStyle.success, custom_id="ticket_training")
    async def training_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await _open_ticket(interaction, "Training Officer", ["🎓 Training Officer"])


def get_rank_role(guild: discord.Guild, display_name: str):
    """Return the first matching Discord role for a rank display name."""
    for _display, role_names, _tag in ALL_RANKS:
        if _display == display_name:
            for rn in role_names:
                role = discord.utils.get(guild.roles, name=rn)
                if role:
                    return role
    return None


async def clear_rank_roles(member: discord.Member):
    """Remove all tracked rank roles from a member."""
    to_remove = [r for r in member.roles if r.name in ROLE_TO_TAG]
    if to_remove:
        await member.remove_roles(*to_remove)


RANK_CHOICES = [
    app_commands.Choice(name="🛡 Chief Commander",        value="Chief Commander"),
    app_commands.Choice(name="⭐ Deputy Commander",       value="Deputy Commander"),
    app_commands.Choice(name="🕵 Internal Affairs",       value="Internal Affairs"),
    app_commands.Choice(name="👮 Captain",                value="Captain"),
    app_commands.Choice(name="👮 Lieutenant",             value="Lieutenant"),
    app_commands.Choice(name="👮 Sergeant",               value="Sergeant"),
    app_commands.Choice(name="👮 Corporal",               value="Corporal"),
    app_commands.Choice(name="🚔 Senior Patrol Officer",  value="Senior Patrol Officer"),
    app_commands.Choice(name="🚓 Patrol Officer",         value="Patrol Officer"),

    app_commands.Choice(name="🪖 HRT Cadet",              value="Cadet"),
]




@bot.tree.command(name="promote", description="Promote a member to a selected rank", guild=GUILD)
@app_commands.describe(member="Member to promote", rank="Rank to promote to")
@app_commands.choices(rank=RANK_CHOICES)
async def promote(
    interaction: discord.Interaction,
    member: discord.Member,
    rank: app_commands.Choice[str]
):

    if not high_command_check(interaction.user):
        return await interaction.response.send_message(
            "❌ No permission.",
            ephemeral=True
        )

    target_role = get_rank_role(interaction.guild, rank.value)

    if not target_role:
        return await interaction.response.send_message(
            f"❌ Role for **{rank.name}** not found.",
            ephemeral=True
        )

    print("[DEBUG] Clearing old rank roles...")

    await clear_rank_roles(member)

    print(f"[DEBUG] Adding role: {target_role.name}")

    await member.add_roles(target_role)
    print("[DEBUG] Updating nickname tag...")

    await update_member_tag(member)

    print("[DEBUG] Updating rank board...")

    await update_rank_board(interaction.guild)

    print("[DEBUG] Promotion complete.")

    await interaction.response.send_message(
        f"⬆️ {member.mention} has been promoted to **{rank.name}** by {interaction.user.mention}."
    )

@bot.tree.command(name="demote", description="Demote a member to a selected rank", guild=GUILD)
@app_commands.describe(member="Member to demote", rank="Rank to demote to")
@app_commands.choices(rank=RANK_CHOICES)
async def demote(
    interaction: discord.Interaction,
    member: discord.Member,
    rank: app_commands.Choice[str]
):

    if not high_command_check(interaction.user):
        return await interaction.response.send_message(
            "❌ No permission.",
            ephemeral=True
        )

    target_role = get_rank_role(interaction.guild, rank.value)

    if not target_role:
        return await interaction.response.send_message(
            f"❌ Role for **{rank.name}** not found.",
            ephemeral=True
        )

    await clear_rank_roles(member)

    await member.add_roles(target_role)

    await update_member_tag(member)

    await update_rank_board(interaction.guild)

    await interaction.response.send_message(
        f"⬇️ {member.mention} has been demoted to **{rank.name}** by {interaction.user.mention}."
    )


@bot.tree.command(name="fire", description="Remove a member from HRT", guild=GUILD)
@app_commands.describe(member="Member to fire", reason="Reason for termination")
async def fire(interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided"):
    if not high_command_check(interaction.user):
        return await interaction.response.send_message("❌ No permission.", ephemeral=True)
    await clear_rank_roles(member)

    await asyncio.sleep(1)

    await update_member_tag(member)
 
    await update_rank_board(interaction.guild)
    embed = discord.Embed(
        title="🚫 Member Terminated",
        description=f"{member.mention} has been **fired** from HRT by {interaction.user.mention}.",
        color=discord.Color.red()
    )
    embed.add_field(name="Reason", value=reason, inline=False)
    await interaction.response.send_message(embed=embed)
    try:
        await member.send(
            f"🚫 You have been **terminated** from **HRT** by {interaction.user.display_name}.\n"
            f"**Reason:** {reason}"
        )
    except discord.Forbidden:
        pass


@bot.tree.command(name="retire", description="Retire a member and give them the Retired role", guild=GUILD)
@app_commands.describe(member="Member to retire")
async def retire(interaction: discord.Interaction, member: discord.Member):
    if not high_command_check(interaction.user):
        return await interaction.response.send_message("❌ No permission.", ephemeral=True)
    await clear_rank_roles(member)

    await asyncio.sleep(1)
    retired_role = discord.utils.get(interaction.guild.roles, name="🎖 Retired")
    if retired_role:
        await member.add_roles(retired_role)
    await update_member_tag(member)
    await update_rank_board(interaction.guild)
    embed = discord.Embed(
        title="🎖 Member Retired",
        description=f"{member.mention} has been **retired** from active duty by {interaction.user.mention}.",
        color=discord.Color.gold()
    )
    embed.set_footer(text="HRT • Thank you for your service.")
    await interaction.response.send_message(embed=embed)
    try:
        await member.send(
            f"🎖 You have been **retired** from active duty in **HRT**.\n"
            "Thank you for your service. Your contributions are appreciated."
        )
    except discord.Forbidden:
        pass



@bot.tree.command(name="faq", description="Post the FAQ embed", guild=GUILD)
async def setup_faq(interaction: discord.Interaction):
    if not high_command_check(interaction.user):
        return await interaction.response.send_message("❌ No permission.", ephemeral=True)

    guild = interaction.guild
    apps_channel = discord.utils.get(guild.text_channels, name=APPLICATIONS_CHANNEL_NAME)
    support_channel = discord.utils.get(
    guild.text_channels,
    name="open-tickets"
)
    apps_link = apps_channel.mention if apps_channel else "#applications"
    support_link = support_channel.mention if support_channel else "#support"

    embed = discord.Embed(
        title="❓ HRT — FREQUENTLY ASKED QUESTIONS",
        description="Here are answers to the most common questions about HRT.",
        color=discord.Color.dark_blue()
    )
    embed.add_field(
        name="❓ What is HRT?",
        value=(
            "HRT is an elite law enforcement unit on **GTA Cops and Robbers (CNR)**. "
            "We are a structured, discipline-driven unit focused on professional operations, teamwork, and rank progression."
        ),
        inline=False
    )
    embed.add_field(
        name="❓ How do I join HRT?",
        value=(
            f"Head to {apps_link} and click **Apply Now**. "
            "A private channel will be created for you where a recruiter will guide you through the process."
        ),
        inline=False
    )
    embed.add_field(
        name="❓ What are the requirements to join?",
        value=(
            "• Active GTA CNR player\n"
            "• Working microphone\n"
            "• Minimum age: 16\n"
            "• Respectful and professional attitude\n"
            "• Willingness to follow orders and work as a team"
        ),
        inline=False
    )
    embed.add_field(
        name="❓ What happens after my application is accepted?",
        value=(
            "You will be given the **Cadet** rank and assigned to the Training Academy. "
            "You must complete your training before being promoted to a full SWAT rank."
        ),
        inline=False
    )
    embed.add_field(
        name="❓ How do promotions work?",
        value=(
            "Promotions are handled by **Lieutenants and above** based on activity, performance, and conduct. "
            "There is no set time requirement — demonstrate your skill and dedication."
        ),
        inline=False
    )
    embed.add_field(
        name="❓ Can I get fired or demoted?",
        value=(
            "Yes. Misconduct or failing to follow unit standards can result in demotion or termination. "
            "All decisions are made by supervision and documented."
        ),
        inline=False
    )
    embed.add_field(
        name="❓ Who do I contact if I have an issue?",
        value=(
            f"For general matters, head to {support_link}. "
            "For serious concerns, reach out to **High Command (Deputy/Chief Commander)** directly."
        ),
        inline=False
    )
    embed.set_footer(text="HRT • We Respond. We Protect. We Prevail.")
    await interaction.channel.send(embed=embed)
    await interaction.response.send_message("✅ FAQ embed posted.", ephemeral=True)


@bot.tree.command(name="rules", description="Send server rules embed", guild=GUILD)
async def setup_rules(interaction: discord.Interaction):
    if not high_command_check(interaction.user):
        return await interaction.response.send_message("❌ No permission.", ephemeral=True)

    embed = discord.Embed(
        title="📜 HRT — SERVER RULES",
        description=(
            "All members are expected to read and follow these rules at all times. "
            "Failure to comply may result in warnings, demotion, or removal from the server."
        ),
        color=discord.Color.blue()
    )
    embed.add_field(
        name="🔷 General Conduct",
        value=(
            "**1.** Treat all members with respect at all times.\n"
            "**2.** No racism, discrimination, harassment, or hate speech of any kind.\n"
            "**3.** No trolling, baiting, or intentional disruption.\n"
            "**4.** Keep conversations in their correct channels.\n"
            "**5.** No spamming, excessive caps, or flooding chat.\n"
            "**6.** No advertising other servers or services without permission.\n"
            "**7.** No sharing of internal server information outside the unit."
        ),
        inline=False
    )
    embed.add_field(
        name="👮 Staff & Chain of Command",
        value=(
            "**8.** Always follow instructions given by staff and superior officers.\n"
            "**9.** Do not impersonate staff or claim ranks you do not hold.\n"
            "**10.** Do not make false reports or accusations against members.\n"
            "**11.** All disputes must be handled through proper channels — do not argue publicly."
        ),
        inline=False
    )
    embed.add_field(
        name="🚔 In-Game Standards",
        value=(
            "**12.** Maintain professionalism during all operations and patrols.\n"
            "**13.** Follow your chain of command during operations and patrols.\n"
            "**14.** Do not act outside your assigned role or division without authorization.\n"
            "**15.** Combat logging, exploiting, or cheating is strictly prohibited."
        ),
        inline=False
    )
    embed.add_field(
        name="🎮 GTA CNR Rules",
        value=(
            "All members must also follow the **GTA Cops and Robbers** server rules:\n\n"
            "**1.** Do not RDM\n"
            "**2.** Do not team up with opposing roles\n"
            "**3.** Do not cheat\n"
            "**4.** Do not exploit\n"
            "**5.** Do not combat log\n"
            "**6.** Do not evade bans\n"
            "**7.** Do not slander or make false reports\n"
            "**8.** Do not impersonate staff\n"
            "**9.** Do not advertise\n"
            "**10.** Maintain proper behavior\n\n"
            "📖 Full CNR rules: https://gtacnr.net/rules"
        ),
        inline=False
    )
    embed.set_footer(text="HRT Administration • Violations will be handled by Command Staff")
    await interaction.channel.send(embed=embed)
    await interaction.response.send_message("✅ Rules embed sent.", ephemeral=True)


@bot.tree.command(name="info", description="Send server information embed", guild=GUILD)
async def setup_info(interaction: discord.Interaction):
    if not high_command_check(interaction.user):
        return await interaction.response.send_message("❌ No permission.", ephemeral=True)

    # Dynamically find the rules and applications channels
    rules_channel = discord.utils.get(interaction.guild.text_channels, name="📜│rules")
    apps_channel = discord.utils.get(interaction.guild.text_channels, name=APPLICATIONS_CHANNEL_NAME)
    rules_link = rules_channel.mention if rules_channel else "#rules"
    apps_link = apps_channel.mention if apps_channel else "#applications"

    embed = discord.Embed(
        title="🚔 HRT — SERVER INFORMATION",
        description=(
            "**HRT** is an elite tactical law enforcement unit operating on **GTA Cops and Robbers (CNR)**. "
            "We are a structured, discipline-driven unit built around professional operations "
            "and strong teamwork. "
            "Our mission is to uphold the law, protect civilians, and execute high-risk operations with precision."
        ),
        color=discord.Color.dark_blue()
    )
    embed.add_field(
        name="🎯 Our Mission",
        value=(
            "HRT responds to the most critical and high-risk situations on the CNR server. "
            "From coordinated raids to active pursuits, we operate as a unit — always professional, always disciplined."
        ),
        inline=False
    )
    embed.add_field(
        name="🏛️ Divisions",
        value=(
            "🚔 **Patrol Division** — Frontline law enforcement and active patrols\n"
            "🎓 **Training Academy** — Cadet training, evaluations, and rank progression\n"
            "📋 **Recruitment Division** — Applications, interviews, and onboarding\n"
            "🕵 **Internal Affairs** — Disciplinary oversight and investigations"
        ),
        inline=False
    )
    embed.add_field(
        name="✅ Requirements to Join",
        value=(
            "• Active GTA CNR player\n"
            "• Working microphone\n"
            "• Mature and professional behavior\n"
            "• Team-oriented mindset\n"
            "• Willingness to follow chain of command\n"
            "• Must follow all CNR and HRT rules"
        ),
        inline=False
    )
    embed.add_field(
        name="📥 How to Join",
        value=(
            f"1. Read the rules in {rules_link}\n"
            f"2. Head to {apps_link} and click **Apply Now**\n"
            "3. Answer all application questions\n"
            "4. Wait for a recruiter to review your application"
        ),
        inline=False
    )
    embed.set_footer(text="HRT • We Respond. We Protect. We Prevail.")
    await interaction.channel.send(embed=embed)
    await interaction.response.send_message("✅ Info embed sent.", ephemeral=True)



@bot.tree.command(name="application", description="Post the application embed with Apply Now button", guild=GUILD)
async def setup_application(interaction: discord.Interaction):
    if not high_command_check(interaction.user):
        return await interaction.response.send_message("❌ No permission.", ephemeral=True)

    embed = discord.Embed(
        title="📋 HRT — APPLICATIONS",
        description=(
            "Interested in joining **HRT**? Click the button below to open your application.\n\n"
            "**Requirements:**\n"
            "• Active GTA CNR player\n"
            "• Working microphone\n"
            "• Mature and professional behavior\n"
            "• Team-oriented mindset\n\n"
            "Once you apply, a private channel will be created for your application. "
            "A recruiter will review it and get back to you."
        ),
        color=discord.Color.gold()
    )
    embed.set_footer(text="HRT Recruitment Division • We Respond. We Protect. We Prevail.")

    await interaction.channel.send(embed=embed, view=ApplyButtonView())
    await interaction.response.send_message("✅ Application embed sent.", ephemeral=True)


@bot.tree.command(name="ranks", description="Post the live rank board (auto-updates on promotions)", guild=GUILD)
async def setup_ranks(interaction: discord.Interaction):
    if not high_command_check(interaction.user):
        return await interaction.response.send_message("❌ No permission.", ephemeral=True)

    embed = build_rank_embed(interaction.guild)
    msg = await interaction.channel.send(embed=embed)
    save_rank_message({"channel_id": str(interaction.channel.id), "message_id": str(msg.id)})
    await interaction.response.send_message("✅ Rank board posted. It will auto-update on any promotion or demotion.", ephemeral=True)


def build_recruitment_embed() -> discord.Embed:
    embed = discord.Embed(
        title="🚨 HRT RECRUITMENT 🚨",
        description=(
            "HRT is recruiting disciplined "
            "and active members for tactical operations."
        ),
        color=discord.Color.red()
    )
    embed.add_field(
        name="What We Offer",
        value=(
            "• Tactical Operations\n"
            "• Patrol Divisions\n"
            "• Trainings\n"
            "• Rank Progression\n"
            "• Competitive Gameplay"
        ),
        inline=False
    )
    embed.set_footer(text="We Respond. We Protect. We Prevail.")
    return embed


def load_recruitment_message() -> dict:
    try:
        with open(RECRUITMENT_MESSAGE_FILE, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_recruitment_message(data: dict):
    with open(RECRUITMENT_MESSAGE_FILE, "w") as f:
        json.dump(data, f)


@bot.event
async def on_message(message: discord.Message):

    global LAST_RECRUITMENT_POST

    if message.author.bot:
        return

    if not message.guild or message.guild.id != GUILD_ID:
        return

    if message.channel.name != GENERAL_CHAT_NAME:
        await bot.process_commands(message)
        return

    # Cooldown protection
    if time.time() - LAST_RECRUITMENT_POST < RECRUITMENT_COOLDOWN:
        await bot.process_commands(message)
        return

    data = load_recruitment_message()

    old_msg_id = data.get("message_id")

    if old_msg_id:
        try:
            old_msg = await message.channel.fetch_message(old_msg_id)
            await old_msg.delete()

        except (discord.NotFound, discord.Forbidden):
            pass

    new_msg = await message.channel.send(
        embed=build_recruitment_embed()
    )

    save_recruitment_message({
        "message_id": new_msg.id,
        "channel_id": message.channel.id
    })

    LAST_RECRUITMENT_POST = time.time()

    await bot.process_commands(message)


@bot.tree.command(name="hrt_news", description="Post a HRT news announcement", guild=GUILD)
@app_commands.describe(title="Title of the news post", news="The news content to announce")
async def hrt_news(interaction: discord.Interaction, title: str, news: str):
    if not high_command_check(interaction.user):
        return await interaction.response.send_message("❌ No permission.", ephemeral=True)

    embed = discord.Embed(
        title=f"📰 HRT NEWS — {title.upper()}",
        description=news,
        color=discord.Color.dark_blue()
    )
    embed.set_footer(text=f"Posted by {interaction.user.display_name} • HRT Command")
    await interaction.channel.send(embed=embed)
    await interaction.response.send_message("✅ News post sent.", ephemeral=True)


def load_disciplinary_log() -> dict:
    try:
        with open(DISCIPLINARY_LOG_FILE, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def save_disciplinary_log(data: dict):
    with open(DISCIPLINARY_LOG_FILE, "w") as f:
        json.dump(data, f)

def ia_check(user: discord.Member) -> bool:
    return high_command_check(user) or any(r.name == "🕵 Internal Affairs" for r in user.roles)


@bot.tree.command(name="investigation", description="Open a formal IA investigation report", guild=GUILD)
@app_commands.describe(
    subject="Officer being investigated",
    nature="Nature / type of the investigation",
    details="Summary of the incident and evidence gathered",
    status="Current status of the investigation",
    original_link="Message link to the original report (required for Ongoing or Closed)"
)
@app_commands.choices(status=[
    app_commands.Choice(name="Open", value="🟡 Open"),
    app_commands.Choice(name="Ongoing", value="🔵 Ongoing"),
    app_commands.Choice(name="Closed", value="🔴 Closed"),
])
async def investigation(
    interaction: discord.Interaction,
    subject: discord.Member,
    nature: str,
    details: str,
    status: app_commands.Choice[str],
    original_link: str = None
):
    if not ia_check(interaction.user):
        return await interaction.response.send_message("❌ No permission.", ephemeral=True)

    if status.value in ("🔵 Ongoing", "🔴 Closed") and not original_link:
        return await interaction.response.send_message(
            "❌ Please provide the message link to the original report when setting status to Ongoing or Closed.",
            ephemeral=True
        )

    embed = discord.Embed(
        title="🕵 INTERNAL AFFAIRS — INVESTIGATION REPORT",
        color=discord.Color.dark_gold()
    )
    embed.add_field(name="📋 Case Status", value=status.value, inline=True)
    embed.add_field(name="🗓 Date", value=f"<t:{int(__import__('datetime').datetime.utcnow().timestamp())}:D>", inline=True)
    embed.add_field(name="👤 Subject Officer", value=f"{subject.mention} (`{subject}`)", inline=False)
    embed.add_field(name="🔍 Nature of Investigation", value=nature, inline=False)
    embed.add_field(name="📁 Details & Evidence", value=details, inline=False)
    if original_link:
        embed.add_field(name="🔗 Original Report", value=f"[Jump to original report]({original_link})", inline=False)
    embed.add_field(name="🕵 Investigating Officer", value=f"{interaction.user.mention} (`{interaction.user}`)", inline=False)
    embed.set_footer(text="HRT Internal Affairs • Confidential")
    await interaction.channel.send(embed=embed)
    await interaction.response.send_message("✅ Investigation report posted.", ephemeral=True)


@bot.tree.command(name="officer_report", description="Submit a formal officer conduct report", guild=GUILD)
@app_commands.describe(
    subject="Officer being reported",
    incident="Description of the incident or behaviour",
    witnesses="Any witnesses present (names or 'None')",
    recommendation="Recommended course of action"
)
async def officer_report(
    interaction: discord.Interaction,
    subject: discord.Member,
    incident: str,
    witnesses: str,
    recommendation: str
):
    embed = discord.Embed(
        title="📄 INTERNAL AFFAIRS — OFFICER REPORT",
        color=discord.Color.orange()
    )
    embed.add_field(name="🗓 Date", value=f"<t:{int(__import__('datetime').datetime.utcnow().timestamp())}:D>", inline=True)
    embed.add_field(name="👤 Subject Officer", value=f"{subject.mention} (`{subject}`)", inline=False)
    embed.add_field(name="📋 Incident Description", value=incident, inline=False)
    embed.add_field(name="👁 Witnesses", value=witnesses, inline=False)
    embed.add_field(name="⚖️ Recommendation", value=recommendation, inline=False)
    embed.add_field(name="🕵 Reporting Officer", value=f"{interaction.user.mention} (`{interaction.user}`)", inline=False)
    embed.set_footer(text="HRT Internal Affairs • Confidential")

    reports_channel = discord.utils.find(
        lambda c: "officer-reports" in c.name.lower(), interaction.guild.text_channels
    )
    target = reports_channel or interaction.channel
    await target.send(embed=embed)

    reply = f"✅ Officer report submitted to {target.mention}." if reports_channel else "✅ Officer report posted."
    await interaction.response.send_message(reply, ephemeral=True)


@bot.tree.command(name="disciplinary_action", description="Issue a formal disciplinary action", guild=GUILD)
@app_commands.describe(
    subject="Officer receiving the disciplinary action",
    violation="Rule or conduct violation committed",
    action="Action being taken",
    notes="Any additional notes or conditions"
)
@app_commands.choices(action=[
    app_commands.Choice(name="Verbal Warning", value="🟡 Verbal Warning"),
    app_commands.Choice(name="Written Warning", value="🟠 Written Warning"),
    app_commands.Choice(name="Suspension", value="🔴 Suspension"),
    app_commands.Choice(name="Demotion", value="⬇️ Demotion"),
    app_commands.Choice(name="Termination", value="🚫 Termination"),
])
async def disciplinary_action(
    interaction: discord.Interaction,
    subject: discord.Member,
    violation: str,
    action: app_commands.Choice[str],
    notes: str = "None"
):
    if not ia_check(interaction.user):
        return await interaction.response.send_message("❌ No permission.", ephemeral=True)

    embed = discord.Embed(
        title="⚖️ INTERNAL AFFAIRS — DISCIPLINARY ACTION",
        color=discord.Color.red()
    )
    embed.add_field(name="🗓 Date Issued", value=f"<t:{int(__import__('datetime').datetime.utcnow().timestamp())}:D>", inline=True)
    embed.add_field(name="👤 Subject Officer", value=f"{subject.mention} (`{subject}`)", inline=False)
    embed.add_field(name="❌ Violation", value=violation, inline=False)
    embed.add_field(name="⚖️ Action Taken", value=action.value, inline=False)
    embed.add_field(name="📝 Notes", value=notes, inline=False)
    embed.add_field(name="🕵 Issued By", value=f"{interaction.user.mention} (`{interaction.user}`)", inline=False)
    embed.set_footer(text="HRT Internal Affairs • Confidential")
    await interaction.channel.send(embed=embed)

    try:
        dm_embed = discord.Embed(
            title="⚖️ Disciplinary Action Issued",
            description=(
                f"You have received a **disciplinary action** in **{interaction.guild.name}**.\n\n"
                f"**Action:** {action.value}\n"
                f"**Violation:** {violation}\n"
                f"**Notes:** {notes}\n\n"
                f"This action was issued by Internal Affairs. If you believe this is incorrect, "
                f"please open a High Command ticket."
            ),
            color=discord.Color.red()
        )
        dm_embed.set_footer(text="HRT Internal Affairs • Confidential")
        await subject.send(embed=dm_embed)
    except discord.Forbidden:
        pass

    import datetime
    log = load_disciplinary_log()
    uid = str(subject.id)
    if uid not in log:
        log[uid] = []
    log[uid].append({
        "action": action.value,
        "violation": violation,
        "notes": notes,
        "issued_by": str(interaction.user),
        "issued_by_id": str(interaction.user.id),
        "timestamp": int(datetime.datetime.utcnow().timestamp())
    })
    save_disciplinary_log(log)

    await interaction.response.send_message("✅ Disciplinary action posted and officer notified.", ephemeral=True)


@bot.tree.command(name="officer_conduct", description="View disciplinary history for an officer", guild=GUILD)
@app_commands.describe(member="Officer to look up")
async def officer_conduct(interaction: discord.Interaction, member: discord.Member):
    if not ia_check(interaction.user):
        return await interaction.response.send_message("❌ No permission.", ephemeral=True)

    log = load_disciplinary_log()
    records = log.get(str(member.id), [])

    embed = discord.Embed(
        title=f"📋 CONDUCT RECORD — {member.display_name}",
        description=f"Disciplinary history for {member.mention}",
        color=discord.Color.dark_red() if records else discord.Color.green()
    )

    active = [r for r in records if not r.get("removed")]

    if not records:
        embed.add_field(name="✅ Clean Record", value="No disciplinary actions on file.", inline=False)
    else:
        for i, r in enumerate(records, 1):
            if r.get("removed"):
                embed.add_field(
                    name=f"~~#{i} — {r['action']}~~ *(Removed)*",
                    value=(
                        f"**Violation:** {r['violation']}\n"
                        f"**Issued By:** <@{r['issued_by_id']}> • **Date:** <t:{r['timestamp']}:D>\n"
                        f"🗑 **Removed by:** <@{r['removed_by_id']}> on <t:{r['removed_at']}:D>"
                    ),
                    inline=False
                )
            else:
                embed.add_field(
                    name=f"#{i} — {r['action']}",
                    value=(
                        f"**Violation:** {r['violation']}\n"
                        f"**Notes:** {r['notes']}\n"
                        f"**Issued By:** <@{r['issued_by_id']}>\n"
                        f"**Date:** <t:{r['timestamp']}:D>"
                    ),
                    inline=False
                )

    embed.set_footer(text=f"Active: {len(active)} • Total: {len(records)} • HRT Internal Affairs")
    await interaction.response.send_message(embed=embed, ephemeral=True)



class RemoveConductSelect(discord.ui.Select):
    def __init__(self, member: discord.Member, records: list):
        self.member = member
        self.records = records
        options = []
        for i, r in enumerate(records):
            if r.get("removed"):
                continue
            label = f"#{i + 1} — {r['action'].split(' ', 1)[-1]}"[:100]
            description = r['violation'][:100]
            options.append(discord.SelectOption(label=label, description=description, value=str(i)))
        super().__init__(placeholder="Select a conduct record to remove...", options=options)

    async def callback(self, interaction: discord.Interaction):
        if not ia_check(interaction.user):
            return await interaction.response.send_message("❌ No permission.", ephemeral=True)
        import datetime
        index = int(self.values[0])
        log = load_disciplinary_log()
        uid = str(self.member.id)
        records = log.get(uid, [])
        if index >= len(records):
            return await interaction.response.send_message("❌ Record no longer exists.", ephemeral=True)
        records[index]["removed"] = True
        records[index]["removed_by"] = str(interaction.user)
        records[index]["removed_by_id"] = str(interaction.user.id)
        records[index]["removed_at"] = int(datetime.datetime.utcnow().timestamp())
        log[uid] = records
        save_disciplinary_log(log)
        await interaction.response.send_message(
            f"✅ Conduct entry **#{index + 1} — {records[index]['action']}** has been marked as removed by {interaction.user.mention}.",
            ephemeral=True
        )
        self.view.stop()


class RemoveConductView(discord.ui.View):
    def __init__(self, member: discord.Member, records: list):
        super().__init__(timeout=60)
        self.add_item(RemoveConductSelect(member, records))


@bot.tree.command(name="remove_conduct", description="Remove a disciplinary action from an officer's conduct record", guild=GUILD)
@app_commands.describe(member="Officer to remove a conduct entry from")
async def remove_conduct(interaction: discord.Interaction, member: discord.Member):
    if not ia_check(interaction.user):
        return await interaction.response.send_message("❌ No permission.", ephemeral=True)

    log = load_disciplinary_log()
    records = log.get(str(member.id), [])

    if not records:
        return await interaction.response.send_message(
            f"✅ {member.mention} has no conduct records on file.", ephemeral=True
        )

    view = RemoveConductView(member, records)
    await interaction.response.send_message(
        f"Select a conduct entry to remove from **{member.display_name}**'s record:",
        view=view,
        ephemeral=True
    )


@bot.tree.command(name="recruitment_log", description="Log a successful recruitment", guild=GUILD)
@app_commands.describe(
    recruit="The member who was recruited",
    notes="Any additional notes (optional)"
)
async def recruitment_log(
    interaction: discord.Interaction,
    recruit: discord.Member,
    notes: str = None
):
    if not recruiter_only_check(interaction.user):
        return await interaction.response.send_message("❌ No permission.", ephemeral=True)

    log_channel = discord.utils.get(interaction.guild.text_channels, name=RECRUITMENT_LOG_CHANNEL_NAME)
    if not log_channel:
        return await interaction.response.send_message(
            f"❌ Could not find `{RECRUITMENT_LOG_CHANNEL_NAME}`. Please create it first.",
            ephemeral=True
        )

    embed = discord.Embed(
        title="✅ RECRUITMENT LOG",
        color=discord.Color.brand_green()
    )
    embed.add_field(name="👤 Recruited Member", value=f"{recruit.mention} (`{recruit}`)", inline=False)
    embed.add_field(name="📋 Recruited By", value=f"{interaction.user.mention} (`{interaction.user}`)", inline=False)
    embed.add_field(name="🗓 Date", value=f"<t:{int(__import__('datetime').datetime.utcnow().timestamp())}:D>", inline=False)
    if notes:
        embed.add_field(name="📝 Notes", value=notes, inline=False)
    embed.set_footer(text="HRT Recruitment Division")

    await log_channel.send(embed=embed)
    await interaction.response.send_message(
        f"✅ Recruitment logged for {recruit.mention}.", ephemeral=True
    )


async def main():
    async with bot:
        await bot.start(TOKEN)

if __name__ == "__main__":
    asyncio.run(main())
