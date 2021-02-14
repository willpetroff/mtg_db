import json
import re
import requests

from datetime import datetime, date
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy import select, case, and_

db = SQLAlchemy()

class BaseModel:
    def add_object(self, path=None, action=None, user_id=None, user_type=None, user_agent=None):
        try:
            self.created_by_id = user_id
        except AttributeError:
            print('error')
            pass
        try:
            db.session.add(self)
            db.session.commit()
        except Exception as e:
            e = str(e)
            db.session.rollback()
            new_error = Errors()
            new_error.add_error(e, path, action, user_id, user_type, user_agent)
            return e
        return False

    def update_object(self, path=None, action=None, user_id=None, user_type=None, user_agent=None):
        try:
            self.last_updated = datetime.utcnow()
            self.last_updated_id = user_id
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            e = str(e)
            new_error = Errors()
            new_error.add_error(e, path, action, user_id, user_type, user_agent)
            return e
        return False

    def delete_object(self, path=None, action=None, user_id=None, user_type=None, user_agent=None):
        try:
            db.session.delete(self)
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            e = str(e)
            new_error = Errors()
            new_error.add_error(e, path, action, user_id, user_type, user_agent)
            return e
        return False

    def serialize(self, *excluded_attributes, exclude_password=True):
        attribute_dict = {attr: str(getattr(self, attr)) for attr in self.__dict__.keys() if attr[0] != '_'}
        if exclude_password:
            try:
                del attribute_dict['password']
            except KeyError:
                pass
        for ex_attr in excluded_attributes:
            try:
                del attribute_dict[ex_attr]
            except KeyError:
                pass
        return attribute_dict

    def get(self, item):
        return getattr(self, item, None)

    def copy_attrs(self, model_to_copy):
        attribute_dict = {attr: getattr(model_to_copy, attr) for attr in model_to_copy.__dict__.keys()
                          if attr[0] != '_' and attr != 'created' and '_id' not in attr}
        for attr in attribute_dict:
            self.__setattr__(attr, getattr(model_to_copy, attr, None))


class Errors(db.Model, BaseModel):
    __tablename__ = "err"
    error_id = db.Column(db.Integer, primary_key=True)
    first_occurred = db.Column(db.DateTime)
    last_occurred = db.Column(db.DateTime)
    occurrences = db.Column(db.Integer, default=1)
    action = db.Column(db.String(255))
    url = db.Column(db.String(255))
    content = db.Column(db.Text)
    card_id = db.Column(db.Integer)
    user_id = db.Column(db.Integer)
    user_type = db.Column(db.String(10))
    user_agent = db.Column(db.String(10))

    def add_error(self, error, path=None, action=None, user_id=None, user_type=None, user_agent=None):
        error_exist = Errors.query.filter_by(content=error, url=path, action=action)
        if user_id:
            error_exist = error_exist.filter_by(user_id=user_id)
        if user_type:
            error_exist = error_exist.filter_by(user_type=user_type)
        if user_agent:
            error_exist = error_exist.filter_by(user_agent=user_agent)
        error_exist = error_exist.first()
        if error_exist:
            error_exist.occurrences += 1
            error_exist.last_occurred = datetime.utcnow()
            try:
                db.session.commit()
            except Exception as e:
                db.session.rollback()
                print(e)
            return True
        else:
            self.content = error
            self.url = path
            self.action = action
            self.user_id = user_id
            self.user_type = user_type
            self.first_occurred = datetime.utcnow()
            self.last_occurred = datetime.utcnow()
            self.user_agent = user_agent
            self.occurrences = 1
            try:
                db.session.add(self)
                db.session.commit()
            except Exception as e:
                print(e)
                db.session.rollback()
            return True


class BlankMultiverseID(db.Model, BaseModel):
    __tablename__ = 'blank_multiverse_id'
    blank_id = db.Column(db.Integer, primary_key=True)
    wotc_multiverse_id = db.Column(db.Integer)
    created = db.Column(db.DateTime, default=datetime.utcnow)


