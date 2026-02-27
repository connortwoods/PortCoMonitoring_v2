-- PortCoMonitoring schema
-- Run in Supabase SQL Editor or via supabase db push

-- Companies: one row per (company, section, URL)
CREATE TABLE IF NOT EXISTS companies (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  company text NOT NULL,
  section text NOT NULL,
  url text NOT NULL,
  created_at timestamptz DEFAULT now(),
  UNIQUE(company, section)
);

CREATE INDEX IF NOT EXISTS idx_companies_company ON companies(company);

-- Subscribers for email alerts
CREATE TABLE IF NOT EXISTS subscribers (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  email text NOT NULL UNIQUE,
  created_at timestamptz DEFAULT now()
);

-- Website change snapshots (content hash per company/section/url)
CREATE TABLE IF NOT EXISTS snapshots (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id uuid NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
  content_hash text NOT NULL,
  fetched_at timestamptz DEFAULT now(),
  UNIQUE(company_id)
);

CREATE INDEX IF NOT EXISTS idx_snapshots_company_id ON snapshots(company_id);

-- Glassdoor insights: current rating, 12-month-ago rating, delta, snippet
CREATE TABLE IF NOT EXISTS glassdoor_insights (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  company text NOT NULL UNIQUE,
  glassdoor_url text,
  current_rating numeric(3,2),
  rating_12m_ago numeric(3,2),
  rating_delta numeric(3,2),
  review_snippet text,
  review_snippet_12m_ago text,
  source text,  -- 'wayback' | 'serpapi'
  updated_at timestamptz DEFAULT now(),
  raw_json jsonb
);

CREATE INDEX IF NOT EXISTS idx_glassdoor_company ON glassdoor_insights(company);

-- Historical change log (website + Glassdoor/review changes)
CREATE TABLE IF NOT EXISTS change_log (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  company text NOT NULL,
  change_type text NOT NULL,  -- 'website' | 'glassdoor_rating' | 'glassdoor_review'
  previous_value text,
  new_value text,
  details jsonb,
  created_at timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_change_log_company ON change_log(company);
CREATE INDEX IF NOT EXISTS idx_change_log_created_at ON change_log(created_at DESC);

-- Optional: LinkedIn headcount (SerpAPI or manual)
CREATE TABLE IF NOT EXISTS linkedin_snapshots (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  company text NOT NULL UNIQUE,
  headcount int,
  employee_count_text text,
  source text,
  updated_at timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_linkedin_snapshots_company ON linkedin_snapshots(company);

-- RLS: allow anon to insert/update for GitHub Actions
ALTER TABLE companies ENABLE ROW LEVEL SECURITY;
ALTER TABLE subscribers ENABLE ROW LEVEL SECURITY;
ALTER TABLE snapshots ENABLE ROW LEVEL SECURITY;
ALTER TABLE glassdoor_insights ENABLE ROW LEVEL SECURITY;
ALTER TABLE change_log ENABLE ROW LEVEL SECURITY;
ALTER TABLE linkedin_snapshots ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Allow anon insert companies" ON companies FOR INSERT TO anon WITH CHECK (true);
CREATE POLICY "Allow anon select companies" ON companies FOR SELECT TO anon USING (true);
CREATE POLICY "Allow anon update companies" ON companies FOR UPDATE TO anon USING (true);

CREATE POLICY "Allow anon insert subscribers" ON subscribers FOR INSERT TO anon WITH CHECK (true);
CREATE POLICY "Allow anon select subscribers" ON subscribers FOR SELECT TO anon USING (true);
CREATE POLICY "Allow anon update subscribers" ON subscribers FOR UPDATE TO anon USING (true);

CREATE POLICY "Allow anon insert snapshots" ON snapshots FOR INSERT TO anon WITH CHECK (true);
CREATE POLICY "Allow anon select snapshots" ON snapshots FOR SELECT TO anon USING (true);
CREATE POLICY "Allow anon update snapshots" ON snapshots FOR UPDATE TO anon USING (true);

CREATE POLICY "Allow anon insert glassdoor_insights" ON glassdoor_insights FOR INSERT TO anon WITH CHECK (true);
CREATE POLICY "Allow anon select glassdoor_insights" ON glassdoor_insights FOR SELECT TO anon USING (true);
CREATE POLICY "Allow anon update glassdoor_insights" ON glassdoor_insights FOR UPDATE TO anon USING (true);

CREATE POLICY "Allow anon insert change_log" ON change_log FOR INSERT TO anon WITH CHECK (true);
CREATE POLICY "Allow anon select change_log" ON change_log FOR SELECT TO anon USING (true);

CREATE POLICY "Allow anon insert linkedin_snapshots" ON linkedin_snapshots FOR INSERT TO anon WITH CHECK (true);
CREATE POLICY "Allow anon select linkedin_snapshots" ON linkedin_snapshots FOR SELECT TO anon USING (true);
CREATE POLICY "Allow anon update linkedin_snapshots" ON linkedin_snapshots FOR UPDATE TO anon USING (true);
