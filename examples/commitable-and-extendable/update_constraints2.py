"""Script to update CHP coupling constraints - simpler approach."""

# Read the file
file_path = r"c:\Users\A64620\Documents\pypsa_tryout\PyPSA\examples\commitable-and-extendable\committable_extendable_chp1.py"

with open(file_path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Find the start of the section to replace (line with "Nominal power proportionality")
start_idx = None
for i, line in enumerate(lines):
    if "Nominal power proportionality using output capacities" in line:
        start_idx = i
        break

if start_idx is None:
    print("ERROR: Could not find start marker")
    exit(1)

# Find the end (line before "n.optimize.solve_model")
end_idx = None
for i in range(start_idx, len(lines)):
    if "n.optimize.solve_model(" in lines[i]:
        end_idx = i
        break

if end_idx is None:
    print("ERROR: Could not find end marker")
    exit(1)

# Create the new section
new_section = '''    # ---------------------------
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
    )

'''

# Build the new file content
new_lines = lines[:start_idx] + [new_section] + lines[end_idx:]

# Write back
with open(file_path, 'w', encoding='utf-8') as f:
    f.writelines(new_lines)

print("✓ Constraints erfolgreich aktualisiert!")
print(f"  - Zeilen {start_idx+1} bis {end_idx} ersetzt")
print("  - Alte flexible Constraints entfernt")
print("  - Neue feste P/Q-Verhältnis Constraints hinzugefügt")
