import os
import re
import tempfile
import requests
import arxiv
from slack_bolt import App

# Environment variables:
# SLACK_BOT_TOKEN, SLACK_SIGNING_SECRET
app = App(
    token=str(os.environ.get("SLACK_BOT_TOKEN")),
    signing_secret=str(os.environ.get("SLACK_SIGNING_TOKEN"))
)

# Regex to detect arXiv links (both abs and pdf)
ARXIV_REGEX = r"https?://arxiv\.org/(?:abs|pdf)/(\d{4}\.\d{5}(?:v\d+)?)(?:\.pdf)?"

def fetch_arxiv_info(arxiv_id):
    """Fetch paper metadata from arXiv."""
    search = arxiv.Search(id_list=[arxiv_id])
    result = next(search.results())
    return {
        "title": result.title,
        "authors": [a.name for a in result.authors],
        "summary": result.summary.strip(),
        "pdf_url": result.pdf_url
    }

def download_pdf(pdf_url):
    """Download PDF to a temporary file."""
    response = requests.get(pdf_url)
    response.raise_for_status()
    tmp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    tmp_file.write(response.content)
    tmp_file.close()
    return tmp_file.name

@app.event("message")
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

        except Exception as e:
            say(f"Error: {e}")

if __name__ == "__main__":
    app.start(port=int(os.environ.get("PORT", 3000)))
