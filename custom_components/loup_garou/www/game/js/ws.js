import { haAccessToken } from './ha_auth.js';
import { t } from './i18n.js';

let _ws = null;
let _onMessage = null;
let _reconnectTimer = null;
let _onConnect = null;
let _reconnectAttempts = 0;
const MAX_RECONNECT_DELAY = 30000;
// Set when HA refused a page that had no token to offer: retrying cannot help.
let _authBlocked = false;

export function connect(onMessage, onConnect) {
  _onMessage = onMessage;
  _onConnect = onConnect;
  _doConnect();
}

export function send(cmd, data = {}) {
  if (_ws && _ws.readyState === WebSocket.OPEN) {
    _ws.send(JSON.stringify({ cmd, data }));
  }
}

function _doConnect() {
  if (_reconnectTimer) { clearTimeout(_reconnectTimer); _reconnectTimer = null; }
  const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
  _ws = new WebSocket(`${proto}//${location.host}/loup_garou/ws`);

  let sentToken = false;

  _ws.onopen = async () => {
    const token = await haAccessToken();
    if (token) {
      sentToken = true;
      _ws.send(JSON.stringify({ type: 'auth', access_token: token }));
    } else {
      _onReady();
    }
  };

  _ws.onmessage = e => {
    let msg;
    try {
      msg = JSON.parse(e.data);
    } catch (err) {
      console.error('WS parse error', err);
      return;
    }
    if (msg.type === 'auth_ok') {
      if (sentToken) _onReady();
      return;
    }
    if (msg.type === 'auth_invalid') {
      _authBlocked = !sentToken;
      return;
    }
    if (_onMessage) _onMessage(msg);
  };

  _ws.onclose = () => {
    if (_authBlocked) {
      _setStatus(t('ui.ws.open_from_ha'), 'disconnected');
      return;
    }
    const delay = Math.min(1000 * (2 ** _reconnectAttempts), MAX_RECONNECT_DELAY);
    _reconnectAttempts += 1;
    _setStatus('Reconnexion…', 'disconnected');
    _reconnectTimer = setTimeout(_doConnect, delay);
  };
}

function _onReady() {
  _reconnectAttempts = 0;
  _setStatus('Connecté', 'connected');
  if (_onConnect) _onConnect();
  send('get_state');
}

function _setStatus(text, className) {
  const el = document.getElementById('ws-status');
  if (el) { el.textContent = text; el.className = className; }
}
