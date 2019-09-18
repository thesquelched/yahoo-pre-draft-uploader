import argparse
import getpass
import string
import re
import time
import logging
import functools
import difflib
import itertools
import os
from unidecode import unidecode
from selenium.webdriver import Firefox
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import StaleElementReferenceException, TimeoutException


LOG = logging.getLogger(__name__)


URL = 'https://hockey.fantasysports.yahoo.com/hockey/1109/12/editprerank?count=950'
KEEP_CHARS = frozenset(string.ascii_letters + string.digits + string.whitespace)
ADDED_PLAYERS_FILE = 'added.dat'


def login(driver):
    e_username = driver.find_element_by_id('login-username')
    e_username.send_keys(input('Enter yahoo username: '), Keys.RETURN)

    e_password = driver.find_element_by_id('login-passwd')
    e_password.send_keys(getpass.getpass('Enter yahoo password:'), Keys.RETURN)

    driver.find_elements_by_css_selector('#all_player_list')


def get_nth_player(driver, n):
    return driver.find_element_by_css_selector(f'#all_player_list li:nth-child({n})')


def retry_stale(func):
    @functools.wraps(func)
    def wrapped(*args, retry=True, **kwargs):
        try:
            return func(*args, **kwargs)
        except StaleElementReferenceException:
            if not retry:
                raise

            return wrapped(*args, retry=False, **kwargs)

    return wrapped


@retry_stale
def get_all_players(driver):
    elements = driver.find_elements_by_css_selector('#all_player_list .playersimple-adddrop')

    return {
        standardize(element.find_element_by_css_selector('span span:nth-child(2)').text): element
        for element in elements
    }


@retry_stale
def get_added_players(driver):
    try:
        elements = WebDriverWait(driver, 1).until(
            EC.presence_of_all_elements_located((By.CSS_SELECTOR,
                                                '#my_player_list .playersimple-adddrop'))
        )
    except TimeoutException:
        elements = []

    return {
        standardize(element.find_element_by_css_selector('span span:nth-child(2)').text): element
        for element in elements
    }


def standardize(value):
    return re.sub(
        r'\s+',
        r' ',
        ''.join(char for char in unidecode(value).lower() if char in KEEP_CHARS)
    ).strip()


def read_rankings(args):
    lines = args.rankings.readlines()

    return [standardize(line) for line in lines]


class player_added:
    def __init__(self, player):
        self.player = standardize(player)

    def __call__(self, driver):
        return get_added_players(driver).get(self.player, False)


def add_player(driver, player, elem):
    elem.find_element_by_css_selector('.F-positive').click()
    WebDriverWait(driver, 5).until(player_added(player))


def init_args(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument('rankings', type=argparse.FileType('r'), metavar='<path>',
                   help='Path to rankings file')
    p.add_argument('-s', '--save-every', type=int, default=100, metavar='<N>',
                   help='Save after every N players (default: 100)')
    p.add_argument('-r', '--reset', action='store_true', help='Reset draft order')

    return p.parse_args(argv)


def reset_roster(driver):
    elem = driver.find_element_by_css_selector('button.reset-roster-btn')

    elem.click()

    try:
        WebDriverWait(driver, 5).until(EC.alert_is_present())
    except TimeoutException:
        return

    driver.switch_to.alert.accept()

    save(driver)

    if os.path.isfile(ADDED_PLAYERS_FILE):
        os.remove(ADDED_PLAYERS_FILE)

    #time.sleep(3)

    #WebDriverWait(driver, 10).until(
    #    EC.invisibility_of_element_located((By.CSS_SELECTOR,
    #                                        '#my_player_list .playersimple-adddrop'))
    #)


def save(driver):
    LOG.info('Saving')

    elem = driver.find_element_by_id('submit-editprerank')
    if 'Btn-disabled' in elem.get_attribute('class'):
        LOG.warning('Save button is disabled; skipping...')
        return

    elem.submit()
    driver.find_element_by_css_selector('.Alert-confirmation')
    LOG.info('Saved successfully')


def init_player_list(driver):
    LOG.info('Loading players...')

    n_added = len(get_added_players(driver))

    loader = driver.find_element_by_id('load_more')
    loader.click()

    driver.find_element_by_css_selector('.loading-players-message')
    WebDriverWait(driver, 5).until(
        EC.invisibility_of_element_located((By.CLASS_NAME, '.loading-players-message'))
    )

    LOG.info('Getting last player')
    get_nth_player(driver, 1000 - n_added)

    return get_all_players(driver)


def read_added_players_file():
    if not os.path.isfile(ADDED_PLAYERS_FILE):
        return set()

    with open(ADDED_PLAYERS_FILE) as f:
        return set(line.strip() for line in f.readlines())


def add_players(args, driver, rankings):
    LOG.info('Filtering out already added players')
    read_added_players_file()
    existing = set(get_added_players(driver)).union(read_added_players_file())

    to_add = [player for player in rankings if player not in existing]
    grouped = itertools.groupby(enumerate(to_add), lambda i: i[0] // args.save_every)

    with open(ADDED_PLAYERS_FILE, 'a') as f:
        for _, chunk in grouped:
            LOG.info('Reloading page')
            driver.get(URL)

            players = init_player_list(driver)

            try:
                for (_, player) in chunk:
                    LOG.info('Adding player %s', player)

                    if player in players:
                        elem = players[player]
                        add_player(driver, player, elem)
                        print(player, file=f)
                    else:
                        closest = next((item for item in difflib.get_close_matches(player, players)), None)
                        if not (closest and closest in players):
                            LOG.warning('Player %s was not found', player)
                            continue

                        LOG.info("Player '%s' not found; using closest match '%s' instead", player, closest)
                        elem = players[closest]

                        add_player(driver, closest, elem)
                        print(closest, file=f)
                        print(player, file=f)
            finally:
                LOG.info('Saving...')
                save(driver)

                f.flush()


def main():
    args = init_args()
    logging.basicConfig(level=logging.ERROR,
                        format='%(asctime)s %(name)s %(levelname)s: %(message)s')
    LOG.setLevel(logging.INFO)

    LOG.info('Reading rankings')
    rankings = read_rankings(args)

    capabilities = DesiredCapabilities().FIREFOX
    capabilities["pageLoadStrategy"] = "eager"

    driver = Firefox(capabilities=capabilities)
    driver.implicitly_wait(5)

    LOG.info('Loading url %s', URL)
    driver.get(URL)

    LOG.info('Logging in')
    login(driver)

    time.sleep(3)

    if args.reset and input('Reset current draft order [y/N]: ') in ('y', 'Y'):
        LOG.info('Resetting roster')
        reset_roster(driver)

        LOG.info('Waiting for page to load')
        driver.find_elements_by_css_selector('#all_player_list')

    add_players(args, driver, rankings)

    input('Press any key to exit')
    driver.close()


if __name__ == '__main__':
    main()
