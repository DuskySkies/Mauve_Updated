import discord
from discord.ext import commands
import asyncio
import logging
from logging.handlers import RotatingFileHandler
import os
import sys

# Discord intents (check dev portal to make sure all are enabled)
intents = discord.Intents.default()
intents.guilds = True
intents.members = True
intents.message_content = True
intents.guild_messages = True

description = '''You probably shouldn't use this if you don't know what it does.
I do a lot of things, but I was made by Sadie (StylisticallyCatgirl)'''

bot = commands.Bot(command_prefix='m;', description=description, intents=intents)

# variable for initial roleback data being saved in memory
rollback_data = {}

# Logging Setup per guild to ensure any testing on
# external servers doesn't obfuscate anything
def get_guild_logger(guild_id: int) -> logging.Logger:
    # Saves locally to mauve/logs/
    log_dir = "logs"
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, f"{guild_id}.log")
    # settings for the logging
    logger = logging.getLogger(f"guild_{guild_id}")
    if not logger.handlers:
        handler = RotatingFileHandler(
            filename=log_path,
            mode="a",
            maxBytes=5*1024*1024,  # 5MB per file
            backupCount=5,
            encoding="utf-8",
            delay=0
        )
        formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
        handler.setFormatter(formatter)

        logger.setLevel(logging.INFO)
        logger.addHandler(handler)

        console = logging.StreamHandler(sys.stdout)
        console.setFormatter(formatter)
        logger.addHandler(console)

    return logger

# Role mappings for replacement
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

# Priority for replacement
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

# Stuff to run on bot start
# Print some basic stuff to console, set up the logger and set presence
@bot.event
async def on_ready():
    for guild in bot.guilds:
        logger = get_guild_logger(guild.id)
        logger.info(f"Logged in as {bot.user} (ID: {bot.user.id}) in guild '{guild.name}'")
        await bot.change_presence(activity=discord.Game(name="Lavender is such a pretty color"))

        # Ensure MauvePermissions role exists
        role_name = "MauvePermissions"
        role = discord.utils.get(guild.roles, name=role_name)
        # If not, create it
        if not role:
            try:
                await guild.create_role(name=role_name, reason="Required to operate Mauve")
                logger.info(f"Created role `{role_name}` in `{guild.name}`")
            except discord.Forbidden:
                logger.error(f"Missing permissions to create role `{role_name}` in `{guild.name}`")

# Logs who runs commands
@bot.before_invoke
async def log_command(ctx):
    logger = get_guild_logger(ctx.guild.id)
    logger.info(f"COMMAND: {ctx.author} ran '{ctx.command}'")

# Handles what happens if an error gets kicked back
# Also handles what happens if someone without perms runs a command
@bot.event
async def on_command_error(ctx, error):
    logger = get_guild_logger(ctx.guild.id)
    logger.error(f"ERROR in command '{ctx.command}': {repr(error)}")
    if isinstance(error, commands.MissingRole):
        await ctx.send("You lack the `MauvePermissions` role, which is necessary for all functions of Mauve.")

# Check latency
@bot.command()
@commands.has_role("MauvePermissions")
async def ping(ctx):
    # Rounds latency to miliseconds
    latency_ms = round(bot.latency * 1000)
    await ctx.send(f'Pong! {latency_ms}ms')

