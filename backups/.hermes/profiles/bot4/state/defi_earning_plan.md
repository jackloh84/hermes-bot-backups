# Jack's DeFi Earning Plan — Capital Deployment Strategy

**Created:** Aug 19, 2026
**Status:** Current position = $43.81 USDC in Gauntlet USDC Prime (Morpho, Base) @ ~4.12% APY
**Goal:** Scale this into a diversified yield stack as capital grows.

---

## The Strategy: 70/30 Safe-to-Yield Split

| Tier | % | Where | APY | Risk |
|------|-----|-------|-----|------|
| 🛡️ Safe | 70% | Morpho Gauntlet Prime (Base) | ~4% | Very low (overcollateralized crypto loans) |
| 📈 Yield | 30% | RWA credit protocol (Ethereum) | ~10% | Medium (lending to real businesses) |

**Blended APY** = 0.7×4% + 0.3×10% = **~5.8%** (vs 4.12% now, and MUCH safer than going all-in on 10%).

---

## Why 70/30 and not "all-in on 10%"

- The 10% RWA protocols lend to **private businesses** that can default → you can lose principal.
- The 4% Morpho lends to **crypto borrowers with 100%+ collateral** → nearly no principal risk.
- 30% cap means even a total loss on the RWA side only costs you 30% of the yield stack, while the 70% safe side still compounds.
- RWA is on **Ethereum mainnet** = higher gas. Small deposits get eaten by gas, so RWA only makes sense above a threshold.

---

## When to deploy each tier (capital triggers)

| Capital level | Action | Why |
|---------------|--------|-----|
| **$0–$250** | Keep 100% in Morpho (Base) | Gas would eat RWA yield; not worth bridging |
| **$250–$1,000** | Keep 100% in Morpho, but start tracking RWA | Build comfort; RWA gas ~$10-20 round-trip |
| **$1,000+** | Split: 70% Morpho / 30% Midas RWA | RWA yield (~$30/yr on $300) now exceeds gas cost |
| **$5,000+** | 60% Morpho / 30% Midas / 10% Ember or Pareto | Diversify RWA across 2 protocols |

---

## The 3 higher-yield RWA protocols (verified live Aug 19 2026)

| Protocol | APY | TVL | Chain | App URL |
|----------|-----|-----|-------|---------|
| **Midas RWA** | ~9.7% | $72M | Ethereum | https://midas.app |
| **Goldfinch** | ~10.2% | $36M | Ethereum | https://app.goldfinch.finance/earn |
| **Pareto Credit** | ~10.6% | $169M | Ethereum | https://app.pareto.credit |

**Recommended first RWA: Midas RWA** — highest APY among the liquid large ones, $72M TVL, clean single-asset USDC deposit, no KYC for basic treasury pools (verify at deposit time).

**Avoid for now:** Ember (small $7-17M, newer, less audited history). Revisit only at $5k+.

---

## Execution checklist (when capital arrives on Base)

1. **Verify current balances** — run `morpho_balance.py`.
2. **Bridge USDC Base → Ethereum** (only the 30% slice) via Relay (same flow as `consolidate_to_base.py`, reversed direction).
3. **Deposit** into Midas RWA USDC pool (ERC-4626-style deposit, same pattern as `morpho_deposit.py`).
4. **Verify** on-chain (Midas dashboard + Etherscan).
5. **Log the split** in state file so weekly check tracks both sides.

---

## Weekly check (already live)

- Cron job `12ebb6367911` → every Monday 9am, reports Morpho balance + change.
- **TODO when RWA deployed:** extend `morpho_balance.py` to also read the Midas/Ethereum position so the weekly report covers the full stack.

---

## Hard rules (don't break these)

1. **Never** put more than 30% into any single RWA/private-credit protocol.
2. **Never** chase "100%+ APY" LP farming (impermanent loss can destroy principal).
3. **Always** verify live APY on the protocol's OWN app (not DefiLlama) before depositing — the Sirloin 5.65%→0% lesson.
4. **Gas math first:** on Ethereum, a deposit+withdraw round-trip is ~$10-20. Only deploy RWA when 30% slice × APY × 1yr > gas cost comfortably.
5. **Withdraw path always tested with $5 first** before moving the full slice to a new protocol.
