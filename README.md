# slack-academic-bot
A slack bot for mathematician

## How to deploy the bot to slack
1. Register a [fly.io](https://fly.io/) account. Hobby account would be enough. 
2. Install flyctl: https://fly.io/docs/hands-on/install-flyctl/
3. Clone the bot and run 
	```
	flyctl launch
	```
	It will create the tmol file.
4. Then just 
	```
	flyctl deploy
	```
   You have to set the environment variables (``SLACK_EVENTS_TOKEN``, ``SLACK_TOKEN``, ``OPENAI_API``) as secrets through flyctl.
