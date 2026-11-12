# KOTZE-4-2 — PLE Engineering Project OS
## Evidence-governed engineering, project risk and procurement intelligence

**Status:** Architektur- und Integrationskonzept; keine implementierte PLE-End-to-End-Ausführung und kein belegter Wettbewerbsvorsprung.  
**Stand:** 12. November 2026  
**Ziel-Repository:** KOTZE Harness; isolierter Konzeptbranch, ohne Änderung der Produkt-Baseline.  
**Leitlinie:** Understand the site. Preserve the constraints. Build the minimum viable design. Verify independently. Improve only against evidence.

> Dieses Dokument ist eine öffentliche, eigenständige Produktspezifikation. Es enthält weder proprietäre Implementierungen noch interne Forschungsheuristiken, Provider-/Modellrouten, private Geschäftsdaten, Zugänge, Prompts oder Quelltext aus privaten Donor-Repositories. Benannte Open-Source-Projekte sind Integrationskandidaten, keine behaupteten Abhängigkeiten oder bestandenen Integrationen.

---

## 1. Mission, Wettbewerb und Produktgrenze

KOTZE-4-2 ist eine spezialisierte Ausprägung des bestehenden C11-/SQLite-Kontrollkerns für komplexe Ingenieuraufgaben im Physical Engineering's Last Exam (PLE). Das Ziel ist nicht, möglichst viele Agenten und Tools einzusetzen, sondern unter festem Modell-, Zeit- und Ressourcenbudget die höchste **nachweislich korrekte, vollständig lieferbare** Ingenieurleistung zu erzeugen.

Die Aufgaben können aus Projektdateien, textlichen Anforderungen, technischen Zeichnungen, GIS-/Shapefile-Daten, CAD-/BIM-Modellen, Tabellen, Materialien, Termin- und Kostenvorgaben bestehen. Fachlich relevant sind insbesondere Civil, Structural, Electrical und Mechanical Engineering. Projektsteuerung, Risiko- und Kostenbetrachtung sind Teil der Ingenieurentscheidung und nicht bloße Präsentationsschichten.

### 1.1 Bewertungsorientierte Leitentscheidungen

- **Hard constraints vor ungesicherter Optimierung:** Ein Verstoß kann den Optimierungsanteil der entsprechenden Bewertungsposition ausschalten; prüfbare Machbarkeit zuerst.
- **Vollständigkeit zählt:** Auch die technisch beste Teilrechnung ersetzt keine geforderte Ausgabedatei, Zeichnung, Tabelle oder Dokumentation.
- **Teilabgabe vor Nullergebnis:** Der Harness muss rechtzeitig einen vorhandenen, bestmöglich geprüften Entwurf liefern können, selbst wenn nicht alle Bedingungen geklärt sind. Ein unbekanntes Gate darf niemals als PASS ausgegeben werden.
- **Nicht alle Aufgaben sind numerisch bewertete Hard-Gate-Aufgaben:** Technische Begründung, professionelle Dokumentenqualität und Rubrik-Anforderungen müssen gesondert unterstützt werden.
- **Eine Einreichung, ein deklariertes Modell:** Das Modell aus submission.yaml ist bindend. Keine produktive Mehrmodell-Routing-Strategie innerhalb dieser Einreichung.
- **Keine Wettbewerbsdaten-Kontamination:** Weder aufgabenspezifische Antworten noch Grader-/Referenzdateien im Harness lesen, einbetten, zur Laufzeit verwenden oder durch gezieltes Task-ID-Matching umgehen. Öffentliche Dev-Grader dürfen ausschließlich außerhalb des Agenten zur unabhängigen Entwicklungsbewertung eingesetzt werden.
- **Keine externen Marktplätze, Routen-APIs oder Websuche während der Bewertung:** Nur erlaubter Modellendpunkt und die vorgesehenen Aufgaben-/MCP-Werkzeuge. Das kommerzielle Beschaffungsprodukt ist ein späterer, strikt separater Betriebsmodus.

Offizielle Referenzen:
- https://github.com/google-research/ple/blob/main/docs/rules.md
- https://github.com/google-research/ple/blob/main/kit/README.md
- https://github.com/google-research/ple/blob/main/docs/protocol.md
- https://github.com/google-research/ple/blob/main/docs/models.md

Diese Regeln vor der tatsächlichen Einreichung erneut gegen den aktuellen Stand prüfen.

## 2. Das integrierte Zielbild

KOTZE soll fünf zusammenwirkende, getrennt verantwortete Fähigkeiten bereitstellen:

