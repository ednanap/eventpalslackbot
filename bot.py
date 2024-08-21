import slack
import os
import ssl
from pathlib import Path
from dotenv import load_dotenv
from flask import Flask
from slackeventsapi import SlackEventAdapter
import openai
import logging
import pytesseract
from PIL import Image, UnidentifiedImageError
from io import BytesIO
import requests
import re

env_path = Path('.') / '.env'
load_dotenv(dotenv_path=env_path)
print("API Key first:",os.environ['OPEN_API_KEY'])

logging.basicConfig(level=logging.DEBUG)

app= Flask(__name__)
slack_events_adapter = SlackEventAdapter(os.environ['SLACK_SIGNING_SECRET'], "/slack/events", app)
ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE
client = slack.WebClient(token=os.environ['SLACK_TOKEN'], ssl=ssl_context)
BOT_ID=client.api_call("auth.test")['user_id']
 
openai.api_key = os.environ['OPEN_API_KEY']
print("API Key second:", openai.api_key)

user_profiles = {}
welcome_messages = {}
class WelcomeMessage:
    START_TEXT = {
        'type': 'section',
        'text': {
            'type': 'mrkdwn',
            'text': (
                'Welcome to this awesome channel! \n\n'
                'I am here to help with generating introduction emails based on business card information.'
                ' Just upload an image, or type `set profile:` followed by your profile info to get started'
            )
        }
    }

    DIVIDER = {'type': 'divider'}

    def __init__(self, channel):
        self.channel = channel
        self.icon_emoji = ':robot_face:'
        self.timestamp = ''
        self.completed = False

    def get_message(self):
        return {
            'ts': self.timestamp,
            'channel': self.channel,
            'username': 'Welcome Robot!',
            'icon_emoji': self.icon_emoji,
            'blocks': [
                self.START_TEXT,
                self.DIVIDER,
                self._get_reaction_task()
            ]
        }

    def _get_reaction_task(self):
        checkmark = ':white_check_mark:'
        if not self.completed:
            checkmark = ':white_large_square:'

        text = f'{checkmark} *React to this message!*'

        return {'type': 'section', 'text': {'type': 'mrkdwn', 'text': text}}


def send_welcome_message(channel, user):
    if channel not in welcome_messages:
        welcome_messages[channel] = {}

    if user in welcome_messages[channel]:
        return

    welcome = WelcomeMessage(channel)
    message = welcome.get_message()
    response = client.chat_postMessage(**message)
    welcome.timestamp = response['ts']

    welcome_messages[channel][user] = welcome


def extract_text_from_image(image):
    text = pytesseract.image_to_string(image)
    return text

def extract_information_from_text(text):
    prompt = f"Extract the name, company name, and email address from the following text: {text} and parse it into a dictionary"
    response = openai.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=200,
        temperature=0.7
    )
    information = response.choices[0].message.content
    return information

def draft_introduction_email(company_profile, extracted_user_info):
    prompt = f"""
    Draft an introduction email to the person in the following information: {extracted_user_info}.
    The email should include my information from the following company profile: {company_profile}.
    The email should be professional and friendly.
    """
    
    response = openai.chat.completions.create(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": prompt}],
    max_tokens=200,
    temperature=0.7
    )
    email_text = response.choices[0].message.content
    return email_text

def fetch_and_open_image(image_url):
    try:
        headers = {'Authorization': 'Bearer ' + os.environ['SLACK_TOKEN']}
        response = requests.get(image_url, headers=headers)

        # Debugging information
        print(f"Response status code: {response.status_code}")
        print(f"Response headers: {response.headers}")
        content_type = response.headers.get('Content-Type')
        print(f"Content-Type: {content_type}")

        if response.status_code != 200:
            raise ValueError(f"Failed to fetch image. Status code: {response.status_code}")

        if not content_type.startswith('image'):
            raise ValueError(f"URL does not point to an image. Content-Type: {content_type}")

        image_bytes = BytesIO(response.content)
        image = Image.open(image_bytes)
        return image
    except UnidentifiedImageError:
        print("Cannot identify image file. The file may be corrupted or in an unsupported format.")
    except Exception as e:
        print(f"An error occurred: {str(e)}")

# @app.route('/')
# def home():
    # email_draft = draft_introduction_email(company_profile, extracted_user_info)
    # return f"<pre>{email_draft}</pre>"
