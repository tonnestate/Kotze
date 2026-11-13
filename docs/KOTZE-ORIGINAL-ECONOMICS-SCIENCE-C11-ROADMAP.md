# KOTZE Original — wirtschaftlich und wissenschaftlich priorisierte C11-Roadmap

**Stand:** 13. November 2026  
**Status:** Architektur- und Investitionsentscheidung nach Quelltextprüfung. Keine Implementierungs-, Test- oder Leistungsbehauptung für noch fehlende Funktionen.  
**Zielbild:** modellunabhängiger Harness für autonome Softwareentwicklung. Reproduktion, Reparatur und unabhängige Verifikation eines konkreten Defekts bilden den ersten vollständigen End-to-End-Nachweis.  
**Codebasis:** `tonnestate/Kotze`, Original-Entwicklungsbranch `feat/kotze-recovery-resume` auf Basis von `feat/kotze-effect-dispatch`. KOTZE-4-2 und FruitStack-Donoren bleiben getrennt.  
**Freigabegrenzen:** Keine kostenpflichtigen CI-Runner, GitHub Actions, laufende Benchmark-/Modelltests, Deployments oder weitere externen Nebenwirkungen ohne explizite Zustimmung.

## 1. Grundentscheidung: alle Konzepte können zusammenarbeiten

Der Nutzer hat zu Recht festgestellt: Die Ansätze konkurrieren nicht. Sie stehen auf verschiedenen Ebenen.

- **Grok / parallele Agenten:** optionale funktionale Zerlegung in Spezialisten, konsolidiert durch einen Koordinator. Mehr Agenten können mehr Perspektiven liefern, verursachen aber zusätzliche Inferenz- und Koordinationskosten. Ein Konsens ist kein unabhängiger Prüfnachweis.
- **Google Harness²:** versionierte Änderungen an Harness-Konfigurationen durch Propose–Probe–Compose; Erfahrungen aus früheren Aufgaben beeinflussen spätere Verbesserungsversuche. Modellgewichte bleiben dabei fest. Keine ungeprüfte Übernahme von Benchmark-Setups ohne Isolation.
- **Gemma-Jacket:** ein und derselbe native Host kann einem kleinen Modell gezielten Kontext, begrenzte Werkzeuge und Skills bereitstellen. Die Verbesserung ist für jede konkrete Modell-/Aufgabenkombination erst zu messen.
- **Statistical Second Brain:** bewahrt Arbeitserfahrungen, Fehler, Resultate, Unsicherheit und tatsächliche Kosten auf, ohne selbst Normen, Regeln oder Berechtigungen zu überschreiben.
- **Repair-Paar und Zero Trust:** Reparaturakteur und Prüfer sind durch Betriebssystemrechte und unabhängige Datenquellen getrennt. Zwei unterschiedliche LLM-Prompts sind keine Sicherheitsisolation.
- **KOTZE C11-Kern:** die verbindende, stabile Kontrollschicht für Vertrag, autorisierte Aktionen, Zustand, Budget, Beweiskette, Effekte und Wiederanlauf.

**Kein Entweder-oder:** Zuerst ein einzelner funktionsfähiger Coding-Worker mit dem Host; optionale Spezialagenten oder Harness-Optimierung werden später als austauschbare, streng kontrollierte Policies aufgesetzt.

## 2. Was die Repositoryprüfung tatsächlich bestätigt

