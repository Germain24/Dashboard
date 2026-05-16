import os
import json
import requests
import base64
import random
from datetime import datetime
import streamlit as st

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HABITS_DIR = os.path.join(BASE_DIR, 'habits')

# ─────────────────────────────────────────────
# SLOTS — 12 emplacements de tenue
# ─────────────────────────────────────────────
SLOTS = [
    {"id": "Manteau", "emoji": "🧥", "categories": ["Manteau"], "need": "METEO", "trigger": "cold_or_rain"},
    {"id": "Veste", "emoji": "🧥", "categories": ["Veste"], "need": "METEO", "trigger": "cool"},
    {"id": "Haut", "emoji": "👕", "categories": ["Haut", "T-shirt", "Chemise", "Pull", "Shirt"], "need": "ALWAYS"},
    {"id": "Pantalon", "emoji": "👖", "categories": ["Pantalon", "Short", "Jean"], "need": "ALWAYS"},
    {"id": "Chaussures", "emoji": "👟", "categories": ["Chaussures", "Bottes", "Sneakers"], "need": "ALWAYS"},
    {"id": "Echarpe", "emoji": "🧣", "categories": ["Accessoire Cou"], "need": "METEO", "trigger": "very_cold"},
    {"id": "Casquette", "emoji": "🧢", "categories": ["Tête"], "need": "OPTIONAL"},
    {"id": "Lunettes", "emoji": "🕶️", "categories": ["Yeux"], "need": "OPTIONAL"},
    {"id": "Bijoux 1", "emoji": "💍", "categories": ["Bijoux"], "need": "OPTIONAL"},
    {"id": "Bijoux 2", "emoji": "💍", "categories": ["Bijoux"], "need": "OPTIONAL"},
    {"id": "Montre", "emoji": "⌚", "categories": ["Poignet"], "need": "OPTIONAL"},
    {"id": "Pendentif", "emoji": "📿", "categories": ["Cou"], "need": "OPTIONAL"},
]

EMO_CAT = {
    "Manteau": "🧥", "Veste": "🧥", "Haut": "👕", "T-shirt": "👕", "Chemise": "👔", "Pull": "🧶",
    "Pantalon": "👖", "Short": "🩳", "Jean": "👖", "Chaussures": "👟", "Bottes": "🥾", "Sneakers": "👟",
    "Accessoire Cou": "🧣", "Tête": "🧢", "Yeux": "🕶️", "Bijoux": "💍", "Poignet": "⌚", "Cou": "📿"
}

MATIERE_THERMIQUE = {
    "Laine": 1.8,
    "Cachemire": 2.0,
    "Duvet": 2.5,
    "Polaire": 1.5,
    "Coton": 1.0,
    "Denim": 1.1,
    "Synthétique": 1.2,
    "Cuir": 1.3,
    "Soie": 1.1,
    "Lin": 0.8
}

couleurs_top = [
    "Bleu Marine",  # La base absolue (Old Money)
    "Gris Anthracite",  # Parfait pour le layering et la musculation
    "Blanc Pur",  # Plus éclatant que le blanc cassé sur un teint froid
    "Vert Sapin",  # L'alternative noble et froide au kaki
    "Bordeaux",  # Apporte de la profondeur sans jaunir le teint
    "Bleu Cobalt",  # Une couleur "power" pour le streetwear
    "Noir"  # Un classique du minimalisme japonais
]

couleurs_a_eviter = [
    "Olive Jauni",  # Trop terreux (comme le manteau de l'image)
    "Jaune Moutarde",  # Ennemi n°1 des sous-tons froids
    "Orange / Rouille",  # Trop chaud, jure avec la peau rosée/bleutée
    "Beige Camel",  # Risque d'effacer le visage (privilégier le Gris Perle)
    "Marron Chocolat",  # Souvent trop riche en jaune/rouge chaud
    "Saumon / Pêche"  # Trop de pigments orangés
]

