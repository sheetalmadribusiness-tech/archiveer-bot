import praw
import json
import csv
import os
from datetime import datetime
import time

from config import (
    REDDIT_CLIENT_ID,
    REDDIT_CLIENT_SECRET,
    REDDIT_USER_AGENT,
    SUBREDDIT_NAME,
    LIMIT,
    INCLUDE_COMMENTS,
    OUTPUT_DIR,
)

reddit = praw.Reddit(
    client_id=REDDIT_CLIENT_ID,
    client_secret=REDDIT_CLIENT_SECRET,
    user_agent=REDDIT_USER_AGENT,
)


def archive_comments(submission):
    submission.comments.replace_more(limit=0)
    comments = []
    for comment in submission.comments.list():
        comments.append({
            "id": comment.id,
            "author": str(comment.author),
            "body": comment.body,
            "score": comment.score,
            "created_utc": datetime.utcfromtimestamp(comment.created_utc).isoformat(),
            "parent_id": comment.parent_id,
        })
    return comments


def archive_subreddit(subreddit_name, limit=1000):
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    subreddit = reddit.subreddit(subreddit_name)

    posts = []
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    print(f"Archiving r/{subreddit_name} ...")

    for submission in subreddit.new(limit=limit):
        post = {
            "id": submission.id,
            "title": submission.title,
            "author": str(submission.author),
            "score": submission.score,
            "upvote_ratio": submission.upvote_ratio,
            "url": submission.url,
            "selftext": submission.selftext,
            "num_comments": submission.num_comments,
            "created_utc": datetime.utcfromtimestamp(submission.created_utc).isoformat(),
            "is_self": submission.is_self,
            "flair": submission.link_flair_text,
            "permalink": f"https://reddit.com{submission.permalink}",
        }

        if INCLUDE_COMMENTS:
            post["comments"] = archive_comments(submission)
            time.sleep(0.3)

        posts.append(post)
        print(f"  [{len(posts)}] {submission.title[:70]}")
        time.sleep(0.1)

    json_path = os.path.join(OUTPUT_DIR, f"{subreddit_name}_{timestamp}.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(posts, f, ensure_ascii=False, indent=2)

    csv_path = os.path.join(OUTPUT_DIR, f"{subreddit_name}_{timestamp}.csv")
    flat_keys = [k for k in posts[0].keys() if k != "comments"] if posts else []
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=flat_keys, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(posts)

    print(f"\nKlaar! {len(posts)} posts opgeslagen.")
    print(f"  JSON : {json_path}")
    print(f"  CSV  : {csv_path}")


if __name__ == "__main__":
    archive_subreddit(SUBREDDIT_NAME, limit=LIMIT)
