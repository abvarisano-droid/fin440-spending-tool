# Presentation deck (Nov 30)

Google Slides: "Spend Shadow: FIN 440 AI Project" in Ashton's Drive (15 slides, speaker notes on each).

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