class Card(db.Model, BaseModel):
    __tablename__ = 'card'
    card_id = db.Column(db.Integer, primary_key=True)
    created = db.Column(db.DateTime, default=datetime.utcnow)
    updated = db.Column(db.DateTime)
    wotc_id = db.Column(db.Integer)  # multiverse_id
    tcg_player_id = db.Column(db.Integer)
    scryfall_id = db.Column(db.String(50))
    oracle_id = db.Column(db.String(50))
    card_draft_rating = db.Column(db.Numeric(6,3), default=0)
    card_name = db.Column(db.String(255))
    set_id = db.Column(db.Integer, db.ForeignKey('wotc_set.set_id', ondelete="CASCADE"))
    block_id = db.Column(db.Integer, db.ForeignKey('wotc_block.block_id'), default=None)
    card_rarity = db.Column(db.String(1))
    card_display_cost = db.Column(db.String(20))
    card_cmc = db.Column(db.Integer)
    card_type = db.Column(db.String(50))
    card_sub_type = db.Column(db.String(100))
    card_power = db.Column(db.String(10))
    card_toughness = db.Column(db.String(10))
    card_loyalty = db.Column(db.String(2))
    card_oracle_text = db.Column(db.Text)
    card_split_card = db.Column(db.Boolean, default=False)
    card_rating_wotc = db.Column(db.Numeric(3,2))
    card_rating_votes_wotc = db.Column(db.Integer)
    card_set_number = db.Column(db.Integer)
    card_flavor_text = db.Column(db.Text)
    card_artist = db.Column(db.String(100))
    has_foil = db.Column(db.Boolean, default=False)
    is_promo = db.Column(db.Boolean, default=False)
    is_reprint = db.Column(db.Boolean, default=False)
    is_reserved = db.Column(db.Boolean, default=False)
    value_last_updated = db.Column(db.Date, default=date.today)
    card_img_uri_normal = db.Column(db.String(255))
    card_img_uri_small = db.Column(db.String(255))

    card_set = db.relationship('Set', foreign_keys=[set_id])
    card_values = db.relationship('CardValue')

    @hybrid_property
    def value_reg(self):
        return self.card_values[-1].card_value_mid_current
        
    @value_reg.expression
    def value_reg(cls):
        return select([CardValue.card_value_mid_current]).where(and_(cls.card_id == CardValue.card_id, cls.value_last_updated <= CardValue.created)).alias('value_reg')

    @hybrid_property
    def value_foil(self):
        return self.card_values[-1].card_foil_value

    @value_reg.expression
    def value_foil(cls):
        return select([CardValue.card_foil_value]).where(and_(cls.card_id == CardValue.card_id, cls.value_last_updated <= CardValue.created)).alias('value_foil')

    def get_current_value(self, return_foil=False, cast_as_int=False):
        if not self.card_values:
            return return_non_price(cast_as_int)
        if return_foil:
            if self.card_values[-1].card_foil_value:
                return self.card_values[-1].card_foil_value
            else:
                return return_non_price(cast_as_int)
        if self.card_values[-1].card_value_mid_current:
            return self.card_values[-1].card_value_mid_current
        elif self.card_values[-1].card_foil_value:
            return self.card_values[-1].card_foil_value
        else:
            return return_non_price(cast_as_int)

    def get_card_img(self, url=None, scryfall=True, size='normal', refresh=False):
        if self.card_img_uri_normal and self.card_img_uri_small and not refresh:
            return self.get_correct_img_size(size)
        if not url and scryfall:
            url = "https://api.scryfall.com/cards/multiverse/{}".format(self.wotc_id)
        r = requests.get(url, allow_redirects=False)
        if r.status_code != 200:
            return False
        card = json.loads(r.text)
        if 'image_uris' in card.keys():
            self.card_img_uri_normal = card['image_uris']['normal']
            self.card_img_uri_small = card['image_uris']['small']
            err = self.update_object()
            if err:
                return card['image_uris']['normal']
        if 'card_faces' in card.keys():
            card = card['card_faces'][0]
            if 'image_uris' in card.keys():
                self.card_img_uri_normal = card['image_uris']['normal']
                self.card_img_uri_small = card['image_uris']['small']
                err = self.update_object()
                if err:
                    return card['image_uris']['normal']
        return self.get_correct_img_size(size)

    def get_correct_img_size(self, size):
        if size == 'normal':
            return self.card_img_uri_normal
        elif size == 'small':
            return self.card_img_uri_small
        return self.card_img_uri_normal

    def update_from_scryfall(self, scryfall_card_obj):
        # print(scryfall_card_obj.scryfall_uri)
        self.card_name = scryfall_card_obj.name
        self.wotc_id = scryfall_card_obj.multiverse_ids[0] if scryfall_card_obj.multiverse_ids else None
        if getattr(scryfall_card_obj, 'tcgplayer_id', None):
            self.tcg_player_id = scryfall_card_obj.tcgplayer_id
        self.scryfall_id = scryfall_card_obj.id
        self.oracle_id = scryfall_card_obj.oracle_id
        # Set Information
        wotc_set = Set.query.filter_by(wotc_code=scryfall_card_obj.set).first()
        if not wotc_set:
            return scryfall_card_obj.scryfall_uri
        self.set_id = wotc_set.set_id
        if getattr(scryfall_card_obj, 'oracle_text', None):
            self.card_oracle_text = scryfall_card_obj.oracle_text
        self.has_foil = scryfall_card_obj.foil
        self.card_display_cost = scryfall_card_obj.mana_cost.replace('{', '').replace('}', ' ').strip() if getattr(scryfall_card_obj, 'mana_cost', None) else None
        self.card_cmc = scryfall_card_obj.cmc
        if getattr(scryfall_card_obj, 'power', None):
            self.card_power = scryfall_card_obj.power
        if getattr(scryfall_card_obj, 'toughness', None):
            self.card_toughness = scryfall_card_obj.toughness
        if getattr(scryfall_card_obj, 'loyalty', None):
            self.card_loyalty = scryfall_card_obj.loyalty
        if '//' not in scryfall_card_obj.type_line:
            type_line = scryfall_card_obj.type_line.split(' — ')
            if len(type_line) > 1:
                self.card_type, self.card_sub_type = type_line
            elif len(type_line) == 1:
                self.card_type = type_line[0]
        else:
            type_line = scryfall_card_obj.type_line.split(' // ')[0].split(' — ')
            if len(type_line) > 1:
                self.card_type, self.card_sub_type = type_line
            elif len(type_line) == 1:
                self.card_type = type_line[0]
        if getattr(scryfall_card_obj, 'flavor_text', None):
            self.card_flavor_text = scryfall_card_obj.flavor_text
        self.card_rarity = scryfall_card_obj.rarity[0].upper() if scryfall_card_obj.rarity else None
        self.card_artist = scryfall_card_obj.artist
        if getattr(scryfall_card_obj, 'image_uris', None):
            self.card_img_uri_normal = scryfall_card_obj.image_uris['normal']
            self.card_img_uri_small = scryfall_card_obj.image_uris['small']
        self.is_reserved = scryfall_card_obj.reserved
        self.is_promo = scryfall_card_obj.promo
        self.is_reprint = scryfall_card_obj.reprint
        self.card_set_number = re.sub('[^0-9]', '', scryfall_card_obj.collector_number)
        self.card_split_card = True if scryfall_card_obj.layout == 'split' else False
        if scryfall_card_obj.prices:
            reg_price = scryfall_card_obj.prices['usd'] if scryfall_card_obj.prices['usd'] else None
            foil_price = scryfall_card_obj.prices['usd_foil'] if scryfall_card_obj.prices['usd_foil'] else None
            if reg_price or foil_price:
                updated_card_value = CardValue()
                updated_card_value.card_value_mid_current = reg_price
                updated_card_value.card_foil_value = foil_price
                if not self.card_values:
                    self.card_values = []
                self.card_values.append(updated_card_value)
        return False

