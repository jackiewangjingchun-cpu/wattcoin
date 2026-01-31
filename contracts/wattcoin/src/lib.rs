use anchor_lang::prelude::*;
use anchor_spl::token::{self, Mint, Token, TokenAccount, Transfer};

declare_id!("WATT1111111111111111111111111111111111111111");

#[program]
pub mod wattcoin {
    use super::*;

    pub fn initialize_token(
        ctx: Context<InitializeToken>,
        total_supply: u64,
        burn_rate_basis_points: u16, // 15 = 0.15% (2026 optimized)
    ) -> Result<()> {
        let token_config = &mut ctx.accounts.token_config;
        token_config.authority = ctx.accounts.authority.key();
        token_config.mint = ctx.accounts.mint.key();
        token_config.burn_rate = burn_rate_basis_points;
        token_config.total_burned = 0;
        token_config.utility_vault = ctx.accounts.utility_vault.key();
        
        msg!("WattCoin initialized: {} WATT, {}bp burn rate", total_supply, burn_rate_basis_points);
        Ok(())
    }

    pub fn execute_task_payment(
        ctx: Context<ExecuteTaskPayment>,
        amount: u64,
        task_id: String,
    ) -> Result<()> {
        let token_config = &mut ctx.accounts.token_config;
        
        // Calculate burn amount (0.15% default for 2026 scarcity signal)
        let burn_amount = (amount * token_config.burn_rate as u64) / 10000;
        let net_amount = amount - burn_amount;

        // Transfer to recipient
        let cpi_accounts = Transfer {
            from: ctx.accounts.from_token_account.to_account_info(),
            to: ctx.accounts.to_token_account.to_account_info(),
            authority: ctx.accounts.authority.to_account_info(),
        };
        let cpi_program = ctx.accounts.token_program.to_account_info();
        let cpi_ctx = CpiContext::new(cpi_program, cpi_accounts);
        token::transfer(cpi_ctx, net_amount)?;

        // Burn tokens (send to burn vault)
        let burn_cpi_accounts = Transfer {
            from: ctx.accounts.from_token_account.to_account_info(),
            to: ctx.accounts.burn_vault.to_account_info(),
            authority: ctx.accounts.authority.to_account_info(),
        };
        let burn_cpi_ctx = CpiContext::new(ctx.accounts.token_program.to_account_info(), burn_cpi_accounts);
        token::transfer(burn_cpi_ctx, burn_amount)?;

        // Update burn tracking
        token_config.total_burned += burn_amount;

        msg!("Task payment: {} WATT (burned: {}), Task ID: {}", net_amount, burn_amount, task_id);
        Ok(())
    }

    pub fn stake_for_energy_rebate(
        ctx: Context<StakeForEnergyRebate>,
        amount: u64,
        duration_days: u8,
    ) -> Result<()> {
        let stake_account = &mut ctx.accounts.stake_account;
        stake_account.owner = ctx.accounts.owner.key();
        stake_account.amount = amount;
        stake_account.start_time = Clock::get()?.unix_timestamp;
        stake_account.duration = duration_days as i64 * 24 * 3600; // Convert to seconds
        stake_account.claimed = false;

        // Transfer tokens to stake vault
        let cpi_accounts = Transfer {
            from: ctx.accounts.owner_token_account.to_account_info(),
            to: ctx.accounts.stake_vault.to_account_info(),
            authority: ctx.accounts.owner.to_account_info(),
        };
        let cpi_program = ctx.accounts.token_program.to_account_info();
        let cpi_ctx = CpiContext::new(cpi_program, cpi_accounts);
        token::transfer(cpi_ctx, amount)?;

        msg!("Staked {} WATT for {} days energy rebate", amount, duration_days);
        Ok(())
    }

