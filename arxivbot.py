import sys

if sys.version_info[0] == 3:
    from urllib.request import urlopen
else:
    # Not Python 3 - today, it is most likely to be Python 2
    # But note that this might need an update when Python 4
    # might be around one day
    from urllib import urlopen

import os
import getopt
import re

import gzip


class ArxivBot:

    # Create a constant that contains the default text for the message

    # TODO: needs to consider the reply here.
    ARXIV_BLOCK = {
        "type": "section",
        "text": {
            "type": "mrkdwn",
            "text": (
                "*Arxiv Preprint Information*\n\n"
            ),
        },
    }

    # The constructor for the class. It takes the channel name as the a
    # parameter and then sets it as an instance variable
    def __init__(self, channel):
        self.channel = channel

    def _extract_abs_preprint(self, addr):

        flag = True
        
        if 'https://arxiv.org/abs/' in addr.lower():
            abstract = addr
        elif 'https://arxiv.org/pdf/' in addr.lower():
            components = addr.split(".")
            if components[-1] == "pdf":
                abstract = ".".join(components[0:-1]).replace("pdf","abs")
            else:
                abstract = addr.replace("pdf", "abs")
        else:
            flag = False

        if flag:
            text = self.get_info_from_addr(abstract)
        else:
            text = "link unrecognizable...\n"
        

        return {
            "type": "section", "text": {"type": "mrkdwn", "text": text}},


    def extract_pdf_link(self, addr):

        if 'https://arxiv.org/abs/' in addr.lower():
            link = addr.replace("abs", "pdf") + ".pdf"
        elif 'https://arxiv.org/pdf/' in addr.lower():
            components = addr.split(".")
            if components[-1] == "pdf":
                link = addr
            else:
                link = addr + ".pdf"
        else:
            link = ""

        return link


    def get_info_from_addr(self, addr):
        htmlObject = urlopen(addr)
        html = htmlObject.read().decode('utf-8')

        title = html[html.find(">Title:</span>")+14:]
        title = title[:title.find("</h1>")]

        authors = html[html.find(">Authors:</span>"):]
        authors = authors[authors.find("\">")+2:]
        authors = authors[:authors.find("</div>")]
        authors = re.sub('<[^>]*>', '', authors)
        authors = authors.replace("\n", "")

        abstract = html[html.find("Abstract:</span>")+17:]
        abstract = abstract[:abstract.find("</blockquote>")-1]

        return ":page_with_curl: "+"*"+title+"* "+"\n\n" + ":pencil2: "+"_"+authors+"_" + "\n\n"+":paperclip: "+abstract + "\n"


    # Craft and return the entire message payload as a dictionary.
    def get_message_payload(self , addr):
        return {
            "channel": self.channel,
            "blocks": [
                self.ARXIV_BLOCK,
                *self._extract_abs_preprint(addr),
            ],
        }
