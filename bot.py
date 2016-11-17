import sys
import json
from html.parser import HTMLParser

import requests
from slacker import Slacker
from websocket import create_connection


class ChatHandler:
    def __init__(self, slacker, translator):
        self._chat = slacker.chat
        resp = slacker.rtm.start()
        self._socket = create_connection(resp.body['url'])
        self._translator = translator
        bot_user_id = slacker.users.get_user_id('gtbot')
        self._gtbot_id = '<@{}>'.format(bot_user_id)
        self._default_target = 'en'

    def loop(self):
        while True:
            ch, msg, target = self._read()
            if msg == '/lang':
                msg = self._translator.availables()
            elif msg == '/setdefault':
                msg = self._set_default(target)
            else:
                msg = self._translator.translate(msg, target=target)
            self._send(ch, msg)

    def _read(self):
        while True:
            event = json.loads(self._socket.recv())
            if 'bot_id' in event:
                continue
            ch, msg, target = self._parse(event)
            if not ch or not msg:
                continue
            break
        return ch, msg, target

    def _parse(self, event):
        if event['type'] != 'message' or self._gtbot_id not in event['text']:
            return None, None, None
        text = event['text'].replace(self._gtbot_id, '').strip()
        target = self._default_target

        if text.startswith('/target'):
            text = text.replace('/target', '').strip().split()
            target, text = text[0], ' '.join(text[1:])
        if text.startswith('/setdefault'):
            text, target = text.split()
        return event['channel'], text, target

    def _send(self, ch, msg):
        self._chat.post_message(ch, msg, as_user=True)

    def _set_default(self, target):
        self._default_target = target
        self._translator.set_default_target(target)
        return '기본 번역 언어가 {}로 설정 되었습니다 ^ㅇ^'.format(target)


class Translator:
    _base_url = 'https://translation.googleapis.com/language/translate/v2'
    _html_parser = HTMLParser()

    def __init__(self, api_key):
        self._api_key = api_key
        self._default_target = 'en'

    def translate(self, msg, target=None):
        if not target:
            target = self._default_target
        params = {
            'key': self._api_key,
            'target': target,
            'q': msg,
        }
        resp = requests.get(self._base_url, params=params).json()
        translated_msg = resp['data']['translations'][0]['translatedText']
        return self._unescape(translated_msg)

    def availables(self):
        params = {
            'key': self._api_key,
        }
        resp = requests.get(self._base_url + '/languages', params=params).json()
        langs = [lang['language'] for lang in resp['data']['languages']]
        info = '사용 가능한 언어 코드는 다음과 같아요 ^ㅇ^\n\n'
        return info + ', '.join(langs)

    def set_default_target(self, target):
        self._default_target = target

    def _unescape(self, msg):
        return self._html_parser.unescape(msg)


def run(slack_token, google_token):
    slacker = Slacker(slack_token)
    chat_handler = ChatHandler(slacker, Translator(google_token))

    print('Start event loop...')
    chat_handler.loop()


if __name__ == '__main__':
    slack_token = sys.argv[1]
    google_token = sys.argv[2]
    run(slack_token, google_token)