| Fähigkeit | Zweck | Nachweismittel |
| --- | --- | --- |
| Engineering Second Brain | Geologie, Materialien, Ausführungspraxis, Normenbezüge, Mechanik, Elektrik und Baugrund kontextabhängig erschließen | Versionierte Quelle, Geltungsbereich, Voraussetzungen und Gegenbeispiele |
| Geo/CAD/BIM Intelligence | GIS, Shapefiles, Gelände, DXF, IFC, Zeichnungs-/Modellgeometrie, Mengen und Kollisionen verarbeiten | Provenienz, CRS, Geometrie- und Dateiintegrität |
| Constraint & Risk Graph | Anforderungen, Grenzwerte, Bauteile, Genehmigungs- und Projektrisiken samt Änderungsfolgen verbinden | Vollständigkeits-, Auswirkungs- und Risikoregister |
| Engineering Execution | Berechnungen, Solver, Artefaktgeneratoren, parametrische Verbesserungen und reversible Änderungen ausführen | Reproduzierbare Inputs, Werkzeugversionen, erzeugte Dateien, numerische Kontrollen |
| Independent Assurance | Berechnungsbeweise, Artefaktkonsistenz, fachliche Akzeptanz und beste abgabefähige Version unabhängig prüfen | Trusted receipts, PASS/FAIL/UNKNOWN/NOT_APPLICABLE, Snapshot-Hashes |

Der C11-Kern ist für **Zustand, Ausführungszulassung, Deadlines, Budget, Recovery und Abschlussentscheidung** verantwortlich. Fachberechnungen sollen durch geeignete, überprüfte Bibliotheken erfolgen. Fachliche Wissensbehauptungen, Modellurteile und unabhängige Prüfergebnisse bleiben getrennt.

### 2.1 Kerneinheiten

- **WorkIdentity:** eine Aufgabe mit verbindlicher Eingangsreferenz und Revision.
- **TaskAtlas:** Inventar der zugänglichen Dateien, Formate, Koordinatensysteme, Parserfehler, Abgabeziele und offenen Sichtungslücken.
- **NormativeConstraint:** konkrete Anforderung mit Quelle, Exaktheit, Einheit, Prüfung, Geltungsbedingung und Auswirkung.
- **EngineeringFact:** Beobachtung oder fachlicher Referenzeintrag mit Provenienz, Datum, Gültigkeitsgrenzen und Unsicherheit.
- **DesignCandidate:** Version eines Entwurfs mit Artefakten, Abhängigkeiten und Annahmen.
- **RiskItem:** Ursache, Ereignis, Auswirkung, Indikator, Abhilfe, Residualrisiko und Evidenzstatus.
- **ViolationTicket:** präzise Abweichung mit betroffenem Objekt, Ist-/Sollwert, Beleg und möglichem Reparaturpfad.
- **VerificationReceipt:** vom vertrauenswürdigen Prüfpfad erzeugter, an Kandidaten/Dateiversionen gebundener Nachweis.
- **BestDeliverable:** zuletzt materialisierter, auf Integrität geprüfter, abgabefähiger Kandidat.
- **ProcurementPackage:** optionaler, aus Mengen/Leistungsspezifikationen abgeleiteter fachlicher Beschaffungsvorschlag, ohne Live-Kontakt im PLE-Modus.

Diese Konzepte sind **Sollschnittstellen** und werden nicht als vorhandene C-ABI ausgegeben.

## 3. Task-Atlas: jeden vorhandenen Datenbestand erschließen

Vor dem ersten großen Modellkontext erfasst der Harness deterministisch und budgetiert, welche Quellen vorhanden und für welchen Aufgabenteil relevant sind. Die Inspektion darf nicht schon eine neue Projektbearbeitung oder einen Grader-Zugriff auslösen.

### 3.1 Datenformate und bevorzugte lokale Donoren

| Datentyp | Mögliche Donoren / Werkzeuge | Wichtigste Eigenschaften |
| --- | --- | --- |
| Shapefile / GeoPackage / GeoJSON | GDAL/OGR, Fiona, GeoPandas | Layer, Attribute, Geometrie, CRS, Projektionen, Validität |
| GeoTIFF / DEM / Gelände | Rasterio/GDAL, PyProj, Shapely | NoData, Einheiten, Rasterauflösung, Steigung, Überschneidungen |
| IFC4 / BIM | IfcOpenShell, IfcTester, IfcClash | Entitäten, Properties, Relationen, Mengenermittlung, Konflikte |
| DXF / 2D-Pläne | ezdxf, Headless-CAD-Adapter | Layer, Elemente, Einheiten, Dimensionen, Diffs |
| STEP / parametrische 3D-Modelle | FreeCAD (headless, falls nötig) | Form/Geometrie, Parameter, Export, ggf. FEM |
| PDF / DOCX | PyMuPDF und geeignete Dokumentenleser | Tabellen, Fundstellen, Versionierung, Einheiten |
| XLSX / CSV | openpyxl, Standard-CSV | Formeln vs. gespeicherte Werte, Pflichtfelder, Mengen, Kosten |
| Mathematische Modelle | NumPy, SciPy, SymPy, Pint | dimensionsrichtige, numerische, symbolische und Optimierungsrechnungen |
| Geotechnik | fachlich geprüfte Open-Source-Solver | Klassifikation, Tragfähigkeit, Setzungen und Stabilität, mit Annahmen |

