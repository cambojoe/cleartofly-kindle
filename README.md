# ClearToFly Alsfeld auf dem Kindle Touch (D01200)

Dieses Projekt soll die ClearToFly-Seite für den Flugplatz Alsfeld auf einem älteren Kindle anzeigen. Der Kindle lädt nur eine einfache HTML-Seite mit einem Schwarz-Weiß-Bild; die Wetterseite selbst wird in einem aktuellen Chromium-Browser in GitHub Actions geöffnet. Es wird kein ständig laufender Heimcomputer benötigt.

## Was die Automatisierung macht

- Öffnet täglich die aktuelle Alsfeld-Tagesseite: `https://cleartofly.de/airfield/DE-ALSFELD?date=YYYY-MM-DD`.
- Erfasst den ersten mobilen Bildschirmausschnitt (600 × 720 Pixel), wandelt ihn in Graustufen um und ergänzt eine Zeitangabe.
- Veröffentlicht Bild und eine sehr einfache Anzeigeseite über GitHub Pages.
- Versucht alle 15 Minuten, ein neues Bild zu erstellen. GitHub Actions kann Zeitpläne verzögern; die Aktualisierung ist nicht sekundengenau garantiert.
- Die Kindle-Seite lädt das Bild alle 15 Minuten neu, auch mit einem Cache-Buster für ältere Browser.

## Einmalige Einrichtung

1. Bei GitHub anmelden und ein neues **öffentliches** Repository anlegen, z. B. `cleartofly-kindle`. Öffentlich ist für GitHub Pages mit dem kostenlosen GitHub-Tarif der einfachste Weg. Es werden keine Zugangsdaten oder API-Schlüssel im Repository benötigt.
2. Alle Dateien dieses Projektordners in das Repository hochladen, einschließlich der versteckten Datei bzw. des Ordners `.github/workflows/update-weather.yml`. Am zuverlässigsten ist dafür GitHub Desktop oder Git mit einem einmaligen Push.
3. Im Repository **Settings → Pages** öffnen und bei **Build and deployment → Source** die Option **GitHub Actions** auswählen.
4. Die Registerkarte **Actions** öffnen und den Workflow **ClearToFly Alsfeld – Kindle-Anzeige** über **Run workflow** einmal manuell starten.
5. In der abgeschlossenen Ausführung den veröffentlichten Link (Environment `github-pages`) öffnen. Erst am Laptop prüfen, ob die Wetterdaten im Bild erscheinen und gut genug lesbar sind.
6. Erst danach diese veröffentlichte Adresse auf dem Kindle öffnen. Die Adresse endet normalerweise auf `https://<GitHub-Benutzername>.github.io/<Repositoryname>/`.

## Falls der Screenshot nicht passt

Die erste Version erfasst absichtlich nur den ersten Bildschirmausschnitt, damit die Schrift nicht durch das Verkleinern einer sehr langen Seite unlesbar wird. Wenn wichtige Werte auf dem Screenshot fehlen, werden danach Auflösung, Ausschnitt oder Scrollposition in `scripts/capture.mjs` gezielt angepasst.

Wenn ClearToFly den automatisierten Aufruf blockiert oder seine Seite ändert, schlägt der Workflow fehl und veröffentlicht kein neues leeres Fehlerbild. In diesem Fall den Lauf unter **Actions** öffnen und die Fehlermeldung prüfen.

## Wichtiger Hinweis zur Flugsicherheit

Diese Anzeige dient nur als Übersicht. Für Flugentscheidungen weiterhin aktuelle METAR/TAF und eine autorisierte Flugwetterberatung heranziehen. ClearToFly weist selbst darauf hin, dass die Prognoseübersicht keine offizielle Wetterberatung ersetzt: https://cleartofly.de/learn/outlook

## Wartungshinweis

GitHub kann zeitgesteuerte Workflows in öffentlichen Repositories nach längerer Inaktivität automatisch deaktivieren. Falls das Bild nicht mehr aktualisiert wird, in **Actions** nachsehen, ob der Workflow deaktiviert wurde, und ihn erneut aktivieren. GitHub weist außerdem darauf hin, dass geplante Läufe verzögert werden können: https://docs.github.com/de/actions/reference/workflows-and-actions/events-that-trigger-workflows
