import csv
import io
import json
import models
import os
import sys

from datetime import date, datetime, timedelta
from decimal import Decimal
from flask import Flask, render_template, request, jsonify, abort, after_this_request, g, send_from_directory
from gatherer_api import MTGDataScraper
from locallibrary import paginate, pretty_exception
from random import randint, uniform
from scryfall_api import ScryfallAPI
from sqlalchemy import case, func, not_
from time import sleep

from nltk import sent_tokenize, word_tokenize

app = Flask(__name__)
app.config.from_pyfile('flaskapp.cfg')
app.config['DEBUG'] = True
# print(app.config['SQLALCHEMY_DATABASE_URI'])
models.db.init_app(app)
port = 5000
scraper = MTGDataScraper()
scryfall = ScryfallAPI()


@app.before_request
def before_request():
    g.user = models.User.query.filter_by(user_id=1).first()


@app.route('/')
def index():
    # DB Test
    # card = models.Card.query.first()
    # print(card.card_name)
    # Scryfall test
    card = models.Card.query.first()
    # card = scryfall.get_card_multiverse(card.wotc_id)
    # print(card.prices)
    # print(card.legalities)
    sentences = sent_tokenize(card.card_oracle_text)
    words = word_tokenize(card.card_oracle_text)
    print(sentences)
    print(words)
    return "INDEX"


@app.route('/<int:user_id>/cards', methods=["GET", "POST"])
def user_card_list(user_id):
    page = request.args.get('page', 1, type=int)
    my_cards = models.OwnedCard.query.filter_by(user_id=user_id).join(models.Card)
    order_by = request.args.get('order', 'name')
    filter_name = request.args.get('name', '')
    filter_set = request.args.get('set', 0, type=int)
    if request.form:
        filter_name = request.form.get('name', '')
        filter_set = request.form.get('set', 0, type=int)
    if filter_name:
        my_cards = my_cards.filter(models.Card.card_name.ilike('%{}%'.format(filter_name)))
    if filter_set:
        # print(filter_set)
        my_cards = my_cards.filter(models.Card.set_id == filter_set)
    if order_by:
        order_by_dict = {
            'name': models.Card.card_name,
            'rarity': models.Card.card_rarity,
            'count': models.OwnedCard.card_count,
            'set': models.Set.name,
            # 'value': case([(models.CardValue.card_value_mid_current != 'null', models.CardValue.card_value_mid_current)], else_=models.CardValue.card_foil_value).desc()
            'value': models.OwnedCard.current_total.desc()
        }
        if order_by == 'set':
            my_cards = my_cards.join(models.Set)
        if order_by == 'value':
            my_cards = my_cards.outerjoin(models.CardValue).filter(models.CardValue.created >= models.Card.value_last_updated)
        my_cards = my_cards.order_by(order_by_dict[order_by])
    my_cards, pagination = paginate(my_cards, page, per_page=50)
    # print(my_cards)
    filter_dict = {
        'name': filter_name,
        'rarity': '',
        'set': filter_set
    }
    sets = models.Set.query.order_by(models.Set.name).all()
    return render_template('user/card_list.html', my_cards=my_cards, pagination=pagination, current_page=page, filter_dict=filter_dict, sets=sets)


@app.route("/<int:set_id>/pack")
def display_card_pack(set_id):
    pack = generate_pack(set_id)
    print(pack)
    return render_template('card_pack.html', pack=pack)


"""
FUNCTION-CENTRIC ROUTES
"""

@app.route('/scrape')
def scrape():
    multiverse_id = 1
    if request.args.get('mid', None):
        sleep(.05)
        call_sleep = randint(1, 100)
        if 0 < call_sleep < 10:
            sleep(uniform(.05, .15))
        if 10 < call_sleep < 20:
            sleep(uniform(.025, .05))
        multiverse_id = request.args.get('mid', type=int)
    try:
        scraper.get_card_info_gatherer(multiverse_id=multiverse_id)
    except Exception:
        exc = sys.exc_info()
        error = models.Errors()
        error.add_error(error=pretty_exception(exc), path='MTGDataScraper',
                        action="Scrape Issue: {}".format(multiverse_id))
        error.card_id = multiverse_id
    return render_template('scrape.html', port=port, multiverse_id=multiverse_id)