class CardRuling(db.Model, BaseModel):
    __tablename__ = 'card_oracle_ruling'
    ruling_id = db.Column(db.Integer, primary_key=True)
    card_id = db.Column(db.Integer, db.ForeignKey("card.card_id", ondelete="CASCADE"))
    source = db.Column(db.String(10))
    ruling = db.Column(db.Text)

    card = db.relationship('Card')


class CardStatus(db.Model, BaseModel):
    __tablename__ = 'card_status'
    status_id = db.Column(db.Integer, primary_key=True)
    created = db.Column(db.DateTime, default=datetime.utcnow)
    updated = db.Column(db.DateTime)
    card_id = db.Column(db.Integer, db.ForeignKey("card.card_id", ondelete="CASCADE"))
    is_banned = db.Column(db.Boolean, default=False)
    is_restricted = db.Column(db.Boolean, default=False)
    format_type = db.Column(db.String(10))  # STANDARD, MODERN, LEGACY, VINTAGE, BRAWL, EDH (Commander)


class CardValue(db.Model, BaseModel):
    __tablename__ = 'card_value'
    card_value_id = db.Column(db.Integer, primary_key=True)
    card_id = db.Column(db.Integer, db.ForeignKey("card.card_id", ondelete="CASCADE"))
    created = db.Column(db.DateTime, default=datetime.utcnow)
    card_value_high_current = db.Column(db.Numeric(8,2), default=0)
    card_value_low_current = db.Column(db.Numeric(8, 2), default=0)
    card_value_mid_current = db.Column(db.Numeric(8, 2), default=0)
    card_foil_value = db.Column(db.Numeric(8, 2), default=0)

    card = db.relationship('Card')


