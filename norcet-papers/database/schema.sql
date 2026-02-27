-- Phase 5: Database Design (PostgreSQL)
-- Stores normalized NORCET MCQs for filtering by year/subject/topic/subtopic.

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

CREATE TABLE IF NOT EXISTS questions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    question_hash TEXT NOT NULL UNIQUE,
    year INT NOT NULL,
    subject TEXT NOT NULL,
    topic TEXT NOT NULL,
    subtopic TEXT NOT NULL,
    question_text TEXT NOT NULL,
    option_a TEXT NOT NULL,
    option_b TEXT NOT NULL,
    option_c TEXT NOT NULL,
    option_d TEXT NOT NULL,
    correct_answer TEXT NOT NULL CHECK (correct_answer IN ('A', 'B', 'C', 'D')),
    explanation TEXT,
    source_pdf TEXT,
    source_file TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_questions_year ON questions (year);
CREATE INDEX IF NOT EXISTS idx_questions_subject ON questions (subject);
CREATE INDEX IF NOT EXISTS idx_questions_topic ON questions (topic);
CREATE INDEX IF NOT EXISTS idx_questions_subtopic ON questions (subtopic);
CREATE INDEX IF NOT EXISTS idx_questions_year_subject_topic ON questions (year, subject, topic);