@app.route('/update/prices/all')
def update_prices_all():
    @after_this_request
    def worker_task(resp):
        mid = request.args.get('mid', 0, type=int)
        cards = models.Card.query
        if mid:
            cards = cards.filter(models.Card.wotc_id >= mid)
        cards = cards.all()
        for card in cards:
            attempts = 0
            if card.value_last_updated == '0000-00-00' or not card.value_last_updated:
                continue
            if card.value_last_updated >= date.today() - timedelta(days=1):
                continue
            print("Getting price for:", card.wotc_id, card.card_set.name, card.card_name)
            scryfall_card = scryfall.get_card_multiverse(card.wotc_id)
            while not scryfall_card and attempts < 3:
                sleep(.5)
                scryfall_card = scryfall.get_card_multiverse(card.wotc_id)
                attempts += 1
            if not scryfall_card:
                card.value_last_updated = None
                err = card.update_object()
                if err:
                    print("Error: {}".format(err))
                continue
            prices = scryfall_card.prices
            new_value = models.CardValue()
            new_value.card_id = card.card_id
            if prices['usd']:
                new_value.card_value_mid_current = Decimal(prices['usd'])
            if prices['usd_foil']:
                new_value.card_foil_value = Decimal(prices['usd_foil']) 
            err = new_value.add_object()
            if err:
                print("Error: {}".format(err))
            card.value_last_updated = date.today()
            err = card.update_object()
            if err:
                print("Error: {}".format(err))
            owned_card = models.OwnedCard.query.filter_by(user_id=1, card_id=card.card_id).first()
            if owned_card:
                owned_card.current_total = owned_card.price_total
                err = owned_card.update_object()
                if err:
                    print("Error: {}".format(err))
            sleep(.5)
            print("Price is:", new_value.card_value_mid_current, card.wotc_id, card.card_set.name, card.card_name)
        return resp
    return "Card Prices Updating -- Please Wait"


@app.route('/update/prices/<int:multiverse_id>')
def update_prices(multiverse_id):
    card = models.Card.query.filter_by(wotc_id=multiverse_id).first_or_404()
    scryfall_card = scryfall.get_card_multiverse(multiverse_id)
    prices = scryfall_card.prices
    new_value = models.CardValue()
    new_value.card_id = card.card_id
    if prices['usd']:
        new_value.card_value_mid_current = Decimal(prices['usd'])
    if prices['usd_foil']:
        new_value.card_foil_value = Decimal(prices['usd_foil'])
    err = new_value.add_object()
    if err:
        return "Error: {}".format(err)
    return "SUCCESS"


@app.route('/error/cleanup')
def error_cleanup():
    errs = models.Errors.query.all()
    for err in errs:
        multiverse_id = int(err.action.split(':')[-1].strip())
        print(multiverse_id)
        try:
            scraper.get_card_info_gatherer(multiverse_id=multiverse_id)
            err.delete_object()
        except Exception:
            exc = sys.exc_info()
            error = models.Errors()
            error.add_error(error=pretty_exception(exc), path='MTGDataScraper',
                            action="Scrape Issue: {}".format(multiverse_id))
            error.card_id = multiverse_id
            print(multiverse_id, error.action)
    return "SUCCESS"


@app.route('/upload/mtg/default', methods=["GET", "POST"])
def card_upload_mtg_default():
    if request.files:
        download_file = request.files.get('card_list')
        file_item = io.StringIO(download_file.stream.read().decode("UTF8", 'ignore'), newline=None)
        for card in file_item.getvalue().split('\n'):
            card_name = card.split(' ', 1)[-1]
            if card_name in ['Plains', 'Island', 'Swamp', 'Mountain', 'Forest']:
                continue
            card_count = card.split(' ', 1)[0]
            card_set = 'Commander 2019'
            card_set = models.Set.query.filter(models.Set.name.ilike('%{}%'.format(card_set))).first()
            if not card_set:
                str_err = "Set {} not found. Card {} not added.".format(card_set, card_name)
                err = models.Errors()
                err.add_error(error=str_err, path=request.full_path, action="Adding Card Record")
            else:
                if '//' in card_name:
                    card_names = card_name.split('//')
                else:
                    card_names = [card_name]
                for card_name in card_names:
                    card_name = card_name.strip()
                    card = models.Card.query.filter_by(card_name=card_name, set_id=card_set.set_id).first()
                    if not card:
                        str_err = "Card {} not found. Card {} not added.".format(card_name, card_name)
                        err = models.Errors()
                        err.add_error(error=str_err, path=request.full_path, action="Adding Card Record")
                    else:
                        owned_card = models.OwnedCard.query.filter_by(user_id=1, card_id=card.card_id).first()
                        if owned_card:
                            print('Card already exists')
                            continue
                        owned_card = models.OwnedCard()
                        owned_card.card_id = card.card_id
                        owned_card.card_count = card_count
                        owned_card.user_id = 1
                        owned_card.in_deck_count = 0
                        owned_card.add_object()
    return render_template('file_upload.html')


