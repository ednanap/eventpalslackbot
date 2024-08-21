## EventPal

<img width="600" alt="Screenshot 2024-08-21 at 5 15 39 PM" src="https://github.com/user-attachments/assets/a750ebf7-de10-4d45-bff5-088b375c1f93">

EventPal is a Python-powered Slack bot designed to streamline business interactions by automating key tasks.
Leveraging the Slack API, EventPal extracts information from business cards and generates personalized introductory emails. 



# Requirements
- Python 3.x
- Slack API token
- OpenAI API key


Install the required dependencies:
pip install -r requirements.txt

Create a .env file:
In the root of your project directory, create a .env file and add your Slack API token and OpenAI API key:

- SLACK_BOT_TOKEN=xoxb-your-slack-bot-token
- OPENAI_API_KEY=your-openai-api-key

# Run the bot:
- python bot.py


Triggering the Bot: The bot will automatically respond when added to a Slack channel or when a user sends it a message
