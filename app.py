import os
import re
import tempfile
import requests
import arxiv
import json
from flask import Flask, request
from slack_bolt import App
from slack_bolt.adapter.flask import SlackRequestHandler
from slack_sdk.errors import SlackApiError

# Regex to detect arXiv links (both abs and pdf)
ARXIV_REGEX = r"https?://arxiv\.org/(?:abs|pdf)/(\d{4}\.\d{5}(?:v\d+)?)(?:\.pdf)?"

# Create the Slack app (Bolt)
slack_app = App(
    token=os.environ.get("SLACK_BOT_TOKEN"),
    signing_secret=os.environ.get("SLACK_SIGNING_TOKEN")
)

# Flask app
flask_app = Flask(__name__)
handler = SlackRequestHandler(slack_app)


def fetch_arxiv_info(arxiv_id):
    """Fetch paper metadata from arXiv."""
    client = arxiv.Client()
    search = arxiv.Search(id_list=[arxiv_id])
    result = next(client.results(search))
    return {
        "title": result.title,
        "authors": [a.name for a in result.authors],
        "summary": result.summary.strip(),
        "pdf_url": result.pdf_url
    }


def download_pdf(pdf_url):
    """Download PDF to a temporary file."""
    response = requests.get(pdf_url, timeout=30)
    response.raise_for_status()
    tmp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    tmp_file.write(response.content)
    tmp_file.close()
    return tmp_file.name


def chat_with_gemini(message_text):
    """Send a message to Google Gemini and return the response."""
    gemini_api_key = os.environ.get("GEMINI_API_KEY")
    
    if not gemini_api_key:
        return "Error: Gemini API key not configured. Please set the GEMINI_API_KEY environment variable."
    
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={gemini_api_key}"
    
    headers = {
        "Content-Type": "application/json"
    }
    
    payload = {
        "contents": [{
            "parts": [{
                "text": f"You are a helpful assistant in a Slack channel for academics. Be informative, clear, accurate, and friendly. User message: {message_text}"
            }]
        }],
        "generationConfig": {
            "temperature": 0.7,
            "topK": 1,
            "topP": 1,
            "maxOutputTokens": 32768,
            "stopSequences": []
        },
        "safetySettings": [
            {
                "category": "HARM_CATEGORY_HARASSMENT",
                "threshold": "BLOCK_MEDIUM_AND_ABOVE"
            },
            {
                "category": "HARM_CATEGORY_HATE_SPEECH",
                "threshold": "BLOCK_MEDIUM_AND_ABOVE"
            },
            {
                "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
                "threshold": "BLOCK_MEDIUM_AND_ABOVE"
            },
            {
                "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
                "threshold": "BLOCK_MEDIUM_AND_ABOVE"
            }
        ]
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        
        if response.status_code == 200:
            result = response.json()
            if "candidates" in result and len(result["candidates"]) > 0:
                return result["candidates"][0]["content"]["parts"][0]["text"].strip()
            else:
                return "Sorry, I couldn't generate a response."
        else:
            return f"Sorry, I encountered an error (status: {response.status_code}). Please try again later."
            
    except requests.exceptions.Timeout:
        return "Sorry, the request timed out. Please try again."
    except Exception as e:
        return f"Sorry, I encountered an error: {str(e)}"


@slack_app.event("app_mention")
def handle_app_mention_events(body, say, client):
    """Handle @mentions in public channels with Gemini."""
    event = body.get("event", {})
    text = event.get("text", "")
    channel = event.get("channel")
    
    # Remove the bot mention from the text
    # Slack mentions look like <@U1234567890>
    clean_text = re.sub(r'<@[A-Z0-9]+>', '', text).strip()
    
    if clean_text:
        try:
            # Get response from Gemini
            gemini_response = chat_with_gemini(clean_text)
            
            # Reply in thread if the original message was in a thread
            thread_ts = event.get("thread_ts") or event.get("ts")
            
            # Post the response
            say(
                text=gemini_response,
                thread_ts=thread_ts
            )
            
        except Exception as e:
            say(f"Sorry, I encountered an error: {str(e)}")
    else:
        say("Hi! How can I help you today?")


@slack_app.event("message")
def handle_message_events(body, say, client):
    text = body.get("event", {}).get("text", "")
    match = re.search(ARXIV_REGEX, text)
    if match:
        arxiv_id = match.group(1)
        try:
            info = fetch_arxiv_info(arxiv_id)
            pdf_path = download_pdf(info["pdf_url"])

            # Post paper details
            say(f"*{info['title']}*\n"
                f"Authors: {', '.join(info['authors'])}\n"
                f"Abstract: {info['summary'][:1000]}...")

            # Upload the PDF
            client.files_upload_v2(
                channel=body["event"]["channel"],
                file=pdf_path,
                title=f"{info['title']}.pdf"
            )
        except SlackApiError as e:
            say(f"Error uploading file: {e.response['error']}")
        except (requests.RequestException, arxiv.ArxivError) as e:
            say(f"Error fetching arXiv paper: {e}")
        except Exception as e:
            say(f"Unexpected error: {e}")


# Slack events endpoint
@flask_app.route("/slack/events", methods=["POST"])
def slack_events():
    return handler.handle(request)


if __name__ == "__main__":
    flask_app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 3000)))
