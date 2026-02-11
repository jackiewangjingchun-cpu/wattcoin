"""Balance check commands."""
import discord
from discord import app_commands
from discord.ext import commands
from services.watt_api import watt_api
from solders.pubkey import Pubkey


class BalanceCog(commands.Cog):
    """Commands for checking WATT balances."""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
    
    def _is_valid_solana_address(self, address: str) -> bool:
        """Validate Solana address format."""
        try:
            Pubkey.from_string(address)
            return True
        except Exception:
            return False
    
    @app_commands.command(name='balance', description='Check WATT balance for a wallet')
    @app_commands.describe(wallet='Solana wallet address')
    async def balance_slash(self, interaction: discord.Interaction, wallet: str):
        """Slash command to check balance."""
        await self._check_balance(interaction, wallet, is_slash=True)
    
    async def _check_balance(self, ctx_or_interaction, wallet: str, is_slash: bool):
        """Check balance for a wallet."""
        if not self._is_valid_solana_address(wallet):
            msg = '❌ Invalid Solana wallet address.'
            if is_slash:
                await ctx_or_interaction.response.send_message(msg, ephemeral=True)
            return
        
        if is_slash:
            await ctx_or_interaction.response.defer()
        
        try:
            result = await watt_api.get_balance(wallet)
            
            embed = discord.Embed(
                title='💰 WATT Balance',
                color=discord.Color.green() if result.get('balance', 0) > 0 else discord.Color.greyple()
            )
            embed.add_field(name='Wallet', value=f'`{wallet[:20]}...{wallet[-4:]}`', inline=False)
            embed.add_field(name='Balance', value=f'**{result.get("balance", 0):,.2f} WATT**', inline=True)
            
            if is_slash:
                await ctx_or_interaction.followup.send(embed=embed)
                
        except Exception as e:
            error_msg = f'❌ Error: {str(e)}'
            if is_slash:
                await ctx_or_interaction.followup.send(error_msg)


async def setup(bot: commands.Bot):
    """Add cog to bot."""
    await bot.add_cog(BalanceCog(bot))
