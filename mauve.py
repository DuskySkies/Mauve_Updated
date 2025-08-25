import discord
from discord.ext import commands
from dotenv import load_dotenv
import asyncio
import logging
import os
import re

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

intents = discord.Intents.default()
intents.members = True
intents.message_content = True

description = '''You probably shouldn't use this if you don't know what it does.
I do a lot of things, but I was made by Sadie (StylisticallyCatgirl)'''

bot = commands.Bot(command_prefix='m;', description=description, intents=intents)

# Mappings for roles

# Role mapping (legacy -> (new_pronoun, new_color))
role_mappings = {
    ".Ask": ("Ask", "Slate"),
    ".Name is pronoun": ("Name is pronoun", "Teal"),
    ".Any Pronouns": ("Any Pronouns", "Peach"),
    ".It/It/Its": ("It/Its/Its", "Slate"),
    ".Fae/Faer/Faers": ("Fae/Faer/Faers", "Helio"),
    ".Ae/Aer": ("Ae/Aer", "Raspberry"),
    ".They/Them/Theirs": ("They/Them/Theirs", "Electric Purple"),
    ".He/Him/His": ("He/Him/His", "Sapphire"),
    ".She/Her/Hers": ("She/Her/Hers", "Bubblegum"),
    ".Not She/Her/Hers": ("Not She/Her/Hers", "Peach"),
    ".Not He/Him/His": ("Not He/Him/His", "Orange"),
}
# Priorities for color roles (Top --> Bottom)
legacy_role_priority = [
    ".Ask",
    ".Name is pronoun",
    ".Any Pronouns",
    ".It/It/Its",
    ".Fae/Faer/Faers",
    ".Ae/Aer",
    ".They/Them/Theirs",
    ".He/Him/His",
    ".She/Her/Hers",
    ".Not She/Her/Hers",
    ".Not He/Him/His",
]


# Stuff to do on boot
@bot.event
# Log in, then set status
async def on_ready():
    print(f'Logged in as {bot.user} (ID: {bot.user.id})')
    await bot.change_presence(activity=discord.Game(name="Lavender is such a pretty color"))
# Check to see if a role named MauvePermissions is present, if not, make it
    role_name = "MauvePermissions"
    for guild in bot.guilds:
        role = discord.utils.get(guild.roles, name=role_name)
        if not role:
            try:
                await guild.create_role(name=role_name, reason="Required to operate Mauve")
                print(f"Created role `{role_name}` in `{guild.name}`")
            except discord.Forbidden:
                print(f"Missing permissions to create role in `{guild.name}`")

# Handle missing permissions

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.MissingRole):
        await ctx.send("You lack the `MauvePermissions` role, which is necessary for all functions of Mauve.")

# Command to check network latency

@bot.command()
#Ensures only users with the manually assigned MauvePermissions command can run this command
@commands.has_role("MauvePermissions")
async def ping(ctx):
    await ctx.send(f'Pong! {round(bot.latency * 1000)}ms')

#role update command

@bot.command(name="update_roles")
@commands.has_role("MauvePermissions")
async def update_roles(ctx, mode: str = None):
    """Updates legacy roles to pronoun and color roles. Requires --dry-run or --execute."""
    guild = ctx.guild
    channel = ctx.channel
# handles instances when user doesn't specify what mode to run the command in
    if mode not in ["--dry-run", "--execute"]:
        await channel.send("Please specify a mode: --dry-run to simulated changes, and --execute to make them")
        return
# sends message in channel once command is run
    dry_run = mode == "--dry-run"
    await channel.send(f"{'Dry-running' if dry_run else 'Executing'} role update for guild: {guild.name}...")

# Validate mappings and existing roles
    missing_roles = set()
    for legacy_role, (pronoun_role, color_role) in role_mappings.items():
        if discord.utils.get(guild.roles, name=legacy_role) is None:
            missing_roles.add(legacy_role)
        if discord.utils.get(guild.roles, name=pronoun_role) is None:
            missing_roles.add(pronoun_role)
        if discord.utils.get(guild.roles, name=color_role) is None:
            missing_roles.add(color_role)