@app.route('/upload/tcg', methods=["GET", "POST"])
def card_list_upload_tcg():
    if request.files:
        download_file = request.files.get('card_list')
        csv_file = io.StringIO(download_file.stream.read().decode("UTF8", 'ignore'), newline=None)
        csv_reader = csv.reader(csv_file)
        csv_reader = sorted(csv_reader, key=lambda x: x[0], reverse=True)
        for row in csv_reader:
            card_count = row[0]
            card_name = row[2]
            card_set = row[3]
            card_set = core_set_edit(card_set)
            # card_number_set = row[4]
            card_set_code = row[5]
            # card_rarity = row[9]
            card_set = models.Set.query.filter(models.Set.name.ilike('%{}%'.format(card_set))).first()
            if not card_set:
                str_err = "Set {} not found. Card {} not added.".format(row[3], card_name)
                err = models.Errors()
                err.add_error(error=str_err, path=request.full_path, action="Adding Card Record")
            else:
                if not card_set.wotc_code:
                    card_set.wotc_code = card_set_code
                    card_set.update_object()
                if '//' in card_name:
                    card_names = card_name.split('//')
                else:
                    card_names = [card_name]
                for card_name in card_names:
                    card_name = card_name.strip()
                    card = models.Card.query.filter_by(card_name=card_name, set_id=card_set.set_id).first()
                    if not card:
                        str_err = "Card {} not found. Card {} not added.".format(card_name, card_name)
                        err = models.Errors()
                        err.add_error(error=str_err, path=request.full_path, action="Adding Card Record")
                    else:
                        owned_card = models.OwnedCard()
                        owned_card.card_id = card.card_id
                        owned_card.card_count = card_count
                        owned_card.user_id = 1
                        owned_card.in_deck_count = 0
                        owned_card.add_object()
    return render_template('file_upload.html')


@app.route('/scryfall/csv/test')
def scryfall_csv_test():
    count = 1
    with open('./data_csv/scryfall-default-cards.json', 'r', encoding='UTF-8') as json_file:
        cards = json.loads(json_file.read())
        for card in cards:
            print(count)
            count += 1
            multiverse_id = card['multiverse_ids'][0] if card['multiverse_ids'] else None
            card_name = card['name']
            card_set = card['set_name']
            if multiverse_id:
                card = models.Card.query.filter_by(wotc_id=multiverse_id).first()
                if not card:
                    wotc_set = models.Set.query.filter_by(name=card_set).first()
                    if wotc_set:
                        card = models.Card.query.filter_by(card_name=card_name, set_id=wotc_set.set_id).first()
                        if card:
                            print(card_name, card_set)
                            # card.wotc_id = multiverse_id
                            # err = card.update_object()
                            # if err:
                            #     print(err)
            # if not card and multiverse_id:
            #     card = models.Card()
            #     card.wotc_id = multiverse_id
            #     card.card_name = card_name
    return "SUCCESS"


@app.route('/get/collection/total')
def get_collection_total():
    cards = models.OwnedCard.query.filter_by(user_id=1).all()
    total = 0
    for card in cards:
        total += card.price_total
        card.current_total = card.price_total
        err = card.update_object()
        if err:
            print(err)
    return str(total)


@app.route('/get/list/standard')
def get_collection_standard_legal():
    _STANDARD_LIST = (209, 207, 201, 190, 188, 183, 180, 174)
    _RARITY_LIST = ('R', 'M')
    cards = models.OwnedCard.query.filter_by(user_id=1)\
        .join(models.Card)\
        .filter(
            models.Card.set_id.in_(_STANDARD_LIST),
            models.Card.card_rarity.in_(_RARITY_LIST)
        ).order_by(models.Card.card_name).all()
    for owned_card in cards:
        print(f'{owned_card.card.card_name}|{owned_card.card_count}|{owned_card.card.card_set.name}')
    return "SUCCESS"


