ALTER TABLE external_api_scene_bindings
  ADD COLUMN badge_text VARCHAR(32) NOT NULL DEFAULT '' AFTER subtitle,
  ADD COLUMN badge_color VARCHAR(16) NOT NULL DEFAULT '' AFTER badge_text;