# If roles are missing, aborts and sends message in channel
    if missing_roles:
        await channel.send(f"Missing roles: {', '.join(missing_roles)}.")
        return

    legacy_roles_set = set(role_mappings.keys())
# If member is a bot, skip
    for member in guild.members:
        if member.bot:
            continue
# if member doesn't have one of the legacy roles, skip
        legacy_roles = [role for role in member.roles if role.name in legacy_roles_set]
        if not legacy_roles:
            continue
# Sorting logic
        legacy_roles_sorted = sorted(legacy_roles, key=lambda r: legacy_role_priority.index(r.name))
        top_legacy = legacy_roles_sorted[0].name

        pronoun_roles_to_add = []
        color_role_to_add = None

        for legacy_role in legacy_roles:
            pronoun, _ = role_mappings[legacy_role.name]
            pronoun_role_obj = discord.utils.get(guild.roles, name=pronoun)
            if pronoun_role_obj:
                pronoun_roles_to_add.append(pronoun_role_obj)

        _, color_role = role_mappings[top_legacy]
        color_role_obj = discord.utils.get(guild.roles, name=color_role)

        roles_to_remove = legacy_roles
        roles_to_add = pronoun_roles_to_add
        if color_role_obj:
            roles_to_add.append(color_role_obj)
# If dry run then display potential changes then stop
        if dry_run:
            status = f"[Dry run] Would update {member.mention}: remove {[r.name for r in roles_to_remove]}, add {[r.name for r in roles_to_add]}"
        else:
            try:
# Does role changes then sends a messaage in chat
                await member.remove_roles(*roles_to_remove, reason="Mauve pronoun migration")
                await member.add_roles(*roles_to_add, reason="Mauve pronoun migration")
                status = f"Updated {member.mention}: removed {[r.name for r in roles_to_remove]}, added {[r.name for r in roles_to_add]}"
# If something weird happens, then send it in chat and move to next member
            except Exception as e:
                status = f"❌ Error updating {member.mention}: {str(e)}"

        await channel.send(status)
# Delay to hopefully avoid ratelimits encountered in testing
        await asyncio.sleep(0.5)

    await channel.send("Role update completed.")

# Makes sure that every role that is expected to be present is actually present

@bot.command()
@commands.has_role("MauvePermissions")
async def check(ctx):
    guild = ctx.guild
    found_all = True
    missing_messages = []
# Looks to see if any of the roles in the role_mappings array are missing
    for legacy, (pronoun, color) in role_mappings.items():
        missing = []
        for role_name in [legacy, pronoun, color]:
            if not discord.utils.get(guild.roles, name=role_name):
                missing.append(role_name)
# If missing, then send a embed in the channel with the missing roles
        if missing:
            found_all = False
            embed = discord.Embed(
                title="I can't find these roles!",
                description="\n".join(f"❌ {r}" for r in missing),
                color=discord.Color.purple()
            )
            embed.set_footer(text="Mapping: Legacy → Pronoun, Color")
            embed.add_field(name="Legacy Role", value=legacy, inline=True)
            embed.add_field(name="Pronoun Role", value=pronoun, inline=True)
            embed.add_field(name="Color Role", value=color, inline=True)
            missing_messages.append(embed)
# If nothing is missing, then say so
    if found_all:
        await ctx.send("All expected roles are present!")
    else:
        for embed in missing_messages:
            await ctx.send(embed=embed)



# Counts how many users have a legacy role

@bot.command(name="count")
@commands.has_role("MauvePermissions")
async def count_legacy(ctx):
# Scans member list to check how many pepole have a role in the legacy_role array
    guild = ctx.guild
    legacy_role_names = set(role_mappings.keys())
    legacy_roles = [role for role in guild.roles if role.name in legacy_role_names]
    legacy_member_count = 0
# If one is present, then increment the legacy_member_count by +1
    for member in guild.members:
        if any(role in legacy_roles for role in member.roles):
            legacy_member_count += 1

    await ctx.send(f"{legacy_member_count} users have a legacy role.")


# Run the bot
bot.run(TOKEN, log_handler=handler)
