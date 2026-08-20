# BOM — nomenclature, sourcing et outillage

**Statut :** **liste de courses en cours d'instruction — rien n'est commandé, rien n'est figé**
**Date :** 2026-08-12 (révision 3 — intégration de la liste Amazon existante + audit)
**Note mère :** [design-brandt-rk711s.md](design-brandt-rk711s.md)
**Piste :** POSTE

> **À LIRE EN PREMIER.**
> Cette liste n'est **pas une commande**. La colonne **Débloqué par** dit ce qui doit être vrai
> avant d'acheter la ligne ; une ligne bloquée qu'on commande quand même est de l'argent joué à
> pile ou face.
>
> **Sur les liens et les prix.** Les liens marqués 🔖 viennent de la **liste Amazon existante**,
> constituée entre **août et septembre 2025** — donc **avant les deux pivots d'architecture**
> (§0). Les prix sont ceux relevés à ce moment-là : ils ont presque un an, ils sont
> **indicatifs et à revérifier**. Les lignes sans lien portent un **terme de recherche** et une
> **fourchette** : aucun lien n'est inventé.
>
> ⚠️ **Deux points de sécurité issus de l'audit sont dans le §0.2. Les lire avant tout achat.**

---

## 0. Audit de la liste existante

### 0.1 À retirer — rendus inutiles par les pivots