| Bestandteil | Status im Original-Entwicklungsbranch | Wichtige Grenze |
| --- | --- | --- |
| C11-Work-FSM, Revisionsvertrag, SQLite WAL, Aktionen und Budgets | Quellcode vorhanden | Aufruferidentität nicht authentifiziert |
| Persistente Hypothesen und Anti-Repeat-Gates | Quellcode vorhanden | Kein autonomer Worker |
| Effekt-Dispatch, Fencing, UNKNOWN/Reconciliation, History | Quellcode vorhanden | Kein ausgeführter Host-/Provider-Adapter |
| `kd_list_unsettled`, `kd_mark_crashed` | Quellcode im Recovery-Branch | Noch kein Host, der Worker-Tod und Remote-Wirkungen nachweist |
| Externer Skill-Grader | Quellcode im Repository | Nicht mit der produktiven End-to-End-Verifikation gleichzusetzen |
| Gemma/andere Modelladapter, sicherer Tool Runner, Git-Patching | Nicht nachgewiesen | Zentraler fehlender vertikaler Slice |
| Tatsächlich OS-isolierter, unabhängiger Prüfer | Nicht nachgewiesen | Die größte Sicherheitslücke |
| Statistik/Repair-Empfehlung | Experimenteller Code auf dem **getrennten KOTZE-4-2-Branch** | Noch nicht im Original integriert; Rollen nicht vertrauenswürdig authentifiziert |
| Grok-artige Multi-Agent-Orchestrierung oder Harness²-Promotion | Nicht nachgewiesen | Forschungsoption, kein Produktmerkmal |

**Qualitätseinschränkung:** Diese Bestandsaufnahme erfolgte als Read-only-Inspektion. Die aktuellen Branch-Änderungen wurden nicht kompiliert oder getestet. Ein Dateiname, eine Dokumentation oder ein Testfall beweist keinen fehlerfreien Ablauf.

## 3. Wirtschaftliche Entscheidungsregel: Cost per Verified Result

KOTZE wird nicht nach maximaler Agentenzahl oder Modellintelligenz optimiert, sondern nach:

`Kosten je unabhängig verifiziertem Ergebnis = Gesamtkosten aller Versuche / Anzahl unabhängig verifizierter korrekter Ergebnisse`

Die Gesamtkosten umfassen:
- tatsächliche Modell-Input-/Output-/Reasoning-Tokens und Provider-/GPU-Kosten;
- Werkzeug-/Rechenzeit, Speicher, externe Dienste, etwaige Runner;
- Retry-, Multi-Agent-, Harness²-Probe- und Fallback-Kosten;
- menschliche Freigaben, Nachbearbeitung und Wartung;
- Sicherheits- und Ausfallfolgen als gesonderte Risikodimension, nicht als erfundener pauschaler Geldbetrag.

Weitere Zielmetriken: unabhängige Erfolgsquote, Zeit bis zur verifizierten Lösung, Anteil verbotener Aktionen (**muss Null sein**), falsche PASS-Meldungen (**muss Null sein**), Wiederholungsschleifen, Aufgabenabbrüche, Sicherheitsvorfälle, gemessene Regressionen.

**Wichtig:** Ohne echte Laufzeitmessungen gibt es keine belastbaren Eurobeträge oder ROI-Prognosen. Die folgende Reihenfolge ist eine risikogewichtete Architekturhypothese, keine empirisch belegte KOTZE-Rangliste.

## 4. Wissenschaftliche Evidenz: was sich übertragen lässt

1. **Harness-Design hängt von Modell und Kontext ab.** In 176 experimentellen Einstellungen mit vier Modellen und zwei Coding-Benchmarks war regelbasierte Kontext-Elision vor modellgestützter Zusammenfassung häufig effizient. Explizite Planung und Toolregister hatten unterschiedliche Effekte abhängig von Modellfähigkeit und Aufgabenart. Daraus folgt **kein** universeller Sieg großer Toolregister.  
   Quelle: https://arxiv.org/abs/2609.20804
2. **Harness² zeigt Verbesserungen durch Meta-Optimierung**, aber nur für untersuchte Modelle/Benchmarks. Der Propose–Probe–Compose-Prozess hat eigene Explorationskosten. Erst bei wiederkehrender Nutzung und gemessenen Folgegewinnen kann sich diese Investition rechnen.  
   Quelle: https://github.com/google-research/harness2
