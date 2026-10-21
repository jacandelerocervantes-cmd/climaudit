/**
 * Links to the public explorer. The ledger reports transaction ids like `0.0.123@1700000000.123456789`; the explorer takes
 * `0.0.123-1700000000-123456789`. Ids of the in-memory ledger and of custodial bookkeeping have no page, so they get no link.
 */
export function hashscanTransaction(base: string | null | undefined, txId: string | null | undefined): string | null {
  if (!base || !txId) return null;
  const match = /^(\d+\.\d+\.\d+)@(\d+)\.(\d+)$/.exec(txId);
  return match ? `${base}/transaction/${match[1]}-${match[2]}-${match[3]}` : null;
}

export function hashscanToken(base: string | null | undefined, tokenId: string | null | undefined): string | null {
  return base && tokenId && /^\d+\.\d+\.\d+$/.test(tokenId) ? `${base}/token/${tokenId}` : null;
}

export function hashscanTopic(base: string | null | undefined, topicId: string | null | undefined): string | null {
  return base && topicId && /^\d+\.\d+\.\d+$/.test(topicId) ? `${base}/topic/${topicId}` : null;
}
