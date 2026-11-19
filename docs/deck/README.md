# Presentation deck (Nov 30)

Google Slides: "Spend Shadow: FIN 440 AI Project" in Ashton's Drive (15 slides, speaker notes on each).
Since Nov 19, 2026 this is the v3 restyle (Liquid Glass light, matching the app), made by the `spend-deck`
agent on a copy and then promoted. The v1 deck is kept as "Spend Shadow: FIN 440 AI Project (old v1,
replaced)". The v3 slide charts were built in the app palette from the same Nov 18 prices and are
inserted by hand from Drive (`spend-shadow-v3-*.png`); the matplotlib scripts below still make the v1 charts.

The deck's charts and numbers come from the app's own engines on one Yahoo price snapshot, so they
can be regenerated and checked:

```
pip install matplotlib==3.10.7 python-pptx==1.0.2   # deck tools only, not app requirements
python docs/deck/build_deck.py   # charts (*.png) + numbers.json from the sample data and live prices
python docs/deck/make_pptx.py    # Spend_Shadow_FIN440.pptx
```

Prices move daily, so dollar figures will drift slightly from the Nov 18, 2026 snapshot in the deck.
Two edits were made directly in Google Slides after upload: the "34% reach $705k" card text was
set to 20pt, and the Monte Carlo bullet on the Proof slide says "within 3 standard errors".
