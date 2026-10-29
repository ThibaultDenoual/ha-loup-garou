// The game runs as an iframe panel on Home Assistant's own origin, so it can
// borrow the signed-in frontend's access token. Returns null when the page is
// opened on its own (or from the standalone dev server, which needs no token).
export async function haAccessToken() {
  try {
    const auth = window.parent.document.querySelector('home-assistant')?.hass?.auth;
    if (!auth) return null;
    if (auth.expired) await auth.refreshAccessToken();
    return auth.accessToken || null;
  } catch (err) {
    return null;
  }
}
