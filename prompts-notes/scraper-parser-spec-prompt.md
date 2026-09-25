Example

Link from clicking the "Del annonse" button:
https://www.finn.no/475878513

Link compied from browser adress bar:
https://www.finn.no/recommerce/forsale/item/475878513

Image 1:
https://www.finn.no/recommerce/forsale/item/475878513?ci=1
Image 2:
https://www.finn.no/recommerce/forsale/item/475878513?ci=2
Image 25:
https://www.finn.no/recommerce/forsale/item/475878513?ci=25

Rightclicking on the big image and clicking copy link adress copies this link:
https://images.finncdn.no/dynamic/1280w/item/476480646/be0964ba-3c1d-4e2c-9d25-9db0a1cfeb30

If I use the link from the share this page or what it's called in English, then I will immediately be taken to the link that is copied from the browser address bar, which shows the first image as a big image immediately. And then there are thumbnails below for the smaller images, but when I click on next image, well actually I don't know if it loads it, I can check the internet here if the internet usage is spiking when I'm scrolling through. okay so it does actually load the images dynamically which means it makes sense based of well based of the urls i guess based off the links.

We hhave to get the maxi,u, size for all images. That is very important.



Use web_to_md.py and run it with --js
uv run C:\data\code\93andresen_Scripts\web_to_md.py "https://www.finn.no/recommerce/forsale/item/475878513?ci=20" --output "C:\data\code\marius-pokemonkort\finn\annonser\{folder_structure}" --js
you should replace the "folder_structure" variable with the ideal folder structure for this project.

I tested running these:
### A
uv run C:\data\code\93andresen_Scripts\web_to_md.py "https://www.finn.no/recommerce/forsale/item/475878513?ci=20" --output "C:\data\code\marius-pokemonkort\finn\annonser\tests\-image-20-default"
### B
uv run C:\data\code\93andresen_Scripts\web_to_md.py "https://www.finn.no/recommerce/forsale/item/475878513?ci=20" --output "C:\data\code\marius-pokemonkort\finn\annonser\tests\-image-20-js" -js

**Direct answer first: Nothing is unique to Block A.** Every single piece of information in A is also present in B. Block B contains everything A has, plus additional elements. So A is a strict subset of B.

## The blocks

- **Block A ("Clean static capture", `image-20.md`)** — a lean extraction of the FINN.no ad "Stort vintage salg av Pokemon Holo/Rare/Japansk" (FINN-kode 475878513, Inaktiv, 100 kr, Lysaker). Core content only: description, condition codes, card list, gallery thumbnails, footer.
- **Block B ("JS-rendered capture", `image-20-js.md`)** — the exact same ad page, but captured with JavaScript rendering and accessibility labels included, so it also contains interactive elements, icon descriptions, and a duplicated high-resolution gallery.

## What is in B but NOT in A

1. **Favorite count: "13"** — B shows "13Legg til som favoritt", revealing the ad has 13 favorites. A only has the button with no number. This is probably the most interesting unique data point.
2. **"Send melding" button** under the price — only in B.
3. **"Pluss tegn"** — the expand button after the card list — only in B.
4. **"Papirkart"** label on the map link — only in B.
5. **A "Meldinger" link** in the top navigation — only in B.
6. **Formatted breadcrumbs**: `/Torget/Fritid, hobby og underholdning/Samleobjekter/Samlekort`. A has the same category text but mashed together without separators.
7. **A second, higher-resolution gallery**: 25 images at 960w in addition to the 25 thumbnails at 142w. Same image UUIDs though — no new pictures, just larger versions.
8. **Accessibility/icon descriptions throughout**: navigation arrows, "Buet pil" on Del annonse, "Kartnål" next to pickup-only similar ads, "Lastebil i bevegelse" next to Fiks ferdig similar ads, "Bjelle" for notifications, "Sirkel med plusstegn", "Sirkel med brukerprofil", "Leilighetsbygg", and a fashion banner arrow. Incidentally, the map-pin vs truck labels reveal which similar ads offer shipping versus pickup only.

### Search URLs searching for "pokemon kort" and various types of sortings and filtering:

I have npt bothered to Manually type out what each of these do sp  if u are unsure about anything just ask me.

You should make a complete map of every filter and parameter available on finn.no when searching.

This is important and will allow you to, well, use all those functionaleties...

This is useful for creating the entire system and is also useful for agentic tasks in general, which will also be a part of what we are building here so that everything is truly as convenient and fast and optimal and magical as possible!

https://www.finn.no/recommerce/forsale/search?q=pokemon+kort

Different sortings
https://www.finn.no/recommerce/forsale/search?q=pokemon+kort&sort=PUBLISHED_ASC
https://www.finn.no/recommerce/forsale/search?q=pokemon+kort&sort=RELEVANCE
https://www.finn.no/recommerce/forsale/search?q=pokemon+kort&sort=PUBLISHED_DESC

Location set to Kristiansand in the rest of the sorting examples
https://www.finn.no/recommerce/forsale/search?polylocation=7.79909+58.06482%2C7.79909+58.03335%2C7.92956+58.05346%2C8.05508+58.03685%2C8.12775+58.07180%2C8.15252+58.10672%2C8.13766+58.36581%2C7.71816+58.36581%2C7.71321+58.03423%2C7.79909+58.06482&q=pokemon+kort&sort=PUBLISHED_DESC
https://www.finn.no/recommerce/forsale/search?polylocation=7.79909+58.06482%2C7.79909+58.03335%2C7.92956+58.05346%2C8.05508+58.03685%2C8.12775+58.07180%2C8.15252+58.10672%2C8.13766+58.36581%2C7.71816+58.36581%2C7.71321+58.03423%2C7.79909+58.06482&q=pokemon+kort&sort=PRICE_DESC
https://www.finn.no/recommerce/forsale/search?polylocation=7.79909+58.06482%2C7.79909+58.03335%2C7.92956+58.05346%2C8.05508+58.03685%2C8.12775+58.07180%2C8.15252+58.10672%2C8.13766+58.36581%2C7.71816+58.36581%2C7.71321+58.03423%2C7.79909+58.06482&q=pokemon+kort&sort=PRICE_ASC

Searching for "pokemon kort" in "Samleobjecter" (This is all pokemon cards)
https://www.finn.no/recommerce/forsale/search?q=pokemon+kort&sort=PUBLISHED_ASC&stored-id=90502263&sub_category=1.86.285
https://www.finn.no/recommerce/forsale/search?q=pokemon+kort&sort=RELEVANCE&stored-id=90502263&sub_category=1.86.285
https://www.finn.no/recommerce/forsale/search?q=pokemon+kort&sort=PUBLISHED_DESC&stored-id=90502263&sub_category=1.86.285
https://www.finn.no/recommerce/forsale/search?lat=58.15246&lon=7.96833&q=pokemon+kort&sort=CLOSEST&stored-id=90502263&sub_category=1.86.285
https://www.finn.no/recommerce/forsale/search?lat=58.15246&lon=7.96833&q=pokemon+kort&sort=PRICE_DESC&stored-id=90502263&sub_category=1.86.285
https://www.finn.no/recommerce/forsale/search?lat=58.15246&lon=7.96833&q=pokemon+kort&sort=PRICE_ASC&stored-id=90502263&sub_category=1.86.285

---

