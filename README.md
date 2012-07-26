arun.chagantys.org
------------------

Source code for my website. The general design is inspired by ruhoh,
jekyll and all those things that advocate website management through
git. I'm just building my own out of NIH syndrome and also to customise
a bit.

Features
--------
* Management through git.
* All pages are actually in pandoc-like markdown (with additional syntax
  to support links and files).
* All static pages! Also, generates a static index.
* Tag support
* Version control might be a future feature.

Installing
----------
You will need to copy the webpage.conf.tmpl to webpage.conf. 

File and Index Generation
-------------------------
Every git push activates a script (python) that processes the files, and
finally builds an index for search.

File Uploads and Image Handling
--------------------------------
It's git, just add your pictures as and how you'd like, and link to them
from your pages!

Tag Support
-----------
Tags are supported through some minor syntax additions. The title,
description (optional) and tags are specified like mail headers, e.g.

> %  How I made my own website.
> % 
> % 
> % Description: Didn't you always want to know?
> % Tags: boring, website, meta
> 
> My article starts here...
> And never finishes.

Code and LaTeX Support
----------------------
Both are supported by the fantastic pandoc.

