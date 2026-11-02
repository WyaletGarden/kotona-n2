// Time-based review counts can expire even when the account revision is unchanged.
export function createRefreshPolicy({ now = Date.now, ttl = 15000 } = {}) {
  let lastSynced = -Infinity;
  let invalidated = false;
  return {
    synced() {
      lastSynced = now();
      invalidated = false;
    },
    invalidate() {
      invalidated = true;
    },
    needsRefresh(validUntil) {
      return (
        invalidated ||
        now() - lastSynced >= ttl ||
        (validUntil != null &&
          (typeof validUntil === 'number' ? validUntil : Date.parse(validUntil)) <= now())
      );
    },
  };
}
