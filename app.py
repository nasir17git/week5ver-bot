import logging
import os
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

app = App(
    token=os.environ["SLACK_BOT_TOKEN"],
    signing_secret=os.environ["SLACK_SIGNING_SECRET"],
)

from slack_list.client import SlackListClient
from handlers.commands import register_commands
from handlers.actions import register_actions
from scheduler import create_scheduler

list_client = SlackListClient(app.client)
register_commands(app)
register_actions(app, list_client)

if __name__ == "__main__":
    scheduler = create_scheduler(app.client)
    scheduler.start()

    print("Starting Slack bot...")
    handler = SocketModeHandler(app, os.environ["SLACK_APP_TOKEN"])
    handler.start()
