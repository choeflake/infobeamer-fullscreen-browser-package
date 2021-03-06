# Pre-note

I Downloaded the source from https://cdn.infobeamer.com/bulk/browser.zip, 
thanks for the great work!
This version is mentioned to support HTTP request headers. For example 
the `Authorization` header.

## Installation


The installation is not straight forward. The repository contains a large file `overlay.squarefs`. This file it to large for Github as 'normal' git file. Therefore Git LFS is used. But Infobeamer does not support Git LFS.
Another approach is the release feature of Github. But the release feature embeds the project name as root folder into the zip, which is not supported by Infobeamer.

Checkout this repository and create a zip of the contents.
*Note* that the zip must contain the 
'hidden' directory .sv and no root folder.

Example command: ``zip -r PATH_TO_ZIP --exclude=.git\* ./``.

You need to host the zip somewhere and get the download url.
Now Import a new Package into Infobeamer by using the `Add Package` button and select `Create from Url...`.

There is also a pre-packaged zip, but that one will not updated actively: https://github.com/choeflake/infobeamer-fullscreen-browser-package-release/raw/main/browser.zip

# Git LFS

This repository uses Git LFS for the large filesystem overlay. See https://docs.github.com/en/repositories/working-with-files/managing-large-files/configuring-git-large-file-storage.

# Experimental browser for info-beamer hosted

This package allows you to show webpages in a constant rotation.
Just add the urls of the pages you want to display and their individual
display time:

![url list](doc-url-list.png)

# Advanced settings

## JavaScript automation

Certain pages require custom actions after loading. Most of those can
probably automated using a short JavaScript snippet that is run in the
context of the page/iframe. The Script feature allows you to do just
that. Have a look at 

https://community.infobeamer.com/t/full-screen-browser-with-login/166

for some discussion of how all that works.

## Presistent Profile

Usually the browser is started with a disposable user profile. If
you restart the Pi or switch between the browser and some other
info-beamer setup, all cookies and other browser settings are lost.

Most of the time this is actually  beneficial as no data has to be
written to the SD card and you can be sure that the browser behaves
exactly the same each time.

The persistent profile option allows you to store the chrowser
settings on your SD card instead. They then most likely survive
Pi restarts and set cookies are persistet. 

Note that you need to either restart the setup or your Pi for this
setting to have any effect.

## Custom certificates

If you use an internal CA for custom SSL certificates, you can
add their PEM formatted certificate here. They will then be
available to the browser for verification.

Note that you need to either restart the setup or your Pi for this
setting to have any effect.

# Releases

## Version 86

 * Updated bundled Chromium
 * Restart X on rotation change

## Version 78

 * Compatibility with info-beamer OS 12 release
 * Added option to rotate content

## Version 65.4 

 * Improved interaction with power saver package
 * Added support for fetching scripts from a remote url

## Version 65.cert.3

 * Added timezone support

## Version 65.cert.2

 * Devices update their content immediately on config change
 * Fallback page if no url playlist is set
 * Unload previous page after switching to free up memory and CPU

## Version 65.cert

 * Added support for custom trusted certificates
