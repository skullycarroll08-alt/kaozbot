import discord
from discord import app_commands
from discord.ext import commands
import os

# =========================
# BOT SETUP
# =========================

intents = discord.Intents.default()

bot = commands.Bot(
    command_prefix="!",
    intents=intents
)


# =========================
# ADMIN+ ONLY CHECK
# =========================

def admin_or_higher():
    async def predicate(interaction: discord.Interaction):

        # Server owner always has access
        if interaction.guild and interaction.user.id == interaction.guild.owner_id:
            return True

        # Discord Administrator permission
        if interaction.user.guild_permissions.administrator:
            return True

        # JUSTKAOZ and ADMIN roles
        allowed_roles = {"JUSTKAOZ", "ADMIN"}

        return any(
            role.name.upper() in allowed_roles
            for role in interaction.user.roles
        )

    return app_commands.check(predicate)


# =========================
# STAFF ROLES
# =========================

STAFF_ROLES = {
    "JUSTKAOZ",
    "ADMIN",
    "MOD"
}


# =========================
# TICKET COUNTER
# =========================

COUNTER_FILE = "ticket_counter.txt"


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

    # Turn /n into actual line breaks
    message = message.replace("/n", "\n")

    # Only command user sees this
    await interaction.response.send_message(
        "✅ Message sent!",
        ephemeral=True
    )

    # Send actual message
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
# FIND INFORMATION CATEGORY
# =========================

def get_information_category(guild: discord.Guild):

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
# FIND STAFF ROLES
# =========================

def get_staff_overwrites(guild: discord.Guild):

    overwrites = {}

    # Hide ticket from everyone
    overwrites[guild.default_role] = discord.PermissionOverwrite(
        view_channel=False
    )

    # Give staff access
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
# TICKET PANEL
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

        # Check if user already has a ticket
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

        # Find INFORMATION category
        category = get_information_category(guild)

        if category is None:

            await interaction.response.send_message(
                "❌ I couldn't find the **📢 INFORMATION** category.",
                ephemeral=True
            )

            return

        # Get staff permissions
        overwrites = get_staff_overwrites(guild)

        # Give ticket creator access
        overwrites[user] = discord.PermissionOverwrite(
            view_channel=True,
            send_messages=True,
            read_message_history=True
        )

        # Get next ticket number
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

        except discord.HTTPException as e:

            await interaction.response.send_message(
                f"❌ Discord returned an error: `{e}`",
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

        # Check if ticket
        if not channel.name.startswith("ticket-"):

            await interaction.response.send_message(
                "❌ This isn't a ticket channel.",
                ephemeral=True
            )

            return

        # Check staff
        is_staff = (
            user.guild_permissions.administrator
            or any(
                role.name.upper() in STAFF_ROLES
                for role in user.roles
            )
        )

        # Find ticket owner
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

        # Owner or staff can close
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

    # Only command user sees this
    await interaction.response.send_message(
        "✅ Ticket panel sent!",
        ephemeral=True
    )

    # Everyone sees the panel
    await interaction.channel.send(
        embed=embed,
        view=TicketView()
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