Jeder Donor wird vor Übernahme auf Quellstand, Lizenz, Architektur, Paketgröße, RAM, Vertrauensgrenze und tatsächlichen Leistungsumfang geprüft. Die Verfügbarkeit eines MCP-Projekts ist kein Beleg seiner Integration oder technischen Richtigkeit. CAD-, GIS- und Geotechnik-Daten niemals ohne Quellen-, Geltungs- und Einheitennachweis zu Sicherheitsfreigaben hochstufen.

### 3.2 Adapterstrategie im PLE

1. Zuerst prüfen, welche **lokalen Aufgaben-MCP-Funktionen** die Evaluation bereitstellt, und den dafür vorgesehenen Protokollweg nutzen.
2. Externe Bibliotheken nur ergänzen, wenn eine nachgewiesene Fähigkeit fehlt.
3. Werkzeugausführung an den tatsächlichen Container binden: Harness-Container und Aufgabencontainer sind getrennte Vertrauens-/Dateiräume.
4. Transfer von Dateiinhalten nur über vorgesehene Protokolloperationen innerhalb der jeweiligen Größenbeschränkungen; niemals indirekt über verbotene Hosts.
5. Schwergewichtige GUI-/CAD-Stacks nur für explizit benötigte Aufgaben, nicht als pauschale Baseline.
6. Fehlende Werkzeuge bleiben als CAPABILITY_UNAVAILABLE sichtbar; keine frei erfundenen Ergebnisse.

Der TaskAtlas erfasst nicht nur erfolgreich gelesene Dateien, sondern auch **unlesbare, mehrdeutige und noch nicht geprüfte** Quellen.

## 4. Engineering Second Brain: praktische Fachlogik statt bloßem RAG

Das Second Brain enthält vier voneinander getrennte Klassen:

1. **Reference Knowledge:** öffentlich zulässig verwendbare Quellen, Fachliteratur, Datentabellen und versionierte Normreferenzen; keine ungenehmigten Volltextkopien.
2. **Contextual Rules:** Aussagen mit Trigger, Anwendungsvoraussetzungen, Gegenbeispielen, Ausnahmen und notwendiger Mess-/Prüfgrundlage.
3. **Computable Methods:** parametrisierte, testbare Berechnungsfunktionen mit Einheitendefinition, Materialmodell, Unsicherheit und Gültigkeitsbereich.
4. **Verified Engineering Episodes:** historisch überprüfte Vorgehensweisen, niemals automatisch als Beweis für eine neue Aufgabe verwendet.

**Beispiel Baugrund:** Die pauschale Regel „nicht auf Sand bauen“ ist fachlich ungeeignet. Die Beurteilung hängt von Lagerungsdichte, Kornverteilung, Grundwasser, Lasten, Setzungen, Erdbeben-/Liquefaktionsrisiken und Untersuchungsgüte ab. Eine geologische Karte ist keine objektspezifische Baugrunderkundung.

**Beispiel Kies:** Als Dränmaterial kann Durchlässigkeit wichtig sein, als Frostschutz-/Tragschicht zusätzlich Verdichtung, Kornabstufung und mechanische Kennwerte; gegenüber feinen Nachbarböden müssen Filterkriterien geprüft werden. Ein zutreffender Materialname ersetzt keine anwendungsabhängige Prüfung.

**Beispiel Elektro:** Leitungsdimensionierung ist nicht nur Nennstrom. Verlegeart, Umgebungstemperatur, Häufung, Schutzorgane, Spannungsfall und einschlägige Regeln können jeweils harte Voraussetzungen sein. Grenzwerte werden aus Aufgabe/zulässiger Quelle ermittelt, nicht global hartcodiert.

Eine Wissenseinheit benötigt mindestens: ID, fachliche Domäne, Quelle+Stand, sachliche Aussage, Einsatzbereich, Messdatenbedarf, Einheiten, nicht zulässige Anwendungen, Abhängigkeiten, Konfidenz-/Unsicherheitsklasse und zugehörige Prüfmethode. Unterbestimmte Entscheidungen werden als OPEN_EVIDENCE kenntlich.