| Article de la liste | Prix relevé | Pourquoi il saute |
|---|---|---|
| 🔖 [Module USB Host Shield 2.0 (MAX3421E)](https://www.amazon.fr/dp/B0DM5VGLMK/) | — | L'USB est **natif** sur le Raspberry Pi (D13). |
| 🔖 [Freenove ESP32](https://www.amazon.fr/dp/B0C9TGJRPH/) | 12,95 € | L'ESP32 n'est plus le cerveau (D2). *À garder si tu veux un jouet de test, pas nécessaire au projet.* |
| 🔖 [Connecteurs USB-C vers DIP ×10](https://www.amazon.fr/dp/B0BGPGNSBW/) | 6,99 € | Reliquat de l'ancienne idée « alimentation USB-C PD », abandonnée au profit du **secteur C7 d'origine** (D6). |
| 🔖 [Headers DIP 1,27 mm ×5](https://www.amazon.fr/dp/B0CRTBTPPD/) | 8,49 € (+3,66 € port) | Pas 1,27 mm : le pas standard du Pi et des modules est **2,54 mm**. Sauf besoin précis identifié, inutile. |

### 0.2 ⚠️ À revoir — deux points de sécurité

**1. Les fusibles auto ne vont pas sur le secteur.**

🔖 [JOREST porte-fusible + fusibles ATC](https://www.amazon.fr/dp/B0DBPQBGBQ/) (9,99 €) et
🔖 [AUPROTEC Mini LP 7,5 A](https://www.amazon.fr/dp/B08BZTJ5Q7/) (4,30 €) sont des fusibles
**automobiles**, donnés pour **12 V / 58 V DC**. Ils sont parfaits **côté batterie**. Ils ne
doivent **jamais** être utilisés sur le **230 V AC** : le pouvoir de coupure n'est pas celui-là,
et un fusible qui ne coupe pas un défaut secteur, c'est un incendie.

→ Il faut **en plus** un porte-fusible et une cartouche **5×20 mm homologués secteur**,
côté 230 V. Voir [design-alimentation.md](design-alimentation.md) §8.

**2. Le pack batterie proposé est un LiPo RC, pas ce que la conception prévoit.**

🔖 [Zeee 3S LiPo 3300 mAh 11,1 V 50C](https://www.amazon.fr/dp/B0DHX5HBL2/) (57,99 €) est une
**batterie de modélisme**. Les faits, sans dramatiser :

| | LiPo RC (Zeee) | 3× 18650 + BMS (conception actuelle) |
|---|---|---|
| Capacité | 3300 mAh ≈ **36 Wh** | 3× 3500 mAh ≈ **39 Wh** — équivalent |
| Protection intégrée | **aucune** (fils d'équilibrage seuls) | le **BMS** protège en permanence |
| Charge | exige un **chargeur RC équilibreur** | chargeur 12,6 V CC/CV + BMS — c'est le schéma prévu (D10) |
| Mécanique | sachet souple, sensible à la perforation et au gonflement | boîtiers acier, support rigide |
| Contexte | poste **fermé**, **transporté**, avec du **230 V à l'intérieur** | — |

Ce n'est pas « interdit » — c'est **le mauvais couple pour ce boîtier**. Toute la chaîne
d'alimentation décrite dans [design-alimentation.md](design-alimentation.md) (chargeur secteur
CC/CV → BMS → pack) est conçue pour du **18650 Li-ion**. Recommandation : **rester sur 18650 +
BMS**, et sortir le LiPo de la liste. Le BMS que tu as déjà choisi va dans ce sens.

### 0.3 À remplacer — inadaptés à la cible Raspberry Pi

| Article | Prix | Problème | Remplacement |
|---|---|---|---|
| 🔖 [LAFVIN écran 3,5" 480×320 **SPI**](https://www.amazon.fr/dp/B0BZV3B664/) | — | Sur un Pi, un écran **SPI** est un framebuffer poussé par le CPU : quelques images/seconde, et du CPU mangé. **Disqualifiant pour un visualiseur.** | Écran **DSI** (D9) — sortie composée par le GPU. *L'écran SPI reste utile comme console de dépannage.* |
| 🔖 [LM2596 buck 3 A](https://www.amazon.fr/dp/B0D9HSB82X/) | 6,79 € | **3 A ne suffisent pas** (le Pi 4 seul les consomme en pointe) et le LM2596 n'est pas synchrone : il dissipe beaucoup, dans un boîtier fermé. | Buck **synchrone 5 V / 5 A** |
| 🔖 [Raspberry Pi 3 Model A+](https://www.amazon.fr/dp/B07KKBCXLY/) | 41,50 € | **512 Mo de RAM**, GPU faible, un seul port USB. Trop juste pour le visualiseur et la couche applicative. | **Raspberry Pi 4, 4 Go** |
| 🔖 [SS-5GL ×5](https://www.amazon.fr/dp/B07D2D4PDK/) | 9,45 € **+ 69,90 € de port** | Le composant est bon, **le port est aberrant**. | Même référence chez un autre vendeur, ou micro-switch à levier équivalent |

### 0.4 À garder tel quel

| Article | Prix | Note |
|---|---|---|
| 🔖 [PCM5102 DAC I²S (Youmile)](https://www.amazon.fr/dp/B09NXKPZ8N/) | 8,59 € | ✅ Toujours au cœur de la chaîne audio (D5). |
| 🔖 [TPA3110 ampli stéréo](https://www.amazon.fr/dp/B09F9ZCVDD/) | 13,11 € | ⏸ Bon candidat, mais **bloqué par D8** — mesurer les HP d'abord. |
| 🔖 [BMS 3S 10 A ×2 (DollaTek)](https://www.amazon.fr/dp/B099DC44B2/) | 5,99 € | ✅ Cohérent. ⚠️ Malgré son titre, **c'est une carte de protection, pas un chargeur**. Vérifier common port. |
| 🔖 [Potentiomètre 10 kΩ linéaire](https://www.amazon.fr/dp/B01N63IMPK/) | 1,80 € (+3 € port) | ✅ Valeur juste (D3). Vérifier que l'axe convient au mécanisme (Phase 0). |
| 🔖 [Câble 18 AWG rouge/noir 5 m](https://www.amazon.fr/dp/B0BCG93BM9/) | 9,99 € | ✅ Pour le **basse tension** uniquement. Pas pour le 230 V. |
| 🔖 [Fusibles + porte-fusibles auto](https://www.amazon.fr/dp/B0DBPQBGBQ/) | 9,99 € | ✅ **Côté batterie uniquement** (§0.2). |
| 🔖 [Ferrites clipsables ×40](https://www.amazon.fr/dp/B0CXPN7ZKB/) | — | ✅ À garder en réserve — utiles seulement si un parasite apparaît en Phase 9. |

---

## 1. Ordre d'achat

| Vague | Quoi | Quand |
|---|---|---|
| **1** | Outillage (§7) — **déjà entièrement listé et non bloqué** | **Tout de suite.** |
| **2** | Pi 4 + carte + DAC + ampli d'essai | Phase 1. |
| **3** | ADS1115, potentiomètre, micro-switchs, accouplement | Phases 3–4, après Phase 0. |
| **4** | Écran DSI, ampli définitif | Après D9 et D8 (donc après Phase 0). |
| **5** | Batterie, BMS, chargeur, buck, passifs, fusible secteur | Phase 7, **après avoir mesuré la consommation**. |

---

## 2. Cœur

| Article | Sourcing | Prix | Débloqué par |
|---|---|---|---|
| **Raspberry Pi 4, 4 Go** | `Raspberry Pi 4 Model B 4GB` | ~60–80 € | — |
| Carte microSD A2 32–64 Go | `microSD A2 U3 64GB` | ~12–18 € | — |
| Alimentation officielle 5,1 V / 3 A | `alimentation officielle Raspberry Pi 4 USB-C` | ~10–12 € | — |
| Dissipateur / ventilation | `dissipateur Raspberry Pi 4` | ~8–12 € | — |

> ⚠️ Le Pi sera **enfermé dans un boîtier fermé** : la dissipation se prévoit dès le premier
> achat, pas en Phase 9.

---

## 3. Audio

| Article | Sourcing | Prix | Débloqué par |
|---|---|---|---|
| **PCM5102 DAC I²S** | 🔖 [lien](https://www.amazon.fr/dp/B09NXKPZ8N/) | 8,59 € | — |
| **Ampli classe D** TPA3110 ou TPA3116D2 | 🔖 [TPA3110](https://www.amazon.fr/dp/B09F9ZCVDD/) | 13,11 € | **D8** — mesure des HP |
| Câble audio blindé (DAC → ampli) | `câble audio blindé 2 conducteurs` | ~6–10 € | — |
| Module récepteur Bluetooth autonome | `module récepteur Bluetooth 5 audio ligne` | ~5–10 € | **D15** |
| Sélecteur d'entrée audio | `module relais commutation audio stéréo` | ~5–10 € | **D15** |
| Ferrites clipsables | 🔖 [lien](https://www.amazon.fr/dp/B0CXPN7ZKB/) | — | *seulement si EMI en Phase 9* |

---

## 4. Interface

| Article | Sourcing | Prix | Débloqué par |
|---|---|---|---|
| **ADS1115** (ADC I²C 16 bits) | `ADS1115 module I2C 16 bit` | ~6–10 € | — |
| **Potentiomètre 10 kΩ linéaire** | 🔖 [lien](https://www.amazon.fr/dp/B01N63IMPK/) | 1,80 € | — |
| Accouplement molette (O-ring, poulie, pièce 3D) | à définir | — | **Phase 0** |
| **Micro-switchs à levier ×5** | `micro switch levier SPDT SS-5GL` — *éviter le vendeur à 69,90 € de port* | ~8–12 € | **Phase 0** (nombre et type de touches) |
| **Écran DSI** | `écran DSI Raspberry Pi <taille>` — **taille inconnue tant que la Phase 0 n'est pas faite** | ~35–70 € | **D9** |
| Nappe DSI | selon écran | — | **D9** |
| Connecteur USB-A de panneau + rallonge | `USB A panneau montage rallonge` | ~8–12 € | — |
| Clavier USB compact | — | ~15–25 € | — |
| *(optionnel)* Écran SPI 3,5" comme console de dépannage | 🔖 [LAFVIN](https://www.amazon.fr/dp/B0BZV3B664/) | — | *pas l'écran du poste* |

---

## 5. Batterie et alimentation

**Rien de cette section ne s'achète avant la consommation mesurée (Phase 1) et D10/D11/D15.**

| Article | Sourcing | Prix | Débloqué par |
|---|---|---|---|
| **18650 ×3**, même référence et même lot | `18650 Li-ion 3500mAh <marque connue>` | ~10–15 €/cellule | **D11** |
| Support / assemblage 3S | `support 18650 3S` | ~5–10 € | Phase 0 (place dispo) |
| **BMS 3S 10–15 A** | 🔖 [DollaTek ×2](https://www.amazon.fr/dp/B099DC44B2/) | 5,99 € | *vérifier common port* |
| **Chargeur AC → 12,6 V CC/CV 3S**, classe II | `chargeur 12.6V 2A Li-ion 3S` (pistes : TalentCell, E-Shark) | ~20–35 € | **D10** |
| **Buck synchrone 5 V / 5 A** | `convertisseur buck 5V 5A synchrone` — ⚠️ **pas le LM2596 3 A** | ~10–15 € | — |
| **Porte-fusible + fusible 5×20 mm SECTEUR** | `porte fusible 5x20 230V châssis` | ~5–10 € | ⚠️ §0.2 |
| Porte-fusible + fusibles **côté batterie** | 🔖 [JOREST](https://www.amazon.fr/dp/B0DBPQBGBQ/) | 9,99 € | — |
| **Interrupteur principal** | selon courant — ⚠️ doit *demander* l'arrêt, pas couper sec | ~5–10 € | **D15** |
| Câble basse tension 18 AWG | 🔖 [THUN-CT](https://www.amazon.fr/dp/B0BCG93BM9/) | 9,99 € | — |
| Câble **secteur** isolé + gaine | *pas d'Amazon au hasard : matériel homologué* | — | ⚠️ |

### Passifs

| Article | Sourcing | Prix |
|---|---|---|
| 1000 µF / 25 V électrolytique | `condensateur 1000uF 25V` | ~5 € le lot |
| 220 µF / 10 V | *(souvent dans un kit)* | — |
| 100 nF céramique ×N | `kit condensateurs céramique 100nF` | ~8 € le kit |
| Résistances (pont diviseur **recalculé**, filtre RC, pull-up I²C) | `kit résistances 1/4W assortiment` | ~10 € |

> ⚠️ Le pont diviseur **220 k / 100 k dépasse la plage d'entrée** à pleine charge :
> à recalculer avant achat ([design-alimentation.md](design-alimentation.md) §7).

---

## 6. Montage

| Article | Sourcing | Prix |
|---|---|---|
| Perfboard | `plaque perfboard 2.54mm lot` | ~10 € |
| Entretoises M2/M3 + visserie | `kit entretoises laiton M2 M3` | ~12 € |
| Gaines thermorétractables | `kit gaine thermo assortiment` | ~10 € |
| Serre-câbles | — | ~5 € |
| Fil HP | `câble haut-parleur 2×1.5mm` | ~8 € |
| Connecteurs débrochables (JST/Dupont) | `kit connecteurs JST XH` | ~12 € |
| **Pièces imprimées 3D** : platine de reprise du clavier cassette, support d'écran, berceau batterie, accouplement molette | à concevoir | — |

---

## 7. Atelier — **déjà entièrement listé, non bloqué, à acheter en premier**

| Article | Lien | Prix |
|---|---|---|
| Fer à souder 110 W réglable + support + pannes | 🔖 [Zhufas](https://www.amazon.fr/dp/B0DS8PD27N/) | *prix non relevé* |
| Étain 0,7 mm Sn60Pb40 avec flux | 🔖 [NAJDER](https://www.amazon.fr/dp/B0CGXPKZ8L/) | *prix non relevé* |
| **Multimètre** | 🔖 [KAIWEETS](https://www.amazon.fr/dp/B08CX9W7G3/) | 16,99 € |
| **Alimentation de laboratoire 30 V / 5 A** | 🔖 [RUZIZAO](https://www.amazon.fr/dp/B0C6K7FC1M/) | 43,99 € |
| Breadboard 1660 points | 🔖 [ARCELI](https://www.amazon.fr/dp/B07MY24K28/) | 14,99 € |
| Jumpers M-M 560 pcs | 🔖 [QIMEI-SHOP](https://www.amazon.fr/dp/B08PF2W1RF/) | 9,99 € |
| Câbles Dupont 3-en-1 120 pcs | 🔖 [ELEGOO](https://www.amazon.fr/dp/B01JD5WCG2/) | 8,99 € |
| Pince coupante | 🔖 [KAIWEETS KWS-112](https://www.amazon.fr/dp/B0BYDJ7W5Q/) | 11,99 € |
| Tresse à dessouder | 🔖 [TOWOT](https://www.amazon.fr/dp/B09XGY9M5H/) | 4,99 € |
| Troisième main + loupe | 🔖 [SUNXIZ](https://www.amazon.fr/dp/B0CX42KX4Q/) | 18,99 € |
| **Manquant : pince à dénuder** | `pince à dénuder automatique` | ~15 € |
| **Manquant : tournevis de précision** | `kit tournevis précision électronique` | ~15 € |
| **Manquant : flux séparé** | `flux à souder seringue no-clean` | ~8 € |

**Sous-total des lignes chiffrées : 130,92 €.** Avec le fer, l'étain et les trois manquants :
**~195–220 €** (détail §8). C'est le seul achat qui n'attend rien.

---

## 8. Totaux

> **Comment lire ces chiffres.** Les montants **fermes** viennent de la liste Amazon existante,
> relevés entre août et septembre 2025 — ils ont presque un an. Les **fourchettes** sont des
> estimations de marché pour des lignes sans référence choisie. Rien ici n'est un devis :
> c'est un ordre de grandeur pour décider quoi acheter quand. Cadrage : le budget est
> **indéfini et ne doit pas être une limitation** (outillage compris) — ces totaux servent à
> planifier les vagues d'achat, pas à arbitrer les choix techniques.

### 8.1 Ce qui est déjà chiffré fermement

| Poste | Montant |
|---|---|
| Outillage (10 lignes 🔖 du §7) | 130,92 € |
| PCM5102 | 8,59 € |
| TPA3110 | 13,11 € |
| BMS 3S ×2 | 5,99 € |
| Potentiomètre 10 kΩ | 1,80 € |
| Câble 18 AWG 5 m | 9,99 € |
| Fusibles + porte-fusibles batterie | 9,99 € |
| **Total des lignes fermes** | **180,39 €** |

*(Fer à souder, étain et ferrites sont dans la liste mais sans prix relevé — estimés ci-dessous.)*

### 8.2 Budget par vague

| Vague | Contenu | Estimation |
|---|---|---|
| **1 — Outillage** | Les 10 lignes chiffrées + fer + étain + pince à dénuder, tournevis de précision, flux | **195 – 220 €** |
| **2 — Cœur et audio** | Pi 4 (4 Go) + microSD + alim + dissipateur + PCM5102 + TPA3110 + câble blindé | **118 – 154 €** |
| **3 — Interface** | ADS1115, potentiomètre, micro-switchs, accouplement, USB de panneau, clavier | **39 – 76 €** |
| **4 — Écran** | Dalle DSI + nappe | **35 – 80 €** |
| **5 — Alimentation** | 3× 18650, support, BMS, chargeur CC/CV, buck 5 A, fusibles (secteur **et** batterie), interrupteur, câblage, passifs | **129 – 196 €** |
| **6 — Montage** | Perfboard, entretoises, gaines, serre-câbles, fil HP, connecteurs, pièces imprimées 3D | **55 – 100 €** |

### 8.3 Total

| | Bas | Haut |
|---|---:|---:|
| **Matériel** (vagues 2 à 6) | **376 €** | **606 €** |
| **Outillage** (vague 1) | **195 €** | **220 €** |
| **TOTAL PROJET** | **≈ 570 €** | **≈ 825 €** |

**Retenir : ~600 à 800 €**, dont **~200 € d'outillage à sortir en premier** et le reste étalé
sur les phases 1 à 8, c'est-à-dire sur plusieurs mois.

> **Correction.** Une estimation antérieure de cette note annonçait « ~305–455 € de matériel ».
> Elle était incomplète : elle omettait le montage, le clavier, les câbles, une partie des
> passifs et le fusible secteur. **Le chiffre à retenir est celui du tableau ci-dessus.**

### 8.4 Ce que l'audit du §0 a évité

| Ligne écartée | Montant | Nature |
|---|---:|---|
| SS-5GL chez ce vendeur (**69,90 € de port** pour 9,45 € d'article) | 79,35 € | **gaspillage pur** — même composant ailleurs |
| Pack LiPo RC Zeee | 57,99 € | remplacé par 18650 + support (~40–55 €) : coût voisin, **sécurité sans commune mesure** |
| ESP32 Freenove | 12,95 € | **inutile** depuis le pivot |
| Headers DIP 1,27 mm (+ port) | 12,15 € | **mauvais pas** (le standard est 2,54 mm) |
| Connecteurs USB-C vers DIP | 6,99 € | reliquat de l'alimentation USB-C abandonnée |
| LM2596 3 A | 6,79 € | **sous-dimensionné** pour un Pi 4 |
| Raspberry Pi 3 A+ | 41,50 € | remplacé par un Pi 4 (plus cher, mais le 3 A+ ne tenait pas la charge) |
| Module USB Host Shield | *non relevé* | **inutile** (USB natif) |

**Achats inutiles évités : ~118 €.** Les deux autres lignes (LiPo, Pi 3 A+) ne sont pas des
économies mais des **substitutions** — l'une pour la sécurité, l'autre pour la capacité.

### 8.5 Ce que ce total ne contient pas

- **Le poste lui-même** — déjà possédé, en état de marche.
- **Les haut-parleurs, la molette, les touches, la prise C7** — récupérés sur le poste.
- **Le serveur AzuraCast** — machine existante
  ([design-serveur-azuracast.md](design-serveur-azuracast.md)).
- **L'impression 3D** — comptée en fourchette haute de la vague 6 si elle est sous-traitée ;
  nulle si tu as accès à une imprimante.
- **La casse et les rechanges.** Sur un premier projet d'électronique, prévoir mentalement
  **10 à 15 %** de plus : un module grillé, une dalle qui ne rentre pas, un composant commandé
  deux fois. Ce n'est pas du pessimisme, c'est le coût normal de l'apprentissage.
- **Ce qui dépend encore de décisions ouvertes** : un module Bluetooth autonome + sélecteur
  d'entrée (~15 €) si D15 va vers l'arrêt complet ; un ampli TPA3116 au lieu du TPA3110 si D8
  le demande.

---

## 9. Rappels

1. **Ne rien acheter dont la ligne « Débloqué par » n'est pas levée.**
2. **L'outillage s'achète en premier** — il est déjà listé et rien ne le bloque.
3. **L'ampli** s'achète après la mesure des haut-parleurs.
4. **L'écran** s'achète après la mesure de la profondeur derrière la façade.
5. **Les cellules** s'achètent en dernier, avec la consommation mesurée en main.
6. ⚠️ **Jamais de fusible automobile sur le 230 V** (§0.2).
7. ⚠️ **Pas de pack LiPo RC** dans un boîtier fermé et transporté (§0.2).
8. **Aucun lien de cette note n'est inventé** : soit il vient de la liste existante, soit c'est
   un terme de recherche à valider.
