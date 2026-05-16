import os
import json
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from scipy.optimize import minimize

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SANTE_DIR = os.path.join(BASE_DIR, 'sante')


def load_sante():
    path = os.path.join(SANTE_DIR, 'sante.json')
    if not os.path.exists(path):
        return []
    with open(path, 'r') as f:
        return json.load(f)


def save_sante(data):
    path = os.path.join(SANTE_DIR, 'sante.json')
    with open(path, 'w') as f:
        json.dump(data, f, indent=4)


def update_sante_data(sante_data, date_str, weight=None, targets=None, consumed=None, watch_calories=None, foods=None,
                      base_targets=None):
    found = False
    for entry in sante_data:
        if entry['date'] == date_str:
            if weight is not None: entry['poids'] = weight
            if targets is not None: entry['targets'] = targets
            if base_targets is not None: entry['base_targets'] = base_targets
            if consumed is not None: entry['consumed'] = consumed
            if watch_calories is not None: entry['watch_calories'] = watch_calories
            if foods is not None: entry['foods'] = foods
            found = True
            break
    if not found:
        new_entry = {"date": date_str}
        if weight is not None: new_entry['poids'] = weight
        if targets is not None: new_entry['targets'] = targets
        if base_targets is not None: new_entry['base_targets'] = base_targets
        if consumed is not None: new_entry['consumed'] = consumed
        if watch_calories is not None: new_entry['watch_calories'] = watch_calories
        if foods is not None: new_entry['foods'] = foods
        sante_data.append(new_entry)
    save_sante(sante_data)
    return sante_data


def get_yesterday_str(date_str):
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    yesterday = dt - timedelta(days=1)
    return yesterday.strftime("%Y-%m-%d")


def calculate_daily_targets(weight, date_str, sante_data):
    # Determine if today is a sport day (Mon-Fri)
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    is_sport_day = dt.weekday() < 5

    p = weight
    maintenance = p * 32

    if is_sport_day:
        cals = (maintenance + 500) * 1.2
        proteins = p * 2.2
        lipids = p * 1.2
    else:
        cals = maintenance * 1.1
        proteins = p * 1.6
        lipids = p * 1.0

    glucides = (cals - (proteins * 4) - (lipids * 9)) / 4

    # Daily Base Targets
    base_daily = {
        "Calories": cals,
        "Protéines": proteins,
        "Lipides": lipids,
        "Glucides": glucides,
        "Fibres": 35,
        "Sodium_Max": 2000,
        "Magnésium": 400,
        "Omega3": 2.0,
        "VitA": 900,
        "VitB1": 1.2,
        "VitB2": 1.3,
        "VitB3": 16,
        "VitB5": 5,
        "VitB6": 1.3,
        "VitB9": 400,
        "VitB12": 2.4,
        "VitC": 100,
        "VitD": 15,
        "VitE": 15,
        "VitK": 120,
        "Calcium": 1000,
        "Chlorure": 2300,
        "Cuivre": 1.6,
        "Fer": 13,
        "Iode": 150,
        "Manganèse": 2.3,
        "Phosphore": 700,
        "Potassium": 4000,
        "Sélénium": 70,
        "Zinc": 11,
        "Cholesterol_Max": 300,
        "Sucres_Max": 50,
        "Prix_Max": 18.0,
        "Poids_Corps": p,
    }

    # Yesterday's gap compensation
    yesterday_str = get_yesterday_str(date_str)
    yesterday_entry = next((e for e in sante_data if e['date'] == yesterday_str), None)

    comp_targets = base_daily.copy()

    if yesterday_entry:
        y_targets = yesterday_entry.get('targets')
        y_consumed = yesterday_entry.get('consumed')

        if y_targets and y_consumed:
            # Check if yesterday's targets were weekly (transition handling)
            is_weekly = y_targets.get('Calories', 0) > 10000

            # Compensate ALL tracked nutrients
            tracking = list(base_daily.keys())
            # Skip non-nutrients
            exclude = ["Poids_Corps", "Prix_Max"]
            for k in tracking:
                if k in exclude: continue
                if k in y_targets and k in y_consumed:
                    gap = y_targets[k] - y_consumed[k]

                    if is_weekly:
                        # If transition from weekly to daily, we only take 1/7th of the gap
                        # to avoid trying to eat a whole week's worth of food today
                        gap /= 7.0

                    # Full compensation without limits
                    comp_targets[k] += gap

    return base_daily, comp_targets


