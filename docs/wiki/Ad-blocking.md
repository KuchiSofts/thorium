# Ad blocking

## Today

Thoron comes with the genuine, unmodified uBlock Origin.

## Built in

Thoron is getting an ad and tracker blocker inside the browser itself. It reads the same filter lists as
uBlock Origin, updates them by itself, and blocks before a request leaves the browser.

- It is **off by default** until its last correctness checks are done.
- To try it: open `chrome://flags/#thoron-native-adblock`, set "Built-in ad blocking" to Enabled and
  relaunch. Turn uBlock Origin off while you try it, or both do the same work.
- A site can be allowed: click the icon in the address bar, or use the "Ads and trackers" setting of the site.
- The count of blocked ads and trackers is kept in memory only. Nothing is stored or sent.