MATCHING_COLORS = {
    "Marron": ["Bleu ciel", "Terracotta", "Ocre", "Beige", "Camel"],
    "Khaki": ["Bordeaux", "Prune", "Moutarde", "Olive", "Vert sauge", "Vert pâle"],
    "Bleu marine": ["Orange cuivré", "Brique", "Vert sapin", "Violet", "Bleu ciel", "Bleu gris"],
    "Vert émeraude": ["Rouge cerise", "Bordeaux", "Bleu marine", "Bleu canard", "Gris anthracite", "Noir"],
    "Gris anthracite": ["Jaune moutarde", "Ocre", "Bleu marine", "Gris perle", "Blanc", "Rose poudré"],
    "Beige sable": ["Bleu marine", "Bleu indigo", "Marron", "Khaki", "Ocre", "Blanc", "Gris clair"],
    "Noir anthracite": ["Jaune moutarde", "Orange brûlé", "Bleu marine", "Gris graphite", "Blanc cassé", "Beige sable"],
    "Bordeaux": ["Vert émeraude", "Khaki", "Bleu marine", "Violet", "Gris anthracite", "Beige sable"],
    "Bleu ciel": ["Marron", "Bleu marine", "Terracotta", "Gris anthracite", "Beige sable", "Bordeaux", "Blanc"],
    "Beige clair": ["Noir", "Noir anthracite", "Bleu marine", "Marron", "Gris anthracite", "Bordeaux", "Bleu ciel",
                    "Blanc"],
    "Or": ["Bleu marine", "Vert émeraude", "Marron", "Khaki", "Bordeaux", "Noir anthracite", "Beige sable",
           "Beige clair"]
}

NEUTRES = ["Noir", "Blanc", "Bleu marine", "Gris anthracite", "Beige sable", "Noir anthracite", "Bleu ciel"]
SECONDAIRES = ["Marron", "Khaki", "Vert émeraude", "Bordeaux"]
ACCENTS = ["Or"]


def get_color_category(color):
    if not color: return "Accent"
    c_lower = color.lower()
    if any(n.lower() == c_lower for n in NEUTRES): return "Neutre"
    if any(s.lower() == c_lower for s in SECONDAIRES): return "Secondaire"
    if any(a.lower() == c_lower for a in ACCENTS): return "Accent"
    return "Accent"


# ─────────────────────────────────────────────
# LOGIQUE MÉTIER
# ─────────────────────────────────────────────

def load_wardrobe():
    path = os.path.join(HABITS_DIR, 'vetements.json')
    if not os.path.exists(path):
        return []
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_wardrobe(data):
    path = os.path.join(HABITS_DIR, 'vetements.json')
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)


def load_history():
    path = os.path.join(HABITS_DIR, 'tenues_history.json')
    if not os.path.exists(path):
        return []
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_history(tenue):
    path = os.path.join(HABITS_DIR, 'tenues_history.json')
    hist = load_history()
    hist.append({"date": datetime.now().strftime("%Y-%m-%d %H:%M"),
                 "tenue": {k: (v['nom'] if v else None) for k, v in tenue.items()}})
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(hist[-50:], f, indent=4, ensure_ascii=False)


def proprete_pct(item):
    p = item.get('portes', 0)
    ep = item.get('etat_propre', 60)
    return max(0, 100 - (p % ep) * (100 / ep))


def vie_pct(item):
    p = item.get('portes', 0)
    ev = item.get('etat_vie', 500)
    return max(0, 100 - (p / ev) * 100)


def needs_wash(item):
    p = item.get('portes', 0)
    ep = item.get('etat_propre', 60)
    return (p % ep == 0) and p > 0


def is_worn_out(item):
    return vie_pct(item) <= 0


def ports_avant_lavage(item):
    p = item.get('portes', 0)
    ep = item.get('etat_propre', 60)
    return ep - (p % ep) if not needs_wash(item) else 0


def badge_html(item):
    p = proprete_pct(item)
    if needs_wash(item): return "<span style='color:#ef4444;font-size:.6em;'>🧺 SALE</span>"
    if p >= 70: return "<span style='color:#4ade80;font-size:.6em;'>✨ PROPRE</span>"
    if p >= 40: return "<span style='color:#f59e0b;font-size:.6em;'>⚠ OK</span>"
    return "<span style='color:#ef4444;font-size:.6em;'>🧺 SALE</span>"


def disponible(item):
    return not needs_wash(item) and not is_worn_out(item)


