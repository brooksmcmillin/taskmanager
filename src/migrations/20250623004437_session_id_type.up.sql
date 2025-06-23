-- Migration: session_id_type
-- Created: 2025-06-23T00:44:37.149Z
  ALTER TABLE sessions ALTER COLUMN id TYPE VARCHAR (255);
  