3. **xAI Multi-Agent** beschreibt einen führenden Agenten plus vier oder 16 zusammenarbeitende Agenten. xAI nennt höheren Tokenverbrauch und längere Latenz bei höherer Agentenzahl. Die dokumentierte Zusammenarbeit darf nicht mit einer kausal bewiesenen Verbesserung der KOTZE-Code-Reparatur gleichgesetzt werden.  
   Quelle: https://docs.x.ai/developers/model-capabilities/text/multi-agent
4. **Verschiedene Harness-Komponenten können sich negativ auswirken.** Für Coding-Aufgaben untersuchte Forschung findet abnehmenden Grenznutzen komplexer Harnesses und teils Nachteile für pauschale Kontextkompression oder generische Subagenten. Deshalb müssen Optionen einzeln und in Kombination abliert werden.  
   Quelle: https://arxiv.org/abs/2609.32459
5. **Externe Skills/MCP-Konfigurationen schaffen eine Supply-Chain-Fläche.** Das bloße Installieren zahlreicher GitHub-Skills ist kein Sicherheits- oder Qualitätsnachweis. Versionen, erlaubte Aktionen, Herkunft und Rechte müssen überprüft werden.  
   Quelle: https://arxiv.org/abs/2609.07360

Diese Quellen liefern methodische Hinweise, **keine auf KOTZE gemessenen Ergebnisse**.

## 5. Priorität und technische Abgrenzung

| Priorität | Zu implementieren | Gehört in C11? | Wirtschaftlich/wissenschaftliche Begründung | Fertig, wenn… |
| --- | --- | --- | --- | --- |
| **P0.1** | Authentifizierter lokaler Host, autoritative Rollentrennung und IPC mit Schema-/Größenprüfung | **Ja**, plus OS-spezifische Sicherheitsadapter | Erst damit werden Verbotspolitik und Prüfergrenze technisch erzwingbar. Ohne diesen Schritt sind Erfolgsaussagen wertlos. | Worker darf weder DB noch VERIFIER/OWNER-Aktionen direkt ausführen |
| **P0.2** | Kontrollierter Tool- und Prozessdispatcher (argv statt Shell-Interpolation, Arbeitsverzeichnis, Ressourcenlimits, Zeitüberschreitung, Ausgabenlimit, Deny-by-default) | **Ja** für Steuerung, OS-Adapter für Sandbox | Ermöglicht erstmals reale, begrenzte Arbeit und schützt vor finanziellen/technischen Nebenwirkungen. | Erlaubte Aktionen sind protokolliert; verbotene Aktionen haben keine Wirkung |
| **P0.3** | Vertrauenswürdige Verifier-Grenze, eingefrorener Ausgangszustand, originaler Fehlerpfad, regressionsbezogene Belege | **Ja** für Beweis- und Zustandskontrolle; Prüftools extern | Ohne echte unabhängige Prüfung lässt sich weder Skill-Lift noch Erfolg messen. | Worker kann eigene PASS-Receipts nicht erzeugen oder Testorakel ändern |
| **P0.4** | Einfacher Single-Worker-Model-/Tool-Loop mit austauschbarem Adapter | **Nur Protokoll/Kontrolle in C11**; Modell-API außerhalb | Kleinster vollständiger funktionaler Slice. Keine teure Orchestrierung vor Produktnachweis. | Ein Bug wird von Aufnahme bis Patch und unabhängigem Prüfresultat bearbeitet |
| **P0.5** | Git-Workspace-/Patch-Sicherung, unveränderter Baseline-Snapshot, last-good Candidate, Absturz-Recovery | **Teilweise** (Leases, Digests, Admission), Git-/Filesystem-Adapter separat | Verhindert Zerstörung und Wiederholung unklarer Außenwirkungen. | Neustart führt zu erklärbarem sicheren Status, nicht zum doppelten Effekt |
| **P1** | Deterministisches Retrieval, knappe Dateikontexte, Budget-bewusste Kompaktierung | **C11 nur für Budget-/Policy-Gates** | Hoher plausibler Kosten-/Qualitätshebel, ohne jeden Schritt durch ein LLM zu schicken. | Auditierbare Reduktion von Kontext-Überlauf und Tokenverschwendung |
| **P1** | Modellabhängige Tool-/Skill-Profile (Gemma zuerst nur nach konkretem Testplan) | **C11 für Zulassung und Versionen**, Skills extern | Kleine Modelle können gezielt entlastet werden, ohne Modelltraining. | Pro Profil sind Tools, Rechte und Kosten reproduzierbar |
| **P2** | Evidence-labelled Episodenspeicher und konservative Repair-Empfehlung | **Ja** für Journaling und Auslese; Statistik ggf. extern | Lernfähigkeit über Aufgaben, aber erst sinnvoll mit vertrauenswürdigen Prüfnachweisen. | Ergebnisse sind task-/umgebungsgebunden; sparse cohorts führen zu ABSTAIN |
| **P3** | Selektive, begrenzte parallele Spezialagenten mit Merge-/Conflict-Gates | **C11 für Rechte/Budget**, Orchestrierung extern | Kann bei zerlegbaren Problemen helfen, aber Multi-Agent-Kosten und Koordinationsfehler beachten. | Gegen Single-Worker-Baseline messbarer Mehrwert bei gleichem Gesamtbudget |
| **P4** | Harness²-inspirierte, versionierte Propose–Probe–Compose-Forschung und Promotion-Gates | **C11 für unveränderbare Schutzregeln und Promotionsfreigabe** | Potenziell skalierbar, aber hohe Kosten für Kandidaten/Probes und Gefahr von Overfitting. | Held-out-Erfolg und Kosten stimmen, Sicherheitsregeln bleiben unangetastet |
| **P5** | LoRA/Distillation/Training | **Nein** | Erst sinnvoll, wenn Daten belegen, dass Modellgewichte – nicht Toolführung/Kontext/Oracle – limitieren. | Vorab registrierter Vergleich zeigt Nettoverbesserung gegenüber einfachem Jacket |

