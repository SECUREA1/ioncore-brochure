import { createThirdwebClient, getContract, readContract, resolveMethod } from 'thirdweb';
import { defineChain } from 'thirdweb/chains';

const DEFAULT_MEKNX_CONTRACT_ADDRESS = '0x809A9457670A382506F30241dD18b91aaDC9c03c';
const DEFAULT_CHAIN_ID = 1;

let cachedClient;
let cachedContract;
let cachedGateMethod;

function getThirdwebCredentials() {
  const clientId = (process.env.THIRDWEB_CLIENT_ID || '').trim();
  const secretKey = (process.env.THIRDWEB_SECRET_KEY || '').trim();
  return {
    clientId: clientId.length > 0 ? clientId : null,
    secretKey: secretKey.length > 0 ? secretKey : null
  };
}

export function isThirdwebConfigured() {
  const creds = getThirdwebCredentials();
  return Boolean(creds.clientId || creds.secretKey);
}

function resolveChain() {
  const configured = Number.parseInt(process.env.MEKNX_CONTRACT_CHAIN_ID || process.env.MEKNX_CHAIN_ID || '', 10);
  const chainId = Number.isFinite(configured) && configured > 0 ? configured : DEFAULT_CHAIN_ID;
  return defineChain(chainId);
}

function ensureThirdwebClient() {
  if (cachedClient) {
    return cachedClient;
  }

  const credentials = getThirdwebCredentials();
  if (!credentials.clientId && !credentials.secretKey) {
    throw new Error('Thirdweb credentials are not configured. Set THIRDWEB_CLIENT_ID or THIRDWEB_SECRET_KEY.');
  }

  const clientConfig = credentials.secretKey
    ? { secretKey: credentials.secretKey }
    : { clientId: credentials.clientId };

  cachedClient = createThirdwebClient(clientConfig);
  return cachedClient;
}

function resolveContractAddress() {
  const address = (process.env.MEKNX_CONTRACT_ADDRESS || '').trim();
  return address.length > 0 ? address : DEFAULT_MEKNX_CONTRACT_ADDRESS;
}

function ensureContract() {
  if (cachedContract) {
    return cachedContract;
  }

  const client = ensureThirdwebClient();
  const address = resolveContractAddress();
  const chain = resolveChain();

  cachedContract = getContract({
    client,
    chain,
    address
  });

  return cachedContract;
}

function resolveGateMethod() {
  if (cachedGateMethod) {
    return cachedGateMethod;
  }

  const signature = (process.env.MEKNX_CONTRACT_GATE_SIGNATURE || '').trim();
  if (signature) {
    cachedGateMethod = signature;
    return cachedGateMethod;
  }

  const methodName = (process.env.MEKNX_CONTRACT_GATE_METHOD || '').trim() || 'verifyAccess';
  cachedGateMethod = resolveMethod(methodName);
  return cachedGateMethod;
}

function parseParamOrder(walletAddressProvided) {
  const rawOrder = (process.env.MEKNX_GATE_PARAM_ORDER || '').trim();
  if (!rawOrder) {
    return walletAddressProvided ? ['wallet', 'pass'] : ['pass'];
  }

  return rawOrder
    .split(',')
    .map((part) => part.trim().toLowerCase())
    .filter((part) => part === 'wallet' || part === 'pass');
}

function buildMethodParams(passId, walletAddress) {
  const order = parseParamOrder(Boolean(walletAddress));
  return order.map((token) => {
    if (token === 'wallet') {
      if (!walletAddress) {
        throw new Error('Wallet address required by MEKNX_GATE_PARAM_ORDER but missing in request.');
      }
      return walletAddress;
    }
    return passId;
  });
}

function coerceBoolean(value) {
  if (typeof value === 'boolean') {
    return value;
  }
  if (typeof value === 'number') {
    return value !== 0;
  }
  if (typeof value === 'bigint') {
    return value !== 0n;
  }
  if (typeof value === 'string') {
    const trimmed = value.trim();
    if (trimmed.length === 0) {
      return false;
    }
    const lowered = trimmed.toLowerCase();
    if (lowered === 'false' || lowered === '0' || lowered === 'no' || lowered === 'denied') {
      return false;
    }
    return true;
  }
  if (Array.isArray(value)) {
    for (const entry of value) {
      const result = coerceBoolean(entry);
      if (typeof result === 'boolean') {
        return result;
      }
    }
    return value.length > 0;
  }
  if (value && typeof value === 'object') {
    if (typeof value.authorized === 'boolean') {
      return value.authorized;
    }
    if (typeof value.success === 'boolean') {
      return value.success;
    }
    if (typeof value.valid === 'boolean') {
      return value.valid;
    }
    if (typeof value.accessGranted === 'boolean') {
      return value.accessGranted;
    }
    if (typeof value.status === 'string') {
      const lowered = value.status.toLowerCase();
      if (['approved', 'granted', 'ok', 'valid', 'verified'].includes(lowered)) {
        return true;
      }
      if (['denied', 'rejected', 'invalid'].includes(lowered)) {
        return false;
      }
    }
    for (const entry of Object.values(value)) {
      if (typeof entry === 'boolean') {
        return entry;
      }
    }
  }
  return Boolean(value);
}

function extractMessage(payload) {
  if (!payload) {
    return undefined;
  }
  if (typeof payload === 'string') {
    return payload.trim().length > 0 ? payload.trim() : undefined;
  }
  if (Array.isArray(payload)) {
    for (const entry of payload) {
      const maybe = extractMessage(entry);
      if (maybe) {
        return maybe;
      }
    }
    return undefined;
  }
  if (typeof payload === 'object') {
    if (typeof payload.message === 'string' && payload.message.trim().length > 0) {
      return payload.message.trim();
    }
    if (typeof payload.reason === 'string' && payload.reason.trim().length > 0) {
      return payload.reason.trim();
    }
    for (const entry of Object.values(payload)) {
      const maybe = extractMessage(entry);
      if (maybe) {
        return maybe;
      }
    }
  }
  return undefined;
}

export async function executeMeknxGate({ passId, walletAddress }) {
  const normalizedPass = typeof passId === 'string' ? passId.trim() : passId?.toString() || '';
  if (!normalizedPass) {
    throw new Error('MEKNX pass ID is required for contract verification.');
  }

  const normalizedWallet = typeof walletAddress === 'string' ? walletAddress.trim() : '';
  const contract = ensureContract();
  const method = resolveGateMethod();
  const params = buildMethodParams(normalizedPass, normalizedWallet || null);

  try {
    const result = await readContract({
      contract,
      method,
      params
    });

    const authorized = coerceBoolean(result);
    const message = extractMessage(result);

    return {
      authorized,
      message,
      contractAddress: contract.address,
      method: typeof method === 'string' ? method : undefined,
      params,
      rawResult: result
    };
  } catch (error) {
    const contractAddress = contract.address;
    const methodLabel = typeof method === 'string' ? method : 'resolved';
    const errorMessage = error && typeof error.message === 'string' ? error.message : String(error);
    throw new Error(
      `Failed to execute MEKNX contract call (${methodLabel} @ ${contractAddress}): ${errorMessage}`,
      { cause: error }
    );
  }
}

export function resetThirdwebCache() {
  cachedClient = undefined;
  cachedContract = undefined;
  cachedGateMethod = undefined;
}
