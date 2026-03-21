# Installatiehandleiding voor een nieuwe PC

Deze handleiding helpt je om het DeGiro Dashboard op te zetten op een computer die zojuist een factory reset heeft gehad.

## 1. Installeer Python
Aangezien de PC nieuw is, moet Python eerst geïnstalleerd worden:
1. Ga naar [python.org](https://www.python.org/downloads/windows/).
2. Download de laatste versie (bijv. Python 3.11 of 3.12).
3. **BELANGRIJK:** Vink tijdens de installatie de optie **"Add Python to PATH"** aan!
4. Klik op "Install Now".

## 2. Het project downloaden
Zorg dat de projectmap (met `app.py`, `requirements.txt`, etc.) op de nieuwe PC staat.
*   Als je dit via OneDrive doet: zorg dat de map gesynchroniseerd is en "Altijd behouden op dit apparaat" is ingeschakeld.

## 3. Terminal openen
1. Open de map waar de bestanden staan in Verkenner.
2. Klik in de adresbalk van de map, typ `cmd` en druk op Enter. Of klik met de rechtermuisknop op een lege plek in de map en kies "In Terminal openen" (Windows 11).

## 4. Virtuele omgeving aanmaken (VENV)
Het is aanbevolen om een virtuele omgeving te gebruiken om je dependencies gescheiden te houden:
```powershell
# Maak de omgeving aan
python -m venv .venv

# Activeer de omgeving
.venv\Scripts\activate
```

## 5. Dependencies installeren
Zodra de virtuele omgeving geactiveerd is (je ziet `(.venv)` voor je prompt), installeer je de benodigde bibliotheken:
```powershell
pip install -r requirements.txt
```

## 6. Streamlit Secrets (Google Drive koppeling)
Voor de koppeling met Google Drive moet je handmatig een bestand aanmaken:
1. Maak een map genaamd `.streamlit` (let op de punt) in de projectmap (als deze nog niet bestaat).
2. Maak in die map een bestand genaamd `secrets.toml`.
3. Plak hierin de Google Service Account gegevens die je voorheen ook gebruikte.

## 7. Het dashboard starten
Voer het volgende commando uit in de terminal:
```powershell
streamlit run app.py
```
Het dashboard opent nu automatisch in je browser.

---
> [!TIP]
> Als je later het dashboard opnieuw wilt starten, hoef je alleen stap 3, 4 (activeren) en 7 te herhalen.

test3
