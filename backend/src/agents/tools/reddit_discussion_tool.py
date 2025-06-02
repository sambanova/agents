import os
import praw
from datetime import datetime, timedelta
from typing import Dict, Any
from crewai.tools import tool

@tool
def reddit_discussion_tool(query: str, limit: int = 10) -> Dict[str, Any]:
    """
    Return up to `limit` post titles from subreddits about `query`.
    E.g. query="AAPL" or "Apple Inc".
    """
    client_id = os.getenv("REDDIT_CLIENT_ID","")
    client_secret = os.getenv("REDDIT_CLIENT_SECRET","")
    user_agent = os.getenv("REDDIT_USER_AGENT","my-reddit-bot")

    reddit = praw.Reddit(
        client_id=client_id,
        client_secret=client_secret,
        user_agent=user_agent
    )

    subreddits = ["wallstreetbets","stocks","investing"]
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=30)

    results = []
    for sub_name in subreddits:
        subreddit = reddit.subreddit(sub_name)
        for post in subreddit.search(query, sort="new", time_filter="month", limit=limit):
            post_date = datetime.utcfromtimestamp(post.created_utc)
            if start_date <= post_date <= end_date:
                results.append({
                    "title": post.title,
                    "created_utc": float(post.created_utc),
                    "subreddit": sub_name
                })

    return {"posts": results}
