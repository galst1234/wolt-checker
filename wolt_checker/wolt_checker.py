import json
import re
import time
import typing

import requests

with open("config.json") as config_file:
    config = json.load(config_file)
    LOCATION = config["location"]
SEARCH_QUERY_URL_FORMAT = f"https://restaurant-api.wolt.com/v1/pages/search?q={{query}}&{LOCATION}"
RESTAURANT_QUERY_URL_FORMAT = "https://restaurant-api.wolt.com/v3/venues/slug/{venue}"
TRACK_ID_REGEX = re.compile("venue-(.*)")
DEFAULT_PAGE_SIZE = 10


def get_venue_options(query: str) -> typing.List[typing.Dict]:
    response = requests.get(SEARCH_QUERY_URL_FORMAT.format(query=query))
    assert response, response.content
    first_selection = response.json()["sections"][0]
    if "items" in first_selection:
        return first_selection["items"]
    else:
        return []


def built_prompt(
        venues: typing.List[typing.Dict],
        page_num: typing.Optional[int] = None,
        page_size: int = DEFAULT_PAGE_SIZE,
        indentation: str = ""
) -> str:
    prompt = "Select venue:\n"
    should_paginate = page_num is not None
    suffix = ""

    if should_paginate:
        page_start = page_num * page_size
        page_end = page_start + page_size
        indexed_venues = enumerate(venues[page_start:page_end], start=page_start + 1)
        if page_num != 0:
            prompt = ""
        if page_end < len(venues):
            suffix = "\nIf you can't find your venue here please reply \"next\""
    else:
        indexed_venues = enumerate(venues, start=1)

    for index, venue in indexed_venues:
        try:
            rating = venue['venue']['rating']['score']
        except KeyError:
            rating = "no rating"
        prompt += f"{indentation}{index}. {venue['title'].strip()} - {rating} - " \
                  f"{venue['venue']['short_description'].strip()}\n"

    prompt += suffix
    return prompt


def prompt_venue_selection(venues: typing.List[typing.Dict]) -> typing.Dict:
    prompt = built_prompt(venues=venues, indentation="\t")
    prompt += "\nSelection: "
    selection = int(input(prompt))
    return venues[selection - 1]


def is_venue_online(venue: typing.Dict) -> bool:
    venue_track_id = TRACK_ID_REGEX.match(venue["track_id"]).groups()[0]
    response = requests.get(RESTAURANT_QUERY_URL_FORMAT.format(venue=venue_track_id))
    assert response, response.content
    venue_info = response.json()["results"][0]
    return venue_info["online"] and venue_info["delivery_specs"]["delivery_enabled"]


def wait_for_venue_availability(venue: typing.Dict) -> None:
    is_online = is_venue_online(venue)
    while not is_online:
        print("Venue is offline, waiting a minute before checking again...")
        time.sleep(60)
        is_online = is_venue_online(venue)

    print("Venue is now online!")


def main():
    venues = get_venue_options(input("Enter venue search: "))
    venue = prompt_venue_selection(venues)
    wait_for_venue_availability(venue)


if __name__ == '__main__':
    main()