def calculate_weekly_targets(weight):
    p = weight

    # Base Maintenance Calculation
    maintenance = p * 32

    # Training Day Targets (5 days/week)
    # Higher activity factor (1.2) for sport days
    t_base_cals = (maintenance + 500) * 1.2
    t_proteins = p * 2.2
    t_lipids = p * 1.2
    t_glucides = (t_base_cals - (t_proteins * 4) - (t_lipids * 9)) / 4

    # Rest Day Targets (2 days/week)
    r_base_cals = maintenance * 1.1
    r_proteins = p * 1.6
    r_lipids = p * 1.0
    r_glucides = (r_base_cals - (r_proteins * 4) - (r_lipids * 9)) / 4

    # Weekly Sum (5 Training + 2 Rest)
    num_t = 5
    num_r = 2

    weekly_cals = (t_base_cals * num_t) + (r_base_cals * num_r)
    weekly_proteins = (t_proteins * num_t) + (r_proteins * num_r)
    weekly_lipids = (t_lipids * num_t) + (r_lipids * num_r)
    weekly_glucides = (t_glucides * num_t) + (r_glucides * num_r)

    # Micronutrients (Daily * 7)
    base_micros = {
        "Fibres": 35 * 7,
        "Sodium_Max": 2000 * 7,
        "Magnésium": 400 * 7,
        "Omega3": 2.0 * 7,
        "VitA": 900 * 7,
        "VitB1": 1.2 * 7,
        "VitB2": 1.3 * 7,
        "VitB3": 16 * 7,
        "VitB5": 5 * 7,
        "VitB6": 1.3 * 7,
        "VitB9": 400 * 7,
        "VitB12": 2.4 * 7,
        "VitC": 100 * 7,
        "VitD": 15 * 7,
        "VitE": 15 * 7,
        "VitK": 120 * 7,
        "Calcium": 1000 * 7,
        "Chlorure": 2300 * 7,
        "Cuivre": 1.6 * 7,
        "Fer": 13 * 7,
        "Iode": 150 * 7,
        "Manganèse": 2.3 * 7,
        "Phosphore": 700 * 7,
        "Potassium": 4000 * 7,
        "Sélénium": 70 * 7,
        "Zinc": 11 * 7,
        "Cholesterol_Max": 300 * 7,
        "Sucres_Max": 50 * 7,
        "Prix_Max": 130.0 * 7,
        "Poids_Corps": p,
    }

    targets = {
        "Calories": weekly_cals,
        "Protéines": weekly_proteins,
        "Lipides": weekly_lipids,
        "Glucides": weekly_glucides,
        **base_micros
    }

    return targets