Für PLE wird das Wissen **vorab offline** paketiert, lokal indiziert (z. B. SQLite FTS5) und von den Wettbewerbsaufgaben strikt isoliert. Keine Laufzeit-Webrecherche.

## 5. Constraint Graph + Risk Management als gemeinsamer Kern

Die zentrale Abstraktion ist nicht „eine Liste roter Warnungen“, sondern ein gerichteter, nachvollziehbarer **Abhängigkeits- und Nachweisgraph**:

Anforderung → Standort/Bedingung → Komponente/Material → Berechnung → Nachweis → Artefakt → Projektwirkung.

Ein Revisionswechsel an einer Materialkennzahl, einer Entwässerungsfläche oder einer Trassenführung markiert alle davon abhängigen Prüfungen als möglicherweise **STALE**. Bereits einmal grüne Ergebnisse werden nicht stillschweigend wiederverwendet.

### 5.1 Risikoobjekt und Entscheidungslogik

Jedes Risiko speichert:
- Risk-ID; Ursache und auslösendes Ereignis;
- betroffene Anforderungen, Assets, Termine und Kostenpositionen;
- Beobachtungs-/Datenqualität; Evidenz statt bloßer Modellbehauptung;
- Eintrittswahrscheinlichkeit **nur falls fundiert schätzbar**, sonst qualitative Unsicherheit;
- Konsequenz, Kritikalität, Gegenmaßnahme, Verantwortlichkeit;
- verbleibendes Risiko und offene Fach-/Freigabepunkte.

Methoden nach Bedarf: FMEA/FMECA, Fehlerbaum, Szenarien, kritischer Pfad, Sensitivitäten und – **nur mit vertretbaren Eingangsdaten** – Monte-Carlo-Simulation. Eine numerische Risikozahl ohne belastbare Verteilung ist keine objektive Aussage.

### 5.2 Project Controls

Projektplanung wird modelliert über Arbeitspakete, Abhängigkeiten, Voraussetzungen, Terminfenster, Ressourcen, Mengengerüste, Änderungsfolgen und Abnahmebedingungen. Ein Ingenieurentwurf gilt nicht schon deshalb als gut, weil er statisch funktioniert: Baubarkeit, Bauablauf, Zugänglichkeit, Lieferfähigkeit, Baugrundrisiken und Kosten können ihn disqualifizieren oder entwerten.

Ein fachliches Risk Gate kann **HOLD_FOR_EVIDENCE** ausgeben. Im Wettbewerb bedeutet das, unter der verfügbaren Zeit eine gekennzeichnete bestmögliche Teilabgabe vorzubereiten, nicht ohne Abgabe endlos zu blockieren.

## 6. Ausführungszyklus: bestes Ergebnis jederzeit bewahren

### 6.1 Zustandsfolge

- **ADMIT:** Aufgabenidentität, feste Ausführungsrechte, Budget, verfügbare Werkzeuge.
- **INVENTORY:** TaskAtlas mit Quellenabdeckung und Abgabeziel-Liste.
- **SPECIFY:** extrahierte Anforderungen; unabhängige Vollständigkeitskontrolle; normative Basis versionieren.
- **BASELINE_DESIGN:** früh einen **lieferbaren ersten Entwurf** erzeugen, bevor spätere Optimierungen anstehen.
- **CHECK:** Dateien, physikalische Gleichungen, Einheiten, geometrische Kollisionen, Anforderungen und projektbezogene Risiken kontrollieren.
- **REPAIR:** gezielt nur nachweislich relevante Abweichungen beheben; keine planlosen Wiederholungen.
- **OPTIMIZE:** nur gegen gültigen Checkpoint und mit Budget; jede Änderung invalidiert betroffene Prüfungen.
- **SEAL & DELIVER:** rechtzeitig die beste prüfbare Artefaktversion innerhalb der tatsächlichen Abgabeziele ausliefern.

Diese Folge ist **ein vorgeschlagenes PLE-Orchestrierungsprofil**, keine Behauptung, dass der aktuelle KOTZE-C-Kern diese gesamte State Machine implementiert.

### 6.2 Anytime- und Fallback-Verhalten

