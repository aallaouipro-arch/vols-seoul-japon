"""Diagnostic temporaire : ce que Google renvoie depuis les serveurs GitHub."""
import time
from tracker.gflights import GoogleFlights
from tracker.booking import BookingBrowser, multicity_url

legs = [("2027-07-21", "CDG+ORY", "SEL")]
for n in (1, 2):
    r = GoogleFlights(adults=n, max_stops=1).search(legs)
    print(f"{n} adulte(s) : best {r.best.price} € {r.best.airlines} {r.best.depart}")
    print("   5 premiers :", sorted((o.price, o.airlines[0], o.depart[-5:]) for o in r.offers)[:5])
    time.sleep(3)

with BookingBrowser() as b:
    url = multicity_url([("2027-07-21", "CDG+ORY", "SEL"), ("2027-08-18", "TYO", "CDG+ORY")])
    b._page.goto(url, wait_until="domcontentloaded")
    b._page.wait_for_timeout(15000)
    print("URL finale :", b._page.url[:120])
    print("TITRE :", b._page.title())
    print("TEXTE :", b._page.inner_text("body")[:1500])
    print("li.pIav2d :", b._page.locator("li.pIav2d").count(), "| li :", b._page.locator("li").count())
