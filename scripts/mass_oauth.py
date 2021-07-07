# for catching full tracebacks on error
from sys import exc_info

import time

# for automating browser
from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By

import tweepy
import random
import logging

# for resolving chromdriver path
import os
from pathlib import Path

# for extracting query params
import urllib.parse as urlparse
from urllib.parse import parse_qs

# for saving results into json files
import json

# to record time when auth was attempted
# and to delay data entry
import time
import datetime

# to match urls
import re

# for solving recaptchas
from anticaptcha import solveRecaptcha

# to randomize ip address
from smartproxy import getRandomIP

# to accpet CL arguments
import sys


# Get random browser
def getWebDriver():
    try:
        proxy_ip = 'gate.smartproxy.com'
        proxy_port = '7000'
        proxy = f'{proxy_ip}:{proxy_port}'

        dir = f'{Path(__file__).resolve().parent.parent}'

        webdriver.DesiredCapabilities.CHROME['proxy']={
            "httpProxy":proxy,
            "ftpProxy":proxy,
            "sslProxy":proxy,
            
            "proxyType":"MANUAL",
            
        }
        driver = webdriver.Chrome(executable_path=f'{dir}/drivers/chromedriver')
    except Exception as e:
        print(e)
        exit()

    return driver


def get_redirect_url(auth):
    logger = logging.getLogger(__name__)

    try:
        redirect_url = auth.get_authorization_url()
        return redirect_url
    except tweepy.TweepError as e:
        logger.error(e, exc_info=True)
        return 'error'


def saveResults(results_file, success, username, email, password, followers, created, country, time, access, secret, screenshot, error, url):
    # load file
    try:
        results = json.load(open(results_file, 'r'))
    except Exception:
        results = {}  # initialize to an empty dictionary

    if success == True:
        results[username] = {
            "email": email, "password": password,
            "tokens": {"access_token": access, "access_secret": secret},
            "followers": followers, "created": created, "country": country,
            "auth_attempt": {"time": time},
        }
    else:
        results[username] = {
            "email": email, "password": password,
            "followers": followers, "created": created, "country": country,
            "auth_attempt": {"time": time},
            "screenshot": screenshot, "error": error, "url": url
        }

    with open(results_file, 'w') as f:
        f.write(json.dumps(results, indent=4))


def getTokensOrHandleRedirects(driver, username, email):
    # Get the current url to know status
    url = driver.current_url

    # reCAPTCHA required
    if re.match('https://twitter.com/login/check', url) is not None:
        solveRecaptcha(driver, email)
    elif re.match('https://twitter.com/account/login_challenge', url) is not None:
        challenge_response = username

        if re.search('challenge_type=RetypePhoneNumber', url) is not None:
            # we can't take care of this for now, so just pass
            pass

        driver.find_element_by_name('challenge_response').send_keys(challenge_response)
        driver.find_element_by_id('email_challenge_submit').click()
        time.sleep(3)
        driver.find_element_by_id('allow').click()
    else:
        pass

    # check url again
    url = driver.current_url

    if re.match('http://127.0.0.1', url) is not None:
        parsed = urlparse.urlparse(url)
        auth_token = parse_qs(parsed.query)['oauth_token'][0]
        verifier = parse_qs(parsed.query)['oauth_verifier'][0]

    return (auth_token, verifier)


def twitterLogin(email, password, username, followers, created, country, two_factor=False):
    accounts_dir = f'{Path(__file__).resolve().parent.parent}/accounts/'

    try:
        # configure browser
        driver = getWebDriver()

        auth_time = datetime.datetime.now(datetime.timezone.utc)

        # Authenticate to the app
        consumer_token = os.environ.get('CONSUMER_TOKEN')
        consumer_secret = os.environ.get('CONSUMER_SECRET')
        callback_url = 'http://127.0.0.1'  # just a dummy callback url, doesn't really do anything
        auth = tweepy.OAuthHandler(consumer_token, consumer_secret, callback_url)

        # Go to twitter auth page
        url = get_redirect_url(auth)

        driver.get(url)

        time.sleep(3)

        # Input credentials
        driver.find_element_by_name('session[username_or_email]').send_keys(email)
        time.sleep(3)
        driver.find_element_by_name('session[password]').send_keys(password)

        # click on the allow button
        driver.find_element_by_id('allow').click()

        tokens = getTokensOrHandleRedirects(driver, username, email)

        # Get and save the keys
        auth.request_token = {'oauth_token': tokens[0], 'oauth_token_secret': tokens[1]}
        keys = auth.get_access_token(tokens[1])

        saveResults(
            f'{accounts_dir}authenticated_accounts.json', True, username, email,
            password, followers, created, country,
            str(auth_time), keys[0], keys[1],
            None, None, None
        )
    except Exception as e:
        screenshots_dir = f'{Path(__file__).resolve().parent.parent}/screenshots/'
        logger = logging.getLogger(__name__)
        logger.error(e, exc_info=True)
        driver.save_screenshot(f'{screenshots_dir}{username}.png')
        saveResults(
            f'{accounts_dir}failed_accounts.json', False, username, email,
            password, followers, created, country,
            str(auth_time), None, None,
            f'{screenshots_dir}{username}.png', str(e), url
        )
        time.sleep(3600)


def authenticate_accounts(retry_failed=False):
    retry_failed = False

    if len(sys.argv) > 1:
        if sys.argv[1] == 'retry-failed':
            retry_failed = True

    accounts_dir = f'{Path(__file__).resolve().parent.parent}/accounts/'

    try:
        all_accounts = json.load(open(f'{accounts_dir}all_accounts.json', 'r'))
        authenticated = list(json.load(open(f'{accounts_dir}authenticated_accounts.json', 'r')).keys())
        failed = list(json.load(open(f'{accounts_dir}failed_accounts.json', 'r')).keys())
    except Exception as e:
        print(f"There was a problem opening an accounts file: {e}")
        exit()

    if retry_failed:
        exclude = authenticated
    else:
        exclude = authenticated + failed

    for key in exclude:
        all_accounts.pop(key)

    print(f'Retrieved {len(all_accounts)} accounts. Attempting authentication')

    # Read accounts from the right source later
    for account in all_accounts:
        try:
            email = all_accounts[account]['email']
            password = all_accounts[account]['password']

            followers = all_accounts[account]['followers']
            created = all_accounts[account]['created']
            country = all_accounts[account]['country']
            two_factor = all_accounts[account]['two_factor']

            print(f'@{account}')

            twitterLogin(email, password, account, followers, created, country, two_factor)

        except Exception as e:
            print(e)

authenticate_accounts()
