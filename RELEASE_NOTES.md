# ShopFlow v1.1.0 - Release Notes
**Datum:** 2026-04-05 | **Suite:** WishFlow | **Vorige versie:** 1.0.0

---

## Nieuwe features v1.1.0

### CSV Bulk Import (`/admin` > CSV Import)
- Sleep of klik om een CSV te uploaden
- Verplichte kolom: `name`
- Optioneel: barcode, price, category, tags, zone_name, aisle, shelf, description
- Automatische zone-koppeling via zone_name
- UTF-8 BOM + latin-1 fallback voor Excel-exports
- Download CSV template via admin
- Max. 10.000 producten per import

### QR Code Generator (`/admin` > QR Codes)
- QR code voor de winkelingang (klant-app)
- QR code per zone (navigeert direct naar die afdeling)
- Printpagina met alle zones in een raster
- Lamineerklaar afdrukken via browser

### Analytics Dashboard (`/admin` > Analytics)
- Sessies per dag (14 dagen trend + Chart.js grafiek)
- Sessies deze week / maand / totaal
- Top zones per productaantal
- **Gemiste producten:** producten die AI zocht maar niet vond in uw catalogus
- Catalogus gezondheidscore (0-100): puntenaftrek voor ontbrekende tags en zones
- Aandachtspunten per product met specifieke verbeteringen

### White-label Branding (`/admin` > Branding)
- Primaire en secundaire kleur instellen
- Logo URL
- Winkel tagline
- Welkomstbericht in NL en FR
- Standaard taal instellen (NL/FR)
- "Powered by ShopFlow" tonen/verbergen
- Opgeslagen in `app_settings` tabel (LifeFlow-compatible)

---

## Verbeteringen
- Dashboard: catalogus gezondheidsscore nu direct zichtbaar
- Zones: QR knop toegevoegd per zone
- Producten: knop naar CSV import

---

## Installatie Replit (upgrade van v1.0.0)
```
py INSTALL.ps1
```
De database wordt automatisch bijgewerkt (backwards compatible).

## Installatie Azure (upgrade)
```powershell
az acr build --registry wishflowacr --image shopflow:1.1.0 .
az containerapp update --name shopflow --resource-group trustai-north-rg --image wishflowacr.azurecr.io/shopflow:1.1.0
```

## Rollback naar v1.0.0
```powershell
$env:PREVIOUS_VERSION = "1.0.0"
.\scripts\rollback.ps1
```

---

## Roadmap v1.2.0
- [ ] Drag-and-drop winkelkaart editor
- [ ] Productafbeeldingen upload (Azure Blob)
- [ ] Medewerker-login (aparte rol)
- [ ] Push notificaties
- [ ] Kassasysteem integratie (Lightspeed API)