def colors_compat(c1, c2):
    if not c1 or not c2: return True
    cat1 = get_color_category(c1)
    cat2 = get_color_category(c2)
    # Neutrals go with everything
    if cat1 == "Neutre" or cat2 == "Neutre": return True
    # Explicit matches
    if c2 in MATCHING_COLORS.get(c1, []) or c1 in MATCHING_COLORS.get(c2, []): return True
    # Same category is usually safe
    if cat1 == cat2: return True
    return False


def style_score_func(items):
    if not items: return 0

    # 1. Style Consistency (Multi-style support)
    # Each item can have a single style (string) or multiple styles (list)
    item_styles = []
    for i in items:
        if i is None: continue
        s = i.get('style', '')
        if isinstance(s, list):
            item_styles.append(set(s))
        elif s:
            item_styles.append({s})
        else:
            item_styles.append(set())

    # Find the style that appears most often across all items
    all_possible_styles = set()
    for s_set in item_styles:
        all_possible_styles.update(s_set)

    max_style_score = 0
    if not all_possible_styles:
        max_style_score = 50  # Neutral if no styles defined
    else:
        for style in all_possible_styles:
            matches = sum(1 for s_set in item_styles if style in s_set)
            # Score is based on the percentage of items sharing this style
            current_score = (matches / len(items)) * 100
            if current_score > max_style_score:
                max_style_score = current_score

    style_consist = max_style_score

    # 2. Color Matching (Points for specific pairings)
    valid_items = [i for i in items if i is not None]
    colors = [i.get('couleur', '') for i in valid_items if i.get('couleur')]
    match_score = 100
    if len(colors) >= 2:
        pairs = 0
        matches = 0
        for i in range(len(colors)):
            for j in range(i + 1, len(colors)):
                c1, c2 = colors[i], colors[j]
                pairs += 1
                if c2 in MATCHING_COLORS.get(c1, []) or c1 in MATCHING_COLORS.get(c2, []):
                    matches += 1.0
                elif get_color_category(c1) == "Neutre" or get_color_category(c2) == "Neutre":
                    matches += 0.7
                elif get_color_category(c1) == get_color_category(c2):
                    matches += 0.5
        match_score = (matches / pairs) * 100 if pairs > 0 else 100

    # 3. Color Ratio (60% Neutre, 30% Secondaire, 10% Accent)
    counts = {"Neutre": 0, "Secondaire": 0, "Accent": 0}
    for c in colors:
        counts[get_color_category(c)] += 1

    total = len(colors) if colors else 1
    ratios = {k: v / total for k, v in counts.items()}
    # Calculate distance to ideal 60/30/10
    dist = abs(ratios["Neutre"] - 0.6) + abs(ratios["Secondaire"] - 0.3) + abs(ratios["Accent"] - 0.1)
    # Max distance is roughly 1.2 (e.g. 1/0/0 vs 0.6/0.3/0.1 -> 0.4+0.3+0.1 = 0.8; 0/0/1 vs 0.6/0.3/0.1 -> 0.6+0.3+0.9 = 1.8? No)
    # Max dist is 2 * (1 - min_target) = 2 * 0.9 = 1.8. Let's use 1.5 as a reasonable scale.
    ratio_score = max(0, 100 * (1 - dist / 1.5))

    # Final weighted score
    return (style_consist * 0.3) + (match_score * 0.4) + (ratio_score * 0.3)


def thermal_score(item):
    if not item: return 0.0
    if 'chaleur' in item:
        return item['chaleur']

    # Catégories purement esthétiques (ne tiennent pas chaud)
    NEUTRAL_CATS = ["Yeux", "Bijoux", "Poignet", "Cou"]
    if item.get('categorie') in NEUTRAL_CATS:
        return 0.0

    # Si aucune borne de température n'est définie, l'objet est considéré comme neutre thermiquement
    if 'temp_min' not in item and 'temp_max' not in item:
        return 0.0

    # Heuristique de base
    base_score = max(0, 25 - item.get('temp_min', 20)) / 2.0

    # Pondération par matière (Layering Bonus logic is in calculate_thermal_gap)
    matiere = item.get('matiere', 'Coton')
    coef = 1.0
    for key, val in MATIERE_THERMIQUE.items():
        if key.lower() in matiere.lower():
            coef = val
            break

    return base_score * coef


def score_rotation(item, history):
    # Dirtiness score: how many times it was worn since last wash
    # Higher is "dirtier" (closer to needing a wash)
    return item.get('portes', 0) % item.get('etat_propre', 60)


