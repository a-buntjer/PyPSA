"""Script to update CHP coupling constraints."""

import re

# Read the file
file_path = r"c:\Users\A64620\Documents\pypsa_tryout\PyPSA\examples\commitable-and-extendable\committable_extendable_chp1.py"

with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Define the old function text pattern (using regex to handle whitespace variations)
old_pattern = r'''    # Nominal power proportionality using output capacities\.

    model\.add_constraints\(
        generator_eff \* BCHP_QP_RATIO \* generator_p_nom
        - boiler_eff \* boiler_p_nom
        == 0,
        name="chp-heat-capacity-proportionality",
    \)

    # ---------------------------
    # BHKW: \(fast\) starre P/Q-Kopplung
    # ---------------------------
    RHO = float\(BCHP_QP_RATIO\)
    RHO_LOW = RHO \* \(1\.0 - BCHP_COUPLING_BAND\)
    RHO_HIGH = RHO \* \(1\.0 \+ BCHP_COUPLING_BAND\)

    # # elektrische Nenn-OUTPUT-Kapazität \(als Referenz, linear in Variablen\):
    electric_output_nom = generator_eff \* generator_p_nom  # \[MW_el,nom\]

    # # Untere Bandgrenze: Q >= RHO_LOW \* P  \(fast „starr" nach unten\)
    model\.add_constraints\(
        heat_output - RHO_LOW \* electric_output >= 0,
        name="bhkw-lower-coupling",
    \)

    # # Obere Bandgrenze: Q <= RHO_HIGH \* P \+ BIAS \* \(P_nom - P\)
    # # -> In Teillast \(P < P_nom\) ist „etwas mehr Wärme" erlaubt\.
    model\.add_constraints\(
        heat_output
        - RHO_HIGH \* electric_output
        - BCHP_THERMAL_BIAS \* \(electric_output_nom - electric_output\)
        <= 0,
        name="bhkw-upper-coupling",
    \)

    # FIX: Status-Synchronisation ENTFERNT
    # Da chp_boiler jetzt nicht mehr committable ist \(committable=False\),
    # gibt es keine status-Variable für chp_boiler mehr\.
    # Die Status-Synchronisation war das Hauptproblem: Sie erzwang gleiche on/off states,.*?
    # aber mit unterschiedlichen p_min_pu Werten \(Generator 40%, Boiler 10%\) entstand.*?
    # eine mathematische Übereinschränkung\.
    # if link_status is not None:
    #     # Synchronise commitment state of CHP links \(nur wenn beide committable sind\)\..*?
    #     if "chp_boiler" in link_status\.coords\["name"\]\.values:
    #         model\.add_constraints\(
    #             link_status\.loc\[:, "chp_generator"\]
    #             - link_status\.loc\[:, "chp_boiler"\]
    #             == 0,
    #             name="chp-status-synchronisation",
    #         \)'''

new_text = '''    # ---------------------------
    # FESTES P/Q-VERHÄLTNIS für BHKW
    # ---------------------------
    # Erzwingt ein starres Verhältnis zwischen elektrischer und thermischer Leistung,
    # sowohl in Teillast als auch in Volllast: Q = RHO * P

    # CONSTRAINT 1: Nominale Kapazitäts-Proportionalität
    # Die nominalen Kapazitäten müssen im Verhältnis Q_nom/P_nom = RHO stehen
    # Q_nom = boiler_eff * boiler_p_nom
    # P_nom = generator_eff * generator_p_nom
    # Daraus folgt: boiler_eff * boiler_p_nom = RHO * generator_eff * generator_p_nom

    model.add_constraints(
        boiler_eff * boiler_p_nom - BCHP_QP_RATIO * generator_eff * generator_p_nom == 0,
        name="chp-nominal-capacity-ratio",
    )

    # CONSTRAINT 2: Festes Q/P-Verhältnis zu jedem Zeitpunkt
    # Erzwingt: Q(t) = RHO * P(t) für alle Zeitpunkte (Teillast und Volllast)
    # heat_output(t) = BCHP_QP_RATIO * electric_output(t)
    # boiler_eff * boiler_p(t) = BCHP_QP_RATIO * generator_eff * generator_p(t)

    model.add_constraints(
        heat_output - BCHP_QP_RATIO * electric_output == 0,
        name="chp-fixed-power-ratio",
    )'''

# Replace using regex
content_new = re.sub(old_pattern, new_text, content, flags=re.DOTALL)

# Write back
with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content_new)

print("✓ Constraints erfolgreich aktualisiert!")
print("  - Alte flexible Constraints entfernt")
print("  - Neue feste P/Q-Verhältnis Constraints hinzugefügt")
