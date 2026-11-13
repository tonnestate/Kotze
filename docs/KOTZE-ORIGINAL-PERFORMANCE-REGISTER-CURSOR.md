# KOTZE Original — Performance, C11 Registry/Cursor and Concurrent Execution

**Stand:** 13. November 2026  
**Status:** erster nativer C11-Register-/Cursor-Slice als Quellcode vorhanden; noch kein Scheduler, keine Kompilierung, keine Tests und keine gemessene Performanceverbesserung.  
**Scope:** Original-KOTZE für autonome Softwareentwicklung. Kein Import der StrawberryMe/OGI/AVCOS-Laufzeit, kein zweiter Organisations-/Capability-Katalog.  
**Budget-Regel:** Keine Cloud-/Modellaufrufe, CI/Actions oder Benchmarkläufe durch diese Dokumentationsänderung.

## A. Verbindliche Leistungsgrundsätze

1. **Performance ist ein Design- und Abnahmekriterium ab der ersten Implementierung.** C11 bleibt bevorzugt für deterministische, häufig ausgeführte Kernoperationen. Die Aussage, dass C in den meisten Fällen nur wenig Mehraufwand verursacht, ist eine Projektpräferenz, keine ohne Messung verifizierte allgemeingültige Quote.
2. **Kein Modellaufruf für deterministische Arbeit.** Status, Budget, Cursor-Navigation, Filter, Hash-/Versionsprüfung und Zustandsübergänge sind native Host-Aufgaben.
3. **Niemals vollständigen Projekt-/Kontextzustand bei jedem Schritt neu aufbauen.** Inkrementelle, positionsbezogene Sichten, Versionsschlüssel und sparsame Abhängigkeits-Expansion.
4. **I/O möglichst asynchron; unabhängige CPU-/I/O-Arbeit begrenzt parallel.** Parallelität ist eine Optimierung unter Abhängigkeiten und Kosten, keine Freigabe für unkontrollierte Konkurrenz.
5. **Exklusive Schreiber auf derselben Work-/Datei-/Effect-Identität.** Audit-Events, Zustandswechsel, externe Effektbestätigungen und Verifikationsfreigaben benötigen deterministische Transaktions-/Fencing-Reihenfolge.
6. **Backpressure statt Queue-Explosion.** Jede Work-Einheit besitzt ein Speicher-, Token-, CPU-, I/O-, Zeit- und externes Effektbudget. Keine unbegrenzten Workers/Agenten, kein impliziter Modell-Fallback.
7. **Reproduzierbare Resultate:** Ergebnisse paralleler Reads/Probes werden nach stabilen Identitäten und Evidenzversionen reduziert; bei Konflikt blockieren und neu prüfen, nicht last-write-wins.
8. **Kein künstliches „immer schneller“.** Synchronisation, SQLite-Schreibsperren, Caching/Memory-Pressure und kleine Tasks können Parallelität teurer machen. Entscheidung nach gemessenem p50/p95, Durchsatz, Peak-RAM und Kosten pro unabhängig verifiziertem Ergebnis.

## B. Übernommenes Denkmuster: StrawberryMe MAP_CURSOR, nicht kopierte Runtime

Aus den früheren StrawberryMe-/OGI-Gesprächen ist die **Current / Future / Observed MAP** mit einem persistenten **MAP_CURSOR** bekannt. Der Cursor fokussiert eine konkrete Architektur- bzw. I/O-Boundary und liefert nur:

- aktuelle Position bzw. Objektidentität und Revision;
- begrenzte Upstream-/Downstream-Nachbarschaft und Input-/Output-Frontier;
- relevante Regeln/Invarianten und Aktions-/Änderungskontext;
- Current-/Future-Abweichung sowie beobachtete Evidenz;
- einen begrenzten Dependency-Horizon **H0–H4**, der nur bei begründetem Bedarf erweitert wird.