def get_weather():
    # Coordonnées de Montréal (Latitude, Longitude)
    lat = 45.5017
    lon = -73.5673

    # URL de l'API Open-Meteo pour obtenir les données actuelles et quotidiennes
    url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=temperature_2m,relative_humidity_2m,apparent_temperature,precipitation,wind_speed_10m&daily=temperature_2m_max,temperature_2m_min&timezone=America%2FNew_York"

    try:
        response = requests.get(url)
        response.raise_for_status()  # Lève une erreur si la requête échoue
        data = response.json()

        current = data['current']
        daily = data['daily']

        # Formatage des données pour correspondre à votre structure initiale
        return {
            "temp": current['temperature_2m'],
            "temp_min": daily['temperature_2m_min'][0],
            "temp_max": daily['temperature_2m_max'][0],
            "feels": current['apparent_temperature'],
            "humidity": current['relative_humidity_2m'],
            "wind": current['wind_speed_10m'],
            "precip": current['precipitation'],
            "desc": "Données en direct (Open-Meteo)"
        }
    except requests.exceptions.RequestException as e:
        return {"error": f"Impossible de récupérer la météo : {e}"}


def get_weather_info(wx):
    if not wx or "error" in wx:
        # Fallback values if API fails
        return 15.0, False, False, "⚠️"

    feels = wx.get("feels", 15.0)
    precip = wx.get("precip", 0.0)
    desc = wx.get("desc", "").lower()

    pluie = precip > 0.5 or any(w in desc for w in ["rain", "pluie", "drizzle", "shower"])
    snow = any(w in desc for w in ["snow", "neige", "blizzard"])
    icon = "🌨️" if snow else "🌧️" if pluie else "☀️" if any(
        w in desc for w in ["sunny", "clear"]) else "🌤️"
    return feels, pluie, snow, icon


def calculate_thermal_gap(tenue, feels, use_body):
    target_thermal = 50.0 - (feels * 1.5)
    worn_items = [v for v in tenue.values() if v is not None]

    # Base thermal sum
    total_thermal = sum(thermal_score(i) for i in worn_items)

    # Layering bonus: air trapped between layers on the torso
    # Layers: Haut, Veste, Manteau
    torso_layers = 0
    if tenue.get("Haut"): torso_layers += 1
    if tenue.get("Veste"): torso_layers += 1
    if tenue.get("Manteau"): torso_layers += 1

    if torso_layers > 1:
        # Bonus of 10% per additional layer (physics of trapped air)
        total_thermal *= (1 + (torso_layers - 1) * 0.1)

    if use_body:
        total_thermal += 1.5
    gap = target_thermal - total_thermal
    return total_thermal, target_thermal, gap


