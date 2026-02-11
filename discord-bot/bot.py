#!/usr/bin/env python3
"""WattCoin Discord Bot - Main entry point."""
import asyncio
import os
import sys
from pathlib import Path

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

import discord
from discord.ext import commands
from config import Config, validate_config

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(
    command_prefix=Config.COMMAND_PREFIX,
    intents=intents,
    help_command=commands.DefaultHelpCommand()
)


@bot.event
async def on_ready():
    """Called when bot is ready."""
    print(f'✅ Logged in as {bot.user} (ID: {bot.user.id})')
    print(f'📊 Connected to {len(bot.guilds)} guilds')
    print(f'⚡ Bot is ready!')
    
    try:
        synced = await bot.tree.sync()
        print(f'🔄 Synced {len(synced)} slash commands')
    except Exception as e:
        print(f'⚠️ Failed to sync commands: {e}')


@bot.event
async def on_guild_join(guild: discord.Guild):
    """Called when bot joins a guild."""
    print(f'📥 Joined guild: {guild.name} (ID: {guild.id})')


@bot.event
async def on_command_error(ctx: commands.Context, error):
    """Handle command errors."""
    if isinstance(error, commands.CommandNotFound):
        return
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f'❌ Missing required argument: {error.param.name}')
    elif isinstance(error, commands.BadArgument):
        await ctx.send(f'❌ Bad argument: {error}')
    else:
        print(f'Command error: {error}')
        await ctx.send('❌ An error occurred while processing your command.')


async def load_extensions():
    """Load all cogs."""
    cogs = ['balance', 'network', 'alerts']
    
    for cog in cogs:
        try:
            await bot.load_extension(f'cogs.{cog}')
            print(f'✅ Loaded cog: {cog}')
        except Exception as e:
            print(f'❌ Failed to load cog {cog}: {e}')


async def main():
    """Main entry point."""
    try:
        validate_config()
    except ValueError as e:
        print(f'❌ Configuration error: {e}')
        sys.exit(1)
    
    await load_extensions()
    
    try:
        await bot.start(Config.DISCORD_TOKEN)
    except KeyboardInterrupt:
        print('\n🛑 Shutting down...')
    finally:
        await bot.close()


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print('\n👋 Goodbye!')
