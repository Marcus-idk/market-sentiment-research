# Trading Bot V1 Requirements

## Project Goal
Build an automated trading bot that leverages LLMs for fundamental analysis to gain an edge over retail traders. The bot will monitor existing holdings and provide hold/sell recommendations every 30 minutes.

## Core Strategy
- **Target Competition**: Retail traders (not institutional HFT firms)
- **Edge**: LLM analyzing hundreds of sources 24/7 vs manual traders reading 2-3 sources
- **V1 Scope**: Monitor existing positions only (no new trade discovery)

## Data Sources (6 APIs)

### Price and News Data
- **Finnhub** (Primary): Stock prices + financial news
- **Polygon.io** (Backup): Price data + news when Finnhub fails
- **RSS Feeds** (Always-on): Unlimited news backup source

### Crowd Sentiment Analysis  
- **Reddit API** (via PRAW): Retail trader sentiment and discussions
- **X/Twitter API**: Real-time social sentiment and trending topics

### Official Company Data
- **SEC EDGAR**: Earnings reports, insider trading, official filings

## LLM Processing Architecture

### Multi-Agent Approach
```
Raw Data → Specialized LLM Agents → Final Decision Agent → User
```

### Agent Roles
1. **News Analyst LLM**: Processes Finnhub + RSS financial news
2. **Sentiment Analyst LLM**: Analyzes Reddit + X social sentiment  
3. **SEC Filings Analyst LLM**: Reviews EDGAR official company data
4. **Head Trader LLM**: Synthesizes all data + current holdings for final decision

### LLM Selection
- **Gemini 2.5 Flash**: Cost-effective for the 3 specialist analyst roles
- **GPT-5**: Premium model for final trading decisions

## Technical Stack
- **Python**: Best financial libraries, all APIs have Python SDKs
- **GitHub Actions**: Free scheduling and execution
- **Storage**: Results append to file in GitHub repo

## Output Format
- **Frequency**: Every 30 minutes during market hours
- **Content**: Holdings analysis + News/Sentiment/SEC summaries + HOLD/SELL recommendations

## Cost & Risk
- **Cost**: ~$10-30/month (API calls + LLM usage)
- **Risk Management**: No actual trade execution, recommendations only
- **Success Metric**: Beat buy-and-hold strategy