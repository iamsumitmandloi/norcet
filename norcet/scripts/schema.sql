CREATE TABLE IF NOT EXISTS questions (
  id UUID PRIMARY KEY,
  year INT,
  subject TEXT,
  topic TEXT,
  subtopic TEXT,
  question_text TEXT,
  option_a TEXT,
  option_b TEXT,
  option_c TEXT,
  option_d TEXT,
  correct_answer CHAR(1),
  explanation TEXT,
  source_pdf TEXT,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_questions_year ON questions(year);
CREATE INDEX IF NOT EXISTS idx_questions_subject ON questions(subject);
CREATE INDEX IF NOT EXISTS idx_questions_topic ON questions(topic);
CREATE INDEX IF NOT EXISTS idx_questions_subtopic ON questions(subtopic);
