let _ws = null;
let _onMessage = null;
let _reconnectTimer = null;
let _onConnect = null;
let _reconnectAttempts = 0;
const MAX_RECONNECT_DELAY = 30000;

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

  _ws.onopen = () => {
    _reconnectAttempts = 0;
    _setStatus('Connecté', 'connected');
    if (_onConnect) _onConnect();
    send('get_state');
  };

  _ws.onmessage = e => {
    try {
      if (_onMessage) _onMessage(JSON.parse(e.data));
    } catch (err) {
      console.error('WS parse error', err);
    }
  };

  _ws.onclose = () => {
    const delay = Math.min(1000 * (2 ** _reconnectAttempts), MAX_RECONNECT_DELAY);
    _reconnectAttempts += 1;
    _setStatus('Reconnexion…', 'disconnected');
    _reconnectTimer = setTimeout(_doConnect, delay);
  };
}

function _setStatus(text, className) {
  const el = document.getElementById('ws-status');
  if (el) { el.textContent = text; el.className = className; }
}