class CardEDHRank(db.Model, BaseModel):
    __tablename__ = 'card_edh_rank'
    edh_rank_id = db.Column(db.Integer, primary_key=True)
    card_id = db.Column(db.Integer, db.ForeignKey("card.card_id", ondelete="CASCADE"))
    created = db.Column(db.DateTime, default=datetime.utcnow)
    edh_rank = db.Column(db.Integer)


class Set(db.Model, BaseModel):
    __tablename__ = 'wotc_set'
    set_id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200))
    block_id = db.Column(db.Integer, db.ForeignKey('wotc_block.block_id'), default=None)
    release_date = db.Column(db.Date)
    wotc_code = db.Column(db.String(10))


class Block(db.Model, BaseModel):
    __tablename__ = 'wotc_block'
    block_id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(30))


class OwnedCard(db.Model, BaseModel):
    __tablename__ = 'owned_card'
    owned_card_id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.user_id", ondelete="CASCADE"))
    created = db.Column(db.DateTime, default=datetime.utcnow)
    updated = db.Column(db.DateTime)
    card_id = db.Column(db.Integer, db.ForeignKey("card.card_id", ondelete="CASCADE"))
    card_count = db.Column(db.Integer)
    foil_count = db.Column(db.Integer, default=0)
    in_deck_count = db.Column(db.Integer, default=0)
    current_total = db.Column(db.Numeric(8, 2), default=0)

    card = db.relationship('Card')
    user = db.relationship('User')

    @hybrid_property
    def card_value_reg(self):
        return self.card.value_reg

    @card_value_reg.expression
    def card_value_reg(cls):
        return select([Card.value_reg]).where(cls.card_id == Card.card_id).alias('card_value_reg')

    @hybrid_property
    def card_value_foil(self):
        return self.card.value_foil

    @card_value_foil.expression
    def card_value_foil(cls):
        return select([Card.value_foil]).where(cls.card_id == Card.card_id).alias('card_value_foil')

    @hybrid_property
    def price_total(self):
        non_foil_count = self.card_count
        foil_count = 0
        if self.foil_count:
            non_foil_count = self.card_count - self.foil_count
            foil_count = self.foil_count
        return non_foil_count * self.card.get_current_value(cast_as_int=True) + \
                foil_count * self.card.get_current_value(return_foil=True, cast_as_int=True)

    @price_total.expression
    def price_total(cls):
        return ((cls.card_count - cls.foil_count) * cls.card_value_reg) + (cls.foil_count * cls.card_value_foil)


