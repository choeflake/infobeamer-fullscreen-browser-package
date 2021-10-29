#!/usr/bin/python2.7
import os
import re
import sys
import time
import urllib
import websocket
import requests
import traceback
import select
import json
import socket
from collections import namedtuple
from itertools import count, cycle

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
def send_ib(data):
    sock.sendto(data, ('127.0.0.1', 4444))
def log(msg):
    print >>sys.stderr, "[control] %s" % msg

http = requests.Session()
http.headers.update({
    'User-Agent': 'browser package'
})

FrameContext = namedtuple('FrameContext', 'context_id origin')

class Frame(object):
    def __init__(self):
        self.id = None
        self.url = None
        self.origin = None
        self.context_id = None

    def __str__(self):
        return '<Frame %s %s %s %s>' % (self.id, self.url, self.origin, self.context_id)
    __repr__ = __str__

class EventLoop(object):
    def __init__(self):
        self._poller = select.poll()
        self._fd_to_handler = {}
    
    def register(self, fd, handler):
        self._fd_to_handler[fd] = handler
        self._poller.register(fd, select.POLLIN)

    def unregister(self, fd):
        self._poller.unregister(fd)
        del self._fd_to_handler[fd]

    def dispatch(self, timeout_ms):
        while 1:
            events = self._poller.poll(timeout_ms)
            if not events:
                break
            for fd, event in events:
                handler = self._fd_to_handler[fd]
                try:
                    handler()
                except:
                    traceback.print_exc()

class Tab(object):
    def __init__(self, eventloop, page):
        self._connection = None
        self._fd = None
        self._next_id = count().next
        self._eventloop = eventloop
        self._loaded = True
        self._scripts = None
        self._socket_url = None
        self._frames = {}
        self.update(page)

    def update(self, page):
        # print page
        self._id = page['id']
        if not self._socket_url:
            # Might be empty in /json/list
            self._socket_url = page['webSocketDebuggerUrl']
        # For rpc information, see https://chromedevtools.github.io/devtools-protocol/
        self.ensure_connected()

    def ensure_connected(self):
        if self._connection:
            return
        try:
            self._connection = websocket.create_connection(self._socket_url)
            self._fd = self._connection.fileno()
        except Exception:
            traceback.print_exc()
            return
        log("websocket connected")
        self._eventloop.register(self._fd, self.receive_rpc)
        self.call_rpc("Network.enable")
        self.call_rpc("Page.enable")
        self.call_rpc("Runtime.enable")
        self.call_rpc("DOM.enable")

    def reset_connection(self):
        log("websocket disconnected")
        self._eventloop.unregister(self._fd)
        self._connection.close()
        self._connection = None

    def call_rpc(self, name, **args):
        self.ensure_connected()
        rpc = json.dumps({
            "id": self._next_id(),
            "method": name,
            "params": args,
        })
        log(">>> %s %s" % (self._id, rpc))
        try:
            self._connection.send(rpc)
        except websocket.WebSocketConnectionClosedException:
            self.reset_connection()
        except Exception:
            traceback.print_exc()
            self.reset_connection()

    @property
    def is_loaded(self):
        return self._loaded

    def rpc_runtime_executioncontextcreated(self, context, **created):
        frameId = context['auxData']['frameId']
        f = self._frames.get(frameId)
        if f is None:
            f = self._frames[frameId] = Frame()
        f.context_id = context['id']
        f.origin = context['origin']

    def rpc_runtime_executioncontextdestroyed(self, executionContextId):
        for frame_id, frame in self._frames.iteritems():
            if frame.context_id == executionContextId:
                del self._frames[frame_id]
                break

    def rpc_page_framestartedloading(self, frameId):
        f = self._frames[frameId] = Frame()
        f.id = frameId
        
    def rpc_page_framenavigated(self, frame):
        f = self._frames[frame['id']]
        f.url = frame['url']
        f.origin = frame['securityOrigin']

    def rpc_page_framestoppedloading(self, frameId):
        f = self._frames[frameId]
        log("===> Loaded %s %s %s %s" % (f.id, f.url, f.origin, f.context_id))

        self.call_rpc("Runtime.evaluate", expression="""
            let style = document.createElement('style')
            document.head.appendChild(style)
            let sheet = style.sheet
            sheet.insertRule(`
                html {
                    overflow: hidden;
                }
            `)
        """, contextId=f.context_id)

        script = self._scripts.get_script(f.url)
        if script:
            log("RUNNING SCRIPT:\n" + script)
            self.call_rpc("Runtime.evaluate", expression=script, contextId=f.context_id)

    def rpc_page_loadeventfired(self, timestamp, **kwargs):
        self._loaded = True

    def runtime_consoleapicalled(self, timestamp, args, type, **kwargs):
        if type == 'log' and args and args[0]['type'] == 'string':
            log("===== CONSOLE LOG: %s" % args[0]['value'])

    def receive_rpc(self):
        try:
            response = json.loads(self._connection.recv())
            log("<<< %r" % response)
            # pprint.pprint(response)
            if 'id' in response:
                return
            method = response['method']
            params = response.get('params', {})
            mangled = "rpc_%s" % re.sub("[^\w]", "_", method.lower())
            handler = getattr(self, mangled, None)
            if handler:
                handler(**params)
        except Exception:
            traceback.print_exc()
            self.reset_connection()

    def navigate(self, url, scripts, headers):
        self._loaded = False
        self._frames = {}
        self._scripts = scripts
        self._headers = headers
        self.call_rpc("Network.setExtraHTTPHeaders", headers=headers)
        self.call_rpc("Page.navigate", url=url)