**Kernentscheidung:** Im nächsten Schritt **P0.1 + P0.2 als eine sichere Host-Grenze** implementieren, danach P0.3 und einen vollständigen P0.4-Slice. Keine zusätzliche Reporting-Engine, BIM-, Bau-, ISO- oder Präsentationsfunktion im Originalkern.

## 6. Was wir bewusst *nicht* in C programmieren

- Keine eigene Transformer-Inferenz, Tokenisierung, Gemma-Feinabstimmung oder model-spezifischen Prompt-Formatter in C.
- Keine komplette Git-/AST-/LSP-Engine neu schreiben; geprüfte bestehende Werkzeuge kapseln.
- Keine neue generische Vektor-Datenbank, keinen SQL-Ersatz, kein graphisches Workflow-Studio und kein BI-Frontend im Kern.
- Keine allgemeine n8n-Kopie oder Cloud-Orchestrierungsplattform, bevor die minimalen Coding-Aufgaben funktionieren.
- Keine eingebauten Benchmark-Grader im selben Sicherheitskontext wie der Worker.
- Keine automatische Änderung des C11-Sicherheitskerns durch einen LLM-Self-Improver.

## 7. Forschungs- und Budget-Gates vor größerer Investition

Erst **nach ausdrücklicher Freigabe** kontrollierte, lokale Offline-Tests und später optional begrenzte Modell-Versuche durchführen.

