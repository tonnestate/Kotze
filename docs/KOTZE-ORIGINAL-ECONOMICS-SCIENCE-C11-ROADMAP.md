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

**Kein Entweder-oder, aber eine klare Reihenfolge:** Zuerst sicherer Single-Worker und unabhängig überprüfbares Ergebnis. **Parallel zur minimalen Laufzeit wird früh ein versioniertes Harness-Profil-/Experimentmodell vorbereitet.** Harness²-artige Optimierung ist die erste größere Forschungsschicht nach dem vertrauenswürdigen Host; zusätzliche parallele Agenten werden nur bei positivem Grenznutzen aktiviert. Selbstoptimierung darf niemals die C11-Sicherheitsinvarianten ändern.

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
| Google-Harness²-artige Profilversionierung, Experimente, Promotion | Nicht nachgewiesen | Neue hohe Entwicklungspriorität, nicht als produktive Funktion ausgeben |
| Grok-artige Multi-Agent-Orchestrierung | Nicht nachgewiesen | Vorläufig zurückgestellt; kein Produktmerkmal |

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

Für eine Harness-Verbesserung gilt eine **Amortisationsbedingung**: Einsparungen aus späteren unabhängigen, verifizierten Aufgaben müssen zusätzliche Entwicklungs-, Probe-, Laufzeit- und Wartungskosten übersteigen. Die primäre Vergleichsgröße bleibt dabei **Kosten pro verifiziertem Erfolg**, nicht nur Kosten pro Modellaufruf. Eine Beschleunigung oder Tokenersparnis bei sinkender Korrektheit ist kein automatischer Gewinn. Die Probe-Kosten zählen einschließlich verworfener Kandidaten und können bei einem Einmalauftrag überwiegen.

## 4. Wissenschaftliche Evidenz und Lieferantenvergleich

1. **Google Harness² (Oktober 2026):** trennt taskbezogenes Propose–Probe–Compose (Kontrastvergleich ohne Ground Truth während der Optimierung) von einer dauerhaften Experience-/Improvement-Schleife. Es nennt acht veränderliche Harness-Bestandteile: System Prompt, Guardrails, Memory, Tool Guidance, Subagents, Skills, Scripts und Plugins. Die berichteten Verbesserungen beziehen sich auf die untersuchten Modelle und Work-Benchmarks, nicht automatisch auf Coding-Reparatur. Das Repository beschreibt Benchmark-Setups mit offenen Netzen und teilweise deaktivierter Executor-Sandbox: **diese Sicherheitseinstellungen dürfen nicht übernommen werden**.  
   Quellen: https://github.com/google-research/harness2 ; https://arxiv.org/abs/2610.14224
2. **OpenAI (August/September 2026):** der offen zugängliche Codex-Harness und seine App-Server-Schnittstelle demonstrieren, wie Agent-Loop, Kontextmanagement, Tool-Events, Freigaben und Sandbox voneinander abgegrenzt werden können. Der managed Agents API-Ansatz unterstützt langlebige Läufe mit persistiertem Zustand und Recovery, ist aber ein optionaler externer Dienst mit eigenen Kosten und Vertrauensannahmen. Das Harness-Engineering beschreibt außerdem kurze, auffindbare Repository-Dokumentation statt eines riesigen und schnell veraltenden Regel-Prompts.  
   Quellen: https://developers.openai.com/blog/codex-as-a-platform ; https://openai.com/index/introducing-the-agents-api/ ; https://openai.com/index/harness-engineering/
3. **Anthropic (November 2025–April 2026):** der Long-Running-Harness verwendet inkrementelle Arbeit und klare Übergaben über Kontextfenster; Managed Agents trennt das langlebige Event-Log von der Modellkontext-Auswahl. Daraus folgt für KOTZE: **persistente Fakten/Events außerhalb des Kontextfensters**, selektive Rekonstruktion, kompakte Fortschrittsübergaben und kein künstliches Wiederauffüllen des gesamten Gesprächs. Ein separater Evaluator kann fachlich sinnvoll sein, muss aber für echte Zero-Trust-Garantien zusätzlich betriebssystemseitig getrennt sein.  
   Quellen: https://www.anthropic.com/research/effective-harnesses-for-long-running-agents ; https://www.anthropic.com/research/managed-agents ; https://www.anthropic.com/research/harness-design-long-running-apps