class Browser(object):
    def __init__(self, eventloop, base_url="http://127.0.0.1:9222"):
        self._base_url = base_url
        self._eventloop = eventloop
        self._tabs = []
        self._tab_by_id = {}
        self.update_tabs()

    def update_tabs(self):
        self._tabs = []
        for prio, page in enumerate(http.get(self._base_url + "/json/list").json()):
            # pprint.pprint(page)
            if page['type'] != 'page':
                continue
            page['prio'] = prio
            id = page['id']
            if not id in self._tab_by_id:
                self._tab_by_id[id] = Tab(self._eventloop, page)
            else:
                self._tab_by_id[id].update(page)
            self._tabs.append(id)
        # pprint.pprint(self._tabs)

    @property
    def tabs(self):
        return self._tabs

    def open(self, url):
        page = http.get((self._base_url + "/json/new?%s") % urllib.quote(url)).json()
        id = page['id']
        self._tab_by_id[id]= Tab(self._eventloop, page)
        self._tabs.append(id)

    def navigate(self, idx, url, script, headers):
        id = self.tabs[idx]
        log("=== Navigate %s -> %s (headers: %s)" % (id, url, headers))
        self._tab_by_id[id].navigate(url, script, headers)

    def switch_to(self, idx):
        id = self.tabs[idx]
        log("=== Switch %s" % id)
        http.get(self._base_url + "/json/activate/%s" % id)
        self.update_tabs()

    def is_loaded(self, idx):
        id = self.tabs[idx]
        return self._tab_by_id[id].is_loaded

    def close(self, idx):
        if len(self._tabs) == 1:
            return
        id = self.tabs[idx]
        http.get(self._base_url + "/json/close/%s" % id).content
        self.update_tabs()

    def tick(self):
        for i in xrange(10):
            self._eventloop.dispatch(100)

class Scripts(object):
    def __init__(self, script_config):
        self._scripts = []
        for config in script_config:
            if isinstance(config, list):
                pattern, script = config
                script_url = None
            else:
                pattern = config['pattern']
                script = config.get('script')
                script_url = config.get('script_url')
            if not script and not script_url:
                log("at least one of 'script' or 'script_url' must be set")
                continue
            self._scripts.append(dict(
                match = re.compile(pattern).match,
                script = script,
                script_url = script_url,
            ))
        log("loaded %d scripts" % len(self._scripts))

    def get_script(self, url):
        for script in self._scripts:
            if not script['match'](url):
                continue
            if script['script_url']:
                log("found script_url for [%s]" % (url,))
                try:
                    r = http.get(
                        url = script['script_url'],
                        timeout = 5,
                    )
                    r.raise_for_status()
                    content = r.content
                    log("got script: %d bytes" % (len(content),))
                    return content
                except:
                    traceback.print_exc()
                    log("could not fetch script for [%s]" % (url,))
                    return None
            else:
                return script['script']
        return None

