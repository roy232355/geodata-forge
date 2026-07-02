# -*- coding: utf-8 -*-
"""Deterministic attribute generator with domain-aware correlated generation for GeoData Forge."""
import datetime
import random


# =============================================================================
# Domain Correlation Lookup Tables
# =============================================================================

SPECIES_PROFILES = {
    "Pinus sylvestris":   {"height_m": (15, 35), "dbh_cm": (20, 80),  "age_years": (20, 200)},
    "Quercus robur":      {"height_m": (20, 40), "dbh_cm": (30, 120), "age_years": (50, 500)},
    "Betula pendula":     {"height_m": (10, 25), "dbh_cm": (10, 40),  "age_years": (10, 80)},
    "Picea abies":        {"height_m": (20, 55), "dbh_cm": (20, 90),  "age_years": (30, 300)},
    "Fagus sylvatica":    {"height_m": (25, 45), "dbh_cm": (30, 150), "age_years": (50, 400)},
    "Acer platanoides":   {"height_m": (12, 25), "dbh_cm": (15, 60),  "age_years": (20, 120)},
    "Fraxinus excelsior": {"height_m": (15, 35), "dbh_cm": (20, 80),  "age_years": (30, 200)},
    "Larix decidua":      {"height_m": (20, 50), "dbh_cm": (20, 100), "age_years": (30, 400)},
    "Populus tremula":    {"height_m": (10, 25), "dbh_cm": (10, 40),  "age_years": (10, 60)},
    "Alnus glutinosa":    {"height_m": (10, 30), "dbh_cm": (10, 50),  "age_years": (10, 100)},
    "Tilia cordata":      {"height_m": (15, 30), "dbh_cm": (20, 80),  "age_years": (30, 300)},
    "Ulmus glabra":       {"height_m": (15, 35), "dbh_cm": (20, 90),  "age_years": (30, 250)},
}

ZONING_VALUE_RANGES = {
    "Residential":  (150_000,   600_000),
    "Commercial":   (800_000, 5_000_000),
    "Industrial":   (500_000, 3_000_000),
    "Agricultural":  (20_000,   200_000),
    "Mixed-Use":    (300_000, 1_500_000),
    "Conservation":  (10_000,   100_000),
}

ZONING_STATUS_WEIGHTS = {
    "Residential":  ["Registered", "Registered", "Registered", "Pending",    "Disputed"],
    "Commercial":   ["Registered", "Registered", "Registered", "Registered", "Pending"],
    "Industrial":   ["Registered", "Registered", "Pending",    "Pending",    "Foreclosed"],
    "Agricultural": ["Registered", "Pending",    "Disputed",   "Disputed",   "Registered"],
    "Mixed-Use":    ["Registered", "Registered", "Pending",    "Disputed",   "Registered"],
    "Conservation": ["Registered", "Registered", "Registered", "Pending",    "Registered"],
}

TELECOM_PROVIDERS = [
    "Airtel", "Jio", "Vi (Vodafone Idea)", "BSNL", "Indus Towers",
    "American Tower", "SBA Communications", "Crown Castle",
    "Cellnex", "Vantage Towers",
]