@app.route('/get/uc/value')
def get_uc_value():
    _RARITY_LIST = ('C', 'U')
    cards = models.OwnedCard.query.filter_by(user_id=1)\
        .join(models.Card)\
        .filter(
            models.Card.card_rarity.in_(_RARITY_LIST),
            models.OwnedCard.current_total >= 1
        ).order_by(models.Card.card_name).all()
    final_list = []
    for card in cards:
        if card.current_total / card.card_count > 1:
            final_list.append((card.card.card_name, card.card.card_set.name, card.card.card_rarity, float(card.current_total/card.card_count)))
    final_list = sorted(final_list, key=lambda x: x[-1])
    return jsonify(cards=final_list)
    
@app.route('/get/cards/artist/<string:artist_name>')
def get_cards_by_artist(artist_name):
    # print(artist_name)
    cards = models.Card.query.filter_by(card_artist=artist_name).join(models.OwnedCard).all()
    owned_cards = [{'card': card.card_name, 'set': card.card_set.name} for card in cards]
    return jsonify(cards=owned_cards)


@app.route('/get/vintagecube/cards')
def get_vintage_cube_cards():
    owned_cards = []
    cards_total = 0
    with open('mtgo_vintage_cube_summer_2019.csv', 'r') as csv_file:
        csv_reader = csv.reader(csv_file)
        for line in csv_reader:
            card_name = line[0]
            owned_card = models.OwnedCard.query.join(models.Card).filter(models.Card.card_name == card_name).first()
            if owned_card:
                owned_cards.append(card_name)
            cards_total += 1
    return jsonify(owned_count=len(owned_cards), owned_percentage=len(owned_cards)/cards_total, owned_cards=owned_cards)


"""
API CALLS
"""


@app.route('/api/card/collection/add', methods=["POST"])
def api_card_collection_add():
    if request.form:
        card_name = request.form.get('card_name', '')
        card_set = request.form.get('card_set', 0)
        card = models.Card.query.filter_by(set_id=card_set).filter(models.Card.card_name.ilike('%{}%'.format(card_name))).first()
        if not card:
            return jsonify(success=False, err="Card {} not found".format(card_name))
        new_card_in_collection = models.OwnedCard.query.filter_by(card_id=card.card_id).first()
        if new_card_in_collection:
            return jsonify(success=False, err="This card is already in your collection")
        new_card = models.OwnedCard()
        new_card.card_id = card.card_id
        new_card.card_count = request.form.get('card_count')
        new_card.user_id = g.user.user_id
        err = new_card.add_object()
        if err:
            return jsonify(success=False, err=err)
        new_card.current_total = new_card.price_total
        err = new_card.update_object()
        if err:
            return jsonify(success=False, err=err)
        return jsonify(success=True, reload=True)
    else:
        return jsonify(success=False, err="The server did not receive any data.")


@app.route('/api/card/count/update', methods=["POST"])
def api_card_count_update():
    if request.form:
        # print(request.form)
        owned_card = models.OwnedCard.query.filter_by(owned_card_id=request.form.get('owned_card_id', None)).first_or_404()
        if request.form.get('card_modifier', 0):
            owned_card.card_count += request.form.get('card_modifier', 0, type=int)
        if request.form.get('card_count', 0):
            owned_card.card_count = request.form.get('card_count', 0, type=int)
        if request.form.get('foil_count', 0):
            owned_card.foil_count = request.form.get('foil_count', 0, type=int)
        if owned_card.card_count <= 0:
            err = owned_card.delete_object()
            if err:
                return jsonify(success=False, err=err)
            return jsonify(success=True)
        owned_card.current_total = owned_card.price_total
        err = owned_card.update_object()
        if err:
            return jsonify(success=False, err=err)
        return jsonify(success=True, reload=True)
    else:
        abort(404)


