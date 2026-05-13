# ShopFlow Handleiding v1.2.0

## Wat is ShopFlow?
ShopFlow helpt klanten producten te vinden in uw winkel, garage of opslagruimte via een digitale kaart en AI-gestuurde reparatiegidsen.

---

## Snel aan de slag

### 1. Inloggen als beheerder
Ga naar `/admin` en log in met uw winkelnaam en wachtwoord.

### 2. Zones aanmaken
Via **Admin > Zones** maakt u afdelingen aan (bijv. "Verf", "Sanitair", "Gereedschap").
Sleep zones op de kaart naar de juiste positie en kies een kleur en icoon.

### 3. Producten toevoegen
Via **Admin > Producten** of via **Admin > CSV Import**.
Vul voor elk product de zone, het rek en de positiebeschrijving in.

---

## Markers (nieuw in v1.2.0)

### Wat zijn markers?
Markers zijn genummerde stickers of borden die u fysiek ophangt in uw winkel, garage of opslagruimte. Elke marker heeft een nummer (bijv. 1, 2, 3...) en staat voor een groep producten op die locatie.

**Voorbeelden:**
- Winkel: marker 5 bij de verfrollers, marker 12 bij de schroeven
- Garage: marker 1 bij de ingang, marker 2 bij de werkbank, marker 3 bij de rekken
- Opslag: marker 1 = zomerspullen, marker 2 = gereedschap

### Markers instellen (medewerker)

**Via Admin > Markers:**
1. Klik op "Nieuwe marker"
2. Kies een markernummer (1–999)
3. Stel het locatietype in: Winkel / Garage / Thuis
4. Klik op de kaart om de positie in te stellen
5. Koppel producten aan de marker
6. Klik "Aanmaken"

**Via de medewerker-app (`/location`) op smartphone:**
1. Log in met uw beheerdersgegevens
2. Kies een markernummer
3. Klik op de kaart waar de marker hangt
4. Voeg producten toe met hoeveelheidsnotitie (bijv. "10 pakjes")
5. Sla op

**Tip voor grote ruimtes:**
Plak markernummer-stickers op de schappen en filmde de opstelling.
Zo weet u altijd: "schroevendraaier? → marker 3, 2e rek"

### Klant zoekt via marker

De klant-app (`/app`) heeft een tabblad "Locatie":
1. Klant typt het markernummer in
2. App toont alle producten bij die marker
3. De marker wordt gemarkeerd op de winkelkaart

---

## QR Codes
Genereer QR codes via **Admin > QR Codes** en hang ze bij de ingang.
Klanten scannen de QR → openen de klant-app direct in hun browser.

---

## AI Reparatiegids
De klant beschrijft een probleem (bijv. "lekkende kraan") → de AI genereert:
- Stap-voor-stap reparatie-instructies
- Lijst met benodigde producten uit uw winkel
- Locatie van die producten op de kaart

---

## Analytics
Via **Admin > Analytics** ziet u:
- Sessies per dag (trend grafiek)
- Meest gezochte producten
- Gemiste producten (zoekterm niet gevonden in catalogus)
- Catalogus gezondheidsscore (0–100)

---

## Branding
Pas uw huisstijl aan via **Admin > Branding**:
- Logo, primaire kleur, tagline
- Welkomstbericht in NL en FR
- "Powered by ShopFlow" aan/uit

---

## Technische installatie

### Replit
De app start automatisch via `start.sh`. Database wordt bij opstart aangemaakt.

### Azure Container Apps
```powershell
az acr build --registry wishflowacr --image shopflow:1.2.0 .
az containerapp update --name shopflow --resource-group trustai-north-rg --image wishflowacr.azurecr.io/shopflow:1.2.0
```

---

## Vragen of problemen?
Raadpleeg `RELEASE_NOTES.md` voor technische details of neem contact op met de beheerder.
