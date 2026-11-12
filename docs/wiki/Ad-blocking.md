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
- **Sees through disguised ad servers.** Some ad servers change their names all the time. When a
  server's answer gives it away, the answer is thrown away before the page sees it.
- **Skips tracking detours.** A link that leads to a tracker first, which then sends you on, goes straight
  to the real page.
- **Switches off ad-tech features.** Browser features that were built for ad targeting, or that help to
  tell your browser from others (ad topics, ad auctions, idle detection and a few more), are off on every
  site.
- **Cleans addresses.** Tracking parts of addresses are taken out, also where a site writes them into
  the path.
- **Cleans the page.** Leftover ad boxes are hidden (also inside widgets that keep their content apart),
  tracking parameters are removed from addresses, and
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

- **The shield in the toolbar:** while the blocker is on, a shield sits next to the extensions button.
  Its number is what was blocked on the page you look at. Click it for the menu:
  - the big **power button** switches blocking off or on for this site (the page reloads);
  - the counts: blocked on this page, sites blocked on this page, blocked so far;
  - **Block element:** click the thing you want gone, choose or edit the rule, press Enter or
    Create. The rule goes into My filters and works at once;
  - **Zapper:** click things to remove them until the page reloads; Esc stops;
  - **Logger:** every blocked request of your open tabs;
  - **Settings:** the full page, `chrome://adblock`;
  - switches for this site: pop-ups (no window the site opens, also from a click), large media (sound
    and video over 50 KB), no hiding, remote fonts, JavaScript. A blue switch means it is on.

- **Pop-ups:** ad windows and tabs a page tries to open are not opened at all, and count on the shield.

- **See what happened:** when something was blocked, an icon appears in the address bar. Click it to see
  how many ads and trackers were blocked on the page, and from which sites.
- **Allow a site:** tick "Always allow ads and trackers on this site" in that bubble, or click the icon
  left of the address, open "Site settings" and set "Ads and trackers" to Allow. Reload the page.
- **Allow everywhere or manage allowed sites:** Settings, "Privacy and security", "Site settings",
  "Additional content settings", "Ads and trackers".

### Lists and your own rules

Open `chrome://adblock`.

- **More lists:** cookie notices, annoyances, more privacy and lists for your region or language, as
  uBlock Origin offers them. Tick a list to add it; untick it to remove it.
- **Filter lists:** every list has a checkbox. A list that is switched off is neither used nor downloaded.
  "Update now" looks for newer lists at once.
- **Add a list:** paste its address (it must start with `https://`) and press Add. The list is checked
  first; something that is not a filter list is refused, and the page says why. Remove takes it out again.
- **My filters:** write your own rules, one per line, and press Save. For example `||ads.example.com^`
  blocks a host, `example.com##.banner` hides something on a site, and `@@||example.com^` allows a site.

Every change is in use at once, and stays after a restart and after an update of the browser. What you
choose stays on your computer. A list you add is fetched from its address every few days, without cookies.

Rules of a list you add, and your own rules, block and hide like any other. They cannot use the powerful
scripts that only uBlock Origin's own lists may use.

### What it cannot do yet

- **Pick an element on a page to hide it.** Planned next.
- **A few rare kinds of rules** in the lists are not applied yet (ROADMAP P5.26).

## uBlock Origin

The genuine, unmodified uBlock Origin extension. Its dashboard has everything it always had: choosing
lists, your own filters, the element picker and the logger. Thoron never changes its settings or your
filters, also not when the built-in blocker becomes the default.
