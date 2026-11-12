# Updates

This page describes how updating works from the first release.

## What happens

1. Thoron looks for a new release on a schedule, and when you open the About page.
2. It downloads the description of the update and checks its signature before reading it.
3. It downloads the new version and checks it against the signed description.
4. It installs the new version next to the running one and asks for one relaunch.

## What never happens

- An update does not delete, move or change your bookmarks, passwords, history, tabs or extensions. It only
  replaces the program.
- An update is not installed if it is unsigned, altered, expired or older than what you have.
- The check sends no identifier and no usage data.

## Your choice

Settings offer three ways: update automatically (the default), only tell me, or off.

## Before a big update

A profile that a newer Chromium version has opened cannot be opened by an older one. Before an update to a
new Chromium major version, Thoron saves a copy of the important profile files, so going back stays possible.
