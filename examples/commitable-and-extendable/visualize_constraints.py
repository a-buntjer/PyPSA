"""Visualisierung der neuen CHP-Constraints."""

import matplotlib.pyplot as plt
import numpy as np

# Parameter
BCHP_ELECTRIC_EFF = 0.38
BCHP_THERMAL_EFF = 0.48
BCHP_QP_RATIO = BCHP_THERMAL_EFF / BCHP_ELECTRIC_EFF

# Brennstoff-Input Bereich
gen_p = np.linspace(0, 10, 100)

# Mit neuen Constraints: boiler_p = gen_p (1:1 Verhältnis)
boiler_p = gen_p

# Output-Leistungen
electric_output = BCHP_ELECTRIC_EFF * gen_p
thermal_output = BCHP_THERMAL_EFF * boiler_p

# Q/P Verhältnis
qp_ratio = np.ones_like(gen_p) * BCHP_QP_RATIO

# Erstelle Figure mit 3 Subplots
fig, axes = plt.subplots(2, 2, figsize=(14, 10))
fig.suptitle('CHP-Constraints: Festes Q/P-Verhältnis', fontsize=16, fontweight='bold')

# Plot 1: Brennstoff-Input
ax1 = axes[0, 0]
ax1.plot(gen_p, gen_p, 'b-', linewidth=2, label='Generator Input')
ax1.plot(gen_p, boiler_p, 'r--', linewidth=2, label='Boiler Input')
ax1.set_xlabel('Generator Input (MW)', fontsize=11)
ax1.set_ylabel('Brennstoff-Input (MW)', fontsize=11)
ax1.set_title('Brennstoff-Input-Verhältnis', fontsize=12, fontweight='bold')
ax1.legend(fontsize=10)
ax1.grid(True, alpha=0.3)
ax1.text(5, 2, f'boiler_p = {boiler_p[-1]/gen_p[-1]:.2f} × gen_p', 
         fontsize=11, bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8))

# Plot 2: Output-Leistungen
ax2 = axes[0, 1]
ax2.plot(gen_p, electric_output, 'b-', linewidth=2, label='Elektrisch (P)')
ax2.plot(gen_p, thermal_output, 'r-', linewidth=2, label='Thermisch (Q)')
ax2.fill_between(gen_p, 0, electric_output, alpha=0.3, color='blue', label='P-Bereich')
ax2.fill_between(gen_p, electric_output, electric_output + thermal_output, 
                  alpha=0.3, color='red', label='Q-Bereich')
ax2.set_xlabel('Generator Input (MW)', fontsize=11)
ax2.set_ylabel('Output-Leistung (MW)', fontsize=11)
ax2.set_title('Output-Leistungen', fontsize=12, fontweight='bold')
ax2.legend(fontsize=10)
ax2.grid(True, alpha=0.3)
total_eff = BCHP_ELECTRIC_EFF + BCHP_THERMAL_EFF
ax2.text(5, 6, f'η_el = {BCHP_ELECTRIC_EFF:.0%}\nη_th = {BCHP_THERMAL_EFF:.0%}\nη_total = {total_eff:.0%}', 
         fontsize=10, bbox=dict(boxstyle='round', facecolor='lightgreen', alpha=0.8))

# Plot 3: Q/P-Verhältnis
ax3 = axes[1, 0]
ax3.plot(electric_output, thermal_output, 'g-', linewidth=3, label='Betriebslinie')
ax3.plot(electric_output, BCHP_QP_RATIO * electric_output, 'k--', 
         linewidth=1, alpha=0.5, label=f'Q = {BCHP_QP_RATIO:.4f} × P')
ax3.set_xlabel('Elektrische Leistung P (MW)', fontsize=11)
ax3.set_ylabel('Thermische Leistung Q (MW)', fontsize=11)
ax3.set_title('Q-P-Diagramm (Betriebslinie)', fontsize=12, fontweight='bold')
ax3.legend(fontsize=10)
ax3.grid(True, alpha=0.3)
ax3.set_aspect('equal', adjustable='box')
ax3.text(1.5, 3.5, f'Festes Verhältnis:\nQ/P = {BCHP_QP_RATIO:.4f}', 
         fontsize=11, bbox=dict(boxstyle='round', facecolor='yellow', alpha=0.8))

# Plot 4: Q/P-Verhältnis über Auslastung
ax4 = axes[1, 1]
load_factor = gen_p / gen_p.max()
ax4.plot(load_factor * 100, qp_ratio, 'purple', linewidth=3)
ax4.axhline(y=BCHP_QP_RATIO, color='k', linestyle='--', linewidth=1, alpha=0.5)
ax4.set_xlabel('Auslastung (%)', fontsize=11)
ax4.set_ylabel('Q/P-Verhältnis', fontsize=11)
ax4.set_title('Q/P-Verhältnis über Auslastung', fontsize=12, fontweight='bold')
ax4.set_ylim([1.0, 1.5])
ax4.grid(True, alpha=0.3)
ax4.fill_between(load_factor * 100, 1.0, 1.5, alpha=0.1, color='green')
ax4.text(50, 1.35, f'KONSTANT\nQ/P = {BCHP_QP_RATIO:.4f}', 
         fontsize=12, ha='center', fontweight='bold',
         bbox=dict(boxstyle='round', facecolor='lightblue', alpha=0.8))

# Markiere Mindestlast
min_load = 40  # 40% Mindestlast
ax4.axvline(x=min_load, color='red', linestyle=':', linewidth=2, alpha=0.7, label='Mindestlast')
ax4.legend(fontsize=10)

plt.tight_layout()
plt.savefig('chp_constraints_visualization.png', dpi=300, bbox_inches='tight')
print("✓ Grafik gespeichert: chp_constraints_visualization.png")
plt.show()

# Zusätzliche Detailanalyse
print("\n" + "="*80)
print("DETAILANALYSE DER CONSTRAINTS")
print("="*80)

test_loads = [0.4, 0.5, 0.75, 1.0]  # 40%, 50%, 75%, 100% Last
print(f"\nBei gen_p_nom = 10 MW:")
print(f"{'Last':<10} {'gen_p':<10} {'boiler_p':<12} {'P_out':<10} {'Q_out':<10} {'Q/P':<10}")
print("-"*80)

for load in test_loads:
    gp = 10 * load
    bp = gp  # Mit neuen Constraints: 1:1 Verhältnis
    p_out = BCHP_ELECTRIC_EFF * gp
    q_out = BCHP_THERMAL_EFF * bp
    qp = q_out / p_out if p_out > 0 else 0
    
    print(f"{load*100:>6.0f}%    {gp:>8.2f}    {bp:>10.2f}    {p_out:>8.2f}    {q_out:>8.2f}    {qp:>8.4f}")

print("\n✓ Alle Laststufen haben Q/P = {:.4f}".format(BCHP_QP_RATIO))
print("="*80)