FALLBACK = cycle([
    (10, 'http://127.0.0.1:8888/no-playlist.html', Scripts([]))
]).next

class Configuration(object):
    def __init__(self, config_json):
        self._urls = FALLBACK
        self._config_json = config_json
        self._prefix = os.path.dirname(config_json)
        self._last_mtime = 0
        self._last_rotation = None
        self.maybe_reload()

    def load_config(self):
        log("[config] Loading %s" % (self._config_json,))
        with open(self._config_json) as f:
            config = json.load(f)
            with open(os.path.join(self._prefix, config['scripts']['asset_name'])) as s:
                scripts = Scripts(json.load(s))

            headers = {}
            _headers = config['headers']
            if _headers:
                for item in _headers:
                    headers[item['name']] = item['value']

            urls = config['urls']
            if urls:
                self._urls = cycle([
                    (item['duration'], item['url'], scripts, headers)
                    for item in urls
                    if item['duration'] > 0
                ]).next
            else:
                self._urls = FALLBACK
            self.update_rotation(config['rotation'])

    def maybe_reload(self):
        updated = False
        try:
            mtime = os.stat(self._config_json).st_mtime
            if mtime != self._last_mtime:
                self.load_config()
                updated = True
                self._last_mtime = mtime
        except Exception:
            traceback.print_exc()
        return updated

    def update_rotation(self, rotation):
        log('rotation is %d rotation' % rotation)
        if self._last_rotation is not None and rotation != self._last_rotation:
            os.system('pkill Xorg')
        self._last_rotation = rotation

    def next_item(self):
        return self._urls()

class Control(object):
    def __init__(self, browser, config):
        self._browser = browser
        self._config = config
        self._next_duration = 0
        self._next_switch = 0
        self._preloading = False

        self.ensure_two_tabs()
        self.preload_next()

    def ensure_two_tabs(self):
        fixed = False
        self._browser.update_tabs()
        while len(self._browser.tabs) < 2:
            fixed = True
            log("[browser-control] Opening new browser tab")
            self._browser.open("about:blank")
        while len(self._browser.tabs) > 2:
            fixed = True
            log("[browser-control] Closing excessive browser tab")
            self._browser.close(2)
        if fixed:
            self._browser.switch_to(0)
        return fixed

    def preload_next(self):
        self._next_duration, url, scripts, headers = self._config.next_item()
        log("[browser-control] Loading %s in tab 1: next switch %d (in %ds)" % (
            url, self._next_switch, self._next_switch - time.time()
        ))
        self._browser.navigate(1, url, scripts, headers)
        self._preloading = True

    def tick(self):
        now = time.time()

        updated = self._config.maybe_reload()
        tab_problem = self.ensure_two_tabs()

        until_switch = self._next_switch - now
        preload = until_switch < 10 and not self._preloading

        log("[browser-control] Tick (%d, %d, %d, %d)" % (
            updated, tab_problem, until_switch, preload
        ))

        if updated or tab_problem:
            log("[browser-control] Forcing next url")
            self._next_switch = now
            self.preload_next()
        elif preload:
            log("[browser-control] Preloading next url")
            self.preload_next()

        self._browser.tick()

        next_ready = self._browser.is_loaded(1) and now > self._next_switch
        next_force = now > self._next_switch + 5

        if next_ready or next_force:
            log("[browser-control] Now switching to tab 1")
            self._browser.switch_to(1)
            send_ib('root/fade:1')
            self._next_switch = now + self._next_duration
            self._preloading = False
            self._browser.navigate(1, 'about:blank', Scripts([]), {})

config_json = os.path.join(os.environ['NODE_PATH'], 'config.json')
if len(sys.argv) == 2:
    config_json = sys.argv[1]

event_loop = EventLoop()
browser = Browser(event_loop)
config = Configuration(config_json)
control = Control(browser, config)

while 1:
    control.tick()
