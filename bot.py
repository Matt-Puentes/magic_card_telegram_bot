import logging
import os
import re
from typing import NamedTuple
import requests

from telegram import InputMediaPhoto, Update, constants
from telegram.ext import Application, filters, MessageHandler, CallbackContext

logger = logging.getLogger(__name__)


async def handle_message(update: Update, context: CallbackContext) -> None:
    # Skip updates without messages (Edits to old messages, etc) or messages without text (images, audio, etc).
    if update.message is None or update.message.text is None:
        return

    matches = re.findall(r"\[\[([^\]]+)\]\]", update.message.text)
    logger.info(f"Cards found: {matches}")
    for match in matches:
        response = None
        try:
            response = await get_card_info(match)
        except ScryFallException as e:
            logger.info(f"ScryFall Query returned error: {e}")
            await context.bot.send_message(
                update.message.chat_id,
                f"Could not parse ScryFall API response {e.scryfall_response}",
            )
        except KeyError as e:
            logger.info(f"KeyError during ScryFall Query: {e}")
            await context.bot.send_message(
                update.message.chat_id,
                f"Bot Encountered error. Keyerror: {e}",
            )
        except Exception as e:
            logger.info(f"Exception during ScryFall Query: {e}")
            await context.bot.send_message(
                update.message.chat_id,
                f"Bot encountered error {e}",
            )

        if isinstance(response, Card):
            msg = f"Found Card {response.name}: {response.url}"
            if response.image is not None:
                msg += "No image found."
            await context.bot.send_photo(
                chat_id=update.message.chat_id,
                photo=response.image,
                caption=f"Found Card {response.name}: {response.url}",
                disable_notification=True,
            )
        if isinstance(response, CardWithFaces):
            await context.bot.send_media_group(
                chat_id=update.message.chat_id,
                media=[InputMediaPhoto(image_url) for image_url in response.images],
                caption=f"Found Card {response.name}: {response.url}",
                disable_notification=True,
            )
        if isinstance(response, CardNotFound):
            card_list = "\n".join([f"`{card}`" for card in response.other_card_names[:10]])
            msg = f"Cannot find card '{match}'."
            if response.other_card_names:
                msg += f"\nMaybe you meant one of these:\n{card_list}"
                other_results = response.num_results - len(response.other_card_names)
                if other_results > 0:
                    msg += f"\n({other_results} Other results)"
            await context.bot.send_message(
                update.message.chat_id,
                parse_mode=constants.ParseMode.MARKDOWN,
                text=msg,
                disable_notification=True,
            )


class Card(NamedTuple):
    name: str
    image: str | None
    url: str


class CardWithFaces(NamedTuple):
    name: str
    images: list[str]
    url: str


class CardNotFound(NamedTuple):
    name: str
    other_card_names: list[str]
    num_results: int


class ScryFallException(Exception):
    def __init__(self, scryfall_response):
        self.scryfall_response = scryfall_response


# Can respond with:
# 1) Card with single image and URL - send Message w/ image
# 2) Card with multiple images and URL - send MediaGroup w/ caption
# 3) Card not found, list of possible other names - send formatted message
async def get_card_info(card_name: str) -> Card | CardWithFaces | CardNotFound:
    name_query = requests.get(f"https://api.scryfall.com/cards/named", params={"exact": card_name})
    # Parse the response
    parsed_card = name_query.json()
    if parsed_card["object"] == "card":
        msg = f"Found Card {parsed_card['name']}: {parsed_card['scryfall_uri']}"
        if "image_uris" in parsed_card:
            # Single card, single photo
            return Card(parsed_card["name"], parsed_card["image_uris"]["png"], parsed_card["scryfall_uri"])
        elif "card_faces" in parsed_card:
            # Single card, multiple photos
            photos: list[str] = [face["image_uris"]["png"] for face in parsed_card["card_faces"]]
            return CardWithFaces(card_name, photos, parsed_card["scryfall_uri"])
        else:
            # Single card, no photos (this might be impossible?)
            return Card(parsed_card["name"], None, parsed_card["scryfall_uri"])
    elif parsed_card["object"] == "error":
        is_ambiguous = "type" in parsed_card and parsed_card["type"] == "ambiguous"
        not_found = "code" in parsed_card and parsed_card["code"] == "not_found"
        if is_ambiguous or not_found:
            # If the error we got was that the card wasn't found (or that the name wasn't specific enough), we'll get a
            #  list of what cards they could have meant and return that instead.
            search_query = requests.get(f"https://api.scryfall.com/cards/search?q=${card_name}")
            parsed_search = search_query.json()
            if parsed_search["object"] == "list" and "data" in parsed_search and len(parsed_search["data"]) > 0:
                # Get a list of the first 10 possible card names
                return CardNotFound(
                    card_name,
                    [card["name"] for card in parsed_search["data"][:10]],
                    int(parsed_search["total_cards"]) if "total_cards" in parsed_search else 0,
                )
            # No matching cards
            return CardNotFound(card_name, [], 0)

    # If we can't parse the scryfall response raise an Exception
    raise ScryFallException(parsed_card)


def main() -> None:
    token = os.environ.get("TELEGRAM_API_TOKEN")
    if token is None:
        raise RuntimeError("Environment variable TELEGRAM_API_TOKEN not found")
    elif token == "NotSet":
        raise RuntimeError("Environment variable TELEGRAM_API_TOKEN found, but isn't initialized")
    app = Application.builder().token(token).build()

    # Register the handler with filter
    app.add_handler(MessageHandler(~filters.COMMAND, handle_message))

    # Start the Bot, run the bot until you press Ctrl-C
    app.run_polling()


if __name__ == "__main__":
    main()
