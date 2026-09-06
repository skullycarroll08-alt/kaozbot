import discord
from discord import app_commands
from discord.ext import commands
import os
import json
from datetime import timedelta

# =========================
# BOT SETUP
# =========================

intents = discord.Intents.default()

bot = commands.Bot(
    command_prefix="!",
    intents=intents
)

# =========================
# FILES
# =========================

COUNTER_FILE = "ticket_counter.txt"
WARNINGS_FILE = "warnings.json"

# =========================
# STAFF ROLES
# =========================

STAFF_ROLES = {
    "JUSTKAOZ",
    "ADMIN",
    "MOD"
}

# =========================
# ADMIN+ CHECK
# =========================

def admin_or_higher():
    async def predicate(interaction: discord.Interaction):

        if not interaction.guild:
            return False

        # Server owner
        if interaction.user.id == interaction.guild.owner_id:
            return True

        # Discord Administrator
        if interaction.user.guild_permissions.administrator:
            return True

        # JUSTKAOZ / ADMIN
        allowed_roles = {
            "JUSTKAOZ",
            "ADMIN"
        }

        return any(
            role.name.upper() in allowed_roles
            for role in interaction.user.roles
        )

    return app_commands.check(predicate)


# =========================
# LOAD WARNINGS
# =========================

def load_warnings():

    try:
        with open(WARNINGS_FILE, "r") as file:
            return json.load(file)

    except (FileNotFoundError, json.JSONDecodeError):
        return {}


# =========================
# SAVE WARNINGS
# =========================

def save_warnings(data):

    with open(WARNINGS_FILE, "w") as file:
        json.dump(data, file, indent=4)


warnings_data = load_warnings()


# =========================
# TICKET COUNTER
# =========================

def get_next_ticket_number():

    try:
        with open(COUNTER_FILE, "r") as file:
            number = int(file.read().strip())

    except (FileNotFoundError, ValueError):
        number = 0

    number += 1

    with open(COUNTER_FILE, "w") as file:
        file.write(str(number))

    return number


# =========================
# BOT READY
# =========================

@bot.event
async def on_ready():

    try:

        synced = await bot.tree.sync()

        print(f"Logged in as {bot.user}")
        print(f"Synced {len(synced)} slash command(s)")

    except Exception as e:

        print(f"Failed to sync commands: {e}")


# =========================
# ROLE HIERARCHY CHECK
# =========================

def can_moderate(
    interaction: discord.Interaction,
    member: discord.Member
):

    if member.id == interaction.user.id:
        return False

    if member.id == interaction.guild.owner_id:
        return False

    if member.top_role >= interaction.user.top_role:
        return False

    if member.top_role >= interaction.guild.me.top_role:
        return False

    return True


# =========================
# /say
# =========================

@bot.tree.command(
    name="say",
    description="Make the bot send a message"
)
@app_commands.describe(
    message="The message you want the bot to send"
)
@admin_or_higher()
async def say(
    interaction: discord.Interaction,
    message: str
):

    message = message.replace("/n", "\n")

    await interaction.response.send_message(
        "✅ Message sent!",
        ephemeral=True
    )

    await interaction.channel.send(message)


# =========================
# /createrole
# =========================

@bot.tree.command(
    name="createrole",
    description="Create a role with a custom hex color"
)
@app_commands.describe(
    name="The name of the role",
    color="The role color in hex format, e.g. #ff0000"
)
@admin_or_higher()
async def createrole(
    interaction: discord.Interaction,
    name: str,
    color: str
):

    color = color.strip().replace("#", "")

    if len(color) != 6:

        await interaction.response.send_message(
            "❌ Invalid hex color. Use something like `#ff0000`.",
            ephemeral=True
        )

        return

    try:
        color_value = int(color, 16)

    except ValueError:

        await interaction.response.send_message(
            "❌ Invalid hex color. Use something like `#ff0000`.",
            ephemeral=True
        )

        return

    try:

        role = await interaction.guild.create_role(
            name=name,
            color=discord.Color(color_value),
            reason=f"Created by {interaction.user}"
        )

        await interaction.response.send_message(
            f"✅ Created role **{role.name}** with color `#{color.upper()}`."
        )

    except discord.Forbidden:

        await interaction.response.send_message(
            "❌ I don't have permission to create roles.",
            ephemeral=True
        )

    except discord.HTTPException as e:

        await interaction.response.send_message(
            f"❌ Discord returned an error: `{e}`",
            ephemeral=True
        )


