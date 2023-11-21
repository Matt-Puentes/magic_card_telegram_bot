# Magic Card Telegram Bot

Simple telegram bot that responds to certain messages with information from the Scryfall API.

It responds to messages with words inside double square brackets `[[like this]]`. It runs a scryfall query on the string
inside the brackets- if it's a match for a card name, it sends a png of the card and it's Scryfall URL to the chat. If 
there is no match, it sends a list of scryfall-recommended possible matches.

Requires a Telegram HTTP API token, given via the `TELEGRAM_API_TOKEN` environment variable.