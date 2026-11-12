# Ad blocking

Thoron has two ad blockers. One is the uBlock Origin extension, which comes with the browser today. The
other is built into the browser itself and is meant to replace the extension once it is finished.

## The built-in blocker

### How it works

- **Same lists as uBlock Origin.** EasyList, EasyPrivacy, the uBlock filter lists (ads, privacy, badware,
  quick fixes, unbreak), Peter Lowe's list and a list of malware sites.
- **Works from the first page.** The lists come with the browser, already prepared, so nothing has to be
  downloaded before it blocks.
- **Keeps itself current.** It fetches newer lists at most every 4 days, over HTTPS, without cookies or
  identifiers. A list that looks wrong is refused and the previous one stays.
- **Blocks before the request leaves.** A request for an ad or a tracker is stopped inside the browser.
  This covers pages, frames, redirects, web workers and WebSocket connections.
- **Cleans the page.** Leftover ad boxes are hidden, tracking parameters are removed from addresses, and
  small scripts from uBlock Origin defuse anti-blocker code. A blocked script that a page needs is answered
  with a harmless stand-in, so the page keeps working.
- **Private.** What is blocked is counted in memory only. Nothing is stored or sent.

Because it is part of the browser, it starts before any page script runs, and it measures faster and
lighter than the extension with the same blocking.

### Turn it on

It is **off by default** until its last correctness checks are done.

1. Open `chrome://flags/#thoron-native-adblock`.
2. Set "Built-in ad blocking" to **Enabled** and relaunch.
3. Turn uBlock Origin off on `chrome://extensions`, or both do the same work.

### Use it

- **See what happened:** when something was blocked, an icon appears in the address bar. Click it to see
  how many ads and trackers were blocked on the page.
- **Allow a site:** tick "Always allow ads and trackers on this site" in that bubble, or click the icon
  left of the address, open "Site settings" and set "Ads and trackers" to Allow. Reload the page.
- **Allow everywhere or manage allowed sites:** Settings, "Privacy and security", "Site settings",
  "Additional content settings", "Ads and trackers".

### What it cannot do yet

- **Your own filters and lists.** You cannot yet add a list, switch a list off or write your own rules.
  This is planned as a page in Settings (ROADMAP P5.30). Until then, uBlock Origin does this.
- **Pick an element on a page to hide it.** Planned after that.
- **A few rare kinds of rules** in the lists are not applied yet (ROADMAP P5.26).

## uBlock Origin

The genuine, unmodified uBlock Origin extension. Its dashboard has everything it always had: choosing
lists, your own filters, the element picker and the logger. Thoron never changes its settings or your
filters, also not when the built-in blocker becomes the default.