@app.route('/api/card/get', methods=["POST"])
def api_card_get():
    if request.form:
        owned_card = models.OwnedCard.query.filter_by(owned_card_id=request.form.get('owned_card_id', None)).first_or_404()
        return jsonify(success=True, card_info=owned_card.serialize())
    else:
        return jsonify(success=False, err="The server failed to receive any data.")


@app.route('/api/card/image/refresh', methods=['POST'])
def api_image_refresh():
    if request.form:
        card = models.Card.query.filter_by(card_id=request.form.get('card_id', None)).first_or_404()
        card.get_card_img(refresh=True)
        return jsonify(success=True, reload=True)
    else:
        return jsonify(success=False, err="The server failed to receive any data.")


"""
SETUP AND CORE FUNCTIONS
"""


@app.route('/setup/init-db')
def init_db():
    with app.app_context():
        models.db.create_all()
    return "SUCCESS"


@app.route('/<path:resource>')
def serve_static_resource(resource):
    return send_from_directory('static/', resource)


"""
MISC. FUNCTIONS
"""


def core_set_edit(set_name):
    set_name = set_name.split('(')[0].strip()
    replacement_dict = {
        '4th': 'Fourth',
        '5th': 'Fifth',
        '6th': 'Classic Sixth',
        '7th': 'Seventh',
        '8th': 'Eighth',
        '9th': 'Ninth',
        '10th': 'Tenth',
        'Commander Anthology Volume II': 'Commander Anthology 2018'
    }
    for numeric_string, replacement_string in replacement_dict.items():
        if numeric_string in set_name:
            return set_name.replace(numeric_string, replacement_string)
    return set_name


def generate_pack(set_id):
    pack = []
    pack_has_foil = False
    pack_has_mythic_rare = False
    pack_requires_guildgate = False
    if set_id in [190, 201]:
        pack_requires_guildgate = True
    if randint(1, 67) == 1:
        pack_has_foil = True
    if randint(1, 8) == 1:
        pack_has_mythic_rare = True
    mythic_rare_count = 0 if not pack_has_mythic_rare else 1
    rare_count = 1 if not pack_has_mythic_rare else 0
    uncommon_count = 3 if not pack_has_foil else 2
    common_count = 10
    guildgate_count = 0 if not pack_requires_guildgate else 1
    basic_land_count = 1 if not pack_requires_guildgate else 0
    # print(mythic_rare_count, rare_count, uncommon_count, common_count, basic_land_count, guildgate_count)
    mythic_rare = None
    if mythic_rare_count:
        mythic_rare = models.Card.query.filter_by(set_id=set_id, card_rarity='M')\
            .order_by(func.rand()).limit(mythic_rare_count).first()
    rare = None
    if rare_count:
        rare = models.Card.query.filter_by(set_id=set_id, card_rarity='R')\
            .order_by(func.rand()).limit(rare_count).first()
    uncommons = models.Card.query.filter_by(set_id=set_id, card_rarity='U')\
        .order_by(func.rand()).limit(uncommon_count).all()
    commons = models.Card.query.filter_by(set_id=set_id, card_rarity='C')
    if pack_requires_guildgate:
        commons = commons.filter(not_(models.Card.card_name.ilike('%{}%'.format('Guildgate'), models.Card.card_type == 'Land')))
    commons = commons.order_by(func.rand()).limit(common_count).all()
    land = models.Card.query.filter_by(set_id=set_id, card_rarity='L')\
        .order_by(func.rand()).limit(basic_land_count).first()
    guildgate = models.Card.query.filter_by(set_id=set_id, card_rarity='C', card_type="Land")\
        .filter(models.Card.card_name.ilike('%{}%'.format('Guildgate')))\
        .order_by(func.rand()).limit(guildgate_count).first()
    foil_card = None
    if pack_has_foil:
        foil_card = models.Card.query.filter_by(set_id=set_id)\
            .filter(models.Card.card_rarity != 'L')\
            .order_by(func.rand()).limit(1).first()
    if mythic_rare:
        pack.append(mythic_rare)
    if rare:
        pack.append(rare)
    for uncommon in uncommons:
        pack.append(uncommon)
    for common in commons:
        pack.append(common)
    if land:
        pack.append(land)
    if guildgate:
        pack.append(guildgate)
    if foil_card:
        pack.append(foil_card)
    return pack


if __name__ == '__main__':
    if os.name == 'nt':
        app.run(port=port)
    else:
        app.run()