**Übertragung auf KOTZE Original:** ein eigener leichtgewichtiger `work/register`-Index für Task-, Repository-, Symbol-, Datei-, Hypothesen-, Tool-/Effect- und Evidence-Referenzen. Die *Wissens-/Organisationswahrheit* verbleibt beim zuständigen OGI/FruitStack-Baustein, wenn er verbunden ist. KOTZE speichert lokale, versionierte Ausführungssichten und sichere Referenzen, aber keine duplizierte zentrale Organisation.

Das „Register“ bezeichnet hier eine **persistente, indizierte Sammlung von Zustands- und Architekturreferenzen**, nicht CPU-Prozessorregister. Ein Cursor ist ein expliziter positionsgebundener Snapshot/Handle, keine rohe Prozessadresse.

### Ziel-Datenmodell (teilweise umgesetzt)

- **Durable source of truth:** bestehende SQLite-Works/Contracts/Events/Actions/Effects; Änderungen weiterhin ausschließlich über den autorisierten C11-Kern. Für neue Registerdaten ggf. zusätzliche indizierte Tabellen oder vorbereitete Views im selben Datenbestand, kein zweites Journal.
- **Registereintrag:** `work_id`, `kind`, `object_key`, `version_digest`, `evidence_epoch`, `parent_ref`, `dependency_keys`, `observed_at`, `confidence_class`, `source_ref`; keine pauschal kopierten Code-Inhalte oder geheimen Testdaten.
- **Cursor:** `work_id`, `object_key`, `expected_revision`, `evidence_epoch`, `map_view=current|future|observed`, `horizon`, `page_token`; jede Auflösung prüft aktuelle Version und Rechte, stale Cursor führt zu Konflikt statt falschen Daten.
- **In-memory Hot Path:** kompakte typisierte C11-Slots und getrennte Indizes, mit stabilen Slot-IDs plus **Generation Counter** zum Erkennen wiederverwendeter Plätze; keine ungesicherten Pointers über Reallokation, Prozessgrenzen oder Neustarts.
- **Lookup:** `cursor_open(work,object,revision)`, `cursor_read(cursor,limit)`, `cursor_edges(cursor,direction,horizon)`, `cursor_advance(cursor,position)`, `cursor_close(cursor)` als mögliche *API-Verträge*, **nicht als existierende Funktionen**.
- **Ausgaben:** begrenzte Nachbarschaft, nicht vollständige Repository-Dumps; erst bei neuem Fehlersignal, referenzierter Abhängigkeit oder Prüfwiderspruch gezielt expandieren.
- **Invalidierung:** Work-Revision, Candidate-SHA, Repo-Baseline, Policy-Version und Evidence-Epoch steuern Cache-Gültigkeit. Alte Cursors werden nicht stillschweigend auf neue Wahrheit umgebogen.
- **SQLite-Sicherheit:** vorbereitete indizierte Queries, Transaktionssnapshots und feste Seitengrößen; WAL ermöglicht überlappende Leser und einen serialisierten Schreiber, **nicht** viele unabhängige parallele SQLite-Schreiber.
- **Speicherbegrenzung:** LRU/TTL nur für **rekonstruierbare Cache-Views**, niemals für verbindliche Aufträge, Belege oder Effect-History; numerische Limits später benchmarkbasiert festlegen.

### Die drei konkreten Cursor-Anwendungsfälle

1. **Code-/Fehlersuche:** Cursor auf defektem Symbol/Stacktrace → lokale Caller/Callee- und Abhängigkeiten → nach Evidenz expandieren → nur relevanten Ausschnitt in den Modellkontext.
2. **Repair und Harness²:** Cursor auf Work + Harness-Profil-Version → diff zu vorgeschlagener Konfiguration → nur betroffene Tools/Skills/Policy-Änderungen prüfen; Security-Invarianten bleiben unveränderlich.
3. **Recovery:** Cursor auf eine `UNKNOWN`-Effect-Position → zugehörige Work-ID, Fencing-Token, Remote-Effect-Key und historisierte Receipts lesen → nur den betroffenen Recovery-Zweig behandeln, niemals alle Aufträge blind wiederholen.