4. **Empirisches Harness-Design:** die Wirkung von Kontextstrategie, Planung und Werkzeugumfang hängt vom Modell und der Aufgabe ab. Daraus folgt keine pauschale Empfehlung für viele Agenten oder möglichst umfangreiche Toolkataloge.  
   Quelle: https://arxiv.org/abs/2609.20804
5. **Grok/xAI Multi-Agent:** parallel arbeitende Agenten können bei gut zerlegbaren Aufgaben nützlich sein, erhöhen jedoch Inferenz- und Koordinationskosten. Ein Agenten-Konsens beweist keine korrekte Änderung. In KOTZE nur ein **späteres, selektives Eskalationsmittel**.  
   Quelle: https://docs.x.ai/developers/model-capabilities/text/multi-agent

Diese Belege begründen ein Forschungsprogramm und eine ökonomisch sinnvolle Reihenfolge, **keinen bereits gemessenen KOTZE-Leistungsvorsprung**.

## 5. Neu priorisierte Implementierung — Harness² vor Multi-Agent

| Priorität | Maßnahme | C11-Anteil | Nachweis-/Kostengrenze |
| --- | --- | --- | --- |
| **P0.1** | Trusted Host und IPC mit authentifizierter Peer-Identität, strikt validierten Nachrichten, Rollen-/Capability-Mapping | **Kern in C11**, Linux-OS-Adapter | Worker erhält keine DB-/OWNER-/VERIFIER-Rechte |
| **P0.2** | Deny-by-default Tool-Dispatcher, Pfad-/Prozess-/Budget-/Netzwerk-Gates | **Kern in C11**, isolierte OS-Ausführung | Verbotene Aktionen erreichen das Host-System nicht |
| **P0.3** | Getrennter Verifier mit eingefrorenen Orakeln, Versionen, Prüfnachweisen | **Admission, Ledger, Gates in C11**; Oracle-Prozess extern | Worker kann Tests/PASS-Meldungen nicht manipulieren |
| **P0.4** | Minimaler Single-Worker-Loop mit austauschbarem Modelladapter | **Protokoll/FSM in C11**, Provider/Inference außerhalb | Eine Aufgabe erreicht korrekten, überprüften Abschluss |
| **P0.5** | Git-Baseline, geschützter Patch, Recovery und vorhandene Effect-Outbox komplett anbinden | **Leases, Zustandsprüfung in C11**, Git-Adapter extern | Keine doppelte unbekannte Remote-Mutation |
| **P1.1 — vorgezogen** | **Harness²-Profilregister:** versionierte `system_prompt`, `guardrail_config`, `memory_policy`, `tool_guidance`, `subagent_policy`, `skill_set`, `script_set`, `plugin_set`; feste Baseline und unveränderliche Schutzregeln | **Ja: Versions-/Hash-/Zulassungs- und Promotion-Metadaten in C11/SQLite** | Konfiguration ist reproduzierbar, kein Profil kann Sicherheitsgrenzen erweitern |
| **P1.2 — vorgezogen** | **Context Engineering nach OpenAI/Anthropic:** Event-Slicing, gezieltes Repository-Retrieval, kompakte Übergabe, deterministisches Elision-/Budget-Management | **Nur Kontext-/Budget-Policy in C11**, Retrieval/Formatter extern | Wiederaufnahmen und Kontextkosten reproduzierbar |
| **P1.3** | Versionsgebundene Skills/Tool-Guidance für einzelne Modelle, einschließlich Gemma | **Capability- und Skill-Freigabe in C11** | Keine unbewertete Übernahme beliebiger externer Skills |
| **P2.1 — vorgezogen** | **Harness²-Experimentledger:** Propose–Probe–Compose als optionale, streng budgetierte Offline-/lokale Versuchsschleife; Kandidaten erfassen, Ergebnisse vergleichen, Zusammenstellung dokumentieren | **Ja: Profil-Snapshots, Budget-/Experimentzustände, Metadaten**; Candidate-Generator/Probes extern | Kein autonomer Probe-Lauf ohne explizite Freigabe; Kosten inkl. Fehlschlägen |
| **P2.2** | Statistical Second Brain: versionierte Episoden und unabhängige Erfolgs-/Fehleretiketten | **Ja für Ledger**, Statistik ggf. extern | Nur vertrauenswürdige Evidenz, Konfidenz und ABSTAIN |
| **P2.3** | Promotion-/Rollback-Gate für Verbesserungen auf Held-out-Aufgaben | **Ja: explizite Freigabe und unveränderliche Policy** | Nur nach unabhängigen vergleichbaren Ergebnissen, Kosten-/Risiko-Nachweis |
| **P4** | Selektive Grok-artige Multi-Agent-Orchestrierung | **Nur Budget-/Delegationspolicy in C11** | Erst bei nachgewiesenem Mehrwert gegenüber Single Worker; standardmäßig aus |
| **P5** | LoRA/Distillation/Training | **Nein** | Nur wenn Modellgewicht-Engpass statt Harness-Engpass nachgewiesen ist |

