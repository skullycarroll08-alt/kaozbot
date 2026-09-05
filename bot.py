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

        # ADMINISTRATOR permission has access
        if interaction.user.guild_permissions.administrator:
            return True

        # Check for a role named ADMIN or JUSTKAOZ
        allowed_roles = {"ADMIN", "JUSTKAOZ"}

        return any(
            role.name.upper() in allowed_roles
            for role in interaction.user.roles
        )

    return app_commands.check(predicate)


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

    # Confirm privately
    await interaction.response.send_message(
        "✅ Message sent!",
        ephemeral=True
    )

    # Send the actual message
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
    # Clean up the hex code
    color = color.strip().replace("#", "")

    # Make sure it is exactly 6 characters
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
            f"✅ Created role **{role.name}** with color `#{color.upper()}**."
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
    print("ERROR: DISCORD_TOKEN environment variable is not set!")
else:
    bot.run(TOKEN)