# =========================
# INFORMATION CATEGORY
# =========================

def get_information_category(guild):

    category = discord.utils.get(
        guild.categories,
        name="📢 INFORMATION"
    )

    if category is None:

        category = discord.utils.get(
            guild.categories,
            name="INFORMATION"
        )

    return category


# =========================
# STAFF PERMISSIONS
# =========================

def get_staff_overwrites(guild):

    overwrites = {}

    overwrites[guild.default_role] = discord.PermissionOverwrite(
        view_channel=False
    )

    for role in guild.roles:

        if role.name.upper() in STAFF_ROLES:

            overwrites[role] = discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                manage_messages=True
            )

    return overwrites


# =========================
# CREATE TICKET BUTTON
# =========================

class TicketView(discord.ui.View):

    def __init__(self):

        super().__init__(timeout=None)

    @discord.ui.button(
        label="🎫 Create Ticket",
        style=discord.ButtonStyle.green,
        custom_id="create_ticket"
    )
    async def create_ticket(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        guild = interaction.guild
        user = interaction.user

        # Check existing ticket
        existing_ticket = discord.utils.find(
            lambda channel:
                channel.name.startswith("ticket-")
                and channel.topic == f"Ticket owner: {user.id}",
            guild.text_channels
        )

        if existing_ticket:

            await interaction.response.send_message(
                f"❌ You already have a ticket: {existing_ticket.mention}",
                ephemeral=True
            )

            return

        category = get_information_category(guild)

        if category is None:

            await interaction.response.send_message(
                "❌ I couldn't find the **📢 INFORMATION** category.",
                ephemeral=True
            )

            return

        overwrites = get_staff_overwrites(guild)

        overwrites[user] = discord.PermissionOverwrite(
            view_channel=True,
            send_messages=True,
            read_message_history=True
        )

        ticket_number = get_next_ticket_number()

        ticket_name = f"ticket-{ticket_number:03d}"

        try:

            channel = await guild.create_text_channel(
                name=ticket_name,
                category=category,
                overwrites=overwrites,
                topic=f"Ticket owner: {user.id}",
                reason=f"Ticket #{ticket_number} created by {user}"
            )

            embed = discord.Embed(
                title=f"🎫 Ticket #{ticket_number:03d}",
                description=(
                    f"Welcome {user.mention}!\n\n"
                    "Please explain what you need help with.\n"
                    "A staff member will assist you soon."
                ),
                color=discord.Color.blurple()
            )

            embed.set_footer(
                text="Kaoz's Chaos"
            )

            await channel.send(
                content=user.mention,
                embed=embed,
                view=CloseTicketView()
            )

            await interaction.response.send_message(
                f"✅ Your ticket has been created: {channel.mention}",
                ephemeral=True
            )

        except discord.Forbidden:

            await interaction.response.send_message(
                "❌ I don't have permission to create the ticket.",
                ephemeral=True
            )


# =========================
# CLOSE TICKET
# =========================

class CloseTicketView(discord.ui.View):

    def __init__(self):

        super().__init__(timeout=None)

    @discord.ui.button(
        label="🔒 Close Ticket",
        style=discord.ButtonStyle.red,
        custom_id="close_ticket"
    )
    async def close_ticket(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        channel = interaction.channel
        user = interaction.user

        if not channel.name.startswith("ticket-"):

            await interaction.response.send_message(
                "❌ This isn't a ticket channel.",
                ephemeral=True
            )

            return

        is_staff = (
            user.guild_permissions.administrator
            or any(
                role.name.upper() in STAFF_ROLES
                for role in user.roles
            )
        )

        ticket_owner = None

        if channel.topic and channel.topic.startswith("Ticket owner: "):

            try:

                user_id = int(
                    channel.topic.replace(
                        "Ticket owner: ",
                        ""
                    )
                )

                ticket_owner = channel.guild.get_member(user_id)

            except ValueError:
                pass

        if not is_staff and user != ticket_owner:

            await interaction.response.send_message(
                "❌ You don't have permission to close this ticket.",
                ephemeral=True
            )

            return

        await interaction.response.send_message(
            "🔒 Closing ticket...",
            ephemeral=True
        )

        await channel.delete(
            reason=f"Ticket closed by {user}"
        )


# =========================
# /ticket
# =========================

@bot.tree.command(
    name="ticket",
    description="Create the ticket panel"
)
@admin_or_higher()
async def ticket(
    interaction: discord.Interaction
):

    embed = discord.Embed(
        title="🎫 Need Help?",
        description=(
            "Click the button below to create a private support ticket.\n\n"
            "A ticket will be created inside **📢 INFORMATION**."
        ),
        color=discord.Color.blurple()
    )

    embed.set_footer(
        text="Kaoz's Chaos"
    )

    await interaction.response.send_message(
        "✅ Ticket panel sent!",
        ephemeral=True
    )

    await interaction.channel.send(
        embed=embed,
        view=TicketView()
    )


# =========================
# /WARN
# =========================

@bot.tree.command(
    name="warn",
    description="Warn a member"
)
@app_commands.describe(
    member="The member to warn",
    reason="The reason for the warning"
)
@admin_or_higher()
async def warn(
    interaction: discord.Interaction,
    member: discord.Member,
    reason: str
):

    if not can_moderate(interaction, member):

        await interaction.response.send_message(
            "❌ You cannot warn this member because of role hierarchy.",
            ephemeral=True
        )

        return

    guild_id = str(interaction.guild.id)
    user_id = str(member.id)

    if guild_id not in warnings_data:
        warnings_data[guild_id] = {}

    if user_id not in warnings_data[guild_id]:
        warnings_data[guild_id][user_id] = []

    warnings_data[guild_id][user_id].append({
        "reason": reason,
        "moderator": interaction.user.id
    })

    save_warnings(warnings_data)

    warning_count = len(
        warnings_data[guild_id][user_id]
    )

    # 3 warnings = 12 hour timeout
    if warning_count >= 3:

        try:

            await member.timeout(
                timedelta(hours=12),
                reason="Reached 3 warnings"
            )

            warnings_data[guild_id][user_id] = []

            save_warnings(warnings_data)

            await interaction.response.send_message(
                f"⚠️ {member.mention} received warning **#{warning_count}**.\n"
                f"🚨 They reached 3 warnings and were automatically "
                f"timed out for **12 hours**.\n"
                f"🔄 Their warnings have been reset."
            )

        except discord.Forbidden:

            await interaction.response.send_message(
                f"⚠️ {member.mention} received warning #{warning_count}, "
                "but I couldn't apply the 12-hour timeout.",
                ephemeral=True
            )

        return

    await interaction.response.send_message(
        f"⚠️ {member.mention} has been warned.\n"
        f"**Warnings:** {warning_count}/3\n"
        f"**Reason:** {reason}"
    )


# =========================
# /UNWARN
# =========================

@bot.tree.command(
    name="unwarn",
    description="Remove one warning from a member"
)
@app_commands.describe(
    member="The member to remove a warning from"
)
@admin_or_higher()
async def unwarn(
    interaction: discord.Interaction,
    member: discord.Member
):

    guild_id = str(interaction.guild.id)
    user_id = str(member.id)

    if (
        guild_id not in warnings_data
        or user_id not in warnings_data[guild_id]
        or len(warnings_data[guild_id][user_id]) == 0
    ):

        await interaction.response.send_message(
            f"❌ {member.mention} has no warnings.",
            ephemeral=True
        )

        return

    # Remove one warning
    warnings_data[guild_id][user_id].pop()

    # Clean empty data
    if len(warnings_data[guild_id][user_id]) == 0:
        del warnings_data[guild_id][user_id]

    save_warnings(warnings_data)

    remaining = len(
        warnings_data.get(guild_id, {}).get(user_id, [])
    )

    await interaction.response.send_message(
        f"✅ Removed one warning from {member.mention}.\n"
        f"**Warnings remaining:** {remaining}/3"
    )


# =========================
# /WARNINGS
# =========================

@bot.tree.command(
    name="warnings",
    description="View a member's warnings"
)
@app_commands.describe(
    member="The member to check"
)
@admin_or_higher()
async def warnings(
    interaction: discord.Interaction,
    member: discord.Member
):

    guild_id = str(interaction.guild.id)
    user_id = str(member.id)

    user_warnings = warnings_data.get(
        guild_id,
        {}
    ).get(
        user_id,
        []
    )

    if not user_warnings:

        await interaction.response.send_message(
            f"✅ **{member.display_name}** has no warnings."
        )

        return

    embed = discord.Embed(
        title=f"⚠️ Warnings for {member.display_name}",
        description=f"**Total:** {len(user_warnings)}/3",
        color=discord.Color.orange()
    )

    for index, warning in enumerate(user_warnings, start=1):

        moderator = interaction.guild.get_member(
            warning.get("moderator")
        )

        moderator_name = (
            moderator.display_name
            if moderator
            else "Unknown"
        )

        embed.add_field(
            name=f"Warning #{index}",
            value=(
                f"**Reason:** {warning.get('reason', 'No reason')}\n"
                f"**Moderator:** {moderator_name}"
            ),
            inline=False
        )

    await interaction.response.send_message(
        embed=embed
    )


# =========================
# /TIMEOUT
# =========================

@bot.tree.command(
    name="timeout",
    description="Timeout a member"
)
@app_commands.describe(
    member="The member to timeout",
    duration="Duration in minutes",
    reason="Reason for the timeout"
)
@admin_or_higher()
async def timeout(
    interaction: discord.Interaction,
    member: discord.Member,
    duration: int,
    reason: str = "No reason provided"
):

    if duration < 1 or duration > 40320:

        await interaction.response.send_message(
            "❌ Duration must be between 1 and 40320 minutes.",
            ephemeral=True
        )

        return

    if not can_moderate(interaction, member):

        await interaction.response.send_message(
            "❌ You cannot timeout this member because of role hierarchy.",
            ephemeral=True
        )

        return

    try:

        await member.timeout(
            timedelta(minutes=duration),
            reason=reason
        )

        await interaction.response.send_message(
            f"🔇 {member.mention} has been timed out for "
            f"**{duration} minutes**.\n"
            f"**Reason:** {reason}"
        )

    except discord.Forbidden:

        await interaction.response.send_message(
            "❌ I don't have permission to timeout this member.",
            ephemeral=True
        )


# =========================
# /UNTIMEOUT
# =========================

@bot.tree.command(
    name="untimeout",
    description="Remove a timeout from a member"
)
@app_commands.describe(
    member="The member to untimeout"
)
@admin_or_higher()
async def untimeout(
    interaction: discord.Interaction,
    member: discord.Member
):

    if not can_moderate(interaction, member):

        await interaction.response.send_message(
            "❌ You cannot untimeout this member because of role hierarchy.",
            ephemeral=True
        )

        return

    try:

        await member.timeout(
            None,
            reason=f"Timeout removed by {interaction.user}"
        )

        await interaction.response.send_message(
            f"🔊 {member.mention} is no longer timed out."
        )

    except discord.Forbidden:

        await interaction.response.send_message(
            "❌ I don't have permission to remove this timeout.",
            ephemeral=True
        )


# =========================
# /KICK
# =========================

@bot.tree.command(
    name="kick",
    description="Kick a member"
)
@app_commands.describe(
    member="The member to kick",
    reason="Reason for the kick"
)
@admin_or_higher()
async def kick(
    interaction: discord.Interaction,
    member: discord.Member,
    reason: str = "No reason provided"
):

    if not can_moderate(interaction, member):

        await interaction.response.send_message(
            "❌ You cannot kick this member because of role hierarchy.",
            ephemeral=True
        )

        return

    try:

        await member.kick(
            reason=reason
        )

        await interaction.response.send_message(
            f"👢 {member.mention} has been kicked.\n"
            f"**Reason:** {reason}"
        )

    except discord.Forbidden:

        await interaction.response.send_message(
            "❌ I don't have permission to kick this member.",
            ephemeral=True
        )


# =========================
# /BAN
# =========================

@bot.tree.command(
    name="ban",
    description="Ban a member"
)
@app_commands.describe(
    member="The member to ban",
    reason="Reason for the ban"
)
@admin_or_higher()
async def ban(
    interaction: discord.Interaction,
    member: discord.Member,
    reason: str = "No reason provided"
):

    if not can_moderate(interaction, member):

        await interaction.response.send_message(
            "❌ You cannot ban this member because of role hierarchy.",
            ephemeral=True
        )

        return

    try:

        await member.ban(
            reason=reason
        )

        await interaction.response.send_message(
            f"🔨 {member.mention} has been banned.\n"
            f"**Reason:** {reason}"
        )

    except discord.Forbidden:

        await interaction.response.send_message(
            "❌ I don't have permission to ban this member.",
            ephemeral=True
        )

# =========================
# /CLEAR
# =========================

@bot.tree.command(
    name="clear",
    description="Delete a member's messages from the last X hours"
)
@app_commands.describe(
    member="The member whose messages should be deleted",
    time="How many hours back to search"
)
@admin_or_higher()
async def clear(
    interaction: discord.Interaction,
    member: discord.Member,
    time: int
):

    if time < 1 or time > 336:
        await interaction.response.send_message(
            "❌ Time must be between 1 and 336 hours (14 days).",
            ephemeral=True
        )
        return

    # Tell Discord we're processing
    await interaction.response.defer(ephemeral=True)

    # Calculate how far back to search
    cutoff = discord.utils.utcnow() - timedelta(hours=time)

    deleted_messages = []

    try:
        async for message in interaction.channel.history(
            after=cutoff,
            oldest_first=False
        ):
            if message.author.id == member.id:
                deleted_messages.append(message)

        # Delete messages individually so we only remove
        # messages from the selected member
        for message in deleted_messages:
            try:
                await message.delete()
            except discord.NotFound:
                pass
            except discord.Forbidden:
                await interaction.followup.send(
                    "❌ I don't have permission to delete messages.",
                    ephemeral=True
                )
                return

        await interaction.followup.send(
            f"🧹 Deleted **{len(deleted_messages)}** message(s) "
            f"from {member.mention} in the last **{time} hour(s)**.",
            ephemeral=True
        )

    except discord.Forbidden:
        await interaction.followup.send(
            "❌ I don't have permission to read/delete messages "
            "in this channel.",
            ephemeral=True
        )

    except discord.HTTPException as e:
        await interaction.followup.send(
            f"❌ Discord returned an error: `{e}`",
            ephemeral=True
        )

# =========================
# /LOCK
# =========================

@bot.tree.command(
    name="lock",
    description="Lock the current channel so only JUSTKAOZ can talk"
)
@admin_or_higher()
async def lock(
    interaction: discord.Interaction
):

    guild = interaction.guild
    channel = interaction.channel

    # Only JUSTKAOZ can use /lock
    is_justkaoz = any(
        role.name.upper() == "JUSTKAOZ"
        for role in interaction.user.roles
    )

    # Server owner also counts as JUSTKAOZ
    if interaction.user.id == guild.owner_id:
        is_justkaoz = True

    if not is_justkaoz:
        await interaction.response.send_message(
            "❌ Only **JUSTKAOZ** can lock channels.",
            ephemeral=True
        )
        return

    # Find JUSTKAOZ role
    justkaoz_role = discord.utils.find(
        lambda role: role.name.upper() == "JUSTKAOZ",
        guild.roles
    )

    if justkaoz_role is None:
        await interaction.response.send_message(
            "❌ I couldn't find the **JUSTKAOZ** role.",
            ephemeral=True
        )
        return

    try:

        # Everyone can still see the channel but cannot talk
        await channel.set_permissions(
            guild.default_role,
            send_messages=False
        )

        # JUSTKAOZ can still talk
        await channel.set_permissions(
            justkaoz_role,
            send_messages=True
        )

        await interaction.response.send_message(
            "🔒 **Channel locked!**\n"
            "Everyone can still see this channel, but only "
            "**JUSTKAOZ** can talk."
        )

    except discord.Forbidden:

        await interaction.response.send_message(
            "❌ I don't have permission to change this channel's permissions.",
            ephemeral=True
        )

    except discord.HTTPException as e:

        await interaction.response.send_message(
            f"❌ Discord returned an error: `{e}`",
            ephemeral=True
        )


# =========================
# ERROR HANDLER
# =========================

@bot.tree.error
async def on_app_command_error(
    interaction: discord.Interaction,
    error: app_commands.AppCommandError
):

    if isinstance(error, app_commands.CheckFailure):

        if not interaction.response.is_done():

            await interaction.response.send_message(
                "❌ Only **ADMIN** or **JUSTKAOZ** can use bot commands.",
                ephemeral=True
            )

        return

    print(f"Command error: {error}")

    if not interaction.response.is_done():

        await interaction.response.send_message(
            "❌ Something went wrong while running the command.",
            ephemeral=True
        )


# =========================
# RUN BOT
# =========================

TOKEN = os.getenv("DISCORD_TOKEN")

if not TOKEN:

    print(
        "ERROR: DISCORD_TOKEN environment variable is not set!"
    )

else:

    bot.run(TOKEN)