## C. Asynchrones und paralleles Ausführungsmodell

`Host Event Loop → bounded Queue → fixed worker pool → verified reducer`

- **Asynchron überlappbar:** Netzwerk-Reads zu unabhängigen Modellen/Providern (nur nach Freigabe), Repository-Metadaten-Reads, Status-Polls, nichtmutierende Retrieval-/Graph-Nachbarschaftsanfragen, vorbereitende Diagnoseprobes in isolierten Snapshots.
- **Parallelisierbar mit Aufwandsschutz:** unabhängige Dateien/symbole, unterschiedliche Work-IDs, voneinander isolierte Tests (keine gemeinsam schreibbaren Verzeichnisse), verschiedene Harness²-Kandidaten *nur nach explizit genehmigtem Probe-Budget*.
- **Nicht unkoordiniert parallel:** dieselbe Datei patchen, derselbe Work-State-Transition, eine Live-Git-Branch-Mutation, ein externer Effect mit unsicherem Ausgang, Oracle-/Pass-Freigabe oder die Promotion desselben Harness-Profils.
- **Deterministische Reduktion:** alle Ergebnisse tragen `work_id`, `revision`, `candidate_sha`, `policy_digest`, `evidence_epoch` und ggf. `fencing_token`; nur passende Generationen können committed werden. Späte Ergebnisse werden als stale erfasst und verworfen.
- **Safety First:** der trusted Host erzwingt Prozess-/Dateisystemgrenzen und Schreibrechte. Ein C-Threadpool allein ist keine Sandbox.
- **Startpunkt:** kein allgemeines verteiltes Scheduling-System; ein bounded lokaler I/O-Executor mit 1 verlässlichem Writer, parallelen Reads und klaren Cancel-/Deadline-Mechanismen reicht als erster Scope.

## D. C11-Scope und Implementierungssequenz

**P0 nach dem vertrauenswürdigen Host/Verifier:**
1. Leichtgewichtige, versionierte Registry/Cursor-Verträge **in C11** mit SQLite-Indizes und minimalem Cursor-Snapshot. Reuse der bestehenden Event-/Effect-Tabellen.
2. Read-only `cursor_open/read/edges` für eine *konkrete* Work-Position mit begrenzten Nachbarn; verpflichtende Revisions-/Epoch-Prüfungen.
3. Bounded Queue mit Cancellation, Deadlines und persistenten Work-Intent-IDs. Zunächst unabhängige Retrieval-/Read-Operationen; keine autonome Remote-Probe.
4. Effekt- und Work-Mutationen über die vorhandenen Host-/FSM-/Fencing-Gates serialisieren; parallele Worker geben nur Vorschläge/Beobachtungen ab.
5. Gezielt kontrastierende lokale Performance-Prüfungen **nach Freigabe**, um Aufwand und Nutzen des C-Slices gegen eine einfache Baseline zu messen.

**P1:** indexierte Dependency-Closure, Current/Future/Observed-Differenzen, adaptive Horizon H0–H4, Hot-Cache/Invalidierung. Erst messbare Engpässe rechtfertigen aufwendige Arenen/SoA-Layouts, mmap, Threadpool-Tuning oder zusätzliche Datenbanktechnologien.

**P2:** Harness²-Propose–Probe–Compose nutzt denselben Registry-/Cursor-Mechanismus für lokale Kandidaten und die Versions-/Kostenbeobachtung. Experimentläufe bleiben opt-in; deren parallele Ausführung ist kein Standardmodus.

**Nicht Bestandteil des Kerns:** frei laufende Multi-Agent-Gruppen, eigene LLM-Inferenz, generische Eventbus-/Kafka-Kopie oder ein zweites OGI-Register.

## E. Mess- und Abnahmekriterien

Vorher/nachher für identische Daten und Budgets, getrennt nach Kaltstart/Warmstart:

| Frage | Messgröße / Invariante |
| --- | --- |
| Findet der Cursor die richtige Position? | Trefferrate und stabile Revision/Source-ID statt bloßer Ähnlichkeit |
| Spart der Cursor Modellkontext? | Gelieferte Bytes/Tokens, Zahl nachgeladener Objekte, korrekte Abhängigkeitsabdeckung |
| Ist C11 schneller als einfache Alternative? | CPU-Zeit, p50/p95 Latenz, Peak-RSS, Cache-Miss-Rate (wo beobachtbar) |
| Hilft Async/Parallelität wirklich? | Gesamtlaufzeit, Durchsatz, Scheduling-Overhead, Queue-Tiefe, tail latency, Fairness |
| Bleibt KOTZE korrekt? | Keine stale Receipts, keine doppelte externe Mutation, keine unautorisierte Änderung |
| Ist es wirtschaftlich? | Gesamtkosten **inkl. Fehlversuche** pro unabhängig verifiziertem Ergebnis |

**Performance ohne unabhängige Korrektheit ist kein Gewinn.** Eine sofortige Sicherheitsverletzung oder falsche PASS-Freigabe bleibt unabhängig von Geschwindigkeitsgewinnen ein Blocker.

## F. Verbindliche Nicht-Behauptungen

Dieses Dokument trennt den **jetzt als C11-Quellcode hinzugefügten Register-/Cursor-Slice** von weiterem Architekturziel. Der Register-Slice ist noch nicht kompiliert oder durch Ausführung nachgewiesen; MAP-Horizons H0–H4, Hot Cache und eine native asynchrone Pipeline sind weiterhin nicht implementiert. Frühere StrawberryMe-Design-/Testangaben beweisen keine bereits existierende KOTZE-Integration. Es wurden keine Performancewerte gemessen, kein Build und keine externen Tests ausgeführt.

## G. C11-Implementierungsstand: erstes Register und Positionscursor

Die neue Library `include/kotze_register.h` und `src/kotze_register.c` verwendet die **bereits vorhandene** KOTZE-SQLite-Datenbank. `kr_open` fordert die vorhandene `works`-Tabelle an und legt lediglich additive Tabellen an. `kr_put` erzeugt pro Arbeitsrevision und Objektkennung **unveränderliche** Referenzen (Art, Quellverweis, Versionsdigest, Evidenzepoch). `kr_link` erzeugt gerichtete und per Fremdschlüssel gebundene Beziehungen. Beide Operationen sind bei identischer Wiederholung idempotent; Änderungen derselben Kennung in derselben Revision werden abgewiesen.

`kr_cursor_open` fixiert die Arbeitsrevision, Evidenzepoch und die pro Work geänderte Registergeneration. `kr_cursor_read` liest eine Position; `kr_cursor_edges` liest **maximal 64** gerichtete Nachbarn mit binärer Sortierung und keyset-basierter Fortsetzung. Jede Abfrage prüft Version und Generation **innerhalb derselben kurzen SQLite-Lesetransaktion**. Neue Registereinträge, Links oder Work-Ereignisse invalidieren alte Cursor ausdrücklich. Es gibt weder ungesicherte Zeiger auf SQLite-Puffer noch einen vollständigen Register-Dump.

**Vorläufige Grenze:** Der Register-Write-API fehlt weiterhin die OS-basierte Authentifizierung des vertrauenswürdigen Hosts. Worker dürfen daher weder Registerdatei noch schreibfähige API erhalten. Das Register ist ein Index, keine unabhängige Oracle-/Verifikationsinstanz. Read-Handles sind pro Thread separat zu führen. SQLite-WAL unterstützt gleichzeitige Leser und genau einen jeweils aktiven Schreiber; es gibt noch keinen C11-Threadpool, keine adaptive Horizon-Erweiterung und keine gemessene Latenzverbesserung.

`tests/test_register.c` enthält deterministische Testfälle für Idempotenz, Referenzintegrität, gerichtete Kanten, Keyset-Pagination, Generation-Konflikte, Versionswechsel und Neustart. **Nicht ausgeführt**; weder lokal noch über CI.
