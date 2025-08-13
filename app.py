import os
import re
import tempfile
import requests
import arxiv
from flask import Flask, request
from slack_bolt import App
from slack_bolt.adapter.flask import SlackRequestHandler
from slack_sdk.errors import SlackApiError

# Regex to detect arXiv links (both abs and pdf)
ARXIV_REGEX = r"https?://arxiv\.org/(?:abs|pdf)/(\d{4}\.\d{5}(?:v\d+)?)(?:\.pdf)?"

# Create the Slack app (Bolt)
slack_app = App(
    token=os.environ.get("SLACK_BOT_TOKEN"),
    signing_secret=os.environ.get("SLACK_SIGNING_SECRET")
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