def suggest_outfit(wardrobe, t_min, t_max, wind, rain):
    import itertools

    res = {s["id"]: None for s in SLOTS}
    available = [i for i in wardrobe if disponible(i)]
    if not available:
        return res

    feels = (t_min + t_max) / 2
    # Cible thermique standard de l'app
    target_thermal = 50.0 - (feels * 1.5)

    # 1. Bloquer l'élément le plus sale portable
    # score_rotation renvoie (portes % etat_propre)
    dirtiest_item = max(available, key=lambda x: score_rotation(x, []), default=None)
    if not dirtiest_item:
        return res

    # Identifier le slot de l'élément bloqué
    blocked_slot_id = None
    for slot in SLOTS:
        if dirtiest_item.get('categorie') in slot["categories"]:
            blocked_slot_id = slot["id"]
            break

    # 2. Déterminer les slots actifs pour la journée
    active_slots = []
    for slot in SLOTS:
        if slot["need"] == "ALWAYS":
            active_slots.append(slot)
        elif slot["need"] == "METEO":
            if slot["id"] == "Manteau" and (feels < 18 or rain):
                active_slots.append(slot)
            elif slot["id"] == "Veste" and feels < 15:
                active_slots.append(slot)
            elif slot["id"] == "Echarpe" and feels < 10:
                active_slots.append(slot)

    # Si l'élément bloqué est un accessoire non-météo, on l'ajoute aux slots à traiter
    if blocked_slot_id and not any(s["id"] == blocked_slot_id for s in active_slots):
        for s in SLOTS:
            if s["id"] == blocked_slot_id:
                active_slots.append(s)
                break

    # 3. Préparer les candidats par slot
    slot_candidates = {}
    for slot in active_slots:
        sid = slot["id"]
        if sid == blocked_slot_id:
            slot_candidates[sid] = [dirtiest_item]
        else:
            cats = slot["categories"]
            options = [i for i in available if i.get('categorie') in cats]
            if not options: continue

            # Pour la veste, on autorise le "None" même en slot actif
            # pour permettre à l'algo de choisir entre Manteau seul ou Manteau + Veste
            if sid == "Veste":
                slot_candidates[sid] = [None] + options[:15]
            else:
                slot_candidates[sid] = options[:15]

    if not slot_candidates:
        return res

    # 4. Générer toutes les combinaisons
    keys = list(slot_candidates.keys())
    values = list(slot_candidates.values())
    combinations = [dict(zip(keys, combo)) for combo in itertools.product(*values)]

    valid_combos = []
    for outfit in combinations:
        # FILTRE 0 : Unicité des items (ex: ne pas porter le même bijou dans Bijoux 1 et Bijoux 2)
        worn_ids = [i['id'] for i in outfit.values() if i is not None]
        if len(worn_ids) != len(set(worn_ids)):
            continue

        # Calcul de la température totale de la tenue (avec layering bonus)
        total_thermal, _, _ = calculate_thermal_gap(outfit, feels, False)

        # FILTRE 1 : Proximité avec la cible thermique (+- 4)
        if abs(total_thermal - target_thermal) <= 4.0:

            # FILTRE 2 : Différence thermique Haut / Bas (Cohérence)
            haut = outfit.get("Haut")
            bas = outfit.get("Pantalon")
            if haut and bas:
                diff = abs(thermal_score(haut) - thermal_score(bas))
                if diff > 3.5:  # Seuil de cohérence (ex: pas de gros pull avec un short)
                    continue

            # Calcul du score de style pour cette combinaison
            style = style_score_func(list(outfit.values()))
            valid_combos.append({
                "outfit": outfit,
                "style": style
            })

    # 5. Sélection de la tenue avec le meilleur score de style
    best_outfit = None
    best_use_body = False

    if valid_combos:
        valid_combos.sort(key=lambda x: x["style"], reverse=True)
        best_outfit = valid_combos[0]["outfit"]
    else:
        # Fallback : Si aucun combo ne respecte les filtres, on prend le meilleur style brut
        # parmi les combinaisons incluant l'élément bloqué
        combinations.sort(key=lambda x: style_score_func(list(x.values())), reverse=True)
        best_outfit = combinations[0]

    # 5b. Vérification automatique du body si la tenue est encore trop froide
    if best_outfit:
        total_th, target_th, gap = calculate_thermal_gap(best_outfit, feels, False)
        # Si on est en dessous de la cible thermique de plus de 1.5 points, on active le body
        if gap > 1.5:
            best_use_body = True

    if best_outfit:
        res.update(best_outfit)
        # Metadata for Dashboard
        res["__use_body"] = best_use_body
        res["__t_outfit"] = float(feels)

        # 6. Ajout des accessoires optionnels (Greedy)
        # On garde cette étape pour peaufiner le style avec ce qui reste
        current_items = [v for v in res.values() if isinstance(v, dict)]
        optional_slots = [s for s in SLOTS if s["need"] == "OPTIONAL" and s["id"] != blocked_slot_id]

        for slot in optional_slots:
            sid = slot["id"]
            cats = slot["categories"]

            # On exclut les items déjà portés dans d'autres slots (pour l'unicité)
            current_ids = [i['id'] for i in res.values() if isinstance(i, dict)]
            options = [i for i in available if i.get('categorie') in cats and i['id'] not in current_ids]

            if not options: continue

            best_accessory = None
            best_style_boost = style_score_func(current_items)

            for opt in options:
                test_items = current_items + [opt]
                new_score = style_score_func(test_items)
                if new_score > best_style_boost:
                    best_style_boost = new_score
                    best_accessory = opt

            if best_accessory:
                res[sid] = best_accessory
                current_items.append(best_accessory)

    return res

    return res