- Der beste verfügbare Kandidat wird versioniert, mit Quellen- und Artefakt-Hashes gesichert.
- Der Harness unterscheidet FEASIBLE_VERIFIED, PARTIAL_VERIFIED, INCONCLUSIVE und INVALID; „kein Nachweis“ ist kein PASS.
- Eine Optimierung darf eine zuvor verifizierte Version nicht unbemerkt zerstören.
- Bei Ablauf des Budgets erfolgt kein endloser Retry, sondern die Auslieferung des zuletzt erlaubten, konsistenten Kandidaten.
- Fehlen Pflichtartefakte, wird der Sachstand kenntlich; frühzeitig priorisierte Mindestdeliverables reduzieren Nullrisiko.
- Eine Wiederaufnahme darf keine externen oder irreversiblen Operationen doppelt ausführen.

### 6.3 Was „kotze.wal“ bedeutet

Der Name **kotze.wal** wird als konzeptionelle Bezeichnung für den Checkpoint-/Recovery-Pfad geführt; er rechtfertigt **kein neues selbstgebautes binäres WAL**. Der bereits vorhandene SQLite-Kern bietet Transaktionen. SQLite-WAL, Journaling, Snapshot-Referenzen und temporäre Dateispeicherung müssen als ein konsistentes System gestaltet werden. Insbesondere darf eine abgebrochene Ausführung im isolierten Bewertungscontainer nicht als nachweislich persistent über neu gestartete Container hinweg bezeichnet werden, bevor das tatsächlich belegt ist.

## 7. Zero Trust, Assurance und Mathematik

**Normative Wahrheit (N)**, **Beobachtung (O)**, **Agentenurteil (J)** und **unabhängig verifizierter Nachweis (V)** dürfen nicht vermischt werden.

Ein vom Agenten erzeugtes Constraint-Manifest ist zunächst eine **Behauptung über die Aufgabe**, nicht automatisch vollständig oder korrekt. Ein Dateimodus wie chmod 0444 allein schützt weder gegen falsche Extraktion noch gegen einen Host mit Schreibrechten. Eine unabhängige Prüfung benötigt eine vom Worker getrennte, tatsächlich durchgesetzte Vertrauensgrenze sowie unveränderte Originalquellen.

Verifikationsfamilien:
- **Syntaktisch:** Dateiformat, notwendige Struktur, Schemas, Pflichtblätter/-felder.
- **Numerisch:** Einheiten, Gleichungen, Residuen, Grenzwerte, Rundung/Toleranzen.
- **Geometrisch:** Topologie, Positionen, Flächen/Volumen, Kollisionen, Höhen, Koordinatensysteme.
- **Fachlich:** Geltungsbedingungen, Materialwahl, technische Nebenbedingungen.
- **Projektbezogen:** Kosten-/Mengen-Konsistenz, Terminabhängigkeiten, riskante Annahmen, offene Abnahmen.
- **Lieferbezogen:** nur erlaubte Abgabeziele, korrekte aktuelle Dateirevisionen.

Der statistische Forschungs-/Ablationsdonor ist **ein Entwicklungsinstrument**, kein Ersatz für eine deterministische Sicherheitsprüfung. Er untersucht gepaarte Unterschiede (gleiche Aufgaben/Modelle/Budgets) zwischen Baseline und Zusatzelementen, trägt negative/inconclusive Resultate fort und verhindert das Hochstufen post-hoc ausgewählter Treffer zu gesicherten Erkenntnissen. Statistische Signifikanz beweist keine individuelle Bauwerksicherheit.

## 8. Project Procurement: Wettbewerb versus kommerzielles Produkt

### 8.1 Im PLE-Harness: offline, beratend, ohne Vertragsschluss

Der Harness darf aus dem Entwurf strukturiert ableiten:
- Leistungsverzeichnis/Materialbedarf (BOM/BOQ) samt Einheiten, toleranzrelevanten Eigenschaften und Mengenherkunft;
- technische Eignungsmerkmale für Alternativen und zulässige Materialsubstitutionen;
- deklarierte Preis-/Lieferannahmen, Kostenmodell, Sensitivität und Terminwirkungen;
- beschaffungsrelevante Risiken und erforderliche Nachweise;
- vergleichbare Angebote **nur falls bereits als legitime Aufgabenunterlagen vorhanden**.

**Nicht im Wettbewerbscontainer:** echte Anfragen an Anbieter, Shopping-Websuche, automatische B2B-Verhandlung, Affiliate-Tracking, Zahlung, verbindliche Bestellung oder Kontakt zu privaten Plattformen. Monetarisierung ist kein PLE-Punktefaktor und darf keine technische Empfehlung verzerren.

### 8.2 Späterer optionaler Produktmodus

Der kommerzielle Beschaffungsworkflow ist ein anderes Sicherheits- und Autorisierungsprofil:

