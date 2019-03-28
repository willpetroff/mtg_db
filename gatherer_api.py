import requests
import models
import csv

from bs4 import BeautifulSoup
from datetime import datetime

# https://mtgjson.com/v4/docs.html

# Non-Traditional Reprints
# http://gatherer.wizards.com/Pages/Card/Details.aspx?multiverseid=85190


class MTGDataScraper(object):

    def __init__(self, multiverse_id=1):
        self.multiverse_id = multiverse_id

    def get_card_info_gatherer(self, multiverse_id=None, id_prefix=None, prefix_modifier_list=None, split_card=False,
                               update=False):
        split_card = split_card
        if not id_prefix:
            id_prefix = 'ctl00_ctl00_ctl00_MainContent_SubContent_SubContent_'
        if not prefix_modifier_list:
            prefix_modifier_list = ['ctl03_', 'ctl04_']
        if not multiverse_id:
            multiverse_id = self.multiverse_id
        target = "http://gatherer.wizards.com/Pages/Card/Details.aspx?multiverseid={}".format(multiverse_id)
        try:
            data = self._scrape(target=target)
        except (requests.HTTPError, requests.ConnectTimeout):
            if not models.BlankMultiverseID.query.filter_by(wotc_multiverse_id=multiverse_id).first():
                blank_id_record = models.BlankMultiverseID()
                blank_id_record.wotc_multiverse_id = multiverse_id
                blank_id_record.add_object(action="Add BlankMultiverseID {}".format(multiverse_id))
            return None
        parsed_page = BeautifulSoup(data, 'html.parser')
        if not split_card and not parsed_page.find('div', attrs={'id': id_prefix + 'nameRow'}):
            split_card = True
        if not split_card:
            card = self.generate_card_record(parsed_page, multiverse_id, id_prefix, update=update)
            return card
        else:
            cards = []
            for modifier in prefix_modifier_list:
                card = self.generate_card_record(parsed_page, multiverse_id, id_prefix + modifier, split_card=True,
                                                 update=update)
                cards.append(card)

    def get_card_set_info_gatherer(self, multiverse_id=None):
        if not multiverse_id:
            multiverse_id = self.multiverse_id
        target = "http://gatherer.wizards.com/Pages/Card/Printings.aspx?multiverseid={}".format(multiverse_id)

        data = self._scrape(target=target)
        parsed_page = BeautifulSoup(data, 'html.parser')
        print(parsed_page)

    def generate_card_record(self, parsed_page, multiverse_id, id_prefix, split_card=False, update=False):
        card_name = parsed_page.find('div', attrs={'id': id_prefix + 'nameRow'})
        if card_name:
            card_name = card_name.find('div', attrs={'class': 'value'}).text.strip()
        card_cmc = 0
        card_cost = parsed_page.find('div', attrs={'id': id_prefix + 'manaRow'})
        if card_cost:
            card_cost = card_cost.find('div', attrs={'id', 'value'}).find_all('img')
            card_cost = self._generate_cost_string(card_cost)
            card_cmc = self._generate_cmc(card_cost)
        card_types = parsed_page.find('div', attrs={'id': id_prefix + 'typeRow'})
        card_sub_types = None
        if card_types:
            card_types = card_types.find('div', attrs={'id', 'value'}).text.strip()
            if '—' in card_types:
                card_types, card_sub_types = [item_type.strip() for item_type in card_types.split('—')]
                card_types = [item.strip() for item in card_types.split()]
                card_sub_types = [item.strip() for item in card_sub_types.split()]
            else:
                card_types = [item.strip() for item in card_types.split()]
        card_oracle_text = parsed_page.find('div', attrs={'id': id_prefix + 'textRow'})
        if card_oracle_text:
            card_oracle_text = card_oracle_text.find('div', attrs={'id', 'value'}).find_all('div')
            # Replace image symbols with alt text
            for div in card_oracle_text:
                for img in div.find_all('img'):
                    img.replaceWith(img['alt'])
            card_oracle_text = '\n'.join([div.text.strip() for div in card_oracle_text])
        card_flavor_text = parsed_page.find('div', attrs={'id': id_prefix + 'flavorRow'})
        if card_flavor_text:
            card_flavor_text = card_flavor_text.find('div', attrs={'id', 'value'}).find_all('div')
            card_flavor_text = '\n'.join([div.text.strip() for div in card_flavor_text])
        card_power_toughness = parsed_page.find('div', attrs={'id': id_prefix + 'ptRow'})
        card_power = None
        card_toughness = None
        card_loyalty = None
        if card_power_toughness:
            card_power_toughness = card_power_toughness.find('div', attrs={'id', 'value'}).text.replace(' ', '')
            if '/' in card_power_toughness:
                card_power, card_toughness = card_power_toughness.split('/')
            else:
                if 'Plansewalker' in card_types:
                    card_loyalty = card_power_toughness
        card_set_rarity = parsed_page.find('div', attrs={'id': id_prefix + 'setRow'})
        card_set = None
        card_rarity = None
        if card_set_rarity:
            card_set_rarity = card_set_rarity.find('div', attrs={'id', 'value'}).find('img')['alt'].strip()
            card_set, card_rarity = card_set_rarity.split('(')
            card_set = card_set.strip()
            card_rarity = card_rarity.replace(')', '').strip()
        card_set_number = parsed_page.find('div', attrs={'id': id_prefix + 'numberRow'})
        if card_set_number:
            card_set_number = card_set_number.find('div', attrs={'id', 'value'}).text.strip()
            card_set_number.replace('a', '').replace('b', '')
        card_artist = parsed_page.find('div', attrs={'id': id_prefix + 'artistRow'})
        if card_artist:
            card_artist = card_artist.find('div', attrs={'id', 'value'}).text.strip()
        wotc_set = models.Set.query.filter_by(name=card_set).first()
        if not wotc_set:
            wotc_set = models.Set()
            wotc_set.name = card_set
            err = wotc_set.add_object()
            if err:
                print(multiverse_id, err)
                return False
        card = models.Card.query \
            .filter_by(card_name=card_name, set_id=wotc_set.set_id, card_set_number=card_set_number).first()
        if card and not update:
            return card
        if not card:
            card = models.Card()
        card.card_name = card_name
        card.wotc_id = multiverse_id
        card.card_oracle_text = card_oracle_text
        card.card_flavor_text = card_flavor_text
        card.card_rarity = card_rarity[0]
        card.card_power = card_power.strip() if card_power else None
        card.card_toughness = card_toughness.strip() if card_toughness else None
        card.card_loyalty = card_loyalty.strip() if card_loyalty else None
        card.card_display_cost = ' '.join(card_cost) if card_cost else None
        card.card_cmc = card_cmc
        card.card_type = ' '.join(card_types)
        card.card_sub_type = ' '.join(card_sub_types) if card_sub_types else None
        card.card_set_number = card_set_number
        card.card_artist = card_artist
        card.set_id = wotc_set.set_id
        card.card_split_card = split_card
        if not card.card_id:
            err = card.add_object()
        else:
            card.updated = datetime.utcnow()
            err = card.update_object()
        if err:
            print(multiverse_id, err)
            return False
        return card

    @staticmethod
    def _scrape(target, params=None):
        # print('In _scrape')
        # print(target)
        try:
            r = requests.get(target, params=params, timeout=10, allow_redirects=False)
        except requests.exceptions.Timeout:
            raise requests.ConnectTimeout
        if r.status_code != 200:
            # print(r.url)
            raise requests.HTTPError
        # print(r.text)
        return r.text

    @staticmethod
    def _capitalize_word(word_string, split_on=None, split_index=None):
        if word_string and type(word_string) == str:
            if split_on:
                word_string = word_string.split(split_on)
            if split_index:
                word_string = [word_string[:split_index], word_string[split_index:]]
            for index in range(len(word_string)):
                word_string = [i.capitalize for i in word_string[index]]
            join_string = '{}'.format(split_on) if split_on else ''
            return join_string.join(word_string)
        else:
            return ""

    @staticmethod
    def _generate_cmc(card_cost_components):
        cmc = 0
        for item in card_cost_components:
            try:
                cmc += int(item)
            except ValueError:
                if item == 'Variable Colorless':
                    cmc += 0
                else:
                    cmc += 1
        return cmc

    @staticmethod
    def _generate_cost_string(card_cost):
        replacement_dict = {
            'Black': 'B',
            'Blue': 'U',
            'Green': 'G',
            'Phyrexian Black': 'pB',
            'Phyrexian Blue': 'pU',
            'Phyrexian Green': 'pG',
            'Phyrexian Red': 'pR',
            'Phyrexian White': 'pW',
            'Red': 'R',
            'Variable Colorless': 'X',
            'Variable Cost': 'X',
            'White': 'W',
            'zero': 0,
            'one': 1,
            'two': 2,
            'three': 3,
            'four': 4,
            'five': 5,
            'six': 6,
            'seven': 7,
            'eight': 8,
            'nine': 9,
            'ten': 10,
            'eleven': 11,
            'twelve': 12
        }
        cost_string = []
        for item in card_cost:
            if 'or' in item['alt']:
                substrings = []
                for substring in item['alt'].split(' or '):
                    try:
                        substrings.append(replacement_dict[substring])
                    except KeyError:
                        substrings.append(substring)
                cost_string.append('/'.join(substrings))
            else:
                try:
                    cost_string.append(replacement_dict[item['alt']])
                except KeyError:
                    cost_string.append(item['alt'])
        return cost_string


if __name__ == '__main__':
    with open('TCGplayer.csv', 'r') as csv_file:
        csv_reader = csv.reader(csv_file)
        csv_reader = sorted(csv_reader, key=lambda x: x[0], reverse=True)
        for row in csv_reader:
            print(row)