# Update roles command
@bot.command(name="update_roles")
# Ensure user has the proper role to run command
@commands.has_role("MauvePermissions")
async def update_roles(ctx, mode: str = None):
    guild = ctx.guild
    logger = get_guild_logger(guild.id)
    channel = ctx.channel
    # Checks to see if user wants to see a dry run or execute the real thing
    # Handles errors if the user doesn't have a mode selected
    if mode not in ["--dry-run", "--execute"]:
        await channel.send("Please specify a mode: --dry-run to simulate changes, and --execute to make them")
        logger.warning(f"Invalid mode specified for update_roles by {ctx.author}")
        return
    # handles dry run
    dry_run = mode == "--dry-run"
    rollback_data[guild.id] = {}  # reset rollback log for this run
    await channel.send(f"{'Dry-running' if dry_run else 'Executing'} role update for guild: {guild.name}...")
    logger.info(f"{'Dry-running' if dry_run else 'Executing'} role update started by {ctx.author}")

    # Validate required roles
    missing_roles = set()
    for legacy_role, (pronoun_role, color_role) in role_mappings.items():
        for role_name in [legacy_role, pronoun_role, color_role]:
            if discord.utils.get(guild.roles, name=role_name) is None:
                missing_roles.add(role_name)
    # Ensures that all roles are present before running command
    if missing_roles:
        await channel.send(f"Missing roles: {', '.join(missing_roles)}.")
        logger.error(f"Aborted update_roles - Missing roles: {missing_roles}")
        return

    legacy_roles_set = set(role_mappings.keys())

    async for member in guild.fetch_members(limit=None):
        if member.bot:
            continue

        legacy_roles = [role for role in member.roles if role.name in legacy_roles_set]
        if not legacy_roles:
            continue

        # Sort legacy roles by priority
        legacy_roles_sorted = sorted(legacy_roles, key=lambda r: legacy_role_priority.index(r.name))
        top_legacy = legacy_roles_sorted[0].name

        # Collect pronoun roles
        pronoun_roles_to_add = set()
        for legacy_role in legacy_roles:
            pronoun, _ = role_mappings[legacy_role.name]
            pronoun_role_obj = discord.utils.get(guild.roles, name=pronoun)
            if pronoun_role_obj:
                pronoun_roles_to_add.add(pronoun_role_obj)

        # Determine color role
        _, color_role = role_mappings[top_legacy]
        color_role_obj = discord.utils.get(guild.roles, name=color_role)
        # Sets the role to remove and the ones to add, pulling from the array
        roles_to_remove = legacy_roles
        roles_to_add = list(pronoun_roles_to_add)
        if color_role_obj:
            roles_to_add.append(color_role_obj)
        # If user is doing a dry run, then don't actually do anything
        if dry_run:
            status = f"[Dry run] Would update {member}: remove {[r.name for r in roles_to_remove]}, add {[r.name for r in roles_to_add]}"
            logger.info(status)
        else:
            # If not doing a dry run then log rollback and migrate the roles
            try:
                # Record rollback info
                rollback_data[guild.id][member.id] = {
                    "remove": [r.id for r in roles_to_remove],
                    "add": [r.id for r in roles_to_add],
                }

                # Actually migrate roles and log it
                new_roles = [r for r in member.roles if r not in roles_to_remove] + roles_to_add
                await member.edit(roles=new_roles, reason="Mauve pronoun migration")
                status = f"Updated {member}: removed {[r.name for r in roles_to_remove]}, added {[r.name for r in roles_to_add]}"
                logger.info(status)
            except Exception as e:
                # if  something goes wrong, log it
                status = f"Error updating {member}: {str(e)}"
                logger.error(status)
        # send what's logged to the chat
        await channel.send(status)
        await asyncio.sleep(0.5)
    # End of command, say so to chat
    await channel.send("Role update completed.")
    logger.info("Role update completed successfully.")

