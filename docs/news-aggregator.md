# AI/LLM Security News Aggregator

The news aggregator automatically fetches and displays AI and LLM security news from various RSS feeds.

## Features

- **Automatic Fetching**: Fetches news every 6 hours from 12 curated sources
- **Keyword Filtering**: Articles are filtered by AI/LLM security keywords
- **Read/Unread Tracking**: Mark articles as read or unread per user
- **Rating System**: Rate articles as:
  - **Good**: High-quality, relevant content
  - **Bad**: Poor quality or misleading content
  - **Not Interested**: Good quality but not relevant to your interests
- **Quality Scoring**: Feed sources are automatically scored based on user ratings
- **Search & Filter**: Search articles by title/summary and filter by unread status

## Architecture

### Backend

**Models** (`app/models/`):
- `FeedSource`: RSS feed sources with quality scores
- `Article`: Fetched news articles with metadata and keywords
- `ArticleInteraction`: User interactions (read status, ratings)

**API Endpoints** (`app/api/news.py`):
- `GET /api/news`: List articles with filters (unread, search, pagination)
- `GET /api/news/{id}`: Get single article
- `POST /api/news/{id}/read`: Mark as read/unread
- `POST /api/news/{id}/rate`: Rate article (good/bad/not_interested)

**Services** (`app/services/`):
- `news_fetcher.py`: RSS parsing and article storage
- `scheduler.py`: APScheduler for periodic fetching

### Frontend

**Route**: `/news`

**Features**:
- Infinite scroll article feed
- Unread-only filter
- Search by title/summary
- Mark as read/unread buttons
- Rating buttons with visual feedback
- Article cards with source, author, date, keywords

## Feed Sources

The aggregator includes these curated sources:

1. **Research Papers**:
   - ArXiv CS.CR (Cryptography and Security)
   - ArXiv CS.AI (Artificial Intelligence)
   - ArXiv CS.LG (Machine Learning)

2. **Security Blogs**:
   - OWASP Blog
   - Trail of Bits Blog
   - NIST Cybersecurity Insights
   - Schneier on Security

3. **AI Research Blogs**:
   - Google AI Blog
   - OpenAI Blog
   - Anthropic Blog
   - DeepMind Blog
   - The Gradient

## Keyword Filtering

Articles are filtered to include only those matching AI/LLM security keywords:

- LLM security, AI security
- Prompt injection, jailbreak
- Adversarial attacks
- Model safety, AI safety
- Machine learning security
- Neural network attacks
- Model poisoning, backdoor attacks
- Data poisoning
- Membership inference
- Model extraction
- Privacy attacks
- Federated learning security
- Transformer security
- GPT security
- Language models
- Generative AI
- Foundation models
- Alignment, RLHF
- Constitutional AI
- Red teaming

## Usage

### Viewing News

1. Navigate to the **News** tab in the navigation bar
2. Browse articles in chronological order (newest first)
3. Use the "Show unread only" filter to focus on new articles
4. Search for specific topics using the search bar

### Managing Articles

**Mark as Read**:
- Click "Read" button to mark an article as read
- Read articles appear slightly faded
- Click "Unread" to mark back as unread

**Rating Articles**:
- **👍 Good**: Quality content that's relevant and useful
- **👎 Bad**: Poor quality, misleading, or inaccurate
- **🚫 Skip**: Good quality but not relevant to your interests

Your ratings help improve future recommendations by adjusting source quality scores.

### Adding New Feed Sources

To add new RSS feeds:

1. Add feed info to `scripts/seed_news_feeds.py`
2. Run: `uv run python scripts/seed_news_feeds.py`
3. Or add directly via database:
   ```python
   feed = FeedSource(
       name="Source Name",
       url="https://example.com/feed.xml",
       description="Brief description",
       is_active=True,
       fetch_interval_hours=6,
       quality_score=1.0,
   )
   ```

### Manual Feed Fetch

To manually trigger a feed fetch:

```bash
uv run python scripts/test_fetch_news.py
```

## Scheduler

The news fetcher runs automatically every 6 hours via APScheduler:

- Started when the FastAPI backend starts
- Runs in the background without blocking requests
- Logs fetch results to console
- Gracefully shuts down when backend stops

## Database Schema

**feed_sources**:
- `id`, `name`, `url`, `description`
- `is_active`, `fetch_interval_hours`
- `last_fetched_at`, `quality_score`

**articles**:
- `id`, `feed_source_id`, `title`, `url`
- `summary`, `content`, `author`
- `published_at`, `fetched_at`, `keywords`

**article_interactions**:
- `id`, `user_id`, `article_id`
- `is_read`, `rating`
- `read_at`, `rated_at`
- Unique constraint: (user_id, article_id)

## Future Enhancements

Potential improvements for Phase 2:

1. **Embeddings & Deduplication**:
   - Use pgvector to detect duplicate articles across sources
   - Semantic similarity clustering

2. **Personalized Ranking**:
   - Train models on user ratings
   - Personalized article recommendations

3. **Email Digests**:
   - Daily/weekly email summaries
   - Customizable digest preferences

4. **Advanced Filtering**:
   - Date range filters
   - Source selection
   - Keyword filtering

5. **RSS Feed Management UI**:
   - Add/remove feeds via frontend
   - Toggle feed active status
   - Adjust quality scores manually
