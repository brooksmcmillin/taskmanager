-- AI/LLM Security News Feed Sources
-- Import with: psql -d taskmanager < feed_sources.sql

INSERT INTO feed_sources (name, url, description, type, is_active, fetch_interval_hours, quality_score)
VALUES
  -- Research Papers (ArXiv)
  ('ArXiv CS.CR (Cryptography and Security)', 'http://export.arxiv.org/rss/cs.CR', 'Latest research papers on cryptography and security from ArXiv', 'paper', true, 6, 1.0),
  ('ArXiv CS.AI (Artificial Intelligence)', 'http://export.arxiv.org/rss/cs.AI', 'Latest AI research papers from ArXiv', 'paper', true, 6, 1.0),
  ('ArXiv CS.LG (Machine Learning)', 'http://export.arxiv.org/rss/cs.LG', 'Latest machine learning research papers from ArXiv', 'paper', true, 6, 1.0),

  -- Security Blogs
  ('OWASP Blog', 'https://owasp.org/www-community/rss.xml', 'OWASP security community updates', 'article', true, 6, 1.0),
  ('Trail of Bits Blog', 'https://blog.trailofbits.com/feed/', 'Security research and engineering insights', 'article', true, 6, 1.0),
  ('NIST Cybersecurity Insights', 'https://www.nist.gov/blogs/cybersecurity-insights/rss.xml', 'NIST cybersecurity research and standards', 'article', true, 6, 1.0),
  ('Schneier on Security', 'https://www.schneier.com/feed/', 'Security expert Bruce Schneier''s blog', 'article', true, 6, 1.0),

  -- AI Research Blogs
  ('Google AI Blog', 'https://blog.research.google/atom.xml', 'Research and insights from Google AI', 'article', true, 6, 1.0),
  ('OpenAI Blog', 'https://openai.com/blog/rss.xml', 'Latest updates and research from OpenAI', 'article', true, 6, 1.0),
  ('Anthropic Blog', 'https://www.anthropic.com/news/rss.xml', 'Research and safety updates from Anthropic', 'article', true, 6, 1.0),
  ('DeepMind Blog', 'https://deepmind.google/blog/rss.xml', 'AI research from Google DeepMind', 'article', true, 6, 1.0),
  ('The Gradient', 'https://thegradient.pub/rss/', 'ML research news and perspectives', 'article', true, 6, 1.0)

ON CONFLICT (url) DO NOTHING;
