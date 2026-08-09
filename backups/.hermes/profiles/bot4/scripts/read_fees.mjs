import { createPublicClient, http } from "viem";
import { base } from "viem/chains";

const client = createPublicClient({ chain: base, transport: http("https://mainnet.base.org") });
const ACP = "0x238E541BfefD82238730D00a2208E5497F1832E0";
const ABI = [
  { name: "platformFeeBP", type: "function", stateMutability: "view", inputs: [], outputs: [{type:"uint256"}] },
  { name: "platformTreasury", type: "function", stateMutability: "view", inputs: [], outputs: [{type:"address"}] },
  { name: "paymentToken", type: "function", stateMutability: "view", inputs: [], outputs: [{type:"address"}] },
];

const [fee, treasury, token] = await Promise.all([
  client.readContract({ address: ACP, abi: ABI, functionName: "platformFeeBP" }),
  client.readContract({ address: ACP, abi: ABI, functionName: "platformTreasury" }),
  client.readContract({ address: ACP, abi: ABI, functionName: "paymentToken" }),
]);
console.log("platformFeeBP:", fee.toString(), "=>", (Number(fee)/100).toFixed(2) + "%");
console.log("platformTreasury:", treasury);
console.log("paymentToken (USDC):", token);