def get_purchase_recommendations(wardrobe):
    if not wardrobe:
        return [{"nom": "Haut Neutre (Blanc/Noir)", "raison": "Ta garde-robe est vide !", "potentiel": 100}]

    recs = []

    # 1. Analyse des catégories manquantes ou faibles
    cat_counts = {}
    for item in wardrobe:
        cat = item.get('categorie', 'Autre')
        cat_counts[cat] = cat_counts.get(cat, 0) + 1

    # Vérifier les catégories essentielles (basées sur SLOTS)
    essential_cats = set()
    for s in SLOTS:
        essential_cats.update(s["categories"])

    for cat in essential_cats:
        if cat_counts.get(cat, 0) == 0:
            recs.append({
                "nom": f"{cat} Basique",
                "raison": f"Tu n'as aucun article dans la catégorie '{cat}'.",
                "potentiel": 90,
                "type": "Basique"
            })
        elif cat_counts.get(cat, 0) < 2:
            recs.append({
                "nom": f"Deuxième {cat}",
                "raison": f"Tu n'as qu'un seul article dans la catégorie '{cat}'.",
                "potentiel": 60,
                "type": "Rotation"
            })

    # 2. Analyse de l'équilibre des couleurs (60/30/10)
    color_cats = {"Neutre": 0, "Secondaire": 0, "Accent": 0}
    for item in wardrobe:
        color_cats[get_color_category(item.get('couleur'))] += 1

    total = len(wardrobe)
    ratios = {k: v / total for k, v in color_cats.items()}

    if ratios["Neutre"] < 0.5:
        recs.append({
            "nom": "Haut ou Pantalon Neutre",
            "raison": "Ta garde-robe manque de couleurs neutres (Blanc, Noir, Gris, Beige) pour faciliter les associations.",
            "potentiel": 85,
            "type": "Polyvalence"
        })

    # 3. Analyse des couleurs orphelines (couleurs qui n'ont pas de match)
    all_colors = set(item.get('couleur') for item in wardrobe if item.get('couleur'))
    for color in all_colors:
        if color in MATCHING_COLORS:
            matches = MATCHING_COLORS[color]
            has_match = any(m in all_colors for m in matches)
            if not has_match:
                # Suggérer une couleur qui matche
                suggested_color = matches[0]
                recs.append({
                    "nom": f"Article {suggested_color}",
                    "raison": f"Tu as des articles '{color}' mais rien pour les accorder parfaitement.",
                    "potentiel": 75,
                    "type": "Harmonie"
                })

    # 4. Analyse des styles
    style_counts = {}
    for item in wardrobe:
        s = item.get('style', '')
        styles = s if isinstance(s, list) else [s] if s else []
        for style in styles:
            style_counts[style] = style_counts.get(style, 0) + 1

    if style_counts:
        dominant_style = max(style_counts, key=style_counts.get)
        # Si un style est dominant mais qu'il manque des pièces pour ce style
        # (Par exemple, beaucoup de hauts Gorpcore mais pas de chaussures Gorpcore)
        for slot in SLOTS:
            cats = slot["categories"]
            has_style_in_cat = any(
                (dominant_style in (i.get('style') if isinstance(i.get('style'), list) else [i.get('style')]))
                for i in wardrobe if i.get('categorie') in cats
            )
            if not has_style_in_cat:
                recs.append({
                    "nom": f"{cats[0]} {dominant_style}",
                    "raison": f"Pour compléter ton look '{dominant_style}', il te manque des articles dans la catégorie {cats[0]}.",
                    "potentiel": 70,
                    "type": "Style"
                })

    # Trier par potentiel et limiter à 5
    recs.sort(key=lambda x: x["potentiel"], reverse=True)

    # Éviter les doublons de noms
    seen = set()
    unique_recs = []
    for r in recs:
        if r["nom"] not in seen:
            unique_recs.append(r)
            seen.add(r["nom"])

    return unique_recs[:5]


def asset_path(item_id: str):
    for folder in ["habits/assets", "assets"]:
        p = os.path.join(BASE_DIR, folder, f"{item_id}.png")
        if os.path.exists(p): return p
    return None


def perso_path():
    for folder in ["habits/assets", "assets", "habits"]:
        p = os.path.join(BASE_DIR, folder, "perso.png")
        if os.path.exists(p): return p
    return None


def to_b64(path):
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()
