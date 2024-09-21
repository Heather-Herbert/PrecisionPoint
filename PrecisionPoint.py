import feedparser
import requests
import json
from bs4 import BeautifulSoup
from dotenv import load_dotenv
import os
import logging
from wordpress_xmlrpc import Client, WordPressPost
from wordpress_xmlrpc.methods.posts import NewPost

# Load environment variables from .env file
load_dotenv()

# Fetch necessary secrets from .env
RSS_FEED_URL = os.getenv('RSS_FEED_URL')
WP_URL = os.getenv('WP_URL')
WP_USERNAME = os.getenv('WP_USERNAME')
WP_PASSWORD = os.getenv('WP_PASSWORD')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

if not all([RSS_FEED_URL, WP_URL, WP_USERNAME, WP_PASSWORD, OPENAI_API_KEY]):
    raise Exception("Ensure RSS_FEED_URL, WP_URL, WP_USERNAME, WP_PASSWORD, and OPENAI_API_KEY are set in the .env file")

# Setup logging
logging.basicConfig(filename='rss_feed_processing.log',
                    level=logging.INFO,
                    format='%(asctime)s %(levelname)s: %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S')

# Function to fetch and parse the RSS feed
def fetch_rss_feed(url):
    try:
        return feedparser.parse(url)
    except Exception as e:
        logging.error(f"Error fetching RSS feed: {e}")
        return None

# Function to fetch the content of the URL and extract text
def fetch_and_extract_text(url):
    try:
        response = requests.get(url)
        soup = BeautifulSoup(response.content, 'html.parser')
        # Extract text from the main body (you can adjust this to fit your needs)
        paragraphs = soup.find_all('p')
        text = '\n'.join([para.get_text() for para in paragraphs])
        return text
    except Exception as e:
        logging.error(f"Error fetching URL content {url}: {e}")
        return None

# Function to send text to ChatGPT for processing
def process_with_chatgpt(article_title, article_text):
    url = "https://api.openai.com/v1/chat/completions"
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {OPENAI_API_KEY}'
    }

    # ChatGPT System Prompt and User Prompt
    payload = {
        "model": "gpt-4",
        "messages": [
            {
                "role": "system",
                "content": "You are a highly accurate and knowledgeable fact-checker. Your primary function is to verify the truthfulness of statements, claims, or information presented to you."
            },
            {
                "role": "user",
                "content": f"Please fact-check the following article titled '{article_title}': {article_text}"
            }
        ]
    }

    try:
        response = requests.post(url, headers=headers, data=json.dumps(payload))
        response_data = response.json()
        fact_checked_text = response_data['choices'][0]['message']['content']
        return fact_checked_text
    except Exception as e:
        logging.error(f"Error processing with ChatGPT for article '{article_title}': {e}")
        return None

# Function to post content to WordPress
def post_to_wordpress(title, content):
    try:
        client = Client(WP_URL, WP_USERNAME, WP_PASSWORD)
        post = WordPressPost()
        post.title = title
        post.content = content
        post.post_status = 'publish'  # Change to 'draft' if you don't want to publish immediately
        client.call(NewPost(post))
        logging.info(f"Successfully posted to WordPress: {title}")
    except Exception as e:
        logging.error(f"Error posting to WordPress for article '{title}': {e}")

# Function to process the RSS feed items
def process_feed(feed_url, output_file):
    feed = fetch_rss_feed(feed_url)
    if feed is None:
        logging.error("Feed could not be fetched.")
        return

    with open(output_file, 'w', encoding='utf-8') as f:
        for entry in feed.entries:
            title = entry.title
            link = entry.link
            logging.info(f"Processing: {title}")

            # Fetch and process the article text from the URL
            text = fetch_and_extract_text(link)
            if text:
                # Process the text with ChatGPT
                processed_text = process_with_chatgpt(title, text)
                if processed_text:
                    # Write to the output file
                    f.write(f"Title: {title}\n")
                    f.write(f"URL: {link}\n")
                    f.write(f"Fact-Checked Content:\n{processed_text}\n")
                    f.write("="*80 + "\n")  # Separator for each article

                    # Post to WordPress
                    post_to_wordpress(title, processed_text)

    logging.info("Feed processing completed.")

# Define the output file
output_file = 'output.txt'

# Process the feed and write to the output file, then post to WordPress
process_feed(RSS_FEED_URL, output_file)

logging.info("Script execution finished.")