# Event listener for when the bot joins a channel
@slack_events_adapter.on('bot_joined_channel')
def bot_joined_channel(payload):
    event = payload.get('event', {})
    channel_id = event.get('channel')
    
    # Send a welcome message to the entire channel
    welcome = WelcomeMessage(channel=channel_id)
    message = welcome.get_message()
    response = client.chat_postMessage(**message)
    welcome.timestamp = response['ts']

    # Track that the welcome message was sent for the bot in this channel
    if channel_id not in welcome_messages:
        welcome_messages[channel_id] = {}
    welcome_messages[channel_id]['bot'] = welcome


# Event listener for first-time user interaction
@slack_events_adapter.on('message')
def handle_message(payload):
    event = payload.get('event', {})
    channel_id = event.get('channel')
    user_id = event.get('user')

    # If it's a bot message or we already have a record of interacting with the user, do nothing
    if 'bot_id' in event or user_id in welcome_messages.get(channel_id, {}):
        return

    # If it's the first time interacting with this user in the channel, send a welcome message
    welcome = WelcomeMessage(channel=channel_id)
    message = welcome.get_message()
    response = client.chat_postMessage(**message)
    welcome.timestamp = response['ts']

    # Track that the welcome message was sent to the user
    if channel_id not in welcome_messages:
        welcome_messages[channel_id] = {}
    welcome_messages[channel_id][user_id] = welcome


# # Event handler for messages
def extract_profile_from_text(profile_text):
    # Define a simple regex to match key pieces of information
    name_pattern = re.search(r"Name:\s*(.*)", profile_text)
    company_pattern = re.search(r"Company:\s*(.*)", profile_text)
    email_pattern = re.search(r"Email:\s*(.*)", profile_text)
    phone_pattern = re.search(r"Phone:\s*(.*)", profile_text)

    # Build the user profile dictionary from extracted values
    user_profile = {
        "myName": name_pattern.group(1) if name_pattern else None,
        "companyName": company_pattern.group(1) if company_pattern else None,
        "email": email_pattern.group(1) if email_pattern else None,
        "phone": phone_pattern.group(1) if phone_pattern else None
    }

    return user_profile


@slack_events_adapter.on('message')
def message(payload):
    event=payload.get('event',{})
    channel_id=event.get('channel')
    user_id= event.get('user')
    text = event.get('text')
    attachments = event.get('files', [])
    if BOT_ID != user_id:
        if text.startswith("set profile:"):
            profile_info = text[len("set profile:"):].strip()
            user_profile = extract_profile_from_text(profile_info)
            try:
                if user_profile.get("myName") and user_profile.get("companyName"):
                    user_profiles[user_id] = user_profile
                    client.chat_postMessage(channel=channel_id, text="Profile set successfully!")
                else:
                    client.chat_postMessage(channel=channel_id, text="Failed to set profile.")
            except:
                client.chat_postMessage(channel=channel_id, text="Failed to set profile. Please provide a valid dictionary format.")
        elif text.startswith("generate email:"):
            if user_id in user_profiles:
                extracted_info = text[len("generate email:"):].strip()
                try:
                    extracted_user_info = eval(extracted_info)
                    email_draft = draft_introduction_email(user_profiles[user_id], extracted_user_info)
                    client.chat_postMessage(channel=channel_id, text=email_draft)
                except:
                    client.chat_postMessage(channel=channel_id, text="Failed to generate email. Please provide a valid dictionary format for the user info.")
            else:
                client.chat_postMessage(channel=channel_id, text="Please set a profile first.")
        elif attachments:
                for attachment in attachments:
                    if 'url_private' in attachment:  # Check for the URL of the image
                        image_url = attachment['url_private']
                        image = fetch_and_open_image(image_url)
                        if image:
                            text_from_image = extract_text_from_image(image)
                            extracted_info = extract_information_from_text(text_from_image)
                            email_draft = draft_introduction_email(user_profiles[user_id], extracted_info)
                            print('************')
                            try:
                                    client.chat_postMessage(channel=channel_id, text=email_draft)
                            except:
                                    client.chat_postMessage(channel=channel_id, text="Failed to generate email. Please provide a valid dictionary format for the user info.")
                                    client.chat_postMessage(channel=channel_id, text="Extracted text: " + text_from_image)
        else:
                client.chat_postMessage(channel=channel_id, text=text)
                
# @app.event("app_mention")
# def handle_message(event_data):
    # message = event_data["event"]
    # if "text" in message and "generate email" in message["text"].lower():
# email_draft = draft_introduction_email(company_profile, extracted_user_info)
# client.chat_postMessage(channel='#testslackbot2', text=email_draft)


if __name__ == "__main__":
    app.run(port=3000,debug=True)