### C11-Grenze für Harness²

**In C11 implementieren:**
- `harness_profiles` mit stabilen IDs, Versionen, Hashes, Elternbeziehung, Modellspezifikation und freigegebenem Skill-/Tool-Umfang;
- `harness_experiments` mit Basis-/Kandidatenprofil, eingefrorenem Task-/Umwelt-Digest, Probe-Budget, Kostenereignissen und Stop-Zustand;
- `harness_promotion` mit Evidence-Referenz, unabhängiger Prüfer-Autorität, Ablehnungsgrund, voriger Version und Rollback-Protokoll;
- sichere, schreibgeschützte Abfrage eines freigegebenen Profils durch den Host, niemals Schreibrecht des Coding-Workers;
- eindeutige Zuordnung jedes Work-Laufs zu exakt einer Profilversion, sodass nachträgliche Profiländerungen keine Historie umlabeln.

**Nicht in C11 implementieren:** Modell-Prompts schreiben, Kandidaten semantisch bewerten, Transformer inference, externe Benchmark-Probes, ein generisches LLM-Framework oder parallele Spezialagenten. Diese Komponenten gehören hinter das vorhandene Host-/Capability-Gate.

**Wesentliche Unterscheidung:** Dass Harness² auf einer Aufgabe ohne Ground-Truth-Feedback **Verbesserungskandidaten** auswählt, rechtfertigt keine ungeprüfte **produktive Promotion**. KOTZE verwendet weiterhin geschützte Held-out-Orakel oder ausdrücklich freigegebene manuelle Abnahme. Durch zusätzliche Probes entstehende Kosten sind vollständig zu erfassen.

**Kernentscheidung:** **P0 Host/Verifier ist das Sicherheitsfundament; P1 Harness²-Profile und OpenAI-/Anthropic-Kontextverfahren sind der nächste Leistungshebel; P2 evaluiert begrenzt; P4 Multi-Agent bleibt deaktiviert.** Kein Bau-/BIM-/Reporting-Scope im Originalkern.

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

**Schlussentscheidung:** C11 implementiert verbindliche Kontrolle, Persistenz, Harness-Profilversionen und Ausführungsgrenzen. **Google Harness² ist nach dem sicheren Single-Worker-Fundament der wichtigste frühe Forschungshebel.** OpenAI und Anthropic liefern anschlussfähige Methoden für Kontext, Laufzeit und persistente Übergaben. Multi-Agent wird nur bei belegter Grenzwirtschaftlichkeit freigeschaltet. Wachstum der Codebasis ist kein Leistungsindikator. **Ein korrekt kontrollierter und unabhängig nachweisbarer End-to-End-Workflow bleibt der erste technische Meilenstein.**
