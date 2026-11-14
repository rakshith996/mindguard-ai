USE mindguard;

-- Increment 6: store only keyed fingerprints for temporary login throttling.
-- No raw login IDs or IP addresses are stored in this table.
CREATE TABLE IF NOT EXISTS auth_rate_limit_buckets (
  bucket_hash CHAR(64) NOT NULL PRIMARY KEY,
  failure_count SMALLINT UNSIGNED NOT NULL DEFAULT 0,
  window_started_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  blocked_until DATETIME NULL,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_auth_rate_updated (updated_at),
  INDEX idx_auth_rate_blocked (blocked_until)
) ENGINE=InnoDB;
