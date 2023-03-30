import os
import logging
from flask import Flask
from slack import WebClient
from slackeventsapi import SlackEventAdapter
from arxivbot import ArxivBot
import urllib.request

import re
import time


# Initialize a Flask app to host the events adapter
app = Flask(__name__)
# Create an events adapter and register it to an endpoint in the slack app for event injestion.
slack_events_adapter = SlackEventAdapter(os.environ.get("SLACK_EVENTS_TOKEN"), "/slack/events", app)


# Initialize a Web API client
slack_web_client = WebClient(token=os.environ.get("SLACK_TOKEN"))


preprints = set()
preprint_hist = []


# When a 'message' event is detected by the events adapter, forward that payload
# to this function.
@slack_events_adapter.on("message")
def message(payload):
    # Get the event data from the payload
    event = payload.get("event", {})

    user = event.get("bot_id")

    if user is not None:
        return

    # Get the text from the event that came through
    text = event.get("text")   

    # Check and see if the activation phrase was in the text of the message.
    # If so, execute the code to flip a coin.
    if "https://arxiv.org/" in text.lower() and len(text) < 50:
        print(text)
        print("\n\n\n\n\n\n\n\n")
        # Since the activation phrase was met, get the channel ID that the event
        # was executed on

        addr = text.lower().find("<https://arxiv.org/")+1
        addr = text.lower()[addr: text.lower().find(">")]

        channel = event.get("channel")

        arxiv_bot = ArxivBot(channel)

        # Get the onboarding message payload
        message = arxiv_bot.get_message_payload(addr)

        download_link = arxiv_bot.extract_pdf_link(addr)

        unique_id = "".join(re.findall(r'\d+', download_link))
        file_path = "./data/"+unique_id + ".pdf"

        urllib.request.urlretrieve(download_link, file_path)

        if unique_id in preprints:
            return

        else:
            preprints.add(unique_id)
            preprint_hist.append(unique_id)

            with open(file_path, "rb"):
                slack_web_client.files_upload(
                    channels=channel,
                    file=file_path,
                    title=unique_id+".pdf",
                    filetype='pdf'
                )

            # Post the onboarding message in Slack
            slack_web_client.chat_postMessage(**message)

            if len(preprint_hist) > 20:
                to_delete = len(preprint_hist) - 20
                for i in range(to_delete):
                    preprints.remove(preprint_hist[i])
                    preprint_hist.pop(0)

if __name__ == "__main__":
    # Create the logging object
    logger = logging.getLogger()

    # Set the log level to DEBUG. This will increase verbosity of logging messages
    logger.setLevel(logging.DEBUG)

    # Add the StreamHandler as a logging handler
    logger.addHandler(logging.StreamHandler())
    # Run our app on our externally facing IP address on port 3000 instead of
    # running it on localhost, which is traditional for development.
    # app.run(host='127.0.0.1', port=3000)
    app.run(port=3000)
