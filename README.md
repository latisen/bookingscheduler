# Istidsplanerare (Flask MVP)

Webapp for grafisk schemalaggning av istider for flera foreningar och hallar.

## Teknik
- Backend: Python + Flask
- Frontend: HTML, CSS, JavaScript
- Lagring: lokala JSON-filer i data/

## Projektstruktur
- app/: Flask-kod, datamodeller, schemalaggning, validering
- templates/: HTML-mallar
- static/: CSS och JavaScript
- data/: JSON-filer som lagrar resurser och schema
- data/seed/: seed-data for snabb uppstart
- exports/: plats for exporterade filer

## Kom igang
1. Skapa virtuell miljo:
   - macOS/Linux:
     - `python3 -m venv .venv`
     - `source .venv/bin/activate`
2. Installera beroenden:
   - `pip install -r requirements.txt`
3. Starta appen:
   - `python run.py`
4. Oppna i webblasare:
   - `http://127.0.0.1:5000`

## Funktioner i MVP
- Hallar: skapa, redigera, ta bort
- Foreningar: skapa, redigera, ta bort (namn + farg)
- Tidsblock: skapa, redigera, ta bort per forening/hall/veckodag
- Grupper: skapa, redigera, ta bort med schemaregler
- Kombinerade pass: skapa, redigera, ta bort (raknas for alla grupper)
- Spolningsregler: skapa, redigera, ta bort
- Automatisk schemalaggning (deterministisk):
  - harda regler prioriteras
  - mjuka mal anvands for scoring
- Grafisk veckovy med dagar och hallar
- Drag-and-drop:
  - flytt till annan tid/hall
  - byte mellan pass
  - backendvalidering, med valfritt manuellt undantag
- Konfliktpanel:
  - ej placerade pass med orsaker
  - konflikter
  - outnyttjade tider per hall/dag
- Export: JSON, CSV, PDF, PNG
- Spara/ladda schema till/fran data/schedule.json

## Harda regler (i motorn)
- Pass maste rymmas inom tillgangliga tidsblock
- Inga overlapp i samma hall
- Gruppers hallkrav foljs (allowed, forbidden, strict)
- Max pass per vecka foljs
- Regler for ingen dubbelbokning samma dag foljs
- Minsta vila mellan pass foljs
- Kombinerade pass raknas per grupp
- Spolningsregler foljs (buffer, max i rad, blockerade veckodagar)

## Mjuka regler (scoring)
- Narhet till onskade dagar/tider
- Undvik dagar i rad nar gruppen markerat det
- Yngre grupper tidigare, senior/vuxen senare
- Hallspridning for grupper som kan trana i flera hallar

## AI-modul
app/ai_assistant.py ar forberedd for framtida OpenAI-integration.
- MVP ar helt deterministisk utan AI
- AI-forslag ska alltid valideras mot harda regler i backend innan visning

## Seed-data
Innehaller exempel for:
- Foreningar:
  - Tyringe KS (mjuk lila)
  - Tyringe Hockey (mjuk rod)
- Hallar:
  - Tyrs Hov
  - Osteras
- Grupper, kombinerade pass, tidsblock och spolningsregler

Reset till seed i UI via knappen "Aterstall seed".

## Vidareutveckling
- Mer avancerad optimering (t.ex. lokalsokning/soktradsmetoder)
- Exakt validering av fler regeltyper
- Forbattrad PNG/PDF-layout med riktig veckotabell
- Autentisering och versionshantering av schema
