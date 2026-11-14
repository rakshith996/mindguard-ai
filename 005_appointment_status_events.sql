USE mindguard;

-- Increment 5: minimal counsellor appointment status audit history.
-- No student message, name, login ID, or wellness values are copied here.
CREATE TABLE IF NOT EXISTS appointment_status_events (
  id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  support_request_id BIGINT UNSIGNED NOT NULL,
  actor_user_id BIGINT UNSIGNED NULL,
  previous_status ENUM('pending','accepted','completed','declined') NOT NULL,
  new_status ENUM('pending','accepted','completed','declined') NOT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_status_event_request FOREIGN KEY (support_request_id)
    REFERENCES support_requests(id) ON DELETE CASCADE,
  CONSTRAINT fk_status_event_actor FOREIGN KEY (actor_user_id)
    REFERENCES users(id) ON DELETE SET NULL,
  INDEX idx_status_event_created (created_at),
  INDEX idx_status_event_request (support_request_id)
) ENGINE=InnoDB;