    pub fn claim_energy_rebate(
        ctx: Context<ClaimEnergyRebate>,
        energy_consumed_kwh: u64,
    ) -> Result<()> {
        let stake_account = &mut ctx.accounts.stake_account;
        let current_time = Clock::get()?.unix_timestamp;
        
        require!(!stake_account.claimed, ErrorCode::AlreadyClaimed);
        require!(
            current_time >= stake_account.start_time + stake_account.duration,
            ErrorCode::StakingPeriodNotComplete
        );

        // Calculate rebate: 5% of energy cost in WATT
        // Simplified: 1 kWh = 0.1 WATT rebate (configurable)
        let rebate_amount = energy_consumed_kwh * 100_000; // 0.1 WATT in lamports
        let max_rebate = stake_account.amount / 10; // Max 10% of stake
        let actual_rebate = std::cmp::min(rebate_amount, max_rebate);

        // Transfer rebate
        let cpi_accounts = Transfer {
            from: ctx.accounts.rebate_vault.to_account_info(),
            to: ctx.accounts.owner_token_account.to_account_info(),
            authority: ctx.accounts.authority.to_account_info(),
        };
        let cpi_program = ctx.accounts.token_program.to_account_info();
        let cpi_ctx = CpiContext::new(cpi_program, cpi_accounts);
        token::transfer(cpi_ctx, actual_rebate)?;

        // Return original stake
        let stake_cpi_accounts = Transfer {
            from: ctx.accounts.stake_vault.to_account_info(),
            to: ctx.accounts.owner_token_account.to_account_info(),
            authority: ctx.accounts.authority.to_account_info(),
        };
        let stake_cpi_ctx = CpiContext::new(ctx.accounts.token_program.to_account_info(), stake_cpi_accounts);
        token::transfer(stake_cpi_ctx, stake_account.amount)?;

        stake_account.claimed = true;

        msg!("Energy rebate claimed: {} WATT for {} kWh", actual_rebate, energy_consumed_kwh);
        Ok(())
    }
}

#[derive(Accounts)]
pub struct InitializeToken<'info> {
    #[account(mut)]
    pub authority: Signer<'info>,
    #[account(
        init,
        payer = authority,
        space = 8 + TokenConfig::SIZE
    )]
    pub token_config: Account<'info, TokenConfig>,
    pub mint: Account<'info, Mint>,
    pub utility_vault: Account<'info, TokenAccount>,
    pub system_program: Program<'info, System>,
}

#[derive(Accounts)]
pub struct ExecuteTaskPayment<'info> {
    pub authority: Signer<'info>,
    #[account(mut)]
    pub token_config: Account<'info, TokenConfig>,
    #[account(mut)]
    pub from_token_account: Account<'info, TokenAccount>,
    #[account(mut)]
    pub to_token_account: Account<'info, TokenAccount>,
    #[account(mut)]
    pub burn_vault: Account<'info, TokenAccount>,
    pub token_program: Program<'info, Token>,
}

#[derive(Accounts)]
pub struct StakeForEnergyRebate<'info> {
    #[account(mut)]
    pub owner: Signer<'info>,
    #[account(
        init,
        payer = owner,
        space = 8 + StakeAccount::SIZE
    )]
    pub stake_account: Account<'info, StakeAccount>,
    #[account(mut)]
    pub owner_token_account: Account<'info, TokenAccount>,
    #[account(mut)]
    pub stake_vault: Account<'info, TokenAccount>,
    pub token_program: Program<'info, Token>,
    pub system_program: Program<'info, System>,
}

#[derive(Accounts)]
pub struct ClaimEnergyRebate<'info> {
    pub owner: Signer<'info>,
    pub authority: Signer<'info>,
    #[account(mut)]
    pub stake_account: Account<'info, StakeAccount>,
    #[account(mut)]
    pub owner_token_account: Account<'info, TokenAccount>,
    #[account(mut)]
    pub stake_vault: Account<'info, TokenAccount>,
    #[account(mut)]
    pub rebate_vault: Account<'info, TokenAccount>,
    pub token_program: Program<'info, Token>,
}

#[account]
pub struct TokenConfig {
    pub authority: Pubkey,
    pub mint: Pubkey,
    pub burn_rate: u16, // Basis points (15 = 0.15% for 2026)
    pub total_burned: u64,
    pub utility_vault: Pubkey,
}

impl TokenConfig {
    pub const SIZE: usize = 32 + 32 + 2 + 8 + 32;
}

#[account]
pub struct StakeAccount {
    pub owner: Pubkey,
    pub amount: u64,
    pub start_time: i64,
    pub duration: i64,
    pub claimed: bool,
}

impl StakeAccount {
    pub const SIZE: usize = 32 + 8 + 8 + 8 + 1;
}

#[error_code]
pub enum ErrorCode {
    #[msg("Energy rebate already claimed")]
    AlreadyClaimed,
    #[msg("Staking period not complete")]
    StakingPeriodNotComplete,
}