Bedarf → fachlich freigegebene Spezifikation → RFQ mit eindeutiger Request-ID → passende Dienstleister/Anbieter → kanal- und einwilligungsbezogene Kontaktfreigabe → strukturierte Angebote und Revisionen → technisch-wirtschaftlicher Vergleich → mandatierte Verhandlung → menschlich/vertraglich autorisierte Bestellung → dokumentierte Erfüllung → tatsächliche Wirtschaftlichkeitsmessung.

**Dienstleistung und Waren sind getrennte Beschaffungsdomänen.** Der bestehende private Vermittlungsdonor ist nach seinem dokumentierten Ist-Stand **auf Dienstleistungen beschränkt**. Seine Konzepte für RFQ, Anbieterrechte, Angebotsrevision, Freigaben, Kontakt-Policy und Kosten-/Erlösnachweise lassen sich fachlich als Vorbild verwenden; ein Waren- und Baustoffkatalog sowie Liefer-/Fracht-/Mengenlogik wären **neu** zu entwickeln und zu prüfen.

Unverzichtbar:
- Lieferantenidentität ≠ Berechtigung zur Kontaktaufnahme ≠ Vertragsstatus;
- Anbieterantwort ≠ technischer Eignungsnachweis ≠ ausführbare Beschaffung;
- verhandelter Preis ≠ realer zahlbarer Gesamtpreis;
- potenzielle Provision ≠ erhaltene Zahlung;
- bezahlte Vermittlung/Partnerschaft ≠ Rankingvorteil bei fachlicher Empfehlung;
- keine automatischen Mails, Bestellungen oder finanziellen Effekte ohne passende Freigabe.

Das private kommerzielle Donorsystem bleibt unverändert, unveröffentlicht und **ist keine PLE-Laufzeitabhängigkeit**.

## 9. Reuse-first und Donor-Grenzen

| Donor-Klasse | Wiederzuverwendende Fähigkeit | Zielintegrationsart | Abnahmehinweis |
| --- | --- | --- | --- |
| KOTZE C11/SQLite | Zustandsübergänge, Anti-Loop, Recovery- und Budgetabsichten | vorhandenen Kern erweitern, nicht neu schreiben | Phase-1-Kern ist noch keine privilegierte OS-Grenze |
| Persistentes Arbeitsgedächtnis | WorkIdentity, Spezifikation, Evidenz, Kontext-Recovery | schlanke, lokale Prinzipien/Adapter | keine neue obligatorische Datenbankdienst-Instanz |
| Kontextkompilierung | Priorisierte Normbedingungen, Quellenspan, exakte Zahlen | deterministischer Kontextpackager | kritische Anforderungen dürfen nicht gekürzt werden |
| Trace-/Repair-first | minimal betroffener Pfad, Reuse vor Änderung, kontrollierte Patches | enges Verfahren | geringstmöglicher Eingriff |
| Hypothesen- und Gegenbeweisverfahren | alternative Ursachen und Falsifikation | neu formulierte, unabhängige PLE-spezifische Regeln | kein Import privater Forschungslogik |
| Statistische Methoden | gepaarte Ablation, robuste Schätzung, Holdout-Disziplin | separate Entwicklungsanalyse | nicht innerhalb jeder Aufgabe nötig |
| Projekt-/Vergabeanalyse | Anforderungsnachweise, Mengenermittlung, Kosten, Projektakte | abstrahierte Prozess- und Datenverträge | keine private Projektquelle kopieren |
| Privater RFQ-/Service-Prototyp | Angebotsversionen, Rechte, Review, Kontaktpolitik, Unit Economics | **nur Konzeptdonor** für späteren Produktmodus | kein privater Code, keine Live-Kommunikation |
| CAD/BIM | IFC-Inspektion, Mengen, Kollisions-/Property-Prüfung | IfcOpenShell/IfcTester/IfcClash-Kandidaten | Software-/Lizenz-/Paketprüfung ausstehend |
| GIS | Shapefile, Raster, CRS, räumliche Validierung | GDAL/GeoPandas/Shapely/PyProj-Kandidaten | CRS und Einheiten müssen im Receipt stehen |
| DXF/3D | geometrische Bearbeitung | ezdxf, ggf. FreeCAD headless | nicht als permanente schwere Standardabhängigkeit |
| Engineering Math | Einheiten und Solver | Pint/NumPy/SciPy/SymPy | methodenspezifische Validierung erforderlich |

Das bedeutet keine Übernahme einer vollständigen proprietären Organisation in ein öffentliches Repository. Private Donoren dürfen ausschließlich als **intern gesondert genehmigte Quellen für unabhängig geschriebene, generische Mechanismen** dienen. Dokumentation dieses Repositories nennt bewusst keine privaten Repository-Namen, lokalen Pfade, internen Klassen, Vertragsregeln, Nutzer-/Anbieterdaten oder Monetarisierungsdetails.

