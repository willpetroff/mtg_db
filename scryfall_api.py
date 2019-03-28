import requests
import models
import json
import csv

from datetime import datetime
from time import sleep

# https://api.scryfall.com

class ScryfallAPI(object):

    _BASE_URL = "https://api.scryfall.com"

    def __init__(self, auth_key=None, grant_key=''):
        self.auth_key = auth_key
        self.grant_key = grant_key
    
    def get_card_multiverse(self, multiverse_id):
        target_url = "{}/cards/multiverse/{}".format(self._BASE_URL, multiverse_id)
        try:
            resp = self._query(target_url)
        except (requests.HTTPError, requests.ConnectTimeout) as e:
            err = models.Errors()
            err.add_error("Card {} not found".format(multiverse_id), path="SCRYFALL_API", action="GET_CARD_MULTIVERSE")
            return None
        card = Card(json.loads(resp))
        # for key, value in card.items():
        #     print(key, value)
        return card

    @staticmethod
    def _query(target):
        try:
            r = requests.get(target, timeout=10, allow_redirects=False)
        except requests.exceptions.Timeout:
            raise requests.ConnectTimeout
        if r.status_code != 200:
            if r.status_code == 429:
                print('Request Overload, Pausing Queries')
                sleep(10)
            raise requests.HTTPError
        return r.text


class Card(object):
    
    def __init__(self, response_json):
        for key, value in response_json.items():
            self.__setattr__(key, value)