- **Baseline:** dieselben Aufgaben mit einem einfachen Worker/Tool-Loop und ohne zusätzliche intelligente Schichten.
- **Paarung:** identischer Task, Repo-Snapshot, Modelldatei/API-Version, Budget, Tool-/Zeitlimits, Hardwareprofil; Reihenfolge randomisieren, soweit praktisch.
- **Ablationen:** jeweils nur eine Komponente variieren: Kontextstrategie, Skills, Planung, Multi-Agent, Repair Memory, rekursive Harness-Verbesserung.
- **Wissenschaftliche Messung:** getrennte Trainings-/Entwicklungs-/Held-out-Aufgaben; Konfidenzintervalle für gepaarte Erfolgsdifferenzen, Mehrfachtestkontrolle, offengelegte fehlgeschlagene/censored Runs, Protokollversionen und Samplegrößen.
- **Wirtschaftliche Messung:** Gesamtressourcenverbrauch **einschließlich fehlgeschlagener Versuche**; Kosten je unabhängig verifiziertem Erfolg und Netto-Zeitersparnis.
- **Sicherheits-Gate:** Jede Policy-Umgehung, unerlaubte Mutation oder Worker-fälschbare Prüfaussage sperrt die Promotion unabhängig von Accuracy.
- **Stop-Regel:** Keine neue Agentenebene, kein großer Skill-Katalog und kein Training, wenn der zusätzliche Nutzen nicht durch unabhängige Ergebnisse und Gesamtkosten getragen wird.

## 8. Konkrete nächste Engineering-Aufgabe (ohne Ausführung in diesem Commit)

**Native Trust Boundary / Host Admission — Design to Code:**

1. Linux-spezifische lokale IPC-Schnittstelle mit authentifizierter Peer-Identität und versionierten, strikt begrenzten Nachrichten.
2. Server-seitige Rollen- und Capability-Mapping-Policy; WORKER darf niemals OWNER oder VERIFIER auswählen.
3. Operation-Katalog mit bindbarer Policy-Revision, kanonisierten `argv`, Pfadfreigaben und Ressourcengrenzen.
4. Externe Ausführungsrechte, Netzwerk und Dateisystem auf OS-Ebene isolieren; Git-Worktree allein ist kein Sandbox-Ersatz, Docker nicht zwingend.
5. Admission in vorhandene SQLite FSM/Effect-Outbox führen; kein selbstgeschriebenes zweites Action-Journal.
6. Reviewer-/Verifier-Seite mit geschützten Orakeln und eigener Autorität, nicht im Worker-Sandbox-Prozess.
7. Statische und deterministische Tests für denied actions, Replay, Crash/Fencing, Rollback, Verifier-Impersonation und stale receipts **nur vorbereiten**, nicht ohne Freigabe starten.

Erst danach die erste real ausgeführte und unabhängig geprüfte Coding-Aufgabe. Diese Priorität folgt aus Risikoreduktion und der Fähigkeit, den späteren Mehrwert überhaupt belastbar messen zu können.

## 9. Bezugsquellen und Grenzen

- Google Research Harness²: https://github.com/google-research/harness2
- Empirical Study of Harness Design for Coding Agents: https://arxiv.org/abs/2609.20804
- Beyond the Model: Demystifying Harness Effects: https://arxiv.org/abs/2609.32459
- Scanning the Harness: https://arxiv.org/abs/2609.07360
- xAI Multi-Agent documentation: https://docs.x.ai/developers/model-capabilities/text/multi-agent
- KOTZE Original: `docs/CORE_PHASE1.md`, `docs/EFFECT_DISPATCH.md`, `docs/KOTZE-Agent-Konzept.md`

**Schlussentscheidung:** C11 implementiert verbindliche Kontrolle, Persistenz und Ausführungsgrenzen. Modelle, Skills, Spezialagenten und Harness² sind austauschbare, ökonomisch nachzuweisende Optionen darüber. Wachstum der Codebasis ist kein Leistungsindikator. **Ein korrekt kontrollierter und unabhängig nachweisbarer End-to-End-Workflow ist der erste wirtschaftliche und wissenschaftliche Meilenstein.**