Vor externer Codeübernahme: Lizenz, Dateiherkunft, Redistributionspflichten, transitive Lizenzpflichten, Supply-Chain-Risiken und Reproduzierbarkeit prüfen. Insbesondere GPL-/AGPL-Komponenten nicht stillschweigend in den öffentlichen Kern kopieren. Bloße Tool-/MCP-Integration und Source-Vendoring sind unterschiedliche Vorgänge.

## 10. PLE-Ressourcenprofil und Packaging

Die offizielle Kit-Dokumentation sieht getrennte Build-, Serve- und Aufgabencontainer vor. Der Serve-Container läuft mit begrenzter CPU/RAM-Ausstattung und schreibgeschütztem Root-Dateisystem; zur Laufzeit kann er nicht beliebig ins Internet kommunizieren. Das gepackte Bundle, die entpackten Dateien und Datenübertragungen unterliegen Limits.

Daraus folgt:
- nur unterstützte Linux-/amd64-Artefakte paketieren;
- GIS-, CAD- und Solverabhängigkeiten im Build pinnen und gegen das zulässige Bundle-Limit bilanzieren;
- für jede Werkzeuggruppe einen **minimalen capability probe** ohne kostenpflichtige Ausführung definieren;
- ein textuelles Verfahren als Fallback anbieten, wenn ein schwerer Solver nicht verfügbar ist, ohne Erfolg vorzutäuschen;
- große Dateien möglichst dort verarbeiten, wo sie liegen, statt unnötig zwischen Containern zu kopieren;
- alle Checkpoints auf zulässige, tatsächlich persistente Speicherorte und entsprechende Datenintegritätsprüfung beschränken;
- bei Budgetknappheit zuerst vorhandene Lieferartefakte sichern.

Für die erste Konzeptabnahme werden **keine** CI-, Modell- oder Benchmarkläufe automatisch gestartet.

## 11. Eng begrenzter Implementierungsplan

### P0 — Regelkonformer Host + Lieferfähigkeit
1. Offizielles PLE-Protokoll samt WebSocket-Adapter implementieren; ein deklariertes Modell verwenden.
2. Existierende KOTZE-Zustands- und Budgetentscheidungen anbinden.
3. Aufgaben-MCPs und verfügbaren lokalen Werkzeugkatalog erkennen.
4. Artefakt-Snapshot, BestDeliverable und zeitbegrenztes Finale vorsehen.
5. Ohne Grader-/Referenzzugriff und ohne ausgelöste Hosted-CI ausführbar halten.

**Gate:** Eine synthetische erlaubte Aufgabe kann ohne externe Dienste angenommen, bearbeitet und mit konsistenten Deliverables abgeschlossen werden. Kein Anspruch auf PLE-Wettbewerbsscore.

### P1 — Constraint Completeness und Tabellen-/Textpipeline
1. TaskAtlas für Text/PDF/DOCX/XLSX/CSV.
2. Quellengenaue Requirement-/Risk-/Deliverable-Matrix.
3. Einheiten und Rechenkontrollen; PASS/FAIL/UNKNOWN.
4. Revisions- und Staleness-Propagation.
5. Früher erster lieferbarer Kandidat.

**Gate:** Quellenabdeckung, Unklarheiten und alle Pflichtdeliverables sind maschinenlesbar nachvollziehbar; keine stillschweigend ausgelassenen harten Anforderungen.

### P2 — GIS/BIM/DXF/Engineering Brain
1. Shapefile/CRS/Raster/Gelände und räumliche Prädikate.
2. IFC- und DXF-Analyse; Mengen-/Geometrieprüfungen.
3. Praktische geotechnische Regelkarten, Geltung und Gegenbeispiele.
4. Fachliche Solver nur wo relevant.
5. Abhängigkeiten zwischen Standort, Material, Entwurf und Nachweis.

**Gate:** fachlich plausibilisierte, reproduzierbare Beispielrechnungen mit unabhängigen Gegenprüfungen; keine pauschale Freigabe für unbekannte Boden-/Normdaten.

### P3 — Risiko, Kosten und Optimierung
1. Projekt-Risikoregister und Abhängigkeiten.
2. BOQ/BOM, Material-/Kosten-/Terminfolgen.
3. Parametrische Optimierung nur gegen gesicherten Kandidaten.
4. Unsicherheitsanalyse und dokumentierte Abwägung.
5. kontrollierter Fallback bei Zeitüberschreitung.