def optimize_nutrition(targets):
    path = os.path.join(SANTE_DIR, 'aliments.csv')
    if not os.path.exists(path):
        return None, "Fichier aliments.csv introuvable."

    try:
        # Read and transpose the CSV
        df_raw = pd.read_csv(path, sep=';', index_col=0)

        # Clean up empty columns (Unnamed)
        df_raw = df_raw.loc[:, ~df_raw.columns.str.contains('^Unnamed')]

        df = df_raw.transpose()

        # Normalize column names (handle Energie/Énergie, etc.)
        df.columns = [c.replace('Energie', 'Energie').replace('AG monoinsaturés', 'AG monoinsatures') for c in
                      df.columns]

        if 'Objectif' in df.index:
            df = df.drop('Objectif')

        # Ensure all required columns exist and are numeric
        required_cols = [
            'Prix', 'Proteines', 'Lipides', 'Glucides', 'Energie', 'Fibres',
            'AG satures', 'AG monoinsatures', 'Omega 3', 'Omega 6',
            'Glucose', 'Fructose', 'Galactose', 'Saccharose', 'Lactose',
            'Sodium', 'Magnesium', 'VitA', 'VitB1', 'VitB2', 'VitB3', 'VitB5',
            'VitB6', 'VitB9', 'VitB12', 'VitC', 'VitD', 'VitE', 'VitK',
            'Calcium', 'Chlorure', 'Cuivre', 'Fer', 'Iode', 'Manganese',
            'Phosphore', 'Potassium', 'Selenium', 'Zinc', 'Cholesterol', 'Polyols', 'MinQty'
        ]
        for col in required_cols:
            if col not in df.columns:
                df[col] = 0.0
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0.0)

        # We use minimize to find the best balance (least squares on relative errors)
        # This ensures we always find a solution and penalize both under and over shooting

        nutrient_map = {
            'Energie': targets['Calories'],
            'Proteines': targets['Protéines'],
            'Lipides': targets['Lipides'],
            'Glucides': targets['Glucides'],
            'Fibres': targets['Fibres'],
            'Magnesium': targets['Magnésium'],
            'Sodium': targets['Sodium_Max'],
            'Cholesterol': targets['Cholesterol_Max'],
            'Omega 3': targets['Omega3'],
            'VitA': targets['VitA'],
            'VitB1': targets['VitB1'],
            'VitB2': targets['VitB2'],
            'VitB3': targets['VitB3'],
            'VitB5': targets['VitB5'],
            'VitB6': targets['VitB6'],
            'VitB9': targets['VitB9'],
            'VitB12': targets['VitB12'],
            'VitC': targets['VitC'],
            'VitD': targets['VitD'],
            'VitE': targets['VitE'],
            'VitK': targets['VitK'],
            'Calcium': targets['Calcium'],
            'Fer': targets['Fer'],
            'Zinc': targets['Zinc'],
            'Potassium': targets['Potassium'],
            'Iode': targets['Iode'],
            'Selenium': targets['Sélénium'],
            'Phosphore': targets['Phosphore'],
            'TotalSugars': targets['Sucres_Max']
        }

        # Weights: prioritize macros and strictly limit "Max" nutrients
        weights = {k: 1.0 for k in nutrient_map.keys()}
        weights['Energie'] = 1000.0
        weights['Proteines'] = 1000.0
        weights['Lipides'] = 100.0
        weights['Glucides'] = 100.0
        weights['TotalSugars'] = 500.0
        weights['Sodium'] = 500.0
        weights['Cholesterol'] = 500.0

        food_names = df.index.tolist()
        num_foods = len(food_names)

        # Pre-calculate sugar content for each food (sum of all sugar types)
        sugar_cols = ['Glucose', 'Fructose', 'Galactose', 'Saccharose', 'Lactose']
        df['TotalSugars'] = df[sugar_cols].sum(axis=1)

        # Pre-calculate staple mask for objective performance
        staples = ["Riz blanc", "Avoine", "Pois chiche", "Patate", "Pates", "Quinoa", "Lentilles"]
        is_staple = np.array([any(s in name for s in staples) for name in food_names])

        max_nutrients = ['Sodium', 'Cholesterol', 'TotalSugars']

        def objective(x):
            error = 0
            for nutrient, target in nutrient_map.items():
                current = np.dot(x, df[nutrient].values)

                # If target is negative or zero, we want it to be 0 for the optimizer
                # but we keep penalizing any consumption if the target is physically impossible (negative)
                eff_target = max(0, target)

                if eff_target == 0:
                    # Penalize any consumption if we are supposed to be at 0 (debt compensation)
                    if current > 0:
                        error += weights.get(nutrient, 1.0) * (current ** 2)
                    continue

                rel_error = (current - eff_target) / eff_target
                w = weights.get(nutrient, 1.0)

                if nutrient in max_nutrients:
                    if current > target:
                        # Heavy penalty for exceeding max (asymmetric)
                        error += w * 5.0 * (rel_error ** 2)
                    else:
                        # No penalty for being under a maximum limit
                        error += 0
                else:
                    # Standard squared error for targets
                    error += w * (rel_error ** 2)

            # Penalty for total food weight > 5% of body weight (approx 3-4kg)
            total_grams = np.sum(x) * 100
            threshold_grams = targets['Poids_Corps'] * 0.05 * 1000
            if total_grams > threshold_grams:
                # Penalty proportional to the square of the excess percentage
                excess_ratio = (total_grams - threshold_grams) / threshold_grams
                error += 5000.0 * (excess_ratio ** 2)

                # Small price penalty to favor cheaper foods when nutrition is equal
            error += 0.001 * np.dot(x, df['Prix'].values)

            return error

        # Hard constraints:
        # 1. Price must be <= Prix_Max
        # 2. Calories must be >= Calories target
        # 3. Proteins must be >= Protéines target
        constraints = [
            {'type': 'ineq', 'fun': lambda x: targets['Prix_Max'] - np.dot(x, df['Prix'].values)},
            {'type': 'ineq', 'fun': lambda x: np.dot(x, df['Energie'].values) - targets['Calories']},
            {'type': 'ineq', 'fun': lambda x: np.dot(x, df['Proteines'].values) - targets['Protéines']}
        ]

        # Bounds: variety control
        # Max 400g/day per item = 4.0 units
        MAX_DAILY_UNITS = 4.0

        bounds = []
        for name in food_names:
            row = df.loc[name]
            min_val = 0.0

            # Default max is 400g/day
            max_val = MAX_DAILY_UNITS

            if 'MaxQty' in row and row['MaxQty'] > 0:
                # If MaxQty is in g, convert to units (100g)
                csv_max = row['MaxQty'] / 100.0 if row['MaxQty'] >= 1.0 else row['MaxQty']
                max_val = min(max_val, csv_max)
            elif "Supplement" in name or "Vitamine" in name:
                max_val = 0.05  # 5g max for supplements

            bounds.append((min_val, max_val))

        # Initial guess: Start with a reasonable amount of staples
        x0 = np.zeros(num_foods)
        for i, name in enumerate(food_names):
            if any(s in name for s in staples):
                x0[i] = 1.0  # 100g of each staple
            else:
                x0[i] = 0.05  # 5g for others

        # SLSQP with hard constraints
        res = minimize(objective, x0, method='SLSQP', bounds=bounds, constraints=constraints,
                       options={'ftol': 1e-8, 'maxiter': 1000})

        warning_msg = ""
        if not res.success:
            # If hard constraint fails, try to find the best possible within budget by relaxing slightly or using soft penalty as fallback
            # but for now, let's report the error as requested
            return None, f"Erreur d'optimisation : {res.message}. Impossible de respecter le budget de {targets['Prix_Max']:.2f} CAD tout en s'approchant des objectifs."

        # Final check for budget/protein/calories to set warning
        final_price = np.dot(res.x, df['Prix'].values)
        final_proteins = np.dot(res.x, df['Proteines'].values)
        final_calories = np.dot(res.x, df['Energie'].values)

        warnings = []
        if final_price > targets['Prix_Max'] * 1.01:
            warnings.append(f"Budget dépassé de {(final_price - targets['Prix_Max']):.2f} CAD")
        if final_proteins < targets['Protéines'] * 0.98:
            warnings.append(f"Protéines à {final_proteins:.0f}g/{targets['Protéines']:.0f}g")
        if final_calories < targets['Calories'] * 0.98:
            warnings.append(f"Calories à {final_calories:.0f}kcal/{targets['Calories']:.0f}kcal")

        if warnings:
            warning_msg = "Note : Budget trop serré. " + " | ".join(warnings)

        plan = []
        for i, x in enumerate(res.x):
            name = food_names[i]
            row = df.loc[name]

            # Weekly min threshold from bounds
            min_val, _ = bounds[i]

            # Only include if x is above the minimum threshold AND at least 0.01g (0.0001 units)
            # This is crucial for supplements which are needed in tiny amounts
            if x >= min_val and x >= 0.0001:
                qty_val = x * 100
                qty_str = f"{qty_val:.0f}g" if qty_val >= 1.0 else f"{qty_val:.2f}g"
                plan.append({
                    "Aliment": name,
                    "Quantité": qty_str,
                    "Calories": float(row['Energie'] * x),
                    "Protéines": float(row['Proteines'] * x),
                    "Lipides": float(row['Lipides'] * x),
                    "Glucides": float(row['Glucides'] * x),
                    "Prix": float(row['Prix'] * x)
                })

        return plan, warning_msg

    except Exception as e:
        return None, f"Erreur lors de l'optimisation : {str(e)}"


