CREATE DATABASE IF NOT EXISTS mindguard CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE mindguard;

CREATE TABLE IF NOT EXISTS users (
  id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  display_name VARCHAR(80) NOT NULL,
  login_id VARCHAR(60) NOT NULL UNIQUE,
  password_hash VARCHAR(255) NOT NULL,
  role ENUM('student','counsellor') NOT NULL DEFAULT 'student',
  consent_at DATETIME NULL,
  consent_version VARCHAR(20) NULL,
  is_active BOOLEAN NOT NULL DEFAULT TRUE,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS checkins (
  id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  student_id BIGINT UNSIGNED NOT NULL,
  mood ENUM('Great','Good','Okay','Low','Stressed') NOT NULL,
  stress TINYINT UNSIGNED NOT NULL,
  sleep_hours DECIMAL(4,1) NOT NULL,
  academic_pressure TINYINT UNSIGNED NOT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT chk_stress CHECK (stress BETWEEN 1 AND 5),
  CONSTRAINT chk_pressure CHECK (academic_pressure BETWEEN 1 AND 5),
  CONSTRAINT chk_sleep CHECK (sleep_hours BETWEEN 0 AND 24),
  CONSTRAINT fk_checkin_student FOREIGN KEY (student_id) REFERENCES users(id) ON DELETE CASCADE,
  INDEX idx_checkin_created (created_at),
  INDEX idx_checkin_student_created (student_id, created_at)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS support_requests (
  id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  student_id BIGINT UNSIGNED NOT NULL,
  preferred_date DATE NOT NULL,
  preferred_time ENUM('Morning','Afternoon','Evening') NOT NULL,
  message VARCHAR(500) NULL,
  status ENUM('pending','accepted','completed','declined') NOT NULL DEFAULT 'pending',
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_request_student FOREIGN KEY (student_id) REFERENCES users(id) ON DELETE CASCADE,
  INDEX idx_request_status_created (status, created_at),
  INDEX idx_request_student (student_id)
) ENGINE=InnoDB;


-- Minimal appointment workflow audit. It deliberately excludes student messages
-- and wellness/check-in data. Events are erased when the related request is erased.
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

-- Increment 6: HMAC-only login throttling buckets; raw identifiers/IPs are never stored.
CREATE TABLE IF NOT EXISTS auth_rate_limit_buckets (
  bucket_hash CHAR(64) NOT NULL PRIMARY KEY,
  failure_count SMALLINT UNSIGNED NOT NULL DEFAULT 0,
  window_started_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  blocked_until DATETIME NULL,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_auth_rate_updated (updated_at),
  INDEX idx_auth_rate_blocked (blocked_until)
) ENGINE=InnoDB;