**Gate:** Änderung eines kritischen Parameters invalidiert korrekte Nachweisketten; Optimierung kann den zuvor lieferbaren Kandidaten nicht verlieren.

### P4 — Wissenschaftliche Ablation / Einreichung
1. Vorab festgelegte Baseline und identische Modell-/Budgetprofile.
2. Abgrenzbare Komponentenvergleiche: Atlas, Constraints, GIS/BIM, Risk, Optimization.
3. Score, hard-gate completion, Dateivollständigkeit, Kosten, Latenz, Ausfallquote und Varianz berichten.
4. Negative, unvollständige und nicht signifikante Ergebnisse mitführen.
5. Offizielle Dev-Artefakte ausschließlich über den vorgeschriebenen Eval-Export; kein manueller Eingriff in Artefaktordner und keine Testkontamination.

**Gate:** Kein Gewinnversprechen und keine Verallgemeinerung auf verdeckte Aufgaben ohne tatsächliche unabhängige Ergebnisse.

## 12. Abnahmekriterien und bewusst ausgeschlossene Tätigkeiten

Eine KOTZE-4-2-Änderung gilt erst als integrabel, wenn sie:
- fachlich einem PLE-Aufgabentyp zugeordnet ist;
- einen klaren Nachweis- und Fehlerpfad besitzt;
- im zulässigen Offline-/Containerprofil funktioniert;
- keine geheimen Informationen oder fremde Source ohne Lizenzfreigabe enthält;
- messbar zur Lösungsvollständigkeit, Korrektheit, Kosten- oder Zeiteffizienz beiträgt;
- von einem unabhängigen Vergleich nicht als nutzlos oder schädlich widerlegt wird;
- keinen unzulässigen Netzwerk-/Beschaffungs-/Zahlungsvorgang ausführt.

**Nicht Bestandteil dieses Konzeptcommits:** ausführbarer PLE-Adapter, Paketinstallation, Download großer Norm-/CAD-Korpora, Datenbankmigration, Änderung des bestehenden KOTZE-C-Kerns, Übernahme privaten Sourcecodes, Änderungen an kommerziellen Donor-Repositories, externe Nachrichten, bezahlte Modellläufe, GitHub Actions oder Kaggle-Submission.

## 12a. Statistisches Second Brain und Repair-Paar

Neben dem fachlichen Engineering Second Brain benötigt KOTZE eine **evidenzgestützte statistische Erfahrungs- und Fehlergedächtnisschicht**. Sie speichert nachvollziehbare Fehlversuche und unabhängig verifizierte Reparaturergebnisse, ohne selbst technische Wahrheit oder Berechtigungen festzulegen. Ein **funktional getrenntes Repair-Paar** umfasst Ursachenanalyse/gezielte Nachbesserung und eine vertrauenswürdig getrennte Prüfung. Es erkennt auch kognitive Prozessfehler: vergessene Nutzervorgaben, falsche Toolwahl, Scheinerfolg, Wiederholungsschleifen und unautorisierte Aktionen. Keine zweite Modellinstanz gilt allein als unabhängiger Zero-Trust-Verifier.

Die vollständigen Schnittstellen, Zustände, statistischen Grenzen und Abnahmekriterien sind in [Statistical Second Brain and Evidence-Governed Repair Pair](STATISTICAL-SECOND-BRAIN-AND-REPAIR-PAIR.md) spezifiziert. Das ist eine **Sollarchitektur**, kein implementierter Benchmark-Vorteil.

## 13. Konkrete Architekturentscheidung

KOTZE-4-2 soll **ein offline-fähiges, evidenzgesteuertes Engineering Project OS** werden, das praktische Materialkunde, GIS, Baugrund, CAD/BIM, Ingenieurmathematik, Risiko, Kosten und Termine in **einer** nachvollziehbaren Entscheidungs- und Prüfkette verbindet.

Der Wettbewerbsmodus maximiert verifizierte Deliverables und vermeidet externe Nebenwirkungen. Ein späterer, separater Produktmodus kann nach gesonderter Freigabe Angebotsanfragen und B2B-Beschaffung bereitstellen. Die bestehenden privaten Forschungs- und Vermittlungssysteme werden nicht veröffentlicht, nicht als zwingende Laufzeitdienste verlangt und nicht in dieser Branch verändert.

**Kernprinzip:** Fachliche Plausibilität ist nicht mathematischer Beweis. Eine Rechnung ist nicht die gesamte Projektentscheidung. Eine vorgeschlagene Verbesserung ist kein Fortschritt, bis unabhängige Evidenz ihren Nutzen belegt.