# Rollback command
@bot.command(name="rollback")
@commands.has_role("MauvePermissions")
async def rollback(ctx, mode: str = None):
    guild = ctx.guild
    logger = get_guild_logger(guild.id)
    channel = ctx.channel
    # same form of error handling in update_roles
    if mode not in ["--dry-run", "--execute"]:
        await channel.send("Please specify a mode: --dry-run to simulate changes, and --execute to make them")
        logger.warning(f"Invalid mode specified for rollback by {ctx.author}")
        return
    # warn user if they try to run rollback without having saved rollback data first
    dry_run = mode == "--dry-run"
    changes = rollback_data.get(guild.id, {})
    if not changes:
        await channel.send("No rollback data found. Run `m;update_roles` first.")
        logger.warning("Rollback attempted with no stored changes")
        return
    # start rollback or dry run
    await channel.send(f"{'Dry-running' if dry_run else 'Executing'} rollback for guild: {guild.name}...")
    logger.info(f"{'Dry-running' if dry_run else 'Executing'} rollback started by {ctx.author}")
    # check users to see if they were affected by the role change
    # if not, skip, if so, mark down
    async for member in guild.fetch_members(limit=None):
        if member.id not in changes:
            continue
        
        change = changes[member.id]
        roles_to_restore = [discord.utils.get(guild.roles, id=r) for r in change["remove"] if discord.utils.get(guild.roles, id=r)]
        roles_to_remove = [discord.utils.get(guild.roles, id=r) for r in change["add"] if discord.utils.get(guild.roles, id=r)]
        # if dry run then just put what would have happened in chat
        if dry_run:
            status = f"[Dry run] Would rollback {member}: restore {[r.name for r in roles_to_restore]}, remove {[r.name for r in roles_to_remove]}"
            logger.info(status)
        # if not a rollback then actually enact the roleback
        else:
            try:
                new_roles = [r for r in member.roles if r not in roles_to_remove] + roles_to_restore
                await member.edit(roles=new_roles, reason="Mauve rollback")
                status = f"Rolled back {member}: restored {[r.name for r in roles_to_restore]}, removed {[r.name for r in roles_to_remove]}"
                logger.info(status)
            except Exception as e:
                status = f"Error rolling back {member}: {str(e)}"
                logger.error(status)

        await channel.send(status)
        await asyncio.sleep(0.5)

    await channel.send("Rollback completed.")
    logger.info("Rollback completed successfully.")

# Check to see if all roles expected in the server are present
@bot.command()
@commands.has_role("MauvePermissions")
async def check(ctx):
    guild = ctx.guild
    logger = get_guild_logger(guild.id)
    found_all = True
    missing_messages = []
# look and see if everything in the main array is there
    for legacy, (pronoun, color) in role_mappings.items():
        missing = []
        for role_name in [legacy, pronoun, color]:
            if not discord.utils.get(guild.roles, name=role_name):
                missing.append(role_name)
        # if it isn't, then send it in an embed
        if missing:
            found_all = False
            embed = discord.Embed(
                title="I can't find these roles!",
                description="\n".join(f"{r}" for r in missing),
                color=discord.Color.purple()
            )
            # stuff for the embed
            embed.set_footer(text="Mapping: Legacy → Pronoun, Color")
            embed.add_field(name="Legacy Role", value=legacy, inline=True)
            embed.add_field(name="Pronoun Role", value=pronoun, inline=True)
            embed.add_field(name="Color Role", value=color, inline=True)
            missing_messages.append(embed)
            logger.warning(f"Missing roles for mapping {legacy}: {missing}")
    # if everything is as expected then say so
    if found_all:
        await ctx.send("All expected roles are present!")
        logger.info("All expected roles found.")
    else:
        for embed in missing_messages:
            await ctx.send(embed=embed)

# Counts how many users have legacy roles
@bot.command(name="count")
@commands.has_role("MauvePermissions")
async def count_legacy(ctx):
    guild = ctx.guild
    logger = get_guild_logger(guild.id)
    legacy_role_names = set(role_mappings.keys())
    legacy_roles = [role for role in guild.roles if role.name in legacy_role_names]
    legacy_member_count = 0

    async for member in guild.fetch_members(limit=None):
        if any(role in legacy_roles for role in member.roles):
            legacy_member_count += 1

    await ctx.send(f"{legacy_member_count} users have a legacy role.")
    logger.info(f"{legacy_member_count} users still have a legacy role.")

# Run bot
bot.run('put your token here')