def calculate_plan_totals(plan):
    path = os.path.join(SANTE_DIR, 'aliments.csv')
    df_raw = pd.read_csv(path, sep=';', index_col=0)

    # Clean up empty columns (Unnamed)
    df_raw = df_raw.loc[:, ~df_raw.columns.str.contains('^Unnamed')]

    df = df_raw.transpose()

    # Normalize column names
    df.columns = [c.replace('Energie', 'Energie').replace('AG monoinsaturés', 'AG monoinsatures') for c in df.columns]

    totals = {}
    for item in plan:
        name = item["Aliment"]
        qty_str = item["Quantité"]
        qty = float(qty_str.replace('g', '')) / 100.0

        row = df.loc[name]
        for col in df.columns:
            val = pd.to_numeric(row[col], errors='coerce')
            if not np.isnan(val):
                # Map unaccented CSV columns to accented keys used in Dashboard
                key = col
                if col == "Energie":
                    key = "Calories"
                elif col == "Proteines":
                    key = "Protéines"
                elif col == "Magnesium":
                    key = "Magnésium"
                elif col == "Manganese":
                    key = "Manganèse"
                elif col == "Selenium":
                    key = "Sélénium"
                elif col == "Cholesterol":
                    key = "Cholesterol_Max"
                elif col == "Sodium":
                    key = "Sodium_Max"
                elif col == "AG satures":
                    key = "AG saturés"
                elif col == "AG monoinsatures":
                    key = "AG monoinsaturés"

                totals[key] = totals.get(key, 0) + (val * qty)

        # Calculate total sugars (Sucres)
        sugars = ['Glucose', 'Fructose', 'Galactose', 'Saccharose', 'Lactose']
        total_sugars = 0
        for s in sugars:
            if s in row:
                total_sugars += (pd.to_numeric(row[s], errors='coerce') or 0)
        totals['Sucres_Max'] = totals.get('Sucres_Max', 0) + (total_sugars * qty)

    return totals