class Deck(db.Model, BaseModel):
    __tablename__ = 'deck'
    deck_id = db.Column(db.Integer, primary_key=True)
    created = db.Column(db.DateTime, default=datetime.utcnow)
    updated = db.Column(db.DateTime)
    deck_name = db.Column(db.String(100))
    user_id = db.Column(db.Integer, db.ForeignKey("user.user_id", ondelete="CASCADE"))

    deck_cards = db.relationship('DeckCard')
    user = db.relationship('User')

    cards_in_deck = {}
    card_count = 0
    cards_played = {}
    cards_prob = {}

    def __init__(self, path=None, cards_in_deck=None, card_count=None, cards_played=None,
                 cards_prob=None):
        if path:
            self.cards_in_deck = {}
            self.card_count = 0
            self.cards_played = {}
            self.cards_prob = {}
            with open(path, 'r') as deck_list:
                for line in deck_list:
                    line = line.replace('\n', '')
                    if line:
                        count, card = line.split(' ', maxsplit=1)
                        self.cards_in_deck[card] = int(count)
                        self.card_count += int(count)
        if cards_in_deck:
            self.cards_in_deck = cards_in_deck
        if card_count:
            self.card_count = card_count
        if cards_played:
            self.cards_played = cards_played
        if cards_prob:
            self.cards_prob = cards_prob

    def card_drawn(self, card):
        for key in self.cards_in_deck:
            # print(key.lower())
            # print(card.lower())
            if card.lower() in key.lower():
                if self.cards_in_deck[key] > 0:
                    if key in self.cards_played.keys():
                        self.cards_played[key] += 1
                    else:
                        self.cards_played[key] = 1
                    self.cards_in_deck[key] -= 1
                    self.card_count -= 1
                    self.cards_draw_chance()
                    return True
        return False

    # add combinatorics to get chances over next 3-5 turns
    def cards_draw_chance(self):
        for key in self.cards_in_deck:
            if self.card_count > 0:
                card_draw_pct = round(self.cards_in_deck[key] / self.card_count, 4) * 100
                # chance_str = "{} {} in deck --> {:.2f}%".format(self.cards_in_deck[key], key, card_draw_pct)
                self.cards_prob[key] = round(card_draw_pct, 2)

    # def load_deck(self):
    #     for card in self.cards:
    #         self.cards_in_deck[card.name] = int(card.count)
    #         self.card_count += int(card.count)

    def card_count_deck(self, card):
        if card in self.cards_in_deck.keys():
            return self.cards_in_deck[card]
        else:
            return 0

    def card_count_played(self, card):
        if card in self.cards_played.keys():
            return self.cards_played[card]
        else:
            return 0

    def card_count_probability(self, card):
        if card in self.cards_prob.keys():
            return self.cards_prob[card]
        else:
            return 0

    def set_initial_probs(self):
        for key in self.cards_in_deck:
            if self.card_count > 0:
                card_draw_pct = round(self.cards_in_deck[key] / self.card_count, 4) * 100
                self.cards_prob[key] = round(card_draw_pct, 2)


class DeckCard(db.Model, BaseModel):
    __tablename__ = 'deck_card'
    deck_card_id = db.Column(db.Integer, primary_key=True)
    created = db.Column(db.DateTime, default=datetime.utcnow)
    updated = db.Column(db.DateTime)
    deck_id = db.Column(db.Integer, db.ForeignKey("deck.deck_id", ondelete="CASCADE"))
    card_id = db.Column(db.Integer, db.ForeignKey("card.card_id", ondelete="CASCADE"))
    owned_card_id = db.Column(db.Integer, db.ForeignKey("owned_card.owned_card_id", ondelete="CASCADE"))
    card_count= db.Column(db.Integer)
    sideboard = db.Column(db.Boolean, default=False)

    # deck = db.relationship('Deck')
    card = db.relationship('Card')


class User(db.Model, BaseModel):
    __tablename__ = 'user'
    user_id = db.Column(db.Integer, primary_key=True)
    active = db.Column(db.Boolean, default=True)
    created = db.Column(db.DateTime, default=datetime.utcnow)
    first_name = db.Column(db.String(50))
    last_name = db.Column(db.String(50))
    email_address = db.Column(db.String(100), unique=True)
    pass_hash = db.Column(db.String(255))
    last_login = db.Column(db.DateTime)
    email_key = db.Column(db.String(10))

    owned_cards = db.relationship('OwnedCard')

    def get_collection_total(self):
        # print('test')
        total = 0
        for owned_card in self.owned_cards:
            card_value = owned_card.card.get_current_value(cast_as_int=True)
            if card_value:
                total += owned_card.card.get_current_value(cast_as_int=True) * owned_card.card_count
        return total


def return_non_price(cast_as_int):
    if cast_as_int:
        return 0
    return '0.00'