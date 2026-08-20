# hardware/ — index

Partie **hardware** de Portal6-music (anciennement projet autonome `project-radio`, intégré
au monorepo le 2026-08-20). Notes de design du projet **Radio** : un poste **Brandt RK 711S**
transformé en web-radio autonome, alimenté par un **serveur de web-radios personnelles**.
Commencer ici.

Le projet a **deux pistes** qui se rejoignent sur un seul contrat : le poste est un **client**
des flux et de l'API du serveur.

```
   PISTE SERVEUR                              PISTE POSTE
   AzuraCast, stations,          ──flux──►    Brandt RK 711S
   grilles, énergie E1–E5         ──API──►    Raspberry Pi, visualiseur
```

## Piste POSTE — le Brandt

| Document | Ce que c'est |
|---|---|
| [design-brandt-rk711s.md](design-brandt-rk711s.md) | **La note maîtresse.** Concept, architecture, sous-systèmes, raccordement, plan en 10 phases avec STOP / VÉRIFIER, décisions D1–D15, questions ouvertes, interdits, journal des pivots. Tout le reste en dépend. |
| [design-visualiseur.md](design-visualiseur.md) | Écran (D9), moteur de visualisation type Winamp/MilkDrop, couche applicative (D14). |
| [design-alimentation.md](design-alimentation.md) | Pack 3S 18650, BMS, chargeur sur le secteur d'origine (C7), rails 12 V / 5 V, découplage, masse en étoile, modèle de veille (D15), **sécurité 230 V**. |
| [bom.md](bom.md) | Nomenclature et outillage, en checklist, avec pour chaque ligne ce qui doit être décidé ou mesuré avant d'acheter. |

## Piste SERVEUR — les web-radios

| Document | Ce que c'est |
|---|---|
| [design-serveur-azuracast.md](design-serveur-azuracast.md) | L'infrastructure : AzuraCast sur Docker, l'état **bloqué** de l'installation Windows, le plan de reprise, la bibliothèque centrale `M:\music`. |
| [design-programmation-editoriale.md](design-programmation-editoriale.md) | L'éditorial : échelle d'énergie **E1–E5**, Midnight Club, Stage 303, la station Hip-Hop en conception, tagging automatique, likes, hub Plex. |

## Où en est le projet

| | État |
|---|---|
| **Poste** | Cadrage terminé. **Rien n'est construit, rien n'est acheté, aucun outillage possédé.** Bloqué par la **Phase 0** : les mesures sur le poste ouvert (haut-parleurs, profondeur du logement cassette, touches, mécanisme d'accord). |
| **Serveur** | **Bloqué.** Aucun déploiement AzuraCast fonctionnel sur l'installation Windows. Reprise à la Phase 1 : vérifier la méthode officielle avant d'écrire le moindre YAML. |

## Comment ces notes fonctionnent

- Ce sont des **walkthroughs d'exécution**, pas des comptes rendus : on avance **une phase à
  la fois**, et chaque phase se termine par un **STOP / VÉRIFIER** à passer avant la suivante.
- Elles **s'enrichissent au fil du projet** : les `?` sont remplacés par les mesures réelles,
  les décisions se figent dans le tableau §3 de la note maîtresse, le journal §12 garde la
  trace des changements de cap et de leurs raisons.
- **On mesure, on ne suppose pas.** Toute valeur non vérifiée est marquée comme telle.
- Chaque note se termine par une **liste d'interdits** — ce sont les erreurs déjà commises ou
  identifiées, écrites pour ne pas les refaire.

## Historique

Deux fichiers issus de sessions ChatGPT antérieures ont servi de matière première et **ne font
pas référence** : `synthese_brandt_rk711s.md` (incomplet — placeholder au milieu de la BOM) et
les notes de passation du serveur radio. Leur contenu utile a été repris, corrigé et structuré
ici.

Le poste a changé deux fois d'architecture pendant le cadrage (ESP32 → Android/Rockchip →
Raspberry Pi). Le détail et les raisons sont dans le journal de
[design-brandt-rk711s.md](design-brandt-rk711s.md) §12.