class AttributeGenerator:
    """Generates realistic attribute tables with domain-aware correlated values."""

    FACILITIES = ["Substation", "Transmitter", "Collector", "Gateway", "Repeater",
                  "Node", "Hub", "Terminal", "Junction", "Control Point"]
    STREETS = ["Pine St", "Oak Rd", "Maple Ave", "Main St", "Cedar Ln",
               "Elm Blvd", "View Rd", "Forest Dr", "Ridge Way", "Valley Rd"]
    CATEGORIES = ["Type A", "Type B", "Type C", "Standard", "Premium", "Legacy"]
    STATUSES = ["Active", "Planned", "Maintenance", "Decommissioned"]

    @staticmethod
    def generate_row(idx, rnd, schema, row_context=None):
        """Generates a single attribute row from schema rules.

        Args:
            idx (int): 0-based sequential row index.
            rnd (random.Random): Seeded random generator.
            schema (list): List of field definition dicts.
            row_context (dict): Already-generated values for correlation lookup.
        """
        row = dict(row_context) if row_context else {}
        for field in schema:
            field_name = field["name"]
            field_type = field["type"]
            if field_name in row:
                continue
            if field_type == "SequentialID":
                row[field_name] = idx + 1
            elif field_type == "Name":
                prefix = field.get("prefix", "")
                choices = field.get("choices", [])
                if choices:
                    row[field_name] = rnd.choice(choices)
                elif prefix:
                    row[field_name] = f"{prefix}_{idx + 1:04d}"
                else:
                    facility = rnd.choice(AttributeGenerator.FACILITIES)
                    street = rnd.choice(AttributeGenerator.STREETS)
                    row[field_name] = f"{facility} {street}"
            elif field_type == "Category":
                choices = field.get("choices", AttributeGenerator.CATEGORIES)
                row[field_name] = rnd.choice(choices)
            elif field_type == "Numeric":
                val_min = field.get("min", 0.0)
                val_max = field.get("max", 100.0)
                is_int = field.get("integer", False)
                if is_int:
                    row[field_name] = rnd.randint(int(val_min), int(val_max))
                else:
                    row[field_name] = round(rnd.uniform(val_min, val_max), 3)
            elif field_type == "Date":
                start_year = field.get("start_year", 2015)
                end_year = field.get("end_year", 2026)
                start_dt = datetime.datetime(start_year, 1, 1)
                end_dt = datetime.datetime(end_year, 12, 31)
                delta_seconds = int((end_dt - start_dt).total_seconds())
                offset = rnd.randint(0, delta_seconds)
                target_dt = start_dt + datetime.timedelta(seconds=offset)
                row[field_name] = target_dt.strftime("%Y-%m-%d")
            elif field_type == "Year":
                start_year = field.get("start_year", 1990)
                end_year = field.get("end_year", 2024)
                row[field_name] = rnd.randint(start_year, end_year)
            elif field_type == "Status":
                choices = field.get("choices", AttributeGenerator.STATUSES)
                row[field_name] = rnd.choice(choices)
            else:
                row[field_name] = None
        return row

    # =========================================================================
    # Domain-Aware Correlated Row Generators
    # =========================================================================

    @staticmethod
    def _generate_parcel_row(idx, rnd, schema):
        """Parcel: zoning_class drives land_value_usd range and registry_status weights."""
        row = {}
        zoning = None
        for field in schema:
            if field["name"] == "zoning_class":
                zoning = rnd.choice(field.get("choices", list(ZONING_VALUE_RANGES.keys())))
                row["zoning_class"] = zoning
                break
        for field in schema:
            if field["name"] == "land_value_usd":
                lo, hi = ZONING_VALUE_RANGES.get(zoning, (50_000, 500_000))
                row["land_value_usd"] = round(rnd.uniform(lo, hi), 2)
                break
        for field in schema:
            if field["name"] == "registry_status":
                choices = ZONING_STATUS_WEIGHTS.get(
                    zoning, ["Registered", "Pending", "Disputed", "Foreclosed"])
                row["registry_status"] = rnd.choice(choices)
                break
        return AttributeGenerator.generate_row(idx, rnd, schema, row)

    @staticmethod
    def _generate_forestry_row(idx, rnd, schema):
        """Forestry: species drives height_m, dbh_cm, and age_years biometric ranges."""
        row = {}
        species = None
        for field in schema:
            if field["name"] == "species_scientific":
                species = rnd.choice(field.get("choices", list(SPECIES_PROFILES.keys())))
                row["species_scientific"] = species
                break
        profile = SPECIES_PROFILES.get(species, {})
        for field in schema:
            fname = field["name"]
            if fname == "height_m" and "height_m" in profile:
                lo, hi = profile["height_m"]
                row["height_m"] = round(rnd.uniform(lo, hi), 1)
            elif fname == "dbh_cm" and "dbh_cm" in profile:
                lo, hi = profile["dbh_cm"]
                row["dbh_cm"] = round(rnd.uniform(lo, hi), 1)
            elif fname == "age_years" and "age_years" in profile:
                lo, hi = profile["age_years"]
                row["age_years"] = rnd.randint(lo, hi)
        return AttributeGenerator.generate_row(idx, rnd, schema, row)

    @staticmethod
    def _generate_telecom_row(idx, rnd, schema):
        """Telecom: tower_type (Macro vs Microcell) drives height, which drives coverage_km."""
        row = {}
        tower_type = None
        for field in schema:
            if field["name"] == "tower_type":
                tower_type = rnd.choice(field.get("choices", ["Monopole", "Lattice", "Guyed Tower", "Stealth Tower", "Microcell"]))
                row["tower_type"] = tower_type
                break
        
        if tower_type is None:
            tower_type = rnd.choice(["Monopole", "Lattice", "Guyed Tower", "Stealth Tower"])
            row["tower_type"] = tower_type

        # Tower height driven by tower_type
        if tower_type == "Microcell":
            height_range = (10, 20)
        elif tower_type in ("Monopole", "Stealth Tower"):
            height_range = (25, 50)
        else:  # Lattice, Guyed Tower (Macro)
            height_range = (50, 120)

        tower_height = rnd.randint(height_range[0], height_range[1])
        row["tower_height_m"] = tower_height

        # Coverage is derived directly from tower_height
        for field in schema:
            if field["name"] == "coverage_km":
                if tower_type == "Microcell":
                    # Microcells have small, dense coverage (0.5 to 2.0 km)
                    base = tower_height * 0.08
                    noise = rnd.uniform(-0.15 * base, 0.15 * base)
                    row["coverage_km"] = round(max(0.5, min(2.0, base + noise)), 2)
                else:
                    # Macro cells coverage scale (height * coefficient)
                    base = tower_height * 0.15
                    noise = rnd.uniform(-0.10 * base, 0.10 * base)
                    row["coverage_km"] = round(base + noise, 2)
                break
        return AttributeGenerator.generate_row(idx, rnd, schema, row)

    @staticmethod
    def _generate_utility_row(idx, rnd, schema):
        """Utility: install_year age drives flow_status probability weighting."""
        row = {}
        install_year = None
        for field in schema:
            if field["name"] == "install_year":
                start = field.get("start_year", 1990)
                end = field.get("end_year", 2024)
                install_year = rnd.randint(start, end)
                row["install_year"] = install_year
                break
        for field in schema:
            if field["name"] == "flow_status":
                if install_year is not None:
                    age = 2026 - install_year
                    if age > 25:
                        choices = ["Maintenance", "Maintenance", "Leak Detected",
                                   "Restricted", "Flowing"]
                    elif age > 15:
                        choices = ["Flowing", "Flowing", "Restricted",
                                   "Maintenance", "Flowing"]
                    else:
                        choices = ["Flowing", "Flowing", "Flowing", "Flowing", "Restricted"]
                else:
                    choices = field.get("choices",
                                        ["Flowing", "Restricted", "Closed",
                                         "Backflow", "Leak Detected"])
                row["flow_status"] = rnd.choice(choices)
                break
        return AttributeGenerator.generate_row(idx, rnd, schema, row)

    # =========================================================================
    # Public API
    # =========================================================================

    @staticmethod
    def generate_attributes(count, seed, schema, template_hint=None):
        """Generates a complete list of attribute row dicts matching the schema.

        Args:
            count (int): Number of feature rows to generate.
            seed (int): Reproducibility seed value.
            schema (list): List of field rule dictionaries.
            template_hint (str): One of 'parcel', 'forestry', 'telecom', 'utility', or None.
        """
        rnd = random.Random(seed)
        correlated = {
            "parcel":   AttributeGenerator._generate_parcel_row,
            "forestry": AttributeGenerator._generate_forestry_row,
            "telecom":  AttributeGenerator._generate_telecom_row,
            "utility":  AttributeGenerator._generate_utility_row,
        }
        gen_fn = correlated.get(template_hint)
        rows = []
        for i in range(count):
            if gen_fn:
                rows.append(gen_fn(i, rnd, schema))
            else:
                rows.append(AttributeGenerator.generate_row(i, rnd, schema))
        return rows


