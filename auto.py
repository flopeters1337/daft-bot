import os
import time
import logging
import pickle as pkl
from configparser import ConfigParser
from daftlistings import Daft, SortType, SearchType, Location
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException, ElementNotInteractableException

PATH = os.path.dirname(os.path.abspath(__file__))
logging.basicConfig(filename=os.path.join('logs', 'daftbot.log'), level=logging.DEBUG)


def prettify_name(name):
    words = name.lower().split(' ')
    new_words = list()

    for w in words:
        new_words.append(w[0].upper() + w[1:])

    return ' '.join(new_words)


def read_config():
    config = ConfigParser()
    config.read(os.path.join(PATH, 'config.ini'))
    return config


def search_listings(config, search_type=SearchType.RESIDENTIAL_RENT):
    locations = [eval('Location.' + x) for x in config['criteria']['locations'].split(',')]
    daft = Daft()
    daft.set_search_type(eval('SearchType.' + config['criteria']['search_type']))
    daft.set_sort_type(SortType.PUBLISH_DATE_DESC)
    daft.set_max_price(config['criteria']['max_budget'])
    daft.set_min_beds(config['criteria']['min_beds'])
    daft.set_location(locations)
    return daft.search(max_pages=3)


def get_cache(filepath=os.path.join(PATH, 'cache.pkl')):
    if os.path.exists(filepath):
        with open(filepath, mode='rb') as fd:
            cache = pkl.load(fd)
    else:
        cache = set()

    return cache


def update_cache(cache, filepath=os.path.join(PATH, 'cache.pkl')):
    with open(filepath, mode='wb') as fd:
        pkl.dump(cache, fd)


def init_driver(config):
    chrome_options = webdriver.ChromeOptions()
    chrome_options.add_argument('--headless')
    driver = webdriver.Chrome(config['webdriver']['location'], options=chrome_options)

    # Add Daft.ie authetication cookies
    driver.get('https://www.daft.ie')
    driver.add_cookie({
        'name': 'session',
        'value': config['webdriver']['session']
    })
    driver.add_cookie({
        'name': 'session.sig',
        'value': config['webdriver']['session.sig']
    })

    # Accept cookies to make prompt disappear
    driver.get('https://www.daft.ie')
    try:
        cookie_btn = driver.find_element(By.XPATH, value="//button[@data-tracking = 'cc-accept']")
        cookie_btn.click()
    except NoSuchElementException:
        pass

    return driver


def send_message(listing, config, driver):
    msg_text = config['inquiry']['template'].format(agentname=prettify_name(listing.agent_name), title=listing.title,
                                                    phone=config['inquiry']['phone'],
                                                    email=config['inquiry']['email'],
                                                    fullname=config['inquiry']['fullname'])

    driver.get(listing.daft_link)

    # Click on the 'EMAIL' button
    email_button = driver.find_element(By.XPATH, value="//button[@aria-label = 'EMAIL']")
    try:
        email_button.click()
    except ElementNotInteractableException:
        email_button = driver.find_element(By.XPATH, value="//button[@data-tracking = 'email-btn']")
        email_button.click()
    time.sleep(2)  # To let the webpage open the form pop-up

    # Fill in the form and click 'Send'
    driver.find_element(By.XPATH, value="//input[@aria-label = 'name']").send_keys(config['inquiry']['fullname'])
    driver.find_element(By.XPATH, value="//input[@aria-label = 'email']").send_keys(config['inquiry']['email'])
    driver.find_element(By.XPATH, value="//input[@aria-label = 'phone']").send_keys(config['inquiry']['phone'])
    driver.find_element(By.XPATH, value="//textarea[@id = 'message']").send_keys(msg_text)
    driver.find_element(By.XPATH, value="//button[@aria-label = 'Send']").click()
    time.sleep(1)   # Let the form send

    logging.info(f"[INFO] Sent message: 'f{msg_text}'")


def run():
    cfg = read_config()
    cache = get_cache()
    driver = init_driver(cfg)
    listings = [x for x in search_listings(cfg) if x.id not in cache]  # Remove listings that are already in the cache.

    for l in listings:
        try:
            send_message(l, cfg, driver)
            cache.add(l.id)
        except Exception as e:
            logging.error(f'Could not send message to listing: {l.daft_link}, {str(e)}')
            continue

    driver.quit()
    update_cache(cache)


if __name__ == '__main__':
    run()
