# BountyBook — $3.00 USDC AI Frameworks Bounty (READY TO SHIP)

**Job ID:** `4e4f5fb7-fa5c-4fa5-9ced-934cbe45943b`
**Budget:** $3.00 USDC (96% = $2.88 to agent after 4% platform fee)
**Status:** Deliverable validated and passing the test harness. **Blocked at submission: needs a Base-chain wallet.**

## Deliverable
File: `agent_frameworks_READY.json` — 25 verified open-source AI agent frameworks with real GitHub star counts (sourced live from GitHub API this session), all required schema fields, all tests pass.

**Test verdict (replicated from bounty spec, ran locally):**
```
ALL TESTS PASSED — 25 frameworks found
Total GitHub stars captured: 902,863
Multi-agent frameworks: 21/25
```

## What's blocking the payout
BountyBook's API requires a signed nonce (Ethereum personal_sign) to claim & submit a job. The bot has no wallet credentials stored. The `PAYOUT_USDC` and `PAYOUT_ETH` env vars in the secrets dir are for inbound payouts, not for signing auth.

## What Jack needs to do (one-time, <90 seconds)
1. Export a Base/Ethereum private key from any wallet (MetaMask, Rabby, Coinbase Wallet). For testnet use, a fresh throwaway key is best — this is an experimental beta per the website banner.
2. Fund the address with ~$0.50 ETH on Base (chain ID 8453) for gas (the agent payout is in USDC, claimed separately).
3. Add to `~/.hermes/profiles/bot4/secrets/`:
   - `BB_PRIVATE_KEY=0x...` (the signing key)
   - `BB_EXECUTOR_ADDRESS=0x...` (the address that receives USDC)
4. Run `bash execute.sh` — claim, submit, oracle auto-verifies, USDC releases.

## Why this bounty is high-EV
- **No competition:** Job sat open for 4+ months (created 2026-03-19, last activity 2026-08-04). Only the poster has claimed it.
- **Trivial deliverable:** Pure research, output is deterministic JSON, test harness is fully transparent.
- **Compounding:** 118 open jobs currently on BountyBook pay $1.50–$5.00 USDC each. Once the wallet is wired, the bot can run a sweep loop claiming/submitting eligible jobs in batch.
- **Stack-fit:** Code/run/dev jobs match the bot's tools exactly; research/JSON jobs are pure LLM work.

## Other top bounty picks (queued for wallet setup)
- `734626a0-26b5-478b-b9cf-fb575aea8adc` — TypeScript EventBus class ($5.00, 20 min)
- `193daf43-6436-4456-a028-dcb3149a2b95` — Dijkstra's algorithm in Python ($5.00, 30 min)
- `dc07cac3-ba35-4f13-965e-4fa8ace642a5` — Trie class in Python ($4.00, 20 min)
