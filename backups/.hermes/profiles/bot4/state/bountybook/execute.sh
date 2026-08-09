#!/bin/bash
# BountyBook bounty execution — runs once a Base wallet is provided.
# Job: 4e4f5fb7-fa5c-4fa5-9ced-934cbe45943b  ($3.00 USDC, AI agent frameworks list)
# Author: Jack Loh's earning agent | 2026-08-04
set -euo pipefail

# === CONFIGURATION (fill these before running) ===
JOB_ID="4e4f5fb7-fa5c-4fa5-9ced-934cbe45943b"
EXECUTOR_ADDRESS="0xREPLACE_WITH_JACKS_BASE_ADDRESS"   # Jack's Base address — receives USDC
PRIVATE_KEY="0xREPLACE_WITH_PRIVATE_KEY"               # signs the nonce
DELIVERABLE="$(dirname "$0")/agent_frameworks_READY.json"

API="https://api.bountybook.ai"

# === STEP 1: get nonce ===
echo "[1/5] Requesting nonce..."
NONCE=$(curl -s "${API}/auth/nonce?address=${EXECUTOR_ADDRESS}" | jq -r .nonce)
echo "  nonce=$NONCE"

# === STEP 2: sign nonce via ethers (works with Node's ethers.js) ===
echo "[2/5] Signing nonce..."
SIGNATURE=$(node -e "
const { Wallet } = require('ethers');
const w = new Wallet('${PRIVATE_KEY}');
console.log(w.signMessageSync('${NONCE}'));
")

# === STEP 3: get session token ===
echo "[3/5] Verifying signature..."
TOKEN=$(curl -s -X POST "${API}/auth/verify" \
  -H "Content-Type: application/json" \
  -d "{\"address\":\"${EXECUTOR_ADDRESS}\",\"signature\":\"${SIGNATURE}\"}" \
  | jq -r .token)
echo "  token=${TOKEN:0:20}..."

# === STEP 4: claim the job ===
echo "[4/5] Claiming job ${JOB_ID}..."
curl -s -X POST "${API}/jobs/${JOB_ID}/claim" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json" \
  -d "{\"executorAddress\":\"${EXECUTOR_ADDRESS}\"}"

# === STEP 5: submit output ===
echo "[5/5] Submitting deliverable..."
OUTPUT=$(cat "$DELIVERABLE")
curl -s -X POST "${API}/jobs/${JOB_ID}/submit" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json" \
  -d "$(jq -nc --arg addr "$EXECUTOR_ADDRESS" --arg json "$OUTPUT" \
       '{executorAddress: $addr, outputData: {agent_frameworks_json: $json}}')"

echo "✅ Submission complete. Oracle will verify within seconds; USDC releases on pass."
echo "Track: https://bountybook.ai/changelog"
